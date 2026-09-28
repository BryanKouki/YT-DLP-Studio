"""Janela de Configurações — todas as opções avançadas do yt-dlp."""
from tkinter import filedialog

import customtkinter as ctk

from theme import PRIMARY_KW


def _section_title(parent, text):
    lbl = ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=15, weight="bold"))
    lbl.pack(anchor="w", pady=(18, 6), padx=4)
    return lbl


class LabeledEntry(ctk.CTkFrame):
    def __init__(self, master, label_text, key, width=None, **kwargs):
        super().__init__(master, fg_color="transparent")
        self.key = key
        self.label = ctk.CTkLabel(self, text=label_text, anchor="w")
        self.label.pack(fill="x")
        self.entry = ctk.CTkEntry(self, **kwargs)
        if width:
            self.entry.configure(width=width)
        self.entry.pack(fill="x", pady=(2, 0))

    def get(self):
        return self.entry.get().strip()

    def set(self, value):
        self.entry.delete(0, "end")
        self.entry.insert(0, "" if value is None else str(value))

    def set_label(self, text):
        self.label.configure(text=text)


class LabeledCheck(ctk.CTkCheckBox):
    """CTkCheckBox com uma referência à chave de configuração associada.
    Não sobrescreve get()/set() (usa os métodos nativos do CTkCheckBox:
    get(), select(), deselect()) para não colidir com o uso interno que o
    próprio CustomTkinter faz desses nomes."""

    def __init__(self, master, label_text, key, **kwargs):
        super().__init__(master, text=label_text, **kwargs)
        self.key = key

    def set_checked(self, value):
        self.select() if value else self.deselect()


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.tr = app.tr
        self.settings = app.settings
        self.title(self.tr.t("settings"))
        self.geometry("560x680")
        self.minsize(480, 400)
        self.transient(app)

        self.entries = {}
        self.checks = {}
        self._section_labels = {}

        container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=16, pady=(12, 0))
        self.container = container

        self._build_folders(container)
        self._build_network(container)
        self._build_filters(container)
        self._build_behavior(container)
        self._build_extra_files(container)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=12)
        self.save_btn = ctk.CTkButton(footer, text=self.tr.t("save"), command=self._save, **PRIMARY_KW)
        self.save_btn.pack(side="right")
        self.close_btn = ctk.CTkButton(
            footer, text=self.tr.t("close"),
            fg_color=("#dbdbdb", "#3a3a3a"), hover_color=("#c8c8c8", "#484848"),
            text_color=("gray10", "gray90"), command=self.destroy,
        )
        self.close_btn.pack(side="right", padx=(0, 8))

        self._load_values()

    # -- construção das seções -------------------------------------------------------
    def _build_folders(self, c):
        self._section_labels[_section_title(c, self.tr.t("folders"))] = "folders"

        row = ctk.CTkFrame(c, fg_color="transparent")
        row.pack(fill="x", pady=4)
        row.grid_columnconfigure(0, weight=1)
        lbl = ctk.CTkLabel(row, text=self.tr.t("music_folder"), anchor="w")
        lbl.grid(row=0, column=0, sticky="w")
        self._section_labels[lbl] = "music_folder"
        self.audio_folder_entry = ctk.CTkEntry(row)
        self.audio_folder_entry.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        browse1 = ctk.CTkButton(row, text=self.tr.t("browse"), width=90,
                                 command=lambda: self._browse(self.audio_folder_entry))
        browse1.grid(row=1, column=1)
        self._section_labels[browse1] = "browse"

        row2 = ctk.CTkFrame(c, fg_color="transparent")
        row2.pack(fill="x", pady=4)
        row2.grid_columnconfigure(0, weight=1)
        lbl2 = ctk.CTkLabel(row2, text=self.tr.t("video_folder"), anchor="w")
        lbl2.grid(row=0, column=0, sticky="w")
        self._section_labels[lbl2] = "video_folder"
        self.video_folder_entry = ctk.CTkEntry(row2)
        self.video_folder_entry.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        browse2 = ctk.CTkButton(row2, text=self.tr.t("browse"), width=90,
                                 command=lambda: self._browse(self.video_folder_entry))
        browse2.grid(row=1, column=1)
        self._section_labels[browse2] = "browse"

    def _browse(self, entry):
        chosen = filedialog.askdirectory(title=self.tr.t("select_folder"), initialdir=entry.get() or None)
        if chosen:
            entry.delete(0, "end")
            entry.insert(0, chosen)

    def _build_network(self, c):
        self._section_labels[_section_title(c, self.tr.t("network"))] = "network"
        for key, label_key in (
            ("speed_limit", "speed_limit"), ("proxy", "proxy"),
            ("playlist_items", "playlist_items"), ("output_template", "filename_template"),
        ):
            e = LabeledEntry(c, self.tr.t(label_key), key)
            e.pack(fill="x", pady=4)
            self.entries[key] = e
            self._section_labels[e.label] = label_key

    def _build_filters(self, c):
        self._section_labels[_section_title(c, self.tr.t("filters"))] = "filters"
        grid = ctk.CTkFrame(c, fg_color="transparent")
        grid.pack(fill="x")
        grid.grid_columnconfigure((0, 1), weight=1)
        pairs = [
            ("date_after", "date_after"), ("date_before", "date_before"),
            ("min_filesize", "min_filesize"), ("max_filesize", "max_filesize"),
            ("min_duration", "min_duration"), ("max_duration", "max_duration"),
        ]
        for i, (key, label_key) in enumerate(pairs):
            e = LabeledEntry(grid, self.tr.t(label_key), key)
            e.grid(row=i // 2, column=i % 2, sticky="ew", padx=(0 if i % 2 == 0 else 8, 8 if i % 2 == 0 else 0), pady=4)
            self.entries[key] = e
            self._section_labels[e.label] = label_key

    def _build_behavior(self, c):
        self._section_labels[_section_title(c, self.tr.t("download_behavior"))] = "download_behavior"
        checks = [
            ("restrict_filenames", "restrict_filenames"),
            ("no_playlist", "no_playlist"),
            ("skip_downloaded", "skip_downloaded"),
            ("geo_bypass", "geo_bypass"),
            ("no_check_certificate", "no_check_cert"),
            ("force_ipv4", "force_ipv4"),
            ("write_comments", "write_comments"),
            ("live_from_start", "live_from_start"),
            ("windows_safe_names", "windows_safe_names"),
            ("no_overwrites", "no_overwrites"),
        ]
        for key, label_key in checks:
            chk = LabeledCheck(c, self.tr.t(label_key), key)
            chk.pack(anchor="w", pady=3)
            self.checks[key] = chk
            self._section_labels[chk] = label_key

        grid = ctk.CTkFrame(c, fg_color="transparent")
        grid.pack(fill="x", pady=(8, 0))
        grid.grid_columnconfigure((0, 1), weight=1)
        num_pairs = [
            ("concurrent_fragments", "concurrent_fragments"), ("retries", "retries"),
            ("fragment_retries", "fragment_retries"), ("trim_filenames", "trim_filenames"),
            ("age_limit", "age_limit"), ("sleep_interval", "sleep_interval"),
        ]
        for i, (key, label_key) in enumerate(num_pairs):
            e = LabeledEntry(grid, self.tr.t(label_key), key)
            e.grid(row=i // 2, column=i % 2, sticky="ew", padx=(0 if i % 2 == 0 else 8, 8 if i % 2 == 0 else 0), pady=4)
            self.entries[key] = e
            self._section_labels[e.label] = label_key

    def _build_extra_files(self, c):
        self._section_labels[_section_title(c, self.tr.t("extra_files"))] = "extra_files"
        checks = [
            ("embed_metadata_thumb", "embed_metadata_thumb"),
            ("embed_chapters", "embed_chapters"),
            ("split_chapters", "split_chapters"),
            ("write_description", "write_description"),
            ("write_info_json", "write_info_json"),
            ("embed_audio_tags", "embed_audio_tags"),
            ("keep_video", "keep_video"),
            ("save_folder_cover", "save_folder_cover"),
        ]
        for key, label_key in checks:
            chk = LabeledCheck(c, self.tr.t(label_key), key)
            chk.pack(anchor="w", pady=3)
            self.checks[key] = chk
            self._section_labels[chk] = label_key

        row = ctk.CTkFrame(c, fg_color="transparent")
        row.pack(fill="x", pady=(6, 20))
        row.grid_columnconfigure((0, 1), weight=1)
        e1 = LabeledEntry(row, self.tr.t("sub_langs"), "sub_langs")
        e1.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.entries["sub_langs"] = e1
        self._section_labels[e1.label] = "sub_langs"
        e2 = LabeledEntry(row, self.tr.t("sub_format"), "sub_format")
        e2.grid(row=0, column=1, sticky="ew")
        self.entries["sub_format"] = e2
        self._section_labels[e2.label] = "sub_format"

    # -- carregar/salvar ---------------------------------------------------------------
    def _load_values(self):
        self.audio_folder_entry.insert(0, self.settings.get("audio_folder", ""))
        self.video_folder_entry.insert(0, self.settings.get("video_folder", ""))
        for key, widget in self.entries.items():
            widget.set(self.settings.get(key, ""))
        for key, widget in self.checks.items():
            widget.set_checked(bool(self.settings.get(key, False)))

    def _save(self):
        self.settings.set("audio_folder", self.audio_folder_entry.get().strip() or self.settings.get("audio_folder"))
        self.settings.set("video_folder", self.video_folder_entry.get().strip() or self.settings.get("video_folder"))
        for key, widget in self.entries.items():
            self.settings.set(key, widget.get())
        for key, widget in self.checks.items():
            self.settings.set(key, bool(widget.get()))
        self.settings.save()
        self.app.on_settings_saved()
        self.destroy()
