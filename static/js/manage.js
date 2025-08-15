$(document).ready(function() {
    // 页面加载直接渲染变量和编辑表单
    displayVariables({
        config_vars: configVars,
        var_descriptions: varDescriptions,
        var_types: varTypes
    });

    // 显示变量值和编辑表单
    function displayVariables(data) {
        const editContainer = $('#editContainer');
        editContainer.empty();
        editContainer.append('<h3>编辑配置值</h3>');
        for (const [name, value] of Object.entries(data.config_vars)) {
            const description = data.var_descriptions?.[name] || name;
            const type = data.var_types?.[name] || 'string';
            const displayValue = Array.isArray(value) ? JSON.stringify(value) : value;
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
        editContainer.append('<button id="saveChanges">保存修改</button>');
        // 绑定保存事件
        bindSaveEvent();
    }

    function bindSaveEvent() {
        $('#saveChanges').off('click').on('click', function() {
            const formData = {};
            $('.edit-form-group').each(function() {
                const name = $(this).data('name');
                const type = $(this).data('type');
                let value = $(this).find('input').val().trim();
                if (type === 'array') {
                    try {
                        value = JSON.parse(value);
                    } catch(e) {
                        value = value.split(',').map(item => item.trim()).filter(item => item);
                    }
                }
                formData[name] = value;
            });
            // 弹窗输入密码
            const password = prompt('请输入管理密码：');
            if (!password) {
                $('#saveMessage').text('未输入密码，无法保存！').removeClass('success-message').addClass('error-message');
                return;
            }
            formData._password = password; // 增加密码字段
            $.ajax({
                url: '/config/update_variables',
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