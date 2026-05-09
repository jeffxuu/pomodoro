# 🍅 番茄钟 Pomodoro

一个参考 [Catime](https://github.com/vladelaina/Catime) 交互思路重构的轻量番茄钟：窗口保持小而透明，悬浮在桌面角落即可随时查看，不再需要完整控制台式主界面。

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.5%2B-green)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-lightgrey)

## 功能

- **Catime 风格轻量浮窗** — 无边框、半透明、可拖拽、默认置顶，适合放在屏幕角落常驻。
- **三阶段番茄循环** — 专注 / 短休息 / 长休息，完成 4 个专注段后自动进入长休息。
- **精简状态机** — 计时逻辑与 UI 分离，使用 `QElapsedTimer` 修正普通 `QTimer` 的漂移。
- **托盘常驻** — 支持隐藏窗口后继续计时，可从托盘开始/暂停、重置、打开设置或退出。
- **快捷键控制** — 空格开始/暂停，`R` 重置，`S` 跳过，`Ctrl+,` 打开设置，`Esc` 隐藏。
- **可配置设置** — 调整三段时长、自动开始下一段、始终置顶、鼠标穿透专注模式。
- **程序化番茄图标** — 使用 `QPainter` 生成图标，保持打包时无需额外图片资源。
- **铃声提醒** — Windows 下使用临时生成的三音和弦 WAV，无外部音频文件依赖。

## 快捷键

| 按键 | 功能 |
|------|------|
| 空格 | 开始 / 暂停 |
| R | 重置当前阶段 |
| S | 跳过当前阶段 |
| Ctrl+, | 打开设置 |
| Esc | 隐藏到托盘 |

## 从源码运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行
python pomodoro.py
```

## 打包为 EXE

```bash
# 一键打包（Windows）
build.bat

# 或手动
pyinstaller --onefile --windowed --name Pomodoro --icon=pomodoro.ico pomodoro.py
```

## 项目结构

```
pomodoro/
├── pomodoro.py          # PySide6 桌面主程序
├── pomodoro.ico         # 番茄图标（缺失时运行后自动生成）
├── requirements.txt     # Python 依赖
├── build.bat            # 一键打包脚本
├── index.html           # 网页版（备选）
└── README.md
```

## 技术栈

- **PySide6** — Qt for Python，GUI 框架。
- **QPainter** — 自定义绘制番茄图标、半透明面板和进度环。
- **QSettings** — 持久化时长、自动开始、置顶与鼠标穿透配置。
- **QSystemTrayIcon** — 托盘常驻与阶段结束通知。
- **PyInstaller** — 单文件 EXE 打包。

## License

MIT
