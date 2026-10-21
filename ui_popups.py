import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.font as tkfont
import urllib.parse
import webbrowser
import os
import sys
import subprocess
import datetime

class SettingsWindow:
    def __init__(self, parent, app):
        self.app = app
        self.win = tk.Toplevel(parent)
        self.win.title("설정")
        self.win.geometry("400x500")
        self.win.attributes("-topmost", True)
        self.win.configure(bg=app.bg_color, padx=30, pady=30)
        
        tk.Label(self.win, text="⚙️ 프로그램 설정", font=(app.font_family, 14, "bold"), bg=app.bg_color, fg=app.fg_color).pack(pady=(0, 20))

        # 테마 설정
        tk.Label(self.win, text="🎨 테마", font=(app.font_family, 10, "bold"), bg=app.bg_color, fg=app.fg_color).pack(anchor="w")
        self.theme_var = tk.StringVar(value=app.theme)
        theme_frame = tk.Frame(self.win, bg=app.bg_color)
        theme_frame.pack(fill="x", pady=(5, 15))
        tk.Radiobutton(theme_frame, text="Black", variable=self.theme_var, value="black", bg=app.bg_color, fg=app.fg_color, selectcolor="#444").pack(side="left")
        tk.Radiobutton(theme_frame, text="White", variable=self.theme_var, value="white", bg=app.bg_color, fg=app.fg_color, selectcolor="#ddd").pack(side="left", padx=10)

        # 투명도 설정
        tk.Label(self.win, text="🌓 투명도", font=(app.font_family, 10, "bold"), bg=app.bg_color, fg=app.fg_color).pack(anchor="w")
        self.alpha_scale = tk.Scale(self.win, from_=0.1, to=1.0, resolution=0.05, orient="horizontal", bg=app.bg_color, fg=app.fg_color, highlightthickness=0)
        self.alpha_scale.set(app.alpha_val)
        self.alpha_scale.pack(fill="x", pady=(5, 15))

        # 폰트 설정
        tk.Label(self.win, text="🔡 폰트", font=(app.font_family, 10, "bold"), bg=app.bg_color, fg=app.fg_color).pack(anchor="w")
        font_families = sorted({f for f in tkfont.families() if not f.startswith("@")}, key=str.lower)
        self.font_var = tk.StringVar(value=app.font_family)
        self.font_combo = ttk.Combobox(self.win, textvariable=self.font_var, values=font_families, state="readonly", font=(app.font_family, 10))
        self.font_combo.pack(fill="x", pady=(5, 15))
        if app.font_family in font_families:
            self.font_combo.set(app.font_family)

        # 폰트 크기 설정
        tk.Label(self.win, text="📏 폰트 크기", font=(app.font_family, 10, "bold"), bg=app.bg_color, fg=app.fg_color).pack(anchor="w")
        self.size_ent = tk.Entry(self.win, font=(app.font_family, 10))
        self.size_ent.pack(fill="x", pady=(5, 20))
        self.size_ent.insert(0, str(app.font_size))

        btn_frame = tk.Frame(self.win, bg=app.bg_color)
        btn_frame.pack(fill="x", pady=(10, 0))

        tk.Button(btn_frame, text="✅ 적용 및 저장", command=self.save_settings, bg="#1a73e8", fg="white", font=(app.font_family, 10, "bold"), pady=8).pack(side="left", expand=True, fill="x", padx=(0, 5))
        tk.Button(btn_frame, text="❌ 취소", command=self.win.destroy, bg="#555555", fg="white", font=(app.font_family, 10), pady=8).pack(side="left", expand=True, fill="x", padx=(5, 0))

        tk.Button(self.win, text="🔄 앱 재시작", command=self.restart_app,
                  bg="#f39c12", fg="white", font=(app.font_family, 10, "bold"), pady=8,
                  cursor="hand2").pack(fill="x", pady=(8, 0))

    def save_settings(self):
        try:
            new_theme = self.theme_var.get()
            new_alpha = float(self.alpha_scale.get())
            new_font = self.font_var.get().strip()
            new_size = int(self.size_ent.get().strip())

            self.app.theme = new_theme
            self.app.alpha_val = new_alpha
            self.app.font_family = new_font
            self.app.font_size = new_size

            self.app.set_theme_colors(new_theme)
            self.app.root.attributes("-alpha", new_alpha)
            self.app.root.configure(bg=self.app.bg_color)

            self.app.save_settings()
            self.app.setup_ui()
            self.app.manual_refresh()

            messagebox.showinfo("알림", "설정이 저장되었습니다.")
            self.win.destroy()
        except Exception as e:
            messagebox.showerror("오류", f"설정 저장 중 오류 발생: {e}")

    def restart_app(self):
        if not messagebox.askyesno("앱 재시작", "앱을 재시작할까요?\n저장되지 않은 변경사항은 사라집니다."):
            return
        try:
            script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            bat_file = os.path.join(script_dir, "run_calendar.bat")
            if os.path.exists(bat_file):
                subprocess.Popen(
                    ["cmd", "/c", bat_file],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                    cwd=script_dir
                )
            else:
                subprocess.Popen([sys.executable] + sys.argv, cwd=script_dir)
            self.app.root.after(800, self.app.root.destroy)
        except Exception as e:
            messagebox.showerror("오류", f"재시작 중 오류 발생: {e}")

class AgendaWindow:
    def __init__(self, parent, app):
        self.app = app
        self.win = tk.Toplevel(parent)
        self.win.title("일정 검색 및 목록")
        self.win.geometry("500x600")
        self.win.attributes("-topmost", True)
        self.win.configure(bg=app.bg_color, padx=20, pady=20)
        
        tk.Label(self.win, text="🔍 일정 검색 및 목록", font=(app.font_family, 16, "bold"), bg=app.bg_color, fg=app.fg_color).pack(pady=(0, 15))

        # 검색창
        search_frame = tk.Frame(self.win, bg=app.bg_color)
        search_frame.pack(fill="x", pady=(0, 15))
        
        self.search_ent = tk.Entry(search_frame, font=(app.font_family, 11))
        self.search_ent.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.search_ent.bind("<Return>", lambda e: self.search())
        
        tk.Button(search_frame, text="검색", command=self.search, bg="#1a73e8", fg="white", font=(app.font_family, 10, "bold"), padx=10).pack(side="left")

        # 결과 리스트 (스크롤 가능)
        list_container = tk.Frame(self.win, bg=app.bg_color)
        list_container.pack(fill="both", expand=True)
        
        self.canvas = tk.Canvas(list_container, bg=app.bg_color, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=app.bg_color)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", width=440)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # 마우스 휠 스크롤 지원
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.refresh_upcoming()

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def refresh_upcoming(self):
        self.clear_list()
        tk.Label(self.scrollable_frame, text="⏳ 다가오는 일정 불러오는 중...", fg=self.app.fg_color, bg=self.app.bg_color).pack(pady=20)
        self.win.after(100, self._fetch_upcoming)

    def _fetch_upcoming(self):
        evts = self.app.api.fetch_upcoming_events(max_results=30)
        self.display_results(evts, "📅 다가오는 일정")

    def search(self):
        query = self.search_ent.get().strip()
        if not query:
            self.refresh_upcoming()
            return
        
        self.clear_list()
        tk.Label(self.scrollable_frame, text=f"🔍 '{query}' 검색 중...", fg=self.app.fg_color, bg=self.app.bg_color).pack(pady=20)
        self.win.after(100, lambda: self._do_search(query))

    def _do_search(self, query):
        evts = self.app.api.search_events(query)
        self.display_results(evts, f"🔍 '{query}' 검색 결과")

    def clear_list(self):
        for w in self.scrollable_frame.winfo_children(): w.destroy()

    def display_results(self, evts, title):
        self.clear_list()
        tk.Label(self.scrollable_frame, text=title, font=(self.app.font_family, 12, "bold"), fg=self.app.fg_color, bg=self.app.bg_color).pack(anchor="w", pady=(0, 10))
        
        if not evts:
            tk.Label(self.scrollable_frame, text="일정이 없습니다.", fg="#888", bg=self.app.bg_color).pack(pady=20)
            return

        for e in evts:
            e_frame = tk.Frame(self.scrollable_frame, bg="#333" if self.app.theme=="black" else "#f0f0f0", padx=10, pady=10)
            e_frame.pack(fill="x", pady=5)
            
            # 날짜 표시
            start = e['start'].get('dateTime', e['start'].get('date', ''))
            date_part = start[:10]
            time_part = start[11:16] if 'T' in start else "종일"
            
            tk.Label(e_frame, text=f"{date_part} ({time_part})", font=(self.app.font_family, 9), fg=self.app.lunar_color, bg=e_frame["bg"]).pack(anchor="w")
            
            summary = e.get('summary', '무제')
            tk.Label(e_frame, text=summary, font=(self.app.font_family, 11, "bold"), fg=self.app.fg_color, bg=e_frame["bg"]).pack(anchor="w")
            
            desc = e.get('description', '')
            if desc:
                tk.Label(e_frame, text=desc, font=(self.app.font_family, 9), fg="#aaa", bg=e_frame["bg"], wraplength=400, justify="left").pack(anchor="w")

            location = e.get('location', '')
            if location:
                map_url = f"https://www.google.com/maps/search/{urllib.parse.quote(location)}"
                loc_lbl = tk.Label(e_frame, text=f"📍 {location}", font=(self.app.font_family, 9), fg="#4fc3f7", bg=e_frame["bg"], cursor="hand2")
                loc_lbl.pack(anchor="w")
                loc_lbl.bind("<Button-1>", lambda ev, url=map_url: webbrowser.open(url))

            # 클릭 시 해당 날짜로 이동
            e_frame.bind("<Button-1>", lambda event, d=date_part: self.go_to_date(d))
            for child in e_frame.winfo_children():
                child.bind("<Button-1>", lambda event, d=date_part: self.go_to_date(d))

    def go_to_date(self, date_str):
        y, m, d = map(int, date_str.split('-'))
        self.app.current_year = y
        self.app.current_month = m
        self.app.update_calendar()
