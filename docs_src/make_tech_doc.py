import sys, os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Image, Spacer, PageBreak, Paragraph

from pdf_common import (
    STYLES, h1, h2, h3, body, bullets, numbered, code, hr, sp,
    simple_table, page_decoration,
)

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs",
                    "Documentacao_Tecnica_YT-DLP_Studio.pdf")

story = []

# ---------------------------------------------------------------- CAPA --
story.append(Spacer(1, 4 * cm))
story.append(Image(os.path.join(ASSETS, "icon.png"), width=3 * cm, height=3 * cm, hAlign="CENTER"))
story.append(Spacer(1, 0.8 * cm))
story.append(Paragraph("YT-DLP Studio", STYLES["cover_title"]))
story.append(Paragraph("Documentação Técnica", STYLES["cover_subtitle"]))
story.append(Spacer(1, 0.6 * cm))
story.append(Paragraph(
    f"Arquitetura, funcionamento interno e guia de manutenção/extensão<br/>"
    f"Versão do documento — {date.today().strftime('%d/%m/%Y')}", STYLES["cover_meta"]))
story.append(PageBreak())

# ------------------------------------------------------------ SUMÁRIO --
story.append(h1("Sumário"))
for it in [
    "1. Visão geral e stack tecnológica",
    "2. Estrutura de arquivos do projeto",
    "3. Fluxo de execução (o que acontece ao abrir o programa)",
    "4. Módulo por módulo",
    "5. Como os comandos do yt-dlp são montados (downloader.py)",
    "6. O mecanismo de recorte de capa (--ppa e escaping)",
    "7. Gerenciamento de dependências (yt-dlp + FFmpeg)",
    "8. Fila de downloads e threading",
    "9. Persistência de configurações",
    "10. Internacionalização (i18n)",
    "11. Guia prático: como adicionar/alterar coisas comuns",
    "12. Build e empacotamento (gerando o .exe)",
    "13. Solução de problemas para desenvolvedores",
]:
    story.append(body(it))
story.append(PageBreak())

# ----------------------------------------------------------- 1. VISÃO --
story.append(h1("1. Visão geral e stack tecnológica"))
story.append(body(
    "O YT-DLP Studio é um aplicativo desktop escrito em <b>Python 3</b>, usando "
    "<b>CustomTkinter</b> (biblioteca de UI sobre o Tkinter padrão) para a interface "
    "gráfica. Ele não reimplementa nenhuma lógica de download: todo o trabalho "
    "pesado é feito pelo binário oficial do <b>yt-dlp</b> e pelo <b>FFmpeg</b>, "
    "chamados como processos externos via <tt>subprocess</tt>. O programa é, em "
    "essência, um construtor de linha de comando com interface gráfica, mais um "
    "gerenciador de fila/dependências em volta disso."
))
story.append(simple_table([
    ["Peça", "Tecnologia", "Papel"],
    ["Interface gráfica", "CustomTkinter (Tkinter)", "Janelas, abas, formulários"],
    ["Motor de download", "yt-dlp (binário externo)", "Extração e download real"],
    ["Processamento de mídia", "FFmpeg (binário externo)", "Conversão, corte, capa, mux"],
    ["Empacotamento", "PyInstaller", "Gera o .exe standalone"],
    ["Persistência", "JSON (settings.json)", "Configurações do usuário"],
], col_widths=[4 * cm, 5.5 * cm, 6.5 * cm]))

# ----------------------------------------------------- 2. ESTRUTURA --
story.append(h1("2. Estrutura de arquivos do projeto"))
story.append(code(
    "ytdlp_studio/\n"
    "|-- build.bat              # gera o .exe (Windows, via PyInstaller)\n"
    "|-- requirements.txt\n"
    "|-- assets/\n"
    "|   |-- icon.ico / icon.png    # icone do app\n"
    "|   |-- logo.png               # logo horizontal (README/splash)\n"
    "|   `-- theme_red.json         # tema CustomTkinter preto/branco/vermelho\n"
    "|-- docs/                  # os dois PDFs (usuario + tecnico)\n"
    "`-- src/\n"
    "    |-- main.py            # ponto de entrada, janela principal\n"
    "    |-- theme.py           # cores compartilhadas (vermelho, cinza, contorno)\n"
    "    |-- i18n.py            # strings PT/EN\n"
    "    |-- settings_store.py  # settings.json (ler/gravar)\n"
    "    |-- dependencies.py    # baixa/verifica yt-dlp e FFmpeg\n"
    "    |-- downloader.py      # monta comandos yt-dlp + fila (thread)\n"
    "    |-- tabs.py            # abas Audio e Video\n"
    "    |-- queue_tab.py       # aba Fila e Log\n"
    "    |-- settings_dialog.py # janela de Configuracoes\n"
    "    |-- help_dialog.py     # janela de Ajuda\n"
    "    `-- widgets.py         # RangeSlider (slider de recorte)"
))

# ----------------------------------------------------- 3. FLUXO --
story.append(h1("3. Fluxo de execução"))
story.append(numbered([
    "<b>main.py</b> cria a classe <tt>App(ctk.CTk)</tt>, que carrega "
    "<tt>SettingsStore</tt> (lê settings.json) e <tt>Translator</tt> (define o "
    "idioma da UI).",
    "A barra superior (<tt>_build_topbar</tt>) e o conteúdo (<tt>_build_content</tt>) "
    "são montados. As três abas (<tt>AudioTab</tt>, <tt>VideoTab</tt>, "
    "<tt>QueueTab</tt>) são instanciadas de uma vez e empilhadas na mesma célula "
    "de grid — trocar de aba é só chamar <tt>.tkraise()</tt> na aba escolhida.",
    "300 ms depois da janela abrir, <tt>check_dependencies(initial=True)</tt> "
    "roda em uma <i>thread</i> separada, verificando/baixando yt-dlp e FFmpeg sem "
    "travar a interface.",
    "Um laço <tt>_poll_queue_events</tt> roda a cada 150 ms via "
    "<tt>self.after(150, ...)</tt>, lendo uma <tt>queue.Queue</tt> onde threads de "
    "fundo (dependências, downloads) depositam eventos. Esse é o único ponto onde "
    "widgets são atualizados — nunca direto de dentro de uma thread.",
    "Quando o usuário clica em Download/Adicionar à fila, um objeto "
    "<tt>downloader.Job</tt> é criado e entregue ao <tt>QueueManager</tt>, que "
    "processa a fila sequencialmente em sua própria thread.",
]))

# ----------------------------------------------------- 4. MÓDULOS --
story.append(h1("4. Módulo por módulo"))

story.append(h2("main.py — App"))
story.append(body(
    "Classe principal da janela. Responsabilidades: montar a barra superior "
    "(abas + engrenagem + ajuda + tema + idioma), alternar entre as três abas, "
    "abrir os diálogos de Configurações/Ajuda, rodar dependências em thread, e o "
    "laço <tt>_poll_queue_events</tt> que traduz eventos da fila em atualizações "
    "de UI. Também guarda <tt>build_output_template(job)</tt>, que decide o "
    "caminho/nome final do arquivo baixado a partir da pasta configurada e do "
    "título/artista do job."
))

story.append(h2("i18n.py"))
story.append(body(
    "Um dicionário <tt>STRINGS = {'pt': {...}, 'en': {...}}</tt> com todas as "
    "strings da interface por chave. A classe <tt>Translator</tt> guarda o "
    "idioma atual e expõe <tt>.t(chave, **kwargs)</tt>, que busca a string e "
    "aplica <tt>.format(**kwargs)</tt> se houver parâmetros (ex.: "
    "<tt>tr.t('dep_downloading', size='~80MB')</tt>)."
))

story.append(h2("settings_store.py"))
story.append(body(
    "<tt>SettingsStore</tt> guarda um dicionário com todas as preferências "
    "(pastas, opções de rede/filtros/comportamento, últimos valores escolhidos "
    "nas abas, geometria da janela). <tt>DEFAULTS</tt> define os valores "
    "padrão — ao carregar, valores salvos são mesclados por cima dos padrões, "
    "então adicionar uma nova configuração no futuro nunca quebra um "
    "settings.json antigo (a chave nova simplesmente usa o padrão até o usuário "
    "mudar). Por padrão o arquivo fica em <tt>data/settings.json</tt>, bem ao "
    "lado do executável (ver seção 7 para os detalhes de como essa pasta é "
    "resolvida, com fallback para <tt>%APPDATA%</tt>)."
))

story.append(h2("dependencies.py"))
story.append(body(
    "Resolve os caminhos de <tt>yt-dlp.exe</tt>/<tt>ffmpeg.exe</tt>/"
    "<tt>ffprobe.exe</tt> dentro de uma pasta <tt>bin/</tt> ao lado do "
    "settings.json. <tt>check_ytdlp()</tt>/<tt>check_ffmpeg()</tt> rodam "
    "<tt>--version</tt> para confirmar que o binário existe e funciona. "
    "<tt>install_ytdlp()</tt> baixa o executável mais recente direto do GitHub "
    "Releases; <tt>install_ffmpeg()</tt> baixa o pacote 'essentials' (Windows) e "
    "extrai só os três executáveis do .zip. A classe <tt>DependencyManager</tt> "
    "orquestra tudo isso e reporta progresso via um callback "
    "<tt>status_cb(componente, estado, extra)</tt>."
))

story.append(h2("downloader.py"))
story.append(body(
    "O módulo mais importante para manutenção. Contém: os dicionários de "
    "mapeamento UI→flag do yt-dlp (ex.: <tt>RES_HEIGHT</tt>, <tt>VCODEC_FILTER</tt>, "
    "<tt>AUDIO_QUALITY_VALUE</tt>), a função <tt>build_command(job, "
    "output_template)</tt> que monta a lista de argumentos final, e a classe "
    "<tt>QueueManager</tt> que executa os jobs em uma thread de fundo. Detalhado "
    "na seção 5."
))

story.append(h2("tabs.py"))
story.append(body(
    "<tt>DownloadTabBase</tt> é a classe-mãe com tudo que Áudio e Vídeo têm em "
    "comum: caixa de link, slider de recorte, botões de pasta, "
    "Download/Adicionar à fila, status e barra de progresso. <tt>AudioTab</tt> e "
    "<tt>VideoTab</tt> só implementam <tt>build_options_row()</tt> (os campos "
    "específicos de cada uma) e <tt>gather_tab_options()</tt> (o dicionário de "
    "opções que vira <tt>job.options</tt>)."
))

story.append(h2("queue_tab.py"))
story.append(body(
    "Interface da aba Fila e Log: <tt>DepStatusRow</tt> (bolinha colorida + "
    "texto de status), <tt>QueueRow</tt> (um item da fila, com sua própria barra "
    "de progresso) e a classe <tt>QueueTab</tt> que organiza tudo, incluindo o "
    "painel de log (<tt>append_log</tt>)."
))

story.append(h2("settings_dialog.py / help_dialog.py"))
story.append(body(
    "Janelas <tt>CTkToplevel</tt> independentes. <tt>SettingsDialog</tt> monta "
    "cada seção (Pastas, Rede, Filtros, Comportamento, Arquivos extras) a partir "
    "de pequenas classes auxiliares (<tt>LabeledEntry</tt>, <tt>LabeledCheck</tt>) "
    "que sabem carregar/salvar seu próprio valor de/para o "
    "<tt>SettingsStore</tt>. <tt>HelpDialog</tt> apenas renderiza o conteúdo "
    "estático de <tt>HELP_CONTENT</tt> (um dicionário pt/en de seções)."
))

story.append(h2("widgets.py"))
story.append(body(
    "<tt>RangeSlider</tt>: um slider de dois cabos desenhado à mão com "
    "<tt>tkinter.Canvas</tt> (CustomTkinter não tem um componente nativo para "
    "isso). Funções auxiliares <tt>seconds_to_hms</tt>/<tt>hms_to_seconds</tt> "
    "convertem entre segundos e o formato HH:MM:SS mostrado nos campos de texto. "
    "Como o Canvas é Tk puro (não CustomTkinter), ele não recebe automaticamente "
    "a troca de tema claro/escuro em tempo de execução — por isso existe o "
    "método <tt>refresh_theme()</tt>, chamado explicitamente por "
    "<tt>App.toggle_theme()</tt> para recalcular a cor de fundo do canvas "
    "sempre que o tema muda."
))

story.append(h2("theme.py + assets/theme_red.json"))
story.append(body(
    "A paleta preto/branco/vermelho (#FF0000, igual à identidade visual do "
    "yt-dlp) tem duas camadas: <tt>assets/theme_red.json</tt> é um tema "
    "completo do CustomTkinter (mesmo schema do tema 'blue' embutido na "
    "biblioteca, só que com os azuis trocados por vermelho), carregado uma "
    "vez em <tt>main.py</tt> via <tt>ctk.set_default_color_theme(...)</tt> — "
    "isso já cobre automaticamente qualquer widget sem cor explícita "
    "(entradas, checkboxes, menus, abas). <tt>theme.py</tt> complementa com "
    "constantes Python (<tt>PRIMARY_KW</tt>, <tt>CANCEL_KW</tt>, "
    "<tt>SECONDARY_KW</tt>) para os poucos botões que precisam de estilo "
    "diferente do padrão — em especial <tt>CANCEL_KW</tt>, que desenha um "
    "botão 'fantasma' (fundo transparente, contorno vermelho) para as ações "
    "de cancelar não ficarem visualmente idênticas aos botões vermelhos "
    "sólidos de ação primária (Download, Iniciar Fila). Para mudar o tom de "
    "vermelho usado em todo o app, basta editar essas duas fontes; não há "
    "cor de tema espalhada em outros arquivos."
))

# ----------------------------------------------------- 5. BUILD_COMMAND --
story.append(h1("5. Como os comandos do yt-dlp são montados"))
story.append(body(
    "Cada download é representado por um objeto <tt>downloader.Job</tt>: modo "
    "('audio' ou 'video'), URL, título/artista opcionais, e um dicionário "
    "<tt>options</tt>. Esse dicionário é montado em <tt>tabs.py → "
    "DownloadTabBase._make_jobs()</tt> mesclando <b>todas</b> as configurações "
    "globais (<tt>dict(self.app.settings.data)</tt>) com as opções específicas "
    "daquela aba (formato, resolução, etc.) — por isso, dentro de "
    "<tt>build_command</tt>, a variável <tt>s = job.options</tt> serve tanto "
    "para ler configurações globais quanto opções da aba, sem distinção."
))
story.append(body("A montagem segue sempre a mesma ordem em <tt>build_command()</tt>:"))
story.append(numbered([
    "Flags base: caminho do yt-dlp, URL, <tt>--newline --no-color --no-warnings "
    "--ignore-errors</tt>, localização do FFmpeg, e o template de saída (-o).",
    "Flags de comportamento geral (restrict-filenames, no-playlist, "
    "download-archive, geo-bypass, etc.) — cada uma checando "
    "<tt>s.get('chave')</tt>.",
    "Flags numéricas de rede/robustez (fragmentos paralelos, tentativas, "
    "limite de velocidade, proxy, playlist-items, filtros de data/tamanho/duração).",
    "Recorte de trecho: se <tt>trim_start</tt>/<tt>trim_end</tt> foram "
    "definidos pelo slider, adiciona <tt>--download-sections '*INÍCIO-FIM' "
    "--force-keyframes-at-cuts</tt>.",
    "Arquivos extras (metadados, capítulos, descrição, thumbnail).",
    "Bloco específico de áudio (<tt>-x --audio-format --audio-quality</tt>, "
    "capa quadrada, metadados via <tt>--postprocessor-args</tt>) <b>ou</b> "
    "bloco específico de vídeo (<tt>-f</tt> com o seletor de formato, "
    "contêiner, legendas) — nunca os dois.",
    "Por fim, se o usuário preencheu um template avançado em Configurações → "
    "Rede, ele substitui o -o padrão.",
]))
story.append(h3("Exemplo de seletor de formato de vídeo"))
story.append(body(
    "<tt>build_format_selector()</tt> traduz Resolução/FPS/Codec em filtros do "
    "seletor -f do yt-dlp, sempre com uma alternativa de fallback para nunca "
    "falhar por excesso de restrição:"
))
story.append(code(
    "# Resolução 1080p + codec H.264 vira:\n"
    "bestvideo[height<=1080][vcodec~='^avc1']+bestaudio\n"
    "/best[height<=1080]"
))
story.append(body(
    "Ou seja: tenta achar vídeo+áudio separados que batam com os filtros; se "
    "não achar, cai para o melhor stream único disponível dentro da resolução "
    "pedida. Para adicionar um novo codec, basta acrescentar uma entrada em "
    "<tt>VCODEC_FILTER</tt> (downloader.py) e na lista de opções da UI "
    "(tabs.py) — ver seção 11."
))

story.append(h2("Pasta de playlist e status ao vivo (--print)"))
story.append(body(
    "Antes de cada job de verdade, <tt>QueueManager._resolve_playlist_folder()</tt> "
    "roda um comando rápido e separado — a mesma estratégia usada no script "
    ".ps1 original — para descobrir se o link é uma playlist:"
))
story.append(code(
    "yt-dlp --get-filename --no-warnings -o \"%(playlist_title)s\" \n"
    "       URL --playlist-items 1"
))
story.append(body(
    "Se o resultado não for vazio, \"NA\" nem a própria URL, "
    "<tt>job.options['folder']</tt> é trocado por uma subpasta com esse nome "
    "(sanitizada por <tt>sanitize_filename()</tt>) antes do template de saída "
    "ser calculado — por isso essa checagem precisa rodar <b>antes</b> de "
    "<tt>output_template_fn(job)</tt> em <tt>_run_job()</tt>."
))
story.append(body(
    "Para o status \"Título - Artista (X de Y)\" em tempo real, "
    "<tt>build_command()</tt> sempre adiciona dois <tt>--print</tt>, usando "
    "os pontos de disparo reais do yt-dlp <tt>before_dl</tt> (antes de cada "
    "vídeo começar a baixar) e <tt>after_move</tt> (depois do arquivo final "
    "estar pronto), com um prefixo próprio (<tt>BDL@@@</tt>/<tt>ADL@@@</tt>) "
    "e campos separados por <tt>@@@</tt> para serem fáceis de reconhecer e "
    "quebrar em <tt>NOW_PLAYING_RE</tt>:"
))
story.append(code(
    "--print before_dl:BDL@@@%(title)s@@@"
    "%(artist|)s@@@%(playlist_index|)s@@@%(playlist_count|)s\n"
    "--print after_move:ADL@@@%(title)s@@@"
    "%(artist|)s@@@%(playlist_index|)s@@@%(playlist_count|)s"
))
story.append(body(
    "<tt>%(artist|)s</tt> usa só o metadado real de artista (presente "
    "sobretudo em links do YouTube Music), com string vazia como padrão "
    "quando não existe — <b>de propósito sem cair para <tt>uploader</tt> "
    "(nome do canal)</b>. Uma primeira versão usava "
    "<tt>%(artist,uploader,creator|)s</tt> como fallback, mas isso fazia o "
    "nome de canais que só reúpam remixes/covers (ex.: 'Canal X') virar um "
    "prefixo errado no nome do arquivo e nos metadados — "
    "'Canal X - Nome da Música' em vez de só 'Nome da Música'. As duas "
    "flags foram validadas rodando o yt-dlp baixado de verdade contra uma "
    "URL inválida: o erro retornado foi de rede (DNS), não de parsing de "
    "argumento — confirmando que a sintaxe é aceita."
))
story.append(body(
    "Quando uma dessas linhas chega no loop de leitura do stdout em "
    "<tt>_run_job()</tt>, um evento <tt>now_playing</tt> é emitido (em vez "
    "do evento genérico <tt>log</tt>) e tratado em "
    "<tt>App._handle_queue_event()</tt>, que monta o texto localizado e "
    "grava em <tt>job.current_label</tt> — lido depois tanto pelo status da "
    "aba quanto por <tt>QueueRow.refresh()</tt>."
))

story.append(h2("Busca automática de título/artista/duração"))
story.append(body(
    "Ao colar exatamente um link numa aba (áudio ou vídeo), "
    "<tt>DownloadTabBase</tt> agenda uma chamada a "
    "<tt>downloader.probe_media_info(url)</tt> 900&nbsp;ms depois da última "
    "tecla apertada (<tt>_on_link_changed</tt> cancela e reagenda o "
    "<tt>self.after()</tt> a cada tecla — debounce simples), rodando numa "
    "thread separada para nunca travar a UI. A função roda um comando "
    "rápido, sem baixar nada:"
))
story.append(code(
    "yt-dlp --print \"%(title|)s@@@%(artist|)s@@@%(duration|0)s\" \n"
    "       --skip-download --playlist-items 1 URL"
))
story.append(body(
    "O resultado volta pela mesma fila thread-safe já usada pelos downloads "
    "(<tt>self._probe_results</tt>, um <tt>queue.Queue</tt> por aba, lido a "
    "cada 200&nbsp;ms por <tt>_poll_probe_results</tt>). Um número de "
    "sequência (<tt>self._probe_seq</tt>) descarta resultados de uma busca "
    "antiga caso o usuário troque o link antes dela terminar. O resultado "
    "atualiza a duração/slider em <tt>DownloadTabBase._apply_probe_result()</tt> "
    "e, na aba de áudio, também título/artista (só se esses campos ainda "
    "estiverem vazios — <tt>AudioTab</tt> sobrescreve o método e chama "
    "<tt>super()</tt> primeiro). Com mais de um link colado, "
    "<tt>_start_probe()</tt> retorna sem fazer nada: título/artista/recorte "
    "valem para todos os itens de uma leva em <tt>_make_jobs()</tt>, então "
    "preenchê-los com dados só do primeiro link aplicaria esses dados "
    "errado nos outros."
))

story.append(h2("Nome do arquivo final: duas regras separadas"))
story.append(body(
    "<tt>App.build_output_template(job)</tt>, em main.py, é onde o "
    "template <tt>-o</tt> passado ao yt-dlp é decidido — e áudio e vídeo "
    "seguem regras propositalmente diferentes, sem nenhum código "
    "compartilhado entre elas:"
))
story.append(code(
    "if job.mode == \"audio\":\n"
    "    # SÓ o título, nunca o artista, mesmo se job.artist existir\n"
    "    return f\"{pasta}/{job.title ou '%(title)s'}.%(ext)s\"\n"
    "# vídeo: título + canal, resolvido pelo próprio yt-dlp\n"
    "return f\"{pasta}/%(title)s - %(channel,uploader)s.%(ext)s\""
))
story.append(body(
    "Essa separação existe porque o campo <tt>artist</tt> do YouTube "
    "(usado tanto pelo <tt>probe_media_info()</tt> quanto pelos metadados "
    "embutidos) nem sempre é confiável — em vídeos sem uma ficha técnica "
    "musical de verdade, pode vir preenchido com algo tão inútil pra nome "
    "de arquivo quanto o nome do canal que subiu o remix/cover. Em vez de "
    "tentar adivinhar quando esse dado é confiável, o nome do arquivo de "
    "áudio simplesmente <b>nunca</b> usa <tt>job.artist</tt> — só "
    "<tt>job.title</tt> (preenchido pelo probe ou digitado à mão) ou, na "
    "ausência dele, o <tt>%(title)s</tt> resolvido pelo próprio yt-dlp. O "
    "campo Artista continua enviado para <tt>--postprocessor-args</tt> "
    "(metadados/ID3 do arquivo, seção 5), então mudar essa política de "
    "nomes não afeta os metadados internos."
))
story.append(body(
    "Para vídeo, <tt>%(channel,uploader)s</tt> é resolvido inteiramente "
    "pelo próprio yt-dlp no momento do download (sintaxe de campos "
    "alternativos, igual à usada em <tt>probe_media_info()</tt>) — não "
    "depende de nenhuma busca prévia do lado do app. Em playlists, "
    "<tt>_resolve_playlist_folder()</tt> zera <tt>job.title</tt>/<tt>job.artist</tt> "
    "(preenchidos pela busca com a 1ª faixa) antes de montar o template e o "
    "comando — sem isso todas as faixas iam para o mesmo nome de arquivo e "
    "recebiam o mesmo <tt>-metadata title=</tt>, sobrescrevendo-se."
))

story.append(h2("Thumbnail: regras de JPG e recorte 1:1"))
story.append(body(
    "A decisão de quando salvar/converter/recortar uma thumbnail está toda "
    "concentrada em poucas linhas no início de <tt>build_command()</tt>. "
    "Não existe uma configuração separada pra isso — em áudio, o recorte "
    "quadrado é sempre automático, tanto pra capa embutida quanto pra "
    "salva em disco (uma versão anterior tinha um toggle 'Capa quadrada "
    "1:1' em Configurações, removido por ser redundante: não há cenário "
    "onde faz sentido querer uma capa de música NÃO quadrada):"
))
story.append(code(
    "save_thumb_file = ... # 'Guardar thumbnail' OU (playlist + salvar capa)\n"
    "want_thumbnail = save_thumb_file or embed_metadata_thumb\n"
    "want_square_crop = job.mode == \"audio\" and want_thumbnail\n"
    "want_jpg_convert = save_thumb_file or want_square_crop"
))
story.append(body(
    "O recorte 1:1 é sempre condicionado a <tt>job.mode == \"audio\"</tt> — "
    "uma thumbnail de vídeo nunca é recortada (fica no tamanho/proporção "
    "original), mesmo com 'Guardar thumbnail' marcado. <tt>--embed-thumbnail</tt> "
    "continua controlado só por 'Incorporar metadados e capa' (que já vem "
    "ligado por padrão); marcar apenas 'Guardar thumbnail' salva/recorta o "
    "arquivo em disco sem necessariamente embutir a capa no áudio."
))

# ----------------------------------------------------- 6. CAPA QUADRADA --
story.append(h1("6. O mecanismo de recorte de capa (--ppa e escaping)"))
story.append(body(
    "O recorte 1:1 automático de capas de música (seção anterior) usa o "
    "mecanismo <tt>--ppa NOME:ARGS</tt> do "
    "yt-dlp para injetar argumentos extras no FFmpeg dentro do passo de "
    "conversão de thumbnail (postprocessor <tt>ThumbnailsConvertor</tt>), "
    "aplicando um filtro de recorte central:"
))
story.append(code("crop='if(gt(ih,iw),iw,ih)':'if(gt(iw,ih),ih,iw)'"))
story.append(body(
    "O desafio é que o yt-dlp faz seu próprio <tt>shlex.split()</tt> no valor "
    "de <tt>--ppa</tt> antes de repassar ao FFmpeg — e esse split remove aspas "
    "simples soltas, que são justamente o que protege as vírgulas da expressão "
    "contra serem lidas como separador de filtro pelo FFmpeg. A solução (em "
    "<tt>SQUARE_CROP_PPA</tt>, downloader.py) é envolver cada aspa simples "
    "literal em aspas duplas (<tt>\"'\"</tt>), um truque clássico de quoting "
    "estilo shell POSIX que sobrevive ao <tt>shlex.split</tt>:"
))
story.append(code(
    "_Q = the 3-character string:  \"  '  \"\n"
    "SQUARE_CROP_PPA = (\n"
    '    "ThumbnailsConvertor+FFmpeg_o:-c:v mjpeg -vf "\n'
    "    f\"crop={_Q}if(gt(ih,iw),iw,ih){_Q}:{_Q}if(gt(iw,ih),ih,iw){_Q}\"\n"
    ")"
))
story.append(body(
    "Isso foi validado isoladamente rodando <tt>shlex.split()</tt> em Python "
    "sobre o valor final e conferindo que o token resultante é exatamente "
    "<tt>crop='if(gt(ih,iw),iw,ih)':'if(gt(iw,ih),ih,iw)'</tt>, com as aspas "
    "simples preservadas. <b>Se essa string precisar ser alterada, revalide "
    "sempre com um teste de shlex antes de testar com o yt-dlp de verdade</b> — "
    "é fácil quebrar o escaping sem perceber."
))
story.append(body(
    "Quando o job é uma playlist detectada (ver seção 5) e a opção 'Salvar "
    "capa do álbum/playlist na pasta' está ativa (ligada por padrão), "
    "<tt>promote_folder_cover()</tt> roda depois que o job termina com "
    "sucesso: procura a imagem de thumbnail mais antiga na subpasta da "
    "playlist (heurística: geralmente é a primeira faixa) e copia/converte "
    "para <tt>playlistcover.jpg</tt>, usando o próprio FFmpeg já empacotado "
    "no app quando o formato original não é jpg."
))

story.append(h2("Capa de playlist, verificação e aba Converter"))
story.append(body(
    "<b>Capa de playlist:</b> com a playlist detectada e 'Guardar thumbnail' "
    "(ou 'Salvar capa na pasta') ligado, <tt>build_command()</tt> adiciona "
    "<tt>-o \"pl_thumbnail:PASTA/playlist_thumb.%(ext)s\"</tt> (tipo de template "
    "documentado do yt-dlp) para a capa da própria playlist ter nome fixo. Ao "
    "terminar, <tt>promote_folder_cover()</tt> prefere esse arquivo (cai para a "
    "imagem mais antiga se a playlist não tiver capa), converte para "
    "<tt>playlistcover.jpg</tt> recortando 1:1 em áudio, e "
    "<tt>cleanup_stray_thumbnails()</tt> apaga as capas das faixas."
))
story.append(body(
    "<b>Verificação:</b> <tt>downloader.check_playlist(url, emit)</tt> é a porta "
    "do script PowerShell: <tt>--flat-playlist --print \"%(id)s\\t%(title)s\"</tt> "
    "mapeia posição/título, depois <tt>-i -s --print OK:%(id)s</tt> simula a "
    "playlist inteira e cada linha <tt>ERROR: [x] ID: motivo</tt> (regex "
    "<tt>PL_ERR_RE</tt>) vira uma linha no Log com as vizinhas. Roda numa thread; "
    "<tt>emit</tt> é a mesma fila thread-safe do Log."
))
story.append(body(
    "<b>Aba Converter</b> (<tt>converter_tab.py</tt>): "
    "<tt>build_ffmpeg_cmd()</tt> monta o comando a partir de duas tabelas "
    "(<tt>AUDIO</tt>: bitrate por qualidade; <tt>VIDEO</tt>: CRF por qualidade) e "
    "limita a resolução com <tt>scale=-2:'min(ih,H)'</tt> (nunca amplia). O "
    "progresso vem de <tt>-progress pipe:1</tt>: a duração sai da linha "
    "<tt>Duration:</tt> e o andamento de <tt>out_time_us=</tt>, ambos no stdout "
    "com stderr mesclado. Para novo formato, basta uma linha em "
    "<tt>AUDIO</tt>/<tt>VIDEO</tt>. Compressor: com <tt>target_bytes</tt>, "
    "<tt>probe_duration()</tt> (ffprobe) lê a duração e o bitrate vira "
    "<tt>bytes×8/duração×0,97</tt> (3% de folga pro contêiner); em vídeo, desconta "
    "o <tt>-b:a</tt> da tabela e usa <tt>-b:v/-maxrate/-bufsize</tt> numa só "
    "passagem (o <tt>-b:v</tt> no fim sobrescreve o <tt>-b:v 0</tt> do VP9, pois no "
    "ffmpeg vale a última opção). Alvo impossível (&lt;100 kbps de vídeo) ou "
    "FLAC/WAV geram <tt>ValueError</tt>, mostrado no Log. Se precisar de tamanho "
    "exato, o próximo passo é 2-pass (<tt>-pass 1/2</tt>). <tt>src/selfcheck.py</tt> testa sem rede o "
    "comando do conversor, o template da capa e o parser da verificação."
))

# ----------------------------------------------------- 7. DEPENDÊNCIAS --
story.append(h1("7. Gerenciamento de dependências"))
story.append(body(
    "yt-dlp e FFmpeg <b>não</b> são embutidos no .exe — são baixados na "
    "primeira execução e guardados numa pasta <tt>data/bin/</tt> criada bem ao "
    "lado do próprio executável (modo portátil: fácil de achar, copiar ou "
    "apagar — nada escondido em AppData). Isso mantém o instalador pequeno e "
    "garante que o usuário sempre tenha uma versão razoavelmente recente do "
    "yt-dlp (que precisa de atualizações frequentes para acompanhar mudanças "
    "nos sites)."
))
story.append(body(
    "<tt>settings_store.get_app_data_dir()</tt> resolve essa pasta a partir de "
    "<tt>sys.executable</tt> quando rodando como .exe empacotado (nunca de "
    "<tt>__file__</tt>, que apontaria para a pasta temporária que o PyInstaller "
    "usa em modo --onefile) — com um fallback automático para "
    "<tt>%APPDATA%/YT-DLP Studio</tt> caso a pasta ao lado do .exe não possa "
    "ser criada/escrita (ex.: instalado em Arquivos de Programas sem permissão "
    "de administrador)."
))
story.append(simple_table([
    ["Binário", "Fonte", "Tamanho aprox."],
    ["yt-dlp.exe", "github.com/yt-dlp/yt-dlp/releases/latest", "~15 MB"],
    ["ffmpeg.exe / ffprobe.exe", "gyan.dev/ffmpeg/builds (pacote essentials)", "~80 MB"],
], col_widths=[5 * cm, 8.5 * cm, 3 * cm]))
story.append(sp(4))
story.append(body(
    "O botão 'Atualizar yt-dlp' simplesmente re-executa "
    "<tt>install_ytdlp()</tt>, sobrescrevendo o binário local pela versão mais "
    "recente do GitHub. Se algum desses domínios mudar no futuro, basta "
    "atualizar as constantes <tt>YTDLP_RELEASE</tt> / <tt>FFMPEG_WIN_ESSENTIALS</tt> "
    "no topo de dependencies.py."
))

# ----------------------------------------------------- 8. FILA/THREADS --
story.append(h1("8. Fila de downloads e threading"))
story.append(body(
    "Regra de ouro do projeto: <b>nenhuma thread de fundo toca em um widget "
    "diretamente.</b> Toda comunicação passa por uma <tt>queue.Queue</tt> "
    "(<tt>QueueManager.events</tt>), e só a thread principal (a que roda o "
    "<tt>mainloop()</tt> do Tkinter) lê essa fila, via "
    "<tt>App._poll_queue_events</tt> reagendado a cada 150 ms com "
    "<tt>self.after()</tt>. Isso evita os travamentos/erros clássicos de "
    "Tkinter quando uma thread mexe na UI diretamente."
))
story.append(body(
    "<tt>QueueManager.start()</tt> sobe uma <i>thread</i> daemon "
    "(<tt>_run_loop</tt>) que percorre <tt>self.jobs</tt> em ordem, chamando "
    "<tt>_run_job()</tt> para cada um. Cada job roda o yt-dlp via "
    "<tt>subprocess.Popen</tt>, lê a saída linha a linha, extrai a "
    "porcentagem com uma regex (<tt>PROGRESS_RE</tt>) e emite eventos "
    "<tt>job_update</tt>/<tt>log</tt> a cada linha nova."
))
story.append(body(
    "'Cancelar Download Atual' seta um <tt>threading.Event</tt> "
    "(<tt>_stop_flag</tt>) e termina o processo do yt-dlp em andamento; isso "
    "cancela <b>só o item atual</b> — a flag é limpa logo em seguida, então os "
    "próximos itens da fila continuam normalmente."
))

# ----------------------------------------------------- 9. SETTINGS --
story.append(h1("9. Persistência de configurações"))
story.append(body(
    "Um único arquivo JSON guarda tudo: pastas padrão, todas as opções "
    "avançadas, e também os últimos valores escolhidos em cada dropdown das "
    "abas (chaves <tt>last_*</tt>), para que o programa reabra do jeito que o "
    "usuário deixou. <tt>SettingsStore.save()</tt> é chamado explicitamente "
    "após qualquer mudança relevante (não há salvamento automático "
    "'em tempo real' campo a campo)."
))

# ----------------------------------------------------- 10. I18N --
story.append(h1("10. Internacionalização (i18n)"))
story.append(body(
    "Toda string visível vive em <tt>i18n.STRINGS['pt']</tt> e "
    "<tt>['en']</tt>, com a mesma chave nos dois dicionários. Cada tela expõe "
    "um método <tt>retranslate()</tt> que reconfigura o texto de cada widget "
    "guardado em <tt>self._i18n_labels</tt> (um dicionário "
    "widget→chave) — chamado sempre que o idioma muda (botão PT/EN no topo)."
))
story.append(h3("Para adicionar um novo idioma"))
story.append(numbered([
    "Copie o bloco <tt>'en': {...}</tt> em i18n.py, traduza todos os valores, "
    "e dê a ele uma nova chave (ex.: <tt>'es'</tt>).",
    "No botão de idioma (main.py → <tt>toggle_language</tt>), troque a lógica "
    "binária 'pt'/'en' por uma lista de idiomas suportados.",
]))

# ----------------------------------------------------- 11. GUIA PRÁTICO --
story.append(h1("11. Guia prático: como adicionar/alterar coisas comuns"))

story.append(h2("Adicionar um novo formato de áudio"))
story.append(numbered([
    "Em <tt>tabs.py → AudioTab.AUDIO_FORMATS_TECH</tt>, adicione o nome que "
    "vai aparecer no menu (ex.: <tt>'WMA'</tt>).",
    "Em <tt>downloader.py → AUDIO_FORMAT_VALUE</tt>, mapeie esse nome para o "
    "valor que o yt-dlp espera em <tt>--audio-format</tt> (ex.: "
    "<tt>'WMA': 'wma'</tt>).",
]))

story.append(h2("Adicionar uma nova resolução de vídeo"))
story.append(numbered([
    "Em <tt>tabs.py → VideoTab.RESOLUTIONS_TECH</tt>, adicione o rótulo (ex.: "
    "<tt>'8640p (16K)'</tt>).",
    "Em <tt>downloader.py → RES_HEIGHT</tt>, mapeie para a altura em pixels "
    "(ex.: <tt>'8640p (16K)': 8640</tt>).",
]))

story.append(h2("Adicionar uma nova opção de Configurações"))
story.append(numbered([
    "Adicione o valor padrão em <tt>settings_store.py → DEFAULTS</tt>.",
    "Adicione as strings PT/EN do rótulo em <tt>i18n.py</tt>.",
    "Adicione o campo em <tt>settings_dialog.py</tt> (uma linha em "
    "<tt>self.entries[...]</tt> ou <tt>self.checks[...]</tt>, dentro da seção "
    "apropriada — os métodos <tt>_load_values</tt>/<tt>_save</tt> já "
    "percorrem esses dicionários automaticamente, não precisa mexer neles).",
    "Use a nova chave dentro de <tt>build_command()</tt> em downloader.py "
    "(<tt>s.get('sua_chave')</tt>).",
]))

story.append(h2("Alterar o texto da Ajuda dentro do app"))
story.append(body(
    "Edite a lista <tt>HELP_CONTENT['pt']</tt> / <tt>['en']</tt> em "
    "help_dialog.py — cada item é uma dupla (título da seção, texto)."
))

# ----------------------------------------------------- 12. BUILD --
story.append(h1("12. Build e empacotamento (gerando o .exe)"))
story.append(body(
    "O projeto é distribuído como código-fonte Python + <tt>build.bat</tt>, "
    "não como um .exe pré-compilado — isso porque o PyInstaller empacota para "
    "a plataforma onde é executado; gerar um .exe Windows exige rodar o build "
    "em uma máquina Windows (ou um ambiente de cross-compilation, que não é "
    "usado aqui por simplicidade e confiabilidade)."
))
story.append(body("O que <tt>build.bat</tt> faz, passo a passo:"))
story.append(numbered([
    "Cria um ambiente virtual Python (<tt>.venv</tt>).",
    "Instala as dependências de <tt>requirements.txt</tt> (customtkinter, "
    "pillow, pyinstaller).",
    "Roda o PyInstaller em modo <tt>--onefile --windowed</tt>, embutindo a "
    "pasta <tt>assets/</tt> (ícone e logo) dentro do executável.",
    "O resultado final fica em <tt>dist/YT-DLP Studio.exe</tt> — um único "
    "arquivo, sem necessidade de Python instalado na máquina de destino.",
]))
story.append(body(
    "Em tempo de execução, o app localiza seus próprios assets com "
    "<tt>resource_path()</tt> (main.py), que verifica <tt>sys._MEIPASS</tt> — "
    "a pasta temporária que o PyInstaller cria ao rodar um .exe "
    "<tt>--onefile</tt>. Fora do .exe (rodando via <tt>python "
    "src/main.py</tt> direto), ele cai de volta para a pasta "
    "<tt>assets/</tt> ao lado do projeto."
))

# ----------------------------------------------------- 13. TROUBLESHOOT --
story.append(h1("13. Solução de problemas para desenvolvedores"))
story.append(simple_table([
    ["Sintoma", "Causa provável / onde olhar"],
    ["App abre mas trava ao clicar em algo",
     "Alguma thread de fundo está chamando um método de widget diretamente — "
     "revise se o código novo está passando pelo padrão "
     "queue.Queue + self.after() em vez de mexer na UI direto."],
    ["Download falha sempre com o mesmo erro",
     "Rode o comando exato copiado do painel de Log direto no terminal — o "
     "log já imprime a linha completa '$ yt-dlp ...' antes de cada execução."],
    ["Opção nova na UI não tem efeito no download",
     "Confira se a chave usada em tabs.py/settings_dialog.py é exatamente a "
     "mesma lida em downloader.py → build_command() (erros de digitação em "
     "nomes de chave falham silenciosamente, sem exceção)."],
    ["PyInstaller gera .exe mas ele não abre",
     "Rode o build sem --windowed uma vez para ver o traceback no console; "
     "geralmente é um import faltando em --hidden-import ou um asset não "
     "incluso em --add-data."],
], col_widths=[5.5 * cm, 10.5 * cm]))

doc = SimpleDocTemplate(
    OUT, pagesize=A4,
    leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
    title="YT-DLP Studio - Documentação Técnica", author="YT-DLP Studio",
)


def _decorate(canvas, d):
    if d.page > 1:
        page_decoration(canvas, d, "Documentação Técnica — YT-DLP Studio")


doc.build(story, onFirstPage=lambda c, d: None, onLaterPages=_decorate)
print("Gerado:", OUT)
