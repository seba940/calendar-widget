@echo off
setlocal
cd /d "%~dp0"

echo [1/3] GitHub 업데이트 확인 중...

:: 1. Git 실행 파일 경로 확인
set GIT_CMD=git
where %GIT_CMD% >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    set GIT_CMD="C:\Program Files\Git\bin\git.exe"
    if not exist %GIT_CMD% (
        echo [오류] Git이 설치되어 있지 않거나 경로를 찾을 수 없습니다.
        pause
        exit /b
    )
)

:: 2. 원격 저장소 최신 정보 가져오기
%GIT_CMD% fetch origin main >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [경고] 서버와 연결할 수 없습니다. 업데이트 확인을 건너뜁니다.
    goto :RUN_APP
)

:: 3. 로컬과 원격의 해시값 비교
for /f "tokens=*" %%a in ('%GIT_CMD% rev-parse HEAD') do set LOCAL_HASH=%%a
for /f "tokens=*" %%b in ('%GIT_CMD% rev-parse origin/main') do set REMOTE_HASH=%%b

if "%LOCAL_HASH%" NEQ "%REMOTE_HASH%" (
    echo [알림] 새로운 업데이트가 발견되었습니다. 업데이트를 진행합니다...
    %GIT_CMD% pull origin main
) else (
    echo [알림] 최신 버전입니다.
)

:RUN_APP
echo [2/3] 필요한 라이브러리 체크 중...
python -m pip install -r requirements.txt --quiet --no-warn-script-location

echo [3/3] 달력 위젯 실행 중...
start "" pythonw grid_calendar.pyw

echo 실행 완료!
timeout /t 2 >nul
exit

