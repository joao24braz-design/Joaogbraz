# JG Reels AI

Editor pessoal web de Reels. Upload MP4/MOV, remoção de pausas, tratamento de áudio, Whisper local em português, revisão opcional de legendas e MP4 H.264/AAC 1080×1920.

## Execução

Docker: `docker compose up --build -d`. Abra http://localhost:8000.

## Hospedagem

Dockerfile com modelo Whisper tiny incluído na imagem e transcrição em processo separado para liberar memória antes da exportação. Servidor único, fila limitada, sem APIs pagas. Configurar JG_PASSWORD com senha forte por variável de ambiente. RENDER_EXTERNAL_HOSTNAME é reconhecido automaticamente. Sem disco pago. Arquivos temporários expiram em 24 horas e são apagados em reinícios.

Somente plano gratuito autorizado. A disponibilidade está sujeita aos limites do host: pouca CPU/memória, suspensão por inatividade e possíveis reinícios. Validação em produção ainda pendente. O aplicativo não publica no Instagram e não adiciona música automaticamente.

## Testes

`python test_critical.py` após instalar requirements.txt e httpx. Testa FFmpeg real e HTTP com áudio sintético e legendas controladas. Pipeline Whisper tiny real também foi exercitado com fala sintetizada. Precisão em voz humana brasileira e Android precisam ser validadas. Sem teste de navegador realizado neste ambiente.
