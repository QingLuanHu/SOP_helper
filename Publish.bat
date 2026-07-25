@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 设置 Python UTF-8 模式，避免路径编码问题
set PYTHONUTF8=1

echo ============================================================
echo   工位SOP助手 - 打包脚本（数据已内嵌混淆）
echo ============================================================
echo.

:: ---------- 获取日期 ----------
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set year=%datetime:~0,4%
set month=%datetime:~4,2%
set day=%datetime:~6,2%
set EXE_NAME=工位SOP助手-%year%-%month%-%day%

echo [信息] 输出文件名: %EXE_NAME%.exe
echo.

:: ---------- 检查 PyInstaller ----------
pip show PyInstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo [信息] 正在安装 PyInstaller ...
    pip install PyInstaller
    if %errorlevel% neq 0 (
        echo [错误] PyInstaller 安装失败，请手动执行: pip install PyInstaller
        pause
        exit /b 1
    )
)

:: ---------- 清理旧文件 ----------
if exist build rmdir /s /q build
if exist *.spec del /q *.spec

:: ---------- 显式指定 Qt 插件路径 ----------
set "QT_PLUGIN_PATH=%CD%\venv\Lib\site-packages\PyQt5\Qt5\plugins"

:: ---------- 执行打包（已移除 data 目录，数据已内嵌） ----------
echo [信息] 开始打包（数据已内嵌，无需外置 data 目录）
echo [信息] QT_PLUGIN_PATH=%QT_PLUGIN_PATH%
echo.

pyinstaller --onefile --windowed --name "%EXE_NAME%" --icon SOP.ico --add-data "app;app" --hidden-import PyQt5.sip --hidden-import PyQt5.QtCore --hidden-import PyQt5.QtWidgets --hidden-import PyQt5.QtGui --hidden-import fitz --hidden-import pymupdf --collect-all fitz --clean main.py


if %errorlevel% neq 0 (
    echo.
    echo [错误] 打包失败！
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   打包完成！
echo   生成文件: dist\%EXE_NAME%.exe
echo ============================================================
pause