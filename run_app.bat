@echo off
chcp 65001 > nul
title 품질심사 스케줄링 시스템

echo ==================================================
echo         품질심사 스케줄링 시스템 가동 중...
echo ==================================================
echo.

cd /d "%~dp0"

echo [1/3] 의존성 라이브러리 점검 및 자동 설치 중...
python -m pip install -r requirements.txt
if errorlevel 1 goto ERR_PIP

echo [성공] 의존성 라이브러리 준비 완료.
echo.

echo [2/3] 웹 브라우저 연결 준비 중...
echo  - 접속 주소: http://localhost:8000
echo  - 콘솔 창을 닫으면 웹 서버가 종료됩니다.
echo ==================================================
echo.

ping 127.0.0.1 -n 3 > nul
start "" "http://localhost:8000"

echo [3/3] app.py 서버 구동 시작...
python app.py
if errorlevel 1 goto ERR_APP

echo.
echo [안내] 프로그램이 정상 종료되었습니다.
echo.
pause
exit /b 0

:ERR_PIP
echo.
echo [오류] 패키지 자동 설치 중 에러가 발생했습니다.
echo 파이썬 설치 상태나 인터넷 연결을 확인해 주세요.
echo.
pause
exit /b 1

:ERR_APP
echo.
echo [오류 발생] app.py 실행 중 문제가 발생하여 서버가 비정상 종료되었습니다.
echo 상단의 오류 로그를 확인해 주세요.
echo.
pause
exit /b 1
