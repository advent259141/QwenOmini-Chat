import os
import time
import subprocess
import signal
from openai import OpenAI
from pathlib import Path
import base64
import numpy as np
import soundfile as sf
import json

try:
    import pyaudio
    import wave
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    print("[警告] PyAudio未安装，录音和实时流式音频播放将不可用。")
    print("可通过以下命令安装: pip install pyaudio")
    print("Windows系统可能需要先安装Visual C++ Build Tools")

# 定义可用模型列表
AVAILABLE_MODELS = [
    "qwen-omni-turbo",
    "qwen-omni-turbo-latest",
    "qwen-omni-turbo-2025-03-26",
    "qwen2.5-omni-7b"
]

# 默认模型
DEFAULT_MODEL = "qwen-omni-turbo-2025-03-26"

# 配置文件路径
CONFIG_FILE = Path("config.json")

def load_config():
    """从配置文件加载配置"""
    config = {"api_key": None, "model": DEFAULT_MODEL}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as file:
                loaded_config = json.load(file)
                # 合并已加载的配置与默认配置
                config.update(loaded_config)
        except Exception as e:
            print(f"读取配置文件时出错: {e}")
    return config

def save_config(config):
    """保存配置到配置文件"""
    try:
        with open(CONFIG_FILE, "w") as file:
            json.dump(config, file)
        return True
    except Exception as e:
        print(f"保存配置文件时出错: {e}")
        return False

def load_api_key():
    """从配置文件加载API密钥"""
    config = load_config()
    return config.get("api_key")

def save_api_key(api_key):
    """保存API密钥到配置文件"""
    config = load_config()
    config["api_key"] = api_key
    return save_config(config)

def get_selected_model():
    """获取选定的模型"""
    config = load_config()
    return config.get("model", DEFAULT_MODEL)

def save_selected_model(model):
    """保存选定的模型"""
    config = load_config()
    config["model"] = model
    return save_config(config)

def get_api_key():
    """获取API密钥，如果没有已保存的密钥则请求用户输入"""
    api_key = load_api_key()
    if not api_key:
        print("\n首次使用需要输入API密钥")
        api_key = input("请输入您的DashScope API密钥: ").strip()
        if save_api_key(api_key):
            print("API密钥已保存，下次启动将自动读取")
        else:
            print("警告: API密钥未能保存，下次启动需要重新输入")
    return api_key

# 获取API密钥
API_KEY = get_api_key()
os.environ["DASHSCOPE_API_KEY"] = API_KEY

# 初始化客户端
client = OpenAI(
    api_key=API_KEY,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

# 创建保存音频的目录
output_dir = Path("audio_output")
output_dir.mkdir(exist_ok=True)

# 创建保存图片的目录
image_dir = Path("image_input")
image_dir.mkdir(exist_ok=True)

def save_audio_base64(audio_string, filename, samplerate=24000):
    """从Base64字符串保存音频文件"""
    audio_path = output_dir / filename
    try:
        # 解码Base64数据
        wav_bytes = base64.b64decode(audio_string)
        # 转换为NumPy数组
        audio_np = np.frombuffer(wav_bytes, dtype=np.int16)
        # 保存为WAV文件
        sf.write(str(audio_path), audio_np, samplerate=samplerate)
        return audio_path
    except Exception as e:
        print(f"保存音频文件时出错: {e}")
        return None

def encode_image(image_path):
    """将图像文件编码为Base64"""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except Exception as e:
        print(f"[图像编码出错: {str(e)}]")
        return None

def encode_video(video_path):
    """将视频文件编码为Base64"""
    try:
        with open(video_path, "rb") as video_file:
            return base64.b64encode(video_file.read()).decode("utf-8")
    except Exception as e:
        print(f"[视频编码出错: {str(e)}]")
        return None

def play_audio_system(audio_path):
    """使用系统命令播放音频文件"""
    try:
        # PowerShell命令来播放音频
        ps_cmd = f'(New-Object Media.SoundPlayer "{audio_path}").PlaySync()'
        subprocess.run(['powershell', '-Command', ps_cmd], check=True)
    except Exception as e:
        print(f"播放音频时出错: {e}")

def play_audio_streaming(audio_string):
    """实时播放Base64编码的音频数据"""
    if not PYAUDIO_AVAILABLE:
        print("[错误] 无法实时播放音频: PyAudio未安装")
        return
    
    try:
        # 解码Base64数据
        wav_bytes = base64.b64decode(audio_string)
        # 转换为NumPy数组
        audio_np = np.frombuffer(wav_bytes, dtype=np.int16)
        
        # 初始化PyAudio (如果尚未初始化)
        if not hasattr(play_audio_streaming, 'audio_stream'):
            p = pyaudio.PyAudio()
            play_audio_streaming.p = p
            play_audio_streaming.audio_stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=24000,
                output=True
            )
        
        # 播放音频数据
        play_audio_streaming.audio_stream.write(audio_np.tobytes())
    except Exception as e:
        print(f"实时播放音频时出错: {e}")

def cleanup_audio_streaming():
    """清理流式音频资源"""
    if hasattr(play_audio_streaming, 'audio_stream'):
        play_audio_streaming.audio_stream.stop_stream()
        play_audio_streaming.audio_stream.close()
        play_audio_streaming.p.terminate()
        delattr(play_audio_streaming, 'audio_stream')
        delattr(play_audio_streaming, 'p')

def record_audio(filename, duration=60, rate=16000, chunk=1024, channels=1, format=pyaudio.paInt16):
    """录制音频并保存到文件，可通过Ctrl+C提前结束录音"""
    if not PYAUDIO_AVAILABLE:
        print("[错误] 无法录音: PyAudio未安装")
        return None
    
    record_path = Path("audio_input") / filename
    record_path.parent.mkdir(exist_ok=True)
    
    # 用于存储录音数据的列表
    frames = []
    
    # 用于标记录音是否被中断
    recording_interrupted = False
    
    def handle_interrupt(sig, frame):
        nonlocal recording_interrupted
        recording_interrupted = True
        print("\n[录音被用户中断]")
    
    # 注册信号处理函数
    original_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, handle_interrupt)
    
    try:
        p = pyaudio.PyAudio()
        stream = p.open(format=format, 
                      channels=channels,
                      rate=rate,
                      input=True,
                      frames_per_buffer=chunk)

        print(f"[开始录音...最长{duration}秒，按Ctrl+C可提前结束]")
        
        start_time = time.time()
        max_chunks = int(rate / chunk * duration)
        
        # 录音循环
        for i in range(max_chunks):
            if recording_interrupted:
                break
                
            # 每秒更新一次状态
            if i % int(rate / chunk) == 0:
                elapsed = time.time() - start_time
                remaining = duration - elapsed
                print(f"\r已录制: {elapsed:.1f}秒 | 剩余: {remaining:.1f}秒...", end="", flush=True)
            
            try:
                data = stream.read(chunk)
                frames.append(data)
            except IOError as e:
                # 忽略溢出错误，继续录音
                print(f"\r[警告: {e}]", end="", flush=True)
        
        if not recording_interrupted:
            print("\r[录音完成，已达到最大时长]                    ")
        
        # 停止和关闭流
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        # 检查是否录到了内容
        if not frames:
            print("[录音为空，未保存文件]")
            return None
        
        # 保存录音
        wf = wave.open(str(record_path), 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(p.get_sample_size(format))
        wf.setframerate(rate)
        wf.writeframes(b''.join(frames))
        wf.close()
        
        actual_duration = len(frames) * chunk / rate
        print(f"[已保存录音，实际长度: {actual_duration:.1f}秒]")
        
        return record_path
    
    except Exception as e:
        print(f"[录音出错: {str(e)}]")
        return None
    finally:
        # 恢复原来的信号处理函数
        signal.signal(signal.SIGINT, original_handler)

def encode_audio(audio_path):
    """将音频文件编码为Base64"""
    try:
        with open(audio_path, "rb") as audio_file:
            return base64.b64encode(audio_file.read()).decode("utf-8")
    except Exception as e:
        print(f"[音频编码出错: {str(e)}]")
        return None

def chat_with_qwen():
    """与Qwen模型进行对话"""
    print("欢迎使用Qwen Omni聊天程序!")
    
    # 选择模型
    print("\n请选择要使用的模型:")
    for i, model in enumerate(AVAILABLE_MODELS, 1):
        print(f"{i}. {model}")
    
    selected_model = get_selected_model()
    current_index = AVAILABLE_MODELS.index(selected_model) + 1 if selected_model in AVAILABLE_MODELS else 0
    
    model_choice = ""
    valid_choices = [str(i) for i in range(1, len(AVAILABLE_MODELS) + 1)]
    while model_choice not in valid_choices:
        model_choice = input(f"请输入选项 ({'/'.join(valid_choices)}) [当前: {current_index}]: ").strip()
        if not model_choice and current_index > 0:  # 如果用户直接回车且有当前选择
            model_choice = str(current_index)
        if model_choice not in valid_choices:
            print(f"无效的选择，请输入{'/'.join(valid_choices)}。")
    
    selected_model = AVAILABLE_MODELS[int(model_choice) - 1]
    if selected_model != get_selected_model():
        save_selected_model(selected_model)
        print(f"已选择模型: {selected_model}，此选择将被保存")
    else:
        print(f"使用模型: {selected_model}")
    
    # 选择输出模式
    print("\n请选择输出模式:")
    print("1. 仅文字输出")
    print("2. 文字+语音输出(完整收到后播放)")
    if PYAUDIO_AVAILABLE:
        print("3. 文字+语音输出(实时流式播放)")
    
    output_mode = ""
    valid_modes = ["1", "2"] + (["3"] if PYAUDIO_AVAILABLE else [])
    while output_mode not in valid_modes:
        output_mode = input(f"请输入选项 ({'/'.join(valid_modes)}): ").strip()
        if output_mode not in valid_modes:
            print(f"无效的选择，请输入{'/'.join(valid_modes)}。")
    
    # 根据选择设置模态和播放方式
    use_audio = (output_mode in ["2", "3"])
    use_streaming_audio = (output_mode == "3")
    modalities = ["text", "audio"] if use_audio else ["text"]
    
    # 选择输入模式
    print("\n请选择输入模式:")
    print("1. 键盘文字输入")
    if PYAUDIO_AVAILABLE:
        print("2. 语音录音输入")
    print("3. 图片+文字输入")
    print("4. 视频+文字输入")  # 添加视频输入选项
    
    input_mode = ""
    valid_input_modes = ["1", "3", "4"] + (["2"] if PYAUDIO_AVAILABLE else [])
    while input_mode not in valid_input_modes:
        input_mode = input(f"请输入选项 ({'/'.join(valid_input_modes)}): ").strip()
        if input_mode not in valid_input_modes:
            print(f"无效的选择，请输入{'/'.join(valid_input_modes)}。")
    
    use_voice_input = (input_mode == "2")
    use_image_input = (input_mode == "3")
    use_video_input = (input_mode == "4")  # 视频输入标志
    
    print(f"\n已选择{'语音' if use_voice_input else '图片+文字' if use_image_input else '视频+文字' if use_video_input else '文字'}输入，{'文字+' + ('实时' if use_streaming_audio else '') + '语音' if use_audio else '仅文字'}输出模式。")
    print("输入'exit'或'退出'结束对话，输入'record'或'录音'使用语音输入（如已选择文字输入模式）。")
    print("输入'image'或'图片'上传图片（如已选择文字输入模式）。")
    print("输入'video'或'视频'上传视频（如已选择文字输入模式）。")  # 添加视频上传提示
    
    # 存储对话历史
    messages = []
    
    try:
        while True:
            # 获取用户输入
            image_path = None
            base64_image = None
            base64_audio = None  # 确保变量存在
            video_path = None  # 视频文件路径
            base64_video = None  # 视频Base64编码
            
            if use_voice_input:
                print("\n[准备录音输入]")
                # 询问录音时长（默认改为60秒）
                try:
                    duration_input = input("请输入最大录音时长(秒)，直接回车默认为60秒，可随时按Ctrl+C结束录音: ").strip()
                    duration = int(duration_input) if duration_input else 60
                except ValueError:
                    print("[无效输入，使用默认值60秒]")
                    duration = 60
                
                # 录制音频
                audio_path = record_audio(f"input_{int(time.time())}.wav", duration=duration)
                
                if not audio_path:
                    print("[录音失败，请重试或切换到文字输入]")
                    continue
                
                # 编码音频
                base64_audio = encode_audio(audio_path)
                if not base64_audio:
                    print("[音频编码失败，请重试]")
                    continue
                
                user_input = "我刚才说的是什么？请回答我的问题或请求。"
                print(f"\n你: [语音输入已录制，长度:{duration}秒]")
                
            elif use_image_input:
                # 处理图片输入
                print("\n[请选择需要上传的图片]")
                try:
                    from tkinter import Tk
                    from tkinter.filedialog import askopenfilename
                    Tk().withdraw()  # 不显示主窗口
                    image_path = askopenfilename(title="选择图片", 
                                              filetypes=[("Image files", "*.jpg *.jpeg *.png *.gif *.bmp")])
                    
                    if not image_path:
                        print("[未选择图片，请重试]")
                        continue
                    
                    # 编码图片
                    base64_image = encode_image(image_path)
                    if not base64_image:
                        print("[图片编码失败，请重试]")
                        continue
                    
                    print(f"[已选择图片: {image_path}]")
                    user_input = input("请输入关于图片的问题或描述: ")
                    
                    # 检查是否退出
                    if user_input.lower() in ['exit', '退出']:
                        print("谢谢使用，再见!")
                        break
                        
                    print(f"\n你: [已上传图片] {user_input}")
                    
                except ImportError:
                    print("[错误] 无法打开文件选择器，请确保已安装tkinter")
                    user_input = input("\n你: ")
                    use_image_input = False
                except Exception as e:
                    print(f"[选择图片时出错: {str(e)}]")
                    user_input = input("\n你: ")
                    use_image_input = False
                
            elif use_video_input:
                # 处理视频输入
                print("\n[请选择需要上传的视频]")
                try:
                    from tkinter import Tk
                    from tkinter.filedialog import askopenfilename
                    Tk().withdraw()  # 不显示主窗口
                    video_path = askopenfilename(title="选择视频",
                                                  filetypes=[("Video files", "*.mp4 *.avi *.mov")])
                    
                    if not video_path:
                        print("[未选择视频，请重试]")
                        continue
                    
                    # 编码视频
                    base64_video = encode_video(video_path)
                    if not base64_video:
                        print("[视频编码失败，请重试]")
                        continue
                    
                    print(f"[已选择视频: {video_path}]")
                    user_input = input("请输入关于视频的问题或描述: ")
                    
                    # 检查是否退出
                    if user_input.lower() in ['exit', '退出']:
                        print("谢谢使用，再见!")
                        break
                    
                    print(f"\n你: [已上传视频] {user_input}")
                    
                except ImportError:
                    print("[错误] 无法打开文件选择器，请确保已安装tkinter")
                    user_input = input("\n你: ")
                    use_video_input = False
                except Exception as e:
                    print(f"[选择视频时出错: {str(e)}]")
                    user_input = input("\n你: ")
                    use_video_input = False
            
            else:
                user_input = input("\n你: ")
                
                # 检查是否需要录音
                if user_input.lower() in ['record', '录音']:
                    if not PYAUDIO_AVAILABLE:
                        print("[错误] 无法录音: PyAudio未安装")
                        continue
                    
                    # 询问录音时长（默认改为60秒）
                    try:
                        duration_input = input("请输入最大录音时长(秒)，直接回车默认为60秒，可随时按Ctrl+C结束录音: ").strip()
                        duration = int(duration_input) if duration_input else 60
                    except ValueError:
                        print("[无效输入，使用默认值60秒]")
                        duration = 60
                    
                    # 录制音频
                    audio_path = record_audio(f"input_{int(time.time())}.wav", duration=duration)
                    
                    if not audio_path:
                        print("[录音失败，请重试]")
                        continue
                    
                    # 编码音频
                    base64_audio = encode_audio(audio_path)
                    if not base64_audio:
                        print("[音频编码失败，请重试]")
                        continue
                    
                    user_input = "我刚才说的是什么？请回答我的问题或请求。"
                    print(f"你: [语音输入已替换为: {user_input}]")
                    
                # 检查是否需要上传图片
                elif user_input.lower() in ['image', '图片']:
                    try:
                        from tkinter import Tk
                        from tkinter.filedialog import askopenfilename
                        Tk().withdraw()  # 不显示主窗口
                        image_path = askopenfilename(title="选择图片", 
                                                  filetypes=[("Image files", "*.jpg *.jpeg *.png *.gif *.bmp")])
                        
                        if not image_path:
                            print("[未选择图片，请输入文本]")
                            continue
                        
                        # 编码图片
                        base64_image = encode_image(image_path)
                        if not base64_image:
                            print("[图片编码失败，请重试]")
                            continue
                        
                        print(f"[已选择图片: {image_path}]")
                        user_input = input("请输入关于图片的问题或描述: ")
                        
                        # 检查是否退出
                        if user_input.lower() in ['exit', '退出']:
                            print("谢谢使用，再见!")
                            break
                            
                        print(f"\n你: [已上传图片] {user_input}")
                        
                    except ImportError:
                        print("[错误] 无法打开文件选择器，请确保已安装tkinter")
                        continue
                    except Exception as e:
                        print(f"[选择图片时出错: {str(e)}]")
                        continue
                
                # 检查是否需要上传视频
                elif user_input.lower() in ['video', '视频']:
                    try:
                        from tkinter import Tk
                        from tkinter.filedialog import askopenfilename
                        Tk().withdraw()  # 不显示主窗口
                        video_path = askopenfilename(title="选择视频",
                                                  filetypes=[("Video files", "*.mp4 *.avi *.mov")])
                        
                        if not video_path:
                            print("[未选择视频，请输入文本]")
                            continue
                        
                        # 编码视频
                        base64_video = encode_video(video_path)
                        if not base64_video:
                            print("[视频编码失败，请重试]")
                            continue
                        
                        print(f"[已选择视频: {video_path}]")
                        user_input = input("请输入关于视频的问题或描述: ")
                        
                        # 检查是否退出
                        if user_input.lower() in ['exit', '退出']:
                            print("谢谢使用，再见!")
                            break
                        
                        print(f"\n你: [已上传视频] {user_input}")
                        
                    except ImportError:
                        print("[错误] 无法打开文件选择器，请确保已安装tkinter")
                        continue
                    except Exception as e:
                        print(f"[选择视频时出错: {str(e)}]")
                        continue
                
                # 检查是否退出
                elif user_input.lower() in ['exit', '退出']:
                    print("谢谢使用，再见!")
                    break
            
            print("\n正在思考...", end="", flush=True)
            
            try:
                # 准备消息内容
                if use_voice_input or user_input.lower() in ['record', '录音']:
                    # 构建多模态消息
                    message_content = [
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": f"data:;base64,{base64_audio}",
                                "format": "wav",  # 根据实际录音格式调整
                            },
                        },
                        {"type": "text", "text": user_input}
                    ]
                    messages.append({"role": "user", "content": message_content})
                elif use_image_input or base64_image:
                    # 构建包含图片的消息
                    image_extension = Path(image_path).suffix.lower().replace(".", "") if image_path else "png"
                    message_content = [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{image_extension};base64,{base64_image}"
                            }
                        },
                        {"type": "text", "text": user_input}
                    ]
                    messages.append({"role": "user", "content": message_content})
                    # 重置标志，除非用户明确选择了图片输入模式
                    if not use_image_input:
                        use_image_input = False
                elif use_video_input or base64_video:
                    # 构建包含视频的消息
                    message_content = [
                        {
                            "type": "video_url",
                            "video_url": {
                                "url": f"data:video/mp4;base64,{base64_video}"  # 假设是MP4格式
                            }
                        },
                        {"type": "text", "text": user_input}
                    ]
                    messages.append({"role": "user", "content": message_content})
                    # 重置标志，除非用户明确选择了视频输入模式
                    if not use_video_input:
                        use_video_input = False
                else:
                    # 普通文本消息
                    messages.append({"role": "user", "content": user_input})
                
                # 调用API
                completion_args = {
                    "model": selected_model,  # 使用选定的模型
                    "messages": messages,
                    "modalities": modalities,
                    "stream": True,
                    "stream_options": {"include_usage": True},
                }
                
                # 如果启用了音频，添加音频配置
                if use_audio:
                    completion_args["audio"] = {"voice": "Cherry", "format": "wav"}
                
                completion = client.chat.completions.create(**completion_args)
                
                print("\r助手: ", end="", flush=True)
                
                # 收集完整的回复文本和音频内容
                full_response = ""
                audio_string = ""
                
                for chunk in completion:
                    if chunk.choices:
                        delta = chunk.choices[0].delta
                        if delta.content:
                            full_response += delta.content
                            print(delta.content, end="", flush=True)
                        
                        # 处理音频数据
                        if use_audio and hasattr(delta, 'audio') and delta.audio:
                            try:
                                # 获取音频数据
                                if isinstance(delta.audio, dict) and "data" in delta.audio:
                                    chunk_audio_data = delta.audio["data"]
                                    # 如果是实时流式播放，则立即播放
                                    if use_streaming_audio:
                                        play_audio_streaming(chunk_audio_data)
                                    # 否则，将数据累加起来
                                    else:
                                        audio_string += chunk_audio_data
                            except Exception as e:
                                # 如果有文本记录，则输出
                                if isinstance(delta.audio, dict) and "transcript" in delta.audio:
                                    print(f"\n[音频文本: {delta.audio['transcript']}]")
                                else:
                                    print(f"\n[处理音频数据时出错: {e}]")
                    
                    elif hasattr(chunk, 'usage'):
                        print(f"\n\n[使用统计: 输入tokens: {chunk.usage.prompt_tokens}, 输出tokens: {chunk.usage.completion_tokens}]")
                
                # 将助手回复简化为纯文本以添加到历史记录
                if len(messages) > 0 and isinstance(messages[-1]["content"], list):
                    # 如果最后一条消息是多模态内容，需要调整历史记录格式
                    for item in messages[-1]["content"]:
                        if item.get("type") == "text":
                            messages[-1] = {"role": "user", "content": item.get("text", "")}
                            break
                
                # 添加助手回复到对话历史
                messages.append({"role": "assistant", "content": full_response})
                
                # 如果有音频内容且非实时播放模式，等全部接收完再播放
                if use_audio and not use_streaming_audio and audio_string:
                    audio_filename = f"response_{int(time.time())}.wav"
                    try:
                        print(f"\n[正在处理音频...]")
                        audio_path = save_audio_base64(audio_string, audio_filename)
                        if audio_path:
                            print(f"[音频已保存到 {audio_path}]")
                            print(f"[播放语音回复...]")
                            play_audio_system(audio_path)
                        else:
                            print("[无法处理音频内容]")
                    except Exception as e:
                        print(f"[处理音频时出错: {str(e)}]")
                
            except Exception as e:
                print(f"\n发生错误: {str(e)}")
                import traceback
                print(traceback.format_exc())
                
            # 如果是语音输入模式，每次对话后询问是否继续使用语音输入
            if use_voice_input:
                choice = input("\n继续使用语音输入? (y/n): ").lower().strip()
                use_voice_input = choice in ['y', 'yes', '是', 'true', 't', '']
            
            # 如果是图片输入模式，每次对话后询问是否继续上传图片
            if use_image_input:
                choice = input("\n继续上传新的图片? (y/n): ").lower().strip()
                use_image_input = choice in ['y', 'yes', '是', 'true', 't', '']
            
            # 如果是视频输入模式，每次对话后询问是否继续上传视频
            if use_video_input:
                choice = input("\n继续上传新的视频? (y/n): ").lower().strip()
                use_video_input = choice in ['y', 'yes', '是', 'true', 't', '']
                
    finally:
        # 如果使用了流式音频，确保资源被清理
        if use_audio and use_streaming_audio:
            cleanup_audio_streaming()

if __name__ == "__main__":
    chat_with_qwen()
