# JG Reels AI 1.3

Estúdio pessoal: https://jg-reels-ai.onrender.com (protegido por senha). Render gratuito, sem APIs pagas. O serviço pode adormecer e a edição usa CPU limitada. Nenhuma atualização de plano contratada.

## Arquitetura

FastAPI serve HTML responsivo e recebe uploads MP4/MOV em fluxo. Um único trabalhador executa FFmpeg e Whisper base local CPU int8 em subprocessos canceláveis. Upload até 300 MB, até 10 minutos, entrada até 4K, dois trabalhos na fila e dez projetos temporários. Sem banco de dados. Um processo Uvicorn.

Detecção de silêncios abaixo de -35 dB: modo Natural a partir de 600 ms com margens de 140/180 ms; modo Dinâmico a partir de 300 ms com margens de 80/100 ms. A sequência da fala é mantida; o modo dinâmico pode exigir conferência de palavras sussurradas ou ruído variável. Cortes sequenciais limitam memória. Vídeo intermediário usa x264 ultrafast CRF18; ruído leve e volume são tratados uma vez após concatenar. A transcrição ocorre no vídeo cortado e na velocidade original. Legendas são agrupadas a partir dos tempos das palavras; podem ser corrigidas antes ou depois da primeira exportação.

## Opções de edição

- Modo automático: velocidade 1×, legenda Premium média off-white/cobre e zoom automático por palavras e frases de destaque. No modo personalizado, o zoom pode ser desligado.
- Modo personalizado: 1× até 2× em passos de 0,1, preservando o tom da voz com atempo; tamanho pequeno/médio/grande; modelos Premium, Limpo ou Caixa; cores de texto e destaque.
- Reels e Stories 9:16 com margens de legenda diferentes; feed 4:5 ou quadrado 1:1. Largura 2160 (4K), 1080 ou 720 pixels; imagem inteira com margens ou preenchimento com corte central.
- Zoom central suave de até 10%. A opção de direcionar ao rosto usa OpenCV local em subprocesso, até três quadros reduzidos por momento, para localizar o maior rosto frontal e aproximar até 18%. Trechos sem detecção ficam sem zoom e geram aviso. A detecção não identifica pessoas nem acompanha o rosto continuamente. Automático seleciona até quatro momentos por palavras-chave e pontuação, sem compreensão semântica completa ou rastreamento contínuo. Personalizado aceita até oito intervalos em segundos do vídeo cortado antes de acelerar. Não há garantia de zoom quando nenhuma pista é encontrada.
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
