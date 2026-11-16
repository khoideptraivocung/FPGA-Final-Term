@echo off
chcp 65001 >nul
echo ====================================================================
echo     KHỞI ĐỘNG GIAO DIỆN PYTHON GUI ĐIỀU KHIỂN BỘ LỌC FPGA
echo ====================================================================
echo Đang chạy bằng Python Miniconda3...
if exist "C:\Users\DO DUC KHOI\miniconda3\python.exe" (
    "C:\Users\DO DUC KHOI\miniconda3\python.exe" "python\sensor_filter_gui.py"
) else (
    python "python\sensor_filter_gui.py"
)
pause
