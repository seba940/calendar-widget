import datetime
import calendar
import json
import re
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
from ui_components import UIComponents, DetailWindow, EventPopup
from ui_popups import SettingsWindow, AgendaWindow
from ui_map_components import LocationSearchPopup

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

# --- 모니터마다 배율(DPI)이 다른 듀얼 모니터 환경에서, DPI 인식을 안 하면 윈도우가
#     좌표를 가상으로 변환해서 창이 모니터 경계 근처에 있을 때 버튼 클릭이 어긋나거나
#     안 먹는 문제가 생길 수 있어 이를 방지합니다. (이 설정을 반드시 mainloop 시작 전에 해야 함)
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

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
        fixed_geometry = self._safe_geometry(self.config.settings.get("geometry", "1000x800+100+100"))
        self.root.geometry(fixed_geometry)
        if getattr(self, "_geometry_was_fixed", False):
            if self.is_pinned:
                # 위치를 강제로 보정한 경우, 고정 상태였다면 사용자가 다시 옮길 수 있도록 고정을 풀어줍니다.
                self.is_pinned = False
            # winfo_geometry()는 창이 아직 화면에 그려지기 전이라 "1x1+0+0" 같은 값을 줄 수 있어서,
            # 방금 계산한 보정값을 그대로 저장합니다 (실제 창 렌더링을 기다리지 않음).
            self.config.save_settings({"geometry": fixed_geometry, "is_pinned": self.is_pinned})
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

    def _get_monitor_rects(self):
        """윈도우에 연결된 각 모니터의 (left, top, right, bottom) 목록을 반환합니다. 실패하면 빈 리스트."""
        try:
            import ctypes
            from ctypes import wintypes
            rects = []
            MonitorEnumProc = ctypes.WINFUNCTYPE(
                ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong,
                ctypes.POINTER(wintypes.RECT), ctypes.c_double
            )
            def _cb(hMonitor, hdcMonitor, lprcMonitor, dwData):
                r = lprcMonitor.contents
                rects.append((r.left, r.top, r.right, r.bottom))
                return 1
            ctypes.windll.user32.EnumDisplayMonitors(0, 0, MonitorEnumProc(_cb), 0)
            return rects
        except Exception:
            return []

    def _safe_geometry(self, geometry_str):
        """저장된 창 위치가 화면 밖이거나 두 모니터 경계에 걸쳐 있으면(버튼 클릭 불가 등) 기본 위치로 보정합니다."""
        m = re.match(r'(\d+)x(\d+)([+-])(-?\d+)([+-])(-?\d+)', geometry_str)
        if not m:
            self._geometry_was_fixed = True
            return "1000x800+100+100"
        w, h, xs, x, ys, y = m.groups()
        w, h = int(w), int(h)
        x = int(x) if xs == "+" else -int(x)
        y = int(y) if ys == "+" else -int(y)

        self._geometry_was_fixed = False
        if w < 400 or h < 300:
            # 창이 비정상적으로 찌그러든 크기로 저장된 경우(예: 렌더링 전에 저장됨) 기본 크기로 되돌림
            w, h = 1000, 800
            self._geometry_was_fixed = True
        monitors = self._get_monitor_rects()
        if monitors:
            # 창 전체가 어느 한 모니터 안에 완전히 들어가는지 확인 (모니터 경계에 걸치면 클릭이 안 먹는 경우가 있음)
            fits = any(x >= mon[0] and y >= mon[1] and x + w <= mon[2] and y + h <= mon[3] for mon in monitors)
            if not fits:
                primary = min(monitors, key=lambda mon: (mon[0], mon[1]))  # (0,0)에 가장 가까운 모니터를 기본으로 사용
                x, y = primary[0] + 100, primary[1] + 100
                w = min(w, (primary[2] - primary[0]) - 200)
                h = min(h, (primary[3] - primary[1]) - 200)
                self._geometry_was_fixed = True
        else:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            if x < 0 or y < 0 or x > sw - 100 or y > sh - 100:
                x, y = 100, 100
                self._geometry_was_fixed = True

        return f"{w}x{h}+{x}+{y}"

    def get_display_color(self, evt):
        """이 앱에서만 저장된 사용자 지정 색(있으면 우선)을 적용하고, 없으면 구글 캘린더 색상을 사용합니다."""
        custom = self.config.settings.get("custom_event_colors", {}).get(evt.get('id'))
        if custom:
            return custom
        return self.api.get_event_color(evt.get('colorId'))

    def _event_date_range(self, e):
        """이벤트의 시작일과 (배타적) 종료일을 date 객체로 반환합니다. 하루짜리 일정도 동일한 규칙을 따릅니다."""
        start = e.get('start', {}) or {}
        end = e.get('end', {}) or {}
        try:
            if 'date' in start:
                s = datetime.datetime.strptime(start['date'], '%Y-%m-%d').date()
                en = datetime.datetime.strptime(end.get('date', start['date']), '%Y-%m-%d').date()
            else:
                s_dt = start.get('dateTime', '')
                e_dt = end.get('dateTime', s_dt)
                s = datetime.datetime.fromisoformat(s_dt.replace('Z', '+00:00')).date()
                en_date = datetime.datetime.fromisoformat(e_dt.replace('Z', '+00:00')).date() if e_dt else s
                en = en_date + datetime.timedelta(days=1)
            if en <= s:
                en = s + datetime.timedelta(days=1)
            return s, en
        except Exception:
            today = datetime.date.today()
            return today, today + datetime.timedelta(days=1)

    def _is_multiday(self, e):
        s, en = self._event_date_range(e)
        return (en - s).days > 1

    def _events_for_date(self, target_date):
        """dateTime/date 시작값 문자열 비교 대신, 실제 날짜 범위를 기준으로 그 날짜에 걸쳐있는 일정을 모두 반환합니다."""
        try:
            d = datetime.datetime.strptime(target_date, "%Y-%m-%d").date()
        except Exception:
            return []
        result = []
        for e in self.events_data:
            s, en = self._event_date_range(e)
            if s <= d < en:
                result.append(e)
        return result

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
        
        tk.Button(btn_f, text="🔄 새로고침", command=self.manual_refresh, bg="#2d3436", fg="white", bd=0, font=(self.font_family, 9, "bold"), padx=10).pack(side="left", padx=2)
        
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
            
            evts = self._events_for_date(target_date)
            evts = self.sort_events(evts)
            handler = lambda e, y=day_date.year, m=day_date.month, d=day_date.day, h=all_hols, ev=evts: self.show_day_details(y, m, d, h, ev)

            f = tk.Frame(self.grid_frame, bg=current_cell_bg, highlightbackground=border_c, highlightcolor=border_c, highlightthickness=border_w)
            f.grid(row=1, column=i, sticky="nsew", padx=1, pady=1)
            f.date_str = target_date
            f.bind("<Button-1>", handler)

            h_f = tk.Frame(f, bg=current_cell_bg); h_f.pack(fill="x", padx=5, pady=2)
            h_f.date_str = target_date
            h_f.bind("<Button-1>", handler)
            day_lbl = tk.Label(h_f, text=f"{day_date.day}", font=(self.font_family, self.font_size+2, "bold"), fg=day_c, bg=current_cell_bg)
            day_lbl.pack(side="left")
            day_lbl.bind("<Button-1>", handler)

            lunar = self.utils.get_lunar_date(day_date.year, day_date.month, day_date.day)
            lunar_lbl = tk.Label(h_f, text=lunar, font=(self.font_family, max(7, self.font_size-2)), fg=self.lunar_color, bg=current_cell_bg)
            lunar_lbl.pack(side="right")
            lunar_lbl.bind("<Button-1>", handler)

            for h in all_hols:
                summary = h.get('summary', '')
                # '대체' 또는 '쉬는날'이 포함된 경우 '대체공휴일'로 변환
                if "대체" in summary or "쉬는날" in summary:
                    summary = summary.replace("공휴일", "").replace("쉬는날", "").strip()
                    if not summary.endswith("대체공휴일"): summary += " 대체공휴일"

                is_red = self.utils.is_red_holiday(summary)
                hol_c = "#ff6b6b" if is_red else self.lunar_color
                hol_lbl = tk.Label(f, text=summary, font=(self.font_family, max(7, self.font_size-3)), fg=hol_c, bg=current_cell_bg)
                hol_lbl.pack(anchor="w", padx=5)
                hol_lbl.bind("<Button-1>", handler)

            for evt in evts[:12]:
                summary = evt.get('summary', '무제')
                is_done = summary.startswith("✅")
                evt_color = self.get_display_color(evt)
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
        multiday_events = [e for e in self.events_data if self._is_multiday(e)]

        for r, week in enumerate(cal):
            self.grid_frame.grid_rowconfigure(r+1, weight=1)

            # 이번 주에 걸쳐있는 여러 날짜짜리 일정의 막대 구간과 레인(줄) 계산
            week_bars = []
            for e in multiday_events:
                s, en = self._event_date_range(e)
                cols = [c for c, d in enumerate(week) if d != 0 and s <= datetime.date(year, month, d) < en]
                if not cols:
                    continue
                sc, ec = min(cols), max(cols)
                last_day = en - datetime.timedelta(days=1)
                week_bars.append({
                    'evt': e, 'sc': sc, 'ec': ec,
                    'start': (s.year == year and s.month == month and week[sc] == s.day),
                    'end': (last_day.year == year and last_day.month == month and week[ec] == last_day.day),
                })
            week_bars.sort(key=lambda b: (b['sc'], -(b['ec'] - b['sc'])))
            lanes = []
            for b in week_bars:
                for li, occupied in enumerate(lanes):
                    if all(b['ec'] < os_ or b['sc'] > oe for os_, oe in occupied):
                        occupied.append((b['sc'], b['ec']))
                        b['lane'] = li
                        break
                else:
                    lanes.append([(b['sc'], b['ec'])])
                    b['lane'] = len(lanes) - 1
            num_lanes = len(lanes)

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
                
                all_evts = self.sort_events(self._events_for_date(target_date))
                evts = [e for e in all_evts if not self._is_multiday(e)]  # 여러 날짜 일정은 막대로 별도 표시
                handler = lambda e, y=year, m=month, d=day, h=all_hols, ev=all_evts: self.show_day_details(y, m, d, h, ev)

                f = tk.Frame(self.grid_frame, bg=current_cell_bg, highlightbackground=border_c, highlightcolor=border_c, highlightthickness=border_w)
                f.grid(row=r+1, column=c, sticky="nsew", padx=1, pady=1)
                f.date_str = target_date
                f.bind("<Button-1>", handler)

                h_f = tk.Frame(f, bg=current_cell_bg); h_f.pack(fill="x", padx=5, pady=2)
                h_f.date_str = target_date
                h_f.bind("<Button-1>", handler)
                day_lbl = tk.Label(h_f, text=str(day), font=(self.font_family, self.font_size, "bold"), fg=day_c, bg=current_cell_bg)
                day_lbl.pack(side="left")
                day_lbl.bind("<Button-1>", handler)
                lunar_lbl = tk.Label(h_f, text=self.utils.get_lunar_date(year, month, day), font=(self.font_family, max(7, self.font_size-3)), fg=self.lunar_color, bg=current_cell_bg)
                lunar_lbl.pack(side="right")
                lunar_lbl.bind("<Button-1>", handler)

                term = self.utils.get_solar_term(year, month, day)
                if term:
                    term_lbl = tk.Label(h_f, text=term, font=(self.font_family, max(7, self.font_size-3), "bold"), fg=self.term_color, bg=current_cell_bg)
                    term_lbl.pack(side="right", padx=2)
                    term_lbl.bind("<Button-1>", handler)

                for h in all_hols:
                    summary = h.get('summary', '')
                    # '대체' 또는 '쉬는날'이 포함된 경우 '대체공휴일'로 변환
                    if "대체" in summary or "쉬는날" in summary:
                        summary = summary.replace("공휴일", "").replace("쉬는날", "").strip()
                        if not summary.endswith("대체공휴일"): summary += " 대체공휴일"

                    is_red = self.utils.is_red_holiday(summary)
                    hol_c = "#ff6b6b" if is_red else self.lunar_color
                    hol_lbl = tk.Label(f, text=summary, font=(self.font_family, max(7, self.font_size-3)), fg=hol_c, bg=current_cell_bg)
                    hol_lbl.pack(anchor="w", padx=5)
                    hol_lbl.bind("<Button-1>", handler)

                # 여러 날짜에 걸친 일정을 이어지는 막대로 표시
                for lane_i in range(num_lanes):
                    bar_holder = tk.Frame(f, bg=current_cell_bg, height=16)
                    bar_holder.pack(fill="x", padx=0, pady=(1, 0))
                    bar_holder.pack_propagate(False)
                    match = next((b for b in week_bars if b['lane'] == lane_i and b['sc'] <= c <= b['ec']), None)
                    if not match:
                        continue
                    evt = match['evt']
                    summary = evt.get('summary', '무제')
                    is_done = summary.startswith("✅")
                    evt_color = "#555555" if is_done else self.get_display_color(evt)
                    bar = tk.Frame(bar_holder, bg=evt_color, cursor="hand2")
                    bar.pack(fill="both", expand=True,
                             padx=(3 if match['start'] else 0, 3 if match['end'] else 0))
                    if c == match['sc']:
                        prefix = "" if match['start'] else "◀ "
                        tk.Label(bar, text=f"{prefix}{summary}", font=(self.font_family, max(7, self.font_size - 4)),
                                 fg="white", bg=evt_color, anchor="w").pack(side="left", fill="x", padx=4)
                    bar.bind("<Button-1>", handler)
                    for ch in bar.winfo_children(): ch.bind("<Button-1>", handler)

                for evt in evts[:3]:
                    summary = evt.get('summary', '무제')
                    is_done = summary.startswith("✅")
                    color = "#888888" if is_done else self.fg_color
                    
                    # 색상 가져오기 (사용자 지정 로컬 색 우선, 없으면 구글 캘린더 색상)
                    evt_color = self.get_display_color(evt)
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
            evts = self._events_for_date(date_str)
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
        events, holidays = self.api.fetch_events(year, month)
        # None이면 API 완전 실패 → 기존 데이터를 지우지 않고 유지
        if events is not None:
            self.events_data = events
        if holidays is not None:
            self.holiday_data = holidays
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
        menu = (
            item('보이기', self.show_window),
            item('위치 초기화 (화면 왼쪽 위로)', self.reset_position),
            item('고정 해제/고정', self.tray_toggle_pin),
            item('종료', self.on_exit),
        )
        self.tray_icon = pystray.Icon("calendar_widget", self.create_tray_image(), "Calendar Widget", menu)
        self.tray_icon.run()

    def reset_position(self):
        """창이 화면 밖이나 모니터 경계에 걸려 조작할 수 없을 때, 트레이 메뉴에서 강제로 위치를 되돌립니다."""
        def _do():
            w = self.root.winfo_width() or 1000
            h = self.root.winfo_height() or 800
            self.root.geometry(f"{w}x{h}+100+100")
            self.root.deiconify()
            self.root.attributes("-topmost", True)
            self.root.after(10, lambda: self.root.attributes("-topmost", False))
            self.save_settings()
        self.root.after(0, _do)

    def tray_toggle_pin(self):
        self.root.after(0, self.toggle_pin)

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
