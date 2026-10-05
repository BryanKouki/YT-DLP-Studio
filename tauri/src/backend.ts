/** Lógica do app: configurações, dependências, fila de downloads e conversor.
 *  Fala com a casca nativa (src-tauri/src/main.rs) por invoke() e eventos, e com a
 *  interface (renderer.ts) pelo objeto `api`. */
import * as core from './core.js';

const { path } = core;

interface Init { dir: string; home: string; tar: string; settings: Record<string, any> | null }
declare global {
  interface Window { __INIT__: Init; __TAURI__: any }
}
const INIT = window.__INIT__;
const invoke: (cmd: string, args?: Record<string, unknown>) => Promise<any> = window.__TAURI__.core.invoke;

// ---- configurações (data/settings.json) ----------------------------------------

const settings: Record<string, any> = {
  language: 'pt',
  theme: 'dark',

  audio_folder: path.join(INIT.home, 'Music', 'Download'),
  video_folder: path.join(INIT.home, 'Videos', 'Download'),

  // Rede
  speed_limit: '',
  proxy: '',
  playlist_items: '',
  output_template: '',

  // Filtros
  date_after: '',
  date_before: '',
  min_filesize: '',
  max_filesize: '',
  min_duration: '',
  max_duration: '',

  // Comportamento do download
  restrict_filenames: false,
  no_playlist: false,
  skip_downloaded: false,
  geo_bypass: false,
  no_check_certificate: false,
  force_ipv4: false,
  write_comments: false,
  live_from_start: false,
  windows_safe_names: false,
  no_overwrites: false,
  concurrent_fragments: '',
  retries: '',
  fragment_retries: '',
  trim_filenames: '',
  age_limit: '',
  sleep_interval: '',

  // Arquivos extras
  embed_metadata_thumb: true,
  embed_chapters: false,
  split_chapters: false,
  write_description: false,
  write_info_json: false,
  embed_audio_tags: true,
  keep_video: false,
  sub_langs: 'en.*',
  sub_format: '',
  save_folder_cover: true,

  ui: {}, // seleções de cada aba, lembradas entre sessões ("audio.format": "mp3", ...)
  window_size: null,
  ...INIT.settings,
};

function saveSettings(patch: Record<string, unknown>): void {
  Object.assign(settings, patch);
  void invoke('write_text', { path: path.join(INIT.dir, 'settings.json'), text: JSON.stringify(settings, null, 2) });
}

const BIN = path.join(INIT.dir, 'bin');
const YTDLP = path.join(BIN, 'yt-dlp.exe');
const FFMPEG = path.join(BIN, 'ffmpeg.exe');
const FFPROBE = path.join(BIN, 'ffprobe.exe');

let resizeTimer = 0;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => saveSettings({ window_size: [window.innerWidth, window.innerHeight] }), 500);
});

// ---- eventos para a interface --------------------------------------------------

let listener: (kind: string, data: any) => void = () => {};
const send = (kind: string, data?: unknown) => listener(kind, data);
const log = (line: string) => send('log', line);

// ---- processos -----------------------------------------------------------------

let nextId = 1;
const onProcLine = new Map<number, (line: string, isErr: boolean) => void>();
const onProcExit = new Map<number, (code: number) => void>();
const onDownloadPct = new Map<number, (pct: number | null) => void>();
const { listen } = window.__TAURI__.event;
await Promise.all([
  listen('proc', (e: { payload: [number, string, boolean] }) => onProcLine.get(e.payload[0])?.(e.payload[1], e.payload[2])),
  listen('exit', (e: { payload: [number, number] }) => onProcExit.get(e.payload[0])?.(e.payload[1])),
  listen('dl', (e: { payload: [number, number] }) => onDownloadPct.get(e.payload[0])?.(e.payload[1] < 0 ? null : e.payload[1])),
]);

const kill = (id: number) => void invoke('kill', { id });

/** Roda um processo entregando a saída linha a linha. done resolve com o código de saída (-1 = não iniciou). */
function runLines(exe: string, args: string[], onLine: (line: string) => void, withStderr = true, timeout = 0) {
  const id = nextId++;
  onProcLine.set(id, (line, isErr) => {
    if (withStderr || !isErr) onLine(line);
  });
  const timer = timeout ? setTimeout(() => kill(id), timeout) : 0;
  const done = new Promise<number>((resolve) => {
    onProcExit.set(id, resolve);
    invoke('spawn', { id, exe, args }).catch(() => resolve(-1));
  }).finally(() => {
    clearTimeout(timer);
    onProcLine.delete(id);
    onProcExit.delete(id);
  });
  return { id, done };
}

/** yt-dlp com saída em UTF-8 (senão títulos com acento chegam quebrados pelo pipe do Windows). */
async function ytdlpLines(args: string[], withStderr: boolean, timeout = 0): Promise<string[]> {
  const lines: string[] = [];
  await runLines(YTDLP, ['--encoding', 'utf-8', ...args], (l) => lines.push(l), withStderr, timeout).done;
  return lines;
}

// ---- dependências (yt-dlp + FFmpeg em data/bin; nada vem embutido no .exe) -----------

const YTDLP_URL = 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe';
const FFMPEG_URL = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip';
const DEPS = {
  ytdlp: { exe: YTDLP, versionArg: '--version', size: '15MB' }, // o texto do i18n já põe o "~"
  ffmpeg: { exe: FFMPEG, versionArg: '-version', size: '100MB' },
};
type Dep = keyof typeof DEPS;

const depReport = (component: Dep, state: string, extra = {}) => send('dep', { component, state, extra });

async function checkDep(component: Dep): Promise<boolean> {
  const { exe, versionArg } = DEPS[component];
  return (await invoke('is_file', { path: exe })) && (await runLines(exe, [versionArg], () => {}, true, 15000).done) === 0;
}

async function download(url: string, dest: string, onPct: (pct: number | null) => void): Promise<void> {
  const id = nextId++;
  onDownloadPct.set(id, onPct);
  try {
    await invoke('download', { id, url, dest });
  } finally {
    onDownloadPct.delete(id);
  }
}

async function installDep(component: Dep): Promise<void> {
  const { size } = DEPS[component];
  const onPct = (pct: number | null) => depReport(component, 'downloading', { size, pct });
  depReport(component, 'downloading', { size });
  let ok = false;
  try {
    await invoke('mkdir', { path: BIN });
    if (component === 'ytdlp') {
      await download(YTDLP_URL, YTDLP, onPct);
    } else {
      const zip = path.join(BIN, 'ffmpeg.zip');
      await download(FFMPEG_URL, zip, onPct);
      // só Windows — usa o tar.exe (bsdtar) do sistema pra extrair o zip, sem dependência.
      // Caminho absoluto de propósito: o tar do Git (GNU) no PATH não lê zip.
      await runLines(INIT.tar,
        ['-xf', zip, '-C', BIN, '--strip-components=2', '*/bin/ffmpeg.exe', '*/bin/ffprobe.exe'], () => {}, true, 120000).done;
      await invoke('remove', { path: zip });
    }
    ok = await checkDep(component);
  } catch {
    // sem internet, disco cheio...: fica como erro e o usuário tenta de novo pelo botão
  }
  depReport(component, ok ? 'ok' : 'error');
}

async function ensureDeps(force = false, initial = false): Promise<void> {
  if (initial) log(`Verificando dependências... (pasta: ${BIN})`);
  for (const component of ['ytdlp', 'ffmpeg'] as const) {
    depReport(component, 'checking');
    if (!force && (await checkDep(component))) depReport(component, 'ok');
    else await installDep(component);
  }
}

// ---- fila de downloads ---------------------------------------------------------

let jobs: core.Job[] = [];
let running = false;
let currentId = 0;
let canceled = false;

async function runQueue(): Promise<void> {
  if (running) return;
  running = true;
  for (let job; (job = jobs.find((j) => j.status === 'queued')); ) await runJob(job);
  running = false;
}

/** Cancela só o item atual; a fila continua. */
function cancelCurrent(): void {
  if (!running) return;
  canceled = true;
  if (currentId) kill(currentId);
}

async function runJob(job: core.Job): Promise<void> {
  canceled = false;
  Object.assign(job, { status: 'downloading', progress: 0, nowTitle: '', nowArtist: '', idx: '', count: '' });
  send('job', job);
  log(`Iniciando: ${job.url}`);

  if (!(await invoke('is_file', { path: YTDLP }))) {
    Object.assign(job, { status: 'error', errorMsg: 'yt-dlp não encontrado' });
    send('job', job);
    log('[erro] yt-dlp não encontrado');
    return;
  }

  // tem que rodar antes de montar o nome do arquivo e o comando (muda pasta/título do job)
  await resolvePlaylistFolder(job);
  await invoke('mkdir', { path: job.options.folder });
  const cmd = core.buildCommand(job, core.outputTemplate(job), YTDLP, BIN);
  log('$ ' + cmd.map(core.shlexQuote).join(' '));

  let code = -1;
  if (!canceled) {
    const run = runLines(cmd[0], cmd.slice(1), (line) => {
      const now = core.NOW_PLAYING_RE.exec(line);
      if (now) {
        const [nowTitle = '', nowArtist = '', idx = '', count = ''] = now[2].split('@@@');
        Object.assign(job, { nowTitle, nowArtist: nowArtist.trim(), idx: idx.trim(), count: count.trim() });
        send('job', job);
        send('now', { id: job.id, phase: now[1] === 'BDL' ? 'start' : 'done' });
        return;
      }
      const pct = core.PROGRESS_RE.exec(line);
      if (pct) {
        job.progress = parseFloat(pct[1]);
        send('job', job);
        return; // só move a barra; não enche o Log com uma linha por porcentagem
      }
      log(line);
    });
    currentId = run.id;
    code = await run.done;
    currentId = 0;
  }

  if (canceled && code !== 0) {
    job.status = 'canceled';
    log(`Cancelado: ${job.url}`);
  } else if (code === 0) {
    job.status = 'done';
    job.progress = 100;
    log(`Concluído: ${job.url}`);
    const o = job.options;
    if (o._is_playlist && (o.save_thumbnail || (job.mode === 'audio' && o.save_folder_cover))) {
      await promoteFolderCover(o.folder, job.mode === 'audio');
      await cleanupStrayThumbnails(o.folder); // só a capa da playlist fica
      log('Capa da playlist salva (playlistcover.jpg)');
    }
  } else {
    job.status = 'error';
    job.errorMsg = `yt-dlp saiu com código ${code}`;
    log(`[erro] código ${code}: ${job.url}`);
  }
  send('job', job);
}

/** Se o link for uma playlist, cria uma subpasta com o nome dela dentro da pasta de destino. */
async function resolvePlaylistFolder(job: core.Job): Promise<void> {
  const url = job.url.trim();
  const out = await ytdlpLines(
    ['--get-filename', '--no-warnings', '-o', '%(playlist_title)s', url, '--playlist-items', '1'], false, 20000);
  const name = out.at(-1) ?? '';
  if (!name || name.toUpperCase() === 'NA' || name === url) return;
  const target = path.join(job.options.folder, core.sanitizeFilename(name));
  if (!(await invoke('mkdir', { path: target }))) return;
  job.options.folder = target;
  job.options._is_playlist = true;
  // título/artista digitados valem pra UMA faixa; numa playlist viravam nome de
  // arquivo e ID3 fixos em todas (cada faixa sobrescrevia a anterior).
  job.title = job.artist = '';
  log(`Playlist detectada: ${name} → ${target}`);
}

/** Imagens da pasta: [nome, data de modificação]. Pasta ilegível = lista vazia (capa é opcional). */
async function thumbnails(folder: string): Promise<[string, number][]> {
  const files: [string, number][] = await invoke('list_dir', { path: folder });
  return files.filter(([name]) => core.THUMB_EXTS.includes(path.extname(name)));
}

/** Promove a capa da playlist (ou, na falta, a imagem mais antiga) para playlistcover.jpg. */
async function promoteFolderCover(folder: string, square: boolean): Promise<void> {
  const target = path.join(folder, 'playlistcover.jpg');
  if (await invoke('is_file', { path: target })) return; // já promovida antes; não sobrescreve
  const isPl = (name: string) => Number(path.stem(name) === 'playlist_thumb');
  // fallback por mtime, playlists sem capa própria pegam a 1ª faixa
  const [source] = (await thumbnails(folder))
    .filter(([name]) => path.stem(name).toLowerCase() !== 'playlistcover')
    .sort((a, b) => isPl(b[0]) - isPl(a[0]) || a[1] - b[1]);
  if (!source) return;
  const src = path.join(folder, source[0]);
  const crop = square ? ['-vf', "crop='if(gt(ih,iw),iw,ih)':'if(gt(iw,ih),ih,iw)'"] : [];
  const converted = (square || path.extname(src) !== '.jpg') &&
    (await runLines(FFMPEG, ['-y', '-i', src, ...crop, target], () => {}, true, 30000).done) === 0;
  if (!converted) await invoke('copy', { from: src, to: target });
}

/** Remove as thumbnails por faixa que sobraram quando --write-thumbnail só serviu pra gerar a capa da playlist. */
async function cleanupStrayThumbnails(folder: string): Promise<void> {
  for (const [name] of await thumbnails(folder)) {
    if (name !== 'playlistcover.jpg') await invoke('remove', { path: path.join(folder, name) });
  }
}

/** Título, artista e duração de um link, sem baixar nada. Campos vazios/0 em caso de falha.
 *  'artist' usa só %(artist)s, de propósito SEM cair para uploader/canal. */
async function probe(url: string) {
  if (!(await invoke('is_file', { path: YTDLP }))) return { title: '', artist: '', duration: 0 };
  const out = await ytdlpLines(['--print', '%(title|)s@@@%(artist|)s@@@%(duration|0)s', '--no-warnings',
    '--skip-download', '--playlist-items', '1', url.trim()], false, 15000);
  const [title = '', artist = '', dur = '0'] = (out.at(-1) ?? '').split('@@@');
  return { title: title.trim(), artist: artist.trim(), duration: Math.floor(parseFloat(dur)) || 0 };
}

// ---- conversor -----------------------------------------------------------------

const DUR_RE = /Duration: (\d+):(\d+):(\d+(?:\.\d+)?)/;
const TIME_RE = /out_time_us=(\d+)/;
let converting = false;
let convId = 0;
let convCanceled = false;

interface ConvertParams { src: string; fmt: string; quality: number; res: string; target: number }

async function convert(p: ConvertParams): Promise<{ error?: string; busy?: boolean }> {
  if (converting) return { busy: true };
  if (!p.src || !(await invoke('is_file', { path: p.src }))) return { error: 'conv_no_file' };
  if (!(await invoke('is_file', { path: FFMPEG }))) return { error: 'conv_no_ffmpeg' };
  converting = true;
  convCanceled = false;
  // setTimeout: quem chamou recebe a resposta antes do 1º evento 'conv'
  setTimeout(() => void runConvert(p).finally(() => (converting = false)));
  return {};
}

async function runConvert(p: ConvertParams): Promise<void> {
  let cmd: string[];
  let out: string;
  try {
    const duration = p.target ? await probeDuration(p.src) : 0;
    if (p.target && !duration) throw new Error('Não foi possível ler a duração do arquivo.');
    ({ cmd, out } = core.buildFfmpegCmd(p.src, p.fmt, p.quality, p.res, FFMPEG, p.target, duration));
  } catch (e) {
    send('conv', { done: true, ok: false, info: (e as Error).message });
    return;
  }
  log('$ ' + cmd.join(' '));
  let total = 0;
  const tail: string[] = []; // guarda o fim pra mostrar o erro no Log
  const run = runLines(cmd[0], cmd.slice(1), (line) => {
    if (tail.push(line) > 5) tail.shift();
    const dur = !total && DUR_RE.exec(line);
    const time = total && TIME_RE.exec(line);
    if (dur) total = +dur[1] * 3600 + +dur[2] * 60 + parseFloat(dur[3]);
    else if (time) send('conv', { progress: +time[1] / 1e6 / total });
  });
  convId = run.id;
  const ok = (await run.done) === 0;
  convId = 0;
  if (!ok) await invoke('remove', { path: out }); // não deixa arquivo pela metade
  send('conv', { done: true, ok, canceled: convCanceled, info: ok ? out : tail.join('\n') });
}

/** Duração em segundos via ffprobe (0 se não der pra ler). */
async function probeDuration(src: string): Promise<number> {
  let text = '';
  await runLines(FFPROBE, ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', src],
    (l) => (text = l), false).done;
  return parseFloat(text) || 0;
}

// ---- o que a interface pode chamar ---------------------------------------------

interface NewJobs { mode: core.Mode; urls: string[]; opts: core.Opts }

const handlers: Record<string, (...args: any[]) => unknown> = {
  saveSettings,
  pickFolder: (initial?: string) => invoke('pick', { folder: true, initial }),
  pickFile: () => invoke('pick', { folder: false }),
  openFolder: async (folder: string, create = false) => {
    if (create) await invoke('mkdir', { path: folder });
    return invoke('open_path', { path: folder });
  },
  openBin: () => invoke('open_path', { path: BIN }),
  copy: (text: string) => navigator.clipboard.writeText(text),

  probe,
  checkPlaylist: (url: string) =>
    core.checkPlaylist(log, (...args) => ytdlpLines(['--no-warnings', ...args, url.trim()], true)),
  checkDeps: ensureDeps,
  updateYtdlp: () => installDep('ytdlp'),

  addJobs: ({ mode, urls, opts }: NewJobs, start: boolean) => {
    for (const url of urls) {
      jobs.push({
        id: crypto.randomUUID().slice(0, 8), mode, url,
        title: mode === 'audio' ? opts.title ?? '' : '',
        artist: mode === 'audio' ? opts.artist ?? '' : '',
        options: { ...settings, ...opts, folder: settings[`${mode}_folder`] },
        status: 'queued', progress: 0, errorMsg: '', nowTitle: '', nowArtist: '', idx: '', count: '',
      });
    }
    send('jobs', jobs);
    if (start) void runQueue();
  },
  queueStart: () => void runQueue(),
  queueCancel: cancelCurrent,
  clearFinished: () => {
    jobs = jobs.filter((j) => j.status === 'queued' || j.status === 'downloading');
    send('jobs', jobs);
  },
  clearAll: () => {
    if (running) return;
    jobs = [];
    send('jobs', jobs);
  },

  convert,
  convertCancel: () => {
    if (!convId) return;
    convCanceled = true;
    kill(convId);
  },
};

export const api = {
  init: { settings, jobs },
  call: async (name: string, ...args: unknown[]): Promise<any> => handlers[name](...args),
  on: (cb: (kind: string, data: any) => void): void => {
    listener = cb;
  },
};
