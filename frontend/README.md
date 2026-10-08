# Frontend — Assistente de Manuais

SPA em **React + TypeScript + Vite**, publicada como arquivos estáticos no XAMPP.

## Estrutura

```
src/
├── main.tsx                  # Raiz de composição: lê config, cria adaptadores e injeta
├── app/                      # Casca da aplicação (layout, telas de erro, config de runtime)
├── features/
│   ├── chat/                 # Conversa com os manuais (perguntas, respostas, fontes)
│   └── health/               # Uma pasta por funcionalidade, cada uma com suas camadas:
│       ├── domain/           #   tipos e portas (interfaces), TypeScript puro
│       ├── infrastructure/   #   adaptadores HTTP que implementam as portas
│       └── presentation/     #   componentes e hooks React
├── shared/                   # Código reutilizável e sem regra de negócio (cliente HTTP)
└── styles/                   # Tokens de design (cores, espaçamentos) e estilos globais
```

**Regra de dependência** (verificada pelo ESLint, quebra o CI se violada):

- `domain` não importa React, bibliotecas nem outras camadas;
- `infrastructure` não conhece a interface (`presentation`);
- `presentation` não conhece a `infrastructure`: recebe as implementações por contexto
  React, montadas em `main.tsx`;
- `shared` não depende de nenhuma funcionalidade.

## Funcionalidades

- **Chat:** pergunta em linguagem natural; a resposta vem formatada (Markdown seguro) e
  com as **fontes clicáveis**, que abrem o PDF do manual na página citada. "Não encontrei"
  tem um visual próprio. Enter envia e Shift+Enter quebra linha.
- **Status do servidor** no cabeçalho (clique para verificar de novo).

Decisões e limitações conhecidas (sem streaming, sem memória de conversa) estão no
[ADR 0006](../docs/adr/0006-chat-no-frontend.md).

## Desenvolvimento

```powershell
cd frontend
npm install
npm run dev        # http://localhost:5173 (a API precisa estar rodando na porta 8000)
```

| Comando                 | O que faz                         |
| ----------------------- | --------------------------------- |
| `npm run typecheck`     | Checagem de tipos (strict)        |
| `npm run lint`          | ESLint + regra de dependência     |
| `npm run format`        | Formata o código com Prettier     |
| `npm test`              | Testes (Vitest + Testing Library) |
| `npm run test:coverage` | Testes com relatório de cobertura |
| `npm run build`         | Build de produção em `dist/`      |

## Configuração em tempo de execução

O endereço da API **não** é embutido no build. Ele é lido de `config.json`, ao lado do
`index.html`:

```json
{ "apiBaseUrl": "http://servidor:8000" }
```

Assim o mesmo build serve para qualquer ambiente: no servidor, basta editar esse arquivo.
O endereço do frontend também precisa estar em `APP_CORS_ORIGINS` no `.env` do backend.

## Deploy no XAMPP

```powershell
npm run deploy:xampp -- -Destino "C:\xampp\htdocs\ia-manuais"
```

O script gera o build, copia para o destino e **preserva o `config.json` que já está no
servidor**. No primeiro deploy, edite o `config.json` criado no destino.

O `.htaccess` incluído desativa o cache do `index.html` e do `config.json` (um novo deploy
aparece na hora para todos) e mantém os arquivos com hash em cache por tempo indeterminado.
Para isso, o `mod_headers` precisa estar habilitado no Apache (já vem ativo por padrão no
XAMPP).
