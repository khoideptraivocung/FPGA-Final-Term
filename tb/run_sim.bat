@echo off
echo ============================================================
echo Starting Questa / ModelSim Simulation for Topic 22 Filter
echo ============================================================

set QUESTA_BIN=D:\quartus26.1\questa_fse\win64
if not exist "%QUESTA_BIN%\vsim.exe" (
    set QUESTA_BIN=D:\quartus26.1\questa_fe\win64
)

if not exist "%QUESTA_BIN%\vsim.exe" (
    echo [ERROR] Could not find vsim.exe in default Intel Quartus paths.
    echo Please make sure Questa / ModelSim is in PATH.
    pause
    exit /b 1
)

cd /d "%~dp0\.."
echo Running simulation script tb/run_sim.do ...
"%QUESTA_BIN%\vsim.exe" -do tb/run_sim.do

pause
