import datetime
import calendar
import os.path
import json
import tkinter as tk
from tkinter import ttk, font as tkfont, messagebox
import threading
import os
import socket
import ssl 
import urllib.request
import httplib2
import webbrowser
from google_auth_httplib2 import AuthorizedHttp
import traceback
from dotenv import load_dotenv, set_key

from korean_lunar_calendar import KoreanLunarCalendar
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

ENV_FILE = ".env"
load_dotenv(ENV_FILE)

# --- 1. 윈도우 시스템 내부의 가짜 프록시 완벽 차단 ---
urllib.request.getproxies = lambda: {}

# --- 2. SSL 인증 강제 무시 ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# --- 3. 환경 변수 프록시 차단 ---
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['NO_PROXY'] = '*'
socket.setdefaulttimeout(30) 

SCOPES = ['https://www.googleapis.com/auth/calendar'] 
SETTINGS_FILE = "settings.json"

class GridCalendarApp:
    def __init__(self, root):
        self.root = root
        self.root.overrideredirect(True)
        self.lunar_cal = KoreanLunarCalendar()
        
        calendar.setfirstweekday(calendar.SUNDAY)
        self.detail_win = None
        
        self._drag_data = None
        self._event_widgets = []
        self._current_day_events = []
        
        self.load_settings()
        self.alpha_val = self.settings.get("alpha", 0.85)
        self.theme = self.settings.get("theme", "black")
        self.font_family = self.settings.get("font_family", "Malgun Gothic").lstrip("@")
        self.font_size = self.settings.get("font_size", 10)
        self.is_pinned = self.settings.get("is_pinned", False)
        
        self.set_theme_colors(self.theme)
        self.root.geometry(self.settings.get("geometry", "1000x800+100+100"))
        self.root.attributes("-alpha", self.alpha_val)
        self.root.configure(bg=self.bg_color)

        self.current_year = datetime.datetime.now().year
        self.current_month = datetime.datetime.now().month
        self._offsetx = 0; self._offsety = 0; self.resizing = False
        self.events_data = []; self.holiday_data = []
        self.holiday_calendar_id = 'ko.south_korea#holiday@group.v.calendar.google.com'

        self.root.bind("<ButtonPress-1>", self.on_press)
        self.root.bind("<B1-Motion>", self.on_motion)
        self.root.bind("<Motion>", self.check_cursor_edge)
        self.root.bind("<Configure>", self.on_resize)

        self.service = None
        self.check_api_configuration()

        self.setup_ui()
        self.auto_sync()

    def check_api_configuration(self):
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        
        if not client_id or not client_secret:
            self.show_api_setup_guide()
        else:
            try:
                self.service = self.authenticate_google()
                self.find_holiday_calendar()
            except Exception as e:
                print(f"인증 실패: {e}")
                self.service = None
                messagebox.showerror("인증 오류", "구글 인증에 실패했습니다. API 키를 확인해 주세요.")
                self.show_api_setup_guide()

    def show_api_setup_guide(self):
        guide_win = tk.Toplevel(self.root)
        guide_win.title("구글 API 설정 가이드")
        guide_win.geometry("500x600")
        guide_win.attributes("-topmost", True)
        guide_win.configure(padx=30, pady=30, bg=self.bg_color)

        tk.Label(guide_win, text="🚀 구글 캘린더 API 설정", font=(self.font_family, 16, "bold"), fg=self.fg_color, bg=self.bg_color).pack(pady=(0, 20))
        
        guide_text = (
            "1. Google Cloud Console에 접속합니다.\n"
            "2. 새 프로젝트를 생성하고 'Google Calendar API'를 활성화하세요.\n"
            "3. '사용자 인증 정보' 메뉴에서 'OAuth 클라이언트 ID'를 생성합니다.\n"
            "4. 애플리케이션 유형을 '데스크톱 앱'으로 선택하세요.\n"
            "5. 생성된 Client ID와 Secret을 아래에 입력해 주세요."
        )
        tk.Label(guide_win, text=guide_text, justify="left", font=(self.font_family, 10), fg=self.fg_color, bg=self.bg_color).pack(fill="x", pady=(0, 20))

        tk.Button(guide_win, text="🔗 Google Cloud Console 바로가기", command=lambda: webbrowser.open("https://console.cloud.google.com/"), bg="#1a73e8", fg="white", font=(self.font_family, 10, "bold"), pady=8).pack(fill="x", pady=(0, 20))

        tk.Label(guide_win, text="Client ID", font=(self.font_family, 10, "bold"), fg=self.fg_color, bg=self.bg_color).pack(anchor="w")
        id_ent = tk.Entry(guide_win, width=50)
        id_ent.pack(pady=(5, 15))
        id_ent.insert(0, os.getenv("GOOGLE_CLIENT_ID", ""))

        tk.Label(guide_win, text="Client Secret", font=(self.font_family, 10, "bold"), fg=self.fg_color, bg=self.bg_color).pack(anchor="w")
        secret_ent = tk.Entry(guide_win, width=50, show="*")
        secret_ent.pack(pady=(5, 20))
        secret_ent.insert(0, os.getenv("GOOGLE_CLIENT_SECRET", ""))

        def save_api_info():
            cid = id_ent.get().strip()
            sec = secret_ent.get().strip()
            
            if not cid or not sec:
                messagebox.showwarning("입력 누락", "Client ID와 Secret을 모두 입력해 주세요.")
                return
            
            # .env 파일에 저장
            set_key(ENV_FILE, "GOOGLE_CLIENT_ID", cid)
            set_key(ENV_FILE, "GOOGLE_CLIENT_SECRET", sec)
            
            # 환경 변수 즉시 갱신
            os.environ["GOOGLE_CLIENT_ID"] = cid
            os.environ["GOOGLE_CLIENT_SECRET"] = sec
            
            messagebox.showinfo("저장 완료", "설정이 저장되었습니다. 인증을 시작합니다.")
            guide_win.destroy()
            
            # 인증 재시도
            try:
                self.service = self.authenticate_google()
                self.find_holiday_calendar()
                self.update_calendar()
            except Exception as e:
                messagebox.showerror("인증 실패", f"인증 중 오류가 발생했습니다: {e}")
                self.show_api_setup_guide()

        tk.Button(guide_win, text="💾 설정 저장 및 인증 시작", command=save_api_info, bg="#2ba347", fg="white", font=(self.font_family, 11, "bold"), pady=10).pack(fill="x")

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f: self.settings = json.load(f)
            except: self.settings = {}
        else: self.settings = {}

    def save_settings(self):
        self.settings.update({
            "geometry": self.root.winfo_geometry(),
            "alpha": self.alpha_val, "theme": self.theme,
            "font_family": self.font_family, "font_size": self.font_size,
            "is_pinned": self.is_pinned
        })
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=4, ensure_ascii=False)

    def authenticate_google(self):
        creds = None
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        
        if not client_id or not client_secret:
            raise ValueError("Google Client ID or Secret is missing in .env")

        # 메모리상에서 클라이언트 설정 생성
        client_config = {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": ["http://localhost"]
            }
        }

        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
            
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try: 
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Token refresh failed: {e}")
                    if os.path.exists('token.json'): os.remove('token.json')
                    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
                    creds = flow.run_local_server(port=0)
            else:
                flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open('token.json', 'w', encoding="utf-8") as t:
                t.write(creds.to_json())
            
        http_client = httplib2.Http(disable_ssl_certificate_validation=True)
        authed_http = AuthorizedHttp(creds, http=http_client)
        
        return build('calendar', 'v3', http=authed_http, static_discovery=False)

    def find_holiday_calendar(self):
        try:
            calendar_list = self.service.calendarList().list().execute()
            for entry in calendar_list.get('items', []):
                if "holiday" in entry.get('summary', '').lower() or "휴일" in entry.get('summary', ''):
                    self.holiday_calendar_id = entry['id']; break
        except: pass

    def set_theme_colors(self, theme):
        self.theme = theme
        if theme == "white":
            self.bg_color = "#ffffff"; self.fg_color = "#000000"; self.cell_bg = "#f8f8f8"
            self.line_color = "#e0e0e0"; self.lunar_color = "#888888"; self.term_color = "#2ba347"
        else:
            self.bg_color = "#121212"; self.fg_color = "#ffffff"; self.cell_bg = "#1e1e1e"
            self.line_color = "#333333"; self.lunar_color = "#aaaaaa"; self.term_color = "#2ecc71"

    def setup_ui(self):
        self.header_frame = tk.Frame(self.root, bg=self.bg_color)
        self.header_frame.pack(fill="x", pady=10, padx=10)
        
        l_f = tk.Frame(self.header_frame, bg=self.bg_color); l_f.pack(side="left")
        tk.Button(l_f, text="◀", command=self.prev_month, bg=self.bg_color, fg=self.fg_color, bd=0, font=("Arial", 14)).pack(side="left", padx=5)
        self.month_label = tk.Label(l_f, text="", font=(self.font_family, 18, "bold"), fg=self.fg_color, bg=self.bg_color, width=14)
        self.month_label.pack(side="left")
        tk.Button(l_f, text="▶", command=self.next_month, bg=self.bg_color, fg=self.fg_color, bd=0, font=("Arial", 14)).pack(side="left", padx=5)
        
        tk.Button(self.header_frame, text="✖", command=self.on_exit, bg=self.bg_color, fg=self.fg_color, bd=0, font=("Arial", 14)).pack(side="right", padx=5)
        
        pin_text = "📍 고정해제" if self.is_pinned else "📌 고정하기"
        self.pin_btn = tk.Button(self.header_frame, text=pin_text, command=self.toggle_pin, bg="#555555", fg="white", bd=0, font=(self.font_family, 10))
        self.pin_btn.pack(side="right", padx=5)
        
        tk.Button(self.header_frame, text="⚙️ 설정", command=self.open_settings, bg="#444444", fg="white", bd=0, font=(self.font_family, 10)).pack(side="right", padx=5)
        tk.Button(self.header_frame, text="🔄 새로고침", command=self.manual_refresh, bg="#2d3436", fg="white", bd=0, font=(self.font_family, 10)).pack(side="right", padx=5)
        
        self.grid_frame = tk.Frame(self.root, bg=self.bg_color)
        self.grid_frame.pack(fill="both", expand=True, padx=10, pady=5)

    def toggle_pin(self):
        self.is_pinned = not self.is_pinned
        self.pin_btn.config(text="📍 고정해제" if self.is_pinned else "📌 고정하기")
        self.save_settings()

    def manual_refresh(self):
        self.update_calendar()

    def toggle_complete(self, event):
        if not self.service:
            messagebox.showerror("연결 오류", "구글 캘린더와 연결되어 있지 않습니다.\ncredentials.json 파일을 확인하고 로그인해주세요.")
            return

        current_summary = event.get('summary', '')
        if current_summary.startswith("✅ "):
            new_summary = current_summary.replace("✅ ", "", 1)
        elif current_summary.startswith("✅"):
            new_summary = current_summary.replace("✅", "", 1).strip()
        else:
            new_summary = "✅ " + current_summary

        try:
            self.service.events().patch(
                calendarId='primary', 
                eventId=event['id'], 
                body={'summary': new_summary}
            ).execute()
            
            if self.detail_win and self.detail_win.winfo_exists():
                self.detail_win.destroy()
            self.update_calendar()
        except Exception as e:
            messagebox.showerror("오류", f"완료 상태 변경에 실패했습니다: {e}")

    def add_event_popup(self, date_str):
        add_win = tk.Toplevel(self.root)
        add_win.title("구글 일정 등록")
        add_win.geometry("400x740")
        add_win.attributes("-topmost", True)
        add_win.configure(padx=25, pady=20)

        tk.Label(add_win, text="📌 일정 제목", font=(self.font_family, 10, "bold")).pack(anchor="w")
        title_ent = tk.Entry(add_win, width=45)
        title_ent.pack(pady=(5, 10))
        title_ent.focus_set()

        tk.Label(add_win, text="📅 시작 날짜", font=(self.font_family, 10, "bold")).pack(anchor="w")
        date_frame = tk.Frame(add_win)
        date_frame.pack(fill="x", pady=(5, 10))
        ev_y, ev_m, ev_d = date_str.split('-')
        
        y_cb = ttk.Combobox(date_frame, values=[str(i) for i in range(2020, 2035)], width=5, state="readonly")
        y_cb.set(ev_y); y_cb.pack(side="left")
        tk.Label(date_frame, text="년 ").pack(side="left")
        
        m_cb = ttk.Combobox(date_frame, values=[f"{i:02d}" for i in range(1, 13)], width=3, state="readonly")
        m_cb.set(ev_m); m_cb.pack(side="left")
        tk.Label(date_frame, text="월 ").pack(side="left")
        
        d_cb = ttk.Combobox(date_frame, values=[f"{i:02d}" for i in range(1, 32)], width=3, state="readonly")
        d_cb.set(ev_d); d_cb.pack(side="left")
        tk.Label(date_frame, text="일").pack(side="left")

        tk.Label(add_win, text="⏰ 시간 설정", font=(self.font_family, 10, "bold")).pack(anchor="w", pady=(5, 0))
        time_main_frame = tk.Frame(add_win)
        time_main_frame.pack(fill="x", pady=(5, 10))

        s_frame = tk.Frame(time_main_frame); s_frame.pack(side="left", padx=(0, 10))
        tk.Label(s_frame, text="시작").pack(side="left")
        s_hour = ttk.Combobox(s_frame, values=[f"{i:02d}" for i in range(24)], width=4, state="readonly")
        s_hour.set("09"); s_hour.pack(side="left", padx=2)
        s_min = ttk.Combobox(s_frame, values=[f"{i:02d}" for i in range(0, 60, 5)], width=4, state="readonly")
        s_min.set("00"); s_min.pack(side="left")

        e_frame = tk.Frame(time_main_frame); e_frame.pack(side="left")
        tk.Label(e_frame, text="종료").pack(side="left")
        e_hour = ttk.Combobox(e_frame, values=[f"{i:02d}" for i in range(24)], width=4, state="readonly")
        e_hour.set("10"); e_hour.pack(side="left", padx=2)
        e_min = ttk.Combobox(e_frame, values=[f"{i:02d}" for i in range(0, 60, 5)], width=4, state="readonly")
        e_min.set("00"); e_min.pack(side="left")

        is_all_day = tk.BooleanVar(value=False)
        tk.Checkbutton(add_win, text="종일 일정 (시간 무시)", variable=is_all_day).pack(anchor="w", pady=(0, 5))

        tk.Label(add_win, text="🔁 반복 설정", font=(self.font_family, 10, "bold")).pack(anchor="w")
        repeat_cb = ttk.Combobox(add_win, values=["반복 없음", "매일", "매주", "매월"], state="readonly", width=42)
        repeat_cb.set("반복 없음")
        repeat_cb.pack(pady=(5, 10))

        tk.Label(add_win, text="🏁 반복 종료일 (반복 안할시 무시)", font=(self.font_family, 10, "bold")).pack(anchor="w")
        rend_frame = tk.Frame(add_win)
        rend_frame.pack(fill="x", pady=(5, 10))
        
        ry_cb = ttk.Combobox(rend_frame, values=[str(i) for i in range(2020, 2035)], width=5, state="readonly")
        ry_cb.set(ev_y); ry_cb.pack(side="left")
        tk.Label(rend_frame, text="년 ").pack(side="left")
        
        rm_cb = ttk.Combobox(rend_frame, values=[f"{i:02d}" for i in range(1, 13)], width=3, state="readonly")
        rm_cb.set(ev_m); rm_cb.pack(side="left")
        tk.Label(rend_frame, text="월 ").pack(side="left")
        
        rd_cb = ttk.Combobox(rend_frame, values=[f"{i:02d}" for i in range(1, 32)], width=3, state="readonly")
        rd_cb.set(ev_d); rd_cb.pack(side="left")
        tk.Label(rend_frame, text="일").pack(side="left")

        tk.Label(add_win, text="📝 메모/설명", font=(self.font_family, 10, "bold")).pack(anchor="w")
        desc_txt = tk.Text(add_win, width=45, height=4, font=(self.font_family, 9))
        desc_txt.pack(pady=(5, 15))

        def save_to_google():
            if not self.service:
                messagebox.showerror("연결 오류", "구글 캘린더와 연결되어 있지 않습니다.\ncredentials.json 파일을 확인하고 로그인해주세요.")
                return

            summary = title_ent.get()
            if not summary:
                messagebox.showwarning("입력 누락", "일정 제목을 입력해주세요.")
                return
            
            new_date_str = f"{y_cb.get()}-{m_cb.get()}-{d_cb.get()}"
            description = desc_txt.get("1.0", "end-1c")
            
            if is_all_day.get():
                target_dt = datetime.datetime.strptime(new_date_str, "%Y-%m-%d")
                next_day = (target_dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                start, end = {'date': new_date_str}, {'date': next_day}
            else:
                if (int(s_hour.get())*60 + int(s_min.get())) >= (int(e_hour.get())*60 + int(e_min.get())):
                    messagebox.showwarning("시간 오류", "종료 시간이 시작 시간보다 빨라야 합니다.")
                    return
                start = {'dateTime': f"{new_date_str}T{s_hour.get()}:{s_min.get()}:00", 'timeZone': 'Asia/Seoul'}
                end = {'dateTime': f"{new_date_str}T{e_hour.get()}:{e_min.get()}:00", 'timeZone': 'Asia/Seoul'}

            body = {
                'summary': summary, 
                'description': description, 
                'start': start, 
                'end': end
            }
            
            rep = repeat_cb.get()
            if rep != "반복 없음":
                until_str = f"{ry_cb.get()}{rm_cb.get()}{rd_cb.get()}T145959Z"
                if rep == "매일": body['recurrence'] = [f'RRULE:FREQ=DAILY;UNTIL={until_str}']
                elif rep == "매주": body['recurrence'] = [f'RRULE:FREQ=WEEKLY;UNTIL={until_str}']
                elif rep == "매월": body['recurrence'] = [f'RRULE:FREQ=MONTHLY;UNTIL={until_str}']

            try:
                self.service.events().insert(calendarId='primary', body=body).execute()
                messagebox.showinfo("성공", f"일정이 등록되었습니다.")
                add_win.destroy(); self.update_calendar()
            except Exception as e: messagebox.showerror("오류", str(e))

        tk.Button(add_win, text="구글 캘린더에 저장", command=save_to_google, bg="#1a73e8", fg="white", font=(self.font_family, 10, "bold"), height=2).pack(fill="x")

    def edit_event_popup(self, event, date_str):
        edit_win = tk.Toplevel(self.root)
        edit_win.title("구글 일정 수정")
        edit_win.geometry("400x620")
        edit_win.attributes("-topmost", True)
        edit_win.configure(padx=25, pady=20)

        tk.Label(edit_win, text="📌 일정 제목", font=(self.font_family, 10, "bold")).pack(anchor="w")
        title_ent = tk.Entry(edit_win, width=45)
        title_ent.insert(0, event.get('summary', ''))
        title_ent.pack(pady=(5, 15))
        title_ent.focus_set()

        tk.Label(edit_win, text="📅 날짜 설정", font=(self.font_family, 10, "bold")).pack(anchor="w")
        date_frame = tk.Frame(edit_win)
        date_frame.pack(fill="x", pady=(5, 10))
        ev_y, ev_m, ev_d = date_str.split('-')
        
        y_cb = ttk.Combobox(date_frame, values=[str(i) for i in range(2020, 2035)], width=5, state="readonly")
        y_cb.set(ev_y); y_cb.pack(side="left")
        tk.Label(date_frame, text="년 ").pack(side="left")
        
        m_cb = ttk.Combobox(date_frame, values=[f"{i:02d}" for i in range(1, 13)], width=3, state="readonly")
        m_cb.set(ev_m); m_cb.pack(side="left")
        tk.Label(date_frame, text="월 ").pack(side="left")
        
        d_cb = ttk.Combobox(date_frame, values=[f"{i:02d}" for i in range(1, 32)], width=3, state="readonly")
        d_cb.set(ev_d); d_cb.pack(side="left")
        tk.Label(date_frame, text="일").pack(side="left")

        tk.Label(edit_win, text="⏰ 시간 설정", font=(self.font_family, 10, "bold")).pack(anchor="w", pady=(5, 0))
        time_main_frame = tk.Frame(edit_win)
        time_main_frame.pack(fill="x", pady=(5, 10))

        s_frame = tk.Frame(time_main_frame); s_frame.pack(side="left", padx=(0, 10))
        tk.Label(s_frame, text="시작").pack(side="left")
        s_hour = ttk.Combobox(s_frame, values=[f"{i:02d}" for i in range(24)], width=4, state="readonly")
        s_hour.pack(side="left", padx=2)
        s_min = ttk.Combobox(s_frame, values=[f"{i:02d}" for i in range(0, 60, 5)], width=4, state="readonly")
        s_min.pack(side="left")

        e_frame = tk.Frame(time_main_frame); e_frame.pack(side="left")
        tk.Label(e_frame, text="종료").pack(side="left")
        e_hour = ttk.Combobox(e_frame, values=[f"{i:02d}" for i in range(24)], width=4, state="readonly")
        e_hour.pack(side="left", padx=2)
        e_min = ttk.Combobox(e_frame, values=[f"{i:02d}" for i in range(0, 60, 5)], width=4, state="readonly")
        e_min.pack(side="left")

        is_all_day = tk.BooleanVar(value=False)
        if 'date' in event['start']:
            is_all_day.set(True)
            s_hour.set("09"); s_min.set("00")
            e_hour.set("10"); e_min.set("00")
        else:
            st = event['start']['dateTime'][11:16]
            et = event['end']['dateTime'][11:16]
            s_hour.set(st[:2]); s_min.set(st[3:])
            e_hour.set(et[:2]); e_min.set(et[3:])

        tk.Checkbutton(edit_win, text="종일 일정 (시간 무시)", variable=is_all_day).pack(anchor="w", pady=(0, 15))

        tk.Label(edit_win, text="📝 메모/설명", font=(self.font_family, 10, "bold")).pack(anchor="w")
        desc_txt = tk.Text(edit_win, width=45, height=5, font=(self.font_family, 9))
        desc_txt.insert("1.0", event.get('description', ''))
        desc_txt.pack(pady=(5, 20))

        def update_to_google():
            if not self.service:
                messagebox.showerror("연결 오류", "구글 캘린더와 연결되어 있지 않습니다.\ncredentials.json 파일을 확인하고 로그인해주세요.")
                return

            summary = title_ent.get()
            if not summary:
                messagebox.showwarning("입력 누락", "일정 제목을 입력해주세요.")
                return
            
            new_date_str = f"{y_cb.get()}-{m_cb.get()}-{d_cb.get()}"
            description = desc_txt.get("1.0", "end-1c")
            
            if is_all_day.get():
                target_dt = datetime.datetime.strptime(new_date_str, "%Y-%m-%d")
                next_day = (target_dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                start, end = {'date': new_date_str}, {'date': next_day}
            else:
                if (int(s_hour.get())*60 + int(s_min.get())) >= (int(e_hour.get())*60 + int(e_min.get())):
                    messagebox.showwarning("시간 오류", "종료 시간이 시작 시간보다 빨라야 합니다.")
                    return
                start = {'dateTime': f"{new_date_str}T{s_hour.get()}:{s_min.get()}:00", 'timeZone': 'Asia/Seoul'}
                end = {'dateTime': f"{new_date_str}T{e_hour.get()}:{e_min.get()}:00", 'timeZone': 'Asia/Seoul'}

            try:
                self.service.events().update(calendarId='primary', eventId=event['id'], body={'summary': summary, 'description': description, 'start': start, 'end': end}).execute()
                messagebox.showinfo("성공", f"일정이 수정되었습니다.")
                edit_win.destroy(); self.update_calendar()
            except Exception as e: messagebox.showerror("오류", str(e))

        tk.Button(edit_win, text="수정 내용 저장하기", command=update_to_google, bg="#2ba347", fg="white", font=(self.font_family, 10, "bold"), height=2).pack(fill="x")

    def delete_event(self, event_id):
        if not self.service:
            messagebox.showerror("연결 오류", "구글 캘린더와 연결되어 있지 않습니다.\ncredentials.json 파일을 확인하고 로그인해주세요.")
            return

        if "_" in event_id:
            base_id = event_id.split('_')[0]
            ans = messagebox.askyesnocancel("반복 일정 삭제", "이 일정은 반복 일정입니다.\n어떻게 지울까요?\n\n[예] 앞으로 반복되는 전체 일정 싹 다 삭제\n[아니요] 딱 이 날짜의 일정 1개만 삭제\n[취소] 돌아가기")
            
            if ans is True: 
                target_id = base_id
            elif ans is False: 
                target_id = event_id
            else:
                return
        else:
            if not messagebox.askyesno("삭제 확인", "이 일정을 정말 삭제하시겠습니까?\n(구글 캘린더에서도 완전히 지워집니다)"):
                return
            target_id = event_id

        try:
            self.service.events().delete(calendarId='primary', eventId=target_id).execute()
            self.update_calendar()
            messagebox.showinfo("삭제 완료", "일정이 삭제되었습니다!")
        except Exception as err:
            messagebox.showerror("삭제 실패", str(err))

    def navigate_day(self, current_date_str, direction, skip_empty):
        target_dt = datetime.datetime.strptime(current_date_str, "%Y-%m-%d")
        
        while True:
            target_dt += datetime.timedelta(days=direction)
            y, m, d = target_dt.year, target_dt.month, target_dt.day
            
            if m != self.current_month or y != self.current_year:
                messagebox.showinfo("알림", "현재 달의 범위를 벗어났습니다.\n뒤의 달력을 먼저 넘긴 후 다시 확인해 주세요!")
                return
                
            date_str = f"{y}-{m:02d}-{d:02d}"
            hols = [h for h in self.holiday_data if date_str in h['start'].get('date', '')]
            evts = [e for e in self.events_data if date_str in e.get('start', {}).get('dateTime', e.get('start', {}).get('date', ''))]
            
            if not skip_empty:
                break
            else:
                if hols or evts:
                    break
                    
        self.show_day_details(y, m, d, hols, evts)

    def sort_events(self, evts):
        orders = self.settings.get("event_orders", {})
        return sorted(evts, key=lambda e: (orders.get(e['id'], 999), e['start'].get('dateTime', e['start'].get('date', ''))))

    def on_drag_start(self, event, event_data):
        self._drag_data = {"event_data": event_data}

    def on_drag_stop(self, event, y, m, d, hols):
        if not self._drag_data: return
        
        y_root = event.y_root
        target_index = -1
        
        for i, w in enumerate(self._event_widgets):
            if not w.winfo_exists(): continue
            wy = w.winfo_rooty()
            wh = w.winfo_height()
            if wy <= y_root <= wy + wh:
                target_index = i
                break
                
        if target_index == -1 and self._event_widgets:
            if y_root < self._event_widgets[0].winfo_rooty():
                target_index = 0
            elif y_root > self._event_widgets[-1].winfo_rooty() + self._event_widgets[-1].winfo_height():
                target_index = len(self._event_widgets) - 1
                
        if target_index != -1:
            evts = self._current_day_events
            old_index = evts.index(self._drag_data["event_data"])
            
            if old_index != target_index:
                ev = evts.pop(old_index)
                evts.insert(target_index, ev)
                
                if "event_orders" not in self.settings:
                    self.settings["event_orders"] = {}
                for idx, ev_item in enumerate(evts):
                    self.settings["event_orders"][ev_item['id']] = idx
                self.save_settings()
                
                self.draw_calendar(self.current_year, self.current_month)
                self.root.after(10, lambda: self.show_day_details(y, m, d, hols, evts))
                
        self._drag_data = None

    # --- [신규 추가] 구글 캘린더의 가짜 공휴일(기념일) 판별 함수 ---
    def is_red_holiday(self, summary):
        # 여기에 적힌 키워드가 포함된 날은 '빨간 날'로 취급하지 않습니다.
        not_red_kw = ["어버이날", "스승의날", "제헌절", "식목일", "국군의 날", "대보름", "단오", "유두", "칠석", "동지", "노동절", "근로자의 날", "발렌타인데이", "화이트데이"]
        return not any(kw in summary for kw in not_red_kw)
    # -------------------------------------------------------------

    def show_day_details(self, year, month, day, hols, evts):
        date_str = f"{year}-{month:02d}-{day:02d}"
        
        evts = self.sort_events(evts)
        self._current_day_events = evts 
        self._event_widgets = [] 
        
        if self.detail_win and self.detail_win.winfo_exists():
            for w in self.detail_win.winfo_children():
                w.destroy()
            win = self.detail_win
        else:
            win = tk.Toplevel(self.root)
            self.detail_win = win
            win.geometry("380x480")
            win.attributes("-topmost", True)
            
        win.title("상세")
        win.configure(bg=self.bg_color, padx=20, pady=20)
        
        nav_frame = tk.Frame(win, bg=self.bg_color)
        nav_frame.pack(fill="x", pady=(0, 15))
        
        tk.Button(nav_frame, text="⏪", command=lambda: self.navigate_day(date_str, -1, True), bg=self.bg_color, fg=self.fg_color, bd=0, font=("Arial", 12), cursor="hand2").pack(side="left")
        tk.Button(nav_frame, text="◀", command=lambda: self.navigate_day(date_str, -1, False), bg=self.bg_color, fg=self.fg_color, bd=0, font=("Arial", 12), cursor="hand2").pack(side="left", padx=(5, 0))
        
        lbl = tk.Label(nav_frame, text=f"{month}월 {day}일 일정", font=(self.font_family, 14, "bold"), bg=self.bg_color, fg=self.fg_color)
        lbl.pack(side="left", expand=True)
        
        tk.Button(nav_frame, text="▶", command=lambda: self.navigate_day(date_str, 1, False), bg=self.bg_color, fg=self.fg_color, bd=0, font=("Arial", 12), cursor="hand2").pack(side="left", padx=(0, 5))
        tk.Button(nav_frame, text="⏩", command=lambda: self.navigate_day(date_str, 1, True), bg=self.bg_color, fg=self.fg_color, bd=0, font=("Arial", 12), cursor="hand2").pack(side="left")
        
        detail_frame = tk.Frame(win, bg=self.bg_color); detail_frame.pack(fill="both", expand=True)
        
        # --- [수정] 상세 창에서 기념일은 회색, 진짜 공휴일은 빨간색으로 표시 ---
        for h in hols: 
            summary = h.get('summary', '')
            is_red = self.is_red_holiday(summary)
            hol_c = "#ff6b6b" if is_red else self.lunar_color
            prefix = "🎉 " if is_red else "📅 "
            tk.Label(detail_frame, text=f"{prefix}{summary}", fg=hol_c, bg=self.bg_color, font=(self.font_family, 11)).pack(anchor="w")
        # ------------------------------------------------------------------------
        
        for e in evts:
            e_frame = tk.Frame(detail_frame, bg=self.bg_color)
            e_frame.pack(fill="x", pady=4)
            self._event_widgets.append(e_frame)
            
            drag_handle = tk.Label(e_frame, text="≡", fg="#888", bg=self.bg_color, font=(self.font_family, 14), cursor="sb_v_double_arrow")
            drag_handle.pack(side="left", padx=(0, 5))
            
            drag_handle.bind("<Button-1>", lambda event, evt=e: self.on_drag_start(event, evt))
            drag_handle.bind("<ButtonRelease-1>", lambda event, y_=year, m_=month, d_=day, hs=hols: self.on_drag_stop(event, y_, m_, d_, hs))
            
            t = e['start'].get('dateTime', '종일')[11:16] if 'dateTime' in e['start'] else "종일"
            
            summary_text = e.get('summary', '무제')
            is_done = summary_text.startswith("✅")
            evt_font = tkfont.Font(family=self.font_family, size=10, overstrike=is_done)
            color = "#888888" if is_done else self.fg_color

            tk.Button(e_frame, text="V", command=lambda evt=e: self.toggle_complete(evt), bg="#444", fg="white", bd=0, width=2, cursor="hand2").pack(side="left", padx=2)
            tk.Label(e_frame, text=f"• {summary_text} ({t})", fg=color, bg=self.bg_color, anchor="w", font=evt_font).pack(side="left", fill="x", expand=True)

            tk.Button(e_frame, text="삭제", command=lambda evt_id=e['id']: [self.detail_win.destroy(), self.delete_event(evt_id)], bg="#ff4757", fg="white", bd=0, font=(self.font_family, 9), cursor="hand2").pack(side="right", padx=(2, 0))
            tk.Button(e_frame, text="수정", command=lambda evt=e: [self.detail_win.destroy(), self.edit_event_popup(evt, date_str)], bg="#555555", fg="white", bd=0, font=(self.font_family, 9), cursor="hand2").pack(side="right")
        
        tk.Button(win, text="+ 새로운 일정 추가하기", command=lambda: [self.detail_win.destroy(), self.add_event_popup(date_str)], bg="#1a73e8", fg="white", font=(self.font_family, 10, "bold")).pack(fill="x", pady=10)
        tk.Button(win, text="닫기", command=self.detail_win.destroy).pack(fill="x")

    def get_solar_term(self, year, month, day):
        if year < 2000 or year > 2099: return ""
        y = year - 2000
        constants = {
            1: [("소한", 5.4055), ("대한", 20.12)], 2: [("입춘", 4.6295), ("우수", 19.204)],
            3: [("경칩", 5.6254), ("춘분", 20.646)], 4: [("청명", 4.908), ("곡우", 20.1)],
            5: [("입하", 5.52), ("소만", 21.04)], 6: [("망종", 5.678), ("하지", 21.37)],
            7: [("소서", 7.108), ("대서", 22.83)], 8: [("입추", 7.446), ("처서", 23.25)],
            9: [("백로", 7.646), ("추분", 23.042)], 10: [("한로", 8.318), ("상강", 23.438)],
            11: [("입동", 7.438), ("소설", 22.36)], 12: [("대설", 7.18), ("동지", 21.94)]
        }
        for name, const in constants.get(month, []):
            term_day = int(const + 0.2422 * y - int((y - 1) / 4))
            if day == term_day: return name
        return ""

    def draw_calendar(self, year, month):
        self.month_label.config(text=f"{year}년 {month}월", font=(self.font_family, 18, "bold"))
        for w in self.grid_frame.winfo_children(): w.destroy()
        
        days = ["일", "월", "화", "수", "목", "금", "토"]
        for c, d in enumerate(days):
            self.grid_frame.grid_columnconfigure(c, weight=1, uniform="col") 
            day_c = "#ff6b6b" if c == 0 else "#74b9ff" if c == 6 else self.fg_color
            lbl = tk.Label(self.grid_frame, text=d, font=(self.font_family, 11, "bold"), fg=day_c, bg=self.bg_color)
            lbl.grid(row=0, column=c, sticky="nsew", pady=(0, 5))

        cal = calendar.monthcalendar(year, month)
        now = datetime.datetime.now()
        
        cell_click_handler = lambda e, y=year, m=month, d_=None, h=None, ev=None: self.show_day_details(y, m, getattr(e.widget, "_day", 1), getattr(e.widget, "_hols", []), getattr(e.widget, "_evts", []))
        
        for r, week in enumerate(cal):
            self.grid_frame.grid_rowconfigure(r+1, weight=1) 
            for c, day in enumerate(week):
                if day == 0: continue
                target_date = f"{year}-{month:02d}-{day:02d}"
                
                all_hols = [h for h in self.holiday_data if target_date in h['start'].get('date', '')]
                
                # --- [수정] 진짜 빨간 날(공휴일)만 추려서 테두리와 숫자 색상을 결정 ---
                red_hols = [h for h in all_hols if self.is_red_holiday(h.get('summary', ''))]
                # ---------------------------------------------------------------------
                
                is_today = (year == now.year and month == now.month and day == now.day)
                current_cell_bg = ("#1a2a40" if self.theme == "black" else "#e3f2fd") if is_today else self.cell_bg
                border_c = "#1a73e8" if is_today else self.line_color
                border_w = 2 if is_today else 1
                
                day_c = "#ff6b6b" if (c == 0 or len(red_hols) > 0) else "#74b9ff" if c == 6 else self.fg_color
                
                f = tk.Frame(self.grid_frame, bg=current_cell_bg, highlightbackground=border_c, highlightcolor=border_c, highlightthickness=border_w)
                f.grid(row=r+1, column=c, sticky="nsew", padx=1, pady=1)
                
                h_f = tk.Frame(f, bg=current_cell_bg); h_f.pack(fill="x", padx=5, pady=2)
                
                tk.Label(h_f, text=str(day), font=(self.font_family, self.font_size, "bold"), fg=day_c, bg=current_cell_bg).pack(side="left")
                self.lunar_cal.setSolarDate(year, month, day)
                tk.Label(h_f, text=f"{self.lunar_cal.lunarMonth}.{self.lunar_cal.lunarDay}", font=(self.font_family, max(7, self.font_size-3)), fg=self.lunar_color, bg=current_cell_bg).pack(side="right")
                
                term = self.get_solar_term(year, month, day)
                if term: tk.Label(h_f, text=term, font=(self.font_family, max(7, self.font_size-3), "bold"), fg=self.term_color, bg=current_cell_bg).pack(side="right", padx=2)
                
                # --- [수정] 메인 달력 셀 안에서도 텍스트 색상 분리 ---
                for h in all_hols: 
                    summary = h.get('summary', '')
                    is_red = self.is_red_holiday(summary)
                    hol_c = "#ff6b6b" if is_red else self.lunar_color
                    hol_font = (self.font_family, max(7, self.font_size-3), "bold" if is_red else "normal")
                    tk.Label(f, text=summary, font=hol_font, fg=hol_c, bg=current_cell_bg).pack(anchor="w", padx=5)
                # -----------------------------------------------------
                
                evts = [e for e in self.events_data if target_date in e.get('start', {}).get('dateTime', e.get('start', {}).get('date', ''))]
                evts = self.sort_events(evts) 
                
                specific_handler = lambda e, y=year, m=month, d=day, h=all_hols, ev=evts: self.show_day_details(y, m, d, h, ev)
                
                for evt in evts[:3]: 
                    summary = evt.get('summary', '무제')
                    is_done = summary.startswith("✅")
                    evt_font = tkfont.Font(family=self.font_family, size=max(8, self.font_size-2), overstrike=is_done)
                    display_color = "#888888" if is_done else self.fg_color

                    evt_f = tk.Frame(f, bg=current_cell_bg)
                    evt_f.pack(fill="x", padx=2, pady=1)
                    
                    dot_lbl = tk.Label(evt_f, text="•", font=evt_font, fg=display_color, bg=current_cell_bg, anchor="n")
                    dot_lbl.pack(side="left", anchor="n", padx=(0, 2))
                    
                    txt_lbl = tk.Label(evt_f, text=summary, font=evt_font, fg=display_color, bg=current_cell_bg, anchor="w", justify="left")
                    txt_lbl.pack(side="left", fill="x", expand=True)
                    
                    txt_lbl.bind('<Configure>', lambda e, l=txt_lbl: l.config(wraplength=max(10, e.width)))
                    
                    evt_f.bind("<Button-1>", specific_handler)
                    dot_lbl.bind("<Button-1>", specific_handler)
                    txt_lbl.bind("<Button-1>", specific_handler)
                
                f.bind("<Button-1>", specific_handler)
                h_f.bind("<Button-1>", specific_handler)
                for child in h_f.winfo_children():
                    child.bind("<Button-1>", specific_handler)

    def fetch_events(self, year, month):
        if not self.service: 
            self.root.after(0, lambda: self.draw_calendar(year, month))
            return
            
        s = f"{year}-{month:02d}-01T00:00:00Z"
        e = f"{year + (1 if month==12 else 0)}-{(month%12)+1:02d}-01T00:00:00Z"
        
        for _ in range(2):
            try:
                self.events_data = self.service.events().list(calendarId='primary', timeMin=s, timeMax=e, singleEvents=True, orderBy='startTime').execute().get('items', [])
                break 
            except Exception:
                pass 
                
        for _ in range(2):
            try:
                self.holiday_data = self.service.events().list(calendarId=self.holiday_calendar_id, timeMin=s, timeMax=e, singleEvents=True, orderBy='startTime').execute().get('items', [])
                break
            except Exception:
                pass 

        self.root.after(0, lambda: self.draw_calendar(year, month))

    def open_settings(self):
        sw = tk.Toplevel(self.root); sw.title("설정"); sw.geometry("400x580"); sw.attributes("-topmost", True); sw.configure(padx=25, pady=25)
        tk.Label(sw, text="⚙️ 달력 설정", font=(self.font_family, 15, "bold")).pack(pady=(0, 20))
        tk.Label(sw, text="위젯 투명도").pack(anchor="w")
        sc = ttk.Scale(sw, from_=0.1, to=1.0, value=self.alpha_val, command=lambda v: self.root.attributes("-alpha", float(v)))
        sc.pack(fill="x", pady=(5, 15))
        tk.Label(sw, text="글꼴 종류").pack(anchor="w")
        font_cb = ttk.Combobox(sw, values=sorted(list(set(tkfont.families()))), state="readonly")
        font_cb.set(self.font_family); font_cb.pack(fill="x", pady=(5, 15))
        tk.Label(sw, text="글자 크기").pack(anchor="w")
        size_sp = tk.Spinbox(sw, from_=8, to=25, increment=1)
        size_sp.delete(0, "end"); size_sp.insert(0, self.font_size); size_sp.pack(fill="x", pady=(5, 15))
        def save_and_apply():
            self.alpha_val = float(sc.get()); self.font_family = font_cb.get(); self.font_size = int(size_sp.get())
            self.save_settings(); self.draw_calendar(self.current_year, self.current_month); sw.destroy()
        def toggle_theme():
            self.theme = "white" if self.theme == "black" else "black"; self.set_theme_colors(self.theme); self.root.configure(bg=self.bg_color)
            self.header_frame.configure(bg=self.bg_color); self.month_label.configure(bg=self.bg_color, fg=self.fg_color)
            self.grid_frame.configure(bg=self.bg_color); self.draw_calendar(self.current_year, self.current_month)
        tk.Button(sw, text="테마 전환", command=toggle_theme, height=2).pack(fill="x", pady=5)
        tk.Button(sw, text="설정 저장 및 적용", command=save_and_apply, bg="#1a73e8", fg="white", font=(self.font_family, 11, "bold"), height=2).pack(fill="x", pady=15)

    def on_exit(self): self.save_settings(); self.root.destroy()
    def update_calendar(self): self.month_label.config(text="⏳ 로딩 중..."); threading.Thread(target=self.fetch_events, args=(self.current_year, self.current_month), daemon=True).start()
    def auto_sync(self): self.update_calendar(); self.root.after(600000, self.auto_sync)
    
    def on_press(self, e):
        if self.is_pinned: return
        self._offsetx, self._offsety = e.x, e.y
        self.resizing = (e.x > self.root.winfo_width()-20 and e.y > self.root.winfo_height()-20)
        
    def on_motion(self, e):
        if self.is_pinned: return
        if self.resizing: self.root.geometry(f"{max(600, e.x)}x{max(400, e.y)}")
        else: self.root.geometry(f"+{self.root.winfo_x()+(e.x-self._offsetx)}+{self.root.winfo_y()+(e.y-self._offsety)}")
        
    def check_cursor_edge(self, e):
        if self.is_pinned: 
            self.root.config(cursor="")
            return
        self.root.config(cursor="size_nw_se" if (e.x > self.root.winfo_width()-20 and e.y > self.root.winfo_height()-20) else "")
        
    def on_resize(self, e):
        if e.widget == self.root:
            if hasattr(self, '_id'): self.root.after_cancel(self._id)
            self._id = self.root.after(200, lambda: self.draw_calendar(self.current_year, self.current_month))
            
    def prev_month(self): self.current_month=12 if self.current_month==1 else self.current_month-1; self.current_year-=(1 if self.current_month==12 else 0); self.update_calendar()
    def next_month(self): self.current_month=1 if self.current_month==12 else self.current_month+1; self.current_year+=(1 if self.current_month==1 else 0); self.update_calendar()

if __name__ == '__main__':
    try:
        print("▶ 달력 프로그램 로딩을 시작합니다...")
        root = tk.Tk()
        app = GridCalendarApp(root)
        
        # 창을 다른 프로그램들 맨 아래로 배치
        app.root.lower() 

        print("▶ 화면 띄우기 성공! 달력을 확인해 주세요.")
        root.mainloop()
    except Exception as e:
        print("\n❌ 숨겨진 에러가 발견되었습니다:")
        traceback.print_exc()
        input("\n엔터 키를 누르면 창이 닫힙니다...")