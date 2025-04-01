# 手动激活虚拟环境指南

本指南介绍如何在不使用启动脚本的情况下，手动切换到项目目录并激活虚拟环境。

## Windows系统

在Windows系统上，可以按照以下步骤操作：

### 使用命令提示符(CMD)

1. 打开命令提示符(按Win+R，输入cmd，回车)
2. 切换到项目目录:
   ```
   cd c:\Users\29684\Desktop\api
   ```
3. 激活虚拟环境:
   ```
   .venv\Scripts\activate.bat
   ```
4. 运行程序:
   ```
   python qwen_chat.py
   ```
5. 使用完毕后，退出虚拟环境:
   ```
   deactivate
   ```

### 使用PowerShell

1. 打开PowerShell(按Win+X，选择Windows PowerShell)
2. 切换到项目目录:
   ```
   cd C:\Users\29684\Desktop\api
   ```
3. 激活虚拟环境:
   ```
   .\.venv\Scripts\Activate.ps1
   ```
   注意：如果遇到执行策略限制，需要先执行:
   ```
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
   ```
4. 运行程序:
   ```
   python qwen_chat.py
   ```
5. 使用完毕后，退出虚拟环境:
   ```
   deactivate
   ```

## 新增功能: 图片上传与识别

通过Qwen Omni模型，现在可以上传图片并让AI分析图片内容：

1. 在输入模式中选择"图片+文字输入"
2. 点击"选择图片"按钮选择本地图片文件
3. 在文本框中输入关于图片的问题或说明
4. 点击发送，AI会分析图片并回答问题

您也可以在命令行版本中使用以下命令：
- 输入"image"或"图片"命令来上传图片
- 按提示选择图片文件和输入问题

## 新增功能: 视频上传与分析

通过Qwen Omni模型，现在可以上传视频并让AI分析视频内容：

1.  在输入模式中选择"视频+文字输入"
2.  点击"选择视频"按钮选择本地视频文件
3.  在文本框中输入关于视频的问题或说明
4.  点击发送，AI会分析视频并回答问题

您也可以在命令行版本中使用以下命令：

*   输入"video"或"视频"命令来上传视频
*   按提示选择视频文件和输入问题

## Ubuntu系统

如果你使用的是Ubuntu系统，可以按照以下步骤操作：

1. 打开终端(按Ctrl+Alt+T)
2. 切换到项目目录:
   ```
   cd ~/Desktop/api  # 路径可能需要调整
   ```
3. 激活虚拟环境:
   ```
   source .venv/bin/activate
   ```
4. 运行程序:
   ```
   python3 qwen_chat_ubuntu.py
   ```
5. 使用完毕后，退出虚拟环境:
   ```
   deactivate
   ```

## 常见问题

1. **找不到虚拟环境**：确保你已经创建了虚拟环境。如果没有，可以使用以下命令创建:
   - Windows: `python -m venv .venv`
   - Ubuntu: `python3 -m venv .venv`

2. **缺少依赖**：如果程序无法运行，可能是缺少必要的依赖包。使用以下命令安装:
   - Windows: `pip install -r requirements.txt`
   - Ubuntu: `pip install -r requirements_ubuntu.txt`

3. **图片上传失败**：确保图片格式是常见格式(PNG, JPG, JPEG, BMP, GIF)，且文件大小不要过大（建议小于5MB）。

4. **权限问题**：在Ubuntu系统上，如果无法访问音频设备，可能需要将用户添加到audio组:
   ```
   sudo adduser $USER audio
   ```
   然后注销并重新登录系统。
