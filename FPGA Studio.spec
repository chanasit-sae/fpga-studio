# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['vscode_app.py'],
    pathex=[],
    binaries=[
        ('core/fpga_engine_rust.dll', '.'),
        ('core/fpga_engine_rust.dll', 'core'),
    ],
    datas=[
        ('core/fpga_engine_rust.dll', 'core'),
        ('custom_cpus/openmips', 'custom_cpus/openmips'),
        ('custom_cpus/riscv', 'custom_cpus/riscv'),
        ('bitstreams', 'bitstreams'),
    ],
    hiddenimports=[
        'serial',
        'serial.tools',
        'serial.tools.list_ports',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FPGA Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app_icon.ico'],
    version='version_info.txt',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FPGA Studio',
)
