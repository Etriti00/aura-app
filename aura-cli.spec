# Aura CLI (headless) — PyInstaller spec for servers, VPS, and Raspberry Pi.
# The CLI is Qt-free, so the GUI stack is excluded for a much smaller build.
block_cipher = None

a = Analysis(
    ["cli.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("assets", "assets"),
    ],
    hiddenimports=[
        "litellm",
        "sqlalchemy",
        "bs4",
        "httpx",
        "cryptography",
        "machineid",
        "resend",
        "lxml",
        "pytrends",
        "openpyxl",
        "whois",
        "dns",
        "discord",
        "telegram",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide6", "shiboken6", "qtawesome", "tkinter"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="aura-cli",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="aura-cli",
)
