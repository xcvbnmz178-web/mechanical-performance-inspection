@echo off
cd /d "%~dp0"

if not exist "C:\venvs\performance_inspection\Scripts\pythonw.exe" (
    echo ERROR: C:\venvs\performance_inspection\Scripts\pythonw.exe not found.
    pause
    exit /b 1
)

if not exist "main.py" (
    echo ERROR: main.py not found.
    echo Put this launcher in the same folder as main.py.
    pause
    exit /b 1
)

start "" "C:\venvs\performance_inspection\Scripts\pythonw.exe" "main.py"
exit /b 0
