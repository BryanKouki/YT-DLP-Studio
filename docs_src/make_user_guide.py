import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import date

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Image, Spacer, PageBreak, KeepTogether, Paragraph
from reportlab.lib import colors

from pdf_common import (
    STYLES, h1, h2, h3, body, bullets, numbered, code, hr, sp,
    simple_table, page_decoration, caption,
)

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "Manual_do_Usuario_YT-DLP_Studio.pdf")

story = []

# ---------------------------------------------------------------- CAPA --
story.append(Spacer(1, 4 * cm))
story.append(Image(os.path.join(ASSETS, "icon.png"), width=3 * cm, height=3 * cm, hAlign="CENTER"))
story.append(Spacer(1, 0.8 * cm))
story.append(Paragraph("YT-DLP Studio", STYLES["cover_title"]))
story.append(Paragraph("Manual do Usuário", STYLES["cover_subtitle"]))
story.append(Spacer(1, 0.6 * cm))
story.append(Paragraph(
    f"Baixador de áudio e vídeo com interface gráfica, construído sobre o yt-dlp<br/>"
    f"Versão do documento — {date.today().strftime('%d/%m/%Y')}", STYLES["cover_meta"]))
story.append(PageBreak())

# ------------------------------------------------------------ SUMÁRIO --
story.append(h1("Sumário"))
toc_items = [
    "1. O que é o YT-DLP Studio",
    "2. Primeira execução (download automático de dependências)",
    "3. Visão geral da janela principal",
    "4. Aba Áudio",
    "5. Aba Vídeo",
    "6. Recortando um trecho do vídeo",
    "7. Download imediato x Fila de downloads",
    "8. Abas Converter e Fila e Log",
    "9. Configurações — Pastas e Rede",
    "10. Configurações — Filtros",
    "11. Configurações — Comportamento do download",
    "12. Configurações — Arquivos extras e capa do álbum",
    "13. Idioma e tema",
    "14. Dicas e solução de problemas",
    "15. Avisos legais",
]
for it in toc_items:
    story.append(body(it))
story.append(PageBreak())

# --------------------------------------------------------- 1. O QUE É --
story.append(h1("1. O que é o YT-DLP Studio"))
story.append(body(
    "O YT-DLP Studio é um aplicativo de mesa (desktop) para baixar áudio e vídeo de "
    "sites como YouTube e centenas de outros suportados pelo motor <b>yt-dlp</b>. Ele "
    "oferece uma interface gráfica simples para as funções mais usadas do yt-dlp — "
    "escolher formato, qualidade, resolução, recortar um trecho, baixar playlists "
    "inteiras, organizar uma fila de downloads — sem precisar digitar comandos."
))
story.append(body(
    "O programa gerencia sozinho suas próprias dependências: na primeira vez que é "
    "aberto, ele baixa o <b>yt-dlp</b> e o <b>FFmpeg</b> automaticamente, guardando-os "
    "numa pasta própria. Você não precisa instalar nada manualmente."
))
story.append(body(
    "<b>Importante:</b> o YT-DLP Studio é uma interface para o yt-dlp — ele não hospeda, "
    "armazena nem distribui nenhum conteúdo. Use-o apenas para baixar vídeos aos quais "
    "você tem direito de acesso, respeitando os termos de uso das plataformas e os "
    "direitos autorais dos criadores."
))

# ------------------------------------------------------- 2. PRIMEIRA EXECUÇÃO --
story.append(h1("2. Primeira execução"))
story.append(body(
    "Ao abrir o programa pela primeira vez, vá até a aba <b>Fila e Log</b> para "
    "acompanhar a barra de status no topo:"
))
story.append(bullets([
    "<b>yt-dlp:</b> um ponto verde com 'OK' indica que já está pronto. Se estiver "
    "ausente, o programa baixa automaticamente (arquivo pequeno, poucos segundos).",
    "<b>FFmpeg:</b> necessário para converter áudio, mesclar vídeo+áudio e gerar "
    "capas. Na primeira vez, é baixado um pacote de ~80 MB — pode levar alguns "
    "minutos dependendo da sua internet.",
]))
story.append(body(
    "Depois desse primeiro download, os arquivos ficam salvos permanentemente e o "
    "programa abre instantaneamente nas próximas vezes. Se precisar reinstalar (por "
    "exemplo, se os arquivos foram apagados ou corrompidos), use o botão "
    "<b>'Verificar / Reinstalar Dependências'</b> na aba Fila e Log."
))
story.append(body(
    "Esses arquivos ficam numa pasta chamada <b>'data'</b>, criada bem ao lado do "
    "próprio programa (não em nenhuma pasta escondida do Windows) — clique no "
    "ícone de pasta ao lado de 'Atualizar yt-dlp' para abrir essa pasta a "
    "qualquer momento e conferir o que está lá."
))

# ------------------------------------------------------- 3. VISÃO GERAL --
story.append(h1("3. Visão geral da janela principal"))
story.append(body("A janela principal é dividida em quatro abas, sempre visíveis no topo:"))
story.append(bullets([
    "<b>ÁUDIO</b> — baixar música/podcasts, convertendo para MP3, FLAC, WAV, etc.",
    "<b>VÍDEO</b> — baixar vídeo completo, escolhendo resolução e formato.",
    "<b>CONVERTER</b> — converter ou comprimir arquivos que já estão no computador.",
    "<b>Fila e Log</b> — acompanhar downloads em andamento, gerenciar a fila e ver o "
    "log detalhado de tudo o que o programa está fazendo.",
]))
story.append(body(
    "No canto superior direito ficam quatro botões sempre acessíveis: a "
    "engrenagem abre as <b>Configurações</b>, o ponto de interrogação (?) abre "
    "esta mesma ajuda dentro do programa, o ícone de lua/sol alterna entre tema "
    "escuro e claro, e o botão 'PT'/'EN' alterna o idioma da interface."
))

# ------------------------------------------------------- 4. ABA ÁUDIO --
story.append(h1("4. Aba Áudio"))
story.append(body("Use esta aba para baixar apenas o áudio de um vídeo (ideal para música)."))
story.append(h3("Playlists e álbuns"))
story.append(body(
    "Se o link colado for uma playlist ou álbum, o programa detecta isso "
    "automaticamente e cria uma subpasta com o nome da playlist dentro da "
    "pasta de música — cada faixa é salva lá dentro, e não soltas na pasta "
    "principal. A capa é salva como <b>playlistcover.jpg</b> nessa mesma "
    "subpasta assim que o download termina."
))
story.append(h3("Campo de link e busca automática"))
story.append(body(
    "Cole o link do vídeo, playlist ou álbum na caixa de texto no topo. Para baixar "
    "vários links de uma vez, cole um por linha — o programa cria um item de "
    "download separado para cada um."
))
story.append(body(
    "Quando há <b>só um</b> link colado, assim que você para de digitar o "
    "programa busca sozinho, em segundo plano, o título, o artista e a "
    "duração — preenchendo os campos abaixo e ajustando a barra de recorte "
    "automaticamente. Isso nunca trava nada: dá pra clicar em Download a "
    "qualquer momento, mesmo antes dessa busca terminar. Com vários links "
    "colados de uma vez, essa busca automática não roda (para não aplicar os "
    "dados de uma faixa nas outras por engano)."
))
story.append(h3("Formato e Qualidade"))
story.append(body(
    "O menu <b>Formato</b> define o tipo de arquivo de áudio final: Melhor "
    "disponível (não reconverte, mais rápido), MP3, M4A, AAC, Opus, Vorbis, FLAC "
    "(sem perdas), ALAC (sem perdas, padrão Apple) ou WAV (sem compressão). O menu "
    "<b>Qualidade</b> define o bitrate de conversão, de 32 a 320 kbps — 320 kbps "
    "(o maior) vem selecionado por padrão."
))
story.append(h3("Título e Artista"))
story.append(body(
    "Preenchidos automaticamente pela busca acima quando há só um link (e "
    "continuam editáveis). O que estiver escrito neles na hora do download "
    "substitui o título/artista originais nos metadados (ID3) do arquivo "
    "final — útil quando o título do YouTube não é exatamente igual ao "
    "nome da faixa. <b>O nome do arquivo, porém, usa sempre só o título</b> "
    "— o artista nunca aparece na frente do nome do arquivo, mesmo com o "
    "campo preenchido; ele só afeta os metadados internos do MP3/FLAC/etc. "
    "Em <b>playlists</b>, Título e Artista são ignorados — cada faixa usa "
    "o próprio título/artista (senão todas cairiam no mesmo arquivo)."
))
story.append(h3("Guardar thumbnail"))
story.append(body(
    "Quando marcado, salva a capa como um arquivo <b>.jpg</b> separado na pasta de "
    "destino. Em música, essa capa sempre sai <b>recortada 1:1</b> (quadrada, o "
    "padrão de capa de álbum); em vídeo, sai no tamanho/proporção normal da "
    "thumbnail original, sem nenhum recorte. Numa <b>playlist</b>, só a capa da "
    "própria playlist é guardada (playlistcover.jpg) — nada de uma capa por faixa."
))
story.append(h3("Verificar disponibilidade da playlist"))
story.append(body(
    "O botão ao lado de 'Guardar thumbnail' testa todas as faixas do link colado "
    "sem baixar nada e escreve no Log (aba Fila e Log) cada faixa indisponível "
    "com a posição e as músicas vizinhas — ex.: <i>12 - Nome — depois de \"A\" e "
    "antes de \"B\"</i> — e o motivo. Playlists grandes levam alguns minutos."
))

# ------------------------------------------------------- 5. ABA VÍDEO --
story.append(h1("5. Aba Vídeo"))
story.append(body(
    "Funciona de forma parecida com a aba Áudio, mas baixa o vídeo completo "
    "— inclusive a busca automática de duração quando há só um link colado "
    "(sem título/artista aqui, já que vídeo não tem esses campos). O nome "
    "do arquivo final sai como <b>'Título - Canal'</b>, para diferenciar "
    "reuploads do mesmo vídeo publicados em canais diferentes."
))
story.append(bullets([
    "<b>Resolução:</b> de 144p até 4320p (8K), ou 'Melhor disponível'.",
    "<b>FPS:</b> limita os quadros por segundo buscados (60/30/24) ou 'Melhor disponível'.",
    "<b>Codec de vídeo/áudio:</b> preferência de codec (H.264, H.265, VP9, AV1, VP8 "
    "para vídeo; AAC, Opus, MP3, FLAC para áudio). Se a combinação exata não "
    "existir para aquele link, o programa cai automaticamente para a melhor opção "
    "disponível, então o download nunca falha só por causa dessa preferência.",
    "<b>Contêiner:</b> 'Automático' deixa o yt-dlp escolher entre MP4/MKV conforme "
    "a compatibilidade dos codecs; 'Forçar MP4'/'Forçar MKV' converte o arquivo "
    "final para esse formato específico, se necessário.",
    "<b>Legendas:</b> quando marcado, baixa e incorpora legendas (idioma e formato "
    "configuráveis em Configurações → Arquivos extras).",
]))

# ------------------------------------------------------- 6. RECORTE --
story.append(h1("6. Recortando um trecho do vídeo"))
story.append(body(
    "Logo abaixo do campo de link, uma barra com dois cabos permite selecionar um "
    "intervalo de tempo. Arraste os círculos para a posição desejada, ou digite o "
    "tempo diretamente nos campos '00:00:00' de cada lado (formato HH:MM:SS)."
))
story.append(body(
    "Se os dois cabos ficarem nas extremidades (posição padrão), o vídeo/música é "
    "baixado por inteiro — o recorte só é aplicado quando você efetivamente move os "
    "cabos ou edita os campos de tempo."
))

# --------------------------------------------- 7. DOWNLOAD x FILA --
story.append(h1("7. Download imediato × Fila de downloads"))
story.append(simple_table([
    ["Botão", "O que faz"],
    ["Download (vermelho, grande)", "Começa a baixar imediatamente. Se já houver algo "
     "em andamento, o novo item entra na fila e começa assim que chegar sua vez."],
    ["+≡ (cinza, ao lado)", "Apenas adiciona o link à fila, sem iniciar nada. Use "
     "para preparar vários downloads e disparar todos de uma vez depois."],
], col_widths=[5.5 * cm, 10.5 * cm]))
story.append(sp(4))
story.append(body(
    "Para iniciar itens que só foram adicionados à fila (sem apertar Download), vá "
    "até a aba <b>Fila e Log</b> e clique em <b>'Iniciar Fila'</b>."
))

# ------------------------------------------------------- 8. FILA E LOG --
story.append(h1("8. Abas Converter e Fila e Log"))
story.append(h3("Converter"))
story.append(body(
    "Converte ou comprime arquivos que já estão no computador, usando o mesmo "
    "FFmpeg que o programa baixa sozinho. Escolha o arquivo, o <b>formato</b> "
    "(MP3, M4A, Opus, FLAC, WAV, MP4 H.264, MKV H.265, WEBM VP9), a <b>qualidade</b> "
    "(Alta = arquivo maior, Baixa = arquivo menor) e, pra vídeo, a <b>resolução</b> "
    "máxima (nunca aumenta a original). O resultado é salvo na mesma pasta do "
    "original, como <i>nome_convertido.ext</i>, com barra de progresso e botão "
    "de cancelar (o arquivo incompleto é apagado)."
))
story.append(body(
    "<b>Compressor por tamanho:</b> preencha <b>Tamanho alvo</b> com o número e "
    "escolha <b>MB</b> ou <b>GB</b> ao lado (ex.: <i>25 MB</i> pra caber num anexo, "
    "<i>1,5 GB</i>). O programa lê a duração do arquivo e calcula o bitrate pra "
    "chegar nesse tamanho — o resultado fica um pouco abaixo do alvo. Com o campo "
    "preenchido, a opção Qualidade é ignorada; deixe vazio pra usar a qualidade "
    "normal. Não se aplica a FLAC/WAV (sem perdas), e alvos pequenos demais pra "
    "duração do vídeo são recusados com aviso no Log."
))
story.append(h3("Fila e Log"))
story.append(body("Esta aba centraliza o acompanhamento de tudo:"))
story.append(bullets([
    "<b>Barra de status</b> — mostra se yt-dlp/FFmpeg estão prontos, com botões "
    "para verificar/reinstalar dependências, atualizar o yt-dlp para a versão "
    "mais recente (recomendado quando downloads começarem a falhar sem motivo "
    "aparente — sites mudam com frequência e isso costuma resolver), e um "
    "ícone de pasta para abrir onde esses arquivos ficam salvos.",
    "<b>Lista da fila</b> — cada item mostra o título e uma barra de progresso "
    "individual. Durante o download, o texto muda para 'Título - Artista (X de "
    "Y)' quando o link é uma playlist, mostrando exatamente qual faixa está "
    "sendo baixada no momento. O item em andamento tem um botão de cancelar "
    "embutido.",
    "<b>Botões de controle</b> — Iniciar Fila, Cancelar Download Atual, Limpar "
    "Concluídos (remove só os que já terminaram) e Limpar Tudo (esvazia a fila "
    "inteira, exceto o item em andamento).",
    "<b>Log</b> — texto detalhado de cada etapa do yt-dlp em tempo real. Use o "
    "botão 'Copiar' para colar em uma mensagem caso precise pedir ajuda sobre um "
    "erro específico.",
]))

# --------------------------------------------- 9-12 CONFIGURAÇÕES --
story.append(h1("9. Configurações — Pastas e Rede"))
story.append(h3("Pastas"))
story.append(body(
    "Define onde os arquivos de música e de vídeo são salvos por padrão. O botão "
    "'Alterar pasta' em cada aba (Áudio/Vídeo) é um atalho rápido para o mesmo "
    "ajuste."
))
story.append(h3("Rede"))
story.append(bullets([
    "<b>Limite de velocidade</b> — ex.: 2M (2 MB/s) ou 500K (500 KB/s), para não "
    "saturar sua internet durante downloads grandes.",
    "<b>Proxy</b> — endereço de um servidor proxy, se você usa um.",
    "<b>Itens da playlist</b> — para baixar só parte de uma playlist, ex.: "
    "'1-5,8,10-13' baixa as faixas 1 a 5, a 8, e de 10 a 13.",
    "<b>Modelo de nome de arquivo (avançado)</b> — para usuários avançados que "
    "conhecem a sintaxe de templates do yt-dlp (ex.: %(artist)s - %(title)s.%(ext)s). "
    "Deixe em branco para usar o padrão do programa.",
]))

story.append(h1("10. Configurações — Filtros"))
story.append(body(
    "Permitem pular vídeos fora de determinados critérios antes mesmo de começar o "
    "download — útil em playlists e canais grandes."
))
story.append(bullets([
    "<b>Enviado após / antes de</b> — filtra por data de publicação (formato AAAAMMDD).",
    "<b>Tamanho mínimo/máximo do arquivo</b> — ex.: 10M, 2G.",
    "<b>Duração mínima/máxima (s)</b> — em segundos; útil para pular vídeos curtos "
    "(shorts) ou lives longas ao baixar um canal inteiro.",
]))

story.append(h1("11. Configurações — Comportamento do download"))
story.append(bullets([
    "<b>Restringir nomes de arquivo</b> — usa só caracteres ASCII simples nos "
    "nomes, evitando qualquer problema de compatibilidade no Windows.",
    "<b>Somente este vídeo</b> — se o link pertence a uma playlist, baixa apenas "
    "aquele vídeo específico, ignorando o restante.",
    "<b>Pular já baixados</b> — mantém um arquivo de histórico para nunca baixar "
    "o mesmo vídeo duas vezes, mesmo em execuções diferentes.",
    "<b>Contornar restrições geográficas / Ignorar erros de certificado SSL / "
    "Forçar IPv4</b> — opções de rede para contornar bloqueios específicos.",
    "<b>Salvar comentários do vídeo</b> — grava os comentários num arquivo à parte.",
    "<b>Lives: baixar desde o início</b> — para transmissões ao vivo já em "
    "andamento, começa a gravação do início disponível, não do momento atual.",
    "<b>Forçar nomes seguros do Windows</b> — garante compatibilidade total de "
    "nomes de arquivo no Windows, mantendo acentos e caracteres unicode.",
    "<b>Não sobrescrever arquivos existentes</b> — pula o download se o arquivo "
    "de destino já existir.",
    "<b>Fragmentos paralelos / Tentativas em caso de erro / Tentativas por "
    "fragmento / Pausa entre downloads</b> — ajustes finos de desempenho e "
    "confiabilidade da conexão; os padrões do yt-dlp já funcionam bem na maioria "
    "dos casos.",
]))

story.append(h1("12. Configurações — Arquivos extras e capa do álbum"))
story.append(bullets([
    "<b>Incorporar metadados e capa</b> — grava título, artista, ano e a capa "
    "diretamente dentro do arquivo final (recomendado, ligado por padrão). Em "
    "música, essa capa já sai automaticamente recortada 1:1 (quadrada, padrão "
    "de capa de álbum) — não existe opção pra desligar esse recorte, já que "
    "não há motivo pra querer uma capa de música não-quadrada.",
    "<b>Incorporar capítulos / Dividir em arquivos por capítulo</b> — para vídeos "
    "com capítulos marcados (comum em podcasts e álbuns completos no YouTube).",
    "<b>Salvar arquivo de descrição / de informações (.info.json)</b> — gera "
    "arquivos de texto extras com a descrição e os metadados completos do vídeo.",
]))
story.append(h3("Salvar capa do álbum/playlist na pasta"))
story.append(body(
    "Ligada por padrão. Ao terminar de baixar uma playlist inteira (que já "
    "ganhou sua própria subpasta, como explicado na seção 4), o programa "
    "escolhe a melhor capa encontrada e salva uma cópia como "
    "<b>playlistcover.jpg</b> dentro dessa subpasta — assim fica claro, só de "
    "olhar a pasta, qual é a capa da playlist inteira."
))

# ------------------------------------------------------- 13. IDIOMA/TEMA --
story.append(h1("13. Idioma e tema"))
story.append(body(
    "O botão 'PT'/'EN' no canto superior direito alterna toda a interface entre "
    "português e inglês instantaneamente. O ícone de lua/sol alterna entre tema "
    "escuro e claro. Ambas as preferências ficam salvas e são lembradas na próxima "
    "vez que o programa for aberto."
))
story.append(body(
    "As cores da interface seguem a identidade visual do próprio yt-dlp: preto, "
    "branco e vermelho puro (#FF0000) para os botões e destaques principais, nos "
    "dois temas."
))

# ------------------------------------------------------- 14. DICAS --
story.append(h1("14. Dicas e solução de problemas"))
story.append(numbered([
    "<b>Download falhou com erro estranho:</b> na aba Fila e Log, clique em "
    "'Atualizar yt-dlp'. Sites como o YouTube mudam com frequência, e isso "
    "resolve a grande maioria dos erros.",
    "<b>FFmpeg não termina de baixar:</b> verifique sua conexão com a internet e "
    "tente novamente em 'Verificar / Reinstalar Dependências'. O pacote tem cerca "
    "de 80 MB.",
    "<b>Vídeo indisponível/privado:</b> o link pode ter sido removido ou tornado "
    "privado pelo autor — isso não é um problema do programa.",
    "<b>Quero ver exatamente o que o yt-dlp está fazendo:</b> acompanhe o painel "
    "de Log em tempo real, ou copie o conteúdo com o botão 'Copiar'.",
    "<b>Nomes de arquivo com caracteres estranhos:</b> ative 'Forçar nomes "
    "seguros do Windows' ou 'Restringir nomes de arquivo' em Configurações.",
]))

# ------------------------------------------------------- 15. LEGAL --
story.append(h1("15. Avisos legais"))
story.append(body(
    "O YT-DLP Studio é uma interface gráfica de uso pessoal construída sobre o "
    "projeto de código aberto <b>yt-dlp</b> (licenciado sob a Unlicense, domínio "
    "público). O programa não contorna nenhum sistema de proteção de conteúdo "
    "pago (DRM) e não hospeda, redistribui nem armazena arquivos de terceiros."
))
story.append(body(
    "É responsabilidade de quem usa o programa respeitar os Termos de Serviço das "
    "plataformas de onde o conteúdo é baixado e os direitos autorais dos "
    "criadores. Use para backups pessoais, conteúdo próprio, ou material "
    "expressamente licenciado para download."
))

doc = SimpleDocTemplate(
    OUT, pagesize=A4,
    leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
    title="YT-DLP Studio - Manual do Usuário", author="YT-DLP Studio",
)


def _decorate(canvas, d):
    if d.page > 1:
        page_decoration(canvas, d, "Manual do Usuário — YT-DLP Studio")


doc.build(story, onFirstPage=lambda c, d: None, onLaterPages=_decorate)
print("Gerado:", OUT)
