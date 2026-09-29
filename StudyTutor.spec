# -*- mode: python ; coding: utf-8 -*-
"""Windows build for MBA Study Tutor.

Produces dist/MBAStudyTutor/MBAStudyTutor.exe. The window has no console.
Check it with: MBAStudyTutor.exe --self-check dist\\self-check.txt
"""

from PyInstaller.utils.hooks import collect_submodules

hidden = collect_submodules("keyring")
hidden += [
    name
    for name in collect_submodules("google.genai")
    if ".tests" not in name and not name.endswith(".tests")
]
hidden += [
    "win32cred",
    "win32api",
    "win32timezone",
    "pywintypes",
    "pythoncom",
    "certifi",
]

a = Analysis(
    ["run_app.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "google.genai.tests"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MBAStudyTutor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MBAStudyTutor",
)
