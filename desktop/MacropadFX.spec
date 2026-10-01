# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec del configurador MacropadFX (one-dir, sin consola).

Compilar:  python -m PyInstaller --noconfirm --clean MacropadFX.spec
(o usar build.ps1, que ademas genera el icono).

Salida:    dist\\MacropadFX\\MacropadFX.exe   (carpeta onedir con _internal\\)
"""

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []

# uvicorn carga loops/protocolos dinamicamente -> hay que traerlos todos.
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("fastapi")
hiddenimports += collect_submodules("starlette")
hiddenimports += collect_submodules("anyio")
hiddenimports += collect_submodules("bleak")

# pystray: solo el backend de Windows (los otros son de Linux/macOS).
hiddenimports += collect_submodules(
    "pystray",
    filter=lambda name: not any(
        b in name for b in ("_xorg", "_gtk", "_darwin", "_appindicator", "_dummy")
    ),
)

# winrt no es detectable estaticamente (namespace package con .pyd por modulo).
hiddenimports += [
    "winrt.system",
    "winrt.windows.devices.bluetooth",
    "winrt.windows.devices.bluetooth.advertisement",
    "winrt.windows.devices.bluetooth.genericattributeprofile",
    "winrt.windows.devices.enumeration",
    "winrt.windows.devices.radios",
    "winrt.windows.foundation",
    "winrt.windows.foundation.collections",
    "winrt.windows.storage.streams",
]

# Dependencias sueltas que se importan de forma dinamica.
hiddenimports += ["h11", "sniffio"]

datas = [
    ("static", "static"),
    ("icon.ico", "."),
]

a = Analysis(
    ["tray.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MacropadFX",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="icon.ico",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MacropadFX",
)
