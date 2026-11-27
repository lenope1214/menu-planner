# -*- coding: utf-8 -*-
"""
과거 식단 기록 창
==================
‘m월 d일에 실제로 무엇을 냈는지’를 넣어 두는 창.
한 행 = 하루, 왼쪽이 중식 6칸 / 오른쪽이 석식 6칸 (엑셀처럼 옆으로 채운다).

입력 방법 세 가지
1) 표에 직접 타이핑 (연/월을 고르고 그 달을 채운다)
2) [엑셀에서 불러오기] — 예전에 쓰던 식단표 .xlsx 를 통째로 읽어 온다
3) 메인 화면의 [지금 표를 기록에 저장] — 만든 식단을 그대로 기록에 넣는다

빈 줄은 저장하지 않는다. 기록은 history.json 에 쌓이고 GitHub 동기화도 함께 된다.
"""

from __future__ import annotations

import calendar
from datetime import date
from tkinter import (
    Toplevel, Label, Button, Entry, Frame, Canvas, StringVar,
    OptionMenu, messagebox, filedialog,
)
from tkinter import ttk

import history
import layouts
import store
from layouts import ITEMS_PER_MEAL, SECTIONS
from settings_windows import PANEL_BG, ACCENT, _center, _f, _grab

# 한 끼 6칸의 자리 이름(입력 표 머리글)
SLOT_LABELS = ["메인", "반찬", "반찬", "반찬", "김치류", "국"]
KIMCHI_IDX = 4
KIMCHI_TEXT = "김치류"

C_LUNCH = "#E4DFEC"
C_DINNER = "#FCE4D6"
C_WEEKEND = "#FDF3F3"
CELL_W = 11


def prev_month(today: date | None = None) -> tuple[int, int]:
    """오늘 기준 ‘지난 달’. 과거 기록을 넣는 창이니 기본값을 여기에 맞춘다."""
    d = today or date.today()
    return (d.year - 1, 12) if d.month == 1 else (d.year, d.month - 1)


class HistoryWindow:
    def __init__(self, parent, on_close=None):
        self._on_close = on_close
        self.cells: dict[tuple[int, str, int], Entry] = {}
        self.year, self.month = prev_month()

        self.win = Toplevel(parent)
        self.win.title("과거 식단 기록")
        self.win.configure(bg=PANEL_BG)
        _center(self.win, 1180, 720, parent)
        self.win.transient(parent)
        self.win.protocol("WM_DELETE_WINDOW", self._close)
        _grab(self.win)

        Label(self.win, text="📅 과거 식단 기록", font=_f(18, True), bg=PANEL_BG, fg=ACCENT)\
            .pack(pady=(14, 2))
        Label(self.win, text="그날 실제로 낸 메뉴를 적어 주세요. 빈 줄은 저장하지 않습니다. "
                             "(김치류 칸은 비워 두면 저장할 때 자동으로 채워집니다)",
              font=_f(11), bg=PANEL_BG, fg="#666").pack(pady=(0, 8))

        self._build_top()
        self._build_grid_area()
        self._build_buttons()
        self._load_month()

    # ---- 위: 연/월 선택 + 기록 현황 ----
    def _build_top(self):
        top = Frame(self.win, bg=PANEL_BG)
        top.pack(fill="x", padx=14)

        Label(top, text="연도", font=_f(12), bg=PANEL_BG).pack(side="left")
        this_year = date.today().year
        self.v_year = StringVar(value=str(self.year))
        OptionMenu(top, self.v_year, *[str(y) for y in range(this_year - 5, this_year + 2)],
                   command=lambda *_a: self._switch_month()).pack(side="left", padx=(6, 14))
        Label(top, text="월", font=_f(12), bg=PANEL_BG).pack(side="left")
        self.v_month = StringVar(value=str(self.month))
        OptionMenu(top, self.v_month, *[str(m) for m in range(1, 13)],
                   command=lambda *_a: self._switch_month()).pack(side="left", padx=6)

        self.v_summary = StringVar(value="")
        Label(top, textvariable=self.v_summary, font=_f(11), bg=PANEL_BG, fg="#2E7D32")\
            .pack(side="right")

    # ---- 가운데: 스크롤 표 ----
    def _build_grid_area(self):
        wrap = Frame(self.win, bg=PANEL_BG)
        wrap.pack(fill="both", expand=True, padx=14, pady=(8, 4))

        canvas = Canvas(wrap, bg="white", highlightthickness=0)
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        hsb = ttk.Scrollbar(wrap, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        hsb.pack(side="bottom", fill="x")
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self.grid_inner = Frame(canvas, bg="white")
        canvas.create_window((0, 0), window=self.grid_inner, anchor="nw")
        self.grid_inner.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Enter>", lambda e: canvas.bind_all(
            "<MouseWheel>", lambda ev: canvas.yview_scroll(int(-ev.delta / 120), "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

    # ---- 아래: 버튼 ----
    def _build_buttons(self):
        bar = Frame(self.win, bg=PANEL_BG)
        bar.pack(fill="x", padx=14, pady=(4, 12))
        Button(bar, text="💾 이 달 기록 저장", font=_f(12, True), bg=ACCENT, fg="white",
               padx=10, pady=6, command=self._save).pack(side="left")
        Button(bar, text="📂 엑셀에서 불러오기", font=_f(12), padx=10, pady=6,
               command=self._import_xlsx).pack(side="left", padx=6)
        Button(bar, text="🍳 기록의 메뉴를 메뉴 풀에 추가", font=_f(12), padx=10, pady=6,
               command=self._fill_pool).pack(side="left", padx=6)
        Button(bar, text="🧹 이 달 기록 지우기", font=_f(12), padx=10, pady=6,
               command=self._clear_month).pack(side="left", padx=6)
        Button(bar, text="닫기", font=_f(12), padx=14, pady=6,
               command=self._close).pack(side="right")

    # ------------------------------------------------------------------ 표
    def _load_month(self):
        for w in self.grid_inner.winfo_children():
            w.destroy()
        self.cells = {}

        # 머리글 2줄: 끼니(6칸 묶음) / 자리 이름
        Label(self.grid_inner, text="날짜", font=_f(11, True), bg="#EEEEEE", width=8,
              relief="solid", bd=1).grid(row=0, column=0, rowspan=2, sticky="nsew")
        for si, section in enumerate(SECTIONS):
            c0 = 1 + si * ITEMS_PER_MEAL
            Label(self.grid_inner, text=section, font=_f(12, True),
                  bg=(C_LUNCH if section == "중식" else C_DINNER), relief="solid", bd=1)\
                .grid(row=0, column=c0, columnspan=ITEMS_PER_MEAL, sticky="nsew")
            for i, name in enumerate(SLOT_LABELS):
                Label(self.grid_inner, text=name, font=_f(10), bg="#F5F5F5", width=CELL_W,
                      relief="solid", bd=1).grid(row=1, column=c0 + i, sticky="nsew")

        md = history.get_month(self.year, self.month)
        _, last_day = calendar.monthrange(self.year, self.month)
        for day in range(1, last_day + 1):
            r = day + 1
            wd = layouts.weekday_of(self.year, self.month, day)
            weekend = wd in ("토", "일")
            Label(self.grid_inner, text=f"{day}일({wd})", font=_f(11, True),
                  bg=(C_WEEKEND if weekend else "#FAFAFA"), width=8,
                  relief="solid", bd=1).grid(row=r, column=0, sticky="nsew")
            for si, section in enumerate(SECTIONS):
                items = md.get(day, section) if md.has_meal(day, section) \
                    else [""] * ITEMS_PER_MEAL
                for i in range(ITEMS_PER_MEAL):
                    e = Entry(self.grid_inner, font=_f(11), width=CELL_W,
                              relief="solid", bd=1, justify="center")
                    e.insert(0, items[i])
                    e.grid(row=r, column=1 + si * ITEMS_PER_MEAL + i, sticky="nsew")
                    self.cells[(day, section, i)] = e

        self.v_summary.set("기록 현황 — " + history.summary())

    def _collect(self) -> layouts.MonthData:
        """표 → MonthData. 한 줄이라도 채운 끼니만 담고 김치류는 자동으로 채운다."""
        md = layouts.MonthData(year=self.year, month=self.month)
        _, last_day = calendar.monthrange(self.year, self.month)
        for day in range(1, last_day + 1):
            for section in SECTIONS:
                items = [self.cells[(day, section, i)].get().strip()
                         for i in range(ITEMS_PER_MEAL)]
                if not any(items):
                    continue
                if not items[KIMCHI_IDX] and sum(1 for x in items if x) >= 2:
                    items[KIMCHI_IDX] = KIMCHI_TEXT
                md.meals.setdefault(day, {})[section] = items
        return md

    def _is_dirty(self) -> bool:
        return self._collect().meals != history.get_month(self.year, self.month).meals

    # ------------------------------------------------------------- 동작
    def _switch_month(self):
        """연/월을 바꾸기 전에 저장하지 않은 내용이 있으면 물어본다."""
        y, m = int(self.v_year.get()), int(self.v_month.get())
        if (y, m) == (self.year, self.month):
            return
        if self._is_dirty():
            ans = messagebox.askyesnocancel(
                "저장할까요?", f"{self.year}년 {self.month}월에 바뀐 내용이 있어요.\n"
                               f"저장하고 넘어갈까요?", parent=self.win)
            if ans is None:
                self.v_year.set(str(self.year))
                self.v_month.set(str(self.month))
                return
            if ans:
                history.save_month(self._collect())
        self.year, self.month = y, m
        self._load_month()

    def _save(self):
        n = history.save_month(self._collect())
        self._load_month()
        messagebox.showinfo("저장 완료",
                            f"{self.year}년 {self.month}월 기록 {n}일치를 저장했어요.",
                            parent=self.win)

    def _clear_month(self):
        if not messagebox.askyesno(
                "확인", f"{self.year}년 {self.month}월 기록을 모두 지울까요?",
                parent=self.win):
            return
        history.delete_month(self.year, self.month)
        self._load_month()

    def _import_xlsx(self):
        path = filedialog.askopenfilename(
            title="예전 식단표 엑셀 파일 고르기", parent=self.win,
            filetypes=[("엑셀 파일", "*.xlsx")])
        if not path:
            return
        if self._is_dirty() and messagebox.askyesno(
                "저장할까요?", "표에 저장하지 않은 내용이 있어요. 먼저 저장할까요?",
                parent=self.win):
            history.save_month(self._collect())
        try:
            done = history.import_xlsx(path, self.year, self.month)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("오류", f"엑셀을 읽지 못했어요.\n\n{e}", parent=self.win)
            return
        if not done:
            messagebox.showwarning(
                "읽을 내용이 없어요",
                "이 파일에서 식단을 찾지 못했어요.\n"
                "이 프로그램에서 저장한 식단표(.xlsx) 서식이어야 읽을 수 있어요.",
                parent=self.win)
            return
        lines = "\n".join(f"· {y}년 {m}월 — {n}일치" for y, m, n in done)
        y, m, _n = done[0]
        self.year, self.month = y, m
        self.v_year.set(str(y))
        self.v_month.set(str(m))
        self._load_month()
        messagebox.showinfo("불러오기 완료", f"기록에 넣었어요.\n\n{lines}", parent=self.win)

    def _fill_pool(self):
        added = store.add_missing_from_history()
        total = sum(added.values())
        if not total:
            messagebox.showinfo("안내", "기록에 나온 메뉴는 이미 모두 메뉴 풀에 있어요.",
                                parent=self.win)
            return
        messagebox.showinfo(
            "추가 완료",
            f"메뉴 풀에 {total}개를 새로 넣었어요.\n"
            f"· 메인 {added['mains']}개 · 반찬 {added['sides']}개 · 국 {added['soups']}개\n\n"
            f"메인 요리의 맛·끼니 같은 세부 설정은 ‘메뉴 설정’에서 고쳐 주세요.",
            parent=self.win)

    def _close(self):
        if self._is_dirty():
            ans = messagebox.askyesnocancel(
                "저장할까요?", "저장하지 않은 내용이 있어요. 저장하고 닫을까요?",
                parent=self.win)
            if ans is None:
                return
            if ans:
                history.save_month(self._collect())
        self.win.destroy()
        if self._on_close:
            self._on_close()
