@echo off
title 품질심사 스케줄링 시스템
cd /d "%~dp0"

if not exist app.py (
    if exist "심사 프로그램\app.py" cd /d "%~dp0심사 프로그램"
)

echo ======================================================================
echo    티웨이항공 품질심사 스케줄링 시스템 가동
echo ======================================================================
echo.
echo [1/2] 브라우저 창을 엽니다 (http://localhost:8000)...
start "" "http://localhost:8000"

echo [2/2] 로컬 서버를 실행합니다...
echo * 프로그램을 종료하시려면 이 창을 닫아주시면 됩니다.
echo ======================================================================
echo.

py app.py
if errorlevel 1 (
    python app.py
)
if errorlevel 1 (
    if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
        "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" app.py
    )
)
if errorlevel 1 (
    echo.
    echo [오류] 서버 실행에 실패했습니다.
    pause
)
