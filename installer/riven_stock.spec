# PyInstaller: carpeta (onedir) sin UPX, para evitar falsos positivos de antivirus.
# Se construye con: python tools/build_exe.py
from pathlib import Path

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    datas=[(str(ROOT / "ui"), "ui"), (str(ROOT / "assets"), "assets"), (str(ROOT / "data"), "data"),
           (str(ROOT / "VERSION"), "."), (str(ROOT / "CHANGELOG.md"), ".")],
    hiddenimports=["websocket", "cryptography"],
    excludes=["tkinter", "PIL", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="RivenStock", console=False, upx=False,
          icon=str(ROOT / "assets" / "icon.ico"))
coll = COLLECT(exe, a.binaries, a.datas, name="RivenStock", upx=False)
