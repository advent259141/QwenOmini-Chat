@echo off
echo ===================================
echo    启动 Qwen Omni 聊天程序 (UI版)
echo ===================================
echo.
echo 支持的功能:
echo - 文字对话
echo - 语音输入/输出
echo - 图片上传与分析
echo - 视频上传与分析
echo - 多种模型选择(支持qwen-omni-turbo等多种模型)
echo.
echo 界面使用说明:
echo 1. 选择输入模式 (文字/语音/图片/视频)
echo 2. 选择输出模式 (文字/语音)
echo 3. 选择使用的AI模型 (可在下拉框中切换)
echo 4. 图片/视频模式可选择本地文件并进行分析
echo 5. 可拖动窗口顶部移动界面
echo.
echo API密钥和配置说明:
echo - 首次使用需要输入DashScope API密钥
echo - 如无密钥将弹出输入窗口
echo - 密钥和模型选择将保存到config.json文件中
echo - 下次启动将自动读取上次的设置
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
    pip install PyQt5
    
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
    echo [提示] 未找到配置文件，将弹出窗口要求输入API密钥
)

echo [信息] 正在启动 Qwen Omni 聊天程序 (UI版)...
echo.
echo ===================================
echo 程序启动中...
echo ===================================
echo.

:: 运行Python脚本
python qwen_chat_ui.py

:: 如果程序异常退出，等待用户确认
if errorlevel 1 (
    echo.
    echo [错误] 程序异常退出，错误代码: %errorlevel%
    pause
)

:: 退出虚拟环境
call deactivate

exit /b 0