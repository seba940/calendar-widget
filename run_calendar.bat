@echo off
cd /d "%~dp0"
echo Starting Google Calendar Grid Widget...

:: 1. 필수 라이브러리 체크 및 설치 (선택 사항)
:: python -m pip install -r requirements.txt --quiet

:: 2. 프로그램 실행 (콘솔 창 없이 실행하려면 pythonw 사용)
start "" pythonw grid_calendar.pyw
