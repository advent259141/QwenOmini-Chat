import sys
import os
import time
import threading
import queue
import signal
import wave
import pyaudio
import base64
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QTextEdit, QComboBox, 
                            QLabel, QLineEdit, QProgressBar, QMessageBox, 
                            QFileDialog, QSpinBox, QSplitter, QGraphicsBlurEffect,
                            QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
                            QDialog, QInputDialog)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QTimer, QEvent, QThread
from PyQt5.QtGui import QPalette, QColor, QFont, QIcon, QTextCursor, QPainter, QPixmap, QPen

# 导入原始的qwen_chat模块
import qwen_chat

# 创建消息队列用于线程间通信
message_queue = queue.Queue()

# 自定义信号类，用于线程间通信
class ChatSignals(QObject):
    append_text = pyqtSignal(str)
    append_system_message = pyqtSignal(str)
    chat_completed = pyqtSignal()
    update_progress = pyqtSignal(int)
    recording_status = pyqtSignal(str)
    enable_input = pyqtSignal(bool)
    process_queue = pyqtSignal()
    display_image = pyqtSignal(str)

# 毛玻璃效果窗口基类
class AcrylicEffect(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        
        # 设置阴影效果
        self.shadow = QGraphicsDropShadowEffect()
        self.shadow.setBlurRadius(20)
        self.shadow.setColor(QColor(0, 0, 0, 50))
        self.shadow.setOffset(0, 2)
        
        # 应用效果
        self.setGraphicsEffect(self.shadow)
    
    def paintEvent(self, event):
        """实现真正的毛玻璃效果"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 创建淡蓝粉色背景
        background = QColor(240, 230, 255, 160)  # 淡蓝粉色半透明
        painter.setPen(Qt.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(self.rect(), 15, 15)
        
        # 添加边框高光
        highlight = QColor(255, 255, 255, 70)
        painter.setPen(QPen(highlight, 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 15, 15)
        
        # 添加底部阴影
        shadow = QColor(0, 0, 0, 40)
        painter.setPen(QPen(shadow, 1))
        painter.drawLine(
            self.rect().left() + 15, self.rect().bottom() - 1,
            self.rect().right() - 15, self.rect().bottom() - 1
        )

# 录音线程类
class RecordingThread(QThread):
    finished = pyqtSignal(object, object)
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    
    def __init__(self, duration):
        super().__init__()
        self.duration = duration
        self.start_time = 0
        self.is_interrupted = False
    
    def run(self):
        try:
            self.start_time = time.time()
            filename = f"input_{int(self.start_time)}.wav"
            
            # 发送状态更新
            self.status.emit("正在录音...")
            
            try:
                # 使用自定义参数调用录音函数
                record_path = Path("audio_input") / filename
                record_path.parent.mkdir(exist_ok=True)
                
                # 初始化PyAudio
                p = pyaudio.PyAudio()
                stream = p.open(format=pyaudio.paInt16, 
                              channels=1,
                              rate=16000,
                              input=True,
                              frames_per_buffer=1024)
                
                frames = []
                max_chunks = int(16000 / 1024 * self.duration)
                
                # 录音循环
                for i in range(max_chunks):
                    if self.is_interrupted:
                        break
                    
                    # 更新进度
                    if i % int(16000 / 1024) == 0:  # 每秒更新一次
                        elapsed = time.time() - self.start_time
                        progress = min(int(elapsed / self.duration * 100), 100)
                        self.progress.emit(progress)
                    
                    try:
                        data = stream.read(1024)
                        frames.append(data)
                    except IOError as e:
                        # 忽略溢出错误，继续录音
                        self.status.emit(f"\r[警告: {e}]")
                
                # 停止和关闭流
                stream.stop_stream()
                stream.close()
                p.terminate()
                
                # 检查是否录到了内容
                if not frames:
                    self.status.emit("[录音为空，未保存文件]")
                    self.finished.emit(None, None)
                    return
                
                # 保存录音
                wf = wave.open(str(record_path), 'wb')
                wf.setnchannels(1)
                wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
                wf.setframerate(16000)
                wf.writeframes(b''.join(frames))
                wf.close()
                
                actual_duration = len(frames) * 1024 / 16000
                self.status.emit(f"[已保存录音，实际长度: {actual_duration:.1f}秒]")
                
                # 编码音频
                base64_audio = None
                with open(record_path, "rb") as audio_file:
                    base64_audio = base64.b64encode(audio_file.read()).decode("utf-8")
                
                self.finished.emit(record_path, base64_audio)
                
            except Exception as e:
                import traceback
                self.status.emit(f"[录音错误: {str(e)}]")
                print(traceback.format_exc())
                self.finished.emit(None, None)
                
        except Exception as e:
            import traceback
            self.status.emit(f"[录音错误: {str(e)}]")
            print(traceback.format_exc())
            self.finished.emit(None, None)
    
    def interrupt(self):
        """提供一个方法来中断录音"""
        self.is_interrupted = True
        self.status.emit("[录音被用户中断]")

# 聊天线程类
class ChatThread(QThread):
    def __init__(self, user_input, messages, use_voice, use_audio, use_streaming_audio, base64_audio, base64_image=None, image_type="png", base64_video=None, selected_model=None):
        super().__init__()
        self.user_input = user_input
        self.messages = messages.copy()  # 复制消息列表以避免线程安全问题
        self.use_voice = use_voice
        self.use_audio = use_audio
        self.use_streaming_audio = use_streaming_audio
        self.base64_audio = base64_audio
        self.base64_image = base64_image
        self.image_type = image_type
        self.base64_video = base64_video
        self.selected_model = selected_model or qwen_chat.get_selected_model()
    
    def run(self):
        try:
            # 添加系统消息
            message_queue.put(("system", "正在思考..."))
            
            # 设置模态
            modalities = ["text", "audio"] if self.use_audio else ["text"]
            
            # 准备消息内容
            if self.use_voice:
                # 构建多模态消息
                message_content = [
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": f"data:;base64,{self.base64_audio}",
                            "format": "wav",
                        },
                    },
                    {"type": "text", "text": self.user_input}
                ]
                self.messages.append({"role": "user", "content": message_content})
            elif self.base64_image:
                # 构建包含图片的消息
                message_content = [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/{self.image_type};base64,{self.base64_image}"
                        }
                    },
                    {"type": "text", "text": self.user_input}
                ]
                self.messages.append({"role": "user", "content": message_content})
            elif self.base64_video:
                # 构建包含视频的消息
                message_content = [
                    {
                        "type": "video_url",
                        "video_url": {
                            "url": f"data:video/mp4;base64,{self.base64_video}"
                        }
                    },
                    {"type": "text", "text": self.user_input}
                ]
                self.messages.append({"role": "user", "content": message_content})
            else:
                # 普通文本消息
                self.messages.append({"role": "user", "content": self.user_input})
            
            # 调用API
            completion_args = {
                "model": self.selected_model,  # 使用选定的模型
                "messages": self.messages,
                "modalities": modalities,
                "stream": True,
                "stream_options": {"include_usage": True},
            }
            
            # 如果启用了音频，添加音频配置
            if self.use_audio:
                completion_args["audio"] = {"voice": "Cherry", "format": "wav"}
            
            # 创建客户端
            client = qwen_chat.client
            
            # 调用API
            completion = client.chat.completions.create(**completion_args)
            
            # 收集完整的回复文本和音频内容
            full_response = ""
            audio_string = ""
            
            message_queue.put(("text", "助手: "))
            
            for chunk in completion:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        full_response += delta.content
                        message_queue.put(("text", delta.content))
                    
                    # 处理音频数据
                    if self.use_audio and hasattr(delta, 'audio') and delta.audio:
                        try:
                            # 获取音频数据
                            if isinstance(delta.audio, dict) and "data" in delta.audio:
                                chunk_audio_data = delta.audio["data"]
                                # 如果是实时流式播放，则立即播放
                                if self.use_streaming_audio:
                                    qwen_chat.play_audio_streaming(chunk_audio_data)
                                # 否则，将数据累加起来
                                else:
                                    audio_string += chunk_audio_data
                        except Exception as e:
                            # 如果有文本记录，则输出
                            if isinstance(delta.audio, dict) and "transcript" in delta.audio:
                                message_queue.put(("system", f"[音频文本: {delta.audio['transcript']}]"))
                            else:
                                message_queue.put(("system", f"[处理音频数据时出错: {e}]"))
                
                elif hasattr(chunk, 'usage'):
                    message_queue.put(("system", 
                        f"[使用统计: 输入tokens: {chunk.usage.prompt_tokens}, "
                        f"输出tokens: {chunk.usage.completion_tokens}]"
                    ))
            
            # 返回结果
            return_data = {
                "full_response": full_response,
                "audio_string": audio_string,
                "messages": self.messages
            }
            
            # 将结果放入队列
            message_queue.put(("result", return_data))
            
        except Exception as e:
            import traceback
            message_queue.put(("system", f"发生错误: {str(e)}"))
            message_queue.put(("system", traceback.format_exc()))
            message_queue.put(("error", None))

# API密钥输入对话框
class ApiKeyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置API密钥")
        self.setFixedSize(400, 150)
        
        # 设置无边框窗口
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 创建主布局
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        
        # 创建毛玻璃效果容器
        self.container = AcrylicEffect()
        self.container_layout = QVBoxLayout(self.container)
        
        # 添加说明标签
        self.info_label = QLabel("首次使用需要输入DashScope API密钥")
        self.info_label.setStyleSheet("font-size: 14px; color: #333; font-weight: bold;")
        self.container_layout.addWidget(self.info_label)
        
        # 添加API密钥输入框
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("请输入您的DashScope API密钥")
        self.api_key_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 180);
                border: 1px solid rgba(200, 200, 200, 150);
                border-radius: 8px;
                padding: 8px;
                font-size: 14px;
            }
        """)
        self.container_layout.addWidget(self.api_key_input)
        
        # 添加按钮布局
        self.button_layout = QHBoxLayout()
        
        # 确认按钮
        self.ok_button = QPushButton("确认")
        self.ok_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(100, 150, 255, 200);
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 8px;
                padding: 10px 15px;
            }
            QPushButton:hover {
                background-color: rgba(120, 170, 255, 220);
            }
        """)
        self.ok_button.clicked.connect(self.accept)
        
        # 退出按钮
        self.exit_button = QPushButton("退出程序")
        self.exit_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 100, 100, 200);
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 8px;
                padding: 10px 15px;
            }
            QPushButton:hover {
                background-color: rgba(255, 80, 80, 220);
            }
        """)
        self.exit_button.clicked.connect(self.reject)
        
        # 添加按钮到布局
        self.button_layout.addWidget(self.ok_button)
        self.button_layout.addWidget(self.exit_button)
        
        # 添加按钮布局
        self.container_layout.addSpacing(10)
        self.container_layout.addLayout(self.button_layout)
        
        # 添加容器到主布局
        self.layout.addWidget(self.container)
    
    def get_api_key(self):
        return self.api_key_input.text().strip()

# 主窗口
class QwenChatUI(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 检查是否有保存的API密钥
        self.check_api_key()
        
        # 设置窗口标题和大小
        self.setWindowTitle("Qwen Omni 聊天助手")
        self.resize(1000, 700)
        
        # 设置无边框窗口
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 设置窗口背景
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                          stop:0 #f0f8ff, stop:1 #e6e6fa);
            }
            QTextEdit, QLineEdit, QComboBox, QPushButton, QSpinBox {
                border-radius: 8px;
                padding: 8px;
            }
            QTextEdit {
                background-color: rgba(255, 255, 255, 180);
                border: 1px solid rgba(200, 200, 200, 150);
                font-size: 14px;
            }
            QLineEdit {
                background-color: rgba(255, 255, 255, 180);
                border: 1px solid rgba(200, 200, 200, 150);
                font-size: 14px;
            }
            QPushButton {
                background-color: rgba(100, 150, 255, 200);
                color: white;
                font-weight: bold;
                border: none;
                padding: 10px 15px;
            }
            QPushButton:hover {
                background-color: rgba(120, 170, 255, 220);
            }
            QPushButton:pressed {
                background-color: rgba(80, 130, 235, 200);
            }
            QComboBox {
                background-color: rgba(255, 255, 255, 180);
                border: 1px solid rgba(200, 200, 200, 150);
                padding: 5px;
            }
            QLabel {
                font-size: 14px;
                color: #333;
            }
            QProgressBar {
                border: 1px solid rgba(200, 200, 200, 150);
                border-radius: 5px;
                background-color: rgba(255, 255, 255, 200);
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: rgba(100, 150, 255, 200);
                border-radius: 5px;
            }
        """)
        
        # 创建主窗口部件
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # 创建主布局
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)
        
        # 创建标题栏
        self.title_bar = QWidget()
        self.title_bar.setFixedHeight(40)
        self.title_bar_layout = QHBoxLayout(self.title_bar)
        self.title_bar_layout.setContentsMargins(10, 0, 10, 0)
        
        # 标题标签
        self.title_label = QLabel("Qwen Omni 聊天助手")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #555;")
        
        # 关闭按钮
        self.close_button = QPushButton("×")
        self.close_button.setFixedSize(30, 30)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 100, 100, 200);
                color: white;
                font-weight: bold;
                border-radius: 15px;
                font-size: 20px;
            }
            QPushButton:hover {
                background-color: rgba(255, 80, 80, 220);
            }
        """)
        self.close_button.clicked.connect(self.close)
        
        # 最小化按钮
        self.minimize_button = QPushButton("_")
        self.minimize_button.setFixedSize(30, 30)
        self.minimize_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(100, 150, 255, 200);
                color: white;
                font-weight: bold;
                border-radius: 15px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: rgba(120, 170, 255, 220);
            }
        """)
        self.minimize_button.clicked.connect(self.showMinimized)
        
        # 添加到标题栏布局
        self.title_bar_layout.addWidget(self.title_label)
        self.title_bar_layout.addStretch()
        self.title_bar_layout.addWidget(self.minimize_button)
        self.title_bar_layout.addWidget(self.close_button)
        
        # 添加标题栏到主布局
        self.main_layout.addWidget(self.title_bar)
        
        # 创建毛玻璃效果的聊天区域
        self.chat_container = AcrylicEffect()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(15, 15, 15, 15)
        
        # 创建聊天历史显示区域
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setPlaceholderText("聊天记录将显示在这里...")
        self.chat_history.setStyleSheet("background-color: rgba(255, 255, 255, 120);")
        
        # 添加阴影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 0)
        self.chat_history.setGraphicsEffect(shadow)
        
        self.chat_layout.addWidget(self.chat_history)
        
        # 创建底部控制区域
        self.bottom_container = AcrylicEffect()
        self.bottom_layout = QVBoxLayout(self.bottom_container)
        self.bottom_layout.setContentsMargins(15, 15, 15, 15)
        
        # 创建设置区域
        self.settings_layout = QHBoxLayout()
        
        # 模型选择
        self.model_label = QLabel("模型:")
        self.model_combo = QComboBox()
        for model in qwen_chat.AVAILABLE_MODELS:
            self.model_combo.addItem(model)
        
        # 设置当前选中的模型
        current_model = qwen_chat.get_selected_model()
        if current_model in qwen_chat.AVAILABLE_MODELS:
            index = qwen_chat.AVAILABLE_MODELS.index(current_model)
            self.model_combo.setCurrentIndex(index)
        
        # 连接信号
        self.model_combo.currentIndexChanged.connect(self.model_changed)
        
        # 输出模式选择
        self.output_mode_label = QLabel("输出模式:")
        self.output_mode_combo = QComboBox()
        self.output_mode_combo.addItem("仅文字输出")
        self.output_mode_combo.addItem("文字+语音输出(完整收到后播放)")
        if qwen_chat.PYAUDIO_AVAILABLE:
            self.output_mode_combo.addItem("文字+语音输出(实时流式播放)")
        
        # 输入模式选择
        self.input_mode_label = QLabel("输入模式:")
        self.input_mode_combo = QComboBox()
        self.input_mode_combo.addItem("键盘文字输入")
        if qwen_chat.PYAUDIO_AVAILABLE:
            self.input_mode_combo.addItem("语音录音输入")
        self.input_mode_combo.addItem("图片+文字输入")
        self.input_mode_combo.addItem("视频+文字输入")
        self.input_mode_combo.currentIndexChanged.connect(self.update_input_mode)
        
        # 添加退出按钮
        self.exit_button = QPushButton("退出程序")
        self.exit_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 100, 100, 200);
                color: white;
                font-weight: bold;
                border: none;
                padding: 10px 15px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: rgba(255, 80, 80, 220);
            }
        """)
        self.exit_button.clicked.connect(self.close)
        
        # 添加到设置布局
        self.settings_layout.addWidget(self.model_label)
        self.settings_layout.addWidget(self.model_combo)
        self.settings_layout.addWidget(self.output_mode_label)
        self.settings_layout.addWidget(self.output_mode_combo)
        self.settings_layout.addWidget(self.input_mode_label)
        self.settings_layout.addWidget(self.input_mode_combo)
        self.settings_layout.addStretch()
        self.settings_layout.addWidget(self.exit_button)
        
        # 添加设置布局到底部布局
        self.bottom_layout.addLayout(self.settings_layout)
        
        # 创建录音控制区域
        self.recording_layout = QHBoxLayout()
        self.duration_label = QLabel("录音时长(秒):")
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 60)
        self.duration_spin.setValue(5)
        
        self.record_button = QPushButton("开始录音")
        self.record_button.clicked.connect(self.start_recording)
        
        self.stop_record_button = QPushButton("停止录音")
        self.stop_record_button.clicked.connect(self.stop_recording)
        self.stop_record_button.setEnabled(False)
        self.recording_status_label = QLabel("")
        
        self.recording_layout.addWidget(self.duration_label)
        self.recording_layout.addWidget(self.duration_spin)
        self.recording_layout.addWidget(self.record_button)
        self.recording_layout.addWidget(self.stop_record_button)
        self.recording_layout.addWidget(self.recording_status_label)
        self.recording_layout.addStretch()
        
        # 录音进度条
        self.recording_progress = QProgressBar()
        self.recording_progress.setRange(0, 100)
        self.recording_progress.setValue(0)
        self.recording_progress.setVisible(False)
        
        # 创建图片上传区域
        self.image_layout = QHBoxLayout()
        self.image_path_label = QLabel("未选择图片")
        self.browse_image_button = QPushButton("选择图片")
        self.browse_image_button.clicked.connect(self.browse_image)
        self.clear_image_button = QPushButton("清除图片")
        self.clear_image_button.clicked.connect(self.clear_image)
        
        self.image_layout.addWidget(QLabel("图片:"))
        self.image_layout.addWidget(self.image_path_label, 1)
        self.image_layout.addWidget(self.browse_image_button)
        self.image_layout.addWidget(self.clear_image_button)
        
        # 图片预览标签
        self.image_preview = QLabel("图片预览")
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.setMinimumHeight(100)
        self.image_preview.setMaximumHeight(200)
        self.image_preview.setStyleSheet("background-color: rgba(240, 240, 240, 120);")
        
        # 创建视频上传区域
        self.video_layout = QHBoxLayout()
        self.video_path_label = QLabel("未选择视频")
        self.browse_video_button = QPushButton("选择视频")
        self.browse_video_button.clicked.connect(self.browse_video)
        self.clear_video_button = QPushButton("清除视频")
        self.clear_video_button.clicked.connect(self.clear_video)
        
        self.video_layout.addWidget(QLabel("视频:"))
        self.video_layout.addWidget(self.video_path_label, 1)
        self.video_layout.addWidget(self.browse_video_button)
        self.video_layout.addWidget(self.clear_video_button)
        
        # 视频预览标签（可以考虑显示视频的第一帧）
        self.video_preview = QLabel("视频预览")
        self.video_preview.setAlignment(Qt.AlignCenter)
        self.video_preview.setMinimumHeight(100)
        self.video_preview.setMaximumHeight(200)
        self.video_preview.setStyleSheet("background-color: rgba(240, 240, 240, 120);")
        
        # 创建文本输入区域
        self.input_layout = QHBoxLayout()
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("在这里输入消息...")
        self.text_input.setMaximumHeight(100)
        
        # 发送按钮
        self.send_button = QPushButton("发送")
        self.send_button.setMinimumWidth(100)
        self.send_button.clicked.connect(self.send_message)
        
        # 添加到输入布局
        self.input_layout.addWidget(self.text_input)
        self.input_layout.addWidget(self.send_button)
        
        # 添加录音布局和输入布局到底部布局
        self.bottom_layout.addLayout(self.recording_layout)
        self.bottom_layout.addWidget(self.recording_progress)
        self.bottom_layout.addLayout(self.image_layout)
        self.bottom_layout.addWidget(self.image_preview)
        self.bottom_layout.addLayout(self.video_layout)
        self.bottom_layout.addWidget(self.video_preview)
        self.bottom_layout.addLayout(self.input_layout)
        
        # 添加聊天区域和底部控制区域到主布局
        self.main_layout.addWidget(self.chat_container, 7)
        self.main_layout.addWidget(self.bottom_container, 3)
        
        # 初始化变量
        self.messages = []
        self.recording_thread = None
        self.chat_thread = None
        self.recording_timer = None
        self.audio_path = None
        self.base64_audio = None
        self.signals = ChatSignals()
        self.image_path = None
        self.base64_image = None
        self.image_type = "png"
        self.video_path = None
        self.base64_video = None
        self.selected_model = current_model
        
        # 连接信号
        self.signals.append_text.connect(self.append_to_chat)
        self.signals.append_system_message.connect(self.append_system_message)
        self.signals.chat_completed.connect(self.on_chat_completed)
        self.signals.update_progress.connect(self.update_recording_progress)
        self.signals.recording_status.connect(self.update_recording_status)
        self.signals.enable_input.connect(self.set_input_enabled)
        self.signals.process_queue.connect(self.process_message_queue)
        self.signals.display_image.connect(self.show_image_preview)
        
        # 设置定时器处理消息队列
        self.queue_timer = QTimer(self)
        self.queue_timer.timeout.connect(self.process_message_queue)
        self.queue_timer.start(100)
        
        # 初始化UI状态
        self.update_input_mode()
        
        # 欢迎消息
        self.append_system_message("欢迎使用Qwen Omni聊天助手！\n请选择输入和输出模式，然后开始聊天。")
        
        # 设置UI特效
        self.setup_ui_effects()
    
    def check_api_key(self):
        """检查API密钥，如果没有则弹窗要求输入"""
        api_key = qwen_chat.load_api_key()
        if not api_key:
            dialog = ApiKeyDialog(self)
            if dialog.exec_() == QDialog.Accepted:
                api_key = dialog.get_api_key()
                if api_key.strip():
                    # 保存API密钥
                    if qwen_chat.save_api_key(api_key):
                        # 重新初始化客户端
                        qwen_chat.API_KEY = api_key
                        os.environ["DASHSCOPE_API_KEY"] = api_key
                        qwen_chat.client = OpenAI(
                            api_key=api_key,
                            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                        )
                        QMessageBox.information(self, "成功", "API密钥已保存，下次启动将自动读取")
                    else:
                        QMessageBox.warning(self, "警告", "API密钥保存失败，程序可能无法正常工作")
                else:
                    # 如果用户没有输入密钥就点了确认，退出程序
                    QMessageBox.critical(self, "错误", "未提供API密钥，程序将退出")
                    sys.exit(1)
            else:
                # 如果用户点击了退出按钮，直接退出程序
                sys.exit(0)

    def setup_ui_effects(self):
        """设置UI特效"""
        self.chat_history.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical {
                border: none;
                background: rgba(200, 200, 200, 100);
                width: 10px;
                margin: 0px 0px 0px 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: rgba(100, 150, 255, 150);
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        for button in [self.send_button, self.record_button, self.exit_button]:
            button.setAutoFillBackground(False)
            button.setFlat(True)
            
            button.enterEvent = lambda e, b=button: self.button_hover_effect(e, b, True)
            button.leaveEvent = lambda e, b=button: self.button_hover_effect(e, b, False)

    def button_hover_effect(self, event, button, hover):
        """按钮悬停效果"""
        if button == self.exit_button:
            if hover:
                button.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(255, 80, 80, 220);
                        color: white;
                        font-weight: bold;
                        border: none;
                        padding: 10px 15px;
                        border-radius: 8px;
                    }
                """)
            else:
                button.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(255, 100, 100, 200);
                        color: white;
                        font-weight: bold;
                        border: none;
                        padding: 10px 15px;
                        border-radius: 8px;
                    }
                """)
        else:
            if hover:
                button.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(120, 170, 255, 220);
                        color: white;
                        font-weight: bold;
                        border: none;
                        padding: 10px 15px;
                        border-radius: 8px;
                    }
                """)
            else:
                button.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(100, 150, 255, 200);
                        color: white;
                        font-weight: bold;
                        border: none;
                        padding: 10px 15px;
                        border-radius: 8px;
                    }
                """)
    
    def mousePressEvent(self, event):
        """鼠标按下事件处理"""
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件处理"""
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()
    
    def process_message_queue(self):
        """处理消息队列中的消息"""
        try:
            while not message_queue.empty():
                msg_type, msg_content = message_queue.get_nowait()
                
                if msg_type == "text":
                    self.append_to_chat(msg_content)
                elif msg_type == "system":
                    self.append_system_message(msg_content)
                elif msg_type == "result":
                    self.handle_chat_result(msg_content)
                elif msg_type == "error":
                    self.on_chat_completed()
        except Exception as e:
            print(f"处理消息队列时出错: {e}")
    
    def handle_chat_result(self, result):
        """处理聊天结果"""
        if not result:
            self.on_chat_completed()
            return
        
        full_response = result.get("full_response", "")
        audio_string = result.get("audio_string", "")
        self.messages = result.get("messages", self.messages)
        
        if len(self.messages) >= 2 and isinstance(self.messages[-2]["content"], list):
            user_input = self.messages[-2].get("content", "")
            if isinstance(user_input, list):
                for item in user_input:
                    if item.get("type") == "text":
                        user_input = item.get("text", "")
                        break
            self.messages[-2] = {"role": "user", "content": user_input}
        
        if len(self.messages) > 0 and self.messages[-1].get("role") != "assistant":
            self.messages.append({"role": "assistant", "content": full_response})
        
        use_audio = self.output_mode_combo.currentIndex() > 0
        use_streaming_audio = self.output_mode_combo.currentIndex() == 2
        
        if use_audio and not use_streaming_audio and audio_string:
            audio_filename = f"response_{int(time.time())}.wav"
            try:
                self.append_system_message("[正在处理音频...]")
                audio_path = qwen_chat.save_audio_base64(audio_string, audio_filename)
                if audio_path:
                    self.append_system_message(f"[音频已保存到 {audio_path}]")
                    self.append_system_message("[播放语音回复...]")
                    qwen_chat.play_audio_system(audio_path)
                else:
                    self.append_system_message("[无法处理音频内容]")
            except Exception as e:
                self.append_system_message(f"[处理音频时出错: {str(e)}]")
        
        self.on_chat_completed()
    
    def update_input_mode(self):
        """根据选择的输入模式更新UI"""
        use_voice = self.input_mode_combo.currentIndex() == 1
        use_image = self.input_mode_combo.currentIndex() == 2
        use_video = self.input_mode_combo.currentIndex() == 3
        
        self.text_input.setVisible(not use_voice)
        self.duration_label.setVisible(use_voice)
        self.duration_spin.setVisible(use_voice)
        self.record_button.setVisible(use_voice)
        self.stop_record_button.setVisible(use_voice)
        self.recording_progress.setVisible(False)
        
        self.image_path_label.setVisible(use_image)
        self.browse_image_button.setVisible(use_image)
        self.clear_image_button.setVisible(use_image)
        self.image_preview.setVisible(use_image)
        
        self.video_path_label.setVisible(use_video)
        self.browse_video_button.setVisible(use_video)
        self.clear_video_button.setVisible(use_video)
        self.video_preview.setVisible(use_video)
        
        if not use_voice:
            self.audio_path = None
            self.base64_audio = None
        
        if not use_image:
            self.clear_image()
        
        if not use_video:
            self.clear_video()
    
    def browse_image(self):
        """浏览并选择图片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        
        if file_path:
            try:
                self.image_path = file_path
                self.image_type = Path(file_path).suffix.lower().replace(".", "")
                if self.image_type not in ["png", "jpg", "jpeg", "bmp", "gif"]:
                    self.image_type = "png"
                
                self.base64_image = qwen_chat.encode_image(file_path)
                
                self.image_path_label.setText(os.path.basename(file_path))
                self.show_image_preview(file_path)
                
                self.append_system_message(f"[已选择图片: {os.path.basename(file_path)}]")
            except Exception as e:
                self.append_system_message(f"[图片加载失败: {str(e)}]")
                self.clear_image()
    
    def clear_image(self):
        """清除选择的图片"""
        self.image_path = None
        self.base64_image = None
        self.image_path_label.setText("未选择图片")
        self.image_preview.clear()
        self.image_preview.setText("图片预览")
    
    def show_image_preview(self, image_path):
        """显示图片预览"""
        if not image_path or not os.path.exists(image_path):
            return
        
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            preview_height = self.image_preview.height()
            scaled_pixmap = pixmap.scaledToHeight(preview_height - 10, Qt.SmoothTransformation)
            self.image_preview.setPixmap(scaled_pixmap)
    
    def browse_video(self):
        """浏览并选择视频"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择视频", "", "视频文件 (*.mp4 *.avi *.mov)"
        )
        
        if file_path:
            try:
                self.video_path = file_path
                
                self.base64_video = qwen_chat.encode_video(file_path)
                
                self.video_path_label.setText(os.path.basename(file_path))
                
                self.append_system_message(f"[已选择视频: {os.path.basename(file_path)}]")
            except Exception as e:
                self.append_system_message(f"[视频加载失败: {str(e)}]")
                self.clear_video()
    
    def clear_video(self):
        """清除选择的视频"""
        self.video_path = None
        self.base64_video = None
        self.video_path_label.setText("未选择视频")
        self.video_preview.clear()
        self.video_preview.setText("视频预览")
    
    def start_recording(self):
        """开始录音"""
        if hasattr(self, 'recording_thread') and self.recording_thread and self.recording_thread.isRunning():
            return
        
        duration = self.duration_spin.value()
        self.recording_progress.setRange(0, duration)
        self.recording_progress.setValue(0)
        self.recording_progress.setVisible(True)
        self.record_button.setEnabled(False)
        self.stop_record_button.setEnabled(True)
        self.update_recording_status("正在准备录音...")
        
        self.recording_thread = RecordingThread(duration)
        self.recording_thread.finished.connect(self.on_recording_finished)
        self.recording_thread.status.connect(self.update_recording_status)
        self.recording_thread.progress.connect(self.update_recording_progress)
        self.recording_thread.start()
    
    def stop_recording(self):
        """停止录音"""
        if hasattr(self, 'recording_thread') and self.recording_thread and self.recording_thread.isRunning():
            self.recording_thread.interrupt()
            self.stop_record_button.setEnabled(False)
    
    def on_recording_finished(self, audio_path, base64_audio):
        """录音完成回调"""
        self.audio_path = audio_path
        self.base64_audio = base64_audio
        self.recording_progress.setValue(100)
        self.record_button.setEnabled(True)
        self.stop_record_button.setEnabled(False)
    
    def update_recording_progress(self, value):
        """更新录音进度条"""
        self.recording_progress.setValue(value)
    
    def update_recording_status(self, status):
        """更新录音状态标签"""
        self.recording_status_label.setText(status)
    
    def send_message(self):
        """发送消息"""
        if hasattr(self, 'chat_thread') and self.chat_thread and self.chat_thread.isRunning():
            return
        
        use_voice = self.input_mode_combo.currentIndex() == 1
        use_image = self.input_mode_combo.currentIndex() == 2
        use_video = self.input_mode_combo.currentIndex() == 3
        
        if use_voice:
            if not self.audio_path or not self.base64_audio:
                QMessageBox.warning(self, "警告", "请先录制语音")
                return
            
            user_input = "我刚才说的是什么？请回答我的问题或请求。"
            self.append_to_chat(f"你: [语音输入]\n")
        elif use_image:
            if not self.image_path or not self.base64_image:
                QMessageBox.warning(self, "警告", "请先选择图片")
                return
            
            user_input = self.text_input.toPlainText().strip()
            if not user_input:
                QMessageBox.warning(self, "警告", "请输入关于图片的问题或描述")
                return
            
            self.append_to_chat(f"你: [已上传图片] {user_input}\n")
            
            self.text_input.clear()
        elif use_video:
            if not self.video_path or not self.base64_video:
                QMessageBox.warning(self, "警告", "请先选择视频")
                return
            
            user_input = self.text_input.toPlainText().strip()
            if not user_input:
                QMessageBox.warning(self, "警告", "请输入关于视频的问题或描述")
                return
            
            self.append_to_chat(f"你: [已上传视频] {user_input}\n")
            
            self.text_input.clear()
        else:
            user_input = self.text_input.toPlainText().strip()
            if not user_input:
                return
            
            if user_input.lower() in ['exit', '退出']:
                self.close()
                return
            
            self.append_to_chat(f"你: {user_input}\n")
            
            self.text_input.clear()
        
        self.set_input_enabled(False)
        
        output_mode_idx = self.output_mode_combo.currentIndex()
        use_audio = output_mode_idx > 0
        use_streaming_audio = output_mode_idx == 2
        
        self.chat_thread = ChatThread(
            user_input, 
            self.messages, 
            use_voice, 
            use_audio, 
            use_streaming_audio, 
            self.base64_audio,
            self.base64_image if use_image else None,
            self.image_type if use_image else None,
            self.base64_video if use_video else None,
            self.selected_model  # 传递选定的模型
        )
        self.chat_thread.start()
    
    def model_changed(self, index):
        """处理模型选择变化"""
        if index >= 0 and index < len(qwen_chat.AVAILABLE_MODELS):
            self.selected_model = qwen_chat.AVAILABLE_MODELS[index]
            qwen_chat.save_selected_model(self.selected_model)
            self.append_system_message(f"[已选择模型: {self.selected_model}]")
    
    def on_chat_completed(self):
        """聊天完成后的处理"""
        self.set_input_enabled(True)
    
    def set_input_enabled(self, enabled):
        """设置输入控件的启用状态"""
        self.send_button.setEnabled(enabled)
        self.text_input.setEnabled(enabled)
        self.input_mode_combo.setEnabled(enabled)
        self.output_mode_combo.setEnabled(enabled)
        self.model_combo.setEnabled(enabled)
        
        if self.input_mode_combo.currentIndex() == 1:
            self.record_button.setEnabled(enabled)
            self.duration_spin.setEnabled(enabled)
        elif self.input_mode_combo.currentIndex() == 2:
            self.browse_image_button.setEnabled(enabled)
            self.clear_image_button.setEnabled(enabled)
        elif self.input_mode_combo.currentIndex() == 3:
            self.browse_video_button.setEnabled(enabled)
            self.clear_video_button.setEnabled(enabled)
    
    def append_to_chat(self, text):
        """添加文本到聊天历史"""
        cursor = self.chat_history.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.chat_history.setTextCursor(cursor)
        self.chat_history.ensureCursorVisible()
    
    def append_system_message(self, text):
        """添加系统消息到聊天历史"""
        cursor = self.chat_history.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        current_format = cursor.charFormat()
        
        system_format = cursor.charFormat()
        system_format.setForeground(QColor(100, 100, 100))
        cursor.setCharFormat(system_format)
        
        cursor.insertText("\n" + text + "\n")
        
        cursor.setCharFormat(current_format)
        
        self.chat_history.setTextCursor(cursor)
        self.chat_history.ensureCursorVisible()
    
    def closeEvent(self, event):
        """窗口关闭事件处理"""
        reply = QMessageBox.question(self, '确认退出', 
                                    '确定要退出程序吗？',
                                    QMessageBox.Yes | QMessageBox.No, 
                                    QMessageBox.No)

        if reply == QMessageBox.Yes:
            if hasattr(qwen_chat, 'cleanup_audio_streaming'):
                qwen_chat.cleanup_audio_streaming()
            event.accept()
        else:
            event.ignore()

# 主函数
def main():
    app = QApplication(sys.argv)
    
    try:
        from openai import OpenAI
        
        app.setStyle("Fusion")
        
        window = QwenChatUI()
        window.show()
        
        sys.exit(app.exec_())
    except Exception as e:
        QMessageBox.critical(None, "错误", f"程序启动失败: {str(e)}")
        import traceback
        print(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()