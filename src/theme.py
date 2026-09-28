"""Paleta de cores compartilhada: preto, branco e vermelho (#FF0000), igual
à identidade visual do yt-dlp original. Usada junto com assets/theme_red.json
(que cobre os componentes padrão do CustomTkinter) para os poucos lugares
onde o código define cores explicitamente."""

RED = "#FF0000"
RED_HOVER = "#CC0000"
RED_HOVER_DARK = "#B30000"

GRAY_BTN = ("#dbdbdb", "#3a3a3a")
GRAY_BTN_HOVER = ("#c8c8c8", "#484848")
GRAY_TEXT = ("gray10", "gray90")

# Botão "fantasma" com contorno vermelho — para ações de cancelar/perigo,
# visualmente distintas dos botões vermelhos sólidos (ações primárias).
CANCEL_KW = dict(
    fg_color="transparent",
    hover_color=("#ffe0e0", "#3a1414"),
    border_width=2,
    border_color=RED,
    text_color=RED,
)

# Botão neutro (cinza) — para ações secundárias (Abrir Pasta, Limpar, etc.)
SECONDARY_KW = dict(
    fg_color=GRAY_BTN,
    hover_color=GRAY_BTN_HOVER,
    text_color=GRAY_TEXT,
)

# Botão vermelho sólido — para a ação primária de cada tela
PRIMARY_KW = dict(
    fg_color=RED,
    hover_color=RED_HOVER,
)
