"""Widgets pequenos e reutilizáveis usados nas abas de download."""
import tkinter as tk

import customtkinter as ctk

from theme import RED


def seconds_to_hms(total_seconds: int) -> str:
    total_seconds = max(0, int(total_seconds))
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def hms_to_seconds(text: str) -> int:
    parts = text.strip().split(":")
    try:
        parts = [int(p) for p in parts]
    except ValueError:
        return 0
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, s = parts[-3:]
    return h * 3600 + m * 60 + s


class RangeSlider(ctk.CTkFrame):
    """Slider com dois cabos (início/fim) para selecionar um trecho de
    tempo, desenhado com Canvas (CustomTkinter não tem range-slider nativo)."""

    HANDLE_R = 8

    def __init__(self, master, max_seconds=7200, on_change=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.max_seconds = max_seconds
        self.on_change = on_change
        self.start_val = 0
        self.end_val = max_seconds
        self._drag = None

        track_color = self._apply_appearance_mode(("#c9c9c9", "#3a3a3a"))
        self.canvas = tk.Canvas(self, height=28, highlightthickness=0,
                                 bg=self._apply_appearance_mode(self._fg_color_of_parent()))
        self.canvas.pack(fill="x", expand=True, padx=4)
        self.canvas.bind("<Configure>", lambda e: self._redraw())
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self._track_color = track_color

    def _fg_color_of_parent(self):
        widget = self.master
        for _ in range(6):
            try:
                color = widget.cget("fg_color")
            except Exception:
                color = None
            if color and color != "transparent":
                if isinstance(color, (list, tuple)):
                    return color[0] if ctk.get_appearance_mode() == "Light" else color[1]
                return color
            widget = getattr(widget, "master", None)
            if widget is None:
                break
        return "#dbdbdb" if ctk.get_appearance_mode() == "Light" else "#242424"

    def _x_to_val(self, x):
        w = max(self.canvas.winfo_width(), 1)
        pad = self.HANDLE_R + 2
        ratio = min(max((x - pad) / max(w - 2 * pad, 1), 0), 1)
        return int(ratio * self.max_seconds)

    def _val_to_x(self, val):
        w = max(self.canvas.winfo_width(), 1)
        pad = self.HANDLE_R + 2
        ratio = val / self.max_seconds if self.max_seconds else 0
        return pad + ratio * (w - 2 * pad)

    def _on_click(self, event):
        xs = self._val_to_x(self.start_val)
        xe = self._val_to_x(self.end_val)
        self._drag = "start" if abs(event.x - xs) <= abs(event.x - xe) else "end"
        self._on_drag(event)

    def _on_drag(self, event):
        if not self._drag:
            return
        val = self._x_to_val(event.x)
        if self._drag == "start":
            self.start_val = min(val, self.end_val)
        else:
            self.end_val = max(val, self.start_val)
        self._redraw()
        if self.on_change:
            self.on_change(self.start_val, self.end_val)

    def _on_release(self, _event):
        self._drag = None

    def set_values(self, start_s, end_s):
        self.start_val = max(0, min(start_s, self.max_seconds))
        self.end_val = max(0, min(end_s, self.max_seconds))
        self._redraw()

    def refresh_theme(self):
        """Recalcula a cor de fundo do canvas para o modo de aparência atual.
        Necessário porque tk.Canvas é um widget Tk puro (não CTk) e por isso
        não se atualiza sozinho quando o tema claro/escuro é alternado em
        tempo de execução — sem isso, o fundo fica 'preso' na cor de quando
        o slider foi criado."""
        self.canvas.configure(bg=self._apply_appearance_mode(self._fg_color_of_parent()))
        self._track_color = self._apply_appearance_mode(("#c9c9c9", "#3a3a3a"))
        self._redraw()

    def _redraw(self):
        c = self.canvas
        c.delete("all")
        w = max(c.winfo_width(), 1)
        y = 14
        pad = self.HANDLE_R + 2
        c.create_line(pad, y, w - pad, y, fill=self._track_color, width=4, capstyle="round")
        xs = self._val_to_x(self.start_val)
        xe = self._val_to_x(self.end_val)
        c.create_line(xs, y, xe, y, fill=RED, width=4, capstyle="round")
        for val_x in (xs, xe):
            c.create_oval(
                val_x - self.HANDLE_R, y - self.HANDLE_R,
                val_x + self.HANDLE_R, y + self.HANDLE_R,
                fill="#e5e5e5", outline=RED,
            )
