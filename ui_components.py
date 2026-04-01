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
            
            # 요약과 메모를 함께 표시
            info_frame = tk.Frame(e_frame, bg=self.app.bg_color)
            info_frame.pack(side="left", fill="x", expand=True)
            
            tk.Label(info_frame, text=f"• {summary_text} ({t})", fg=color, bg=self.app.bg_color, anchor="w", font=evt_font).pack(side="top", fill="x")
            
            memo = e.get('description', '')
            if memo:
                tk.Label(info_frame, text=f"  ㄴ {memo}", fg=self.app.lunar_color, bg=self.app.bg_color, anchor="w", font=(self.app.font_family, 8)).pack(side="top", fill="x")

            tk.Button(e_frame, text="삭제", command=lambda evt_id=e['id'], evt=e: self.app.delete_event_with_win(evt_id, self.win, evt), bg="#ff4757", fg="white", bd=0, font=(self.app.font_family, 9), cursor="hand2").pack(side="right", padx=(2, 0))
            tk.Button(e_frame, text="수정", command=lambda evt=e: self.app.edit_event_popup_with_win(evt, self.date_str, self.win), bg="#555555", fg="white", bd=0, font=(self.app.font_family, 9), cursor="hand2").pack(side="right")
        
        tk.Button(self.win, text="+ 새로운 일정 추가하기", command=lambda: self.app.add_event_popup_with_win(self.date_str, self.win), bg="#1a73e8", fg="white", font=(self.app.font_family, 10, "bold")).pack(fill="x", pady=10)
        tk.Button(self.win, text="닫기", command=self.win.destroy).pack(fill="x")

class EventPopup:
    def __init__(self, parent, app, date_str, event=None):
        self.app = app
        self.date_str = date_str
        self.event = event
        self.win = tk.Toplevel(parent)
        self.win.title("일정 추가" if not event else "일정 수정")
        self.win.geometry("450x650") # 높이 증가
        self.win.attributes("-topmost", True)
        self.win.configure(bg=app.bg_color, padx=30, pady=20)
        
        tk.Label(self.win, text=f"🗓 {date_str} 일정", font=(app.font_family, 14, "bold"), bg=app.bg_color, fg=app.fg_color).pack(pady=(0, 15))

        # 제목
        tk.Label(self.win, text="📝 제목", font=(app.font_family, 10, "bold"), bg=app.bg_color, fg=app.fg_color).pack(anchor="w")
        self.summary_ent = tk.Entry(self.win, font=(app.font_family, 10))
        self.summary_ent.pack(fill="x", pady=(5, 10))
        if event: self.summary_ent.insert(0, event.get('summary', ''))
        
        # 시간
        tk.Label(self.win, text="⏰ 시간 (HH:MM 또는 '종일')", font=(app.font_family, 10, "bold"), bg=app.bg_color, fg=app.fg_color).pack(anchor="w")
        self.time_ent = tk.Entry(self.win, font=(app.font_family, 10))
        self.time_ent.pack(fill="x", pady=(5, 10))
        
        if event:
            t = event['start'].get('dateTime', '종일')
            if 'T' in t: t = t[11:16]
            self.time_ent.insert(0, t)
        else:
            self.time_ent.insert(0, "종일")

        # 메모 (Description)
        tk.Label(self.win, text="🗒 메모", font=(app.font_family, 10, "bold"), bg=app.bg_color, fg=app.fg_color).pack(anchor="w")
        self.memo_ent = tk.Text(self.win, font=(app.font_family, 10), height=4)
        self.memo_ent.pack(fill="x", pady=(5, 10))
        if event and event.get('description'):
            self.memo_ent.insert("1.0", event.get('description'))

        # 반복 설정
        tk.Label(self.win, text="🔄 반복 설정", font=(app.font_family, 10, "bold"), bg=app.bg_color, fg=app.fg_color).pack(anchor="w")
        self.repeat_var = tk.StringVar(value="없음")
        repeat_frame = tk.Frame(self.win, bg=app.bg_color)
        repeat_frame.pack(fill="x", pady=(5, 10))
        
        repeats = [("없음", "NONE"), ("매일", "DAILY"), ("매월", "MONTHLY"), ("매년", "YEARLY")]
        for text, val in repeats:
            tk.Radiobutton(repeat_frame, text=text, variable=self.repeat_var, value=val, bg=app.bg_color, fg=app.fg_color, selectcolor="#444").pack(side="left", padx=5)

        if event and event.get('recurrence'):
            rrule = event['recurrence'][0]
            if "DAILY" in rrule: self.repeat_var.set("DAILY")
            elif "MONTHLY" in rrule: self.repeat_var.set("MONTHLY")
            elif "YEARLY" in rrule: self.repeat_var.set("YEARLY")

        # 반복 종료일
        tk.Label(self.win, text="📅 반복 종료일 (YYYY-MM-DD)", font=(app.font_family, 10, "bold"), bg=app.bg_color, fg=app.fg_color).pack(anchor="w")
        self.end_date_ent = tk.Entry(self.win, font=(app.font_family, 10))
        self.end_date_ent.pack(fill="x", pady=(5, 15))
        
        if event and event.get('recurrence'):
            rrule = event['recurrence'][0]
            if "UNTIL=" in rrule:
                until = rrule.split("UNTIL=")[1].split(";")[0]
                formatted_until = f"{until[:4]}-{until[4:6]}-{until[6:8]}"
                self.end_date_ent.insert(0, formatted_until)

        btn_frame = tk.Frame(self.win, bg=app.bg_color)
        btn_frame.pack(fill="x", pady=(10, 0))

        tk.Button(btn_frame, text="💾 저장하기", command=self.save_event, bg="#1a73e8", fg="white", font=(app.font_family, 10, "bold"), pady=8).pack(side="left", expand=True, fill="x", padx=(0, 5))
        tk.Button(btn_frame, text="❌ 취소", command=self.win.destroy, bg="#555555", fg="white", font=(app.font_family, 10), pady=8).pack(side="left", expand=True, fill="x", padx=(5, 0))

    def save_event(self):
        summary = self.summary_ent.get().strip()
        time_str = self.time_ent.get().strip()
        memo = self.memo_ent.get("1.0", "end-1c").strip()
        repeat = self.repeat_var.get()
        end_date = self.end_date_ent.get().strip()
        
        if not summary:
            messagebox.showwarning("입력 누락", "일정 제목을 입력해 주세요.")
            return

        body = {'summary': summary, 'description': memo, 'start': {}, 'end': {}}
        
        # 시간 처리
        if time_str == "종일" or not time_str:
            start_dt = datetime.datetime.strptime(self.date_str, "%Y-%m-%d")
            end_dt = start_dt + datetime.timedelta(days=1)
            body['start'] = {'date': self.date_str}
            body['end'] = {'date': end_dt.strftime("%Y-%m-%d")}
        else:
            try:
                time_obj = datetime.datetime.strptime(time_str, "%H:%M")
                start_dt_str = f"{self.date_str}T{time_str}:00"
                end_time_obj = time_obj + datetime.timedelta(hours=1)
                end_time_str = end_time_obj.strftime("%H:%M")
                
                end_dt_str = f"{self.date_str}T{end_time_str}:00"
                if end_time_obj.day > time_obj.day:
                    curr_dt = datetime.datetime.strptime(self.date_str, "%Y-%m-%d")
                    next_dt = curr_dt + datetime.timedelta(days=1)
                    end_dt_str = f"{next_dt.strftime('%Y-%m-%d')}T{end_time_str}:00"

                body['start'] = {'dateTime': start_dt_str, 'timeZone': 'Asia/Seoul'}
                body['end'] = {'dateTime': end_dt_str, 'timeZone': 'Asia/Seoul'}
            except ValueError:
                messagebox.showerror("형식 오류", "시간은 HH:MM 형식으로 입력해 주세요.")
                return

        # 반복 처리
        if repeat != "NONE":
            rrule = f"RRULE:FREQ={repeat}"
            if end_date:
                try:
                    # YYYY-MM-DD -> YYYYMMDD
                    until = end_date.replace("-", "") + "T235959Z"
                    rrule += f";UNTIL={until}"
                except:
                    messagebox.showerror("형식 오류", "종료일은 YYYY-MM-DD 형식으로 입력해 주세요.")
                    return
            body['recurrence'] = [rrule]

        try:
            if self.event:
                self.app.api.update_event(self.event['id'], body)
            else:
                self.app.api.insert_event(body)
            
            self.win.destroy()
            self.app.manual_refresh()
        except Exception as e:
            messagebox.showerror("오류", f"일정 저장 중 오류 발생: {e}")

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
        tk.Label(self.win, text="🔡 폰트 (예: Malgun Gothic)", font=(app.font_family, 10, "bold"), bg=app.bg_color, fg=app.fg_color).pack(anchor="w")
        self.font_ent = tk.Entry(self.win, font=(app.font_family, 10))
        self.font_ent.pack(fill="x", pady=(5, 15))
        self.font_ent.insert(0, app.font_family)

        # 폰트 크기 설정
        tk.Label(self.win, text="📏 폰트 크기", font=(app.font_family, 10, "bold"), bg=app.bg_color, fg=app.fg_color).pack(anchor="w")
        self.size_ent = tk.Entry(self.win, font=(app.font_family, 10))
        self.size_ent.pack(fill="x", pady=(5, 20))
        self.size_ent.insert(0, str(app.font_size))

        btn_frame = tk.Frame(self.win, bg=app.bg_color)
        btn_frame.pack(fill="x", pady=(10, 0))

        tk.Button(btn_frame, text="✅ 적용 및 저장", command=self.save_settings, bg="#1a73e8", fg="white", font=(app.font_family, 10, "bold"), pady=8).pack(side="left", expand=True, fill="x", padx=(0, 5))
        tk.Button(btn_frame, text="❌ 취소", command=self.win.destroy, bg="#555555", fg="white", font=(app.font_family, 10), pady=8).pack(side="left", expand=True, fill="x", padx=(5, 0))

    def save_settings(self):
        try:
            new_theme = self.theme_var.get()
            new_alpha = float(self.alpha_scale.get())
            new_font = self.font_ent.get().strip()
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
