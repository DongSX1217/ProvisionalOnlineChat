from flask import Flask, render_template, request, jsonify
import base64
import os
import time
from datetime import datetime
import threading

app = Flask(__name__)

# 存储聊天消息的列表（最多保留100条）
chat_history = []
history_lock = threading.Lock()

@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')

@app.route('/send_message', methods=['POST'])
def send_message():
    """处理消息发送请求"""
    try:
        # 获取用户提交的数据
        username = request.form.get('username', '匿名').strip() or '匿名'
        message = request.form.get('message', '').strip()
        user_ip = request.remote_addr
        
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
        
        # 创建消息对象
        message_obj = {
            'username': username,
            'ip': user_ip,
            'message': message,
            'image': image,
            'timestamp': timestamp,
            'sort_key': timestamp_sort  # 用于排序的键
        }
        
        # 添加到聊天历史记录
        with history_lock:
            chat_history.append(message_obj)
            # 保持只保留最近的100条消息
            if len(chat_history) > 100:
                chat_history.pop(0)
        
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
        user_ip = data.get('ip')
        
        if not message_id or not user_ip:
            return jsonify({'status': 'error', 'message': '参数错误'}), 400
        
        with history_lock:
            # 查找消息并验证IP
            for i, msg in enumerate(chat_history):
                if msg['sort_key'] == message_id and msg['ip'] == user_ip:
                    del chat_history[i]
                    return jsonify({'status': 'success'})
            
            return jsonify({'status': 'error', 'message': '消息不存在或无权删除'}), 404
        
    except Exception as e:
        app.logger.error(f"删除消息时出错: {str(e)}")
        return jsonify({'status': 'error', 'message': f'服务器错误: {str(e)}'}), 500

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)