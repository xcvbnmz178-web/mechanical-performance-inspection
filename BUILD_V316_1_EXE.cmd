@echo off
setlocal
cd /d "%~dp0"

if not exist "C:\venvs\performance_inspection\Scripts\python.exe" (
    echo ERROR: C:\venvs\performance_inspection\Scripts\python.exe not found.
    pause
    exit /b 1
)

if not exist "main.py" (
    echo ERROR: main.py not found.
    pause
    exit /b 1
)

rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /q MechanicalPerformanceInspection.spec 2>nul

"C:\venvs\performance_inspection\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name MechanicalPerformanceInspection "main.py"

if errorlevel 1 (
    echo BUILD FAILED
    pause
    exit /b 1
)

echo.
echo BUILD SUCCESS
echo %CD%\dist\MechanicalPerformanceInspection.exe
pause
endlocal
