# -*- coding: utf-8 -*-
"""
Main Application Workbench Window: VSCodeFPGAStudio
Combines FramelessWindowMixin, SidebarPanelsMixin, and BoardPanelsMixin with
the Multi-Tab Code Editor, Top Search Capsule, Menus, and Real-Time 32-Bit Compiler.
"""

import os
import sys
import re
import json
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk
from config.theme import (
    BG_BLACK,
    BG_ACTIVITY,
    BG_SIDEBAR,
    BG_EDITOR,
    BG_TAB_BAR,
    BG_ELEVATED,
    BG_PILL_INACT,
    BG_PILL_ACT,
    BG_PANEL,
    BG_HOVER,
    BG_SELECTION,
    BORDER_COLOR,
    BORDER_HOVER,
    ACCENT_GREEN,
    ACCENT_YELLOW,
    ACCENT_RED,
    TXT_BRIGHT,
    TXT_PRIMARY,
    TXT_MUTED,
    TXT_DIM,
    TXT_ON_WHITE,
    SYN_KEYWORD,
    SYN_TYPE,
    SYN_MACRO,
    SYN_FUNC,
    SYN_MMIO,
    SYN_STRING,
    SYN_NUMBER,
    SYN_COMMENT,
    FONT_UI,
    FONT_CODE,
    FONT_ICON,
)
from config.catalog import ROOT_DIR, WORKSPACE_ROOT, DEFAULT_PROJECT_DIR, APP_ICON_PNG, APP_ICON_ICO
from core import (
    RISCV_BIN_DIR,
    MIPS_BIN_DIR,
    CPUSimulatorEngine,
    check_code_syntax,
    compile_c_to_asm,
    compile_with_real_riscv_gcc,
    compile_with_real_mips_gcc,
    assemble_riscv,
    assemble_mips,
    transpile_python_to_c,
    transpile_rust_to_c,
    translate_rv_ins_to_mips,
    generate_vhdl_rom,
    generate_verilog_rom,
    generate_coe_content,
)
from ui.graphics import (
    truncate_to_pixel_width,
    get_antialiased_pill_photo,
    add_card_rounded_corners,
    add_hover_border,
)
from ui.widgets import SpotifyPillButton, SpotifyPopupMenu, SpotifyAutoScrollbar, attach_tooltip
from ui.window_manager import FramelessWindowMixin
from ui.sidebar_panels import SidebarPanelsMixin
from ui.board_panels import BoardPanelsMixin


class VSCodeFPGAStudio(tk.Tk, FramelessWindowMixin, SidebarPanelsMixin, BoardPanelsMixin):
    """Main FPGA Studio IDE Window (Spotify Dark Edition)."""

    def __init__(self):
        super().__init__()
        self.title("FPGA Studio")
        self.geometry("1540x920+60+40")
        self.minsize(1100, 650)
        self.configure(bg=BG_BLACK)
        self.root = self

        # Set Application & Taskbar Icons
        if os.path.exists(APP_ICON_ICO):
            try:
                self.iconbitmap(default=APP_ICON_ICO)
            except Exception:
                pass
        if os.path.exists(APP_ICON_PNG):
            try:
                from PIL import Image, ImageTk
                _ico = Image.open(APP_ICON_PNG).resize((64, 64), Image.Resampling.LANCZOS)
                self._app_icon_photo = ImageTk.PhotoImage(_ico)
                self.iconphoto(True, self._app_icon_photo)
            except Exception:
                pass

        avail_fonts = set(tkfont.families())
        if "Segoe Fluent Icons" not in avail_fonts and "Segoe MDL2 Assets" in avail_fonts:
            self.icon_font_name = "Segoe MDL2 Assets"
        else:
            self.icon_font_name = FONT_ICON

        self._is_maximized = False
        self._normal_geom = "1540x920+60+40"
        self._drag_offset_x = 0
        self._drag_offset_y = 0

        self._init_workspace_on_disk()
        self.workspace_root = WORKSPACE_ROOT
        self.project_dir = DEFAULT_PROJECT_DIR
        self.expanded_folders = {os.path.abspath(DEFAULT_PROJECT_DIR)}
        self.installed_extensions = self._load_extensions_state()

        # Multi-Tab Editor State (Toggleable in Edit menu)
        self.multi_tab_var = tk.BooleanVar(value=True)
        self.open_tabs = []
        self.tab_widgets = {}

        self.current_file_path = ""
        self.current_file = ""
        self.current_target_mode = "fpga_board"
        self.cpu_target_var = tk.StringVar(value="fpga_board")
        self.arch_var = tk.StringVar(value="openmips (Nexys A7)")
        self.compiler_mode_var = tk.StringVar(value="mips_gcc")
        self.sim_speed_var = tk.StringVar(value="5Hz")
        self.active_compiler_name = "Real GCC Toolchain (MIPS32 / OpenMIPS)"
        self.settings_file = os.path.join(self.project_dir, "fpga_project_settings.json")
        self.global_settings_file = os.path.join(os.path.expanduser("~"), ".fpga_studio_settings.json")
        self.custom_cpus = []
        self.custom_compilers = []
        self._load_project_settings()

        self.com_port_var = tk.StringVar(value="AUTO")
        self.realtime_var = tk.BooleanVar(value=True)
        self.right_view_mode = "opcode"

        # Panel Visibility State (Right Machine Code panel is closed at startup)
        self.left_sidebar_mode = "explorer"
        self.show_machine_panel_var = tk.BooleanVar(value=False)
        self.show_simulator_var = tk.BooleanVar(value=False)
        self.show_overview_var = tk.BooleanVar(value=False)

        self._inline_entry_row = None
        self.file_errors = {}
        self.last_error_line = None
        self.last_error_msg = ""
        self._hover_popup = None
        self._ext_toast_frame = None

        self.compiled_ins = []
        self.last_vhdl = ""
        self.last_verilog = ""
        self.last_coe = ""
        self._compile_after_id = None
        self._save_after_id = None
        self._highlight_after_id = None
        self._compile_seq = 0

        # Cycle-Accurate CPU & Board Simulator Engine
        self.sim_engine = CPUSimulatorEngine()
        self.sim_running = False
        self.sim_after_id = None

        self.protocol("WM_DELETE_WINDOW", self._on_app_close)

        self._setup_ttk_styles()
        self._build_ui()
        self._enable_frameless_rounded_resizable_window()

        self.refresh_project_explorer()
        first_files = self._list_files_in_dir(self.project_dir)
        preferred_first = ["1_switch_to_led.c", "main.c", "test.c"]
        initial_file = None
        for pf in preferred_first:
            if pf in first_files:
                initial_file = pf
                break
        if not initial_file and first_files:
            initial_file = first_files[0]
        if initial_file:
            self.load_file_path(os.path.join(self.project_dir, initial_file))
        self._ensure_runnable_software_loaded()

        # Global Keyboard Shortcuts
        self.bind_all("<Control-s>", lambda e: self.save_current_file())
        self.bind_all("<Control-Shift-B>", lambda e: self.compile_now())
        self.bind_all("<Control-Shift-b>", lambda e: self.compile_now())
        self.bind_all("<Control-n>", lambda e: self.start_inline_new_file())
        self.bind_all("<Control-w>", lambda e: self.close_tab(self.current_file_path))
        self.bind_all("<Control-b>", lambda e: self.switch_left_sidebar("explorer", toggle=True))
        self.bind_all("<Control-Shift-F>", lambda e: self.switch_left_sidebar("search", toggle=True))
        self.bind_all("<Control-j>", lambda e: self.toggle_simulator())
        self.bind_all("<Control-k>", lambda e: self.toggle_overview())
        self.bind_all("<Control-i>", lambda e: self.import_rom_file_dialog())
        self.bind_all("<Control-I>", lambda e: self.import_rom_file_dialog())
        self.bind_all("<Control-Shift-P>", lambda e: self.open_rtl_verify_dialog())
        self.bind_all("<Control-Shift-p>", lambda e: self.open_rtl_verify_dialog())
        self.bind_all("<F7>", lambda e: self.open_fpga_programmer_dialog())
        self.bind_all("<F11>", lambda e: self.step_hardware_board() if hasattr(self, "step_hardware_board") else None)
        # Simulator transport controls (mirrors the Run menu and the top toolbar)
        self.bind_all("<F5>", lambda e: self.run_and_show_sim())
        self.bind_all("<F10>", lambda e: self.step_and_show_sim())
        self.bind_all("<Control-Shift-R>", lambda e: self.reset_sim())
        self.bind_all("<Control-Shift-r>", lambda e: self.reset_sim())
        self.bind_all("<Escape>", lambda e: SpotifyPopupMenu.close_active(), add="+")
        self.bind_all("<ButtonPress-1>", self._global_click_outside_menu, add="+")
        self._refresh_target_pills()

    def _global_click_outside_menu(self, event):
        pop = SpotifyPopupMenu._active_frame
        if not pop or not pop.winfo_exists():
            return
        w = event.widget
        if getattr(w, "_is_top_menubutton", False):
            return
        cur = w
        while cur is not None:
            if cur == pop:
                return
            cur = getattr(cur, "master", None)
        SpotifyPopupMenu.close_active()

    # ==========================================================================
    # TTK STYLING (BORDERLESS TREEVIEW)
    # ==========================================================================
    def _setup_ttk_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        style.configure(
            "Treeview",
            background=BG_EDITOR,
            foreground=TXT_PRIMARY,
            fieldbackground=BG_EDITOR,
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
            rowheight=32,
            font=(FONT_CODE, 9)
        )
        style.configure(
            "Treeview.Heading",
            background="#181818",
            foreground=TXT_MUTED,
            borderwidth=0,
            relief="flat",
            padding=(10, 8),
            font=(FONT_UI, 9, "bold")
        )
        style.map(
            "Treeview",
            background=[("selected", "#282828")],
            foreground=[("selected", ACCENT_GREEN)]
        )
        style.map(
            "Treeview.Heading",
            background=[("active", BG_HOVER)],
            foreground=[("active", TXT_BRIGHT)]
        )

    # ==========================================================================
    # BUILD SPOTIFY DARK WORKBENCH
    # ==========================================================================
    def _build_ui(self):
        # 1. INTEGRATED BORDERLESS TOP BAR
        topbar = tk.Frame(self, bg=BG_BLACK, height=50)
        topbar.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(4, 0))
        topbar.pack_propagate(False)

        topbar.bind("<ButtonPress-1>", self._start_window_drag)
        topbar.bind("<B1-Motion>", self._do_window_drag)
        topbar.bind("<Double-Button-1>", lambda e: self.toggle_maximize_window())

        self._create_top_menus(topbar)
        self._build_top_search_capsule(topbar)

        # Integrated Window Controls on Top-Right
        win_ctrl = tk.Frame(topbar, bg=BG_BLACK)
        win_ctrl.pack(side=tk.RIGHT)

        btn_close = tk.Button(
            win_ctrl, text="\uE8BB", bg=BG_BLACK, fg=TXT_MUTED,
            activebackground="#E81123", activeforeground=TXT_BRIGHT,
            bd=0, highlightthickness=0, width=4, pady=8, cursor="hand2",
            font=(self.icon_font_name, 10), command=self.destroy
        )
        btn_close.pack(side=tk.RIGHT)
        btn_close.bind("<Enter>", lambda e: btn_close.config(bg="#E81123", fg=TXT_BRIGHT))
        btn_close.bind("<Leave>", lambda e: btn_close.config(bg=BG_BLACK, fg=TXT_MUTED))

        self.btn_max_win = tk.Button(
            win_ctrl, text="\uE922", bg=BG_BLACK, fg=TXT_MUTED,
            activebackground=BG_HOVER, activeforeground=TXT_BRIGHT,
            bd=0, highlightthickness=0, width=4, pady=8, cursor="hand2",
            font=(self.icon_font_name, 10), command=self.toggle_maximize_window
        )
        self.btn_max_win.pack(side=tk.RIGHT)
        self.btn_max_win.bind("<Enter>", lambda e: self.btn_max_win.config(bg=BG_HOVER, fg=TXT_BRIGHT))
        self.btn_max_win.bind("<Leave>", lambda e: self.btn_max_win.config(bg=BG_BLACK, fg=TXT_MUTED))

        btn_min = tk.Button(
            win_ctrl, text="\uE921", bg=BG_BLACK, fg=TXT_MUTED,
            activebackground=BG_HOVER, activeforeground=TXT_BRIGHT,
            bd=0, highlightthickness=0, width=4, pady=8, cursor="hand2",
            font=(self.icon_font_name, 10), command=self.minimize_window
        )
        btn_min.pack(side=tk.RIGHT)
        btn_min.bind("<Enter>", lambda e: btn_min.config(bg=BG_HOVER, fg=TXT_BRIGHT))
        btn_min.bind("<Leave>", lambda e: btn_min.config(bg=BG_BLACK, fg=TXT_MUTED))

        # 1B. SIMULATION QUICK-ACTION TOOLBAR
        # Mirrors the Run menu's Step / Reset commands as always-visible buttons.
        # Both call the exact same handlers the menu does; the menu items remain.
        self.sim_toolbar = tk.Frame(self, bg=BG_BLACK, height=38)
        self.sim_toolbar.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(2, 0))
        self.sim_toolbar.pack_propagate(False)

        self.btn_run_toolbar = SpotifyPillButton(
            self.sim_toolbar,
            text="▶  Run",
            command=self.run_and_show_sim,
            bg_parent=BG_BLACK,
            fill_col=ACCENT_GREEN,
            fg_col=TXT_ON_WHITE,
            hover_fill="#1FDF64",
            height=28,
        )
        self.btn_run_toolbar.pack(side=tk.LEFT, padx=(6, 6), pady=4)
        attach_tooltip(self.btn_run_toolbar, lambda: (
            "หยุดชั่วคราว (Pause)" if getattr(self, "sim_running", False)
            else "เริ่มรันจำลอง (Run)") + "  •  F5")

        self.btn_step_toolbar = SpotifyPillButton(
            self.sim_toolbar,
            text="⏭  Step Instruction",
            command=self.step_and_show_sim,
            bg_parent=BG_BLACK,
            fill_col=BG_PILL_INACT,
            fg_col=TXT_BRIGHT,
            height=28,
        )
        self.btn_step_toolbar.pack(side=tk.LEFT, padx=(0, 6), pady=4)
        attach_tooltip(self.btn_step_toolbar, "รันทีละคำสั่ง (Step)  •  F10")

        self.btn_reset_toolbar = SpotifyPillButton(
            self.sim_toolbar,
            text="🔄  Reset Simulation",
            command=self.reset_sim,
            bg_parent=BG_BLACK,
            fill_col=BG_PILL_INACT,
            fg_col=TXT_BRIGHT,
            height=28,
        )
        self.btn_reset_toolbar.pack(side=tk.LEFT, padx=(0, 6), pady=4)
        attach_tooltip(self.btn_reset_toolbar, "รีเซ็ตการจำลอง (Reset)  •  Ctrl+Shift+R")

        # 2. BOTTOM STATUS BAR
        self.status_bar = tk.Frame(self, bg=BG_BLACK, height=28)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0, 6))
        self.status_bar.pack_propagate(False)

        self.status_dot = tk.Label(self.status_bar, text="●", bg=BG_BLACK, fg=ACCENT_GREEN,
                                   font=(FONT_UI, 10, "bold"))
        self.status_dot.pack(side=tk.LEFT, padx=(6, 4))

        self.status_lbl = tk.Label(
            self.status_bar, text="Real GCC 15.2  •  Ready",
            bg=BG_BLACK, fg=TXT_BRIGHT, font=(FONT_UI, 9, "bold"), cursor="hand2"
        )
        self.status_lbl.pack(side=tk.LEFT)
        self.status_lbl.bind("<Button-1>", lambda e: self._on_status_bar_clicked())

        self.cursor_lbl = tk.Label(
            self.status_bar, text="Ln 1, Col 1   •   UTF-8",
            bg=BG_BLACK, fg=TXT_MUTED, font=(FONT_UI, 9), padx=10
        )
        self.cursor_lbl.pack(side=tk.RIGHT)

        # 3. MAIN WORKBENCH CONTAINER
        self.main_body = tk.Frame(self, bg=BG_BLACK)
        self.main_body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=(2, 4))

        # 3A. LEFTMOST ICON RAIL
        act_bar = tk.Frame(self.main_body, bg=BG_ACTIVITY, width=58)
        act_bar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6))
        act_bar.pack_propagate(False)
        add_card_rounded_corners(act_bar, BG_ACTIVITY, BG_BLACK, radius=10)

        self.rail_buttons = {}
        rail_items = [
            ("explorer",   "\uE8B7", lambda: self.switch_left_sidebar("explorer", toggle=True), True),
            ("search",     "\uE721", lambda: self.switch_left_sidebar("search", toggle=True), False),
            ("chip",       "\uE950", self.toggle_machine_panel, False),
            ("simulator",  "\uE7F4", self.toggle_simulator, False),
            ("overview",   "\uE9D9", self.toggle_overview, False),
        ]

        rail_tips = {
            "explorer":  "Explorer — ไฟล์ในโปรเจกต์  (Ctrl+B)",
            "search":    "ค้นหาในโปรเจกต์  (Ctrl+Shift+F)",
            "chip":      "32-bit Machine Code / Opcode",
            "simulator": "บอร์ดจำลอง Nexys A7  (Ctrl+J)",
            "overview":  "CPU & Registers  (Ctrl+K)",
        }

        for key, glyph, cmd, is_active in rail_items:
            cell = tk.Frame(act_bar, bg=BG_ACTIVITY, width=56, height=52)
            cell.pack(fill=tk.X, pady=2)
            cell.pack_propagate(False)

            ind = tk.Frame(cell, bg=ACCENT_GREEN if is_active else BG_ACTIVITY, width=3, height=24)
            ind.place(x=0, y=14)

            btn = tk.Button(
                cell, text=glyph,
                bg=BG_ACTIVITY, fg=TXT_BRIGHT if is_active else TXT_MUTED,
                activebackground=BG_HOVER, activeforeground=TXT_BRIGHT,
                bd=0, highlightthickness=1, highlightbackground=BG_ACTIVITY,
                relief="flat", takefocus=0,
                font=(self.icon_font_name, 15), cursor="hand2", command=cmd
            )
            btn.place(relx=0.5, rely=0.5, anchor="center", width=42, height=40)

            def _r_enter(e, b=btn, k=key):
                if b.cget("state") == "disabled":
                    return
                b.config(bg="#202020", highlightbackground=BORDER_HOVER, fg=TXT_BRIGHT)

            def _r_leave(e, b=btn, k=key):
                if b.cget("state") == "disabled":
                    return
                act = self._is_rail_key_active(k)
                b.config(bg=BG_ACTIVITY, highlightbackground=BG_ACTIVITY, fg=TXT_BRIGHT if act else TXT_MUTED)

            btn.bind("<Enter>", _r_enter)
            btn.bind("<Leave>", _r_leave)
            attach_tooltip(btn, rail_tips.get(key, ""))
            self.rail_buttons[key] = (ind, btn)

        self._update_simulator_rail_button()

        # 3B. MULTI-VIEW LEFT SIDEBAR CARD (Explorer / Search)
        self.sidebar_container = tk.Frame(self.main_body, bg=BG_SIDEBAR, width=285)
        self.sidebar_container.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6))
        self.sidebar_container.pack_propagate(False)

        self.view_explorer = tk.Frame(self.sidebar_container, bg=BG_SIDEBAR)
        self.view_search = tk.Frame(self.sidebar_container, bg=BG_SIDEBAR)

        self._build_explorer_view()
        self._build_search_view()
        self.view_explorer.pack(fill=tk.BOTH, expand=True)
        add_card_rounded_corners(self.sidebar_container, BG_SIDEBAR, BG_BLACK, radius=10)

        # 3C. COLLAPSIBLE RIGHT OVERVIEW PANEL
        self.overview_panel = tk.Frame(self.main_body, bg=BG_PANEL, width=295)
        self.overview_panel.pack_propagate(False)
        self._build_overview_panel()
        add_card_rounded_corners(self.overview_panel, BG_PANEL, BG_BLACK, radius=10)

        # 3D. CENTER AREA (Editors on Top + Collapsible Simulator Panel on Bottom)
        self.center_area = tk.Frame(self.main_body, bg=BG_BLACK)
        self.center_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.sim_panel = tk.Frame(self.center_area, bg=BG_PANEL, height=240)
        self.sim_panel.pack_propagate(False)
        self._build_simulator_panel()
        add_card_rounded_corners(self.sim_panel, BG_PANEL, BG_BLACK, radius=10)

        self.editor_split = tk.PanedWindow(self.center_area, orient=tk.HORIZONTAL, bg=BG_BLACK, sashwidth=6, bd=0)
        self.editor_split.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # ---- LEFT EDITOR CARD (MULTI-TAB CODE EDITOR) ----
        self.left_group = tk.Frame(self.editor_split, bg=BG_EDITOR)
        self.editor_split.add(self.left_group, width=650)

        self.l_tabbar = tk.Frame(self.left_group, bg=BG_TAB_BAR, height=50, padx=14, pady=10)
        self.l_tabbar.pack(fill=tk.X)
        self.l_tabbar.pack_propagate(False)

        self.tabs_strip = tk.Frame(self.l_tabbar, bg=BG_TAB_BAR)
        self.tabs_strip.pack(side=tk.LEFT, fill=tk.X, expand=True)

        l_bread = tk.Frame(self.left_group, bg=BG_EDITOR, padx=16, pady=4)
        l_bread.pack(fill=tk.X)
        self.breadcrumb_lbl = tk.Label(
            l_bread, text="โค้ดต้นฉบับ",
            bg=BG_EDITOR, fg=TXT_BRIGHT, font=(FONT_UI, 13, "bold")
        )
        self.breadcrumb_lbl.pack(side=tk.LEFT)

        ed_body = tk.Frame(self.left_group, bg=BG_EDITOR, pady=4)
        ed_body.pack(fill=tk.BOTH, expand=True)

        self.line_nums = tk.Text(
            ed_body, width=4, padx=10, pady=10, takefocus=0, bd=0, highlightthickness=0,
            bg=BG_EDITOR, fg=TXT_DIM, font=(FONT_CODE, 10), state=tk.DISABLED,
            spacing1=3, spacing3=3
        )
        self.line_nums.pack(side=tk.LEFT, fill=tk.Y)

        self.code_scroll = SpotifyAutoScrollbar(ed_body, bg_track=BG_EDITOR)
        self.code_text = tk.Text(
            ed_body, wrap=tk.NONE, bd=0, highlightthickness=0, padx=8, pady=10,
            undo=True, autoseparators=True, maxundo=-1,
            bg=BG_EDITOR, fg=TXT_BRIGHT, insertbackground=ACCENT_GREEN,
            selectbackground=BG_SELECTION, font=(FONT_CODE, 10),
            spacing1=3, spacing3=3
        )
        self.code_scroll.command = self._on_editor_scrollbar_move
        self.code_text.configure(yscrollcommand=self._on_editor_yscroll)
        self.code_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.code_text.tag_configure("kw", foreground=SYN_KEYWORD, font=(FONT_CODE, 10, "bold"))
        self.code_text.tag_configure("type", foreground=SYN_TYPE)
        self.code_text.tag_configure("macro", foreground=SYN_MACRO)
        self.code_text.tag_configure("func", foreground=SYN_FUNC, font=(FONT_CODE, 10, "bold"))
        self.code_text.tag_configure("mmio", foreground=SYN_MMIO, font=(FONT_CODE, 10, "bold"))
        self.code_text.tag_configure("str", foreground=SYN_STRING)
        self.code_text.tag_configure("num", foreground=SYN_NUMBER)
        self.code_text.tag_configure("comment", foreground=SYN_COMMENT, font=(FONT_UI, 10))
        self.code_text.tag_configure("search_hit", background="#3B2E00", foreground="#FFD43B")
        self.code_text.tag_configure("error_line", background="#3A1519", foreground="#FF948E")
        self.code_text.tag_configure("active_exec_line", background="#1A402A", foreground="#38EF7D")

        self.code_text.bind("<Motion>", self._on_editor_mouse_motion)
        self.code_text.bind("<Leave>", lambda e: self._hide_error_hover_popup())
        self.code_text.bind("<KeyRelease>", self._on_code_changed)
        self.code_text.bind("<ButtonRelease-1>", self._update_cursor_pos)
        self._setup_copy_paste(self.code_text, editable=True)
        add_card_rounded_corners(self.left_group, BG_EDITOR, BG_BLACK, radius=10)

        # ---- RIGHT EDITOR CARD (32-BIT MACHINE CODE — CLOSED AT STARTUP) ----
        self.right_group = tk.Frame(self.editor_split, bg=BG_EDITOR)

        self.r_tabbar = tk.Frame(self.right_group, bg=BG_TAB_BAR, height=50, padx=14, pady=10)
        self.r_tabbar.pack(fill=tk.X)
        self.r_tabbar.pack_propagate(False)

        self.tab_btn_op = SpotifyPillButton(
            self.r_tabbar, text="32-bit Machine Code", bg_parent=BG_TAB_BAR,
            fill_col=BG_PILL_ACT, fg_col=TXT_ON_WHITE,
            font_spec=(FONT_UI, 9, "bold"), pad_x=14, height=30,
            icon_font_name=self.icon_font_name,
            command=lambda: self.switch_right_view("opcode")
        )
        self.tab_btn_op.pack(side=tk.LEFT, padx=(0, 6))

        self.tab_btn_vhdl = SpotifyPillButton(
            self.r_tabbar, text="VHDL (.vhd)", bg_parent=BG_TAB_BAR,
            fill_col=BG_PILL_INACT, fg_col=TXT_BRIGHT,
            font_spec=(FONT_UI, 9, "bold"), pad_x=14, height=30,
            icon_font_name=self.icon_font_name,
            command=lambda: self.switch_right_view("vhdl")
        )
        self.tab_btn_vhdl.pack(side=tk.LEFT, padx=(0, 6))

        self.tab_btn_verilog = SpotifyPillButton(
            self.r_tabbar, text="Verilog (.v)", bg_parent=BG_TAB_BAR,
            fill_col=BG_PILL_INACT, fg_col=TXT_BRIGHT,
            font_spec=(FONT_UI, 9, "bold"), pad_x=14, height=30,
            icon_font_name=self.icon_font_name,
            command=lambda: self.switch_right_view("verilog")
        )
        self.tab_btn_verilog.pack(side=tk.LEFT, padx=(0, 6))

        self.tab_btn_coe = SpotifyPillButton(
            self.r_tabbar, text="Vivado (.coe)", bg_parent=BG_TAB_BAR,
            fill_col=BG_PILL_INACT, fg_col=TXT_BRIGHT,
            font_spec=(FONT_UI, 9, "bold"), pad_x=14, height=30,
            icon_font_name=self.icon_font_name,
            command=lambda: self.switch_right_view("coe")
        )
        self.tab_btn_coe.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_copy_all_pill = SpotifyPillButton(
            self.r_tabbar, text="คัดลอกทั้งหมด", bg_parent=BG_TAB_BAR,
            fill_col=ACCENT_GREEN, fg_col=TXT_ON_WHITE, hover_fill="#1FDF64",
            font_spec=(FONT_UI, 9, "bold"), pad_x=14, height=30,
            icon_font_name=self.icon_font_name,
            command=self.copy_right_panel
        )
        self.btn_copy_all_pill.pack(side=tk.RIGHT)

        r_bread = tk.Frame(self.right_group, bg=BG_EDITOR, padx=16, pady=4)
        r_bread.pack(fill=tk.X)
        self.right_bread_lbl = tk.Label(
            r_bread, text="ตารางคำสั่ง 32-bit Machine Code",
            bg=BG_EDITOR, fg=TXT_BRIGHT, font=(FONT_UI, 13, "bold")
        )
        self.right_bread_lbl.pack(side=tk.LEFT)

        self.right_content = tk.Frame(self.right_group, bg=BG_EDITOR, padx=8, pady=4, bd=0, highlightthickness=0)
        self.right_content.pack(fill=tk.BOTH, expand=True)

        cols = ("pc", "fmt", "asm", "hex", "bin", "desc")
        self.op_scroll = SpotifyAutoScrollbar(self.right_content, bg_track=BG_EDITOR)
        self.op_tree = ttk.Treeview(self.right_content, columns=cols, show="headings", yscrollcommand=self.op_scroll.set)
        self.op_scroll.command = self.op_tree.yview

        self.op_tree.heading("pc", text="PC")
        self.op_tree.heading("fmt", text="Fmt")
        self.op_tree.heading("asm", text="Assembly")
        self.op_tree.heading("hex", text="Hex (32-bit)")
        self.op_tree.heading("bin", text="32-bit Machine Code (Binary)")
        self.op_tree.heading("desc", text="Operation / Sim Memory Map")

        self.op_tree.column("pc", width=62, anchor="center")
        self.op_tree.column("fmt", width=42, anchor="center")
        self.op_tree.column("asm", width=175, anchor="w")
        self.op_tree.column("hex", width=95, anchor="center")
        self.op_tree.column("bin", width=255, anchor="center")
        self.op_tree.column("desc", width=215, anchor="w")

        self.op_tree.tag_configure("active_pc", background="#1B4A2D", foreground="#38EF7D")
        self.op_tree.tag_configure("even", background=BG_EDITOR)
        self.op_tree.tag_configure("odd", background="#181818")
        self._setup_tree_copy(self.op_tree)

        self.op_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.vhdl_scroll = SpotifyAutoScrollbar(self.right_content, bg_track=BG_EDITOR)
        self.vhdl_preview = tk.Text(
            self.right_content, wrap=tk.NONE, bd=0, highlightthickness=0, padx=12, pady=12,
            bg=BG_EDITOR, fg=TXT_BRIGHT, font=(FONT_CODE, 10), spacing1=3,
            yscrollcommand=self.vhdl_scroll.set
        )
        self.vhdl_scroll.command = self.vhdl_preview.yview
        self._setup_copy_paste(self.vhdl_preview, editable=False)
        add_card_rounded_corners(self.right_group, BG_EDITOR, BG_BLACK, radius=10)

    # ==========================================================================
    # TOP ROUNDED SPOTIFY SEARCH CAPSULE
    # ==========================================================================
    def _build_top_search_capsule(self, topbar):
        self.search_capsule = tk.Canvas(
            topbar, width=460, height=36, bg=BG_BLACK, bd=0, highlightthickness=0, cursor="hand2"
        )
        self.search_capsule.place(relx=0.5, rely=0.5, anchor="center")

        self.top_search_var = tk.StringVar()
        self.top_search_entry = tk.Entry(
            self.search_capsule, textvariable=self.top_search_var,
            bg=BG_ELEVATED, fg=TXT_BRIGHT, insertbackground=ACCENT_GREEN,
            bd=0, relief="flat", font=(FONT_UI, 9)
        )
        self._top_search_placeholder = "ค้นหาโค้ดในโปรเจกต์ หรือคำสั่ง 32-bit..."
        self.top_search_entry.insert(0, self._top_search_placeholder)
        self.top_search_entry.config(fg=TXT_MUTED)

        def _draw_capsule(hover=False, focused=False):
            self.search_capsule.delete("bg_pill")
            fill = "#282828" if (hover or focused) else BG_ELEVATED
            outline = ACCENT_GREEN if focused else ("#4A4A4A" if hover else fill)
            photo = get_antialiased_pill_photo(460, 36, BG_BLACK, fill, outline)
            self.search_capsule._bg_photo = photo
            self.search_capsule.create_image(0, 0, image=photo, anchor="nw", tags="bg_pill")
            self.search_capsule.tag_lower("bg_pill")
            self.top_search_entry.config(bg=fill)

        self.search_capsule.create_text(24, 18, text="\uE721", fill=TXT_MUTED, font=(self.icon_font_name, 11))
        self.search_capsule.create_window(228, 18, window=self.top_search_entry, width=355, height=20)
        self.search_capsule.create_line(418, 9, 418, 27, fill="#383838", width=1)
        ic_folder = self.search_capsule.create_text(438, 18, text="\uE8B7", fill=TXT_MUTED, font=(self.icon_font_name, 11))
        self.search_capsule.tag_bind(ic_folder, "<Button-1>", lambda e: self.open_folder_dialog())
        _draw_capsule(False, False)

        def _on_focus_in(e):
            if self.top_search_entry.get() == self._top_search_placeholder:
                self.top_search_entry.delete(0, tk.END)
                self.top_search_entry.config(fg=TXT_BRIGHT)
            _draw_capsule(hover=True, focused=True)

        def _on_focus_out(e):
            if not self.top_search_entry.get().strip():
                self.top_search_entry.delete(0, tk.END)
                self.top_search_entry.insert(0, self._top_search_placeholder)
                self.top_search_entry.config(fg=TXT_MUTED)
            _draw_capsule(hover=False, focused=False)

        def _on_top_type(e):
            q = self.top_search_entry.get().strip()
            if q and q != self._top_search_placeholder:
                if self.left_sidebar_mode != "search":
                    self.switch_left_sidebar("search", toggle=False)
                self.search_var.set(q)
                self._run_project_search()
                self.top_search_entry.focus_set()

        self.top_search_entry.bind("<FocusIn>", _on_focus_in)
        self.top_search_entry.bind("<FocusOut>", _on_focus_out)
        self.top_search_entry.bind("<KeyRelease>", _on_top_type)
        self.search_capsule.bind("<Enter>", lambda e: _draw_capsule(hover=True, focused=(self.focus_get() == self.top_search_entry)))
        self.search_capsule.bind("<Leave>", lambda e: _draw_capsule(hover=False, focused=(self.focus_get() == self.top_search_entry)))
        self.search_capsule.bind("<Button-1>", lambda e: self.top_search_entry.focus_set())

    # ==========================================================================
    # MULTI-TAB BAR MANAGEMENT
    # ==========================================================================
    def _on_toggle_multi_tab_mode(self):
        if not self.multi_tab_var.get():
            if self.current_file_path and os.path.exists(self.current_file_path):
                self.open_tabs = [os.path.abspath(self.current_file_path)]
            else:
                self.open_tabs = self.open_tabs[-1:]
        self._refresh_editor_tabs()
        mode_str = "เปิดโหมดหลายแท็บ (Multi-Tab)" if self.multi_tab_var.get() else "ปิดโหมดหลายแท็บ (แสดงทีละ 1 แท็บ)"
        self.status_lbl.config(text=mode_str)

    def _refresh_editor_tabs(self):
        for w in self.tabs_strip.winfo_children():
            w.destroy()
        self.tab_widgets.clear()

        cur_abs = os.path.abspath(self.current_file_path) if self.current_file_path else ""
        show_close = self.multi_tab_var.get()

        for tab_path in list(self.open_tabs):
            if not os.path.exists(tab_path):
                self.open_tabs.remove(tab_path)
                continue
            fname = os.path.basename(tab_path)
            is_act = (tab_path == cur_abs)
            missing_ext = self._is_file_missing_extension(tab_path) is not None
            has_err = (tab_path in self.file_errors) and not missing_ext

            dot_col = ACCENT_YELLOW if missing_ext else (ACCENT_RED if has_err else None)
            fill_col = BG_PILL_ACT if is_act else BG_PILL_INACT
            fg_col = TXT_ON_WHITE if is_act else TXT_BRIGHT

            pill = SpotifyPillButton(
                self.tabs_strip,
                text=truncate_to_pixel_width(fname, (FONT_UI, 9, "bold"), max_px=150),
                bg_parent=BG_TAB_BAR,
                fill_col=fill_col,
                fg_col=fg_col,
                font_spec=(FONT_UI, 9, "bold"),
                pad_x=14,
                height=30,
                dot_color=dot_col,
                icon_font_name=self.icon_font_name,
                command=lambda p=tab_path: self.load_file_path(p),
                close_command=(lambda p=tab_path: self.close_tab(p)) if show_close else None,
            )
            pill.pack(side=tk.LEFT, padx=(0, 6))
            self.tab_widgets[tab_path] = pill

    def close_tab(self, filepath):
        if not filepath:
            return
        abs_p = os.path.abspath(filepath)
        if abs_p in self.open_tabs:
            idx = self.open_tabs.index(abs_p)
            self.open_tabs.remove(abs_p)
            if os.path.abspath(self.current_file_path) == abs_p:
                if self.open_tabs:
                    next_idx = min(idx, len(self.open_tabs) - 1)
                    self.load_file_path(self.open_tabs[next_idx])
                    return
                else:
                    self.current_file = ""
                    self.current_file_path = ""
                    self.code_text.delete("1.0", tk.END)
                    self.breadcrumb_lbl.config(text="ไม่มีไฟล์ที่เปิดอยู่ (คลิกไฟล์ใน Explorer เพื่อเปิด)")
                    self._hide_extension_recommend_popup()
        self._refresh_editor_tabs()
        self._highlight_active_file_in_explorer()

    def _on_editor_yscroll(self, first, last):
        self.code_scroll.set(first, last)
        self.line_nums.yview_moveto(first)

    def _on_editor_scrollbar_move(self, *args):
        self.code_text.yview(*args)
        self.line_nums.yview(*args)

    # ==========================================================================
    # RIGHT-SIDE EXTENSION RECOMMENDATION POPUP TOAST
    # ==========================================================================
    def _show_extension_recommend_popup(self, ext_info, filename):
        pass

    def _hide_extension_recommend_popup(self):
        pass

    # ==========================================================================
    # VS CODE-STYLE HOVER ERROR TOOLTIP POPUP
    # ==========================================================================
    def _on_editor_mouse_motion(self, event):
        if not self.last_error_line or not self.last_error_msg:
            self._hide_error_hover_popup()
            return
        try:
            idx = self.code_text.index(f"@{event.x},{event.y}")
            ln = int(idx.split(".")[0])
            if ln == self.last_error_line:
                self._show_error_hover_popup(event.x_root + 14, event.y_root + 18, self.last_error_msg)
            else:
                self._hide_error_hover_popup()
        except Exception:
            self._hide_error_hover_popup()

    def _show_error_hover_popup(self, x_root, y_root, msg):
        if self._hover_popup and self._hover_popup.winfo_exists():
            self._hover_popup.geometry(f"+{x_root}+{y_root}")
            return
        pop = tk.Toplevel(self)
        pop.wm_overrideredirect(True)
        pop.attributes("-topmost", True)
        pop.configure(bg=ACCENT_RED)
        pop.geometry(f"+{x_root}+{y_root}")

        inner = tk.Frame(pop, bg="#1E1E1E", padx=12, pady=8)
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        tk.Label(
            inner, text=f"●  {msg}",
            bg="#1E1E1E", fg=ACCENT_RED, font=(FONT_UI, 9, "bold"),
            justify="left", anchor="w"
        ).pack(fill=tk.X)
        self._hover_popup = pop

    def _hide_error_hover_popup(self):
        if self._hover_popup and self._hover_popup.winfo_exists():
            self._hover_popup.destroy()
        self._hover_popup = None

    # ==========================================================================
    # TOP MENUS
    # ==========================================================================
    def _create_top_menus(self, topbar):
        def make_menubutton(label_text, builder_fn):
            btn = tk.Button(
                topbar, text=label_text,
                bg=BG_BLACK, fg=TXT_MUTED,
                activebackground=BG_ELEVATED, activeforeground=TXT_BRIGHT,
                bd=0, highlightthickness=1, highlightbackground=BG_BLACK,
                relief="flat", takefocus=0,
                padx=12, pady=5, cursor="hand2",
                font=(FONT_UI, 9, "bold")
            )
            btn._is_top_menubutton = True
            btn.pack(side=tk.LEFT, padx=2, pady=8)

            def _enter(e):
                btn.config(fg=TXT_BRIGHT, bg=BG_ELEVATED, highlightbackground=BORDER_HOVER)

            def _leave(e):
                btn.config(fg=TXT_MUTED, bg=BG_BLACK, highlightbackground=BG_BLACK)

            def _open_menu():
                menu = builder_fn()
                menu.show_at_widget(btn)

            btn.configure(command=_open_menu)
            btn.bind("<Enter>", _enter)
            btn.bind("<Leave>", _leave)
            return btn

        def build_file_menu():
            m = SpotifyPopupMenu(self, tag="File")
            m.add_command("สร้างไฟล์ใหม่ (New File)", "Ctrl+N", self.start_inline_new_file)
            m.add_command("สร้างโฟลเดอร์ใหม่ (New Folder)", "", self.start_inline_new_project)
            m.add_command("เปิดโฟลเดอร์โปรเจกต์ (Open Folder...)", "", self.open_folder_dialog)
            m.add_command("บันทึกไฟล์ปัจจุบัน (Save)", "Ctrl+S", self.save_current_file)
            m.add_command("ปิดแท็บไฟล์ปัจจุบัน (Close Tab)", "Ctrl+W", lambda: self.close_tab(self.current_file_path))
            m.add_separator()
            m.add_command("⚡ ติดตั้ง/นำเข้า CPU (Setup Wizard)...", "", self.import_custom_cpu_dialog)
            m.add_command("🔨 ติดตั้ง/นำเข้าคอมไพเลอร์ (Setup Wizard)...", "", self.import_custom_compiler_dialog)
            m.add_separator()
            m.add_command("เปิดโฟลเดอร์จริงใน Windows Explorer", "", lambda: os.startfile(self.project_dir))
            m.add_separator()
            m.add_command("📦 ส่งออกโปรเจกต์ Vivado SoC ครบชุด (.v + .xdc + .tcl)...", "", lambda: self.export_file("vivado_soc"))
            m.add_command("🔬 วิเคราะห์ 5-Stage Pipeline & ทดสอบ RTL Testbench...", "Ctrl+Shift+P", self.open_rtl_verify_dialog)
            m.add_separator()
            m.add_command("ส่งออกเป็น instruction_memory.vhd...", "", lambda: self.export_file("vhdl"))
            m.add_command("ส่งออกเป็น instruction_memory.v (Verilog)...", "", lambda: self.export_file("verilog"))
            m.add_command("ส่งออกเป็น program.coe...", "", lambda: self.export_file("coe"))
            m.add_command("ส่งออกเป็น machine_code_32bit.txt...", "", lambda: self.export_file("bin"))
            m.add_separator()
            m.add_command("ออกจากโปรแกรม (Exit)", "", self.destroy)
            return m

        def build_edit_menu():
            m = SpotifyPopupMenu(self, tag="Edit")
            m.add_checkbutton("เปิดโค้ดหลายแท็บพร้อมกัน (Multi-Tab Mode)", self.multi_tab_var, self._on_toggle_multi_tab_mode)
            m.add_separator()
            m.add_command("ย้อนกลับ (Undo)", "Ctrl+Z", lambda: self._undo_text(self.code_text))
            m.add_command("ทำซ้ำ (Redo)", "Ctrl+Y", lambda: self._redo_text(self.code_text))
            m.add_separator()
            m.add_command("ตัด (Cut)", "Ctrl+X", lambda: self._cut_from(self.code_text))
            m.add_command("คัดลอก (Copy)", "Ctrl+C", lambda: self._copy_from(self.code_text))
            m.add_command("วาง (Paste)", "Ctrl+V", lambda: self._paste_into(self.code_text))
            m.add_separator()
            m.add_command("ค้นหาในโปรเจกต์ (Search)", "Ctrl+Shift+F", lambda: self.switch_left_sidebar("search", toggle=False))
            m.add_command("คัดลอกตาราง Machine Code ทั้งหมด", "", self.copy_right_panel)
            return m

        def build_view_menu():
            m = SpotifyPopupMenu(self, tag="View")
            m.add_checkbutton("32-bit Machine Code Panel", self.show_machine_panel_var, self._apply_machine_panel_visibility)
            has_board = True
            sim_label = "Board Simulator (บอร์ดจำลอง Nexys A7)"
            m.add_checkbutton(sim_label, self.show_simulator_var, self._apply_simulator_visibility, "Ctrl+J", enabled=True)
            m.add_checkbutton("Overview (สถานะ CPU & Registers)", self.show_overview_var, self._apply_overview_visibility, "Ctrl+K")
            m.add_separator()
            m.add_command("Explorer", "Ctrl+B", lambda: self.switch_left_sidebar("explorer", toggle=True))
            m.add_command("Search", "Ctrl+Shift+F", lambda: self.switch_left_sidebar("search", toggle=True))
            return m

        def build_cpu_menu():
            m = SpotifyPopupMenu(self, tag="CPU")
            m.add_radiobutton(
                "⚡ OpenMIPS 32-bit (Digilent Nexys A7 FPGA)", self.arch_var, "openmips (Nexys A7)", self._on_cpu_changed,
                on_right_click=lambda e: self.show_cpu_context_menu({"name": "OpenMIPS (Nexys A7)", "path": self._get_openmips_hdl_path()}, e)
            )
            m.add_radiobutton(
                "⚡ RISC-V RV32I 32-bit (Digilent Nexys A7 FPGA)", self.arch_var, "riscv (RV32I)", self._on_cpu_changed,
                on_right_click=lambda e: self.show_cpu_context_menu({"name": "RISC-V RV32I (Nexys A7)", "path": self._get_riscv_hdl_path()}, e)
            )
            if self.custom_cpus:
                m.add_separator()
                for cpu in list(self.custom_cpus):
                    cid = f"custom:{cpu['path']}"
                    m.add_radiobutton(
                        f"⚡ [Custom CPU] {cpu['name']}",
                        self.arch_var, cid, self._on_cpu_changed,
                        on_right_click=lambda e, c=cpu: self.show_custom_cpu_context_menu(c, e)
                    )
            m.add_separator()
            m.add_command("⚡ แฟลช CPU ปัจจุบันลงบอร์ด FPGA...", "F7", self.open_fpga_programmer_dialog)
            return m

        def build_compiler_menu():
            m = SpotifyPopupMenu(self, tag="Compiler")
            m.add_command("⚡ คอมไพล์เดี๋ยวนี้ (Build / Compile)", "Ctrl+Shift+B", self.compile_now)
            m.add_separator()
            m.add_radiobutton("⚙️ Real GCC Toolchain (RISC-V RV32IM)", self.compiler_mode_var, "gcc", self._on_compiler_mode_changed)
            m.add_radiobutton("⚙️ Real GCC Toolchain (MIPS32 / OpenMIPS)", self.compiler_mode_var, "mips_gcc", self._on_compiler_mode_changed)
            if self.custom_compilers:
                m.add_separator()
                for comp in list(self.custom_compilers):
                    cid = f"custom:{comp['path']}"
                    m.add_radiobutton(
                        f"⚙️ [Custom] {comp['name']}",
                        self.compiler_mode_var, cid, self._on_compiler_mode_changed,
                        on_right_click=lambda e, cp=comp: self.show_custom_compiler_context_menu(cp, e)
                    )
            m.add_separator()
            m.add_checkbutton("แปลงโค้ดอัตโนมัติขณะพิมพ์ (Real-Time)", self.realtime_var)
            return m

        def build_run_menu():
            m = SpotifyPopupMenu(self, tag="Run")
            m.add_command("▶  เริ่มรัน / หยุดจำลอง", "F5", self.run_and_show_sim)
            m.add_separator()
            m.add_radiobutton("⏱️  ความเร็ว: 🐢 1 Hz (ช้ามาก 1 วิ/คำสั่ง)", self.sim_speed_var, "1Hz", self._on_sim_speed_changed)
            m.add_radiobutton("⏱️  ความเร็ว: 🚶 5 Hz (ช้า 200ms / กำลังดี)", self.sim_speed_var, "5Hz", self._on_sim_speed_changed)
            m.add_radiobutton("⏱️  ความเร็ว: 🏃 20 Hz (ปานกลาง 50ms)", self.sim_speed_var, "20Hz", self._on_sim_speed_changed)
            m.add_radiobutton("⏱️  ความเร็ว: ⚡ 100 Hz (เร็ว 10ms)", self.sim_speed_var, "100Hz", self._on_sim_speed_changed)
            m.add_radiobutton("⏱️  ความเร็ว: 🚀 Max Speed (เต็มสปีด / ทันที)", self.sim_speed_var, "max", self._on_sim_speed_changed)
            m.add_separator()
            m.add_command("⏭  รันทีละคำสั่ง (Step Single Instruction)", "F10", self.step_and_show_sim)
            m.add_command("🔄  รีเซ็ตการจำลอง (Reset Simulation)", "Ctrl+Shift+R", self.reset_sim)
            m.add_separator()
            m.add_command("🔬  วิเคราะห์ 5-Stage Pipeline & ทดสอบ RTL Testbench...", "Ctrl+Shift+P", self.open_rtl_verify_dialog)
            m.add_command("⚡  แฟลชฮาร์ดแวร์ CPU ลงบอร์ด FPGA (In-App JTAG)", "F7", self.open_fpga_programmer_dialog)
            m.add_command("📦  ส่งออกโปรเจกต์ Vivado SoC (Nexys A7-100T)...", "", lambda: self.export_file("vivado_soc"))
            m.add_command("🚀  อัปโหลดโค้ดลงบอร์ดจริง Nexys A7 (USB UART)", "", self.upload_to_board)
            return m

        make_menubutton("File", build_file_menu)
        make_menubutton("Edit", build_edit_menu)
        make_menubutton("View", build_view_menu)
        make_menubutton("CPU", build_cpu_menu)
        make_menubutton("Compiler", build_compiler_menu)
        make_menubutton("Run", build_run_menu)

    # ==========================================================================
    # LEFT RAIL TOGGLE HANDLERS
    # ==========================================================================
    def _is_rail_key_active(self, key):
        if key in ("explorer", "search", "extensions"):
            return self.left_sidebar_mode == key
        if key == "chip":
            return self.show_machine_panel_var.get()
        if key == "simulator":
            return self.show_simulator_var.get()
        if key == "overview":
            return self.show_overview_var.get()
        return False

    def _update_rail_indicator(self, key, active):
        if key in self.rail_buttons:
            ind, btn = self.rail_buttons[key]
            if str(btn.cget("state")) == "disabled":
                ind.config(bg=BG_ACTIVITY)
                btn.config(fg="#383838")
                return
            ind.config(bg=ACCENT_GREEN if active else BG_ACTIVITY)
            btn.config(fg=TXT_BRIGHT if active else TXT_MUTED)

    def _update_simulator_rail_button(self):
        if not hasattr(self, "rail_buttons") or "simulator" not in self.rail_buttons:
            return
        ind, btn = self.rail_buttons["simulator"]
        btn.config(state="normal", cursor="hand2")
        self._update_rail_indicator("simulator", self.show_simulator_var.get())

    def switch_left_sidebar(self, mode, toggle=True):
        if toggle and self.left_sidebar_mode == mode:
            self.left_sidebar_mode = None
            self.sidebar_container.pack_forget()
        else:
            self.left_sidebar_mode = mode
            for v in (self.view_explorer, self.view_search):
                v.pack_forget()
            if mode == "explorer":
                self.view_explorer.pack(fill=tk.BOTH, expand=True)
            elif mode == "search":
                self.view_search.pack(fill=tk.BOTH, expand=True)
                self.search_entry.focus_set()
                self._run_project_search()

            if not self.sidebar_container.winfo_ismapped():
                self.sidebar_container.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6), before=self.center_area)

        self._update_rail_indicator("explorer",   self.left_sidebar_mode == "explorer")
        self._update_rail_indicator("search",     self.left_sidebar_mode == "search")

    def toggle_machine_panel(self):
        self.show_machine_panel_var.set(not self.show_machine_panel_var.get())
        self._apply_machine_panel_visibility()

    def _apply_machine_panel_visibility(self):
        active = self.show_machine_panel_var.get()
        pane_names = [str(p) for p in self.editor_split.panes()]
        right_str = str(self.right_group)
        if active:
            if right_str not in pane_names:
                self.editor_split.add(self.right_group, width=660)
        else:
            if right_str in pane_names:
                self.editor_split.forget(self.right_group)
        self._update_rail_indicator("chip", active)

    def toggle_simulator(self):
        self.show_simulator_var.set(not self.show_simulator_var.get())
        self._apply_simulator_visibility()

    def _apply_simulator_visibility(self):
        active = self.show_simulator_var.get()
        if active:
            if hasattr(self, "editor_split") and self.editor_split.winfo_manager() == "pack":
                self.sim_panel.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 0), before=self.editor_split)
            else:
                self.sim_panel.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 0))
        else:
            self.sim_panel.pack_forget()
        self._update_simulator_rail_button()

    def toggle_overview(self):
        self.show_overview_var.set(not self.show_overview_var.get())
        self._apply_overview_visibility()

    def _apply_overview_visibility(self):
        active = self.show_overview_var.get()
        if active:
            if hasattr(self, "center_area") and self.center_area.winfo_manager() == "pack":
                self.overview_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0), before=self.center_area)
            else:
                self.overview_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0))
        else:
            self.overview_panel.pack_forget()
        self._update_rail_indicator("overview", active)

    def run_and_show_sim(self):
        # 1. Automatically open and show 32-bit Machine Code (Opcode Table)
        if not self.show_machine_panel_var.get():
            self.show_machine_panel_var.set(True)
            self._apply_machine_panel_visibility()
        self.switch_right_view("opcode")

        # 2. Automatically open and show CPU Status & Registers Panel
        if not self.show_overview_var.get():
            self.show_overview_var.set(True)
            self._apply_overview_visibility()

        # 3. Ensure simulator panel is visible
        if not self.show_simulator_var.get():
            self.show_simulator_var.set(True)
            self._apply_simulator_visibility()

        self.toggle_sim()

    def step_and_show_sim(self):
        # 1. Automatically open and show 32-bit Machine Code (Opcode Table)
        if not self.show_machine_panel_var.get():
            self.show_machine_panel_var.set(True)
            self._apply_machine_panel_visibility()
        self.switch_right_view("opcode")

        # 2. Automatically open and show CPU Status & Registers Panel
        if not self.show_overview_var.get():
            self.show_overview_var.set(True)
            self._apply_overview_visibility()

        # 3. Ensure simulator panel is visible
        if not self.show_simulator_var.get():
            self.show_simulator_var.set(True)
            self._apply_simulator_visibility()

        self.step_sim()

    # ==========================================================================
    # UNDO / REDO / COPY / PASTE / RIGHT-CLICK MENU
    # ==========================================================================
    def _undo_text(self, widget):
        try:
            widget.edit_undo()
            self._on_code_changed()
        except Exception:
            pass

    def _redo_text(self, widget):
        try:
            widget.edit_redo()
            self._on_code_changed()
        except Exception:
            pass

    def _setup_copy_paste(self, widget, editable=True):
        def _show_ctx(event):
            widget.focus_set()
            m = SpotifyPopupMenu(self)
            if editable:
                m.add_command("ย้อนกลับ (Undo)", "Ctrl+Z", lambda: self._undo_text(widget))
                m.add_command("ทำซ้ำ (Redo)", "Ctrl+Y", lambda: self._redo_text(widget))
                m.add_separator()
                m.add_command("ตัด (Cut)", "Ctrl+X", lambda: self._cut_from(widget))
            m.add_command("คัดลอก (Copy)", "Ctrl+C", lambda: self._copy_from(widget))
            if editable:
                m.add_command("วาง (Paste)", "Ctrl+V", lambda: self._paste_into(widget))
            m.add_separator()
            m.add_command("เลือกทั้งหมด (Select All)", "Ctrl+A", lambda: self._select_all(widget))
            m.show(event.x_root, event.y_root)

        widget.bind("<Button-3>", _show_ctx)

        def on_key(event):
            if event.state & 0x4:
                code = event.keycode
                shift = bool(event.state & 0x1)
                if code == 67:
                    self._copy_from(widget)
                    return "break"
                elif code == 86 and editable:
                    self._paste_into(widget)
                    return "break"
                elif code == 88 and editable:
                    self._cut_from(widget)
                    return "break"
                elif code == 65:
                    self._select_all(widget)
                    return "break"
                elif code == 90 and editable:
                    if shift:
                        self._redo_text(widget)
                    else:
                        self._undo_text(widget)
                    return "break"
                elif code == 89 and editable:
                    self._redo_text(widget)
                    return "break"
        widget.bind("<KeyPress>", on_key, add="+")

    def _copy_from(self, widget):
        try:
            text = widget.get(tk.SEL_FIRST, tk.SEL_LAST) if widget.tag_ranges(tk.SEL) else widget.get("1.0", "end-1c")
            self.clipboard_clear()
            self.clipboard_append(text)
            self.status_lbl.config(text="คัดลอกลงคลิปบอร์ดแล้ว")
        except Exception:
            pass

    def _cut_from(self, widget):
        try:
            if widget.tag_ranges(tk.SEL):
                text = widget.get(tk.SEL_FIRST, tk.SEL_LAST)
                self.clipboard_clear()
                self.clipboard_append(text)
                widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
                self._on_code_changed()
        except Exception:
            pass

    def _paste_into(self, widget):
        try:
            text = self.clipboard_get()
            if widget.tag_ranges(tk.SEL):
                widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
            widget.insert(tk.INSERT, text)
            self._on_code_changed()
            self.status_lbl.config(text="วางโค้ดเรียบร้อย")
        except Exception:
            pass

    def _select_all(self, widget):
        widget.tag_add(tk.SEL, "1.0", tk.END)
        widget.mark_set(tk.INSERT, "1.0")
        widget.see(tk.INSERT)

    def _setup_tree_copy(self, tree):
        def _show_tree_ctx(event):
            m = SpotifyPopupMenu(self)
            m.add_command("คัดลอกแถวที่เลือก", "Ctrl+C", self._copy_selected_tree_row)
            m.add_command("คัดลอกตารางทั้งหมด", "", self.copy_right_panel)
            m.show(event.x_root, event.y_root)

        tree.bind("<Button-3>", _show_tree_ctx)
        tree.bind("<Control-c>", lambda e: self._copy_selected_tree_row())
        tree.bind("<<TreeviewSelect>>", self._on_op_tree_select)

    def _on_op_tree_select(self, event=None):
        sel = self.op_tree.selection()
        if not sel:
            return
        iid = sel[0]
        try:
            idx = int(iid)
            compiled = getattr(self, "compiled_ins", [])
            if 0 <= idx < len(compiled):
                cur = compiled[idx]
                src_line = cur.get("src_line")
                if src_line is not None and src_line > 0 and hasattr(self, "code_text"):
                    self.code_text.tag_remove("active_exec_line", "1.0", tk.END)
                    self.code_text.tag_add("active_exec_line", f"{src_line}.0", f"{src_line}.end+1c")
                    self.code_text.see(f"{src_line}.0")
        except Exception:
            pass

    def _copy_selected_tree_row(self):
        sel = self.op_tree.selection()
        if not sel:
            self.copy_right_panel()
            return
        lines = ["\t".join(str(v) for v in self.op_tree.item(iid, "values")) for iid in sel]
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        self.status_lbl.config(text="คัดลอกแถวที่เลือกแล้ว")

    def copy_right_panel(self):
        if self.right_view_mode == "vhdl":
            txt = self.last_vhdl
        elif self.right_view_mode == "verilog":
            txt = self.last_verilog
        elif self.right_view_mode == "coe":
            txt = self.last_coe
        else:
            lines = ["PC\tType\tAssembly\tHex (32-bit)\t32-bit Machine Code (Binary)\tDescription (Sim Memory Map)"]
            for i in self.compiled_ins:
                lines.append(f"{i['pc']}\t{i['fmt']}\t{i['asm']}\t{i['hex']}\t{i['fields']}\t{i['desc']}")
            txt = "\n".join(lines)
        self.clipboard_clear()
        self.clipboard_append(txt)
        self.status_lbl.config(text=f"คัดลอกตาราง {len(self.compiled_ins)} คำสั่งลงคลิปบอร์ดแล้ว")

    # ==========================================================================
    # FILE SAVING, COMPILER SYNC & REAL-TIME COMPILATION
    # ==========================================================================
    def save_current_file(self):
        if not self.current_file_path:
            return
        try:
            content = self.code_text.get("1.0", "end-1c")
            with open(self.current_file_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.compile_now()
            self.status_lbl.config(text=f"บันทึกไฟล์ {self.current_file} และคอมไพล์เรียบร้อย")
        except Exception as e:
            self.status_lbl.config(text=f"บันทึกไฟล์ไม่สำเร็จ: {e}")

    def _on_status_bar_clicked(self):
        missing_info = self._is_file_missing_extension(self.current_file_path)
        if missing_info:
            self._show_extension_recommend_popup(missing_info, self.current_file)
            return
        if self.last_error_line:
            self.code_text.mark_set(tk.INSERT, f"{self.last_error_line}.0")
            self.code_text.see(f"{self.last_error_line}.0")
            self.code_text.focus_set()

    def _set_file_error_state(self, state_kind, msg, err_line=None):
        self.code_text.tag_remove("error_line", "1.0", tk.END)
        self.last_error_line = err_line if state_kind == "error" else None
        self.last_error_msg = msg if state_kind == "error" else ""
        cur_abs = os.path.abspath(self.current_file_path) if self.current_file_path else ""

        if state_kind == "ok":
            self._hide_error_hover_popup()
            if cur_abs:
                self.file_errors.pop(cur_abs, None)
            self.status_dot.config(fg=ACCENT_GREEN)
            self.status_lbl.config(fg=TXT_BRIGHT, text=msg)
        elif state_kind == "missing_ext":
            self._hide_error_hover_popup()
            if cur_abs:
                self.file_errors.pop(cur_abs, None)
            self.status_dot.config(fg=ACCENT_YELLOW)
            self.status_lbl.config(fg=ACCENT_YELLOW, text=msg)
        else:
            if cur_abs:
                self.file_errors[cur_abs] = (err_line or 1, msg)
            self.status_dot.config(fg=ACCENT_RED)
            self.status_lbl.config(fg=ACCENT_RED, text=msg)
            if err_line:
                self.code_text.tag_add("error_line", f"{err_line}.0", f"{err_line}.end")

        self._refresh_editor_tabs()
        self._highlight_active_file_in_explorer()

    def _sync_compiler_to_file_language(self, filepath):
        ext = os.path.splitext(filepath)[1].lower()
        arch = self.get_current_arch()
        is_mips = (arch == "mips")
        arch_tag = "OpenMIPS" if is_mips else "RV32"
        comp_mode = self.compiler_mode_var.get()

        if comp_mode == "direct_hex":
            self.active_compiler_name = "Custom Machine Code / ROM"
        elif comp_mode.startswith("custom:"):
            c_name = os.path.basename(comp_mode.split("custom:", 1)[1])
            self.active_compiler_name = f"Custom: {c_name}"
        elif comp_mode in ("mips_gcc", "gcc") or (is_mips and comp_mode == "builtin"):
            if is_mips:
                if ext == ".cpp":
                    self.active_compiler_name = "Real GCC (OpenMIPS C++)"
                elif ext == ".c":
                    self.active_compiler_name = "Real GCC (OpenMIPS C)"
                elif ext == ".py":
                    self.active_compiler_name = "Python → OpenMIPS"
                elif ext == ".rs":
                    self.active_compiler_name = "Rust → OpenMIPS"
                elif ext in (".s", ".asm"):
                    self.active_compiler_name = "OpenMIPS Direct 32-Bit Assembler"
                else:
                    self.active_compiler_name = "Real GCC Toolchain (OpenMIPS 32-bit)"
            else:
                if ext == ".cpp":
                    self.active_compiler_name = "Real GCC (RISC-V RV32IM C++)"
                elif ext == ".c":
                    self.active_compiler_name = "Real GCC (RISC-V RV32IM C)"
                elif ext == ".py":
                    self.active_compiler_name = "Python → RV32"
                elif ext == ".rs":
                    self.active_compiler_name = "Rust → RV32"
                elif ext in (".s", ".asm"):
                    self.active_compiler_name = "RV32 Direct 32-Bit Assembler"
                else:
                    self.active_compiler_name = "Real GCC Toolchain (RISC-V RV32IM)"

        elif ext == ".c":
            self.active_compiler_name = f"Built-in ({arch_tag} C)"
        elif ext == ".cpp":
            self.active_compiler_name = f"Built-in ({arch_tag} C++)"
        elif ext == ".py":
            self.active_compiler_name = f"Python Compiler (Python → {arch_tag})"
        elif ext == ".rs":
            self.active_compiler_name = f"Rust Bare-Metal (Rust → {arch_tag})"
        elif ext in (".s", ".asm"):
            self.active_compiler_name = f"{arch_tag} Direct 32-Bit Assembler"
        elif ext in (".vhd", ".vhdl", ".v", ".sv", ".coe"):
            self.active_compiler_name = f"HDL Hardware Mode ({ext.upper()})"
        else:
            self.active_compiler_name = "Plain Text Editor (TEXT)"

        self._update_cursor_pos()
        self._refresh_target_pills()

    def load_file_path(self, fpath):
        if not os.path.exists(fpath):
            return
        fpath_abs = os.path.abspath(fpath)
        self._flush_pending_editor_save()
        self.current_file_path = fpath_abs
        self.current_file = os.path.basename(fpath_abs)
        if not fpath_abs.lower().startswith(os.path.abspath(self.project_dir).lower()):
            self.project_dir = os.path.dirname(fpath_abs)
        self._hide_error_hover_popup()

        # 1. Stop any currently running simulation loop immediately
        if hasattr(self, "sim_running") and self.sim_running:
            self.sim_running = False
            if hasattr(self, "sim_after_id") and self.sim_after_id:
                self.after_cancel(self.sim_after_id)
                self.sim_after_id = None
            self._set_run_ui(False)

        # 2. Fully reset CPU simulation state & Pointer (PC=0, registers=0, cycles=0)
        if hasattr(self, "sim_engine"):
            self.sim_engine.reset()
        if hasattr(self, "stage_vars"):
            for st in self.stage_vars.values():
                st.config(text="-")
        if hasattr(self, "uart_quick_console"):
            try:
                self.uart_quick_console.config(state=tk.NORMAL)
                self.uart_quick_console.delete("1.0", tk.END)
                self.uart_quick_console.insert(tk.END, "> [UART Ready] รอรับข้อมูลจาก 0xF0000010...\n")
                self.uart_quick_console.config(state=tk.DISABLED)
            except Exception:
                pass
        elif hasattr(self, "uart_line_lbl"):
            try:
                self.uart_line_lbl.config(text="> [UART Ready] _", fg=TXT_MUTED)
            except Exception:
                pass
        if hasattr(self, "latched_buttons"):
            self.latched_buttons.clear()

        if self.multi_tab_var.get():
            if fpath_abs not in self.open_tabs:
                self.open_tabs.append(fpath_abs)
        else:
            self.open_tabs = [fpath_abs]

        self.breadcrumb_lbl.config(text=f"โค้ดต้นฉบับ  •  {self.current_file}")
        self._sync_compiler_to_file_language(fpath_abs)

        with open(fpath_abs, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        self.code_text.delete("1.0", tk.END)
        self.code_text.insert("1.0", content)
        self.code_text.edit_reset()
        self._update_line_numbers()
        self._highlight_syntax()

        missing_info = self._is_file_missing_extension(fpath_abs)
        if missing_info:
            self._show_extension_recommend_popup(missing_info, self.current_file)
        else:
            self._hide_extension_recommend_popup()

        self.compile_now()

        # 3. Refresh all displays to cleanly show reset pointer and registers for the new file
        if hasattr(self, "_refresh_hilo_display"):
            self._refresh_hilo_display()
        if hasattr(self, "_refresh_register_labels"):
            self._refresh_register_labels()
        if hasattr(self, "_refresh_board_widgets"):
            self._refresh_board_widgets()
        if hasattr(self, "_highlight_active_pc"):
            self._highlight_active_pc()

    def load_file(self, filename):
        self.load_file_path(os.path.join(self.project_dir, filename))

    def _flush_pending_editor_save(self):
        if getattr(self, "_save_after_id", None):
            try:
                self.after_cancel(self._save_after_id)
            except Exception:
                pass
            self._save_after_id = None
        if self.current_file_path and os.path.exists(os.path.dirname(self.current_file_path)):
            try:
                with open(self.current_file_path, "w", encoding="utf-8") as f:
                    f.write(self.code_text.get("1.0", "end-1c"))
            except Exception:
                pass

    def _on_code_changed(self, event=None):
        self._update_line_numbers()
        self._update_cursor_pos()
        if getattr(self, "_highlight_after_id", None):
            self.after_cancel(self._highlight_after_id)
        self._highlight_after_id = self.after(60, self._highlight_syntax)

        if self.current_file_path:
            if getattr(self, "_save_after_id", None):
                self.after_cancel(self._save_after_id)
            self._save_after_id = self.after(360, self._flush_pending_editor_save)

        if self.realtime_var.get():
            if self._compile_after_id:
                self.after_cancel(self._compile_after_id)
            self._compile_after_id = self.after(360, lambda: self.compile_now(async_bg=True))

    def _update_line_numbers(self):
        lines = int(self.code_text.index("end-1c").split(".")[0])
        num_str = "\n".join(str(i) for i in range(1, lines + 1))
        self.line_nums.config(state=tk.NORMAL)
        self.line_nums.delete("1.0", tk.END)
        self.line_nums.insert("1.0", num_str)
        self.line_nums.config(state=tk.DISABLED)

    def _update_cursor_pos(self, event=None):
        pos = self.code_text.index(tk.INSERT)
        ln, col = pos.split(".")
        self.cursor_lbl.config(text=f"Ln {ln}, Col {int(col)+1}   •   UTF-8")

    def _highlight_syntax(self):
        code = self.code_text.get("1.0", tk.END)
        for tag in ("kw", "type", "macro", "func", "mmio", "str", "num", "comment"):
            self.code_text.tag_remove(tag, "1.0", tk.END)

        patterns = [
            ("kw", r"\b(while|if|else|for|return|loop|fn|let|mut|def|True|False|struct|class|static|inline)\b"),
            ("type", r"\b(int|void|volatile|unsigned|signed|uint32_t|char|short|long|i32|u32)\b"),
            ("macro", r"(#\s*(define|include)\b|#\!\[[^\]]*\])"),
            ("func", r"\b(main|printf|puts|print|println)\b"),
            ("mmio", r"\b(LED|SWITCH|SEG7|SW|BTN)\b"),
            ("str", r"\"[^\"]*\""),
            ("num", r"\b(0x[0-9a-fA-F]+|\d+)\b"),
            ("comment", r"(//[^\n]*|#[^\n]*)"),
        ]
        for tag, pat in patterns:
            for m in re.finditer(pat, code):
                self.code_text.tag_add(tag, f"1.0+{m.start()}c", f"1.0+{m.end()}c")

    def switch_right_view(self, mode):
        self.right_view_mode = mode
        for b, m in [
            (self.tab_btn_op, "opcode"),
            (self.tab_btn_vhdl, "vhdl"),
            (self.tab_btn_verilog, "verilog"),
            (self.tab_btn_coe, "coe"),
        ]:
            is_act = (mode == m)
            b.set_style(
                fill_col=BG_PILL_ACT if is_act else BG_PILL_INACT,
                fg_col=TXT_ON_WHITE if is_act else TXT_BRIGHT
            )

        if mode == "opcode":
            self.vhdl_preview.pack_forget()
            self.vhdl_scroll.pack_forget()
            self.op_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        else:
            self.op_tree.pack_forget()
            self.op_scroll.pack_forget()
            self.vhdl_preview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self.vhdl_preview.delete("1.0", tk.END)
            if mode == "vhdl":
                self.vhdl_preview.insert("1.0", self.last_vhdl)
            elif mode == "verilog":
                self.vhdl_preview.insert("1.0", self.last_verilog)
            else:
                self.vhdl_preview.insert("1.0", self.last_coe)

    def set_target_mode(self, mode_id):
        self.current_target_mode = mode_id
        if hasattr(self, "cpu_target_var"):
            self.cpu_target_var.set(mode_id)
        if mode_id in ("pymips", "fpga_board", "openmips"):
            self.arch_var.set("openmips (Nexys A7)")
        elif mode_id == "riscv":
            self.arch_var.set("riscv (RV32I)")
        self._on_cpu_changed()

    def import_custom_cpu_dialog(self):
        from tkinter import filedialog
        from ui.installer_wizard import CPUInstallWizardDialog
        fpath = filedialog.askopenfilename(
            parent=self,
            title="เลือกไฟล์โมดูล CPU ที่ต้องการติดตั้ง (เช่น openmips.v, top.v, *.v, *.vhd)",
            filetypes=[
                ("CPU Files (*.v, *.vhd, *.vhdl, *.py, *.json)", "*.v *.vhd *.vhdl *.py *.json"),
                ("Verilog HDL (*.v, *.sv)", "*.v *.sv"),
                ("VHDL Design (*.vhd, *.vhdl)", "*.vhd *.vhdl"),
                ("Python Architecture Model (*.py)", "*.py"),
                ("All Files (*.*)", "*.*")
            ]
        )
        if not fpath:
            return
        # Open Frameless Setup Wizard directly with the chosen file
        CPUInstallWizardDialog(
            parent=self,
            target_file_path=fpath,
            project_dir=self.project_dir,
            on_complete=self._on_cpu_installed_from_wizard
        )

    def _on_cpu_installed_from_wizard(self, data):
        target_path = data["path"]
        fname = data["name"]
        arch = data.get("arch", "")
        set_active = data.get("set_active", True)
        use_sim = data.get("use_sim", True)

        existing = next((c for c in self.custom_cpus if c["path"] == target_path), None)
        if existing:
            existing["name"] = fname
            existing["arch"] = arch
            existing["use_sim"] = use_sim
        else:
            self.custom_cpus.append({"name": fname, "path": target_path, "arch": arch, "use_sim": use_sim})

        if set_active:
            cid = f"custom:{target_path}"
            self.arch_var.set(cid)
            if hasattr(self, "sim_board_lbl"):
                arch_type = self.get_current_arch().upper()
                sim_tag = " • SIM CONNECTED" if use_sim else " • STANDALONE HDL"
                self.sim_board_lbl.config(text=f"สถาปัตยกรรม CPU  •  CUSTOM CPU ({fname}) [{arch_type}]{sim_tag}")

        self._save_project_settings()
        self.refresh_project_explorer()
        self.load_file_path(target_path)
        self._set_file_error_state("ok", f"ติดตั้งและนำเข้า CPU '{fname}' สำเร็จผ่าน Setup Wizard")
        self.status_lbl.config(text=f"CPU: {fname} ({arch})")
        if use_sim:
            self._ensure_runnable_software_loaded()
        self.compile_now()
        self._update_peripheral_cards()

    def import_custom_compiler_dialog(self):
        from tkinter import filedialog
        from ui.installer_wizard import CompilerInstallWizardDialog
        fpath = filedialog.askopenfilename(
            parent=self,
            title="เลือกไฟล์คอมไพเลอร์ที่ต้องการนำเข้า (.exe, .bat, .py, .jar, .sh)",
            filetypes=[
                ("Compiler Executables & Scripts (*.exe, *.bat, *.py, *.jar, *.sh)", "*.exe *.bat *.py *.jar *.sh"),
                ("Executable (*.exe)", "*.exe"),
                ("Batch / Script (*.bat, *.sh)", "*.bat *.sh"),
                ("Python Script (*.py)", "*.py"),
                ("All Files (*.*)", "*.*")
            ]
        )
        if not fpath:
            return
        # Open Frameless Compiler Setup Wizard directly with the chosen file
        CompilerInstallWizardDialog(
            parent=self,
            target_file_path=fpath,
            project_dir=self.project_dir,
            on_complete=self._on_compiler_installed_from_wizard
        )

    def _on_compiler_installed_from_wizard(self, data):
        fpath = data["path"]
        fname = data["name"]
        arch = data.get("arch", "")
        args = data.get("args", "")
        set_active = data.get("set_active", True)
        if not any(c["path"] == fpath for c in self.custom_compilers):
            self.custom_compilers.append({"name": fname, "path": fpath, "arch": arch, "args": args})

        if set_active:
            cid = f"custom:{fpath}"
            self.compiler_mode_var.set(cid)
            self.active_compiler_name = f"Custom: {fname}"
            self._set_file_error_state("ok", f"ติดตั้งคอมไพเลอร์ '{fname}' สำเร็จผ่าน Compiler Setup Wizard")
            self.status_lbl.config(text=f"Compiler: {fname} ({arch})")
            self.compile_now()
        else:
            self._set_file_error_state("ok", f"ติดตั้งคอมไพเลอร์ '{fname}' สำเร็จ (ยังไม่ได้เปิดใช้งาน)")
        self._save_project_settings()

    def delete_custom_compiler(self, comp):
        comp_path = comp.get('path', '')
        comp_name = comp.get('name', '')

        if comp in self.custom_compilers:
            self.custom_compilers.remove(comp)
        self.custom_compilers = [c for c in self.custom_compilers if c.get('path') != comp_path and c.get('name') != comp_name]

        target_cid = f"custom:{comp_path}"
        if self.compiler_mode_var.get() == target_cid or (comp_name and comp_name in self.compiler_mode_var.get()):
            self.compiler_mode_var.set("builtin")
            arch = self.get_current_arch().upper()
            self.active_compiler_name = f"Built-in {arch} Assembler"
            self.compile_now()

        self._save_project_settings()
        SpotifyPopupMenu.close_active()
        self.status_lbl.config(text=f"ถอดคอมไพเลอร์ '{comp_name}' ออกจากรายการเรียบร้อย")

    def delete_custom_cpu(self, cpu):
        import shutil
        cpu_path = cpu.get('path', '')
        cpu_name = cpu.get('name', '')

        # 1. Remove from in-memory list
        if cpu in self.custom_cpus:
            self.custom_cpus.remove(cpu)
        self.custom_cpus = [c for c in self.custom_cpus if c.get('path') != cpu_path and c.get('name') != cpu_name]

        # 2. Check if this CPU package was installed in project's custom_cpus folder
        custom_cpu_dir = os.path.abspath(os.path.join(self.project_dir, "custom_cpus"))
        if cpu_path:
            abs_p = os.path.abspath(cpu_path)
            if abs_p.startswith(custom_cpu_dir):
                pkg_dir = os.path.dirname(abs_p)
                if pkg_dir != custom_cpu_dir and os.path.isdir(pkg_dir):
                    shutil.rmtree(pkg_dir, ignore_errors=True)
                elif os.path.isfile(abs_p):
                    try:
                        os.remove(abs_p)
                    except Exception:
                        pass

        # Also clean up any folder in custom_cpus matching cpu_name
        if cpu_name:
            candidate_dir = os.path.join(custom_cpu_dir, cpu_name)
            if os.path.isdir(candidate_dir):
                shutil.rmtree(candidate_dir, ignore_errors=True)
            for ext in [".v", ".sv", ".vhd", ".vhdl"]:
                candidate_file = os.path.join(custom_cpu_dir, f"{cpu_name}{ext}")
                if os.path.isfile(candidate_file):
                    try:
                        os.remove(candidate_file)
                    except Exception:
                        pass

        # 3. If currently active, reset to default MIPS Nexys A7
        target_cid = f"custom:{cpu_path}"
        if self.arch_var.get() == target_cid or (cpu_name and cpu_name in self.arch_var.get()):
            self.arch_var.set("openmips (Nexys A7)")
            if hasattr(self, "sim_board_lbl"):
                self.sim_board_lbl.config(text="บอร์ดจำลองเสมือนจริง  •  DIGILENT NEXYS A7-100T (OPENMIPS 32-BIT CPU)")
            self.compile_now()

        # 4. Save settings and refresh project tree
        self._save_project_settings()
        SpotifyPopupMenu.close_active()
        self.refresh_project_explorer()
        self.status_lbl.config(text=f"ลบ CPU '{cpu_name}' และล้างไฟล์แพ็กเกจเรียบร้อย")

    def show_custom_compiler_context_menu(self, comp, event):
        cmenu = tk.Menu(self, tearoff=0, bg="#242424", fg="#FFFFFF", activebackground="#333333", activeforeground="#FFFFFF", bd=1)
        cmenu.add_command(label=f"🗑️ ถอด '{comp.get('name', '')}' ออกจากรายการ (Unregister)", command=lambda: self.delete_custom_compiler(comp))
        try:
            cmenu.tk_popup(event.x_root, event.y_root)
        finally:
            cmenu.grab_release()

    def _get_openmips_hdl_path(self):
        cands = [
            os.path.join(self.project_dir, "custom_cpus", "openmips", "openmips.v"),
            os.path.join(ROOT_DIR, "custom_cpus", "openmips", "openmips.v"),
            os.path.join(os.path.dirname(self.project_dir), "custom_cpus", "openmips", "openmips.v"),
        ]
        for p in cands:
            if os.path.exists(p):
                return os.path.abspath(p)
        return os.path.abspath(cands[0])

    def _get_riscv_hdl_path(self):
        cands = [
            os.path.join(self.project_dir, "custom_cpus", "riscv", "riscv_rv32i.v"),
            os.path.join(ROOT_DIR, "custom_cpus", "riscv", "riscv_rv32i.v"),
            os.path.join(os.path.dirname(self.project_dir), "custom_cpus", "riscv", "riscv_rv32i.v"),
        ]
        for p in cands:
            if os.path.exists(p):
                return os.path.abspath(p)
        return os.path.abspath(cands[0])

    def open_pin_assignment_dialog(self, cpu):
        from ui.pin_assignment_dialog import PinAssignmentDialog
        c_path = cpu.get("path", "")
        if not c_path or not os.path.exists(c_path):
            c_name = cpu.get("name", "").lower()
            if "openmips" in c_name or "mips" in c_name:
                c_path = self._get_openmips_hdl_path()
            elif "risc" in c_name or "rv32" in c_name:
                c_path = self._get_riscv_hdl_path()
        def _on_saved(data):
            if hasattr(self, "_update_peripheral_cards"):
                self._update_peripheral_cards()
            self._on_cpu_changed()
        PinAssignmentDialog(self, target_file_path=c_path, cpu_info=cpu, on_save=_on_saved)

    def show_cpu_context_menu(self, cpu, event=None):
        """Shows right-click context menu for any CPU (Built-in or Custom)."""
        import tkinter as tk
        cmenu = tk.Menu(self, tearoff=0, bg="#242424", fg="#FFFFFF", activebackground="#333333", activeforeground="#FFFFFF", bd=1)
        cmenu.add_command(
            label="⚙️ กำหนดขาพอร์ตและแอดเดรส (Pin & Address Configuration)...",
            command=lambda: self.open_pin_assignment_dialog(cpu)
        )
        c_name_low = cpu.get("name", "").lower()
        is_builtin_cpu = any(k in c_name_low for k in ("openmips", "riscv rv32i"))
        is_custom = bool(cpu.get("path") and not is_builtin_cpu)
        if is_custom:
            cmenu.add_separator()
            cmenu.add_command(
                label=f"🗑️ ลบ '{cpu.get('name', '')}' และถอนการติดตั้ง (Uninstall)",
                command=lambda: self.delete_custom_cpu(cpu)
            )
        cmenu.add_separator()
        cmenu.add_command(
            label="🔄 รีเซ็ตการเชื่อมต่อเริ่มต้น (Reset to Default)",
            command=lambda: self._reset_cpu_manifest_to_default(cpu)
        )
        try:
            if event:
                cmenu.tk_popup(event.x_root, event.y_root)
            else:
                x = self.winfo_rootx() + 300
                y = self.winfo_rooty() + 200
                cmenu.tk_popup(x, y)
        finally:
            cmenu.grab_release()

    def show_custom_cpu_context_menu(self, cpu, event):
        self.show_cpu_context_menu(cpu, event)

    def show_active_cpu_context_menu(self, event=None):
        arch_val = self.arch_var.get()
        if arch_val.startswith("custom:"):
            c_path = arch_val.split("custom:", 1)[1]
            matching = next((c for c in self.custom_cpus if c.get("path") == c_path), None)
            if matching:
                self.show_cpu_context_menu(matching, event)
                return
            self.show_cpu_context_menu({"name": os.path.basename(c_path), "path": c_path}, event)
        elif "openmips" in arch_val.lower() or "mips" in arch_val.lower():
            mips_path = self._get_openmips_hdl_path()
            self.show_cpu_context_menu({"name": "OpenMIPS (Nexys A7)", "path": mips_path}, event)
        else:
            rv_path = self._get_riscv_hdl_path()
            self.show_cpu_context_menu({"name": "RISC-V RV32I (Nexys A7)", "path": rv_path}, event)

    def _reset_cpu_manifest_to_default(self, cpu):
        from core.hdl_analyzer import invalidate_hdl_cache
        c_path = cpu.get("path", "")
        if c_path and os.path.exists(c_path):
            pkg_dir = os.path.dirname(c_path)
            manifest = os.path.join(pkg_dir, "cpu_manifest.json")
            if os.path.exists(manifest):
                try:
                    os.remove(manifest)
                except Exception:
                    pass
            invalidate_hdl_cache(c_path)
        if hasattr(self, "sim_engine"):
            self.sim_engine.reset_mmio_map()
        if hasattr(self, "_update_peripheral_cards"):
            self._update_peripheral_cards()
        self._on_cpu_changed()
        from tkinter import messagebox
        messagebox.showinfo("รีเซ็ตสำเร็จ", f"รีเซ็ตการกำหนดค่าของ {cpu.get('name', 'CPU')} เรียบร้อยแล้ว", parent=self)

    def get_current_arch(self):
        """Returns 'mips' or 'riscv' for the currently selected CPU."""
        arch_val = self.arch_var.get()
        if arch_val in ("openmips (Nexys A7)", "mips (Nexys A7)"):
            return "mips"
        if arch_val == "riscv (RV32I)":
            return "riscv"
        if arch_val.startswith("custom:"):
            c_path = arch_val.split("custom:", 1)[1]
            matching = next((c for c in self.custom_cpus if c.get("path") == c_path), None)
            if matching:
                m_arch = matching.get("arch", "").lower()
                if any(k in m_arch for k in ("mips", "dlx", "openmips")):
                    return "mips"
                if any(k in m_arch for k in ("riscv", "rv32")):
                    return "riscv"
            low = c_path.lower()
            if any(k in low for k in ("mips", "dlx", "openmips")):
                return "mips"
            if any(k in low for k in ("riscv", "rv32")):
                return "riscv"
            return "mips"
        return "mips" if any(w in arch_val.lower() for w in ("mips", "openmips", "dlx")) else "riscv"

    def _save_project_settings(self):
        try:
            data = {
                "custom_cpus": self.custom_cpus,
                "custom_compilers": self.custom_compilers,
                "active_arch": self.arch_var.get(),
                "active_compiler": self.compiler_mode_var.get(),
                "sim_speed": self.sim_speed_var.get(),
            }
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            with open(self.global_settings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _load_project_settings(self):
        data = None
        for s_path in [self.settings_file, self.global_settings_file]:
            if os.path.isfile(s_path):
                try:
                    with open(s_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if data:
                        break
                except Exception:
                    pass

        self.custom_cpus = []
        self.custom_compilers = []

        builtin_core_names = {"openmips", "riscv", "riscv_rv32i", "riscv-rv32i", "openmips 32-bit"}

        if data:
            for cpu in data.get("custom_cpus", []):
                cname = cpu.get("name", "").lower()
                cpath = cpu.get("path", "").lower()
                if any(b in cname or b in cpath for b in builtin_core_names):
                    continue
                if cpu.get("path") and os.path.exists(cpu["path"]) and not any(c["path"] == cpu["path"] for c in self.custom_cpus):
                    if "use_sim" not in cpu:
                        cpu["use_sim"] = True
                    self.custom_cpus.append(cpu)
            for comp in data.get("custom_compilers", []):
                if comp.get("path") and os.path.exists(comp["path"]) and not any(c["path"] == comp["path"] for c in self.custom_compilers):
                    self.custom_compilers.append(comp)

        # Auto-discover package subdirectories inside custom_cpus/ (skipping built-in cores)
        custom_cpu_dir = os.path.join(self.project_dir, "custom_cpus")
        if os.path.isdir(custom_cpu_dir):
            for entry in os.listdir(custom_cpu_dir):
                if entry.lower() in builtin_core_names:
                    continue
                entry_path = os.path.join(custom_cpu_dir, entry)
                if os.path.isfile(entry_path):
                    if not any(c["path"] == entry_path for c in self.custom_cpus):
                        self.custom_cpus.append({
                            "name": entry,
                            "path": entry_path,
                            "arch": "MIPS32 Architecture" if "mips" in entry.lower() else "Generic RISC"
                        })
                elif os.path.isdir(entry_path):
                    main_file = None
                    for ext in [".v", ".sv", ".vhd", ".vhdl"]:
                        candidate = os.path.join(entry_path, f"{entry}{ext}")
                        if os.path.isfile(candidate):
                            main_file = candidate
                            break
                    if not main_file:
                        for f in os.listdir(entry_path):
                            if f.lower().endswith((".v", ".sv", ".vhd", ".vhdl")):
                                main_file = os.path.join(entry_path, f)
                                break
                    if main_file and not any(c["path"] == main_file for c in self.custom_cpus):
                        low = (entry + " " + main_file).lower()
                        arch_guess = "MIPS32 Architecture" if ("mips" in low or "dlx" in low) else "Generic RISC"
                        self.custom_cpus.append({
                            "name": entry,
                            "path": main_file,
                            "arch": arch_guess
                        })

        if data:
            saved_arch = data.get("active_arch")
            if saved_arch:
                if saved_arch in ("openmips (Nexys A7)", "mips (Nexys A7)", "riscv (RV32I)"):
                    if saved_arch == "mips (Nexys A7)":
                        saved_arch = "openmips (Nexys A7)"
                    self.arch_var.set(saved_arch)
                elif saved_arch.startswith("custom:") and any(c["path"] == saved_arch.split("custom:", 1)[1] for c in self.custom_cpus):
                    self.arch_var.set(saved_arch)

            saved_comp = data.get("active_compiler")
            if saved_comp:
                if saved_comp in ("builtin", "gcc", "mips_gcc"):
                    self.compiler_mode_var.set(saved_comp)
                    if saved_comp == "mips_gcc":
                        self.active_compiler_name = "Real GCC Toolchain (MIPS32 / OpenMIPS)"
                    elif saved_comp == "gcc":
                        self.active_compiler_name = "Real GCC Toolchain (RISC-V RV32IM)"
                    else:
                        self.active_compiler_name = "OpenMIPS Native Compiler (Fast 32-bit)"
                elif saved_comp.startswith("custom:") and any(c["path"] == saved_comp.split("custom:", 1)[1] for c in self.custom_compilers):
                    self.compiler_mode_var.set(saved_comp)
                    comp_name = os.path.basename(saved_comp.split("custom:", 1)[1])
                    self.active_compiler_name = f"Custom: {comp_name}"

    def _on_app_close(self):
        self._flush_pending_editor_save()
        self._save_project_settings()
        self.destroy()

    def _on_cpu_changed(self):
        arch_val = self.arch_var.get()
        arch_type = self.get_current_arch()
        if arch_val.startswith("custom:"):
            c_path = arch_val.split("custom:", 1)[1]
            try:
                from core.hdl_analyzer import inspect_cpu_hardware_ports
                hw_caps = inspect_cpu_hardware_ports(c_path)
                is_alu = hw_caps.get("is_standalone_alu", False)
            except Exception:
                is_alu = False

            cpu_name = os.path.basename(c_path)
            if hasattr(self, "sim_board_lbl"):
                if is_alu:
                    sim_tag = " • STANDALONE ALU (NO I/O BUS)"
                else:
                    sim_tag = " • BUS CONNECTED (MMIO SOC)"
                self.sim_board_lbl.config(text=f"สถาปัตยกรรม CPU  •  CUSTOM CPU ({cpu_name.upper()}) [{arch_type.upper()}]{sim_tag}")
            self._set_file_error_state("ok", f"เลือกใช้งาน Custom CPU: {cpu_name}")
        else:
            if hasattr(self, "sim_board_lbl"):
                if arch_type == "mips":
                    self.sim_board_lbl.config(text="บอร์ดจำลองเสมือนจริง  •  DIGILENT NEXYS A7-100T (OPENMIPS 32-BIT CPU)")
                else:
                    self.sim_board_lbl.config(text="บอร์ดจำลองเสมือนจริง  •  DIGILENT NEXYS A7-100T (RISC-V RV32I 32-BIT CPU)")
        
        # Auto-match compiler if using built-in GCC toolchains
        comp_val = self.compiler_mode_var.get()
        if not comp_val.startswith("custom:"):
            if arch_type == "mips":
                self.compiler_mode_var.set("mips_gcc")
                self.active_compiler_name = "Real GCC Toolchain (MIPS32 / OpenMIPS)"
            else:
                self.compiler_mode_var.set("gcc")
                self.active_compiler_name = "Real GCC Toolchain (RISC-V RV32IM)"

        # Sync dynamic MMIO mapping from cpu_manifest if present
        try:
            if arch_val.startswith("custom:"):
                c_dir = os.path.dirname(c_path)
            elif arch_type == "mips":
                c_dir = os.path.dirname(self._get_openmips_hdl_path())
            else:
                c_dir = os.path.dirname(self._get_riscv_hdl_path())

            m_path = os.path.join(c_dir, "cpu_manifest.json")
            if hasattr(self, "sim_engine"):
                self.sim_engine.reset_mmio_map()
            if os.path.exists(m_path):
                import json
                with open(m_path, "r", encoding="utf-8") as jf:
                    mdata = json.load(jf)
                    if "mmio_mapping" in mdata and hasattr(self, "sim_engine"):
                        self.sim_engine.set_mmio_map(mdata["mmio_mapping"])
        except Exception:
            pass

        # When CPU architecture changes, recompile software for the new CPU architecture
        ext = os.path.splitext(self.current_file)[1].lower() if self.current_file else ""
        if ext in (".vhd", ".vhdl", ".v", ".sv", ".coe", ".xdc", ""):
            self.compiled_ins = []
            self._ensure_runnable_software_loaded()
        else:
            self.compile_now()
        self._update_peripheral_cards()
        self._save_project_settings()

    def _on_compiler_mode_changed(self):
        comp_val = self.compiler_mode_var.get()
        if comp_val.startswith("custom:"):
            comp_name = os.path.basename(comp_val.split("custom:", 1)[1])
            self.active_compiler_name = f"Custom: {comp_name}"
        elif comp_val in ("gcc", "mips_gcc"):
            arch = self.get_current_arch()
            self.active_compiler_name = "Real GCC Toolchain (MIPS32 / OpenMIPS)" if arch == "mips" else "Real GCC Toolchain (RISC-V RV32IM)"
        else:
            arch = self.get_current_arch()
            self.active_compiler_name = "OpenMIPS Native Compiler (Fast 32-bit)" if arch == "mips" else "Built-in Assembler (Fast 32-bit)"
        self._save_project_settings()
        self.compile_now()

    def _refresh_target_pills(self):
        pass

    def import_rom_file_dialog(self):
        from tkinter import filedialog
        fpath = filedialog.askopenfilename(
            title="เลือกไฟล์ Machine Code / ROM ที่ท่านทำมา (.hex, .coe, .bin, .elf)",
            filetypes=[
                ("All Supported ROM Formats", "*.hex *.coe *.bin *.mem *.elf *.txt"),
                ("Xilinx Memory Vector (*.coe)", "*.coe"),
                ("Hex Machine Code (*.hex, *.mem)", "*.hex *.mem"),
                ("Binary Machine Code (*.bin)", "*.bin"),
                ("ELF Executable (*.elf, *.out)", "*.elf *.out"),
                ("All Files (*.*)", "*.*")
            ]
        )
        if not fpath:
            return
        self.load_rom_file(fpath)

    def load_rom_file(self, fpath):
        try:
            from core.rom_loader import load_machine_code_file
            arch = self.get_current_arch()
            is_mips = (arch == "mips")
            ins_list, summary = load_machine_code_file(fpath, arch=arch)
            self.compiled_ins = ins_list
            self.compiler_mode_var.set("direct_hex")
            self.active_compiler_name = f"ROM ({os.path.basename(fpath)})"

            # Populate right table
            for item in self.op_tree.get_children():
                self.op_tree.delete(item)
            for idx, ins in enumerate(self.compiled_ins):
                tag = "even" if idx % 2 == 0 else "odd"
                self.op_tree.insert(
                    "", tk.END, iid=str(idx),
                    values=(ins["pc"], ins["fmt"], ins["asm"], ins["hex"], ins["fields"], ins["desc"]),
                    tags=(tag,)
                )

            # Generate HDL previews
            self.last_vhdl = generate_vhdl_rom(self.compiled_ins, arch=arch)
            self.last_verilog = generate_verilog_rom(self.compiled_ins, arch=arch)
            self.last_coe = generate_coe_content(self.compiled_ins)

            # Display in Right Machine Code Panel
            if hasattr(self, "show_machine_panel_var"):
                self.show_machine_panel_var.set(True)
                self._apply_machine_panel_visibility()

            # Load into Simulator Engine (Rust accelerator or fallback)
            raw_asm = "\n".join(ins["asm"] for ins in self.compiled_ins)
            self.sim_engine.load_program(self.compiled_ins, raw_asm_text=raw_asm)
            self.reset_sim()

            self._refresh_target_pills()
            self._set_file_error_state("ok", f"{summary}   •   พร้อมรันจำลองบนบอร์ดเสมือน")
            self.status_lbl.config(text=f"ROM Ready: {len(self.compiled_ins)} คำสั่ง 32-bit ({os.path.basename(fpath)})")
        except Exception as e:
            self._set_file_error_state("error", f"เกิดข้อผิดพลาดในการโหลด ROM: {e}")

    def _ensure_runnable_software_loaded(self):
        """Ensures that a valid software program (e.g. 1_switch_to_led.c) is compiled and loaded into ROM."""
        if getattr(self, "compiled_ins", None) and len(self.compiled_ins) > 0:
            return

        search_dirs = [self.project_dir, getattr(self, "workspace_root", None), DEFAULT_PROJECT_DIR]
        preferred_names = ["1_switch_to_led.c", "main.c", "test.c", "2_binary_counter.c", "3_calculator.c"]
        sw_file = None
        for sdir in search_dirs:
            if not sdir or not os.path.isdir(sdir):
                continue
            for name in preferred_names:
                candidate = os.path.join(sdir, name)
                if os.path.isfile(candidate):
                    sw_file = candidate
                    break
            if sw_file:
                break

        if not sw_file:
            for sdir in search_dirs:
                if not sdir or not os.path.isdir(sdir):
                    continue
                for f in os.listdir(sdir):
                    if f.lower().endswith((".c", ".s", ".asm")):
                        candidate = os.path.join(sdir, f)
                        if os.path.isfile(candidate):
                            sw_file = candidate
                            break
                if sw_file:
                    break

        if not sw_file:
            return

        try:
            with open(sw_file, "r", encoding="utf-8", errors="ignore") as f:
                code = f.read()
            ext = os.path.splitext(sw_file)[1].lower()
            arch = self.get_current_arch()
            is_mips = (arch == "mips")

            comp_mode = self.compiler_mode_var.get()
            is_asm_file = ext in (".s", ".asm")
            is_cpp_file = ext in (".cpp", ".cc", ".cxx")

            res_tuple = self._execute_compiler_pipeline(
                code, arch, is_mips, comp_mode, ext, is_asm_file, is_cpp_file
            )
            self._apply_compiled_output(sw_file, *res_tuple)
            self._update_peripheral_cards()
            return
        except Exception as e:
            print("[Auto-Load Software ROM Error]:", e)

    @staticmethod
    def _execute_compiler_pipeline(code, arch, is_mips, comp_mode, ext, is_asm_file, is_cpp_file):
        """Pure compiler/assembler worker (safe to run on a background thread, zero Tkinter calls)."""
        if comp_mode.startswith("custom:"):
            custom_tool = comp_mode.split("custom:", 1)[1]
            import tempfile
            import subprocess
            tmp_dir = tempfile.gettempdir()
            tmp_src = os.path.join(tmp_dir, f"fpga_studio_temp_src{ext}")
            with open(tmp_src, "w", encoding="utf-8") as f:
                f.write(code)

            c_lower = custom_tool.lower()
            if c_lower.endswith(".py"):
                cmd = [sys.executable, custom_tool, tmp_src]
            elif c_lower.endswith(".jar"):
                cmd = ["java", "-jar", custom_tool, tmp_src]
            elif c_lower.endswith((".bat", ".cmd")):
                cmd = ["cmd.exe", "/c", custom_tool, tmp_src]
            elif c_lower.endswith(".sh"):
                cmd = ["bash", custom_tool, tmp_src]
            else:
                cmd = [custom_tool, tmp_src]

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            )
            if proc.returncode != 0:
                err_msg = proc.stderr.strip() or proc.stdout.strip() or f"Exit code {proc.returncode}"
                raise RuntimeError(f"Custom Compiler Error:\n{err_msg}")

            out_text = proc.stdout.strip()
            out_lines = [l.strip() for l in out_text.splitlines() if l.strip()]
            is_hex_stream = False
            if out_lines and all(re.match(r"^(0x)?[0-9a-fA-F]{8}$", l.split()[0].replace(",", "")) for l in out_lines[:min(5, len(out_lines))]):
                is_hex_stream = True

            if is_hex_stream:
                from core.rom_loader import load_machine_code_file
                tmp_hex = os.path.join(tmp_dir, "fpga_studio_custom_out.hex")
                with open(tmp_hex, "w", encoding="utf-8") as f:
                    f.write(out_text)
                compiled_ins, _ = load_machine_code_file(tmp_hex, arch=arch)
                asm_lines = [ins["asm"] for ins in compiled_ins]
            else:
                asm_lines = out_lines if out_lines else [l.strip() for l in code.splitlines() if l.strip()]
                compiled_ins = assemble_mips(asm_lines) if is_mips else assemble_riscv(asm_lines)
        elif comp_mode == "mips_gcc" or (is_mips and comp_mode == "gcc"):
            if is_asm_file:
                asm_lines = code.splitlines()
                compiled_ins = assemble_mips(asm_lines)
            elif MIPS_BIN_DIR:
                asm_lines, compiled_ins = compile_with_real_mips_gcc(code, opt_level="-O1", is_cpp=is_cpp_file)
            elif RISCV_BIN_DIR:
                asm_lines, raw_ins = compile_with_real_riscv_gcc(code, opt_level="-O1", is_cpp=is_cpp_file)
                compiled_ins = translate_rv_ins_to_mips(raw_ins)
                asm_lines = [ins["asm"] for ins in compiled_ins]
            else:
                asm_lines = compile_c_to_asm(code, arch="mips")
                compiled_ins = assemble_mips(asm_lines)
        elif comp_mode == "gcc":
            if is_asm_file:
                asm_lines = code.splitlines()
                compiled_ins = assemble_riscv(asm_lines)
            elif RISCV_BIN_DIR:
                asm_lines, compiled_ins = compile_with_real_riscv_gcc(code, opt_level="-O1", is_cpp=is_cpp_file)
            else:
                asm_lines = compile_c_to_asm(code, arch="riscv")
                compiled_ins = assemble_riscv(asm_lines)
        elif is_mips:
            if is_asm_file:
                asm_lines = code.splitlines()
                compiled_ins = assemble_mips(asm_lines)
            elif MIPS_BIN_DIR:
                asm_lines, compiled_ins = compile_with_real_mips_gcc(code, opt_level="-O1", is_cpp=is_cpp_file)
            elif RISCV_BIN_DIR:
                asm_lines, raw_ins = compile_with_real_riscv_gcc(code, opt_level="-O1", is_cpp=is_cpp_file)
                compiled_ins = translate_rv_ins_to_mips(raw_ins)
                asm_lines = [ins["asm"] for ins in compiled_ins]
            else:
                asm_lines = compile_c_to_asm(code, arch="mips")
                compiled_ins = assemble_mips(asm_lines)
        else:
            if is_asm_file:
                asm_lines = code.splitlines()
                compiled_ins = assemble_riscv(asm_lines)
            elif RISCV_BIN_DIR:
                asm_lines, compiled_ins = compile_with_real_riscv_gcc(code, opt_level="-O1", is_cpp=is_cpp_file)
            else:
                asm_lines = compile_c_to_asm(code, arch="riscv")
                compiled_ins = assemble_riscv(asm_lines)

        target_arch = "mips" if is_mips else "riscv"
        raw_asm_joined = "\n".join(asm_lines)
        vhdl_txt = generate_vhdl_rom(compiled_ins, arch=target_arch)
        verilog_txt = generate_verilog_rom(compiled_ins, arch=target_arch)
        coe_txt = generate_coe_content(compiled_ins)
        return compiled_ins, raw_asm_joined, vhdl_txt, verilog_txt, coe_txt

    def _apply_compiled_output(self, fpath_snapshot, compiled_ins, raw_asm_joined, vhdl_txt, verilog_txt, coe_txt):
        self.compiled_ins = compiled_ins
        self.compiled_raw_asm = raw_asm_joined
        self.active_rom_filename = os.path.basename(fpath_snapshot) if fpath_snapshot else ""
        self.sim_engine.load_program(self.compiled_ins, raw_asm_text=self.compiled_raw_asm)

        self.last_vhdl = vhdl_txt
        self.last_verilog = verilog_txt
        self.last_coe = coe_txt

        for item in self.op_tree.get_children():
            self.op_tree.delete(item)
        pc_idx = self.sim_engine.pc_index
        for idx, ins in enumerate(self.compiled_ins):
            tag = "active_pc" if idx == pc_idx else ("even" if idx % 2 == 0 else "odd")
            self.op_tree.insert(
                "", tk.END, iid=str(idx),
                values=(ins["pc"], ins["fmt"], ins["asm"], ins["hex"], ins["fields"], ins["desc"]),
                tags=(tag,)
            )

        if self.right_view_mode in ("vhdl", "verilog", "coe"):
            self.switch_right_view(self.right_view_mode)

        self._set_file_error_state(
            "ok",
            f"{self.active_compiler_name}   •   {len(self.compiled_ins)} คำสั่ง 32-bit"
        )
        if hasattr(self, "_update_peripheral_cards"):
            self._update_peripheral_cards()
        self._update_cursor_pos()

    def _apply_compile_error(self, err_exc):
        err_str = str(err_exc)
        m_ln = re.search(r"Line\s+(\d+):\s*(.+)", err_str)
        if m_ln:
            ln_no = int(m_ln.group(1))
            clean_msg = f"Line {ln_no}: {m_ln.group(2)}"
            self._set_file_error_state("error", clean_msg, err_line=ln_no)
        else:
            self._set_file_error_state("error", f"Error: {err_str}", err_line=1)

    def compile_now(self, async_bg=False):
        if self.compiler_mode_var.get() == "direct_hex":
            return

        self._compile_seq = getattr(self, "_compile_seq", 0) + 1
        my_seq = self._compile_seq

        raw_code = self.code_text.get("1.0", tk.END)
        arch = self.get_current_arch()
        is_mips = (arch == "mips")
        comp_mode = self.compiler_mode_var.get()
        fpath_snapshot = self.current_file_path
        ext = os.path.splitext(self.current_file)[1].lower()
        self._sync_compiler_to_file_language(fpath_snapshot)

        supported_code_exts = {".c", ".cpp", ".py", ".rs", ".s", ".asm"}
        text_doc_exts = {"", ".txt", ".md", ".log", ".json", ".csv", ".ini"}
        hdl_rom_exts = {".vhd", ".vhdl", ".v", ".sv", ".coe", ".xdc"}

        # 1. Check if file extension requires an uninstalled Extension Pack
        missing_info = self._is_file_missing_extension(fpath_snapshot)
        if missing_info:
            for item in self.op_tree.get_children():
                self.op_tree.delete(item)
            self.compiled_ins = []
            self._set_file_error_state(
                "missing_ext",
                f"ยังไม่ได้ติดตั้งส่วนเสริม '{missing_info['name']}' สำหรับไฟล์ {ext} (คลิกที่นี่หรือป็อปอัพขวามือเพื่อติดตั้ง)"
            )
            return

        # 2. Plain Text / Document files or completely empty files
        if ext in text_doc_exts or not raw_code.strip():
            for item in self.op_tree.get_children():
                self.op_tree.delete(item)
            self.compiled_ins = []
            if not raw_code.strip():
                label_mode = f"{self.active_compiler_name}   •   ไฟล์ว่าง (พร้อมเขียนโค้ด)"
            else:
                label_mode = "Text File (โหมดข้อความ — เปลี่ยนนามสกุลเป็น .c, .cpp, .py, .rs, .s เพื่อแปลงเป็น Opcode ได้)"
            self._set_file_error_state("ok", label_mode)
            return

        # 3. Hardware Description / ROM files (.vhd, .v, .coe, .xdc)
        if ext in hdl_rom_exts:
            if not getattr(self, "compiled_ins", None):
                self._ensure_runnable_software_loaded()
            rom_label = getattr(self, "active_rom_filename", "1_switch_to_led.c")
            self._set_file_error_state("ok", f"ไฟล์ฮาร์ดแวร์ ({ext.upper()}) — สถาปัตยกรรม CPU พร้อมจำลองซอฟต์แวร์: {rom_label}")
            self._update_peripheral_cards()
            return

        # 4. Other unsupported code file extensions
        if ext not in supported_code_exts:
            for item in self.op_tree.get_children():
                self.op_tree.delete(item)
            self.compiled_ins = []
            self._set_file_error_state(
                "missing_ext",
                f"ไฟล์นามสกุล '{ext}' ยังไม่รองรับการแปลงเป็น 32-Bit Opcode (รองรับ .c, .cpp, .py, .rs, .s, .asm)"
            )
            return

        is_asm_file = ext in (".s", ".asm")
        is_cpp_file = (ext == ".cpp")

        # 5. Fast Syntax Checking on UI thread
        syn_line, syn_err = check_code_syntax(raw_code, ext)
        if syn_line:
            self._set_file_error_state("error", syn_err, err_line=syn_line)
            return

        if ext == ".py":
            code = transpile_python_to_c(raw_code)
        elif ext == ".rs":
            code = transpile_rust_to_c(raw_code)
        else:
            code = raw_code

        # Offload external GCC / custom subprocess execution to background worker when typing
        if async_bg and not is_asm_file:
            import threading

            def _bg_worker():
                try:
                    res_tuple = self._execute_compiler_pipeline(
                        code, arch, is_mips, comp_mode, ext, is_asm_file, is_cpp_file
                    )
                    def _on_ok():
                        if not self.winfo_exists() or self._compile_seq != my_seq or self.current_file_path != fpath_snapshot:
                            return
                        self._apply_compiled_output(fpath_snapshot, *res_tuple)
                    self.after(0, _on_ok)
                except Exception as exc:
                    def _on_err(e=exc):
                        if not self.winfo_exists() or self._compile_seq != my_seq or self.current_file_path != fpath_snapshot:
                            return
                        self._apply_compile_error(e)
                    self.after(0, _on_err)

            threading.Thread(target=_bg_worker, daemon=True).start()
            return

        try:
            res_tuple = self._execute_compiler_pipeline(
                code, arch, is_mips, comp_mode, ext, is_asm_file, is_cpp_file
            )
            self._apply_compiled_output(fpath_snapshot, *res_tuple)
        except Exception as e:
            self._apply_compile_error(e)
