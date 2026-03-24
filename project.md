📋 구글 캘린더 API 설정 자동화 및 UX 개선 작업 지시서

1. 개요

현재 grid_calendar.pyw는 구글 API 인증을 위해 외부 파일인 credentials.json에 의존하고 있습니다. 이를 개선하여 사용자가 프로그램 내에서 API 정보를 입력하고, .env 파일에 안전하게 저장하여 사용할 수 있도록 관리 방식을 변경합니다.

2. 주요 개선 목표

환경 변수 관리: python-dotenv 라이브러리를 도입하여 API Key를 코드 외부에서 관리.

초기 가이드 제공: .env 파일이 없을 경우 사용자가 직접 API를 발급받을 수 있도록 단계별 안내 UI 구현.

파일 의존성 제거: credentials.json 파일 없이도 환경 변수 값만으로 구글 인증이 가능하도록 로직 리팩토링.

3. 세부 작업 지시 사항

A. 라이브러리 및 환경 설정

python-dotenv 라이브러리를 임포트합니다.

파일 상단에 .env 파일 경로(ENV_FILE = ".env")를 상수로 정의합니다.

프로그램 시작 시 load_dotenv()를 호출하여 기존 설정값을 로드합니다.

B. API 설정 체크 로직 (check_api_configuration)

__init__ 단계에서 GOOGLE_CLIENT_ID와 GOOGLE_CLIENT_SECRET이 환경 변수에 존재하는지 확인합니다.

Case 1 (정보 없음): show_api_setup_guide() 메서드를 호출하여 안내 창을 띄웁니다.

Case 2 (정보 있음): 즉시 authenticate_google()을 수행하고 캘린더를 동기화합니다.

C. 가이드 및 입력 UI 구현 (show_api_setup_guide)

안내 창(Toplevel) 생성:

Google Cloud Console에서 프로젝트 생성 및 API 활성화 방법 요약 설명.

콘솔로 바로 이동할 수 있는 링크 버튼 배치.

입력 폼:

Client ID 입력창.

Client Secret 입력창.

저장 로직:

입력된 값을 .env 파일에 작성하는 기능을 구현합니다.

저장 완료 후 사용자가 재시작하지 않아도 즉시 인증 프로세스를 시작하도록 설계합니다.

D. 인증 로직 수정 (authenticate_google)

기존 InstalledAppFlow.from_client_secrets_file 방식에서 InstalledAppFlow.from_client_config 방식으로 변경합니다.

환경 변수에서 읽어온 정보를 바탕으로 구글이 요구하는 JSON 구조(딕셔너리)를 메모리상에서 생성하여 전달합니다.

E. 예외 처리 강화

잘못된 API 키 입력 시 발생하는 인증 오류를 포착하여 사용자에게 "키를 다시 확인해 주세요"라는 메시지 상자를 띄웁니다.

네트워크 문제와 인증 문제를 구분하여 알림을 제공합니다.

4. 기대 효과

사용자 편의성: JSON 파일을 직접 생성하고 이름을 바꾸는 복잡한 과정이 생략됩니다.

보안성: API 키가 코드에 노출되지 않고 별도의 환경 파일로 분리됩니다.

프로그램 완성도: 초기 실행 시의 친절한 가이드를 통해 사용자 이탈을 방지합니다.