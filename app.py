from flask import Flask, render_template, request, jsonify, make_response, send_from_directory, abort
from flask_socketio import SocketIO, emit
from apscheduler.schedulers.background import BackgroundScheduler
import base64, time, json, re, os, uuid, threading, requests, smtplib, sys
import http.client
import get_xinhuanet
from datetime import datetime, timedelta
from pathlib import Path
from openai import OpenAI
from bs4 import BeautifulSoup

app = Flask(__name__) # 创建 Flask 应用
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# 存储路径定义
HIGHLIGHTS_FILE = './data/highlights.json'
CHAT_HISTORY_FILE = './data/chat_history.json'
VARS_FILE = './data/variables.json'
IMAGE_STORAGE_PATH = './data/images/'

# 初始化 存储聊天消息的列表（最多保留300条）
chat_history = []
history_lock = threading.Lock()

# 初始化 精华消息列表
highlights = []
if os.path.exists(HIGHLIGHTS_FILE):
    with open(HIGHLIGHTS_FILE, 'r', encoding='utf-8') as f:
        highlights = json.load(f)

# 初始化 IP地理位置缓存列表
ip_location_cache = {}
ip_location_lock = threading.Lock()

# 密码配置
with open('secrets.json', 'r', encoding='utf-8') as f:
    data_secret = json.load(f)
    if data_secret.get('manage','') != '':
        SECRET_PASSWORD = data_secret.get('manage','')
    else:
        # 如果没有设置密码，则使用默认密码
        SECRET_PASSWORD = "1919810"

# 可配置变量定义 （在这里添加需要在manage页面配置的变量）
CONFIG_VARS = {
    'admin_ips': {
        'default': ["127.0.0.1", "223.160.176.6", "27.225.45.194"],
        'description': "管理员IP列表",
        'type': 'array'
    },
    'blocked_ips': {
        'default': [],
        'description': "限制发言IP列表",
        'type': 'array'
    },
    'banned_ips': {
        'default': [],
        'description': "禁止访问IP列表",
        'type': 'array'
    },
    'info_bar_content':{
        'default': "注意：仅保留最近300条消息 • 图片限制2MB以内 • 测试中<br>仅供个人学习交流使用，受邀才可使用，严禁公开服务器IP，严禁发布违法内容，严禁故意损坏服",
        'description': "聊天页面顶端提示文字",
        'type': 'string'
    },
    'ai_system': {
        'default': "你是一个聊天机器人，请注意遵守法律法规、规避敏感话题！",
        'description': "AI的System参数",
        'type': 'string'
    },
    'get_news_time':{
        'default': '300',  # 默认每5分钟获取一次新闻
        'description': "获取新闻的时间间隔（单位：秒）",
        'type': 'string'
    }
}

# 当前配置变量值
config_values = {}

def AIChat(api_key=None, 
        message_text=None,
        base_url=None, 
        model_name=None):
    try:
        with open('secrets.json', 'r', encoding='utf-8') as f:
            secrets = json.load(f)
        if api_key is None:
            api_key = secrets["ai"][0]["key"]
        if model_name is None:
            model_name = secrets["ai"][0]["name"]
        if base_url is None:
            base_url = secrets["ai"][0]["base_url"]
        if message_text is None:
            message_text = "你好！"
        messages = [
            {'role': 'system', 'content': config_values.get('ai_system', " ")},
            {'role': 'user', 'content': message_text}
            ]
        client = OpenAI(api_key=api_key, base_url=base_url)
        # 模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
        completion = client.chat.completions.create(
            model=model_name,  
            messages=messages,
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"错误信息：{e}"

class Pages:
    """页面路由"""
    @staticmethod # 静态方法，避免每次请求都创建实例
    @app.before_request
    def check_banned_ip():
        """拦截禁止访问的IP"""
        banned_ips = config_values.get('banned_ips', [])
        user_ip = API.get_client_ip() # 获取用户IP地址
        if user_ip in banned_ips:
            return "<br><br><h3>您的IP已被禁止访问，如有疑问，请联系bright2024_2035@163.com</h3>", 403

    @app.route('/')
    def home():
        """主页路由"""
        return render_template('home.html')
    
    @app.route('/chat')
    def chat_html():
        """聊天室页面"""
        username = request.cookies.get('username', '') # 获取用户名cookie（如果存在）
        # 如果是匿名或不存在，则默认为空
        if username == '匿名':
            username = ''
        
        # 从配置中获取聊天室标题和信息栏内容
        chat_title = config_values.get('chat_title', '简易临时在线聊天室')
        info_bar_content = config_values.get('info_bar_content', '本站测试中，仅供技术学习和练习，请勿滥用')
        
        resp = make_response(render_template('chat.html', chat_title=chat_title, info_bar_content=info_bar_content))
        
        # 如果用户已经设置过用户名，则保留原来的cookie
        if username:
            resp.set_cookie('username', username, max_age=60*60*24*30)  # 保存30天
        return resp

    @app.route('/manage')
    def manage_html():
        """管理页面"""
         # 只渲染变量，不做权限校验，前端可直接展示
        return render_template(
            'manage.html',
            config_vars=config_values,
            var_descriptions={name: data['description'] for name, data in CONFIG_VARS.items()},
            var_types={name: data.get('type', 'string') for name, data in CONFIG_VARS.items()}
        )
    
    @app.route('/news')
    def news():
        w="none"
        page = requests.get("http://news.cn/")
        soup = BeautifulSoup(page.content, 'html.parser')
        w = soup.find_all(class_="part bg-white")[0]
        m = [(a['href'], a.get_text()) for a in w.find_all('a') if 'href' in a.attrs]
        return render_template('news.html',w=w,links=m)
    
    @app.route('/restart/<password>')
    def restart_app(password):
        """重启 Flask 应用（开发环境用）"""
        global SECRET_PASSWORD
        if password != SECRET_PASSWORD:
            return jsonify({'status': 'error', 'message': '密码错误，无法重启！'}), 403
        threading.Thread(target=_restart_server).start()
        return jsonify({'status': 'success', 'message': '正在重启，请稍候...'})
    
class API:
    @staticmethod
    def get_news_message(lists=3):
        """获取新闻消息内容，返回消息对象"""
        time.sleep(2)
        try:
            text = get_xinhuanet.get_xinhuanet(lists=lists)  # 调用获取新闻的函数
            message = {
                'username': '新闻助手',
                'ip': '127.0.0.1',
                'message': text,
                'image': None,
                'timestamp': datetime.now().strftime("%H:%M:%S"),
                'sort_key': datetime.now().timestamp(),
                'location': '本地'
            }
            return message
        except Exception as e:
            app.logger.error(f"获取新闻失败: {str(e)}")
            return {
                'username': '新闻助手',
                'ip': '127.0.0.1',
                'message': f"新闻获取失败: {e}",
                'image': None,
                'timestamp': datetime.now().strftime("%H:%M:%S"),
                'sort_key': datetime.now().timestamp(),
                'location': '本地'
            }

    @staticmethod
    def get_ai_message(message_text):
        """获取AI回复消息内容，返回消息对象"""
        result = AIChat(message_text=message_text.replace("@ai", ""))
        ai_message = {
            'username': 'AI助手',
            'ip': '127.0.0.1',
            'message': result,
            'image': None,
            'timestamp': datetime.now().strftime("%H:%M:%S"),
            'sort_key': datetime.now().timestamp(),
            'location': '本地'
        }
        return ai_message
    
    @app.route('/api/check_password', methods=['POST'])
    def check_password():
        """验证密码"""
        try:
            password = request.form.get('password', '').strip() # 获取表单提交的密码
            if not password:
                return jsonify({'status': 'error', 'message': '没有收到密码，无法验证！'}), 400
            if password == SECRET_PASSWORD: # 密码正确时
                # 返回所有配置变量及其描述和类型
                return jsonify({
                    'status': 'success',
                    'config_vars': config_values,
                    'var_descriptions': {name: data['description'] for name, data in CONFIG_VARS.items()},
                    'var_types': {name: data.get('type', 'string') for name, data in CONFIG_VARS.items()}
                })
            else:
                return jsonify({'status': 'error', 'message': '密码错误，请重试！'})
        except Exception as e:
            app.logger.error(f"验证密码时出错: {str(e)}")
            return jsonify({'status': 'error', 'message': f'服务器错误: {str(e)}'}), 500

    def get_client_ip():
        """获取客户端真实IP（兼容代理服务器）"""
        # 尝试从各种可能的请求头中获取真实IP
        if request.environ.get('HTTP_X_REAL_IP'):
            return request.environ.get('HTTP_X_REAL_IP')
        elif request.environ.get('HTTP_X_FORWARDED_FOR'):
            # X-Forwarded-For可能包含多个IP，取第一个
            forwarded_for = request.environ.get('HTTP_X_FORWARDED_FOR').split(',')[0].strip()
            if forwarded_for:
                return forwarded_for
        elif request.headers.getlist("X-Forwarded-For"):
            return request.headers.getlist("X-Forwarded-For")[0].split(',')[0]
        elif request.environ.get('HTTP_X_FORWARDED'):
            return request.environ.get('HTTP_X_FORWARDED')
        elif request.environ.get('HTTP_X_CLUSTER_CLIENT_IP'):
            return request.environ.get('HTTP_X_CLUSTER_CLIENT_IP')
        elif request.environ.get('HTTP_FORWARDED_FOR'):
            return request.environ.get('HTTP_FORWARDED_FOR')
        elif request.environ.get('HTTP_FORWARDED'):
            return request.environ.get('HTTP_FORWARDED')
        
        # 如果以上都失败，使用REMOTE_ADDR
        return request.remote_addr or 'unknown'
    
    def get_ip_location(ip):
        """获取IP的地理位置信息"""
        # 特殊处理本地IP和未知IP
        if ip == '127.0.0.1':
            return "本地"
        if ip == '124.23.134.28':
            return "陕西的abandon"
        if ip == 'unknown':
            return "未知"
        
        # 检查缓存中是否有该IP的地理位置
        with ip_location_lock:
            if ip in ip_location_cache:
                return ip_location_cache[ip]
        
        try:
            url = f"https://ip9.com.cn/get?ip={ip}"
            payload={}
            headers = {}
            response = requests.request("GET", url, headers=headers, data=payload)
            data = response.json()
            try:
                # 提取国家、省份和城市信息
                country = data['data'].get('country', '')
                region = data['data'].get('prov', '')
                
                # 优先显示省份，其次是国家
                if country != "中国":
                    location = country
                else:
                    location = region or country or '不明'
                
                # 将结果存入缓存
                with ip_location_lock:
                    ip_location_cache[ip] = location
                
                return location
            except KeyError as e:
                return f"解析IP地理位置失败: {str(e)}"
        except Exception as e:
            app.logger.error(f"获取地理位置失败: {str(e)}")
            return '未知'
    
    def mask_ip(ip):
        """对IP地址进行打码处理 (127.*.0.1 格式)"""
        if not ip:
            return ""
        
        # 使用正则表达式匹配IPv4地址
        ipv4_pattern = r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
        match = re.match(ipv4_pattern, ip)
        if match:
            return f"{match.group(1)}.*.{match.group(3)}.{match.group(4)}"
        
        return ip


class File:
    """文件相关API"""
    @staticmethod
    @app.route('/image/<filename>')
    def serve_image(filename):
        """提供图片文件服务"""
        try:
            return send_from_directory(IMAGE_STORAGE_PATH, filename)
        except Exception as e:
            app.logger.error(f"提供图片文件时出错: {str(e)}")
            return abort(404)
        
    def check_image(filename):
        """检查文件扩展名是否为允许的图片"""
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions



class Message:
    """消息相关函数"""

    def __init__(self):
        pass
    
    @staticmethod
    @socketio.on('send_message')
    def handle_send_message(data):
        """处理发送消息的SocketIO事件"""
        global chat_history, history_lock, config_values
        try:
            username = data.get('username', '匿名').strip()
            message = data.get('message', '').strip()
            user_ip = API.get_client_ip()
            blocked_ips = config_values.get('blocked_ips', [])
            if user_ip != 'unknown' and user_ip in blocked_ips:
                emit('error', {'message': '您的IP已被限制发言'})
                return

            timestamp = datetime.now().strftime("%H:%M:%S")
            timestamp_sort = datetime.now().timestamp()
            image_filename = None

            # 处理 base64 图片
            image_data = data.get('image')
            if image_data:
                try:
                    header, encoded = image_data.split(',', 1)
                    img_bytes = base64.b64decode(encoded)
                    if len(img_bytes) > 20 * 1024 * 1024:
                        emit('error', {'message': '图片大小不能超过20MB'})
                        return
                    ext = 'png' if 'png' in header else 'jpg'
                    image_filename = f"{uuid.uuid4().hex}.{ext}"
                    file_path = os.path.join(IMAGE_STORAGE_PATH, image_filename)
                    with open(file_path, 'wb') as f:
                        f.write(img_bytes)
                except Exception as e:
                    app.logger.error(f"图片保存失败: {str(e)}")
                    image_filename = None

            if not message and not image_filename:
                emit('error', {'message': '消息内容不能为空'})
                return

            location = API.get_ip_location(user_ip) if user_ip != 'unknown' else '未知'
            message_obj = {
                'username': username,
                'ip': user_ip,
                'message': message,
                'image': image_filename,
                'image_url': f"/image/{image_filename}" if image_filename else None,
                'timestamp': timestamp,
                'sort_key': timestamp_sort,
                'location': location
            }

            with history_lock:
                chat_history.append(message_obj)
                Message.save_messages()
                if len(chat_history) > 300:
                    removed_message = chat_history.pop(0)
                    # 图片删除略
                    Message.save_messages()            
            
            socketio.emit('new_message', message_obj, namespace='/')  # 广播新消息给所有连接的客户端

            emit('new_message', message_obj, namespace='/', room=request.sid)  # 仅发送给当前用户

            # 异步处理 @ai 和 @news 指令
            if "@ai" in message:
                def send_ai():
                    ai_msg = API.get_ai_message(message)  # 获取AI消息
                    with history_lock:
                        chat_history.append(ai_msg)
                        Message.save_messages()
                    socketio.emit('new_message', ai_msg, namespace='/')  # 实时推送AI消息
                socketio.start_background_task(send_ai)  # 使用 Flask-SocketIO 的后台任务
            elif "@news" in message:
                lists=3
                if "/1" in message:
                    lists = 1
                elif "/2" in message:
                    lists = 2
                def send_news():
                    news_msg = API.get_news_message(lists=lists)  # 获取新闻消息
                    with history_lock:
                        chat_history.append(news_msg)
                        Message.save_messages()
                    socketio.emit('new_message', news_msg, namespace='/')  # 实时推送新闻消息
                socketio.start_background_task(send_news)  # 使用 Flask-SocketIO 的后台任务        
        except Exception as e:
            emit('error', {'message': f'服务器错误: {str(e)}'})

    @socketio.on('connect')
    def handle_connect():
        user_ip = API.get_client_ip()
        emit('user_ip', user_ip)
        # 推送最近50条历史消息
        with history_lock:
            sorted_history = sorted(chat_history, key=lambda x: x['sort_key'])
            emit('history', sorted_history[-50:])

    @socketio.on('delete_message')
    def handle_delete_message(data):
        message_id = data.get('message_id')
        user_ip = API.get_client_ip()
        admin = config_values.get('admin_ips', [])
        with history_lock:
            for i, msg in enumerate(chat_history):
                if msg['sort_key'] == message_id:
                    # 检查用户是否有权限删除消息（管理员或消息发送者）
                    # 如果无法获取IP，允许管理员操作
                    if (user_ip != 'unknown' and user_ip not in admin) and (msg['ip'] != 'unknown' and user_ip != msg['ip']):
                        emit('error', {'message': '无权删除此消息'})
                        return
                    if msg.get('image'):
                        image_path = os.path.join(IMAGE_STORAGE_PATH, msg['image'])
                        if os.path.exists(image_path):
                            try:
                                os.remove(image_path)
                            except Exception as e:
                                app.logger.error(f"删除图片文件失败: {str(e)}")
                    del chat_history[i]
                    Message.save_messages()
                    emit('message_deleted', {'message_id': message_id}, broadcast=True)
                    return
        emit('error', {'message': '消息不存在'})

    @socketio.on('toggle_highlight')
    def handle_toggle_highlight(data):
        message_id = data.get('message_id')
        user_ip = API.get_client_ip()
        with history_lock:
            is_highlighted = any(h['sort_key'] == message_id for h in highlights)
            if is_highlighted:
                highlights[:] = [h for h in highlights if h['sort_key'] != message_id]
            else:
                for msg in chat_history:
                    if msg['sort_key'] == message_id:
                        highlight_msg = msg.copy()
                        highlight_msg['highlighted_at'] = datetime.now().timestamp()
                        highlights.append(highlight_msg)
                        break
            Message.save_highlights()
            Message.save_messages()
            emit('highlight_toggled', {'message_id': message_id, 'is_highlighted': not is_highlighted}, broadcast=True)

    @app.route('/message/get_highlights')
    def get_highlights(): # 目前还保留使用
        """获取所有精华消息"""
        try:
            # 按设置时间倒序排列
            sorted_highlights = sorted(highlights, key=lambda x: x['highlighted_at'], reverse=True)
            return jsonify({'highlights': sorted_highlights})
        except Exception as e:
            app.logger.error(f"获取精华消息失败: {str(e)}")
            return jsonify({'status': 'error', 'message': f'获取精华失败: {str(e)}'}), 500
    
    def load_messages():
        """从文件加载聊天记录"""
        if os.path.exists(CHAT_HISTORY_FILE):
            with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    def save_messages():
        """保存聊天记录"""
        with open(CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(chat_history, f, ensure_ascii=False, indent=2)

    def save_highlights():
        """保存精华消息记录"""
        with open(HIGHLIGHTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(highlights, f, ensure_ascii=False, indent=2)


class Config:
    """配置相关函数"""

    @app.route('/config/get_config')
    def get_config():
        global config_values
        return jsonify({
            'admin_ips': config_values.get('admin_ips', []),
            'blocked_ips': config_values.get('blocked_ips', [])
        })
    
    def save():
        """保存配置变量到文件"""
        global config_values
        try:
            with open(VARS_FILE, 'w', encoding='utf-8') as f:
                json.dump(config_values, f, ensure_ascii=False, indent=2)
        except Exception as e:
            app.logger.error(f"保存配置变量失败: {str(e)}")
    
    @app.route('/config/update_variables', methods=['POST'])
    def update_variables():
        """更新配置变量"""
        global config_values
        try:
            data = request.get_json() # 获取JSON数据
            password = data.pop('_password', None) # 取出密码字段
            if not password or password != SECRET_PASSWORD:
                return jsonify({'status': 'error', 'message': '密码错误，无法保存！'}), 403
            if not data:
                return jsonify({'status': 'error', 'message': '无效的JSON数据'}), 400
                
            # 更新所有接收到的变量
            for name, value in data.items(): # 遍历所有变量
                if name in CONFIG_VARS: # 检查变量是否在配置中定义
                    var_type = CONFIG_VARS[name].get('type', 'string') # 获取变量类型，默认为字符串
                    # 根据变量类型处理值
                    if var_type == 'array': # 如果是数组类型
                        if isinstance(value, str): # 如果是字符串，尝试解析为JSON或逗号分隔的列表
                            try:
                                config_values[name] = json.loads(value) # 尝试解析为JSON
                            except json.JSONDecodeError:
                                config_values[name] = [item.strip() for item in value.split(',') if item.strip()] # 确保是列表
                        elif isinstance(value, list): # 如果是列表类型
                            config_values[name] = value # 确保是列表
                        else:
                            config_values[name] = [value] if value else [] # 空值处理为列表
                    else:
                        config_values[name] = value # 其他类型直接赋值
            
            Config.save() # 保存到文件
            
            # 返回更新后的值
            return jsonify({
                'status': 'success',
                'config_vars': config_values,
                'var_descriptions': {name: data['description'] for name, data in CONFIG_VARS.items()},
                'var_types': {name: data.get('type', 'string') for name, data in CONFIG_VARS.items()}
            })
        except Exception as e:
            app.logger.error(f"更新变量时出错: {str(e)}", exc_info=True)
            return jsonify({'status': 'error', 'message': f'更新失败: {str(e)}'}), 500
    
    def load_config_vars():
        """从文件加载配置变量"""
        global config_values
        if os.path.exists(VARS_FILE):
            try:
                with open(VARS_FILE, 'r', encoding='utf-8') as f:
                    saved_vars = json.load(f)
                    # 合并保存的变量和默认配置
                    config_values = {
                        name: saved_vars.get(name, data['default'])
                        for name, data in CONFIG_VARS.items()
                    }
            except Exception as e:
                app.logger.error(f"加载配置变量失败: {str(e)}")
                config_values = {name: data['default'] for name, data in CONFIG_VARS.items()}
        else:
            config_values = {name: data['default'] for name, data in CONFIG_VARS.items()}

class Log:
    @app.route('/log')
    def view_log():
        """在线查看操作日志"""
        # 获取筛选参数
        date_range = request.args.get('date_range', '1')
        operator_ip = request.args.get('operator_ip', '').strip()
        target_ip = request.args.get('target_ip', '').strip()
        action = request.args.get('action', '').strip()
        operator_location = request.args.get('operator_location', '').strip()
        target_location = request.args.get('target_location', '').strip()
        content = request.args.get('content', '').strip()
        result = request.args.get('result', '').strip()
        level = request.args.get('level', '').strip()
        page = int(request.args.get('page', 1))
        page_size = 30

        # 计算日期范围
        end_date = datetime.now()
        if date_range == 'all':
            start_date = None
        else:
            start_date = end_date - timedelta(days=int(date_range))

        # 加载日志文件
        log_dir = './data'
        logs = []
        operator_ips = set()
        target_ips = set()
        actions = set()
        operator_locations = set()
        target_locations = set()
        results = set()
        levels = set()
        for file_name in os.listdir(log_dir):
            if file_name.startswith('operation_') and file_name.endswith('.log'):
                file_date = datetime.strptime(file_name[10:-4], '%Y-%m-%d')
                if start_date and file_date < start_date:
                    continue
                with open(os.path.join(log_dir, file_name), 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            log = json.loads(line)
                            logs.append(log)
                            operator_ips.add(log.get('operator_ip', ''))
                            target_ips.add(log.get('target_ip', ''))
                            actions.add(log.get('action', ''))
                            operator_locations.add(log.get('operator_location', ''))
                            target_locations.add(log.get('target_location', ''))
                            results.add(log.get('result', ''))
                            levels.add(log.get('level', ''))
                        except Exception:
                            continue

        # 筛选日志
        if operator_ip:
            logs = [log for log in logs if log.get('operator_ip') == operator_ip]
        if target_ip:
            logs = [log for log in logs if log.get('target_ip') == target_ip]
        if action:
            logs = [log for log in logs if log.get('action') == action]
        if operator_location:
            logs = [log for log in logs if log.get('operator_location') == operator_location]
        if target_location:
            logs = [log for log in logs if log.get('target_location') == target_location]
        if content:
            logs = [log for log in logs if content in log.get('content', '')]
        if result:
            logs = [log for log in logs if log.get('result') == result]
        if level:
            logs = [log for log in logs if log.get('level') == level]

        # 分页
        total = len(logs)
        logs = logs[::-1]
        logs_page = logs[(page - 1) * page_size: page * page_size]
        total_pages = (total + page_size - 1) // page_size

        # 渲染 HTML
        return render_template(
            'log.html',
            logs=logs_page,
            page=page,
            total_pages=total_pages,
            date_range=date_range,
            operator_ip=operator_ip,
            target_ip=target_ip,
            action=action,
            operator_location=operator_location,
            target_location=target_location,
            content=content,
            result=result,
            level=level,
            operator_ips=sorted(operator_ips),
            target_ips=sorted(target_ips),
            actions=sorted(actions),
            operator_locations=sorted(operator_locations),
            target_locations=sorted(target_locations),
            results=sorted(results),
            levels=sorted(levels)
        )

    def operation(action, operator_ip, operator_location, target_ip, target_location, content, result='success', level='info'):
        """记录操作日志到本地文件（按天分割）"""
        log_dir = './data'
        log_file = os.path.join(log_dir, f'operation_{datetime.now().strftime("%Y-%m-%d")}.log')
        log_entry = {
            'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'action': action,
            'operator_ip': operator_ip,
            'operator_location': operator_location,
            'target_ip': target_ip,
            'target_location': target_location,
            'content': content,
            'result': result,
            'level': level
        }
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except Exception as e:
            app.logger.error(f"写入操作日志失败: {str(e)}")

pages = Pages()
api = API()
image_api = File()
message = Message()
config = Config()

def _restart_server():
    """重启进程"""
    time.sleep(1)
    os.execv(sys.executable, [sys.executable] + sys.argv) # 重启当前进程

def get_news_auto():
    """定时获取新闻并推送"""
    print("定时获取新闻任务开始")
    try:
        # 加载之前的新闻数据
        try:
            with open('./data/news.txt', 'r', encoding='utf-8') as f:
                news_data = json.load(f)
        except FileNotFoundError:
            news_data = " "

        # 获取最新新闻内容
        news_latest = get_xinhuanet.get_xinhuanet(lists=1)

        # 检测新闻内容是否有变化
        if news_data != news_latest:
            text = "新华网头条新闻有更新，"+ news_latest

            # 构造消息对象
            message = {
                'username': '新闻助手（定时发送）',
                'ip': '127.0.0.1',
                'message': text,
                'image': None,
                'timestamp': datetime.now().strftime("%H:%M:%S"),
                'sort_key': datetime.now().timestamp(),
                'location': '本地'
            }

            # 保存到聊天记录
            with history_lock:
                chat_history.append(message)
                Message.save_messages()

            # 保存最新新闻数据到文件
            with open('./data/news.txt', 'w', encoding='utf-8') as f:
                json.dump(news_latest, f, ensure_ascii=False, indent=4)

            # 实时推送新闻消息给所有在线用户
            socketio.emit('new_message', message, namespace='/')  # 直接使用 emit 推送消息
            print("定时新闻推送成功")
            app.logger.info("定时新闻推送成功")

        else:
            app.logger.info("新闻内容无变化，无需推送")

    except Exception as e:
        app.logger.error(f"(定时)获取新闻失败: {str(e)}")

# 调度器配置
Config.load_config_vars()  # 初始化时加载配置变量
scheduler = BackgroundScheduler()
scheduler.add_job(lambda: socketio.start_background_task(get_news_auto), 'interval', seconds=int(config_values.get('get_news_time', '300')))# 每n秒获取一次新闻
scheduler.start()

if __name__ == '__main__':
    Path('./data').mkdir(exist_ok=True) # 确保数据目录存在
    Path(IMAGE_STORAGE_PATH).mkdir(exist_ok=True)  # 创建图片存储目录
    chat_history = Message.load_messages() # 初始化时加载聊天记录 
    Config.load_config_vars() # 初始化时加载配置变量
    app.logger.info(f"初始配置: {config_values}") # 初始化时打印配置
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
    scheduler.shutdown()# 应用退出时关闭调度器