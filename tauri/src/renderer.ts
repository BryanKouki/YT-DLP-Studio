/** Interface: abas, diálogos e i18n. Só conversa com o resto do app por `api` (backend.ts). */
import { api } from './backend.js';
import { isYouTube, linksFrom, searchUrls } from './core.js';
import { HELP, STRINGS } from './i18n.js';

const cfg: Record<string, any> = structuredClone(api.init.settings);
let jobList: any[] = structuredClone(api.init.jobs);
let lang: string = cfg.language === 'en' ? 'en' : 'pt';

const $ = <T extends HTMLElement = HTMLElement>(sel: string, root: ParentNode = document) =>
  root.querySelector(sel) as T;
const $$ = <T extends HTMLElement = HTMLElement>(sel: string, root: ParentNode = document) =>
  [...root.querySelectorAll<T>(sel)];

function t(key: string, vars: Record<string, string | number> = {}): string {
  const text = STRINGS[lang][key] ?? key;
  return text.replace(/\{(\w+)\}/g, (whole, name) => (name in vars ? String(vars[name]) : whole));
}

function saveSettings(patch: Record<string, unknown>): void {
  Object.assign(cfg, patch);
  void api.call('saveSettings', patch);
}

/** Todo texto fixo vem de data-i18n / data-i18n-ph / data-i18n-title, então trocar de idioma é só isto. */
function retranslate(): void {
  for (const el of $$('[data-i18n]')) el.textContent = t(el.dataset.i18n!);
  for (const el of $$<HTMLTextAreaElement>('[data-i18n-ph]')) el.placeholder = t(el.dataset.i18nPh!);
  for (const el of $$('[data-i18n-title]')) el.title = t(el.dataset.i18nTitle!);
  for (const el of $$('[data-i18n-label]')) el.setAttribute('label', t(el.dataset.i18nLabel!));
  document.documentElement.lang = lang;
  $('#btn-lang').textContent = lang.toUpperCase();
  renderDeps();
  renderJobs();
}

function applyTheme(): void {
  document.documentElement.dataset.theme = cfg.theme;
  $('#btn-theme use').setAttribute('href', cfg.theme === 'light' ? '#i-sun' : '#i-moon');
}

function showTab(tab: string): void {
  for (const btn of $$('nav button')) btn.classList.toggle('on', btn.dataset.tab === tab);
  for (const section of $$('.tab')) section.classList.toggle('on', section.id === `tab-${tab}`);
}

const setBar = (bar: HTMLElement, pct: number) => bar.style.setProperty('--p', `${Math.max(0, Math.min(100, pct))}%`);

const ICONS = { ok: 'i-check', warn: 'i-warn', err: 'i-x' };

/** Aviso flutuante no canto (some sozinho). action vira um botão dentro do aviso. */
function toast(text: string, kind: keyof typeof ICONS = 'ok', action?: { label: string; run: () => void }): void {
  const box = document.createElement('div');
  box.className = `toast ${kind}`;
  box.innerHTML = `<svg><use href="#${ICONS[kind]}"/></svg><span></span>`;
  $('span', box).textContent = text; // pode vir do yt-dlp: só textContent
  if (action) {
    const btn = document.createElement('button');
    btn.className = 'small';
    btn.textContent = action.label;
    btn.onclick = () => {
      action.run();
      close();
    };
    box.append(btn);
  }
  const close = () => {
    box.classList.add('out');
    box.addEventListener('animationend', () => box.remove(), { once: true });
  };
  $('#toasts').append(box);
  setTimeout(close, action ? 9000 : 3500);
}

const hms = (total: number) =>
  [total / 3600, (total / 60) % 60, total % 60].map((v) => String(Math.floor(v)).padStart(2, '0')).join(':');
/** "HH:MM:SS", "MM:SS" ou "SS" -> segundos (0 se não for número). */
const secs = (text: string) => {
  const parts = text.trim().split(':').map(Number);
  return parts.some(isNaN) ? 0 : parts.reduce((acc, part) => acc * 60 + part, 0);
};

// ---- abas Áudio e Vídeo --------------------------------------------------------

interface DownloadTab {
  setStatus(text: string): void;
  setProgress(pct: number): void;
  showFolder(): void;
}

const cloneTemplate = (id: string) => $<HTMLTemplateElement>(id).content.cloneNode(true);

function setupDownloadTab(mode: 'audio' | 'video'): DownloadTab {
  const root = $(`#tab-${mode}`);
  root.append(cloneTemplate('#tpl-download'));
  $('.opts', root).append(cloneTemplate(`#tpl-${mode}-opts`));

  const links = $<HTMLTextAreaElement>('.links', root);
  const [rStart, rEnd, tStart, tEnd] =
    ['.r-start', '.r-end', '.t-start', '.t-end'].map((sel) => $<HTMLInputElement>(sel, root));
  const fill = $('.fill', root);
  const detect = $('.detect', root);
  const statusLabel = $('.status', root);
  const folderKey = `${mode}_folder`;
  const textField = (key: string) => root.querySelector<HTMLInputElement>(`input[data-opt="${key}"]`);
  let trimActive = false;
  let probeSeq = 0;
  let probeTimer = 0;
  // o que a busca automática encontrou para o link atual
  let found = { playlist: '', title: '', autoTitle: '', autoArtist: '' };

  const urls = () => linksFrom(links.value);
  const showFolder = () => {
    $('.folder', root).textContent = cfg[folderKey];
  };

  // -- recorte de trecho --
  const paint = () => {
    const max = +rEnd.max;
    fill.style.setProperty('--from', `${(+rStart.value / max) * 100}%`);
    fill.style.setProperty('--to', `${(+rEnd.value / max) * 100}%`);
    // com as duas bolinhas juntas no fim, a de início fica por cima (senão ninguém mais se move)
    rStart.style.zIndex = +rStart.value > max / 2 ? '1' : '';
    trimActive = +rStart.value > 0 || +rEnd.value < max;
    $('.trim-sum', root).textContent = trimActive ? `${hms(+rStart.value)} – ${hms(+rEnd.value)}` : '';
  };
  const setRange = (start: number, end: number, max = +rEnd.max) => {
    rStart.max = rEnd.max = String(max);
    rStart.value = String(start);
    rEnd.value = String(end);
    paint();
  };
  const resetTrim = (max = 7200) => {
    setRange(0, max, max);
    tStart.value = hms(0);
    tEnd.value = max === 7200 ? hms(0) : hms(max);
  };
  rStart.oninput = rEnd.oninput = (event) => {
    const [moved, other] = event.target === rStart ? [rStart, rEnd] : [rEnd, rStart];
    if (+rStart.value > +rEnd.value) moved.value = other.value;
    tStart.value = hms(+rStart.value);
    tEnd.value = hms(+rEnd.value);
    paint();
  };
  tStart.onchange = tEnd.onchange = () => {
    const max = +rEnd.max;
    const start = Math.min(secs(tStart.value), max);
    setRange(start, Math.min(Math.max(secs(tEnd.value) || max, start), max));
  };

  // -- o que foi colado: playlist (Título/Artista não se aplicam), música/vídeo, vários links --
  const showDetect = (state: 'busy' | 'ok' | 'fail' | '', kind = '', name = '') => {
    detect.hidden = !state;
    detect.dataset.state = state;
    $('.detect-kind', detect).textContent = kind;
    $('.detect-name', detect).textContent = name;
  };
  const setPlaylistMode = (isPlaylist: boolean) => {
    for (const el of $$('.single-only', root)) el.hidden = isPlaylist;
  };
  // campo preenchido pela busca anterior é limpo; o que o usuário digitou fica
  const clearAuto = () => {
    for (const [key, auto] of [['title', found.autoTitle], ['artist', found.autoArtist]] as const) {
      const input = textField(key);
      if (input && auto && input.value === auto) input.value = '';
    }
    found = { playlist: '', title: '', autoTitle: '', autoArtist: '' };
  };

  // busca automática em segundo plano, com atraso após parar de digitar; nunca trava o Download
  links.oninput = () => {
    clearTimeout(probeTimer);
    probeSeq++; // descarta qualquer resposta de um link anterior
    clearAuto();
    setPlaylistMode(false);
    const list = urls();
    if (!list.length) return showDetect('');
    if (list.length > 1) return showDetect('ok', t('detect_multi', { n: list.length }));
    showDetect('busy', t('detect_checking'));
    probeTimer = window.setTimeout(async () => {
      const seq = probeSeq;
      const info = await api.call('probe', list[0]);
      if (seq !== probeSeq) return; // o link já foi trocado
      if (info.playlist) {
        found.playlist = info.playlist;
        setPlaylistMode(true);
        showDetect('ok', t('detect_playlist'), info.playlist);
        return;
      }
      if (!info.title) return showDetect('fail', t('detect_unknown'));
      found.title = info.title;
      const label = [info.title, info.artist].filter(Boolean).join(' — ');
      showDetect('ok', t(`detect_single_${mode}`), `${label}${info.duration ? ` (${hms(info.duration)})` : ''}`);
      if (info.duration > 0) resetTrim(info.duration);
      for (const [key, value] of [['title', info.title], ['artist', info.artist]] as const) {
        const input = textField(key);
        if (input && value && !input.value.trim()) {
          input.value = value;
          found[key === 'title' ? 'autoTitle' : 'autoArtist'] = value;
        }
      }
    }, 700);
  };

  // -- seleções lembradas entre sessões (só <select> e caixas de seleção) --
  for (const el of $$<HTMLInputElement | HTMLSelectElement>('select[data-opt], input[type=checkbox][data-opt]', root)) {
    const key = `${mode}.${el.dataset.opt}`;
    const saved = cfg.ui?.[key];
    if (el instanceof HTMLInputElement) el.checked = Boolean(saved);
    else if ([...el.options].some((o) => o.value === saved)) el.value = saved;
    el.onchange = () =>
      saveSettings({ ui: { ...cfg.ui, [key]: el instanceof HTMLInputElement ? el.checked : el.value } });
  }

  const submit = async (start: boolean) => {
    const list = urls();
    if (!list.length) {
      links.focus();
      return toast(t('no_link_error'), 'warn');
    }
    const opts: Record<string, unknown> = {
      trim_start: trimActive ? tStart.value.trim() : '',
      trim_end: trimActive ? tEnd.value.trim() : '',
    };
    for (const el of $$<HTMLInputElement>('[data-opt]', root)) {
      opts[el.dataset.opt!] = el.type === 'checkbox' ? el.checked : el.value.trim();
    }
    if (found.playlist) opts.title = opts.artist = ''; // Título/Artista valem só para uma música
    const name = found.playlist || String(opts.title || '') || found.title;
    opts.name = name;
    await api.call('addJobs', { mode, urls: list, opts }, start);
    const what = list.length > 1 ? t('detect_multi', { n: list.length }) : name || list[0];
    toast(t(start ? 'toast_started' : 'toast_queued', { name: what }), 'ok',
      { label: t('tab_queue'), run: () => showTab('queue') });
    // pronto para colar o próximo link, sem herdar nome/artista do anterior
    links.value = '';
    links.dispatchEvent(new Event('input'));
    for (const key of ['title', 'artist']) {
      const input = textField(key);
      if (input) input.value = '';
    }
    resetTrim();
    links.focus();
  };
  $('.download', root).onclick = () => submit(true);
  $('.queue-add', root).onclick = () => submit(false);
  links.onkeydown = (event) => {
    if (event.key === 'Enter' && event.ctrlKey) void submit(true);
  };
  $('.cancel-current', root).onclick = () => api.call('queueCancel');
  $('.open-folder', root).onclick = () => api.call('openFolder', cfg[folderKey], true);
  $('.change-folder', root).onclick = async () => {
    const chosen = await api.call('pickFolder', cfg[folderKey]);
    if (!chosen) return;
    saveSettings({ [folderKey]: chosen });
    showFolder();
  };
  $('.check-pl', root).onclick = () => {
    const list = urls();
    if (!list.length) return toast(t('no_link_error'), 'warn');
    void api.call('checkPlaylist', list[0]);
    toast(t('toast_check_started'), 'ok', { label: t('view_log'), run: () => showTab('queue') });
  };

  statusLabel.textContent = t('ready');
  showFolder();
  paint();
  return {
    showFolder,
    setStatus: (text) => {
      statusLabel.textContent = text;
    },
    setProgress: (pct) => setBar($('.bar', root), pct),
  };
}

// ---- aba Converter -------------------------------------------------------------

function setupConvertTab(): void {
  const file = $<HTMLInputElement>('#c-file');
  const value = (sel: string) => $<HTMLSelectElement>(sel).value;
  $('#c-status').textContent = t('ready');
  $('#c-pick').onclick = async () => {
    const chosen = await api.call('pickFile');
    if (chosen) file.value = chosen;
  };
  $('#c-open').onclick = () => {
    const src = file.value.trim();
    if (src) void api.call('openFolder', src.replace(/[\\/][^\\/]*$/, ''));
  };
  $('#c-cancel').onclick = () => api.call('convertCancel');
  $('#c-start').onclick = async () => {
    const raw = $<HTMLInputElement>('#c-size').value.trim().replace(',', '.');
    const size = raw ? Number(raw) : 0;
    if (!(size >= 0)) return toast(t('conv_bad_size'), 'warn');
    const result = await api.call('convert', {
      src: file.value.trim(), fmt: value('#c-fmt'), quality: +value('#c-quality'), res: value('#c-res'),
      target: Math.floor(size * 1024 ** (value('#c-unit') === 'GB' ? 3 : 2)),
    });
    if (result.error) return toast(t(result.error), 'warn');
    if (result.busy) return;
    setBar($('#c-bar'), 0);
    $('#c-status').textContent = t('conv_running');
  };
}

function onConvert(ev: { progress?: number; done?: boolean; ok?: boolean; canceled?: boolean; info?: string }): void {
  if (!ev.done) return setBar($('#c-bar'), (ev.progress ?? 0) * 100);
  setBar($('#c-bar'), ev.ok ? 100 : 0);
  if (ev.ok) {
    const name = ev.info!.split(/[\\/]/).pop()!;
    $('#c-status').textContent = t('conv_done', { name });
    toast(t('conv_done', { name }));
  } else if (ev.canceled) {
    $('#c-status').textContent = t('status_canceled');
  } else {
    $('#c-status').textContent = t('conv_error');
    toast(t('conv_error'), 'err');
    appendLog('[erro ffmpeg] ' + ev.info);
  }
}

// ---- aba Fila e Log ------------------------------------------------------------

const depState: Record<string, { state: string; extra?: Record<string, any> }> = {
  ytdlp: { state: 'missing' },
  ffmpeg: { state: 'missing' },
  deno: { state: 'missing' },
};

function renderDeps(): void {
  for (const [component, { state, extra = {} }] of Object.entries(depState)) {
    let text = t(`dep_${state}`, { size: extra.size ?? '' });
    if (state === 'downloading' && extra.pct != null) text += ` ${extra.pct}%`;
    $(`#dep-${component}`).textContent = `${t(`dep_${component}`)} ${text}`;
    $(`#dot-${component}`).dataset.state = state;
  }
}

/** "Título - Artista (X de Y)" da faixa sendo baixada agora. */
function nowLabel(job: any): string {
  let label = job.nowTitle || job.title || job.url;
  if (job.nowArtist) label += ` - ${job.nowArtist}`;
  if (job.idx && job.count) label += ` (${t('position_of_total', { idx: job.idx, total: job.count })})`;
  return label;
}

/** Faixas com erro que ainda não ganharam substituta. */
const remaining = (job: any): number => job.failed?.filter((f: any) => f.state !== 'done' && f.state !== 'ignored').length ?? 0;
const STATUS_ICON: Record<string, string> = { queued: 'i-queue', done: 'i-check', error: 'i-x', canceled: 'i-x' };

function renderJobs(): void {
  const list = $('#q-list');
  list.replaceChildren();
  if (!jobList.length) {
    list.innerHTML = '<div class="empty muted"><svg><use href="#i-queue"/></svg><span></span></div>';
    $('.empty span', list).textContent = t('queue_empty');
  }
  for (const job of jobList) {
    const row = document.createElement('div');
    row.className = 'job';
    row.id = `job-${job.id}`;
    row.innerHTML = '<span class="job-ico"><svg><use/></svg></span><div class="info grow"><span class="tag"></span>' +
      '<div class="name"></div><div class="state muted small"></div><span class="bar"><i></i></span></div>' +
      '<button class="fails small" hidden></button><button class="cancel small"></button>' +
      '<button class="icon play"><svg><use href="#i-play"/></svg></button>' +
      '<button class="icon remove"><svg><use href="#i-x"/></svg></button>';
    $('.cancel', row).onclick = () => api.call('queueCancel');
    $('.fails', row).onclick = () => openFailed(job.id);
    $('.remove', row).onclick = () => api.call('removeJob', job.id);
    $('.play', row).onclick = async () => {
      if ((await api.call('startJob', job.id)) === 'next') toast(t('toast_next', { name: job.name || job.title || job.url }));
    };
    list.append(row);
    paintJob(job);
  }
  paintSummary();
}

const PHASES = new Set(['MetadataParser', 'ThumbnailsConvertor', 'ExtractAudio', 'Merger', 'Metadata', 'EmbedThumbnail', 'EmbedSubtitle', 'MoveFiles']);

/** O que está acontecendo com a faixa atual: baixando, convertendo, capa, metadados... */
function phaseLabel(job: any): string {
  if (!job.phase || job.phase === 'download') return t('phase_download');
  return t(PHASES.has(job.phase) ? `pp_${job.phase}` : 'pp_other');
}

/** Linha da faixa atual: "Etapa · Título - Artista (X de Y)", ou ✓ quando ela já está na pasta. */
function paintTrack(el: HTMLElement, job: any): void {
  if (job.phase !== 'done') {
    el.textContent = `${phaseLabel(job)} · ${nowLabel(job)}`;
    return;
  }
  if (!el.querySelector('.done-check')) el.innerHTML = '<svg class="done-check"><use href="#i-check"/></svg><span></span>';
  $('span', el).textContent = nowLabel(job); // vem do yt-dlp: só textContent
}

function paintJob(job: any): void {
  const row = document.getElementById(`job-${job.id}`);
  if (!row) return;
  const position = t('position_of_total', { idx: jobList.indexOf(job) + 1, total: jobList.length });
  const left = remaining(job);
  let state = t(`status_${job.status}`);
  if (job.status === 'downloading' && job.nowTitle) state = nowLabel(job);
  if (job.status === 'error' && job.errorMsg) state += ` — ${job.errorMsg}`;
  if (job.status === 'done' && left) state = t('done_with_failures', { n: left });
  if (row.dataset.status !== job.status) {
    row.dataset.status = job.status; // troca o ícone (e roda a animação dele)
    $('.job-ico use', row).setAttribute('href', `#${STATUS_ICON[job.status] ?? 'i-queue'}`);
  }
  const fails = $<HTMLButtonElement>('.fails', row);
  fails.hidden = !left;
  fails.textContent = t('failed_button', { n: left });
  $('.tag', row).textContent = `${t(`tab_${job.mode}`)} · ${position}`;
  $('.name', row).textContent = job.name || [job.title, job.artist].filter(Boolean).join(' - ') || job.url;
  $('.name', row).title = job.url;
  if (job.status === 'downloading' && job.nowTitle) paintTrack($('.state', row), job);
  else $('.state', row).textContent = state;
  $('.cancel', row).textContent = t('cancel_current');
  $('.remove', row).title = t('remove_item');
  $('.play', row).title = t('start_item');
  setBar($('.bar', row), job.progress);
}

/** Contador na barra lateral e o download em andamento visível de qualquer aba. */
function paintSummary(): void {
  const pending = jobList.filter((j) => j.status === 'queued' || j.status === 'downloading').length;
  const failing = jobList.filter(remaining).length;
  // botão do topo da fila: abre as faixas com erro (conta só as que ainda não ganharam substituta)
  const failedTracks = jobList.reduce((sum, j) => sum + remaining(j), 0);
  const failedBtn = $<HTMLButtonElement>('#q-failed');
  failedBtn.disabled = !failedTracks;
  failedBtn.textContent = t('failed_button', { n: failedTracks });
  const badge = $('#q-badge');
  badge.hidden = !pending && !failing;
  badge.textContent = String(pending || failing);
  badge.classList.toggle('warn', !pending && failing > 0);
  const current = jobList.find((j) => j.status === 'downloading');
  const now = $<HTMLButtonElement>('#now');
  now.hidden = !current;
  if (current) {
    $('.now-label', now).textContent = current.nowTitle ? nowLabel(current) : current.name || current.url;
    setBar($('.bar', now), current.progress);
  }
}

function onJob(job: any): void {
  const i = jobList.findIndex((j) => j.id === job.id);
  if (i < 0) return;
  const before = jobList[i].status;
  jobList[i] = job;
  paintJob(job);
  paintSummary();
  if (failedJobId === job.id) paintFailedStates(job);
  const tab = downloadTabs[job.mode];
  const name = job.name || job.title || job.url;
  if (job.status === 'downloading') {
    tab.setStatus(!job.nowTitle ? `${t('status_downloading')} ${name}`
      : job.phase === 'done' ? `✓ ${nowLabel(job)}` : `${phaseLabel(job)} · ${nowLabel(job)}`);
  }
  else tab.setStatus(`${t(`status_${job.status}`)} — ${name}`);
  tab.setProgress(job.status === 'downloading' ? job.progress : job.status === 'done' ? 100 : 0);
  if (before !== job.status && job.status === 'done') toast(`${t('status_done')}: ${name}`);
  if (before !== job.status && job.status === 'error') toast(`${t('status_error')}: ${name}`, 'err');
}

function appendLog(line: string): void {
  const log = $('#q-log');
  const entry = document.createElement('span');
  entry.textContent = `[${new Date().toTimeString().slice(0, 8)}] ${line}\n`;
  if (/ERROR|\[erro/.test(line)) entry.className = 'err';
  log.append(entry);
  log.scrollTop = log.scrollHeight;
}

// ---- faixas com erro das playlists ---------------------------------------------

let failedJobId = '';
let reviewAll = false; // aberto pelo botão do topo: depois de cada playlist, vai para a próxima
const failedJobs = () => jobList.filter((j) => j.failed?.length);

async function copyText(text: string, el: HTMLElement): Promise<void> {
  await api.call('copy', text);
  el.classList.remove('copied');
  void el.offsetWidth; // reinicia a animação se clicar de novo
  el.classList.add('copied');
  toast(text.length > 90 ? t('copied') : `${t('copied')} ${text}`);
}

/** Lista as faixas que falharam numa playlist: nome (copia "Música - Artista"), link copiável
 *  (inteiro ou só o ID) e caixa para o link substituto. Setas passam para as outras playlists. */
function openFailed(jobId: string, fromTop = false): void {
  const job = jobList.find((j) => j.id === jobId);
  if (!job?.failed?.length) return;
  failedJobId = jobId;
  const dialogOpen = $<HTMLDialogElement>('#dlg-failed').open;
  if (!dialogOpen) reviewAll = fromTop;
  const all = failedJobs();
  const at = all.indexOf(job);
  $('#failed-nav').textContent = all.length > 1 ? t('failed_nav', { i: at + 1, n: all.length }) : '';
  $<HTMLButtonElement>('#failed-prev').disabled = at <= 0;
  $<HTMLButtonElement>('#failed-next').disabled = at >= all.length - 1;
  $('#failed-pl').textContent = job.name || job.url;
  const prefix = /music\.youtube\.com/.test(job.url) ? 'https://music.youtube.com/watch?v=' : 'https://www.youtube.com/watch?v=';
  const list = $('#failed-list');
  list.replaceChildren();
  for (const f of job.failed) {
    // títulos e motivos vêm do yt-dlp: só textContent, nunca innerHTML
    const row = document.createElement('div');
    row.className = 'fail';
    row.dataset.id = f.id;
    row.innerHTML = '<div class="row"><b class="pos"></b><button type="button" class="copy-name grow"></button>' +
      '<span class="state small"></span><button type="button" class="ghost small ignore"></button></div><div class="reason muted small"></div>' +
      '<div class="row search-links"><button type="button" class="ghost small"></button>' +
      '<button type="button" class="ghost small"></button></div><div class="row">' +
      '<span class="copy-link"><button type="button"></button><button type="button" class="id"></button></span>' +
      '<input class="grow"></div>';
    $('.pos', row).textContent = `${f.pos || '?'}.`;
    // vídeo apagado/privado vem como "[Deleted video]": o YouTube não informa o nome
    const known = f.title && !/^\[.*\]$/.test(f.title);
    const song = [f.title, f.artist].filter(Boolean).join(' - ');
    const name = $<HTMLButtonElement>('.copy-name', row);
    name.textContent = known ? song : f.title || f.id;
    name.disabled = !known;
    name.title = known ? t('failed_copy_name') : t('failed_no_name');
    name.onclick = () => copyText(song, name);
    $('.reason', row).textContent = $('.reason', row).title = f.reason;
    $('.ignore', row).onclick = () => api.call('ignoreFailed', job.id, f.id);
    // links de busca prontos, só para playlists do YouTube e faixas com nome conhecido
    $('.search-links', row).hidden = !(known && isYouTube(job.url));
    const search = searchUrls(song);
    const [onMusic, onYouTube] = $$<HTMLButtonElement>('.search-links button', row);
    onMusic.textContent = t('copy_search_music');
    onMusic.title = search.music;
    onMusic.onclick = () => copyText(search.music, onMusic);
    onYouTube.textContent = t('copy_search_youtube');
    onYouTube.title = search.youtube;
    onYouTube.onclick = () => copyText(search.youtube, onYouTube);
    const [whole, id] = $$<HTMLButtonElement>('.copy-link button', row);
    whole.textContent = prefix;
    whole.title = prefix + f.id;
    whole.onclick = () => copyText(prefix + f.id, whole);
    id.textContent = id.title = f.id;
    id.onclick = () => copyText(f.id, id);
    $<HTMLInputElement>('input', row).placeholder = t('failed_paste');
    list.append(row);
  }
  paintFailedStates(job);
  const dialog = $<HTMLDialogElement>('#dlg-failed');
  if (!dialog.open) dialog.showModal();
}

function paintFailedStates(job: any): void {
  for (const f of job.failed ?? []) {
    const row = document.querySelector<HTMLElement>(`#failed-list .fail[data-id="${CSS.escape(f.id)}"]`);
    if (!row) continue;
    row.dataset.state = f.state ?? '';
    $('.state', row).textContent = f.state ? t(`status_${f.state}`) : '';
    const ignore = $<HTMLButtonElement>('.ignore', row);
    ignore.textContent = t(f.state === 'ignored' ? 'failed_unignore' : 'failed_ignore');
    ignore.hidden = f.state === 'done' || f.state === 'downloading';
    $<HTMLInputElement>('input', row).disabled = f.state === 'ignored';
  }
}

function setupFailedDialog(): void {
  const dialog = $<HTMLDialogElement>('#dlg-failed');
  const step = (delta: number) => {
    const all = failedJobs();
    const next = all[all.findIndex((j) => j.id === failedJobId) + delta];
    if (next) openFailed(next.id);
    else dialog.close();
  };
  $('#failed-prev').onclick = () => step(-1);
  $('#failed-next').onclick = () => step(1);
  $('#failed-go').onclick = () => {
    const links: Record<string, string> = {};
    for (const row of $$('.fail', dialog)) links[row.dataset.id!] = $<HTMLInputElement>('input', row).value.trim();
    void api.call('replaceFailed', failedJobId, links);
    if (Object.values(links).some(Boolean)) toast(t('toast_replacing'));
    if (reviewAll) step(1);
    else dialog.close(); // aberto pela linha da playlist: só fecha
  };
  $('#failed-skip').onclick = () => {
    void api.call('resumeQueue');
    if (reviewAll) step(1);
    else dialog.close();
  };
}

/** Pergunta Sim/Não na janela do app; Esc ou fechar conta como Não. */
function ask(text: string): Promise<boolean> {
  const dialog = $<HTMLDialogElement>('#dlg-confirm');
  $('p', dialog).textContent = text;
  dialog.returnValue = '';
  dialog.showModal();
  return new Promise((resolve) => dialog.addEventListener('close', () => resolve(dialog.returnValue === 'yes'), { once: true }));
}

function setupErrorDialog(): void {
  $('#err-continue').onclick = () => api.call('resumeQueue');
  $('#err-retry').onclick = () => api.call('retryPaused');
  $('#err-stop').onclick = () => api.call('stopQueue');
}

function setupQueueTab(): void {
  $('#q-deps').onclick = () => api.call('checkDeps', true);
  $('#q-update').onclick = () => api.call('updateYtdlp');
  $('#q-bin').onclick = () => api.call('openBin');
  $('#q-start').onclick = () => api.call('queueStart');
  $('#q-cancel').onclick = () => api.call('queueCancel');
  $('#q-failed').onclick = () => openFailed((jobList.find(remaining) ?? failedJobs()[0])?.id, true);
  $('#q-clear-done').onclick = () => api.call('clearFinished');
  $('#q-clear-all').onclick = () => api.call('clearAll');
  $('#q-open').onclick = () => api.call('openFolder', cfg.audio_folder, true);
  $('#q-copy').onclick = () => copyText($('#q-log').textContent ?? '', $('#q-log')).then(() => undefined);
  $('#now').onclick = () => showTab('queue');
}

// ---- Configurações e Ajuda -----------------------------------------------------

// onde o texto do rótulo não tem a mesma chave da configuração
const LABEL_KEY: Record<string, string> = { output_template: 'filename_template', no_check_certificate: 'no_check_cert' };
// [título da seção, campos de largura total, caixas de seleção, campos em 2 colunas]
const SETTINGS_FORM: [string, string[], string[], string[]][] = [
  ['network', ['speed_limit', 'proxy', 'playlist_items', 'output_template'], [], []],
  ['filters', [], [], ['date_after', 'date_before', 'min_filesize', 'max_filesize', 'min_duration', 'max_duration']],
  ['download_behavior', [],
    ['restrict_filenames', 'no_playlist', 'skip_downloaded', 'geo_bypass', 'no_check_certificate', 'force_ipv4',
      'write_comments', 'live_from_start', 'windows_safe_names', 'no_overwrites'],
    ['concurrent_fragments', 'retries', 'fragment_retries', 'trim_filenames', 'age_limit', 'sleep_interval']],
  ['extra_files', [],
    ['embed_metadata_thumb', 'embed_chapters', 'split_chapters', 'write_description', 'write_info_json',
      'keep_video'],
    ['sub_langs', 'sub_format']],
];

function setupDialogs(): void {
  const label = (key: string) => `<span data-i18n="${LABEL_KEY[key] ?? key}"></span>`;
  const entry = (key: string) => `<label class="field">${label(key)}<input data-set="${key}"></label>`;
  const check = (key: string) => `<label class="chk"><input type="checkbox" data-set="${key}">${label(key)}</label>`;
  $('#set-form').insertAdjacentHTML('beforeend', SETTINGS_FORM.map(([title, wide, checks, grid]) =>
    `<h3 data-i18n="${title}"></h3>${wide.map(entry).join('')}${checks.map(check).join('')}` +
    `<div class="grid">${grid.map(entry).join('')}</div>`).join(''));

  const dialog = $<HTMLDialogElement>('#dlg-settings');
  const fields = $$<HTMLInputElement>('[data-set]', dialog);
  for (const btn of $$('.browse', dialog)) {
    btn.onclick = async () => {
      const input = btn.previousElementSibling as HTMLInputElement;
      const chosen = await api.call('pickFolder', input.value || undefined);
      if (chosen) input.value = chosen;
    };
  }
  // Chrome só depois de duas confirmações; "Não" em qualquer uma volta para o anterior
  const browser = $<HTMLSelectElement>('[data-set="cookies_browser"]', dialog);
  // navegadores Chromium no Windows: o yt-dlp pode não abrir os cookies (DPAPI), mesmo fechados
  const warnChromium = () => {
    $('.cookie-warn', dialog).hidden = !['edge', 'chrome', 'brave', 'chromium', 'opera', 'vivaldi', 'whale'].includes(browser.value);
  };
  let lastBrowser = 'firefox';
  // "só quando bloquear" é uma opção da opção: aparece depois de ligar os cookies
  const useCookies = $<HTMLInputElement>('[data-set="use_cookies"]', dialog);
  const syncCookiesSub = () => {
    $('.cookies-sub', dialog).hidden = !useCookies.checked;
  };
  useCookies.addEventListener('change', syncCookiesSub);
  browser.onchange = async () => {
    if (browser.value === 'chrome' && !((await ask(t('chrome_confirm_1'))) && (await ask(t('chrome_confirm_2'))))) {
      browser.value = lastBrowser;
    }
    lastBrowser = browser.value;
    warnChromium();
  };
  $('#btn-settings').onclick = () => {
    for (const el of fields) {
      if (el.type === 'checkbox') el.checked = Boolean(cfg[el.dataset.set!]);
      else el.value = cfg[el.dataset.set!] ?? '';
    }
    lastBrowser = browser.value;
    warnChromium();
    syncCookiesSub();
    dialog.showModal();
  };
  $('#set-save').onclick = () => {
    const patch: Record<string, unknown> = {};
    for (const el of fields) {
      const key = el.dataset.set!;
      // pasta em branco mantém a anterior
      patch[key] = el.type === 'checkbox' ? el.checked : el.value.trim() || (key.endsWith('_folder') ? cfg[key] : '');
    }
    saveSettings(patch);
    for (const tab of Object.values(downloadTabs)) tab.showFolder();
    dialog.close();
    toast(t('toast_saved'));
  };

  $('#btn-help').onclick = () => {
    // HELP é texto fixo nosso (tem <b>), não entrada do usuário
    $('#help-body').innerHTML = HELP[lang].map(([heading, text]) => `<h3>${heading}</h3><p>${text}</p>`).join('');
    $<HTMLDialogElement>('#dlg-help').showModal();
  };
}

// ---- início --------------------------------------------------------------------

for (const btn of $$('nav button')) btn.onclick = () => showTab(btn.dataset.tab!);
$('#btn-theme').onclick = () => {
  saveSettings({ theme: cfg.theme === 'light' ? 'dark' : 'light' });
  applyTheme();
};
$('#btn-lang').onclick = () => {
  lang = lang === 'pt' ? 'en' : 'pt';
  saveSettings({ language: lang });
  retranslate();
};

const downloadTabs: Record<string, DownloadTab> = { audio: setupDownloadTab('audio'), video: setupDownloadTab('video') };
setupConvertTab();
setupQueueTab();
setupFailedDialog();
setupErrorDialog();
setupDialogs();
applyTheme();
retranslate();
showTab('audio');

api.on((kind, data) => {
  if (kind === 'log') appendLog(data);
  else if (kind === 'job') onJob(data);
  else if (kind === 'jobs') {
    jobList = data;
    renderJobs();
  } else if (kind === 'now') {
    const job = jobList.find((j) => j.id === data.id);
    if (job) appendLog(`${t(data.phase === 'start' ? 'status_downloading' : 'status_done')}: ${nowLabel(job)}`);
  } else if (kind === 'dep') {
    depState[data.component] = data;
    renderDeps();
  } else if (kind === 'paused') {
    downloadTabs[data.mode].setStatus(t('queue_paused', { n: remaining(data) }));
    toast(t('queue_paused', { n: remaining(data) }), 'warn', { label: t('view_failed'), run: () => openFailed(data.id) });
  } else if (kind === 'review') {
    toast(t('queue_review', { n: data }), 'warn', { label: t('view_failed'), run: () => openFailed(failedJobs()[0]?.id, true) });
  } else if (kind === 'close_requested') {
    void ask(t(data.busy ? 'quit_confirm_busy' : 'quit_confirm')).then((ok) => ok && api.call('quit'));
  } else if (kind === 'error_pause') {
    $('#err-name').textContent = data.name || data.title || data.url;
    $('#err-text').textContent = data.errorMsg; // vem do yt-dlp: só textContent
    const dialog = $<HTMLDialogElement>('#dlg-error');
    if (!dialog.open) dialog.showModal();
  } else if (kind === 'confirm_close') {
    void ask(t('close_browser_confirm', { browser: data })).then((ok) => api.call('answerClose', ok));
  } else if (kind === 'playlist_fallback') {
    toast(t('toast_playlist_fallback', { name: data }), 'warn');
  } else if (kind === 'bot_cookies') {
    toast(t('toast_bot_cookies'), 'warn');
  } else if (kind === 'cookies_off') {
    cfg.use_cookies = false;
    toast(t('toast_cookies_off'), 'warn');
  } else if (kind === 'replaced') {
    toast(t('toast_replaced', { pos: data.pos }));
  } else if (kind === 'conv') onConvert(data);
});
void api.call('checkDeps', false, true);
