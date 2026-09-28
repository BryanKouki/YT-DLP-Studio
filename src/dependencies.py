"""
Verifica e baixa automaticamente o yt-dlp e o FFmpeg, guardando os binários
em uma pasta local do aplicativo (sem exigir instalação manual pelo usuário).
"""
import io
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

from settings_store import get_app_data_dir

YTDLP_RELEASE = {
    "windows": "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe",
    "linux": "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp",
    "darwin": "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos",
}

FFMPEG_WIN_ESSENTIALS = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
FFMPEG_LINUX_STATIC = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"

NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def _os_key():
    system = platform.system().lower()
    if "windows" in system:
        return "windows"
    if "darwin" in system:
        return "darwin"
    return "linux"


def bin_dir() -> Path:
    d = get_app_data_dir() / "bin"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ytdlp_path() -> Path:
    name = "yt-dlp.exe" if _os_key() == "windows" else "yt-dlp"
    return bin_dir() / name


def ffmpeg_path() -> Path:
    name = "ffmpeg.exe" if _os_key() == "windows" else "ffmpeg"
    return bin_dir() / name


def ffprobe_path() -> Path:
    name = "ffprobe.exe" if _os_key() == "windows" else "ffprobe"
    return bin_dir() / name


def _run_version(path: Path, arg="--version"):
    if not path.exists():
        return False
    try:
        result = subprocess.run(
            [str(path), arg],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
            creationflags=NO_WINDOW,
        )
        return result.returncode == 0
    except Exception:
        return False


def check_ytdlp() -> bool:
    return _run_version(ytdlp_path(), "--version")


def check_ffmpeg() -> bool:
    return _run_version(ffmpeg_path(), "-version")


def _download_with_progress(url: str, dest: Path, on_progress=None, chunk=1024 * 256):
    """on_progress(downloaded_bytes, total_bytes_or_None)"""
    req = Request(url, headers={"User-Agent": "YT-DLP-Studio/1.0"})
    with urlopen(req, timeout=30) as resp:
        total = resp.headers.get("Content-Length")
        total = int(total) if total else None
        downloaded = 0
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            while True:
                block = resp.read(chunk)
                if not block:
                    break
                f.write(block)
                downloaded += len(block)
                if on_progress:
                    on_progress(downloaded, total)
        tmp.replace(dest)


def _download_bytes(url: str, on_progress=None) -> bytes:
    req = Request(url, headers={"User-Agent": "YT-DLP-Studio/1.0"})
    with urlopen(req, timeout=30) as resp:
        total = resp.headers.get("Content-Length")
        total = int(total) if total else None
        buf = io.BytesIO()
        downloaded = 0
        while True:
            block = resp.read(1024 * 256)
            if not block:
                break
            buf.write(block)
            downloaded += len(block)
            if on_progress:
                on_progress(downloaded, total)
        return buf.getvalue()


def install_ytdlp(on_progress=None) -> bool:
    """Baixa o binário mais recente do yt-dlp para a pasta local do app."""
    osk = _os_key()
    url = YTDLP_RELEASE.get(osk, YTDLP_RELEASE["linux"])
    dest = ytdlp_path()
    try:
        _download_with_progress(url, dest, on_progress)
        if osk != "windows":
            st = os.stat(dest)
            os.chmod(dest, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        return check_ytdlp()
    except Exception:
        return False


def update_ytdlp(on_progress=None) -> bool:
    """Atualiza reinstalando a versão mais recente."""
    return install_ytdlp(on_progress)


def install_ffmpeg(on_progress=None) -> bool:
    """Baixa o FFmpeg (build essentials) e extrai ffmpeg/ffprobe para a
    pasta local do app."""
    osk = _os_key()
    try:
        if osk == "windows":
            data = _download_bytes(FFMPEG_WIN_ESSENTIALS, on_progress)
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for info in z.infolist():
                    fname = os.path.basename(info.filename)
                    if fname in ("ffmpeg.exe", "ffprobe.exe") and "/bin/" in info.filename.replace("\\", "/"):
                        target = bin_dir() / fname
                        with z.open(info) as src, open(target, "wb") as dst:
                            shutil.copyfileobj(src, dst)
        elif osk == "linux":
            data = _download_bytes(FFMPEG_LINUX_STATIC, on_progress)
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:xz") as tf:
                for member in tf.getmembers():
                    fname = os.path.basename(member.name)
                    if fname in ("ffmpeg", "ffprobe") and member.isfile():
                        target = bin_dir() / fname
                        with tf.extractfile(member) as src, open(target, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        os.chmod(target, 0o755)
        else:  # darwin - binários estáticos da evermeet.cx
            for exe, url in (
                ("ffmpeg", "https://evermeet.cx/ffmpeg/getrelease/zip"),
                ("ffprobe", "https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip"),
            ):
                data = _download_bytes(url, on_progress)
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    names = z.namelist()
                    if names:
                        with z.open(names[0]) as src, open(bin_dir() / exe, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        os.chmod(bin_dir() / exe, 0o755)
        return check_ffmpeg()
    except Exception:
        return False


class DependencyManager:
    """Coordena a checagem/instalação de yt-dlp + FFmpeg, reportando status
    através de um callback thread-safe (chamado de uma worker thread)."""

    def __init__(self, status_cb=None):
        # status_cb(component: 'ytdlp'|'ffmpeg', state: str, extra: dict)
        self.status_cb = status_cb or (lambda *a, **k: None)

    def _report(self, component, state, **extra):
        self.status_cb(component, state, extra)

    def ensure_all(self, force_reinstall=False):
        self._report("ytdlp", "checking")
        has_ytdlp = False if force_reinstall else check_ytdlp()
        if not has_ytdlp:
            self._report("ytdlp", "downloading", size="~15MB")

            def prog(done, total):
                pct = int(done * 100 / total) if total else None
                self._report("ytdlp", "downloading", size="~15MB", pct=pct)

            ok = install_ytdlp(prog)
            self._report("ytdlp", "ok" if ok else "error")
        else:
            self._report("ytdlp", "ok")

        self._report("ffmpeg", "checking")
        has_ffmpeg = False if force_reinstall else check_ffmpeg()
        if not has_ffmpeg:
            self._report("ffmpeg", "downloading", size="~80MB")

            def prog2(done, total):
                pct = int(done * 100 / total) if total else None
                self._report("ffmpeg", "downloading", size="~80MB", pct=pct)

            ok = install_ffmpeg(prog2)
            self._report("ffmpeg", "ok" if ok else "error")
        else:
            self._report("ffmpeg", "ok")

    def update_ytdlp(self):
        self._report("ytdlp", "downloading", size="~15MB")

        def prog(done, total):
            pct = int(done * 100 / total) if total else None
            self._report("ytdlp", "downloading", size="~15MB", pct=pct)

        ok = update_ytdlp(prog)
        self._report("ytdlp", "ok" if ok else "error")
