# -*- coding: utf-8 -*-
"""
Nexys A7 Virtual Board Simulator Panel & CPU / Registers Overview Panel Mixin
Provides authentic Digilent Nexys A7 FPGA hardware controls:
- 8-Digit 7-Segment Display (AN0-7) with 16 Slide Switches (SW0-15) and LEDs (LD0-15) directly underneath
- Dual Tri-Color RGB LEDs (LD16-17) placed above the 5-Way Directional Pushbuttons (BTNU, BTNL, BTNC, BTNR, BTND)
- Two Red Hardware Buttons: CPU RESET and PROG B (FPGA Reconfiguration)
- Press-and-release button action with Shift-click latching support
- Frameless VGA 640x480 Color Monitor and USB-UART Serial Terminal Monitor
- 5-Stage Pipeline CPU Status & Register Inspection Overview Panel
"""

import os
import struct
import time
import tkinter as tk
from tkinter import filedialog
from config.theme import (
    BG_BLACK,
    BG_PANEL,
    BG_ELEVATED,
    BG_PILL_INACT,
    BG_PILL_ACT,
    BG_HOVER,
    BORDER_COLOR,
    BORDER_HOVER,
    ACCENT_GREEN,
    ACCENT_AMBER,
    ACCENT_RED,
    TXT_BRIGHT,
    TXT_PRIMARY,
    TXT_MUTED,
    TXT_DIM,
    TXT_ON_WHITE,
    FONT_UI,
    FONT_CODE,
)
from config.catalog import RV_NAMES, MIPS_NAMES
from ui.graphics import add_hover_border
from ui.widgets import attach_tooltip
from ui.peripheral_dialogs import VGADisplayWindow, UARTTerminalWindow


class BoardPanelsMixin:
    """Provides the bottom Nexys A7 Simulator panel, right CPU Overview panel, and HDL/UART export."""

    def _build_simulator_panel(self):
        # 1. Header Bar
        hdr = tk.Frame(self.sim_panel, bg="#181818", height=38, padx=12)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        self.sim_board_lbl = tk.Label(
            hdr, text="บอร์ดจำลองเสมือนจริง  •  DIGILENT NEXYS A7-100T (ARTIX-7 FPGA)",
            bg="#181818", fg=TXT_BRIGHT, font=(FONT_UI, 9, "bold"), cursor="hand2"
        )
        self.sim_board_lbl.pack(side=tk.LEFT)
        self.sim_board_lbl.bind("<Button-3>", lambda e: self.show_active_cpu_context_menu(e) if hasattr(self, "show_active_cpu_context_menu") else None)

        self.com_port_var = getattr(self, "com_port_var", None) or tk.StringVar(value="AUTO")
        cur_port = self.com_port_var.get().strip() or "AUTO"
        init_port_txt = "🔌 COM Auto ▾" if cur_port.upper() == "AUTO" else f"🔌 {cur_port} ▾"

        btn_wave = tk.Button(
            hdr, text="📈 คลื่นสัญญาณ (GTKWave)", bg="#1E3A8A", fg=TXT_ON_WHITE,
            activebackground="#2563EB", activeforeground=TXT_ON_WHITE,
            bd=0, highlightthickness=1, highlightbackground="#1E3A8A",
            padx=8, pady=2, cursor="hand2",
            font=(FONT_UI, 8, "bold"), command=self.open_rtl_verify_dialog
        )
        btn_wave.pack(side=tk.RIGHT, padx=3, pady=5)
        add_hover_border(btn_wave, "#1E3A8A", "#2563EB", "#1E3A8A", "#3B82F6")

        btn_flash_hw = tk.Button(
            hdr, text="⚡ แฟลช CPU", bg="#2E1B5B", fg="#E9D5FF",
            activebackground="#4C1D95", activeforeground="#FFFFFF",
            bd=0, highlightthickness=1, highlightbackground="#3B2070",
            padx=8, pady=2, cursor="hand2",
            font=(FONT_UI, 8, "bold"), command=self.open_fpga_programmer_dialog
        )
        btn_flash_hw.pack(side=tk.RIGHT, padx=3, pady=5)
        add_hover_border(btn_flash_hw, "#2E1B5B", "#4C1D95", "#3B2070", "#A855F7")

        self.hw_exec_mode_var = getattr(self, "hw_exec_mode_var", None) or tk.StringVar(value="step")
        cur_mode = self.hw_exec_mode_var.get()
        init_mode_txt = "🎯 โหมด: Step (หยุดรอ) ▾" if cur_mode == "step" else "🚀 โหมด: Auto-Run (25MHz) ▾"
        init_mode_bg = "#064E3B" if cur_mode == "step" else "#1E3A8A"
        init_mode_fg = "#6EE7B7" if cur_mode == "step" else "#BFDBFE"

        self.btn_hw_mode = tk.Button(
            hdr, text=init_mode_txt, bg=init_mode_bg, fg=init_mode_fg,
            activebackground="#047857", activeforeground="#FFFFFF",
            bd=0, highlightthickness=1, highlightbackground=init_mode_bg,
            padx=8, pady=2, cursor="hand2",
            font=(FONT_UI, 8, "bold"), command=self._show_hw_mode_popup
        )
        self.btn_hw_mode.pack(side=tk.RIGHT, padx=3, pady=5)
        add_hover_border(self.btn_hw_mode, init_mode_bg, "#047857", init_mode_bg, "#34D399")

        btn_upload = tk.Button(
            hdr, text="อัปโหลด USB", bg=BG_PILL_INACT, fg=TXT_BRIGHT,
            activebackground=BG_HOVER, activeforeground=TXT_BRIGHT,
            bd=0, highlightthickness=1, highlightbackground=BG_PILL_INACT,
            padx=8, pady=2, cursor="hand2",
            font=(FONT_UI, 8, "bold"), command=self.upload_to_board
        )
        btn_upload.pack(side=tk.RIGHT, padx=3, pady=5)
        add_hover_border(btn_upload, BG_PILL_INACT, BG_HOVER, BG_PILL_INACT, BORDER_HOVER)

        self.btn_hw_step = tk.Button(
            hdr, text="⚡ Step บอร์ดจริง", bg="#065F46", fg="#A7F3D0",
            activebackground="#047857", activeforeground="#FFFFFF",
            bd=0, highlightthickness=1, highlightbackground="#059669",
            padx=8, pady=2, cursor="hand2",
            font=(FONT_UI, 8, "bold"), command=self.step_hardware_board
        )
        self.btn_hw_step.pack(side=tk.RIGHT, padx=3, pady=5)
        add_hover_border(self.btn_hw_step, "#065F46", "#047857", "#059669", "#10B981")

        self.btn_hw_pause = tk.Button(
            hdr, text="⏸ หยุดบอร์ด", bg="#7C2D12", fg="#FED7AA",
            activebackground="#9A3412", activeforeground="#FFFFFF",
            bd=0, highlightthickness=1, highlightbackground="#C2410C",
            padx=7, pady=2, cursor="hand2",
            font=(FONT_UI, 8, "bold"), command=self.pause_hardware_board
        )
        self.btn_hw_pause.pack(side=tk.RIGHT, padx=3, pady=5)
        add_hover_border(self.btn_hw_pause, "#7C2D12", "#9A3412", "#C2410C", "#FB923C")

        self.btn_hw_run = tk.Button(
            hdr, text="▶ รัน 25MHz", bg="#1E3A8A", fg="#BFDBFE",
            activebackground="#2563EB", activeforeground="#FFFFFF",
            bd=0, highlightthickness=1, highlightbackground="#3B82F6",
            padx=7, pady=2, cursor="hand2",
            font=(FONT_UI, 8, "bold"), command=self.resume_hardware_board
        )
        self.btn_hw_run.pack(side=tk.RIGHT, padx=3, pady=5)
        add_hover_border(self.btn_hw_run, "#1E3A8A", "#2563EB", "#3B82F6", "#60A5FA")

        self.btn_hw_rst = tk.Button(
            hdr, text="🔄 รีเซ็ต PC=0", bg=BG_PILL_INACT, fg=TXT_BRIGHT,
            activebackground=BG_HOVER, activeforeground=TXT_BRIGHT,
            bd=0, highlightthickness=1, highlightbackground=BG_PILL_INACT,
            padx=7, pady=2, cursor="hand2",
            font=(FONT_UI, 8, "bold"), command=self.reset_hardware_board
        )
        self.btn_hw_rst.pack(side=tk.RIGHT, padx=3, pady=5)
        add_hover_border(self.btn_hw_rst, BG_PILL_INACT, BG_HOVER, BG_PILL_INACT, BORDER_HOVER)

        self.btn_com_port = tk.Button(
            hdr, text=init_port_txt, bg=BG_PILL_INACT, fg=TXT_BRIGHT,
            activebackground=BG_HOVER, activeforeground=TXT_BRIGHT,
            bd=0, highlightthickness=1, highlightbackground=BG_PILL_INACT,
            padx=8, pady=2, cursor="hand2",
            font=(FONT_UI, 8, "bold"), command=self._show_com_port_popup
        )
        self.btn_com_port.pack(side=tk.RIGHT, padx=3, pady=5)
        add_hover_border(self.btn_com_port, BG_PILL_INACT, BG_HOVER, BG_PILL_INACT, BORDER_HOVER)

        sim_quick_btns = []
        for b_txt, b_cmd in [
            ("รีเซ็ต",             self.reset_sim),
            ("ทีละคำสั่ง (Step)",  self.step_sim),
        ]:
            b = tk.Button(
                hdr, text=b_txt, bg=BG_PILL_INACT, fg=TXT_BRIGHT,
                activebackground=BG_HOVER, activeforeground=TXT_BRIGHT,
                bd=0, highlightthickness=1, highlightbackground=BG_PILL_INACT,
                padx=8, pady=2, cursor="hand2",
                font=(FONT_UI, 8, "bold"), command=b_cmd
            )
            b.pack(side=tk.RIGHT, padx=3, pady=5)
            add_hover_border(b, BG_PILL_INACT, BG_HOVER, BG_PILL_INACT, BORDER_HOVER)
            sim_quick_btns.append((b, b_cmd))

        self.sim_speed_var = getattr(self, "sim_speed_var", None) or tk.StringVar(value="5Hz")
        speed_lbls = {"1Hz": "1 Hz", "5Hz": "5 Hz", "20Hz": "20 Hz", "100Hz": "100 Hz", "max": "Max Speed"}
        init_speed_text = f"⏱️ {speed_lbls.get(self.sim_speed_var.get(), '5 Hz')} ▾"

        self.btn_speed = tk.Button(
            hdr, text=init_speed_text, bg=BG_PILL_INACT, fg=TXT_BRIGHT,
            activebackground=BG_HOVER, activeforeground=TXT_BRIGHT,
            bd=0, highlightthickness=1, highlightbackground=BG_PILL_INACT,
            padx=8, pady=2, cursor="hand2",
            font=(FONT_UI, 8, "bold"), command=self._show_speed_popup
        )
        self.btn_speed.pack(side=tk.RIGHT, padx=3, pady=5)
        add_hover_border(self.btn_speed, BG_PILL_INACT, BG_HOVER, BG_PILL_INACT, BORDER_HOVER)

        self.btn_run = tk.Button(
            hdr, text="▶ เริ่มรันจำลอง", bg=ACCENT_GREEN, fg=TXT_ON_WHITE,
            activebackground="#1FDF64", activeforeground=TXT_ON_WHITE,
            bd=0, highlightthickness=1, highlightbackground=ACCENT_GREEN,
            padx=10, pady=2, cursor="hand2",
            font=(FONT_UI, 8, "bold"), command=self.toggle_sim
        )
        self.btn_run.pack(side=tk.RIGHT, padx=4, pady=5)

        # Responsive overflow: when the header is too narrow, low-priority
        # buttons collapse into a trailing "⋯" menu. Listed in creation
        # order, which is also overflow order -- the first entry hides first,
        # and btn_run (last) is the final one to go.
        self._register_header_overflow(hdr, [
            (btn_wave,             self.open_rtl_verify_dialog,      3),
            (btn_flash_hw,         self.open_fpga_programmer_dialog, 3),
            (self.btn_hw_mode,     self._show_hw_mode_popup,         3),
            (btn_upload,           self.upload_to_board,             3),
            (self.btn_hw_step,     self.step_hardware_board,         3),
            (self.btn_hw_pause,    self.pause_hardware_board,        3),
            (self.btn_hw_run,      self.resume_hardware_board,       3),
            (self.btn_hw_rst,      self.reset_hardware_board,        3),
            (self.btn_com_port,    self._show_com_port_popup,        3),
            (sim_quick_btns[0][0], sim_quick_btns[0][1],             3),
            (sim_quick_btns[1][0], sim_quick_btns[1][1],             3),
            (self.btn_speed,       self._show_speed_popup,           3),
            (self.btn_run,         self.toggle_sim,                  4),
        ])

        # 2. Main Hardware Modules Body (Authentic Hardware Cards + Expanding Live Console)
        body = tk.Frame(self.sim_panel, bg=BG_PANEL, padx=8, pady=6)
        body.pack(fill=tk.BOTH, expand=True)

        self.latched_buttons = set()

        # ======================================================================
        # CARD 1: 7-SEGMENT DISPLAY (TOP) & 16-BIT SWITCHES/LEDS (AUTHENTIC HARDWARE WIDTH)
        # ======================================================================
        card_main_io = tk.Frame(body, bg="#161616", width=590, padx=8, pady=4, highlightthickness=1, highlightbackground="#282828")
        card_main_io.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6))
        card_main_io.pack_propagate(False)
        self.card_main_io = card_main_io

        self.card_main_hdr = tk.Label(
            card_main_io, text="7-SEGMENT & 16-BIT SWITCHES/LEDS",
            bg="#161616", fg=TXT_MUTED, font=(FONT_UI, 8, "bold")
        )
        self.card_main_hdr.pack(anchor="center", pady=(6, 12))

        # 8-Digit 7-Segment Display (Top - Expanded font, comfortably dropped down)
        seg_frame = tk.Frame(card_main_io, bg="#161616")
        seg_frame.pack(pady=(4, 14))

        self.seg_digits = []
        for i in range(8):
            if i == 4:
                tk.Frame(seg_frame, bg="#161616", width=16).pack(side=tk.LEFT)
            d = tk.Label(
                seg_frame, text="0", bg="#100505", fg="#FF2222",
                font=(FONT_CODE, 14, "bold"), width=2, padx=3, pady=2,
                highlightthickness=1, highlightbackground="#2A0E0E"
            )
            d.pack(side=tk.LEFT, padx=2)
            self.seg_digits.append(d)

        # 16-bit Slide Switches & LEDs (Underneath 7-segment - Perfectly Spaced across 590px)
        sw_strip = tk.Frame(card_main_io, bg="#161616")
        sw_strip.pack(fill=tk.X, expand=True, pady=(2, 2))

        self.led_widgets = {}
        self.sw_buttons = {}
        for bit in range(15, -1, -1):
            col = tk.Frame(sw_strip, bg="#161616")
            col.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)

            bulb = tk.Label(col, text="●", bg="#161616", fg="#282828", font=(FONT_UI, 10))
            bulb.pack()
            self.led_widgets[bit] = bulb

            btn = tk.Button(
                col, text="0", width=2, bd=0,
                highlightthickness=1, highlightbackground=BG_ELEVATED,
                cursor="hand2",
                bg=BG_ELEVATED, fg=TXT_MUTED, font=(FONT_CODE, 8, "bold"), pady=2,
                command=lambda b=bit: self.toggle_switch(b)
            )
            btn.pack(pady=2)
            add_hover_border(btn, BG_ELEVATED, BG_HOVER, BG_ELEVATED, BORDER_HOVER)
            self.sw_buttons[bit] = btn

            tk.Label(col, text=f"{bit}", bg="#161616", fg=TXT_DIM, font=(FONT_CODE, 7)).pack()

        # ======================================================================
        # CARD 2: RGB LEDS & BUTTONS (AUTHENTIC HARDWARE WIDTH)
        # ======================================================================
        card_btn = tk.Frame(body, bg="#161616", width=220, padx=6, pady=4, highlightthickness=1, highlightbackground="#282828")
        card_btn.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6))
        card_btn.pack_propagate(False)
        self.card_btn = card_btn

        self.card_btn_hdr = tk.Label(
            card_btn, text="BUTTONS & RGB",
            bg="#161616", fg=TXT_MUTED, font=(FONT_UI, 8, "bold")
        )
        self.card_btn_hdr.pack(anchor="center", pady=(6, 12))

        # Dual RGB LEDs centered at the top (dropped down from title)
        rgb_strip = tk.Frame(card_btn, bg="#161616")
        rgb_strip.pack(fill=tk.X, pady=(4, 10))

        rgb_center = tk.Frame(rgb_strip, bg="#161616")
        rgb_center.pack(anchor="center")
        tk.Label(rgb_center, text="RGB:", bg="#161616", fg=TXT_DIM, font=(FONT_CODE, 7, "bold")).pack(side=tk.LEFT, padx=(0, 4))
        self.rgb_widgets = []
        for rgb_name in ("LD16", "LD17"):
            w = tk.Label(rgb_center, text=f"● {rgb_name}", bg="#161616", fg="#333333", font=(FONT_UI, 7, "bold"))
            w.pack(side=tk.LEFT, padx=3)
            self.rgb_widgets.append(w)

        # Buttons Center Area (Takes space and centers D-pad + Red buttons)
        btn_area = tk.Frame(card_btn, bg="#161616")
        btn_area.pack(expand=True, fill=tk.BOTH, pady=1)

        btn_center_box = tk.Frame(btn_area, bg="#161616")
        btn_center_box.place(relx=0.5, rely=0.5, anchor="center")

        dpad = tk.Frame(btn_center_box, bg="#161616")
        dpad.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_widgets = {}

        def _on_btn_press(event, bit):
            # Shift + Click toggles latch mode (กดค้าง)
            is_shift = bool(event.state & 0x0001)
            if is_shift:
                if bit in self.latched_buttons:
                    self.latched_buttons.remove(bit)
                    self.sim_engine.set_button(bit, False)
                else:
                    self.latched_buttons.add(bit)
                    self.sim_engine.set_button(bit, True)
            else:
                # Normal press (กดแล้วปล่อย)
                if bit not in self.latched_buttons:
                    self.sim_engine.set_button(bit, True)
            self._refresh_board_widgets()

        def _on_btn_release(event, bit):
            # If not latched with Shift, release immediately on mouse up
            if bit not in self.latched_buttons:
                self.sim_engine.set_button(bit, False)
                self._refresh_board_widgets()

        def _make_push_btn(parent, text, bit, is_red=False):
            b = tk.Button(
                parent, text=text, width=3 if not is_red else 6, bd=0,
                bg="#3A1519" if is_red else BG_ELEVATED,
                fg="#FF948E" if is_red else TXT_BRIGHT,
                highlightthickness=1,
                highlightbackground="#5A2529" if is_red else "#333333",
                font=(FONT_UI, 7, "bold"), cursor="hand2", pady=2 if not is_red else 2
            )
            b.bind("<ButtonPress-1>", lambda e, b_num=bit: _on_btn_press(e, b_num))
            b.bind("<ButtonRelease-1>", lambda e, b_num=bit: _on_btn_release(e, b_num))
            self.btn_widgets[bit] = b
            return b

        # D-pad cross layout (BTNU, BTNL, BTNC, BTNR, BTND)
        _make_push_btn(dpad, "▲", 1).grid(row=0, column=1, padx=1, pady=1)  # BTNU
        _make_push_btn(dpad, "◀", 2).grid(row=1, column=0, padx=1, pady=1)  # BTNL
        _make_push_btn(dpad, "●", 0).grid(row=1, column=1, padx=1, pady=1)  # BTNC
        _make_push_btn(dpad, "▶", 3).grid(row=1, column=2, padx=1, pady=1)  # BTNR
        _make_push_btn(dpad, "▼", 4).grid(row=2, column=1, padx=1, pady=1)  # BTND

        # Two Red Buttons: CPU RESET & PROG B (Hardware FPGA Reconfig)
        red_box = tk.Frame(btn_center_box, bg="#161616")
        red_box.pack(side=tk.LEFT)

        b_rst = _make_push_btn(red_box, "RESET", 5, is_red=True)
        b_rst.pack(pady=2)

        def _on_prog_click():
            self.reset_sim()
            self.status_lbl.config(text="✓ FPGA PROG B: โหลด Bitstream ใหม่ และรีเซ็ตฮาร์ดแวร์เสร็จสมบูรณ์")

        b_prog = tk.Button(
            red_box, text="PROG B", width=6, bd=0,
            bg="#3A1519", fg="#FF948E", highlightthickness=1,
            highlightbackground="#5A2529", font=(FONT_UI, 7, "bold"),
            cursor="hand2", pady=2, command=_on_prog_click
        )
        b_prog.pack(pady=2)
        add_hover_border(b_prog, "#3A1519", "#4A1D22", "#5A2529", ACCENT_RED)

        # ======================================================================
        # CARD 3: PERIPHERALS & LIVE SERIAL TERMINAL (EXPANDS ACROSS SCREEN)
        # ======================================================================
        card_io = tk.Frame(body, bg="#161616", padx=10, pady=4, highlightthickness=1, highlightbackground="#282828")
        card_io.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.card_io = card_io

        self.card_io_hdr = tk.Label(
            card_io, text="PERIPHERALS (VGA & UART SERIAL)",
            bg="#161616", fg=TXT_MUTED, font=(FONT_UI, 8, "bold")
        )
        self.card_io_hdr.pack(anchor="w", pady=(4, 4))

        # Compact Rows Container for Monitors
        rows_frame = tk.Frame(card_io, bg="#161616")
        rows_frame.pack(fill=tk.X, pady=(0, 2))

        # VGA Section (Streamlined without awkward empty gaps)
        vga_box = tk.Frame(rows_frame, bg="#161616")
        vga_box.pack(fill=tk.X, pady=1)

        tk.Label(
            vga_box, text="🖥️ VGA Port (640×480 @ 60Hz)", bg="#161616",
            fg=TXT_BRIGHT, font=(FONT_UI, 8, "bold")
        ).pack(side=tk.LEFT)

        btn_open_vga = tk.Button(
            vga_box, text="🖥️ เปิดจอภาพ VGA", bg=BG_PILL_INACT, fg=TXT_BRIGHT,
            activebackground=BG_HOVER, activeforeground=TXT_BRIGHT,
            bd=0, highlightthickness=1, highlightbackground="#333333",
            padx=10, pady=1, cursor="hand2", font=(FONT_UI, 8, "bold"),
            command=self.open_vga_monitor
        )
        btn_open_vga.pack(side=tk.RIGHT)
        add_hover_border(btn_open_vga, BG_PILL_INACT, BG_HOVER, BG_PILL_INACT, BORDER_HOVER)

        # UART Serial Section
        uart_box = tk.Frame(rows_frame, bg="#161616")
        uart_box.pack(fill=tk.X, pady=1)

        tk.Label(
            uart_box, text="💬 USB-UART (115200 8-N-1)", bg="#161616",
            fg=TXT_BRIGHT, font=(FONT_UI, 8, "bold")
        ).pack(side=tk.LEFT)

        btn_open_uart = tk.Button(
            uart_box, text="💬 เปิด Serial Monitor", bg=BG_PILL_INACT, fg=TXT_BRIGHT,
            activebackground=BG_HOVER, activeforeground=TXT_BRIGHT,
            bd=0, highlightthickness=1, highlightbackground="#333333",
            padx=10, pady=1, cursor="hand2", font=(FONT_UI, 8, "bold"),
            command=self.open_uart_monitor
        )
        btn_open_uart.pack(side=tk.RIGHT)
        add_hover_border(btn_open_uart, BG_PILL_INACT, BG_HOVER, BG_PILL_INACT, BORDER_HOVER)

        # Multi-line Live UART Quick Console (Utilizes all bottom card space for newlines)
        console_frame = tk.Frame(card_io, bg="#080C0A", padx=4, pady=2, highlightthickness=1, highlightbackground="#222222")
        console_frame.pack(fill=tk.BOTH, expand=True, pady=(2, 2))

        c_hdr = tk.Frame(console_frame, bg="#080C0A")
        c_hdr.pack(fill=tk.X)
        tk.Label(c_hdr, text=">_ LIVE SERIAL LOG", bg="#080C0A", fg=TXT_DIM, font=(FONT_CODE, 7, "bold")).pack(side=tk.LEFT)

        self.uart_quick_console = tk.Text(
            console_frame, height=3, bg="#080C0A", fg=ACCENT_GREEN,
            insertbackground=ACCENT_GREEN, selectbackground="#1B4D27",
            font=(FONT_CODE, 8), wrap=tk.WORD, bd=0, highlightthickness=0,
            padx=4, pady=1
        )
        self.uart_quick_console.pack(fill=tk.BOTH, expand=True)
        self.uart_quick_console.insert(tk.END, "> [UART Ready] รอรับข้อมูลจาก 0xF0000010...\n")
        self.uart_quick_console.config(state=tk.DISABLED, cursor="hand2")

        # Click anywhere on quick console to launch full terminal
        self.uart_quick_console.bind("<Button-1>", lambda e: self.open_uart_monitor())
        console_frame.bind("<Button-1>", lambda e: self.open_uart_monitor())
        c_hdr.bind("<Button-1>", lambda e: self.open_uart_monitor())
        self.uart_line_lbl = self.uart_quick_console

        self.vga_lbl = self.uart_line_lbl
        self.vga_window = None
        self.uart_window = None
        self._refresh_board_widgets()

    def open_vga_monitor(self):
        if self.vga_window is None or not self.vga_window.winfo_exists():
            self.vga_window = VGADisplayWindow(self, self.sim_engine)
        self.vga_window.deiconify()
        try:
            self.winfo_toplevel()._active_raised_window = self.vga_window
        except Exception:
            pass
        self.vga_window.lift()
        self.vga_window.focus_force()

    def open_uart_monitor(self):
        if self.uart_window is None or not self.uart_window.winfo_exists():
            self.uart_window = UARTTerminalWindow(self, self.sim_engine, on_send_callback=self._refresh_board_widgets)
        self.uart_window.deiconify()
        try:
            self.winfo_toplevel()._active_raised_window = self.uart_window
        except Exception:
            pass
        self.uart_window.lift()
        self.uart_window.focus_force()

    def _build_overview_panel(self):
        hdr = tk.Frame(self.overview_panel, bg="#181818", height=40, padx=16)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        tk.Label(hdr, text="สถานะ CPU & REGISTERS", bg="#181818", fg=TXT_BRIGHT,
                 font=(FONT_UI, 10, "bold")).pack(side=tk.LEFT)

        btn_reset_regs = tk.Button(
            hdr, text="↺ รีเซ็ตรีจิสเตอร์", bg=BG_ELEVATED, fg=TXT_BRIGHT,
            activebackground=ACCENT_GREEN, activeforeground=TXT_ON_WHITE,
            font=(FONT_UI, 8, "bold"), relief=tk.FLAT, bd=0, padx=8, pady=3,
            cursor="hand2", command=self.reset_registers
        )
        btn_reset_regs.pack(side=tk.RIGHT)

        pipe_sec = tk.Frame(self.overview_panel, bg=BG_PANEL, padx=12, pady=6)
        pipe_sec.pack(fill=tk.X)

        badge_box = tk.Frame(pipe_sec, bg=BG_ELEVATED, padx=8, pady=4)
        badge_box.pack(fill=tk.X, pady=(0, 4))

        self.ov_cycle_badge = tk.Label(
            badge_box, text="PC = 0x0000   •   Cycles = 0",
            bg=BG_ELEVATED, fg=ACCENT_GREEN, font=(FONT_CODE, 8, "bold")
        )
        self.ov_cycle_badge.pack(fill=tk.X)

        self.ov_hilo_badge = tk.Label(
            badge_box, text="HI = 0x00000000   •   LO = 0x00000000",
            bg=BG_ELEVATED, fg=TXT_MUTED, font=(FONT_CODE, 8)
        )

        self.stage_vars = {}
        for st_key, st_title in [
            ("IF",  "1. IF (Fetch)"),
            ("ID",  "2. ID (Decode)"),
            ("EX",  "3. EX (ALU)"),
            ("MEM", "4. MEM (I/O)"),
            ("WB",  "5. WB (Write)"),
        ]:
            r = tk.Frame(pipe_sec, bg=BG_PANEL, pady=1)
            r.pack(fill=tk.X)
            tk.Label(r, text=st_title, bg=BG_PANEL, fg=TXT_MUTED, font=(FONT_UI, 8, "bold"), width=13, anchor="w").pack(side=tk.LEFT)
            val_lbl = tk.Label(r, text="-", bg=BG_ELEVATED, fg=TXT_BRIGHT, font=(FONT_CODE, 8),
                               anchor="w", padx=8, pady=2)
            val_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.stage_vars[st_key] = val_lbl

        tk.Frame(self.overview_panel, bg=BORDER_COLOR, height=1).pack(fill=tk.X, padx=12, pady=4)

        reg_sec = tk.Frame(self.overview_panel, bg=BG_PANEL, padx=8, pady=2)
        reg_sec.pack(fill=tk.BOTH, expand=True)
        self.reg_sec_title = tk.Label(reg_sec, text="ค่าในเรจิสเตอร์ 32 ช่อง ($0–$31)", bg=BG_PANEL, fg=TXT_BRIGHT,
                                      font=(FONT_UI, 9, "bold"), anchor="w")
        self.reg_sec_title.pack(fill=tk.X, pady=(0, 3))

        grid_box = tk.Frame(reg_sec, bg=BG_PANEL)
        grid_box.pack(fill=tk.BOTH, expand=True)
        grid_box.columnconfigure(0, weight=1)
        grid_box.columnconfigure(1, weight=1)

        self.reg_labels = {}
        self.reg_name_labels = {}
        self._prev_reg_vals = {}

        for row_idx in range(16):
            r_left = row_idx
            r_right = row_idx + 16

            # Left cell (r0 - r15)
            c_left = tk.Frame(grid_box, bg=BG_PANEL)
            c_left.grid(row=row_idx, column=0, sticky="ew", padx=(0, 4), pady=1)

            nl = tk.Label(c_left, text=f"${r_left}", bg=BG_PANEL, fg=TXT_MUTED, font=(FONT_CODE, 8), anchor="w")
            nl.pack(side=tk.LEFT)
            vl = tk.Label(c_left, text="0x00000000", bg=BG_PANEL, fg=TXT_PRIMARY, font=(FONT_CODE, 8), anchor="e")
            vl.pack(side=tk.RIGHT)
            self.reg_name_labels[r_left] = nl
            self.reg_labels[r_left] = vl

            # Right cell (r16 - r31)
            c_right = tk.Frame(grid_box, bg=BG_PANEL)
            c_right.grid(row=row_idx, column=1, sticky="ew", padx=(4, 0), pady=1)

            nr = tk.Label(c_right, text=f"${r_right}", bg=BG_PANEL, fg=TXT_MUTED, font=(FONT_CODE, 8), anchor="w")
            nr.pack(side=tk.LEFT)
            vr = tk.Label(c_right, text="0x00000000", bg=BG_PANEL, fg=TXT_PRIMARY, font=(FONT_CODE, 8), anchor="e")
            vr.pack(side=tk.RIGHT)
            self.reg_name_labels[r_right] = nr
            self.reg_labels[r_right] = vr

    # ==========================================================================
    # SIMULATOR & BOARD CONTROLS
    # ==========================================================================
    def toggle_switch(self, bit):
        self.sim_engine.toggle_switch_bit(bit)
        self._refresh_board_widgets()

    def _update_peripheral_cards(self):
        self._refresh_hilo_display()
        self._refresh_register_labels()
        """Dynamic Peripheral Dimming & Status Indicator based on real CPU hardware HDL pins & code."""
        arch_val = self.arch_var.get() if hasattr(self, "arch_var") else ""
        is_custom = arch_val.startswith("custom:")
        
        # Built-in Nexys A7 FPGA CPUs (OpenMIPS and RISC-V RV32I) always have full SoC Bus
        has_bus = True
        has_gpio = True
        has_uart = True
        has_vga = True
        is_standalone_alu = False

        if is_custom:
            c_path = arch_val.split("custom:", 1)[1]
            try:
                from core.hdl_analyzer import inspect_cpu_hardware_ports
                hw_caps = inspect_cpu_hardware_ports(c_path)
                has_bus = hw_caps.get("has_bus", False)
                has_gpio = hw_caps.get("has_gpio", False)
                has_uart = hw_caps.get("has_uart", False)
                has_vga = hw_caps.get("has_vga", False)
                is_standalone_alu = hw_caps.get("is_standalone_alu", False)
            except Exception:
                pass

        if is_standalone_alu or (not has_bus and not has_gpio and not has_uart and not has_vga):
            # Pure ALU-only core or Closed Testbench without external ports -> UNMAPPED
            if hasattr(self, "card_main_io") and hasattr(self, "card_main_hdr"):
                self.card_main_io.config(highlightbackground="#1C1C1C", highlightthickness=1)
                self.card_main_hdr.config(text="7-SEGMENT & 16-BIT SWITCHES/LEDS • [UNMAPPED]", fg="#555555")
            if hasattr(self, "card_btn") and hasattr(self, "card_btn_hdr"):
                self.card_btn.config(highlightbackground="#1C1C1C", highlightthickness=1)
                self.card_btn_hdr.config(text="BUTTONS & RGB • [UNMAPPED]", fg="#555555")
            if hasattr(self, "card_io") and hasattr(self, "card_io_hdr"):
                self.card_io.config(highlightbackground="#1C1C1C", highlightthickness=1)
                self.card_io_hdr.config(text="PERIPHERALS (VGA & UART SERIAL) • [UNMAPPED]", fg="#555555")
            return

        # Check active peripherals in compiled instructions or simulator engine
        ins_text = " ".join(i.get("desc", "") + " " + i.get("asm", "") for i in getattr(self, "compiled_ins", []))
        
        has_io = bool("0xF0000000" in ins_text or "0xF0000004" in ins_text or "0xF0000008" in ins_text or "LED" in ins_text or "SWITCH" in ins_text or "SEG7" in ins_text or (hasattr(self, "sim_engine") and (self.sim_engine.led_value > 0 or self.sim_engine.seg7_value > 0)))
        has_btn = bool("0xF000000C" in ins_text or "0xF0000018" in ins_text or "BTN" in ins_text or "BUTTON" in ins_text or "RGB" in ins_text or (hasattr(self, "sim_engine") and (self.sim_engine.btn_value > 0 or any(self.sim_engine.rgb_value))))
        has_periph = bool("0xF0000010" in ins_text or "0xF0000014" in ins_text or "0xFF00" in ins_text or "UART" in ins_text or "VGA" in ins_text or (hasattr(self, "sim_engine") and (len(self.sim_engine.uart_buffer) > 0 or len(self.sim_engine.vga_buffer) > 0)))

        # For OpenMIPS, RISC-V RV32I, and Custom CPUs with use_sim=True:
        # Peripherals are connected: Clean dark borders, no green highlight, no badges
        if hasattr(self, "card_main_io") and hasattr(self, "card_main_hdr"):
            self.card_main_io.config(highlightbackground="#282828", highlightthickness=1)
            self.card_main_hdr.config(text="7-SEGMENT & 16-BIT SWITCHES/LEDS", fg=TXT_MUTED)

        if hasattr(self, "card_btn") and hasattr(self, "card_btn_hdr"):
            self.card_btn.config(highlightbackground="#282828", highlightthickness=1)
            self.card_btn_hdr.config(text="BUTTONS & RGB", fg=TXT_MUTED)

        if hasattr(self, "card_io") and hasattr(self, "card_io_hdr"):
            self.card_io.config(highlightbackground="#282828", highlightthickness=1)
            self.card_io_hdr.config(text="PERIPHERALS (VGA & UART SERIAL)", fg=TXT_MUTED)

    def _refresh_board_widgets(self):
        sw_val = self.sim_engine.sw_value
        led_val = self.sim_engine.led_value
        seg_val = self.sim_engine.seg7_value
        btn_val = getattr(self.sim_engine, "btn_value", 0)

        # Switches & LEDs
        for bit, btn in self.sw_buttons.items():
            is_on = ((sw_val >> bit) & 1) == 1
            btn.config(
                text="1" if is_on else "0",
                bg=ACCENT_GREEN if is_on else BG_ELEVATED,
                fg=TXT_ON_WHITE if is_on else TXT_MUTED
            )
        for bit, bulb in self.led_widgets.items():
            is_on = ((led_val >> bit) & 1) == 1
            bulb.config(fg="#1ED760" if is_on else "#282828")

        # 7-Segment (Matches Real Hardware Nexys A7: 8-digit Hexadecimal / Nibble decoding)
        s = f"{seg_val & 0xFFFFFFFF:08X}"
        for i in range(8):
            self.seg_digits[i].config(text=s[i])

        # Push Buttons
        for bit, b in getattr(self, "btn_widgets", {}).items():
            is_active = ((btn_val >> bit) & 1) == 1
            is_latched = bit in getattr(self, "latched_buttons", set())

            if bit == 5:  # CPU RESET
                bg_col = ACCENT_RED if is_active else ("#6A1E24" if is_latched else "#3A1519")
                fg_col = TXT_ON_WHITE if is_active else "#FF948E"
            else:
                bg_col = ACCENT_GREEN if is_active else ("#18542A" if is_latched else BG_ELEVATED)
                fg_col = TXT_ON_WHITE if is_active else TXT_BRIGHT

            b.config(bg=bg_col, fg=fg_col)

        # RGB LEDs
        rgb_vals = getattr(self.sim_engine, "rgb_value", [0, 0])
        for idx, w in enumerate(getattr(self, "rgb_widgets", [])):
            val = rgb_vals[idx] if idx < len(rgb_vals) else 0
            if val != 0:
                hex_col = f"#{val & 0xFFFFFF:06X}"
                w.config(fg=hex_col)
            else:
                w.config(fg="#333333")

        # UART Live Console readout (Supports multi-line & newlines live in card)
        buf = getattr(self.sim_engine, "uart_buffer", "")
        if hasattr(self, "uart_quick_console"):
            self.uart_quick_console.config(state=tk.NORMAL)
            self.uart_quick_console.delete("1.0", tk.END)
            if buf:
                lines = buf.splitlines()[-5:]
                text_to_show = "\n".join(lines) if lines else "> _"
                self.uart_quick_console.insert(tk.END, text_to_show)
            else:
                self.uart_quick_console.insert(tk.END, "> [UART Ready] รอรับข้อมูลจาก CPU (0xF0000010)...")
            self.uart_quick_console.config(state=tk.DISABLED)
            self.uart_quick_console.see(tk.END)
        elif hasattr(self, "uart_line_lbl"):
            if buf:
                lines = [l for l in buf.splitlines() if l.strip()]
                last_line = lines[-1] if lines else ""
                self.uart_line_lbl.config(text=f"> {last_line} _", fg=ACCENT_GREEN)
            else:
                self.uart_line_lbl.config(text="> [UART Ready] _", fg=TXT_MUTED)

        # Update open dialogs
        if getattr(self, "uart_window", None) and self.uart_window.winfo_exists():
            self.uart_window._refresh_content()
        if getattr(self, "vga_window", None) and self.vga_window.winfo_exists():
            self.vga_window.redraw()

        self._refresh_hilo_display()

    # ==========================================================================
    # RESPONSIVE HEADER OVERFLOW ("⋯" MENU)
    # ==========================================================================
    def _register_header_overflow(self, hdr, entries):
        """Make the simulator header degrade gracefully when it is too narrow.

        `entries` is [(widget, command, padx), ...] in creation order, which is
        also priority order: the FIRST entry is the first to be pushed into the
        overflow menu, the LAST is the most important and hides last.
        """
        self._hdr_frame = hdr
        self._hdr_items = [{"w": w, "cmd": c, "padx": px} for w, c, px in entries]
        self._hdr_hidden = []
        self._hdr_busy = False
        self._hdr_sig = None

        self.btn_hdr_more = tk.Button(
            hdr, text="⋯", bg=BG_PILL_INACT, fg=TXT_BRIGHT,
            activebackground=BG_HOVER, activeforeground=TXT_BRIGHT,
            bd=0, highlightthickness=1, highlightbackground=BG_PILL_INACT,
            padx=8, pady=2, cursor="hand2",
            font=(FONT_UI, 10, "bold"), command=self._show_hdr_overflow_popup
        )
        add_hover_border(self.btn_hdr_more, BG_PILL_INACT, BG_HOVER, BG_PILL_INACT, BORDER_HOVER)
        attach_tooltip(self.btn_hdr_more, self._hdr_overflow_tip)

        hdr.bind("<Configure>", lambda e: self._relayout_sim_header())
        self.after(150, self._relayout_sim_header)

    def _relayout_sim_header(self):
        hdr = getattr(self, "_hdr_frame", None)
        if hdr is None or self._hdr_busy or not hdr.winfo_exists():
            return
        total = hdr.winfo_width()
        if total <= 1:            # not laid out yet
            return

        title_w = self.sim_board_lbl.winfo_reqwidth() if hasattr(self, "sim_board_lbl") else 0
        avail = total - title_w - 10
        widths = {id(it["w"]): it["w"].winfo_reqwidth() + it["padx"] * 2 for it in self._hdr_items}

        if sum(widths.values()) <= avail:
            keep, hidden = list(self._hdr_items), []
        else:
            budget = avail - (self.btn_hdr_more.winfo_reqwidth() + 6)
            keep, hidden, used, stop = [], [], 0, False
            for it in reversed(self._hdr_items):      # highest priority first
                w = widths[id(it["w"])]
                if not stop and used + w <= budget:
                    keep.append(it)
                    used += w
                else:
                    stop = True                        # strict priority, no gaps
                    hidden.append(it)
            keep.reverse()
            hidden.reverse()

        sig = tuple(id(it["w"]) for it in keep)
        if sig == self._hdr_sig:                       # nothing changed -> no churn
            return
        self._hdr_sig = sig

        self._hdr_busy = True
        try:
            for it in self._hdr_items:
                it["w"].pack_forget()
            self.btn_hdr_more.pack_forget()
            if hidden:
                self.btn_hdr_more.pack(side=tk.RIGHT, padx=3, pady=5)
            for it in keep:
                it["w"].pack(side=tk.RIGHT, padx=it["padx"], pady=5)
            self._hdr_hidden = hidden
        finally:
            self._hdr_busy = False

    def _hdr_overflow_tip(self):
        """Preview what the overflow menu currently holds, so the
        ⋯ button is not an opaque mystery."""
        hidden = getattr(self, "_hdr_hidden", [])
        if not hidden:
            return ""
        nl = chr(10)
        names = [it["w"].cget("text") for it in hidden]
        shown = names[:8]
        more = len(names) - len(shown)
        body = nl.join("• " + n for n in shown)
        if more:
            body += nl + "• … อีก %d รายการ" % more
        return "เครื่องมือเพิ่มเติม (%d)%s%s" % (len(names), nl, body)

    def _show_hdr_overflow_popup(self):
        from ui.widgets import SpotifyPopupMenu
        m = SpotifyPopupMenu(self, tag="BoardHeaderOverflow")
        for it in self._hdr_hidden:
            # read the label live so toggling buttons (Run/Pause, speed, COM
            # port, hw mode) show their current text inside the menu too
            m.add_command(it["w"].cget("text"), "", it["cmd"])
        m.show_at_widget(self.btn_hdr_more)

    def _set_run_ui(self, running):
        """Single source of truth for Run/Pause button appearance.

        Keeps the simulator panel's btn_run and the top toolbar's pill button
        in sync. Both are optional: either may not exist yet depending on which
        panels have been built, so each is guarded.
        """
        if running:
            label, color = "⏸ หยุดชั่วคราว", ACCENT_AMBER
        else:
            label, color = "▶ เริ่มรันจำลอง", ACCENT_GREEN

        if hasattr(self, "btn_run"):
            self.btn_run.config(text=label, bg=color)

        if hasattr(self, "btn_run_toolbar"):
            # set_style() does not touch hover_fill, so keep it in step with
            # fill_col -- otherwise hovering the amber Pause button redraws green.
            self.btn_run_toolbar.hover_fill = "#FFB224" if running else "#1FDF64"
            self.btn_run_toolbar.set_style(
                text="⏸  Pause" if running else "▶  Run",
                fill_col=color,
                fg_col=TXT_ON_WHITE,
            )

    def toggle_sim(self):
        if self.sim_running:
            self.sim_running = False
            if self.sim_after_id:
                self.after_cancel(self.sim_after_id)
                self.sim_after_id = None
            self._set_run_ui(False)
            self.status_lbl.config(text="หยุดการจำลองชั่วคราว")
        else:
            # Ensure program instructions are loaded in ROM
            if not getattr(self, "compiled_ins", None):
                if hasattr(self, "_ensure_runnable_software_loaded"):
                    self._ensure_runnable_software_loaded()

            # Auto-rewind pointer to 0 if out of bounds or at the end
            if hasattr(self, "sim_engine") and hasattr(self, "compiled_ins") and self.compiled_ins:
                if self.sim_engine.pc_index >= len(self.compiled_ins) or self.sim_engine.pc_index < 0:
                    self.sim_engine.pc_index = 0
                    self._highlight_active_pc()

            # Auto-open 32-bit Machine Code (Opcode) and Registers panel
            if hasattr(self, "show_machine_panel_var") and not self.show_machine_panel_var.get():
                self.show_machine_panel_var.set(True)
                self._apply_machine_panel_visibility()
            if hasattr(self, "switch_right_view"):
                self.switch_right_view("opcode")
            if hasattr(self, "show_overview_var") and not self.show_overview_var.get():
                self.show_overview_var.set(True)
                self._apply_overview_visibility()

            self.sim_running = True
            self._set_run_ui(True)
            self.status_lbl.config(text="กำลังรันจำลองการทำงานบนบอร์ดเสมือน Nexys A7...")
            self._sim_loop()

    def _sim_loop(self):
        if not self.sim_running:
            return
        if not getattr(self, "compiled_ins", None):
            if hasattr(self, "_ensure_runnable_software_loaded"):
                self._ensure_runnable_software_loaded()
            if not getattr(self, "compiled_ins", None):
                self.sim_running = False
                self._set_run_ui(False)
                self.status_lbl.config(text="กรุณาเปิดไฟล์โค้ด (.c หรือ .s) เพื่อรันจำลอง")
                return

        is_mips = (self.get_current_arch() == "mips") if hasattr(self, "get_current_arch") else any(k in self.arch_var.get().lower() for k in ("mips", "openmips"))
        speed_val = self.sim_speed_var.get() if hasattr(self, "sim_speed_var") else "5Hz"
        if speed_val == "1Hz":
            batch_size = 1
            delay_ms = 1000
        elif speed_val == "5Hz":
            batch_size = 1
            delay_ms = 200
        elif speed_val == "20Hz":
            batch_size = 1
            delay_ms = 50
        elif speed_val == "100Hz":
            batch_size = 2
            delay_ms = 20
        else: # "max"
            batch_size = 2500
            delay_ms = 20

        raw_asm = getattr(self, "compiled_raw_asm", None)
        res = self.sim_engine.step_batch(self.compiled_ins, batch_size=batch_size, is_mips=is_mips, raw_asm_text=raw_asm)
        if res:
            for st_key in ("IF", "ID", "EX", "MEM", "WB"):
                self.stage_vars[st_key].config(text=res[st_key])
            self._refresh_board_widgets()
            self._refresh_register_labels()
            self._highlight_active_pc()

            if res.get("error"):
                self.status_lbl.config(text=f"⚠️ คำเตือนการจำลอง: {res['error']}", fg=ACCENT_AMBER)

            if res.get("is_halted"):
                self.sim_running = False
                if self.sim_after_id:
                    self.after_cancel(self.sim_after_id)
                    self.sim_after_id = None
                self._set_run_ui(False)
                is_mips = (self.get_current_arch() == "mips") if hasattr(self, "get_current_arch") else False
                ret_val = self.sim_engine.regs[14] if self.sim_engine.regs[14] else (self.sim_engine.regs[2] or self.sim_engine.regs[10])
                self.status_lbl.config(
                    text=f"✅ โปรแกรมทำงานเสร็จสิ้น (HALTED) • รวม {self.sim_engine.cycles} ไซเคิล • ผลลัพธ์: {ret_val} (0x{ret_val:X})",
                    fg=ACCENT_GREEN
                )
                return

        self.sim_after_id = self.after(delay_ms, self._sim_loop)

    def reset_sim(self):
        if self.sim_running:
            self.toggle_sim()
        self.sim_engine.reset()
        self.latched_buttons.clear()
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
        for st in self.stage_vars.values():
            st.config(text="-")
        self._update_peripheral_cards()
        self._refresh_board_widgets()
        self._refresh_register_labels(force=True)
        self._refresh_hilo_display()
        self._highlight_active_pc(force=True)

    def step_sim(self):
        # Ensure program instructions are loaded in ROM
        if not getattr(self, "compiled_ins", None):
            if hasattr(self, "_ensure_runnable_software_loaded"):
                self._ensure_runnable_software_loaded()

        # Auto-rewind pointer to 0 if out of bounds or at the end
        if hasattr(self, "sim_engine") and hasattr(self, "compiled_ins") and self.compiled_ins:
            if self.sim_engine.pc_index >= len(self.compiled_ins) or self.sim_engine.pc_index < 0:
                self.sim_engine.pc_index = 0
                self._highlight_active_pc()

        # Auto-open 32-bit Machine Code (Opcode) and Registers panel
        if hasattr(self, "show_machine_panel_var") and not self.show_machine_panel_var.get():
            self.show_machine_panel_var.set(True)
            self._apply_machine_panel_visibility()
        if hasattr(self, "switch_right_view"):
            self.switch_right_view("opcode")
        if hasattr(self, "show_overview_var") and not self.show_overview_var.get():
            self.show_overview_var.set(True)
            self._apply_overview_visibility()

        is_mips = (self.get_current_arch() == "mips") if hasattr(self, "get_current_arch") else any(k in self.arch_var.get().lower() for k in ("mips", "openmips"))
        raw_asm = getattr(self, "compiled_raw_asm", None)
        res = self.sim_engine.step(self.compiled_ins, is_mips=is_mips, raw_asm_text=raw_asm)
        if not res:
            return

        for st_key in ("IF", "ID", "EX", "MEM", "WB"):
            self.stage_vars[st_key].config(text=res[st_key])

        self._refresh_board_widgets()
        self._refresh_register_labels()
        self._highlight_active_pc()
        if res.get("error"):
            self.status_lbl.config(text=f"⚠️ คำเตือนการจำลอง: {res['error']}", fg=ACCENT_AMBER)

    def _refresh_hilo_display(self):
        arch_val = self.arch_var.get() if hasattr(self, "arch_var") else ""
        is_custom = arch_val.startswith("custom:")
        has_hilo = False
        is_alu = False

        if is_custom:
            c_path = arch_val.split("custom:", 1)[1]
            try:
                from core.hdl_analyzer import inspect_cpu_hardware_ports
                caps = inspect_cpu_hardware_ports(c_path)
                has_hilo = caps.get("has_hilo", False)
                is_alu = caps.get("is_standalone_alu", False)
            except Exception:
                has_hilo = False
                is_alu = False
        else:
            arch_type = self.get_current_arch() if hasattr(self, "get_current_arch") else "mips"
            has_hilo = (arch_type == "mips")

        if hasattr(self, "ov_cycle_badge") and hasattr(self, "sim_engine"):
            self.ov_cycle_badge.config(
                text=f"PC = 0x{self.sim_engine.pc_index * 4:04X}   •   Cycles = {self.sim_engine.cycles}"
            )

        if hasattr(self, "ov_hilo_badge") and hasattr(self, "sim_engine"):
            if is_alu:
                # Standalone ALU: Display real ALU output bus and Zero/Negative status flags
                alu_res = getattr(self.sim_engine, "last_alu_out", 0) & 0xFFFFFFFF
                z_flag = 1 if alu_res == 0 else 0
                n_flag = 1 if (alu_res & 0x80000000) != 0 else 0
                self.ov_hilo_badge.config(
                    text=f"ALU_OUT = 0x{alu_res:08X}   •   Z={z_flag}  N={n_flag}",
                    fg=ACCENT_AMBER
                )
                if self.ov_hilo_badge.winfo_manager() != "pack":
                    self.ov_hilo_badge.pack(fill=tk.X, pady=(2, 0))
            elif has_hilo:
                # MIPS Core with HILO Special Registers (e.g. OpenMIPS)
                self.ov_hilo_badge.config(
                    text=f"HI = 0x{self.sim_engine.hi:08X}   •   LO = 0x{self.sim_engine.lo:08X}",
                    fg=TXT_MUTED
                )
                if self.ov_hilo_badge.winfo_manager() != "pack":
                    self.ov_hilo_badge.pack(fill=tk.X, pady=(2, 0))
            else:
                # RISC-V or Core without HILO (e.g. RV32I)
                if self.ov_hilo_badge.winfo_manager() == "pack":
                    self.ov_hilo_badge.pack_forget()

    def reset_registers(self):
        """Reset all 32 CPU registers to 0, reset PC to 0, and refresh overview panel."""
        self.sim_engine.reset_registers()
        for st in self.stage_vars.values():
            st.config(text="-")
        self._refresh_hilo_display()
        self._refresh_register_labels(force=True)
        self._highlight_active_pc(force=True)

    def _refresh_register_labels(self, force=False):
        arch_val = self.arch_var.get() if hasattr(self, "arch_var") else ""
        arch_type = self.get_current_arch() if hasattr(self, "get_current_arch") else "mips"
        is_mips = (arch_type == "mips")
        is_alu = False
        if arch_val.startswith("custom:"):
            c_path = arch_val.split("custom:", 1)[1]
            try:
                from core.hdl_analyzer import inspect_cpu_hardware_ports
                is_alu = inspect_cpu_hardware_ports(c_path).get("is_standalone_alu", False)
            except Exception:
                pass

        if hasattr(self, "reg_sec_title"):
            if is_alu:
                self.reg_sec_title.config(text="ค่าในเรจิสเตอร์ ALU 32 ช่อง (r0–r31)")
            elif is_mips:
                self.reg_sec_title.config(text="ค่าในเรจิสเตอร์ MIPS 32 ช่อง ($0–$31)")
            else:
                self.reg_sec_title.config(text="ค่าในเรจิสเตอร์ RISC-V 32 ช่อง (x0–x31)")

        MIPS_COMPACT = [
            "$zero", "$at", "$v0", "$v1", "$a0", "$a1", "$a2", "$a3",
            "$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7",
            "$s0", "$s1", "$s2", "$s3", "$s4", "$s5", "$s6", "$s7",
            "$t8", "$t9", "$k0", "$k1", "$gp", "$sp", "$fp", "$ra"
        ]
        RV_COMPACT = [
            "x0/ze", "x1/ra", "x2/sp", "x3/gp", "x4/tp", "x5/t0", "x6/t1", "x7/t2",
            "x8/s0", "x9/s1", "x10/a0", "x11/a1", "x12/a2", "x13/a3", "x14/a4", "x15/a5",
            "x16/a6", "x17/a7", "x18/s2", "x19/s3", "x20/s4", "x21/s5", "x22/s6", "x23/s7",
            "x24/s8", "x25/s9", "x26/s10", "x27/s11", "x28/t3", "x29/t4", "x30/t5", "x31/t6"
        ]

        if not hasattr(self, "_prev_reg_vals"):
            self._prev_reg_vals = {}

        for rnum, lbl in self.reg_labels.items():
            val = self.sim_engine.regs[rnum] & 0xFFFFFFFF
            old_val = self._prev_reg_vals.get(rnum)
            if force or old_val != val:
                lbl.config(text=f"0x{val:08X}", fg=ACCENT_GREEN if val != 0 else TXT_PRIMARY)
                self._prev_reg_vals[rnum] = val

            if hasattr(self, "reg_name_labels") and rnum in self.reg_name_labels:
                if is_alu:
                    rname = f"r{rnum}"
                elif is_mips:
                    rname = MIPS_COMPACT[rnum] if rnum < len(MIPS_COMPACT) else f"${rnum}"
                else:
                    rname = RV_COMPACT[rnum] if rnum < len(RV_COMPACT) else f"x{rnum}"
                self.reg_name_labels[rnum].config(text=f"{rname:6s}")

    def _highlight_active_pc(self, force=False):
        pc_idx = self.sim_engine.pc_index
        prev_pc = getattr(self, "_prev_active_pc", None)
        compiled = getattr(self, "compiled_ins", [])
        if force or prev_pc != pc_idx:
            # 1. Clear previous highlight & pointer
            if prev_pc is not None and prev_pc != pc_idx:
                prev_iid = str(prev_pc)
                if self.op_tree.exists(prev_iid):
                    tag = "even" if prev_pc % 2 == 0 else "odd"
                    self.op_tree.item(prev_iid, tags=(tag,))
                    if prev_pc < len(compiled):
                        orig_pc = compiled[prev_pc].get("pc", "")
                        old_vals = list(self.op_tree.item(prev_iid, "values"))
                        if old_vals:
                            old_vals[0] = orig_pc
                            self.op_tree.item(prev_iid, values=old_vals)

            # 2. Add visual pointer ▶ to Opcode Table on the right
            active_iid = str(pc_idx)
            cur_ins = compiled[pc_idx] if (pc_idx < len(compiled)) else None
            if self.op_tree.exists(active_iid):
                self.op_tree.item(active_iid, tags=("active_pc",))
                self.op_tree.see(active_iid)
                old_vals = list(self.op_tree.item(active_iid, "values"))
                if old_vals and cur_ins:
                    orig_pc = cur_ins.get("pc", "")
                    old_vals[0] = f"▶ {orig_pc}"
                    self.op_tree.item(active_iid, values=old_vals)

            # 3. Add visual pointer & highlight to source line in Code Editor on the left
            if hasattr(self, "code_text"):
                self.code_text.tag_remove("active_exec_line", "1.0", tk.END)
                if cur_ins:
                    src_line = cur_ins.get("src_line")
                    if src_line is not None and src_line > 0:
                        self.code_text.tag_add("active_exec_line", f"{src_line}.0", f"{src_line}.end+1c")
                        self.code_text.see(f"{src_line}.0")
                    elif cur_ins.get("sym_name") in ("_start", "") and pc_idx <= 4:
                        main_idx = self.code_text.search(r"\bmain\s*\(", "1.0", regexp=True)
                        if main_idx:
                            line_main = int(main_idx.split(".")[0])
                            self.code_text.tag_add("active_exec_line", f"{line_main}.0", f"{line_main}.end+1c")
                            self.code_text.see(f"{line_main}.0")
                    elif getattr(self, "current_file_path", "").endswith((".s", ".asm")):
                        line_no = pc_idx + 1
                        self.code_text.tag_add("active_exec_line", f"{line_no}.0", f"{line_no}.end+1c")
                        self.code_text.see(f"{line_no}.0")

            # 4. Status bar telemetry
            if hasattr(self, "status_lbl") and cur_ins:
                pc_str = cur_ins.get("pc", "")
                asm_str = cur_ins.get("asm", "")
                s_line_str = f" • บรรทัดที่ {cur_ins['src_line']}" if cur_ins.get("src_line") else ""
                self.status_lbl.config(
                    text=f"▶ PC: {pc_str} ({asm_str}){s_line_str}   •   รอบคล็อกที่: {getattr(self.sim_engine, 'cycles', 0)}",
                    fg=ACCENT_GREEN
                )

            self._prev_active_pc = pc_idx

    # ==========================================================================
    # EXPORT & HARDWARE UART UPLOAD
    # ==========================================================================
    def _get_active_cpu_hdl_and_mmio(self):
        arch = self.get_current_arch() if hasattr(self, "get_current_arch") else "mips"
        arch_val = self.arch_var.get() if hasattr(self, "arch_var") else ""
        if arch_val.startswith("custom:"):
            c_path = arch_val.split("custom:", 1)[1]
            c_name = os.path.basename(c_path)
        elif arch == "mips":
            c_path = self._get_openmips_hdl_path() if hasattr(self, "_get_openmips_hdl_path") else ""
            c_name = "OpenMIPS 32-bit (Nexys A7)"
        else:
            c_path = self._get_riscv_hdl_path() if hasattr(self, "_get_riscv_hdl_path") else ""
            c_name = "RISC-V RV32IM 32-bit (Nexys A7)"

        mmio_map = {
            "led":       f"0x{getattr(self.sim_engine, 'mmio_led', 0xF0000000):08X}",
            "sw":        f"0x{getattr(self.sim_engine, 'mmio_sw', 0xF0000004):08X}",
            "seg7":      f"0x{getattr(self.sim_engine, 'mmio_seg7', 0xF0000008):08X}",
            "btn":       f"0x{getattr(self.sim_engine, 'mmio_btn', 0xF000000C):08X}",
            "uart_tx":   f"0x{getattr(self.sim_engine, 'mmio_uart', 0xF0000010):08X}",
            "uart_stat": f"0x{getattr(self.sim_engine, 'mmio_uart_stat', 0xF0000014):08X}",
            "rgb":       f"0x{getattr(self.sim_engine, 'mmio_rgb', 0xF0000018):08X}",
            "vga":       f"0x{getattr(self.sim_engine, 'mmio_vga', 0xFF000000):08X}",
        }
        return arch, c_name, c_path, mmio_map

    def export_vivado_soc_dialog(self):
        from tkinter import messagebox
        from core.hdl_generator import export_vivado_soc_package

        if not getattr(self, "compiled_ins", None) and hasattr(self, "_ensure_runnable_software_loaded"):
            self._ensure_runnable_software_loaded()

        chosen = filedialog.askdirectory(
            parent=self,
            initialdir=self.project_dir,
            title="เลือกโฟลเดอร์สำหรับส่งออกชุดโปรเจกต์ Vivado Nexys A7-100T SoC (.v + .xdc + .tcl)",
        )
        if not chosen:
            return

        arch, c_name, c_path, mmio_map = self._get_active_cpu_hdl_and_mmio()
        if os.path.abspath(chosen).lower() == os.path.abspath(self.project_dir).lower():
            out_dir = os.path.join(chosen, f"vivado_nexys_a7_{arch}")
        else:
            out_dir = chosen

        pkg = export_vivado_soc_package(
            out_dir,
            self.compiled_ins,
            arch=arch,
            cpu_hdl_path=c_path,
            mmio_map=mmio_map,
        )
        self.refresh_project_explorer()
        self.status_lbl.config(
            text=f"✅ ส่งออกชุดโปรเจกต์ Vivado SoC ({c_name}) สำเร็จที่: {os.path.basename(pkg['out_dir'])}",
            fg=ACCENT_GREEN,
        )
        messagebox.showinfo(
            "ส่งออกชุดโปรเจกต์ Vivado SoC สำเร็จ",
            f"สร้างชุดสังเคราะห์ฮาร์ดแวร์สำหรับบอร์ด Digilent Nexys A7-100T เรียบร้อยแล้ว:\n"
            f"{pkg['out_dir']}\n\n"
            f"• nexys_a7_soc_top.v (SoC Top + 16KB RAM + MMIO + 7-Seg + PWM RGB)\n"
            f"• uart_prog_loader.v (USB-UART Live Bootloader @ 115200 baud)\n"
            f"• Nexys-A7-100T-Master.xdc (Pin Constraints มาตรฐาน XC7A100T)\n"
            f"• rtl_cpu/ ({len(pkg['copied_rtl'])} ไฟล์ RTL ของ {c_name})\n"
            f"• program.hex, dmem_init.hex, program.coe & build_vivado_project.tcl",
            parent=self,
        )

    def open_rtl_verify_dialog(self):
        from ui.rtl_verify_dialog import RTLVerifyDialog

        if not getattr(self, "compiled_ins", None) and hasattr(self, "_ensure_runnable_software_loaded"):
            self._ensure_runnable_software_loaded()

        arch, c_name, c_path, mmio_map = self._get_active_cpu_hdl_and_mmio()

        def _after_tb_export(pkg):
            self.refresh_project_explorer()
            self.status_lbl.config(
                text=f"✅ ส่งออกชุด RTL Testbench สำเร็จที่: {os.path.basename(pkg['out_dir'])}",
                fg=ACCENT_GREEN,
            )

        RTLVerifyDialog(
            self,
            instructions=self.compiled_ins,
            arch=arch,
            cpu_name=c_name,
            cpu_hdl_path=c_path,
            sw_init=getattr(self.sim_engine, "sw_value", 0),
            btn_init=getattr(self.sim_engine, "btn_value", 0),
            mmio_map=mmio_map,
            project_dir=self.project_dir,
            on_exported=_after_tb_export,
        )

    def open_fpga_programmer_dialog(self):
        from ui.fpga_programmer_dialog import FPGAProgrammerDialog

        if not getattr(self, "compiled_ins", None) and hasattr(self, "_ensure_runnable_software_loaded"):
            self._ensure_runnable_software_loaded()

        arch = self.get_current_arch() if hasattr(self, "get_current_arch") else "openmips"
        arch_val = self.arch_var.get() if hasattr(self, "arch_var") else ""
        custom_cpus = getattr(self, "custom_cpus", [])
        FPGAProgrammerDialog(
            self,
            current_arch=arch,
            active_arch_val=arch_val,
            custom_cpus=custom_cpus,
            project_dir=self.project_dir,
            compiled_ins=getattr(self, "compiled_ins", None),
        )

    def export_file(self, kind):
        if kind == "vivado_soc":
            self.export_vivado_soc_dialog()
            return
        if kind == "vhdl":
            path = filedialog.asksaveasfilename(
                defaultextension=".vhd", initialfile="instruction_memory.vhd",
                initialdir=self.project_dir,
                filetypes=[("VHDL Files", "*.vhd"), ("All Files", "*.*")]
            )
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.last_vhdl)
                self.refresh_project_explorer()
                self.status_lbl.config(text=f"บันทึกไฟล์ VHDL สำเร็จ: {os.path.basename(path)}")
        elif kind == "verilog":
            path = filedialog.asksaveasfilename(
                defaultextension=".v", initialfile="instruction_memory.v",
                initialdir=self.project_dir,
                filetypes=[("Verilog Files", "*.v"), ("All Files", "*.*")]
            )
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.last_verilog)
                self.refresh_project_explorer()
                self.status_lbl.config(text=f"บันทึกไฟล์ Verilog สำเร็จ: {os.path.basename(path)}")
        elif kind == "coe":
            path = filedialog.asksaveasfilename(
                defaultextension=".coe", initialfile="program.coe",
                initialdir=self.project_dir,
                filetypes=[("Vivado COE", "*.coe"), ("All Files", "*.*")]
            )
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.last_coe)
                self.refresh_project_explorer()
                self.status_lbl.config(text=f"บันทึกไฟล์ .COE สำเร็จ: {os.path.basename(path)}")
        elif kind == "bin":
            path = filedialog.asksaveasfilename(
                defaultextension=".txt", initialfile="machine_code_32bit.txt",
                initialdir=self.project_dir,
                filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
            )
            if path:
                lines = [f"{i['pc']} | {i['hex']} | {i['bin']} | {i['asm']} | {i['desc']}" for i in self.compiled_ins]
                with open(path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
                self.refresh_project_explorer()
                self.status_lbl.config(text=f"บันทึกตาราง 32-bit สำเร็จ: {os.path.basename(path)}")

    _cached_ports = []
    _last_ports_scan = 0.0

    @classmethod
    def _detect_serial_ports(cls, force=False):
        """Scan connected USB-UART / COM ports, prioritizing Digilent / FTDI / USB-Serial bridges.
        Uses 1.0s caching to eliminate SetupAPI device enumeration latency on Windows.
        """
        import time
        now = time.time()
        if not force and cls._cached_ports and (now - cls._last_ports_scan < 1.0):
            return cls._cached_ports

        try:
            from serial.tools import list_ports
            raw_ports = list(list_ports.comports())
        except Exception:
            return []

        def _score(p):
            meta = f"{p.description or ''} {p.manufacturer or ''} {p.hwid or ''}".lower()
            if any(k in meta for k in ("digilent", "ftdi", "0403:6010", "nexys")):
                return 0
            if any(k in meta for k in ("usb", "uart", "cp210", "ch340")):
                return 1
            return 2

        raw_ports.sort(key=lambda p: (_score(p), p.device))
        cls._cached_ports = [(p.device, p.description or "Serial Port", p.hwid or "") for p in raw_ports]
        cls._last_ports_scan = now
        return cls._cached_ports

    def _on_com_port_changed(self):
        val = (self.com_port_var.get() or "AUTO").strip()
        disp = "🔌 COM Auto ▾" if val.upper() == "AUTO" else f"🔌 {val} ▾"
        if hasattr(self, "btn_com_port"):
            self.btn_com_port.config(text=disp)
        if hasattr(self, "_save_project_settings"):
            self._save_project_settings()

    def _show_com_port_popup(self):
        from ui.widgets import SpotifyPopupMenu
        m = SpotifyPopupMenu(self, tag="BoardComPortPopup")
        m.add_radiobutton("🔍 Auto-Detect (ค้นหาบอร์ด Nexys A7 อัตโนมัติ)", self.com_port_var, "AUTO", self._on_com_port_changed)
        m.add_separator()
        live_ports = self._detect_serial_ports()
        if live_ports:
            for dev, desc, _ in live_ports:
                short_desc = desc[:36] + ("..." if len(desc) > 36 else "")
                m.add_radiobutton(f"🔌 {dev}  •  {short_desc}", self.com_port_var, dev, self._on_com_port_changed)
        else:
            m.add_command("⚠️ ไม่พบพอร์ต USB-UART ที่เชื่อมต่ออยู่ในขณะนี้", "", None, enabled=False)
        m.show_at_widget(self.btn_com_port)

    def _on_hw_mode_changed(self):
        val = self.hw_exec_mode_var.get()
        if val == "step":
            txt = "🎯 โหมด: Step (หยุดรอ) ▾"
            bg = "#064E3B"
            fg = "#6EE7B7"
        else:
            txt = "🚀 โหมด: Auto-Run (25MHz) ▾"
            bg = "#1E3A8A"
            fg = "#BFDBFE"
        if hasattr(self, "btn_hw_mode"):
            self.btn_hw_mode.config(text=txt, bg=bg, fg=fg, highlightbackground=bg)
        if hasattr(self, "_save_project_settings"):
            self._save_project_settings()

        # Apply the mode to the real board right away, not only at the next
        # upload. Previously this only recoloured the button, so selecting
        # Step while the board was running froze nothing.
        # Silent when no board is attached: this is also a saved preference
        # that can legitimately be set offline.
        try:
            ser = getattr(self, "_hw_serial", None)
            board_reachable = bool(ser is not None and getattr(ser, "is_open", False)) or bool(self._detect_serial_ports())
        except Exception:
            board_reachable = False

        if board_reachable:
            if val == "step":
                self.pause_hardware_board()      # 'P' -> freeze pipeline
            else:
                self.resume_hardware_board()     # 'R' -> free-run 25 MHz

    def _show_hw_mode_popup(self):
        from ui.widgets import SpotifyPopupMenu
        m = SpotifyPopupMenu(self, tag="BoardHwModePopup")
        m.add_radiobutton("🎯 โหมด Step ทีละคำสั่ง (หลังอัปโหลดหยุดรอที่ PC=0 ให้กดก้าวทีละบรรทัด)", self.hw_exec_mode_var, "step", self._on_hw_mode_changed)
        m.add_radiobutton("🚀 โหมด Auto-Run (หลังอัปโหลดรันเต็มสปีด 25 MHz บนบอร์ดจริงทันที)", self.hw_exec_mode_var, "autorun", self._on_hw_mode_changed)
        m.show_at_widget(self.btn_hw_mode)

    def upload_to_board(self):
        if hasattr(self, "compile_now"):
            try:
                self.compile_now(async_bg=False)
            except Exception:
                pass
        if not getattr(self, "compiled_ins", None) and hasattr(self, "_ensure_runnable_software_loaded"):
            self._ensure_runnable_software_loaded()
        if not getattr(self, "compiled_ins", None):
            self.status_lbl.config(text="⚠️ ไม่มีคำสั่งโปรแกรม 32-bit สำหรับอัปโหลดขึ้นบอร์ด", fg=ACCENT_AMBER)
            return

        selected = (self.com_port_var.get() or "AUTO").strip()
        live_ports = self._detect_serial_ports()
        if selected.upper() == "AUTO":
            if not live_ports:
                self.status_lbl.config(
                    text="⚠️ ไม่พบพอร์ต USB-UART ที่เชื่อมต่อ — เสียบสายบอร์ด Nexys A7 หรือกดเมนู File → ส่งออกโปรเจกต์ Vivado SoC",
                    fg=ACCENT_AMBER,
                )
                return
            port = live_ports[0][0]
        else:
            port = selected

        try:
            import time
            import struct

            # Temporarily pause background telemetry while uploading to avoid COM contention
            self._hw_telemetry_active = False

            ser, err = self._get_hw_serial()
            if err or ser is None:
                self.status_lbl.config(
                    text=f"⚠️ {err} — กรุณาตรวจสอบสาย USB-UART หรือเลือกพอร์ตใหม่",
                    fg=ACCENT_AMBER,
                )
                return

            prog_words = []
            for ins in self.compiled_ins:
                prog_words.append(ins.get("word", int(ins["hex"], 16)) & 0xFFFFFFFF)

            cur_arch = self.get_current_arch() if hasattr(self, "get_current_arch") else "mips"
            nop_word = 0x00000013 if cur_arch == "riscv" else 0x00000000
            # Pad with clean NOPs up to at least 1024 words (4KB)
            # This 100% wipes out any leftover instructions from previously uploaded larger programs
            pad_target = max(len(prog_words) + 256, 1024)
            if pad_target > 4096:
                pad_target = 4096
            while len(prog_words) < pad_target:
                prog_words.append(nop_word)

            payload = bytearray(b"PROG")
            payload.extend(struct.pack("<I", len(prog_words)))
            for w in prog_words:
                payload.extend(struct.pack("<I", w))

            init_dmem = self.compiled_ins[0].get("init_dmem", {}) if self.compiled_ins else {}
            dmem_words_sent = 0
            if init_dmem:
                word_map = {((int(k) & 0x3FFF) >> 2): (int(v) & 0xFFFFFFFF) for k, v in init_dmem.items() if 0 <= ((int(k) & 0x3FFF) >> 2) < 4096}
                if word_map:
                    min_idx = min(word_map.keys())
                    max_idx = max(word_map.keys())
                    dmem_words_sent = (max_idx - min_idx) + 1
                    hdr_word = ((min_idx & 0xFFFF) << 16) | (dmem_words_sent & 0xFFFF)
                    payload.extend(b"DMEM")
                    payload.extend(struct.pack("<I", hdr_word))
                    for w_idx in range(min_idx, max_idx + 1):
                        payload.extend(struct.pack("<I", word_map.get(w_idx, 0)))

            ser.reset_input_buffer()
            ser.write(payload)
            ser.flush()
            # Wait for all UART bytes to physically transmit over 115200 baud before issuing CPU run/reset
            time.sleep(len(payload) / 11520.0 + 0.15)

            mode = getattr(self, "hw_exec_mode_var", None)
            is_step = (mode.get() if mode else "step") == "step"

            if is_step:
                # In Step mode: send 'Z' to reset CPU and freeze at PC=0x0000!
                try:
                    ser.write(b"Z")
                    ser.flush()
                    time.sleep(0.05)
                    raw = ser.read(ser.in_waiting or 14)
                    if not self._parse_and_apply_telemetry(raw):
                        raw += ser.read(14)
                        self._parse_and_apply_telemetry(raw)
                except Exception:
                    pass
            else:
                # In Auto-Run mode: send 'R' to run full speed 25MHz immediately!
                try:
                    ser.write(b"R")
                    ser.flush()
                except Exception:
                    pass

            # Resume background telemetry listener
            self._hw_telemetry_active = True
            self.after(50, self._poll_hw_telemetry)

            dmem_msg = f" + ข้อมูล .data/.rodata {dmem_words_sent} คำ" if dmem_words_sent else ""
            if is_step:
                self.status_lbl.config(
                    text=f"✅ อัปโหลด {len(self.compiled_ins)} คำสั่งสำเร็จ! [โหมด Step] ซีพียูหยุดรอที่ PC=0 — กด '⚡ Step บอร์ดจริง' หรือ F11 เพื่อก้าวดูโค้ด",
                    fg=ACCENT_GREEN,
                )
            else:
                self.status_lbl.config(
                    text=f"✅ อัปโหลด {len(self.compiled_ins)} คำสั่งสำเร็จ! [โหมด Auto-Run] ซีพียูรันเต็มสปีด 25 MHz บนบอร์ดจริงเรียบร้อย",
                    fg=ACCENT_GREEN,
                )
        except Exception as e:
            self.status_lbl.config(
                text=f"⚠️ เชื่อมต่อพอร์ต {port} ไม่สำเร็จ ({e}) — กรุณาตรวจสอบสาย USB-UART หรือเลือกพอร์ตใหม่",
                fg=ACCENT_AMBER,
            )

    def _on_sim_speed_changed(self):
        val = self.sim_speed_var.get()
        speed_lbls = {"1Hz": "1 Hz", "5Hz": "5 Hz", "20Hz": "20 Hz", "100Hz": "100 Hz", "max": "Max Speed"}
        display = speed_lbls.get(val, val)
        if hasattr(self, "btn_speed"):
            self.btn_speed.config(text=f"⏱️ {display} ▾")
        if hasattr(self, "_save_project_settings"):
            self._save_project_settings()

    def _show_speed_popup(self):
        from ui.widgets import SpotifyPopupMenu
        m = SpotifyPopupMenu(self, tag="BoardSpeedPopup")
        m.add_radiobutton("🐢 1 Hz (ช้ามาก 1 วิ/คำสั่ง)", self.sim_speed_var, "1Hz", self._on_sim_speed_changed)
        m.add_radiobutton("🚶 5 Hz (ช้า 200ms / กำลังดี)", self.sim_speed_var, "5Hz", self._on_sim_speed_changed)
        m.add_radiobutton("🏃 20 Hz (ปานกลาง 50ms)", self.sim_speed_var, "20Hz", self._on_sim_speed_changed)
        m.add_radiobutton("⚡ 100 Hz (เร็ว 10ms)", self.sim_speed_var, "100Hz", self._on_sim_speed_changed)
        m.add_separator()
        m.add_radiobutton("🚀 Max Speed (เต็มสปีด / ทันที)", self.sim_speed_var, "max", self._on_sim_speed_changed)
        m.show_at_widget(self.btn_speed)

    # ==========================================================================
    # HARDWARE IN-CIRCUIT DEBUGGER (ICD) FOR REAL DIGILENT NEXYS A7 BOARD
    # ==========================================================================
    def _get_hw_serial(self):
        """Returns or opens a dedicated serial connection to Nexys A7 over USB-UART."""
        import serial
        selected = (self.com_port_var.get() or "AUTO").strip()
        live_ports = self._detect_serial_ports()
        if selected.upper() == "AUTO":
            if not live_ports:
                return None, "ไม่พบพอร์ต USB-UART ของบอร์ด Nexys A7 — กรุณาเสียบสาย USB"
            port = live_ports[0][0]
        else:
            port = selected

        # If existing connection is already open on this port, reuse it
        cur_ser = getattr(self, "_hw_serial", None)
        if cur_ser is not None:
            if getattr(cur_ser, "is_open", False) and getattr(cur_ser, "port", "") == port:
                return cur_ser, None
            try:
                cur_ser.close()
            except Exception:
                pass
            self._hw_serial = None

        try:
            self._hw_serial = serial.Serial(port, 115200, timeout=0.2, write_timeout=1)
            time.sleep(0.05)
            # Start telemetry background listener if not already active
            if not getattr(self, "_hw_telemetry_active", False):
                self._hw_telemetry_active = True
                self.after(50, self._poll_hw_telemetry)
            return self._hw_serial, None
        except Exception as e:
            return None, f"ไม่สามารถเปิดพอร์ต {port}: {e}"

    def _update_hardware_active_pc(self, pc_byte, ins_val=0, led_val=0, seg7_val=0):
        """Synchronizes computer IDE pointer, source line highlight, LEDs, and 7-segment display with real FPGA."""
        pc_idx = (pc_byte & 0xFFFF) >> 2
        compiled = getattr(self, "compiled_ins", [])
        prev_pc = getattr(self, "_prev_active_pc", None)

        # 1. Clear previous pointer in Opcode Table
        if prev_pc is not None and prev_pc != pc_idx:
            prev_iid = str(prev_pc)
            if hasattr(self, "op_tree") and self.op_tree.exists(prev_iid):
                tag = "even" if prev_pc % 2 == 0 else "odd"
                self.op_tree.item(prev_iid, tags=(tag,))
                if prev_pc < len(compiled):
                    orig_pc = compiled[prev_pc].get("pc", "")
                    old_vals = list(self.op_tree.item(prev_iid, "values"))
                    if old_vals:
                        old_vals[0] = orig_pc
                        self.op_tree.item(prev_iid, values=old_vals)

        # 2. Add visual pointer ▶ to Opcode Table on the right
        active_iid = str(pc_idx)
        cur_ins = compiled[pc_idx] if (pc_idx < len(compiled)) else None
        if hasattr(self, "op_tree") and self.op_tree.exists(active_iid):
            self.op_tree.item(active_iid, tags=("active_pc",))
            self.op_tree.see(active_iid)
            old_vals = list(self.op_tree.item(active_iid, "values"))
            if old_vals and cur_ins:
                orig_pc = cur_ins.get("pc", "")
                old_vals[0] = f"▶ {orig_pc}"
                self.op_tree.item(active_iid, values=old_vals)

        # 3. Add visual pointer & highlight to source line in Code Editor on the left
        if hasattr(self, "code_text"):
            self.code_text.tag_remove("active_exec_line", "1.0", tk.END)
            if cur_ins:
                src_line = cur_ins.get("src_line")
                if src_line is not None and src_line > 0:
                    self.code_text.tag_add("active_exec_line", f"{src_line}.0", f"{src_line}.end+1c")
                    self.code_text.see(f"{src_line}.0")
                elif cur_ins.get("sym_name") in ("_start", "") and pc_idx <= 4:
                    # Bootstrap CRT instructions (_start: lui $sp, jal main) -> point to main() in C code!
                    main_idx = self.code_text.search(r"\bmain\s*\(", "1.0", regexp=True)
                    if main_idx:
                        line_main = int(main_idx.split(".")[0])
                        self.code_text.tag_add("active_exec_line", f"{line_main}.0", f"{line_main}.end+1c")
                        self.code_text.see(f"{line_main}.0")
                elif getattr(self, "current_file_path", "").endswith((".s", ".asm")):
                    line_no = pc_idx + 1
                    self.code_text.tag_add("active_exec_line", f"{line_no}.0", f"{line_no}.end+1c")
                    self.code_text.see(f"{line_no}.0")

        # 4. Sync Virtual Nexys A7 Hardware Display with Real Hardware
        if hasattr(self, "sim_engine"):
            self.sim_engine.led_value = led_val & 0xFFFF
            self.sim_engine.seg7_value = seg7_val & 0xFFFFFFFF
            self.sim_engine.pc_index = pc_idx
        if hasattr(self, "_refresh_board_widgets"):
            self._refresh_board_widgets()

        # 5. Status bar telemetry
        if hasattr(self, "status_lbl"):
            asm_str = cur_ins.get("asm", "") if cur_ins else f"0x{ins_val:08X}"
            if cur_ins and cur_ins.get("src_line"):
                s_line = f" • บรรทัดที่ {cur_ins['src_line']}"
            elif pc_idx <= 4:
                s_line = " • เริ่มระบบ (Bootstrap: lui $sp / jal main)"
            else:
                s_line = ""
            self.status_lbl.config(
                text=f"⚡ [บอร์ดจริง Nexys A7] PC: 0x{pc_byte:04X} ({asm_str}){s_line}  |  LED: 0x{led_val:04X} ({led_val})  |  7-SEG: 0x{seg7_val:08X}",
                fg="#38EF7D"
            )

        self._prev_active_pc = pc_idx

    def _parse_and_apply_telemetry(self, raw):
        """Extracts 14-byte packet [0xA5, 0x5A, PC(2), INS(4), LED(2), SEG(4)]."""
        if len(raw) < 14:
            return False
        # Search for magic header 0xA5 0x5A
        idx = raw.find(b"\xA5\x5A")
        if idx >= 0 and len(raw) >= idx + 14:
            pkt = raw[idx:idx+14]
            pc_val, ins_val, led_val, seg7_val = struct.unpack(">HIHI", pkt[2:14])
            self._update_hardware_active_pc(pc_val, ins_val, led_val, seg7_val)
            return True
        return False

    def step_hardware_board(self):
        """Sends 'S' to real Nexys A7 FPGA over USB-UART to execute 1 clock cycle / instruction."""
        if not getattr(self, "compiled_ins", None) and hasattr(self, "_ensure_runnable_software_loaded"):
            self._ensure_runnable_software_loaded()

        ser, err = self._get_hw_serial()
        if not ser:
            if hasattr(self, "status_lbl"):
                self.status_lbl.config(text=f"⚠️ {err}", fg=ACCENT_AMBER)
            return

        try:
            ser.reset_input_buffer()
            ser.write(b"S")
            ser.flush()
            time.sleep(0.015)
            # Read 14-byte packet returned by FPGA
            raw = ser.read(ser.in_waiting or 14)
            if not self._parse_and_apply_telemetry(raw):
                # Try reading once more with slight wait if FPGA UART transmitter was framing
                raw += ser.read(14)
                if not self._parse_and_apply_telemetry(raw):
                    if hasattr(self, "status_lbl"):
                        self.status_lbl.config(text="⚠️ บอร์ดไม่ส่ง telemetry กลับมา — กรุณาแฟลช Bitstream ที่มี Hardware ICD", fg=ACCENT_AMBER)
        except Exception as e:
            if hasattr(self, "status_lbl"):
                self.status_lbl.config(text=f"⚠️ สื่อสารกับบอร์ดล้มเหลว: {e}", fg=ACCENT_AMBER)

    def pause_hardware_board(self):
        """Sends 'P' to freeze the OpenMIPS CPU pipeline synchronously and capture state."""
        ser, err = self._get_hw_serial()
        if not ser:
            if hasattr(self, "status_lbl"):
                self.status_lbl.config(text=f"⚠️ {err}", fg=ACCENT_AMBER)
            return

        try:
            ser.reset_input_buffer()
            ser.write(b"P")
            ser.flush()
            raw = ser.read(14)
            self._parse_and_apply_telemetry(raw)
            if hasattr(self, "status_lbl"):
                cur_text = self.status_lbl.cget("text")
                self.status_lbl.config(text=f"⏸ [หยุดบอร์ดจริง] {cur_text}", fg="#FED7AA")
        except Exception as e:
            if hasattr(self, "status_lbl"):
                self.status_lbl.config(text=f"⚠️ สื่อสารกับบอร์ดล้มเหลว: {e}", fg=ACCENT_AMBER)

    def resume_hardware_board(self):
        """Sends 'R' to resume full 25MHz hardware execution on Nexys A7."""
        ser, err = self._get_hw_serial()
        if not ser:
            if hasattr(self, "status_lbl"):
                self.status_lbl.config(text=f"⚠️ {err}", fg=ACCENT_AMBER)
            return

        try:
            ser.write(b"R")
            ser.flush()
            if hasattr(self, "status_lbl"):
                self.status_lbl.config(text="▶ [บอร์ดจริงกำลังรัน 25MHz] กำลังประมวลผลเต็มสปีดบนชิป Artix-7 (กด '⏸ หยุดบอร์ด' หรือ '⚡ Step บอร์ดจริง' เพื่อตรวจเช็ค)", fg=ACCENT_GREEN)
        except Exception as e:
            if hasattr(self, "status_lbl"):
                self.status_lbl.config(text=f"⚠️ สื่อสารกับบอร์ดล้มเหลว: {e}", fg=ACCENT_AMBER)

    def reset_hardware_board(self):
        """Sends 'Z' to reset CPU on Nexys A7 and freeze at PC=0x0000 with telemetry."""
        ser, err = self._get_hw_serial()
        if not ser:
            if hasattr(self, "status_lbl"):
                self.status_lbl.config(text=f"⚠️ {err}", fg=ACCENT_AMBER)
            return

        try:
            ser.reset_input_buffer()
            ser.write(b"Z")
            ser.flush()
            time.sleep(0.02)
            raw = ser.read(14)
            if self._parse_and_apply_telemetry(raw):
                if hasattr(self, "status_lbl"):
                    self.status_lbl.config(text="🔄 [รีเซ็ตบอร์ดจริง] ซีพียูถูกรีเซ็ตกลับมาที่คำสั่งแรก (PC: 0x0000) พร้อมให้กด Step", fg=ACCENT_GREEN)
            else:
                raw += ser.read(14)
                self._parse_and_apply_telemetry(raw)
        except Exception as e:
            if hasattr(self, "status_lbl"):
                self.status_lbl.config(text=f"⚠️ สื่อสารกับบอร์ดล้มเหลว: {e}", fg=ACCENT_AMBER)

    def _poll_hw_telemetry(self):
        """Periodic background check for telemetry from hardware (e.g. when physical BTNC button is pressed)."""
        if not getattr(self, "_hw_telemetry_active", False):
            return

        ser = getattr(self, "_hw_serial", None)
        if ser is not None and getattr(ser, "is_open", False):
            try:
                waiting = ser.in_waiting
                if waiting >= 14:
                    raw = ser.read(waiting)
                    self._parse_and_apply_telemetry(raw)
            except Exception:
                pass

        # Schedule next poll in 50ms
        self.after(50, self._poll_hw_telemetry)
