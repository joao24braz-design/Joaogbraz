# Validação — 19/10/2026

## Testes locais

Fluxo HTTP de upload, análise de silêncio, prévia, correção de legenda, exportação, download, exclusão, formatos inválidos, proteção de origem, tempos de legenda inválidos e autenticação testados. FFmpeg real: vídeo de 6 segundos passou a 4,31466 segundos. Transcrição em subprocesso testada com Whisper tiny real.

## Teste no serviço online

Deploy dep-dbb14pdg1s2s73dshq20, Render plan free, aplicativo iniciado com sucesso. Upload real HTTP de vídeo com fala sintetizada, detecção de pausas, corte, transcrição Whisper tiny configurado para português, revisão de legenda por POST e incorporação em MP4 concluídos. Download HTTP autenticado confirmado. ffprobe confirmou H.264, 1080×1920, AAC e duração final de 7,2 segundos. FFmpeg decodificou o MP4 final sem erros. Resposta sem senha negada com 401. O vídeo e a voz do teste são sintéticos e não contêm dados pessoais.

Limites: teste não mede precisão com voz humana brasileira; interface não foi exercitada em Android real. Modelos maiores e vídeos longos não foram validados neste plano. O plano gratuito pode suspender o serviço por inatividade ou limites. Arquivos expiram em 24 horas ou em qualquer reinício, inclusive suspensão do host. Usuário deve baixar o resultado antes disso. Sem serviços de IA pagos. Credenciais ficam somente em variáveis de ambiente.
