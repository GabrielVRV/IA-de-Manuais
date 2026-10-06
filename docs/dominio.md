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

| Porta               | Responsabilidade                                      | Implementação prevista      |
| ------------------- | ----------------------------------------------------- | --------------------------- |
| `ManualRepository`  | Guardar os manuais e seus status                      | PostgreSQL (degrau 4)       |
| `DocumentParser`    | Extrair o texto do PDF, página a página               | PyMuPDF (degrau 5)          |
| `TextChunker`       | Dividir as páginas em trechos                         | Divisor próprio (degrau 5)  |
| `EmbeddingProvider` | Gerar embeddings de trechos e perguntas               | Gemini / OpenAI (degrau 6)  |
| `VectorStore`       | Indexar trechos e buscar por similaridade             | pgvector (degrau 4/5)       |
| `LanguageModel`     | Gerar a resposta a partir dos trechos encontrados     | Gemini / OpenAI (degrau 6)  |

Os adaptadores traduzem as exceções das bibliotecas para os erros da aplicação
(`UnreadableDocumentError`, `ExternalServiceError`). Assim, trocar o Gemini pela OpenAI
não altera nenhum caso de uso.
