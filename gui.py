# -*- coding: utf-8 -*-
"""
한식 뷔페 식단표 생성기 — 데스크톱 GUI (어르신 친화)
=====================================================
- 큰 글씨 / 큰 버튼 / 단순한 흐름
- 연/월 선택 → [식단표 만들기] → 화면에서 수정 → 저장/복사/인쇄
- API 키는 [설정]에서 1회 입력하면 PC에 저장되어 자동 사용

실행:
    python gui.py
빌드(.exe):
    GitHub Actions(.github/workflows/build-windows.yml) 또는 build_windows.bat
"""

from __future__ import annotations

import threading
from datetime import date
from tkinter import (
    Tk, Toplevel, StringVar, BooleanVar, END, DISABLED, NORMAL,
    Label, Button, Entry, Frame, Checkbutton, OptionMenu, messagebox, filedialog,
)
from tkinter import font as tkfont
from tkinter.scrolledtext import ScrolledText

import app_config
import exporters
from menu_planner import generate_validated_menu

# 어르신 가독성을 위한 글씨 크기
FONT_FAMILY = "맑은 고딕"   # Windows 기본 한글 폰트(없으면 시스템 기본으로 대체됨)
SZ_TITLE = 26
SZ_LABEL = 16
SZ_BUTTON = 16
SZ_RESULT = 15

BG = "#FAFAFA"
ACCENT = "#2E7D32"   # 초록(식단/건강 느낌)


class MenuPlannerApp:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("한식 뷔페 식단표 만들기")
        self.root.configure(bg=BG)
        self.root.geometry("900x760")
        self.root.minsize(820, 680)

        self._busy = False
        self._build_fonts()
        self._build_ui()
        self._check_key_on_start()

    # --- 폰트 ---
    def _build_fonts(self):
        self.f_title = tkfont.Font(family=FONT_FAMILY, size=SZ_TITLE, weight="bold")
        self.f_label = tkfont.Font(family=FONT_FAMILY, size=SZ_LABEL)
        self.f_button = tkfont.Font(family=FONT_FAMILY, size=SZ_BUTTON, weight="bold")
        self.f_result = tkfont.Font(family=FONT_FAMILY, size=SZ_RESULT)

    # --- 화면 구성 ---
    def _build_ui(self):
        # 제목 + 설정 버튼
        top = Frame(self.root, bg=BG)
        top.pack(fill="x", padx=20, pady=(18, 8))
        Label(top, text="🍚 식단표 만들기", font=self.f_title, bg=BG, fg=ACCENT).pack(side="left")
        Button(top, text="⚙ 설정", font=self.f_label, command=self.open_settings,
               bg="#ECEFF1", relief="groove", padx=12, pady=4).pack(side="right")

        # 연/월 선택 + 만들기 버튼
        ctrl = Frame(self.root, bg=BG)
        ctrl.pack(fill="x", padx=20, pady=8)

        today = date.today()
        self.var_year = StringVar(value=str(today.year))
        self.var_month = StringVar(value=str(today.month))

        Label(ctrl, text="연도", font=self.f_label, bg=BG).pack(side="left")
        years = [str(y) for y in range(today.year, today.year + 3)]
        OptionMenu(ctrl, self.var_year, *years).pack(side="left", padx=(6, 18))

        Label(ctrl, text="월", font=self.f_label, bg=BG).pack(side="left")
        months = [str(m) for m in range(1, 13)]
        OptionMenu(ctrl, self.var_month, *months).pack(side="left", padx=(6, 18))

        self.btn_make = Button(
            ctrl, text="식단표 만들기", font=self.f_button, bg=ACCENT, fg="white",
            activebackground="#1B5E20", relief="raised", padx=24, pady=10,
            command=self.on_make,
        )
        self.btn_make.pack(side="left", padx=10)

        # 진행 상태
        self.var_status = StringVar(value="‘식단표 만들기’ 버튼을 눌러 주세요.")
        Label(self.root, textvariable=self.var_status, font=self.f_label,
              bg=BG, fg="#555").pack(fill="x", padx=22, pady=(2, 6), anchor="w")

        # 결과(수정 가능)
        self.txt = ScrolledText(self.root, font=self.f_result, wrap="word",
                                undo=True, padx=10, pady=10)
        self.txt.pack(fill="both", expand=True, padx=20, pady=6)

        # 하단 버튼: 저장 / 복사 / 인쇄
        bottom = Frame(self.root, bg=BG)
        bottom.pack(fill="x", padx=20, pady=(6, 18))
        self._mkbtn(bottom, "💾 파일로 저장", self.on_save)
        self._mkbtn(bottom, "📋 복사하기", self.on_copy)
        self._mkbtn(bottom, "🖨 인쇄하기", self.on_print)

    def _mkbtn(self, parent, text, cmd):
        Button(parent, text=text, font=self.f_button, command=cmd,
               bg="#FFFFFF", relief="raised", padx=18, pady=10,
               highlightbackground=ACCENT).pack(side="left", expand=True, fill="x", padx=6)

    # --- API 키 확인 ---
    def _check_key_on_start(self):
        if not app_config.get_api_key():
            messagebox.showinfo(
                "처음 설정이 필요해요",
                "식단표를 만들려면 먼저 ‘API 키’를 한 번 등록해야 합니다.\n"
                "[설정] 화면에서 키를 입력해 주세요. (한 번만 하면 됩니다)",
            )
            self.open_settings()

    # --- 설정 창 ---
    def open_settings(self):
        win = Toplevel(self.root)
        win.title("설정 — API 키")
        win.configure(bg=BG)
        win.geometry("640x300")
        win.transient(self.root)
        win.grab_set()

        Label(win, text="Gemini API 키", font=self.f_title, bg=BG, fg=ACCENT).pack(pady=(20, 6))
        Label(win, text="Google AI Studio에서 발급받은 키를 붙여넣어 주세요.",
              font=self.f_label, bg=BG, fg="#555").pack()

        var_key = StringVar(value=app_config.get_api_key())
        var_show = BooleanVar(value=False)

        ent = Entry(win, textvariable=var_key, font=self.f_label, width=46, show="*")
        ent.pack(pady=14, ipady=6)

        def toggle_show():
            ent.config(show="" if var_show.get() else "*")
        Checkbutton(win, text="키 보이기", font=self.f_label, bg=BG,
                    variable=var_show, command=toggle_show).pack()

        def save_key():
            key = var_key.get().strip()
            if not key:
                messagebox.showwarning("확인", "키를 입력해 주세요.", parent=win)
                return
            app_config.set_api_key(key)
            messagebox.showinfo("저장 완료", "API 키를 저장했어요. 이제 식단표를 만들 수 있습니다.", parent=win)
            win.destroy()

        Button(win, text="저장", font=self.f_button, bg=ACCENT, fg="white",
               padx=30, pady=8, command=save_key).pack(pady=18)

    # --- 식단표 만들기(백그라운드 실행) ---
    def on_make(self):
        if self._busy:
            return
        if not app_config.get_api_key():
            self.open_settings()
            return
        year = int(self.var_year.get())
        month = int(self.var_month.get())

        self._set_busy(True)
        self.var_status.set("식단표를 만들고 있어요... 잠시만 기다려 주세요 (수십 초 걸릴 수 있어요)")

        def worker():
            try:
                text, errors = generate_validated_menu(
                    year, month,
                    model="gemini-2.5-flash",
                    api_key=app_config.get_api_key(),
                    progress=lambda msg: self.root.after(0, self.var_status.set, msg),
                )
                self.root.after(0, self._on_done, text, errors)
            except Exception as e:  # noqa: BLE001  (사용자에게 친절한 오류 표시)
                self.root.after(0, self._on_error, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_done(self, text: str, errors: list[str]):
        self.txt.delete("1.0", END)
        self.txt.insert("1.0", text)
        self._set_busy(False)
        if errors:
            self.var_status.set(f"완성했어요. 다만 규칙 {len(errors)}건은 자동으로 못 맞췄어요(직접 수정 가능).")
            messagebox.showwarning(
                "일부 규칙 안내",
                "대부분 규칙은 맞췄지만 아래 항목은 직접 확인해 주세요:\n\n" + "\n".join(errors[:8]),
            )
        else:
            self.var_status.set("완성했어요! 모든 규칙을 통과했습니다. 필요하면 화면에서 바로 수정하세요.")

    def _on_error(self, msg: str):
        self._set_busy(False)
        self.var_status.set("문제가 생겼어요. 인터넷 연결과 API 키를 확인해 주세요.")
        messagebox.showerror("오류", f"식단표를 만들지 못했어요.\n\n{msg}")

    def _set_busy(self, busy: bool):
        self._busy = busy
        self.btn_make.config(state=DISABLED if busy else NORMAL,
                             text="만드는 중..." if busy else "식단표 만들기")

    # --- 저장 / 복사 / 인쇄 ---
    def _current_text(self) -> str:
        return self.txt.get("1.0", END).strip()

    def _has_content(self) -> bool:
        if not self._current_text():
            messagebox.showinfo("안내", "먼저 식단표를 만들어 주세요.")
            return False
        return True

    def on_save(self):
        if not self._has_content():
            return
        y, m = self.var_year.get(), self.var_month.get()
        path = filedialog.asksaveasfilename(
            title="식단표 저장",
            defaultextension=".xlsx",
            initialfile=f"식단표_{y}년{m}월",
            filetypes=[("엑셀 파일", "*.xlsx"), ("텍스트 파일", "*.txt")],
        )
        if not path:
            return
        try:
            if path.lower().endswith(".txt"):
                exporters.save_txt(self._current_text(), path)
            else:
                exporters.save_xlsx(self._current_text(), path, title=f"{y}년 {m}월 식단표")
            messagebox.showinfo("저장 완료", f"저장했어요:\n{path}")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("오류", f"저장하지 못했어요.\n\n{e}")

    def on_copy(self):
        if not self._has_content():
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self._current_text())
        self.var_status.set("복사했어요! 카카오톡·문자 등에 붙여넣기(Ctrl+V) 하세요.")

    def on_print(self):
        if not self._has_content():
            return
        y, m = self.var_year.get(), self.var_month.get()
        try:
            path = exporters.print_text(self._current_text(), title=f"{y}년 {m}월 식단표")
            import sys
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
