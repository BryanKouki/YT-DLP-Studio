"""
Constrói os argumentos de linha de comando do yt-dlp a partir do que foi
escolhido na interface, e executa a fila de downloads em segundo plano.
"""
import os
import queue
import re
import shlex
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import dependencies

NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

RES_HEIGHT = {
    "4320p (8K)": 4320, "2160p (4K)": 2160, "1440p (2K)": 1440, "1080p": 1080,
    "720p": 720, "480p": 480, "360p": 360, "240p": 240, "144p": 144,
}
VCODEC_FILTER = {
    "H.264 (AVC)": "avc1", "H.265 (HEVC)": "hev", "VP9": "vp9", "AV1": "av01", "VP8": "vp8",
}
ACODEC_FILTER = {"AAC": "mp4a", "Opus": "opus", "MP3": "mp3", "FLAC": "flac"}
FPS_VALUE = {"60 fps": 60, "30 fps": 30, "24 fps": 24}
CONTAINER_VALUE = {"Forçar MP4": "mp4", "Force MP4": "mp4", "Forçar MKV": "mkv", "Force MKV": "mkv"}
AUDIO_FORMAT_VALUE = {
    "MP3": "mp3", "M4A": "m4a", "AAC": "aac", "Opus": "opus", "Vorbis": "vorbis",
    "FLAC": "flac", "ALAC": "alac", "WAV": "wav",
    "Melhor disponível": "best", "Best available": "best",
}
AUDIO_QUALITY_VALUE = {
    "320 kbps": "320K", "256 kbps": "256K", "224 kbps": "224K", "192 kbps": "192K",
    "160 kbps": "160K", "128 kbps": "128K", "96 kbps": "96K", "64 kbps": "64K", "32 kbps": "32K",
    "Melhor qualidade (VBR)": "0", "Best quality (VBR)": "0",
}

PROGRESS_RE = re.compile(r"\[download\]\s+(\d{1,3}(?:\.\d+)?)%")
DEST_RE = re.compile(r"\[download\] Destination:\s*(.+)")
ALREADY_RE = re.compile(r"\[download\] (.+) has already been downloaded")
NOW_PLAYING_RE = re.compile(r"^(BDL|ADL)@@@(.*)$")
_INVALID_FS_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Filtro ffmpeg para recorte quadrado (1:1) centralizado da capa, aplicado via
# --ppa no postprocessor "ThumbnailsConvertor" (mesmo mecanismo usado no
# yt-dlp.conf original, só que já resolvido para argv direto, sem depender
# de alias nem de arquivo .conf). As aspas simples embutidas em torno de cada
# expressão protegem as vírgulas do if(...) para o parser de filtergraph do
# próprio ffmpeg; a sequência "'" garante que essas aspas sobrevivam ao
# shlex.split() que o yt-dlp usa internamente para separar os argumentos do
# --ppa (testado isoladamente com Python shlex antes de entrar aqui).
_Q = "\"'\""
SQUARE_CROP_PPA = (
    "ThumbnailsConvertor+FFmpeg_o:-c:v mjpeg -vf "
    f"crop={_Q}if(gt(ih,iw),iw,ih){_Q}:{_Q}if(gt(iw,ih),ih,iw){_Q}"
)

THUMB_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def sanitize_filename(name: str) -> str:
    """Remove caracteres inválidos em nomes de pasta/arquivo do Windows."""
    cleaned = _INVALID_FS_CHARS_RE.sub("_", name).strip().rstrip(". ")
    return cleaned[:180] if cleaned else "playlist"


@dataclass
class Job:
    id: str
    mode: str  # "audio" | "video"
    url: str
    title: str = ""
    artist: str = ""
    options: dict = field(default_factory=dict)
    status: str = "queued"
    progress: float = 0.0
    error_msg: str = ""
    current_label: str = ""  # "Título - Artista (X de Y)", atualizado ao vivo

    def label(self, translator):
        title = self.title or self.url
        if self.mode == "audio" and self.artist:
            return translator.t("queue_position", title=title, artist=self.artist, idx="", total="").strip(" -()")
        return title


def _duration_filter(min_s, max_s):
    parts = []
    if min_s:
        parts.append(f"duration >=? {min_s}")
    if max_s:
        parts.append(f"duration <=? {max_s}")
    return " & ".join(parts) if parts else None


def build_format_selector(opts: dict) -> str:
    """Monta o seletor -f do yt-dlp a partir das opções de vídeo escolhidas."""
    height = RES_HEIGHT.get(opts.get("resolution"))
    fps = FPS_VALUE.get(opts.get("fps"))
    vcodec = VCODEC_FILTER.get(opts.get("vcodec"))
    acodec = ACODEC_FILTER.get(opts.get("acodec"))

    vfilters = []
    if height:
        vfilters.append(f"height<={height}")
    if fps:
        vfilters.append(f"fps<={fps}")
    if vcodec:
        vfilters.append(f"vcodec~='^{vcodec}'")
    vf = "".join(f"[{f}]" for f in vfilters)

    afilters = []
    if acodec:
        afilters.append(f"acodec~='^{acodec}'")
    af = "".join(f"[{f}]" for f in afilters)

    primary = f"bestvideo{vf}+bestaudio{af}"
    fallback_bits = []
    if height:
        fallback_bits.append(f"height<={height}")
    fallback = f"best{''.join(f'[{b}]' for b in fallback_bits)}" if fallback_bits else "best"
    return f"{primary}/{fallback}"


def build_command(job: Job, output_template: str) -> list:
    ytdlp = str(dependencies.ytdlp_path())
    ffdir = str(dependencies.bin_dir())
    args = [ytdlp, job.url.strip(), "--newline", "--no-color", "--no-warnings", "--ignore-errors",
            "--ffmpeg-location", ffdir,
            "--print", "before_dl:BDL@@@%(title)s@@@%(artist|)s@@@"
                       "%(playlist_index|)s@@@%(playlist_count|)s",
            "--print", "after_move:ADL@@@%(title)s@@@%(artist|)s@@@"
                       "%(playlist_index|)s@@@%(playlist_count|)s",
            "-o", output_template]

    s = job.options  # settings snapshot mesclado com as opções da aba

    # ---- comportamento geral -------------------------------------------------
    if s.get("restrict_filenames"):
        args.append("--restrict-filenames")
    if s.get("no_playlist"):
        args.append("--no-playlist")
    if s.get("skip_downloaded"):
        archive_dir = job.options.get("folder") or s.get("_archive_dir", ".")
        archive = str(Path(archive_dir) / "download_archive.txt")
        args += ["--download-archive", archive]
    if s.get("geo_bypass"):
        args.append("--geo-bypass")
    if s.get("no_check_certificate"):
        args.append("--no-check-certificates")
    if s.get("force_ipv4"):
        args.append("--force-ipv4")
    if s.get("write_comments"):
        args.append("--write-comments")
    if s.get("live_from_start"):
        args.append("--live-from-start")
    if s.get("windows_safe_names"):
        args.append("--windows-filenames")
    if s.get("no_overwrites"):
        args.append("--no-overwrites")

    for flag, key in (
        ("--concurrent-fragments", "concurrent_fragments"),
        ("--retries", "retries"),
        ("--fragment-retries", "fragment_retries"),
        ("--trim-filenames", "trim_filenames"),
        ("--age-limit", "age_limit"),
        ("--sleep-interval", "sleep_interval"),
    ):
        val = str(s.get(key, "")).strip()
        if val:
            args += [flag, val]

    if str(s.get("speed_limit", "")).strip():
        args += ["--limit-rate", str(s["speed_limit"]).strip()]
    if str(s.get("proxy", "")).strip():
        args += ["--proxy", str(s["proxy"]).strip()]
    if str(s.get("playlist_items", "")).strip():
        args += ["--playlist-items", str(s["playlist_items"]).strip()]
    if str(s.get("date_after", "")).strip():
        args += ["--dateafter", str(s["date_after"]).strip()]
    if str(s.get("date_before", "")).strip():
        args += ["--datebefore", str(s["date_before"]).strip()]
    if str(s.get("min_filesize", "")).strip():
        args += ["--min-filesize", str(s["min_filesize"]).strip()]
    if str(s.get("max_filesize", "")).strip():
        args += ["--max-filesize", str(s["max_filesize"]).strip()]

    dur_filter = _duration_filter(s.get("min_duration"), s.get("max_duration"))
    if dur_filter:
        args += ["--match-filters", dur_filter]

    # ---- recorte de trecho (start/end) ---------------------------------------
    start_s, end_s = job.options.get("trim_start"), job.options.get("trim_end")
    if start_s or end_s:
        rng = f"*{start_s or '0'}-{end_s or 'inf'}"
        args += ["--download-sections", rng, "--force-keyframes-at-cuts"]

    # ---- arquivos extras -------------------------------------------------
    if s.get("embed_metadata_thumb"):
        args += ["--embed-metadata", "--embed-thumbnail"]
        args += ["--parse-metadata", "release_year:%(release_year)s"]
    if s.get("embed_chapters"):
        args.append("--embed-chapters")
    if s.get("split_chapters"):
        args.append("--split-chapters")
    if s.get("write_description"):
        args.append("--write-description")
    if s.get("write_info_json"):
        args.append("--write-info-json")

    # --write-thumbnail só é forçado (mesmo sem o usuário marcar "Guardar
    # thumbnail") quando é uma playlist detectada E "Salvar capa na pasta"
    # está ativo — é o único caso em que precisamos de um arquivo de capa no
    # disco pra gerar o playlistcover.jpg. Numa música avulsa isso não deve
    # nunca criar um arquivo de capa que o usuário não pediu.
    is_pl = bool(job.options.get("_is_playlist"))
    save_thumb_file = bool(job.options.get("save_thumbnail")) or (
        job.mode == "audio" and s.get("save_folder_cover") and is_pl
    )
    if save_thumb_file and is_pl:
        # a capa DA PLAYLIST (não das faixas) vem com nome fixo -> vira playlistcover.jpg
        args += ["-o", "pl_thumbnail:" + str(Path(job.options["folder"]) / "playlist_thumb.%(ext)s")]

    # Em áudio, toda thumbnail — salva em disco e/ou embutida no arquivo —
    # sempre sai em .jpg recortada 1:1 (padrão de capa de álbum); não é
    # opcional, não há motivo pra deixar isso configurável. Em vídeo nunca
    # recorta (mantém o tamanho/proporção original da thumbnail).
    want_thumbnail = save_thumb_file or s.get("embed_metadata_thumb")
    want_square_crop = job.mode == "audio" and want_thumbnail
    want_jpg_convert = save_thumb_file or want_square_crop

    if save_thumb_file:
        args.append("--write-thumbnail")
    if want_jpg_convert:
        args += ["--convert-thumbnail", "jpg"]
    if want_square_crop:
        args += ["--ppa", SQUARE_CROP_PPA]

    # ---- modo áudio -------------------------------------------------------
    if job.mode == "audio":
        fmt = AUDIO_FORMAT_VALUE.get(job.options.get("format"), "mp3")
        quality = AUDIO_QUALITY_VALUE.get(job.options.get("quality"), "0")
        args += ["-x", "--audio-format", fmt, "--audio-quality", quality]
        args.append("--keep-video" if s.get("keep_video") else "--no-keep-video")

        pp_meta = []
        if job.title:
            pp_meta.append(f"-metadata title={shlex.quote(job.title)}")
        if job.artist:
            pp_meta.append(f"-metadata artist={shlex.quote(job.artist)}")
        if pp_meta and s.get("embed_audio_tags", True):
            args += ["--postprocessor-args", "ffmpeg:" + " ".join(pp_meta)]

    # ---- modo vídeo ---------------------------------------------------------
    else:
        args += ["-f", build_format_selector(job.options)]
        container = CONTAINER_VALUE.get(job.options.get("container"))
        if container:
            args += ["--merge-output-format", container]
        if job.options.get("subtitles"):
            args += ["--write-subs", "--write-auto-subs", "--embed-subs"]
            if str(s.get("sub_langs", "")).strip():
                args += ["--sub-langs", str(s["sub_langs"]).strip()]
            if str(s.get("sub_format", "")).strip():
                args += ["--convert-subs", str(s["sub_format"]).strip()]

    if str(s.get("output_template", "")).strip():
        # substitui o -o padrão pelo modelo avançado do usuário
        idx = args.index("-o")
        args[idx + 1] = str(s["output_template"]).strip()

    return args


def promote_folder_cover(folder: str, square: bool = True):
    """Depois de baixar uma playlist com sucesso, promove a primeira imagem
    de capa encontrada na pasta para 'playlistcover.jpg', para identificar a
    capa da playlist/álbum inteiro na própria pasta."""
    try:
        folder_path = Path(folder)
        if not folder_path.is_dir():
            return
        target = folder_path / "playlistcover.jpg"
        if target.exists():
            return  # já promovida antes; não sobrescreve
        candidates = [
            p for p in folder_path.iterdir()
            if p.is_file() and p.suffix.lower() in THUMB_EXTS
            and p.stem.lower() != "playlistcover"
        ]
        if not candidates:
            return
        # capa da própria playlist primeiro; senão a imagem mais antiga (1ª faixa)
        # ponytail: fallback por mtime, playlists sem capa própria pegam a 1ª faixa
        candidates.sort(key=lambda p: (p.stem != "playlist_thumb", p.stat().st_mtime))
        source = candidates[0]
        crop = ["-vf", "crop='if(gt(ih,iw),iw,ih)':'if(gt(iw,ih),ih,iw)'"] if square else []
        if source.suffix.lower() == ".jpg" and not square:
            shutil.copyfile(source, target)
        else:
            try:
                subprocess.run(
                    [str(dependencies.ffmpeg_path()), "-y", "-i", str(source), *crop, str(target)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=30, creationflags=NO_WINDOW,
                )
            except Exception:
                shutil.copyfile(source, target)
    except Exception:
        pass


def cleanup_stray_thumbnails(folder: str, keep_name: str = "playlistcover.jpg"):
    """Remove as imagens de thumbnail individuais que sobraram na pasta
    depois que --write-thumbnail foi forçado só para gerar o
    playlistcover.jpg (o usuário não marcou 'Guardar thumbnail', então não
    deve sobrar um arquivo de capa por faixa)."""
    try:
        folder_path = Path(folder)
        if not folder_path.is_dir():
            return
        for p in folder_path.iterdir():
            if p.is_file() and p.suffix.lower() in THUMB_EXTS and p.name != keep_name:
                try:
                    p.unlink()
                except Exception:
                    pass
    except Exception:
        pass


def probe_media_info(url: str, timeout: int = 15):
    """Busca rapidamente título, artista e duração de um link, sem baixar
    nada (--skip-download) — usado só para pré-preencher a UI assim que o
    usuário cola o link. Retorna (title, artist, duration_seconds); campos
    vazios/0 em caso de falha (link inválido, sem internet, etc.) — nunca
    levanta exceção, para nunca travar a interface.

    O campo 'artist' só usa %(artist)s (metadado real, presente sobretudo
    em links do YouTube Music) — de propósito SEM cair para uploader/nome
    do canal, que costuma ser só quem subiu o vídeo, não o artista da
    música, e acabaria virando um prefixo errado no nome do arquivo
    (ex.: 'Canal X - Nome da Música' em vez de só 'Nome da Música')."""
    ytdlp = dependencies.ytdlp_path()
    if not ytdlp.exists():
        return "", "", 0
    try:
        result = subprocess.run(
            [str(ytdlp), "--print",
             "%(title|)s@@@%(artist|)s@@@%(duration|0)s",
             "--no-warnings", "--skip-download", "--playlist-items", "1", url.strip()],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            timeout=timeout, creationflags=NO_WINDOW,
        )
        out = (result.stdout or "").strip()
        line = out.splitlines()[-1] if out else ""
        parts = (line.split("@@@") + ["", "", "0"])[:3]
        title, artist, dur_s = parts
        try:
            duration = int(float(dur_s))
        except ValueError:
            duration = 0
        return title.strip(), artist.strip(), duration
    except Exception:
        return "", "", 0


PL_ERR_RE = re.compile(r"ERROR:\s*\[.*?\]\s*([\w-]+):\s*(.*)")


def check_playlist(url: str, emit):
    """Porta do script .ps1 de verificação: lista as faixas indisponíveis da
    playlist com posição e as vizinhas. emit(linha) recebe cada linha do
    relatório (roda numa thread; emit tem que ser thread-safe)."""
    def run(*extra):
        r = subprocess.run([str(dependencies.ytdlp_path()), "--no-warnings", *extra, url.strip()],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                           encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
        return r.stdout.splitlines()

    emit("Obtendo a estrutura da playlist...")
    items = [p for line in run("--flat-playlist", "--print", "%(id)s\t%(title)s")
             if len(p := line.split("\t", 1)) == 2]
    if not items:
        emit("[erro] Não foi possível carregar a playlist. Verifique o link.")
        return
    pos = {vid: i for i, (vid, _) in enumerate(items)}
    titles = [title for _, title in items]
    emit(f"Testando a disponibilidade de {len(items)} faixas...")
    faltando = 0
    for line in run("-i", "-s", "--print", "OK:%(id)s"):
        m = PL_ERR_RE.search(line)
        if not m or m.group(1) not in pos:
            continue
        i = pos[m.group(1)]
        faltando += 1
        antes = titles[i - 1] if i else "[Início da playlist]"
        depois = titles[i + 1] if i + 1 < len(titles) else "[Fim da playlist]"
        emit(f"✖ {i + 1} - {titles[i]} — depois de \"{antes}\" e antes de \"{depois}\"")
        emit(f"   Motivo: {m.group(2)}")
    emit(f"{faltando} faixa(s) indisponível(is)." if faltando
         else "Todas as músicas estão disponíveis na playlist!")


class QueueManager:
    """Executa os jobs da fila em uma worker thread; toda comunicação com a
    UI passa por uma queue.Queue thread-safe, consumida via root.after()."""

    def __init__(self, event_cb):
        self.jobs: list[Job] = []
        self.events = queue.Queue()
        self.event_cb = event_cb  # não chamado diretamente pela thread
        self._worker = None
        self._proc = None
        self._stop_flag = threading.Event()
        self._running = False
        self.output_template_fn = None  # callable(job) -> str

    # -- API pública (chamada pela thread da UI) --------------------------
    def add_job(self, job: Job):
        self.jobs.append(job)
        self._emit("job_added", job=job)

    def clear_finished(self):
        self.jobs = [j for j in self.jobs if j.status not in ("done", "error", "canceled")]
        self._emit("queue_reset")

    def clear_all(self):
        if not self._running:
            self.jobs = []
            self._emit("queue_reset")

    def cancel_current(self):
        self._stop_flag.set()
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass

    def start(self):
        if self._running:
            return
        self._stop_flag.clear()
        self._running = True
        self._worker = threading.Thread(target=self._run_loop, daemon=True)
        self._worker.start()

    def is_running(self):
        return self._running

    # -- worker thread ------------------------------------------------------
    def _emit(self, kind, **data):
        self.events.put((kind, data))

    def _run_loop(self):
        for job in self.jobs:
            if self._stop_flag.is_set():
                job.status = "canceled" if job.status == "queued" else job.status
                self._emit("job_update", job=job)
                continue
            if job.status != "queued":
                continue
            self._run_job(job)
        self._running = False
        self._emit("queue_finished")

    def _run_job(self, job: Job):
        job.status = "downloading"
        job.progress = 0.0
        job.current_label = ""
        self._emit("job_update", job=job)
        self._emit("log", line=f"Iniciando: {job.url}")

        self._resolve_playlist_folder(job)

        output_template = self.output_template_fn(job) if self.output_template_fn else "%(title)s.%(ext)s"
        cmd = build_command(job, output_template)
        self._emit("log", line="$ " + " ".join(shlex.quote(c) for c in cmd))

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=NO_WINDOW,
            )
        except FileNotFoundError:
            job.status = "error"
            job.error_msg = "yt-dlp não encontrado"
            self._emit("job_update", job=job)
            self._emit("log", line="[erro] yt-dlp não encontrado")
            return

        for line in self._proc.stdout:
            line = line.rstrip()
            if not line:
                continue

            m2 = NOW_PLAYING_RE.match(line)
            if m2:
                kind, rest = m2.groups()
                fields = (rest.split("@@@") + ["", "", "", ""])[:4]
                title, artist, idx, count = fields
                self._emit(
                    "now_playing", job=job,
                    phase=("start" if kind == "BDL" else "done"),
                    title=title, artist=artist, idx=idx, count=count,
                )
                if self._stop_flag.is_set():
                    try:
                        self._proc.terminate()
                    except Exception:
                        pass
                    break
                continue

            m = PROGRESS_RE.search(line)
            if m:
                job.progress = float(m.group(1))
                self._emit("job_update", job=job)
            self._emit("log", line=line)
            if self._stop_flag.is_set():
                try:
                    self._proc.terminate()
                except Exception:
                    pass
                break

        ret = self._proc.wait()
        if self._stop_flag.is_set() and ret != 0:
            job.status = "canceled"
            self._emit("log", line=f"Cancelado: {job.url}")
        elif ret == 0:
            job.status = "done"
            job.progress = 100.0
            self._emit("log", line=f"Concluído: {job.url}")
            wants_cover = job.options.get("save_thumbnail") or (
                job.mode == "audio" and job.options.get("save_folder_cover"))
            if job.options.get("_is_playlist") and wants_cover:
                folder = job.options.get("folder")
                if folder:
                    promote_folder_cover(folder, square=job.mode == "audio")
                    cleanup_stray_thumbnails(folder)  # só a capa da playlist fica
                    self._emit("log", line="Capa da playlist salva (playlistcover.jpg)")
        else:
            job.status = "error"
            job.error_msg = f"yt-dlp saiu com código {ret}"
            self._emit("log", line=f"[erro] código {ret}: {job.url}")

        self._emit("job_update", job=job)
        self._proc = None
        # o stop_flag só cancela o item atual; a fila continua
        self._stop_flag.clear() if job.status == "canceled" else None

    def _resolve_playlist_folder(self, job: Job):
        """Detecta se o link é uma playlist (mesma estratégia do script .ps1
        original: uma checagem rápida com --get-filename antes do download de
        verdade) e, se for, cria uma subpasta com o nome da playlist dentro
        da pasta de destino configurada."""
        base_folder = job.options.get("folder")
        if not base_folder:
            return
        ytdlp = str(dependencies.ytdlp_path())
        url = job.url.strip()
        try:
            result = subprocess.run(
                [ytdlp, "--get-filename", "--no-warnings", "-o", "%(playlist_title)s",
                 url, "--playlist-items", "1"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                timeout=20, creationflags=NO_WINDOW,
            )
            name = (result.stdout or "").strip().splitlines()[-1] if result.stdout else ""
        except Exception:
            name = ""

        if name and name.upper() != "NA" and name != url:
            safe_name = sanitize_filename(name)
            target = Path(base_folder) / safe_name
            try:
                target.mkdir(parents=True, exist_ok=True)
                job.options["folder"] = str(target)
                job.options["_is_playlist"] = True
                # título/artista digitados/auto-preenchidos valem pra UMA faixa;
                # numa playlist viravam nome de arquivo e ID3 fixos em todas
                # (cada faixa sobrescrevia a anterior). Cada faixa usa o seu.
                job.title = job.artist = ""
                self._emit("log", line=f"Playlist detectada: {name} → {target}")
            except Exception:
                pass


def new_job_id() -> str:
    return uuid.uuid4().hex[:8]
