"""Abas ÁUDIO e VÍDEO: formulário de download + fila/queue."""
import os
import queue as _queue
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

import downloader
from theme import RED, RED_HOVER, CANCEL_KW, SECONDARY_KW, PRIMARY_KW
from widgets import RangeSlider, hms_to_seconds, seconds_to_hms


def open_in_file_manager(path: str):
    path = str(path)
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


class PlaceholderTextbox(ctk.CTkTextbox):
    """CTkTextbox com texto de espaço reservado (placeholder) simples."""

    def __init__(self, master, placeholder="", **kwargs):
        super().__init__(master, **kwargs)
        self.placeholder = placeholder
        self._showing_placeholder = False
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
        self._show_placeholder()

    def _show_placeholder(self):
        self.delete("1.0", "end")
        self.insert("1.0", self.placeholder)
        self.configure(text_color=("#8a8a8a", "#8a8a8a"))
        self._showing_placeholder = True

    def _on_focus_in(self, _e):
        if self._showing_placeholder:
            self.delete("1.0", "end")
            self.configure(text_color=("gray10", "gray90"))
            self._showing_placeholder = False

    def _on_focus_out(self, _e):
        if not self.get("1.0", "end").strip():
            self._show_placeholder()

    def set_placeholder(self, text):
        self.placeholder = text
        if self._showing_placeholder:
            self.delete("1.0", "end")
            self.insert("1.0", text)

    def get_lines(self):
        if self._showing_placeholder:
            return []
        raw = self.get("1.0", "end")
        return [ln.strip() for ln in raw.splitlines() if ln.strip()]


class DownloadTabBase(ctk.CTkFrame):
    mode = "audio"

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.tr = app.tr
        self._i18n_labels = {}
        self.grid_columnconfigure(0, weight=1)

        row = 0
        self.link_box = PlaceholderTextbox(
            self, placeholder=self.tr.t("link_placeholder"), height=64, wrap="none",
        )
        self.link_box.grid(row=row, column=0, sticky="ew", padx=16, pady=(16, 8))
        row += 1

        # ---- busca automática de título/artista/duração (sem travar nada) --
        self._probe_results = _queue.Queue()
        self._probe_after_id = None
        self._probe_seq = 0
        self.link_box.bind("<KeyRelease>", self._on_link_changed, add="+")
        self.after(200, self._poll_probe_results)

        # ---- slider de recorte + campos de tempo -----------------------
        trim_frame = ctk.CTkFrame(self, fg_color="transparent")
        trim_frame.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 8))
        trim_frame.grid_columnconfigure(1, weight=1)
        row += 1

        self.start_entry = ctk.CTkEntry(trim_frame, width=100, justify="center")
        self.start_entry.insert(0, "00:00:00")
        self.start_entry.grid(row=0, column=0, padx=(0, 8))
        self.start_entry.bind("<Return>", self._on_entry_time_edit)
        self.start_entry.bind("<FocusOut>", self._on_entry_time_edit)

        self.range_slider = RangeSlider(trim_frame, max_seconds=7200, on_change=self._on_slider_change)
        self.range_slider.grid(row=0, column=1, sticky="ew")

        self.end_entry = ctk.CTkEntry(trim_frame, width=100, justify="center")
        self.end_entry.insert(0, "00:00:00")
        self.end_entry.grid(row=0, column=2, padx=(8, 0))
        self.end_entry.bind("<Return>", self._on_entry_time_edit)
        self.end_entry.bind("<FocusOut>", self._on_entry_time_edit)
        self._trim_active = False

        # ---- opções específicas do modo (áudio/vídeo) --------------------
        self.options_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.options_frame.grid(row=row, column=0, sticky="ew", padx=16, pady=(4, 8))
        self.options_frame.grid_columnconfigure((0, 1), weight=1)
        row += 1
        self.build_options_row()

        # ---- linha: abrir pasta + guardar thumbnail ------------------------
        misc_frame = ctk.CTkFrame(self, fg_color="transparent")
        misc_frame.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 4))
        row += 1
        self.open_folder_btn = ctk.CTkButton(
            misc_frame, text=self.tr.t("open_folder"), width=120,
            fg_color=("#dbdbdb", "#3a3a3a"), hover_color=("#c8c8c8", "#484848"),
            text_color=("gray10", "gray90"), command=self._open_folder,
        )
        self.open_folder_btn.pack(side="left")
        self._i18n_labels[self.open_folder_btn] = "open_folder"

        self.save_thumb_var = ctk.BooleanVar(value=self.app.settings.get(f"last_save_thumb_{self.mode}", False))
        self.save_thumb_chk = ctk.CTkCheckBox(
            misc_frame, text=self.tr.t("save_thumbnail"), variable=self.save_thumb_var,
        )
        self.save_thumb_chk.pack(side="left", padx=(12, 0))

        self.check_pl_btn = ctk.CTkButton(
            misc_frame, text=self.tr.t("check_playlist"), command=self._check_playlist, **SECONDARY_KW,
        )
        self.check_pl_btn.pack(side="right")
        self._i18n_labels[self.check_pl_btn] = "check_playlist"
        self._i18n_labels[self.save_thumb_chk] = "save_thumbnail"

        # ---- linha: pasta atual + alterar pasta -----------------------------
        folder_frame = ctk.CTkFrame(self, fg_color="transparent")
        folder_frame.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 8))
        folder_frame.grid_columnconfigure(0, weight=1)
        row += 1
        self.folder_label = ctk.CTkLabel(
            folder_frame, text=self._folder(), anchor="w",
            text_color=("gray35", "gray65"), font=ctk.CTkFont(size=12),
        )
        self.folder_label.grid(row=0, column=0, sticky="w")
        self.change_folder_btn = ctk.CTkButton(
            folder_frame, text=self.tr.t("change_folder"), width=1, height=20,
            fg_color="transparent", hover_color=("#e5e5e5", "#333333"),
            text_color=RED, font=ctk.CTkFont(size=12, underline=True),
            command=self._change_folder,
        )
        self.change_folder_btn.grid(row=0, column=1, sticky="e")
        self._i18n_labels[self.change_folder_btn] = "change_folder"

        # ---- botões de download / fila ------------------------------------
        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 8))
        action_frame.grid_columnconfigure(0, weight=1)
        row += 1
        self.download_btn = ctk.CTkButton(
            action_frame, text=self.tr.t("download"), height=42,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._on_download_now, **PRIMARY_KW,
        )
        self.download_btn.grid(row=0, column=0, sticky="ew")
        self._i18n_labels[self.download_btn] = "download"

        self.queue_btn = ctk.CTkButton(
            action_frame, text="+≡", width=42, height=42,
            font=ctk.CTkFont(size=17, weight="bold"),
            command=self._on_add_to_queue, **SECONDARY_KW,
        )
        self.queue_btn.grid(row=0, column=1, padx=(8, 0))

        # ---- status + cancelar + barra de progresso ------------------------
        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.grid(row=row, column=0, sticky="ew", padx=16, pady=(4, 0))
        status_frame.grid_columnconfigure(0, weight=1)
        row += 1
        self.status_label = ctk.CTkLabel(status_frame, text=self.tr.t("ready"), anchor="w")
        self.status_label.grid(row=0, column=0, sticky="w")
        self.cancel_btn = ctk.CTkButton(
            status_frame, text=self.tr.t("cancel_current"),
            width=160, command=lambda: self.app.queue.cancel_current(), **CANCEL_KW,
        )
        self.cancel_btn.grid(row=0, column=1, sticky="e")
        self._i18n_labels[self.cancel_btn] = "cancel_current"

        self.progress_bar = ctk.CTkProgressBar(self, height=10, corner_radius=0)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=row, column=0, sticky="ew", padx=16, pady=(6, 16))
        row += 1

        spacer = ctk.CTkFrame(self, fg_color="transparent", height=1)
        spacer.grid(row=row, column=0, sticky="nsew")
        self.grid_rowconfigure(row, weight=1)

    # -- helpers ------------------------------------------------------------
    def _folder(self):
        key = "audio_folder" if self.mode == "audio" else "video_folder"
        return self.app.settings.get(key)

    def _open_folder(self):
        Path(self._folder()).mkdir(parents=True, exist_ok=True)
        open_in_file_manager(self._folder())

    def _change_folder(self):
        chosen = filedialog.askdirectory(title=self.tr.t("select_folder"), initialdir=self._folder())
        if chosen:
            key = "audio_folder" if self.mode == "audio" else "video_folder"
            self.app.settings.set(key, chosen)
            self.app.settings.save()
            self.folder_label.configure(text=chosen)

    def _on_slider_change(self, start_s, end_s):
        self.start_entry.delete(0, "end")
        self.start_entry.insert(0, seconds_to_hms(start_s))
        self.end_entry.delete(0, "end")
        self.end_entry.insert(0, seconds_to_hms(end_s))
        self._trim_active = start_s > 0 or end_s < self.range_slider.max_seconds

    def _on_entry_time_edit(self, _event=None):
        start_s = hms_to_seconds(self.start_entry.get())
        end_s = hms_to_seconds(self.end_entry.get())
        if end_s == 0:
            end_s = self.range_slider.max_seconds
        self.range_slider.set_values(start_s, end_s)
        self._trim_active = start_s > 0 or end_s < self.range_slider.max_seconds

    # -- busca automática de título/artista/duração ao colar um link -------
    # Roda em segundo plano (thread + fila, nunca mexendo na UI direto de
    # uma thread) com um pequeno atraso após o usuário parar de digitar, e
    # NUNCA impede o botão de Download de ser usado antes de terminar.
    def _on_link_changed(self, _event=None):
        if self._probe_after_id is not None:
            try:
                self.after_cancel(self._probe_after_id)
            except Exception:
                pass
        self._probe_after_id = self.after(900, self._start_probe)

    def _start_probe(self):
        self._probe_after_id = None
        urls = self._urls()
        # só busca quando há exatamente UM link — com vários links coladas
        # de uma vez, preencher título/artista/duração do primeiro aplicaria
        # esses dados errado nos outros (título/artista/recorte valem pra
        # todos os itens de uma leva, ver _make_jobs)
        if len(urls) != 1:
            return
        self._probe_seq += 1
        seq = self._probe_seq
        threading.Thread(target=self._probe_worker, args=(urls[0], seq), daemon=True).start()

    def _probe_worker(self, url, seq):
        title, artist, duration = downloader.probe_media_info(url)
        self._probe_results.put((seq, title, artist, duration))

    def _poll_probe_results(self):
        try:
            while True:
                seq, title, artist, duration = self._probe_results.get_nowait()
                if seq == self._probe_seq:  # descarta resultado de um link já trocado
                    self._apply_probe_result(title, artist, duration)
        except _queue.Empty:
            pass
        finally:
            self.after(200, self._poll_probe_results)

    def _apply_probe_result(self, title, artist, duration):
        if duration and duration > 0:
            self.range_slider.max_seconds = duration
            self.range_slider.set_values(0, duration)
            self.start_entry.delete(0, "end")
            self.start_entry.insert(0, "00:00:00")
            self.end_entry.delete(0, "end")
            self.end_entry.insert(0, seconds_to_hms(duration))
            self._trim_active = False

    def _check_playlist(self):
        urls = self._urls()
        if not urls:
            self.app.show_message(self.tr.t("no_link_error"))
            return
        emit = lambda line: self.app.queue.events.put(("log", {"line": line}))  # fila thread-safe
        threading.Thread(target=downloader.check_playlist, args=(urls[0], emit), daemon=True).start()
        self.app.select_queue_tab()

    def build_options_row(self):
        raise NotImplementedError

    def gather_tab_options(self):
        raise NotImplementedError

    def _urls(self):
        return self.link_box.get_lines()

    def _trim_values(self):
        if not self._trim_active:
            return "", ""
        return self.start_entry.get().strip(), self.end_entry.get().strip()

    def _make_jobs(self):
        urls = self._urls()
        if not urls:
            self.app.show_message(self.tr.t("no_link_error"))
            return []
        tab_opts = self.gather_tab_options()
        start_s, end_s = self._trim_values()
        folder = self._folder()
        jobs = []
        for url in urls:
            options = dict(self.app.settings.data)
            options.update(tab_opts)
            options["folder"] = folder
            options["trim_start"] = start_s
            options["trim_end"] = end_s
            options["save_thumbnail"] = bool(self.save_thumb_var.get())
            job = downloader.Job(
                id=downloader.new_job_id(), mode=self.mode, url=url,
                title=tab_opts.get("title", "") if self.mode == "audio" else "",
                artist=tab_opts.get("artist", "") if self.mode == "audio" else "",
                options=options,
            )
            jobs.append(job)
        self.app.settings.set(f"last_save_thumb_{self.mode}", bool(self.save_thumb_var.get()))
        self.app.settings.save()
        return jobs

    def _on_download_now(self):
        jobs = self._make_jobs()
        if not jobs:
            return
        for j in jobs:
            self.app.queue.add_job(j)
        self.app.queue.start()
        self.app.select_queue_tab()

    def _on_add_to_queue(self):
        jobs = self._make_jobs()
        if not jobs:
            return
        for j in jobs:
            self.app.queue.add_job(j)
        self.app.select_queue_tab()

    def retranslate(self):
        for widget, key in self._i18n_labels.items():
            try:
                widget.configure(text=self.tr.t(key))
            except Exception:
                pass
        self.link_box.set_placeholder(self.tr.t("link_placeholder"))
        self.folder_label.configure(text=self._folder())

    def set_status(self, text):
        self.status_label.configure(text=text)

    def set_progress(self, pct):
        self.progress_bar.set(max(0.0, min(1.0, pct / 100.0)))


class AudioTab(DownloadTabBase):
    mode = "audio"

    AUDIO_FORMATS_TECH = ["MP3", "M4A", "AAC", "Opus", "Vorbis", "FLAC", "ALAC", "WAV"]
    QUALITIES = ["320 kbps", "256 kbps", "224 kbps", "192 kbps", "160 kbps",
                 "128 kbps", "96 kbps", "64 kbps", "32 kbps"]

    def build_options_row(self):
        f = self.options_frame
        self.fmt_label = ctk.CTkLabel(f, text=self.tr.t("format"), anchor="w")
        self.fmt_label.grid(row=0, column=0, sticky="w", pady=(0, 2))
        self._i18n_labels[self.fmt_label] = "format"
        self.fmt_menu = ctk.CTkOptionMenu(f, values=self._format_values())
        self.fmt_menu.set(self._match_or_default(
            self.app.settings.get("last_audio_format", "MP3"), self._format_values(), "MP3"))
        self.fmt_menu.grid(row=1, column=0, sticky="ew", padx=(0, 8))

        self.quality_label = ctk.CTkLabel(f, text=self.tr.t("quality"), anchor="w")
        self.quality_label.grid(row=2, column=0, sticky="w", pady=(8, 2))
        self._i18n_labels[self.quality_label] = "quality"
        self.quality_menu = ctk.CTkOptionMenu(f, values=self.QUALITIES)
        self.quality_menu.set(self.app.settings.get("last_audio_quality", "320 kbps"))
        self.quality_menu.grid(row=3, column=0, sticky="ew", padx=(0, 8))

        self.title_label = ctk.CTkLabel(f, text=self.tr.t("title"), anchor="w")
        self.title_label.grid(row=0, column=1, sticky="w", pady=(0, 2))
        self._i18n_labels[self.title_label] = "title"
        self.title_entry = ctk.CTkEntry(f)
        self.title_entry.grid(row=1, column=1, sticky="ew")

        self.artist_label = ctk.CTkLabel(f, text=self.tr.t("artist"), anchor="w")
        self.artist_label.grid(row=2, column=1, sticky="w", pady=(8, 2))
        self._i18n_labels[self.artist_label] = "artist"
        self.artist_entry = ctk.CTkEntry(f)
        self.artist_entry.grid(row=3, column=1, sticky="ew")

    def _format_values(self):
        return [self.tr.t("best_available")] + self.AUDIO_FORMATS_TECH

    @staticmethod
    def _match_or_default(value, options, fallback):
        return value if value in options else fallback

    def gather_tab_options(self):
        self.app.settings.set("last_audio_format", self.fmt_menu.get())
        self.app.settings.set("last_audio_quality", self.quality_menu.get())
        return {
            "format": self.fmt_menu.get(),
            "quality": self.quality_menu.get(),
            "title": self.title_entry.get().strip(),
            "artist": self.artist_entry.get().strip(),
        }

    def retranslate(self):
        super().retranslate()
        self.fmt_menu.configure(values=self._format_values())
        self.quality_menu.configure(values=self.QUALITIES)

    def _apply_probe_result(self, title, artist, duration):
        super()._apply_probe_result(title, artist, duration)
        if title and not self.title_entry.get().strip():
            self.title_entry.insert(0, title)
        if artist and not self.artist_entry.get().strip():
            self.artist_entry.insert(0, artist)


class VideoTab(DownloadTabBase):
    mode = "video"

    VCODECS_TECH = ["H.264 (AVC)", "H.265 (HEVC)", "VP9", "AV1", "VP8"]
    ACODECS_TECH = ["AAC", "Opus", "MP3", "FLAC"]
    RESOLUTIONS_TECH = ["4320p (8K)", "2160p (4K)", "1440p (2K)", "1080p",
                        "720p", "480p", "360p", "240p", "144p"]
    FPS_TECH = ["60 fps", "30 fps", "24 fps"]

    def build_options_row(self):
        f = self.options_frame

        self.res_label = ctk.CTkLabel(f, text=self.tr.t("resolution"), anchor="w")
        self.res_label.grid(row=0, column=0, sticky="w", pady=(0, 2))
        self._i18n_labels[self.res_label] = "resolution"
        self.res_menu = ctk.CTkOptionMenu(f, values=self._res_values())
        self.res_menu.set(self._match_or_default(
            self.app.settings.get("last_resolution", "1080p"), self._res_values(), "1080p"))
        self.res_menu.grid(row=1, column=0, sticky="ew", padx=(0, 8))

        self.fps_label = ctk.CTkLabel(f, text=self.tr.t("fps"), anchor="w")
        self.fps_label.grid(row=0, column=1, sticky="w", pady=(0, 2))
        self._i18n_labels[self.fps_label] = "fps"
        self.fps_menu = ctk.CTkOptionMenu(f, values=self._fps_values())
        self.fps_menu.set(self._match_or_default(
            self.app.settings.get("last_fps", self.tr.t("best_available")), self._fps_values(), self.tr.t("best_available")))
        self.fps_menu.grid(row=1, column=1, sticky="ew")

        self.vcodec_label = ctk.CTkLabel(f, text=self.tr.t("video_codec"), anchor="w")
        self.vcodec_label.grid(row=2, column=0, sticky="w", pady=(8, 2))
        self._i18n_labels[self.vcodec_label] = "video_codec"
        self.vcodec_menu = ctk.CTkOptionMenu(f, values=self._vcodec_values())
        self.vcodec_menu.set(self._match_or_default(
            self.app.settings.get("last_vcodec", "H.264 (AVC)"), self._vcodec_values(), "H.264 (AVC)"))
        self.vcodec_menu.grid(row=3, column=0, sticky="ew", padx=(0, 8))

        self.acodec_label = ctk.CTkLabel(f, text=self.tr.t("audio_codec"), anchor="w")
        self.acodec_label.grid(row=2, column=1, sticky="w", pady=(8, 2))
        self._i18n_labels[self.acodec_label] = "audio_codec"
        self.acodec_menu = ctk.CTkOptionMenu(f, values=self._acodec_values())
        self.acodec_menu.set(self._match_or_default(
            self.app.settings.get("last_acodec", "AAC"), self._acodec_values(), "AAC"))
        self.acodec_menu.grid(row=3, column=1, sticky="ew")

        self.container_label = ctk.CTkLabel(f, text=self.tr.t("container"), anchor="w")
        self.container_label.grid(row=4, column=0, sticky="w", pady=(8, 2))
        self._i18n_labels[self.container_label] = "container"
        self.container_menu = ctk.CTkOptionMenu(f, values=self._container_values())
        self.container_menu.set(self._match_or_default(
            self.app.settings.get("last_container", self.tr.t("automatic")), self._container_values(), self.tr.t("automatic")))
        self.container_menu.grid(row=5, column=0, sticky="ew", padx=(0, 8))

        self.subs_var = ctk.BooleanVar(value=self.app.settings.get("last_subtitles", False))
        self.subs_chk = ctk.CTkCheckBox(f, text=self.tr.t("subtitles"), variable=self.subs_var)
        self.subs_chk.grid(row=5, column=1, sticky="w")
        self._i18n_labels[self.subs_chk] = "subtitles"

    def _res_values(self):
        return [self.tr.t("best_available")] + self.RESOLUTIONS_TECH

    def _fps_values(self):
        return [self.tr.t("best_available")] + self.FPS_TECH

    def _vcodec_values(self):
        return [self.tr.t("best_any")] + self.VCODECS_TECH

    def _acodec_values(self):
        return [self.tr.t("best_any")] + self.ACODECS_TECH

    def _container_values(self):
        return [self.tr.t("automatic"), self.tr.t("force_mp4"), self.tr.t("force_mkv")]

    @staticmethod
    def _match_or_default(value, options, fallback):
        return value if value in options else fallback

    def gather_tab_options(self):
        self.app.settings.set("last_resolution", self.res_menu.get())
        self.app.settings.set("last_fps", self.fps_menu.get())
        self.app.settings.set("last_vcodec", self.vcodec_menu.get())
        self.app.settings.set("last_acodec", self.acodec_menu.get())
        self.app.settings.set("last_container", self.container_menu.get())
        self.app.settings.set("last_subtitles", bool(self.subs_var.get()))
        return {
            "resolution": self.res_menu.get(),
            "fps": self.fps_menu.get(),
            "vcodec": self.vcodec_menu.get(),
            "acodec": self.acodec_menu.get(),
            "container": self.container_menu.get(),
            "subtitles": bool(self.subs_var.get()),
        }

    def retranslate(self):
        super().retranslate()
        self.res_menu.configure(values=self._res_values())
        self.fps_menu.configure(values=self._fps_values())
        self.vcodec_menu.configure(values=self._vcodec_values())
        self.acodec_menu.configure(values=self._acodec_values())
        self.container_menu.configure(values=self._container_values())
