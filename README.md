# JG Reels AI

Editor pessoal web com FFmpeg e Whisper local: upload MP4/MOV, cortes de pausas, áudio normalizado, legendas em português, revisão opcional e exportação MP4 H.264/AAC 1080×1920.

Aplicativo: https://jg-reels-ai.onrender.com — acesso protegido por senha. As credenciais são entregues ao proprietário fora deste repositório.

## Hospedagem gratuita

Um único serviço Docker no Render, plan free. Modelo Whisper tiny incluído na imagem. Transcrição em subprocesso para liberar memória antes da exportação. Nenhuma API de IA paga. Recursos sujeitos às limitações de CPU, memória, disponibilidade e uso do plano gratuito do provedor. Não existe garantia de operação ilimitada ou suporte a vídeos longos nesse plano. Suspensão por inatividade pode demorar a reabrir e apaga os arquivos temporários.

## Execução local

`docker compose up --build -d` e abrir http://localhost:8000. Para acesso externo configurar JG_PASSWORD, JG_HOSTS e HTTPS. No Render, RENDER_EXTERNAL_HOSTNAME é reconhecido automaticamente. Sem disco pago. Limite de upload 300 MB/10 minutos; recomenda-se começar com Reels curtos. Fila com um trabalhador e dez projetos temporários. Arquivos expiram em 24h ou em reinícios.

## Validação

Ver VALIDACAO.md. Teste de edição real na implantação concluído com MP4 baixado e decodificado. Voz humana em português e Android real aguardam validação de uso. Não adiciona música nem publica no Instagram.
