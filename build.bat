@echo off
chcp 65001 >nul
echo ========================================
echo   番茄钟 Pomodoro - 打包为 EXE
echo ========================================
echo.

:: Check Python
set "PYTHON=python"
%PYTHON% --version >nul 2>&1
if errorlevel 1 (
    set "PYTHON=py -3.12"
    %PYTHON% --version >nul 2>&1
)
if errorlevel 1 (
    set "PYTHON="%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" -3.12"
    %PYTHON% --version >nul 2>&1
)
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+，或把 Python 加入 PATH
    pause
    exit /b 1
)

:: Install dependencies
echo [1/3] 安装依赖...
%PYTHON% -m pip install -U pip
if errorlevel 1 (
    echo [错误] pip 更新失败
    pause
    exit /b 1
)
%PYTHON% -m pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)

:: Build
echo [2/3] 打包中（约 1-2 分钟）...
if exist pomodoro.ico (
    %PYTHON% -m PyInstaller --onefile --windowed --name Pomodoro --icon=pomodoro.ico --noconfirm pomodoro.py
) else (
    echo [提示] 未找到 pomodoro.ico，将使用默认 EXE 图标。
    %PYTHON% -m PyInstaller --onefile --windowed --name Pomodoro --noconfirm pomodoro.py
)
if errorlevel 1 (
    echo [错误] 打包失败
    pause
    exit /b 1
)

if not exist dist\Pomodoro.exe (
    echo [错误] 未找到 dist\Pomodoro.exe
    pause
    exit /b 1
)

:: Done
echo [3/3] 完成！
echo.
echo 可执行文件:  dist\Pomodoro.exe
echo 复制此文件到任意 Windows 电脑即可使用。
echo.
pause
