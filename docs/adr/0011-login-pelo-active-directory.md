# ADR 0011 — Login pelo Active Directory no lugar do TOTVS

- **Status:** aceito
- **Data:** 2026-11-04
- **Substitui:** o item 1 da [ADR 0008](0008-login-pelo-totvs-e-sessoes-no-banco.md) (login
  pelo TOTVS). O resto da ADR 0008 continua valendo: sessões no banco, perfil "aguardando
  liberação", usuários locais e bloqueio por tentativas.

## Contexto

O login pelo TOTVS só atende quem tem usuário no Datasul. Praticamente todos os
funcionários têm usuário de rede (AD), e o GLPI já confere logins no AD. Manter os dois
logins ao mesmo tempo criaria cadastros duplicados quando o login do TOTVS e o de rede
fossem diferentes (ex.: `gviaro` e `gabriel.viaro`).

## Decisão

1. **O AD substitui o TOTVS.** O backend autentica no AD por LDAP (`ldap3`), como o
   próprio usuário: `usuario@APP_AD_DOMAIN` e a senha digitada. **Não há conta de
   serviço.** Depois do login, a mesma conexão busca o usuário (`sAMAccountName`) em
   `APP_AD_BASE_DN` e lê o `displayName`. A senha não é guardada nem vai para o log.
2. **Grupo opcional que libera o acesso** (`APP_AD_REQUIRED_GROUP_DN`). Ele vale também
   para grupos dentro de grupos (`LDAP_MATCHING_RULE_IN_CHAIN`). Quem está fora do grupo
   recebe "peça a liberação à TI" e não é cadastrado. Mesmo dentro do grupo, o primeiro
   login continua `pending` até um administrador liberar.
3. **Conexão criptografada:** `ldaps://` (porta 636) ou `APP_AD_START_TLS=true`, com o
   certificado conferido (`APP_AD_CA_CERT_FILE` para a CA interna). Com `ldap://` sem
   StartTLS, a API avisa no log que as senhas de rede trafegam abertas.
4. **O código que o AD devolve no erro 49 é traduzido:**
   - `52e` senha errada, `525` usuário inexistente e qualquer outro: "Usuário ou senha
     inválidos". Conta como tentativa errada;
   - `532` senha vencida e `773` troca obrigatória: pede para trocar a senha no Windows.
     Não conta como tentativa errada;
   - `533` desativada, `701` expirada, `775` bloqueada, `530`/`531` fora do horário ou da
     estação: "conta de rede bloqueada ou desativada, procure a TI" (HTTP 403).
5. **Nosso bloqueio continua antes do AD.** Ninguém consegue bloquear a conta de rede de
   um colega errando a senha aqui de propósito. Isso pesa mais que no TOTVS, porque essa
   conta também é a do Windows e a do e-mail. Mantenha `APP_AUTH_MAX_FAILED_ATTEMPTS`
   abaixo do limite de bloqueio do AD.
6. **Senha vazia nunca chega ao AD:** no LDAP, ela vale como login anônimo, que o servidor
   aceita.
7. **Login digitado com domínio:** `EMPRESA\fulano` e `fulano@empresa.local` viram `fulano`.
8. **Migração (0006):** `auth_source = 'totvs'` vira `'ad'`, mantendo perfil e histórico.
   Quem tinha um login no TOTVS diferente do de rede é ajustado pelo comando
   `use-ad --username <login-antigo> --ad-login <login-de-rede>`. O comando recusa o
   ajuste se o login de rede já tiver outro cadastro.

## Consequências

- `APP_TOTVS_LOGIN_URL` e `APP_TOTVS_TIMEOUT_SECONDS` deixaram de existir. A configuração
  nova é `APP_AD_SERVER_URLS` (vazia = só usuários locais), `APP_AD_DOMAIN`,
  `APP_AD_BASE_DN`, `APP_AD_REQUIRED_GROUP_DN`, `APP_AD_START_TLS`, `APP_AD_CA_CERT_FILE` e
  `APP_AD_TIMEOUT_SECONDS`.
- O comando `use-totvs` deu lugar ao `use-ad`.
- **Login de rede depende do AD no ar.** Com mais de um controlador em
  `APP_AD_SERVER_URLS`, o próximo é tentado quando um cai. Sessões abertas e usuários
  locais continuam funcionando.
- Como na ADR 0008, não há consulta periódica: uma conta desativada no AD só é barrada no
  próximo login. Para cortar o acesso na hora, desative o usuário aqui.
- Logins de rede fora do formato aceito (3 a 50 caracteres: letras, números, `.`, `_` ou
  `-`) continuam precisando de um usuário local.
