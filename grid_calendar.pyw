import datetime
import calendar
import json
import tkinter as tk
from tkinter import ttk, font as tkfont, messagebox
import threading
import os
import socket
import ssl 
import urllib.request
import traceback
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item

from google_calendar_api import GoogleCalendarAPI
from calendar_utils import CalendarUtils
from config_manager import ConfigManager
from ui_components import UIComponents, DetailWindow, EventPopup, SettingsWindow, AgendaWindow

# --- 윈도우 시스템 내부의 가짜 프록시 및 SSL 설정 ---
urllib.request.getproxies = lambda: {}
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
socket.setdefaulttimeout(30) 

class GridCalendarApp:
    def __init__(self, root):
        self.root = root
        self.root.overrideredirect(True)
        
        self.config = ConfigManager()
        self.api = GoogleCalendarAPI()
        self.utils = CalendarUtils()
        
        calendar.setfirstweekday(calendar.SUNDAY)
        self.detail_win_instance = None
        self.settings_win_instance = None
        self._drag_data = None
        self._event_widgets = []
        
        self.alpha_val = self.config.settings.get("alpha", 0.85)
        self.theme = self.config.settings.get("theme", "black")
        self.font_family = self.config.settings.get("font_family", "Malgun Gothic").lstrip("@")
        self.font_size = self.config.settings.get("font_size", 10)
        self.is_pinned = self.config.settings.get("is_pinned", False)
        self.tray_icon = None
        self.view_mode = "monthly" # "monthly" or "weekly"
        self.memos_data = self.config.settings.get("memos", {})
        
        self.set_theme_colors(self.theme)
        self.root.geometry(self.config.settings.get("geometry", "1000x800+100+100"))
        self.root.attributes("-alpha", self.alpha_val)
        self.root.configure(bg=self.bg_color)

        now = datetime.datetime.now()
        self.current_year = now.year
        self.current_month = now.month
        self.current_date = now.date() # 주간 보기 및 기준 날짜

        self._offsetx = 0; self._offsety = 0; self.resizing = False
        self.events_data = []; self.holiday_data = []

        self.root.bind("<ButtonPress-1>", self.on_press)
        self.root.bind("<B1-Motion>", self.on_motion)
        self.root.bind("<Motion>", self.check_cursor_edge)
        self.root.bind("<Configure>", self.on_resize)

        self.check_api_configuration()
        self.setup_ui()
        self.auto_sync()

    def save_memo(self, date_str, text):
        if not text.strip():
            if date_str in self.memos_data:
                del self.memos_data[date_str]
        else:
            self.memos_data[date_str] = text
        self.config.save_settings({"memos": self.memos_data})

    def check_api_configuration(self):
        try:
            self.api.authenticate()
        except Exception as e:
            print(f"인증 실패: {e}")
            UIComponents.create_api_guide(self.root, self.bg_color, self.fg_color, self.font_family, self.config, self.manual_refresh)

    def set_theme_colors(self, theme):
        self.theme = theme
        if theme == "white":
            self.bg_color = "#ffffff"; self.fg_color = "#000000"; self.cell_bg = "#f8f8f8"
            self.line_color = "#e0e0e0"; self.lunar_color = "#888888"; self.term_color = "#2ba347"
            self.sun_color = "#ff6b6b"; self.sat_color = "#4dabf7"
        else:
            self.bg_color = "#121212"; self.fg_color = "#ffffff"; self.cell_bg = "#1e1e1e"
            self.line_color = "#333333"; self.lunar_color = "#aaaaaa"; self.term_color = "#2ecc71"
            self.sun_color = "#ff6b6b"; self.sat_color = "#74b9ff"

    def setup_ui(self):
        for w in self.root.winfo_children(): w.destroy()
        
        self.header_frame = tk.Frame(self.root, bg=self.bg_color)
        self.header_frame.pack(fill="x", pady=10, padx=10)
        
        l_f = tk.Frame(self.header_frame, bg=self.bg_color); l_f.pack(side="left")
        tk.Button(l_f, text="◀", command=self.prev_view, bg=self.bg_color, fg=self.fg_color, bd=0, font=("Arial", 14)).pack(side="left", padx=5)
        self.month_label = tk.Label(l_f, text="", font=(self.font_family, 18, "bold"), fg=self.fg_color, bg=self.bg_color, width=12, cursor="hand2")
        self.month_label.pack(side="left")
        self.month_label.bind("<Button-1>", lambda e: self.open_jump_popup())
        tk.Button(l_f, text="▶", command=self.next_view, bg=self.bg_color, fg=self.fg_color, bd=0, font=("Arial", 14)).pack(side="left", padx=5)
        
        # 오늘 버튼, 보기 전환, 검색 버튼
        btn_f = tk.Frame(self.header_frame, bg=self.bg_color)
        btn_f.pack(side="left", padx=10)
        
        tk.Button(btn_f, text="오늘", command=self.go_today, bg="#1a73e8", fg="white", bd=0, font=(self.font_family, 9, "bold"), padx=10).pack(side="left", padx=2)
        
        self.view_btn = tk.Button(btn_f, text="주간 보기" if self.view_mode=="monthly" else "월간 보기", command=self.toggle_view_mode, bg="#444", fg="white", bd=0, font=(self.font_family, 9), padx=10)
        self.view_btn.pack(side="left", padx=2)
        
        tk.Button(btn_f, text="🔍 검색/목록", command=self.open_agenda, bg="#2d3436", fg="white", bd=0, font=(self.font_family, 9, "bold"), padx=10).pack(side="left", padx=2)

        self.clock_label = tk.Label(self.header_frame, text="", font=(self.font_family, 12), fg=self.fg_color, bg=self.bg_color)
        self.clock_label.pack(side="left", padx=10)
        
        tk.Button(self.header_frame, text="✖", command=self.on_exit, bg=self.bg_color, fg=self.fg_color, bd=0, font=("Arial", 14)).pack(side="right", padx=5)
        
        pin_text = "📍 고정해제" if self.is_pinned else "📌 고정하기"
        self.pin_btn = tk.Button(self.header_frame, text=pin_text, command=self.toggle_pin, bg="#555555", fg="white", bd=0, font=(self.font_family, 10))
        self.pin_btn.pack(side="right", padx=5)
        
        tk.Button(self.header_frame, text="⚙️ 설정", command=self.open_settings, bg="#444444", fg="white", bd=0, font=(self.font_family, 10)).pack(side="right", padx=5)
        
        self.grid_frame = tk.Frame(self.root, bg=self.bg_color)
        self.grid_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.update_clock()
        threading.Thread(target=self.setup_tray, daemon=True).start()

    def draw_calendar(self, year, month):
        if self.view_mode == "monthly":
            self.draw_monthly(year, month)
        else:
            self.draw_weekly()

    def draw_weekly(self):
        # 주간 보기 제목 설정 (예: 4월 1주)
        start_of_week = self.current_date - datetime.timedelta(days=(self.current_date.weekday() + 1) % 7)
        self.month_label.config(text=f"{start_of_week.month}월 {((start_of_week.day-1)//7)+1}주")
        
        for w in self.grid_frame.winfo_children(): w.destroy()
        
        days = ["일", "월", "화", "수", "목", "금", "토"]
        for c, d in enumerate(days):
            self.grid_frame.grid_columnconfigure(c, weight=1, uniform="col") 
            day_c = self.sun_color if c == 0 else self.sat_color if c == 6 else self.fg_color
            lbl = tk.Label(self.grid_frame, text=d, font=(self.font_family, 11, "bold"), fg=day_c, bg=self.bg_color)
            lbl.grid(row=0, column=c, sticky="nsew", pady=(0, 5))

        self.grid_frame.grid_rowconfigure(1, weight=1)
        now = datetime.datetime.now().date()
        
        for i in range(7):
            day_date = start_of_week + datetime.timedelta(days=i)
            target_date = day_date.strftime("%Y-%m-%d")
            
            all_hols = [h for h in self.holiday_data if target_date in h['start'].get('date', '')]
            red_hols = [h for h in all_hols if self.utils.is_red_holiday(h.get('summary', ''))]
            
            is_today = (day_date == now)
            current_cell_bg = ("#1a2a40" if self.theme == "black" else "#e3f2fd") if is_today else self.cell_bg
            border_c = "#1a73e8" if is_today else self.line_color
            border_w = 2 if is_today else 1
            day_c = self.sun_color if (i == 0 or red_hols) else self.sat_color if i == 6 else self.fg_color
            
            f = tk.Frame(self.grid_frame, bg=current_cell_bg, highlightbackground=border_c, highlightcolor=border_c, highlightthickness=border_w)
            f.grid(row=1, column=i, sticky="nsew", padx=1, pady=1)
            f.date_str = target_date
            
            h_f = tk.Frame(f, bg=current_cell_bg); h_f.pack(fill="x", padx=5, pady=2)
            h_f.date_str = target_date
            tk.Label(h_f, text=f"{day_date.day}", font=(self.font_family, self.font_size+2, "bold"), fg=day_c, bg=current_cell_bg).pack(side="left")
            
            lunar = self.utils.get_lunar_date(day_date.year, day_date.month, day_date.day)
            tk.Label(h_f, text=lunar, font=(self.font_family, max(7, self.font_size-2)), fg=self.lunar_color, bg=current_cell_bg).pack(side="right")

            for h in all_hols: 
                summary = h.get('summary', '')
                # '대체' 또는 '쉬는날'이 포함된 경우 '대체공휴일'로 변환
                if "대체" in summary or "쉬는날" in summary:
                    summary = summary.replace("공휴일", "").replace("쉬는날", "").strip()
                    if not summary.endswith("대체공휴일"): summary += " 대체공휴일"
                
                is_red = self.utils.is_red_holiday(summary)
                hol_c = "#ff6b6b" if is_red else self.lunar_color
                tk.Label(f, text=summary, font=(self.font_family, max(7, self.font_size-3)), fg=hol_c, bg=current_cell_bg).pack(anchor="w", padx=5)

            evts = [e for e in self.events_data if target_date in e.get('start', {}).get('dateTime', e.get('start', {}).get('date', ''))]
            evts = self.sort_events(evts)
            
            handler = lambda e, y=day_date.year, m=day_date.month, d=day_date.day, h=all_hols, ev=evts: self.show_day_details(y, m, d, h, ev)
            f.bind("<Button-1>", handler)

            for evt in evts[:12]:
                summary = evt.get('summary', '무제')
                is_done = summary.startswith("✅")
                evt_color = self.api.get_event_color(evt.get('colorId'))
                if is_done: evt_color = "#555555"
                
                evt_row = tk.Frame(f, bg=current_cell_bg)
                evt_row.pack(fill="x", padx=2, pady=1)
                evt_row.bind("<Button-1>", handler)

                canvas = tk.Canvas(evt_row, width=8, height=8, bg=current_cell_bg, highlightthickness=0)
                canvas.pack(side="left", padx=(2, 4))
                canvas.create_oval(1, 1, 7, 7, fill=evt_color, outline=evt_color)
                
                t = evt['start'].get('dateTime', '종일')[11:16] if 'dateTime' in evt['start'] else ""
                display_text = f"[{t}] {summary}" if t else summary
                tk.Label(evt_row, text=display_text, font=(self.font_family, max(8, self.font_size-1)), 
                         fg="#888888" if is_done else self.fg_color, bg=current_cell_bg, anchor="w").pack(side="left", fill="x")

            # 메모 기능 추가
            memo_f = tk.Frame(f, bg=current_cell_bg)
            memo_f.pack(fill="both", expand=True, padx=5, pady=(5, 5))
            
            # 구분선 (선택사항)
            line = tk.Frame(memo_f, height=1, bg=self.line_color)
            line.pack(fill="x", pady=(0, 5))

            memo_txt = tk.Text(memo_f, font=(self.font_family, max(9, self.font_size-1)), 
                               bg=current_cell_bg, fg=self.lunar_color, bd=0, 
                               insertbackground=self.fg_color, insertwidth=2,
                               highlightthickness=0, undo=True, wrap="word")
            memo_txt.pack(fill="both", expand=True)
            
            # 기존 메모 로드
            initial_memo = self.memos_data.get(target_date, "")
            if initial_memo:
                memo_txt.insert("1.0", initial_memo)
            
            # 포커스 아웃 시 자동 저장
            memo_txt.bind("<FocusOut>", lambda e, d=target_date, t=memo_txt: self.save_memo(d, t.get("1.0", "end-1c")))
            
            # 클릭 시 메모장에 포커스 (프레임 클릭 방지)
            memo_f.bind("<Button-1>", lambda e, t=memo_txt: t.focus_set())

    def toggle_view_mode(self):
        self.view_mode = "weekly" if self.view_mode == "monthly" else "monthly"
        self.view_btn.config(text="월간 보기" if self.view_mode == "weekly" else "주간 보기")
        self.update_calendar()

    def prev_view(self):
        if self.view_mode == "monthly":
            self.prev_month()
        else:
            self.current_date -= datetime.timedelta(days=7)
            self.current_year, self.current_month = self.current_date.year, self.current_date.month
            self.update_calendar()

    def next_view(self):
        if self.view_mode == "monthly":
            self.next_month()
        else:
            self.current_date += datetime.timedelta(days=7)
            self.current_year, self.current_month = self.current_date.year, self.current_date.month
            self.update_calendar()

    def open_agenda(self):
        AgendaWindow(self.root, self)

    def draw_monthly(self, year, month):
        self.month_label.config(text=f"{year}년 {month}월")
        for w in self.grid_frame.winfo_children(): w.destroy()
        
        days = ["일", "월", "화", "수", "목", "금", "토"]
        for c, d in enumerate(days):
            self.grid_frame.grid_columnconfigure(c, weight=1, uniform="col") 
            day_c = self.sun_color if c == 0 else self.sat_color if c == 6 else self.fg_color
            lbl = tk.Label(self.grid_frame, text=d, font=(self.font_family, 11, "bold"), fg=day_c, bg=self.bg_color)
            lbl.grid(row=0, column=c, sticky="nsew", pady=(0, 5))

        cal = calendar.monthcalendar(year, month)
        now = datetime.datetime.now()
        
        for r, week in enumerate(cal):
            self.grid_frame.grid_rowconfigure(r+1, weight=1) 
            for c, day in enumerate(week):
                if day == 0: continue
                target_date = f"{year}-{month:02d}-{day:02d}"
                all_hols = [h for h in self.holiday_data if target_date in h['start'].get('date', '')]
                red_hols = [h for h in all_hols if self.utils.is_red_holiday(h.get('summary', ''))]
                
                is_today = (year == now.year and month == now.month and day == now.day)
                current_cell_bg = ("#1a2a40" if self.theme == "black" else "#e3f2fd") if is_today else self.cell_bg
                border_c = "#1a73e8" if is_today else self.line_color
                border_w = 2 if is_today else 1
                day_c = self.sun_color if (c == 0 or len(red_hols) > 0) else self.sat_color if c == 6 else self.fg_color
                
                f = tk.Frame(self.grid_frame, bg=current_cell_bg, highlightbackground=border_c, highlightcolor=border_c, highlightthickness=border_w)
                f.grid(row=r+1, column=c, sticky="nsew", padx=1, pady=1)
                f.date_str = target_date
                
                h_f = tk.Frame(f, bg=current_cell_bg); h_f.pack(fill="x", padx=5, pady=2)
                h_f.date_str = target_date
                tk.Label(h_f, text=str(day), font=(self.font_family, self.font_size, "bold"), fg=day_c, bg=current_cell_bg).pack(side="left")
                tk.Label(h_f, text=self.utils.get_lunar_date(year, month, day), font=(self.font_family, max(7, self.font_size-3)), fg=self.lunar_color, bg=current_cell_bg).pack(side="right")
                
                term = self.utils.get_solar_term(year, month, day)
                if term: tk.Label(h_f, text=term, font=(self.font_family, max(7, self.font_size-3), "bold"), fg=self.term_color, bg=current_cell_bg).pack(side="right", padx=2)
                
                for h in all_hols: 
                    summary = h.get('summary', '')
                    # '대체' 또는 '쉬는날'이 포함된 경우 '대체공휴일'로 변환
                    if "대체" in summary or "쉬는날" in summary:
                        summary = summary.replace("공휴일", "").replace("쉬는날", "").strip()
                        if not summary.endswith("대체공휴일"): summary += " 대체공휴일"
                    
                    is_red = self.utils.is_red_holiday(summary)
                    hol_c = "#ff6b6b" if is_red else self.lunar_color
                    tk.Label(f, text=summary, font=(self.font_family, max(7, self.font_size-3)), fg=hol_c, bg=current_cell_bg).pack(anchor="w", padx=5)
                
                evts = [e for e in self.events_data if target_date in e.get('start', {}).get('dateTime', e.get('start', {}).get('date', ''))]
                evts = self.sort_events(evts) 
                
                handler = lambda e, y=year, m=month, d=day, h=all_hols, ev=evts: self.show_day_details(y, m, d, h, ev)
                f.bind("<Button-1>", handler)

                for evt in evts[:3]:
                    summary = evt.get('summary', '무제')
                    is_done = summary.startswith("✅")
                    color = "#888888" if is_done else self.fg_color
                    
                    # 구글 캘린더 색상 가져오기
                    evt_color = self.api.get_event_color(evt.get('colorId'))
                    if is_done: evt_color = "#555555" # 완료된 일정은 색상도 흐리게

                    # 일정 한 줄을 위한 프레임
                    evt_row = tk.Frame(f, bg=current_cell_bg)
                    evt_row.pack(fill="x", padx=2, pady=1)
                    evt_row.bind("<Button-1>", handler) # 클릭 이벤트 전파

                    # 둥근 사각형 색상 블록 (Canvas 이용)
                    canvas = tk.Canvas(evt_row, width=10, height=10, bg=current_cell_bg, highlightthickness=0)
                    canvas.pack(side="left", padx=(2, 4))
                    
                    # 둥근 사각형 그리기 (여기서는 아주 작은 원/타원으로 둥근 느낌 구현)
                    canvas.create_oval(1, 1, 9, 9, fill=evt_color, outline=evt_color)
                    canvas.bind("<Button-1>", handler)

                    tk.Label(evt_row, text=summary, font=(self.font_family, max(8, self.font_size-2)), 
                             fg=color, bg=current_cell_bg, anchor="w").pack(side="left", fill="x")

    def show_day_details(self, year, month, day, hols, evts):
        if self.detail_win_instance and self.detail_win_instance.win.winfo_exists():
            self.detail_win_instance.win.destroy()
        self.detail_win_instance = DetailWindow(self.root, year, month, day, hols, evts, self)

    def navigate_day(self, current_date_str, direction, skip_empty):
        target_dt = datetime.datetime.strptime(current_date_str, "%Y-%m-%d")
        while True:
            target_dt += datetime.timedelta(days=direction)
            y, m, d = target_dt.year, target_dt.month, target_dt.day
            if m != self.current_month or y != self.current_year:
                messagebox.showinfo("알림", "현재 달의 범위를 벗어났습니다.")
                return
            date_str = f"{y}-{m:02d}-{d:02d}"
            hols = [h for h in self.holiday_data if date_str in h['start'].get('date', '')]
            evts = [e for e in self.events_data if date_str in e.get('start', {}).get('dateTime', e.get('start', {}).get('date', ''))]
            if not skip_empty or (hols or evts): break
        self.show_day_details(y, m, d, hols, evts)

    def sort_events(self, evts):
        orders = self.config.settings.get("event_orders", {})
        return sorted(evts, key=lambda e: (orders.get(e['id'], 999), e['start'].get('dateTime', e['start'].get('date', ''))))

    def on_drag_start(self, event, event_data):
        self._drag_data = {"event_data": event_data}

    def on_drag_stop(self, event):
        if not self._drag_data: return
        
        # 마우스 위치의 위젯 찾기
        x, y_root = event.x_root, event.y_root
        target_widget = self.root.winfo_containing(x, y_root)
        
        # 위젯을 타고 올라가며 date_str 속성이 있는 프레임 찾기
        target_date = None
        curr = target_widget
        while curr:
            if hasattr(curr, 'date_str'):
                target_date = curr.date_str
                break
            if hasattr(curr, 'master'):
                curr = curr.master
            else:
                break
            
        if target_date:
            event_data = self._drag_data["event_data"]
            if messagebox.askyesno("일정 이동", f"'{event_data.get('summary')}' 일정을 {target_date}로 이동하시겠습니까?"):
                self.move_event_to_date(event_data, target_date)
        
        self._drag_data = None

    def move_event_to_date(self, event_data, target_date):
        body = {}
        start = event_data['start']
        end = event_data['end']
        
        if 'date' in start:
            # 종일 일정
            body['start'] = {'date': target_date}
            target_dt = datetime.datetime.strptime(target_date, "%Y-%m-%d")
            end_dt = target_dt + datetime.timedelta(days=1)
            body['end'] = {'date': end_dt.strftime("%Y-%m-%d")}
        else:
            # 시간 지정 일정
            orig_start = start['dateTime']
            orig_end = end['dateTime']
            time_part_start = orig_start.split('T')[1]
            
            # 종료일 계산 (시작일과 종료일의 차이 유지)
            # ISO format handling (Z or timezone offset)
            def parse_iso(dt_str):
                return datetime.datetime.fromisoformat(dt_str.replace('Z', '+00:00'))

            orig_start_dt = parse_iso(orig_start)
            orig_end_dt = parse_iso(orig_end)
            delta = orig_end_dt - orig_start_dt
            
            # 새 시작 시간 (타겟 날짜 + 원본 시간)
            # time_part_start might have timezone info like +09:00
            new_start_str = f"{target_date}T{time_part_start}"
            new_start_dt = parse_iso(new_start_str)
            new_end_dt = new_start_dt + delta
            
            body['start'] = {'dateTime': new_start_dt.isoformat(), 'timeZone': 'Asia/Seoul'}
            body['end'] = {'dateTime': new_end_dt.isoformat(), 'timeZone': 'Asia/Seoul'}

        try:
            self.api.patch_event(event_data['id'], body)
            self.manual_refresh()
            if self.detail_win_instance:
                self.detail_win_instance.win.destroy()
        except Exception as e:
            messagebox.showerror("오류", f"일정 이동 중 오류 발생: {e}")

    def toggle_complete(self, event):
        summary = event.get('summary', '')
        new_summary = summary.replace("✅ ", "", 1) if summary.startswith("✅ ") else "✅ " + summary
        try:
            self.api.patch_event(event['id'], {'summary': new_summary})
            self.manual_refresh()
        except Exception as e: messagebox.showerror("오류", str(e))

    def delete_event_with_win(self, event_id, win, event_data=None):
        recurring_id = event_data.get('recurringEventId') if event_data else None
        
        if recurring_id:
            # 반복 일정인 경우 선택 팝업
            ask_win = tk.Toplevel(self.root)
            ask_win.title("반복 일정 삭제")
            ask_win.geometry("300x180")
            ask_win.attributes("-topmost", True)
            ask_win.configure(bg=self.bg_color, padx=20, pady=20)
            
            tk.Label(ask_win, text="이 일정은 반복되는 일정입니다.", fg=self.fg_color, bg=self.bg_color).pack(pady=10)
            
            def delete_one():
                try:
                    self.api.delete_event(event_id)
                    ask_win.destroy()
                    win.destroy()
                    self.manual_refresh()
                except Exception as e: messagebox.showerror("오류", str(e))

            def delete_all():
                try:
                    self.api.delete_event(recurring_id)
                    ask_win.destroy()
                    win.destroy()
                    self.manual_refresh()
                except Exception as e: messagebox.showerror("오류", str(e))

            tk.Button(ask_win, text="이 일정만 삭제", command=delete_one, bg="#555", fg="white").pack(fill="x", pady=2)
            tk.Button(ask_win, text="모든 반복 일정 삭제", command=delete_all, bg="#ff4757", fg="white").pack(fill="x", pady=2)
            tk.Button(ask_win, text="취소", command=ask_win.destroy, bg="#333", fg="white").pack(fill="x", pady=2)
            
        else:
            if messagebox.askyesno("삭제 확인", "삭제하시겠습니까?"):
                try:
                    self.api.delete_event(event_id)
                    win.destroy()
                    self.manual_refresh()
                except Exception as e: messagebox.showerror("오류", str(e))

    def add_event_popup_with_win(self, date_str, win):
        win.destroy()
        EventPopup(self.root, self, date_str)

    def edit_event_popup_with_win(self, event, date_str, win):
        win.destroy()
        EventPopup(self.root, self, date_str, event)

    def fetch_events_thread(self, year, month):
        self.events_data, self.holiday_data = self.api.fetch_events(year, month)
        self.root.after(0, lambda: self.draw_calendar(year, month))

    def update_calendar(self): 
        if self.month_label: self.month_label.config(text="⏳ 로딩 중...")
        threading.Thread(target=self.fetch_events_thread, args=(self.current_year, self.current_month), daemon=True).start()

    def manual_refresh(self): self.update_calendar()
    def auto_sync(self): self.update_calendar(); self.root.after(600000, self.auto_sync)
    def toggle_pin(self): self.is_pinned = not self.is_pinned; self.pin_btn.config(text="📍 고정해제" if self.is_pinned else "📌 고정하기"); self.save_settings()
    def on_exit(self): 
        self.save_settings()
        if self.tray_icon: self.tray_icon.stop()
        self.root.destroy()

    def update_clock(self):
        now = datetime.datetime.now()
        self.clock_label.config(text=now.strftime("%H:%M:%S"))
        self.root.after(1000, self.update_clock)

    def go_today(self):
        now = datetime.datetime.now()
        self.current_year = now.year
        self.current_month = now.month
        self.update_calendar()

    def setup_tray(self):
        menu = (item('보이기', self.show_window), item('종료', self.on_exit))
        self.tray_icon = pystray.Icon("calendar_widget", self.create_tray_image(), "Calendar Widget", menu)
        self.tray_icon.run()

    def create_tray_image(self):
        width = 64; height = 64
        image = Image.new('RGB', (width, height), color=(30, 30, 30))
        dc = ImageDraw.Draw(image)
        dc.rectangle([10, 10, 54, 54], fill=(26, 115, 232))
        dc.text((15, 15), "CAL", fill=(255, 255, 255))
        return image

    def show_window(self):
        self.root.after(0, self.root.deiconify)
        self.root.after(0, lambda: self.root.attributes("-topmost", True))
        self.root.after(10, lambda: self.root.attributes("-topmost", False))

    def save_settings(self): 
        self.config.save_settings({
            "geometry": self.root.winfo_geometry(), 
            "alpha": self.alpha_val, 
            "theme": self.theme, 
            "font_family": self.font_family, 
            "font_size": self.font_size, 
            "is_pinned": self.is_pinned,
            "memos": self.memos_data
        })
    
    def on_press(self, e):
        if self.is_pinned: return
        self._offsetx, self._offsety = e.x, e.y
        self.resizing = (e.x > self.root.winfo_width()-20 and e.y > self.root.winfo_height()-20)
    def on_motion(self, e):
        if self.is_pinned: return
        if self.resizing: self.root.geometry(f"{max(600, e.x)}x{max(400, e.y)}")
        else: self.root.geometry(f"+{self.root.winfo_x()+(e.x-self._offsetx)}+{self.root.winfo_y()+(e.y-self._offsety)}")
    def check_cursor_edge(self, e):
        if self.is_pinned: self.root.config(cursor=""); return
        self.root.config(cursor="size_nw_se" if (e.x > self.root.winfo_width()-20 and e.y > self.root.winfo_height()-20) else "")
    def on_resize(self, e):
        if e.widget == self.root: self.draw_calendar(self.current_year, self.current_month)
    def prev_month(self): 
        self.current_month=12 if self.current_month==1 else self.current_month-1
        self.current_year-=(1 if self.current_month==12 else 0)
        self.update_calendar()
    def next_month(self): 
        self.current_month=1 if self.current_month==12 else self.current_month+1
        self.current_year+=(1 if self.current_month==1 else 0)
        self.update_calendar()

    def open_jump_popup(self):
        jump_win = tk.Toplevel(self.root)
        jump_win.title("날짜 이동")
        jump_win.geometry("250x150")
        jump_win.attributes("-topmost", True)
        jump_win.configure(bg=self.bg_color, padx=20, pady=20)
        
        f = tk.Frame(jump_win, bg=self.bg_color)
        f.pack(pady=10)
        
        y_ent = tk.Entry(f, width=6, font=(self.font_family, 12)); y_ent.pack(side="left", padx=2)
        y_ent.insert(0, str(self.current_year))
        tk.Label(f, text="년", bg=self.bg_color, fg=self.fg_color).pack(side="left", padx=2)
        
        m_ent = tk.Entry(f, width=4, font=(self.font_family, 12)); m_ent.pack(side="left", padx=2)
        m_ent.insert(0, str(self.current_month))
        tk.Label(f, text="월", bg=self.bg_color, fg=self.fg_color).pack(side="left", padx=2)
        
        def do_jump():
            try:
                y, m = int(y_ent.get()), int(m_ent.get())
                if 1900 <= y <= 2100 and 1 <= m <= 12:
                    self.current_year, self.current_month = y, m
                    self.current_date = datetime.date(y, m, 1)
                    self.update_calendar()
                    jump_win.destroy()
                else: raise ValueError
            except: messagebox.showerror("오류", "올바른 연도(1900-2100)와 월(1-12)을 입력하세요.")

        tk.Button(jump_win, text="이동", command=do_jump, bg="#1a73e8", fg="white", padx=20).pack(pady=10)
        y_ent.focus_set()
        jump_win.bind("<Return>", lambda e: do_jump())

    def open_settings(self): 
        if self.settings_win_instance and self.settings_win_instance.win.winfo_exists():
            self.settings_win_instance.win.destroy()
        self.settings_win_instance = SettingsWindow(self.root, self)

if __name__ == '__main__':
    root = tk.Tk()
    app = GridCalendarApp(root)
    root.mainloop()
