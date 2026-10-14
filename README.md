<div align="center">

# 📘 Assistente de Manuais com IA

**Assistente interno que responde perguntas sobre manuais técnicos de equipamentos,
citando o manual e a página de origem de cada informação.**

[![Backend CI](https://github.com/GabrielVRV/IA-de-Manuais/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/GabrielVRV/IA-de-Manuais/actions/workflows/backend-ci.yml)
[![Frontend CI](https://github.com/GabrielVRV/IA-de-Manuais/actions/workflows/frontend-ci.yml/badge.svg)](https://github.com/GabrielVRV/IA-de-Manuais/actions/workflows/frontend-ci.yml)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)

</div>

---

## Sumário

- [Visão geral](#visão-geral)
- [Funcionalidades](#funcionalidades)
- [Como funciona](#como-funciona)
- [Arquitetura](#arquitetura)
- [Stack](#stack)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Começando](#começando)
- [Qualidade e CI](#qualidade-e-ci)
- [Roadmap](#roadmap)
- [Convenções](#convenções)
- [Documentação](#documentação)
- [Licença](#licença)

## Visão geral

Em empresas que operam muitos equipamentos, boa parte das dúvidas que chegam à Engenharia
já está respondida em algum manual — o difícil é encontrá-la. Este projeto resolve isso
com um **chat interno** que consulta os manuais e responde em linguagem natural, sempre
**indicando a fonte** (manual e página) para que a resposta possa ser conferida.

Um ponto central do projeto é o **custo**: em vez de uma licença de assistente de IA por
usuário, paga-se apenas o consumo da API do modelo de linguagem (**Gemini** ou **OpenAI**,
configurável), e só os trechos relevantes dos manuais são enviados a cada pergunta.

## Funcionalidades

- 💬 **Chat com respostas fundamentadas** — respostas geradas apenas a partir do conteúdo
  dos manuais, com resposta explícita de "não encontrei" quando a informação não existe.
- 📎 **Fontes clicáveis** — cada citação abre o PDF original diretamente na página citada.
- 🗂️ **Histórico de conversas** — o usuário retoma conversas anteriores.
- 📥 **Ingestão de PDFs** — upload pela interface ou importação em lote por script, com
  indexação em segundo plano.
- 🔄 **Sincronização com a pasta da Engenharia** — os manuais são lidos da pasta oficial
  (somente leitura), mantendo o acervo atualizado.
- 🔐 **Autenticação corporativa** — login com o usuário do TOTVS, liberação de acesso pelo
  administrador, sessões no banco e cookies `HttpOnly`.
- 🛠️ **Administração** — telas para gerenciar usuários e acompanhar o status dos manuais.
- 🎨 **Marca configurável** — nome, logo e cores definidos por instalação, sem rebuild.
- 🔌 **Provedor de IA intercambiável** — Gemini ou OpenAI, trocados por configuração.

## Como funciona

O assistente usa **RAG (Retrieval-Augmented Generation)**:

1. **Ingestão** — cada PDF é lido, dividido em trechos e transformado em *embeddings*
   (vetores que representam o significado do texto), armazenados no PostgreSQL com
   `pgvector`.
2. **Recuperação** — a pergunta do usuário também vira um vetor, e o banco devolve os
   trechos semanticamente mais próximos.
3. **Geração** — apenas esses trechos são enviados ao LLM, com instruções para responder
   somente com base neles e citar manual e página.

O resultado são respostas presas ao conteúdo real dos manuais, com custo baixo por pergunta.

## Arquitetura

```
 Navegador (rede interna)
        │  HTTP
        ▼
 ┌──────────────┐   HTTP/JSON   ┌───────────────────────────┐   HTTPS   ┌──────────────┐
 │ Frontend     │ ────────────▶ │ Backend (Docker)          │ ────────▶ │ API de LLM   │
 │ React (SPA)  │               │ Python + FastAPI          │           │ Gemini/OpenAI│
 └──────────────┘               │ Clean Architecture        │           └──────────────┘
                                │            │              │
                                └────────────┼──────────────┘
                                             ▼
                                ┌───────────────────────────┐
                                │ PostgreSQL + pgvector     │
                                │ (dados + índice vetorial) │
                                └───────────────────────────┘
```

O backend segue **Clean Architecture**, com as dependências sempre apontando para dentro:

```
presentation / infrastructure  ──▶  application  ──▶  domain
```

- **domain** — entidades e regras de negócio puras, sem frameworks.
- **application** — casos de uso e as portas (interfaces) de que eles precisam.
- **infrastructure** — adaptadores: banco, provedores de IA, leitura de PDF, TOTVS, armazenamento.
- **presentation** — API HTTP (rotas e schemas).

A regra de dependência é verificada automaticamente pelo `import-linter`: um import na
direção errada quebra o CI. As decisões de arquitetura estão registradas como
[ADRs](docs/adr/).

## Stack

| Camada          | Tecnologias                                                                 |
|-----------------|-----------------------------------------------------------------------------|
| **Backend**     | Python 3.11+, FastAPI, SQLAlchemy (async), Alembic, Pydantic, pypdfium2, Argon2 |
| **IA**          | Google Gemini, OpenAI (embeddings + geração)                                |
| **Banco**       | PostgreSQL 17 + pgvector                                                    |
| **Frontend**    | React 19, TypeScript, Vite, React Router, Zod                               |
| **Qualidade**   | Ruff, mypy (estrito), import-linter, pytest + Testcontainers, ESLint, Prettier, Vitest |
| **Infra**       | Docker, Docker Compose, GitHub Actions                                      |

## Estrutura do repositório

```
.
├── backend/               # API Python — ver backend/README.md
│   └── src/manual_assistant/
│       ├── domain/
│       ├── application/
│       ├── infrastructure/
│       └── presentation/
├── frontend/              # SPA React — ver frontend/README.md
├── docs/
│   ├── adr/               # Registros de decisões de arquitetura
│   ├── dominio.md         # Vocabulário do negócio
│   └── IMPLANTACAO.md     # Guia de implantação
├── docker-compose.yml
└── .github/workflows/     # CI do backend e do frontend
```

## Começando

> 📘 Passo a passo completo, com solução de problemas: **[docs/IMPLANTACAO.md](docs/IMPLANTACAO.md)**.

### Pré-requisitos

- [Docker](https://www.docker.com/) e Docker Compose
- [Node.js](https://nodejs.org/) 22+ (só para desenvolver a tela)
- Chave de API do **Gemini** ou da **OpenAI**

### 1. Tudo no Docker (tela + API + banco)

```bash
cp .env.example .env                  # defina DB_PASSWORD
cp backend/.env.example backend/.env  # configurações da API (chaves de IA, TOTVS...)
docker compose up -d --build
curl http://localhost:8084/api/v1/health
```

A tela fica em <http://localhost:8084>. O nginx do container `web` repassa `/api/` para a
API, então tela e API ficam no mesmo endereço, o que o cookie de login exige. As migrações
do banco são aplicadas automaticamente quando a API inicia.

### 2. Desenvolvimento da tela

```bash
cd frontend
npm install
npm run dev
```

Detalhes em [frontend/README.md](frontend/README.md).

## Qualidade e CI

Todo push e pull request passa por pipelines no GitHub Actions:

| Backend                                   | Frontend                          |
|-------------------------------------------|-----------------------------------|
| Lint e formatação (Ruff)                  | Lint (ESLint) e formatação (Prettier) |
| Tipagem estrita (mypy)                    | Checagem de tipos (TypeScript)    |
| Regra de dependência (import-linter)      | Testes (Vitest + Testing Library) |
| Testes com cobertura (pytest + Testcontainers) | Build de produção            |
| Build da imagem Docker                    |                                   |

## Roadmap

| #   | Etapa                                                                                | Status |
|-----|--------------------------------------------------------------------------------------|:------:|
| 1   | Fundação: repositório, esqueleto Clean Architecture, health check, Docker, CI        | ✅ |
| 2   | Frontend: React + Vite + TypeScript, configuração em runtime e deploy               | ✅ |
| 3   | Domínio: entidades (Manual, Trecho, Pergunta, Resposta) e portas                     | ✅ |
| 4   | Persistência: PostgreSQL + pgvector, migrações com Alembic                           | ✅ |
| 5   | Ingestão: leitura de PDF, divisão em trechos e armazenamento                         | ✅ |
| 6   | Provedores de IA (Gemini/OpenAI) e API de manuais (upload, listagem, exclusão)       | ✅ |
| 7   | Caso de uso "Perguntar" (RAG) com citação de manual e página                          | ✅ |
| 8   | Chat no frontend com fontes clicáveis (abre o PDF na página citada)                  | ✅ |
| 9a  | Usuários, login (cookie HttpOnly + Argon2) e proteção das rotas                      | ✅ |
| 9b  | Telas de login, usuários e acompanhamento dos manuais                                | ✅ |
| 9c  | Login com usuário do TOTVS, liberação pelo administrador e sessões no banco          | ✅ |
| 10a | Sincronização com a pasta de manuais da Engenharia (`sync-manuals`)                  | ✅ |
| 10b | Sincronização periódica na API e acompanhamento na tela de administração            | ⏳ |
| 11  | Observabilidade: logs estruturados, custo de tokens, feedback 👍/👎 nas respostas     | ⏳ |

## Convenções

- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/pt-br/)
  (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`, `ci:`).
- **Idioma:** código em inglês, documentação em português.
- **Integração:** todo commit em `main` precisa passar no CI.

## Documentação

| Documento                                      | Conteúdo                                  |
|------------------------------------------------|-------------------------------------------|
| [docs/IMPLANTACAO.md](docs/IMPLANTACAO.md)     | Guia de implantação passo a passo         |
| [docs/dominio.md](docs/dominio.md)             | Vocabulário do domínio e portas           |
| [docs/adr/](docs/adr/)                         | Decisões de arquitetura (ADRs)            |
| [backend/README.md](backend/README.md)         | Detalhes da API e execução local          |
| [frontend/README.md](frontend/README.md)       | Detalhes da SPA, configuração e deploy    |

## Licença

Distribuído sob a licença MIT. Veja [LICENSE](LICENSE).

---

<div align="center">

Desenvolvido por **[Gabriel](https://github.com/GabrielVRV)**

</div>
