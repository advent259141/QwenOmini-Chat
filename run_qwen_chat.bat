@echo off
echo ===================================
echo    启动 Qwen Omni 聊天程序
echo ===================================
echo.
echo 支持的功能:
echo - 文字对话
echo - 语音输入/输出
echo - 图片上传与分析
echo - 视频上传与分析
echo - 多种模型选择(支持qwen-omni-turbo等多种模型)
echo.
echo 特殊命令:
echo - 输入 'exit' 或 '退出' 结束对话
echo - 输入 'record' 或 '录音' 使用语音输入
echo - 输入 'image' 或 '图片' 上传图片
echo - 输入 'video' 或 '视频' 上传视频
echo.
echo 首次使用说明:
echo - 首次使用需要输入DashScope API密钥
echo - 密钥将保存到config.json文件中
echo - 模型选择也会保存在配置文件中
echo - 后续启动将自动读取上次的设置
echo ===================================
echo.

:: 检查虚拟环境是否存在
if not exist ".venv\Scripts\activate.bat" (
    echo [错误] 未找到虚拟环境，尝试创建新的虚拟环境...
    python -m venv .venv
    
    if errorlevel 1 (
        echo [错误] 无法创建虚拟环境，请确保已安装Python 3.8+
        echo.
        pause
        exit /b 1
    )
    
    echo [成功] 已创建虚拟环境，正在安装依赖...
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
    
    if errorlevel 1 (
        echo [错误] 安装依赖失败，请检查网络连接或手动运行 pip install -r requirements.txt
        echo.
        pause
        exit /b 1
    )
    
    echo [成功] 依赖安装完成！
) else (
    echo [信息] 找到现有虚拟环境，正在激活...
    call .venv\Scripts\activate.bat
)

:: 检查是否存在配置文件
if exist "config.json" (
    echo [信息] 已找到配置文件，将使用保存的API密钥
) else (
    echo [提示] 未找到配置文件，首次运行将提示输入API密钥
)

echo [信息] 正在启动 Qwen Omni 聊天程序...
echo.
echo ===================================
echo 程序启动中...按Ctrl+C退出程序
echo ===================================
echo.

:: 运行Python脚本
python qwen_chat.py

:: 如果程序异常退出，等待用户确认
if errorlevel 1 (
    echo.
    echo [错误] 程序异常退出，错误代码: %errorlevel%
    pause
)

:: 退出虚拟环境
call deactivate

exit /b 0
