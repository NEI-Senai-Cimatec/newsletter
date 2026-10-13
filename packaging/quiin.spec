# packaging/quiin.spec
"""PyInstaller onedir build for the portable QuIIN folder."""
import sys
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    copy_metadata,
)

ROOT = Path(SPECPATH).resolve().parent

datas = [(str(ROOT / "template"), "template")]
datas += collect_data_files("customtkinter")
datas += copy_metadata("webdriver-manager")

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=collect_submodules("webdriver_manager"),
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "coverage", "_pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="QuIIN",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="QuIIN",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="QuIIN.app",
        icon=None,
        bundle_identifier="br.org.senai.cimatec.quiin",
    )
