"""Self-check sem rede: python src/selfcheck.py  (falha com AssertionError se algo quebrar)."""
import types

import converter_tab
import downloader


def run():
    # 3. conversor: compressão de vídeo com limite de resolução, áudio sem vídeo
    cmd, out = converter_tab.build_ffmpeg_cmd("C:/x/clip.mov", "MP4 (H.264)", 2, "720p")
    assert "-crf" in cmd and cmd[cmd.index("-crf") + 1] == "28"
    assert "scale=-2:'min(ih,720)'" in cmd and out.name == "clip_convertido.mp4"
    cmd, out = converter_tab.build_ffmpeg_cmd("C:/x/a.wav", "MP3", 0, "720p")
    assert "-vn" in cmd and "320k" in cmd and not any("scale" in c for c in cmd)

    # 3b. compressor: 100 MB em 100 s -> ~8,1 Mbps total, menos o áudio
    cmd, _ = converter_tab.build_ffmpeg_cmd("v.mp4", "MP4 (H.264)", 1, "Original", 100 * 1024 ** 2, 100.0)
    vk = int(cmd[cmd.index("-maxrate") + 1].rstrip("k"))
    assert 7900 < vk < 8000 and "-crf" not in cmd, vk
    try:
        converter_tab.build_ffmpeg_cmd("v.mp4", "MP4 (H.264)", 1, "Original", 1024 ** 2, 3600.0)
        raise AssertionError("alvo impossível deveria falhar")
    except ValueError:
        pass

    # 1. playlist + "Guardar thumbnail" -> nomeia a capa da playlist
    job = downloader.Job(id="1", mode="audio", url="u", options={
        "folder": "/tmp/pl", "save_thumbnail": True, "_is_playlist": True})
    assert any(c.startswith("pl_thumbnail:") for c in downloader.build_command(job, "%(title)s.%(ext)s"))

    # 2. verificação: acha a faixa com erro e as vizinhas
    flat = "a1\tFaixa 1\nb2\tFaixa 2\nc3\tFaixa 3\n"
    sim = "OK:a1\nERROR: [youtube] b2: Video unavailable\nOK:c3\n"
    real = downloader.subprocess.run
    downloader.subprocess.run = lambda cmd, **k: types.SimpleNamespace(
        stdout=flat if "--flat-playlist" in cmd else sim)
    lines = []
    try:
        downloader.check_playlist("u", lines.append)
    finally:
        downloader.subprocess.run = real
    assert any('2 - Faixa 2' in l and 'depois de "Faixa 1"' in l and 'antes de "Faixa 3"' in l for l in lines), lines
    print("selfcheck OK")


if __name__ == "__main__":
    run()
