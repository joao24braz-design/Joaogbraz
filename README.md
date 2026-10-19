# JG Reels AI 1.1

Estúdio pessoal: https://jg-reels-ai.onrender.com (protegido por senha). Render gratuito, sem APIs pagas. O serviço pode adormecer e a edição usa CPU limitada. Nenhuma atualização de plano contratada.

## Arquitetura

FastAPI serve HTML responsivo e recebe uploads MP4/MOV em fluxo. Um único trabalhador executa FFmpeg e Whisper tiny local CPU int8 em subprocessos canceláveis. Upload até 300 MB, até 10 minutos, entrada até 4K, dois trabalhos na fila e dez projetos temporários. Sem banco de dados. Um processo Uvicorn.

Detecção de silêncios abaixo de -35 dB por 600 ms, preservando margens de fala de 140/180 ms. Cortes sequenciais limitam memória. Vídeo intermediário usa x264 ultrafast CRF18; ruído leve e volume são tratados uma vez após concatenar. A transcrição ocorre no vídeo cortado e na velocidade original. Legendas são agrupadas a partir dos tempos das palavras; podem ser corrigidas antes ou depois da primeira exportação.

## Opções de edição

- Modo automático: velocidade 1×, legenda Premium média off-white/cobre e zoom automático por palavras e frases de destaque. No modo personalizado, o zoom pode ser desligado.
- Modo personalizado: 1× até 2× em passos de 0,1, preservando o tom da voz com atempo; tamanho pequeno/médio/grande; modelos Premium, Limpo ou Caixa; cores de texto e destaque.
- Reels e Stories 9:16 com margens de legenda diferentes; feed 4:5 ou quadrado 1:1. Largura 1080 ou 720 pixels; imagem inteira com margens ou preenchimento com corte central.
- Zoom central suave de até 10%. Automático seleciona até quatro momentos por palavras-chave e pontuação, sem compreensão semântica completa ou rastreamento de rosto. Personalizado aceita até oito intervalos em segundos do vídeo cortado antes de acelerar. Não há garantia de zoom quando nenhuma pista é encontrada.
- Alterações de estilo, zoom e velocidade podem ser reexportadas sem repetir cortes/transcrição. Formato, resolução e enquadramento são definidos no envio e exigem novo upload para mudar.

O relógio canônico das legendas permanece no vídeo cortado, antes de acelerar. Na exportação, o mesmo fator divide timestamps do vídeo e das legendas e acelera o áudio. A prévia de revisão usa a velocidade original. ASS aplica tamanho e cor no vídeo real; a amostra HTML é apenas amostra de estilo. Saída H.264, AAC, yuv420p e MP4 faststart. Zoom e 1080p aumentam o tempo de exportação.

## Limites

Whisper tiny pode errar nomes e termos jurídicos; revisão é recomendada. Música e ruído podem confundir detecção de silêncio. Corte central e zoom podem esconder elementos periféricos. Não há linha do tempo para arrastar clipes, rastreamento facial ou edição semântica por serviço pago. Android real e precisão com fala humana não foram medidos automaticamente.

## Operação e privacidade

Docker: `docker compose up --build -d`. Alternativa: Python 3.12, FFmpeg com libass e fonte DejaVu Sans, `pip install -r requirements.txt`, `uvicorn app:app --host 127.0.0.1 --port 8000 --workers 1`.

Render usa Dockerfile, porta 8000, JG_PASSWORD e RENDER_EXTERNAL_HOSTNAME. Autenticação Basic sob HTTPS; nunca colocar senha na URL. Arquivos em pasta por ID aleatório de 192 bits, sem envio para APIs externas de transcrição. Não persistir data é intencional: reinícios e implantações apagam todos os projetos. Expiração após 24h mais até um minuto, salvo trabalhos ativos. Cancelar encerra subprocessos e libera a fila. Baixar resultados antes de atualizar.

## Testes

`python test_critical.py` valida fluxo original com legendas controladas. `python test_options.py` valida formatos, aceleração, preservação de frequência de áudio, zoom, estilos, cores, rejeição de parâmetros inválidos, decodificação e download. `python test_cancel.py` valida cancelamento real. `python test_memory.py` mede processamento com entrada 4K e zoom 1080p. São necessários httpx e numpy para testes. Esses testes não medem acurácia do Whisper.
