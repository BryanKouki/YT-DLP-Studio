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
  assert.equal(after(c, '-o'), "It's-Mine.%(ext)s");
  assert.equal(after(c, '-P'), 'C:/m'); // pasta de destino; intermediários vão para a pasta temporária
  assert(core.buildCommand(job('audio', { folder: 'C:/m' }), 'x', 'y', 'b', 'C:/t').includes('temp:C:/t'));
  assert.equal(after(c, '--postprocessor-args'), `ffmpeg:-metadata title='It'"'"'s/Mine' -metadata artist=AC/DC -metadata album_artist=AC/DC`);
  // propriedades do arquivo (padrão: tudo menos gênero): ano do ℗, artista do álbum, nº da faixa só em álbum
  const albumArtist = '%(artists.0|)s:(?P<album_artist>.+)';
  const video = cmdFor(job('video', { folder: 'C:/v', embed_metadata_thumb: true }));
  assert(c.includes(albumArtist) && !video.includes(albumArtist) && c.includes('--embed-thumbnail') && video.includes('--embed-thumbnail'));
  assert(c.includes('%(release_year|)s:(?P<meta_date>\\d{4})')); // ano do ℗, não o de envio ao YouTube
  assert(c.includes(':(?P<meta_genre>)') && !c.includes(':(?P<meta_title>)')); // "Music" do YouTube nunca vai
  // desmarcadas: a tag não vai; sem capa embutida o áudio não recorta capa nenhuma
  const off = cmdFor(job('audio', { folder: 'C:/m', embed_metadata_thumb: true, tag_audio_date: false, tag_audio_cover: false,
    tag_audio_album_artist: false, tag_audio_comment: false }, '', 'X'));
  assert(off.includes(':(?P<meta_date>)') && off.includes(':(?P<meta_purl>)') && off.includes(':(?P<meta_comment>)') && !off.includes(albumArtist));
  assert(!off.includes('--embed-thumbnail') && !off.includes('--ppa') && !after(off, '--postprocessor-args').includes('album_artist'));
  assert(!core.tagOn({}, 'audio', 'genre') && core.tagOn({}, 'video', 'title') && core.tagOn({ tag_audio_genre: true }, 'audio', 'genre'));
  const trackTag = core.tagArgs({}, 'audio').find((a) => a.includes('track_number'))!;
  const trackRe = new RegExp(trackTag.slice(trackTag.indexOf(':') + 1).replace('(?P<', '(?<'));
  assert.equal(trackRe.exec('Album - Thriller|02')?.groups?.track_number, '2');
  assert.equal(trackRe.exec('Album - Bad|12')?.groups?.track_number, '12');
  assert.equal(trackRe.exec('Top 100 Funk|02'), null); // playlist comum: sem número de faixa
  // atualização: compara número a número; acha o .exe mesmo com o nome que o GitHub dá ("YT-DLP.Studio.exe")
  assert(core.isNewer('1.4.10', '1.4.2') && core.isNewer('v2.0.0', '1.9.9') && !core.isNewer('1.4.2', '1.4.2') && !core.isNewer('1.4.1', '1.4.2'));
  const rel = { tag_name: 'v1.4.3', html_url: 'https://github.com/BryanKouki/YT-DLP-Studio/releases/tag/v1.4.3', assets: [{ name: 'YT-DLP-Studio-v1.4.3-source.zip', browser_download_url: 'z' },
    { name: 'YT-DLP.Studio.exe', browser_download_url: 'https://x/YT-DLP.Studio.exe', digest: 'sha256:ABC' }] };
  assert.equal(JSON.stringify(core.pickUpdate(rel, '1.4.2')), '{"latest":"1.4.3","newer":true,"url":"https://x/YT-DLP.Studio.exe","sha256":"abc","page":"https://github.com/BryanKouki/YT-DLP-Studio/releases/tag/v1.4.3"}');
  assert(!core.pickUpdate(rel, '1.4.3').newer && core.pickUpdate({}, '1.4.2').url === '');
  // gênero: só de um álbum do mesmo artista (sem acento/caixa); outro artista = sem gênero
  const itunes = { results: [{ artistName: 'Anita Baker', primaryGenreName: 'R&B/soul' }, { artistName: 'Djavan', primaryGenreName: 'MPB' }] };
  assert.equal(core.itunesGenre(itunes, 'DJAVAN'), 'MPB');
  assert.equal(core.itunesGenre(itunes, 'Anitta'), '');
  assert.equal(core.itunesGenre({ results: [{ artistName: 'Beyoncé', primaryGenreName: 'Pop' }] }, 'Beyonce'), 'Pop');
  assert.equal(core.itunesGenre({}, 'x'), '');
  assert(core.genreUrl('Sade', 'Love Deluxe', 'pt').endsWith('country=BR&term=Sade%20Love%20Deluxe'));
  assert.equal(after(cmdFor(job('video', { folder: 'C:/v' })), '-o'), '%(title)s - %(channel,uploader)s.%(ext)s');
  assert(!c.join(' ').includes('uploader') && c.join(' ').includes('%(artist|)s'));
  assert(c.includes('--progress'), 'sem --progress o --print esconde o progresso');
  assert(c.includes('postprocess:PP@@@%(progress.status)s@@@%(progress.postprocessor)s'));
  assert.equal(core.PP_RE.exec('PP@@@started@@@ExtractAudio')?.[2], 'ExtractAudio');
  const busca = core.searchUrls('Try Again - Aaliyah');
  assert.equal(busca.music, 'https://music.youtube.com/search?q=Try+Again+-+Aaliyah');
  assert.equal(busca.youtube, 'https://www.youtube.com/results?search_query=Try+Again+-+Aaliyah');
  assert(core.isYouTube('https://music.youtube.com/playlist?list=X') && core.isYouTube('https://youtu.be/abc'));
  assert(!core.isYouTube('https://soundcloud.com/a/sets/b') && !core.isYouTube('https://notyoutube.com.evil/x'));
  assert.equal(after(c, '--js-runtimes'), core.path.join('bin', 'deno.exe').replace(/^/, 'deno:'));
  assert(after(c, '--print').endsWith('@@@%(id)s@@@%(filepath|)s@@@%(album|)s') && !c.includes('--cookies-from-browser'));

  // 2b. cookies: Firefox por padrão (não Chromium); substituta fica entre as vizinhas (na ordem que a pasta mostra)
  assert.equal(after(cmdFor(job('audio', { folder: 'C:/m', use_cookies: true })), '--cookies-from-browser'), 'firefox');
  assert.equal(core.cookieArgs({ use_cookies: true, cookies_browser: 'chrome' }).join(' '), '--cookies-from-browser chrome');
  const [cr, mo] = core.between([1000, 5000], [3000, 9000], 0);
  assert(cr > 1000 && cr < 3000 && mo > 5000 && mo < 9000, `${cr} ${mo}`);
  assert.equal(core.between([1000, 5000], null, 0)[0], 2000);
  assert.equal(core.between(null, [3000, 9000], 0)[1], 8000);
  assert(core.COOKIE_ERR_RE.test('ERROR: Could not copy Chrome cookie database. See  https://github.com/yt-dlp/yt-dlp/issues/7271'));
  assert(core.COOKIE_ERR_RE.test('ERROR: Failed to decrypt with DPAPI. See  https://github.com/yt-dlp/yt-dlp/issues/10927'));
  // Log colado na caixa de links: só os links das linhas "Iniciando:", sem repetir
  const pastedLog = '[11:17:31] $ \'yt-dlp.exe\' \'https://music.youtube.com/playlist?list=A\'\n' +
    '[11:17:35] ERROR: Could not copy Chrome cookie database. See  https://github.com/yt-dlp/yt-dlp/issues/7271\n' +
    '[11:17:36] Iniciando: https://music.youtube.com/playlist?list=A\n[11:17:43] Iniciando: https://music.youtube.com/playlist?list=B\n' +
    '[11:18:00] Iniciando: https://music.youtube.com/playlist?list=A';
  assert.equal(core.linksFrom(pastedLog).join(' '), 'https://music.youtube.com/playlist?list=A https://music.youtube.com/playlist?list=B');
  assert.equal(core.linksFrom(' u1 \n\n u2 ').join(' '), 'u1 u2');
  assert.equal(core.PL_ERR_RE.exec("ERROR: [youtube] nYuJU4AXxk4: Sign in to confirm you're not a bot")?.[1], 'nYuJU4AXxk4');

  // 3. capas: áudio sempre recorta 1:1; vídeo nunca; música avulsa não deixa arquivo de capa
  assert.equal(after(c, '--ppa'),
    `ThumbnailsConvertor+FFmpeg_o:-c:v mjpeg -vf crop="'"if(gt(ih,iw),iw,ih)"'":"'"if(gt(iw,ih),ih,iw)"'"`);
  assert(!c.includes('--write-thumbnail'));
  c = cmdFor(job('video', { folder: 'C:/v', embed_metadata_thumb: true, save_thumbnail: true }));
  assert(c.includes('--write-thumbnail') && !c.includes('--ppa'));

  // 4. playlist + "Guardar thumbnail": nenhuma capa de faixa vai pro disco (só a embutida, recortada);
  //    a capa da playlist vem de um comando à parte que não toca nas faixas
  c = cmdFor(job('audio', { folder: 'C:/pl', save_thumbnail: true, _is_playlist: true, embed_metadata_thumb: true }));
  assert(!c.includes('--write-thumbnail') && !c.some((a) => a.startsWith('pl_thumbnail:')) && c.includes('--ppa'));
  assert(cmdFor(job('audio', { folder: 'C:/m', save_thumbnail: true })).includes('--write-thumbnail'));
  c = cmdFor(job('audio', { folder: 'C:/pl', save_track_covers: true, _is_playlist: true }));
  assert(c.includes('--write-thumbnail') && c.includes('--ppa') && c.includes('pl_thumbnail:')); // capa de cada música, quadrada; sem a da playlist
  const cover = core.playlistCoverArgs(' u ', 'C:/pl');
  assert(cover.includes('--flat-playlist') && after(cover, '--playlist-items') === '0' && cover.at(-1) === 'u');
  assert(cover.some((a) => a.startsWith('pl_thumbnail:') && a.endsWith('playlist_thumb.%(ext)s')));
  assert.equal(core.artistFromUploader('Anitta - Topic'), 'Anitta');
  // bloqueio na 19 de 32 depois de baixar até a 18: continua da 19
  assert.equal(core.resumeFrom(['16', '17', '18']), '19:');
  assert.equal(core.resumeFrom([]), '');
  // montar playlist: canal do 1º artista da busca; na página dele, a lista "Top songs"; busca de músicas
  const artistEp = (id: string) => ({ browseEndpoint: { browseId: id,
    browseEndpointContextSupportedConfigs: { browseEndpointContextMusicConfig: { pageType: 'MUSIC_PAGE_TYPE_ARTIST' } } } });
  assert.equal(core.ytmArtistId({ contents: [{ a: { navigationEndpoint: artistEp('UCx') } }, { navigationEndpoint: artistEp('UCy') }] }), 'UCx');
  assert.equal(core.ytmArtistId({}), '');
  const col = (text: string) => ({ musicResponsiveListItemFlexColumnRenderer: { text: { runs: [{ text }] } } });
  const top = core.ytmTopSongs({
    header: { musicImmersiveHeaderRenderer: { title: { runs: [{ text: 'Sade' }] } } },
    contents: { tabs: [{ musicShelfRenderer: { bottomEndpoint: { browseEndpoint: { browseId: 'VLOLAK5uy_abc' } },
      contents: [{ musicResponsiveListItemRenderer: { flexColumns: [col('Smooth Operator'), col('Sade'), col('489M plays')] } }] } }] },
  });
  assert.equal(JSON.stringify(top), '{"artist":"Sade","list":"OLAK5uy_abc"}');
  assert.equal(core.ytmTopSongs({ header: {}, contents: {} }).list, '');
  const songs = core.ytmSongs({ x: [{ musicResponsiveListItemRenderer: { playlistItemData: { videoId: 'XzNWRmqibNE' },
    flexColumns: [col('Smooth Criminal'), col('Michael Jackson • Bad • 4:18')] } }, { musicResponsiveListItemRenderer: {} }] });
  assert.equal(JSON.stringify(songs), '[{"id":"XzNWRmqibNE","title":"Smooth Criminal","artist":"Michael Jackson","info":"Michael Jackson • Bad • 4:18"}]');
  // lista montada: um link por faixa (só as posições pedidas), sem --playlist-items
  const list = [{ id: 'a', title: 'A', artist: '' }, { id: 'b', title: 'B', artist: '' }, { id: 'c', title: 'C', artist: '' }];
  assert.equal(core.trackUrls(list, '1,3').join(' '), 'https://music.youtube.com/watch?v=a https://music.youtube.com/watch?v=c');
  c = cmdFor(job('audio', { folder: 'C:/m', tracks: list, playlist_items: '2', _is_playlist: true }));
  assert.equal(c[1], 'https://music.youtube.com/watch?v=b');
  assert(!c.includes('--playlist-items') && !c.includes('u'));
  assert.equal(JSON.stringify(core.splitRoundRobin(['1', '2', '3', '4', '5', '6', '7'], 3)), '[["1","4","7"],["2","5"],["3","6"]]');
  assert.equal(core.splitRoundRobin(['9'], 3).length, 1); // menos faixas que processos: um processo por faixa
  assert.equal(core.playlistIdFrom('https://music.youtube.com/playlist?list=PLsTaFPbVzr42Zagqe6HDBgac7erdK4M41'), 'PLsTaFPbVzr42Zagqe6HDBgac7erdK4M41');
  assert.equal(core.playlistIdFrom('https://www.youtube.com/watch?v=abc&list=RDabc&index=2'), 'RDabc');
  assert.equal(core.playlistIdFrom('https://www.youtube.com/watch?v=abc'), ''); // bloqueou logo na primeira: recomeça do início
  // .m3u8: ordem da playlist (a substituta da posição 2 entra entre 1 e 3), caminho relativo
  assert.equal(core.m3uText([{ pos: 3, file: 'C:\\pl\\c.mp3' }, { pos: 1, file: 'C:\\pl\\a.mp3' }, { pos: 2, file: 'C:\\pl\\b b.mp3' }]),
    '#EXTM3U\r\n#EXTINF:-1,a\r\na.mp3\r\n#EXTINF:-1,b b\r\nb b.mp3\r\n#EXTINF:-1,c\r\nc.mp3\r\n');

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
