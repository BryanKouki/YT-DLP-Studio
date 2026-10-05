/** Monta as linhas de comando do yt-dlp e do ffmpeg. Sem I/O: roda na página e no Node (ver selfcheck.ts). */

// Caminhos do Windows sem depender do Node.
export const path = {
  join: (...parts: string[]) => parts.join('\\'),
  dirname: (p: string) => p.slice(0, Math.max(p.lastIndexOf('\\'), p.lastIndexOf('/'), 0)) || '.',
  basename: (p: string) => p.slice(Math.max(p.lastIndexOf('\\'), p.lastIndexOf('/')) + 1),
  stem: (p: string) => path.basename(p).replace(/\.[^.]*$/, ''),
  extname: (p: string) => /\.[^.]*$/.exec(path.basename(p))?.[0].toLowerCase() ?? '',
};

export type Mode = 'audio' | 'video';
export type Opts = Record<string, any>;

export interface Job {
  id: string;
  mode: Mode;
  url: string;
  title: string;
  artist: string;
  options: Opts; // snapshot das configurações mesclado com as opções da aba
  status: 'queued' | 'downloading' | 'done' | 'error' | 'canceled';
  progress: number;
  errorMsg: string;
  // faixa sendo baixada agora (playlists), atualizado ao vivo
  nowTitle: string;
  nowArtist: string;
  idx: string;
  count: string;
}

export const PROGRESS_RE = /\[download\]\s+(\d{1,3}(?:\.\d+)?)%/;
export const NOW_PLAYING_RE = /^(BDL|ADL)@@@(.*)$/;
export const THUMB_EXTS = ['.jpg', '.jpeg', '.png', '.webp'];

// Recorte quadrado (1:1) da capa via --ppa. As aspas simples protegem as vírgulas
// do if(...) para o ffmpeg; a sequência "'" faz essas aspas sobreviverem ao
// shlex.split() que o yt-dlp aplica no --ppa. Deliberado: não simplificar.
const Q = `"'"`;
export const SQUARE_CROP_PPA =
  `ThumbnailsConvertor+FFmpeg_o:-c:v mjpeg -vf crop=${Q}if(gt(ih,iw),iw,ih)${Q}:${Q}if(gt(iw,ih),ih,iw)${Q}`;

const BOOL_FLAGS: Record<string, string> = {
  restrict_filenames: '--restrict-filenames',
  no_playlist: '--no-playlist',
  geo_bypass: '--geo-bypass',
  no_check_certificate: '--no-check-certificates',
  force_ipv4: '--force-ipv4',
  write_comments: '--write-comments',
  live_from_start: '--live-from-start',
  windows_safe_names: '--windows-filenames',
  no_overwrites: '--no-overwrites',
  embed_chapters: '--embed-chapters',
  split_chapters: '--split-chapters',
  write_description: '--write-description',
  write_info_json: '--write-info-json',
};
const VALUE_FLAGS: Record<string, string> = {
  concurrent_fragments: '--concurrent-fragments',
  retries: '--retries',
  fragment_retries: '--fragment-retries',
  trim_filenames: '--trim-filenames',
  age_limit: '--age-limit',
  sleep_interval: '--sleep-interval',
  speed_limit: '--limit-rate',
  proxy: '--proxy',
  playlist_items: '--playlist-items',
  date_after: '--dateafter',
  date_before: '--datebefore',
  min_filesize: '--min-filesize',
  max_filesize: '--max-filesize',
};

/** Equivalente ao shlex.quote do Python (o yt-dlp faz shlex.split nos --postprocessor-args). */
export function shlexQuote(s: string): string {
  return /^[\w@%+=:,./-]+$/.test(s) ? s : `'${s.replace(/'/g, `'"'"'`)}'`;
}

/** Remove caracteres inválidos em nomes de pasta/arquivo do Windows. */
export function sanitizeFilename(name: string): string {
  const cleaned = name.replace(/[<>:"/\\|?*\x00-\x1f]/g, '_').trim().replace(/[. ]+$/, '');
  return cleaned.slice(0, 180) || 'playlist';
}

/** Seletor -f do yt-dlp a partir das opções de vídeo (0/'' = melhor disponível). */
export function buildFormatSelector(opts: Opts): string {
  const height = Number(opts.resolution) || 0;
  const fps = Number(opts.fps) || 0;
  const vf = [
    height && `height<=${height}`,
    fps && `fps<=${fps}`,
    opts.vcodec && `vcodec~='^${opts.vcodec}'`,
  ].filter(Boolean).map((f) => `[${f}]`).join('');
  const af = opts.acodec ? `[acodec~='^${opts.acodec}']` : '';
  return `bestvideo${vf}+bestaudio${af}/best${height ? `[height<=${height}]` : ''}`;
}

/** Nome final do arquivo. Áudio = só o título (artista vai só no ID3); vídeo = título + canal. */
export function outputTemplate(job: Job): string {
  const folder: string = job.options.folder;
  if (job.mode === 'video') return path.join(folder, '%(title)s - %(channel,uploader)s.%(ext)s');
  return path.join(folder, job.title ? `${job.title.replace(/[/\\]/g, '-')}.%(ext)s` : '%(title)s.%(ext)s');
}

export function buildCommand(job: Job, outTemplate: string, ytdlp: string, ffdir: string): string[] {
  const s = job.options;
  const str = (key: string) => String(s[key] ?? '').trim();
  const fields = '%(title)s@@@%(artist|)s@@@%(playlist_index|)s@@@%(playlist_count|)s';
  const args = [
    // --progress: o --print implica --quiet, e sem isto nenhuma linha "[download] N%" sai (barra parada)
    ytdlp, job.url.trim(), '--encoding', 'utf-8', '--newline', '--progress', '--no-color', '--no-warnings', '--ignore-errors',
    '--ffmpeg-location', ffdir,
    '--print', `before_dl:BDL@@@${fields}`,
    '--print', `after_move:ADL@@@${fields}`,
    '-o', str('output_template') || outTemplate,
  ];

  for (const [key, flag] of Object.entries(BOOL_FLAGS)) if (s[key]) args.push(flag);
  for (const [key, flag] of Object.entries(VALUE_FLAGS)) if (str(key)) args.push(flag, str(key));
  if (s.skip_downloaded) args.push('--download-archive', path.join(s.folder || '.', 'download_archive.txt'));

  const duration = [
    str('min_duration') && `duration >=? ${str('min_duration')}`,
    str('max_duration') && `duration <=? ${str('max_duration')}`,
  ].filter(Boolean).join(' & ');
  if (duration) args.push('--match-filters', duration);

  // recorte de trecho
  if (s.trim_start || s.trim_end) {
    args.push('--download-sections', `*${s.trim_start || '0'}-${s.trim_end || 'inf'}`, '--force-keyframes-at-cuts');
  }

  if (s.embed_metadata_thumb) {
    args.push('--embed-metadata', '--embed-thumbnail', '--parse-metadata', 'release_year:%(release_year)s');
  }

  // --write-thumbnail só é forçado sem o usuário pedir quando é playlist E
  // "Salvar capa na pasta" está ativo (para gerar o playlistcover.jpg). Numa
  // música avulsa nunca sobra um arquivo de capa que o usuário não pediu.
  const isPlaylist = Boolean(s._is_playlist);
  const saveThumbFile = Boolean(s.save_thumbnail) || (job.mode === 'audio' && Boolean(s.save_folder_cover) && isPlaylist);
  if (saveThumbFile && isPlaylist) {
    // a capa DA PLAYLIST (não das faixas) vem com nome fixo -> vira playlistcover.jpg
    args.push('-o', 'pl_thumbnail:' + path.join(s.folder, 'playlist_thumb.%(ext)s'));
  }
  // áudio: capa sempre .jpg recortada 1:1; vídeo: nunca recorta
  const squareCrop = job.mode === 'audio' && (saveThumbFile || Boolean(s.embed_metadata_thumb));
  if (saveThumbFile) args.push('--write-thumbnail');
  if (saveThumbFile || squareCrop) args.push('--convert-thumbnail', 'jpg');
  if (squareCrop) args.push('--ppa', SQUARE_CROP_PPA);

  if (job.mode === 'audio') {
    args.push('-x', '--audio-format', s.format || 'mp3', '--audio-quality', s.quality || '0');
    args.push(s.keep_video ? '--keep-video' : '--no-keep-video');
    const meta = [
      job.title && `-metadata title=${shlexQuote(job.title)}`,
      job.artist && `-metadata artist=${shlexQuote(job.artist)}`,
    ].filter(Boolean);
    if (meta.length && (s.embed_audio_tags ?? true)) args.push('--postprocessor-args', 'ffmpeg:' + meta.join(' '));
  } else {
    args.push('-f', buildFormatSelector(s));
    if (s.container) args.push('--merge-output-format', s.container);
    if (s.subtitles) {
      args.push('--write-subs', '--write-auto-subs', '--embed-subs');
      if (str('sub_langs')) args.push('--sub-langs', str('sub_langs'));
      if (str('sub_format')) args.push('--convert-subs', str('sub_format'));
    }
  }
  return args;
}

// ---- conversor ---------------------------------------------------------------

// formato -> [extensão, argumentos do codec, bitrate por qualidade Alta/Média/Baixa; null = sem perdas]
export const AUDIO: Record<string, [string, string[], string[] | null]> = {
  'MP3': ['mp3', ['-c:a', 'libmp3lame'], ['320k', '192k', '128k']],
  'M4A (AAC)': ['m4a', ['-c:a', 'aac'], ['256k', '192k', '128k']],
  'Opus': ['opus', ['-c:a', 'libopus'], ['192k', '128k', '96k']],
  'FLAC': ['flac', ['-c:a', 'flac'], null],
  'WAV': ['wav', ['-c:a', 'pcm_s16le'], null],
};
// formato -> [extensão, argumentos, CRF por qualidade Alta/Média/Baixa (maior = menor arquivo)]
export const VIDEO: Record<string, [string, string[], string[]]> = {
  'MP4 (H.264)': ['mp4', ['-c:v', 'libx264', '-preset', 'medium', '-c:a', 'aac', '-b:a', '192k'], ['18', '23', '28']],
  'MKV (H.265)': ['mkv', ['-c:v', 'libx265', '-preset', 'medium', '-c:a', 'aac', '-b:a', '192k'], ['20', '26', '32']],
  'WEBM (VP9)': ['webm', ['-c:v', 'libvpx-vp9', '-b:v', '0', '-c:a', 'libopus', '-b:a', '128k'], ['28', '34', '40']],
};

/** quality: 0=Alta, 1=Média, 2=Baixa. Com targetBytes (compressor) a qualidade é
 *  ignorada e o bitrate sai do tamanho alvo / duração. Lança Error se o alvo não for possível. */
export function buildFfmpegCmd(
  src: string, fmt: string, quality: number, res: string, ffmpeg: string, targetBytes = 0, duration = 0,
): { cmd: string[]; out: string } {
  // 1 passagem com teto de bitrate; tamanho fica perto do alvo (±~5%), 2-pass se precisar exato
  const kbps = targetBytes ? (targetBytes * 8 / duration / 1000) * 0.97 : 0; // 3% de folga p/ contêiner
  let ext: string;
  let args: string[];
  if (fmt in AUDIO) {
    const [e, codec, rates] = AUDIO[fmt];
    if (kbps && !rates) throw new Error(`${fmt} é sem perdas: tamanho alvo não se aplica.`);
    const rate = kbps ? `${Math.min(Math.floor(kbps), 320)}k` : rates?.[quality];
    ext = e;
    args = ['-vn', ...codec, ...(rate ? ['-b:a', rate] : [])];
  } else {
    const [e, codec, crfs] = VIDEO[fmt];
    ext = e;
    if (kbps) {
      const vk = Math.floor(kbps - parseInt(codec[codec.indexOf('-b:a') + 1]));
      if (vk < 100) {
        throw new Error(`Tamanho alvo pequeno demais pra ${duration.toFixed(0)}s de vídeo (daria ${Math.max(vk, 0)} kbps de vídeo).`);
      }
      // -b:v no fim sobrescreve o '-b:v 0' do VP9 (no ffmpeg vale a última opção)
      args = [...codec, '-b:v', `${vk}k`, '-maxrate', `${vk}k`, '-bufsize', `${vk * 2}k`];
    } else {
      args = [...codec, '-crf', crfs[quality]];
    }
    if (res !== 'Original') args.push('-vf', `scale=-2:'min(ih,${parseInt(res)})'`); // só reduz, nunca aumenta
  }
  const out = path.join(path.dirname(src), `${path.stem(src)}_convertido.${ext}`);
  return { cmd: [ffmpeg, '-hide_banner', '-y', '-i', src, ...args, '-progress', 'pipe:1', '-nostats', out], out };
}

// ---- verificação de playlist ---------------------------------------------------

const PL_ERR_RE = /ERROR:\s*\[.*?\]\s*([\w-]+):\s*(.*)/;

/** Lista as faixas indisponíveis da playlist com posição e vizinhas.
 *  run(...args) executa o yt-dlp e devolve as linhas de stdout+stderr. */
export async function checkPlaylist(
  emit: (line: string) => void, run: (...args: string[]) => Promise<string[]>,
): Promise<void> {
  emit('Obtendo a estrutura da playlist...');
  const items = (await run('--flat-playlist', '--print', '%(id)s\t%(title)s'))
    .map((line) => line.split('\t')).filter((p) => p.length >= 2)
    .map(([id, ...rest]) => ({ id, title: rest.join('\t') }));
  if (!items.length) {
    emit('[erro] Não foi possível carregar a playlist. Verifique o link.');
    return;
  }
  const pos = new Map(items.map((it, i) => [it.id, i]));
  emit(`Testando a disponibilidade de ${items.length} faixas...`);
  let missing = 0;
  for (const line of await run('-i', '-s', '--print', 'OK:%(id)s')) {
    const m = PL_ERR_RE.exec(line);
    const i = m ? pos.get(m[1]) : undefined;
    if (!m || i === undefined) continue;
    missing++;
    const before = i ? items[i - 1].title : '[Início da playlist]';
    const after = i + 1 < items.length ? items[i + 1].title : '[Fim da playlist]';
    emit(`✖ ${i + 1} - ${items[i].title} — depois de "${before}" e antes de "${after}"`);
    emit(`   Motivo: ${m[2]}`);
  }
  emit(missing ? `${missing} faixa(s) indisponível(is).` : 'Todas as músicas estão disponíveis na playlist!');
}
