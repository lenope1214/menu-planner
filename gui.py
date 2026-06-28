# -*- coding: utf-8 -*-
"""
한식 뷔페 식단표 생성기 — 데스크톱 GUI (어르신 친화, 2단 레이아웃)
===================================================================
- 왼쪽: 미리보기(칸을 클릭해 메뉴 텍스트를 바로 수정) — 달력형/주방형
- 오른쪽: 설정 패널(보기 형식·연/월·만들기·저장/복사/인쇄·API 키)
- 세밀한 서식은 엑셀로 저장해 엑셀에서 편집한다(앱은 단순하게 유지).

실행:    python gui.py
빌드:    GitHub Actions(.github/workflows/build-windows.yml) 또는 build_windows.bat
"""

from __future__ import annotations

import sys
import threading
from datetime import date
from tkinter import (
    Tk, StringVar, BooleanVar, END, DISABLED, NORMAL,
    Label, Button, Entry, Frame, Canvas, Checkbutton, Radiobutton,
    OptionMenu, LabelFrame, messagebox, filedialog,
)
from tkinter import ttk
from tkinter import font as tkfont

import app_config
import exporters
import layouts
import store
import settings_windows
from layouts import WEEKDAYS_KR, SECTIONS, ITEMS_PER_MEAL

# 어르신 가독성을 위한 글씨 크기
FONT_FAMILY = "맑은 고딕"   # Windows 기본 한글 폰트(없으면 시스템 기본으로 대체됨)
SZ_TITLE = 22
SZ_SECTION = 32   # 달력형 중식/석식 제목
SZ_SUBTITLE = 16
SZ_LABEL = 14
SZ_BUTTON = 15
SZ_GRID = 12
SZ_CELL = 11

BG = "#FAFAFA"
ACCENT = "#2E7D32"
PANEL_BG = "#F1F4F1"

C_HEADER = "#D9E1F2"   # 요일 헤더(달력)
C_EMPTY = "#E2EFDA"    # 빈 날짜 칸
C_LUNCH = "#E4DFEC"    # 주방형 헤더/중식
C_DINNER = "#FCE4D6"   # 주방형 석식
C_GRID = "#B7B7B7"     # 표 격자선


class MenuPlannerApp:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("한식 뷔페 식단표 만들기")
        self.root.configure(bg=BG)
        self.root.geometry("1280x820")
        self.root.minsize(1040, 640)

        self._busy = False
        self.month_data: layouts.MonthData | None = None
        self._cells: list[tuple[Entry, int, str, int]] = []  # (entry, day, section, idx)
        today = date.today()
        self.cur_year, self.cur_month = today.year, today.month

        self._build_fonts()
        self._build_layout()
        self._render_preview()
        self._check_key_on_start()

    # --- 폰트 ---
    def _build_fonts(self):
        self.f_title = tkfont.Font(family=FONT_FAMILY, size=SZ_TITLE, weight="bold")
        self.f_section = tkfont.Font(family=FONT_FAMILY, size=SZ_SECTION, weight="bold")
        self.f_subtitle = tkfont.Font(family=FONT_FAMILY, size=SZ_SUBTITLE, weight="bold")
        self.f_label = tkfont.Font(family=FONT_FAMILY, size=SZ_LABEL)
        self.f_button = tkfont.Font(family=FONT_FAMILY, size=SZ_BUTTON, weight="bold")
        self.f_grid = tkfont.Font(family=FONT_FAMILY, size=SZ_GRID, weight="bold")
        self.f_cell = tkfont.Font(family=FONT_FAMILY, size=SZ_CELL)

    # --- 스크롤 가능한 영역 헬퍼 ---
    def _scroll_area(self, parent, bg, horizontal=False):
        canvas = Canvas(parent, bg=bg, highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        if horizontal:
            hsb = ttk.Scrollbar(parent, orient="horizontal", command=canvas.xview)
            canvas.configure(xscrollcommand=hsb.set)
            hsb.pack(side="bottom", fill="x")
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = Frame(canvas, bg=bg)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _cfg(_=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            if not horizontal:
                canvas.itemconfigure(win, width=canvas.winfo_width())

        inner.bind("<Configure>", _cfg)
        canvas.bind("<Configure>", lambda e: _cfg())

        def _wheel(e):
            canvas.yview_scroll(int(-e.delta / 120), "units")

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        return inner

    # --- 전체 레이아웃: 왼쪽 미리보기 + 오른쪽 설정 ---
    def _build_layout(self):
        self._build_right_panel()
        self._build_left_preview()

    # ====================== 오른쪽: 설정 패널(스크롤) ======================
    def _build_right_panel(self):
        panel = Frame(self.root, bg=PANEL_BG, width=350)
        panel.pack(side="right", fill="y")
        panel.pack_propagate(False)
        content = self._scroll_area(panel, PANEL_BG, horizontal=False)

        Label(content, text="⚙ 설정", font=self.f_title, bg=PANEL_BG, fg=ACCENT)\
            .pack(pady=(18, 8))

        # 보기 형식(달력형/주방형)
        box0 = LabelFrame(content, text=" 보기 형식 ", font=self.f_label,
                          bg=PANEL_BG, fg="#333", padx=12, pady=8)
        box0.pack(fill="x", padx=16, pady=8)
        self.var_preset = StringVar(value=layouts.PRESET_CALENDAR)
        for pid in layouts.PRESETS:
            Radiobutton(box0, text=layouts.PRESET_LABELS[pid], value=pid,
                        variable=self.var_preset, command=self._on_preset_change,
                        font=self.f_label, bg=PANEL_BG, fg="#333", anchor="w",
                        selectcolor="white", activebackground=PANEL_BG)\
                .pack(fill="x", pady=2)

        # 식단 구성(메뉴/조건)
        box_r = LabelFrame(content, text=" 식단 구성 ", font=self.f_label,
                           bg=PANEL_BG, fg="#333", padx=12, pady=10)
        box_r.pack(fill="x", padx=16, pady=8)
        rrow = Frame(box_r, bg=PANEL_BG)
        rrow.pack(fill="x")
        Button(rrow, text="🍳 메뉴 설정", font=self.f_button, bg="#FFFFFF", relief="raised",
               pady=8, command=self.open_menu_settings)\
            .pack(side="left", expand=True, fill="x", padx=(0, 4))
        Button(rrow, text="🧩 조건 설정", font=self.f_button, bg="#FFFFFF", relief="raised",
               pady=8, command=self.open_conditions)\
            .pack(side="left", expand=True, fill="x", padx=(4, 0))
        self.var_pool_only = BooleanVar(value=store.get_pool_only())
        Checkbutton(box_r, text="추가된 메뉴만 사용 (끄면 모든 한식 메뉴에서 랜덤)",
                    font=self.f_label, bg=PANEL_BG, variable=self.var_pool_only,
                    command=self._on_pool_only, selectcolor="white",
                    activebackground=PANEL_BG, wraplength=290, justify="left", anchor="w")\
            .pack(fill="x", pady=(8, 0))

        # 연/월 + 만들기
        box1 = LabelFrame(content, text=" 식단표 만들기 ", font=self.f_label,
                          bg=PANEL_BG, fg="#333", padx=12, pady=12)
        box1.pack(fill="x", padx=16, pady=8)

        today = date.today()
        self.var_year = StringVar(value=str(today.year))
        self.var_month = StringVar(value=str(today.month))

        row = Frame(box1, bg=PANEL_BG)
        row.pack(fill="x", pady=4)
        Label(row, text="연도", font=self.f_label, bg=PANEL_BG).pack(side="left")
        OptionMenu(row, self.var_year, *[str(y) for y in range(today.year, today.year + 3)])\
            .pack(side="left", padx=(6, 14))
        Label(row, text="월", font=self.f_label, bg=PANEL_BG).pack(side="left")
        OptionMenu(row, self.var_month, *[str(m) for m in range(1, 13)])\
            .pack(side="left", padx=6)

        self.btn_make = Button(
            box1, text="식단표 만들기", font=self.f_button, bg=ACCENT, fg="white",
            activebackground="#1B5E20", relief="raised", pady=10, command=self.on_make,
        )
        self.btn_make.pack(fill="x", pady=(10, 2))

        self.var_status = StringVar(value="‘식단표 만들기’를 눌러 주세요.")
        Label(box1, textvariable=self.var_status, font=self.f_label, bg=PANEL_BG,
              fg="#555", wraplength=290, justify="left").pack(fill="x", pady=(8, 0))

        # 저장/복사/인쇄
        box2 = LabelFrame(content, text=" 내보내기 ", font=self.f_label,
                          bg=PANEL_BG, fg="#333", padx=12, pady=12)
        box2.pack(fill="x", padx=16, pady=8)
        self._mkbtn(box2, "💾 파일로 저장 (엑셀/텍스트)", self.on_save)
        self._mkbtn(box2, "📋 복사하기", self.on_copy)
        self._mkbtn(box2, "🖨 인쇄하기", self.on_print)

        # API 키
        box3 = LabelFrame(content, text=" API 키 ", font=self.f_label,
                          bg=PANEL_BG, fg="#333", padx=12, pady=12)
        box3.pack(fill="x", padx=16, pady=(8, 18))
        Label(box3, text="Google AI Studio 키를 입력하세요.",
              font=self.f_label, bg=PANEL_BG, fg="#666",
              wraplength=290, justify="left").pack(anchor="w")

        self.var_key = StringVar(value=app_config.get_api_key())
        self.ent_key = Entry(box3, textvariable=self.var_key, font=self.f_label, show="*")
        self.ent_key.pack(fill="x", pady=(8, 4), ipady=4)
        self.var_show = BooleanVar(value=False)
        Checkbutton(box3, text="키 보이기", font=self.f_label, bg=PANEL_BG,
                    variable=self.var_show, command=self._toggle_key,
                    selectcolor="white", activebackground=PANEL_BG).pack(anchor="w")
        Button(box3, text="키 저장", font=self.f_button, bg="#455A64", fg="white",
               pady=6, command=self.on_save_key).pack(fill="x", pady=(6, 0))

    def _mkbtn(self, parent, text, cmd):
        Button(parent, text=text, font=self.f_button, command=cmd,
               bg="#FFFFFF", relief="raised", pady=10)\
            .pack(fill="x", pady=4)

    # --- 메뉴/조건 설정 ---
    def open_menu_settings(self):
        settings_windows.MenuSettingsWindow(self.root)

    def open_conditions(self):
        settings_windows.ConditionsWindow(self.root)

    def _on_pool_only(self):
        store.set_pool_only(bool(self.var_pool_only.get()))

    # ====================== 왼쪽: 미리보기 ======================
    def _build_left_preview(self):
        left = Frame(self.root, bg=BG)
        left.pack(side="left", fill="both", expand=True)

        Label(left, text="🍚 식단표 미리보기", font=self.f_title, bg=BG, fg=ACCENT)\
            .pack(anchor="w", padx=16, pady=(16, 2))
        Label(left, text="칸을 클릭해 메뉴를 바로 고칠 수 있어요. (세밀한 꾸미기는 엑셀로 저장해서 편집)",
              font=self.f_label, bg=BG, fg="#777").pack(anchor="w", padx=16, pady=(0, 6))

        wrap = Frame(left, bg=BG)
        wrap.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.preview_inner = self._scroll_area(wrap, BG, horizontal=True)

    # --- 미리보기 렌더링 ---
    def _on_preset_change(self):
        self._flush_cells()
        self._render_preview()

    def _render_preview(self):
        for w in self.preview_inner.winfo_children():
            w.destroy()
        self._cells = []

        if not self.month_data or self.month_data.is_empty():
            Label(self.preview_inner,
                  text="아직 식단표가 없어요.\n오른쪽 [식단표 만들기]를 눌러 주세요.",
                  font=self.f_subtitle, bg=BG, fg="#AAA", justify="left")\
                .pack(anchor="w", padx=20, pady=40)
            return

        if self.var_preset.get() == layouts.PRESET_KITCHEN:
            self._render_kitchen(self.preview_inner, self.month_data)
        else:
            self._render_calendar(self.preview_inner, self.month_data)

    def _make_cell_entry(self, parent, day, section, idx, value, width, flat=False):
        if flat:  # 달력형: 테두리 없는 입력칸(한 칸 안에 줄바꿈처럼 보이게)
            e = Entry(parent, font=self.f_cell, width=width, justify="center",
                      relief="flat", bd=0, highlightthickness=0, bg="white")
        else:
            e = Entry(parent, font=self.f_cell, width=width, justify="center",
                      relief="solid", bd=1)
        e.insert(0, value)
        self._cells.append((e, day, section, idx))
        return e

    # 달력형(중식/석식 분리)
    def _render_calendar(self, parent, md):
        weeks = layouts.calendar_weeks(md.year, md.month)
        for section in SECTIONS:
            Label(parent, text=f"{md.month}월 식단표 ({section})",
                  font=self.f_section, bg=BG, fg=ACCENT, anchor="center")\
                .pack(fill="x", padx=6, pady=(12, 4))
            table = Frame(parent, bg=C_GRID)
            table.pack(anchor="w", padx=6, pady=(0, 6))

            for ci, wd in enumerate(WEEKDAYS_KR):
                Label(table, text=wd, font=self.f_grid, bg=C_HEADER, width=11,
                      relief="solid", bd=1).grid(row=0, column=ci, sticky="nsew",
                                                 padx=1, pady=1)
            r = 1
            for week in weeks:
                for ci, day in enumerate(week):
                    if not day:
                        Frame(table, bg=C_EMPTY, width=90, height=150)\
                            .grid(row=r, column=ci, sticky="nsew", padx=1, pady=1)
                        continue
                    cell = Frame(table, bg="white")
                    cell.grid(row=r, column=ci, sticky="nsew", padx=1, pady=1)
                    Label(cell, text=str(day), font=self.f_grid, bg="white",
                          fg="#333", anchor="w").pack(fill="x", padx=2, pady=(2, 0))
                    items = md.get(day, section)
                    for idx in range(ITEMS_PER_MEAL):
                        self._make_cell_entry(cell, day, section, idx, items[idx],
                                              11, flat=True)\
                            .pack(fill="x", padx=2, pady=0)
                r += 1

        Label(parent, text=layouts.FOOTER_NOTE, font=self.f_cell, bg=BG, fg="#C00000")\
            .pack(anchor="w", padx=6, pady=(4, 12))

    # 주방형(주간 중식+석식 통합)
    def _render_kitchen(self, parent, md):
        weeks = layouts.calendar_weeks(md.year, md.month)
        for week in weeks:
            if not any(d and md.meals.get(d) for d in week):
                continue
            block = Frame(parent, bg=C_GRID)
            block.pack(anchor="w", padx=6, pady=(10, 2))

            Label(block, text="구분", font=self.f_grid, bg=C_LUNCH, width=6,
                  relief="solid", bd=1).grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
            for ci, day in enumerate(week, start=1):
                wd = WEEKDAYS_KR[ci - 1]
                txt = f"{wd}요일 {day}일" if day else f"{wd}요일"
                Label(block, text=txt, font=self.f_grid, bg=C_LUNCH, width=12,
                      relief="solid", bd=1).grid(row=0, column=ci, sticky="nsew",
                                                 padx=1, pady=1)
            r = 1
            for section in SECTIONS:
                fill = C_LUNCH if section == "중식" else C_DINNER
                Label(block, text=section, font=self.f_grid, bg=fill, width=6,
                      relief="solid", bd=1).grid(row=r, column=0, rowspan=ITEMS_PER_MEAL,
                                                 sticky="nsew", padx=1, pady=1)
                for idx in range(ITEMS_PER_MEAL):
                    for ci, day in enumerate(week, start=1):
                        if day and md.has_meal(day, section):
                            self._make_cell_entry(block, day, section, idx,
                                                  md.get(day, section)[idx], 12)\
                                .grid(row=r + idx, column=ci, sticky="nsew", padx=1, pady=1)
                        else:
                            Label(block, text="", bg=C_EMPTY if not day else "white",
                                  width=12, relief="solid", bd=1)\
                                .grid(row=r + idx, column=ci, sticky="nsew", padx=1, pady=1)
                r += ITEMS_PER_MEAL

        Label(parent, text=layouts.FOOTER_NOTE, font=self.f_cell, bg=BG, fg="#C00000")\
            .pack(anchor="w", padx=6, pady=(6, 12))

    # --- 편집값 -> 데이터 반영 / 직렬화 ---
    def _flush_cells(self):
        if not self.month_data:
            return
        for e, day, section, idx in self._cells:
            try:
                self.month_data.set_item(day, section, idx, e.get().strip())
            except Exception:
                pass

    def _grid_to_text(self) -> str:
        self._flush_cells()
        return layouts.month_data_to_text(self.month_data) if self.month_data else ""

    def _has_content(self) -> bool:
        if not self.month_data or self.month_data.is_empty():
            messagebox.showinfo("안내", "먼저 식단표를 만들어 주세요.")
            return False
        return True

    # --- API 키 ---
    def _toggle_key(self):
        self.ent_key.config(show="" if self.var_show.get() else "*")

    def on_save_key(self):
        key = self.var_key.get().strip()
        if not key:
            messagebox.showwarning("확인", "키를 입력해 주세요.")
            return
        app_config.set_api_key(key)
        messagebox.showinfo("저장 완료", "API 키를 저장했어요. 이제 식단표를 만들 수 있습니다.")

    def _check_key_on_start(self):
        if not app_config.get_api_key():
            messagebox.showinfo(
                "처음 설정이 필요해요",
                "식단표를 만들려면 오른쪽 ‘API 키’ 칸에 키를 한 번 입력하고\n"
                "[키 저장]을 눌러 주세요. (한 번만 하면 됩니다)",
            )
            self.ent_key.focus_set()

    # --- 식단표 만들기(백그라운드) ---
    def on_make(self):
        if self._busy:
            return
        if not app_config.get_api_key():
            messagebox.showinfo("안내", "먼저 오른쪽에서 API 키를 저장해 주세요.")
            self.ent_key.focus_set()
            return

        # 메뉴 풀 / 조건 / 추가메뉴만 — 생성 전에 충돌 점검
        pool_dict = store.get_pool()
        conds = store.get_conditions()
        pool_only = bool(self.var_pool_only.get())
        conflicts = store.check_conflicts(pool_dict, conds, pool_only)
        if conflicts:
            messagebox.showerror("조건/메뉴 충돌",
                                 "아래 때문에 식단표를 만들 수 없어요:\n\n" + "\n".join(conflicts))
            return
        mpool = store.pool_to_menupool(pool_dict)

        self.cur_year, self.cur_month = int(self.var_year.get()), int(self.var_month.get())
        self._set_busy(True)
        self.var_status.set("식단표를 만들고 있어요... 잠시만 기다려 주세요.")

        year, month = self.cur_year, self.cur_month

        def worker():
            try:
                text, errors = generate_validated_menu(
                    year, month, model="gemini-2.5-flash",
                    api_key=app_config.get_api_key(), pool=mpool,
                    conditions=conds, pool_only=pool_only,
                    progress=lambda msg: self.root.after(0, self.var_status.set, msg),
                )
                self.root.after(0, self._on_done, text, errors)
            except Exception as e:  # noqa: BLE001
                self.root.after(0, self._on_error, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_done(self, text: str, errors: list[str]):
        self.month_data = layouts.build_month_data(text, self.cur_year, self.cur_month)
        self._render_preview()
        self._set_busy(False)
        if errors:
            self.var_status.set(f"완성했어요. 규칙 {len(errors)}건은 표에서 직접 확인해 주세요.")
            messagebox.showwarning(
                "일부 규칙 안내",
                "대부분 규칙은 맞췄지만 아래 항목은 확인해 주세요:\n\n" + "\n".join(errors[:8]),
            )
        else:
            self.var_status.set("완성! 모든 규칙 통과. 칸을 클릭해 수정할 수 있어요.")

    def _on_error(self, msg: str):
        self._set_busy(False)
        self.var_status.set("문제가 생겼어요. 인터넷 연결과 API 키를 확인해 주세요.")
        messagebox.showerror("오류", f"식단표를 만들지 못했어요.\n\n{msg}")

    def _set_busy(self, busy: bool):
        self._busy = busy
        self.btn_make.config(state=DISABLED if busy else NORMAL,
                             text="만드는 중..." if busy else "식단표 만들기")

    # --- 저장 / 복사 / 인쇄 ---
    def on_save(self):
        if not self._has_content():
            return
        y, m = self.cur_year, self.cur_month
        path = filedialog.asksaveasfilename(
            title="식단표 저장", defaultextension=".xlsx",
            initialfile=f"식단표_{y}년{m}월",
            filetypes=[("엑셀 파일", "*.xlsx"), ("텍스트 파일", "*.txt")],
        )
        if not path:
            return
        try:
            text = self._grid_to_text()
            if path.lower().endswith(".txt"):
                exporters.save_txt(text, path)
            else:
                exporters.save_xlsx(text, path, title=f"{y}년 {m}월 식단표",
                                    preset=self.var_preset.get(), year=y, month=m)
            messagebox.showinfo("저장 완료", f"저장했어요:\n{path}")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("오류", f"저장하지 못했어요.\n\n{e}")

    def on_copy(self):
        if not self._has_content():
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self._grid_to_text())
        self.var_status.set("복사했어요! 카카오톡·문자 등에 붙여넣기(Ctrl+V) 하세요.")

    def on_print(self):
        if not self._has_content():
            return
        y, m = self.cur_year, self.cur_month
        try:
            path = exporters.print_text(self._grid_to_text(), title=f"{y}년 {m}월 식단표")
            if sys.platform.startswith("win"):
                self.var_status.set("프린터로 보냈어요. 인쇄 대화상자를 확인하세요.")
            else:
                messagebox.showinfo("인쇄 안내",
                                    f"이 컴퓨터에서는 자동 인쇄가 지원되지 않아요.\n"
                                    f"아래 파일을 열어 인쇄하세요:\n{path}")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("오류", f"인쇄하지 못했어요.\n\n{e}")


# 지연 import(메뉴 생성은 실제 사용 시점에만 필요)
from menu_planner import generate_validated_menu  # noqa: E402


def main():
    root = Tk()
    MenuPlannerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
