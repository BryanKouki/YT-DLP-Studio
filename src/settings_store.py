"""Carrega/salva as configurações do usuário em um JSON local."""
import json
import os
import sys
from pathlib import Path

APP_DIR_NAME = "YT-DLP Studio"


def _portable_base_dir() -> Path:
    """Pasta onde o .exe realmente está (modo --onefile do PyInstaller usa
    uma pasta temporária para os arquivos do programa, então é preciso usar
    sys.executable, não __file__, para achar a pasta real do .exe)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # rodando direto do código-fonte (python src/main.py): usa a raiz do projeto
    return Path(__file__).resolve().parent.parent


def get_app_data_dir() -> Path:
    """Pasta de dados do app. Por padrão é 'data/' bem ao lado do .exe
    (modo portátil — fácil de ver/copiar/apagar). Se essa pasta não puder
    ser criada/escrita (ex.: .exe rodando em local sem permissão, como
    Arquivos de Programas), cai de volta para %APPDATA%/YT-DLP Studio."""
    candidate = _portable_base_dir() / "data"
    try:
        candidate.mkdir(parents=True, exist_ok=True)
        probe = candidate / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return candidate
    except Exception:
        pass

    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home())
        d = Path(base) / APP_DIR_NAME
    else:
        d = Path.home() / ".ytdlp-studio"
    d.mkdir(parents=True, exist_ok=True)
    return d


DEFAULTS = {
    "language": "pt",
    "theme": "dark",

    "audio_folder": str(Path.home() / "Music" / "Download"),
    "video_folder": str(Path.home() / "Videos" / "Download"),

    # Rede
    "speed_limit": "",
    "proxy": "",
    "playlist_items": "",
    "output_template": "",

    # Filtros
    "date_after": "",
    "date_before": "",
    "min_filesize": "",
    "max_filesize": "",
    "min_duration": "",
    "max_duration": "",

    # Comportamento do download
    "restrict_filenames": False,
    "no_playlist": False,
    "skip_downloaded": False,
    "geo_bypass": False,
    "no_check_certificate": False,
    "force_ipv4": False,
    "write_comments": False,
    "live_from_start": False,
    "windows_safe_names": False,
    "no_overwrites": False,
    "concurrent_fragments": "",
    "retries": "",
    "fragment_retries": "",
    "trim_filenames": "",
    "age_limit": "",
    "sleep_interval": "",

    # Arquivos extras
    "embed_metadata_thumb": True,
    "embed_chapters": False,
    "split_chapters": False,
    "write_description": False,
    "write_info_json": False,
    "embed_audio_tags": True,
    "keep_video": False,
    "sub_langs": "en.*",
    "sub_format": "",
    "save_folder_cover": True,

    # UI por aba (lembrado entre sessões)
    "last_audio_format": "MP3",
    "last_audio_quality": "320 kbps",
    "last_resolution": "1080p",
    "last_fps": "Melhor disponível",
    "last_vcodec": "H.264 (AVC)",
    "last_acodec": "AAC",
    "last_container": "Automático (MP4/MKV)",
    "last_subtitles": False,
    "last_save_thumb_audio": False,
    "last_save_thumb_video": False,

    "window_geometry": "",
}


class SettingsStore:
    def __init__(self):
        self.path = get_app_data_dir() / "settings.json"
        self.data = dict(DEFAULTS)
        self.load()

    def load(self):
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                merged = dict(DEFAULTS)
                merged.update(saved)
                self.data = merged
            except Exception:
                self.data = dict(DEFAULTS)
        return self.data

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    def update(self, mapping: dict):
        self.data.update(mapping)
