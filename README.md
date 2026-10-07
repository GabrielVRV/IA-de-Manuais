# Assistente de Manuais (IA)

Assistente interno que responde perguntas sobre os manuais dos equipamentos da empresa,
**citando o manual e a página de origem**. O objetivo é tirar da Engenharia as dúvidas
repetitivas dos demais setores, sem exigir licença de Copilot para cada usuário: pagamos
apenas pelo consumo da API de LLM (Gemini ou OpenAI).

## Arquitetura

```
 Navegador (rede interna)
        │  HTTP
        ▼
 ┌──────────────┐   HTTP/JSON   ┌───────────────────────────┐   HTTPS   ┌──────────────┐
 │ Frontend     │ ────────────▶ │ Backend (Docker)          │ ────────▶ │ API de LLM   │
 │ React (XAMPP)│               │ Python + FastAPI          │           │ Gemini/OpenAI│
 └──────────────┘               │ Clean Architecture        │           └──────────────┘
                                │   └─ Banco vetorial (RAG) │
                                └───────────────────────────┘
```

A técnica usada é **RAG (Retrieval-Augmented Generation)**: os manuais são quebrados em
trechos, indexados por significado (embeddings) e, a cada pergunta, só os trechos mais
relevantes são enviados ao LLM. Assim a resposta fica presa ao conteúdo dos manuais e o
custo por pergunta fica baixo.

Decisões de arquitetura ficam registradas em [`docs/adr/`](docs/adr/) e o vocabulário do
negócio em [`docs/dominio.md`](docs/dominio.md).

## Estrutura do repositório

```
.
├── backend/               # API Python (ver backend/README.md)
├── frontend/              # SPA React (ver frontend/README.md)
├── docs/adr/              # Registros de decisões de arquitetura
├── docker-compose.yml
└── .github/workflows/     # CI
```

## Roadmap (degraus)

| #  | Degrau                                                                              | Status |
|----|-------------------------------------------------------------------------------------|--------|
| 1  | Fundação: repositório, esqueleto Clean Architecture, health check, Docker, CI       | ✅     |
| 2  | Frontend: React + Vite + TypeScript, consumindo o health check; build para o XAMPP  | ✅     |
| 3  | Domínio: entidades (Manual, Trecho, Pergunta, Resposta) e portas (LLM, vetores...)  | ✅     |
| 4  | Persistência: PostgreSQL + pgvector no compose, migrações com Alembic               | ✅     |
| 5  | Ingestão: upload de PDF → extração → divisão em trechos → embeddings → indexação    | ⏳     |
| 6  | Adaptadores de LLM: Gemini e OpenAI, selecionáveis por variável de ambiente         | ⏳     |
| 7  | Caso de uso "Perguntar" (RAG) com citação de manual e página                         | ⏳     |
| 8  | Chat no frontend com resposta em streaming                                          | ⏳     |
| 9  | Autenticação e área administrativa de manuais                                       | ⏳     |
| 10 | Observabilidade: logs estruturados, custo de tokens, feedback 👍/👎 nas respostas    | ⏳     |

## Convenções

- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/pt-br/)
  (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`, `ci:`).
- **Código em inglês, documentação em português.**
- Todo commit em `main` precisa passar no CI: lint, tipagem estrita, regra de
  dependência entre camadas e testes.

## Rodando o projeto

**Backend + banco (Docker):**

```bash
cp .env.example .env                  # defina DB_PASSWORD
cp backend/.env.example backend/.env  # configurações da API (CORS, chaves de IA...)
docker compose up -d --build
curl http://localhost:8000/api/v1/health
```

As migrações do banco são aplicadas automaticamente quando a API inicia.

**Frontend (XAMPP):**

```powershell
cd frontend
npm install
npm run deploy:xampp -- -Destino "C:\xampp\htdocs\ia-manuais"
```

Depois, ajuste o `config.json` publicado para o endereço da API e inclua o endereço do
frontend em `APP_CORS_ORIGINS`, no `backend/.env`. Detalhes em
[frontend/README.md](frontend/README.md).
