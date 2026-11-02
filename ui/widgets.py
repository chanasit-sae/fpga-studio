# -*- coding: utf-8 -*-
"""
Custom Spotify-Style Dark UI Widgets:
- SpotifyPillButton (4x Anti-Aliased Capsule Button & Closeable Editor Tab)
- SpotifyPopupMenu (Frameless Dark In-Window Dropdown & Context Menu)
- SpotifyAutoScrollbar (Slim Auto-Hiding Scrollbar)
"""

import tkinter as tk
import tkinter.font as tkfont
from config.theme import (
    BG_TAB_BAR,
    BG_PILL_INACT,
    BG_PILL_ACT,
    BG_EDITOR,
    BG_POPUP,
    ACCENT_GREEN,
    TXT_BRIGHT,
    TXT_PRIMARY,
    TXT_MUTED,
    FONT_UI,
    FONT_CODE,
    FONT_ICON,
)
from ui.graphics import get_antialiased_pill_photo


def attach_tooltip(widget, text, delay=500):
    """Attach a themed hover tooltip to any widget.

    `text` may be a plain string or a zero-arg callable, so captions that
    depend on live state (counts, current mode) stay correct. Bindings use
    add="+" so existing <Enter>/<Leave> hover styling is preserved.
    """
    state = {"after": None, "win": None}

    def _hide(_event=None):
        if state["after"] is not None:
            try:
                widget.after_cancel(state["after"])
            except Exception:
                pass
            state["after"] = None
        win, state["win"] = state["win"], None
        if win is not None:
            try:
                win.destroy()
            except Exception:
                pass

    def _show():
        state["after"] = None
        if state["win"] is not None or not widget.winfo_exists():
            return
        try:
            msg = text() if callable(text) else text
        except Exception:
            return
        if not msg:
            return

        tip = tk.Toplevel(widget)
        tip.wm_overrideredirect(True)
        try:
            tip.attributes("-topmost", True)
        except Exception:
            pass
        frame = tk.Frame(tip, bg=BG_POPUP, highlightthickness=1, highlightbackground="#3A3A3A")
        frame.pack()
        tk.Label(
            frame, text=msg, bg=BG_POPUP, fg=TXT_PRIMARY,
            font=(FONT_UI, 8), padx=8, pady=4, justify="left"
        ).pack()

        tip.update_idletasks()
        x = widget.winfo_rootx() + widget.winfo_width() // 2 - tip.winfo_width() // 2
        y = widget.winfo_rooty() + widget.winfo_height() + 6
        # keep the tip fully on screen
        x = max(4, min(x, widget.winfo_screenwidth() - tip.winfo_width() - 4))
        if y + tip.winfo_height() > widget.winfo_screenheight():
            y = widget.winfo_rooty() - tip.winfo_height() - 6
        tip.wm_geometry(f"+{x}+{y}")
        state["win"] = tip

    def _enter(_event=None):
        _hide()
        state["after"] = widget.after(delay, _show)

    widget.bind("<Enter>", _enter, add="+")
    widget.bind("<Leave>", _hide, add="+")
    widget.bind("<ButtonPress>", _hide, add="+")
    widget.bind("<Destroy>", _hide, add="+")
    return _hide


class SpotifyPillButton(tk.Canvas):
    """4x Anti-Aliased Capsule Button supporting icons, status dots, and tab close ('✕') button."""

    def __init__(self, parent, text="", command=None, close_command=None,
                 bg_parent=None, fill_col=BG_PILL_INACT, fg_col=TXT_BRIGHT,
                 hover_fill="#303030", font_spec=None, pad_x=14, height=30,
                 icon_glyph=None, dot_color=None, icon_font_name=FONT_ICON):
        if bg_parent is None:
            try:
                bg_parent = parent.cget("bg")
            except Exception:
                bg_parent = BG_TAB_BAR
        super().__init__(parent, bg=bg_parent, bd=0, highlightthickness=0, relief="flat", cursor="hand2")
        self.text = text
        self.icon_glyph = icon_glyph
        self.dot_color = dot_color
        self.command = command
        self.close_command = close_command
        self.bg_parent = bg_parent
        self.fill_col = fill_col
        self.fg_col = fg_col
        self.hover_fill = hover_fill
        self.font_spec = font_spec or (FONT_UI, 9, "bold")
        self.icon_font_name = icon_font_name
        self.pad_x = pad_x
        self.pill_height = height
        self._hover = False
        self._hover_close = False
        self._close_x1 = 0
        self._photo_ref = None

        self._measure_and_draw()
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Motion>", self._on_motion)
        self.bind("<ButtonRelease-1>", self._on_click)

    def _measure_and_draw(self):
        f = tkfont.Font(font=self.font_spec)
        txt_w = f.measure(self.text)
        ic_w = 18 if self.icon_glyph else 0
        dot_w = 14 if self.dot_color else 0
        close_w = 22 if self.close_command else 0
        total_w = max(54, txt_w + ic_w + dot_w + close_w + self.pad_x * 2)
        total_h = self.pill_height
        self._close_x1 = total_w - self.pad_x - 16 if self.close_command else total_w + 100
        self.configure(width=total_w, height=total_h)
        self._redraw(total_w, total_h)

    def _redraw(self, w=None, h=None):
        self.delete("all")
        w = w or int(self["width"])
        h = h or int(self["height"])
        fill = self.hover_fill if (self._hover and self.fill_col != BG_PILL_ACT) else self.fill_col
        outline = "#5A5A5A" if (self._hover and self.fill_col != BG_PILL_ACT) else fill

        self._photo_ref = get_antialiased_pill_photo(w, h, self.bg_parent, fill, outline)
        self.create_image(0, 0, image=self._photo_ref, anchor="nw")

        cy = h // 2
        cur_x = self.pad_x
        if self.icon_glyph:
            self.create_text(cur_x + 6, cy, text=self.icon_glyph, fill=self.fg_col, font=(self.icon_font_name, 9))
            cur_x += 18

        if self.close_command or self.dot_color:
            self.create_text(cur_x, cy, text=self.text, fill=self.fg_col, font=self.font_spec, anchor="w")
            f = tkfont.Font(font=self.font_spec)
            cur_x += f.measure(self.text) + 6
            if self.dot_color:
                self.create_text(cur_x + 4, cy, text="●", fill=self.dot_color, font=(FONT_UI, 8, "bold"))
                cur_x += 14
            if self.close_command:
                cx = w - self.pad_x - 4
                if self._hover_close:
                    self.create_oval(
                        cx - 8, cy - 8, cx + 8, cy + 8,
                        fill="#484848" if self.fill_col != BG_PILL_ACT else "#D8D8D8",
                        outline=""
                    )
                self.create_text(cx, cy, text="\uE8BB", fill=self.fg_col, font=(self.icon_font_name, 7))
        else:
            self.create_text(w // 2, cy, text=self.text, fill=self.fg_col, font=self.font_spec)

    def set_style(self, text=None, fill_col=None, fg_col=None, dot_color="KEEP"):
        if text is not None:
            self.text = text
        if fill_col is not None:
            self.fill_col = fill_col
        if fg_col is not None:
            self.fg_col = fg_col
        if dot_color != "KEEP":
            self.dot_color = dot_color
        self._measure_and_draw()

    def _on_enter(self, event):
        self._hover = True
        self._redraw()

    def _on_leave(self, event):
        self._hover = False
        self._hover_close = False
        self._redraw()

    def _on_motion(self, event):
        if not self.close_command:
            return
        hc = event.x >= self._close_x1
        if hc != self._hover_close:
            self._hover_close = hc
            self._redraw()

    def _on_click(self, event):
        if self.close_command and event.x >= self._close_x1:
            self.close_command()
        elif self.command:
            self.command()


class SpotifyPopupMenu:
    """In-window frameless dark popup menu (zero white border, instant rendering)."""

    _active_frame = None
    _active_tag = None
    _active_submenu_frame = None

    def __init__(self, master_app, tag=None):
        self.app = master_app
        self.tag = tag
        self.items = []

    def add_command(self, label="", shortcut="", command=None, enabled=True, on_right_click=None):
        self.items.append(("command", label, shortcut, command, None, None, enabled, on_right_click))

    def add_cascade(self, label="", menu=None, shortcut="▸", enabled=True):
        self.items.append(("cascade", label, shortcut, None, menu, None, enabled, None))

    def add_checkbutton(self, label="", variable=None, command=None, shortcut="", enabled=True):
        self.items.append(("check", label, shortcut, command, variable, None, enabled, None))

    def add_radiobutton(self, label="", variable=None, value=None, command=None, enabled=True, on_right_click=None):
        self.items.append(("radio", label, "", command, variable, value, enabled, on_right_click))

    def add_separator(self):
        self.items.append(("sep", "", "", None, None, None, True))

    @classmethod
    def close_active(cls):
        if cls._active_submenu_frame and cls._active_submenu_frame.winfo_exists():
            try:
                cls._active_submenu_frame.destroy()
            except Exception:
                pass
        cls._active_submenu_frame = None
        if cls._active_frame and cls._active_frame.winfo_exists():
            try:
                cls._active_frame.destroy()
            except Exception:
                pass
        cls._active_frame = None
        cls._active_tag = None

    def show_at_widget(self, anchor_widget):
        if self.tag and SpotifyPopupMenu._active_tag == self.tag and SpotifyPopupMenu._active_frame:
            SpotifyPopupMenu.close_active()
            return
        x = anchor_widget.winfo_rootx() - self.app.winfo_rootx()
        y = (anchor_widget.winfo_rooty() - self.app.winfo_rooty()) + anchor_widget.winfo_height() + 2
        self._render_overlay(x, y)

    def show(self, x_root, y_root):
        x = x_root - self.app.winfo_rootx()
        y = y_root - self.app.winfo_rooty()
        self._render_overlay(x, y)

    def _render_overlay(self, x, y):
        SpotifyPopupMenu.close_active()
        SpotifyPopupMenu._active_tag = self.tag

        box = tk.Frame(
            self.app, bg=BG_POPUP, padx=4, pady=4,
            highlightthickness=1, highlightbackground="#3A3A3A"
        )
        SpotifyPopupMenu._active_frame = box

        for item in self.items:
            on_rc = None
            if len(item) == 8:
                kind, label, shortcut, cmd, var, val, enabled, on_rc = item
            elif len(item) == 7:
                kind, label, shortcut, cmd, var, val, enabled = item
            else:
                kind, label, shortcut, cmd, var, val = item
                enabled = True

            if kind == "sep":
                tk.Frame(box, bg="#343434", height=1).pack(fill=tk.X, padx=6, pady=4)
                continue

            cursor_style = "hand2" if enabled else "arrow"
            text_color = TXT_PRIMARY if enabled else "#555555"

            row = tk.Frame(
                box, bg=BG_POPUP, padx=10, pady=5, cursor=cursor_style,
                highlightthickness=1, highlightbackground=BG_POPUP
            )
            row.pack(fill=tk.X, pady=1)

            mark_txt = ""
            if kind == "check" and var is not None:
                mark_txt = "✓" if var.get() else ""
            elif kind == "radio" and var is not None:
                mark_txt = "●" if var.get() == val else ""

            lbl_mark = tk.Label(row, text=mark_txt, bg=BG_POPUP, fg=ACCENT_GREEN if enabled else "#555555",
                                font=(FONT_UI, 9, "bold"), width=2, anchor="w")
            lbl_mark.pack(side=tk.LEFT)

            lbl_main = tk.Label(row, text=label, bg=BG_POPUP, fg=text_color,
                                font=(FONT_UI, 9, "bold"), anchor="w")
            lbl_main.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 18))

            lbl_sc = None
            if shortcut:
                lbl_sc = tk.Label(row, text=shortcut, bg=BG_POPUP, fg=TXT_MUTED if enabled else "#444444",
                                  font=(FONT_CODE, 8), anchor="e")
                lbl_sc.pack(side=tk.RIGHT)

            if enabled:
                def _invoke(k=kind, c=cmd, v=var, vl=val, r=row, bx=box):
                    if k == "cascade":
                        self._show_submenu(r, bx, v)
                        return
                    SpotifyPopupMenu.close_active()
                    if k == "check" and v is not None:
                        v.set(not v.get())
                    elif k == "radio" and v is not None:
                        v.set(vl)
                    if c:
                        c()

                def _enter(e, r=row, lm=lbl_mark, l1=lbl_main, ls=lbl_sc, k=kind, v=var, bx=box):
                    r.configure(bg="#333333", highlightbackground="#4E4E4E")
                    lm.configure(bg="#333333")
                    l1.configure(bg="#333333", fg=TXT_BRIGHT)
                    if ls:
                        ls.configure(bg="#333333", fg=TXT_BRIGHT)
                    if k == "cascade":
                        self._show_submenu(r, bx, v)
                    else:
                        if SpotifyPopupMenu._active_submenu_frame and SpotifyPopupMenu._active_submenu_frame.winfo_exists():
                            try:
                                SpotifyPopupMenu._active_submenu_frame.destroy()
                            except Exception:
                                pass
                            SpotifyPopupMenu._active_submenu_frame = None

                def _leave(e, r=row, lm=lbl_mark, l1=lbl_main, ls=lbl_sc):
                    r.configure(bg=BG_POPUP, highlightbackground=BG_POPUP)
                    lm.configure(bg=BG_POPUP)
                    l1.configure(bg=BG_POPUP, fg=TXT_PRIMARY)
                    if ls:
                        ls.configure(bg=BG_POPUP, fg=TXT_MUTED)

                for w in (row, lbl_mark, lbl_main) + ((lbl_sc,) if lbl_sc else ()):
                    w.bind("<Enter>", _enter)
                    w.bind("<Leave>", _leave)
                    w.bind("<Button-1>", lambda e, fn=_invoke: fn())
                    w.bind("<ButtonRelease-1>", lambda e, fn=_invoke: fn())
                    if on_rc:
                        def _handle_rc(e, fn=on_rc):
                            fn(e)
                            return "break"
                        w.bind("<Button-3>", _handle_rc)

        box.update_idletasks()
        req_w = max(260, box.winfo_reqwidth())
        req_h = box.winfo_reqheight()
        max_x = max(10, self.app.winfo_width() - req_w - 10)
        max_y = max(10, self.app.winfo_height() - req_h - 10)
        x = max(6, min(x, max_x))
        y = max(6, min(y, max_y))

        box.place(x=x, y=y, width=req_w)
        box.tkraise()

    def _show_submenu(self, parent_row, parent_box, sub_menu):
        if SpotifyPopupMenu._active_submenu_frame and SpotifyPopupMenu._active_submenu_frame.winfo_exists():
            try:
                SpotifyPopupMenu._active_submenu_frame.destroy()
            except Exception:
                pass
            SpotifyPopupMenu._active_submenu_frame = None

        if not sub_menu or not getattr(sub_menu, "items", None):
            return

        sub_box = tk.Frame(
            self.app, bg=BG_POPUP, padx=4, pady=4,
            highlightthickness=1, highlightbackground="#3A3A3A"
        )
        SpotifyPopupMenu._active_submenu_frame = sub_box

        for item in sub_menu.items:
            on_rc = None
            if len(item) == 8:
                kind, label, shortcut, cmd, var, val, enabled, on_rc = item
            elif len(item) == 7:
                kind, label, shortcut, cmd, var, val, enabled = item
            else:
                kind, label, shortcut, cmd, var, val = item
                enabled = True

            if kind == "sep":
                tk.Frame(sub_box, bg="#343434", height=1).pack(fill=tk.X, padx=6, pady=4)
                continue

            cursor_style = "hand2" if enabled else "arrow"
            text_color = TXT_PRIMARY if enabled else "#555555"

            row = tk.Frame(
                sub_box, bg=BG_POPUP, padx=10, pady=5, cursor=cursor_style,
                highlightthickness=1, highlightbackground=BG_POPUP
            )
            row.pack(fill=tk.X, pady=1)

            mark_txt = ""
            if kind == "check" and var is not None:
                mark_txt = "✓" if var.get() else ""
            elif kind == "radio" and var is not None:
                mark_txt = "●" if var.get() == val else ""

            lbl_mark = tk.Label(row, text=mark_txt, bg=BG_POPUP, fg=ACCENT_GREEN if enabled else "#555555",
                                font=(FONT_UI, 9, "bold"), width=2, anchor="w")
            lbl_mark.pack(side=tk.LEFT)

            lbl_main = tk.Label(row, text=label, bg=BG_POPUP, fg=text_color,
                                font=(FONT_UI, 9, "bold"), anchor="w")
            lbl_main.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 18))

            lbl_sc = None
            if shortcut:
                lbl_sc = tk.Label(row, text=shortcut, bg=BG_POPUP, fg=TXT_MUTED if enabled else "#444444",
                                  font=(FONT_CODE, 8), anchor="e")
                lbl_sc.pack(side=tk.RIGHT)

            if enabled:
                def _sub_invoke(k=kind, c=cmd, v=var, vl=val):
                    SpotifyPopupMenu.close_active()
                    if k == "check" and v is not None:
                        v.set(not v.get())
                    elif k == "radio" and v is not None:
                        v.set(vl)
                    if c:
                        c()

                def _sub_enter(e, r=row, lm=lbl_mark, l1=lbl_main, ls=lbl_sc):
                    r.configure(bg="#333333", highlightbackground="#4E4E4E")
                    lm.configure(bg="#333333")
                    l1.configure(bg="#333333", fg=TXT_BRIGHT)
                    if ls:
                        ls.configure(bg="#333333", fg=TXT_BRIGHT)

                def _sub_leave(e, r=row, lm=lbl_mark, l1=lbl_main, ls=lbl_sc):
                    r.configure(bg=BG_POPUP, highlightbackground=BG_POPUP)
                    lm.configure(bg=BG_POPUP)
                    l1.configure(bg=BG_POPUP, fg=TXT_PRIMARY)
                    if ls:
                        ls.configure(bg=BG_POPUP, fg=TXT_MUTED)

                for w in (row, lbl_mark, lbl_main) + ((lbl_sc,) if lbl_sc else ()):
                    w.bind("<Enter>", _sub_enter)
                    w.bind("<Leave>", _sub_leave)
                    w.bind("<Button-1>", lambda e, fn=_sub_invoke: fn())
                    w.bind("<ButtonRelease-1>", lambda e, fn=_sub_invoke: fn())

        sub_box.update_idletasks()
        sub_w = max(240, sub_box.winfo_reqwidth())
        sub_h = sub_box.winfo_reqheight()

        parent_box.update_idletasks()
        p_x = parent_box.winfo_x()
        p_y = parent_box.winfo_y()
        p_w = parent_box.winfo_width()
        r_y = parent_row.winfo_y()

        pos_x = p_x + p_w - 4
        pos_y = p_y + r_y - 4

        if pos_x + sub_w > self.app.winfo_width() - 8:
            pos_x = max(6, p_x - sub_w + 4)
        if pos_y + sub_h > self.app.winfo_height() - 8:
            pos_y = max(6, self.app.winfo_height() - sub_h - 10)

        sub_box.place(x=pos_x, y=pos_y, width=sub_w)
        sub_box.tkraise()


class SpotifyAutoScrollbar(tk.Canvas):
    """Slim auto-hiding scrollbar that only appears when content overflows."""

    def __init__(self, parent, command=None, bg_track=BG_EDITOR, thumb_color="#5A5A5A", hover_color="#8A8A8A", width=6):
        super().__init__(parent, width=width, bg=bg_track, bd=0, highlightthickness=0, relief="flat")
        self.command = command
        self.bg_track = bg_track
        self.thumb_color = thumb_color
        self.hover_color = hover_color
        self.bar_width = width
        self._first = 0.0
        self._last = 1.0
        self._hover = False
        self._drag_start_y = None
        self._drag_start_first = 0.0
        self._is_visible = False

        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)

    def set(self, first, last):
        f, l = float(first), float(last)
        self._first, self._last = f, l
        if f <= 0.001 and l >= 0.999:
            if self._is_visible:
                self.pack_forget()
                self._is_visible = False
        else:
            if not self._is_visible:
                self.pack(side=tk.RIGHT, fill=tk.Y, padx=(2, 2), pady=4)
                self._is_visible = True
            self._redraw()

    def _redraw(self):
        self.delete("all")
        if not self._is_visible:
            return
        h = max(1, self.winfo_height())
        w = self.bar_width
        y1 = int(self._first * h)
        y2 = max(y1 + 24, int(self._last * h))
        col = self.hover_color if (self._hover or self._drag_start_y is not None) else self.thumb_color
        self.create_rectangle(0, y1, w, y2, fill=col, outline="")

    def _on_enter(self, event):
        self._hover = True
        self._redraw()

    def _on_leave(self, event):
        self._hover = False
        self._redraw()

    def _on_press(self, event):
        h = max(1, self.winfo_height())
        y1 = self._first * h
        y2 = max(y1 + 24, self._last * h)
        if y1 <= event.y <= y2:
            self._drag_start_y = event.y
            self._drag_start_first = self._first
        else:
            span = self._last - self._first
            target = max(0.0, min(1.0 - span, (event.y / h) - span / 2))
            if self.command:
                self.command("moveto", target)
            self._drag_start_y = event.y
            self._drag_start_first = target

    def _on_drag(self, event):
        if self._drag_start_y is None:
            return
        h = max(1, self.winfo_height())
        dy = (event.y - self._drag_start_y) / h
        span = self._last - self._first
        target = max(0.0, min(1.0 - span, self._drag_start_first + dy))
        if self.command:
            self.command("moveto", target)

    def _on_release(self, event):
        self._drag_start_y = None
        self._redraw()
