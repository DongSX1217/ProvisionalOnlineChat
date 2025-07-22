from flask import Flask, render_template, request, jsonify
import base64
import time,json,re,os
from datetime import datetime
import threading
import requests,smtplib
from pathlib import Path

app = Flask(__name__)

# 存储聊天消息的列表（最多保留100条）
chat_history = []
history_lock = threading.Lock()

# 存储路径定义
HIGHLIGHTS_FILE = './data/highlights.json'
CHAT_HISTORY_FILE = './data/chat_history.json'
TEST_VARS_FILE = './data/test_variables.json'

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
SECRET_PASSWORD = "241217"

# 配置变量定义 (可轻松添加更多变量)
CONFIG_VARS = {
    'admin_ips': {
        'default': ["127.0.0.1", "223.160.176.6", "27.225.45.194"],
        'description': "管理员IP列表"
    },
    'blocked_ips': {
        'default': [],
        'description': "限制发言IP列表"
    }
}

# 当前配置变量值
config_values = {}

def load_config_vars():
    """从文件加载配置变量"""
    global config_values
    if os.path.exists(TEST_VARS_FILE):
        try:
            with open(TEST_VARS_FILE, 'r', encoding='utf-8') as f:
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
        with open(TEST_VARS_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_values, f, ensure_ascii=False, indent=2)
    except Exception as e:
        app.logger.error(f"保存配置变量失败: {str(e)}")

def get_ip_location(ip):
    """获取IP的地理位置信息"""
    # 特殊处理本地IP
    if ip == '127.0.0.1':
        return "本地"
    
    # 检查缓存中是否有该IP的地理位置
    with ip_location_lock:
        if ip in ip_location_cache:
            return ip_location_cache[ip]
    
    try:
        # 使用ip-api.com获取地理位置信息
        response = requests.get(f'http://ip-api.com/json/{ip}?fields=status,message,country,regionName,query&lang=zh-CN', timeout=3)
        data = response.json()
        
        if data.get('status') == 'success':
            # 提取国家、省份和城市信息
            country = data.get('country', '')
            region = data.get('regionName', '')
            
            # 优先显示省份，其次是国家
            location = region or country or '未知'
            
            # 将结果存入缓存
            with ip_location_lock:
                ip_location_cache[ip] = location
            
            return location
        else:
            return '未知'
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

@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')

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
            # 返回所有配置变量及其描述
            return jsonify({
                'status': 'success',
                'config_vars': config_values,
                'var_descriptions': {name: data['description'] for name, data in CONFIG_VARS.items()}
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
                # 特殊处理数组类型
                if isinstance(value, str) and name in ['admin_ips', 'blocked_ips']:
                    try:
                        config_values[name] = json.loads(value)
                    except json.JSONDecodeError:
                        config_values[name] = [ip.strip() for ip in value.split(',') if ip.strip()]
                elif isinstance(value, list):
                    config_values[name] = value
                else:
                    config_values[name] = value
        
        # 保存到文件
        save_config_vars()
        
        # 返回更新后的值
        return jsonify({
            'status': 'success',
            'config_vars': config_values
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
        image = None
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                # 检查图片大小
                file.seek(0, os.SEEK_END)
                file_length = file.tell()
                file.seek(0)
                
                if file_length > 2 * 1024 * 1024:  # 限制2MB
                    return jsonify({'status': 'error', 'message': '图片大小不能超过2MB'}), 400
                
                # 将图片转为base64编码
                image_data = file.read()
                image = f"data:image/{file.filename.split('.')[-1]};base64,{base64.b64encode(image_data).decode('utf-8')}"
        
        # 如果既没有消息也没有图片，则返回错误
        if not message and not image:
            return jsonify({'status': 'error', 'message': '消息内容不能为空'}), 400
        
        # 获取IP地理位置
        location = get_ip_location(user_ip)
        
        # 创建消息对象
        message_obj = {
            'username': username,
            'ip': user_ip,
            'message': message,
            'image': image,
            'timestamp': timestamp,
            'sort_key': timestamp_sort,
            'location': location  # 地理位置信息
        }
        
        # 添加到聊天历史记录
        with history_lock:
            chat_history.append(message_obj)
            # 保持只保留最近的100条消息
            if len(chat_history) > 100:
                chat_history.pop(0)
            save_chat_history()  # 新增保存操作
        
        return jsonify({'status': 'success'})
    
    except Exception as e:
        app.logger.error(f"发送消息时出错: {str(e)}")
        return jsonify({'status': 'error', 'message': f'服务器错误: {str(e)}'}), 500

@app.route('/get_messages')
def get_messages():
    """获取最新的聊天消息（按时间正序排列，最新的在底部）"""
    try:
        # 返回按时间正序排列的消息（最新的在最后）
        with history_lock:
            # 按时间戳排序（从小到大，最新的在最后）
            sorted_history = sorted(chat_history, key=lambda x: x['sort_key'])
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
        user_ip = get_client_ip()
        
        if not message_id or not user_ip:
            return jsonify({'status': 'error', 'message': '参数错误'}), 400
        
        with history_lock:
            # 查找消息
            for i, msg in enumerate(chat_history):
                if msg['sort_key'] == message_id:
                    # 检查权限
                    if (user_ip in admin) or (user_ip == msg['ip']):
                        del chat_history[i]
                        save_chat_history()  # 新增保存操作
                        return jsonify({'status': 'success'})
                    else:
                        return jsonify({'status': 'error', 'message': '无权删除此消息'}), 403
            
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
            return jsonify({'status': 'error', 'message': '消息不存在'}), 404
        
        # 切换精华状态
        is_highlighted = any(h['sort_key'] == message_id for h in highlights)
        if is_highlighted:
            # 移出精华
            highlights[:] = [h for h in highlights if h['sort_key'] != message_id]
        else:
            # 添加为精华
            highlight_msg = original_msg.copy()
            highlight_msg['highlighted_at'] = datetime.now().timestamp()
            highlights.append(highlight_msg)
        
        save_highlights()
        save_chat_history()  # 新增保存操作
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

if __name__ == '__main__':
    Path('./data').mkdir(exist_ok=True) # 确保数据目录存在
    chat_history = load_chat_history() # 初始化时加载聊天记录 
    load_config_vars() 
    app.logger.info(f"初始配置: {config_values}") # 初始化时打印配置
    app.run(host='0.0.0.0', port=5000, debug=True)