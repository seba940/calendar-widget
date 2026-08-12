@echo off
cd /d "%~dp0"
echo Starting Google Calendar Grid Widget...

:: 1. 필수 라이브러리 설치 (없을 경우에만)
python -c "import googleapiclient, google_auth_httplib2, google_auth_oauthlib, dotenv, korean_lunar_calendar, httplib2, pystray, PIL, tkintermapview" 2>nul || (
    echo [설치 중] 필수 라이브러리 설치 중... 잠시만 기다려주세요...
    python -m pip install -r requirements.txt --quiet
    echo [완료] 설치 완료!
)

:: 2. 프로그램 실행 (콘솔 창 없이 실행)
start "" pythonw grid_calendar.pyw
