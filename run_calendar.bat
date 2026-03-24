@echo off
setlocal
cd /d "%~dp0"

echo [1/3] GitHub 업데이트 확인 중...

:: Git 경로 설정 (사용자 환경에 맞춰 자동 감지 시도 및 고정 경로 사용)
set GIT_PATH="C:\Program Files\Git\bin\git.exe"

:: Git이 설치되어 있는지 확인
if not exist %GIT_PATH% (
    echo [오류] Git을 찾을 수 없습니다. 경로를 확인해 주세요.
    pause
    exit /b
)

:: 원격 저장소 정보 가져오기
%GIT_PATH% fetch origin main >nul 2>&1

:: 로컬과 원격의 차이 확인
for /f %%i in ('%GIT_PATH% rev-list HEAD..origin/main --count') do set UPDATES=%%i

if "%UPDATES%" NEQ "0" (
    echo [알림] 새로운 업데이트가 발견되었습니다. 업데이트를 진행합니다...
    %GIT_PATH% pull origin main
) else (
    echo [알림] 최신 버전입니다.
)

echo [2/3] 필요한 라이브러리 체크 중...
:: 실행 전 필요한 라이브러리 설치/업데이트
python -m pip install -r requirements.txt --quiet --no-warn-script-location

echo [3/3] 달력 위젯 실행 중...
:: pythonw를 사용하여 백그라운드에서 실행 (콘솔 창 생기지 않음)
start "" pythonw grid_calendar.pyw

echo 실행 완료!
timeout /t 2 >nul
exit
