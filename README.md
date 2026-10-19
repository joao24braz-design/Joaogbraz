# JG Reels AI 1.4

Estúdio pessoal: https://jg-reels-ai.onrender.com (protegido por senha). Render gratuito, sem APIs pagas. O serviço pode adormecer e a edição usa CPU limitada. Nenhuma atualização de plano contratada.

## Arquitetura

FastAPI serve HTML responsivo e recebe uploads MP4/MOV em fluxo. Um único trabalhador executa FFmpeg e Whisper base local CPU int8 em subprocessos canceláveis. Upload até 300 MB, até 10 minutos, entrada até 4K, dois trabalhos na fila e dez projetos temporários. Sem banco de dados. Um processo Uvicorn.

Detecção de silêncios abaixo de -35 dB: modo Natural a partir de 600 ms com margens de 140/180 ms; modo Dinâmico a partir de 300 ms com margens de 80/100 ms. A sequência da fala é mantida; o modo dinâmico pode exigir conferência de palavras sussurradas ou ruído variável. Cortes sequenciais limitam memória. Vídeo intermediário usa x264 ultrafast CRF18; ruído leve e volume são tratados uma vez após concatenar. A transcrição ocorre no vídeo cortado e na velocidade original. Legendas são agrupadas a partir dos tempos das palavras; podem ser corrigidas antes ou depois da primeira exportação.

## Opções de edição

- Modo automático: velocidade 1×, legenda Premium média off-white/cobre e zoom automático por palavras e frases de destaque. No modo personalizado, o zoom pode ser desligado.
- Modo personalizado: 1× até 2× em passos de 0,1, preservando o tom da voz com atempo; tamanho pequeno/médio/grande; modelos Premium, Limpo ou Caixa; cores de texto e destaque.
- Reels e Stories 9:16 com margens de legenda diferentes; feed 4:5 ou quadrado 1:1. Largura 2160 (4K), 1080 ou 720 pixels; imagem inteira com margens ou preenchimento com corte central.
- Zoom central suave de até 10%. A opção de direcionar ao rosto usa OpenCV local em subprocesso, até três quadros reduzidos por momento, para localizar o maior rosto frontal e aproximar até 18%. Trechos sem detecção ficam sem zoom e geram aviso. A detecção não identifica pessoas nem acompanha o rosto continuamente. Automático seleciona até quatro momentos por palavras-chave, números, valores, comparações e pontuação; se necessário, distribui aproximações na fala. É uma heurística editorial, sem compreensão semântica completa ou rastreamento contínuo. Personalizado aceita até oito intervalos em segundos do vídeo cortado antes de acelerar. Vídeos curtos demais ainda podem ficar sem zoom; ao direcionar ao rosto, trechos sem detecção ficam sem aproximação. As sugestões de momentos ficam disponíveis na edição.
- Alterações de estilo, zoom e velocidade podem ser reexportadas sem repetir cortes/transcrição. Formato, resolução e enquadramento são definidos no envio e exigem novo upload para mudar.

O relógio canônico das legendas permanece no vídeo cortado, antes de acelerar. Na exportação, o mesmo fator divide timestamps do vídeo e das legendas e acelera o áudio. A prévia de revisão usa a velocidade original. ASS aplica tamanho e cor no vídeo real; a amostra HTML é apenas amostra de estilo. Saída H.264, AAC, yuv420p e MP4 faststart. Zoom e resoluções maiores aumentam o tempo de exportação. Reels/Stories 4K usam 2160×3840; feed usa 2160×2700 e quadrado 2160×2160. Aumentar a resolução não cria detalhes ausentes no original.

## Início, final e recomeços

Ajuste de bordas usa a atividade do áudio: preserva cerca de 180 ms antes da primeira fala e 160 ms depois da última, quando há silêncio detectável. Corrige a retenção de pedaços isolados do silêncio inicial/final. Não determina visualmente o instante em que a boca fecha, nem remove olhares que ocorram enquanto ainda há fala/ruído. Essa análise visual precisa permanece pendente.

Detecção opcional de recomeços usa tempos de palavras e exige “errei” seguido, em até sete segundos, por “(vou) começar/recomeçar de novo/novamente/do zero”. Descarta a parte anterior ao último aviso e mantém a tentativa seguinte. Não identifica erros sem aviso, nem sabe qual parágrafo o usuário pretendia refazer; desative se quiser preservar trechos anteriores válidos. A fala remanescente e as legendas são recalculadas para o novo início. A gravação original permanece até a limpeza do projeto.

## Legendas opcionais e transcrição

Adicionar legendas pode ser desmarcado no envio ou em nova exportação. Sem legendas, sem zoom automático e com detecção de recomeços desligada, a transcrição é dispensada. Zoom automático ainda exige transcrição para selecionar os destaques mesmo sem legendas visíveis. Ativar legendas posteriormente gera a transcrição a partir do PCM salvo; desativar não exige repetir os cortes. Sem legenda, zoom ou aceleração, exportar copia o MP4 editado sem recodificar. O modo de cortes, ajuste de bordas, recomeços e vocabulário são fixados no upload.

O modelo base exige mais tempo de CPU do que tiny e é executado em subprocesso int8, um thread, liberando RAM antes da exportação. Não usamos modelos maiores ou APIs pagas. Não existe promessa de transcrição perfeita. Foi comparado o texto antigo com uma nova passagem de reconhecimento no áudio de uma gravação real do usuário, sem publicação de voz/vídeo/transcrição no repositório; não há referência humana integral nem percentual de acerto medido.

## Limites

Whisper base substitui o tiny, com busca beam 5, fallback de temperatura 0/0,2/0,4 e idioma português. Um campo opcional aceita até 300 caracteres de nomes/vocabulário como contexto, sem substituir palavras por regras. Continua sujeito a erros, especialmente nomes e termos jurídicos; revisão é recomendada. Música e ruído podem confundir detecção de silêncio. Corte central e zoom podem esconder elementos periféricos. Não há linha do tempo para arrastar clipes, rastreamento facial ou edição semântica por serviço pago. Android real e precisão com fala humana não foram medidos automaticamente.

## Operação e privacidade

Docker: `docker compose up --build -d`. Alternativa: Python 3.12, FFmpeg com libass e fonte DejaVu Sans, `pip install -r requirements.txt`, `uvicorn app:app --host 127.0.0.1 --port 8000 --workers 1`.

Render usa Dockerfile, porta 8000, JG_PASSWORD e RENDER_EXTERNAL_HOSTNAME. Autenticação Basic sob HTTPS; nunca colocar senha na URL. Arquivos em pasta por ID aleatório de 192 bits, sem envio para APIs externas de transcrição. Não persistir data é intencional: reinícios e implantações apagam todos os projetos. Expiração após 24h mais até um minuto, salvo trabalhos ativos. Cancelar encerra subprocessos e libera a fila. Baixar resultados antes de atualizar.

## Testes

`python test_critical.py` valida fluxo original com legendas controladas. `python test_options.py` valida formatos, aceleração, preservação de frequência de áudio, zoom, estilos, cores, rejeição de parâmetros inválidos, decodificação e download. `python test_cancel.py` valida cancelamento real. `python test_edges_retakes.py` valida bordas e remoção de aviso de recomeço entre blocos de legenda, preservando a fala subsequente. `python test_captions_pauses.py` valida dispensa de transcrição, ativação/desativação posterior, áudio PCM sincronizado e remoção de pausas curtas. `python test_face_4k.py` valida detecção real de rosto fora do centro, fallback sem rosto e exportação 2160×3840 (usa o retrato de domínio público Grace Hopper distribuído com matplotlib apenas como fixture de teste). `python test_memory.py` mede processamento com entrada 4K e zoom 1080p. São necessários httpx e numpy para testes. Esses testes não medem acurácia do Whisper.

## Ajustar um projeto pronto

Aplicar ajustes e gerar MP4 aparece junto aos ajustes e na revisão. O botão principal também aplica ao projeto atual; selecionar outro arquivo inicia um novo envio. Reabrir os ajustes preserva texto e opções ainda não enviados. Cliques duplicados são bloqueados; respostas de consultas anteriores não sobrescrevem uma exportação nova. Erros aparecem junto aos botões.

Zoom manual aceita segundos, vírgula decimal e relógio (ex.: 00:10-00:12; 20,5-22), ordena intervalos e rejeita sobreposições/tempos fora do vídeo. Usar momentos sugeridos preenche os intervalos para revisão. Após falha de exportação, o projeto que já tem mídia válida pode ser exportado novamente.

Teste de interface: `npm install --prefix /tmp/jg-dom jsdom --no-audit --no-fund` e `NODE_PATH=/tmp/jg-dom/node_modules node test_ui.cjs`. Usa DOM JavaScript real com cliques, requisições HTTP locais e FFmpeg, transcrição controlada e mídia sintética. Não mede aparência em navegador Android real. `python test_reexport.py` verifica nova exportação e recuperação após erro simulado do encoder.

## Zoom e cortes manuais — 1.5

Intensidade do zoom de 5% a 100%, em passos de 1%, tanto para centro quanto rosto. A porcentagem representa o aumento máximo suave: 50% chega a 1,5×; 100% a 2×.

Em Cortes manuais, abra a prévia e posicione o player para remover tudo à esquerda ou à direita. Também pode digitar tempos em segundos ou minutos:segundos e remover até 20 intervalos no meio. Aplicar cortes e ajustes exporta novamente. Limpar cortes manuais e aplicar restaura a versão após os cortes automáticos.

Tempos são sempre relativos à prévia após cortes automáticos, antes da velocidade e dos cortes manuais. A base permanece intacta e os cortes não se acumulam. Intervalos sobrepostos são unidos e bordas arredondadas ao frame de 30 fps. Legendas e zoom manual são remapeados para o novo relógio; na ausência de tempos de palavras confiáveis, o texto de legendas parcialmente cortadas é distribuído proporcionalmente e uma mensagem pede revisão. `python test_manual_cuts.py` testa cortes e nova exportação com FFmpeg real.

## Transição do zoom — 1.6

Escolha Suave (aproxima e volta progressivamente) ou Seco (entra imediatamente na porcentagem escolhida e retorna de uma vez ao final). A escolha aparece também no modo automático, serve para centro/rosto e é preservada ao reaplicar ajustes. Suave permanece como padrão dos projetos sem escolha explícita. Intervalos adjacentes não somam suas intensidades no frame compartilhado. `python test_zoom_transition.py` mede os frames reais do FFmpeg.

## Publicações — 1.7

`/publications.html` cria artes PNG em Canvas, sem API/modelo generativo. Stories e capas de Reels 1080×1920, posts 1080×1080 e carrosséis 1080×1350 de até 10 páginas. Ideia vira título e roteiro por modelos editoriais; os textos podem ser revistos página a página. Descrição e hashtags são sugestões por tema, sem promessa de alcance. Não há interpretação semântica de imagem, geração de fotografias, copywriting por LLM ou análise jurídica automática. A capa de Reels é uma imagem, não um vídeo.

Fotos JPEG/PNG/WebP de até 12 MB são decodificadas e reduzidas no navegador; não são enviadas ao servidor. Títulos/textos que não cabem bloqueiam o download em vez de serem cortados. ZIP sem compressão contém PNGs numerados e TXT com descrição/hashtags/fonte, com CRC32 por arquivo. Rascunho textual é salvo em localStorage no dispositivo; a foto não é persistida e precisa ser selecionada novamente após fechar a página. Somente o filtro da pesquisa é enviado ao servidor.

`GET /api/publications/research?q=&days=30` consulta quatro canais oficiais: API pública Incra e RSS Câmara Agropecuária/Meio Ambiente e STJ. Busca é limitada aos itens disponíveis nesses canais (30 do Incra e quantidade disponível nos RSS), filtrados por palavras, data e tema; não é busca exaustiva nem pesquisa jurisprudencial aprofundada. Fontes, falhas e datas são visíveis. Janela 1–90 dias, fuso São Paulo, cache de 15 minutos, deduplicação por URL, quatro conexões concorrentes, timeout de 10 s por fonte, limite de 2 MB/resposta, hosts e redirects HTTPS restritos. Não considera lei vigente só porque uma manchete menciona projeto. A seleção de notícia apenas vincula título/data/link ao rascunho; não analisa a íntegra. Sem custos de APIs.

Testes: `python test_publications.py`; `npm install --prefix /tmp/jg-pub-test jsdom @napi-rs/canvas --no-audit --no-fund` e `NODE_PATH=/tmp/jg-pub-test/node_modules node test_publications.cjs`. Não são dependências de produção.
