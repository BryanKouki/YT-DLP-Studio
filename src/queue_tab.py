"""Aba 'Fila e Log': status de dependências, fila de downloads e log."""
import datetime

import customtkinter as ctk

import dependencies
from tabs import open_in_file_manager
from theme import RED, RED_HOVER, CANCEL_KW, SECONDARY_KW, PRIMARY_KW

DOT_COLORS = {
    "ok": "#22c55e", "downloading": "#f59e0b", "checking": "#f59e0b",
    "installing": "#f59e0b", "error": "#ef4444", "missing": "#9ca3af",
}

STATUS_BAR_COLORS = {
    "queued": ("gray70", "gray40"),
    "downloading": (RED, RED),
    "done": ("#22c55e", "#22c55e"),
    "error": ("#ef4444", "#ef4444"),
    "canceled": ("gray70", "gray40"),
}


class DepStatusRow(ctk.CTkFrame):
    def __init__(self, master, tr, key_label):
        super().__init__(master, fg_color="transparent")
        self.tr = tr
        self.key_label = key_label
        self.dot = ctk.CTkLabel(self, text="●", text_color=DOT_COLORS["missing"], width=14)
        self.dot.pack(side="left")
        self.label = ctk.CTkLabel(self, text=f"{tr.t(key_label)} {tr.t('dep_missing')}")
        self.label.pack(side="left", padx=(2, 0))
        self._last_state = "missing"
        self._last_extra = {}

    def update_state(self, state, extra=None):
        extra = extra or {}
        self._last_state, self._last_extra = state, extra
        self.dot.configure(text_color=DOT_COLORS.get(state, "#9ca3af"))
        if state == "ok":
            text = self.tr.t("dep_ok")
        elif state == "downloading":
            pct = extra.get("pct")
            base = self.tr.t("dep_downloading", size=extra.get("size", ""))
            text = f"{base} {pct}%" if pct is not None else base
        elif state == "checking":
            text = self.tr.t("dep_checking")
        elif state == "installing":
            text = self.tr.t("dep_installing")
        elif state == "error":
            text = self.tr.t("dep_error")
        else:
            text = self.tr.t("dep_missing")
        self.label.configure(text=f"{self.tr.t(self.key_label)} {text}")

    def retranslate(self):
        self.update_state(self._last_state, self._last_extra)


class QueueRow(ctk.CTkFrame):
    def __init__(self, master, app, job, index, total):
        super().__init__(master, fg_color=("gray92", "gray20"), corner_radius=8)
        self.app = app
        self.job = job
        self.grid_columnconfigure(0, weight=1)

        title = job.title or job.url
        subtitle = f" - {job.artist}" if job.artist else ""
        self.name_label = ctk.CTkLabel(
            self, text=f"{title}{subtitle} ({index} de {total})", anchor="w",
        )
        self.name_label.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 0))

        self.status_label = ctk.CTkLabel(self, text="", anchor="w", text_color=("gray40", "gray60"),
                                          font=ctk.CTkFont(size=11))
        self.status_label.grid(row=1, column=0, sticky="ew", padx=10)

        self.cancel_btn = ctk.CTkButton(
            self, text=app.tr.t("cancel_current"),
            width=120, height=22, font=ctk.CTkFont(size=11),
            command=lambda: app.queue.cancel_current(), **CANCEL_KW,
        )

        self.progress = ctk.CTkProgressBar(self, height=8, corner_radius=0)
        self.progress.set(0)
        self.progress.grid(row=2, column=0, sticky="ew", padx=10, pady=(4, 8))

        self.refresh()

    def refresh(self):
        job = self.job
        if job.status == "downloading" and job.current_label:
            text = job.current_label
        else:
            status_key = {
                "queued": "status_queued", "downloading": "status_downloading",
                "done": "status_done", "error": "status_error", "canceled": "status_canceled",
            }.get(job.status, job.status)
            text = self.app.tr.t(status_key)
            if job.status == "error" and job.error_msg:
                text += f" — {job.error_msg}"
        self.status_label.configure(text=text)
        self.progress.set(max(0.0, min(1.0, job.progress / 100.0)))
        color = STATUS_BAR_COLORS.get(job.status, ("gray70", "gray40"))
        self.progress.configure(progress_color=color)

        if job.status == "downloading":
            self.cancel_btn.grid(row=0, column=1, rowspan=2, padx=(0, 10), sticky="e")
        else:
            self.cancel_btn.grid_forget()


class QueueTab(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.tr = app.tr
        self._i18n_labels = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)
        self.grid_rowconfigure(6, weight=1)

        # ---- status de dependências -----------------------------------------
        dep_bar = ctk.CTkFrame(self, fg_color=("gray90", "gray17"), corner_radius=8)
        dep_bar.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        dep_bar.grid_columnconfigure(2, weight=1)

        self.ytdlp_status = DepStatusRow(dep_bar, self.tr, "dep_ytdlp")
        self.ytdlp_status.grid(row=0, column=0, padx=(10, 20), pady=8)
        self.ffmpeg_status = DepStatusRow(dep_bar, self.tr, "dep_ffmpeg")
        self.ffmpeg_status.grid(row=0, column=1, pady=8)

        self.check_deps_btn = ctk.CTkButton(
            dep_bar, text=self.tr.t("check_reinstall_deps"),
            fg_color=("#dbdbdb", "#3a3a3a"), hover_color=("#c8c8c8", "#484848"),
            text_color=("gray10", "gray90"), command=lambda: self.app.check_dependencies(force=True),
        )
        self.check_deps_btn.grid(row=0, column=3, padx=6, pady=8)
        self._i18n_labels[self.check_deps_btn] = "check_reinstall_deps"

        self.update_ytdlp_btn = ctk.CTkButton(
            dep_bar, text=self.tr.t("update_ytdlp"),
            fg_color=("#dbdbdb", "#3a3a3a"), hover_color=("#c8c8c8", "#484848"),
            text_color=("gray10", "gray90"), command=self.app.update_ytdlp,
        )
        self.update_ytdlp_btn.grid(row=0, column=4, padx=(0, 6), pady=8)
        self._i18n_labels[self.update_ytdlp_btn] = "update_ytdlp"

        self.open_deps_btn = ctk.CTkButton(
            dep_bar, text="📁", width=34,
            fg_color=("#dbdbdb", "#3a3a3a"), hover_color=("#c8c8c8", "#484848"),
            text_color=("gray10", "gray90"),
            command=lambda: open_in_file_manager(dependencies.bin_dir()),
        )
        self.open_deps_btn.grid(row=0, column=5, padx=(0, 10), pady=8)

        # ---- botões da fila -----------------------------------------------------
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))

        self.start_btn = ctk.CTkButton(
            actions, text=self.tr.t("start_queue"),
            command=self.app.queue.start, **PRIMARY_KW,
        )
        self.start_btn.pack(side="left", padx=(0, 8))
        self._i18n_labels[self.start_btn] = "start_queue"

        self.cancel_btn = ctk.CTkButton(
            actions, text=self.tr.t("cancel_current"),
            command=self.app.queue.cancel_current, **CANCEL_KW,
        )
        self.cancel_btn.pack(side="left", padx=(0, 8))
        self._i18n_labels[self.cancel_btn] = "cancel_current"

        self.clear_done_btn = ctk.CTkButton(
            actions, text=self.tr.t("clear_done"),
            fg_color=("#dbdbdb", "#3a3a3a"), hover_color=("#c8c8c8", "#484848"),
            text_color=("gray10", "gray90"), command=self._clear_done,
        )
        self.clear_done_btn.pack(side="left", padx=(0, 8))
        self._i18n_labels[self.clear_done_btn] = "clear_done"

        self.clear_all_btn = ctk.CTkButton(
            actions, text=self.tr.t("clear_all"),
            fg_color=("#dbdbdb", "#3a3a3a"), hover_color=("#c8c8c8", "#484848"),
            text_color=("gray10", "gray90"), command=self._clear_all,
        )
        self.clear_all_btn.pack(side="left", padx=(0, 8))
        self._i18n_labels[self.clear_all_btn] = "clear_all"

        self.open_folder_btn = ctk.CTkButton(
            actions, text=self.tr.t("open_folder"),
            fg_color=("#dbdbdb", "#3a3a3a"), hover_color=("#c8c8c8", "#484848"),
            text_color=("gray10", "gray90"),
            command=lambda: open_in_file_manager(self.app.settings.get("audio_folder")),
        )
        self.open_folder_btn.pack(side="left")
        self._i18n_labels[self.open_folder_btn] = "open_folder"

        # ---- lista da fila --------------------------------------------------------
        self.queue_list = ctk.CTkScrollableFrame(self, fg_color=("gray95", "gray14"))
        self.queue_list.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 8))
        self.queue_list.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._empty_label = ctk.CTkLabel(self.queue_list, text=self.tr.t("queue_empty"),
                                          text_color=("gray45", "gray55"))
        self._empty_label.grid(row=0, column=0, pady=20)
        self._row_widgets = {}

        # ---- log ---------------------------------------------------------------------
        log_header = ctk.CTkFrame(self, fg_color="transparent")
        log_header.grid(row=3, column=0, sticky="ew", padx=16)
        self.log_title = ctk.CTkLabel(log_header, text=self.tr.t("log"), font=ctk.CTkFont(weight="bold"))
        self.log_title.pack(side="left")
        self._i18n_labels[self.log_title] = "log"
        self.copy_btn = ctk.CTkButton(
            log_header, text=self.tr.t("copy"), width=80, height=24,
            fg_color=("#dbdbdb", "#3a3a3a"), hover_color=("#c8c8c8", "#484848"),
            text_color=("gray10", "gray90"), command=self._copy_log,
        )
        self.copy_btn.pack(side="right")
        self._i18n_labels[self.copy_btn] = "copy"

        self.log_box = ctk.CTkTextbox(self, wrap="none", font=ctk.CTkFont(family="Consolas", size=11))
        self.log_box.grid(row=4, column=0, sticky="nsew", padx=16, pady=(4, 16))
        self.log_box.configure(state="disabled")

    # -- API pública usada pelo App ------------------------------------------------
    def append_log(self, line: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{ts}] {line}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _copy_log(self):
        text = self.log_box.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(text)

    def _clear_done(self):
        self.app.queue.clear_finished()

    def _clear_all(self):
        self.app.queue.clear_all()

    def refresh_queue(self):
        jobs = self.app.queue.jobs
        for w in self.queue_list.winfo_children():
            w.destroy()
        self._row_widgets = {}
        if not jobs:
            self._empty_label = ctk.CTkLabel(self.queue_list, text=self.tr.t("queue_empty"),
                                              text_color=("gray45", "gray55"))
            self._empty_label.grid(row=0, column=0, pady=20)
            return
        total = len(jobs)
        for i, job in enumerate(jobs, start=1):
            row = QueueRow(self.queue_list, self.app, job, i, total)
            row.grid(row=i - 1, column=0, sticky="ew", pady=4, padx=4)
            self._row_widgets[job.id] = row

    def update_job_row(self, job):
        row = self._row_widgets.get(job.id)
        if row:
            row.job = job
            row.refresh()
        else:
            self.refresh_queue()

    def retranslate(self):
        for widget, key in self._i18n_labels.items():
            try:
                widget.configure(text=self.tr.t(key))
            except Exception:
                pass
        self.ytdlp_status.retranslate()
        self.ffmpeg_status.retranslate()
        self.refresh_queue()
