</div>

<div align="center">

![:name](https://count.getloli.com/@QwenOmini_Chat?name=QwenOmini_Chat&theme=booru-lewd&padding=7&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

</div>

# Qwen Omni 聊天助手

![Qwen Omni](https://img.shields.io/badge/AI-Qwen%20Omni-blue)
![版本](https://img.shields.io/badge/版本-1.0.0-green)
![Python](https://img.shields.io/badge/Python-3.8+-orange)
![许可证](https://img.shields.io/badge/许可证-MIT-lightgrey)

基于阿里云千问（Qwen）Omni系列大模型的多模态聊天应用，支持文字对话、语音交互、图像识别和视频分析等功能。

## 📌 功能特点

- **多模态交互**：支持文字、语音、图片和视频多种输入方式
- **语音功能**：实时语音输入和输出，支持流式播放
- **图像识别**：上传图片并进行智能分析和理解
- **视频分析**：上传视频并对内容进行智能解析
- **多种模型支持**：
  - qwen-omni-turbo
  - qwen-omni-turbo-latest
  - qwen-omni-turbo-2025-03-26
  - qwen2.5-omni-7b
- **双界面模式**：
  - 图形用户界面 (GUI)：美观易用的现代界面
  - 命令行界面 (CLI)：适用于终端环境

## ⚙️ 系统要求

- Python 3.8 或更高版本
- Windows 系统
- 互联网连接（用于API调用）
- DashScope API密钥（可从阿里云获取）

## 🚀 安装指南

### 使用启动脚本自动安装（推荐）

只需运行相应的批处理文件，它将自动设置虚拟环境并安装所有依赖：

- 对于命令行界面：双击 `run_qwen_chat.bat`
- 对于图形界面：双击 `run_qwen_chat_ui.bat`

### 手动安装

1. **克隆或下载本仓库**

2. **创建虚拟环境**：
   ```bash
   python -m venv .venv
   ```

3. **激活虚拟环境**：
   - Windows:
     ```bash
     .venv\Scripts\activate.bat
     ```

4. **安装依赖**：
   - Windows:
     ```bash
     pip install -r requirements.txt
     ```

## 🎮 使用方法

### 图形界面版本

1. 运行 `run_qwen_chat_ui.bat` 或在激活的环境中执行：
   ```bash
   python qwen_chat_ui.py
   ```

2. 首次启动时需要输入DashScope API密钥
3. 选择模型、输入模式和输出模式
4. 进行交互：
   - 文字输入：直接在输入框中输入文字
   - 语音输入：选择"语音录音输入"并点击"开始录音"
   - 图片分析：选择"图片+文字输入"，上传图片并输入问题
   - 视频分析：选择"视频+文字输入"，上传视频并输入问题

### 命令行版本

1. 运行 `run_qwen_chat.bat` 或在激活的环境中执行：
   ```bash
   python qwen_chat.py
   ```

2. 根据提示选择模型和输出模式
3. 特殊命令：
   - `exit` 或 `退出`：结束对话
   - `record` 或 `录音`：使用语音输入
   - `image` 或 `图片`：上传图片进行分析
   - `video` 或 `视频`：上传视频进行分析

## ⚡ 快速使用示例

### 图片分析示例

1. 选择"图片+文字输入"模式
2. 点击"选择图片"按钮选择本地图片
3. 在文本框中输入："这张图片中有什么？"
4. 点击发送，AI将分析图片并回答问题

### 视频分析示例

1. 选择"视频+文字输入"模式
2. 点击"选择视频"按钮选择本地视频
3. 在文本框中输入："概述这个视频的内容"
4. 点击发送，AI将分析视频并提供内容概述

## 📋 常见问题

1. **找不到虚拟环境**：确保已正确创建虚拟环境。使用启动脚本可自动创建。

2. **缺少依赖**：如果程序无法运行，可能是缺少必要的依赖包。使用以下命令安装：
   ```bash
   pip install -r requirements.txt
   ```

3. **PyAudio安装问题**：在Windows上安装PyAudio可能需要先安装Visual C++ Build Tools。

4. **图片上传失败**：确保图片格式为常见格式(PNG, JPG, JPEG, BMP, GIF)，且文件大小不超过5MB。

5. **权限问题**：在Ubuntu系统上，如果无法访问音频设备，可能需要将用户添加到audio组。

## 🔧 高级配置

API密钥和模型选择会保存在`config.json`文件中。您可以手动编辑此文件更改配置：

```json
{
  "api_key": "你的DashScope API密钥",
  "model": "qwen2.5-omni-7b"
}
```

## 📄 许可证

本项目采用MIT许可证。详情请参阅LICENSE文件。

## 🙏 致谢

- 感谢阿里云提供的千问Omni模型API
- 感谢所有开源贡献者
