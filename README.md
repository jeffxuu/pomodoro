# 🍅 番茄钟 Pomodoro

Apple 风格设计的番茄钟桌面应用，基于 PySide6 构建。

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.5%2B-green)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-lightgrey)

## 截图

<!-- TODO: 添加截图 -->

## 功能

- **三种模式** — 专注 (25min) / 短休息 (5min) / 长休息 (15min)，4 轮专注后自动切长休息
- **圆形进度环** — SVG 级抗锯齿，颜色随模式切换（蓝/绿/橙）
- **Windows 毛玻璃** — 调用 DWM Acrylic API，原生模糊效果
- **深色/浅色/跟随系统** — 三种主题，通过注册表自动检测 Windows 深色模式
- **自定义时长** — 设置页可调整三种时长（1-120 分钟）、提醒音量、自动开始
- **铃声提醒** — 三音和弦提示，无外部音频文件依赖
- **iOS 风格 Toggle** — 自定义 QPainter 绘制的滑动开关
- **番茄图标** — 程序化生成的矢量图标，窗口标题栏 + 任务栏 + EXE 文件全覆盖
- **单文件 EXE** — PyInstaller 打包，拷贝到任意 Windows 电脑直接运行

## 快捷键

| 按键 | 功能 |
|------|------|
| 空格 | 开始 / 暂停 |
| 重置 | 回到初始状态 |
| 跳过 | 跳过当前阶段 |

## 下载

前往 [Releases](https://github.com/jeffxuu/pomodoro/releases) 下载最新版 `Pomodoro.exe`。

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
├── pomodoro.py          # 主程序
├── pomodoro.ico         # 番茄图标（运行后自动生成）
├── requirements.txt     # Python 依赖
├── build.bat            # 一键打包脚本
├── index.html           # 网页版（备选）
├── dist/
│   └── Pomodoro.exe     # 打包好的可执行文件
└── README.md
```

## 技术栈

- **PySide6** — Qt for Python，GUI 框架
- **QSS** — Qt 样式表，实现 Apple 风格主题
- **QPainter** — 自定义绘制环形进度、Toggle 开关、番茄图标
- **Windows DWM** — `SetWindowCompositionAttribute` 启用 Acrylic 模糊
- **Web Audio API** — 网页版使用，无文件合成提示音
- **PyInstaller** — 单文件 EXE 打包

## License

MIT
