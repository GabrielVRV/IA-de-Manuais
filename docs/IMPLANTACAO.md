# Guia de implantação: subindo o Assistente de Manuais

Passo a passo para subir o sistema em uma máquina ou servidor e testar com manuais reais.

- **API + banco:** rodam no **Docker**.
- **Tela (frontend):** roda no **XAMPP** ou, para um teste rápido, direto pelo Node.

> ⏱️ Tempo estimado: 20 a 30 minutos na primeira vez.

---

## 0. Pré-requisitos

| Item | Para quê | Como conferir |
| ---- | -------- | ------------- |
| **Git** | Baixar o código | `git --version` |
| **Docker** (Desktop ou Engine) **rodando** | API e banco de dados | `docker info` (precisa responder sem erro) |
| **Node.js 22+** | Gerar a tela (frontend) | `node --version` |
| **Internet de saída (porta 443)** | Falar com o Gemini | O servidor precisa acessar `generativelanguage.googleapis.com` |
| **Portas 8000 e 5432 livres** | API e banco | Se estiverem ocupadas, veja [Problemas comuns](#8-problemas-comuns) |

Você também vai precisar da **chave da API do Gemini**. Ela não está no repositório, por segurança.

---

## 1. Baixar o código

```powershell
git clone https://github.com/GabrielVRV/IA-de-Manuais.git
cd IA-de-Manuais
```

Se a pasta já existir de um teste anterior, basta atualizar com `git pull`.

---

## 2. Configurar os segredos (arquivos `.env`)

Os arquivos `.env` **nunca vão para o Git**. São dois arquivos, cada um com seu papel.

### 2.1 `.env` da raiz: banco de dados (usado pelo Docker)

```powershell
Copy-Item .env.example .env
notepad .env
```

Troque `DB_PASSWORD` por uma senha forte. Os outros valores podem ficar como estão.

### 2.2 `backend\.env`: IA, login e acesso

```powershell
Copy-Item backend\.env.example backend\.env
notepad backend\.env
```

Preencha **obrigatoriamente**:

| Variável | O que colocar |
| -------- | ------------- |
| `APP_GEMINI_API_KEY` | A chave da API do Gemini |
| `APP_AUTH_SECRET_KEY` | Uma chave aleatória. Gere com o comando abaixo e cole o resultado |
| `APP_CORS_ORIGINS` | O endereço da **tela** exatamente como aparece no navegador, sem a subpasta. Ex.: `http://NOME-DO-SERVIDOR,http://localhost:5173` |

Para gerar a `APP_AUTH_SECRET_KEY` no PowerShell:

```powershell
$b = New-Object byte[] 48; [Security.Cryptography.RNGCryptoServiceProvider]::Create().GetBytes($b); [Convert]::ToBase64String($b)
```

> As variáveis `APP_DB_*` desse arquivo só valem quando a API roda fora do Docker. Dentro
> do Docker, elas vêm automaticamente do `.env` da raiz.

---

## 3. Subir a API e o banco

```powershell
docker compose up -d --build
```

Na primeira vez, o Docker baixa as imagens e monta a API (alguns minutos). Depois, confira:

```powershell
docker compose ps
```

Os dois serviços (`manual-assistant-api` e `manual-assistant-db`) devem aparecer como **healthy**.

```powershell
curl.exe http://localhost:8000/api/v1/health
```

A resposta esperada é `{"status":"up",...,"components":{"database":"up"}}`. As tabelas do
banco são criadas sozinhas quando a API inicia.

---

## 4. Criar o seu usuário administrador

```powershell
docker compose exec api python -m manual_assistant.cli create-admin --username seu.login --name "Seu Nome"
```

O comando pede a senha **duas vezes**, sem mostrá-la na tela. Esse é o único usuário criado
por comando. Os demais você cria pela tela (passo 6).

---

## 5. Subir a tela (frontend)

Escolha **uma** das opções.

### Opção A: teste rápido na mesma máquina

```powershell
cd frontend
npm ci
npm run dev
```

Abra **<http://localhost:5173>** no Chrome ou no Edge. Use `localhost`, e não `127.0.0.1`.

### Opção B: XAMPP (para outras pessoas acessarem pela rede)

1. Gere e publique os arquivos (troque o destino se o XAMPP estiver em outro lugar):

   ```powershell
   cd frontend
   npm ci
   npm run deploy:xampp -- -Destino "C:\xampp\htdocs\ia-manuais"
   ```

2. Edite `C:\xampp\htdocs\ia-manuais\config.json` e aponte para a API:

   ```json
   { "apiBaseUrl": "http://NOME-DO-SERVIDOR:8000" }
   ```

   > ⚠️ **Use o mesmo nome de servidor no `config.json` e na barra do navegador.** Se a tela
   > abrir por `http://NOME-DO-SERVIDOR/ia-manuais` mas o `config.json` usar o IP
   > (`http://192.168.x.x:8000`), o navegador trata como sites diferentes e **não envia o
   > cookie de login**: você entra e é deslogado em seguida.

3. Confira se `http://NOME-DO-SERVIDOR` está em `APP_CORS_ORIGINS` no `backend\.env`. Se você
   alterou esse arquivo, recrie a API para aplicar:

   ```powershell
   docker compose up -d --force-recreate api
   ```

4. Acesse **`http://NOME-DO-SERVIDOR/ia-manuais/`**.

Nos próximos deploys, o script preserva o `config.json` que já está no servidor.

---

## 6. Usar o sistema

1. **Entre** com o administrador criado no passo 4.
2. **Manuais:** arraste os PDFs para a área tracejada, ou clique em **Escolher PDFs**. Cada
   manual aparece como *Na fila* → *Indexando…* → **Disponível**. A tela se atualiza sozinha.
3. **Chat:** faça perguntas. As fontes no fim de cada resposta abrem o PDF na página citada.
4. **Usuários:** crie contas para os colegas. Uma **senha provisória** é gerada e mostrada
   **uma única vez**: entregue-a à pessoa, que vai trocá-la no primeiro acesso.
   - **Usuário:** só usa o chat.
   - **Administrador:** também gerencia manuais e usuários.

### Roteiro sugerido para a demonstração (defender a chave paga)

1. Mostrar a tela de **Manuais** com alguns PDFs reais já indexados.
2. Fazer **3 a 4 perguntas reais**, das que a Engenharia mais recebe, e **clicar na fonte**
   para mostrar que a resposta veio do manual, na página citada.
3. Fazer uma pergunta **que não está nos manuais** (ex.: um valor que não consta): o sistema
   responde "não encontrei" em vez de inventar.
4. Mostrar um manual com **"Falhou: serviço externo"**. Isso é o **limite do plano
   gratuito**, e se resolve com a chave paga: basta clicar em **Reprocessar**.
5. Comparar o custo: no plano pago, cada pergunta custa uma fração de centavo, enquanto o
   Copilot exige uma licença por usuário.

---

## 7. Atualizar, parar e religar

| Ação | Comando (na raiz do projeto) |
| ---- | ---------------------------- |
| Atualizar para a versão mais nova | `git pull` → `docker compose up -d --build` → refazer o deploy da tela (5B.1) |
| Parar tudo (os dados ficam guardados) | `docker compose down` |
| Religar | `docker compose up -d` |
| Ver os logs da API | `docker compose logs api --tail 100` |

> ⚠️ `docker compose down -v` **apaga** o banco e os PDFs (o `-v` remove os volumes). Não use
> sem querer.

---

## 8. Problemas comuns

| Sintoma | Causa provável | Solução |
| ------- | -------------- | ------- |
| `docker compose up` falha baixando pacotes | Proxy corporativo | Configure o proxy no Docker Desktop (Settings → Resources → Proxies) |
| Erro de porta `5432` em uso | Já existe um PostgreSQL na máquina | No `.env` da raiz: `DB_PUBLISHED_PORT=5433` |
| Erro de porta `8000` em uso | Outro serviço usando a porta | No `docker-compose.yml`, troque `"8000:8000"` por `"8001:8000"` e use `:8001` no `config.json` |
| API não fica *healthy* | Variável obrigatória faltando | `docker compose logs api`: procure por `APP_AUTH_SECRET_KEY`, `APP_GEMINI_API_KEY` ou `DB_PASSWORD` |
| Tela mostra **"Offline"** no cabeçalho | API fora do ar, `config.json` errado ou CORS | Teste o passo 3; confira o `apiBaseUrl` e o `APP_CORS_ORIGINS` |
| Entra e **é deslogado em seguida** | Nome do servidor diferente na tela e no `config.json` | Use o mesmo nome nos dois (ver o alerta em 5B.2) |
| Manual **"Falhou: serviço externo"** | Limite ou cota do plano gratuito do Gemini | Aguarde a cota renovar (diária) ou use a chave paga, e clique em **Reprocessar** |
| Manual **"Falhou: ... OCR"** | PDF escaneado (imagem, sem texto) | Ainda não suportado; use a versão digital do PDF |
| Chat responde **"temporariamente indisponível"** | Gemini sobrecarregado ou sem cota | Tente em instantes; `docker compose logs api` mostra o motivo |
| Esqueceu a senha do administrador | — | Crie outro administrador com o comando do passo 4 (outro login) e redefina a senha pela tela |

---

## 9. Lembretes de segurança (antes de abrir para a empresa)

- **Chave paga:** no plano gratuito do Gemini, o Google pode usar o conteúdo enviado para
  treinar modelos. **Não use manuais confidenciais com a chave gratuita.**
- **HTTPS:** sem ele, as senhas trafegam abertas na rede interna. Antes da produção,
  instale um certificado interno e defina `APP_AUTH_COOKIE_SECURE=true`. Ver o
  [ADR 0007](adr/0007-autenticacao-e-controle-de-acesso.md).
- **Backup:** faça backup regular do volume do banco (`manual-assistant_db-data`) e do
  volume dos PDFs (`manual-assistant_manual-files`).
