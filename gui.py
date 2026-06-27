# -*- coding: utf-8 -*-
"""
한식 뷔페 식단표 생성기 — 데스크톱 GUI (어르신 친화, 2단 레이아웃)
===================================================================
- 왼쪽: 엑셀처럼 보이는 표 미리보기(셀 더블클릭으로 수정 가능)
- 오른쪽: 설정 패널(연/월 선택·식단표 만들기·API 키·저장/복사/인쇄)
- API 키는 오른쪽 설정에서 1회 입력하면 PC에 저장되어 자동 사용

실행:    python gui.py
빌드:    GitHub Actions(.github/workflows/build-windows.yml) 또는 build_windows.bat
"""

from __future__ import annotations

import sys
import threading
from datetime import date
from tkinter import (
    Tk, StringVar, BooleanVar, END, DISABLED, NORMAL,
    Label, Button, Entry, Frame, Checkbutton, OptionMenu, LabelFrame,
    messagebox, filedialog,
)
from tkinter import ttk
from tkinter import font as tkfont

import app_config
import exporters
from menu_planner import parse_menu_text, generate_validated_menu

# 어르신 가독성을 위한 글씨 크기
FONT_FAMILY = "맑은 고딕"   # Windows 기본 한글 폰트(없으면 시스템 기본으로 대체됨)
SZ_TITLE = 22
SZ_LABEL = 14
SZ_BUTTON = 15
SZ_GRID = 13

BG = "#FAFAFA"
ACCENT = "#2E7D32"   # 초록(식단/건강 느낌)
PANEL_BG = "#F1F4F1"

# 표(엑셀 미리보기) 컬럼 정의
COLUMNS = ["구분", "날짜", "메인요리", "반찬1", "반찬2", "반찬3", "김치", "국"]
COL_WIDTHS = [70, 110, 150, 130, 130, 130, 80, 130]
EDITABLE_FROM = 2  # 0=구분,1=날짜 는 잠금. 2번째 컬럼부터 수정 가능


class MenuPlannerApp:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("한식 뷔페 식단표 만들기")
        self.root.configure(bg=BG)
        self.root.geometry("1200x780")
        self.root.minsize(1040, 680)

        self._busy = False
        self._build_fonts()
        self._build_layout()
        self._check_key_on_start()

    # --- 폰트 ---
    def _build_fonts(self):
        self.f_title = tkfont.Font(family=FONT_FAMILY, size=SZ_TITLE, weight="bold")
        self.f_label = tkfont.Font(family=FONT_FAMILY, size=SZ_LABEL)
        self.f_button = tkfont.Font(family=FONT_FAMILY, size=SZ_BUTTON, weight="bold")
        self.f_grid = tkfont.Font(family=FONT_FAMILY, size=SZ_GRID)
        self.f_grid_head = tkfont.Font(family=FONT_FAMILY, size=SZ_GRID, weight="bold")

    # --- 전체 레이아웃: 왼쪽 미리보기 + 오른쪽 설정 ---
    def _build_layout(self):
        self._build_right_panel()   # 먼저 오른쪽(고정폭) 배치
        self._build_left_preview()  # 나머지를 왼쪽 표가 채움

    # ====================== 오른쪽: 설정 패널 ======================
    def _build_right_panel(self):
        panel = Frame(self.root, bg=PANEL_BG, width=340)
        panel.pack(side="right", fill="y")
        panel.pack_propagate(False)  # 고정폭 유지

        Label(panel, text="⚙ 설정", font=self.f_title, bg=PANEL_BG, fg=ACCENT)\
            .pack(pady=(20, 10))

        # 1) 연/월 + 만들기
        box1 = LabelFrame(panel, text=" 식단표 만들기 ", font=self.f_label,
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
              fg="#555", wraplength=280, justify="left").pack(fill="x", pady=(8, 0))

        # 2) 저장/복사/인쇄
        box2 = LabelFrame(panel, text=" 내보내기 ", font=self.f_label,
                          bg=PANEL_BG, fg="#333", padx=12, pady=12)
        box2.pack(fill="x", padx=16, pady=8)
        self._mkbtn(box2, "💾 파일로 저장 (엑셀/텍스트)", self.on_save)
        self._mkbtn(box2, "📋 복사하기", self.on_copy)
        self._mkbtn(box2, "🖨 인쇄하기", self.on_print)

        # 3) API 키 설정(인라인)
        box3 = LabelFrame(panel, text=" API 키 ", font=self.f_label,
                          bg=PANEL_BG, fg="#333", padx=12, pady=12)
        box3.pack(fill="x", padx=16, pady=8)
        Label(box3, text="Google AI Studio 키를 입력하세요.",
              font=self.f_label, bg=PANEL_BG, fg="#666",
              wraplength=280, justify="left").pack(anchor="w")

        self.var_key = StringVar(value=app_config.get_api_key())
        self.ent_key = Entry(box3, textvariable=self.var_key, font=self.f_label, show="*")
        self.ent_key.pack(fill="x", pady=(8, 4), ipady=4)
        self.var_show = BooleanVar(value=False)
        Checkbutton(box3, text="키 보이기", font=self.f_label, bg=PANEL_BG,
                    variable=self.var_show, command=self._toggle_key).pack(anchor="w")
        Button(box3, text="키 저장", font=self.f_button, bg="#455A64", fg="white",
               pady=6, command=self.on_save_key).pack(fill="x", pady=(6, 0))

    def _mkbtn(self, parent, text, cmd):
        Button(parent, text=text, font=self.f_button, command=cmd,
               bg="#FFFFFF", relief="raised", pady=10)\
            .pack(fill="x", pady=4)

    # ====================== 왼쪽: 엑셀 미리보기 표 ======================
    def _build_left_preview(self):
        left = Frame(self.root, bg=BG)
        left.pack(side="left", fill="both", expand=True)

        Label(left, text="🍚 식단표 미리보기", font=self.f_title, bg=BG, fg=ACCENT)\
            .pack(anchor="w", padx=16, pady=(18, 2))
        Label(left, text="셀을 더블클릭하면 메뉴를 바로 고칠 수 있어요.",
              font=self.f_label, bg=BG, fg="#777").pack(anchor="w", padx=16, pady=(0, 8))

        # 엑셀 느낌의 표 스타일
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Menu.Treeview", font=self.f_grid, rowheight=34,
                        background="white", fieldbackground="white", borderwidth=1)
        style.configure("Menu.Treeview.Heading", font=self.f_grid_head,
                        background="#D9E1F2", relief="raised")
        style.map("Menu.Treeview", background=[("selected", "#C8E6C9")],
                  foreground=[("selected", "black")])

        grid_wrap = Frame(left, bg=BG)
        grid_wrap.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.tree = ttk.Treeview(grid_wrap, columns=COLUMNS, show="headings",
                                 style="Menu.Treeview")
        for col, w in zip(COLUMNS, COL_WIDTHS):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="center", stretch=True)

        vsb = ttk.Scrollbar(grid_wrap, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(grid_wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        grid_wrap.rowconfigure(0, weight=1)
        grid_wrap.columnconfigure(0, weight=1)

        # 줄무늬(가독성)
        self.tree.tag_configure("lunch", background="#FFFDF5")   # 중식
        self.tree.tag_configure("dinner", background="#F2F7FF")  # 석식

        # 셀 더블클릭 → 수정
        self.tree.bind("<Double-1>", self._on_cell_edit)

    # --- 셀 편집 ---
    def _on_cell_edit(self, event):
        if self._busy:
            return
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        col = self.tree.identify_column(event.x)   # 예: '#3'
        row = self.tree.identify_row(event.y)
        if not row:
            return
        col_idx = int(col[1:]) - 1
        if col_idx < EDITABLE_FROM:
            return  # 구분/날짜는 잠금
        x, y, w, h = self.tree.bbox(row, col)
        cur = self.tree.set(row, COLUMNS[col_idx])

        editor = Entry(self.tree, font=self.f_grid, justify="center")
        editor.place(x=x, y=y, width=w, height=h)
        editor.insert(0, cur)
        editor.focus_set()
        editor.select_range(0, END)

        def commit(_=None):
            self.tree.set(row, COLUMNS[col_idx], editor.get().strip())
            editor.destroy()

        editor.bind("<Return>", commit)
        editor.bind("<FocusOut>", commit)
        editor.bind("<Escape>", lambda e: editor.destroy())

    # --- 표 채우기 / 표 → 텍스트 ---
    def _populate_grid(self, text: str):
        self.tree.delete(*self.tree.get_children())
        for m in parse_menu_text(text):
            items = list(m.items) + [""] * (6 - len(m.items))
            tag = "lunch" if m.section == "중식" else "dinner"
            self.tree.insert("", END, values=(m.section, m.date_label, *items[:6]), tags=(tag,))

    def _grid_to_text(self) -> str:
        """현재 표(수정 포함)를 식단표 텍스트로 직렬화."""
        sections: dict[str, list[str]] = {}
        order: list[str] = []
        for iid in self.tree.get_children():
            vals = self.tree.item(iid, "values")
            sec, datelabel, items = vals[0], vals[1], vals[2:8]
            if sec not in sections:
                sections[sec] = []
                order.append(sec)
            sections[sec].append(f"{datelabel}: " + ", ".join(items))
        lines: list[str] = []
        for sec in order:
            lines.append(f"[{sec}]")
            lines.extend(sections[sec])
        return "\n".join(lines)

    def _has_content(self) -> bool:
        if not self.tree.get_children():
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
        year, month = int(self.var_year.get()), int(self.var_month.get())
        self._set_busy(True)
        self.var_status.set("식단표를 만들고 있어요... 잠시만 기다려 주세요.")

        def worker():
            try:
                text, errors = generate_validated_menu(
                    year, month, model="gemini-2.5-flash",
                    api_key=app_config.get_api_key(),
                    progress=lambda msg: self.root.after(0, self.var_status.set, msg),
                )
                self.root.after(0, self._on_done, text, errors)
            except Exception as e:  # noqa: BLE001
                self.root.after(0, self._on_error, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_done(self, text: str, errors: list[str]):
        self._populate_grid(text)
        self._set_busy(False)
        if errors:
            self.var_status.set(f"완성했어요. 규칙 {len(errors)}건은 표에서 직접 확인해 주세요.")
            messagebox.showwarning(
                "일부 규칙 안내",
                "대부분 규칙은 맞췄지만 아래 항목은 확인해 주세요:\n\n" + "\n".join(errors[:8]),
            )
        else:
            self.var_status.set("완성! 모든 규칙 통과. 셀을 더블클릭해 수정할 수 있어요.")

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
        y, m = self.var_year.get(), self.var_month.get()
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
                exporters.save_xlsx(text, path, title=f"{y}년 {m}월 식단표")
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
        y, m = self.var_year.get(), self.var_month.get()
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


def main():
    root = Tk()
    MenuPlannerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
