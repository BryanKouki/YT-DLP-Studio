/** Self-check sem rede: npm run check (lança erro e sai com código 1 se algo quebrar). */
import * as core from './core.js';

const { path } = core;
function assert(ok: unknown, message = 'assert falhou'): asserts ok {
  if (!ok) throw new Error(message);
}
assert.equal = (actual: unknown, expected: unknown) =>
  assert(actual === expected, `esperado: ${expected} | obtido: ${actual}`);
assert.throws = (fn: () => unknown) => {
  try {
    fn();
  } catch {
    return;
  }
  throw new Error('deveria ter lançado erro');
};

const job = (mode: core.Mode, options: core.Opts, title = '', artist = ''): core.Job => ({
  id: '1', mode, url: 'u', title, artist, options,
  status: 'queued', progress: 0, errorMsg: '', nowTitle: '', nowArtist: '', idx: '', count: '',
});
const cmdFor = (j: core.Job) => core.buildCommand(j, core.outputTemplate(j), 'yt-dlp', 'bin');
const after = (cmd: string[], flag: string) => cmd[cmd.indexOf(flag) + 1];

async function run(): Promise<void> {
  // 1. conversor: compressão de vídeo com limite de resolução, áudio sem vídeo
  let { cmd, out } = core.buildFfmpegCmd('C:/x/clip.mov', 'MP4 (H.264)', 2, '720p', 'ffmpeg');
  assert.equal(after(cmd, '-crf'), '28');
  assert(cmd.includes("scale=-2:'min(ih,720)'") && path.basename(out) === 'clip_convertido.mp4');
  ({ cmd } = core.buildFfmpegCmd('C:/x/a.wav', 'MP3', 0, '720p', 'ffmpeg'));
  assert(cmd.includes('-vn') && cmd.includes('320k') && !cmd.some((c) => c.includes('scale')));

  // 1b. compressor: 100 MB em 100 s -> ~8,1 Mbps total, menos o áudio
  ({ cmd } = core.buildFfmpegCmd('v.mp4', 'MP4 (H.264)', 1, 'Original', 'ffmpeg', 100 * 1024 ** 2, 100));
  const vk = parseInt(after(cmd, '-maxrate'));
  assert(vk > 7900 && vk < 8000 && !cmd.includes('-crf'), String(vk));
  assert.throws(() => core.buildFfmpegCmd('v.mp4', 'MP4 (H.264)', 1, 'Original', 'ffmpeg', 1024 ** 2, 3600));
  assert.throws(() => core.buildFfmpegCmd('a.mp3', 'FLAC', 1, 'Original', 'ffmpeg', 1024 ** 2, 60));
  // VP9: o -b:v do alvo tem que vir depois do '-b:v 0'
  ({ cmd } = core.buildFfmpegCmd('v.mp4', 'WEBM (VP9)', 1, 'Original', 'ffmpeg', 100 * 1024 ** 2, 100));
  assert(cmd.lastIndexOf('-b:v') > cmd.indexOf('-b:v') && cmd[cmd.lastIndexOf('-b:v') + 1] !== '0');

  // 2. nome do arquivo: áudio = só o título (artista só no ID3); vídeo = título + canal
  let c = cmdFor(job('audio', { folder: 'C:/m', embed_metadata_thumb: true }, "It's/Mine", 'AC/DC'));
  assert.equal(after(c, '-o'), path.join('C:/m', "It's-Mine.%(ext)s"));
  assert.equal(after(c, '--postprocessor-args'), `ffmpeg:-metadata title='It'"'"'s/Mine' -metadata artist=AC/DC`);
  assert.equal(after(cmdFor(job('video', { folder: 'C:/v' })), '-o'),
    path.join('C:/v', '%(title)s - %(channel,uploader)s.%(ext)s'));
  assert(!c.join(' ').includes('uploader') && c.join(' ').includes('%(artist|)s'));
  assert(c.includes('--progress'), 'sem --progress o --print esconde o progresso');

  // 3. capas: áudio sempre recorta 1:1; vídeo nunca; música avulsa não deixa arquivo de capa
  assert.equal(after(c, '--ppa'),
    `ThumbnailsConvertor+FFmpeg_o:-c:v mjpeg -vf crop="'"if(gt(ih,iw),iw,ih)"'":"'"if(gt(iw,ih),ih,iw)"'"`);
  assert(!c.includes('--write-thumbnail'));
  c = cmdFor(job('video', { folder: 'C:/v', embed_metadata_thumb: true, save_thumbnail: true }));
  assert(c.includes('--write-thumbnail') && !c.includes('--ppa'));

  // 4. playlist + "Guardar thumbnail" (ou "Salvar capa na pasta") -> nomeia a capa da playlist
  c = cmdFor(job('audio', { folder: 'C:/pl', save_thumbnail: true, _is_playlist: true }));
  assert(c.some((a) => a.startsWith('pl_thumbnail:') && a.endsWith('playlist_thumb.%(ext)s')));
  c = cmdFor(job('audio', { folder: 'C:/pl', save_folder_cover: true, _is_playlist: true }));
  assert(c.includes('--write-thumbnail') && c.some((a) => a.startsWith('pl_thumbnail:')));

  // 5. seletor de vídeo, recorte de trecho e modelo avançado
  assert.equal(core.buildFormatSelector({ resolution: '1080', fps: '0', vcodec: 'avc1', acodec: 'mp4a' }),
    "bestvideo[height<=1080][vcodec~='^avc1']+bestaudio[acodec~='^mp4a']/best[height<=1080]");
  assert.equal(core.buildFormatSelector({}), 'bestvideo+bestaudio/best');
  c = cmdFor(job('video', { folder: 'C:/v', trim_start: '00:00:10', trim_end: '', output_template: 'x.%(ext)s' }));
  assert.equal(after(c, '--download-sections'), '*00:00:10-inf');
  assert.equal(after(c, '-o'), 'x.%(ext)s');
  assert.equal(core.sanitizeFilename(' a<b>: c?. '), 'a_b__ c_');

  // 6. verificação de playlist: acha a faixa com erro e as vizinhas
  const flat = ['a1\tFaixa 1', 'b2\tFaixa 2', 'c3\tFaixa 3'];
  const sim = ['OK:a1', 'ERROR: [youtube] b2: Video unavailable', 'OK:c3'];
  const lines: string[] = [];
  await core.checkPlaylist((l) => lines.push(l), async (...args) => (args.includes('--flat-playlist') ? flat : sim));
  assert(lines.some((l) => l.includes('2 - Faixa 2') && l.includes('depois de "Faixa 1"') && l.includes('antes de "Faixa 3"')),
    lines.join('\n'));

  console.log('selfcheck OK');
}

await run();
