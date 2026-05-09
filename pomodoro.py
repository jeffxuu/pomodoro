#!/usr/bin/env python3
"""Catime-inspired Pomodoro timer built with PySide6.

Run:    python pomodoro.py
Build:  pyinstaller --onefile --windowed --name Pomodoro --icon=pomodoro.ico pomodoro.py
"""

from __future__ import annotations

import atexit
import math
import os
import struct
import sys
import tempfile
import wave
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QPoint, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSpinBox,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)


APP_NAME = "番茄钟"
ORG_NAME = "Pomodoro"


@dataclass(frozen=True)
class Palette:
    """Theme tokens shared by the timer, settings dialog, and tray icon."""

    window: str
    panel: str
    panel_border: str
    text: str
    muted: str
    accent: str
    focus: str
    short_break: str
    long_break: str
    danger: str
    ring_bg: str
    button: str
    button_hover: str


LIGHT = Palette(
    window="#f6f3ee",
    panel="rgba(255, 255, 255, 214)",
    panel_border="rgba(32, 25, 20, 38)",
    text="#211c19",
    muted="#7d746d",
    accent="#ff6b3d",
    focus="#ff6b3d",
    short_break="#2bb673",
    long_break="#3b82f6",
    danger="#ff3b30",
    ring_bg="rgba(32, 25, 20, 30)",
    button="rgba(32, 25, 20, 18)",
    button_hover="rgba(32, 25, 20, 34)",
)

DARK = Palette(
    window="#10100f",
    panel="rgba(28, 27, 25, 220)",
    panel_border="rgba(255, 255, 255, 34)",
    text="#fbf7f0",
    muted="#aaa29a",
    accent="#ff8a5c",
    focus="#ff8a5c",
    short_break="#4ade80",
    long_break="#60a5fa",
    danger="#ff6b65",
    ring_bg="rgba(255, 255, 255, 32)",
    button="rgba(255, 255, 255, 22)",
    button_hover="rgba(255, 255, 255, 40)",
)


class Phase(str, Enum):
    """Pomodoro phase identifiers persisted in settings and used by menus."""

    FOCUS = "focus"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"


PHASE_LABELS = {
    Phase.FOCUS: "专注",
    Phase.SHORT_BREAK: "短休息",
    Phase.LONG_BREAK: "长休息",
}

PHASE_KEYS = {
    Phase.FOCUS: "duration_focus",
    Phase.SHORT_BREAK: "duration_short",
    Phase.LONG_BREAK: "duration_long",
}

PHASE_DEFAULTS = {
    Phase.FOCUS: 25,
    Phase.SHORT_BREAK: 5,
    Phase.LONG_BREAK: 15,
}

CHIME_PATH: str | None = None


def is_dark_mode() -> bool:
    """Detect system dark mode using Qt's active palette."""

    color = QApplication.palette().color(QPalette.Window)
    return color.lightness() < 128


def format_seconds(seconds: int) -> str:
    """Return M:SS for compact floating display."""

    seconds = max(0, int(seconds))
    minutes, secs = divmod(seconds, 60)
    return f"{minutes:02d}:{secs:02d}"


def generate_chime_wav() -> str:
    """Generate a small three-note WAV and return its temporary path."""

    sample_rate = 44100
    notes = (523.25, 659.25, 783.99)
    note_duration = 0.2
    total_duration = len(notes) * note_duration + 0.45
    samples: list[int] = []

    for i in range(int(sample_rate * total_duration)):
        t = i / sample_rate
        value = 0.0
        for index, freq in enumerate(notes):
            start = index * note_duration
            if t >= start:
                dt = t - start
                envelope = math.exp(-4.6 * dt)
                value += 0.26 * math.sin(2 * math.pi * freq * t) * envelope
        samples.append(int(max(-1.0, min(1.0, value)) * 32767))

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(struct.pack("<" + "h" * len(samples), *samples))
    return tmp.name


def play_chime() -> None:
    """Play the generated chime on Windows; silently no-op elsewhere."""

    global CHIME_PATH
    if CHIME_PATH is None:
        CHIME_PATH = generate_chime_wav()
    if sys.platform == "win32":
        import winsound

        winsound.PlaySound(CHIME_PATH, winsound.SND_FILENAME | winsound.SND_ASYNC)


def cleanup_chime() -> None:
    """Remove the generated temporary sound file."""

    if CHIME_PATH and os.path.exists(CHIME_PATH):
        os.unlink(CHIME_PATH)


atexit.register(cleanup_chime)


def tomato_pixmap(size: int = 128) -> QPixmap:
    """Paint a tomato icon that also works as the tray icon."""

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    margin = size * 0.1
    body_rect = pixmap.rect().adjusted(int(margin), int(size * 0.2), -int(margin), -int(margin * 0.6))
    gradient = QLinearGradient(body_rect.topLeft(), body_rect.bottomRight())
    gradient.setColorAt(0, QColor("#ff815f"))
    gradient.setColorAt(0.55, QColor("#f04d35"))
    gradient.setColorAt(1, QColor("#bd2b24"))
    painter.setBrush(gradient)
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(body_rect)

    highlight = body_rect.adjusted(
        int(body_rect.width() * 0.16),
        int(body_rect.height() * 0.08),
        -int(body_rect.width() * 0.42),
        -int(body_rect.height() * 0.5),
    )
    highlight_gradient = QLinearGradient(highlight.topLeft(), highlight.bottomRight())
    highlight_gradient.setColorAt(0, QColor(255, 255, 255, 130))
    highlight_gradient.setColorAt(1, QColor(255, 255, 255, 0))
    painter.setBrush(highlight_gradient)
    painter.drawEllipse(highlight)

    leaf = QPainterPath()
    center_x = size / 2
    stem_y = size * 0.23
    leaf.moveTo(center_x, stem_y)
    leaf.cubicTo(size * 0.26, size * 0.04, size * 0.28, size * 0.32, center_x, stem_y)
    leaf.cubicTo(size * 0.49, size * 0.0, size * 0.68, size * 0.08, center_x, stem_y)
    leaf.cubicTo(size * 0.74, size * 0.08, size * 0.67, size * 0.34, center_x, stem_y)
    painter.setBrush(QColor("#2fb55d"))
    painter.drawPath(leaf)

    painter.end()
    return pixmap


def save_ico(path: Path) -> None:
    """Persist an ICO beside the script for PyInstaller packaging."""

    tomato_pixmap(256).save(str(path), "ICO")


class TimerEngine(QWidget):
    """Small state machine that keeps timing logic separate from presentation."""

    changed = Signal()
    phase_finished = Signal(Phase)

    def __init__(self, settings: QSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.phase = Phase.FOCUS
        self.completed_focuses = int(settings.value("completed_focuses", 0))
        self.durations = self.load_durations()
        self.remaining = self.durations[self.phase]
        self.running = False
        self._target_remaining = self.remaining
        self._elapsed = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self.tick)

    def load_durations(self) -> dict[Phase, int]:
        return {
            phase: int(self.settings.value(PHASE_KEYS[phase], PHASE_DEFAULTS[phase])) * 60
            for phase in Phase
        }

    @property
    def total(self) -> int:
        return self.durations[self.phase]

    @property
    def progress(self) -> float:
        if self.total <= 0:
            return 1.0
        return 1 - (self.remaining / self.total)

    def toggle(self) -> None:
        if self.running:
            self.pause()
        else:
            self.start()

    def start(self) -> None:
        if self.remaining <= 0:
            self.remaining = self.total
        self.running = True
        self._target_remaining = self.remaining
        self._elapsed.restart()
        self._timer.start()
        self.changed.emit()

    def pause(self) -> None:
        self.running = False
        self._timer.stop()
        self.changed.emit()

    def reset(self) -> None:
        self.pause()
        self.remaining = self.total
        self.changed.emit()

    def skip(self) -> None:
        self.finish_phase(play_sound=False)

    def switch_phase(self, phase: Phase) -> None:
        self.pause()
        self.phase = phase
        self.remaining = self.total
        self.changed.emit()

    def apply_settings(self) -> None:
        was_running = self.running
        self.pause()
        self.durations = self.load_durations()
        self.remaining = min(self.remaining, self.total) if self.remaining else self.total
        self.changed.emit()
        if was_running:
            self.start()

    def tick(self) -> None:
        elapsed_seconds = self._elapsed.elapsed() / 1000
        next_remaining = max(0, math.ceil(self._target_remaining - elapsed_seconds))
        if next_remaining != self.remaining:
            self.remaining = next_remaining
            self.changed.emit()
        if self.remaining <= 0:
            self.finish_phase(play_sound=True)

    def finish_phase(self, play_sound: bool) -> None:
        finished_phase = self.phase
        self.pause()
        if play_sound:
            play_chime()
        if finished_phase == Phase.FOCUS:
            self.completed_focuses = (self.completed_focuses + 1) % 4
            self.settings.setValue("completed_focuses", self.completed_focuses)
            self.phase = Phase.LONG_BREAK if self.completed_focuses == 0 else Phase.SHORT_BREAK
        else:
            self.phase = Phase.FOCUS
        self.remaining = self.total
        self.changed.emit()
        self.phase_finished.emit(finished_phase)
        if self.settings.value("auto_start", "false") == "true":
            self.start()


class RingWidget(QWidget):
    """Transparent Catime-like countdown surface with a thin progress halo."""

    def __init__(self, engine: TimerEngine, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.engine = engine
        self.palette_tokens = DARK
        self.setMinimumSize(290, 150)

    def set_tokens(self, tokens: Palette) -> None:
        self.palette_tokens = tokens
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(6, 6, -6, -6)
        bg = QColor(self.palette_tokens.panel)
        painter.setBrush(bg)
        painter.setPen(QPen(QColor(self.palette_tokens.panel_border), 1.2))
        painter.drawRoundedRect(rect, 28, 28)

        ring_rect = rect.adjusted(18, 18, -18, -18)
        pen = QPen(QColor(self.palette_tokens.ring_bg), 5)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(ring_rect, 90 * 16, -360 * 16)

        phase_color = self.phase_color()
        pen.setColor(QColor(phase_color))
        painter.setPen(pen)
        painter.drawArc(ring_rect, 90 * 16, int(-360 * self.engine.progress * 16))

        painter.setPen(QColor(self.palette_tokens.text))
        time_font = QFont()
        time_font.setFamilies(["Segoe UI Variable", "SF Pro Display", "PingFang SC", "Microsoft YaHei", "Arial"])
        time_font.setPixelSize(56)
        time_font.setWeight(QFont.Weight.Light)
        time_font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 102)
        painter.setFont(time_font)
        painter.drawText(rect.adjusted(0, 14, 0, -30), Qt.AlignCenter, format_seconds(self.engine.remaining))

        painter.setPen(QColor(self.palette_tokens.muted))
        label_font = QFont()
        label_font.setFamilies(["Segoe UI", "PingFang SC", "Microsoft YaHei", "Arial"])
        label_font.setPixelSize(13)
        label_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(label_font)
        state = "运行中" if self.engine.running else "已暂停"
        painter.drawText(rect.adjusted(0, 78, 0, -18), Qt.AlignCenter, f"{PHASE_LABELS[self.engine.phase]} · {state}")

    def phase_color(self) -> str:
        if self.engine.phase == Phase.SHORT_BREAK:
            return self.palette_tokens.short_break
        if self.engine.phase == Phase.LONG_BREAK:
            return self.palette_tokens.long_break
        return self.palette_tokens.focus


class SettingsDialog(QDialog):
    """Compact settings dialog for durations and automation behavior."""

    settings_changed = Signal()

    def __init__(self, settings: QSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("设置")
        self.setModal(True)
        self.setMinimumWidth(340)
        self.spins: dict[Phase, QSpinBox] = {}
        self.auto_start = QCheckBox("阶段结束后自动开始下一段")
        self.always_on_top = QCheckBox("窗口始终置顶")
        self.click_through = QCheckBox("专注模式：鼠标穿透")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        title = QLabel("番茄钟设置")
        title.setObjectName("settingsTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        for row, phase in enumerate(Phase):
            label = QLabel(PHASE_LABELS[phase])
            spin = QSpinBox()
            spin.setRange(1, 180)
            spin.setSuffix(" 分钟")
            spin.setValue(int(self.settings.value(PHASE_KEYS[phase], PHASE_DEFAULTS[phase])))
            self.spins[phase] = spin
            grid.addWidget(label, row, 0)
            grid.addWidget(spin, row, 1)
        layout.addLayout(grid)

        self.auto_start.setChecked(self.settings.value("auto_start", "false") == "true")
        self.always_on_top.setChecked(self.settings.value("always_on_top", "true") == "true")
        self.click_through.setChecked(self.settings.value("click_through", "false") == "true")
        layout.addWidget(self.auto_start)
        layout.addWidget(self.always_on_top)
        layout.addWidget(self.click_through)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save(self) -> None:
        for phase, spin in self.spins.items():
            self.settings.setValue(PHASE_KEYS[phase], spin.value())
        self.settings.setValue("auto_start", "true" if self.auto_start.isChecked() else "false")
        self.settings.setValue("always_on_top", "true" if self.always_on_top.isChecked() else "false")
        self.settings.setValue("click_through", "true" if self.click_through.isChecked() else "false")
        self.settings_changed.emit()
        self.accept()


class TimerWindow(QWidget):
    """Frameless floating window modeled after Catime's unobtrusive timer."""

    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings(ORG_NAME, "PomodoroApp")
        self.engine = TimerEngine(self.settings, self)
        self.tokens = DARK if is_dark_mode() else LIGHT
        self.drag_position = QPoint()
        self.tray: QSystemTrayIcon | None = None
        self.phase_buttons: dict[Phase, QPushButton] = {}

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(tomato_pixmap(128)))
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(330, 230)
        self.resize(360, 250)
        self._build_ui()
        self._build_tray()
        self._build_shortcuts()
        self.apply_settings()
        self.engine.changed.connect(self.refresh)
        self.engine.phase_finished.connect(self.on_phase_finished)
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        top = QHBoxLayout()
        self.status = QLabel("Catime 风格 · 轻量浮窗")
        self.status.setObjectName("statusLabel")
        top.addWidget(self.status)
        top.addStretch()
        self.pin_button = QPushButton("置顶")
        self.pin_button.setObjectName("miniButton")
        self.pin_button.setCheckable(True)
        self.pin_button.clicked.connect(self.toggle_always_on_top)
        top.addWidget(self.pin_button)
        root.addLayout(top)

        self.ring = RingWidget(self.engine)
        root.addWidget(self.ring, 1)

        phases = QHBoxLayout()
        phases.setSpacing(8)
        for phase in Phase:
            button = QPushButton(PHASE_LABELS[phase])
            button.setObjectName("phaseButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, selected=phase: self.engine.switch_phase(selected))
            self.phase_buttons[phase] = button
            phases.addWidget(button)
        root.addLayout(phases)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        self.reset_button = QPushButton("重置")
        self.reset_button.setObjectName("controlButton")
        self.reset_button.clicked.connect(self.engine.reset)
        controls.addWidget(self.reset_button)

        self.play_button = QPushButton("开始")
        self.play_button.setObjectName("playButton")
        self.play_button.clicked.connect(self.engine.toggle)
        controls.addWidget(self.play_button, 1)

        self.skip_button = QPushButton("跳过")
        self.skip_button.setObjectName("controlButton")
        self.skip_button.clicked.connect(self.engine.skip)
        controls.addWidget(self.skip_button)
        root.addLayout(controls)

        footer = QHBoxLayout()
        self.progress_label = QLabel("0 / 4")
        self.progress_label.setObjectName("progressLabel")
        footer.addWidget(self.progress_label)
        footer.addStretch()
        settings_button = QPushButton("设置")
        settings_button.setObjectName("miniButton")
        settings_button.clicked.connect(self.open_settings)
        footer.addWidget(settings_button)
        quit_button = QPushButton("退出")
        quit_button.setObjectName("miniButton")
        quit_button.clicked.connect(QApplication.quit)
        footer.addWidget(quit_button)
        root.addLayout(footer)

    def _build_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        menu = QMenu(self)
        toggle_action = QAction("开始 / 暂停", self)
        toggle_action.triggered.connect(self.engine.toggle)
        reset_action = QAction("重置", self)
        reset_action.triggered.connect(self.engine.reset)
        settings_action = QAction("设置", self)
        settings_action.triggered.connect(self.open_settings)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(toggle_action)
        menu.addAction(reset_action)
        menu.addSeparator()
        menu.addAction(settings_action)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

    def _build_shortcuts(self) -> None:
        QShortcut(QKeySequence("Space"), self, activated=self.engine.toggle)
        QShortcut(QKeySequence("R"), self, activated=self.engine.reset)
        QShortcut(QKeySequence("S"), self, activated=self.engine.skip)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=self.open_settings)
        QShortcut(QKeySequence("Esc"), self, activated=self.hide)

    def apply_settings(self) -> None:
        flags = Qt.FramelessWindowHint | Qt.Tool
        if self.settings.value("always_on_top", "true") == "true":
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setWindowOpacity(float(self.settings.value("window_opacity", 0.96)))
        self.setAttribute(Qt.WA_TransparentForMouseEvents, self.settings.value("click_through", "false") == "true")
        self.pin_button.setChecked(self.settings.value("always_on_top", "true") == "true")
        self.engine.apply_settings()
        self.apply_theme()
        self.show()

    def apply_theme(self) -> None:
        self.tokens = DARK if is_dark_mode() else LIGHT
        self.ring.set_tokens(self.tokens)
        self.setStyleSheet(
            f"""
            QWidget {{
                color: {self.tokens.text};
                font-family: 'Segoe UI', 'PingFang SC', 'Microsoft YaHei';
                font-size: 13px;
            }}
            QLabel#statusLabel, QLabel#progressLabel {{
                color: {self.tokens.muted};
                font-weight: 600;
            }}
            QPushButton {{
                border: 1px solid {self.tokens.panel_border};
                border-radius: 13px;
                padding: 8px 12px;
                background: {self.tokens.button};
                color: {self.tokens.text};
                font-weight: 700;
            }}
            QPushButton:hover {{ background: {self.tokens.button_hover}; }}
            QPushButton#playButton {{
                min-height: 42px;
                border-radius: 21px;
                background: {self.tokens.accent};
                color: white;
                border: none;
                font-size: 16px;
            }}
            QPushButton#controlButton {{ min-height: 38px; }}
            QPushButton#miniButton {{
                padding: 6px 10px;
                border-radius: 11px;
                color: {self.tokens.muted};
            }}
            QPushButton#miniButton:checked, QPushButton#phaseButton:checked {{
                background: {self.tokens.accent};
                color: white;
                border: none;
            }}
            QPushButton#phaseButton {{
                padding: 7px 10px;
                border-radius: 12px;
            }}
            QDialog {{ background: {self.tokens.window}; }}
            QLabel#settingsTitle {{ font-size: 19px; font-weight: 800; }}
            QSpinBox {{
                border: 1px solid {self.tokens.panel_border};
                border-radius: 9px;
                padding: 6px 10px;
                background: {self.tokens.button};
                color: {self.tokens.text};
            }}
            QCheckBox {{ color: {self.tokens.text}; padding: 4px 0; }}
            """
        )

    def refresh(self) -> None:
        self.ring.update()
        self.play_button.setText("暂停" if self.engine.running else "开始")
        for phase, button in self.phase_buttons.items():
            button.setChecked(phase == self.engine.phase)
        self.progress_label.setText(f"本轮番茄：{self.engine.completed_focuses} / 4")
        self.status.setText("空格开始/暂停 · R 重置 · S 跳过")
        title = f"{format_seconds(self.engine.remaining)} · {PHASE_LABELS[self.engine.phase]}"
        self.setWindowTitle(title)
        if self.tray:
            self.tray.setToolTip(title)

    def toggle_always_on_top(self) -> None:
        self.settings.setValue("always_on_top", "true" if self.pin_button.isChecked() else "false")
        self.apply_settings()

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        dialog.setStyleSheet(self.styleSheet())
        dialog.settings_changed.connect(self.apply_settings)
        dialog.exec()

    def on_phase_finished(self, phase: Phase) -> None:
        if self.tray:
            next_phase = PHASE_LABELS[self.engine.phase]
            self.tray.showMessage(APP_NAME, f"{PHASE_LABELS[phase]}结束，下一段：{next_phase}", self.windowIcon(), 3500)

    def on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.setVisible(not self.isVisible())

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        if event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        if self.tray and self.tray.isVisible():
            self.hide()
            event.ignore()
        else:
            event.accept()


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setQuitOnLastWindowClosed(False)

    font = app.font()
    font.setFamilies(["Segoe UI Variable", "Segoe UI", "PingFang SC", "Microsoft YaHei", "Arial"])
    font.setPointSize(11)
    app.setFont(font)

    icon = QIcon(tomato_pixmap(128))
    app.setWindowIcon(icon)
    ico_path = Path(__file__).with_name("pomodoro.ico")
    if not ico_path.exists():
        save_ico(ico_path)

    window = TimerWindow()
    window.setWindowIcon(icon)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
