# Validação — 19/10/2026

PASSOU: fluxo HTTP de upload MP4, análise e remoção de pausas, prévia, revisão de legenda, exportação, download, exclusão, formato inválido, proteção de origem, tempos de legenda inválidos e autenticação com senha.

O vídeo sintético de 6 segundos, com pausa entre 2 e 4 segundos, resultou em 4,31466 segundos. Resultado confirmado por ffprobe: H.264, 1080×1920, áudio AAC. FFmpeg decodificou o MP4 final sem erro. A legenda corrigida foi incorporada e o quadro exportado foi inspecionado visualmente, incluindo destaque cobre.

PASSOU: segundo teste com Whisper tiny real, CPU int8 e vídeo com fala sintetizada em inglês. Pipeline automático completo: upload → cortes → Whisper configurado para português → legendas incorporadas → MP4 reproduzível e download HTTP. De 10,835 segundos para 7,04756 segundos. Whisper gerou quatro blocos de legenda. Este teste valida a integração; não mede a precisão de transcrição em português brasileiro. Modelo base, voz humana em português, vídeos MOV reais, sincronização audiovisual humana e navegador Android ainda precisam ser verificados.

Incompatibilidade encontrada entre PyAV do ambiente e faster-whisper foi corrigida passando áudio PCM do módulo wave em array numpy para o modelo. Nenhuma chamada de API paga foi realizada.

PUBLICAÇÃO PENDENTE: não há conta de hospedagem de processamento conectada. A integração Render foi sugerida para verificar opções e recursos da conta. Não há link online publicado. Nenhum custo foi contratado. Interface responsiva implementada, sem validação de navegador neste ambiente.

O teste de upload/exportação pode ser repetido com `python test_critical.py` após instalar httpx (dependência exclusiva de teste). O teste usa legendas controladas para isolar e validar o fluxo de edição. Não representa um teste de acurácia do Whisper.

## Preparação da publicação

Conexões GitHub e Render verificadas. Repositório autorizado em 19/10/2026. A implantação usará somente o plano free. Transcrição passou a executar em processo separado para liberar memória antes da incorporação das legendas. Fonte não contém vídeos, senhas, dados pessoais ou modelos binários.
