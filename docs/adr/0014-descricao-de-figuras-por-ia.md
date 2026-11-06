# ADR 0014 — Descrição das figuras por IA

- **Status:** aceito
- **Data:** 2026-11-06
- **Complementa:** a [ADR 0004](0004-leitura-de-pdf-e-divisao-em-trechos.md) (leitura de PDF),
  que deixava os PDFs escaneados para uma evolução futura

## Contexto

A indexação só lia o **texto selecionável** do PDF. O que estava nas fotos, nos diagramas e
nos desenhos técnicos (nomes de peças, números de posição, cotas, ligações) ficava de fora
da busca, e os PDFs escaneados eram recusados.

Uma amostra da pasta da Engenharia mostrou que esses manuais dependem muito de figuras:
de **50% a 70% das páginas** têm fotos ou desenhos. Há também manuais inteiros escaneados
(ex.: `95010011-01P.pdf`, 9 páginas, cada uma uma imagem).

Os manuais já tinham sido indexados quando a necessidade apareceu, e reindexar tudo só
para acrescentar as figuras seria desperdício.

## Decisão

1. **Uma descrição por página com figuras.** A página é renderizada como JPEG (150 dpi) e
   enviada a um **modelo com visão**, junto com o texto já extraído dela. O modelo descreve
   componentes, legendas, cotas, ligações e avisos, e transcreve o texto de dentro das
   figuras. Numa página escaneada, transcreve a página inteira. Quando a página só tem
   logotipo ou moldura, o modelo responde `SEM_FIGURAS` e a página fica registrada sem texto.
2. **Quais páginas vão.** Uma página tem figuras quando:
   - imagens cobrem ao menos **5%** dela (ícones e logotipos ficam de fora); ou
   - ela tem muito mais **traços vetoriais** que uma página comum do mesmo documento
     (desenhos exportados do CAD). A base é o percentil 20 do documento, porque nesses
     manuais até as páginas de texto têm mais de mil traços na moldura; o corte é o dobro
     da base, com no mínimo 300 traços a mais; ou
   - não tem texto, mas tem algum desenho.
3. **A descrição vira um trecho do tipo `figure`**, citado pela própria página. O texto do
   trecho começa com `[Figuras da página N, descritas por IA a partir da imagem]`, então o
   modelo que responde sabe de onde veio a informação. A tabela `chunks` ganhou a coluna
   `kind` (`text` ou `figure`), e a posição passou a ser única por tipo.
4. **As descrições são guardadas** na tabela `figure_descriptions`, por manual, página e
   **hash do arquivo**. Reindexar o texto reaproveita o que já foi descrito sem chamar a
   IA. Um arquivo novo (outra revisão) tem outro hash e é descrito de novo; as descrições
   da versão antiga são apagadas quando a nova é indexada. Cada descrição é gravada assim
   que chega: se a execução parar no meio, o que já foi pago não se perde.
5. **Quem decide é quem importa, a cada vez** (não uma configuração do servidor):
   - **Indexação com figuras:** opção no envio de PDFs, no **Reprocessar** de um manual com
     falha, em **Sincronizar** e no agendamento diário (guardado em `sync_schedule`). A API
     recebe `describe_figures` em cada pedido. Se a IA falhar num manual com texto, ele é
     indexado só com o texto e as figuras ficam para depois. Num manual escaneado, a falha
     é do manual.
   - **Só as figuras, num manual já indexado:** botão **Descrever figuras** (ou o comando
     `describe-figures`). Descreve as páginas que faltam e refaz **só os trechos de
     figuras**: os trechos de texto e seus embeddings ficam como estão. Antes de confirmar,
     a tela mostra quantas páginas têm figuras e quantas faltam (`GET
     /manuals/{id}/figures`, sem chamar a IA). Roda em segundo plano, um pedido por manual;
     o andamento fica em memória, como o da sincronização.
6. **Modelo:** o mesmo do chat, ou outro em `APP_GEMINI_FIGURE_MODEL` /
   `APP_OPENAI_FIGURE_MODEL` (ex.: um mais barato, desde que aceite imagens). A interface
   `LanguageModel` passou a aceitar imagens no pedido; os dois provedores as enviam.
7. **Escaneados:** o leitor de PDF não recusa mais um documento sem texto. Quem decide é a
   indexação: sem texto e sem figuras descritas, o manual falha com uma mensagem que manda
   reprocessar descrevendo as figuras.

## Consequências

- **Custo:** uma chamada ao modelo por página com figuras. Cada uma usa cerca de 1.500 a
  2.500 tokens de entrada (imagem + texto da página) e algumas centenas de saída. Como mais
  da metade das páginas tem figuras, descrever a pasta inteira custa bem mais que os
  embeddings do texto. Por isso a opção vem **desmarcada** em todas as telas, a confirmação
  mostra quantas páginas vão para a IA, e o comando tem simulação e limite.
- O consumo da descrição de figuras **não entra** na tela **Consumo** (que é por pergunta e
  por usuário). Os tokens ficam registrados em `figure_descriptions`.
- A descrição é gerada por IA e pode errar ou omitir detalhes. O cabeçalho do trecho deixa
  isso visível, e a resposta continua citando a página para conferência.
- Nova dependência: **Pillow** (converter a página renderizada em JPEG).
- A detecção por traços vetoriais é heurística: pode mandar uma página de tabela com muitas
  linhas (que o modelo descreve ou marca como `SEM_FIGURAS`) e pode deixar passar um
  desenho pequeno numa página de texto.
