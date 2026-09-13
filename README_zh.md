# 🎵 AI Audio Studio (AI 音频工作室)
<p align="center">
<img src="https://github.com/SUmmerLunchhh/AAA-/blob/main/imgs/%E5%B1%8F%E5%B9%95%E6%88%AA%E5%9B%BE%202026-09-13%20124308.png" height="300">
</p>
基于 **PyQt6**、**Demucs** 和 **AudD API** 构建的现代桌面端 AI 音频处理工作室，内置 PowerShell 终端。

</div>

---

## ✨ 核心功能

- **🎤 人声伴奏分离**：依托 Meta 的 Demucs AI 模型，实现高质量的二轨（人声/伴奏）快速分离。
- **🎛️ 多轨拆分（四轨分离）**：支持将歌曲一键批量拆分为人声（Vocals）、鼓点（Drums）、贝斯（Bass）和其他（Other）音轨。
- **🔍 系统声音识别**：集成 `sounddevice` 与 AudD API，可实时录制并识别电脑正在播放的音乐。
- **💻 内置终端**：界面内嵌持久化、半透明且安全的 PowerShell 终端，支持智能路径精简与自动清理。
- **🎨 个性化美观设计**：支持高斯模糊/毛玻璃特效、动态皮肤背景以及自定义 UI 皮肤切换。
- - <p align="center">
  <img src="https://raw.githubusercontent.com/SUmmerLunchhh/AAA-/main/imgs/%E5%B1%8F%E5%B9%95%E6%88%AA%E5%9B%BE%202026-09-13%20124344.png" width="48%" />
  <img src="https://raw.githubusercontent.com/SUmmerLunchhh/AAA-/main/imgs/%E5%B1%8F%E5%B9%95%E6%88%AA%E5%9B%BE%202026-09-13%20124404.png" width="48%" />
</p>

---

## 🛠️ 技术栈

- **UI 框架**：[PyQt6](https://pypi.org/project/PyQt6/)
- **AI 音频分离**：[Demucs](https://github.com/facebookresearch/demucs) (PyTorch)
- **音频录制与处理**：`sounddevice`, `numpy`, `wave`
- **音乐识别接口**：AudD Music Recognition API

---

## 🚀 快速上手指南

### 1. 克隆仓库
```bash
git clone [https://github.com/SummerLunchhh/AudioSplitter.git](https://github.com/SummerLunchhh/AudioSplitter.git)
cd AudioSplitter
```
### 2.安装并配置[FFmpeg](https://ffmpeg.org/)
### 3.在下载好的文件夹下打开终端，并运行
```powershell 
$ffmpegPath = (Get-ChildItem -Path "C:\Users\$env:USERNAME\AppData" -Filter "ffmpeg.exe" -Recurse -ErrorAction SilentlyContinue \vert{} Select-Object -ExpandProperty FullName -First 1); pyinstaller --noconfirm --onedir --windowed -n "AudioSplitter" --icon="my_app.ico" --add-binary "$ffmpegPath;." --collect-all torch --collect-all demucs --collect-all sounddevice --noupx app.py
```
