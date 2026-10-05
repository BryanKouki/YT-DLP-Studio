/** Interface: abas, diálogos e i18n. Só conversa com o resto do app por `api` (backend.ts). */
import { api } from './backend.js';
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
  document.documentElement.lang = lang;
  $('#btn-lang').textContent = lang.toUpperCase();
  renderDeps();
  renderJobs();
}

function applyTheme(): void {
  document.documentElement.dataset.theme = cfg.theme;
  $('#btn-theme').textContent = cfg.theme === 'light' ? '☀' : '🌙';
}

function showTab(tab: string): void {
  for (const btn of $$('nav button')) btn.classList.toggle('on', btn.dataset.tab === tab);
  for (const section of $$('.tab')) section.classList.toggle('on', section.id === `tab-${tab}`);
}

function showMessage(text: string): void {
  $('#dlg-msg p').textContent = text;
  $<HTMLDialogElement>('#dlg-msg').showModal();
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
  const statusLabel = $('.status', root);
  const folderKey = `${mode}_folder`;
  let trimActive = false;
  let probeSeq = 0;
  let probeTimer = 0;

  const urls = () => links.value.split('\n').map((line) => line.trim()).filter(Boolean);
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
  };
  const setRange = (start: number, end: number, max = +rEnd.max) => {
    rStart.max = rEnd.max = String(max);
    rStart.value = String(start);
    rEnd.value = String(end);
    paint();
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

  // -- busca automática de título/artista/duração: em segundo plano, com atraso
  //    após parar de digitar, e sem nunca travar o botão de Download --
  links.oninput = () => {
    clearTimeout(probeTimer);
    probeTimer = window.setTimeout(async () => {
      const list = urls();
      if (list.length !== 1) return; // com vários links, os dados do 1º seriam aplicados nos outros
      const seq = ++probeSeq;
      const info = await api.call('probe', list[0]);
      if (seq !== probeSeq) return; // o link já foi trocado
      if (info.duration > 0) {
        setRange(0, info.duration, info.duration);
        tStart.value = hms(0);
        tEnd.value = hms(info.duration);
      }
      for (const key of ['title', 'artist']) {
        const input = root.querySelector<HTMLInputElement>(`input[data-opt="${key}"]`);
        if (input && info[key] && !input.value.trim()) input.value = info[key];
      }
    }, 900);
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
    if (!list.length) return showMessage(t('no_link_error'));
    const opts: Record<string, unknown> = {
      trim_start: trimActive ? tStart.value.trim() : '',
      trim_end: trimActive ? tEnd.value.trim() : '',
    };
    for (const el of $$<HTMLInputElement>('[data-opt]', root)) {
      opts[el.dataset.opt!] = el.type === 'checkbox' ? el.checked : el.value.trim();
    }
    await api.call('addJobs', { mode, urls: list, opts }, start);
    showTab('queue');
  };
  $('.download', root).onclick = () => submit(true);
  $('.queue-add', root).onclick = () => submit(false);
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
    if (!list.length) return showMessage(t('no_link_error'));
    void api.call('checkPlaylist', list[0]);
    showTab('queue');
  };

  statusLabel.textContent = t('ready');
  showFolder();
  paint();
  return {
    showFolder,
    setStatus: (text) => {
      statusLabel.textContent = text;
    },
    setProgress: (pct) => {
      $<HTMLProgressElement>('progress', root).value = pct;
    },
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
    if (!(size >= 0)) return showMessage(t('conv_bad_size'));
    const result = await api.call('convert', {
      src: file.value.trim(), fmt: value('#c-fmt'), quality: +value('#c-quality'), res: value('#c-res'),
      target: Math.floor(size * 1024 ** (value('#c-unit') === 'GB' ? 3 : 2)),
    });
    if (result.error) return showMessage(t(result.error));
    if (result.busy) return;
    $<HTMLProgressElement>('#c-bar').value = 0;
    $('#c-status').textContent = t('conv_running');
  };
}

function onConvert(ev: { progress?: number; done?: boolean; ok?: boolean; canceled?: boolean; info?: string }): void {
  const bar = $<HTMLProgressElement>('#c-bar');
  if (!ev.done) {
    bar.value = Math.min(1, ev.progress ?? 0);
    return;
  }
  bar.value = ev.ok ? 1 : 0;
  if (ev.ok) $('#c-status').textContent = t('conv_done', { name: ev.info!.split(/[\\/]/).pop()! });
  else if (ev.canceled) $('#c-status').textContent = t('status_canceled');
  else {
    $('#c-status').textContent = t('conv_error');
    appendLog('[erro ffmpeg] ' + ev.info);
  }
}

// ---- aba Fila e Log ------------------------------------------------------------

const depState: Record<string, { state: string; extra?: Record<string, any> }> = {
  ytdlp: { state: 'missing' },
  ffmpeg: { state: 'missing' },
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

function renderJobs(): void {
  const list = $('#q-list');
  list.replaceChildren();
  if (!jobList.length) {
    list.innerHTML = '<span class="empty muted"></span>';
    $('.empty', list).textContent = t('queue_empty');
    return;
  }
  for (const job of jobList) {
    const row = document.createElement('div');
    row.className = 'job';
    row.id = `job-${job.id}`;
    row.innerHTML = '<div class="row"><div class="grow"><div class="name"></div><div class="state muted small">' +
      '</div></div><button class="cancel small"></button></div><progress max="100" value="0"></progress>';
    $('button', row).onclick = () => api.call('queueCancel');
    list.append(row);
    paintJob(job);
  }
}

function paintJob(job: any): void {
  const row = document.getElementById(`job-${job.id}`);
  if (!row) return;
  const position = t('position_of_total', { idx: jobList.indexOf(job) + 1, total: jobList.length });
  let state = t(`status_${job.status}`);
  if (job.status === 'downloading' && job.nowTitle) state = nowLabel(job);
  if (job.status === 'error' && job.errorMsg) state += ` — ${job.errorMsg}`;
  row.dataset.status = job.status;
  $('.name', row).textContent = `${job.title || job.url}${job.artist ? ` - ${job.artist}` : ''} (${position})`;
  $('.state', row).textContent = state;
  $('button', row).textContent = t('cancel_current');
  $<HTMLProgressElement>('progress', row).value = job.progress;
}

function onJob(job: any): void {
  const i = jobList.findIndex((j) => j.id === job.id);
  if (i < 0) return;
  jobList[i] = job;
  paintJob(job);
  const tab = downloadTabs[job.mode];
  if (job.status === 'downloading') tab.setStatus(job.nowTitle ? nowLabel(job) : t('status_downloading'));
  else tab.setStatus(`${t(`status_${job.status}`)} — ${job.title || job.url}`);
  tab.setProgress(job.status === 'downloading' ? job.progress : job.status === 'done' ? 100 : 0);
}

function appendLog(line: string): void {
  const log = $('#q-log');
  const entry = document.createElement('span');
  entry.textContent = `[${new Date().toTimeString().slice(0, 8)}] ${line}\n`;
  if (/ERROR|\[erro/.test(line)) entry.className = 'err';
  log.append(entry);
  log.scrollTop = log.scrollHeight;
}

function setupQueueTab(): void {
  $('#q-deps').onclick = () => api.call('checkDeps', true);
  $('#q-update').onclick = () => api.call('updateYtdlp');
  $('#q-bin').onclick = () => api.call('openBin');
  $('#q-start').onclick = () => api.call('queueStart');
  $('#q-cancel').onclick = () => api.call('queueCancel');
  $('#q-clear-done').onclick = () => api.call('clearFinished');
  $('#q-clear-all').onclick = () => api.call('clearAll');
  $('#q-open').onclick = () => api.call('openFolder', cfg.audio_folder, true);
  $('#q-copy').onclick = () => api.call('copy', $('#q-log').textContent);
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
      'embed_audio_tags', 'keep_video', 'save_folder_cover'],
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
  $('#btn-settings').onclick = () => {
    for (const el of fields) {
      if (el.type === 'checkbox') el.checked = Boolean(cfg[el.dataset.set!]);
      else el.value = cfg[el.dataset.set!] ?? '';
    }
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
  } else if (kind === 'conv') onConvert(data);
});
void api.call('checkDeps', false, true);
