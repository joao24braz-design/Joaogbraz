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

PRODUÇÃO 1.2: deploy dep-dbb2cjgm7kps73aplnt0, commit eb27d45017ab5409bb29621104fe0dca9e0d2986 publicado como live. Teste remoto com Whisper real: entrada 6,0 s → corte 3,739 s; detecção real de rosto fora do centro (x=0,2875/y=0,2102), zoom, legendas e MP4 final 2160×3840 H.264/AAC. Download de 1812737 bytes, decodificação completa e quadro extraído passaram. Projeto de teste excluído. Nenhum upgrade de plano ou API paga.

## Transcrição, legendas opcionais e pausas — versão 1.3

Whisper base multilingual int8 substitui tiny. Configuração padrão de contexto, busca beam 5 e fallback de temperatura; condição do segmento anterior desativada para reduzir propagação de erros. Entrada de reconhecimento alterada de AAC filtrado para PCM sem compressão da mesma concatenação. Vocabulário opcional, até 300 caracteres. Testes de voz sintética em português revelaram falhas graves com janelas de 15 segundos/temperatura fixa; essa configuração foi descartada. Não se mediu acurácia com voz humana do usuário.

PASSOU: FFmpeg/HTTP real, amostra com pausas de 0,4 e 1 segundo: Natural 5,4 s; Dinâmico 4,8 s. Sem legendas/zoom não chamou transcrição e exportou cópia exata de edited.mp4. Ativar legendas depois gerou transcrição uma vez, incorporar texto alterou o vídeo; desativar novamente restaurou saída sem texto sem nova transcrição. PCM mono 16 kHz conferido com tolerância de 0,15 s ao vídeo cortado. Ajustes de cortes/vocabulário permanecem os definidos no envio. Regressão de quatro formatos/velocidades/estilos e cancelamento passou. JavaScript e Python com sintaxe válida.

Teste de reconhecimento real (áudio privado de gravação já processada, 52,5 s, sem exportar conteúdo ao repositório): Whisper base int8, configuração final sem vocabulário, pico 358,1 MB no subprocesso e 7,81 s de CPU local. Texto comparado com saída tiny; há diferenças, mas sem transcrição humana de referência não se mede taxa de acerto nem se promete correção total. Testes sintéticos com vocabulário mostraram vieses/repetições: campo permanece opcional, sem preenchimento automático.

Ajuste de bordas implementado por áudio: 180 ms antes/160 ms depois. Regra opcional de último recomeço explícito (“errei… começar de novo”) usa tempos de palavras. Não existe detecção visual de boca fechada; permanece pendente. Não há detecção semântica geral de tentativas abandonadas.

PASSOU: teste HTTP/FFmpeg com silêncio inicial/final e aviso de recomeço atravessando blocos de legenda. Regra retirou 3,32 s; final 2,081 s, legenda “Fala correta agora.” com início 0,18 s. Nenhum corte por apenas mencionar “erro” ou “errei na análise” sem reinício. MP4 decodificado e download disponível.

PUBLICAÇÃO 1.3: commit aa9473b5e48a4414f984ef528116227f2f73ab85, deploy dep-dbb2qh0n74is73c2bek0 live. Teste remoto final usou somente fala genérica sintetizada com Flite (inglês com reconhecimento configurado para português; não mede acurácia linguística). Upload, Whisper base real, revisão, exportar sem legenda e depois com legenda, H.264/AAC 720×1280, download e decodificação passaram. Entrada 6 s → saída 2,566 s; 2 blocos de legenda. Sem legenda/zoom, bytes iguais à prévia, comprovando que texto não foi incorporado. Projeto sintético excluído.

A revisão automática de permissões bloqueou a verificação que reenviaria um trecho privado do projeto anterior ao serviço Render, pois faltava autorização específica para esse reenvio. O bloqueio não foi contornado; foi criado um teste alternativo com fala sintética genérica e sem gravações do usuário. A comparação local anterior não fornece taxa de acerto.

## Correção de zoom e reaplicação — versão 1.4

PASSOU: teste de interface com jsdom, HTTP e FFmpeg reais. Projeto já concluído → editar → zoom manual em formato relógio/vírgula → corrigir legenda → aplicar. Três exportações por cliques nos botões de ajustes, principal e revisão. Abrir edição novamente preservou alterações; clique duplicado bloqueado; tempo inválido mostrou mensagem junto aos dois botões e não enviou HTTP. Sugestões automáticas preenchidas e aplicadas. Não representa teste visual em navegador Android.

PASSOU: backend retomou exportação após falha intencional de encoder, preservando a mídia intermediária. Zoom automático gerado para fala sem palavras-chave e para comparação com valores numéricos. Quatro formatos/estilos/velocidades da regressão passaram. Versão mantém dados temporários: é necessário baixar resultados antes de publicar.

## Zoom e cortes manuais — 1.5

PASSOU: vídeo sintético de 8 s, remover antes de 1 s, depois de 7 s e intervalo de 3–5 s produziu 4 s selecionados. Exportação com velocidade 1,2×, zoom 50% e 100%, H.264/AAC e decodificação passaram. Frequências de áudio confirmaram a seleção dos trechos corretos. MP4 base permaneceu byte a byte intacto; limpar cortes restaurou a base. Intervalos sobrepostos unidos, parâmetros inválidos rejeitados, palavras e momentos de zoom remapeados e temporários removidos.

PASSOU: regressão de quatro formatos/velocidades/legendas e teste de interface anterior com três reexportações reais. Testes usam mídias sintéticas e legendas controladas; não medem acurácia do reconhecimento nem aparência em Android real.

PASSOU: interface com cinco reexportações reais, incluindo slider de zoom 50%, marcação à esquerda/direita pela posição da prévia, intervalo em formato relógio, aplicação de cortes e restauração ao limpar.

## Transição do zoom — 1.6

PASSOU: FFmpeg real com padrão estático e zoom de 50%. Largura do marcador antes/entrada/meio/último frame/saída: zoom seco 40/60/60/60/40 pixels; suave 40/46/60/46/40 nos frames correspondentes de rampa. Intervalos adjacentes mantiveram 50% na fronteira sem duplicação. Valor inválido de transição rejeitado.

PASSOU: teste de interface com cinco reexportações reais; seleção de zoom seco enviada à API e preservada na tela e nas opções do projeto após cortes manuais e nova exportação.

## Publicações — 1.7

PASSOU: API com filtros, datas, descarte de item antigo, duplicação, cache, falha parcial, validação de intervalo, parsers RSS/JSON e restrição de hosts. Consulta de rede real em 19/10/2026: quatro canais oficiais responderam, 16 pautas retornadas; fonte e data mantidas. Não mede relevância semântica nem valida o mérito jurídico das matérias.

PASSOU: DOM JavaScript com Canvas nativo: carrossel de cinco páginas a partir de ideia, foto carregada localmente, edição/paginação, adicionar/excluir página, ZIP/PNG, bloqueio de título que não cabe, notícia vinculada com fonte na descrição, Stories/quadrado e rascunho local. ZIP reaberto com Python, CRC íntegro, cinco PNGs 1080×1350 decodificados com Pillow e TXT com descrição/hashtags. Arte inspecionada visualmente. Não equivale a teste visual em Android real.

PENDENTE POR ESCOPO GRATUITO: geração livre de imagens por IA, interpretação da foto, redação por modelo de linguagem e pesquisa jurídica aprofundada com análise/cruzamento da íntegra. Os recursos entregues são composição visual, roteiros por modelo e pesquisa de canais oficiais, rotulados na interface. Nenhuma API paga configurada.

## Estilos e modelos favoritos — 1.8

PASSOU: integração DOM/Canvas real com oito opções (sete renderizações distintas sem fotografia enviada), aplicação de descrição reconhecida, rejeição informativa de descrição não reconhecida, fonte/alinhamento/título/cor, favorito salvo e reaplicado com preservação do conteúdo, recuperação de favorito e rascunho após reinicialização do JavaScript e exclusão do favorito. Regressão de PNG, ZIP, foto local, carrossel, texto excedente, formatos e notícia vinculada passou. Favoritos não incluem foto nem texto das páginas. Prévia dos estilos inspecionada em mosaico PNG. Sem teste em aparelho Android real.

## Referências visuais — 1.9

PASSOU: integração DOM/Canvas com uma imagem, adição incremental de mais quatro e lote de cinco; rejeição da sexta, lote de seis, formato inválido e falha de decodificação. Reordenação altera a sequência, remoção individual/total atualiza contagem e painel, referência ampliada é sincronizada entre aba e editor. Criar com referências preserva ideia, título e estilo. Anotações persistem localmente e referências não são enviadas à pesquisa. Navegação por teclado e regressão dos modelos favoritos, descrição visual, foto, PNG/ZIP e formatos passaram. Sem teste em aparelho Android real.

## IA de marketing — integração preparada, não ativada

PASSOU, COM RESPOSTAS SIMULADAS: API bloqueada sem configuração, status sem segredo, exigência de consentimentos de texto/imagem, validação de referências, briefing, tamanho de requisição, serialização REST, resposta JSON validada, erro de resposta incompleta, cota e limite local. Nenhuma chamada real ao Google e nenhuma chave criada/configurada.

PASSOU, COM RESPOSTAS SIMULADAS: UI define público/objetivo/tom, bloqueia sem consentimento, mostra proposta sem alterar rascunho, aplica após revisão, preserva visual salvo por padrão e aceita sugestão visual apenas sob seleção explícita. Erro de provedor preserva rascunho; clique duplicado bloqueado; botão desabilitado sem configuração. Regressão do editor de publicações, referências, favoritos, PNG/ZIP e formatos passou.

PENDENTE: chave de projeto Google AI Studio Free Tier sem faturamento, configuração segura no servidor, geração real e avaliação editorial com material genérico, análise real de referências e publicação. Sem afirmar qualidade estratégica validada ou camada ativa. Produção mantida na versão 1.9.
