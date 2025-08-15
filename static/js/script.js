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
    const highlightsBtn = document.createElement('button'); // 精华消息按钮

    // 获取用户名cookie
    const usernameCookie = decodeURIComponent(document.cookie.replace(/(?:(?:^|.*;\s*)username\s*=\s*([^;]*).*$)|^.*$/, "$1"));

    // 如果有保存的用户名且不是匿名，则填充到输入框
    if (usernameCookie && usernameCookie !== '匿名') {
        if (usernameInput) {
            usernameInput.value = usernameCookie;
        }
    }
    
    let selectedImage = null;
    let lastMessageId = 0;
    let userIP = '';
    let notificationPermission = false;
    let highlights = []; 
    let adminIps = [];
    let blockedIps = [];
    let newMessageArrived = false;

    console.log('Element check:');
    console.log('sendBtn:', sendBtn);
    console.log('emojiBtn:', emojiBtn);
    console.log('imageBtn:', imageBtn);
    console.log('notificationBtn:', notificationBtn);
    

    // ==================== 初始化精华消息UI ====================
    function HighlightUI() {
        // 创建精华消息按钮
        highlightsBtn.className = 'highlights-btn';
        highlightsBtn.id = 'highlightsBtn';
        highlightsBtn.textContent = '⭐ 精华  ';
        notificationBtn.parentNode.insertBefore(highlightsBtn, notificationBtn);

        // 创建精华消息弹窗
        document.body.insertAdjacentHTML('beforeend', `
            <div class="highlights-modal" id="highlightsModal">
                <button class="close-btn" id="closeHighlights">&times;</button>
                <h2>精华消息</h2>
                <div class="highlights-container" id="highlightsContainer"></div>
            </div>
        `);

        bindEvents();
    }

    // ==================== 粘贴图片自动上传 ====================
    document.addEventListener('paste', function (event) {
        if (!event.clipboardData || !event.clipboardData.items) return;
        for (let i = 0; i < event.clipboardData.items.length; i++) {
            const item = event.clipboardData.items[i];
            if (item.type.indexOf('image') !== -1) {
                const file = item.getAsFile();
                if (file) {
                    // 检查文件类型和大小
                    const validTypes = ['image/jpeg', 'image/png', 'image/gif'];
                    if (!validTypes.includes(file.type)) {
                        showError('只支持JPEG、PNG或GIF格式的图片');
                        return;
                    }
                    if (file.size > 10 * 1024 * 1024) {
                        showError('图片大小不能超过10MB');
                        return;
                    }
                    // 预览图片
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        if (previewImage) previewImage.src = e.target.result;
                        if (imagePreview) imagePreview.style.display = 'block';
                        selectedImage = file;
                        if (imageUpload) imageUpload.value = ''; // 清空文件选择框
                    };
                    reader.readAsDataURL(file);
                    event.preventDefault();
                    break;
                }
            }
        }
    });

    // ==================== 事件绑定函数 ====================
    function bindEvents() {
        console.log('Binding events...');

        // 精华消息按钮事件
        if (highlightsBtn) {
            highlightsBtn.addEventListener('click', showHighlights);
        }
        
        // 精华消息弹窗关闭按钮事件
        const closeHighlightsBtn = document.getElementById('closeHighlights');
        if (closeHighlightsBtn) {
            closeHighlightsBtn.addEventListener('click', hideHighlights);
        }

        // Markdown源码弹窗关闭按钮事件
        const closeSourceBtn = document.querySelector('.source-modal .close-btn');
        if (closeSourceBtn) {
            closeSourceBtn.addEventListener('click', function() {
                document.querySelector('.source-modal').style.display = 'none';
                if (overlay) overlay.style.display = 'none';
            });
        }

        // 主页按钮事件处理
        const homeBtn = document.querySelector('#homeBtn');
        if (homeBtn) {
            homeBtn.addEventListener('click', function() {
                window.location.href = '/';
            });
        }

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
        if (overlay) {
            overlay.addEventListener('click', function() {
                hideMarkdownHelp();
                hideHighlights(); // 同时关闭精华消息弹窗
            });
        }
        
        // 发送按钮事件
        if (sendBtn) {
            sendBtn.addEventListener('click', sendMessage);
        }
        
        // Shift+Enter事件
        if (messageInput) {
            messageInput.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' && e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            });
        }

        // 回到底部按钮
        const scrollToBottomBtn = document.getElementById('scrollToBottomBtn');
        if (scrollToBottomBtn && scrollAnchor) {
            scrollToBottomBtn.addEventListener('click', function() {
                scrollAnchor.scrollIntoView({ behavior: 'smooth' });
                // 恢复按钮颜色
                scrollToBottomBtn.style.backgroundColor = '';
                scrollToBottomBtn.style.color = '';
                newMessageArrived = false;
            });
        }
        
        console.log('Events bound successfully');
    }

    // ==================== 精华消息功能 ====================
    function addHighlightButton(div, msg) {
        // 先检查是否已有按钮
        const existingBtn = div.querySelector('.highlight-btn');
        if (existingBtn) {
            existingBtn.remove(); // 移除旧按钮
        }

        const highlightBtn = document.createElement('button');
        highlightBtn.className = 'highlight-btn';
        highlightBtn.title = msg.is_highlighted ? '移出精华' : '设为精华';
        highlightBtn.innerHTML = msg.is_highlighted ? '⭐' : '☆';
        
        // 添加一次性事件监听
        highlightBtn.addEventListener('click', function handler() {
            toggleHighlightStatus(msg.sort_key);
            this.removeEventListener('click', handler); // 点击后移除监听
        });
        
        // 添加到删除按钮左侧
        const deleteBtn = div.querySelector('.delete-btn');
        if (deleteBtn) {
            deleteBtn.parentNode.insertBefore(highlightBtn, deleteBtn);
        }
    }

    // 切换精华状态
    function toggleHighlightStatus(messageId) {
        fetch('/message/toggle_highlight', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                message_id: messageId,
                ip: userIP
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // 更新主消息列表和弹窗中的按钮状态
                const buttons = document.querySelectorAll(`.message[data-id="${messageId}"] .highlight-btn`);
                buttons.forEach(btn => {
                    btn.innerHTML = data.is_highlighted ? '⭐' : '☆';
                    btn.title = data.is_highlighted ? '移出精华' : '设为精华';
                });
                
                // 如果取消精华，显示提示
                if (!data.is_highlighted) {
                    showError('取消精华设置将在刷新页面后生效', 'info');
                }
            } else {
                showError(data.message || '操作失败');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showError('操作失败');
        });
    }

    // 显示精华消息弹窗
    function showHighlights() {
        fetch('/message/get_highlights')
        .then(response => response.json())
        .then(data => {
            if (data.highlights) {
                const container = document.getElementById('highlightsContainer');
                container.innerHTML = '';
                
                // 渲染精华消息，强制设置为精华状态
                data.highlights.forEach(msg => {
                    const el = createMessageElement({...msg, is_highlighted: true});
                    container.appendChild(el);
                });
                
                document.getElementById('highlightsModal').style.display = 'block';
                overlay.style.display = 'block';
            }
        })
        .catch(error => {
            console.error('获取精华消息失败:', error);
            showError('获取精华消息失败');
        });
    }

    // 隐藏精华消息弹窗
    function hideHighlights() {
        document.getElementById('highlightsModal').style.display = 'none';
        overlay.style.display = 'none';
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

    function isAdminUser() {
        return adminIps.includes(userIP);
    }

    function isBlockedUser() {
        return blockedIps.includes(userIP);
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
        if (file.size > 10 * 1024 * 1024) {
            showError('图片大小不能超过10MB');
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

    // 显示加载指示器
    function showLoadingIndicator() {
        if (!chatContainer) return;
        
        const loadingDiv = document.createElement('div');
        loadingDiv.id = 'loadingIndicator';
        loadingDiv.textContent = '正在加载中...';
        loadingDiv.style.textAlign = 'center';
        loadingDiv.style.padding = '20px';
        loadingDiv.style.color = '#666';
        chatContainer.insertBefore(loadingDiv, scrollAnchor);
    }

    // 延迟加载图片
    function loadImages() {
        const imagePlaceholders = document.querySelectorAll('.image-placeholder');
        let loadedCount = 0;
        const totalCount = imagePlaceholders.length;
        
        // 判断是否是初次加载（页面刚打开时）
        const isFirstLoad = lastMessageId === 0;
        
        if (totalCount === 0) {
            return;
        }
        
        imagePlaceholders.forEach(placeholder => {
            const messageId = placeholder.getAttribute('data-message-id');
            const imageUrl = placeholder.getAttribute('data-image-url');
            
            if (imageUrl) {
                const img = document.createElement('img');
                img.src = imageUrl;
                img.alt = '图片';
                img.className = 'message-image';
                img.style.display = 'none'; // 先隐藏，加载完成后再显示
                
                img.onload = function() {
                    // 图片加载完成后替换占位符
                    placeholder.parentNode.replaceChild(img, placeholder);
                    img.style.display = 'block';
                    
                    // 图片加载完成后，如果是初次加载，再次滚动到底部
                    loadedCount++;
                    if (isFirstLoad && loadedCount === totalCount) {
                        // 所有图片加载完成后，延迟一点时间再滚动到底部
                        setTimeout(() => {
                            scrollToBottomSmooth();
                        }, 100);
                    }
                };
                
                img.onerror = function() {
                    // 图片加载失败，显示错误信息
                    placeholder.innerHTML = '图片加载失败';
                    placeholder.style.backgroundColor = '#fcc';
                    
                    // 图片加载失败时也检查是否需要滚动到底部
                    loadedCount++;
                    if (isFirstLoad && loadedCount === totalCount) {
                        setTimeout(() => {
                            scrollToBottomSmooth();
                        }, 100);
                    }
                };
            }
        });
    }

    // 隐藏加载指示器
    function hideLoadingIndicator() {
        const loadingIndicator = document.getElementById('loadingIndicator');
        if (loadingIndicator) {
            loadingIndicator.remove();
        }
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

    // 添加获取配置值的函数
    function getConfigValue(key) {
        return window.config_values?.[key] || [];
    }
    
    // 发送消息
    function sendMessage() {
        console.log('Sending message...');

        // 获取用户IP
        if (!userIP) {
            showError('无法获取用户IP');
            return;
        }
        
        // 检查是否在限制IP名单中
        if (blockedIps.includes(userIP)) {
            showError('您的IP已被限制发言');
            return;
        }
        
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
        
        fetch('/message/send', {
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
        // 获取配置信息
        fetch('/config/get_config')
        .then(response => response.json())
        .then(config => {
            adminIps = config.admin_ips || [];
            blockedIps = config.blocked_ips || [];
            
            // 获取消息
            return fetch('/message/get');
        })
        .then(response => response.json())
        .then(data => {
            if (data.messages && Array.isArray(data.messages)) {
                // 设置userIP（如果尚未设置）
                if (!userIP && data.messages.length > 0) {
                    userIP = data.messages[0].ip || '';
                }
                
                renderMessages(data.messages, scrollToBottom);
            }
        })
        .catch(error => {
            console.error('获取数据失败:', error);
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
        
        // 如果是第一次加载且没有消息，显示加载提示
        if (lastMessageId === 0 && messages.length === 0) {
            showLoadingIndicator();
            return;
        }
        hideLoadingIndicator(); // 隐藏加载提示
        
        // 获取所有新消息（基于lastMessageId）
        const newMessages = messages.filter(msg => msg.sort_key > lastMessageId);
        
        if (newMessages.length === 0) {
            return;
        }

        // 如果有新消息且不是自动滚动到底部，则让“底”按钮变红
        if (newMessages.length > 0 && !scrollToBottom) {
            const scrollToBottomBtn = document.getElementById('scrollToBottomBtn');
            if (scrollToBottomBtn) {
                scrollToBottomBtn.style.backgroundColor = '#e74c3c'; // 红色
                scrollToBottomBtn.style.color = '#fff';
                newMessageArrived = true;
            }
        }
        
        // 更新lastMessageId为最新消息的时间戳
        lastMessageId = Math.max(...messages.map(msg => msg.sort_key));
        
        // 按时间戳排序所有新消息
        newMessages.sort((a, b) => a.sort_key - b.sort_key);
        
        // 渲染所有新消息（按时间顺序）
        newMessages.forEach(msg => {
            const messageElement = createMessageElement(msg, !!msg.image); // 对于图片消息，先创建占位符
            if (msg.image && msg.image_height) {
                const placeholder = messageElement.querySelector('.image-placeholder');
                if (placeholder) {
                    placeholder.style.height = msg.image_height + 'px';
                }
            }
            scrollAnchor.insertAdjacentElement('beforebegin', messageElement);
        });
        
        const allMessages = chatContainer.querySelectorAll('.message');
        // 如果消息数量超过300条，删除最旧的消息
        if (allMessages.length > 300) {
            for (let i = 0; i < allMessages.length - 300; i++) {
                allMessages[i].remove();
            }
        }
        
        if (scrollToBottom) {
            scrollToBottomSmooth();
            // 恢复按钮颜色
            const scrollToBottomBtn = document.getElementById('scrollToBottomBtn');
            if (scrollToBottomBtn) {
                scrollToBottomBtn.style.backgroundColor = '';
                scrollToBottomBtn.style.color = '';
                newMessageArrived = false;
            }
        }
        
        // 延迟加载图片
        setTimeout(loadImages, 100);
    }

    // 引用消息
    function quoteMessage(msg) {
        const messageInput = document.querySelector('#message');
        if (!messageInput) return;
        
        // 获取原始消息文本（去除HTML标签）
        let messageText = msg.message || '';
        
        // 如果有HTML内容，需要提取纯文本
        if (messageText && (messageText.includes('<') || messageText.includes('>'))) {
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = messageText;
            messageText = tempDiv.textContent || tempDiv.innerText || '';
        }
        
        // 处理嵌套引用，确保每一行都添加">"符号
        const lines = messageText.split('\n');
        const processedLines = lines.map(line => {
            return '> ' + line;
        });
        messageText = processedLines.join('\n');
        
        // 创建引用格式
        const quotedText = `${messageText}\n> —— ${msg.username}\n\n`;
        
        // 将引用添加到消息输入框的开头
        messageInput.value = quotedText + messageInput.value;
        
        // 聚焦到输入框并滚动到顶部
        messageInput.focus();
        // messageInput.scrollTop = 0;
    }

    // 显示消息的Markdown源代码
    function showSourceCode(msg) {
        const sourceModal = document.querySelector('.source-modal');
        const overlay = document.querySelector('#overlay');
        const sourceContent = sourceModal.querySelector('.source-content');
        
        if (msg.message) {
            sourceContent.textContent = msg.message;
            sourceModal.style.display = 'block';
            overlay.style.display = 'block';
        }
    }
    
    // 创建消息元素
    // 创建消息元素
    function createMessageElement(msg, imagePlaceholder = false) {
        const div = document.createElement('div');
        div.className = 'message';
        div.setAttribute('data-id', msg.sort_key);
        
        // 获取消息日期和时间
        const msgDate = new Date(msg.sort_key * 1000); // 乘以1000转换为毫秒
        const month = msgDate.getMonth() + 1;
        const day = msgDate.getDate();
        const hours = msgDate.getHours().toString().padStart(2, '0');
        const minutes = msgDate.getMinutes().toString().padStart(2, '0');
        const seconds = msgDate.getSeconds().toString().padStart(2, '0');    

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
        
        // 判断当前用户是否是管理员（能看真实IP）
        const currentUserIsAdmin = adminIps.includes(userIP);
        const displayIp = currentUserIsAdmin ? msg.ip : maskIp(msg.ip);
        
        const ipAddress = document.createElement('span');
        ipAddress.className = 'ip-address';
        ipAddress.textContent = 'IP: ' + displayIp;
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

        // 引用按钮
        const quoteBtn = document.createElement('button');
        quoteBtn.className = 'quote-btn';
        quoteBtn.title = '引用消息';
        quoteBtn.innerHTML = '❞';
        quoteBtn.addEventListener('click', () => quoteMessage(msg));
        div.appendChild(quoteBtn);

        // 源码查看按钮（如果消息有内容）
        if (msg.message) {
            const sourceBtn = document.createElement('button');
            sourceBtn.className = 'source-btn';
            sourceBtn.title = '查看源码';
            sourceBtn.innerHTML = '{}';
            sourceBtn.addEventListener('click', () => showSourceCode(msg));
            div.appendChild(sourceBtn);
        }
        
        messageHeader.appendChild(timestampArea);
        div.appendChild(messageHeader);
        
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
        
        // 处理图片显示
        if (msg.image) {
            if (imagePlaceholder) {
                // 创建图片占位符
                const placeholder = document.createElement('div');
                placeholder.className = 'image-placeholder';
                placeholder.setAttribute('data-message-id', msg.sort_key);
                placeholder.setAttribute('data-image-url', msg.image_url || '');
                placeholder.style.backgroundColor = '#eee';
                placeholder.style.padding = '20px';
                placeholder.style.textAlign = 'center';
                placeholder.style.borderRadius = '8px';
                placeholder.style.marginTop = '8px';
                placeholder.style.color = '#999';
                placeholder.style.fontSize = '14px';
                placeholder.textContent = '正在加载中...';
                div.appendChild(placeholder);
            } else if (msg.image_url) {
                // 直接显示图片
                const img = document.createElement('img');
                img.src = msg.image_url;
                img.alt = '图片';
                img.className = 'message-image';
                div.appendChild(img);
            }
        }
        
        //if (msg.ip === userIP || userIP === '127.0.0.1') {
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'delete-btn';
        deleteBtn.title = '撤回消息';
        deleteBtn.innerHTML = '×';
        deleteBtn.addEventListener('click', () => deleteMessage(msg.sort_key));
        div.appendChild(deleteBtn);
        //}
        
        // 优先使用传入的is_highlighted状态
        const isHighlighted = msg.is_highlighted !== undefined ? 
                            msg.is_highlighted : 
                            highlights.some(h => h.sort_key == msg.sort_key);
        addHighlightButton(div, {...msg, is_highlighted: isHighlighted});

        return div;
    }
    
    // 删除消息
    function deleteMessage(messageId) {
        if (!confirm('确定要撤回这条消息吗？')) return;
        
        fetch('/message/delete', {
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
        if (!ip || ip === '本地') {
            return '';
        }
        
        // 使用正则表达式匹配IPv4地址
        const ipv4_pattern = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/;
        const match = ipv4_pattern.exec(ip);
        
        if (match) {
            return `${match[1]}.*.${match[3]}.${match[4]}`;
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

    // 添加获取精华消息的函数
    function fetchHighlights() {
        fetch('/message/get_highlights')
        .then(response => response.json())
        .then(data => {
            if (data.highlights) {
                highlights = data.highlights;
                // 刷新页面后重新渲染所有消息的精华状态
                document.querySelectorAll('.message').forEach(el => {
                    const msgId = el.getAttribute('data-id');
                    const isHighlighted = highlights.some(h => h.sort_key == msgId);
                    const btn = el.querySelector('.highlight-btn');
                    if (btn) {
                        btn.innerHTML = isHighlighted ? '⭐' : '☆';
                        btn.title = isHighlighted ? '移出精华' : '设为精华';
                    }
                });
            }
        })
        .catch(error => {
            console.error('获取精华消息失败:', error);
        });
    }

    // ==================== 初始化应用 ====================
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            breaks: true,
            gfm: true,
            sanitize: false,
            highlight: code => code
        });
    } else {
        console.error('marked.js 未加载');
    }

    HighlightUI();

    fetch('/config/get_config')  // 先获取配置
    .then(response => response.json())
    .then(config => {
        adminIps = config.admin_ips || [];
        blockedIps = config.blocked_ips || [];
        
        // 然后获取用户IP
        fetch('/message/get')
        .then(response => response.json())
        .then(data => {
            if (data.messages && Array.isArray(data.messages) && data.messages.length > 0) {
                userIP = data.messages[0].ip || '';
            }
            
            // 最后初始化消息获取
            fetchMessages(true);
            fetchHighlights();
            setInterval(() => fetchMessages(), 5000);
        });
    })
    .catch(error => {
        console.error('初始化失败:', error);
    });
});