from flask import Flask, render_template, request, jsonify, make_response, send_from_directory, abort
import base64
import time,json,re,os
import uuid
import http.client
from datetime import datetime
import threading
import requests,smtplib
from pathlib import Path
from openai import OpenAI

app = Flask(__name__)

# 存储聊天消息的列表（最多保留300条）
chat_history = []
history_lock = threading.Lock()

# 存储路径定义
HIGHLIGHTS_FILE = './data/highlights.json'
CHAT_HISTORY_FILE = './data/chat_history.json'
VARS_FILE = './data/variables.json'
IMAGE_STORAGE_PATH = './data/images/'

# 创建数据目录
Path('./data').mkdir(exist_ok=True)

# 初始化精华消息列表
highlights = []
if os.path.exists(HIGHLIGHTS_FILE):
    with open(HIGHLIGHTS_FILE, 'r', encoding='utf-8') as f:
        highlights = json.load(f)

# IP地理位置缓存
ip_location_cache = {}
ip_location_lock = threading.Lock()

# 管理员IP
admin = ['127.0.0.1','223.160.176.6','27.225.45.194']

# 密码配置
SECRET_PASSWORD = "1919810"

# 配置变量定义 (可轻松添加更多变量)
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
}

# 当前配置变量值
config_values = {}

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

def save_config_vars():
    """保存配置变量到文件"""
    try:
        with open(VARS_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_values, f, ensure_ascii=False, indent=2)
    except Exception as e:
        app.logger.error(f"保存配置变量失败: {str(e)}")

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

def get_ip_location(ip):
    """获取IP的地理位置信息"""
    # 特殊处理本地IP
    if ip == '127.0.0.1':
        return "本地"
    if ip == '124.23.134.28':
        return "陕西的abandon"
    
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

def save_highlights():
    """保存精华消息到文件"""
    with open(HIGHLIGHTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(highlights, f, ensure_ascii=False, indent=2)

@app.route('/get_config')
def get_config():
    return jsonify({
        'admin_ips': config_values.get('admin_ips', []),
        'blocked_ips': config_values.get('blocked_ips', [])
    })

def get_client_ip():
    """获取客户端真实IP（兼容代理服务器）"""
    if request.headers.getlist("X-Forwarded-For"):
        return request.headers.getlist("X-Forwarded-For")[0].split(',')[0]
    return request.remote_addr

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def load_chat_history():
    """从文件加载聊天记录"""
    if os.path.exists(CHAT_HISTORY_FILE):
        with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_chat_history():
    """保存聊天记录到文件"""
    with open(CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(chat_history, f, ensure_ascii=False, indent=2)

@app.before_request
def check_banned_ip():
    """禁止访问的IP列表拦截"""
    banned_ips = config_values.get('banned_ips', [])
    user_ip = get_client_ip()
    if user_ip in banned_ips:
        return "<br><br><h3>您的IP已被禁止访问，如有疑问，请联系bright2024_2035@163.com</h3>", 403

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/chat')
def chat_html():
    """主页面"""
    # 获取用户名cookie（如果存在）
    username = request.cookies.get('username', '')
    # 如果是匿名或不存在，则默认为空
    if username == '匿名':
        username = ''
    
    # 从配置中获取聊天室标题和信息栏内容
    chat_title = config_values.get('chat_title', '简易临时在线聊天室')
    info_bar_content = config_values.get('info_bar_content', '注意：仅保留最近300条消息 • 图片限制2MB以内 • 测试中<br>仅供个人学习交流使用，受邀才可使用，严禁公开服务器IP，严禁发布违法内容，严禁故意损坏服务器')
    
    resp = make_response(render_template('chat.html', chat_title=chat_title, info_bar_content=info_bar_content))
    
    # 如果用户已经设置过用户名，则保留原来的cookie
    if username:
        resp.set_cookie('username', username, max_age=60*60*24*30)  # 保存30天
    return resp

@app.route('/manage')
def manage_html():
    """管理页面"""
    return render_template('manage.html')

@app.route('/check_password', methods=['POST'])
def check_password():
    """验证密码"""
    try:
        password = request.form.get('password', '').strip()
        if password == SECRET_PASSWORD:
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

@app.route('/update_variables', methods=['POST'])
def update_variables():
    """更新配置变量"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': '无效的JSON数据'}), 400
            
        # 更新所有接收到的变量
        for name, value in data.items():
            if name in CONFIG_VARS:
                var_type = CONFIG_VARS[name].get('type', 'string')
                # 根据变量类型处理值
                if var_type == 'array':
                    if isinstance(value, str):
                        try:
                            config_values[name] = json.loads(value)
                        except json.JSONDecodeError:
                            config_values[name] = [item.strip() for item in value.split(',') if item.strip()]
                    elif isinstance(value, list):
                        config_values[name] = value
                    else:
                        config_values[name] = [value] if value else []
                else:
                    config_values[name] = value
        
        # 保存到文件
        save_config_vars()
        
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

@app.route('/send_message', methods=['POST'])
def send_message():
    """处理消息发送请求"""
    try:
        # 获取用户提交的数据
        username = request.form.get('username', '匿名').strip() or '匿名'
        message = request.form.get('message', '').strip()
        user_ip = get_client_ip()

         # 检查是否在限制发言名单中
        blocked_ips = config_values.get('blocked_ips', [])
        if user_ip in blocked_ips:
            return jsonify({'status': 'error', 'message': '您的IP已被限制发言'}), 403
        
        
        # 获取当前时间
        timestamp = datetime.now().strftime("%H:%M:%S")
        timestamp_sort = datetime.now().timestamp()  # 用于排序的时间戳
        
        # 处理图片上传
        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                # 检查图片大小
                file.seek(0, os.SEEK_END)
                file_length = file.tell()
                file.seek(0)
                
                if file_length > 10 * 1024 * 1024:  # 限制2MB
                    return jsonify({'status': 'error', 'message': '图片大小不能超过10MB'}), 400
                
                # 保存图片到服务器本地
                file_extension = file.filename.rsplit('.', 1)[1].lower()
                image_filename = f"{uuid.uuid4().hex}.{file_extension}"
                file_path = os.path.join(IMAGE_STORAGE_PATH, image_filename)
                file.save(file_path)
        
        # 如果既没有消息也没有图片，则返回错误
        if not message and not image_filename:
            return jsonify({'status': 'error', 'message': '消息内容不能为空'}), 400
        
        # 获取IP地理位置
        location = get_ip_location(user_ip)
        
        # 创建消息对象
        message_obj = {
            'username': username,
            'ip': user_ip,
            'message': message,
            'image': image_filename,  # 只保存文件名，不保存base64数据
            'timestamp': timestamp,
            'sort_key': timestamp_sort,
            'location': location  # 地理位置信息
        }
        
        # 添加到聊天历史记录
        with history_lock:
            chat_history.append(message_obj)
            save_chat_history() 
            if "@ai" in message:
                threading.Thread(target=api_ai, args=(message,)).start()
            # 保持只保留最近的300条消息
            if len(chat_history) > 300:
                # 删除超出300条的最早消息中的图片文件
                removed_message = chat_history.pop(0)
                if removed_message.get('image'):
                    image_path = os.path.join(IMAGE_STORAGE_PATH, removed_message['image'])
                    if os.path.exists(image_path):
                        try:
                            os.remove(image_path)
                        except Exception as e:
                            app.logger.error(f"删除图片文件失败: {str(e)}")
                save_chat_history()  # 新增保存操作
        
        return jsonify({'status': 'success'})
    
    except Exception as e:
        app.logger.error(f"发送消息时出错: {str(e)}")
        return jsonify({'status': 'error', 'message': f'服务器错误: {str(e)}'}), 500
    
@app.route('/api/ai_chat/<message_text>')
def api_ai(message_text):
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
    chat_history.append(ai_message)
    save_chat_history()  # 新增保存操作

@app.route('/image/<filename>')
def serve_image(filename):
    """提供图片文件服务"""
    try:
        return send_from_directory(IMAGE_STORAGE_PATH, filename)
    except Exception as e:
        app.logger.error(f"提供图片文件时出错: {str(e)}")
        return abort(404)

@app.route('/get_messages')
def get_messages():
    """获取最新的聊天消息（按时间正序排列，最新的在底部）"""
    try:
        # 返回按时间正序排列的消息（最新的在最后）
        with history_lock:
            # 按时间戳排序（从小到大，最新的在最后）
            sorted_history = sorted(chat_history, key=lambda x: x['sort_key'])
            # 为图片消息添加图片URL和高度
            for msg in sorted_history:
                if msg.get('image'):
                    msg['image_url'] = f"/image/{msg['image']}"
                    # 获取图片高度（单位：像素），如果图片存在则读取实际高度，否则为None
                    try:
                        from PIL import Image # 使用PIL库读取图片高度
                        image_path = os.path.join(IMAGE_STORAGE_PATH, msg['image'])
                        with Image.open(image_path) as img:
                            msg['image_height'] = img.height
                    except Exception as e:
                        msg['image_height'] = None
            return jsonify({'messages': sorted_history})
    except Exception as e:
        app.logger.error(f"获取消息时出错: {str(e)}")
        return jsonify({'status': 'error', 'message': f'获取消息失败: {str(e)}'}), 500

@app.route('/delete_message', methods=['POST'])
def delete_message():
    """删除消息"""
    try:
        data = request.get_json()
        message_id = data.get('message_id')
        admin = config_values.get('admin_ips', [])
        user_ip = get_client_ip()
        operator_location = get_ip_location(user_ip)
        
        if not message_id or not user_ip:
            return jsonify({'status': 'error', 'message': '参数错误'}), 400
        
        with history_lock:
            # 查找消息
            for i, msg in enumerate(chat_history):
                if msg['sort_key'] == message_id:
                    # 检查权限
                    if (user_ip not in admin) and (user_ip != msg['ip']):
                        return jsonify({'status': 'error', 'message': '无权删除此消息'}), 403
                    if msg.get('image'): # 如果有图片，删除本地图片文件
                        image_path = os.path.join(IMAGE_STORAGE_PATH, msg['image'])
                        if not os.path.exists(image_path):
                            app.logger.error(f"尝试删除不存在的图片文件: {image_path}")
                        try:
                            os.remove(image_path)
                        except Exception as e:
                            app.logger.error(f"删除图片文件失败: {str(e)}")
                    del chat_history[i]
                    save_chat_history()  # 新增保存操作
                    # 日志记录
                    log_operation(
                        action='撤回消息',
                        operator_ip=user_ip,
                        operator_location=operator_location,
                        target_ip=msg['ip'],
                        target_location=get_ip_location(msg['ip']),
                        content=msg['message']
                    )
                    return jsonify({'status': 'success'})                       
            for i, h in enumerate(highlights):
                if h['sort_key'] == message_id:
                    if (user_ip not in admin) and (user_ip != h['ip']):
                        return jsonify({'status': 'error', 'message': '无权删除此消息'}), 403
                    if h.get('image'):
                        image_path = os.path.join(IMAGE_STORAGE_PATH, h['image'])
                        if os.path.exists(image_path):
                            try:
                                os.remove(image_path)
                            except Exception as e:
                                app.logger.error(f"删除图片文件失败: {str(e)}")
                    del highlights[i]
                    save_highlights()
                    # 日志记录
                    log_operation(
                        action='撤回精华消息',
                        operator_ip=user_ip,
                        operator_location=operator_location,
                        target_ip=h['ip'],
                        target_location=get_ip_location(h['ip']),
                        content=h['message']
                    )
                    return jsonify({'status': 'success'})
            return jsonify({'status': 'error', 'message': '消息不存在'}), 404
        
    except Exception as e:
        app.logger.error(f"删除消息时出错: {str(e)}")
        return jsonify({'status': 'error', 'message': f'服务器错误: {str(e)}'}), 500

@app.route('/toggle_highlight', methods=['POST'])
def toggle_highlight():
    try:
        data = request.get_json()
        message_id = data.get('message_id')
        user_ip = get_client_ip()
        operator_location = get_ip_location(user_ip)
        
        if not message_id or not user_ip:
            return jsonify({'status': 'error', 'message': '参数错误'}), 400
        
        # 查找原始消息
        original_msg = None
        with history_lock:
            for msg in chat_history:
                if msg['sort_key'] == message_id:
                    original_msg = msg
                    break
            if not original_msg:
                for h in highlights:
                    if h['sort_key'] == message_id:
                        original_msg = h
                        break
        
        if not original_msg:
            return jsonify({'status': 'error', 'message': '消息不存在'}), 404
        
        # 切换精华状态
        is_highlighted = any(h['sort_key'] == message_id for h in highlights)
        if is_highlighted:
            # 移出精华
            highlights[:] = [h for h in highlights if h['sort_key'] != message_id]
            log_operation(
                action='取消精华',
                operator_ip=user_ip,
                operator_location=operator_location,
                target_ip=original_msg['ip'],
                target_location=get_ip_location(original_msg['ip']),
                content=original_msg['message']
            )
        else:
            # 添加为精华
            highlight_msg = original_msg.copy()
            highlight_msg['highlighted_at'] = datetime.now().timestamp()
            highlights.append(highlight_msg)
            log_operation(
                action='设置精华',
                operator_ip=user_ip,
                operator_location=operator_location,
                target_ip=original_msg['ip'],
                target_location=get_ip_location(original_msg['ip']),
                content=original_msg['message']
            )
        
        save_highlights()
        save_chat_history()  # 保存操作
        return jsonify({'status': 'success', 'is_highlighted': not is_highlighted})
    
    except Exception as e:
        app.logger.error(f"设置精华失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'服务器错误: {str(e)}'}), 500

@app.route('/get_highlights')
def get_highlights():
    """获取所有精华消息"""
    try:
        # 按设置时间倒序排列
        sorted_highlights = sorted(highlights, key=lambda x: x['highlighted_at'], reverse=True)
        return jsonify({'highlights': sorted_highlights})
    except Exception as e:
        app.logger.error(f"获取精华消息失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'获取精华失败: {str(e)}'}), 500
    
@app.route('/log')
def view_log():
    """在线查看操作日志"""
    # 获取日期参数
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    log_file = os.path.join('./data', f'operation_{date}.log')
    logs = []
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    logs.append(json.loads(line))
                except Exception:
                    continue
    # 分页
    page = int(request.args.get('page', 1))
    page_size = 30
    total = len(logs)
    logs = logs[::-1]  # 最新在前
    logs_page = logs[(page-1)*page_size: page*page_size]
    # 搜索
    keyword = request.args.get('kw', '').strip()
    if keyword:
        logs_page = [log for log in logs_page if keyword in json.dumps(log, ensure_ascii=False)]
    # HTML渲染
    html = """
    <html>
    <head>
        <title>操作日志查看</title>
        <style>
            body {{ font-family: '微软雅黑', Arial; background: #f7f7f7; }}
            table {{ border-collapse: collapse; width: 98%; margin: 20px auto; background: #fff; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; }}
            th {{ background: #eee; }}
            tr:nth-child(even){{background-color: #f2f2f2;}}
            .search-bar {{ margin: 20px auto; width: 98%; text-align: right; }}
            .pagination {{ margin: 10px auto; width: 98%; text-align: center; }}
            .pagination a {{ margin: 0 5px; text-decoration: none; color: #007bff; }}
        </style>
    </head>
    <body>
        <h2 style="text-align:center;">操作日志（{date}）</h2>
        <div class="search-bar">
            <form method="get">
                <input type="date" name="date" value="{date}">
                <input type="text" name="kw" placeholder="关键词" value="{kw}">
                <button type="submit">搜索</button>
            </form>
        </div>
        <table>
            <tr>
                <th>时间</th>
                <th>操作</th>
                <th>操作者IP</th>
                <th>操作者属地</th>
                <th>目标IP</th>
                <th>目标属地</th>
                <th>内容</th>
                <th>结果</th>
                <th>级别</th>
            </tr>
    """.format(date=date, kw=keyword)
    for log in logs_page:
        html += f"""
        <tr>
            <td>{log.get('datetime','')}</td>
            <td>{log.get('action','')}</td>
            <td>{log.get('operator_ip','')}</td>
            <td>{log.get('operator_location','')}</td>
            <td>{log.get('target_ip','')}</td>
            <td>{log.get('target_location','')}</td>
            <td>{log.get('content','')}</td>
            <td>{log.get('result','')}</td>
            <td>{log.get('level','')}</td>
        </tr>
        """
    html += "</table>"
    # 分页导航
    total_pages = (total + page_size - 1) // page_size
    html += '<div class="pagination">'
    for p in range(1, total_pages+1):
        if p == page:
            html += f'<b>{p}</b>'
        else:
            html += f'<a href="?date={date}&page={p}&kw={keyword}">{p}</a>'
    html += '</div></body></html>'
    return html

def log_operation(action, operator_ip, operator_location, target_ip, target_location, content, result='success', level='info'):
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

if __name__ == '__main__':
    Path('./data').mkdir(exist_ok=True) # 确保数据目录存在
    Path(IMAGE_STORAGE_PATH).mkdir(exist_ok=True)  # 创建图片存储目录
    chat_history = load_chat_history() # 初始化时加载聊天记录 
    load_config_vars() 
    app.logger.info(f"初始配置: {config_values}") # 初始化时打印配置
    app.run(host='0.0.0.0', port=5000, debug=True)