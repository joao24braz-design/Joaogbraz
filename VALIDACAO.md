# Validação — 19/10/2026

PASSOU: fluxo HTTP de upload MP4, análise e remoção de pausas, prévia, revisão de legenda, exportação, download, exclusão, formato inválido, proteção de origem, tempos de legenda inválidos e autenticação com senha.

O vídeo sintético de 6 segundos, com pausa entre 2 e 4 segundos, resultou em 4,31466 segundos. Resultado confirmado por ffprobe: H.264, 1080×1920, áudio AAC. FFmpeg decodificou o MP4 final sem erro. A legenda corrigida foi incorporada e o quadro exportado foi inspecionado visualmente, incluindo destaque cobre.

PASSOU: segundo teste com Whisper tiny real, CPU int8 e vídeo com fala sintetizada em inglês. Pipeline automático completo: upload → cortes → Whisper configurado para português → legendas incorporadas → MP4 reproduzível e download HTTP. De 10,835 segundos para 7,04756 segundos. Whisper gerou quatro blocos de legenda. Este teste valida a integração; não mede a precisão de transcrição em português brasileiro. Modelo base, voz humana em português, vídeos MOV reais, sincronização audiovisual humana e navegador Android ainda precisam ser verificados.

Incompatibilidade encontrada entre PyAV do ambiente e faster-whisper foi corrigida passando áudio PCM do módulo wave em array numpy para o modelo. Nenhuma chamada de API paga foi realizada.

PUBLICAÇÃO: serviço Docker gratuito disponível em https://jg-reels-ai.onrender.com com senha. Upload, Whisper real, cortes, legendas, exportação 1080p e download foram verificados no host. Correção de memória e botão cancelar publicados e testados. Nenhum plano/API pago contratado.

O teste de upload/exportação pode ser repetido com `python test_critical.py` após instalar httpx (dependência exclusiva de teste). O teste usa legendas controladas para isolar e validar o fluxo de edição. Não representa um teste de acurácia do Whisper.

## Edição personalizada 1.1

Teste local de integração com FFmpeg real: Reels 720×1280, velocidade 1× sem zoom; Stories 720×1280, 1,1×, zoom automático e estilo limpo; feed 720×900, 2×, zoom manual e caixa; quadrado 720×720, 1,5×, zoom automático e Premium. Todos decodificaram e baixaram com H.264/AAC. Tempos ASS foram divididos pelo mesmo fator de velocidade; duração final conferida com tolerância de 0,2 s. Tom de teste de 440 Hz preservado na saída 2× (FFT). Validação de velocidade, cores e intervalos de zoom inválidos passou. Transcrição controlada nesses testes, sem alegação de precisão do Whisper.

Cancelamento de subprocesso ativo e trabalho na fila passou novamente. Entrada 2160×3840 com quatro cortes e zoom automático em saída 1080×1920: pico FFmpeg 152,5 MB, processo Python 33,7 MB; saída decodificada sem erro.

Interface: sintaxe JavaScript validada. Teste em navegador local indisponível: Chromium não instalado e download bloqueado/truncado no ambiente. Não foi alegada validação visual no Android.

PUBLICAÇÃO 1.1 VERIFICADA: commit 220f73f7cd562466fc336f2c1ca2e61358162e2f, deploy dep-dbb27a6i0phs73b86tl0 (live). Teste real em produção com Whisper: upload, cortes, transcrição (4 blocos), correção de legenda, exportação Stories 720×1280, legenda grande/caixa branca, zoom manual e velocidade 1,2×. Entrada 10,835 s → cortes 7,1 s → saída 5,866 s. MP4 H.264/AAC baixado (181978 bytes), decodificado e quadro extraído. Projeto de teste excluído após verificação. Nenhuma medição de acurácia de português humano ou Android real.

## Rosto e 4K — versão 1.2

Teste local com FFmpeg/OpenCV reais e retrato Grace Hopper fora do centro. Opção zoom_target=face com momento manual detectou âncora x=0,289 / y=0,211. Vídeo final 2160×3840 H.264/AAC, legenda incorporada, download HTTP e decodificação completa passaram. Sem rosto, exportação concluiu com zero zoom e aviso explícito. Pico de subprocesso 239,8 MB + Python 62,7 MB no teste. Os quatro formatos/estilos/velocidades da regressão 1.1 passaram novamente. Não representa garantia de detecção em perfis, oclusões ou movimentos rápidos, nem de memória para todo codec de entrada.
