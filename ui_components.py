import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont, colorchooser
import webbrowser
import datetime
import re
import urllib.parse
import os
import sys
import subprocess
import map_utils

# 타 모듈에서 클래스 가져오기
from ui_map_components import LocationSearchPopup
from ui_popups import SettingsWindow, AgendaWindow

try:
    from tkintermapview import TkinterMapView
    MAP_AVAILABLE = True
except ImportError:
    MAP_AVAILABLE = False

# 구글 캘린더 기본 색상 팔레트 (colors().get() API 호출 전이거나 실패했을 때의 대체값)
DEFAULT_EVENT_COLORS = {
    "1": {"background": "#7986cb"}, "2": {"background": "#33b679"},
    "3": {"background": "#8e24aa"}, "4": {"background": "#e67c73"},
    "5": {"background": "#f6c026"}, "6": {"background": "#f5511d"},
    "7": {"background": "#039be5"}, "8": {"background": "#616161"},
    "9": {"background": "#3f51b5"}, "10": {"background": "#0b8043"},
    "11": {"background": "#d60000"},
}

class UIComponents:
    @staticmethod
    def create_api_guide(root, bg_color, fg_color, font_family, config_manager, auth_callback):
        guide_win = tk.Toplevel(root)
        guide_win.title("구글 API 설정 가이드")
        guide_win.geometry("520x650")
        guide_win.attributes("-topmost", True)
        guide_win.configure(padx=30, pady=30, bg=bg_color)

        tk.Label(guide_win, text="🚀 구글 캘린더 연결 설정", font=(font_family, 16, "bold"), fg=fg_color, bg=bg_color).pack(pady=(0, 20))
        
        guide_text = (
            "구글 캘린더 연동을 위해 'Google Cloud Console' 설정이 필요합니다.\n\n"
            "1단계: 프로젝트 생성 및 API 활성화\n"
            " - Google Cloud Console 접속 후 새 프로젝트를 만듭니다.\n"
            " - [API 및 서비스 > 라이브러리]에서 'Google Calendar API'를 검색해 [활성화]를 누릅니다.\n\n"
            "2단계: OAuth 동의 화면 설정 (중요!)\n"
            " - [OAuth 동의 화면] 메뉴에서 User Type을 [외부]로 선택 후 생성합니다.\n"
            " - [테스트 사용자] 섹션에 본인의 구글 이메일을 반드시 추가해야 로그인이 가능합니다.\n\n"
            "3단계: 사용자 인증 정보 생성\n"
            " - [사용자 인증 정보 > 인증 정보 만들기]에서 [OAuth 클라이언트 ID]를 선택합니다.\n"
            " - 애플리케이션 유형을 [데스크톱 앱]으로 선택하고 생성합니다.\n\n"
            "4단계: 파일 적용\n"
            " - 생성된 클라이언트 ID의 [JSON 다운로드] 버튼을 누릅니다.\n"
            " - 다운로드된 파일 이름을 'credentials.json'으로 바꾸어 프로그램 폴더에 넣으세요.\n"
            " - (파일 대신 아래에 ID와 Secret을 직접 입력해도 됩니다.)"
        )
        tk.Label(guide_win, text=guide_text, justify="left", font=(font_family, 10), fg=fg_color, bg=bg_color).pack(fill="x", pady=(0, 20))

        tk.Button(guide_win, text="🔗 Google Cloud Console 바로가기", command=lambda: webbrowser.open("https://console.cloud.google.com/"), bg="#1a73e8", fg="white", font=(font_family, 10, "bold"), pady=8).pack(fill="x", pady=(0, 20))

        tk.Label(guide_win, text="Client ID", font=(font_family, 10, "bold"), fg=fg_color, bg=bg_color).pack(anchor="w")
        id_ent = tk.Entry(guide_win, width=50)
        id_ent.pack(pady=(5, 15))
        id_ent.insert(0, config_manager.get_env("GOOGLE_CLIENT_ID", ""))

        tk.Label(guide_win, text="Client Secret", font=(font_family, 10, "bold"), fg=fg_color, bg=bg_color).pack(anchor="w")
        secret_ent = tk.Entry(guide_win, width=50, show="*")
        secret_ent.pack(pady=(5, 20))
        secret_ent.insert(0, config_manager.get_env("GOOGLE_CLIENT_SECRET", ""))

        def save_api_info():
            cid = id_ent.get().strip()
            sec = secret_ent.get().strip()
            
            if not cid or not sec:
                messagebox.showwarning("입력 누락", "ID와 Secret을 입력하거나 credentials.json을 폴더에 넣어주세요.")
                return
            
            config_manager.set_env("GOOGLE_CLIENT_ID", cid)
            config_manager.set_env("GOOGLE_CLIENT_SECRET", sec)
            
            messagebox.showinfo("저장 완료", "설정이 저장되었습니다. 이제 구글 로그인을 시작합니다.")
            guide_win.destroy()
            auth_callback()

        tk.Button(guide_win, text="🔓 구글 로그인 시작 (SSO)", command=save_api_info, bg="#2ba347", fg="white", font=(font_family, 11, "bold"), pady=10).pack(fill="x")
        return guide_win

class DetailWindow:
    def __init__(self, parent, year, month, day, hols, evts, app_instance):
        self.app = app_instance
        self.win = tk.Toplevel(parent)
        self.win.geometry("380x560")
        self.win.attributes("-topmost", True)
        self.win.title("상세")
        self.win.configure(bg=self.app.bg_color, padx=20, pady=20)
        
        self.year, self.month, self.day = year, month, day
        self.hols, self.evts = hols, evts
        self.date_str = f"{year}-{month:02d}-{day:02d}"
        self.setup_ui()

    def setup_ui(self):
        for w in self.win.winfo_children(): w.destroy()
        
        nav_frame = tk.Frame(self.win, bg=self.app.bg_color)
        nav_frame.pack(fill="x", pady=(0, 15))
        
        tk.Button(nav_frame, text="⏪", command=lambda: self.app.navigate_day(self.date_str, -1, True), bg=self.app.bg_color, fg=self.app.fg_color, bd=0, font=("Arial", 12), cursor="hand2").pack(side="left")
        tk.Button(nav_frame, text="◀", command=lambda: self.app.navigate_day(self.date_str, -1, False), bg=self.app.bg_color, fg=self.app.fg_color, bd=0, font=("Arial", 12), cursor="hand2").pack(side="left", padx=(5, 0))
        
        lbl = tk.Label(nav_frame, text=f"{self.month}월 {self.day}일 일정", font=(self.app.font_family, 14, "bold"), bg=self.app.bg_color, fg=self.app.fg_color)
        lbl.pack(side="left", expand=True)
        
        tk.Button(nav_frame, text="▶", command=lambda: self.app.navigate_day(self.date_str, 1, False), bg=self.app.bg_color, fg=self.app.fg_color, bd=0, font=("Arial", 12), cursor="hand2").pack(side="left", padx=(0, 5))
        tk.Button(nav_frame, text="⏩", command=lambda: self.app.navigate_day(self.date_str, 1, True), bg=self.app.bg_color, fg=self.app.fg_color, bd=0, font=("Arial", 12), cursor="hand2").pack(side="left")

        # 하단 버튼을 먼저 배치해서 항상 보이도록 고정 (일정이 많아 내용이 길어져도 안 가려짐)
        bottom_btns = tk.Frame(self.win, bg=self.app.bg_color)
        bottom_btns.pack(side="bottom", fill="x", pady=(10, 0))
        tk.Button(bottom_btns, text="+ 새로운 일정 추가하기", command=lambda: self.app.add_event_popup_with_win(self.date_str, self.win), bg="#1a73e8", fg="white", font=(self.app.font_family, 10, "bold")).pack(fill="x", pady=(0, 5))
        tk.Button(bottom_btns, text="닫기", command=self.win.destroy).pack(fill="x")

        # 일정 목록은 스크롤 가능한 영역에 배치 (일정이 많거나 길어도 마우스 휠로 접근 가능)
        body_container = tk.Frame(self.win, bg=self.app.bg_color)
        body_container.pack(side="top", fill="both", expand=True)
        canvas = tk.Canvas(body_container, bg=self.app.bg_color, highlightthickness=0)
        scrollbar = ttk.Scrollbar(body_container, orient="vertical", command=canvas.yview)
        detail_frame = tk.Frame(canvas, bg=self.app.bg_color)
        detail_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=detail_frame, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self.win.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>") if e.widget == self.win else None)

        for h in self.hols: 
            summary = h.get('summary', '')
            is_red = self.app.utils.is_red_holiday(summary)
            hol_c = "#ff6b6b" if is_red else self.app.lunar_color
            prefix = "🎉 " if is_red else "📅 "
            tk.Label(detail_frame, text=f"{prefix}{summary}", fg=hol_c, bg=self.app.bg_color, font=(self.app.font_family, 11)).pack(anchor="w")
        
        self.app._event_widgets = []
        for e in self.evts:
            e_frame = tk.Frame(detail_frame, bg=self.app.bg_color)
            e_frame.pack(fill="x", pady=4)
            self.app._event_widgets.append(e_frame)
            
            drag_handle = tk.Label(e_frame, text="≡", fg="#888", bg=self.app.bg_color, font=(self.app.font_family, 14), cursor="sb_v_double_arrow")
            drag_handle.pack(side="left", padx=(0, 5))
            
            drag_handle.bind("<Button-1>", lambda event, evt=e: self.app.on_drag_start(event, evt))
            drag_handle.bind("<ButtonRelease-1>", lambda event: self.app.on_drag_stop(event))
            
            t = e['start'].get('dateTime', '종일')[11:16] if 'dateTime' in e['start'] else "종일"
            summary_text = e.get('summary', '무제')
            is_done = summary_text.startswith("✅")
            evt_font = tkfont.Font(family=self.app.font_family, size=10, overstrike=is_done)
            color = "#888888" if is_done else self.app.fg_color

            tk.Button(e_frame, text="V", command=lambda evt=e: self.app.toggle_complete(evt), bg="#444", fg="white", bd=0, width=2, cursor="hand2").pack(side="left", padx=2)

            # 수정/삭제 버튼을 먼저 배치해서 오른쪽 공간을 확보 (내용 라벨이 expand=True라 나중에 넣으면 버튼이 밀려서 안 보임)
            tk.Button(e_frame, text="삭제", command=lambda evt_id=e['id'], evt=e: self.app.delete_event_with_win(evt_id, self.win, evt), bg="#ff4757", fg="white", bd=0, font=(self.app.font_family, 9), cursor="hand2").pack(side="right", padx=(2, 0))
            tk.Button(e_frame, text="수정", command=lambda evt=e: self.app.edit_event_popup_with_win(evt, self.date_str, self.win), bg="#555555", fg="white", bd=0, font=(self.app.font_family, 9), cursor="hand2").pack(side="right")

            info_frame = tk.Frame(e_frame, bg=self.app.bg_color)
            info_frame.pack(side="left", fill="x", expand=True)

            tk.Label(info_frame, text=f"• {summary_text} ({t})", fg=color, bg=self.app.bg_color, anchor="w", justify="left", wraplength=200, font=evt_font).pack(side="top", fill="x")

            memo = e.get('description', '')
            if memo:
                tk.Label(info_frame, text=f"  ㄴ {memo}", fg=self.app.lunar_color, bg=self.app.bg_color, anchor="w", justify="left", wraplength=200, font=(self.app.font_family, 8)).pack(side="top", fill="x")

            location = e.get('location', '')
            if location:
                map_url = f"https://www.google.com/maps/search/{urllib.parse.quote(location)}"
                loc_lbl = tk.Label(info_frame, text=f"  📍 {location}", fg="#4fc3f7", bg=self.app.bg_color, anchor="w", justify="left", wraplength=200, font=(self.app.font_family, 8), cursor="hand2")
                loc_lbl.pack(side="top", fill="x")
                loc_lbl.bind("<Button-1>", lambda ev, url=map_url: webbrowser.open(url))
                if MAP_AVAILABLE:
                    map_container = tk.Frame(detail_frame, bg=self.app.bg_color, height=160)
                    map_container.pack(fill="x", pady=(2, 6))
                    map_container.pack_propagate(False)
                    m = TkinterMapView(map_container, width=340, height=155, corner_radius=6)
                    m.pack(fill="both", expand=True)
                    m.bind("<Button-1>", lambda ev, url=map_url: webbrowser.open(url))
                    self.win.after(400, lambda addr=location, mw=m: self._load_detail_map(mw, addr))

    def _load_detail_map(self, map_widget, address):
        try:
            # 1. 먼저 Photon API 기반 지오코딩 시도 (한국 POI 및 상호명 검색에 더 강함)
            lat, lng, name = map_utils.geocode(address)
            if lat:
                map_widget.set_position(lat, lng)
                map_widget.set_marker(lat, lng, text=name)
                map_widget.set_zoom(15)
                return

            # 2. 실패 시 기본 set_address (Nominatim) 시도
            result = map_widget.set_address(address, marker=False)
            if result:
                pos = map_widget.get_position()
                map_widget.set_marker(pos[0], pos[1], text=address)
                map_widget.set_zoom(15)
        except Exception:
            pass

class EventPopup:
    def __init__(self, parent, app, date_str, event=None):
        self.app = app
        self.date_str = date_str
        self.event = event
        self.win = tk.Toplevel(parent)
        self.win.title("일정 추가" if not event else "일정 수정")
        self.win.geometry("480x760")
        self.win.minsize(400, 320)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=app.bg_color)

        # 저장/취소 버튼을 창 맨 아래에 먼저 고정 배치 (내용이 길어져도 항상 보이도록)
        btn_frame = tk.Frame(self.win, bg=app.bg_color)
        btn_frame.pack(side="bottom", fill="x", padx=20, pady=15)
        tk.Button(btn_frame, text="💾 저장하기", command=self.save_event, bg="#1a73e8", fg="white", font=(app.font_family, 10, "bold"), pady=8).pack(side="left", expand=True, fill="x", padx=(0, 5))
        tk.Button(btn_frame, text="❌ 취소", command=self.win.destroy, bg="#555555", fg="white", font=(app.font_family, 10), pady=8).pack(side="left", expand=True, fill="x", padx=(5, 0))

        # 본문은 스크롤 가능한 영역에 배치 (내용이 창보다 길어도 마우스 휠로 스크롤해서 접근 가능)
        body_container = tk.Frame(self.win, bg=app.bg_color)
        body_container.pack(side="top", fill="both", expand=True)
        canvas = tk.Canvas(body_container, bg=app.bg_color, highlightthickness=0)
        scrollbar = ttk.Scrollbar(body_container, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg=app.bg_color)
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=(20, 0))
        scrollbar.pack(side="right", fill="y", pady=(20, 0))

        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self.win.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>") if e.widget == self.win else None)

        tk.Label(content, text="📅 일정 정보", font=(app.font_family, 14, "bold"), bg=app.bg_color, fg=app.fg_color).pack(pady=(0, 15))

        tk.Label(content, text="📅 날짜 설정", font=(app.font_family, 10, "bold"), bg=app.bg_color, fg=app.fg_color).pack(anchor="w")
        date_frame = tk.Frame(content, bg=app.bg_color)
        date_frame.pack(fill="x", pady=(5, 10))

        curr_year = datetime.datetime.now().year
        self.year_cb = ttk.Combobox(date_frame, values=[str(y) for y in range(curr_year - 5, curr_year + 6)], width=6, state="readonly")
        self.year_cb.pack(side="left")
        tk.Label(date_frame, text="년", bg=app.bg_color, fg=app.fg_color).pack(side="left", padx=(2, 5))

        self.month_cb = ttk.Combobox(date_frame, values=[f"{m:02d}" for m in range(1, 13)], width=4, state="readonly")
        self.month_cb.pack(side="left")
        tk.Label(date_frame, text="월", bg=app.bg_color, fg=app.fg_color).pack(side="left", padx=(2, 5))

        self.day_cb = ttk.Combobox(date_frame, values=[f"{d:02d}" for d in range(1, 32)], width=4, state="readonly")
        self.day_cb.pack(side="left")
        tk.Label(date_frame, text="일", bg=app.bg_color, fg=app.fg_color).pack(side="left", padx=(2, 5))

        y, m, d = map(int, date_str.split('-'))
        self.year_cb.set(str(y))
        self.month_cb.set(f"{m:02d}")
        self.day_cb.set(f"{d:02d}")

        tk.Label(content, text="📝 제목", font=(app.font_family, 10, "bold"), bg=app.bg_color, fg=app.fg_color).pack(anchor="w")
        self.summary_ent = tk.Entry(content, font=(app.font_family, 10))
        self.summary_ent.pack(fill="x", pady=(5, 10))
        if event: self.summary_ent.insert(0, event.get('summary', ''))

        # 카테고리 / 색상: 카테고리를 고르면 이전에 저장해둔 고유 색이 자동으로 선택됨
        tk.Label(content, text="🏷 카테고리 / 색상", font=(app.font_family, 10, "bold"), bg=app.bg_color, fg=app.fg_color).pack(anchor="w")
        cat_frame = tk.Frame(content, bg=app.bg_color)
        cat_frame.pack(fill="x", pady=(5, 5))
        self.categories = self.app.config.settings.get("categories", {})
        self.custom_colors = self.app.config.settings.get("custom_event_colors", {})  # event_id -> hex (앱 로컬 전용, 구글에 안 보냄)
        self.category_var = tk.StringVar()
        self.category_cb = ttk.Combobox(cat_frame, textvariable=self.category_var, values=list(self.categories.keys()))
        self.category_cb.pack(side="left", fill="x", expand=True)
        self.category_cb.bind("<<ComboboxSelected>>", self.on_category_selected)
        self.category_cb.bind("<Return>", self.on_category_selected)
        self.category_cb.bind("<FocusOut>", self.on_category_selected)

        self.event_colors = self.app.api.event_colors if getattr(self.app.api, 'event_colors', None) else DEFAULT_EVENT_COLORS
        self.custom_hex = self.custom_colors.get(event['id']) if event else None
        self.selected_color_id = (event.get('colorId') if event else None) if not self.custom_hex else None
        self.color_swatches = {}
        swatch_frame = tk.Frame(content, bg=app.bg_color)
        swatch_frame.pack(fill="x", pady=(5, 5))
        for cid in sorted(self.event_colors.keys(), key=lambda x: int(x)):
            sw = tk.Canvas(swatch_frame, width=22, height=22, bg=app.bg_color, highlightthickness=0, cursor="hand2")
            sw.pack(side="left", padx=3)
            self.color_swatches[cid] = sw
            sw.bind("<Button-1>", lambda e, c=cid: self.select_color(c))

        # 사용자 지정 색상 (RGB/HEX 직접 입력, 이 앱에서만 적용되고 구글 캘린더로는 저장되지 않음)
        custom_frame = tk.Frame(content, bg=app.bg_color)
        custom_frame.pack(fill="x", pady=(0, 5))
        tk.Label(custom_frame, text="사용자 지정:", font=(app.font_family, 9), bg=app.bg_color, fg=app.fg_color).pack(side="left")
        self.custom_preview = tk.Canvas(custom_frame, width=22, height=22, bg=app.bg_color, highlightthickness=0)
        self.custom_preview.pack(side="left", padx=(6, 4))
        self.hex_ent = tk.Entry(custom_frame, font=(app.font_family, 10), width=9)
        self.hex_ent.pack(side="left")
        self.hex_ent.insert(0, self.custom_hex or "#RRGGBB")
        self.hex_ent.bind("<Return>", lambda e: self._apply_hex_entry())
        self.hex_ent.bind("<FocusOut>", lambda e: self._apply_hex_entry())
        tk.Button(custom_frame, text="🎨 색상 선택", command=self.open_color_chooser,
                  bg="#555555", fg="white", font=(app.font_family, 9), cursor="hand2").pack(side="left", padx=(6, 0))
        tk.Label(content, text="(RGB/HEX 값을 직접 입력하거나 색상 선택 버튼으로 고를 수 있고, 이 색은 구글 캘린더와 동기화되지 않고 이 프로그램에만 저장됩니다)",
                 font=(app.font_family, 8), bg=app.bg_color, fg="#888888", wraplength=380, justify="left").pack(anchor="w", pady=(0, 10))

        self._redraw_swatches()
        self._redraw_custom_preview()

        if event and event.get('summary') and not self.custom_hex:
            # 기존 일정의 제목과 정확히 일치하는 카테고리가 있으면 자동으로 표시
            for name in self.categories:
                if name and name in event.get('summary', ''):
                    self.category_var.set(name)
                    self.on_category_selected()
                    break

        tk.Label(content, text="⏰ 시간 설정", font=(app.font_family, 10, "bold"), bg=app.bg_color, fg=app.fg_color).pack(anchor="w")
        time_frame = tk.Frame(content, bg=app.bg_color)
        time_frame.pack(fill="x", pady=(5, 10))

        self.all_day_var = tk.BooleanVar()
        tk.Checkbutton(time_frame, text="종일", variable=self.all_day_var, command=self.toggle_time_fields, bg=app.bg_color, fg=app.fg_color, selectcolor="#444", activebackground=app.bg_color).pack(side="left")

        self.hour_cb = ttk.Combobox(time_frame, values=[f"{h:02d}" for h in range(24)], width=4, state="readonly")
        self.hour_cb.pack(side="left", padx=(5, 2))
        tk.Label(time_frame, text=":", bg=app.bg_color, fg=app.fg_color).pack(side="left")
        
        self.min_cb = ttk.Combobox(time_frame, values=[f"{m:02d}" for m in range(0, 60, 5)], width=4, state="readonly")
        self.min_cb.pack(side="left", padx=(2, 5))
        
        tk.Label(time_frame, text="~", bg=app.bg_color, fg=app.fg_color, font=("Arial", 12, "bold")).pack(side="left", padx=5)

        self.end_hour_cb = ttk.Combobox(time_frame, values=[f"{h:02d}" for h in range(24)], width=4, state="readonly")
        self.end_hour_cb.pack(side="left", padx=(5, 2))
        tk.Label(time_frame, text=":", bg=app.bg_color, fg=app.fg_color).pack(side="left")
        
        self.end_min_cb = ttk.Combobox(time_frame, values=[f"{m:02d}" for m in range(0, 60, 5)], width=4, state="readonly")
        self.end_min_cb.pack(side="left", padx=(2, 5))

        if event:
            start_t = event['start'].get('dateTime', '종일')
            end_t = event['end'].get('dateTime', '종일')
            if 'T' in start_t:
                self.all_day_var.set(False)
                self.hour_cb.set(start_t[11:13])
                self.min_cb.set(start_t[14:16])
                if 'T' in end_t:
                    self.end_hour_cb.set(end_t[11:13])
                    self.end_min_cb.set(end_t[14:16])
                else:
                    self.end_hour_cb.set("10")
                    self.end_min_cb.set("00")
            else:
                self.all_day_var.set(True)
                self.hour_cb.set("09")
                self.min_cb.set("00")
                self.end_hour_cb.set("10")
                self.end_min_cb.set("00")
        else:
            self.all_day_var.set(True)
            self.hour_cb.set("09")
            self.min_cb.set("00")
            self.end_hour_cb.set("10")
            self.end_min_cb.set("00")
        
        self.toggle_time_fields()

        tk.Label(content, text="🗒 메모", font=(app.font_family, 10, "bold"), bg=app.bg_color, fg=app.fg_color).pack(anchor="w")
        self.memo_ent = tk.Text(content, font=(app.font_family, 10), height=4, insertbackground=app.fg_color, insertwidth=2)
        self.memo_ent.pack(fill="x", pady=(5, 10))
        if event and event.get('description'):
            self.memo_ent.insert("1.0", event.get('description'))

        tk.Label(content, text="📍 장소", font=(app.font_family, 10, "bold"), bg=app.bg_color, fg=app.fg_color).pack(anchor="w")
        loc_input_frame = tk.Frame(content, bg=app.bg_color)
        loc_input_frame.pack(fill="x", pady=(5, 5))
        self.location_ent = tk.Entry(loc_input_frame, font=(app.font_family, 10))
        self.location_ent.pack(side="left", fill="x", expand=True, padx=(0, 5))
        tk.Button(loc_input_frame, text="🔍 장소 검색", command=self.open_location_search,
                  bg="#34a853", fg="white", font=(app.font_family, 9), pady=3, cursor="hand2").pack(side="left")

        map_bg = "#1e1e2e" if app.theme == "black" else "#ebebeb"
        self.map_preview_frame = tk.Frame(content, bg=map_bg, height=190)
        self.map_preview_frame.pack(fill="x", pady=(0, 10))
        self.map_preview_frame.pack_propagate(False)
        self.map_placeholder = tk.Label(self.map_preview_frame,
                                         text="🗺  장소를 검색하면 지도가 표시됩니다",
                                         fg="#666", bg=map_bg, font=(app.font_family, 10))
        self.map_placeholder.pack(expand=True)
        self.map_widget = None
        self.location_lat = None
        self.location_lng = None
        self._preview_marker = None

        if event and event.get('location'):
            self.location_ent.insert(0, event.get('location'))
            if MAP_AVAILABLE:
                self.win.after(600, lambda: self._load_existing_location(event.get('location')))

        tk.Label(content, text="🔄 반복 설정", font=(app.font_family, 10, "bold"), bg=app.bg_color, fg=app.fg_color).pack(anchor="w")
        self.repeat_var = tk.StringVar(value="NONE")
        repeat_frame = tk.Frame(content, bg=app.bg_color)
        repeat_frame.pack(fill="x", pady=(5, 10))
        
        repeats = [("없음", "NONE"), ("매일", "DAILY"), ("매월", "MONTHLY"), ("매년", "YEARLY")]
        for text, val in repeats:
            tk.Radiobutton(repeat_frame, text=text, variable=self.repeat_var, value=val, bg=app.bg_color, fg=app.fg_color, selectcolor="#444", command=self.toggle_repeat_fields).pack(side="left", padx=5)

        if event and event.get('recurrence'):
            rrule = event['recurrence'][0]
            if "DAILY" in rrule: self.repeat_var.set("DAILY")
            elif "MONTHLY" in rrule: self.repeat_var.set("MONTHLY")
            elif "YEARLY" in rrule: self.repeat_var.set("YEARLY")

        self.end_date_label = tk.Label(content, text="📅 반복 종료일", font=(app.font_family, 10, "bold"), bg=app.bg_color, fg=app.fg_color)
        self.end_date_label.pack(anchor="w")

        self.end_date_frame = tk.Frame(content, bg=app.bg_color)
        self.end_date_frame.pack(fill="x", pady=(5, 15))

        curr_year = datetime.datetime.now().year
        self.end_year_cb = ttk.Combobox(self.end_date_frame, values=[str(y) for y in range(curr_year, curr_year + 11)], width=6, state="readonly")
        self.end_year_cb.pack(side="left")
        tk.Label(self.end_date_frame, text="년", bg=app.bg_color, fg=app.fg_color).pack(side="left", padx=(2, 5))

        self.end_month_cb = ttk.Combobox(self.end_date_frame, values=[f"{m:02d}" for m in range(1, 13)], width=4, state="readonly")
        self.end_month_cb.pack(side="left")
        tk.Label(self.end_date_frame, text="월", bg=app.bg_color, fg=app.fg_color).pack(side="left", padx=(2, 5))

        self.end_day_cb = ttk.Combobox(self.end_date_frame, values=[f"{d:02d}" for d in range(1, 32)], width=4, state="readonly")
        self.end_day_cb.pack(side="left")
        tk.Label(self.end_date_frame, text="일", bg=app.bg_color, fg=app.fg_color).pack(side="left", padx=(2, 5))

        self.end_year_cb.set(str(curr_year))
        self.end_month_cb.set(datetime.datetime.now().strftime("%m"))
        self.end_day_cb.set(datetime.datetime.now().strftime("%d"))

        if event and event.get('recurrence'):
            rrule = event['recurrence'][0]
            if "UNTIL=" in rrule:
                until = rrule.split("UNTIL=")[1].split(";")[0]
                self.end_year_cb.set(until[:4])
                self.end_month_cb.set(until[4:6])
                self.end_day_cb.set(until[6:8])

        self.toggle_repeat_fields()

    def _redraw_swatches(self):
        for cid, sw in self.color_swatches.items():
            sw.delete("all")
            bg_hex = self.event_colors[cid].get('background', '#888888')
            is_sel = (cid == self.selected_color_id and not self.custom_hex)
            outline = self.app.fg_color if is_sel else bg_hex
            width = 3 if is_sel else 0
            sw.create_oval(2, 2, 20, 20, fill=bg_hex, outline=outline, width=width)

    def _redraw_custom_preview(self):
        self.custom_preview.delete("all")
        if self.custom_hex:
            self.custom_preview.create_oval(2, 2, 20, 20, fill=self.custom_hex, outline=self.app.fg_color, width=2)
        else:
            self.custom_preview.create_oval(2, 2, 20, 20, fill=self.app.bg_color, outline="#888888", width=1)

    def select_color(self, color_id):
        self.selected_color_id = color_id
        self.custom_hex = None
        self.hex_ent.delete(0, "end")
        self.hex_ent.insert(0, "#RRGGBB")
        self._redraw_swatches()
        self._redraw_custom_preview()
        # 카테고리 이름이 입력돼 있으면 이 색을 그 카테고리의 고유 색으로 저장 (구글 표준색 -> 동기화됨)
        cat_name = self.category_var.get().strip()
        if cat_name:
            self.categories[cat_name] = {"colorId": color_id}
            if cat_name not in self.category_cb['values']:
                self.category_cb['values'] = list(self.categories.keys())

    def _normalize_hex(self, text):
        text = text.strip()
        if not text:
            return None
        if not text.startswith('#'):
            text = '#' + text
        if re.fullmatch(r'#[0-9A-Fa-f]{6}', text):
            return text.lower()
        return None

    def apply_custom_hex(self, hex_code):
        self.custom_hex = hex_code
        self.selected_color_id = None
        self.hex_ent.delete(0, "end")
        self.hex_ent.insert(0, hex_code)
        self._redraw_swatches()
        self._redraw_custom_preview()
        # 카테고리 이름이 입력돼 있으면 이 사용자 지정 색을 그 카테고리의 고유 색으로 저장 (로컬 전용, 구글엔 저장 안 됨)
        cat_name = self.category_var.get().strip()
        if cat_name:
            self.categories[cat_name] = {"custom": hex_code}
            if cat_name not in self.category_cb['values']:
                self.category_cb['values'] = list(self.categories.keys())

    def _apply_hex_entry(self):
        hex_code = self._normalize_hex(self.hex_ent.get())
        if hex_code:
            self.apply_custom_hex(hex_code)
        elif self.hex_ent.get().strip() not in ("", "#RRGGBB"):
            messagebox.showwarning("입력 오류", "색상 코드는 #RRGGBB 형식(예: #3f51b5)으로 입력해 주세요.")

    def open_color_chooser(self):
        initial = self.custom_hex or "#3f51b5"
        _, hex_code = colorchooser.askcolor(color=initial, title="사용자 지정 색상 선택", parent=self.win)
        if hex_code:
            self.apply_custom_hex(hex_code)

    def on_category_selected(self, _event=None):
        cat_name = self.category_var.get().strip()
        if not cat_name or cat_name not in self.categories:
            return
        val = self.categories[cat_name]
        if isinstance(val, dict):
            if val.get('custom'):
                self.apply_custom_hex(val['custom'])
            elif val.get('colorId'):
                self.select_color(val['colorId'])
        else:
            # 이전 버전 형식(구글 colorId 문자열) 호환
            self.select_color(val)

    def toggle_time_fields(self):
        state = "disabled" if self.all_day_var.get() else "readonly"
        self.hour_cb.config(state=state)
        self.min_cb.config(state=state)
        self.end_hour_cb.config(state=state)
        self.end_min_cb.config(state=state)

    def toggle_repeat_fields(self):
        cb_state = "readonly" if self.repeat_var.get() != "NONE" else "disabled"
        self.end_year_cb.config(state=cb_state)
        self.end_month_cb.config(state=cb_state)
        self.end_day_cb.config(state=cb_state)

    def open_location_search(self):
        LocationSearchPopup(self.win, self.app, self.set_location)

    def set_location(self, address, lat, lng):
        self.location_ent.delete(0, "end")
        self.location_ent.insert(0, address)
        self.location_lat = lat
        self.location_lng = lng
        self._show_map_preview(lat, lng, address)

    def _create_map_widget(self):
        if self.map_placeholder:
            self.map_placeholder.destroy()
            self.map_placeholder = None
        self.map_widget = TkinterMapView(self.map_preview_frame, width=390, height=185, corner_radius=6)
        self.map_widget.pack(fill="both", expand=True)

    def _show_map_preview(self, lat, lng, address=""):
        if not MAP_AVAILABLE:
            return
        if not self.map_widget:
            self._create_map_widget()
        self.map_widget.set_position(lat, lng)
        self.map_widget.set_zoom(15)
        if self._preview_marker:
            self._preview_marker.delete()
        self._preview_marker = self.map_widget.set_marker(lat, lng, text=address)

    def _load_existing_location(self, address):
        if not MAP_AVAILABLE:
            return
        try:
            if not self.map_widget:
                self._create_map_widget()
            
            # 1. 기본 set_address 시도
            result = self.map_widget.set_address(address, marker=False)
            if result:
                pos = self.map_widget.get_position()
                self.location_lat, self.location_lng = pos[0], pos[1]
                if self._preview_marker: self._preview_marker.delete()
                self._preview_marker = self.map_widget.set_marker(pos[0], pos[1], text=address)
                self.map_widget.set_zoom(15)
                return
            
            # 2. 실패 시 Photon API 기반 지오코딩 시도
            lat, lng, name = map_utils.geocode(address)
            if lat:
                self.location_lat, self.location_lng = lat, lng
                if self._preview_marker: self._preview_marker.delete()
                self._preview_marker = self.map_widget.set_marker(lat, lng, text=name)
                self.map_widget.set_position(lat, lng)
                self.map_widget.set_zoom(15)
        except Exception:
            pass

    def save_event(self):
        summary = self.summary_ent.get().strip()
        is_all_day = self.all_day_var.get()
        memo = self.memo_ent.get("1.0", "end-1c").strip()
        location = self.location_ent.get().strip()
        repeat = self.repeat_var.get()
        selected_date = f"{self.year_cb.get()}-{self.month_cb.get()}-{self.day_cb.get()}"

        if not summary:
            messagebox.showwarning("입력 누락", "일정 제목을 입력해 주세요.")
            return

        body = {'summary': summary, 'description': memo, 'location': location, 'start': {}, 'end': {}}
        if self.custom_hex:
            # 사용자 지정 색상은 로컬 전용: 구글에는 새로 보내지 않고, 기존에 있던 colorId만 그대로 유지
            if self.event and self.event.get('colorId'):
                body['colorId'] = self.event['colorId']
        elif self.selected_color_id:
            body['colorId'] = self.selected_color_id

        if is_all_day:
            start_dt = datetime.datetime.strptime(selected_date, "%Y-%m-%d")
            end_dt = start_dt + datetime.timedelta(days=1)
            body['start'] = {'date': selected_date}
            body['end'] = {'date': end_dt.strftime("%Y-%m-%d")}
        else:
            start_time_str = f"{self.hour_cb.get()}:{self.min_cb.get()}"
            end_time_str = f"{self.end_hour_cb.get()}:{self.end_min_cb.get()}"
            try:
                start_dt_str = f"{selected_date}T{start_time_str}:00"
                if end_time_str <= start_time_str:
                    curr_dt = datetime.datetime.strptime(selected_date, "%Y-%m-%d")
                    next_dt = curr_dt + datetime.timedelta(days=1)
                    end_dt_str = f"{next_dt.strftime('%Y-%m-%d')}T{end_time_str}:00"
                else:
                    end_dt_str = f"{selected_date}T{end_time_str}:00"
                body['start'] = {'dateTime': start_dt_str, 'timeZone': 'Asia/Seoul'}
                body['end'] = {'dateTime': end_dt_str, 'timeZone': 'Asia/Seoul'}
            except ValueError:
                messagebox.showerror("오류", "시간 선택이 올바르지 않습니다.")
                return

        if repeat != "NONE":
            rrule = f"RRULE:FREQ={repeat}"
            end_date_str = f"{self.end_year_cb.get()}{self.end_month_cb.get()}{self.end_day_cb.get()}"
            rrule += f";UNTIL={end_date_str}T235959Z"
            body['recurrence'] = [rrule]

        try:
            if self.event:
                self.app.api.update_event(self.event['id'], body)
                result_id = self.event['id']
            else:
                result = self.app.api.insert_event(body)
                result_id = result.get('id') if result else None

            # 사용자 지정 색상은 이 프로그램의 설정 파일에만 저장 (구글 캘린더로는 전송되지 않음)
            if result_id:
                if self.custom_hex:
                    self.custom_colors[result_id] = self.custom_hex
                    self.app.config.save_settings({"custom_event_colors": self.custom_colors})
                elif result_id in self.custom_colors:
                    del self.custom_colors[result_id]
                    self.app.config.save_settings({"custom_event_colors": self.custom_colors})

            cat_name = self.category_var.get().strip()
            if cat_name and (self.selected_color_id or self.custom_hex):
                self.app.config.save_settings({"categories": self.categories})

            self.win.destroy()
            self.app.manual_refresh()
        except Exception as e:
            messagebox.showerror("오류", f"일정 저장 중 오류 발생: {e}")
