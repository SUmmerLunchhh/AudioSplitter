# 🎵 AI Audio Studio

<div align="center">

A modern, customizable desktop AI audio processing studio built with **PyQt6**, **Demucs**, and **AudD API**, featuring a built-in PowerShell terminal.

</div>

---

## ✨ Features

- **🎤 Vocal & Accompaniment Separation**: Powered by Meta's Demucs AI model for fast, high-quality two-stem separation.
- **🎛️ Multi-Stem Splitting (4-Stems)**: Split songs into Vocals, Drums, Bass, and Other tracks in batches.
- **🔍 System Audio Recognition**: Integrated with sounddevice and AudD API to capture and identify playing music from your PC in real-time.
- **💻 Integrated Terminal**: A persistent, transparent, and secure PowerShell terminal built right into the interface with auto-clearing path optimization.
- **🎨 Custom Aesthetics**: Supports customizable blur/glass-morphism themes, dynamic skin backgrounds, and custom UI style switching.
- **🚀 Frameless Design**: Custom window controls with smooth drag-and-drop movement.

---

## 🛠️ Tech Stack

- **UI Framework**: [PyQt6](https://pypi.org/project/PyQt6/)
- **AI Audio Separation**: [Demucs](https://github.com/facebookresearch/demucs) (PyTorch)
- **Audio Capture**: `sounddevice`, `numpy`, `wave`
- **Recognition API**: AudD Music Recognition API

---

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone [https://github.com/SummerLunchhh/AudioSplitter.git](https://github.com/SummerLunchhh/AudioSplitter.git)
cd AudioSplitter