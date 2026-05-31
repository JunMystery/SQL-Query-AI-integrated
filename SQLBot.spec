# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs


block_cipher = None
project_root = Path(SPECPATH)
datas = [
    (str(project_root / "resources"), "resources"),
]
datas += collect_data_files("llama_cpp")

binaries = []
binaries += collect_dynamic_libs("llama_cpp")
from PySide6.QtCore import QLibraryInfo

pyside_plugins = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))
for plugin_group in ["platforms", "styles", "imageformats", "iconengines"]:
    plugin_dir = pyside_plugins / plugin_group
    if plugin_dir.exists():
        for plugin_file in plugin_dir.iterdir():
            if plugin_file.is_file():
                binaries.append((str(plugin_file), f"PySide6/plugins/{plugin_group}"))

hiddenimports = [
    "sqlalchemy",
    "sqlalchemy.dialects.mysql.pymysql",
    "sqlalchemy.dialects.postgresql.psycopg",
    "pymysql",
    "psycopg",
    "psycopg_binary",
    "llama_cpp",
]
hiddenimports += collect_submodules("sqlbot_desktop")
hiddenimports += collect_submodules("pymysql")
hiddenimports += collect_submodules("psycopg")

a = Analysis(
    ["run.py"],
    pathex=[str(project_root / "src"), str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SQLBot",
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SQLBot",
)
