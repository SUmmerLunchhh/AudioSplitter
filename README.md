# 🎵 AI Audio Studio
<img src="https://github.com/SUmmerLunchhh/AAA-/blob/main/imgs/%E5%B1%8F%E5%B9%95%E6%88%AA%E5%9B%BE%202026-09-13%20124308.png" height="300">
<div align="center">

A modern desktop-class AI audio processing studio built with **PyQt6**, **Demucs**, and the **AudD API**, featuring a built-in PowerShell terminal.

</div>

---

## ✨ Core Features

- **🎤 Vocal & Accompaniment Separation**: Powered by Meta's Demucs AI model for high-quality two-track rapid separation.
- **🎛️ Multi-track Stem Splitting**: Supports one-click batch splitting of songs into Vocals, Drums, Bass, and Other tracks.
- **🔍 System Audio Recognition**: Integrated with `sounddevice` and the AudD API to capture and identify computer audio in real time.
- **💻 Built-in Terminal**: An embedded, persistent, semi-transparent PowerShell terminal with smart path shortening.
- **🎨 Aesthetic Design**: Supports Gaussian blur/frosted glass effects, dynamic backgrounds, and custom UI skins.
- **🚀 Borderless Interactive Experience**: Custom window controls with smooth window dragging support.

---

## 🛠️ Tech Stack

- **UI Framework**: [PyQt6](https://pypi.org/project/PyQt6/)
- **AI Audio Separation**: [Demucs](https://github.com/facebookresearch/demucs) (PyTorch)
- **Audio Processing**: `sounddevice`, `numpy`, `wave`
- **Music Recognition**: AudD Music Recognition API

---

## 🚀 Quick Start Guide

### 1. Clone the Repository
```bash
git clone [https://github.com/SummerLunchhh/AudioSplitter.git](https://github.com/SummerLunchhh/AudioSplitter.git)
cd AudioSplitter
```
### 2. Install and Configure [FFmpeg](https://ffmpeg.org/)
### 3.Install Dependencies and Run Packaging in the Downloaded Folder
```powershell 
$ffmpegPath = (Get-ChildItem -Path "C:\Users\$env:USERNAME\AppData" -Filter "ffmpeg.exe" -Recurse -ErrorAction SilentlyContinue \vert{} Select-Object -ExpandProperty FullName -First 1); pyinstaller --noconfirm --onedir --windowed -n "AudioSplitter" --icon="my_app.ico" --add-binary "$ffmpegPath;." --collect-all torch --collect-all demucs --collect-all sounddevice --noupx app.py
```
