"""Janela de Ajuda — guia rápido de uso, acessível pelo botão '?' da barra superior."""
import customtkinter as ctk

HELP_CONTENT = {
    "pt": [
        ("Primeiros passos",
         "Na primeira execução, o programa baixa sozinho o yt-dlp e o FFmpeg "
         "(acompanhe o progresso na aba 'Fila e Log'). Isso só acontece uma vez; "
         "os arquivos ficam salvos numa pasta 'data' criada bem ao lado do "
         "programa (não em nenhuma pasta escondida) — use o botão 📁 ao lado de "
         "'Atualizar yt-dlp' para abri-la a qualquer momento."),
        ("Aba Áudio",
         "Cole um link para baixar como música. Assim que você para de digitar, "
         "o programa busca sozinho o título, artista e duração em segundo plano "
         "e preenche esses campos e o recorte de trecho automaticamente — sem "
         "travar nada, você pode clicar em Download a qualquer momento, mesmo "
         "antes dessa busca terminar. Título e Artista continuam editáveis e "
         "sobrescrevem os metadados (ID3) do arquivo final, mas o "
         "<b>nome do arquivo usa só o título</b> — nunca vem com o artista na "
         "frente, mesmo que o campo Artista esteja preenchido. Em playlists, Título e Artista são ignorados: cada faixa usa os próprios dados."),
        ("Aba Vídeo",
         "Mesma ideia da aba Áudio (inclusive a busca automática de duração), "
         "mas para vídeo. O nome do arquivo sai como 'Título - Canal', para "
         "diferenciar reuploads do mesmo vídeo em canais diferentes. "
         "Resolução, FPS e os codecs de vídeo/áudio definem o "
         "formato procurado; se a combinação exata não existir para aquele "
         "link, o programa cai automaticamente para a melhor opção disponível. "
         "'Contêiner' controla se o arquivo final sai em .mp4 ou .mkv."),
        ("Busca automática e links em lote",
         "A busca de título/artista/duração só acontece quando há exatamente "
         "um link na caixa. Colando vários links de uma vez (um por linha) "
         "para baixar em lote, essa busca não roda — do contrário os dados de "
         "uma faixa acabariam sendo aplicados nas outras."),
        ("Recorte de trecho",
         "A barra de intervalo permite baixar só um pedaço do vídeo/música. "
         "Arraste as bolinhas ou digite o tempo direto nos campos. Assim que a "
         "duração real é encontrada, a barra já reflete o tamanho certo da "
         "mídia; deixe os dois cabos nas extremidades para baixar por inteiro."),
        ("Download vs. Fila",
         "O botão vermelho 'Download' começa a baixar imediatamente (entrando "
         "na fila se já houver algo em andamento). O botão cinza ao lado só "
         "adiciona à fila sem iniciar — útil para deixar vários links prontos "
         "e apertar 'Iniciar Fila' depois, na aba Fila e Log."),
        ("Fila e Log",
         "Mostra o status do yt-dlp/FFmpeg, todos os itens da fila com progresso "
         "individual (durante playlists, mostra 'Título - Artista (X de Y)' "
         "com a faixa sendo baixada no momento), e um log detalhado de tudo o "
         "que está acontecendo (pode copiar com o botão 'Copiar' para pedir "
         "ajuda ou relatar um problema)."),
        ("Guardar thumbnail",
         "Salva a capa como um arquivo .jpg separado, ao lado do arquivo "
         "baixado. Em música, a capa (salva em disco e/ou incorporada ao "
         "arquivo) sempre sai recortada 1:1 (quadrada, padrão de capa de "
         "álbum) — automaticamente, sem precisar ligar nada em "
         "Configurações; em vídeo, sai no tamanho/proporção normal da "
         "thumbnail original, sem recorte."),
        ("Playlists e capa da playlist (Configurações → Arquivos extras)",
         "Ao baixar uma playlist/álbum inteiro, o programa cria automaticamente "
         "uma subpasta com o nome da playlist e salva a melhor capa encontrada "
         "como 'playlistcover.jpg' dentro dela (opção 'Salvar capa do "
         "álbum/playlist na pasta', ligada por padrão)."),
        ("Playlist: capa e verificação",
         "Com 'Guardar thumbnail' marcado numa playlist, só a capa DA PLAYLIST é "
         "salva (playlistcover.jpg), não uma por faixa. O botão 'Verificar "
         "disponibilidade da playlist' testa todas as faixas sem baixar nada e "
         "lista no Log as indisponíveis, com a posição e as músicas vizinhas."),
        ("Aba Converter",
         "Converte ou comprime qualquer arquivo do computador usando o FFmpeg do "
         "app. Escolha o arquivo, o formato (MP3, M4A, Opus, FLAC, WAV, MP4, MKV, "
         "WEBM), a qualidade (Baixa = arquivo menor) e, pra vídeo, a resolução "
         "máxima. O resultado sai na mesma pasta, como 'nome_convertido'. "
         "Compressor: preencha 'Tamanho alvo' (ex.: 25 MB ou 1,5 GB) e o arquivo "
         "sai com esse tamanho aproximado (fica um pouco abaixo), ignorando a "
         "qualidade. Não vale pra FLAC/WAV (sem perdas)."),
        ("Pastas e nomes de arquivo",
         "As pastas padrão de música e vídeo ficam em Configurações → Pastas. O botão "
         "'Alterar pasta' em cada aba é um atalho rápido para a mesma configuração."),
        ("Problemas comuns",
         "Se o download falhar, veja a mensagem em vermelho no Log — geralmente é o "
         "link indisponível/privado, ou uma dependência desatualizada (use 'Atualizar "
         "yt-dlp' na aba Fila e Log). Sites de vídeo mudam com frequência; manter o "
         "yt-dlp atualizado resolve a maioria dos erros."),
    ],
    "en": [
        ("Getting started",
         "On first run, the app downloads yt-dlp and FFmpeg on its own (watch the "
         "progress in the 'Queue & Log' tab). This only happens once; the files "
         "are saved in a 'data' folder created right next to the program (not "
         "hidden away anywhere) — use the 📁 button next to 'Update yt-dlp' to "
         "open it anytime."),
        ("Audio tab",
         "Paste a link to download as music. As soon as you stop typing, the "
         "app looks up the title, artist and duration in the background and "
         "fills in those fields and the trim range automatically — without "
         "blocking anything, you can click Download at any moment, even "
         "before that lookup finishes. Title and Artist stay editable and "
         "override the final file's (ID3) metadata, but the "
         "<b>filename only ever uses the title</b> — never prefixed with the "
         "artist, even when the Artist field is filled in. For playlists, Title and Artist are ignored: each track uses its own data."),
        ("Video tab",
         "Same idea as the Audio tab (including the automatic duration "
         "lookup), but for video. The filename comes out as 'Title - "
         "Channel', to tell apart reuploads of the same video from "
         "different channels. Resolution, FPS and the video/audio codecs "
         "define the format being searched for; if that exact combination "
         "doesn't exist for a given link, the app automatically falls back to "
         "the best available option. 'Container' controls whether the final "
         "file comes out as .mp4 or .mkv."),
        ("Automatic lookup and batch links",
         "The title/artist/duration lookup only runs when there's exactly "
         "one link in the box. When pasting several links at once (one per "
         "line) for a batch download, that lookup is skipped — otherwise one "
         "track's data would end up applied to all the others."),
        ("Trimming a section",
         "The range bar lets you download just part of the video/track. Drag "
         "the handles or type the time directly into the fields. Once the "
         "real duration is found, the bar already reflects the media's actual "
         "length; leave both handles at the extremes to download the whole "
         "thing."),
        ("Download vs. Queue",
         "The red 'Download' button starts downloading right away (joining "
         "the queue if something is already running). The gray button next "
         "to it only adds to the queue without starting — handy for lining "
         "up several links and pressing 'Start Queue' later, on the Queue & "
         "Log tab."),
        ("Queue & Log",
         "Shows yt-dlp/FFmpeg status, every queued item with its own progress "
         "(during playlists, shows 'Title - Artist (X of Y)' with the track "
         "currently downloading), and a detailed log of everything happening "
         "(copy it with the 'Copy' button to ask for help or report an "
         "issue)."),
        ("Save thumbnail",
         "Saves the cover as a separate .jpg file, next to the downloaded "
         "file. For music, the cover (saved to disk and/or embedded in the "
         "file) always comes out cropped 1:1 (square, the standard "
         "album-cover shape) — automatically, nothing to turn on in "
         "Settings; for video, it comes out at the thumbnail's normal "
         "size/proportions, uncropped."),
        ("Playlists and playlist cover (Settings → Extra files)",
         "When downloading a whole playlist/album, the app automatically "
         "creates a subfolder named after the playlist and saves the best "
         "cover it found as 'playlistcover.jpg' inside it ('Save "
         "album/playlist cover in folder' option, on by default)."),
        ("Playlist: cover and check",
         "With 'Save thumbnail' checked on a playlist, only the PLAYLIST cover "
         "is saved (playlistcover.jpg), not one per track. The 'Check playlist "
         "availability' button tests every track without downloading and lists "
         "unavailable ones in the Log, with position and neighbouring tracks."),
        ("Convert tab",
         "Converts or compresses any file on your computer using the app's "
         "FFmpeg. Pick the file, format (MP3, M4A, Opus, FLAC, WAV, MP4, MKV, "
         "WEBM), quality (Low = smaller file) and, for video, the max "
         "resolution. The result lands in the same folder as 'name_convertido'. "
         "Compressor: fill in 'Target size' (e.g. 25 MB or 1.5 GB) and the file "
         "comes out at roughly that size (slightly under), ignoring quality. Not "
         "available for FLAC/WAV (lossless)."),
        ("Folders and filenames",
         "Default music/video folders live in Settings → Folders. The 'Change "
         "folder' button on each tab is a quick shortcut to the same setting."),
        ("Common issues",
         "If a download fails, check the red message in the Log — usually it's an "
         "unavailable/private link, or an outdated dependency (use 'Update yt-dlp' on "
         "the Queue & Log tab). Video sites change often; keeping yt-dlp updated "
         "fixes most errors."),
    ],
}


class HelpDialog(ctk.CTkToplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.tr = app.tr
        self.title(self.tr.t("help_title"))
        self.geometry("560x680")
        self.minsize(440, 400)
        self.transient(app)

        header = ctk.CTkLabel(self, text=self.tr.t("help_title"),
                               font=ctk.CTkFont(size=18, weight="bold"))
        header.pack(anchor="w", padx=20, pady=(18, 4))

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        sections = HELP_CONTENT.get(self.tr.lang, HELP_CONTENT["pt"])
        for heading, text in sections:
            h = ctk.CTkLabel(body, text=heading, anchor="w",
                              font=ctk.CTkFont(size=14, weight="bold"))
            h.pack(fill="x", pady=(14, 2))
            p = ctk.CTkLabel(body, text=text, anchor="w", justify="left",
                              wraplength=480, text_color=("gray20", "gray85"))
            p.pack(fill="x")

        close_btn = ctk.CTkButton(self, text=self.tr.t("close"), width=100, command=self.destroy)
        close_btn.pack(pady=(0, 16))
        self.grab_set()
