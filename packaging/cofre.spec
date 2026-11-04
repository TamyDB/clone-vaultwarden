# PyInstaller: um executável único, sem console. Gere no próprio sistema de destino:
#   pyinstaller packaging/cofre.spec --noconfirm --distpath dist --workpath build
from pathlib import Path

root = Path(SPECPATH).parent

analysis = Analysis(
    [str(root / "packaging" / "entry.py")],
    pathex=[str(root / "src")],
    excludes=[
        # O aplicativo só usa QtCore, QtGui e QtWidgets; o resto só aumentaria o tamanho.
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuickWidgets",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtNetwork",
        "PySide6.QtOpenGL",
        "PySide6.QtOpenGLWidgets",
        "PySide6.QtSvg",
        "PySide6.QtSvgWidgets",
        "PySide6.QtDBus",
        "PySide6.QtConcurrent",
        "PySide6.QtTest",
        "tkinter",
    ],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="cofre",
    console=False,
    upx=False,
    strip=False,
)
