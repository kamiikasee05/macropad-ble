"""Genera el icono del configurador MacropadFX (icon.ico + static/favicon.ico).

Dibuja un mini teclado 4x4 con la paleta del proyecto:
  - fondo oscuro  RGB(10, 14, 20)
  - teclas cian   RGB(0, 219, 231)
  - acento purpura RGB(235, 178, 255) (tecla superior izquierda)
  - acento verde   RGB(74, 222, 128)  (tecla inferior derecha)

Solo depende de Pillow.  Uso:  python make_icon.py
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw

BG = (10, 14, 20, 255)
CYAN = (0, 219, 231, 255)
PURPLE = (235, 178, 255, 255)
GREEN = (74, 222, 128, 255)

SIZES = [16, 24, 32, 48, 64, 128, 256]
SS = 8  # supersampling para bordes suaves


def render(size: int = 256, ss: int = SS) -> Image.Image:
    s = size * ss
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # placa redondeada oscura
    pad = int(s * 0.015)
    d.rounded_rectangle(
        [pad, pad, s - pad, s - pad], radius=int(s * 0.24), fill=BG
    )

    # grilla 4x4 de keycaps
    margin = int(s * 0.16)
    gap = int(s * 0.038)
    cell = (s - 2 * margin - 3 * gap) / 4.0
    radius = max(1, int(cell * 0.24))
    for row in range(4):
        for col in range(4):
            x0 = margin + col * (cell + gap)
            y0 = margin + row * (cell + gap)
            x1 = x0 + cell
            y1 = y0 + cell
            if row == 0 and col == 0:
                fill = PURPLE
            elif row == 3 and col == 3:
                fill = GREEN
            else:
                fill = CYAN
            d.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill)

    return img.resize((size, size), Image.LANCZOS)


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    ico = os.path.join(here, "icon.ico")
    favicon = os.path.join(here, "static", "favicon.ico")

    base = render(256)
    sizes = [(n, n) for n in SIZES]
    base.save(ico, format="ICO", sizes=sizes)

    os.makedirs(os.path.dirname(favicon), exist_ok=True)
    with open(ico, "rb") as src, open(favicon, "wb") as dst:
        dst.write(src.read())

    print(f"icon.ico     -> {ico} ({os.path.getsize(ico)} bytes)")
    print(f"favicon.ico  -> {favicon} ({os.path.getsize(favicon)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
