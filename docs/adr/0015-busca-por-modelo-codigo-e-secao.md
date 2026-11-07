# ADR 0015 — Busca por modelo, por código e com o título da seção

- **Status:** aceito
- **Data:** 2026-11-06
- **Complementa:** a [ADR 0004](0004-leitura-de-pdf-e-divisao-em-trechos.md) (divisão em
  trechos) e a [ADR 0010](0010-historico-de-conversas.md) (perguntas de continuação)

## Contexto

Comparando com o agente feito no Copilot, as mesmas perguntas recebiam respostas mais
curtas e, às vezes, erradas. Os casos analisados:

- **"quais os acionamentos dos siloflex diâmetros 55, 75 e 100"**: a busca não reconhecia a
  lista de modelos, os 6 trechos vinham todos do manual do 55, e a resposta dizia que o 75
  e o 100 "não constam".
- Os manuais do **Siloflex 75 e 100** (`95014002-01P.pdf`, `95014003-01P.pdf`) quase não têm
  texto selecionável: 61 páginas e 1 trecho. Uma varredura da pasta da Engenharia achou
  9 de 289 PDFs nessa situação.
- **Códigos de peça** ("20.400.319"): a busca por sentido trata códigos parecidos quase como
  iguais e pode não trazer o trecho que tem o código exato.
- **O meio de uma tabela** caía num trecho sem o título da seção ("Acionamento
  Motoredutor") e sem o nome do equipamento.
- **Conversa longa**: a busca só usava a pergunta anterior; na terceira pergunta seguida o
  modelo citado na primeira se perdia.

## Decisão

1. **Listas de modelos.** "Siloflex 55, 75 e 100", "55/75", "modelo 75 ou 100" e "Ø75" viram
   um modelo por número. Com mais de um modelo, **cada um tem a sua cota** de trechos (ao
   menos 4). O total pode passar do `top_k`, até o dobro dele.
2. **Busca por código exato.** Palavras com 5 dígitos ou mais (ou letras e 3 dígitos, como
   "GA56/71") são buscadas também literalmente no texto dos trechos, sem contar pontos,
   hífens e barras. Até 3 trechos encontrados assim vão na frente. Tensões e frequências
   ("220/380V", "60Hz") e modelos de equipamento ficam de fora.
3. **Título da seção nos trechos.** Um trecho que começa no meio de uma seção numerada
   ("1.2.5.1 Acionamento Motoredutor:") leva os títulos dela na primeira linha:
   `[Seção: 1.2 … > 1.2.5.1 …]`. O título precisa ter um ponto na numeração e letra
   maiúscula depois, para não confundir com códigos e listas de peças.
4. **Título do manual no embedding.** O texto que vira embedding é o título do manual mais
   o trecho. O texto guardado e mostrado à IA não muda.
5. **Modelo lembrado na conversa.** Se nem a pergunta atual nem a anterior citam um
   modelo, a busca usa também a última pergunta da conversa que citou um.
6. **Regras no prompt.** Responder cada modelo separadamente (tabela para comparar ou listar
   códigos). Sem modelo na pergunta e com trechos de manuais diferentes, separar a resposta
   por manual e pedir o modelo. Em pedidos de lista completa, avisar que pode estar
   incompleta e indicar as páginas.
7. **Especificações do modelo citado.** Quando a pergunta cita um modelo, o trecho da seção
   *Especificações Técnicas* do manual dele vai sempre junto, fora da cota (um trecho a
   mais por modelo). Em "quais os acionamentos do Siloflex", as tabelas de códigos repetem
   "acionamento" dezenas de vezes e ocupavam todas as vagas, e a resposta perdia "0,5 CV
   para linhas de 0 a 80 m". Valem os títulos "Especificações Técnicas", "Dados Técnicos"
   e "(Principais) Características", só como título de linha: o sumário (pontinhos) e a
   frase padrão "especificações técnicas contidas neste manual" ficam de fora. Na pasta,
   44 de 229 manuais com texto têm essa seção (mais os escaneados com figuras descritas);
   os outros ficam como antes.
8. **Aviso de PDF sem texto.** A tela de manuais avisa quando um manual indexado tem menos
   de um trecho a cada 4 páginas e nenhuma figura descrita: é para clicar em
   *Descrever figuras* (ADR 0014).

## Consequências

- Os itens 3 e 4 só valem para manuais **reindexados**. A sincronização só reprocessa os
  manuais que mudaram, então há um comando para reindexar todos:
  `python -m manual_assistant.cli reindex-manuals`. Ele gera os embeddings de novo, o que
  é barato, e reaproveita as figuras já descritas, sem chamar o modelo com visão.
- A busca por código lê o texto de todos os trechos (`regexp_replace` + `LIKE`, sem índice).
  Com alguns milhares de trechos é rápido. Se o acervo crescer muito, cabe um índice de
  trigramas (`pg_trgm`) sobre o texto normalizado.
- Perguntas sobre vários modelos mandam mais trechos à IA (12 em vez de 6 para três
  modelos) e custam um pouco mais.
- O reconhecimento dos títulos de seção é heurístico: títulos sem numeração não são
  reconhecidos.
