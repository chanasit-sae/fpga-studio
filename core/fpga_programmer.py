# -*- coding: utf-8 -*-
"""
FPGA Studio — Direct Hardware Bitstream Programmer & JTAG Manager
Enables 1-click flashing of synthesizable CPU bitstreams (.bit) directly to
FPGA boards (Digilent Nexys A7-100T, Virtex-6, Basys 3, etc.) without requiring
the user to manually operate the Xilinx Vivado GUI.

Supported JTAG Programmers:
  1. Xilinx Vivado CLI (`vivado -mode batch -source ...`)
  2. Xilinx Vivado Lab Edition (`vivado_lab -mode batch -source ...`)
  3. Digilent Adept CLI (`djtgcfg prog ...`)
  4. openFPGALoader (`openFPGALoader -b nexysA7 ...`)
  5. Built-in USB-UART Instruction Memory Loader (High-speed 115200 baud)
"""

import glob
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from typing import Callable, Dict, List, Optional, Tuple



def _app_toolchain_roots():
    """Folders that may contain the bundled toolchain/ directory.

    When frozen, sys._MEIPASS points at _internal/, which does NOT hold the
    toolchain -- the installer places it next to the .exe. So the real
    application folder must be searched too.
    """
    roots = [os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
    if getattr(sys, "frozen", False):
        roots.append(os.path.dirname(sys.executable))
    try:
        from config.catalog import ROOT_DIR as _root_dir
        if _root_dir:
            roots.append(_root_dir)
    except Exception:
        pass
    seen, out = set(), []
    for r in roots:
        if r and r not in seen:
            seen.add(r)
            out.append(r)
    return out

def find_vivado_binary() -> Optional[str]:
    """Search system PATH and standard drive locations for Vivado or Vivado Lab executable."""
    for bin_name in ("vivado.bat", "vivado_lab.bat", "vivado", "vivado_lab"):
        found = shutil.which(bin_name)
        if found and os.path.isfile(found):
            return found

    # Search standard Windows install roots
    search_patterns = [
        r"C:\Xilinx\Vivado\*\bin\vivado.bat",
        r"C:\Xilinx\Vivado_Lab\*\bin\vivado_lab.bat",
        r"D:\Xilinx\Vivado\*\bin\vivado.bat",
        r"D:\Xilinx\Vivado_Lab\*\bin\vivado_lab.bat",
        r"E:\Xilinx\Vivado\*\bin\vivado.bat",
        r"C:\tools\Xilinx\Vivado\*\bin\vivado.bat",
        r"D:\tools\Xilinx\Vivado\*\bin\vivado.bat",
    ]
    for pattern in search_patterns:
        matches = glob.glob(pattern)
        if matches:
            # Sort descending to pick latest version (e.g. 2024.1 > 2022.2)
            matches.sort(reverse=True)
            return matches[0]

    return None


def find_djtgcfg_binary() -> Optional[str]:
    """Search for Digilent Adept djtgcfg CLI tool."""
    found = shutil.which("djtgcfg") or shutil.which("djtgcfg.exe")
    if found and os.path.isfile(found):
        return found

    std_paths = [
        r"C:\Program Files (x86)\Digilent\AdeptUtilities\djtgcfg.exe",
        r"C:\Program Files\Digilent\AdeptUtilities\djtgcfg.exe",
        r"D:\Program Files (x86)\Digilent\AdeptUtilities\djtgcfg.exe",
        r"D:\Program Files\Digilent\AdeptUtilities\djtgcfg.exe",
    ]
    for p in std_paths:
        if os.path.isfile(p):
            return p
    return None


def find_openfpgaloader_binary(toolchain_dir: Optional[str] = None) -> Optional[str]:
    """Search for bundled or system openFPGALoader binary."""
    # 1. System PATH
    found = shutil.which("openFPGALoader") or shutil.which("openFPGALoader.exe")
    if found and os.path.isfile(found):
        return found

    # 2. PyInstaller bundled temporary dir (_MEIPASS)
    if hasattr(sys, "_MEIPASS"):
        meipass_cands = [
            os.path.join(sys._MEIPASS, "toolchain", "openFPGALoader", "openFPGALoader.exe"),
            os.path.join(sys._MEIPASS, "toolchain", "openFPGALoader.exe"),
        ]
        for c in meipass_cands:
            if os.path.isfile(c):
                return c

    # 3. Passed toolchain directory
    if toolchain_dir:
        cand_list = [
            os.path.join(toolchain_dir, "openFPGALoader", "openFPGALoader.exe"),
            os.path.join(toolchain_dir, "openFPGALoader.exe"),
            os.path.join(toolchain_dir, "bin", "openFPGALoader.exe"),
        ]
        for c in cand_list:
            if os.path.isfile(c):
                return c

    # 4. App relative directory
    fallback_cands = []
    for app_root in _app_toolchain_roots():
        fallback_cands.extend([
            os.path.join(app_root, "toolchain", "openFPGALoader", "openFPGALoader.exe"),
            os.path.join(app_root, "toolchain", "openFPGALoader.exe"),
        ])
    for c in fallback_cands:
        if os.path.isfile(c):
            return c

    return None


def map_board_to_openfpgaloader_target(board_name: str) -> str:
    """Map human-friendly board names to openFPGALoader board target strings."""
    b = (board_name or "").lower()
    if "50t" in b or "nexys_a7_50" in b:
        return "nexys_a7_50"
    if "basys" in b or "basys3" in b:
        return "basys3"
    if "arty" in b:
        return "arty_a7_100t" if "100" in b else "arty_a7_35t"
    # Default to Nexys A7-100T (Artix-7 xc7a100tcsg324)
    return "nexys_a7_100"


def detect_all_fpga_programmers(toolchain_dir: Optional[str] = None) -> Dict[str, Optional[str]]:
    """Scan and return status of all supported hardware programmer backends."""
    return {
        "vivado": find_vivado_binary(),
        "djtgcfg": find_djtgcfg_binary(),
        "openfpgaloader": find_openfpgaloader_binary(toolchain_dir),
    }


def generate_vivado_program_tcl(bitstream_path: str, device_hint: str = "xc7a100t") -> str:
    """Generate Vivado Tcl script to connect to JTAG and program device."""
    safe_bit = bitstream_path.replace("\\", "/")
    return f"""# ==============================================================================
# FPGA Studio — Direct JTAG In-App Programmer Script
# ==============================================================================
set bitfile "{safe_bit}"

if {{![file exists $bitfile]}} {{
    puts "ERROR: Bitstream file does not exist: $bitfile"
    exit 1
}}

puts "=================================================================="
puts "FPGA Studio: Connecting to Hardware Server..."
puts "=================================================================="
open_hw_manager
connect_hw_server -allow_non_jtag

set targets [get_hw_targets]
if {{[llength $targets] == 0}} {{
    puts "ERROR: No JTAG targets found. Please check board USB cable."
    disconnect_hw_server
    close_hw_manager
    exit 2
}}

open_hw_target
set devices [get_hw_devices]
if {{[llength $devices] == 0}} {{
    puts "ERROR: No FPGA devices detected on JTAG chain."
    close_hw_target
    disconnect_hw_server
    close_hw_manager
    exit 3
}}

set target_dev [lindex $devices 0]
foreach d $devices {{
    if {{[string match "*{device_hint}*" $d]}} {{
        set target_dev $d
        break
    }}
}}

current_hw_device $target_dev
refresh_hw_device -update_hw_probes false $target_dev

puts "=================================================================="
puts "FPGA Studio: Programming Device $target_dev with $bitfile..."
puts "=================================================================="
set_property PROGRAM.FILE $bitfile $target_dev
program_hw_devices $target_dev

refresh_hw_device $target_dev
close_hw_target
disconnect_hw_server
close_hw_manager

puts "=================================================================="
puts "FPGA_STUDIO_FLASH_SUCCESS: Device programmed successfully!"
puts "=================================================================="
exit 0
"""


def program_fpga_with_vivado(
    vivado_path: str,
    bitstream_path: str,
    device_hint: str = "xc7a100t",
    on_log: Optional[Callable[[str], None]] = None,
) -> Tuple[bool, str]:
    """Execute Vivado in batch mode to flash bitstream via JTAG."""
    if not os.path.isfile(bitstream_path):
        return False, f"ไม่พบไฟล์ Bitstream ที่ระบุ: {bitstream_path}"

    with tempfile.TemporaryDirectory(prefix="fpga_prog_") as tmpdir:
        tcl_script = os.path.join(tmpdir, "program_fpga.tcl")
        with open(tcl_script, "w", encoding="utf-8") as f:
            f.write(generate_vivado_program_tcl(bitstream_path, device_hint))

        cmd = [vivado_path, "-mode", "batch", "-nojournal", "-nolog", "-source", tcl_script]
        if on_log:
            on_log(f"⚡ กำลังเริ่มรันตัวโปรแกรมเมอร์ Vivado: {' '.join(cmd)}\n")

        try:
            p = subprocess.Popen(
                cmd,
                cwd=tmpdir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            full_logs = []
            for line in p.stdout:
                clean_line = line.strip()
                full_logs.append(clean_line)
                if on_log and clean_line:
                    on_log(clean_line)
            p.wait()

            log_text = "\n".join(full_logs)
            if p.returncode == 0 or "FPGA_STUDIO_FLASH_SUCCESS" in log_text:
                return True, "แฟลช CPU Bitstream ลงบอร์ด FPGA สำเร็จเรียบร้อย! (DONE LED ติดสว่าง)"
            return False, f"การแฟลชล้มเหลว (รหัสคืนค่า {p.returncode}):\n{log_text[-500:]}"
        except Exception as ex:
            return False, f"เกิดข้อผิดพลาดในการรัน Vivado: {ex}"


def program_fpga_with_djtgcfg(
    djtgcfg_path: str,
    bitstream_path: str,
    device_name: str = "NexysA7",
    on_log: Optional[Callable[[str], None]] = None,
) -> Tuple[bool, str]:
    """Execute Digilent Adept djtgcfg CLI to program device."""
    if not os.path.isfile(bitstream_path):
        return False, f"ไม่พบไฟล์ Bitstream: {bitstream_path}"

    cmd = [djtgcfg_path, "prog", "-d", device_name, "-i", "0", "-f", bitstream_path]
    if on_log:
        on_log(f"⚡ รัน Digilent Adept Programmer: {' '.join(cmd)}\n")

    try:
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        logs = []
        for line in p.stdout:
            c = line.strip()
            logs.append(c)
            if on_log and c:
                on_log(c)
        p.wait()
        log_text = "\n".join(logs)
        if p.returncode == 0 and "Programming succeeded" in log_text:
            return True, "แฟลช CPU ด้วย Digilent Adept สำเร็จเรียบร้อย!"
        return False, f"Digilent Adept รายงานข้อผิดพลาด:\n{log_text}"
    except Exception as ex:
        return False, f"เกิดข้อผิดพลาดในการรัน djtgcfg: {ex}"


def program_fpga_with_openfpgaloader(
    loader_path: str,
    bitstream_path: str,
    board: str = "nexys_a7_100",
    on_log: Optional[Callable[[str], None]] = None,
) -> Tuple[bool, str]:
    """Execute openFPGALoader to flash bitstream directly into FPGA via USB-JTAG."""
    if not os.path.isfile(bitstream_path):
        return False, f"ไม่พบไฟล์ Bitstream: {bitstream_path}"

    target_board = map_board_to_openfpgaloader_target(board)
    # Detect connected Digilent FTDI serial number to ensure 100% reliable USB binding on Windows
    serial_num = None
    try:
        proc = subprocess.run([loader_path, "--scan-usb"], capture_output=True, text=True, timeout=3)
        for line in proc.stdout.splitlines():
            if "0x0403:0x6010" in line or "Digilent" in line:
                parts = line.split()
                if len(parts) >= 6:
                    serial_num = parts[5]
                    break
    except Exception:
        pass

    cmd = [loader_path, "-c", "digilent"]
    if serial_num:
        cmd.extend(["--usb-serial-num", serial_num])
    cmd.extend(["-m", bitstream_path])
    if on_log:
        on_log(f"⚡ รัน openFPGALoader (บอร์ด: {target_board}): {' '.join(cmd)}\n")

    # Ensure DLL folder is in PATH environment for child process
    env = os.environ.copy()
    loader_dir = os.path.dirname(os.path.abspath(loader_path))
    env["PATH"] = loader_dir + os.pathsep + env.get("PATH", "")

    try:
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        logs = []
        for line in p.stdout:
            c = line.strip()
            logs.append(c)
            if on_log and c:
                on_log(c)
        p.wait()
        log_text = "\n".join(logs)
        if p.returncode == 0:
            return True, "แฟลช CPU ด้วย openFPGALoader สำเร็จเรียบร้อย! (ไฟ DONE LED ติดสว่าง)"
        return False, f"openFPGALoader รายงานข้อผิดพลาด:\n{log_text}"
    except Exception as ex:
        return False, f"เกิดข้อผิดพลาดในการรัน openFPGALoader: {ex}"
