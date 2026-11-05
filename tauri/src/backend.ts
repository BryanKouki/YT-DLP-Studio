/** Lógica do app: configurações, dependências, fila de downloads e conversor.
 *  Fala com a casca nativa (src-tauri/src/main.rs) por invoke() e eventos, e com a
 *  interface (renderer.ts) pelo objeto `api`. */
import * as core from './core.js';

const { path } = core;

interface Init { dir: string; home: string; tar: string; version: string; settings: Record<string, any> | null }
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
  keep_video: false,
  sub_langs: 'en.*',
  sub_format: '',
  parallel_tracks: '1', // músicas ao mesmo tempo em cada playlist (1 a 5)
  pause_on_error: true, // item com erro pausa a fila: continuar, tentar de novo ou cancelar
  pause_failed: 'each', // faixas de playlist falharam: 'each' pausa depois da playlist, 'end' no fim da fila, 'off' não pausa
  use_cookies: false,
  cookies_on_bot: false, // só liga os cookies no primeiro bloqueio "not a bot" (até fechar o app)
  cookies_browser: 'firefox', // não Chromium: o yt-dlp lê sem o erro de DPAPI do Windows

  // "Propriedades do arquivo": tag_audio_title, tag_video_cover... tudo ligado, menos o gênero (consulta a Apple)
  ...Object.fromEntries((['audio', 'video'] as const).flatMap((mode) =>
    core.TAGS[mode].map((tag) => [`tag_${mode}_${tag}`, tag !== 'genre']))),

  ui: {}, // seleções de cada aba, lembradas entre sessões ("audio.format": "mp3", ...)
  window_size: null,
  ...INIT.settings,
};
// a v1.2.0 guardava liga/desliga
if (typeof settings.pause_failed === 'boolean') settings.pause_failed = settings.pause_failed ? 'each' : 'off';

function saveSettings(patch: Record<string, unknown>): void {
  Object.assign(settings, patch);
  void invoke('write_text', { path: path.join(INIT.dir, 'settings.json'), text: JSON.stringify(settings, null, 2) });
}

const BIN = path.join(INIT.dir, 'bin');
// versão em pasta do yt-dlp: abre em ~1 s; a de arquivo único se descompacta a cada execução (4-7 s medidos)
const YTDLP_DIR = path.join(BIN, 'yt-dlp');
const YTDLP = path.join(YTDLP_DIR, 'yt-dlp.exe');
const FFMPEG = path.join(BIN, 'ffmpeg.exe');
const FFPROBE = path.join(BIN, 'ffprobe.exe');
const DENO = path.join(BIN, 'deno.exe');
const TEMP = path.join(INIT.dir, 'tmp'); // intermediários do yt-dlp: a pasta de destino só vê o arquivo pronto

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

// fechar a janela pede confirmação na interface (o Rust segura o fechamento e avisa aqui)
await listen('close_requested', () =>
  send('close_requested', { busy: running || jobs.some((j) => j.status === 'queued' || j.status === 'downloading') }));

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
async function ytdlpLines(args: string[], withStderr: boolean, timeout = 0, cookies = true): Promise<string[]> {
  const lines: string[] = [];
  await runLines(YTDLP, ['--encoding', 'utf-8', ...core.jsRuntimeArgs(BIN), ...(cookies ? core.cookieArgs({ use_cookies: cookiesNow(), cookies_browser: settings.cookies_browser }) : []), ...args],
    (l) => lines.push(l), withStderr, timeout).done;
  return lines;
}

// ---- navegador aberto trava o arquivo de cookies --------------------------------

// só os Chromium travam o arquivo de cookies enquanto abertos; o Firefox é lido aberto mesmo
const BROWSERS: Record<string, { exe: string; name: string }> = {
  edge: { exe: 'msedge.exe', name: 'Microsoft Edge' },
  chrome: { exe: 'chrome.exe', name: 'Google Chrome' },
  brave: { exe: 'brave.exe', name: 'Brave' },
  chromium: { exe: 'chrome.exe', name: 'Chromium' },
  opera: { exe: 'opera.exe', name: 'Opera' },
  vivaldi: { exe: 'vivaldi.exe', name: 'Vivaldi' },
  whale: { exe: 'whale.exe', name: 'Naver Whale' },
};
let answerClose: ((ok: boolean) => void) | null = null;

/** Com cookies ligados e o navegador aberto (o Edge fica em segundo plano mesmo sem janelas),
 *  pergunta na tela e, se o usuário aceitar, fecha o navegador antes de baixar. */
async function closeBrowserForCookies(job: core.Job): Promise<void> {
  const browser = BROWSERS[job.options.cookies_browser];
  if (!browser) return;
  const tasks: string[] = [];
  await runLines('tasklist', ['/FI', `IMAGENAME eq ${browser.exe}`, '/NH'], (l) => tasks.push(l), true, 15000).done;
  if (!tasks.some((line) => line.toLowerCase().startsWith(browser.exe))) return;
  send('confirm_close', browser.name);
  const ok = await new Promise<boolean>((resolve) => (answerClose = resolve));
  answerClose = null;
  if (!ok) return log(`[cookies] ${browser.name} continua aberto; os cookies provavelmente não serão lidos.`);
  await runLines('taskkill', ['/F', '/T', '/IM', browser.exe], () => {}, true, 15000).done;
  await new Promise((resolve) => setTimeout(resolve, 1500)); // o Windows solta o arquivo de cookies logo depois
  log(`[cookies] ${browser.name} fechado para ler os cookies.`);
}

// ---- dependências (yt-dlp + FFmpeg em data/bin; nada vem embutido no .exe) -----------

const YTDLP_URL = 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_win.zip';
const FFMPEG_URL = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip';
const DENO_URL = 'https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip';
const DEPS = {
  ytdlp: { exe: YTDLP, versionArg: '--version', size: '25MB' }, // o texto do i18n já põe o "~"
  ffmpeg: { exe: FFMPEG, versionArg: '-version', size: '100MB' },
  deno: { exe: DENO, versionArg: '--version', size: '45MB' },
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
      const zip = path.join(BIN, 'yt-dlp.zip');
      await download(YTDLP_URL, zip, onPct);
      await invoke('mkdir', { path: YTDLP_DIR });
      await runLines(INIT.tar, ['-xf', zip, '-C', YTDLP_DIR], () => {}, true, 120000).done;
      await invoke('remove', { path: zip });
      await invoke('remove', { path: path.join(BIN, 'yt-dlp.exe') }); // a versão antiga, de arquivo único
    } else if (component === 'deno') {
      const zip = path.join(BIN, 'deno.zip');
      await download(DENO_URL, zip, onPct);
      await runLines(INIT.tar, ['-xf', zip, '-C', BIN, 'deno.exe'], () => {}, true, 120000).done;
      await invoke('remove', { path: zip });
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
  for (const component of ['ytdlp', 'ffmpeg', 'deno'] as const) {
    depReport(component, 'checking');
    if (!force && (await checkDep(component))) depReport(component, 'ok');
    else await installDep(component);
  }
}

// ---- fila de downloads ---------------------------------------------------------

let jobs: core.Job[] = [];
let running = false;
let currentIds: number[] = []; // processos do yt-dlp do item atual (vários com "músicas ao mesmo tempo")
let canceled = false;
let botCookies = false; // "só quando bloquear": virou true no primeiro bloqueio desta sessão

/** Cookies valem para este download? Com "só quando bloquear", só depois do primeiro bloqueio. */
const cookiesNow = () => Boolean(settings.use_cookies) && (!settings.cookies_on_bot || botCookies);
let resumeQueue: (() => void) | null = null; // existe enquanto a fila está pausada
let pausedOn: core.Job | null = null; // item cujas falhas pausaram a fila

/** only: baixa só esse item (o resto da fila continua esperando). */
async function runQueue(only?: core.Job): Promise<void> {
  if (running) return;
  running = true;
  const next = () => (only ? (only.status === 'queued' && jobs.includes(only) ? only : undefined)
    : jobs.find((j) => j.status === 'queued'));
  for (let job; (job = next()); ) {
    await runJob(job);
    if (job.status === 'error' && settings.pause_on_error) {
      log(`Fila pausada por erro em ${job.name || job.url}.`);
      send('error_pause', job);
      pausedOn = job;
      await new Promise<void>((resolve) => (resumeQueue = resolve));
      pausedOn = null;
      continue;
    }
    if (remaining(job) && settings.pause_failed === 'each') {
      log(`Fila pausada: ${remaining(job)} faixa(s) falharam em ${job.url}. Use "Faixas com erro" na fila.`);
      send('paused', job);
      pausedOn = job;
      await new Promise<void>((resolve) => (resumeQueue = resolve));
      pausedOn = null;
      resumeQueue = null;
      log('Fila retomada.');
    }
  }
  running = false;
  const toReview = jobs.filter(remaining);
  if (toReview.length && settings.pause_failed === 'end') {
    log(`Fila terminada: ${toReview.length} playlist(s) com faixas com erro para revisar.`);
    send('review', toReview.length);
  }
}

/** Faixas com erro que ainda não ganharam substituta. */
const remaining = (job: core.Job) => job.failed?.filter((f) => f.state !== 'done' && f.state !== 'ignored').length ?? 0;

/** Mensagens do yt-dlp que têm uma saída conhecida: explica no Log uma vez por download. */
const BOT_RE = /Sign in to confirm you.re not a bot/;
const HINTS: [RegExp, string][] = [
  [/Sign in to confirm you.re not a bot/,
    '[dica] O YouTube bloqueou temporariamente por excesso de downloads seguidos. Ative "Usar cookies do navegador" ' +
    '(com o navegador fechado) ou aumente ' +
    '"Pausa entre downloads (s)" em Configurações, ou aguarde alguns minutos antes de continuar.'],
];

/** Cancela só o item atual; a fila continua. */
function cancelCurrent(): void {
  if (!running) return;
  canceled = true;
  for (const id of currentIds) kill(id);
}

async function runJob(job: core.Job): Promise<void> {
  canceled = false;
  Object.assign(job, { status: 'downloading', progress: 0, nowTitle: '', nowArtist: '', idx: '', count: '' });
  // cookies: vale o que está nas Configurações agora, não o que estava quando o item entrou na fila
  Object.assign(job.options, { use_cookies: cookiesNow(), cookies_browser: settings.cookies_browser });
  send('job', job);
  log(`Iniciando: ${job.url}`);

  if (!(await invoke('is_file', { path: YTDLP }))) {
    Object.assign(job, { status: 'error', errorMsg: 'yt-dlp não encontrado' });
    send('job', job);
    log('[erro] yt-dlp não encontrado');
    return;
  }

  // tem que rodar antes de montar o nome do arquivo e o comando (muda pasta/título do job)
  if (job.options.use_cookies) await closeBrowserForCookies(job);
  await resolvePlaylistFolder(job);
  await invoke('mkdir', { path: job.options.folder });
  // "Músicas ao mesmo tempo": a playlist é dividida entre vários processos do yt-dlp
  const parts = await splitPlaylist(job);
  const cmds = (parts ?? [null]).map((part) => core.buildCommand(
    part ? { ...job, options: { ...job.options, playlist_items: part.join(',') } } : job,
    core.outputTemplate(job), YTDLP, BIN, TEMP));
  for (const cmd of cmds) log('$ ' + cmd.map(core.shlexQuote).join(' '));
  const parallel = cmds.length > 1;
  const total = parts?.flat().length ?? 0;
  // lista montada no app: cada link é uma faixa avulsa, a posição é a da lista
  const tracks: core.Track[] | undefined = job.options.tracks;
  const posOf = new Map(tracks?.map((t, i) => [t.id, String(i + 1)]));
  const withGenre = job.mode === 'audio' && Boolean(job.options.embed_metadata_thumb) && core.tagOn(job.options, 'audio', 'genre');
  const genres: Promise<void>[] = []; // gênero gravado em cada faixa pronta, enquanto as outras baixam
  let doneHere = 0;

  let code = -1;
  // numa retomada, o que já tinha baixado/falhado antes do bloqueio continua valendo
  const failed: core.Failed[] = [...(job.prevFailed ?? [])];
  const saved: Saved[] = [...(job.prevSaved ?? [])];
  let botHit = false;
  const hinted = new Set<string>();
  let lastError = ''; // última linha ERROR do yt-dlp: vira o motivo mostrado na fila
  let cookieFailed: '' | 'dpapi' | 'lock' = ''; // dpapi = criptografia que o yt-dlp não abre; lock = navegador aberto
  if (!canceled) {
    const onLine = (line: string) => {
      const now = core.NOW_PLAYING_RE.exec(line);
      if (now) {
        const [nowTitle = '', nowArtist = '', plIdx = '', plCount = '', id = '', file = '', album = ''] = now[2].split('@@@');
        if (now[1] === 'ADL' && file && withGenre) genres.push(writeGenre(file, nowArtist, album));
        const idx = posOf.get(id) ?? plIdx.trim();
        const count = tracks ? String(tracks.length) : plCount.trim();
        Object.assign(job, { nowTitle, nowArtist: nowArtist.trim(), idx, count });
        // BDL = faixa começou; ADL = faixa pronta na pasta (✓ ao lado do nome)
        if (now[1] === 'ADL') doneHere++;
        // com várias ao mesmo tempo a barra mostra a playlist inteira (faixas prontas / total)
        Object.assign(job, now[1] === 'BDL' ? { phase: 'download', progress: parallel ? job.progress : 0 }
          : { phase: 'done', progress: parallel ? (doneHere / total) * 100 : 100 });
        if (now[1] === 'ADL' && file) saved.push({ id, idx: idx.trim(), file });
        send('job', job);
        send('now', { id: job.id, phase: now[1] === 'BDL' ? 'start' : 'done' });
        return;
      }
      const err = core.PL_ERR_RE.exec(line);
      if (err && !failed.some((f) => f.id === err[1])) failed.push({ pos: 0, id: err[1], title: '', artist: '', reason: err[2] });
      if (line.startsWith('ERROR: ')) lastError = line.slice(7);
      if (core.COOKIE_ERR_RE.test(line)) cookieFailed = /DPAPI/.test(line) ? 'dpapi' : 'lock';
      if (BOT_RE.test(line) && !job.options.use_cookies && settings.use_cookies && settings.cookies_on_bot && !botHit) {
        botHit = true;
        for (const id of currentIds) kill(id); // para já: as próximas faixas também falhariam; retoma com cookies
        return;
      }
      if (BOT_RE.test(line) && job.options.use_cookies && !hinted.has('bot+cookies')) {
        hinted.add('bot+cookies');
        setTimeout(() => log('[dica] Os cookies do navegador foram usados, mas o YouTube ainda pediu login. Entre na sua ' +
          'conta Google no YouTube por esse navegador (só abrir o site não basta), feche-o e tente de novo. Uma pausa ' +
          'entre downloads (Configurações → "Pausa entre downloads (s)") também reduz o bloqueio.'));
      }
      for (const [re, hint] of HINTS) {
        if (re.test(line) && !hinted.has(hint) && !job.options.use_cookies) {
          hinted.add(hint);
          setTimeout(() => log(hint)); // depois da linha de erro original
        }
      }
      const pp = core.PP_RE.exec(line);
      if (pp) {
        // depois do ✓ o yt-dlp já roda etapas da PRÓXIMA faixa antes de anunciá-la: o ✓ fica até ela começar
        if (pp[1] === 'started' && job.phase !== 'done') {
          job.phase = pp[2];
          if (!parallel) job.progress = Math.max(job.progress, core.PP_PROGRESS[pp[2]] ?? job.progress);
          send('job', job);
        }
        return;
      }
      const pct = core.PROGRESS_RE.exec(line);
      if (pct) {
        job.phase = 'download';
        if (!parallel) job.progress = parseFloat(pct[1]) * 0.75; // o resto da barra é o pós-processamento
        send('job', job);
        return; // só move a barra; não enche o Log com uma linha por porcentagem
      }
      log(line);
    };
    const runs = cmds.map((cmd) => runLines(cmd[0], cmd.slice(1), onLine));
    currentIds = runs.map((run) => run.id);
    const codes = await Promise.all(runs.map((run) => run.done));
    currentIds = [];
    code = codes.find((c) => c !== 0) ?? 0;
  }
  // antes de mexer nas datas: a gravação do gênero recoloca as datas que o arquivo tinha
  if (genres.length) await Promise.all(genres);
  // baixadas fora de ordem: datas de criação/modificação voltam à ordem da playlist (é por elas que você ordena)
  if (parallel) await stampInOrder(saved);

  // "só quando bloquear": liga os cookies até fechar o app e continua da faixa onde o YouTube bloqueou
  if (botHit && !canceled) {
    botCookies = true;
    job.prevSaved = saved;
    job.prevFailed = failed.filter((f) => !BOT_RE.test(f.reason));
    const doneIdx = new Set(saved.map((s) => Number(s.idx)));
    // em partes (ou numa lista montada no app) faixas anteriores podem ter ficado pela metade: retoma exatamente as que faltam
    const pending = parts?.flat() ?? tracks?.map((_, i) => String(i + 1));
    const from = pending ? pending.filter((i) => !doneIdx.has(Number(i))).join(',') : core.resumeFrom(saved.map((s) => s.idx));
    if (job.options._is_playlist && from && (pending || !String(settings.playlist_items ?? '').trim())) job.options.playlist_items = from;
    Object.assign(job, { status: 'queued', progress: 0 });
    log(`[cookies] O YouTube bloqueou ("not a bot"). Cookies ativados até fechar o app; ` +
      (from ? `continuando a partir da faixa ${parseInt(from)}.` : 'recomeçando este item.'));
    send('bot_cookies');
    send('job', job);
    return;
  }

  // cookies ilegíveis derrubam todo item na hora: desliga a opção e baixa o mesmo item de novo, sem cookies
  if (cookieFailed && code !== 0 && !canceled && job.options.use_cookies) {
    saveSettings({ use_cookies: false });
    for (const j of jobs) if (j.status === 'queued' || j === job) j.options.use_cookies = false;
    Object.assign(job, { status: 'queued', progress: 0 });
    log(cookieFailed === 'dpapi'
      ? '[cookies] O navegador criptografa os cookies de um jeito que o yt-dlp ainda não consegue abrir ' +
        '("Failed to decrypt with DPAPI", problema conhecido do yt-dlp); fechar o navegador não resolve. ' +
        'A opção foi desativada e o item será baixado novamente sem cookies.'
      : '[cookies] Não foi possível ler os cookies: o navegador estava aberto (o Edge fica em segundo plano mesmo ' +
        'sem janelas). O yt-dlp escreve "Chrome" nessa mensagem mesmo quando é o Edge. A opção foi desativada e o ' +
        'item será baixado novamente sem cookies.');
    send('cookies_off');
    send('job', job);
    return;
  }
  if (job.options._is_playlist) job.placed = saved.map(({ idx, file }) => ({ pos: Number(idx) || 0, file }));
  if (job.options._is_playlist && failed.length && !canceled) await locateFailed(job, failed, saved);
  // playlist com algumas faixas indisponíveis: o resto baixou, então conta como concluída
  const partial = code !== 0 && Boolean(job.failed?.length) && saved.length > 0;

  if (canceled && code !== 0) {
    job.status = 'canceled';
    log(`Cancelado: ${job.url}`);
  } else if (code === 0 || partial) {
    job.status = 'done';
    job.progress = 100;
    log(`Concluído: ${job.url}` + (partial ? ` (${job.failed!.length} faixa(s) com erro)` : ''));
    const o = job.options;
    if (o._is_playlist && o.save_thumbnail) { // numa playlist, "Guardar thumbnail" = capa da playlist
      const files: [string, number][] = await invoke('list_dir', { path: TEMP });
      const early = files.find(([f]) => f.startsWith(`pl_${job.id}.`));
      if (early) { // já veio na consulta inicial
        const src = path.join(TEMP, early[0]);
        await invoke('copy', { from: src, to: path.join(o.folder, `playlist_thumb${path.extname(early[0])}`) });
        await invoke('remove', { path: src });
      } else if (tracks) { // lista montada no app: capa da 1ª faixa
        await ytdlpLines(['--skip-download', '--write-thumbnail', '--no-warnings',
          '-o', 'thumbnail:' + path.join(o.folder, 'playlist_thumb.%(ext)s'), core.trackUrls(tracks, '')[0]], true, 60000);
      } else {
        await ytdlpLines(core.playlistCoverArgs(job.url, o.folder), true, 60000); // ex.: item retomado depois de fechar
      }
      await promoteFolderCover(o.folder, job.mode === 'audio');
      await cleanupStrayThumbnails(o.folder); // apaga o playlist_thumb.* original; fica só playlistcover.jpg
      log('Capa da playlist salva (playlistcover.jpg)');
    }
    await writePlaylistFile(job);
  } else {
    job.status = 'error';
    job.errorMsg = lastError || `yt-dlp saiu com código ${code}`;
    log(`[erro] código ${code}: ${job.url}`);
  }
  send('job', job);
}

interface Saved { id: string; idx: string; file: string }

/** Índices das faixas (respeitando "Itens da playlist" e a retomada) divididos entre os processos.
 *  null = um processo só (opção em 1, não é playlist ou a listagem falhou). */
const parallelCount = () => Math.min(5, Math.max(1, Number(settings.parallel_tracks) || 1));

async function splitPlaylist(job: core.Job): Promise<string[][] | null> {
  const n = parallelCount();
  if (n < 2 || !job.options._is_playlist) return null;
  const items = String(job.options.playlist_items ?? '').trim();
  // retomada: "19,22,25" já é a lista das que faltam; senão a da consulta inicial; só lista de novo se não houver
  let idx = /^\d+(,\d+)*$/.test(items) ? items.split(',')
    : job.options.tracks?.map((_: unknown, i: number) => String(i + 1)) ?? job.indices ?? [];
  job.indices = undefined; // vale só para esta rodada
  if (!idx.length) {
    idx = (await ytdlpLines(['--flat-playlist', '--no-warnings', '--print', '%(playlist_index)s',
      ...(items ? ['--playlist-items', items] : []), job.url.trim()], false, 120000))
      .map(Number).filter((i) => i > 0).map(String);
  }
  return idx.length > 1 ? core.splitRoundRobin(idx, n) : null;
}

/** Datas dos arquivos na ordem da playlist, 1 s entre cada (as substitutas também se guiam por elas). */
async function stampInOrder(saved: Saved[]): Promise<void> {
  const ordered = [...saved].sort((a, b) => Number(a.idx) - Number(b.idx));
  const base = Date.now() - ordered.length * 1000;
  for (const [i, s] of ordered.entries()) {
    await invoke('set_times', { path: s.file, created: base + i * 1000, modified: base + i * 1000 });
  }
}

/** "Criar arquivo de playlist": <nome da playlist>.m3u8 na pasta, na ordem da playlist. */
async function writePlaylistFile(job: core.Job): Promise<void> {
  const o = job.options;
  if (!o._is_playlist || !o.save_playlist_file || !job.placed?.length) return;
  const file = path.join(o.folder, `${core.sanitizeFilename(job.name || 'playlist')}.m3u8`);
  if (await invoke('write_text', { path: file, text: core.m3uText(job.placed) })) log(`Arquivo de playlist salvo: ${file}`);
}

/** Descobre a posição e o título de cada faixa que falhou (pela lista da playlist) e
 *  guarda os arquivos baixados por posição, para encaixar substitutas entre eles. */
async function locateFailed(job: core.Job, failed: core.Failed[], saved: Saved[]): Promise<void> {
  const tracks: core.Track[] | undefined = job.options.tracks; // lista montada no app: já tem a ordem
  const order = tracks ? tracks.map((t) => [t.id, t.title, t.artist]) : (await ytdlpLines(
    ['--flat-playlist', '--no-warnings', '--print', '%(id)s\t%(title)s\t%(uploader|)s', job.url.trim()], false))
    .map((line) => line.split('\t'));
  const posOf = new Map(order.map(([id], i) => [id, i + 1]));
  for (const f of failed) {
    f.pos = posOf.get(f.id) ?? 0;
    const [, title = '', uploader = ''] = order[f.pos - 1] ?? [];
    f.title = title;
    f.artist = core.artistFromUploader(uploader);
  }
  job.failed = failed.sort((a, b) => a.pos - b.pos);
  job.placed = saved.map(({ id, idx, file }) => ({ pos: posOf.get(id) ?? (Number(idx) || 0), file }));
}

/** Baixa as músicas substitutas (links[id do vídeo que falhou]) na pasta da playlist e
 *  ajusta as datas do arquivo para ele ficar exatamente entre as faixas vizinhas. */
async function replaceFailed(jobId: string, links: Record<string, string>): Promise<void> {
  const job = jobs.find((j) => j.id === jobId);
  if (!job?.failed) return;
  for (const f of job.failed) {
    const link = links[f.id]?.trim();
    if (!link || f.state === 'done' || f.state === 'ignored') continue;
    f.state = 'downloading';
    send('job', job);
    const sub: core.Job = {
      ...job, url: link, title: '', artist: '',
      options: { ...job.options, _is_playlist: false, no_playlist: true, save_thumbnail: false },
    };
    const cmd = core.buildCommand(sub, core.outputTemplate(sub), YTDLP, BIN, TEMP);
    log(`Substituta da faixa ${f.pos} (${f.title || f.id}): ${link}`);
    log('$ ' + cmd.map(core.shlexQuote).join(' '));
    let file = '';
    let fields: string[] = [];
    const code = await runLines(cmd[0], cmd.slice(1), (line) => {
      const now = core.NOW_PLAYING_RE.exec(line);
      if (now?.[1] === 'ADL') file = (fields = now[2].split('@@@'))[5] ?? '';
      else if (!now && !core.PROGRESS_RE.test(line) && !core.PP_RE.test(line)) log(line);
    }).done;
    if (code !== 0 || !file) {
      f.state = 'error';
      log(`[erro] substituta da faixa ${f.pos} não baixou`);
      send('job', job);
      continue;
    }
    if (job.mode === 'audio' && job.options.embed_metadata_thumb && core.tagOn(job.options, 'audio', 'genre')) {
      await writeGenre(file, fields[1] ?? '', fields[6] ?? '');
    }
    const placed = (job.placed ??= []).sort((a, b) => a.pos - b.pos);
    const before = placed.filter((p) => p.pos < f.pos).at(-1);
    const after = placed.find((p) => p.pos > f.pos);
    const times = async (p?: { file: string }) => (p ? await invoke('file_times', { path: p.file }) : null);
    const [created, modified] = core.between(await times(before), await times(after), Date.now());
    await invoke('set_times', { path: file, created, modified });
    placed.push({ pos: f.pos, file }); // a próxima substituta encaixa considerando esta
    f.state = 'done';
    log(`Substituta salva na posição ${f.pos}: ${file}`);
    await writePlaylistFile(job); // a substituta entra no lugar dela no .m3u8
    send('replaced', f);
    send('job', job);
  }
}

// ---- gênero --------------------------------------------------------------------

const genreCache = new Map<string, Promise<string>>();
let genreTurn = Promise.resolve();
let genreAt = 0;
/** Gênero do álbum no catálogo da Apple: uma consulta por artista+álbum, uma a cada 3 s (limite de ~20 por minuto). */
function albumGenre(artist: string, album: string): Promise<string> {
  const key = `${artist}\n${album}`.toLowerCase();
  if (!genreCache.has(key)) {
    genreCache.set(key, new Promise((resolve) => {
      genreTurn = genreTurn.then(async () => {
        await new Promise((r) => setTimeout(r, Math.max(0, genreAt + 3000 - Date.now())));
        genreAt = Date.now();
        try {
          const res = await invoke('fetch_text', { url: core.genreUrl(artist, album, settings.language), body: null });
          resolve(core.itunesGenre(JSON.parse(res), artist));
        } catch (e) {
          log(`[aviso] Gênero não consultado (${artist} - ${album}): ${e}`);
          resolve('');
        }
      });
    }));
  }
  return genreCache.get(key)!;
}

/** Grava o gênero no arquivo pronto: cópia sem recodificar (capa e demais tags ficam) e as mesmas datas.
 *  Se o ffmpeg falhar, o arquivo original fica como estava. */
async function writeGenre(file: string, artist: string, album: string): Promise<void> {
  const ext = path.extname(file);
  if (!artist.trim() || !album.trim() || !core.GENRE_EXTS.includes(ext)) return;
  const genre = await albumGenre(artist.split(', ')[0].trim(), album.trim());
  if (!genre) return;
  const tmp = path.join(TEMP, `genre_${crypto.randomUUID().slice(0, 8)}${ext}`);
  const times: [number, number] | null = await invoke('file_times', { path: file });
  const ok = (await runLines(FFMPEG, ['-y', '-v', 'error', '-i', file, '-map', '0', '-c', 'copy',
    '-metadata', `genre=${genre}`, ...(ext === '.mp3' ? ['-id3v2_version', '3'] : []), tmp], () => {}, true, 60000).done) === 0;
  if (ok && (await invoke('copy', { from: tmp, to: file })) && times) {
    await invoke('set_times', { path: file, created: times[0], modified: times[1] });
  }
  await invoke('remove', { path: tmp });
}

/** Se o link for uma playlist, cria uma subpasta com o nome dela dentro da pasta de destino. */
async function resolvePlaylistFolder(job: core.Job): Promise<void> {
  if (job.options._is_playlist) return; // item baixado de novo (retomada, ▶): a subpasta já existe
  if (job.options.no_playlist) return; // "Somente este vídeo": o yt-dlp baixa só o vídeo do link
  const url = job.url.trim();
  // Uma chamada só, só a listagem (não abre faixa nenhuma): nome da playlist, as faixas (para dividir entre
  // processos) e a capa da playlist. --no-simulate porque o --print sozinho não grava a capa.
  // Se a primeira tentativa falhar com cookies (navegador aberto, ilegíveis), tenta de novo sem eles.
  const items = String(job.options.playlist_items ?? '').trim();
  const cover = job.options.save_thumbnail ? path.join(TEMP, `pl_${job.id}.%(ext)s`) : '';
  if (cover) await invoke('mkdir', { path: TEMP });
  const lookup = async (cookies: boolean) => (await ytdlpLines(['--flat-playlist', '--no-warnings', '--no-simulate',
    '--skip-download', ...(parallelCount() > 1 ? (items ? ['--playlist-items', items] : []) : ['--playlist-items', '1']),
    '--print', '%(playlist_title|)s\t%(playlist_index|)s',
    ...(cover ? ['--write-thumbnail', '-o', `pl_thumbnail:${cover}`, '-o', 'thumbnail:'] : []), url], false, 120000, cookies))
    .map((line) => line.split('\t'));
  const custom = Boolean(job.options.tracks); // lista montada no app: nome escolhido, nada para consultar
  let rows = custom ? [] : await lookup(true);
  if (!custom && !rows.some(([title]) => title?.trim()) && cookiesNow()) rows = await lookup(false);
  let name = String(job.options.playlist_name ?? '').trim() || (rows.find(([title]) => title?.trim())?.[0].trim() ?? '');
  job.indices = rows.map(([, idx]) => Number(idx)).filter((i) => i > 0).map(String);
  const listId = core.playlistIdFrom(url);
  if (!name || name.toUpperCase() === 'NA' || name === url) {
    if (!listId) return; // link sem playlist: música/vídeo avulso
    // é playlist, mas o nome não veio: pasta com o ID, nunca solta na pasta principal
    name = `Playlist ${listId}`;
    log(`[aviso] Não foi possível ler o nome da playlist; salvando em "${name}".`);
    send('playlist_fallback', name);
  }
  const target = path.join(job.options.folder, core.sanitizeFilename(name));
  if (!(await invoke('mkdir', { path: target }))) return;
  job.options.folder = target;
  job.options._is_playlist = true;
  // título/artista digitados valem pra UMA faixa; numa playlist viravam nome de
  // arquivo e ID3 fixos em todas (cada faixa sobrescrevia a anterior).
  job.title = job.artist = '';
  job.name ||= name;
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

/** Apaga o playlist_thumb.* original depois de virar playlistcover.jpg (capas de faixa ficam: o usuário pediu). */
async function cleanupStrayThumbnails(folder: string): Promise<void> {
  for (const [name] of await thumbnails(folder)) {
    if (path.stem(name) === 'playlist_thumb') await invoke('remove', { path: path.join(folder, name) });
  }
}

/** Título, artista, duração e (se for playlist) o nome da playlist, sem baixar nada.
 *  Campos vazios/0 em caso de falha. 'artist' usa só %(artist)s, de propósito SEM cair
 *  para uploader/canal (o nome do arquivo de áudio é só o título). */
async function probe(url: string) {
  if (!(await invoke('is_file', { path: YTDLP }))) return { title: '', artist: '', duration: 0, playlist: '' };
  // sem cookies: a busca é só para mostrar o nome, e não pode falhar com o navegador aberto
  const out = await ytdlpLines(['--flat-playlist', '--print', '%(title|)s@@@%(artist|)s@@@%(duration|0)s@@@%(playlist_title|)s',
    '--no-warnings', '--skip-download', '--playlist-items', '1', url.trim()], false, 20000, false);
  const [title = '', artist = '', dur = '0', playlist = ''] = (out.at(-1) ?? '').split('@@@');
  return { title: title.trim(), artist: artist.trim(), duration: Math.floor(parseFloat(dur)) || 0, playlist: playlist.trim() };
}

/** API do YouTube Music (a mesma do site), pela casca nativa: a página não pode acessar outros sites. */
const ytm = async (endpoint: string, extra: Record<string, string>) => JSON.parse(await invoke('fetch_text',
  { url: `${core.YTM_API}${endpoint}?prettyPrint=false`, body: core.ytmBody(settings.language === 'en' ? 'en' : 'pt', extra) }));

/** "Montar playlist": as n mais tocadas do artista no YouTube Music (lista "Top songs", na ordem do site; n vazio = todas). */
async function findArtist(query: string, n: string) {
  try {
    const id = core.ytmArtistId(await ytm('search', { query, params: core.YTM_ARTISTS }));
    if (!id) return { error: 'artist_not_found' };
    const { artist, list } = core.ytmTopSongs(await ytm('browse', { browseId: id }));
    if (!list) return { error: 'artist_no_top', artist };
    const url = `https://www.youtube.com/playlist?list=${list}`;
    const tracks = (await ytdlpLines(['--flat-playlist', '--no-warnings', ...(n ? ['--playlist-items', `1:${n}`] : []),
      '--print', '%(id)s\t%(title)s\t%(channel,uploader|)s', url], false, 60000, false))
      .map((line) => line.split('\t')).filter(([id, title]) => id && title)
      .map(([id, title, channel = '']) => ({ id, title, artist: core.artistFromUploader(channel) }));
    if (!tracks.length) return { error: 'artist_error' };
    return { artist, url, tracks };
  } catch (e) {
    log(`[erro] busca do artista "${query}": ${e}`);
    return { error: 'artist_error' };
  }
}

/** Busca de músicas no YouTube Music (só faixas de áudio), para adicionar à playlist montada. */
async function searchSongs(query: string) {
  try {
    return core.ytmSongs(await ytm('search', { query, params: core.YTM_SONGS }));
  } catch (e) {
    log(`[erro] busca de música "${query}": ${e}`);
    return null;
  }
}

/** Itens adicionados sem nome (a busca da tela não tinha terminado): busca um por vez, em segundo plano. */
let naming = Promise.resolve();
function nameLater(job: core.Job): void {
  naming = naming.then(async () => {
    if (job.name || job.status !== 'queued') return;
    const info = await probe(job.url);
    job.name ||= info.playlist || info.title;
    send('job', job);
  });
}

// ---- atualização e configurações de fábrica ------------------------------------

async function checkUpdate() {
  try {
    return core.pickUpdate(JSON.parse(await invoke('fetch_text', { url: core.RELEASES_API, body: null })), INIT.version);
  } catch (e) {
    log(`[erro] Verificação de atualização: ${e}`);
    return { error: true };
  }
}

/** Baixa o .exe da release, confere o SHA-256 que o GitHub informa, troca o .exe e reabre o app.
 *  Qualquer falha antes da troca deixa o app como está. */
async function installUpdate(u: { latest: string; url: string; sha256: string }) {
  const file = path.join(TEMP, 'update.exe');
  try {
    await invoke('mkdir', { path: TEMP });
    log(`Baixando a atualização v${u.latest}: ${u.url}`);
    await download(u.url, file, (pct) => send('update_pct', pct));
    if (u.sha256) {
      // certutil vem no Windows: sem dependência nova para calcular o hash
      let hash = '';
      await runLines(path.join(path.dirname(INIT.tar), 'certutil.exe'), ['-hashfile', file, 'SHA256'], (line) => {
        if (/^[0-9a-f ]{64,}$/i.test(line.trim())) hash = line.replace(/\s/g, '').toLowerCase();
      }).done;
      if (hash !== u.sha256) throw new Error(`SHA-256 diferente do informado pelo GitHub (${hash || 'não calculado'})`);
    }
    const exe = await invoke('replace_exe', { update: file });
    log(`Atualizado para v${u.latest}; reabrindo.`);
    await invoke('relaunch', { path: exe });
    return {};
  } catch (e) {
    await invoke('remove', { path: file });
    log(`[erro] Atualização: ${e}`);
    return { error: String(e) };
  }
}

/** Apaga data\settings.json e reabre: tudo volta ao padrão (músicas, vídeos e data\bin ficam). */
async function factoryReset() {
  await invoke('remove', { path: path.join(INIT.dir, 'settings.json') });
  await invoke('relaunch', { path: null });
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
  findArtist,
  searchSongs,
  checkUpdate,
  installUpdate,
  factoryReset,
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
        name: urls.length === 1 ? opts.name ?? '' : '', // o nome da tela só vale quando há um link
      });
    }
    send('jobs', jobs);
    for (const job of jobs.slice(-urls.length)) nameLater(job);
    if (start) void runQueue();
  },
  queueStart: () => (resumeQueue ? resumeQueue() : void runQueue()),
  /** ▶ de um item: parado = baixa só ele; fila rodando = vira o próximo. Erro/cancelado tenta de novo. */
  startJob: (id: string) => {
    const job = jobs.find((j) => j.id === id);
    if (!job || job.status === 'downloading' || job.status === 'done') return '';
    Object.assign(job, { status: 'queued', progress: 0, errorMsg: '' });
    if (!running) {
      send('job', job);
      void runQueue(job);
      return 'started';
    }
    jobs = jobs.filter((j) => j !== job);
    const at = jobs.findIndex((j) => j.status === 'queued');
    jobs.splice(at < 0 ? jobs.length : at, 0, job);
    send('jobs', jobs);
    return 'next';
  },
  resumeQueue: () => resumeQueue?.(),
  /** "Ignorar esta música": sem substituta, de propósito (de novo = desfaz). */
  ignoreFailed: (jobId: string, trackId: string) => {
    const job = jobs.find((j) => j.id === jobId);
    const f = job?.failed?.find((x) => x.id === trackId);
    if (!job || !f || f.state === 'done' || f.state === 'downloading') return;
    f.state = f.state === 'ignored' ? undefined : 'ignored';
    send('job', job);
  },
  /** Pausa por erro: tenta o mesmo item de novo, ou cancela o resto da fila. */
  retryPaused: () => {
    if (pausedOn) Object.assign(pausedOn, { status: 'queued', progress: 0, errorMsg: '' });
    send('jobs', jobs);
    resumeQueue?.();
  },
  stopQueue: () => {
    for (const j of jobs) if (j.status === 'queued') j.status = 'canceled';
    send('jobs', jobs);
    resumeQueue?.();
  },
  quit: () => invoke('quit'),
  answerClose: (ok: boolean) => answerClose?.(ok),
  replaceFailed: async (jobId: string, links: Record<string, string>) => {
    await replaceFailed(jobId, links);
    resumeQueue?.();
  },
  queueCancel: cancelCurrent,
  clearFinished: () => {
    jobs = jobs.filter((j) => j.status === 'queued' || j.status === 'downloading');
    send('jobs', jobs);
  },
  removeJob: (id: string) => {
    const job = jobs.find((j) => j.id === id);
    if (!job) return;
    if (job.status === 'downloading') cancelCurrent();
    jobs = jobs.filter((j) => j !== job);
    send('jobs', jobs);
    if (pausedOn === job) resumeQueue?.(); // a pausa era por causa dele
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
  init: { settings, jobs, version: INIT.version },
  call: async (name: string, ...args: unknown[]): Promise<any> => handlers[name](...args),
  on: (cb: (kind: string, data: any) => void): void => {
    listener = cb;
  },
};
