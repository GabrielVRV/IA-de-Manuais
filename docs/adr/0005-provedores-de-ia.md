# ADR 0005 — Provedores de IA (Gemini e OpenAI)

- **Status:** aceito
- **Data:** 2026-10-06

## Contexto

Precisamos de embeddings (para a busca semântica) e de um modelo de linguagem (para
redigir as respostas). O objetivo do projeto é custo baixo e liberdade para trocar de
fornecedor.

## Decisão

1. **Dois adaptadores para as mesmas portas** (`EmbeddingProvider`, `LanguageModel`):
   Gemini (`google-genai`) e OpenAI (`openai`). A escolha é feita em `APP_AI_PROVIDER`, e
   nenhum caso de uso muda ao trocar.
2. **Gemini como padrão**, com estes modelos (todos configuráveis por variável de ambiente):
   - **Embeddings: `gemini-embedding-001` com 1536 dimensões.** Em teste real, o
     `gemini-embedding-2` combinou todos os textos de uma chamada num **único vetor**
     (é multimodal), o que impede o envio em lote. Indexar um manual exigiria centenas de
     chamadas.
   - **Respostas: `gemini-3.5-flash` com `thinking_budget=0`.** Em teste real, os modelos
     Gemini 3.x "pensam" por padrão: 200 a 300 tokens de raciocínio para uma frase. Esses
     tokens são **cobrados** e consomem o limite de saída, chegando a **cortar a
     resposta**. Responder a partir de trechos já selecionados não precisa de raciocínio.
     O `thinking_level=LOW` não basta no 3.5 Flash, só o orçamento 0 desliga.
3. **Repetição automática** em erros 429/5xx (até 4 tentativas, com espera crescente). Em
   teste real, o Gemini devolveu `503 high demand` várias vezes seguidas e respondeu
   depois de algumas tentativas.
4. **Os erros dos SDKs viram `ExternalServiceError`**, com mensagens que identificam a
   causa (chave inválida, cota, indisponibilidade) sem expor a chave.
5. **Tokens de raciocínio contam como saída** no `TokenUsage`, porque são cobrados assim.
   Essa é a base do controle de custos do degrau 10.
6. **Três níveis de teste:**
   - **Unitários sem rede:** o HTTP do SDK é interceptado, e o teste confere o que vai na
     requisição.
   - **Ponta a ponta com banco real e IA falsa:** roda no CI.
   - **Testes `live`:** chamam a API real e só rodam com `pytest -m live`.

## Consequências

- **A dimensão 1536 vale para os dois provedores.** O Gemini a gera via
  `output_dimensionality` e a OpenAI via `dimensions`. Trocar de provedor exige
  **reindexar** os manuais (`POST /manuals/{id}/reindex`), porque os vetores de
  provedores diferentes não são comparáveis. O esquema do banco não muda.
- **O SDK 3.x da OpenAI usa o `httpx2`, e o do Gemini usa o `httpx`.** Cada adaptador
  intercepta o seu nos testes.
- **Modelos de raciocínio da OpenAI** (`o*`, `gpt-5*`) recusam `temperature`. O adaptador
  omite o parâmetro para eles.
- **Os nomes de modelos mudam com frequência.** Por isso eles ficam no `.env`, e os testes
  `live` servem para validar uma troca antes de levá-la para produção.
