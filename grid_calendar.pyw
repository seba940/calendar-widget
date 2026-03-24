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

from google_calendar_api import GoogleCalendarAPI
from calendar_utils import CalendarUtils
from config_manager import ConfigManager
from ui_components import UIComponents, DetailWindow

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
        self._drag_data = None
        self._event_widgets = []
        
        self.alpha_val = self.config.settings.get("alpha", 0.85)
        self.theme = self.config.settings.get("theme", "black")
        self.font_family = self.config.settings.get("font_family", "Malgun Gothic").lstrip("@")
        self.font_size = self.config.settings.get("font_size", 10)
        self.is_pinned = self.config.settings.get("is_pinned", False)
        
        self.set_theme_colors(self.theme)
        self.root.geometry(self.config.settings.get("geometry", "1000x800+100+100"))
        self.root.attributes("-alpha", self.alpha_val)
        self.root.configure(bg=self.bg_color)

        self.current_year = datetime.datetime.now().year
        self.current_month = datetime.datetime.now().month
        self._offsetx = 0; self._offsety = 0; self.resizing = False
        self.events_data = []; self.holiday_data = []

        self.root.bind("<ButtonPress-1>", self.on_press)
        self.root.bind("<B1-Motion>", self.on_motion)
        self.root.bind("<Motion>", self.check_cursor_edge)
        self.root.bind("<Configure>", self.on_resize)

        self.check_api_configuration()
        self.setup_ui()
        self.auto_sync()

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

    def draw_calendar(self, year, month):
        self.month_label.config(text=f"{year}년 {month}월")
        for w in self.grid_frame.winfo_children(): w.destroy()
        
        days = ["일", "월", "화", "수", "목", "금", "토"]
        for c, d in enumerate(days):
            self.grid_frame.grid_columnconfigure(c, weight=1, uniform="col") 
            day_c = "#ff6b6b" if c == 0 else "#74b9ff" if c == 6 else self.fg_color
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
                day_c = "#ff6b6b" if (c == 0 or len(red_hols) > 0) else "#74b9ff" if c == 6 else self.fg_color
                
                f = tk.Frame(self.grid_frame, bg=current_cell_bg, highlightbackground=border_c, highlightcolor=border_c, highlightthickness=border_w)
                f.grid(row=r+1, column=c, sticky="nsew", padx=1, pady=1)
                
                h_f = tk.Frame(f, bg=current_cell_bg); h_f.pack(fill="x", padx=5, pady=2)
                tk.Label(h_f, text=str(day), font=(self.font_family, self.font_size, "bold"), fg=day_c, bg=current_cell_bg).pack(side="left")
                tk.Label(h_f, text=self.utils.get_lunar_date(year, month, day), font=(self.font_family, max(7, self.font_size-3)), fg=self.lunar_color, bg=current_cell_bg).pack(side="right")
                
                term = self.utils.get_solar_term(year, month, day)
                if term: tk.Label(h_f, text=term, font=(self.font_family, max(7, self.font_size-3), "bold"), fg=self.term_color, bg=current_cell_bg).pack(side="right", padx=2)
                
                for h in all_hols: 
                    summary = h.get('summary', '')
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
                    tk.Label(f, text=f"• {summary}", font=(self.font_family, max(8, self.font_size-2)), fg=color, bg=current_cell_bg, anchor="w").pack(fill="x", padx=2)

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

    def on_drag_stop(self, event, y, m, d, hols):
        if not self._drag_data: return
        # 드래그 앤 드롭 정렬 로직은 DetailWindow와 연계하여 구현
        self._drag_data = None

    def toggle_complete(self, event):
        summary = event.get('summary', '')
        new_summary = summary.replace("✅ ", "", 1) if summary.startswith("✅ ") else "✅ " + summary
        try:
            self.api.patch_event(event['id'], {'summary': new_summary})
            self.manual_refresh()
        except Exception as e: messagebox.showerror("오류", str(e))

    def delete_event_with_win(self, event_id, win):
        if messagebox.askyesno("삭제 확인", "삭제하시겠습니까?"):
            try:
                self.api.delete_event(event_id)
                win.destroy()
                self.manual_refresh()
            except Exception as e: messagebox.showerror("오류", str(e))

    def add_event_popup_with_win(self, date_str, win):
        # 팝업 UI는 ui_components로 분리 가능 (현재는 기존 로직 유지 가능)
        win.destroy()
        # ... (이하 생략 - 상세 UI는 필요시 추가 모듈화)

    def edit_event_popup_with_win(self, event, date_str, win):
        win.destroy()
        # ...

    def fetch_events_thread(self, year, month):
        self.events_data, self.holiday_data = self.api.fetch_events(year, month)
        self.root.after(0, lambda: self.draw_calendar(year, month))

    def update_calendar(self): 
        if self.month_label: self.month_label.config(text="⏳ 로딩 중...")
        threading.Thread(target=self.fetch_events_thread, args=(self.current_year, self.current_month), daemon=True).start()

    def manual_refresh(self): self.update_calendar()
    def auto_sync(self): self.update_calendar(); self.root.after(600000, self.auto_sync)
    def toggle_pin(self): self.is_pinned = not self.is_pinned; self.pin_btn.config(text="📍 고정해제" if self.is_pinned else "📌 고정하기"); self.save_settings()
    def on_exit(self): self.save_settings(); self.root.destroy()
    def save_settings(self): self.config.save_settings({"geometry": self.root.winfo_geometry(), "alpha": self.alpha_val, "theme": self.theme, "font_family": self.font_family, "font_size": self.font_size, "is_pinned": self.is_pinned})
    
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
    def prev_month(self): self.current_month=12 if self.current_month==1 else self.current_month-1; self.current_year-=(1 if self.current_month==12 else 0); self.update_calendar()
    def next_month(self): self.current_month=1 if self.current_month==12 else self.current_month+1; self.current_year+=(1 if self.current_month==1 else 0); self.update_calendar()
    def open_settings(self): pass # 설정 UI 모듈화 예정

if __name__ == '__main__':
    root = tk.Tk()
    app = GridCalendarApp(root)
    root.mainloop()
