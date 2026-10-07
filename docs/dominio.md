# Linguagem do domínio (glossário)

O código está em inglês e o negócio fala português. Esta tabela é o "dicionário" entre os
dois. Use sempre estes termos em conversas, issues e commits.

| Termo do negócio | No código        | Significado                                                                                                     |
| ---------------- | ---------------- | --------------------------------------------------------------------------------------------------------------- |
| Manual           | `Manual`         | Documento de um equipamento cadastrado no sistema. Tem um ciclo de vida de indexação.                           |
| Página           | `Page`           | Texto extraído de uma página do PDF original.                                                                   |
| Intervalo        | `PageRange`      | Páginas consecutivas de onde um trecho foi tirado (ex.: 12 a 13).                                               |
| Trecho           | `Chunk`          | Pedaço do manual com tamanho ideal para busca. É o que é indexado, encontrado e citado.                         |
| Relevância       | `ScoredChunk`    | Trecho encontrado numa busca, com nota de 0 (nada a ver) a 1 (idêntico) em relação à pergunta.                  |
| Pergunta         | `Question`       | Dúvida do usuário, de 3 a 2000 caracteres.                                                                      |
| Resposta         | `Answer`         | Texto gerado pela IA mais as citações que o embasam.                                                            |
| Citação          | `Citation`       | Manual e páginas usados na resposta. Vários trechos do mesmo manual viram uma única citação, com páginas unidas. |
| Embedding        | `Embedding`      | Vetor numérico que representa o significado de um texto; é o que permite buscar por significado.                |
| Indexar          | `mark_indexed()` | Processar o manual (ler, dividir em trechos, gerar embeddings) para que ele possa ser consultado.               |

## Ciclo de vida do manual

```
PENDENTE ──▶ PROCESSANDO ──▶ INDEXADO
                 │  ▲            │
                 ▼  └────────────┤  (reprocessar)
               FALHOU ───────────┘
```

- Só manuais **indexados** aparecem nas respostas.
- Não é possível iniciar um processamento enquanto outro está em andamento.
- Um manual indexado tem obrigatoriamente ao menos uma página e um trecho.
- Uma falha sempre registra o motivo (ex.: "PDF protegido por senha").

## Portas (o que o núcleo exige do mundo externo)

| Porta               | Responsabilidade                                  | Implementação                           |
| ------------------- | ------------------------------------------------- | --------------------------------------- |
| `ManualRepository`  | Guardar os manuais e seus status                  | `SqlAlchemyManualRepository` (Postgres) |
| `FileStorage`       | Guardar o PDF original de cada manual             | `LocalFileStorage` (pasta/volume)       |
| `DocumentParser`    | Extrair o texto do PDF, página a página           | `PdfiumDocumentParser` (pypdfium2)      |
| `TextChunker`       | Dividir as páginas em trechos                     | `LineChunker` (por linhas, sobreposto)  |
| `EmbeddingProvider` | Gerar embeddings de trechos e perguntas           | Gemini / OpenAI (degrau 6)              |
| `VectorStore`       | Indexar trechos e buscar por similaridade         | `PgVectorStore` (pgvector)              |
| `LanguageModel`     | Gerar a resposta a partir dos trechos encontrados | Gemini / OpenAI (degrau 6)              |

## Casos de uso

| Caso de uso             | O que faz                                                                   |
| ----------------------- | --------------------------------------------------------------------------- |
| `CheckHealthUseCase`    | Consolida a saúde da API e de suas dependências                              |
| `RegisterManualUseCase` | Valida o PDF (conteúdo e tamanho), guarda o arquivo e cadastra como pendente |
| `IndexManualUseCase`    | Lê, divide, gera embeddings e indexa; registra falhas no próprio manual      |
| `ListManualsUseCase`    | Lista os manuais, do mais recente para o mais antigo                         |
| `DeleteManualUseCase`   | Remove trechos, cadastro e arquivo original                                  |
| `AskQuestionUseCase`    | Busca os trechos relevantes, pede a resposta ao modelo e cita as fontes      |

## Como uma pergunta é respondida

1. A pergunta vira um embedding e os `APP_RAG_TOP_K` trechos mais parecidos são buscados
   (só de manuais indexados).
2. Os trechos vão numerados no prompt (`<trecho id="1" manual="..." paginas="12-13">`), com
   regras fixas: responder **somente** com base neles, citar o número de cada informação e
   responder `NAO_ENCONTRADO` quando a resposta não estiver lá.
3. As citações exibidas saem dos números que o modelo **realmente citou**. Vários trechos do
   mesmo manual viram uma citação só, com as páginas unidas.
4. Se a busca não encontrar nenhum trecho, o modelo nem é chamado (custo zero).

O texto dos manuais é tratado como **dado, não instrução**: um PDF com algo como "ignore
as regras" não altera o comportamento do assistente.

Os adaptadores traduzem as exceções das bibliotecas para os erros da aplicação
(`UnreadableDocumentError`, `ExternalServiceError`). Assim, trocar o Gemini pela OpenAI
não altera nenhum caso de uso.
