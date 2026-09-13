import os
import sys
import random
import threading
import subprocess
import wave
import tempfile
import sounddevice as sd
import numpy as np
import requests
from PIL import Image, ImageFilter
from PyQt6.QtCore import Qt, QPoint, QRectF, pyqtSignal, QObject, QProcess
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPainterPath, QColor, QTextCursor
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                               QHBoxLayout, QVBoxLayout, QPushButton, 
                               QLabel, QLineEdit, QFileDialog, QMessageBox, 
                               QStackedWidget, QProgressBar, QComboBox, QTextEdit)

class DummyStream:
    def write(self, *args, **kwargs): pass
    def flush(self, *args, **kwargs): pass

if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

os.environ["PATH"] += os.pathsep + base_path

class WorkerSignals(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    status = pyqtSignal(str)

class RecognizeSignals(QObject):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    status = pyqtSignal(str)

class ProtectedTextEdit(QTextEdit):
    return_pressed = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.input_start_position = 0

    def keyPressEvent(self, event):
        cursor = self.textCursor()
        current_pos = cursor.position()
        
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self.return_pressed.emit()
            event.accept()
            return
            
        if event.key() == Qt.Key.Key_Backspace:
            if current_pos <= self.input_start_position:
                event.ignore()
                return
        elif event.key() == Qt.Key.Key_Left:
            if current_pos <= self.input_start_position:
                event.ignore()
                return

        if cursor.hasSelection():
            if cursor.selectionStart() < self.input_start_position:
                event.ignore()
                return

        super().keyPressEvent(event)

class PowerShellWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.text_edit = ProtectedTextEdit()
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: transparent; 
                color: #000000; 
                font-family: Consolas; 
                font-size: 13px;
                border: none;
            }
        """)
        layout.addWidget(self.text_edit)
        
        self.process = QProcess()
        self.process.setProgram("powershell.exe")
        self.process.start()
        
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        
        self.text_edit.return_pressed.connect(self.run_command)
        
        # 启动后自动清屏，消除视觉误导
        self.process.write("Clear-Host\n".encode('gbk'))
        self.text_edit.input_start_position = self.text_edit.textCursor().position()

    def handle_stdout(self):
        data = self.process.readAllStandardOutput().data().decode('gbk', errors='ignore')
        self.text_edit.input_start_position = -1 
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.text_edit.setTextCursor(cursor)
        self.text_edit.insertPlainText(data)
        self.text_edit.input_start_position = self.text_edit.textCursor().position()

    def handle_stderr(self):
        data = self.process.readAllStandardError().data().decode('gbk', errors='ignore')
        self.text_edit.input_start_position = -1
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.text_edit.setTextCursor(cursor)
        self.text_edit.insertPlainText(f"Error: {data}")
        self.text_edit.input_start_position = self.text_edit.textCursor().position()

    def run_command(self):
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.setPosition(self.text_edit.input_start_position, QTextCursor.MoveMode.KeepAnchor)
        cmd = cursor.selectedText().strip() + "\n"
        
        self.process.write(cmd.encode('gbk'))
        self.text_edit.input_start_position = -1 
        self.text_edit.insertPlainText("\n")

class AudioSplitterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Audio Studio")
        self.resize(820, 480)
        
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowMinMaxButtonsHint)
        
        self.old_pos = QPoint()
        self.file_paths = []
        self.single_file = ""
        self.current_skin_path = None
        self.current_style_mode = "男娘模式"
        self.pil_processed_image = None
        self.bg_pixmap = QPixmap()
        
        self.song_title = ""
        self.song_artist = ""
        self.song_album = ""

        self.central_widget = QWidget(self)
        self.central_widget.setObjectName("CentralWidget")
        self.central_widget.setStyleSheet("QWidget#CentralWidget { background-color: transparent; }")
        self.setCentralWidget(self.central_widget)
        
        main_layout = QHBoxLayout(self.central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. 左侧窄导航栏
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(65)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(10, 20, 10, 20)

        self.btn_style_base = "border-radius: 8px; font-size: 16px; border: none;"
        
        self.btn_vocal = QPushButton("🎤")
        self.btn_vocal.setFixedSize(45, 45)
        self.btn_vocal.clicked.connect(lambda: self.switch_tab(0))
        sidebar_layout.addWidget(self.btn_vocal)

        self.btn_stems = QPushButton("🎛️")
        self.btn_stems.setFixedSize(45, 45)
        self.btn_stems.clicked.connect(lambda: self.switch_tab(1))
        sidebar_layout.addWidget(self.btn_stems)

        self.btn_recognize = QPushButton("🔍")
        self.btn_recognize.setFixedSize(45, 45)
        self.btn_recognize.clicked.connect(lambda: self.switch_tab(2))
        sidebar_layout.addWidget(self.btn_recognize)

        self.btn_ps = QPushButton("💻")
        self.btn_ps.setFixedSize(45, 45)
        self.btn_ps.clicked.connect(lambda: self.switch_tab(3))
        sidebar_layout.addWidget(self.btn_ps)

        self.btn_settings = QPushButton("⚙️")
        self.btn_settings.setFixedSize(45, 45)
        self.btn_settings.clicked.connect(lambda: self.switch_tab(4))
        sidebar_layout.addWidget(self.btn_settings)

        sidebar_layout.addStretch()
        main_layout.addWidget(self.sidebar)

        self.separator = QWidget()
        self.separator.setFixedWidth(1)
        main_layout.addWidget(self.separator)

        # 2. 右侧内容区
        self.content_container = QWidget()
        content_layout = QVBoxLayout(self.content_container)
        content_layout.setContentsMargins(25, 15, 25, 20)

        top_bar = QHBoxLayout()
        self.title_lbl = QLabel("AI Audio Studio                                                                   软件开发者：SummerLunch")
        self.title_lbl.setStyleSheet("font-weight: bold; font-size: 13px; background: transparent;")
        top_bar.addWidget(self.title_lbl)
        top_bar.addStretch()

        self.btn_min = QPushButton("—")
        self.btn_min.setFixedSize(30, 30)
        self.btn_min.setStyleSheet("border: none; background: transparent; font-weight: bold;")
        self.btn_min.clicked.connect(self.showMinimized)
        top_bar.addWidget(self.btn_min)

        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(30, 30)
        self.btn_close.setStyleSheet("border: none; background: transparent; color: #ef4444; font-weight: bold;")
        self.btn_close.clicked.connect(self.close)
        top_bar.addWidget(self.btn_close)

        content_layout.addLayout(top_bar)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: transparent;")
        
        self.init_vocal_page()
        self.init_stems_page()
        self.init_recognize_page()
        
        self.ps_page = PowerShellWidget()
        self.stack.addWidget(self.ps_page)
        
        self.init_settings_page()

        content_layout.addWidget(self.stack)
        main_layout.addWidget(self.content_container)

        self.apply_theme_styles()

        for skin in ["background.jpg", "background.png", "background.jpeg"]:
            if os.path.exists(skin):
                self.load_skin(skin, update_msg=False)
                break

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 15, 15)
        painter.setClipPath(path)
        
        if not self.bg_pixmap.isNull():
            painter.drawPixmap(self.rect(), self.bg_pixmap)
        else:
            painter.fillPath(path, QColor(240, 242, 245))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.pil_processed_image:
            self.update_bg_pixmap()

    def set_style_mode(self, mode_text):
        self.current_style_mode = mode_text
        self.apply_theme_styles()
        if self.current_skin_path and os.path.exists(self.current_skin_path):
            self.load_skin(self.current_skin_path, update_msg=False)

    def apply_theme_styles(self):
        current_index = self.stack.currentIndex()
        if self.current_style_mode == "男娘模式":
            self.sidebar.setStyleSheet("background-color: rgba(243, 244, 246, 150); border-top-left-radius: 15px; border-bottom-left-radius: 15px;")
            self.separator.setStyleSheet("background-color: rgba(229, 231, 235, 100);")
            self.content_container.setStyleSheet("background-color: rgba(255, 255, 255, 120); border-top-right-radius: 15px; border-bottom-right-radius: 15px;")
            self.title_lbl.setStyleSheet("font-weight: bold; color: #111827; font-size: 13px; background: transparent;")
            self.btn_min.setStyleSheet("border: none; background: transparent; color: #111827; font-weight: bold;")
            for entry in [self.entry_vocal, self.entry_stems]:
                entry.setStyleSheet("background: rgba(255, 255, 255, 180); border: 1px solid #d1d5db; border-radius: 6px; padding: 6px; color: #111827;")
            for lbl in [self.lbl_vocal_status, self.lbl_stems_status, self.lbl_recognize_status, self.lbl_title, self.lbl_artist, self.lbl_album]:
                lbl.setStyleSheet("color: #374151; background: transparent; font-weight: bold;")
        else:
            self.sidebar.setStyleSheet("background-color: rgba(30, 30, 30, 180); border-top-left-radius: 15px; border-bottom-left-radius: 15px;")
            self.separator.setStyleSheet("background-color: rgba(255, 255, 255, 50);")
            self.content_container.setStyleSheet("background-color: rgba(25, 25, 25, 150); border-top-right-radius: 15px; border-bottom-right-radius: 15px;")
            self.title_lbl.setStyleSheet("font-weight: bold; color: #f3f4f6; font-size: 13px; background: transparent;")
            self.btn_min.setStyleSheet("border: none; background: transparent; color: #f3f4f6; font-weight: bold;")
            for entry in [self.entry_vocal, self.entry_stems]:
                entry.setStyleSheet("background: rgba(30, 30, 30, 180); border: 1px solid rgba(255, 255, 255, 40); border-radius: 6px; padding: 6px; color: #f3f4f6;")
            for lbl in [self.lbl_vocal_status, self.lbl_stems_status, self.lbl_recognize_status, self.lbl_title, self.lbl_artist, self.lbl_album]:
                lbl.setStyleSheet("color: #9ca3af; background: transparent; font-weight: bold;")
        self.switch_tab(current_index)

    def load_skin(self, image_path, update_msg=False):
        try:
            self.current_skin_path = image_path
            raw_img = Image.open(image_path).convert("RGB")
            if self.current_style_mode == "男娘模式":
                blurred = raw_img.filter(ImageFilter.GaussianBlur(radius=8))
                white_tint = Image.new("RGB", blurred.size, (245, 247, 250))
                self.pil_processed_image = Image.blend(blurred, white_tint, alpha=0.12)
            else:
                blurred = raw_img.filter(ImageFilter.GaussianBlur(radius=10))
                pixels = blurred.load()
                width, height = blurred.size
                for x in range(0, width, 1):
                    for y in range(0, height, 1):
                        r, g, b = pixels[x, y]
                        noise = random.randint(-18, 18)
                        nr = max(0, min(255, r + noise))
                        ng = max(0, min(255, g + noise))
                        nb = max(0, min(255, b + noise))
                        pixels[x, y] = (nr, ng, nb)
                bright_tint = Image.new("RGB", blurred.size, (220, 225, 230))
                self.pil_processed_image = Image.blend(blurred, bright_tint, alpha=0.15)
            self.update_bg_pixmap()
            if update_msg:
                QMessageBox.information(self, "成功", "壁纸更换成功！")
            return True
        except Exception as e:
            return False

    def update_bg_pixmap(self):
        if not self.pil_processed_image:
            return
        w, h = self.width(), self.height()
        if w > 10 and h > 10:
            resized = self.pil_processed_image.resize((w, h), Image.Resampling.LANCZOS)
            im_data = resized.convert("RGBA").tobytes("raw", "RGBA")
            qim = QImage(im_data, resized.width, resized.height, QImage.Format.Format_RGBA8888)
            self.bg_pixmap = QPixmap.fromImage(qim)
            self.update()

    def switch_tab(self, index):
        self.stack.setCurrentIndex(index)
        btns = [self.btn_vocal, self.btn_stems, self.btn_recognize, self.btn_ps, self.btn_settings]
        for i, btn in enumerate(btns):
            if i == index:
                c = "rgba(0, 0, 0, 30)" if self.current_style_mode == "男娘模式" else "rgba(255, 255, 255, 60)"
                btn.setStyleSheet(f"background-color: {c}; {self.btn_style_base}")
            else:
                btn.setStyleSheet(f"background-color: transparent; {self.btn_style_base}")

    # ==================== 页面 1：人声伴奏分离 ====================
    def init_vocal_page(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 10)

        lbl = QLabel("人声与伴奏极速分离")
        lbl.setStyleSheet("font-weight: bold; font-size: 15px; background: transparent;")
        layout.addWidget(lbl)

        file_layout = QHBoxLayout()
        self.entry_vocal = QLineEdit()
        self.entry_vocal.setPlaceholderText("选择需要分离的音频...")
        self.entry_vocal.setReadOnly(True)
        file_layout.addWidget(self.entry_vocal)

        btn_browse = QPushButton("浏览...")
        btn_browse.setStyleSheet("background: #2563eb; color: white; border-radius: 6px; padding: 6px 15px; font-weight: bold; border: none;")
        btn_browse.clicked.connect(self.browse_vocal)
        file_layout.addWidget(btn_browse)
        layout.addLayout(file_layout)

        self.btn_vocal_start = QPushButton("开始分离人声与伴奏")
        self.btn_vocal_start.setStyleSheet("background: #2563eb; color: white; border-radius: 6px; padding: 10px; font-weight: bold; border: none;")
        self.btn_vocal_start.clicked.connect(self.start_vocal_process)
        layout.addWidget(self.btn_vocal_start)

        self.lbl_vocal_status = QLabel("状态: 等待操作...")
        layout.addWidget(self.lbl_vocal_status)

        self.progress_vocal = QProgressBar()
        self.progress_vocal.setRange(0, 0)
        self.progress_vocal.hide()
        layout.addWidget(self.progress_vocal)

        layout.addStretch()
        self.stack.addWidget(page)

    def browse_vocal(self):
        filename, _ = QFileDialog.getOpenFileName(self, "选择音频", "", "音频文件 (*.mp3 *.wav *.flac *.m4a *.aac);;所有文件 (*.*)")
        if filename:
            self.single_file = filename
            self.entry_vocal.setText(filename)
            self.lbl_vocal_status.setText(f"状态: 已加载 {os.path.basename(filename)}")

    def start_vocal_process(self):
        if not self.single_file:
            QMessageBox.warning(self, "提示", "请先选择音频文件！")
            return
        self.btn_vocal_start.setEnabled(False)
        self.progress_vocal.show()
        self.lbl_vocal_status.setText("状态: AI 处理中，请稍候...")
        
        self.signals = WorkerSignals()
        self.signals.finished.connect(self.vocal_finished)
        self.signals.error.connect(self.vocal_error)
        
        threading.Thread(target=self.run_demucs_vocal, daemon=True).start()

    def run_demucs_vocal(self):
        output_dir = os.path.join(os.path.dirname(self.single_file), "Separated_Output")
        os.makedirs(output_dir, exist_ok=True)
        if sys.stdout is None: sys.stdout = DummyStream()
        if sys.stderr is None: sys.stderr = DummyStream()
        try:
            if getattr(sys, 'frozen', False):
                os.environ["PATH"] = sys._MEIPASS + os.pathsep + os.environ["PATH"]
            from demucs.separate import main as demucs_main
            sys.argv = ["demucs", "--two-stems", "vocals", "-o", output_dir, self.single_file]
            demucs_main()
            self.signals.finished.emit(output_dir)
        except Exception as e:
            self.signals.error.emit(str(e))

    def vocal_finished(self, out_dir):
        self.progress_vocal.hide()
        self.btn_vocal_start.setEnabled(True)
        self.lbl_vocal_status.setText("状态: 分离成功！")
        QMessageBox.information(self, "完成", f"分离完成！\n保存在: {out_dir}")

    def vocal_error(self, err):
        self.progress_vocal.hide()
        self.btn_vocal_start.setEnabled(True)
        self.lbl_vocal_status.setText("状态: 处理失败")
        QMessageBox.critical(self, "错误", f"发生错误: {err[:100]}")

    # ==================== 页面 2：多音轨分离 ====================
    def init_stems_page(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 10)

        lbl = QLabel("专业多音轨拆分 (4stems)")
        lbl.setStyleSheet("font-weight: bold; font-size: 15px; background: transparent;")
        layout.addWidget(lbl)

        file_layout = QHBoxLayout()
        self.entry_stems = QLineEdit()
        self.entry_stems.setPlaceholderText("支持【多选】音频拆分为 人声/鼓点/贝斯/其他...")
        self.entry_stems.setReadOnly(True)
        file_layout.addWidget(self.entry_stems)

        btn_browse = QPushButton("批量选择")
        btn_browse.setStyleSheet("background: #2563eb; color: white; border-radius: 6px; padding: 6px 15px; font-weight: bold; border: none;")
        btn_browse.clicked.connect(self.browse_stems)
        file_layout.addWidget(btn_browse)
        layout.addLayout(file_layout)

        self.btn_stems_start = QPushButton("开始 4 轨智能拆分")
        self.btn_stems_start.setStyleSheet("background: #2563eb; color: white; border-radius: 6px; padding: 10px; font-weight: bold; border: none;")
        self.btn_stems_start.clicked.connect(self.start_stems_process)
        layout.addWidget(self.btn_stems_start)

        self.lbl_stems_status = QLabel("状态: 等待导入文件...")
        layout.addWidget(self.lbl_stems_status)

        self.progress_stems = QProgressBar()
        self.progress_stems.setRange(0, 0)
        self.progress_stems.hide()
        layout.addWidget(self.progress_stems)

        layout.addStretch()
        self.stack.addWidget(page)

    def browse_stems(self):
        filenames, _ = QFileDialog.getOpenFileNames(self, "选择音频（支持多选）", "", "音频文件 (*.mp3 *.wav *.flac *.m4a);;所有文件 (*.*)")
        if filenames:
            self.file_paths = filenames
            self.entry_stems.setText(f"已选择 {len(filenames)} 个文件")
            self.lbl_stems_status.setText(f"状态: 已加载 {len(filenames)} 首歌曲")

    def start_stems_process(self):
        if not self.file_paths:
            QMessageBox.warning(self, "提示", "请先选择音频文件！")
            return
        self.btn_stems_start.setEnabled(False)
        self.progress_stems.show()
        self.lbl_stems_status.setText("状态: 4轨拆分处理中...")
        threading.Thread(target=self.run_demucs_stems, daemon=True).start()

    def run_demucs_stems(self):
        total = len(self.file_paths)
        success = 0
        if sys.stdout is None: sys.stdout = DummyStream()
        if sys.stderr is None: sys.stderr = DummyStream()
        try:
            if getattr(sys, 'frozen', False):
                os.environ["PATH"] = sys._MEIPASS + os.pathsep + os.environ["PATH"]
            from demucs.separate import main as demucs_main
            for f in self.file_paths:
                out_dir = os.path.join(os.path.dirname(f), "Separated_Output")
                os.makedirs(out_dir, exist_ok=True)
                sys.argv = ["demucs", "-o", out_dir, f]
                try:
                    demucs_main()
                    success += 1
                except Exception as e:
                    print(e)
            QMessageBox.information(self, "完成", f"多音轨任务全部处理完毕！成功: {success}/{total}")
        except Exception as e:
            print("Stems error:", e)

    # ==================== 页面 3：听歌识曲 ====================
    def init_recognize_page(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 10)

        lbl = QLabel("全网听歌识曲 (内录识别)")
        lbl.setStyleSheet("font-weight: bold; font-size: 15px; background: transparent;")
        layout.addWidget(lbl)

        desc = QLabel("请确保电脑正在播放音乐，点击下方按钮将自动监听 5 秒并识别歌曲。")
        desc.setStyleSheet("font-size: 11px; background: transparent;")
        layout.addWidget(desc)

        self.btn_recognize_start = QPushButton("开始听歌识曲（监听 5 秒）")
        self.btn_recognize_start.setStyleSheet("background: #2563eb; color: white; border-radius: 6px; padding: 10px; font-weight: bold; border: none;")
        self.btn_recognize_start.clicked.connect(self.start_recognize_process)
        layout.addWidget(self.btn_recognize_start)

        self.lbl_recognize_status = QLabel("状态: 准备就绪...")
        layout.addWidget(self.lbl_recognize_status)

        self.progress_recognize = QProgressBar()
        self.progress_recognize.setRange(0, 0)
        self.progress_recognize.hide()
        layout.addWidget(self.progress_recognize)

        title_layout = QHBoxLayout()
        self.lbl_title = QLabel("🎵 歌名: 暂无")
        self.lbl_title.setStyleSheet("font-size: 13px; font-weight: bold; background: transparent;")
        title_layout.addWidget(self.lbl_title)
        title_layout.addStretch()
        self.btn_copy_title = QPushButton("复制歌名")
        self.btn_copy_title.setStyleSheet("background: #2563eb; color: white; border-radius: 4px; padding: 4px 10px; font-size: 11px; font-weight: bold; border: none;")
        self.btn_copy_title.clicked.connect(lambda: self.copy_field(self.song_title, "歌名"))
        self.btn_copy_title.hide()
        title_layout.addWidget(self.btn_copy_title)
        layout.addLayout(title_layout)

        artist_layout = QHBoxLayout()
        self.lbl_artist = QLabel("🎤 歌手: 暂无")
        self.lbl_artist.setStyleSheet("font-size: 13px; font-weight: bold; background: transparent;")
        artist_layout.addWidget(self.lbl_artist)
        artist_layout.addStretch()
        self.btn_copy_artist = QPushButton("复制歌手")
        self.btn_copy_artist.setStyleSheet("background: #2563eb; color: white; border-radius: 4px; padding: 4px 10px; font-size: 11px; font-weight: bold; border: none;")
        self.btn_copy_artist.clicked.connect(lambda: self.copy_field(self.song_artist, "歌手"))
        self.btn_copy_artist.hide()
        artist_layout.addWidget(self.btn_copy_artist)
        layout.addLayout(artist_layout)

        album_layout = QHBoxLayout()
        self.lbl_album = QLabel("💿 专辑: 暂无")
        self.lbl_album.setStyleSheet("font-size: 13px; font-weight: bold; background: transparent;")
        album_layout.addWidget(self.lbl_album)
        album_layout.addStretch()
        self.btn_copy_album = QPushButton("复制专辑")
        self.btn_copy_album.setStyleSheet("background: #2563eb; color: white; border-radius: 4px; padding: 4px 10px; font-size: 11px; font-weight: bold; border: none;")
        self.btn_copy_album.clicked.connect(lambda: self.copy_field(self.song_album, "专辑"))
        self.btn_copy_album.hide()
        album_layout.addWidget(self.btn_copy_album)
        layout.addLayout(album_layout)

        layout.addStretch()
        self.stack.addWidget(page)

    def start_recognize_process(self):
        self.btn_recognize_start.setEnabled(False)
        self.btn_copy_title.hide()
        self.btn_copy_artist.hide()
        self.btn_copy_album.hide()
        self.progress_recognize.show()
        self.lbl_recognize_status.setText("状态: 正在监听电脑播放的声音...")
        self.lbl_title.setText("🎵 歌名: 监听中...")
        self.lbl_artist.setText("🎤 歌手: 监听中...")
        self.lbl_album.setText("💿 专辑: 监听中...")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            self.temp_filename = tmp.name

        self.rec_signals = RecognizeSignals()
        self.rec_signals.status.connect(self.recognize_status_update)
        self.rec_signals.finished.connect(self.recognize_finished)
        self.rec_signals.error.connect(self.recognize_error)

        threading.Thread(target=self.run_recognize_task, daemon=True).start()

    def run_recognize_task(self):
        DURATION, SAMPLE_RATE, CHANNELS = 5, 44100, 2
        try:
            devices = sd.query_devices()
            device_idx = sd.default.device[0]
            for idx, dev in enumerate(devices):
                name = dev['name'].lower()
                if 'loopback' in name or 'stereo mix' in name or '立体声混音' in name:
                    device_idx = idx
                    break

            audio_data = sd.rec(int(DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='int16', device=device_idx)
            sd.wait()
            
            with wave.open(self.temp_filename, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(2)
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(audio_data.tobytes())
                
            self.rec_signals.status.emit("✅ 录音完成，正在识别...")

            url = "https://api.audd.io/"
            with open(self.temp_filename, 'rb') as f:
                response = requests.post(url, data={'api_token': 'test', 'return': 'apple_music,spotify'}, files={'file': f})
                result = response.json()
                if result.get('status') == 'success' and result.get('result'):
                    self.rec_signals.finished.emit(result['result'])
                else:
                    self.rec_signals.error.emit("未能识别该歌曲。")
        except Exception as e:
            self.rec_signals.error.emit(f"识别出错: {e}")
        finally:
            if os.path.exists(self.temp_filename):
                try: os.remove(self.temp_filename)
                except: pass

    def recognize_status_update(self, text):
        self.lbl_recognize_status.setText(text)

    def recognize_finished(self, song):
        self.progress_recognize.hide()
        self.btn_recognize_start.setEnabled(True)
        self.lbl_recognize_status.setText("状态: 识别成功！")
        self.song_title = song.get('title', '未知')
        self.song_artist = song.get('artist', '未知')
        self.song_album = song.get('album', '未知')
        self.lbl_title.setText(f"🎵 歌名: {self.song_title}")
        self.lbl_artist.setText(f"🎤 歌手: {self.song_artist}")
        self.lbl_album.setText(f"💿 专辑: {self.song_album}")
        self.btn_copy_title.show()
        self.btn_copy_artist.show()
        self.btn_copy_album.show()

    def copy_field(self, text, field_name):
        if text:
            QApplication.clipboard().setText(text)
            self.lbl_recognize_status.setText(f"状态: 已成功复制{field_name}！")

    def recognize_error(self, err):
        self.progress_recognize.hide()
        self.btn_recognize_start.setEnabled(True)
        self.lbl_recognize_status.setText("状态: 识别失败")
        self.lbl_title.setText("🎵 歌名: 识别失败")
        self.lbl_artist.setText(f"🎤 歌手: {err}")
        self.lbl_album.setText("💿 专辑: 暂无")

    # ==================== 页面 5：系统设置 ====================
    def init_settings_page(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 10)

        lbl = QLabel("个性化外观设置")
        lbl.setStyleSheet("font-weight: bold; font-size: 15px; background: transparent;")
        layout.addWidget(lbl)

        card = QWidget()
        card.setStyleSheet("background: rgba(30, 30, 30, 160); border: 1px solid rgba(255, 255, 255, 40); border-radius: 8px;")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("🎨 界面材质与壁纸设置")
        title.setStyleSheet("font-weight: bold; font-size: 13px; color: #f3f4f6; border: none; background: transparent;")
        card_layout.addWidget(title)

        mode_layout = QHBoxLayout()
        lbl_mode = QLabel("磨砂材质风格:")
        lbl_mode.setStyleSheet("color: #f3f4f6; font-size: 12px; background: transparent;")
        mode_layout.addWidget(lbl_mode)

        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["男娘模式", "嘉豪模式"])
        self.combo_mode.setCurrentText(self.current_style_mode)
        self.combo_mode.setStyleSheet("background: rgba(50, 50, 50, 200); color: white; border: 1px solid rgba(255, 255, 255, 40); border-radius: 4px; padding: 4px;")
        self.combo_mode.currentTextChanged.connect(self.set_style_mode)
        mode_layout.addWidget(self.combo_mode)
        card_layout.addLayout(mode_layout)

        btn_skin = QPushButton("选择并更换背景图片")
        btn_skin.setStyleSheet("background: #2563eb; color: white; border-radius: 6px; padding: 8px 15px; font-weight: bold; border: none;")
        btn_skin.clicked.connect(self.change_skin)
        card_layout.addWidget(btn_skin)

        layout.addWidget(card)
        layout.addStretch()
        self.stack.addWidget(page)

    def change_skin(self):
        img_path, _ = QFileDialog.getOpenFileName(self, "选择背景皮肤图片", "", "图片文件 (*.jpg *.jpeg *.png *.webp);;所有文件 (*.*)")
        if img_path:
            self.load_skin(img_path, update_msg=True)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = AudioSplitterApp()
    window.show()
    sys.exit(app.exec())