"""
Gera a logo do "YT-DLP Studio", inspirada no estilo visual do yt-dlp original
(prompt de terminal ">_" em preto/branco + wordmark itálico em vermelho),
mas desenhada do zero com formas e tipografia próprias.
"""
import math
from PIL import Image, ImageDraw, ImageFont

RED = (255, 0, 0, 255)             # vermelho puro #FF0000, igual ao yt-dlp original
DARK = (30, 32, 36, 255)
LIGHT = (245, 245, 245, 255)
TRANSPARENT = (0, 0, 0, 0)

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def draw_chevron_glyph(size=512, stroke_color=DARK, bg=None):
    """Desenha o glifo '>_' estilo prompt de terminal, em traços próprios
    (ângulos + barra inferior), não copiado do SVG original."""
    img = Image.new("RGBA", (size, size), bg or TRANSPARENT)
    d = ImageDraw.Draw(img)

    s = size / 512
    stroke_w = int(26 * s)

    # Chevron ">" duplo (como um prompt de shell), levemente mais largo/angular
    # que o original, para não ser um traçado idêntico.
    def chevron(x0, y0, x1, y1, width):
        p1 = (x0, y0)
        p2 = (x1, (y0 + y1) / 2)
        p3 = (x0, y1)
        d.line([p1, p2], fill=stroke_color, width=width, joint="curve")
        d.line([p2, p3], fill=stroke_color, width=width, joint="curve")
        for pt in (p1, p2, p3):
            r = width / 2
            d.ellipse([pt[0] - r, pt[1] - r, pt[0] + r, pt[1] + r], fill=stroke_color)

    chevron(120 * s, 150 * s, 250 * s, 300 * s, stroke_w)
    chevron(150 * s, 210 * s, 260 * s, 330 * s, int(stroke_w * 0.55))

    # underscore
    d.rounded_rectangle(
        [150 * s, 350 * s, 330 * s, 350 * s + stroke_w],
        radius=stroke_w / 2,
        fill=stroke_color,
    )
    return img


def make_wordmark(text="STUDIO", height=140, color=RED):
    font = ImageFont.truetype(FONT_BOLD, height)
    tmp = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(tmp)
    bbox = d.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0] + 20, bbox[3] - bbox[1] + 20
    word = Image.new("RGBA", (w, h), TRANSPARENT)
    dw = ImageDraw.Draw(word)
    dw.text((10 - bbox[0], 10 - bbox[1]), text, font=font, fill=color)

    # itálico via cisalhamento (shear), como no original, mas tipografia própria
    shear = 0.22
    new_w = w + int(h * shear)
    coeffs = (1, shear, -shear * h, 0, 1, 0)
    word = word.transform((new_w, h), Image.AFFINE, coeffs, resample=Image.BICUBIC)
    return word


def build_app_icon(size=512):
    """Icone quadrado (para .ico / janela do app): fundo escuro arredondado
    + chevron branco + barra vermelha, estilo 'app de terminal'."""
    img = Image.new("RGBA", (size, size), TRANSPARENT)
    d = ImageDraw.Draw(img)
    pad = int(size * 0.04)
    d.rounded_rectangle(
        [pad, pad, size - pad, size - pad],
        radius=int(size * 0.22),
        fill=DARK,
    )
    chevron = draw_chevron_glyph(size, stroke_color=LIGHT)
    img.alpha_composite(chevron)

    # barra vermelha inferior (referência ao underscore/red bar do original)
    bar_h = int(size * 0.07)
    y0 = int(size * 0.78)
    d.rounded_rectangle(
        [int(size * 0.24), y0, int(size * 0.76), y0 + bar_h],
        radius=bar_h // 2,
        fill=RED,
    )
    return img


def build_full_logo(glyph_color=DARK):
    """Logo horizontal completa: glifo + wordmark, para README/splash."""
    glyph = draw_chevron_glyph(220, stroke_color=glyph_color)
    word = make_wordmark("YT-DLP STUDIO", height=100, color=RED)

    pad = 20
    canvas_w = glyph.width + pad + word.width + 40
    canvas_h = max(glyph.height, word.height) + 40
    canvas = Image.new("RGBA", (canvas_w, canvas_h), TRANSPARENT)
    canvas.alpha_composite(glyph, (20, (canvas_h - glyph.height) // 2))
    canvas.alpha_composite(word, (20 + glyph.width + pad, (canvas_h - word.height) // 2))
    return canvas


if __name__ == "__main__":
    icon = build_app_icon(512)
    icon.save("assets/icon.png")
    icon.save(
        "assets/icon.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )

    logo = build_full_logo()
    logo.save("assets/logo.png")
    build_full_logo(LIGHT).save("assets/logo_dark.png")  # p/ tema escuro do GitHub

    print("OK - assets/icon.png, assets/icon.ico, assets/logo.png gerados")
