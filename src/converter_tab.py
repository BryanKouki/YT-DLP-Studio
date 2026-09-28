"""Aba CONVERTER: converte/comprime arquivos locais com o ffmpeg que o app já baixa."""
import queue
import re
import subprocess
import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

import dependencies
from downloader import NO_WINDOW
from tabs import open_in_file_manager
from theme import CANCEL_KW, PRIMARY_KW, SECONDARY_KW

# formato -> (extensão, argumentos do codec, bitrate por qualidade Alta/Média/Baixa; None = sem perdas)
AUDIO = {
    "MP3": ("mp3", ["-c:a", "libmp3lame"], ["320k", "192k", "128k"]),
    "M4A (AAC)": ("m4a", ["-c:a", "aac"], ["256k", "192k", "128k"]),
    "Opus": ("opus", ["-c:a", "libopus"], ["192k", "128k", "96k"]),
    "FLAC": ("flac", ["-c:a", "flac"], None),
    "WAV": ("wav", ["-c:a", "pcm_s16le"], None),
}
# formato -> (extensão, argumentos, CRF por qualidade Alta/Média/Baixa — maior = menor arquivo)
VIDEO = {
    "MP4 (H.264)": ("mp4", ["-c:v", "libx264", "-preset", "medium", "-c:a", "aac", "-b:a", "192k"], ["18", "23", "28"]),
    "MKV (H.265)": ("mkv", ["-c:v", "libx265", "-preset", "medium", "-c:a", "aac", "-b:a", "192k"], ["20", "26", "32"]),
    "WEBM (VP9)": ("webm", ["-c:v", "libvpx-vp9", "-b:v", "0", "-c:a", "libopus", "-b:a", "128k"], ["28", "34", "40"]),
}
RESOLUTIONS = ["Original", "1080p", "720p", "480p", "360p"]
QUALITY_KEYS = ["q_high", "q_medium", "q_low"]

DUR_RE = re.compile(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)")
TIME_RE = re.compile(r"out_time_us=(\d+)")


def probe_duration(src):
    """Duração em segundos via ffprobe (0 se não der pra ler)."""
    r = subprocess.run([str(dependencies.ffprobe_path()), "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(src)], capture_output=True, text=True, creationflags=NO_WINDOW)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def build_ffmpeg_cmd(src, fmt, quality, res, target_bytes=0, duration=0.0):
    """Monta o comando ffmpeg. quality: 0=Alta, 1=Média, 2=Baixa. Com target_bytes
    (compressor), a qualidade é ignorada e o bitrate sai do tamanho alvo / duração.
    Retorna (cmd, arquivo_saida); ValueError se o alvo não for possível."""
    # ponytail: 1 passagem com teto de bitrate; tamanho fica perto do alvo (±~5%), 2-pass se precisar exato
    kbps = target_bytes * 8 / duration / 1000 * 0.97 if target_bytes else 0  # 3% de folga p/ contêiner
    if fmt in AUDIO:
        ext, codec, rates = AUDIO[fmt]
        if kbps and not rates:
            raise ValueError(f"{fmt} é sem perdas: tamanho alvo não se aplica.")
        rate = f"{min(int(kbps), 320)}k" if kbps else (rates[quality] if rates else None)
        args = ["-vn", *codec] + (["-b:a", rate] if rate else [])
    else:
        ext, codec, crfs = VIDEO[fmt]
        if kbps:
            audio_k = int(codec[codec.index("-b:a") + 1].rstrip("k"))
            vk = int(kbps - audio_k)
            if vk < 100:
                raise ValueError(f"Tamanho alvo pequeno demais pra {duration:.0f}s de vídeo "
                                 f"(daria {max(vk, 0)} kbps de vídeo).")
            # -b:v no fim sobrescreve o '-b:v 0' do VP9 (no ffmpeg vale a última opção)
            args = [*codec, "-b:v", f"{vk}k", "-maxrate", f"{vk}k", "-bufsize", f"{vk * 2}k"]
        else:
            args = [*codec, "-crf", crfs[quality]]
        if res != "Original":  # só reduz, nunca aumenta a resolução
            args += ["-vf", f"scale=-2:'min(ih,{res[:-1]})'"]
    out = Path(src).with_name(f"{Path(src).stem}_convertido.{ext}")
    cmd = [str(dependencies.ffmpeg_path()), "-hide_banner", "-y", "-i", str(src), *args,
           "-progress", "pipe:1", "-nostats", str(out)]
    return cmd, out


class ConverterTab(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app, self.tr = app, app.tr
        self._labels = {}
        self._q = queue.Queue()
        self._proc = None
        self._canceled = False
        self._last_out = None
        self.grid_columnconfigure((0, 1), weight=1)

        def label(key, row, col):
            w = ctk.CTkLabel(self, text=self.tr.t(key), anchor="w")
            w.grid(row=row, column=col, sticky="w", padx=16 if col == 0 else (0, 16), pady=(10, 2))
            self._labels[w] = key

        label("conv_file", 0, 0)
        self.file_entry = ctk.CTkEntry(self)
        self.file_entry.grid(row=1, column=0, sticky="ew", padx=(16, 8))
        self.pick_btn = ctk.CTkButton(self, text=self.tr.t("browse"), command=self._pick, **SECONDARY_KW)
        self.pick_btn.grid(row=1, column=1, sticky="w")
        self._labels[self.pick_btn] = "browse"

        label("format", 2, 0)
        label("conv_quality", 2, 1)
        self.fmt_menu = ctk.CTkOptionMenu(self, values=[*AUDIO, *VIDEO])
        self.fmt_menu.grid(row=3, column=0, sticky="ew", padx=(16, 8))
        self._qidx = 1  # Média
        self.quality_menu = ctk.CTkOptionMenu(
            self, values=self._quality_values(),
            command=lambda v: setattr(self, "_qidx", self._quality_values().index(v)))
        self.quality_menu.set(self._quality_values()[self._qidx])
        self.quality_menu.grid(row=3, column=1, sticky="ew", padx=(0, 16))

        label("resolution", 4, 0)
        self.res_menu = ctk.CTkOptionMenu(self, values=RESOLUTIONS)
        self.res_menu.grid(row=5, column=0, sticky="ew", padx=(16, 8))

        label("conv_target", 4, 1)
        size_row = ctk.CTkFrame(self, fg_color="transparent")
        size_row.grid(row=5, column=1, sticky="ew", padx=(0, 16))
        size_row.grid_columnconfigure(0, weight=1)
        self.size_entry = ctk.CTkEntry(size_row)
        self.size_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.unit_menu = ctk.CTkOptionMenu(size_row, values=["MB", "GB"], width=70)
        self.unit_menu.grid(row=0, column=1)

        self.start_btn = ctk.CTkButton(self, text=self.tr.t("conv_start"), height=42,
                                       font=ctk.CTkFont(size=15, weight="bold"), command=self._start, **PRIMARY_KW)
        self.start_btn.grid(row=6, column=0, columnspan=2, sticky="ew", padx=16, pady=(18, 8))
        self._labels[self.start_btn] = "conv_start"

        self.status = ctk.CTkLabel(self, text=self.tr.t("ready"), anchor="w")
        self.status.grid(row=7, column=0, sticky="w", padx=16)
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=7, column=1, sticky="e", padx=16)
        self.open_btn = ctk.CTkButton(btns, text=self.tr.t("open_folder"), width=110,
                                      command=self._open_folder, **SECONDARY_KW)
        self.open_btn.pack(side="left", padx=(0, 8))
        self._labels[self.open_btn] = "open_folder"
        self.cancel_btn = ctk.CTkButton(btns, text=self.tr.t("cancel"), command=self._cancel, **CANCEL_KW)
        self.cancel_btn.pack(side="left")
        self._labels[self.cancel_btn] = "cancel"

        self.progress = ctk.CTkProgressBar(self, height=10, corner_radius=0)
        self.progress.set(0)
        self.progress.grid(row=8, column=0, columnspan=2, sticky="ew", padx=16, pady=(6, 16))
        self.after(200, self._poll)

    def _quality_values(self):
        return [self.tr.t(k) for k in QUALITY_KEYS]

    def _pick(self):
        path = filedialog.askopenfilename()
        if path:
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, path)

    def _open_folder(self):
        src = self.file_entry.get().strip()
        if src:
            open_in_file_manager(Path(src).parent)

    def _start(self):
        src = self.file_entry.get().strip()
        if self._proc:
            return
        if not src or not Path(src).is_file():
            self.app.show_message(self.tr.t("conv_no_file"))
            return
        if not dependencies.ffmpeg_path().exists():
            self.app.show_message(self.tr.t("conv_no_ffmpeg"))
            return
        raw = self.size_entry.get().strip().replace(",", ".")
        try:
            size = float(raw) if raw else 0.0
        except ValueError:
            size = -1
        if size < 0:
            self.app.show_message(self.tr.t("conv_bad_size"))
            return
        target = int(size * 1024 ** (3 if self.unit_menu.get() == "GB" else 2))
        params = (src, self.fmt_menu.get(), self._qidx, self.res_menu.get(), target)
        self._canceled = False
        self.progress.set(0)
        self.status.configure(text=self.tr.t("conv_running"))
        threading.Thread(target=self._worker, args=params, daemon=True).start()

    def _worker(self, src, fmt, quality, res, target):
        try:
            duration = probe_duration(src) if target else 0.0
            if target and not duration:
                raise ValueError("Não foi possível ler a duração do arquivo.")
            cmd, out = build_ffmpeg_cmd(src, fmt, quality, res, target, duration)
        except ValueError as e:
            self._q.put(("done", False, str(e)))
            return
        self.app.queue.events.put(("log", {"line": "$ " + " ".join(cmd)}))
        total = 0.0
        try:
            self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                          encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
        except OSError as e:
            self._q.put(("done", False, str(e)))
            return
        tail = []
        for line in self._proc.stdout:
            tail = (tail + [line.rstrip()])[-5:]  # guarda o fim pra mostrar erro no Log
            if not total and (m := DUR_RE.search(line)):
                h, mi, s = m.groups()
                total = int(h) * 3600 + int(mi) * 60 + float(s)
            elif total and (m := TIME_RE.search(line)):
                self._q.put(("progress", int(m.group(1)) / 1e6 / total))
        ok = self._proc.wait() == 0
        self._proc = None
        if not ok:
            out.unlink(missing_ok=True)  # não deixa arquivo pela metade
        self._q.put(("done", ok, str(out) if ok else "\n".join(tail)))

    def _cancel(self):
        if self._proc:
            self._canceled = True
            self._proc.terminate()

    def _poll(self):
        try:
            while True:
                kind, *data = self._q.get_nowait()
                if kind == "progress":
                    self.progress.set(min(1.0, data[0]))
                else:
                    ok, info = data
                    self.progress.set(1.0 if ok else 0)
                    if ok:
                        self.status.configure(text=self.tr.t("conv_done", name=Path(info).name))
                    elif self._canceled:
                        self.status.configure(text=self.tr.t("status_canceled"))
                    else:
                        self.status.configure(text=self.tr.t("conv_error"))
                        self.app.queue.events.put(("log", {"line": "[erro ffmpeg] " + info}))
        except queue.Empty:
            pass
        self.after(200, self._poll)

    def retranslate(self):
        for w, key in self._labels.items():
            w.configure(text=self.tr.t(key))
        self.quality_menu.configure(values=self._quality_values())
        self.quality_menu.set(self._quality_values()[self._qidx])
