#!/usr/bin/env python3
"""
Pomodoro Timer — Apple-inspired desktop app.
Requires: PySide6
Run:    python pomodoro.py
Build:  pyinstaller --onefile --windowed --name Pomodoro pomodoro.py
"""

import sys
import os
import math
import struct
import wave
import tempfile
import atexit
from time import perf_counter as _perf_counter
from pathlib import Path

# ── System dark-mode detection (no extra deps) ─────────────────────────────
def _is_system_dark():
    """Detect OS dark mode without third-party packages."""
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            )
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return val == 0
        except Exception:
            pass
    elif sys.platform == "darwin":
        try:
            import subprocess
            r = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True
            )
            return "Dark" in r.stdout
        except Exception:
            pass
    return False  # default light


def _is_widget_dark(widget) -> bool:
    """Check if widget is in a dark-themed window."""
    while widget:
        if hasattr(widget, '_is_dark'):
            return widget._is_dark
        widget = widget.parent()
    return False

# ── Check PySide6 ──────────────────────────────────────────────────────────
try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QStackedWidget, QSlider, QSpinBox,
        QFrame, QSizePolicy, QButtonGroup, QRadioButton, QStyle,
        QGraphicsDropShadowEffect, QScrollArea,
    )
    from PySide6.QtCore import (
        Qt, QTimer, QPropertyAnimation, QEasingCurve, QSettings,
        QPoint, QPointF, Signal, QRectF, QSize, Property as QtCore_Property,
    )
    from PySide6.QtGui import (
        QPainter, QPen, QColor, QFont, QFontDatabase,
        QIcon, QPixmap, QPainterPath, QAction, QPalette, QLinearGradient,
    )
except ImportError:
    print("请先安装 PySide6:  pip install PySide6")
    sys.exit(1)

# ── Chime Generator (no external deps) ─────────────────────────────────────
CHIME_PATH = None

def _generate_chime_wav():
    """Generate a pleasant 3-note chime WAV, return file path."""
    sample_rate = 44100
    notes = [523.25, 659.25, 783.99]  # C5, E5, G5
    note_dur = 0.22
    decay_extra = 0.35
    total = len(notes) * note_dur + decay_extra
    n = int(sample_rate * total)
    samples = []
    for i in range(n):
        t = i / sample_rate
        v = 0.0
        for j, freq in enumerate(notes):
            start = j * note_dur
            if t >= start:
                dt = t - start
                env = math.exp(-4.5 * dt)
                v += 0.28 * math.sin(2 * math.pi * freq * t) * env
        v = max(-1.0, min(1.0, v))
        samples.append(int(v * 32767))

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack("<" + "h" * len(samples), *samples))
    return tmp.name

def play_chime(volume=80):
    """Play chime sound at given volume (0-100)."""
    global CHIME_PATH
    if CHIME_PATH is None:
        CHIME_PATH = _generate_chime_wav()
    try:
        import winsound
        winsound.PlaySound(CHIME_PATH, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception:
        pass  # silent fail — sound is non-critical

def _cleanup_chime():
    global CHIME_PATH
    if CHIME_PATH and os.path.exists(CHIME_PATH):
        try:
            os.unlink(CHIME_PATH)
        except Exception:
            pass

atexit.register(_cleanup_chime)


# ── App Icon Generator ──────────────────────────────────────────────────────
def _create_tomato_pixmap(size=64):
    """Paint a tomato icon programmatically, return QPixmap."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)

    s = size
    m = s * 0.08  # margin

    # Tomato body (red-orange gradient circle, slightly flattened)
    body = QRectF(m, m + s * 0.14, s - 2 * m, s * 0.78)
    grad = QLinearGradient(body.topLeft(), body.bottomRight())
    grad.setColorAt(0.0, QColor("#ff5c4a"))
    grad.setColorAt(0.5, QColor("#e8453a"))
    grad.setColorAt(1.0, QColor("#c0392b"))
    p.setBrush(grad)
    p.setPen(Qt.NoPen)
    p.drawEllipse(body)

    # Highlight (top-left light spot)
    hl = QRectF(body.x() + body.width() * 0.2,
                body.y() + body.height() * 0.12,
                body.width() * 0.38,
                body.height() * 0.35)
    hl_grad = QLinearGradient(hl.topLeft(), hl.bottomRight())
    hl_grad.setColorAt(0.0, QColor(255, 255, 255, 120))
    hl_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.setBrush(hl_grad)
    p.drawEllipse(hl)

    # Green leaf
    leaf_path = QPainterPath()
    lx = s / 2
    ly = m + s * 0.14
    leaf_path.moveTo(lx - s * 0.06, ly)
    leaf_path.cubicTo(lx - s * 0.18, ly - s * 0.2,
                      lx + s * 0.08, ly - s * 0.22,
                      lx + s * 0.1, ly + s * 0.02)
    leaf_path.cubicTo(lx + s * 0.06, ly - s * 0.08,
                      lx - s * 0.02, ly - s * 0.04,
                      lx - s * 0.06, ly)
    p.setBrush(QColor("#4cd964"))
    p.drawPath(leaf_path)

    # Stem
    stem_pen = QPen(QColor("#5a8f3c"), s * 0.05)
    stem_pen.setCapStyle(Qt.RoundCap)
    p.setPen(stem_pen)
    p.drawLine(QPointF(lx + s * 0.01, ly - s * 0.05),
               QPointF(lx + s * 0.01, ly - s * 0.16))

    p.end()
    return pm


def _generate_ico(pixmap: QPixmap, path: str):
    """Save a QPixmap as a Windows .ico file (PNG-in-ICO format)."""
    import io
    ba = QPixmap(pixmap)
    buf = QPixmap(ba)
    # Save pixmap to PNG bytes
    png_bytes = QPixmap(pixmap)
    # QPixmap.save to memory
    byte_arr = QPixmap(pixmap)
    # Use QBuffer
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    ba = QByteArray()
    buf_device = QBuffer(ba)
    buf_device.open(QIODevice.WriteOnly)
    pixmap.save(buf_device, "PNG")
    buf_device.close()
    png_data = ba.data()

    # Write ICO: header(6) + entry(16) + PNG data
    with open(path, "wb") as f:
        # ICO header
        f.write(struct.pack("<HHH", 0, 1, 1))  # reserved, type=ICO, count=1
        w, h = pixmap.width(), pixmap.height()
        f.write(struct.pack("<BBBBHHII",
            0 if w >= 256 else w,   # width (0 = 256)
            0 if h >= 256 else h,   # height
            0, 0,                    # color count, reserved
            1, 32,                   # planes, bpp
            len(png_data),           # size of image data
            22))                     # offset to image data (6 + 16)
        f.write(png_data)


# ── Windows Acrylic / Blur Behind ──────────────────────────────────────────
def _enable_acrylic(hwnd, dark=False):
    """Enable Windows 10/11 acrylic blur behind the window for real frosted glass."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        class ACCENTPOLICY(ctypes.Structure):
            _fields_ = [
                ("AccentState", ctypes.c_uint),
                ("AccentFlags", ctypes.c_uint),
                ("GradientColor", ctypes.c_uint),
                ("AnimationId", ctypes.c_uint),
            ]
        class WINCOMPATTRDATA(ctypes.Structure):
            _fields_ = [
                ("Attribute", ctypes.c_int),
                ("Data", ctypes.POINTER(ACCENTPOLICY)),
                ("SizeOfData", ctypes.c_size_t),
            ]
        accent = ACCENTPOLICY()
        accent.AccentState = 3  # ACCENT_ENABLE_BLURBEHIND (works on Win10/11)
        accent.AccentFlags = 0
        accent.GradientColor = 0x00000000
        data = WINCOMPATTRDATA()
        data.Attribute = 19  # WCA_ACCENT_POLICY
        data.SizeOfData = ctypes.sizeof(accent)
        data.Data = ctypes.pointer(accent)
        ctypes.windll.user32.SetWindowCompositionAttribute(
            ctypes.wintypes.HWND(hwnd), ctypes.byref(data)
        )
    except Exception:
        pass

# ── Apple Color Palette ────────────────────────────────────────────────────
LIGHT = {
    "bg":           "#f5f5f7",
    "card":         "rgba(255,255,255,0.75)",
    "card_solid":   "#ffffff",
    "text":         "#1d1d1f",
    "text_sec":     "#86868b",
    "blue":         "#007aff",
    "green":        "#34c759",
    "orange":       "#ff9500",
    "red":          "#ff3b30",
    "ring_bg":      "#e5e5ea",
    "btn_bg":       "rgba(0,0,0,0.04)",
    "btn_hover":    "rgba(0,0,0,0.08)",
    "sep":          "rgba(0,0,0,0.08)",
    "tab_active":   "#ffffff",
    "tab_inactive": "transparent",
    "slider_groove": "#e5e5ea",
    "input_bg":     "#f2f2f7",
}

DARK = {
    "bg":           "#000000",
    "card":         "rgba(28,28,30,0.78)",
    "card_solid":   "#1c1c1e",
    "text":         "#f5f5f7",
    "text_sec":     "#98989d",
    "blue":         "#0a84ff",
    "green":        "#30d158",
    "orange":       "#ff9f0a",
    "red":          "#ff453a",
    "ring_bg":      "#3a3a3c",
    "btn_bg":       "rgba(255,255,255,0.08)",
    "btn_hover":    "rgba(255,255,255,0.14)",
    "sep":          "rgba(255,255,255,0.1)",
    "tab_active":   "#636366",
    "tab_inactive": "transparent",
    "slider_groove": "#3a3a3c",
    "input_bg":     "#2c2c2e",
}


# ── Circular Progress Widget ───────────────────────────────────────────────
class CircularProgress(QWidget):
    """Apple-style circular progress ring with center text."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress = 0.0          # 0.0 … 1.0
        self._color = QColor("#007aff")
        self._ring_bg_color = QColor("#e5e5ea")
        self._ring_width = 6
        self._text = "25:00"
        self._label = "专注"
        self.setMinimumSize(200, 200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_progress(self, val: float):
        self._progress = max(0.0, min(1.0, val))
        self.update()

    def set_ring_color(self, color: QColor):
        self._color = QColor(color)
        self.update()

    def set_ring_bg(self, color: QColor):
        self._ring_bg_color = QColor(color)
        self.update()

    def set_text(self, text: str):
        self._text = text
        self.update()

    def set_label(self, label: str):
        self._label = label
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        side = min(w, h)
        margin = self._ring_width / 2 + 4
        ring_rect = QRectF(
            (w - side) / 2 + margin,
            (h - side) / 2 + margin,
            side - 2 * margin,
            side - 2 * margin,
        )

        # Background ring
        pen = QPen(self._ring_bg_color, self._ring_width)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(ring_rect, 90 * 16, -360 * 16)

        # Progress ring
        if self._progress > 0.001:
            pen.setColor(self._color)
            p.setPen(pen)
            span = int(-360 * self._progress * 16)
            p.drawArc(ring_rect, 90 * 16, span)

        # Center text
        p.setPen(QColor(self.palette().color(QPalette.WindowText)))
        font = QFont()
        font.setFamilies(["-apple-system", "Segoe UI Variable", "Segoe UI", "Helvetica Neue", "sans-serif"])
        font.setPixelSize(int(side * 0.205))
        font.setWeight(QFont.ExtraLight)
        p.setFont(font)
        p.drawText(QRectF(0, 0, w, h - 6), Qt.AlignCenter, self._text)

        # Label below time
        font2 = QFont()
        font2.setFamilies(["-apple-system", "Segoe UI Variable", "Segoe UI", "Helvetica Neue", "sans-serif"])
        font2.setPixelSize(int(side * 0.045))
        font2.setWeight(QFont.Medium)
        font2.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.5)
        p.setPen(QColor(self.palette().color(QPalette.WindowText).darker(160)))
        p.setFont(font2)
        p.drawText(QRectF(0, 0, w, h + int(side * 0.12)), Qt.AlignHCenter | Qt.AlignBottom, self._label)

        p.end()


# ── Timer Page ─────────────────────────────────────────────────────────────
class TimerPage(QWidget):
    """Main timer page with circular progress, controls, and session dots."""

    DEFAULT_DURATIONS = {"focus": 25, "shortBreak": 5, "longBreak": 15}
    LABELS = {"focus": "专注", "shortBreak": "短休息", "longBreak": "长休息"}

    session_finished = Signal(str)  # emitted when a session finishes

    def __init__(self, settings: QSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.mode = "focus"
        self._load_durations()
        self.remaining = self.durations[self.mode]
        self.running = False
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(50)  # 20 fps for smooth ring
        self._tick_timer.timeout.connect(self._tick)
        self._tick_start = 0.0
        self._tick_target = self.remaining
        self.completed = 0  # completed focus sessions (0-3)

        self._build_ui()

    def _load_durations(self):
        self.durations = {
            "focus": int(self.settings.value("duration_focus", 25)),
            "shortBreak": int(self.settings.value("duration_short", 5)),
            "longBreak": int(self.settings.value("duration_long", 15)),
        }
        # Convert minutes → seconds
        for k in self.durations:
            self.durations[k] *= 60

    def reload_settings(self):
        """Call after settings change."""
        was_running = self.running
        self.stop()
        self._load_durations()
        self.mode = "focus"
        self.remaining = self.durations[self.mode]
        self.completed = 0
        self._update_display()
        self._update_dots()
        self._update_tabs()
        self.ring.set_ring_bg(QColor(self._ring_bg_hex()))
        self.ring.set_label(self.LABELS[self.mode])
        if was_running:
            self.start()

    @property
    def _dark(self):
        w = self.window()
        return getattr(w, '_is_dark', False)

    def _ring_bg_hex(self):
        return DARK["ring_bg"] if self._dark else LIGHT["ring_bg"]

    def _ring_color(self):
        dark_prefix = "0a84ff" if self._dark else "007aff"
        if self.mode == "focus":
            return "#0a84ff" if self._dark else "#007aff"
        elif self.mode == "shortBreak":
            return "#30d158" if self._dark else "#34c759"
        else:
            return "#ff9f0a" if self._dark else "#ff9500"

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(28)

        # ── Mode tabs ──
        tabs_widget = QWidget()
        tabs_layout = QHBoxLayout(tabs_widget)
        tabs_layout.setContentsMargins(0, 0, 0, 0)
        tabs_layout.setSpacing(0)
        self.tab_group = QButtonGroup(self)
        self.tab_btns = {}
        for key, label in [("focus", "专注"), ("shortBreak", "短休息"), ("longBreak", "长休息")]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setObjectName(f"tab_{key}")
            btn.clicked.connect(lambda checked, k=key: self._switch_mode(k))
            self.tab_btns[key] = btn
            self.tab_group.addButton(btn)
            tabs_layout.addWidget(btn)
        tabs_widget.setObjectName("tabsContainer")
        layout.addWidget(tabs_widget, alignment=Qt.AlignCenter)

        # ── Circular progress ──
        self.ring = CircularProgress()
        self.ring.setFixedSize(300, 300)
        self.ring.set_ring_bg(QColor(self._ring_bg_hex()))
        layout.addWidget(self.ring, alignment=Qt.AlignCenter)

        # ── Control buttons ──
        ctrl = QWidget()
        ctrl_layout = QHBoxLayout(ctrl)
        ctrl_layout.setContentsMargins(0, 0, 0, 0)
        ctrl_layout.setSpacing(20)

        self.btn_reset = QPushButton("↺")
        self.btn_reset.setObjectName("ctrlBtn")
        self.btn_reset.setToolTip("重置")
        self.btn_reset.clicked.connect(self.reset)
        ctrl_layout.addWidget(self.btn_reset)

        self.btn_play = QPushButton("▶")
        self.btn_play.setObjectName("playBtn")
        self.btn_play.clicked.connect(self._toggle)
        ctrl_layout.addWidget(self.btn_play)

        self.btn_skip = QPushButton("⏭")
        self.btn_skip.setObjectName("ctrlBtn")
        self.btn_skip.setToolTip("跳过")
        self.btn_skip.clicked.connect(self.skip)
        ctrl_layout.addWidget(self.btn_skip)

        layout.addWidget(ctrl, alignment=Qt.AlignCenter)

        # ── Session dots ──
        dots_widget = QWidget()
        dots_layout = QHBoxLayout(dots_widget)
        dots_layout.setContentsMargins(0, 0, 0, 0)
        dots_layout.setSpacing(10)
        self.dots = []
        for i in range(4):
            dot = QFrame()
            dot.setFixedSize(10, 10)
            dot.setObjectName("dot")
            self.dots.append(dot)
            dots_layout.addWidget(dot)
        layout.addWidget(dots_widget, alignment=Qt.AlignCenter)

        self._update_display()
        self._update_dots()
        self._update_tabs()

    def _switch_mode(self, new_mode: str):
        self.stop()
        self.mode = new_mode
        self.remaining = self.durations[self.mode]
        self.ring.set_label(self.LABELS[self.mode])
        self._update_display()
        self._update_dots()
        self._update_tabs()

    def _update_tabs(self):
        for key, btn in self.tab_btns.items():
            btn.setChecked(key == self.mode)

    def _toggle(self):
        if self.running:
            self.stop()
        else:
            self.start()

    def start(self):
        if self.running:
            return
        self.running = True
        self._tick_start = self._current_time_ms()
        self._tick_target = self.remaining
        self._tick_timer.start()
        self.btn_play.setText("⏸")
        self.ring.set_label(self.LABELS[self.mode])

    def stop(self):
        if not self.running:
            return
        self.running = False
        self._tick_timer.stop()
        elapsed = (self._current_time_ms() - self._tick_start) / 1000
        self.remaining = max(0, round(self._tick_target - elapsed))
        self._update_display()
        self.btn_play.setText("▶")

    def reset(self):
        self.stop()
        self.mode = "focus"
        self.remaining = self.durations[self.mode]
        self.completed = 0
        self.ring.set_label(self.LABELS[self.mode])
        self._update_display()
        self._update_dots()
        self._update_tabs()

    def skip(self):
        self.stop()
        if self.mode == "focus":
            self._switch_mode("shortBreak")
        else:
            self._switch_mode("focus")
            self.completed = 0
            self._update_dots()

    def _tick(self):
        if not self.running:
            return
        elapsed = (self._current_time_ms() - self._tick_start) / 1000
        remaining_float = max(0.0, self._tick_target - elapsed)
        new_remaining = math.ceil(remaining_float)

        if new_remaining != self.remaining:
            self.remaining = new_remaining
            self._update_display()
            if self.remaining <= 0:
                self._finish()

    def _finish(self):
        self.stop()
        vol = int(self.settings.value("alarm_volume", 80))
        play_chime(vol)

        if self.mode == "focus":
            self.completed = min(self.completed + 1, 4)
            self._update_dots()
            if self.completed >= 4:
                self.completed = 0
                self._switch_mode("longBreak")
            else:
                self._switch_mode("shortBreak")
        else:
            self._switch_mode("focus")

        # Auto-start next
        auto = self.settings.value("auto_start", "true")
        if auto != "false":
            QTimer.singleShot(1000, self.start)

    def _update_display(self):
        m = self.remaining // 60
        s = self.remaining % 60
        text = f"{m:02d}:{s:02d}"
        self.ring.set_text(text)
        progress = 1.0 - (self.remaining / self.durations[self.mode]) if self.durations[self.mode] > 0 else 0.0
        self.ring.set_progress(progress)
        self.ring.set_ring_color(QColor(self._ring_color()))
        color_label = "🔴专注" if self.mode == "focus" else ("🟢休息" if self.mode == "shortBreak" else "🟠长休息")
        self.window().setWindowTitle(f"{text} – {self.LABELS[self.mode]}")

    def _update_dots(self):
        for i, dot in enumerate(self.dots):
            dot.setProperty("state", "")
            if i < self.completed:
                dot.setProperty("state", "done")
            elif self.mode == "focus" and i == self.completed:
                dot.setProperty("state", "current")
            dot.style().unpolish(dot)
            dot.style().polish(dot)

    @staticmethod
    def _current_time_ms():
        return _perf_counter()


# ── iOS-style Toggle Switch ─────────────────────────────────────────────────
class ToggleSwitch(QPushButton):
    """Custom iOS-style toggle switch with sliding knob."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(48, 28)
        self._anim = QPropertyAnimation(self, b"knob_offset")
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)
        self._knob_offset = 2.0
        self._anim.valueChanged.connect(self.update)

    def knob_offset(self):
        return self._knob_offset
    def setKnobOffset(self, v):
        self._knob_offset = v

    knob_offset_p = QtCore_Property(float, knob_offset, setKnobOffset)

    def setChecked(self, checked):
        super().setChecked(checked)
        self._anim.setEndValue(22.0 if checked else 2.0)
        self._anim.start()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        is_dark = _is_widget_dark(self)
        w, h = self.width(), self.height()

        # Track
        track_color = QColor("#34c759") if self.isChecked() else QColor(
            "#3a3a3c" if is_dark else "#e5e5ea"
        )
        p.setPen(Qt.NoPen)
        p.setBrush(track_color)
        p.drawRoundedRect(QRectF(0, 0, w, h), h / 2, h / 2)

        # Knob
        p.setBrush(QColor("#ffffff"))
        knob_r = (h - 5) / 2
        p.drawEllipse(QPointF(self._knob_offset + knob_r + 1.5, h / 2), knob_r, knob_r)
        p.end()


# ── Settings Page ──────────────────────────────────────────────────────────
class SettingsPage(QWidget):
    """Settings panel: theme, durations, alarm, auto-start."""

    theme_changed = Signal(str)
    setting_changed = Signal()

    def __init__(self, settings: QSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(24)

        title = QLabel("设置")
        title.setObjectName("settingsTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # ── Theme ──
        layout.addWidget(self._section_label("外观主题"))

        theme_widget = QWidget()
        theme_widget.setObjectName("rowCard")
        theme_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        theme_layout = QHBoxLayout(theme_widget)
        theme_layout.setContentsMargins(18, 12, 18, 12)
        theme_layout.setSpacing(6)
        self.theme_group = QButtonGroup(self)
        theme_opts = [("light", "浅色"), ("dark", "深色"), ("system", "跟随系统")]
        self.theme_btns = {}
        for key, label in theme_opts:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setObjectName("segBtn")
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda checked, k=key: self._set_theme(k))
            self.theme_btns[key] = btn
            self.theme_group.addButton(btn)
            theme_layout.addWidget(btn)
        current = self.settings.value("theme", "system")
        if current in self.theme_btns:
            self.theme_btns[current].setChecked(True)
        layout.addWidget(theme_widget)

        # ── Durations ──
        layout.addWidget(self._section_label("时长设置（分钟）"))

        self.spins = {}
        for key, label, default in [
            ("duration_focus", "专注时长", 25),
            ("duration_short", "短休息时长", 5),
            ("duration_long", "长休息时长", 15),
        ]:
            row = QWidget()
            row.setObjectName("rowCard")
            row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(18, 8, 18, 8)
            lbl = QLabel(label)
            lbl.setObjectName("rowLabel")
            row_layout.addWidget(lbl)
            row_layout.addStretch()
            spin = QSpinBox()
            spin.setObjectName("durationSpin")
            spin.setRange(1, 120)
            spin.setValue(int(self.settings.value(key, default)))
            spin.valueChanged.connect(lambda v, k=key: self.settings.setValue(k, v))
            spin.valueChanged.connect(lambda: self.setting_changed.emit())
            self.spins[key] = spin
            row_layout.addWidget(spin)
            layout.addWidget(row)

        # ── Alarm volume ──
        layout.addWidget(self._section_label("提醒音量"))

        vol_row = QWidget()
        vol_row.setObjectName("rowCard")
        vol_row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        vol_layout = QHBoxLayout(vol_row)
        vol_layout.setContentsMargins(18, 12, 18, 12)
        vol_layout.addWidget(QLabel("🔈"))
        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setObjectName("volSlider")
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(int(self.settings.value("alarm_volume", 80)))
        self.vol_slider.valueChanged.connect(
            lambda v: self.settings.setValue("alarm_volume", v)
        )
        vol_layout.addWidget(self.vol_slider, 1)
        vol_layout.addWidget(QLabel("🔊"))
        layout.addWidget(vol_row)

        # Test sound button
        test_btn = QPushButton("试听铃声")
        test_btn.setObjectName("testSoundBtn")
        test_btn.clicked.connect(lambda: play_chime(
            int(self.settings.value("alarm_volume", 80))
        ))
        layout.addWidget(test_btn, alignment=Qt.AlignCenter)

        # ── Auto-start toggle ──
        auto_row = QWidget()
        auto_row.setObjectName("rowCard")
        auto_row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        auto_layout = QHBoxLayout(auto_row)
        auto_layout.setContentsMargins(18, 12, 18, 12)
        auto_layout.addWidget(QLabel("完成后自动开始下一轮"))
        auto_layout.addStretch()
        self.auto_btn = ToggleSwitch()
        auto_val = self.settings.value("auto_start", "true")
        self.auto_btn.setChecked(auto_val != "false")
        self.auto_btn.toggled.connect(
            lambda on: self.settings.setValue("auto_start", "true" if on else "false")
        )
        self.auto_btn.clicked.connect(lambda: self.setting_changed.emit())
        auto_layout.addWidget(self.auto_btn)
        layout.addWidget(auto_row)

        layout.addStretch()

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("sectionLabel")
        return lbl

    def _set_theme(self, theme: str):
        self.settings.setValue("theme", theme)
        self.theme_changed.emit(theme)

    @staticmethod
    def _label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("rowLabel")
        return lbl


# ── Main Window ────────────────────────────────────────────────────────────
class PomodoroWindow(QMainWindow):
    """Main window: navigation bar, stacked pages."""

    def __init__(self):
        super().__init__()
        self.settings = QSettings("Pomodoro", "PomodoroApp")
        self._is_dark = False
        self._current_theme = self.settings.value("theme", "system")

        self.setWindowTitle("番茄钟")
        self.setMinimumSize(440, 640)
        self.resize(500, 700)

        # Central widget
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 20, 24, 28)
        root.setSpacing(16)

        # ── Nav bar ──
        nav = QWidget()
        nav.setObjectName("navBar")
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(4, 4, 4, 4)
        nav_layout.setSpacing(4)

        self.btn_timer = QPushButton("⏱  计时")
        self.btn_timer.setCheckable(True)
        self.btn_timer.setObjectName("navBtn")
        self.btn_timer.clicked.connect(lambda: self._switch_page(0))

        self.btn_settings = QPushButton("⚙  设置")
        self.btn_settings.setCheckable(True)
        self.btn_settings.setObjectName("navBtn")
        self.btn_settings.clicked.connect(lambda: self._switch_page(1))

        self.nav_group = QButtonGroup(self)
        self.nav_group.addButton(self.btn_timer)
        self.nav_group.addButton(self.btn_settings)
        self.btn_timer.setChecked(True)

        nav_layout.addWidget(self.btn_timer)
        nav_layout.addWidget(self.btn_settings)
        nav_layout.addStretch()
        root.addWidget(nav)

        # ── Stacked pages ──
        self.stack = QStackedWidget()
        self.timer_page = TimerPage(self.settings)
        self.settings_page = SettingsPage(self.settings)

        # Timer page: direct card wrap
        self.timer_card = self._wrap_card(self.timer_page)

        # Settings page: scroll area inside card
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.settings_page)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setObjectName("settingsScroll")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.settings_card = self._wrap_card(scroll)

        self.stack.addWidget(self.timer_card)
        self.stack.addWidget(self.settings_card)
        root.addWidget(self.stack, 1)

        # ── Bottom hint ──
        hint = QLabel("按 空格键 开始 / 暂停")
        hint.setObjectName("hintLabel")
        hint.setAlignment(Qt.AlignCenter)
        root.addWidget(hint)

        # Connections
        self.settings_page.theme_changed.connect(self._apply_theme)
        self.settings_page.setting_changed.connect(self.timer_page.reload_settings)

        # Apply theme
        self._apply_theme(self._current_theme)

    def _wrap_card(self, widget: QWidget) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 28, 24, 28)
        layout.addWidget(widget)
        return card

    def _switch_page(self, index: int):
        self.stack.setCurrentIndex(index)

    def _apply_theme(self, theme: str):
        self._current_theme = theme

        if theme == "system":
            dark = _is_system_dark()
        else:
            dark = (theme == "dark")

        self._is_dark = dark
        palette = DARK if dark else LIGHT

        # Build gradient colors for glass-morphism effect
        if dark:
            bg_color = "#000000"
            glass_top = "rgba(44,44,46,0.92)"
            glass_bot = "rgba(30,30,32,0.6)"
            nav_glass_top = "rgba(44,44,46,0.88)"
            nav_glass_bot = "rgba(30,30,32,0.58)"
        else:
            bg_color = "#f0f0f5"
            glass_top = "rgba(255,255,255,0.94)"
            glass_bot = "rgba(245,245,250,0.55)"
            nav_glass_top = "rgba(255,255,255,0.9)"
            nav_glass_bot = "rgba(245,245,250,0.5)"

        # Build QSS
        qss = f"""
        /* ── Global ── */
        QMainWindow {{
            background-color: {palette["bg"]};
        }}
        QWidget#centralWidget {{
            background-color: {palette["bg"]};
        }}

        /* ── Card (frosted glass via gradient + transparency) ── */
        QFrame#card {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {glass_top}, stop:1 {glass_bot});
            border-radius: 20px;
            border: 1px solid {palette["sep"]};
        }}

        /* ── Nav Bar ── */
        QWidget#navBar {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {nav_glass_top}, stop:1 {nav_glass_bot});
            border-radius: 12px;
            border: 1px solid {palette["sep"]};
        }}
        QPushButton#navBtn {{
            background: transparent;
            border: none;
            border-radius: 8px;
            padding: 9px 20px;
            color: {palette["text_sec"]};
            font-size: 15px;
            font-weight: 500;
        }}
        QPushButton#navBtn:hover {{
            background-color: {palette["btn_hover"]};
        }}
        QPushButton#navBtn:checked {{
            background-color: {palette["tab_active"]};
            color: {palette["text"]};
        }}

        /* ── Mode Tabs (timer page) ── */
        QWidget#tabsContainer {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {glass_top}, stop:1 {glass_bot});
            border-radius: 10px;
            border: 1px solid {palette["sep"]};
            padding: 3px;
        }}
        QPushButton[id^="tab_"] {{
            background: transparent;
            border: none;
            border-radius: 7px;
            padding: 8px 18px;
            color: {palette["text_sec"]};
            font-size: 15px;
            font-weight: 500;
        }}
        QPushButton[id^="tab_"]:hover {{
            color: {palette["text"]};
        }}
        QPushButton[id^="tab_"]:checked {{
            background-color: {palette["tab_active"]};
            color: {palette["text"]};
        }}

        /* ── Control Buttons ── */
        QPushButton#ctrlBtn {{
            background-color: {palette["btn_bg"]};
            border: none;
            border-radius: 22px;
            min-width: 44px;
            max-width: 44px;
            min-height: 44px;
            max-height: 44px;
            color: {palette["text"]};
            font-size: 20px;
        }}
        QPushButton#ctrlBtn:hover {{
            background-color: {palette["btn_hover"]};
        }}
        QPushButton#ctrlBtn:pressed {{
            background-color: {palette["btn_hover"]};
        }}

        QPushButton#playBtn {{
            background-color: {palette["blue"]};
            border: none;
            border-radius: 32px;
            min-width: 64px;
            max-width: 64px;
            min-height: 64px;
            max-height: 64px;
            color: white;
            font-size: 26px;
        }}
        QPushButton#playBtn:hover {{
            background-color: {palette["blue"]};
        }}

        /* ── Session Dots ── */
        QFrame#dot {{
            background-color: {palette["sep"]};
            border-radius: 5px;
            min-width: 10px;
            max-width: 10px;
            min-height: 10px;
            max-height: 10px;
            border: none;
        }}
        QFrame#dot[state="done"] {{
            background-color: {palette["red"]};
        }}
        QFrame#dot[state="current"] {{
            background-color: {palette["orange"]};
            border: 3px solid {QColor(palette["orange"]).lighter(140).name()};
        }}

        /* ── Hint ── */
        QLabel#hintLabel {{
            color: {palette["text_sec"]};
            font-size: 12px;
            font-weight: 400;
        }}

        /* ── Settings ── */
        QLabel#settingsTitle {{
            color: {palette["text"]};
            font-size: 28px;
            font-weight: 700;
        }}
        QLabel#sectionLabel {{
            color: {palette["text_sec"]};
            font-size: 13px;
            font-weight: 600;
            letter-spacing: 0.5px;
            padding-left: 6px;
        }}
        QWidget#rowCard {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {glass_top}, stop:1 {glass_bot});
            border-radius: 12px;
            border: 1px solid {palette["sep"]};
        }}
        QLabel#rowLabel {{
            color: {palette["text"]};
            font-size: 15px;
            font-weight: 400;
        }}

        /* ── Segmented buttons (theme) ── */
        QPushButton#segBtn {{
            background: transparent;
            border: none;
            border-radius: 7px;
            padding: 7px 14px;
            color: {palette["text_sec"]};
            font-size: 14px;
            font-weight: 500;
        }}
        QPushButton#segBtn:hover {{
            color: {palette["text"]};
        }}
        QPushButton#segBtn:checked {{
            background-color: {palette["tab_active"]};
            color: {palette["text"]};
        }}

        /* ── Test Sound Button ── */
        QPushButton#testSoundBtn {{
            background-color: {palette["btn_bg"]};
            border: none;
            border-radius: 10px;
            padding: 10px 24px;
            color: {palette["blue"]};
            font-size: 14px;
            font-weight: 500;
        }}
        QPushButton#testSoundBtn:hover {{
            background-color: {palette["btn_hover"]};
        }}

        /* ── SpinBox ── */
        QSpinBox#durationSpin {{
            background-color: {palette["input_bg"]};
            border: 1px solid {palette["sep"]};
            border-radius: 8px;
            padding: 5px 10px;
            color: {palette["text"]};
            font-size: 15px;
            min-width: 72px;
        }}
        QSpinBox#durationSpin:focus {{
            border-color: {palette["blue"]};
        }}

        /* ── Slider ── */
        QSlider#volSlider::groove:horizontal {{
            background: {palette["slider_groove"]};
            height: 6px;
            border-radius: 3px;
        }}
        QSlider#volSlider::handle:horizontal {{
            background: {palette["blue"]};
            width: 20px;
            height: 20px;
            margin: -7px 0;
            border-radius: 10px;
        }}
        QSlider#volSlider::sub-page:horizontal {{
            background: {palette["blue"]};
            border-radius: 3px;
        }}

        /* ── Scroll Area (settings) ── */
        QScrollArea#settingsScroll {{
            background: transparent;
            border: none;
        }}
        QScrollArea#settingsScroll > QWidget > QWidget {{
            background: transparent;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 6px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {palette["ring_bg"]};
            border-radius: 3px;
            min-height: 40px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {palette["text_sec"]};
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {{
            background: none;
        }}
        """

        self.setStyleSheet(qss)

        # Update ring colors on timer page
        self.timer_page.ring.set_ring_bg(
            QColor(DARK["ring_bg"] if dark else LIGHT["ring_bg"])
        )
        self.timer_page._update_display()
        self.timer_page._update_dots()

        # Update palette for custom-painted text colors
        app = QApplication.instance()
        if dark:
            app.setPalette(self._dark_palette())
        else:
            app.setPalette(self._light_palette())

    def _dark_palette(self):
        p = QPalette()
        p.setColor(QPalette.Window, QColor("#000000"))
        p.setColor(QPalette.WindowText, QColor("#f5f5f7"))
        p.setColor(QPalette.Base, QColor("#1c1c1e"))
        p.setColor(QPalette.Text, QColor("#f5f5f7"))
        p.setColor(QPalette.Button, QColor("#2c2c2e"))
        p.setColor(QPalette.ButtonText, QColor("#f5f5f7"))
        return p

    def _light_palette(self):
        p = QPalette()
        p.setColor(QPalette.Window, QColor("#f5f5f7"))
        p.setColor(QPalette.WindowText, QColor("#1d1d1f"))
        p.setColor(QPalette.Base, QColor("#ffffff"))
        p.setColor(QPalette.Text, QColor("#1d1d1f"))
        p.setColor(QPalette.Button, QColor("#f2f2f7"))
        p.setColor(QPalette.ButtonText, QColor("#1d1d1f"))
        return p

    def showEvent(self, event):
        super().showEvent(event)
        # Enable Windows acrylic blur behind window for true frosted glass
        if not hasattr(self, '_acrylic_applied'):
            self._acrylic_applied = True
            _enable_acrylic(int(self.winId()), self._is_dark)

    def event(self, event):
        """Intercept Space key before child widgets consume it."""
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Space and self.stack.currentIndex() == 0:
                if not event.isAutoRepeat():
                    self.timer_page._toggle()
                return True
        return super().event(event)


# ── Entry Point ────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("番茄钟")
    app.setOrganizationName("Pomodoro")

    # Font tweaks
    font = app.font()
    font.setFamilies([
        "-apple-system", "Segoe UI Variable", "Segoe UI",
        "PingFang SC", "Microsoft YaHei", "Helvetica Neue", "sans-serif",
    ])
    font.setPointSize(13)
    app.setFont(font)

    # Tomato icon
    pm = _create_tomato_pixmap(128)
    app_icon = QIcon(pm)
    app.setWindowIcon(app_icon)

    # Save ICO for PyInstaller bundling
    ico_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pomodoro.ico")
    try:
        _generate_ico(_create_tomato_pixmap(256), ico_path)
    except Exception:
        pass  # icon file is optional; window icon still works

    window = PomodoroWindow()
    window.setWindowIcon(app_icon)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
