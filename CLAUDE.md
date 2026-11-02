# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

FPGA Studio is a zero-dependency, offline desktop IDE (Tkinter, Windows) for designing, compiling, simulating, synthesizing, and flashing 32-bit CPU systems (OpenMIPS and RISC-V RV32IM) targeting the Digilent Nexys A7-100T FPGA board. It bundles real GCC cross-toolchains, a cycle-accurate pipeline simulator, an interactive virtual board, and a path to real hardware via WSL-based open-source synthesis (Yosys/nextpnr) or Vivado.

The canonical deep-dive reference is `FPGA_Studio_System_Architecture_and_Features_Guide.md` (Thai-language developer manual) — read the relevant numbered section there before making non-trivial changes to pipeline, compiler, HDL generation, or synthesis code. `PROJECT_DEV_LOG.md` is a chronological run log of past investigations/fixes; check it for prior context before re-debugging something that looks already solved.

## Commands

Run from the `fpga-studio/` directory (no `requirements.txt`; the only runtime dependency beyond stdlib is `pyserial`):

```bash
pip install pyserial
python vscode_app.py        # launch the IDE (main.py is a thin wrapper that calls vscode_app.main())
```

Tests (pytest, no config file — just point at the `tests/` directory):

```bash
pytest tests/                                   # full suite (excludes tests/legacy, which is ad hoc scratch scripts, not a suite)
pytest tests/test_isa_and_sim.py                # one file
pytest tests/test_isa_and_sim.py::test_signed_comparisons_and_slti   # one test
```

Tests compile real C through the bundled GCC toolchains and run the result on both the MIPS and RISC-V simulators, so they are slower than unit tests and depend on the bundled `toolchain/` GCC binaries being present (not in git — see `.gitignore`; obtained via the installer/setup, not `pip`).

Packaging (not needed for day-to-day development):
```bash
pyinstaller "FPGA Studio.spec"     # produces FPGA Studio.exe (bundles core/fpga_engine_rust.dll, toolchain/, custom_cpus/, bitstreams/, fonts/)
# then installer.iss (Inno Setup 6) wraps that into FPGA_Studio_Setup_v4.2.exe
```

Cloud bitstream synthesis is a manually-dispatched GitHub Actions workflow (`.github/workflows/fpga_studio_synthesis.yml`), not something run locally in a dev loop — it spins up the `regymm/openxc7` Docker image and runs Yosys → nextpnr-xilinx → fasm2frames → xc7frames2bit against `build_soc_<cpu_name>/`.

## Architecture

### Layering
```
config/   theme.py (UI colors/fonts), catalog.py (ROOT_DIR, paths, starter templates, ISA reference tables)
core/     compiler/assembler/disassembler/transpiler, simulator engine, HDL generation, synthesis, programmer
ui/       Tkinter widgets, board view, dialogs, main studio_window.py
app.py    backward-compat facade re-exporting core/config symbols (don't add new logic here)
vscode_app.py  real entry point — sets Windows DPI awareness, then builds ui.VSCodeFPGAStudio
```
`core/__init__.py` is the package's public API surface — when adding a new core module, export its public functions there (and in `app.py`'s facade if it needs backward-compat access) rather than having `ui/` import deep submodules directly.

### Two CPU architectures, one simulator, one MMIO map
OpenMIPS (5-stage, big-endian, branch delay slots, hardware mul/div) and RISC-V RV32IM (5-stage, little-endian, M-extension, branch flush instead of delay slots) are both driven through `core/simulator_engine.py::CPUSimulatorEngine`. Instructions are pre-decoded once into `(op, rd, rs, rt, imm, shamt)` tuples before the run loop, not re-parsed per cycle — preserve that if touching the hot path. `core/rust_accel.py` + `core/fpga_engine_rust.dll` is an optional ctypes/C-ABI accelerated backend for the same simulation semantics (50–100x); any behavioral change to the Python simulator's instruction semantics needs the equivalent change to stay compatible with the Rust engine, or results silently diverge between the two backends.

Both CPUs' Verilog RTL lives under `custom_cpus/<cpu_name>/` and must match the behavior of the Python/Rust simulators — the simulator is the fast iteration loop, the RTL is what actually gets synthesized, and `core/rtl_cosim.py` (Icarus Verilog co-simulation) is the tool that checks they agree.

MMIO is one flat address map shared by hardware, RTL, and both simulator backends — changing it means touching all three:
| Address | Device |
|---|---|
| `0x0000_0000–0x0000_7FFF` | Instruction ROM (RO) |
| `0x8000_0000–0x8000_FFFF` | Data RAM (.data/.bss/heap/stack) |
| `0xF000_0000` | 16 LEDs (RW) |
| `0xF000_0004` | 16 Slide switches (RO) |
| `0xF000_0008` | 8-digit 7-segment (RW) |
| `0xF000_000C` | 5 pushbuttons + reset (RO) |
| `0xF000_0010` | UART TX/RX data |
| `0xF000_0014` | UART status (bit0 RX ready, bit1 TX ready) |
| `0xF000_0018` | 2 RGB LEDs (PWM) |
| `0xFF00_0000–0xFF04_AFFF` | VGA framebuffer (640x480) |

(`ADDRESS_AND_PINOUT_GUIDE.md` additionally maps each MMIO bit to its physical Nexys A7 FPGA pin — needed when generating/checking constraints, not needed for simulator-only changes.)

### Compile → simulate → synthesize → flash pipeline
1. **Compile**: user source (C/C++/ASM/Python/Rust subset) goes through `core/gcc_toolchain.py` (bundled real `mips64-elf-gcc` / `riscv-none-elf-gcc`, with an in-memory LRU cache keyed on source) or `core/transpiler.py` (Python/Rust → C) or `core/assembler.py` (direct ASM). A startup routine (`start.S`) and linker script are generated automatically; output `.data` is extracted and word-aligned for BRAM init.
2. **Simulate**: `core/simulator_engine.py` runs the decoded instructions, routes `SW`/`SB`/`LW`/`LB` through the MMIO map above, and drives `ui/board_panels.py`'s virtual board live.
3. **Hardware generation**: `core/hdl_generator.py` builds ROM/RAM init (VHDL, Verilog, Vivado `.coe`) and the full `nexys_a7_soc_top.v` + Vivado SoC package; `core/hdl_analyzer.py` is a Verilog/VHDL AST parser used to auto-inspect *user-imported* custom CPU cores (classifies standalone-ALU vs SoC CPU, detects `clk`/`rst`/`addr`/`din`/`dout`/`we`-style ports) and binds them to board peripherals via `cpu_manifest.json` — this is the extension point for adding a new CPU architecture (add `custom_cpus/<name>/`, write its `cpu_manifest.json`, add disassembly support in `core/disassembler.py`, add a UI entry in `ui/studio_window.py`).
4. **Synthesize**: either `core/wsl_synthesis.py` (local, offline, Yosys + nextpnr-xilinx inside WSL — no Vivado needed) or Vivado CLI batch mode, or the GitHub Actions cloud workflow described above.
5. **Flash**: `core/fpga_programmer.py` auto-detects and drives `openFPGALoader`, Digilent Adept (`djtgcfg`), or Vivado CLI over JTAG. `uart_prog_loader.v` is a separate fast path: it lets already-synthesized hardware reload new program binaries into Block RAM over USB-UART in ~1s without re-synthesizing a bitstream.

### Workspace vs. repo root
`workspace/` holds user project state and is partially git-ignored (`workspace/*/build_soc_*`, `workspace/*/bitstreams/`, `workspace/*/custom_cpus/`, etc. are generated/duplicated content, not source). `build_soc_openmips/` at repo root is a prebuilt SoC package directory consumed by the cloud synthesis workflow.
