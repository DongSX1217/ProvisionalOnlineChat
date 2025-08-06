$(document).ready(function() {
    // 密码验证
    $('#submitPassword').click(function() {
        const password = $('#passwordInput').val();
        if (!password) {
            $('#errorMessage').text('请输入密码');
            return;
        }
        
        $.ajax({
            url: '/check_password',
            method: 'POST',
            data: { password: password },
            success: function(response) {
                if (response.status === 'success') {
                    // 密码正确，显示结果和编辑表单
                    $('#errorMessage').text('');
                    displayVariables(response);
                    $('#resultContainer').show();
                    $('#editContainer').show();
                } else {
                    // 密码错误
                    $('#errorMessage').text(response.message);
                    $('#resultContainer').hide();
                    $('#editContainer').hide();
                }
            },
            error: function(xhr, status, error) {
                let message = '验证密码时出错';
                if (xhr.responseJSON && xhr.responseJSON.message) {
                    message = xhr.responseJSON.message;
                }
                $('#errorMessage').text(message);
            }
        });
    });

    // 显示变量值
    function displayVariables(data) {
        const resultContainer = $('#resultContainer');
        const editContainer = $('#editContainer');
        
        // 清空容器
        resultContainer.empty();
        editContainer.empty();
        
        // 添加标题
        resultContainer.append('<h3>当前配置值：</h3>');
        editContainer.append('<h3>编辑配置值</h3>');
        
        // 遍历所有配置变量
        for (const [name, value] of Object.entries(data.config_vars)) {
            const description = data.var_descriptions?.[name] || name;
            const type = data.var_types?.[name] || 'string';
            const displayValue = Array.isArray(value) ? JSON.stringify(value) : value;
            
            // 显示当前值
            resultContainer.append(
                `<p><strong>${description}:</strong> <span class="value-${name}">${displayValue}</span></p>`
            );
            
            // 添加编辑表单，根据类型提供不同的输入方式
            let inputElement = '';
            if (type === 'array') {
                inputElement = `<input type="text" value='${displayValue.replace(/'/g, "\\'")}' placeholder="格式: [\\\"IP1\\\",\\\"IP2\\\"] 或 IP1,IP2">`;
            } else {
                inputElement = `<input type="text" value='${displayValue.replace(/'/g, "\\'")}'>`;
            }
            
            editContainer.append(`
                <div class="form-group edit-form-group" data-name="${name}" data-type="${type}">
                    <label>${description}:</label>
                    ${inputElement}
                </div>
            `);
        }
        
        // 添加保存按钮
        editContainer.append('<button id="saveChanges">保存修改</button>');
        editContainer.append('<div id="saveMessage" class="success-message"></div>');
        
        // 绑定保存事件
        bindSaveEvent();
    }

    // 绑定事件函数
    function bindSaveEvent() {
        // 移除旧的监听器
        $('#saveChanges').off('click').on('click', function() {
            const formData = {};
            $('.edit-form-group').each(function() {
                const name = $(this).data('name');
                const type = $(this).data('type');
                let value = $(this).find('input').val().trim();
                
                // 根据类型处理值
                if (type === 'array') {
                    try {
                        // 尝试解析JSON
                        value = JSON.parse(value);
                    } catch(e) {
                        // 如果JSON解析失败，按逗号分割
                        value = value.split(',').map(item => item.trim()).filter(item => item);
                    }
                }
                
                formData[name] = value;
            });
            
            $.ajax({
                url: '/update_variables',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify(formData),
                success: function(response) {
                    if (response.status === 'success') {
                        $('#saveMessage').text('配置修改成功！').removeClass('error-message').addClass('success-message');
                        displayVariables(response);
                    } else {
                        $('#saveMessage').text(response.message).removeClass('success-message').addClass('error-message');
                    }
                },
                error: function(xhr, status, error) {
                    let message = '保存时出错: ' + error;
                    if (xhr.responseJSON?.message) {
                        message = xhr.responseJSON.message;
                    }
                    $('#saveMessage').text(message).removeClass('success-message').addClass('error-message');
                }
            });
        });
    }
});