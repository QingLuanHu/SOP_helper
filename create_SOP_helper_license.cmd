@echo off
title 创建 SOP_helper 授权文件

:: 检查管理员权限
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误：此脚本需要管理员权限才能向 C:\Program Files 写入文件。
    echo 请右键点击本脚本，选择“以管理员身份运行”。
    pause
    exit /b 1
)

:: 目标路径（注意：原需求中的 "Progran" 已按标准更正为 "Program"，若需保留原拼写请自行修改）
set "targetDir=C:\Program Files\SOP_helper"

:: 创建目录（若已存在则跳过）
if not exist "%targetDir%" (
    mkdir "%targetDir%" 2>nul
    if errorlevel 1 (
        echo 创建目录失败，请检查路径或权限。
        pause
        exit /b 1
    )
)

:: 写入授权文件（内容 HF796）
echo HF796 > "%targetDir%\license"

:: 验证结果
if exist "%targetDir%\license" (
    echo 成功！
) else (
    echo 文件写入失败，请检查磁盘空间或权限。
)

pause
exit /b 0