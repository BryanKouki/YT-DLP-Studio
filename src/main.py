"""YT-DLP Studio — aplicativo desktop para baixar áudio/vídeo com yt-dlp."""
import os
import sys
import threading
from pathlib import Path

import customtkinter as ctk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dependencies
import downloader
from converter_tab import ConverterTab
from help_dialog import HelpDialog
from i18n import Translator
from queue_tab import QueueTab
from settings_dialog import SettingsDialog
from settings_store import SettingsStore
from tabs import AudioTab, VideoTab


def resource_path(relative: str) -> str:
    """Resolve caminho de recursos tanto em modo dev quanto empacotado
    (PyInstaller --onefile expõe os arquivos em sys._MEIPASS)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    candidate = os.path.join(base, relative)
    if os.path.exists(candidate):
        return candidate
    # fallback: pasta assets ao lado do executável/script
    alt = os.path.join(os.path.dirname(base), "assets", os.path.basename(relative))
    return alt


class MessageDialog(ctk.CTkToplevel):
    def __init__(self, master, text):
        super().__init__(master)
        self.title("")
        self.geometry("360x140")
        self.transient(master)
        ctk.CTkLabel(self, text=text, wraplength=320, justify="center").pack(expand=True, padx=16, pady=16)
        ctk.CTkButton(self, text="OK", width=100, command=self.destroy).pack(pady=(0, 16))
        self.grab_set()


class App(ctk.CTk):
    TAB_ORDER = ("audio", "video", "convert", "queue")

    def __init__(self):
        super().__init__()
        self.settings = SettingsStore()
        self.tr = Translator(self.settings.get("language", "pt"))

        ctk.set_appearance_mode("Dark" if self.settings.get("theme", "dark") == "dark" else "Light")
        ctk.set_default_color_theme(resource_path("assets/theme_red.json"))

        self.title("YT-DLP Studio")
        geo = self.settings.get("window_geometry") or "840x820"
        self.geometry(geo)
        self.minsize(720, 620)
        self._set_icon()

        self.queue = downloader.QueueManager(event_cb=None)
        self.queue.output_template_fn = self.build_output_template

        self._build_topbar()
        self._build_content()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(150, self._poll_queue_events)
        self.after(300, lambda: self.check_dependencies(initial=True))

    # ---------------------------------------------------------------- UI --
    def _set_icon(self):
        try:
            ico = resource_path("assets/icon.ico")
            if os.path.exists(ico) and os.name == "nt":
                self.iconbitmap(ico)
        except Exception:
            pass
        try:
            from PIL import Image, ImageTk
            png = resource_path("assets/icon.png")
            if os.path.exists(png):
                self._icon_img = ImageTk.PhotoImage(Image.open(png))
                self.iconphoto(True, self._icon_img)
        except Exception:
            pass

    def _build_topbar(self):
        bar = ctk.CTkFrame(self, fg_color=("gray88", "gray15"), corner_radius=0, height=48)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.segmented = ctk.CTkSegmentedButton(bar, values=self._tab_labels(), command=self._on_tab_change)
        self.segmented.set(self._tab_labels()[0])
        self.segmented.grid(row=0, column=0, padx=12, pady=8, sticky="w")

        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.grid(row=0, column=2, padx=12, pady=8, sticky="e")

        self.settings_btn = ctk.CTkButton(
            right, text="⚙", width=34, height=28, font=ctk.CTkFont(size=15),
            fg_color=("gray80", "gray25"), hover_color=("gray70", "gray32"),
            text_color=("gray10", "gray95"), command=self.open_settings,
        )
        self.settings_btn.pack(side="left", padx=3)

        self.help_btn = ctk.CTkButton(
            right, text="?", width=34, height=28, font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=("gray80", "gray25"), hover_color=("gray70", "gray32"),
            text_color=("gray10", "gray95"), command=self.open_help,
        )
        self.help_btn.pack(side="left", padx=3)

        self.theme_btn = ctk.CTkButton(
            right, text="🌙" if self.settings.get("theme") == "dark" else "☀",
            width=34, height=28, font=ctk.CTkFont(size=13),
            fg_color=("gray80", "gray25"), hover_color=("gray70", "gray32"),
            text_color=("gray10", "gray95"), command=self.toggle_theme,
        )
        self.theme_btn.pack(side="left", padx=3)

        self.lang_btn = ctk.CTkButton(
            right, text=self.tr.lang.upper(), width=34, height=28, font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("gray80", "gray25"), hover_color=("gray70", "gray32"),
            text_color=("gray10", "gray95"), command=self.toggle_language,
        )
        self.lang_btn.pack(side="left", padx=3)

    def _tab_labels(self):
        return [self.tr.t(k) for k in ("tab_audio", "tab_video", "tab_convert", "tab_queue")]

    def _build_content(self):
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.audio_tab = AudioTab(self.content, self)
        self.video_tab = VideoTab(self.content, self)
        self.convert_tab = ConverterTab(self.content, self)
        self.queue_tab = QueueTab(self.content, self)
        for frame in (self.audio_tab, self.video_tab, self.convert_tab, self.queue_tab):
            frame.grid(row=0, column=0, sticky="nsew")
        self.audio_tab.tkraise()
        self._active = "audio"

    def _on_tab_change(self, label):
        idx = self._tab_labels().index(label)
        key = self.TAB_ORDER[idx]
        self._raise_tab(key)

    def _raise_tab(self, key):
        {"audio": self.audio_tab, "video": self.video_tab, "convert": self.convert_tab,
         "queue": self.queue_tab}[key].tkraise()
        self._active = key
        self.segmented.set(self._tab_labels()[self.TAB_ORDER.index(key)])

    def select_queue_tab(self):
        self._raise_tab("queue")

    # ------------------------------------------------------------ ações --
    def toggle_theme(self):
        new_theme = "light" if self.settings.get("theme") == "dark" else "dark"
        self.settings.set("theme", new_theme)
        self.settings.save()
        ctk.set_appearance_mode("Dark" if new_theme == "dark" else "Light")
        self.theme_btn.configure(text="🌙" if new_theme == "dark" else "☀")
        self.audio_tab.range_slider.refresh_theme()
        self.video_tab.range_slider.refresh_theme()

    def toggle_language(self):
        new_lang = "en" if self.tr.lang == "pt" else "pt"
        self.tr.set_lang(new_lang)
        self.settings.set("language", new_lang)
        self.settings.save()
        self.lang_btn.configure(text=new_lang.upper())
        self.segmented.configure(values=self._tab_labels())
        self.segmented.set(self._tab_labels()[self.TAB_ORDER.index(self._active)])
        self.audio_tab.retranslate()
        self.video_tab.retranslate()
        self.convert_tab.retranslate()
        self.queue_tab.retranslate()

    def open_settings(self):
        SettingsDialog(self)

    def open_help(self):
        HelpDialog(self)

    def on_settings_saved(self):
        self.audio_tab.folder_label.configure(text=self.audio_tab._folder())
        self.video_tab.folder_label.configure(text=self.video_tab._folder())

    def show_message(self, text):
        MessageDialog(self, text)

    def _on_close(self):
        try:
            self.settings.set("window_geometry", self.geometry())
            self.settings.save()
        except Exception:
            pass
        self.destroy()

    # ------------------------------------------------------- dependências --
    def check_dependencies(self, initial=False, force=False):
        def worker():
            mgr = dependencies.DependencyManager(status_cb=self._dep_status_cb)
            if initial:
                self.queue.events.put((
                    "log",
                    {"line": f"Verificando dependências... (pasta: {dependencies.bin_dir()})"},
                ))
            mgr.ensure_all(force_reinstall=force)
        threading.Thread(target=worker, daemon=True).start()

    def update_ytdlp(self):
        def worker():
            mgr = dependencies.DependencyManager(status_cb=self._dep_status_cb)
            mgr.update_ytdlp()
        threading.Thread(target=worker, daemon=True).start()

    def _dep_status_cb(self, component, state, extra):
        # chamado de uma worker thread -> só enfileira, quem aplica na UI é o poller
        self.queue.events.put(("dep_status", {"component": component, "state": state, "extra": extra}))

    # ---------------------------------------------------------- fila/log --
    def build_output_template(self, job: downloader.Job) -> str:
        folder = job.options.get("folder") or (
            self.settings.get("audio_folder") if job.mode == "audio" else self.settings.get("video_folder")
        )
        Path(folder).mkdir(parents=True, exist_ok=True)

        if job.mode == "audio":
            # Áudio: SEMPRE só o título — nunca prefixado com artista, nem
            # quando um artista foi encontrado (auto ou digitado à mão). O
            # campo Artista continua existindo só para os metadados/ID3
            # embutidos no arquivo (ver build_command), não para o nome.
            if job.title:
                safe = job.title.replace("/", "-").replace("\\", "-")
                return str(Path(folder) / f"{safe}.%(ext)s")
            return str(Path(folder) / "%(title)s.%(ext)s")

        # Vídeo: título + nome do canal, pra diferenciar reuploads do mesmo
        # título vindos de canais diferentes. %(channel,uploader)s é
        # resolvido pelo próprio yt-dlp na hora do download (tenta o nome
        # do canal primeiro, cai para o uploader se não houver).
        return str(Path(folder) / "%(title)s - %(channel,uploader)s.%(ext)s")

    def _poll_queue_events(self):
        try:
            while True:
                kind, data = self.queue.events.get_nowait()
                self._handle_queue_event(kind, data)
        except Exception:
            pass
        finally:
            self.after(150, self._poll_queue_events)

    def _handle_queue_event(self, kind, data):
        if kind == "job_added":
            self.queue_tab.refresh_queue()
        elif kind == "job_update":
            job = data["job"]
            self.queue_tab.update_job_row(job)
            tab = self.audio_tab if job.mode == "audio" else self.video_tab
            status_key = {
                "queued": "status_queued", "downloading": "status_downloading",
                "done": "status_done", "error": "status_error", "canceled": "status_canceled",
            }.get(job.status)
            if status_key:
                if job.status == "downloading":
                    tab.set_status(job.current_label or self.tr.t(status_key))
                else:
                    label = job.title or job.url
                    tab.set_status(f"{self.tr.t(status_key)} — {label}")
            tab.set_progress(job.progress if job.status == "downloading" else (100 if job.status == "done" else 0))
        elif kind == "now_playing":
            job = data["job"]
            title = data.get("title") or job.title or job.url
            artist = (data.get("artist") or "").strip()
            idx = (data.get("idx") or "").strip()
            count = (data.get("count") or "").strip()
            label = title
            if artist:
                label = f"{label} - {artist}"
            if idx and count:
                label = f"{label} ({self.tr.t('position_of_total', idx=idx, total=count)})"
            job.current_label = label
            self.queue_tab.update_job_row(job)
            if job.status == "downloading":
                tab = self.audio_tab if job.mode == "audio" else self.video_tab
                tab.set_status(label)
            prefix = self.tr.t("status_downloading") if data.get("phase") == "start" else self.tr.t("status_done")
            self.queue_tab.append_log(f"{prefix}: {label}")
        elif kind == "log":
            self.queue_tab.append_log(data["line"])
        elif kind == "queue_finished":
            pass
        elif kind == "dep_status":
            comp, state, extra = data["component"], data["state"], data["extra"]
            row = self.queue_tab.ytdlp_status if comp == "ytdlp" else self.queue_tab.ffmpeg_status
            row.update_state(state, extra)


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
