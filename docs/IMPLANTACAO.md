# Guia de implantação: subindo o Assistente de Manuais

Passo a passo para subir o sistema em uma máquina ou servidor e testar com manuais reais.

Tudo roda no **Docker**, em três containers:

- **`web`:** a tela, servida por um nginx que também repassa `/api/` para a API. É o único
  endereço que os usuários abrem (porta **8084**).
- **`api`:** a API (porta 8000, usada só para diagnóstico).
- **`db`:** o banco de dados.

> Tela e API ficam **no mesmo endereço** de propósito: o navegador só envia o cookie de
> login quando as duas estão no mesmo servidor. Com a tela em outra máquina (ex.: no XAMPP
> de outro servidor), a pessoa entra e é deslogada em seguida.

> ⏱️ Tempo estimado: 20 a 30 minutos na primeira vez.

---

## 0. Pré-requisitos

| Item | Para quê | Como conferir |
| ---- | -------- | ------------- |
| **Git** (opcional) | Baixar o código (ou copie a pasta, ver o passo 1) | `git --version` |
| **Docker** (Desktop ou Engine) **rodando** | Tela, API e banco de dados | `docker info` (precisa responder sem erro) |
| **Internet de saída (porta 443)** | Falar com o Gemini e baixar os pacotes no build | O servidor precisa acessar `generativelanguage.googleapis.com`, o Docker Hub, o PyPI e o npm |
| **Portas 8084, 8000 e 5432 livres** | Tela, API e banco | Se estiverem ocupadas, veja [Problemas comuns](#8-problemas-comuns) |
| **Porta 8084 liberada no firewall** | Os usuários abrirem a tela pela rede | Abrir `http://IP-DO-SERVIDOR:8084` de outra máquina |

Você também vai precisar da **chave da API do Gemini**. Ela não está no repositório, por segurança.

---

## 1. Levar o código para o servidor

Com Git:

```powershell
git clone https://github.com/GabrielVRV/IA-de-Manuais.git
cd IA-de-Manuais
```

Se a pasta já existir de um teste anterior, basta atualizar com `git pull`.

Sem Git (ex.: copiando pelo WinSCP): copie a pasta do projeto **sem** as pastas geradas
ou locais (`.git`, `frontend/node_modules`, `frontend/dist`, `backend/.venv`). Nas
atualizações, **não sobrescreva** os `.env` do servidor (`.env` e `backend/.env`).

> A pasta `frontend/public/brand/` (logo e cores da empresa) não está no Git. Se for usada,
> copie-a para o servidor antes do build.

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
| `APP_CORS_ORIGINS` | O endereço da **tela** como aparece no navegador. Ex.: `http://IP-DO-SERVIDOR:8084`. Como a tela chama a API pelo mesmo endereço, quase não é usado, mas deixe certo |
| `APP_AD_SERVER_URLS` | O controlador de domínio, para os usuários entrarem com o usuário de rede. Ex.: `ldaps://dc01.empresa.local` (vários: separados por vírgula). Vazio = só entram usuários criados aqui |
| `APP_AD_DOMAIN` | O domínio. Ex.: `empresa.local` (o login vira `fulano@empresa.local`) |
| `APP_AD_BASE_DN` | Onde procurar os usuários. Ex.: `DC=empresa,DC=local` (é o "BaseDN" do GLPI) |

Opcionais: `APP_AD_REQUIRED_GROUP_DN` (só quem está nesse grupo entra), `APP_AD_START_TLS`
(para `ldap://`) e `APP_AD_CA_CERT_FILE` (certificado da CA interna, ver abaixo).
`APP_TIMEZONE` (padrão `America/Sao_Paulo`) define o fuso do relatório de consumo e do
horário da sincronização agendada; só mude se o servidor atender outro fuso. Os
valores podem ser copiados da configuração LDAP do GLPI. O backend **não precisa** da
conta de serviço do GLPI: ele autentica como o próprio usuário.

> **Certificado do AD:** com `ldaps://`, a API confere o certificado do controlador. Se ele
> foi emitido por uma CA interna, peça à TI o certificado da CA em PEM (`.pem` ou `.crt`
> em Base64) e salve-o em `backend\certs\ca-ad.pem`. O `docker-compose.yml` já monta essa
> pasta no container e aponta `APP_AD_CA_CERT_FILE` para ela. A pasta fica fora do git.
> Num computador do domínio, a CA costuma estar no Windows e dá para exportá-la assim:
>
> ```powershell
> $c = Get-ChildItem Cert:\LocalMachine\Root | Where-Object Subject -like '*NOME-DA-CA*'
> "-----BEGIN CERTIFICATE-----`n$([Convert]::ToBase64String($c.RawData, 'InsertLineBreaks'))`n-----END CERTIFICATE-----" | Set-Content -Encoding ascii backend\certs\ca-ad.pem
> ```
>
> Use em `APP_AD_SERVER_URLS` o **nome** do servidor que está no certificado (ex.:
> `ldaps://dc01.empresa.local`), não o IP: com o IP, o certificado não confere.

> O `backend\.env` nunca vai para o GitHub (está no `.gitignore`): é nele que ficam a chave
> do Gemini e os dados do AD.

> As variáveis `APP_DB_*` desse arquivo só valem quando a API roda fora do Docker. Dentro
> do Docker, elas vêm automaticamente do `.env` da raiz.

---

## 3. Subir a tela, a API e o banco

```powershell
docker compose up -d --build
```

Na primeira vez, o Docker baixa as imagens e monta a API e a tela (alguns minutos). Depois, confira:

```powershell
docker compose ps
```

Os três serviços (`manual-assistant-web`, `manual-assistant-api` e `manual-assistant-db`)
devem aparecer como **healthy**.

```powershell
curl.exe http://localhost:8084/api/v1/health
```

A resposta esperada é `{"status":"up",...,"components":{"database":"up"}}`. As tabelas do
banco são criadas sozinhas quando a API inicia.

---

## 4. Criar o seu usuário administrador

```powershell
docker compose exec api python -m manual_assistant.cli create-admin --username seu.login --name "Seu Nome"
```

O comando pede a senha **duas vezes**, sem mostrá-la na tela. Ele é um usuário **local**:
entra com essa senha mesmo se o AD estiver fora do ar, então guarde-o como acesso de
emergência. Os colegas entram com o usuário de rede (passo 6).

Se quiser que o seu próprio login passe a usar a senha de rede, crie antes um segundo
administrador local de emergência e então rode, mantendo o perfil de administrador:

```powershell
docker compose exec api python -m manual_assistant.cli use-ad --username seu.login
```

**Vindo do TOTVS:** quem entrava pelo TOTVS passa a entrar pelo AD automaticamente, com o
mesmo login, perfil e histórico. Se o login de rede for diferente (ex.: `gviaro` no
TOTVS e `gabriel.viaro` na rede), ajuste **antes** de a pessoa entrar, para não surgir um
cadastro novo:

```powershell
docker compose exec api python -m manual_assistant.cli use-ad --username gviaro --ad-login gabriel.viaro
```

---

## 5. Abrir a tela

A tela sobe junto no passo 3. Acesse **`http://IP-DO-SERVIDOR:8084/`** (ex.:
`http://10.10.1.24:8084/`). Não há `config.json` para editar: a tela chama a API pelo
próprio endereço, e o container `web` repassa para a API.

Para trocar a porta, defina `WEB_PUBLISHED_PORT` no `.env` da raiz e rode
`docker compose up -d`.

> **Desenvolvimento:** para mexer na tela com recarga automática, rode `npm ci` e
> `npm run dev` em `frontend/` e abra **<http://localhost:5173>** (use `localhost`, e não
> `127.0.0.1`).

---

## 6. Usar o sistema

As telas de administração ficam no botão **Administração**, no topo, com um menu ao lado:
**Usuários**, **Acessos**, **Consumo** e **Configurações** (gerais) e **Manuais** (do
Assistente de Engenharia).

1. **Entre** com o administrador criado no passo 4.
2. **Manuais:** arraste os PDFs para a área tracejada, ou clique em **Escolher PDFs**. Cada
   manual aparece como *Na fila* → *Indexando…* → **Disponível**. A tela se atualiza sozinha.
3. **Chat:** faça perguntas. As fontes no fim de cada resposta abrem o PDF na página citada.
4. **Usuários:** os colegas entram com o **usuário e a senha de rede** (os do Windows). No primeiro
   acesso eles já aparecem na tela **Usuários** e usam os assistentes liberados para todos
   (veja **Acessos**, abaixo). O perfil define o que mais a pessoa pode fazer:
   - **Usuário:** usa o chat.
   - **Administrador:** também acessa a Administração e usa todos os assistentes.

   A coluna **Acesso** mostra quais assistentes cada pessoa usa. Em **Gerenciar**, escolha
   para cada assistente se ela segue o **padrão**, fica **liberada** ou fica **bloqueada**,
   e clique em **Salvar acessos**. Para tirar alguém do sistema inteiro, clique em
   **Desativar**. Para limitar quem entra, use o grupo do AD (`APP_AD_REQUIRED_GROUP_DN`).
   Quem não tem usuário de rede pode ser criado na Quem não tem usuário de rede pode ser criado na
   própria tela, como **usuário local**: uma **senha provisória** é gerada e mostrada
   **uma única vez**, e a pessoa a troca no primeiro acesso.

   A sessão fica aberta: só pede login de novo depois de **7 dias sem uso**, ou **30 dias**
   depois do último login. Senha trocada ou usuário bloqueado no AD só valem no próximo
   login. Para cortar o acesso na hora, desative o usuário aqui.
5. **Acessos** (administrador): para cada assistente do chat, escolha o acesso padrão:
   - **Liberado para todos:** é o padrão, e todo usuário ativo usa.
   - **Só para quem for liberado:** só administradores e quem for liberado na tela
     Usuários.

   Em **Como pedir acesso**, escreva o que fazer (ex.: "Abra um chamado no GLPI pedindo
   acesso ao Assistente de Engenharia."). Quem não tem acesso vê esse texto no lugar do
   chat. Antes de restringir, libere na tela Usuários quem precisa continuar usando.
6. **Configurações** (administrador), sem mexer no `.env` nem reiniciar:
   - **Limite de perguntas** por usuário, por minuto e em 24 horas (padrão: 10 e 200;
     `0` desliga). Quem passa do limite recebe um aviso no chat, e a pergunta não gasta
     tokens.
   - **Preço dos modelos**, em dólares por milhão de tokens, copiado da tabela de preços do
     provedor. Os modelos já usados aparecem na lista; sem preço, a tela de Consumo mostra
     só os tokens.
   - **Retenção do consumo** (padrão: 12 meses).
7. **Consumo** (administrador): perguntas, tokens e custo estimado do período, por dia,
   **por usuário** (quem mais usou primeiro) e por modelo. Só números: as perguntas não
   aparecem. Vale avisar os usuários de que o uso é registrado para controle de custo.

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

### Sincronizar com a pasta de manuais da Engenharia

Em vez de enviar os PDFs pela tela, o sistema pode importar direto da pasta de rede da
Engenharia. A pasta **só é lida**, nunca alterada.

1. A pasta precisa estar **montada no servidor do Docker** (no `/etc/fstab`, com `ro` e uma
   conta de serviço somente leitura). O padrão é `/mnt/Manual`; se for outro caminho,
   defina `MANUAIS_HOST_DIR` no `.env` da raiz e rode `docker compose up -d`.
2. Confira se o container enxerga os manuais:

   ```bash
   docker compose exec api ls /mnt/manuais
   ```

3. Na tela **Manuais** (administrador), no quadro **Pasta de manuais da Engenharia**:
   - **Verificar** mostra o que seria feito (novos, revisões novas, a remover, ignorados),
     **sem alterar nada nem gastar API**.
   - **Sincronizar** aparece depois da verificação e pede confirmação, informando quantos
     manuais serão indexados. Ela roda **em segundo plano**: dá para sair da tela, e o
     andamento e o resultado (inclusive as falhas) aparecem no quadro.

   Uma sincronização por vez. O resumo da última some se a API reiniciar (os manuais ficam).
   - **Sincronizar automaticamente todo dia às…**: marque, escolha o horário (ex.: `00:00`,
     no horário de Brasília) e clique em **Salvar agendamento**. A próxima execução aparece
     logo abaixo. Se o servidor estiver desligado no horário, ela roda quando ele voltar;
     se não conseguir começar (pasta fora do ar), o motivo aparece no quadro e ela tenta
     de novo no dia seguinte.

O mesmo também pode ser feito pelo comando, útil para testar com poucos manuais:

```bash
docker compose exec api python -m manual_assistant.cli sync-manuals --dry-run --verbose
```

```bash
docker compose exec -it api python -m manual_assistant.cli sync-manuals --limit 3
```

Só entram os PDFs que estão **direto** dentro de cada subpasta (`ARMAZENAGEM/`,
`PROTEÍNA/`...). As subpastas de dentro delas (`Versões Anteriores`, `Versões Obsoletas`)
não são lidas. Sincronize de novo sempre que quiser atualizar: só o que mudou é
reindexado, e o manual que saiu da pasta é removido do sistema.

### Figuras e manuais escaneados (descrição por IA)

O texto do PDF não diz o que mostram as fotos, os diagramas e os desenhos técnicos. Com a
descrição de figuras ([ADR 0014](adr/0014-descricao-de-figuras-por-ia.md)), cada página com
figuras é enviada como imagem ao modelo com visão, e a descrição vira um trecho pesquisável,
citado pela página. Os PDFs escaneados também passam a ser lidos.

> 💰 É **uma chamada de IA por página com figuras**, e mais da metade das páginas desses
> manuais tem figuras. O que já foi descrito fica guardado e nunca é pago de novo. Comece
> com poucos manuais e confira as respostas no chat antes de seguir.

Vem **desligada**: quem decide, a cada importação, é o administrador, na tela **Manuais**:

| Onde | Como |
| ---- | ---- |
| Enviar PDFs | Marque **Descrever as figuras com IA** antes de escolher os arquivos |
| Um manual já cadastrado | Botão **Descrever figuras** na linha dele. Mostra quantas páginas têm figuras e quantas faltam antes de confirmar. Num manual indexado, só acrescenta as figuras (o texto não é refeito); num com falha (ex.: escaneado), reprocessa com as figuras |
| Sincronizar | Depois de **Verificar**, marque **Descrever as figuras dos manuais novos e alterados** |
| Sincronização automática | Marque **Na sincronização automática, descrever também as figuras** e salve o agendamento |

Enquanto as figuras de um manual são descritas, a linha dele mostra **Descrevendo
figuras…** com o número de páginas já feitas. Se parar no meio (ex.: cota da IA), o motivo
aparece ali, e um novo clique continua de onde parou.

Pelo comando, para vários manuais já indexados de uma vez (`--dry-run` só conta as páginas):

```bash
docker compose exec -it api python -m manual_assistant.cli describe-figures --limit 3
```

Na sincronização pelo comando, use `sync-manuals --figures`.

Depois de uma atualização que muda a divisão em trechos (ex.: a ADR 0015, que pôs o título
da seção e do manual nos trechos), reindexe todos os manuais. Isso só gera embeddings de
novo e reaproveita as figuras já descritas:

```bash
docker compose exec -it api python -m manual_assistant.cli reindex-manuals
```

---

## 7. Atualizar, parar e religar

| Ação | Comando (na raiz do projeto) |
| ---- | ---------------------------- |
| Atualizar para a versão mais nova | `git pull` (ou copiar os arquivos novos, sem sobrescrever os `.env`) → `docker compose up -d --build` |
| Parar tudo (os dados ficam guardados) | `docker compose down` |
| Religar | `docker compose up -d` |
| Ver os logs da API | `docker compose logs api --tail 100` |
| Ver os logs da tela | `docker compose logs web --tail 100` |

> ⚠️ `docker compose down -v` **apaga** o banco e os PDFs (o `-v` remove os volumes). Não use
> sem querer.

---

## 8. Problemas comuns

| Sintoma | Causa provável | Solução |
| ------- | -------------- | ------- |
| `docker compose up` falha baixando pacotes | Proxy corporativo | Configure o proxy no Docker Desktop (Settings → Resources → Proxies) |
| Erro de porta `5432` em uso | Já existe um PostgreSQL na máquina | No `.env` da raiz: `DB_PUBLISHED_PORT=5433` |
| Erro de porta `8084` em uso | Outro serviço usando a porta | No `.env` da raiz: `WEB_PUBLISHED_PORT=8085` (e acesse por `:8085`) |
| Erro de porta `8000` em uso | Outro serviço usando a porta | No `docker-compose.yml`, troque `"8000:8000"` por `"8001:8000"` (a tela não usa essa porta) |
| Build falha no `npm ci` | Sem acesso ao npm (proxy corporativo) | Configure o proxy no Docker, como no item acima |
| API não fica *healthy* | Variável obrigatória faltando | `docker compose logs api`: procure por `APP_GEMINI_API_KEY` ou `DB_PASSWORD` |
| Login de rede: **"temporariamente indisponível"** | AD fora do ar, endereço errado, porta 636 bloqueada ou certificado não confiável | `docker compose logs api` mostra o motivo (ex.: `exige conexão segura`, `certificate verify failed`). Teste de dentro do container: `docker compose exec api python -c "import socket; socket.create_connection(('dc01.empresa.local', 636), 5); print('ok')"`. Certificado: veja `APP_AD_CA_CERT_FILE` no passo 2 |
| Usuário de rede: **"não tem acesso a este sistema"** | Fora do grupo de `APP_AD_REQUIRED_GROUP_DN`, ou fora de `APP_AD_BASE_DN` | Peça à TI para incluir a pessoa no grupo; confira o DN do grupo e a base |
| Tela mostra **"Offline"** no cabeçalho | API fora do ar | Teste o passo 3 e veja `docker compose logs api` |
| Entra e **é deslogado em seguida** | Tela aberta por um endereço que não passa pelo container `web` (ex.: XAMPP em outro servidor) | Acesse a tela pela porta 8084 do servidor da API |
| Manual **"Falhou: serviço externo"** | Limite ou cota do plano gratuito do Gemini | Aguarde a cota renovar (diária) ou use a chave paga, e clique em **Reprocessar** |
| Manual **"Falhou: ... não contém texto selecionável"** | PDF escaneado (imagem, sem texto) | Clique em **Descrever figuras** na linha do manual (veja "Figuras e manuais escaneados") |
| Sincronização: **"O arquivo excede o limite de N MB"** | PDF maior que `APP_MAX_UPLOAD_MB` | Aumente `APP_MAX_UPLOAD_MB` em `backend/.env` (os maiores manuais têm ~96 MB; o padrão é 100) e sincronize de novo |
| Chat: **"Você ainda não tem acesso a este assistente"** | O assistente está "só para quem for liberado" e a pessoa não foi liberada | Na tela **Usuários**, clique em **Gerenciar** na linha da pessoa e libere o assistente, ou mude o padrão em **Acessos** |
| Chat: **"Você atingiu o limite de N pergunta(s)…"** | Limite de perguntas por usuário | Aguarde, ou ajuste o limite em **Configurações** (`0` desliga) |
| Sincronização agendada **"não começou"** | Pasta de rede fora do ar ou outra sincronização rodando | Confira a pasta com o passo de verificação acima; ela tenta de novo no horário do dia seguinte |
| Chat responde **"temporariamente indisponível"** | Gemini sobrecarregado ou sem cota | Tente em instantes; `docker compose logs api` mostra o motivo |
| Esqueceu a senha do administrador | — | Crie outro administrador com o comando do passo 4 (outro login) e redefina a senha pela tela |

---

## 9. Lembretes de segurança (antes de abrir para a empresa)

- **Chave paga:** no plano gratuito do Gemini, o Google pode usar o conteúdo enviado para
  treinar modelos. **Não use manuais confidenciais com a chave gratuita.**
- **HTTPS:** sem ele, as senhas de rede trafegam abertas entre o navegador e a API. É a
  mesma senha do Windows e do e-mail, então priorize um certificado interno e defina
  `APP_AUTH_COOKIE_SECURE=true`. Entre a API e o AD, use sempre `ldaps://`. Ver as ADRs
  [0008](adr/0008-login-pelo-totvs-e-sessoes-no-banco.md) e
  [0011](adr/0011-login-pelo-active-directory.md).
- **Consumo por usuário (LGPD):** a tela de Consumo mostra quanto cada pessoa usou (sem as
  perguntas). Avise os usuários de que o uso é registrado para controle de custo e
  confirme com o jurídico ou o encarregado de dados. Ver a
  [ADR 0012](adr/0012-consumo-limites-e-agendamento.md).
- **Backup:** faça backup regular do volume do banco (`manual-assistant_db-data`) e do
  volume dos PDFs (`manual-assistant_manual-files`).
