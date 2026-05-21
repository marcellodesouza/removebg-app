# -*- coding: utf-8 -*-
"""
Remove Background App - powered by rembg + CustomTkinter
"""

import os
import io
import subprocess
import shutil
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from functools import lru_cache

# ---------------------------------------------------------------------------
# OFFLINE FIX
# ---------------------------------------------------------------------------
_MODELS_DIR = os.environ.setdefault(
    "U2NET_HOME",
    os.path.join(os.path.expanduser("~"), ".local", "share", "removebg", "models"),
)
os.makedirs(_MODELS_DIR, exist_ok=True)

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont, ImageTk

import logging
_log_path = os.path.join(os.path.expanduser("~"), "removebg-debug.log")
logging.basicConfig(
    filename=_log_path, level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s", filemode="w",
)
log = logging.getLogger("removebg")
log.info("=== App starting ===")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

MODELS = {
    "u2net": {
        "label":    "U2Net (padrao)",
        "tip":      "Modelo geral. Bom para objetos, produtos e pessoas. Rapido.",
        "filename": "u2net.onnx",
        "size_mb":  170,
    },
    "u2net_human_seg": {
        "label":    "U2Net Humano",
        "tip":      "Especializado em pessoas. Bordas mais limpas em retratos.",
        "filename": "u2net_human_seg.onnx",
        "size_mb":  170,
    },
    "isnet-general-use": {
        "label":    "IS-Net (alta qualidade)",
        "tip":      "Bordas muito mais precisas. Ideal para cabelos finos. Mais lento.",
        "filename": "isnet-general-use.onnx",
        "size_mb":  170,
    },
    "isnet-anime": {
        "label":    "IS-Net Anime",
        "tip":      "Para ilustracoes, anime e desenhos. Nao funciona bem em fotos.",
        "filename": "isnet-anime.onnx",
        "size_mb":  170,
    },
    "birefnet-general": {
        "label":    "BiRefNet (melhor qualidade)",
        "tip":      "Maior qualidade disponivel. Recomendado para uso profissional. Lento.",
        "filename": "birefnet-general.onnx",
        "size_mb":  200,
    },
}

MODEL_KEYS   = list(MODELS.keys())
MODEL_LABELS = [v["label"] for v in MODELS.values()]


def model_is_cached(key):
    path   = os.path.join(_MODELS_DIR, MODELS[key]["filename"])
    exists = os.path.isfile(path)
    log.debug("model_is_cached(%s) -> %s", key, exists)
    return exists


# ---------------------------------------------------------------------------
# Clipboard helper — xclip fica vivo em background (comportamento normal)
# ---------------------------------------------------------------------------

def _find_xclip():
    """Localiza o xclip: primeiro dentro do AppImage, depois no sistema."""
    # Quando rodando como AppImage, APPDIR aponta para o AppDir montado
    appdir = os.environ.get("APPDIR", "")
    if appdir:
        bundled = os.path.join(appdir, "usr", "bin", "xclip")
        if os.path.isfile(bundled):
            log.debug("xclip: usando versao embutida em %s", bundled)
            return bundled
    found = shutil.which("xclip")
    log.debug("xclip: usando versao do sistema: %s", found)
    return found


def _xclip_copy(img_rgba, callback_ok, callback_err):
    """Copia imagem RGBA para clipboard via xclip.

    O xclip propositalmente fica rodando em background ate que outro programa
    leia o clipboard (comportamento padrao do X11). Nao esperamos ele terminar:
    apenas verificamos que iniciou sem erro imediato e chamamos callback_ok.
    """
    xclip_bin = _find_xclip()
    if not xclip_bin:
        callback_err(
            "xclip nao encontrado.\n"
            "Instale com:\n  sudo apt install xclip"
        )
        return
    try:
        buf = io.BytesIO()
        img_rgba.save(buf, format="PNG")
        png_bytes = buf.getvalue()
        log.debug("xclip: enviando %d bytes", len(png_bytes))

        # Popen: nao bloqueia — xclip fica vivo ate o proximo Ctrl+V
        proc = subprocess.Popen(
            [xclip_bin, "-selection", "clipboard", "-t", "image/png"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        proc.stdin.write(png_bytes)
        proc.stdin.close()

        # Aguarda ate 3s para detectar erro de inicializacao
        try:
            proc.wait(timeout=3)
            # Se terminou rapido, verifica se foi erro
            if proc.returncode != 0:
                stderr = proc.stderr.read().decode(errors="replace").strip()
                log.warning("xclip returncode=%d stderr=%r", proc.returncode, stderr)
                callback_err(f"xclip retornou codigo {proc.returncode}\n{stderr}")
                return
        except subprocess.TimeoutExpired:
            # Ainda rodando apos 3s = normal, esta segurando o clipboard
            log.debug("xclip: rodando em background (normal)")

        log.debug("xclip: OK — imagem no clipboard")
        callback_ok()

    except Exception as exc:
        log.exception("xclip: excecao inesperada")
        callback_err(str(exc))


# ---------------------------------------------------------------------------
# Splash tips
# ---------------------------------------------------------------------------

SPLASH_TIPS = [
    (
        "O que e o Remove Background?",
        "Este app usa inteligencia artificial para remover o fundo de qualquer imagem "
        "automaticamente. Funciona com fotos de pessoas, produtos, animais, objetos e muito mais. "
        "Tudo processado localmente, sem enviar seus dados para nenhum servidor."
    ),
    (
        "Modelo U2Net (padrao)",
        "O U2Net e o modelo padrao: rapido, leve e otimo para a maioria dos casos. "
        "Produtos em fundo liso, objetos simples e fotos gerais. "
        "Ja vem pronto para usar sem nenhum download extra."
    ),
    (
        "Modelo U2Net Humano",
        "Versao especializada do U2Net treinada exclusivamente para recortar pessoas. "
        "Produz bordas mais limpas em retratos e fotos de corpo inteiro. "
        "Recomendado para fotos de perfil e e-commerce de moda."
    ),
    (
        "Modelo IS-Net (alta qualidade)",
        "O IS-Net detecta detalhes muito finos como cabelos soltos, pelos e transparencias. "
        "Ideal quando a qualidade do recorte e critica. "
        "Mais lento que o U2Net, mas entrega resultados visivelmente superiores."
    ),
    (
        "Modelo IS-Net Anime",
        "Especializado em ilustracoes, manga e estilo anime. "
        "Nao funciona bem com fotos reais — use apenas para arte digital, "
        "personagens desenhados ou imagens com tracos definidos."
    ),
    (
        "Modelo BiRefNet (melhor qualidade)",
        "O BiRefNet e o estado da arte em remocao de fundo. "
        "Ideal para uso profissional: cabelos complexos, sombras sutis e bordas perfeitas. "
        "Requer download de ~200 MB e e consideravelmente mais lento."
    ),
    (
        "Dica: qualidade da foto importa",
        "Fotos com boa iluminacao e fundo contrastante produzem resultados muito melhores. "
        "Evite imagens escuras, desfocadas ou com fundo da mesma cor do objeto principal. "
        "Quanto mais nitida a borda real, mais preciso sera o recorte da IA."
    ),
    (
        "Dica: modelos adicionais",
        "Apenas o modelo padrao (U2Net) precisa ser baixado antes de usar. "
        "Os outros modelos sao baixados automaticamente na primeira vez que voce os selecionar "
        "e ficam salvos no computador para uso offline nas proximas vezes."
    ),
    (
        "Resultado em PNG com transparencia",
        "O app salva o resultado como PNG com canal alfa (transparencia). "
        "Esse formato e compativel com Photoshop, GIMP, Canva, Figma e qualquer "
        "editor que suporte camadas transparentes."
    ),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@lru_cache(maxsize=8)
def make_checker(size, sq=14):
    w, h = size
    img  = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    c1, c2 = (210, 210, 210), (160, 160, 160)
    for y in range(0, h, sq):
        for x in range(0, w, sq):
            color = c1 if (x // sq + y // sq) % 2 == 0 else c2
            draw.rectangle([x, y, x + sq - 1, y + sq - 1], fill=color)
    return img


def composite_on_checker(img):
    checker = make_checker(img.size).copy()
    checker.paste(img, mask=img.split()[3])
    return checker


def _clean_env():
    env = os.environ.copy()
    for var in ("LD_LIBRARY_PATH", "LD_PRELOAD"):
        orig = env.pop(var + "_ORIG", None)
        if orig is not None:
            env[var] = orig
        else:
            env.pop(var, None)
    return env


def _get_font(size, bold=False):
    suffix = "-Bold" if bold else ""
    candidates = [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{suffix}.ttf",
        f"/usr/share/fonts/TTF/DejaVuSans{suffix}.ttf",
        f"/usr/share/fonts/dejavu/DejaVuSans{suffix}.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationSans{suffix}.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def make_splash_illustration(w=220, h=340):
    img  = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    blue  = (59, 130, 246)
    white = (255, 255, 255)
    gray1 = (156, 163, 175)
    gray2 = (75,  85,  99)
    green = (34, 197,  94)

    bx, by, bw, bh = 20, 10, w - 40, 120
    draw.rounded_rectangle([bx+3, by+3, bx+bw+3, by+bh+3],
                            radius=10, fill=(0, 0, 0, 80))
    draw.rounded_rectangle([bx, by, bx+bw, by+bh],
                            radius=10, fill=(31, 41, 55))
    draw.rounded_rectangle([bx, by, bx+bw, by+bh],
                            radius=10, outline=gray2, width=1)
    draw.rectangle([bx+1, by+1, bx+bw-1, by+bh//2], fill=(96, 165, 250))
    draw.rectangle([bx+1, by+bh//2, bx+bw-1, by+bh-1], fill=(34, 197, 94))
    px, py = bx + bw//2, by + 18
    draw.ellipse([px-14, py, px+14, py+28], fill=(252, 211, 77))
    draw.rounded_rectangle([px-18, py+28, px+18, py+75],
                            radius=6, fill=(99, 102, 241))
    f_sm = _get_font(11, bold=True)
    draw.text((bx+6, by+4), "ANTES", font=f_sm, fill=gray1)

    ax, ay = w // 2, by + bh + 10
    for i in range(3):
        draw.line([(ax, ay + i*8), (ax, ay + i*8 + 6)],
                  fill=(*blue, 255 - i * 60), width=3)
    draw.polygon([(ax, ay+28), (ax-10, ay+18), (ax+10, ay+18)], fill=blue)
    draw.text((ax + 8, ay + 8), "IA", font=_get_font(9), fill=blue)

    dy = ay + 36
    dw, dh, dx = bw, 120, bx
    sq = 10
    for gy in range(dy, dy+dh, sq):
        for gx in range(dx, dx+dw, sq):
            c = (200, 200, 200) if ((gx-dx)//sq + (gy-dy)//sq) % 2 == 0 \
                else (160, 160, 160)
            draw.rectangle([gx, gy, min(gx+sq, dx+dw)-1,
                             min(gy+sq, dy+dh)-1], fill=c)
    draw.rounded_rectangle([dx, dy, dx+dw, dy+dh], radius=10, outline=green, width=2)
    px2, py2 = dx + dw//2, dy + 8
    draw.ellipse([px2-14, py2, px2+14, py2+28], fill=(252, 211, 77))
    draw.rounded_rectangle([px2-18, py2+28, px2+18, py2+75],
                            radius=6, fill=(99, 102, 241))
    draw.ellipse([dx+dw-26, dy+4, dx+dw-4, dy+26], fill=green)
    draw.line([(dx+dw-21, dy+15), (dx+dw-15, dy+21)], fill=white, width=2)
    draw.line([(dx+dw-15, dy+21), (dx+dw-6,  dy+10)], fill=white, width=2)
    draw.text((dx+6, dy+4), "DEPOIS", font=f_sm, fill=green)
    return img


def make_welcome_image(w=900, h=600):
    img  = Image.new("RGB", (w, h), (17, 24, 39))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        draw.line([(0, y), (w, y)], fill=(
            int(17 + 14 * t), int(24 + 17 * t), int(39 + 16 * t)))
    color     = (59, 130, 246)
    cx, cy    = w // 2, h // 2 - 30
    icon_size = 72
    ix        = cx - icon_size // 2
    iy        = cy - icon_size // 2 - 20
    draw.rounded_rectangle([ix, iy, ix+icon_size, iy+icon_size],
                            radius=10, outline=color, width=3)
    draw.ellipse([ix+10, iy+10, ix+24, iy+24], outline=color, width=2)
    draw.polygon([
        ix+5,              iy+icon_size-8,
        ix+icon_size//2-8, iy+icon_size//2+4,
        ix+icon_size//2+8, iy+icon_size//2+14,
        ix+icon_size-5,    iy+icon_size-8,
    ], outline=color, fill=(31, 41, 55))
    ax, ay = cx, iy + icon_size + 16
    draw.line([(ax, ay), (ax, ay+28)], fill=color, width=3)
    draw.line([(ax, ay+28), (ax-12, ay+16)], fill=color, width=3)
    draw.line([(ax, ay+28), (ax+12, ay+16)], fill=color, width=3)
    f_title = _get_font(26, bold=True)
    title   = "Use o botao 'Abrir Imagem' para comecar"
    try:
        bbox = draw.textbbox((0, 0), title, font=f_title)
        tw   = bbox[2] - bbox[0]
    except Exception:
        tw = len(title) * 13
    draw.text(((w - tw) // 2, cy + icon_size // 2 + 30),
              title, fill=(229, 231, 235), font=f_title)
    f_sub = _get_font(15)
    sub   = "Formatos suportados: JPG, PNG, WEBP, BMP, TIFF"
    try:
        bbox = draw.textbbox((0, 0), sub, font=f_sub)
        sw   = bbox[2] - bbox[0]
    except Exception:
        sw = len(sub) * 8
    draw.text(((w - sw) // 2, cy + icon_size // 2 + 68),
              sub, fill=(107, 114, 128), font=f_sub)
    return img


def make_result_placeholder_image(w=900, h=600):
    """Imagem informativa para o painel de resultado. Fontes proporcionais ao tamanho."""
    img  = Image.new("RGB", (w, h), (17, 24, 39))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        draw.line([(0, y), (w, y)], fill=(
            int(17 + 10 * t), int(24 + 12 * t), int(39 + 10 * t)))

    cx = w // 2

    # Tamanhos proporcionais ao canvas
    icon_size  = max(40, min(80, h // 7))
    f_title_sz = max(13, min(22, h // 28))
    f_body_sz  = max(10, min(15, h // 38))
    gap_line   = max(16, min(26, h // 24))

    sq = max(8, icon_size // 5)
    bx = cx - icon_size // 2
    by = h // 2 - icon_size - gap_line * 2
    for gy in range(by, by + icon_size, sq):
        for gx in range(bx, bx + icon_size, sq):
            c = (55, 65, 81) if ((gx - bx)//sq + (gy - by)//sq) % 2 == 0 \
                else (31, 41, 55)
            draw.rectangle([gx, gy, min(gx+sq, bx+icon_size)-1,
                             min(gy+sq, by+icon_size)-1], fill=c)
    draw.rounded_rectangle([bx, by, bx+icon_size, by+icon_size],
                            radius=6, outline=(59, 130, 246), width=2)

    f_title = _get_font(f_title_sz, bold=True)
    title = "O resultado aparecera aqui"
    try:
        bbox = draw.textbbox((0, 0), title, font=f_title)
        tw = bbox[2] - bbox[0]
    except Exception:
        tw = len(title) * (f_title_sz // 2)
    draw.text(((w - tw) // 2, by + icon_size + gap_line // 2), title,
              fill=(229, 231, 235), font=f_title)

    f_body = _get_font(f_body_sz)
    lines = [
        ("Apos remover o fundo, use os botoes acima:", (148, 163, 184)),
        ("", None),
        ("Salvar PNG  ->  salva o arquivo no seu computador", (203, 213, 225)),
        ("Copiar      ->  copia para colar no GIMP, Canva, Photoshop...", (203, 213, 225)),
        ("", None),
        ("O resultado e um PNG com fundo transparente.", (100, 116, 139)),
    ]
    y_cur = by + icon_size + gap_line * 2 + f_title_sz
    for line, color in lines:
        if not line:
            y_cur += gap_line // 2
            continue
        try:
            bbox = draw.textbbox((0, 0), line, font=f_body)
            lw = bbox[2] - bbox[0]
        except Exception:
            lw = len(line) * (f_body_sz // 2)
        draw.text(((w - lw) // 2, y_cur), line, fill=color, font=f_body)
        y_cur += gap_line

    return img


# ---------------------------------------------------------------------------
# Splash Screen
# ---------------------------------------------------------------------------

class SplashScreen(tk.Tk):

    STEPS = [
        "Carregando onnxruntime...",
        "Carregando rembg...",
        "Iniciando interface...",
    ]

    TIP_INTERVAL_MS = 4500

    def __init__(self):
        super().__init__()
        self.overrideredirect(True)
        self.configure(bg="#0f172a")
        self.attributes("-topmost", True)

        W, H = 720, 400
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

        self._tip_index = 0
        self._tip_job   = None
        self._bar_pos   = 0
        self._bar_dir   = 1
        self._bar_done  = False

        self._build(W, H)
        self._rotate_tip()
        self.after(16, self._pulse_bar)

    def _build(self, W, H):
        LEFT = 240
        left_frame = tk.Frame(self, bg="#111827", width=LEFT)
        left_frame.pack(side="left", fill="y")
        left_frame.pack_propagate(False)

        tk.Label(left_frame, text="*", font=("Arial", 44, "bold"),
                 bg="#111827", fg="#3b82f6").pack(pady=(28, 0))
        tk.Label(left_frame, text="Remove",
                 font=("Arial", 15, "bold"), bg="#111827", fg="white").pack()
        tk.Label(left_frame, text="Background",
                 font=("Arial", 15, "bold"), bg="#111827", fg="white").pack()
        tk.Label(left_frame, text="powered by rembg",
                 font=("Arial", 9), bg="#111827", fg="#6b7280").pack(pady=(2, 10))
        try:
            illus_pil   = make_splash_illustration(LEFT - 20, 220)
            self._illus = ImageTk.PhotoImage(illus_pil)
            tk.Label(left_frame, image=self._illus, bg="#111827").pack()
        except Exception:
            log.exception("illustration failed")

        tk.Frame(self, bg="#1e293b", width=1).place(x=LEFT, y=0, height=H)

        right_frame = tk.Frame(self, bg="#0f172a")
        right_frame.pack(side="left", fill="both", expand=True)

        tk.Label(right_frame, text="Saiba mais enquanto carrega",
                 font=("Arial", 11, "bold"),
                 bg="#0f172a", fg="#64748b").pack(anchor="w", padx=24, pady=(20, 0))

        dots = tk.Frame(right_frame, bg="#0f172a")
        dots.pack(anchor="w", padx=24, pady=(4, 0))
        self._dot_labels = []
        for _ in SPLASH_TIPS:
            d = tk.Label(dots, text="\u2022", font=("Arial", 10),
                         bg="#0f172a", fg="#1e3a5f")
            d.pack(side="left", padx=1)
            self._dot_labels.append(d)

        self._tip_title_var = tk.StringVar()
        tk.Label(right_frame, textvariable=self._tip_title_var,
                 font=("Arial", 13, "bold"), bg="#0f172a", fg="#e2e8f0",
                 wraplength=420, justify="left").pack(anchor="w", padx=24, pady=(14, 0))

        self._tip_body_var = tk.StringVar()
        tk.Label(right_frame, textvariable=self._tip_body_var,
                 font=("Arial", 11), bg="#0f172a", fg="#94a3b8",
                 wraplength=420, justify="left").pack(anchor="w", padx=24, pady=(8, 0))

        tk.Frame(right_frame, bg="#0f172a").pack(fill="both", expand=True)
        tk.Frame(right_frame, bg="#1e293b", height=1).pack(fill="x", pady=(0, 14))

        self._status_var = tk.StringVar(value="Iniciando...")
        tk.Label(right_frame, textvariable=self._status_var,
                 font=("Arial", 10), bg="#0f172a", fg="#64748b").pack(
                     anchor="w", padx=24, pady=(0, 6))

        track = tk.Frame(right_frame, bg="#1e293b", height=6)
        track.pack(fill="x", padx=24, pady=(0, 20))
        self._track = track
        self._bar   = tk.Frame(track, bg="#3b82f6", height=6, width=80)
        self._bar.place(x=0, y=0, relheight=1)

    def _pulse_bar(self):
        if self._bar_done:
            return
        try:
            total = self._track.winfo_width()
            if total < 10:
                self.after(16, self._pulse_bar)
                return
            seg = 100
            self._bar_pos += self._bar_dir * 5
            if self._bar_pos + seg >= total:
                self._bar_pos = total - seg
                self._bar_dir = -1
            elif self._bar_pos <= 0:
                self._bar_pos = 0
                self._bar_dir = 1
            self._bar.place(x=self._bar_pos, y=0, relheight=1, width=seg)
            self.after(16, self._pulse_bar)
        except Exception:
            pass

    def _fill_bar(self):
        self._bar_done = True
        try:
            self._bar.place(x=0, y=0, relheight=1,
                            width=self._track.winfo_width())
        except Exception:
            pass

    def _rotate_tip(self):
        i = self._tip_index % len(SPLASH_TIPS)
        self._tip_title_var.set(SPLASH_TIPS[i][0])
        self._tip_body_var.set(SPLASH_TIPS[i][1])
        for j, d in enumerate(self._dot_labels):
            d.configure(fg="#3b82f6" if j == i else "#1e3a5f")
        self._tip_index += 1
        try:
            self.update_idletasks()
        except Exception:
            pass
        self._tip_job = self.after(self.TIP_INTERVAL_MS, self._rotate_tip)

    def stop_tips(self):
        if self._tip_job:
            try:
                self.after_cancel(self._tip_job)
            except Exception:
                pass
            self._tip_job = None

    def advance(self, step_index):
        msg = self.STEPS[step_index] if step_index < len(self.STEPS) else "Pronto!"
        self._status_var.set(msg)
        try:
            self.update_idletasks()
            self.update()
        except Exception:
            pass

    def finish(self):
        self._fill_bar()
        try:
            self.update_idletasks()
            self.update()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Image Panel
# ---------------------------------------------------------------------------

class ImagePanel(ctk.CTkFrame):

    ZOOM_MIN  = 0.05
    ZOOM_MAX  = 10.0
    ZOOM_STEP = 1.25

    def __init__(self, master, title, placeholder, **kw):
        super().__init__(master, **kw)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._pil_image   = None
        self._photo       = None
        self._zoom        = 1.0
        self._offset      = [0, 0]
        self._drag_start  = None
        self._placeholder = placeholder
        self._has_image   = False
        self._is_welcome  = False
        self._zoom_timer  = None
        self._resize_job  = None

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 0))
        bar.columnconfigure(0, weight=1)

        ctk.CTkLabel(bar, text=title,
                     font=ctk.CTkFont(size=13, weight="bold")).grid(
                         row=0, column=0, sticky="w")

        zf = ctk.CTkFrame(bar, fg_color="transparent")
        zf.grid(row=0, column=1)
        ctk.CTkButton(zf, text="-", width=26, height=22,
                      command=self.zoom_out).pack(side="left", padx=1)
        self._zoom_lbl = ctk.CTkLabel(zf, text="--", width=46,
                                       font=ctk.CTkFont(size=11))
        self._zoom_lbl.pack(side="left")
        ctk.CTkButton(zf, text="+", width=26, height=22,
                      command=self.zoom_in).pack(side="left", padx=1)
        ctk.CTkButton(zf, text="Fit", width=30, height=22,
                      fg_color="transparent",
                      command=self.zoom_fit).pack(side="left", padx=(3, 0))

        self.canvas = tk.Canvas(self, bg="#111827",
                                highlightthickness=2,
                                highlightbackground="#1f2937",
                                cursor="crosshair")
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=10, pady=(6, 10))

        self.canvas.bind("<Configure>",     self._on_resize)
        self.canvas.bind("<ButtonPress-1>", self._on_click)
        self.canvas.bind("<B1-Motion>",     self._pan_move)
        self.canvas.bind("<MouseWheel>",    self._on_scroll)
        self.canvas.bind("<Button-4>",      self._on_scroll)
        self.canvas.bind("<Button-5>",      self._on_scroll)

        self._open_callback  = None
        self._placeholder_fn = None  # callable(w,h)->Image para placeholders responsivos

    def show(self, img, is_welcome=False):
        display = img.copy()
        if display.mode == "RGBA":
            display = composite_on_checker(display)
        self._pil_image  = display
        self._has_image  = True
        self._is_welcome = is_welcome
        self.canvas.configure(highlightbackground="#1f2937")
        self.zoom_fit()

    def show_responsive(self, fn, is_welcome=True):
        """Mostra imagem gerada por fn(w,h) — regenerada a cada resize."""
        self._placeholder_fn = fn
        self._has_image  = False
        self._is_welcome = False
        cw = max(self.canvas.winfo_width(),  200)
        ch = max(self.canvas.winfo_height(), 200)
        img = fn(cw, ch)
        self.show(img, is_welcome=is_welcome)

    def clear(self, placeholder=""):
        self._pil_image      = None
        self._photo          = None
        self._has_image      = False
        self._is_welcome     = False
        self._placeholder_fn = None
        if placeholder:
            self._placeholder = placeholder
        self._draw_placeholder()

    def zoom_fit(self):
        if not self._pil_image:
            return
        self._offset = [0, 0]
        cw = max(self.canvas.winfo_width(),  1)
        ch = max(self.canvas.winfo_height(), 1)
        iw, ih = self._pil_image.size
        self._zoom = min(cw / iw, ch / ih, 1.0)
        self._render(Image.BILINEAR)

    def zoom_in(self):
        if self._is_welcome:
            return
        self._zoom = min(self._zoom * self.ZOOM_STEP, self.ZOOM_MAX)
        self._render_fast()

    def zoom_out(self):
        if self._is_welcome:
            return
        self._zoom = max(self._zoom / self.ZOOM_STEP, self.ZOOM_MIN)
        self._render_fast()

    def _render(self, quality=Image.BILINEAR):
        if not self._pil_image:
            return
        cw = max(self.canvas.winfo_width(),  1)
        ch = max(self.canvas.winfo_height(), 1)
        nw = max(1, int(self._pil_image.width  * self._zoom))
        nh = max(1, int(self._pil_image.height * self._zoom))
        self._photo = ImageTk.PhotoImage(self._pil_image.resize((nw, nh), quality))
        self.canvas.delete("all")
        self.canvas.create_image(
            cw // 2 + self._offset[0],
            ch // 2 + self._offset[1],
            anchor="center", image=self._photo, tags="image")
        self._zoom_lbl.configure(text=f"{int(self._zoom * 100)}%")

    def _render_fast(self):
        self._render(Image.NEAREST)
        if self._zoom_timer:
            self.after_cancel(self._zoom_timer)
        self._zoom_timer = self.after(150, lambda: self._render(Image.BILINEAR))

    def _draw_placeholder(self):
        self.canvas.delete("all")
        self.after(80, self._deferred_placeholder)

    def _deferred_placeholder(self):
        w = self.canvas.winfo_width()  or 300
        h = self.canvas.winfo_height() or 300
        self.canvas.delete("all")
        self.canvas.create_text(w//2, h//2,
            text=self._placeholder, font=("Arial", 13),
            fill="#94a3b8", justify="center", tags="ph")

    def _on_resize(self, _event):
        if self._resize_job:
            try:
                self.after_cancel(self._resize_job)
            except Exception:
                pass
        self._resize_job = self.after(100, self._do_resize)

    def _do_resize(self):
        self._resize_job = None
        if self._has_image:
            self.zoom_fit()
        elif self._placeholder_fn:
            # Regenera placeholder responsivo com novo tamanho
            cw = max(self.canvas.winfo_width(),  200)
            ch = max(self.canvas.winfo_height(), 200)
            img = self._placeholder_fn(cw, ch)
            self.show(img, is_welcome=True)
        else:
            self._deferred_placeholder()

    def _on_click(self, event):
        # Clique no canvas so inicia pan quando ha imagem real carregada
        if self._has_image and not self._is_welcome:
            self._drag_start = (event.x, event.y)

    def _pan_move(self, event):
        if self._drag_start and self._pil_image and not self._is_welcome:
            self._offset[0] += event.x - self._drag_start[0]
            self._offset[1] += event.y - self._drag_start[1]
            self._drag_start = (event.x, event.y)
            self._render(Image.NEAREST)

    def _on_scroll(self, event):
        if not self._pil_image or self._is_welcome:
            return
        up = event.num == 4 or event.delta > 0
        self._zoom = (
            min(self._zoom * self.ZOOM_STEP, self.ZOOM_MAX) if up
            else max(self._zoom / self.ZOOM_STEP, self.ZOOM_MIN)
        )
        self._render_fast()


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------

class App(ctk.CTk):

    TIP_DONE_DELAY_MS = 5000
    TIP_INFO_DELAY_MS = 4000

    _TIP_COLOR = {
        "info":    ("#94a3b8", "#94a3b8"),
        "working": ("#60a5fa", "#60a5fa"),
        "ok":      ("#4ade80", "#4ade80"),
        "error":   ("#f87171", "#f87171"),
    }

    def __init__(self, remove_fn, new_session_fn):
        super().__init__()
        self._remove_fn      = remove_fn
        self._new_session_fn = new_session_fn
        self._session        = None
        self._cur_model      = MODEL_KEYS[0]
        self._original       = None
        self._result         = None
        self._src_path       = ""
        self._tip_hide_job   = None
        self._dialog_busy    = False
        self._result_full    = None   # resultado original sem crop (para resetar)
        self._crop_rect      = None   # (x1,y1,x2,y2) em pixels da imagem RGBA original
        self._crop_mode      = False  # True quando usuario esta desenhando crop

        self.title("Remove Background")
        self.geometry("1100x700")
        self.minsize(800, 520)

        self._build()
        self.after(100, self._show_welcome)

    def _show_welcome(self):
        try:
            self._panel_orig.show(make_welcome_image(), is_welcome=True)
            self._panel_result.show_responsive(make_result_placeholder_image)
        except Exception:
            log.exception("welcome image failed")
            self._panel_orig._draw_placeholder()
            self._panel_result._draw_placeholder()

    def _build(self):
        bar = ctk.CTkFrame(self, height=56, corner_radius=0)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        ctk.CTkLabel(bar, text="Remove Background",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
                         side="left", padx=18)

        self._btn_save = ctk.CTkButton(
            bar, text="Salvar PNG", width=110,
            state="disabled", command=self._save)
        self._btn_save.pack(side="right", padx=(0, 12), pady=10)

        self._btn_copy = ctk.CTkButton(
            bar, text="Copiar", width=80,
            state="disabled",
            fg_color="transparent",
            border_width=1,
            command=self._copy_to_clipboard)
        self._btn_copy.pack(side="right", padx=(0, 4), pady=10)

        self._btn_remove = ctk.CTkButton(
            bar, text="Remover Fundo", width=140,
            state="disabled", command=self._start_remove)
        self._btn_remove.pack(side="right", padx=(0, 6), pady=10)

        self._btn_open = ctk.CTkButton(
            bar, text="Abrir Imagem", width=130, command=self._open)
        self._btn_open.pack(side="right", padx=(0, 6), pady=10)

        model_bar = ctk.CTkFrame(self, height=44, corner_radius=0,
                                  fg_color=("gray88", "gray18"))
        model_bar.pack(fill="x")
        model_bar.pack_propagate(False)

        ctk.CTkLabel(model_bar, text="Modelo:",
                     font=ctk.CTkFont(size=12)).pack(
                         side="left", padx=(14, 6), pady=10)

        self._model_menu = ctk.CTkOptionMenu(
            model_bar, values=MODEL_LABELS, width=220,
            command=self._on_model_change)
        self._model_menu.pack(side="left", pady=10)

        self._tip_label = ctk.CTkLabel(
            model_bar, text="",
            font=ctk.CTkFont(size=12),
            text_color=self._TIP_COLOR["info"])

        panels = ctk.CTkFrame(self, fg_color="transparent")
        panels.pack(fill="both", expand=True, padx=12, pady=(10, 10))
        panels.columnconfigure((0, 1), weight=1)
        panels.rowconfigure(0, weight=1)

        self._panel_orig = ImagePanel(
            panels, title="Original",
            placeholder="Use o botao 'Abrir Imagem' para comecar")
        self._panel_orig.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        # Sem _open_callback — abrir imagem apenas pelo botao

        self._panel_result = ImagePanel(
            panels, title="Sem Fundo",
            placeholder="O resultado aparecera aqui apos processar")
        self._panel_result.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        # Barra de crop abaixo dos paineis
        self._crop_bar = ctk.CTkFrame(self, height=40, corner_radius=0,
                                       fg_color=("gray82", "gray14"))
        # Nao empacotada ainda — aparece so apos processar

        ctk.CTkLabel(self._crop_bar, text="Recorte:",
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(14, 6))

        self._btn_crop_auto = ctk.CTkButton(
            self._crop_bar, text="Auto (rente ao objeto)", width=170,
            command=self._crop_auto)
        self._btn_crop_auto.pack(side="left", padx=(0, 4))

        self._btn_crop_manual = ctk.CTkButton(
            self._crop_bar, text="Desenhar area", width=130,
            fg_color="transparent", border_width=1,
            command=self._crop_start_manual)
        self._btn_crop_manual.pack(side="left", padx=(0, 4))

        self._btn_crop_reset = ctk.CTkButton(
            self._crop_bar, text="Resetar", width=80,
            fg_color="transparent", border_width=1,
            command=self._crop_reset)
        self._btn_crop_reset.pack(side="left", padx=(0, 4))

        self._crop_tip = ctk.CTkLabel(
            self._crop_bar, text="",
            font=ctk.CTkFont(size=11), text_color="#94a3b8")
        self._crop_tip.pack(side="left", padx=(8, 0))

        self._progress = ctk.CTkProgressBar(bar, mode="indeterminate", width=180)

    # ----- Tip label -----

    def _set_tip(self, text, kind="info", auto_hide_ms=None):
        log.debug("_set_tip(%r, %s)", text, kind)
        try:
            if self._tip_hide_job:
                self.after_cancel(self._tip_hide_job)
                self._tip_hide_job = None
            color = self._TIP_COLOR.get(kind, self._TIP_COLOR["info"])
            self._tip_label.configure(text=text, text_color=color)
            self._tip_label.pack_forget()
            self._tip_label.pack(side="left", padx=(8, 0))
            if auto_hide_ms:
                self._tip_hide_job = self.after(auto_hide_ms, self._hide_tip)
        except Exception:
            log.exception("_set_tip failed")

    def _hide_tip(self):
        self._tip_hide_job = None
        try:
            self._tip_label.pack_forget()
            self._tip_label.configure(text="")
        except Exception:
            pass

    # ----- Model -----

    def _on_model_change(self, label):
        try:
            idx     = MODEL_LABELS.index(label)
            new_key = MODEL_KEYS[idx]
            info    = MODELS[new_key]
            cached  = model_is_cached(new_key)

            if not cached:
                confirmed = messagebox.askyesno(
                    title="Download necessario",
                    message=(
                        f"O modelo \"{info['label']}\" ainda nao foi baixado.\n\n"
                        f"Tamanho do download: ~{info['size_mb']} MB\n\n"
                        f"O arquivo sera salvo em:\n{_MODELS_DIR}\n\n"
                        f"Nas proximas vezes, sera usado sem internet.\n\n"
                        f"Deseja baixar agora?"
                    ), icon="question",
                )
                if not confirmed:
                    self._model_menu.set(MODELS[self._cur_model]["label"])
                    return

            self._cur_model = new_key
            self._session   = None

            if cached:
                self._set_tip(info["tip"], kind="info",
                              auto_hide_ms=self.TIP_INFO_DELAY_MS)
            else:
                self._btn_remove.configure(state="disabled")
                self._btn_open.configure(state="disabled")
                self._set_tip(
                    f"\u2b07 Baixando... ~{info['size_mb']} MB",
                    kind="working")
                self._progress.pack(side="right", padx=16, pady=8)
                self._progress.start()

                def _download():
                    try:
                        self._session = self._new_session_fn(new_key)
                        self.after(0, self._on_download_done, new_key)
                    except Exception as exc:
                        log.exception("Download error: %s", new_key)
                        self.after(0, self._on_download_error, new_key, str(exc))

                threading.Thread(target=_download, daemon=True).start()
        except Exception:
            log.exception("_on_model_change failed")

    def _on_download_done(self, key):
        try:
            self._progress.stop()
            self._progress.pack_forget()
            self._btn_open.configure(state="normal")
            if self._original:
                self._btn_remove.configure(state="normal")
            label = MODELS[key]["label"]
            self._set_tip("\u2713 Download concluido!", kind="ok",
                          auto_hide_ms=self.TIP_DONE_DELAY_MS)
            self.lift()
            self.focus_force()
            messagebox.showinfo(
                title="Download concluido",
                message=(
                    f"O modelo \"{label}\" foi baixado com sucesso!\n\n"
                    f"Salvo em:\n{_MODELS_DIR}\n\n"
                    f"Nas proximas vezes sera usado sem internet.\n\n"
                    f"Voce ja pode usar este modelo para remover fundos."
                )
            )
        except Exception:
            log.exception("_on_download_done failed")

    def _on_download_error(self, key, msg):
        try:
            self._progress.stop()
            self._progress.pack_forget()
            self._btn_open.configure(state="normal")
            self._set_tip("\u2717 Erro no download", kind="error",
                          auto_hide_ms=self.TIP_DONE_DELAY_MS)
            messagebox.showerror("Erro no download", msg)
        except Exception:
            log.exception("_on_download_error handler failed")

    def _get_session(self):
        if self._session is None:
            self._session = self._new_session_fn(self._cur_model)
        return self._session

    # ----- Open -----

    def _open(self):
        if self._dialog_busy:
            log.debug("_open() ignorado: dialog ja aberto")
            return
        self._dialog_busy = True
        self.update_idletasks()
        try:
            path = self._native_open_dialog()
        except Exception as e:
            log.exception("dialog crashed")
            path = None
        finally:
            self._dialog_busy = False

        if not path or not os.path.isfile(path):
            return
        self._load_image(path)

    def _native_open_dialog(self):
        filters = "*.jpg *.jpeg *.png *.bmp *.webp *.tiff *.tif"
        env     = _clean_env()

        if shutil.which("zenity"):
            try:
                r = subprocess.run(
                    ["zenity", "--file-selection",
                     "--title=Selecionar imagem",
                     "--file-filter=Imagens | " + filters,
                     "--file-filter=Todos os arquivos | *"],
                    capture_output=True, text=True, env=env,
                    stdin=subprocess.DEVNULL)
                return r.stdout.strip()
            except Exception:
                log.exception("zenity failed")

        if shutil.which("kdialog"):
            try:
                r = subprocess.run(
                    ["kdialog", "--getopenfilename", ".",
                     filters + "|Imagens"],
                    capture_output=True, text=True, env=env)
                return r.stdout.strip()
            except Exception:
                pass

        return filedialog.askopenfilename(
            title="Selecionar imagem",
            filetypes=[
                ("Imagens", "*.jpg *.jpeg *.png *.bmp *.webp *.tiff *.tif"),
                ("Todos os arquivos", "*.*"),
            ])

    def _load_image(self, path):
        self._set_tip("Carregando...", kind="working")
        self.update_idletasks()
        try:
            img = Image.open(path).convert("RGBA")
        except Exception as exc:
            log.exception("open failed")
            messagebox.showerror("Erro ao abrir", str(exc))
            self._hide_tip()
            return
        self._src_path = path
        self._original = img
        self._result   = None
        self._panel_orig.show(img, is_welcome=False)
        # Restaura placeholder informativo no painel de resultado
        self._panel_result.show_responsive(make_result_placeholder_image)
        self._btn_remove.configure(state="normal")
        self._btn_save.configure(state="disabled")
        self._btn_copy.configure(state="disabled")
        self._crop_bar.pack_forget()
        self._result_full = None
        self._crop_rect   = None
        self._set_tip(
            f"{os.path.basename(path)}  {img.size[0]}x{img.size[1]}",
            kind="info", auto_hide_ms=self.TIP_INFO_DELAY_MS)

    # ----- Remove -----

    def _start_remove(self):
        if not self._original:
            return

        if not model_is_cached(self._cur_model):
            m = MODELS[self._cur_model]
            if not messagebox.askyesno(
                title="Download necessario",
                message=(
                    f"O modelo \"{m['label']}\" ainda nao foi baixado.\n\n"
                    f"Tamanho: ~{m['size_mb']} MB\n\nDeseja baixar agora?"
                ), icon="question",
            ):
                return

        self._btn_remove.configure(state="disabled")
        self._btn_open.configure(state="disabled")
        self._btn_save.configure(state="disabled")
        self._btn_copy.configure(state="disabled")
        self._panel_result.clear("Processando...")
        self._set_tip("\u2699 Processando imagem...", kind="working")
        self._progress.pack(side="right", padx=16, pady=8)
        self._progress.start()
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        was_cached = model_is_cached(self._cur_model)
        try:
            result     = self._remove_fn(self._original, session=self._get_session())
            now_cached = model_is_cached(self._cur_model)
            self.after(0, self._on_success, result,
                       not was_cached and now_cached)
        except Exception as exc:
            self.after(0, self._on_error, str(exc))

    def _on_success(self, result, model_just_downloaded=False):
        self._result      = result
        self._result_full = result   # guarda original para reset
        self._crop_rect   = None
        self._progress.stop()
        self._progress.pack_forget()
        # Crop automatico imediato
        self._apply_auto_crop(show_tip=False)
        self._btn_open.configure(state="normal")
        self._btn_remove.configure(state="normal")
        self._btn_save.configure(state="normal")
        self._btn_copy.configure(state="normal")
        self._set_tip("\u2713 Fundo removido!", kind="ok",
                      auto_hide_ms=self.TIP_DONE_DELAY_MS)
        # Mostra barra de crop
        self._crop_bar.pack(fill="x", before=self._panel_result.master)

        if model_just_downloaded:
            label = MODELS[self._cur_model]["label"]
            self.lift()
            self.focus_force()
            messagebox.showinfo(
                title="Modelo baixado",
                message=(
                    f"O modelo \"{label}\" foi baixado automaticamente.\n\n"
                    f"Salvo em:\n{_MODELS_DIR}\n\n"
                    f"Nas proximas vezes sera usado sem internet."
                )
            )

    def _on_error(self, msg):
        self._progress.stop()
        self._progress.pack_forget()
        self._btn_open.configure(state="normal")
        self._btn_remove.configure(state="normal")
        self._set_tip("\u2717 Erro ao processar", kind="error",
                      auto_hide_ms=self.TIP_DONE_DELAY_MS)
        messagebox.showerror("Erro ao processar", msg)

    # ----- Crop -----

    def _apply_auto_crop(self, show_tip=True):
        """Crop automatico: corta rente aos pixels nao-transparentes."""
        if not self._result_full:
            return
        bbox = self._result_full.getbbox()  # (x1,y1,x2,y2) ou None
        if not bbox:
            return
        self._crop_rect = bbox
        self._result    = self._result_full.crop(bbox)
        self._panel_result.show(self._result)
        if show_tip:
            sz = self._result.size
            self._crop_tip.configure(
                text=f"Auto: {sz[0]}x{sz[1]} px", text_color="#4ade80")

    def _crop_reset(self):
        """Volta para a imagem completa sem crop."""
        if not self._result_full:
            return
        self._crop_rect = None
        self._result    = self._result_full
        self._panel_result.show(self._result)
        self._crop_tip.configure(text="Sem recorte", text_color="#94a3b8")
        self._panel_result.canvas.unbind("<ButtonPress-1>")
        self._panel_result.canvas.unbind("<B1-Motion>")
        self._panel_result.canvas.unbind("<ButtonRelease-1>")
        self._panel_result.canvas.configure(cursor="crosshair")
        self._crop_mode = False

    def _crop_start_manual(self):
        """Ativa modo de desenho de retangulo de crop no canvas do resultado."""
        if not self._result_full:
            return
        # Garante que estamos mostrando a imagem completa para desenhar
        if self._crop_rect:
            self._result = self._result_full
            self._panel_result.show(self._result)
        self._crop_mode = True
        self._panel_result.canvas.configure(cursor="crosshair")
        self._crop_tip.configure(
            text="Clique e arraste para definir a area", text_color="#60a5fa")

        canvas    = self._panel_result.canvas
        self._crop_start_xy = None
        self._crop_rect_id  = None

        def _on_press(event):
            self._crop_start_xy = (event.x, event.y)
            if self._crop_rect_id:
                canvas.delete(self._crop_rect_id)

        def _on_drag(event):
            if not self._crop_start_xy:
                return
            if self._crop_rect_id:
                canvas.delete(self._crop_rect_id)
            x0, y0 = self._crop_start_xy
            self._crop_rect_id = canvas.create_rectangle(
                x0, y0, event.x, event.y,
                outline="#60a5fa", width=2, dash=(4, 4))

        def _on_release(event):
            if not self._crop_start_xy:
                return
            canvas.configure(cursor="crosshair")
            self._crop_mode = False

            # Converte coordenadas canvas -> pixels da imagem original
            x0c, y0c = self._crop_start_xy
            x1c, y1c = event.x, event.y
            if abs(x1c - x0c) < 5 or abs(y1c - y0c) < 5:
                self._crop_tip.configure(
                    text="Area muito pequena, tente novamente", text_color="#f87171")
                if self._crop_rect_id:
                    canvas.delete(self._crop_rect_id)
                return

            # Coordenadas do centro da imagem no canvas
            panel   = self._panel_result
            cw      = canvas.winfo_width()
            ch      = canvas.winfo_height()
            img_w   = int(self._result_full.width  * panel._zoom)
            img_h   = int(self._result_full.height * panel._zoom)
            img_x0  = cw // 2 + panel._offset[0] - img_w // 2
            img_y0  = ch // 2 + panel._offset[1] - img_h // 2

            # Canvas coords -> imagem coords
            def to_img(cx, cy):
                ix = (cx - img_x0) / panel._zoom
                iy = (cy - img_y0) / panel._zoom
                return (
                    max(0, min(int(ix), self._result_full.width)),
                    max(0, min(int(iy), self._result_full.height)),
                )

            ix0, iy0 = to_img(min(x0c, x1c), min(y0c, y1c))
            ix1, iy1 = to_img(max(x0c, x1c), max(y0c, y1c))

            if ix1 <= ix0 or iy1 <= iy0:
                self._crop_tip.configure(
                    text="Area invalida, tente novamente", text_color="#f87171")
                if self._crop_rect_id:
                    canvas.delete(self._crop_rect_id)
                return

            self._crop_rect = (ix0, iy0, ix1, iy1)
            self._result    = self._result_full.crop(self._crop_rect)
            self._panel_result.show(self._result)
            sz = self._result.size
            self._crop_tip.configure(
                text=f"Manual: {sz[0]}x{sz[1]} px", text_color="#4ade80")

            # Remove bindings temporarios
            canvas.unbind("<ButtonPress-1>")
            canvas.unbind("<B1-Motion>")
            canvas.unbind("<ButtonRelease-1>")

        canvas.bind("<ButtonPress-1>",   _on_press)
        canvas.bind("<B1-Motion>",       _on_drag)
        canvas.bind("<ButtonRelease-1>", _on_release)

    def _crop_auto(self):
        self._apply_auto_crop(show_tip=True)

    # ----- Copy (async com timeout) -----

    def _copy_to_clipboard(self):
        if not self._result:
            return

        self._btn_copy.configure(state="disabled")
        self._set_tip("\u29d7 Copiando...", kind="working")
        self.update_idletasks()

        img_snapshot = self._result

        def _on_ok():
            self.after(0, lambda: self._btn_copy.configure(state="normal"))
            self.after(0, lambda: self._set_tip(
                "\u2713 Copiado para area de transferencia!",
                kind="ok", auto_hide_ms=self.TIP_DONE_DELAY_MS))

        def _on_err(msg):
            self.after(0, lambda: self._btn_copy.configure(state="normal"))
            self.after(0, lambda: self._set_tip(
                "\u2717 Falha ao copiar", kind="error",
                auto_hide_ms=self.TIP_DONE_DELAY_MS))
            self.after(0, lambda: messagebox.showerror("Erro ao copiar", msg))

        def _run():
            try:
                _xclip_copy(img_snapshot, callback_ok=_on_ok, callback_err=_on_err)
            except Exception as exc:
                # Garantia extra: callback SEMPRE e chamado
                log.exception("_run copy: excecao nao tratada")
                _on_err(str(exc))

        threading.Thread(target=_run, daemon=True).start()

    # ----- Save -----

    def _save(self):
        if not self._result:
            return
        base    = os.path.splitext(os.path.basename(self._src_path))[0]
        default = f"{base}_sem_fundo.png"
        env     = _clean_env()
        path    = ""

        if shutil.which("zenity"):
            try:
                r = subprocess.run(
                    ["zenity", "--file-selection", "--save",
                     "--confirm-overwrite", "--title=Salvar imagem",
                     "--filename=" + default, "--file-filter=PNG | *.png"],
                    capture_output=True, text=True, env=env)
                path = r.stdout.strip()
            except Exception:
                pass
        elif shutil.which("kdialog"):
            try:
                r = subprocess.run(
                    ["kdialog", "--getsavefilename", default, "*.png|PNG"],
                    capture_output=True, text=True, env=env)
                path = r.stdout.strip()
            except Exception:
                pass
        else:
            path = filedialog.asksaveasfilename(
                title="Salvar imagem", initialfile=default,
                defaultextension=".png",
                filetypes=[("PNG com transparencia", "*.png")])

        if path:
            if not path.endswith(".png"):
                path += ".png"
            self._result.save(path)
            self._set_tip(f"\u2713 Salvo: {os.path.basename(path)}",
                          kind="ok", auto_hide_ms=self.TIP_DONE_DELAY_MS)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    splash = SplashScreen()
    splash.update()

    remove_fn      = None
    new_session_fn = None

    def _load_heavy():
        global remove_fn, new_session_fn

        splash.after(0, splash.advance, 0)
        import onnxruntime

        splash.after(0, splash.advance, 1)
        from rembg import remove, new_session
        remove_fn      = remove
        new_session_fn = new_session

        splash.after(0, splash.advance, 2)
        splash.after(0, splash.finish)
        splash.after(200, _launch)

    def _launch():
        global app
        splash.stop_tips()
        app = App(remove_fn, new_session_fn)
        app.update_idletasks()
        app.update()
        tk._default_root = app
        splash.destroy()
        app.mainloop()

    threading.Thread(target=_load_heavy, daemon=True).start()
    splash.mainloop()