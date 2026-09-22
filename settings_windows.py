# -*- coding: utf-8 -*-
"""
설정 창(Toplevel)
==================
- MenuSettingsWindow : 메인/반찬/국 메뉴 등록·조회·수정·삭제
- ConditionsWindow   : 식단 조건 등록·조회·수정·삭제
둘 다 store 를 통해 menu-planner 폴더 JSON 에 즉시 저장한다.
"""

from __future__ import annotations

import os

from tkinter import (
    Toplevel, Listbox, Label, Button, Entry, Frame, Text, StringVar, BooleanVar,
    OptionMenu, Checkbutton, END, SINGLE, filedialog, messagebox,
)
from tkinter import ttk
from tkinter import font as tkfont

import store
import conditions as cond_mod
import importers

FONT_FAMILY = "맑은 고딕"
SCOPE_KR = {"both": "모두", "lunch": "중식", "dinner": "석식"}
SCOPE_FROM = {v: k for k, v in SCOPE_KR.items()}
PANEL_BG = "#F1F4F1"
ACCENT = "#2E7D32"


def _f(size=12, bold=False):
    return tkfont.Font(family=FONT_FAMILY, size=size, weight="bold" if bold else "normal")


def _grab(win):
    """모달 grab(창이 아직 표시 전이면 실패할 수 있어 방어적으로)."""
    try:
        win.grab_set()
    except Exception:
        pass


def _center(win, w, h, parent):
    try:
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        x, y = px + (pw - w) // 2, py + (ph - h) // 2
    except Exception:
        x, y = 200, 120
    win.geometry(f"{w}x{h}+{max(x, 0)}+{max(y, 0)}")


# ============================================================ 메뉴 설정
class MenuSettingsWindow:
    """메뉴 등록/수정/삭제 + 검색 + 정렬 + 일시정지.

    Treeview 의 iid 는 항상 '풀 리스트의 원래 인덱스'로 둔다. 그래야 검색으로
    걸러내거나 정렬로 순서를 바꿔도 선택한 행 → 실제 항목 대응이 어긋나지 않는다.
    """

    # (컬럼id, 헤더, 너비, 정렬)
    COLS = {
        "mains": [("name", "이름", 160, "w"), ("state", "상태", 110, "center"),
                  ("flavor", "맛", 60, "center"), ("scope", "끼니", 60, "center"),
                  ("fish", "생선", 55, "center"), ("weekday", "평일만", 65, "center"),
                  ("max", "월최대", 65, "center")],
        "sides": [("name", "반찬 이름", 300, "w"), ("state", "상태", 150, "center")],
        "soups": [("name", "국 이름", 300, "w"), ("state", "상태", 150, "center")],
    }
    TABS = (("mains", "메인 요리"), ("sides", "반찬"), ("soups", "국"))

    def __init__(self, parent, on_close=None):
        self.pool = store.get_pool()
        self._on_close = on_close
        self.tabs: dict = {}
        self.search: dict = {}
        self.counts: dict = {}
        self.pause_btns: dict = {}
        # (정렬 컬럼, 내림차순). None = 등록한 순서 그대로 — 첫 화면은 손대지 않는다.
        self.sort: dict = {k: (None, False) for k, _ in self.TABS}

        self.win = Toplevel(parent)
        self.win.title("메뉴 설정")
        self.win.configure(bg=PANEL_BG)
        _center(self.win, 820, 600, parent)
        self.win.transient(parent)
        self.win.protocol("WM_DELETE_WINDOW", self._close)
        _grab(self.win)

        Label(self.win, text="🍳 메뉴 설정", font=_f(18, True), bg=PANEL_BG, fg=ACCENT)\
            .pack(pady=(14, 4))
        Label(self.win, text="검색해서 이미 등록했는지 확인하고, 머리글을 눌러 정렬할 수 있어요. "
                             "당분간 못 내는 메뉴는 ‘일시정지’ 하세요.",
              font=_f(11), bg=PANEL_BG, fg="#666").pack(pady=(0, 8))

        style = ttk.Style(self.win)
        style.configure("Menu.Treeview", font=_f(12), rowheight=30,
                        background="white", fieldbackground="white")
        style.configure("Menu.Treeview.Heading", font=_f(12, True))

        nb = ttk.Notebook(self.win)
        nb.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        for key, title in self.TABS:
            self._build_tab(nb, key, title)

    def _close(self):
        self.win.destroy()
        if self._on_close:
            self._on_close()

    # ---- 탭 구성 ----
    def _build_tab(self, nb, key, title):
        tab = Frame(nb, bg="white")
        nb.add(tab, text=f"  {title}  ")

        # 검색줄
        top = Frame(tab, bg="white")
        top.pack(fill="x", padx=10, pady=(10, 0))
        Label(top, text="🔍 검색", font=_f(12), bg="white").pack(side="left")
        var = StringVar()
        self.search[key] = var
        ent = Entry(top, textvariable=var, font=_f(12))
        ent.pack(side="left", fill="x", expand=True, padx=6)
        var.trace_add("write", lambda *_a, k=key: self._refresh(k))
        Button(top, text="지우기", font=_f(11), command=lambda: var.set(""))\
            .pack(side="left")
        self.counts[key] = Label(top, text="", font=_f(11), bg="white", fg="#666")
        self.counts[key].pack(side="left", padx=(10, 0))

        body = Frame(tab, bg="white")
        body.pack(fill="both", expand=True)

        cols = self.COLS[key]
        tv = ttk.Treeview(body, columns=[c[0] for c in cols], show="headings",
                          selectmode="browse", style="Menu.Treeview")
        for cid, _head, width, anchor in cols:
            tv.heading(cid, command=lambda c=cid, k=key: self._sort_by(k, c))
            tv.column(cid, width=width, anchor=anchor, stretch=(cid == "name"))
        tv.tag_configure("paused", foreground="#9E9E9E")
        tv.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        sb = ttk.Scrollbar(body, orient="vertical", command=tv.yview)
        sb.pack(side="left", fill="y", pady=10)
        tv.configure(yscrollcommand=sb.set)
        self.tabs[key] = tv

        btns = Frame(body, bg="white")
        btns.pack(side="left", fill="y", padx=10, pady=10)
        Button(btns, text="추가", font=_f(12, True), width=10,
               command=lambda: self._add(key)).pack(pady=4)
        Button(btns, text="수정", font=_f(12, True), width=10,
               command=lambda: self._edit(key)).pack(pady=4)
        Button(btns, text="삭제", font=_f(12, True), width=10,
               command=lambda: self._delete(key)).pack(pady=4)
        self.pause_btns[key] = Button(btns, text="⏸ 일시정지", font=_f(11, True), width=10,
                                      command=lambda: self._toggle_pause(key))
        self.pause_btns[key].pack(pady=(16, 4))

        tv.bind("<Double-1>", lambda e: self._edit(key))
        tv.bind("<<TreeviewSelect>>", lambda e, k=key: self._sync_pause_btn(k))
        self._refresh(key)

    # ---- 데이터 ----
    def _items(self, key):
        return self.pool[key]

    def _name_at(self, key, i):
        it = self._items(key)[i]
        return it.get("name", "") if key == "mains" else it

    def _state_text(self, key, name):
        if not store.is_paused(key, name):
            return "사용"
        note = store.paused_note(key, name)
        return f"⏸ {note}" if note else "⏸ 일시정지"

    def _row_values(self, key, item):
        name = item.get("name", "") if key == "mains" else item
        state = self._state_text(key, name)
        if key != "mains":
            return (name, state)
        return (name, state, item.get("flavor", ""),
                SCOPE_KR.get(item.get("meal_scope", "both"), "모두"),
                "○" if item.get("is_fish") else "",
                "○" if item.get("weekday_only") else "",
                item.get("monthly_max") or "")

    # ---- 검색/정렬/표시 ----
    @staticmethod
    def _sortable(v):
        """숫자로 보이는 값은 숫자로 정렬(‘10’이 ‘2’보다 앞에 오지 않도록)."""
        s = str(v).strip()
        return (0, int(s), "") if s.isdigit() else (1, 0, s)

    def _sort_by(self, key, col):
        """머리글 클릭: 처음엔 오름차순, 같은 컬럼을 또 누르면 내림차순."""
        cur_col, rev = self.sort[key]
        self.sort[key] = (col, (not rev) if col == cur_col else False)
        self._refresh(key)

    def _refresh(self, key, select=None):
        tv = self.tabs[key]
        cols = self.COLS[key]
        sort_col, rev = self.sort[key]

        # 머리글에 정렬 방향 표시
        for cid, head, _w, _a in cols:
            arrow = ("  ▼" if rev else "  ▲") if cid == sort_col else ""
            tv.heading(cid, text=head + arrow)

        q = self.search[key].get().strip().lower()
        rows = []
        for i, it in enumerate(self._items(key)):
            vals = self._row_values(key, it)
            if q and q not in str(vals[0]).lower():
                continue
            rows.append((i, vals))

        if sort_col is not None:
            ci = next((n for n, c in enumerate(cols) if c[0] == sort_col), 0)
            rows.sort(key=lambda r: self._sortable(r[1][ci]), reverse=rev)

        tv.delete(*tv.get_children())
        for i, vals in rows:
            paused = store.is_paused(key, self._name_at(key, i))
            tv.insert("", "end", iid=str(i), values=vals,
                      tags=("paused",) if paused else ())

        total = len(self._items(key))
        if q:
            if rows:
                self.counts[key].config(text=f"‘{q}’ {len(rows)}개 찾음 (전체 {total}개)",
                                        fg="#2E7D32")
            else:
                self.counts[key].config(text=f"‘{q}’ 없음 — 아직 등록 안 됐어요",
                                        fg="#C62828")
        else:
            self.counts[key].config(text=f"전체 {total}개", fg="#666")

        if select is not None and tv.exists(str(select)):
            tv.selection_set(str(select))
            tv.see(str(select))
        self._sync_pause_btn(key)

    def _sel(self, key):
        s = self.tabs[key].selection()
        return int(s[0]) if s else None

    # ---- 일시정지 ----
    def _sync_pause_btn(self, key):
        i = self._sel(key)
        paused = i is not None and store.is_paused(key, self._name_at(key, i))
        self.pause_btns[key].config(text="▶ 다시 사용" if paused else "⏸ 일시정지")

    def _toggle_pause(self, key):
        i = self._sel(key)
        if i is None:
            messagebox.showinfo("안내", "일시정지할 메뉴를 목록에서 먼저 누르세요.",
                                parent=self.win)
            return
        name = self._name_at(key, i)
        if store.is_paused(key, name):
            store.set_paused(key, name, False)
        else:
            note = _ask_text(self.win, "일시정지",
                             f"‘{name}’ 을(를) 당분간 식단에서 뺍니다.\n"
                             f"사유·기간 (안 적어도 됩니다)")
            if note is None:      # 취소
                return
            store.set_paused(key, name, True, note)
        self._refresh(key, select=i)

    # ---- 추가/수정/삭제 ----
    def _add(self, key):
        if key == "mains":
            res = _MainForm(self.win).result
            if not res:
                return
            dup = next((n for n, it in enumerate(self._items(key))
                        if it.get("name") == res["name"]), None)
            if dup is not None:
                messagebox.showinfo("이미 있어요", f"‘{res['name']}’ 은(는) 이미 등록돼 있어요.",
                                    parent=self.win)
                self._refresh(key, select=dup)
                return
            self._items(key).append(res)
        else:
            name = _ask_text(self.win, f"{'반찬' if key == 'sides' else '국'} 추가", "메뉴 이름")
            if not name or not name.strip():
                return
            name = name.strip()
            dup = next((n for n, it in enumerate(self._items(key)) if it == name), None)
            if dup is not None:
                messagebox.showinfo("이미 있어요", f"‘{name}’ 은(는) 이미 등록돼 있어요.",
                                    parent=self.win)
                self._refresh(key, select=dup)
                return
            self._items(key).append(name)
        self._save_and_refresh(key, select=len(self._items(key)) - 1)

    def _edit(self, key):
        i = self._sel(key)
        if i is None:
            messagebox.showinfo("안내", "수정할 항목을 선택하세요.", parent=self.win)
            return
        old = self._name_at(key, i)
        if key == "mains":
            res = _MainForm(self.win, self._items(key)[i]).result
            if not res:
                return
            self._items(key)[i] = res
        else:
            name = _ask_text(self.win, "메뉴 수정", "메뉴 이름", old)
            if not name or not name.strip():
                return
            self._items(key)[i] = name.strip()
        store.rename_paused(key, old, self._name_at(key, i))
        self._save_and_refresh(key, select=i)

    def _delete(self, key):
        i = self._sel(key)
        if i is None:
            messagebox.showinfo("안내", "삭제할 항목을 선택하세요.", parent=self.win)
            return
        name = self._name_at(key, i)
        if messagebox.askyesno("삭제 확인", f"‘{name}’ 을(를) 삭제할까요?", parent=self.win):
            del self._items(key)[i]
            store.clear_paused(key, name)
            self._save_and_refresh(key)

    def _save_and_refresh(self, key, select=None):
        store.save_pool(self.pool)
        self._refresh(key, select=select)


class _MainForm:
    """메인 요리 추가/수정 폼. 끝나면 self.result(dict 또는 None)."""

    def __init__(self, parent, item=None):
        self.result = None
        base = dict(store.MAIN_FIELDS)
        if item:
            base.update(item)
        self.win = Toplevel(parent)
        self.win.title("메인 요리")
        self.win.configure(bg=PANEL_BG)
        _center(self.win, 360, 380, parent)
        self.win.transient(parent)
        _grab(self.win)

        self.v_name = StringVar(value=base["name"])
        self.v_flavor = StringVar(value=base["flavor"])
        self.v_scope = StringVar(value=SCOPE_KR.get(base["meal_scope"], "모두"))
        self.v_fish = BooleanVar(value=base["is_fish"])
        self.v_weekday = BooleanVar(value=base["weekday_only"])
        self.v_max = StringVar(value="" if base["monthly_max"] in (None, "") else str(base["monthly_max"]))

        self._row("이름", Entry(self.win, textvariable=self.v_name, font=_f(12)))
        self._row("맛", OptionMenu(self.win, self.v_flavor, "자극", "담백"))
        self._row("끼니", OptionMenu(self.win, self.v_scope, "모두", "중식", "석식"))
        self._row("월 최대(빈칸=무제한)", Entry(self.win, textvariable=self.v_max, font=_f(12)))
        Checkbutton(self.win, text="생선류", font=_f(12), bg=PANEL_BG, variable=self.v_fish,
                    selectcolor="white").pack(anchor="w", padx=24, pady=2)
        Checkbutton(self.win, text="평일만 편성", font=_f(12), bg=PANEL_BG,
                    variable=self.v_weekday, selectcolor="white").pack(anchor="w", padx=24, pady=2)

        bar = Frame(self.win, bg=PANEL_BG)
        bar.pack(side="bottom", fill="x", pady=12)
        Button(bar, text="저장", font=_f(12, True), width=8, bg=ACCENT, fg="white",
               command=self._ok).pack(side="right", padx=(0, 16))
        Button(bar, text="취소", font=_f(12), width=8,
               command=self.win.destroy).pack(side="right", padx=6)
        self.win.wait_window()

    def _row(self, label, widget):
        f = Frame(self.win, bg=PANEL_BG)
        f.pack(fill="x", padx=24, pady=(8, 0))
        Label(f, text=label, font=_f(12), bg=PANEL_BG, anchor="w").pack(anchor="w")
        widget.pack(fill="x")

    def _ok(self):
        name = self.v_name.get().strip()
        if not name:
            messagebox.showwarning("확인", "이름을 입력하세요.", parent=self.win)
            return
        mx = self.v_max.get().strip()
        if mx and not mx.isdigit():
            messagebox.showwarning("확인", "월 최대는 숫자만 입력하세요.", parent=self.win)
            return
        out = dict(store.MAIN_FIELDS)
        out.update({
            "name": name,
            "flavor": self.v_flavor.get(),
            "meal_scope": SCOPE_FROM.get(self.v_scope.get(), "both"),
            "is_fish": bool(self.v_fish.get()),
            "weekday_only": bool(self.v_weekday.get()),
            "monthly_max": int(mx) if mx else None,
        })
        self.result = out
        self.win.destroy()


# ============================================================ 조건 설정
class ConditionsWindow:
    def __init__(self, parent):
        self.conds = store.get_conditions()
        self.win = Toplevel(parent)
        self.win.title("조건 설정")
        self.win.configure(bg=PANEL_BG)
        _center(self.win, 560, 520, parent)
        self.win.transient(parent)
        _grab(self.win)

        Label(self.win, text="🧩 조건 설정", font=_f(18, True), bg=PANEL_BG, fg=ACCENT)\
            .pack(pady=(14, 4))
        Label(self.win, text="식단표를 만들 때 반드시 지킬 조건을 등록/수정/삭제하세요.\n"
                             "‘추가’를 누르면 문장으로 바로 쓸 수 있어요. "
                             "(✎ 표시는 자동 검사 없이 AI에게만 전달되는 조건)",
              font=_f(11), bg=PANEL_BG, fg="#666", justify="center").pack(pady=(0, 8))

        body = Frame(self.win, bg=PANEL_BG)
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.lb = Listbox(body, font=_f(12), activestyle="dotbox")
        self.lb.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(body, orient="vertical", command=self.lb.yview)
        sb.pack(side="left", fill="y")
        self.lb.configure(yscrollcommand=sb.set)
        self.lb.bind("<Double-1>", lambda e: self._edit())

        btns = Frame(body, bg=PANEL_BG)
        btns.pack(side="left", fill="y", padx=10)
        Button(btns, text="추가", font=_f(12, True), width=8, command=self._add).pack(pady=4)
        Button(btns, text="수정", font=_f(12, True), width=8, command=self._edit).pack(pady=4)
        Button(btns, text="삭제", font=_f(12, True), width=8, command=self._delete).pack(pady=4)
        self._refresh()

    def _refresh(self):
        self.lb.delete(0, END)
        for c in self.conds:
            # ✎ = 서술형(자동 검사 없이 AI에게 전달만 되는 조건)
            mark = "✎ " if c.get("type") == "text" else ""
            self.lb.insert(END, mark + cond_mod.to_text(c))

    def _sel(self):
        s = self.lb.curselection()
        return s[0] if s else None

    def _add(self):
        res = _ConditionForm(self.win).result
        if res:
            # 서술형 문장 하나가 여러 조건으로 풀릴 수 있다
            self.conds.extend(res if isinstance(res, list) else [res])
            self._save()

    def _edit(self):
        i = self._sel()
        if i is None:
            messagebox.showinfo("안내", "수정할 조건을 선택하세요.", parent=self.win)
            return
        res = _ConditionForm(self.win, self.conds[i]).result
        if res:
            self.conds[i:i + 1] = res if isinstance(res, list) else [res]
            self._save()

    def _delete(self):
        i = self._sel()
        if i is None:
            messagebox.showinfo("안내", "삭제할 조건을 선택하세요.", parent=self.win)
            return
        if messagebox.askyesno("삭제 확인", f"‘{cond_mod.to_text(self.conds[i])}’ 삭제할까요?",
                               parent=self.win):
            del self.conds[i]
            self._save()

    def _save(self):
        store.save_conditions(self.conds)
        self._refresh()


class _ConditionForm:
    """조건 추가/수정 폼. 끝나면 self.result(dict 또는 None)."""

    OP_KR = {"이하": "<=", "정확히": "==", "이상": ">="}
    OP_FROM = {v: k for k, v in OP_KR.items()}

    def __init__(self, parent, cond=None):
        self.result = None
        self.win = Toplevel(parent)
        self.win.title("조건")
        self.win.configure(bg=PANEL_BG)
        _center(self.win, 430, 380, parent)
        self.win.transient(parent)
        _grab(self.win)

        # 새 조건은 '서술형'을 기본으로 — 문장으로 바로 쓸 수 있게
        self.v_type = StringVar(value=cond_mod.TYPE_LABELS[cond["type"]] if cond
                                else cond_mod.TYPE_LABELS["text"])
        Label(self.win, text="조건 종류", font=_f(12), bg=PANEL_BG).pack(anchor="w", padx=24, pady=(14, 0))
        OptionMenu(self.win, self.v_type, *cond_mod.TYPE_LABELS.values(),
                   command=lambda *_: self._build_fields()).pack(fill="x", padx=24)

        self.fields = Frame(self.win, bg=PANEL_BG)
        self.fields.pack(fill="x", padx=24, pady=8)
        self._cond = cond
        self._build_fields()

        bar = Frame(self.win, bg=PANEL_BG)
        bar.pack(side="bottom", fill="x", pady=12)
        Button(bar, text="저장", font=_f(12, True), width=8, bg=ACCENT, fg="white",
               command=self._ok).pack(side="right", padx=(0, 16))
        Button(bar, text="취소", font=_f(12), width=8,
               command=self.win.destroy).pack(side="right", padx=6)
        self.win.wait_window()

    def _type_key(self):
        for k, v in cond_mod.TYPE_LABELS.items():
            if v == self.v_type.get():
                return k
        return "menu_count"

    def _build_fields(self):
        for w in self.fields.winfo_children():
            w.destroy()
        t = self._type_key()
        c = self._cond if (self._cond and self._cond.get("type") == t) else {}

        def labeled(text, widget):
            Label(self.fields, text=text, font=_f(12), bg=PANEL_BG).pack(anchor="w", pady=(6, 0))
            widget.pack(fill="x")

        if t == "text":
            Label(self.fields, text="조건을 문장으로 적어 주세요.", font=_f(12),
                  bg=PANEL_BG).pack(anchor="w", pady=(6, 0))
            Label(self.fields, text="예) 비빔밥은 일요일에만 넣어줘\n"
                                    "     수육은 점심에만 내고 월 2회 이하로",
                  font=_f(11), bg=PANEL_BG, fg="#666", justify="left")\
                .pack(anchor="w", pady=(0, 4))
            self.t_text = Text(self.fields, height=4, font=_f(12), wrap="word",
                               relief="solid", bd=1)
            self.t_text.pack(fill="x")
            self.t_text.insert("1.0", c.get("text", ""))
            self.t_text.focus_set()
        elif t == "menu_count":
            self.v_menu = StringVar(value=c.get("menu", ""))
            self.v_op = StringVar(value=self.OP_FROM.get(c.get("op", "<="), "이하"))
            self.v_count = StringVar(value=str(c.get("count", 2)))
            labeled("메뉴 이름", Entry(self.fields, textvariable=self.v_menu, font=_f(12)))
            labeled("비교", OptionMenu(self.fields, self.v_op, "이하", "정확히", "이상"))
            labeled("월 횟수", Entry(self.fields, textvariable=self.v_count, font=_f(12)))
        elif t == "menu_section":
            self.v_menu = StringVar(value=c.get("menu", ""))
            self.v_section = StringVar(value=c.get("section", "중식"))
            labeled("메뉴 이름", Entry(self.fields, textvariable=self.v_menu, font=_f(12)))
            labeled("편성 끼니", OptionMenu(self.fields, self.v_section, "중식", "석식"))
        elif t == "menu_weekday":
            self.v_menu = StringVar(value=c.get("menu", ""))
            labeled("메뉴 이름", Entry(self.fields, textvariable=self.v_menu, font=_f(12)))
            Label(self.fields, text="이 요일에만 편성 (여러 개 고를 수 있어요)",
                  font=_f(12), bg=PANEL_BG).pack(anchor="w", pady=(10, 0))
            picked = set(c.get("weekdays") or [])
            box = Frame(self.fields, bg=PANEL_BG)
            box.pack(fill="x")
            self.v_wdays = {}
            for n, wd in enumerate(cond_mod.WEEKDAYS):
                var = BooleanVar(value=(wd in picked))
                self.v_wdays[wd] = var
                Checkbutton(box, text=wd, font=_f(12), bg=PANEL_BG, variable=var,
                            selectcolor="white", activebackground=PANEL_BG)\
                    .grid(row=0, column=n, padx=2)
        elif t == "menu_gap":
            self.v_menu = StringVar(value=c.get("menu", ""))
            self.v_days = StringVar(value=str(c.get("days", 7)))
            labeled("메뉴 이름", Entry(self.fields, textvariable=self.v_menu, font=_f(12)))
            labeled("최소 간격(일)", Entry(self.fields, textvariable=self.v_days, font=_f(12)))
        elif t == "category_max":
            self.v_cat = StringVar(value=c.get("category", "생선류"))
            self.v_max = StringVar(value=str(c.get("max", 4)))
            labeled("카테고리", OptionMenu(self.fields, self.v_cat, *cond_mod.CATEGORIES))
            labeled("월 최대", Entry(self.fields, textvariable=self.v_max, font=_f(12)))

    def _int(self, var, name):
        s = var.get().strip()
        if not s.isdigit():
            messagebox.showwarning("확인", f"{name}은(는) 숫자만 입력하세요.", parent=self.win)
            return None
        return int(s)

    def _ok(self):
        t = self._type_key()
        out = {"type": t}

        if t == "text":
            raw = self.t_text.get("1.0", END).strip()
            if not raw:
                messagebox.showwarning("확인", "조건 문장을 입력하세요.", parent=self.win)
                return
            parsed = cond_mod.parse_text(raw)
            if parsed:
                lines = "\n".join(f"  • {cond_mod.to_text(p)}" for p in parsed)
                ans = messagebox.askyesnocancel(
                    "이렇게 이해했어요",
                    f"{lines}\n\n"
                    "[예]  이 조건으로 저장 — 지켜졌는지 프로그램이 자동으로 검사하고,\n"
                    "        어기면 다시 만듭니다. (권장)\n\n"
                    "[아니오]  쓴 문장 그대로 저장 — AI에게 전달만 되고 자동 검사는 없습니다.\n\n"
                    "[취소]  문장 다시 고치기",
                    parent=self.win)
                if ans is None:
                    return
                self.result = parsed if ans else {"type": "text", "text": raw}
            else:
                messagebox.showinfo(
                    "문장 그대로 저장할게요",
                    "이 문장은 자동 검사까지는 어려워서 AI에게 그대로 전달합니다.\n"
                    "꼭 지켜지게 하려면 위 ‘조건 종류’를 바꿔 항목으로 넣어 주세요.",
                    parent=self.win)
                self.result = {"type": "text", "text": raw}
            self.win.destroy()
            return

        if t in ("menu_count", "menu_section", "menu_gap"):
            menu = self.v_menu.get().strip()
            if not menu:
                messagebox.showwarning("확인", "메뉴 이름을 입력하세요.", parent=self.win)
                return
            out["menu"] = menu
        if t == "menu_count":
            n = self._int(self.v_count, "월 횟수")
            if n is None:
                return
            out["op"] = self.OP_KR[self.v_op.get()]
            out["count"] = n
        elif t == "menu_section":
            out["section"] = self.v_section.get()
        elif t == "menu_weekday":
            wds = [wd for wd in cond_mod.WEEKDAYS if self.v_wdays[wd].get()]
            if not wds:
                messagebox.showwarning("확인", "요일을 하나 이상 고르세요.", parent=self.win)
                return
            out["weekdays"] = wds
        elif t == "menu_gap":
            n = self._int(self.v_days, "최소 간격")
            if n is None:
                return
            out["days"] = n
        elif t == "category_max":
            n = self._int(self.v_max, "월 최대")
            if n is None:
                return
            out["category"] = self.v_cat.get()
            out["max"] = n
        self.result = out
        self.win.destroy()


# ============================================================ 예시 식단표(참고 데이터)
class ExamplesWindow:
    """기존 식단표를 예시로 등록 → 그 스타일대로 생성(few-shot)."""

    def __init__(self, parent):
        self.examples = store.get_examples()
        self.win = Toplevel(parent)
        self.win.title("예시 식단표")
        self.win.configure(bg=PANEL_BG)
        _center(self.win, 640, 560, parent)
        self.win.transient(parent)
        _grab(self.win)

        Label(self.win, text="📋 예시 식단표 (스타일 참고)", font=_f(18, True),
              bg=PANEL_BG, fg=ACCENT).pack(pady=(14, 4))
        Label(self.win,
              text="기존에 쓰던 식단표를 등록하면 그 스타일(메뉴 이름·조합)대로 생성합니다.\n"
                   "직접 붙여넣거나, 엑셀/CSV 파일에서 가져올 수 있어요.",
              font=_f(11), bg=PANEL_BG, fg="#666", justify="center").pack(pady=(0, 8))

        # 사용 토글
        self.v_use = BooleanVar(value=store.get_use_examples())
        Checkbutton(self.win, text="예시 스타일 따라 만들기 (끄면 예시 무시)",
                    font=_f(12), bg=PANEL_BG, variable=self.v_use,
                    command=self._toggle_use, selectcolor="white",
                    activebackground=PANEL_BG).pack(anchor="w", padx=16)

        body = Frame(self.win, bg=PANEL_BG)
        body.pack(fill="both", expand=True, padx=12, pady=(6, 12))
        self.lb = Listbox(body, font=_f(12), activestyle="dotbox")
        self.lb.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(body, orient="vertical", command=self.lb.yview)
        sb.pack(side="left", fill="y")
        self.lb.configure(yscrollcommand=sb.set)
        self.lb.bind("<Double-1>", lambda e: self._edit())

        btns = Frame(body, bg=PANEL_BG)
        btns.pack(side="left", fill="y", padx=10)
        Button(btns, text="붙여넣기\n추가", font=_f(11, True), width=8,
               command=self._add_paste).pack(pady=4)
        Button(btns, text="파일에서\n가져오기", font=_f(11, True), width=8,
               command=self._add_file).pack(pady=4)
        Button(btns, text="수정", font=_f(12, True), width=8, command=self._edit).pack(pady=4)
        Button(btns, text="삭제", font=_f(12, True), width=8, command=self._delete).pack(pady=4)
        self._refresh()

    def _toggle_use(self):
        store.set_use_examples(bool(self.v_use.get()))

    def _refresh(self):
        self.lb.delete(0, END)
        for ex in self.examples:
            title = ex.get("title", "예시")
            n = len(ex.get("body", ""))
            self.lb.insert(END, f"{title}  ({n:,}자)")

    def _sel(self):
        s = self.lb.curselection()
        return s[0] if s else None

    def _add_paste(self):
        res = _ExampleForm(self.win).result
        if res:
            self.examples.append(res)
            self._save()

    def _add_file(self):
        path = filedialog.askopenfilename(
            title="예시로 가져올 파일 선택",
            filetypes=[("엑셀/표 파일", "*.xlsx *.xlsm *.csv *.tsv *.txt"),
                       ("모든 파일", "*.*")],
            parent=self.win,
        )
        if not path:
            return
        try:
            body = importers.read_table_file(path)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("오류", f"파일을 읽지 못했어요.\n\n{e}", parent=self.win)
            return
        if not body.strip():
            messagebox.showwarning("확인", "파일에서 읽을 내용이 없어요.", parent=self.win)
            return
        title = os.path.splitext(os.path.basename(path))[0]
        # 가져온 내용을 확인/수정 후 저장
        res = _ExampleForm(self.win, {"title": title, "body": body}).result
        if res:
            self.examples.append(res)
            self._save()

    def _edit(self):
        i = self._sel()
        if i is None:
            messagebox.showinfo("안내", "수정할 예시를 선택하세요.", parent=self.win)
            return
        res = _ExampleForm(self.win, self.examples[i]).result
        if res:
            self.examples[i] = res
            self._save()

    def _delete(self):
        i = self._sel()
        if i is None:
            messagebox.showinfo("안내", "삭제할 예시를 선택하세요.", parent=self.win)
            return
        if messagebox.askyesno("삭제 확인",
                               f"‘{self.examples[i].get('title', '예시')}’ 삭제할까요?",
                               parent=self.win):
            del self.examples[i]
            self._save()

    def _save(self):
        store.save_examples(self.examples)
        self._refresh()


class _ExampleForm:
    """예시 추가/수정 폼(제목 + 여러 줄 본문). 끝나면 self.result(dict 또는 None)."""

    def __init__(self, parent, item=None):
        self.result = None
        self.win = Toplevel(parent)
        self.win.title("예시 식단표")
        self.win.configure(bg=PANEL_BG)
        _center(self.win, 560, 520, parent)
        self.win.transient(parent)
        _grab(self.win)

        Label(self.win, text="제목", font=_f(12), bg=PANEL_BG).pack(anchor="w", padx=20, pady=(16, 2))
        self.v_title = StringVar(value=(item or {}).get("title", ""))
        Entry(self.win, textvariable=self.v_title, font=_f(12)).pack(fill="x", padx=20)

        Label(self.win, text="식단표 내용 (붙여넣기)", font=_f(12), bg=PANEL_BG)\
            .pack(anchor="w", padx=20, pady=(12, 2))
        tf = Frame(self.win, bg=PANEL_BG)
        tf.pack(fill="both", expand=True, padx=20)
        self.txt = Text(tf, font=_f(11), wrap="word", undo=True)
        self.txt.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.txt.yview)
        sb.pack(side="left", fill="y")
        self.txt.configure(yscrollcommand=sb.set)
        if item and item.get("body"):
            self.txt.insert("1.0", item["body"])

        bar = Frame(self.win, bg=PANEL_BG)
        bar.pack(side="bottom", fill="x", pady=12)
        Button(bar, text="저장", font=_f(12, True), width=8, bg=ACCENT, fg="white",
               command=self._ok).pack(side="right", padx=(0, 20))
        Button(bar, text="취소", font=_f(12), width=8,
               command=self.win.destroy).pack(side="right", padx=6)
        self.win.wait_window()

    def _ok(self):
        title = self.v_title.get().strip() or "예시"
        body = self.txt.get("1.0", END).strip()
        if not body:
            messagebox.showwarning("확인", "식단표 내용을 입력하세요.", parent=self.win)
            return
        self.result = {"title": title, "body": body}
        self.win.destroy()


# ---- 공용: 간단 텍스트 입력 ----
def _ask_text(parent, title, label, initial=""):
    win = Toplevel(parent)
    win.title(title)
    win.configure(bg=PANEL_BG)
    _center(win, 320, 150, parent)
    win.transient(parent)
    _grab(win)
    Label(win, text=label, font=_f(12), bg=PANEL_BG).pack(anchor="w", padx=20, pady=(18, 4))
    var = StringVar(value=initial)
    ent = Entry(win, textvariable=var, font=_f(12))
    ent.pack(fill="x", padx=20)
    ent.focus_set()
    result = {"v": None}

    def ok():
        result["v"] = var.get()
        win.destroy()

    bar = Frame(win, bg=PANEL_BG)
    bar.pack(side="bottom", fill="x", pady=12)
    Button(bar, text="저장", font=_f(12, True), width=7, bg=ACCENT, fg="white",
           command=ok).pack(side="right", padx=(0, 16))
    Button(bar, text="취소", font=_f(12), width=7, command=win.destroy).pack(side="right", padx=6)
    ent.bind("<Return>", lambda e: ok())
    win.wait_window()
    return result["v"]
