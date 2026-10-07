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
pytest --cov            # testes + cobertura (precisa do Docker em execução)
pytest -m "not db"      # só os testes que não dependem do banco
```

Os testes marcados com `db` sobem um PostgreSQL descartável via
[Testcontainers](https://testcontainers.com/), com a mesma imagem da produção.
