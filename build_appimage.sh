#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  build_appimage.sh
#  Gera um AppImage do Remove Background App
#  - Modelos de IA baixados sob demanda na primeira execucao
#
#  Pre-requisitos:
#    - python3, python3-venv, python3-tk
#    - wget
#    - FUSE (libfuse2 no Ubuntu 22.04+)
#
#  Uso:
#    chmod +x build_appimage.sh
#    ./build_appimage.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build_tmp"
APPDIR="$BUILD_DIR/RemoveBackground.AppDir"
OUTPUT="$SCRIPT_DIR/RemoveBackground.AppImage"
VENV="$BUILD_DIR/venv"
APPIMAGETOOL="$BUILD_DIR/appimagetool"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   Build: Remove Background AppImage  ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── 1. Dependências do sistema ────────────────────────────────────────────────
echo "▶ [1/5] Verificando dependências do sistema…"

if ! command -v zenity &>/dev/null && ! command -v kdialog &>/dev/null; then
    echo "📦 Instalando zenity…"
    sudo apt-get install -y zenity 2>/dev/null || true
fi

if ! command -v python3 &>/dev/null; then
    echo "❌ python3 não encontrado."
    echo "   sudo apt install python3 python3-venv python3-tk"
    exit 1
fi

if ! python3 -c "import tkinter" &>/dev/null; then
    echo "📦 Instalando python3-tk…"
    sudo apt-get install -y python3-tk
fi

if ! ldconfig -p | grep -q libfuse.so.2; then
    echo "📦 Instalando libfuse2…"
    sudo apt-get install -y libfuse2
fi

# ── 2. Ambiente virtual + dependências Python ─────────────────────────────────
echo "▶ [2/5] Preparando ambiente Python…"
mkdir -p "$BUILD_DIR"
python3 -m venv "$VENV"
source "$VENV/bin/activate"

pip install --quiet --upgrade pip
pip install --quiet "rembg[cpu]" customtkinter Pillow pyinstaller

# ── 3. PyInstaller ────────────────────────────────────────────────────────────
echo "▶ [3/5] Empacotando com PyInstaller…"
cd "$SCRIPT_DIR"

python3 - <<'PYEOF'
import customtkinter
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

ctk_path = Path(customtkinter.__file__).parent

metas = []
for pkg in ['rembg', 'pymatting', 'onnxruntime', 'Pillow', 'numpy', 'pooch', 'tqdm']:
    try:
        metas += copy_metadata(pkg)
    except Exception:
        pass

spec = f"""# -*- mode: python ; coding: utf-8 -*-

datas = {metas!r} + [(r"{ctk_path}", "customtkinter")]

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "customtkinter",
        "PIL", "PIL._tkinter_finder",
        "onnxruntime",
        "onnxruntime.capi.onnxruntime_pybind11_state",
        "rembg", "rembg.sessions", "rembg.sessions.u2net",
        "numpy", "scipy", "skimage", "pooch",
        "pymatting", "pymatting.alpha",
    ],
    hookspath=[], hooksconfig={{}}, runtime_hooks=[], excludes=[], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
    name="removebg", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, console=False, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas,
    strip=False, upx=True, upx_exclude=[], name="removebg")
"""
Path("app.spec").write_text(spec)
print("app.spec gerado.")
PYEOF

pyinstaller --clean --noconfirm \
    --distpath "$BUILD_DIR/dist" \
    --workpath "$BUILD_DIR/work" \
    app.spec

# ── 4. Montar AppDir ──────────────────────────────────────────────────────────
echo "▶ [4/5] Montando AppDir…"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

cp -r "$BUILD_DIR/dist/removebg" "$APPDIR/usr/bin/removebg"

# Icone
ICON_SRC="$SCRIPT_DIR/icon.png"
if [ ! -f "$ICON_SRC" ]; then
    python3 - <<'PYEOF'
from PIL import Image, ImageDraw
size = 256
img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)
draw.ellipse([8, 8, size-8, size-8], fill=(30, 120, 255, 255))
draw.ellipse([60, 60, size-60, size-60], fill=(255, 255, 255, 200))
img.save("icon.png")
PYEOF
fi
cp "$ICON_SRC" "$APPDIR/removebg.png"
cp "$ICON_SRC" "$APPDIR/usr/share/icons/hicolor/256x256/apps/removebg.png"

cat > "$APPDIR/removebg.desktop" << 'EOF'
[Desktop Entry]
Name=Remove Background
Comment=Remove o fundo de imagens usando IA
Exec=removebg
Icon=removebg
Type=Application
Categories=Graphics;RasterGraphics;
Keywords=background;remove;rembg;
EOF

cat > "$APPDIR/AppRun" << 'APPRUN'
#!/bin/bash
USER_MODELS="$HOME/.local/share/removebg/models"
mkdir -p "$USER_MODELS"
export U2NET_HOME="$USER_MODELS"
exec "$APPDIR/usr/bin/removebg/removebg" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

# ── 5. Gerar AppImage ─────────────────────────────────────────────────────────
echo "▶ [5/5] Gerando AppImage…"

if [ ! -f "$APPIMAGETOOL" ]; then
    echo "   Baixando appimagetool…"
    wget -q --show-progress \
        "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" \
        -O "$APPIMAGETOOL"
    chmod +x "$APPIMAGETOOL"
fi

ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$OUTPUT"

SIZE=$(du -sh "$OUTPUT" | cut -f1)

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   ✅  AppImage gerado com sucesso!       ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "   📦 Arquivo : RemoveBackground.AppImage"
echo "   💾 Tamanho : $SIZE"
echo ""
echo "   chmod +x RemoveBackground.AppImage"
echo "   ./RemoveBackground.AppImage"
echo ""
echo "   ✦ Modelos baixados na primeira execução de cada um."
echo "   ✦ Após o download, funciona 100% offline."
echo ""