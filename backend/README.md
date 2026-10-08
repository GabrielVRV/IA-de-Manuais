# Backend — API do Assistente de Manuais

API em **Python + FastAPI** organizada em Clean Architecture.

## Estrutura

```
src/manual_assistant/
├── domain/           # Entidades e regras de negócio puras (sem frameworks)
├── application/      # Casos de uso + portas (interfaces) que eles exigem
│   ├── ports/
│   └── use_cases/
├── infrastructure/   # Adaptadores das portas: banco, LLM, PDFs, configuração
├── presentation/     # Adaptadores de entrada: API HTTP (rotas, schemas)
│   └── http/
└── main.py           # Raiz de composição: conecta as camadas
```

**Regra de dependência:** as setas apontam sempre para dentro
(`presentation`/`infrastructure` → `application` → `domain`). Ela é verificada
automaticamente pelo `import-linter`; um import na direção errada quebra o CI.
Um segundo contrato proíbe o núcleo (`domain` e `application`) de importar frameworks
(FastAPI, Pydantic...).

O vocabulário do domínio e as portas estão descritos em [docs/dominio.md](../docs/dominio.md).

## Rodando localmente (Windows / PowerShell)

O banco roda no Docker. A API pode rodar fora dele, com recarga automática:

```powershell
# Na raiz do projeto: sobe só o PostgreSQL
Copy-Item .env.example .env          # defina DB_PASSWORD
docker compose up -d db

# Em backend/
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env          # APP_DB_PASSWORD igual ao DB_PASSWORD da raiz
python -m manual_assistant.infrastructure.persistence.migrate
uvicorn --factory manual_assistant.main:create_app --reload
```

- Health check: <http://localhost:8000/api/v1/health>
- Documentação interativa (Swagger): <http://localhost:8000/api/docs>

## Usuários e acesso

Todas as rotas exigem login, exceto `/api/v1/health` e `/api/v1/auth/login`. Detalhes no
[ADR 0007](../docs/adr/0007-autenticacao-e-controle-de-acesso.md).

| Perfil  | Pode                                                   |
| ------- | ------------------------------------------------------ |
| `user`  | Usar o chat e abrir os manuais citados                 |
| `admin` | Tudo do `user` + enviar/reprocessar/excluir manuais e gerenciar usuários |

**Primeiro administrador** (no servidor; a senha é pedida sem aparecer na tela):

```powershell
docker compose exec api python -m manual_assistant.cli create-admin --username seu.login --name "Seu Nome"
```

| Método e rota                              | O que faz                                          |
| ------------------------------------------ | -------------------------------------------------- |
| `POST /api/v1/auth/login`                  | Entra; a sessão fica num cookie HttpOnly           |
| `POST /api/v1/auth/logout`                 | Sai                                                |
| `GET /api/v1/auth/me`                      | Usuário da sessão                                  |
| `POST /api/v1/auth/change-password`        | Troca a própria senha                              |
| `GET/POST /api/v1/users`                   | Lista / cria usuários com senha provisória (admin) |
| `POST /api/v1/users/{id}/reset-password`   | Define uma nova senha provisória (admin)           |
| `PATCH /api/v1/users/{id}`                 | Ativa/desativa ou muda o perfil (admin)            |

Pelo Swagger (`/api/docs`), faça o `POST /auth/login` primeiro: o navegador guarda o
cookie e as demais chamadas passam a funcionar.

## API de manuais

| Método e rota                         | O que faz                                                  |
| ------------------------------------- | ---------------------------------------------------------- |
| `POST /api/v1/manuals`                | Envia um PDF (`file`, `title` opcional). Responde **202** e indexa em segundo plano |
| `GET /api/v1/manuals`                 | Lista os manuais com o status de cada um                   |
| `GET /api/v1/manuals/{id}`            | Consulta um manual (use para acompanhar a indexação)       |
| `POST /api/v1/manuals/{id}/reindex`   | Reprocessa (após falha ou troca de provedor de IA)         |
| `DELETE /api/v1/manuals/{id}`         | Exclui o manual, seus trechos e o PDF original             |
| `POST /api/v1/questions`              | Responde `{"question": "..."}` com o texto, `found` e as citações (manual e páginas) |

Status de um manual: `pending → processing → indexed | failed`. Em caso de falha, o
motivo aparece em `failure_reason`. Se a API reiniciar no meio de uma indexação, o manual
é marcado como falha na próxima inicialização e pode ser reprocessado.

O jeito mais fácil de testar é pelo Swagger (`/api/docs`): abra `POST /manuals`, clique
em *Try it out* e escolha um PDF.

## Provedores de IA

Configurados no `.env` (ver `.env.example` e o [ADR 0005](../docs/adr/0005-provedores-de-ia.md)):

```ini
APP_AI_PROVIDER=gemini        # ou openai
APP_GEMINI_API_KEY=...        # a API não inicia sem a chave do provedor escolhido
```

> Use o **plano pago** da API. No plano gratuito, os trechos dos manuais enviados podem
> ser usados pelo provedor para treinar modelos.

## Banco de dados e migrações

- O esquema é versionado com **Alembic** em
  `src/manual_assistant/infrastructure/persistence/migrations/`.
- No container, as migrações pendentes são aplicadas automaticamente na inicialização.
- Para criar uma migração depois de alterar `models.py`:

  ```powershell
  alembic revision --autogenerate -m "descricao da mudanca"
  ```

  Revise o arquivo gerado. Um teste falha se os modelos e as migrações divergirem.

## Verificações de qualidade

Os mesmos comandos rodam no CI do GitHub:

```powershell
ruff check .            # lint
ruff format --check .   # formatação (use `ruff format .` para corrigir)
mypy                    # tipagem estática (modo strict)
lint-imports            # regra de dependência da Clean Architecture
pytest --cov                       # testes + cobertura (precisa do Docker em execução)
pytest -m "not db and not live"    # só os testes que não dependem de banco nem de IA real
pytest -m live                     # chama a API real do provedor de IA (gasta cota)
```

- Os testes marcados com `db` sobem um PostgreSQL descartável via
  [Testcontainers](https://testcontainers.com/), com a mesma imagem da produção.
- Os testes `live` não rodam por padrão nem no CI. Use-os para validar uma chave nova ou
  uma troca de modelo.
