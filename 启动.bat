@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   BiliDaka · 分P研习录  启动中...
echo ========================================
echo.

py -m streamlit run app.py

echo.
echo 程序已退出，按任意键关闭窗口...
pause >nul
