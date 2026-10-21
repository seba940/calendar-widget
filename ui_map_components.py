import tkinter as tk
from tkinter import ttk, messagebox
import map_utils

try:
    from tkintermapview import TkinterMapView
    MAP_AVAILABLE = True
except ImportError:
    MAP_AVAILABLE = False

class LocationSearchPopup:
    """장소 검색 팝업 - 검색창 + 후보 리스트 + 지도 + 구글 지도 연동"""
    def __init__(self, parent, app, callback):
        self.app = app
        self.callback = callback
        self.selected_location = None
        self.selected_lat = None
        self.selected_lng = None
        self._marker = None
        self.results = []
        
        self.user_lat, self.user_lon, self.user_city = map_utils.get_current_location()

        self.win = tk.Toplevel(parent)
        self.win.title("장소 검색")
        self.win.geometry("600x780")
        self.win.attributes("-topmost", True)
        self.win.configure(bg=app.bg_color, padx=15, pady=15)

        tk.Label(self.win, text=f"🔍 장소 검색 (현재: {self.user_city} 인근)", 
                 font=(app.font_family, 13, "bold"),
                 bg=app.bg_color, fg=app.fg_color).pack(pady=(0, 8))

        search_frame = tk.Frame(self.win, bg=app.bg_color)
        search_frame.pack(fill="x", pady=(0, 8))
        self.search_ent = tk.Entry(search_frame, font=(app.font_family, 11))
        self.search_ent.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.search_ent.bind("<Return>", lambda e: self.search())
        tk.Button(search_frame, text="검색", command=self.search,
                  bg="#1a73e8", fg="white", font=(app.font_family, 10, "bold"),
                  padx=12, cursor="hand2").pack(side="left")

        # 결과 리스트 영역
        self.list_label = tk.Label(self.win, text="검색 결과", 
                              font=(app.font_family, 9), bg=app.bg_color, fg="#888")
        self.list_label.pack(anchor="w")
        
        list_frame = tk.Frame(self.win, bg=app.bg_color)
        list_frame.pack(fill="x", pady=(2, 8))
        
        self.listbox = tk.Listbox(list_frame, height=5, font=(app.font_family, 10), 
                                  bg="#2d2d2d" if app.theme=="black" else "white",
                                  fg=app.fg_color, borderwidth=0, highlightthickness=1)
        self.listbox.pack(side="left", fill="x", expand=True)
        self.listbox.bind("<<ListboxSelect>>", self._on_list_select)
        
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scrollbar.set)

        # 결과가 없을 때 보여줄 도구
        self.fallback_frame = tk.Frame(self.win, bg=app.bg_color)
        self.fallback_btn = tk.Button(self.fallback_frame, text="🌐 구글 지도에서 검색하기 (상호명 검색)", 
                                     command=self._open_google_maps, bg="#4285F4", fg="white",
                                     font=(app.font_family, 9, "bold"), cursor="hand2")
        self.fallback_btn.pack(fill="x", pady=5)
        tk.Label(self.fallback_frame, text="💡 구글 지도에서 주소를 복사해 아래에 붙여넣으세요.", 
                 font=(app.font_family, 8), bg=app.bg_color, fg="#aaa").pack()

        if MAP_AVAILABLE:
            self.map_widget = TkinterMapView(self.win, width=570, height=350, corner_radius=8)
            self.map_widget.pack(fill="both", expand=True, pady=(8, 8))
            self.map_widget.set_position(self.user_lat, self.user_lon)
            self.map_widget.set_zoom(12)
            self.map_widget.add_left_click_map_command(self._on_map_click)
        else:
            tk.Label(self.win, text="지도 라이브러리가 없습니다. (pip install tkintermapview)",
                     fg="#ff4757", bg=app.bg_color).pack(expand=True)

        self.status_lbl = tk.Label(self.win, text="장소를 검색하세요.",
                                    font=(app.font_family, 9), fg="#888", bg=app.bg_color)
        self.status_lbl.pack(anchor="w", pady=(0, 6))

        btn_f = tk.Frame(self.win, bg=app.bg_color)
        btn_f.pack(fill="x")
        tk.Button(btn_f, text="✅ 선택 완료", command=self._confirm,
                  bg="#34a853", fg="white", font=(app.font_family, 10, "bold"),
                  pady=10, cursor="hand2").pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Button(btn_f, text="❌ 취소", command=self.win.destroy,
                  bg="#555", fg="white", font=(app.font_family, 10),
                  pady=10, cursor="hand2").pack(side="left", fill="x", expand=True, padx=(4, 0))

    def search(self):
        query = self.search_ent.get().strip()
        if not query: return
        
        self.status_lbl.config(text=f"🔍 '{query}' 검색 중...")
        self.win.update()
        
        self.results = map_utils.geocode_list(query, self.user_lat, self.user_lon)
        self.listbox.delete(0, tk.END)
        
        if not self.results:
            self.status_lbl.config(text="❌ 검색 결과가 없습니다. 구글 지도를 이용해보세요.")
            self.fallback_frame.pack(fill="x", before=self.status_lbl)
            return
            
        self.fallback_frame.pack_forget()
        for res in self.results:
            self.listbox.insert(tk.END, res['display'])
            
        self.status_lbl.config(text=f"✅ {len(self.results)}개의 장소를 찾았습니다.")
        self.listbox.selection_set(0)
        self._on_list_select(None)

    def _open_google_maps(self):
        query = self.search_ent.get().strip()
        map_utils.open_google_maps_search(query)

    def _on_list_select(self, event):
        selection = self.listbox.curselection()
        if not selection: return
        idx = selection[0]
        res = self.results[idx]
        self.selected_lat, self.selected_lng = res['lat'], res['lng']
        self.selected_location = f"{res['name']} ({res['address']})"
        if MAP_AVAILABLE:
            self.map_widget.set_position(self.selected_lat, self.selected_lng)
            self.map_widget.set_zoom(16)
            self._set_marker(self.selected_lat, self.selected_lng, self.selected_location)
        self.status_lbl.config(text=f"📍 선택됨: {res['name']} ({res['distance']:.1f}km)")

    def _set_marker(self, lat, lng, text=""):
        if self._marker: self._marker.delete()
        self._marker = self.map_widget.set_marker(lat, lng, text=text)

    def _on_map_click(self, coords):
        lat, lng = coords
        self._set_marker(lat, lng)
        self.selected_lat, self.selected_lng = lat, lng
        self.selected_location = f"{lat:.5f}, {lng:.5f}"
        self.status_lbl.config(text=f"📍 선택됨: {self.selected_location}")

    def _confirm(self):
        if self.selected_location:
            self.callback(self.selected_location, self.selected_lat, self.selected_lng)
            self.win.destroy()
        else:
            self.status_lbl.config(text="⚠️ 먼저 장소를 선택하세요.")
