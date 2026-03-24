import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont
import webbrowser
import datetime

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
            "구글 캘린더와 연동하려면 프로그램의 '신분증'이 필요합니다.\n"
            "아래 방법 중 하나를 선택해 주세요:\n\n"
            "방법 A: 'credentials.json' 파일을 이 프로그램 폴더에 넣기 (추천)\n"
            "방법 B: 아래에 Client ID와 Secret을 직접 입력하기\n\n"
            "설정 방법:\n"
            "1. Google Cloud Console에서 'OAuth 클라이언트 ID'를 생성합니다.\n"
            "2. 애플리케이션 유형을 '데스크톱 앱'으로 선택하세요.\n"
            "3. 생성 후 JSON 파일을 다운로드하여 이름을 'credentials.json'으로\n"
            "   바꾸어 폴더에 넣거나, 정보를 복사해 아래에 입력하세요."
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
        self.win.geometry("380x480")
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
        
        detail_frame = tk.Frame(self.win, bg=self.app.bg_color); detail_frame.pack(fill="both", expand=True)
        
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
            drag_handle.bind("<ButtonRelease-1>", lambda event: self.app.on_drag_stop(event, self.year, self.month, self.day, self.hols))
            
            t = e['start'].get('dateTime', '종일')[11:16] if 'dateTime' in e['start'] else "종일"
            summary_text = e.get('summary', '무제')
            is_done = summary_text.startswith("✅")
            evt_font = tkfont.Font(family=self.app.font_family, size=10, overstrike=is_done)
            color = "#888888" if is_done else self.app.fg_color

            tk.Button(e_frame, text="V", command=lambda evt=e: self.app.toggle_complete(evt), bg="#444", fg="white", bd=0, width=2, cursor="hand2").pack(side="left", padx=2)
            tk.Label(e_frame, text=f"• {summary_text} ({t})", fg=color, bg=self.app.bg_color, anchor="w", font=evt_font).pack(side="left", fill="x", expand=True)

            tk.Button(e_frame, text="삭제", command=lambda evt_id=e['id']: self.app.delete_event_with_win(evt_id, self.win), bg="#ff4757", fg="white", bd=0, font=(self.app.font_family, 9), cursor="hand2").pack(side="right", padx=(2, 0))
            tk.Button(e_frame, text="수정", command=lambda evt=e: self.app.edit_event_popup_with_win(evt, self.date_str, self.win), bg="#555555", fg="white", bd=0, font=(self.app.font_family, 9), cursor="hand2").pack(side="right")
        
        tk.Button(self.win, text="+ 새로운 일정 추가하기", command=lambda: self.app.add_event_popup_with_win(self.date_str, self.win), bg="#1a73e8", fg="white", font=(self.app.font_family, 10, "bold")).pack(fill="x", pady=10)
        tk.Button(self.win, text="닫기", command=self.win.destroy).pack(fill="x")
