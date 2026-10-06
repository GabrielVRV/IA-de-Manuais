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

## Rodando localmente (Windows / PowerShell)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
uvicorn --factory manual_assistant.main:create_app --reload
```

- Health check: <http://localhost:8000/api/v1/health>
- Documentação interativa (Swagger): <http://localhost:8000/api/docs>

## Verificações de qualidade

Os mesmos comandos rodam no CI do GitHub:

```powershell
ruff check .            # lint
ruff format --check .   # formatação (use `ruff format .` para corrigir)
mypy                    # tipagem estática (modo strict)
lint-imports            # regra de dependência da Clean Architecture
pytest --cov            # testes + cobertura
```
