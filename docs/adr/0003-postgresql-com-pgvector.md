# ADR 0003 — PostgreSQL com pgvector para dados e busca vetorial

- **Status:** aceito
- **Data:** 2026-10-06

## Contexto

O sistema precisa guardar os manuais (metadados e status) e os trechos com seus
embeddings, além de buscar trechos por similaridade semântica. Existem bancos vetoriais
dedicados (Qdrant, Chroma, Milvus), mas cada um é mais um serviço para operar no
servidor interno.

## Decisão

1. **Um único PostgreSQL com a extensão pgvector** para os dados relacionais e os vetores.
2. **Distância de cosseno com índice HNSW**, que mantém a busca rápida com milhares de
   trechos. A distância é convertida em relevância de 0 a 1 (`1 - distância`, com
   negativos limitados a 0).
3. **Embeddings de 1536 dimensões.** O Gemini (`output_dimensionality=1536`) e a OpenAI
   (`text-embedding-3-small`) geram vetores desse tamanho, então a troca de provedor não
   muda o esquema do banco. Fica abaixo do limite de 2000 dimensões do índice HNSW.
4. **SQLAlchemy 2 assíncrono + asyncpg**, com modelos ORM separados das entidades de
   domínio. O repositório converte de um para o outro.
5. **Migrações com Alembic, aplicadas ao iniciar o container.** Um teste garante que os
   modelos e as migrações estão sincronizados, e outro garante que as migrações podem ser
   revertidas.
6. **Testes de integração contra um PostgreSQL real** (Testcontainers), com a mesma imagem
   da produção. Um mock de banco não pegaria erros de SQL, de índice ou da extensão.

## Consequências

- Só um banco para operar, fazer backup e monitorar.
- A busca filtra por manuais indexados com um simples `JOIN`, sem duplicar o status no
  índice vetorial.
- Mudar o provedor para um modelo de outra dimensão exige uma nova migração e a
  reindexação de todos os manuais.
- Se o volume crescer muito (milhões de trechos), dá para migrar para um banco vetorial
  dedicado implementando a porta `VectorStore`, sem mexer nos casos de uso.
- Rodar os testes de integração localmente exige o Docker em execução. Sem ele, use
  `pytest -m "not db"`.
