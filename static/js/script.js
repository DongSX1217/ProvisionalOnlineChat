// 确保所有代码在页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM fully loaded and parsed');
    
    // ==================== 初始化变量 ====================
    const emojis = ["😀", "😃", "😄", "😁", "😆", "😅", "😂", "🤣", "😊", "😇", 
                    "🙂", "🙃", "😉", "😌", "😍", "🥰", "😘", "😗", "😙", "😚", 
                    "😋", "😛", "😝", "😜", "🤪", "🤨", "🧐", "🤓", "😎", "🤩", 
                    "🥳", "😏", "😒", "😞", "😔", "😟", "😕", "🙁", "☹️", "😣", 
                    "😖", "😫", "😩", "🥺", "😢", "😭", "😤", "😠", "😡", "🤬", 
                    "🤯", "😳", "🥵", "🥶", "😱", "😨", "😰", "😥", "😓", "🤗", 
                    "🤔", "🤭", "🤫", "🤥", "😶", "😐", "😑", "😬", "🙄", "😯", 
                    "😦", "😧", "😮", "😲", "🥱", "😴", "🤤", "😪", "😵", "🤐", 
                    "🥴", "🤢", "🤮", "🤧", "😷", "🤒", "🤕", "🤑", "🤠", "😈"];
    
    // 使用更可靠的选择器获取元素
    const chatContainer = document.querySelector('#chatContainer');
    const usernameInput = document.querySelector('#username');
    const messageInput = document.querySelector('#message');
    const sendBtn = document.querySelector('#sendBtn');
    const emojiBtn = document.querySelector('#emojiBtn');
    const emojiContainer = document.querySelector('#emojiContainer');
    const imageBtn = document.querySelector('#imageBtn');
    const imageUpload = document.querySelector('#imageUpload');
    const imagePreview = document.querySelector('#imagePreview');
    const previewImage = document.querySelector('#previewImage');
    const removeImage = document.querySelector('#removeImage');
    const errorMessage = document.querySelector('#errorMessage');
    const scrollAnchor = document.querySelector('#scrollAnchor');
    const notificationBtn = document.querySelector('#notificationBtn');
    const markdownHelpBtn = document.querySelector('#markdownHelpBtn');
    const markdownHelp = document.querySelector('#markdownHelp');
    const markdownHelpClose = document.querySelector('#markdownHelpClose');
    const overlay = document.querySelector('#overlay');
    
    let selectedImage = null;
    let lastMessageId = 0;
    let userIP = '';
    let notificationPermission = false;
    
    console.log('Element check:');
    console.log('sendBtn:', sendBtn);
    console.log('emojiBtn:', emojiBtn);
    console.log('imageBtn:', imageBtn);
    console.log('notificationBtn:', notificationBtn);
    
    // ==================== 事件绑定函数 ====================
    function bindEvents() {
        console.log('Binding events...');
        
        // 表情按钮事件
        if (emojiBtn && emojiContainer) {
            emojiBtn.addEventListener('click', toggleEmojiContainer);
        }
        
        // 图片按钮事件
        if (imageBtn && imageUpload) {
            imageBtn.addEventListener('click', () => {
                imageUpload.click();
            });
        }
        
        // 图片上传事件
        if (imageUpload) {
            imageUpload.addEventListener('change', handleImageUpload);
        }
        
        // 移除图片事件
        if (removeImage) {
            removeImage.addEventListener('click', removeSelectedImage);
        }
        
        // 通知按钮事件
        if (notificationBtn) {
            notificationBtn.addEventListener('click', requestNotificationPermission);
        }
        
        // Markdown帮助按钮事件
        if (markdownHelpBtn && markdownHelp && overlay) {
            markdownHelpBtn.addEventListener('click', showMarkdownHelp);
        }
        
        // 关闭Markdown帮助事件
        if (markdownHelpClose && markdownHelp && overlay) {
            markdownHelpClose.addEventListener('click', hideMarkdownHelp);
        }
        
        // 遮罩层点击事件
        if (overlay && markdownHelp) {
            overlay.addEventListener('click', hideMarkdownHelp);
        }
        
        // 发送按钮事件
        if (sendBtn) {
            sendBtn.addEventListener('click', sendMessage);
        }
        
        // 消息输入框回车事件
        if (messageInput) {
            messageInput.addEventListener('keypress', handleMessageKeypress);
        }
        
        console.log('Events bound successfully');
    }
    
    // ==================== 核心功能函数 ====================
    
    // 显示/隐藏表情选择器
    function toggleEmojiContainer() {
        if (emojiContainer.style.display === 'flex') {
            emojiContainer.style.display = 'none';
        } else {
            populateEmojis();
            emojiContainer.style.display = 'flex';
        }
    }
    
    // 填充表情
    function populateEmojis() {
        if (!emojiContainer) return;
        
        emojiContainer.innerHTML = '';
        emojis.forEach(emoji => {
            const span = document.createElement('span');
            span.className = 'emoji';
            span.textContent = emoji;
            span.addEventListener('click', () => {
                if (messageInput) {
                    messageInput.value += emoji;
                    messageInput.focus();
                }
            });
            emojiContainer.appendChild(span);
        });
    }
    
    // 处理图片上传
    function handleImageUpload(e) {
        const file = e.target.files[0];
        if (!file) return;
        
        // 检查文件类型
        const validTypes = ['image/jpeg', 'image/png', 'image/gif'];
        if (!validTypes.includes(file.type)) {
            showError('只支持JPEG、PNG或GIF格式的图片');
            return;
        }
        
        // 检查文件大小
        if (file.size > 2 * 1024 * 1024) {
            showError('图片大小不能超过2MB');
            return;
        }
        
        // 预览图片
        const reader = new FileReader();
        reader.onload = (event) => {
            if (previewImage) previewImage.src = event.target.result;
            if (imagePreview) imagePreview.style.display = 'block';
            selectedImage = file;
        };
        reader.readAsDataURL(file);
    }
    
    // 移除已选图片
    function removeSelectedImage() {
        if (previewImage) previewImage.src = '';
        if (imagePreview) imagePreview.style.display = 'none';
        if (imageUpload) imageUpload.value = '';
        selectedImage = null;
    }
    
    // 显示错误信息
    function showError(message) {
        if (errorMessage) {
            errorMessage.textContent = message;
            errorMessage.style.display = 'block';
            setTimeout(() => {
                if (errorMessage) errorMessage.style.display = 'none';
            }, 5000);
        }
    }
    
    // 请求通知权限
    function requestNotificationPermission() {
        if (!("Notification" in window)) {
            showError("您的浏览器不支持通知功能");
            return;
        }
        
        Notification.requestPermission().then(permission => {
            if (permission === "granted") {
                notificationPermission = true;
                if (notificationBtn) notificationBtn.textContent = "🔔 已启用";
                showError("通知功能已启用");
            } else {
                notificationPermission = false;
                if (notificationBtn) notificationBtn.textContent = "🔕 通知";
                showError("通知功能被拒绝");
            }
        });
    }
    
    // 显示Markdown帮助
    function showMarkdownHelp() {
        if (markdownHelp) markdownHelp.style.display = 'block';
        if (overlay) overlay.style.display = 'block';
    }
    
    // 隐藏Markdown帮助
    function hideMarkdownHelp() {
        if (markdownHelp) markdownHelp.style.display = 'none';
        if (overlay) overlay.style.display = 'none';
    }
    
    // 处理消息输入框按键
    function handleMessageKeypress(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    }
    
    // 发送消息
    function sendMessage() {
        console.log('Sending message...');
        
        const username = usernameInput ? usernameInput.value.trim() || '匿名' : '匿名';
        const message = messageInput ? messageInput.value.trim() : '';
        
        if (!message && !selectedImage) {
            showError('消息内容不能为空');
            return;
        }
        
        const formData = new FormData();
        formData.append('username', username);
        formData.append('message', message);
        if (selectedImage) {
            formData.append('image', selectedImage);
        }
        
        fetch('/send_message', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                if (messageInput) messageInput.value = '';
                if (imageUpload) imageUpload.value = '';
                if (previewImage) previewImage.src = '';
                if (imagePreview) imagePreview.style.display = 'none';
                selectedImage = null;
                
                fetchMessages(true);
            } else {
                showError(data.message || '发送消息失败');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showError('发送消息时出错');
        });
    }
    
    // 获取消息
    function fetchMessages(scrollToBottom = false) {
        fetch('/get_messages')
        .then(response => response.json())
        .then(data => {
            if (data.messages && Array.isArray(data.messages)) {
                if (!userIP && data.messages.length > 0) {
                    userIP = data.messages[0].ip || '';
                }
                
                const newMessages = data.messages.filter(msg => msg.sort_key > lastMessageId);
                
                if (newMessages.length > 0 && notificationPermission) {
                    const nonSelfMessages = newMessages.filter(msg => msg.ip !== userIP);
                    if (nonSelfMessages.length > 0) {
                        const sender = nonSelfMessages[0].username;
                        const content = nonSelfMessages[0].message ? 
                            nonSelfMessages[0].message.substring(0, 30) + (nonSelfMessages[0].message.length > 30 ? '...' : '') : 
                            '发送了一张图片';
                        
                        sendNotification('新消息', `${sender}: ${content}`);
                    }
                }
                
                renderMessages(data.messages, scrollToBottom);
            }
        })
        .catch(error => {
            console.error('获取消息失败:', error);
        });
    }
    
    // 发送通知
    function sendNotification(title, body) {
        if (!notificationPermission) return;
        
        if (document.visibilityState !== 'visible') {
            const notification = new Notification(title, {
                body: body,
                icon: 'https://cdn-icons-png.flaticon.com/512/733/733585.png'
            });
            
            notification.onclick = () => {
                window.focus();
            };
        }
    }
    
    // 渲染消息
    function renderMessages(messages, scrollToBottom = false) {
        if (!chatContainer || !scrollAnchor) return;
        
        const newMessages = messages.filter(msg => msg.sort_key > lastMessageId);
        
        if (newMessages.length === 0) {
            return;
        }
        
        lastMessageId = Math.max(...messages.map(msg => msg.sort_key));
        
        newMessages.forEach(msg => {
            const messageElement = createMessageElement(msg);
            scrollAnchor.insertAdjacentElement('beforebegin', messageElement);
        });
        
        const allMessages = chatContainer.querySelectorAll('.message');
        if (allMessages.length > 100) {
            for (let i = 0; i < allMessages.length - 100; i++) {
                allMessages[i].remove();
            }
        }
        
        if (scrollToBottom) {
            scrollToBottomSmooth();
        }
    }
    
    // 创建消息元素
    function createMessageElement(msg) {
        const div = document.createElement('div');
        div.className = 'message';
        div.setAttribute('data-id', msg.sort_key);
        
        // 获取当前日期和时间
        const now = new Date();
        const month = now.getMonth() + 1;
        const day = now.getDate();
        const hours = now.getHours().toString().padStart(2, '0');
        const minutes = now.getMinutes().toString().padStart(2, '0');
        const seconds = now.getSeconds().toString().padStart(2, '0');
        
        // 创建消息头部
        const messageHeader = document.createElement('div');
        messageHeader.className = 'message-header';
        
        // 用户信息容器
        const userInfo = document.createElement('div');
        userInfo.className = 'user-info';
        
        // 用户名
        const usernameSpan = document.createElement('span');
        usernameSpan.className = 'username';
        usernameSpan.textContent = escapeHtml(msg.username);
        userInfo.appendChild(usernameSpan);
        
        // IP信息
        const ipInfo = document.createElement('div');
        ipInfo.className = 'ip-info';
        
        // IP地址
        const ipAddress = document.createElement('span');
        ipAddress.className = 'ip-address';
        ipAddress.textContent = 'IP: ' + maskIp(msg.ip);
        ipInfo.appendChild(ipAddress);
        
        // 位置信息
        const location = document.createElement('span');
        location.className = 'ip-location';
        location.textContent = msg.location || '未知';
        ipInfo.appendChild(location);
        
        userInfo.appendChild(ipInfo);
        messageHeader.appendChild(userInfo);
        
        // 时间容器
        const timestampArea = document.createElement('div');
        timestampArea.className = 'timestamp-area';
        
        // 日期
        const dateSpan = document.createElement('span');
        dateSpan.className = 'date';
        dateSpan.textContent = `${month}月${day}日`;
        timestampArea.appendChild(dateSpan);
        
        // 时间
        const timestampSpan = document.createElement('span');
        timestampSpan.className = 'timestamp';
        timestampSpan.textContent = `${hours}:${minutes}:${seconds}`;
        timestampArea.appendChild(timestampSpan);
        
        messageHeader.appendChild(timestampArea);
        div.appendChild(messageHeader);
        
        // 消息内容部分保持不变
        if (msg.message) {
            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content markdown-body';
            
            if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
                contentDiv.innerHTML = DOMPurify.sanitize(marked(msg.message));
            } else {
                contentDiv.textContent = msg.message;
            }
            div.appendChild(contentDiv);
        }
        
        if (msg.image) {
            const img = document.createElement('img');
            img.src = msg.image;
            img.alt = '图片';
            img.className = 'message-image';
            div.appendChild(img);
        }
        
        // 删除按钮保持不变
        if (msg.ip === userIP || userIP === '127.0.0.1') {
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'delete-btn';
            deleteBtn.title = '撤回消息';
            deleteBtn.innerHTML = '×';
            deleteBtn.addEventListener('click', () => deleteMessage(msg.sort_key));
            div.appendChild(deleteBtn);
        }
        
        return div;
    }
    
    // 删除消息
    function deleteMessage(messageId) {
        if (!confirm('确定要撤回这条消息吗？')) return;
        
        fetch('/delete_message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message_id: messageId,
                ip: userIP
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                const messageElement = document.querySelector(`.message[data-id="${messageId}"]`);
                if (messageElement) {
                    messageElement.remove();
                }
            } else {
                showError(data.message || '撤回消息失败');
            }
        })
        .catch(error => {
            console.error('撤回消息出错:', error);
            showError('撤回消息时出错');
        });
    }
    
    // IP地址打码处理
    function maskIp(ip) {
        if (!ip) return '';
        if (ip === '127.0.0.1') return ip;
        
        const parts = ip.split('.');
        if (parts.length === 4) {
            return `${parts[0]}.*.${parts[2]}.${parts[3]}`;
        }
        return ip;
    }
    
    // 平滑滚动到底部
    function scrollToBottomSmooth() {
        if (scrollAnchor) {
            scrollAnchor.scrollIntoView({ behavior: 'smooth' });
        }
    }
    
    // HTML转义
    function escapeHtml(unsafe) {
        if (!unsafe) return '';
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
    
    // ==================== 初始化应用 ====================
    
    // 配置marked.js
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            breaks: true,
            gfm: true,
            sanitize: false,
            highlight: function(code, lang) {
                return code;
            }
        });
    } else {
        console.error('marked.js 未加载');
    }
    
    // 绑定所有事件
    bindEvents();
    
    // 初始加载消息
    fetchMessages(true);
    
    // 每5秒刷新一次消息
    setInterval(() => fetchMessages(), 5000);
    
    console.log('Application initialized');
});