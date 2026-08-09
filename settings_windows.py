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
    # (컬럼id, 헤더, 너비, 정렬)
    COLS = {
        "mains": [("name", "이름", 150, "w"), ("flavor", "맛", 60, "center"),
                  ("scope", "끼니", 60, "center"), ("fish", "생선", 55, "center"),
                  ("weekday", "평일만", 65, "center"), ("max", "월최대", 65, "center")],
        "sides": [("name", "반찬 이름", 380, "w")],
        "soups": [("name", "국 이름", 380, "w")],
    }

    def __init__(self, parent):
        self.pool = store.get_pool()
        self.win = Toplevel(parent)
        self.win.title("메뉴 설정")
        self.win.configure(bg=PANEL_BG)
        _center(self.win, 720, 560, parent)
        self.win.transient(parent)
        _grab(self.win)

        Label(self.win, text="🍳 메뉴 설정", font=_f(18, True), bg=PANEL_BG, fg=ACCENT)\
            .pack(pady=(14, 4))
        Label(self.win, text="메인·반찬·국 메뉴를 등록/수정/삭제할 수 있어요. (제목 줄로 항목 구분)",
              font=_f(11), bg=PANEL_BG, fg="#666").pack(pady=(0, 8))

        style = ttk.Style(self.win)
        style.configure("Menu.Treeview", font=_f(12), rowheight=30,
                        background="white", fieldbackground="white")
        style.configure("Menu.Treeview.Heading", font=_f(12, True))

        nb = ttk.Notebook(self.win)
        nb.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.tabs = {}
        for key, title in (("mains", "메인 요리"), ("sides", "반찬"), ("soups", "국")):
            self.tabs[key] = self._build_tab(nb, key, title)

    def _build_tab(self, nb, key, title):
        tab = Frame(nb, bg="white")
        nb.add(tab, text=f"  {title}  ")
        cols = self.COLS[key]
        tv = ttk.Treeview(tab, columns=[c[0] for c in cols], show="headings",
                          selectmode="browse", style="Menu.Treeview")
        for cid, head, width, anchor in cols:
            tv.heading(cid, text=head)
            tv.column(cid, width=width, anchor=anchor, stretch=(cid == "name"))
        tv.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        sb = ttk.Scrollbar(tab, orient="vertical", command=tv.yview)
        sb.pack(side="left", fill="y", pady=10)
        tv.configure(yscrollcommand=sb.set)

        btns = Frame(tab, bg="white")
        btns.pack(side="left", fill="y", padx=10, pady=10)
        Button(btns, text="추가", font=_f(12, True), width=8,
               command=lambda: self._add(key)).pack(pady=4)
        Button(btns, text="수정", font=_f(12, True), width=8,
               command=lambda: self._edit(key)).pack(pady=4)
        Button(btns, text="삭제", font=_f(12, True), width=8,
               command=lambda: self._delete(key)).pack(pady=4)
        tv.bind("<Double-1>", lambda e: self._edit(key))
        self._refresh(key, tv)
        return tv

    def _items(self, key):
        return self.pool[key]

    def _row_values(self, key, item):
        if key != "mains":
            return (item,)
        return (item.get("name", ""), item.get("flavor", ""),
                SCOPE_KR.get(item.get("meal_scope", "both"), "모두"),
                "○" if item.get("is_fish") else "",
                "○" if item.get("weekday_only") else "",
                item.get("monthly_max") or "")

    def _refresh(self, key, tv=None):
        tv = tv or self.tabs[key]
        tv.delete(*tv.get_children())
        for i, it in enumerate(self._items(key)):
            tv.insert("", "end", iid=str(i), values=self._row_values(key, it))

    def _sel(self, key):
        s = self.tabs[key].selection()
        return int(s[0]) if s else None

    def _add(self, key):
        if key == "mains":
            res = _MainForm(self.win).result
            if res:
                self._items(key).append(res)
        else:
            name = _ask_text(self.win, f"{'반찬' if key == 'sides' else '국'} 추가", "메뉴 이름")
            if name:
                self._items(key).append(name.strip())
        self._save_and_refresh(key)

    def _edit(self, key):
        i = self._sel(key)
        if i is None:
            messagebox.showinfo("안내", "수정할 항목을 선택하세요.", parent=self.win)
            return
        if key == "mains":
            res = _MainForm(self.win, self._items(key)[i]).result
            if res:
                self._items(key)[i] = res
        else:
            cur = self._items(key)[i]
            name = _ask_text(self.win, "메뉴 수정", "메뉴 이름", cur)
            if name:
                self._items(key)[i] = name.strip()
        self._save_and_refresh(key)

    def _delete(self, key):
        i = self._sel(key)
        if i is None:
            messagebox.showinfo("안내", "삭제할 항목을 선택하세요.", parent=self.win)
            return
        item = self._items(key)[i]
        name = item.get("name", "") if key == "mains" else item
        if messagebox.askyesno("삭제 확인", f"‘{name}’ 을(를) 삭제할까요?", parent=self.win):
            del self._items(key)[i]
            self._save_and_refresh(key)

    def _save_and_refresh(self, key):
        store.save_pool(self.pool)
        self._refresh(key)


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
        Label(self.win, text="식단표를 만들 때 반드시 지킬 조건을 등록/수정/삭제하세요.",
              font=_f(11), bg=PANEL_BG, fg="#666").pack(pady=(0, 8))

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
            self.lb.insert(END, cond_mod.to_text(c))

    def _sel(self):
        s = self.lb.curselection()
        return s[0] if s else None

    def _add(self):
        res = _ConditionForm(self.win).result
        if res:
            self.conds.append(res)
            self._save()

    def _edit(self):
        i = self._sel()
        if i is None:
            messagebox.showinfo("안내", "수정할 조건을 선택하세요.", parent=self.win)
            return
        res = _ConditionForm(self.win, self.conds[i]).result
        if res:
            self.conds[i] = res
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
        _center(self.win, 380, 320, parent)
        self.win.transient(parent)
        _grab(self.win)

        self.v_type = StringVar(value=cond_mod.TYPE_LABELS[cond["type"]] if cond
                                else cond_mod.TYPE_LABELS["menu_count"])
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

        if t == "menu_count":
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
