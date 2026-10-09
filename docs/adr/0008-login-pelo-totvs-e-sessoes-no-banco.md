# ADR 0008 — Login pelo TOTVS e sessões no banco

- **Status:** aceito
- **Data:** 2026-10-09
- **Substitui:** os itens 1, 3 (para usuários do TOTVS), 4 e 6 (bloqueio) da
  [ADR 0007](0007-autenticacao-e-controle-de-acesso.md)

## Contexto

Com o cadastro próprio da ADR 0007, cada pessoa tem mais uma senha para lembrar, e quem
sai da empresa continua com acesso até alguém desativá-lo aqui. Quase todos os usuários
já têm login no Datasul, e foi criada uma API REST no Progress (`api_valida_login.p`)
que confere usuário e senha contra o `usuar_mestre` e avisa quando a senha venceu.

A ADR 0007 já previa trocar a validação da senha por um sistema externo, mantendo o
perfil e as permissões no nosso banco.

## Decisão

1. **Usuários do TOTVS entram com o usuário e a senha do Datasul.** O backend chama o
   `validarLogin` direto do servidor, com o Basic Auth do próprio usuário. O navegador
   nunca fala com o Datasul, e a senha não é guardada em lugar nenhum: ela só passa pelo
   backend durante o login.
2. **O primeiro login cria o usuário com o perfil `pending` (aguardando liberação).** Ele
   entra, mas só vê uma tela de espera, e aparece destacado na aba de usuários para um
   administrador escolher `user` ou `admin`. Para recusar alguém, basta desativá-lo. O
   nome vem do TOTVS (`nom_usuario`) e é atualizado a cada login.
3. **Usuários locais continuam existindo** (`auth_source = local`), para quem não tem
   TOTVS e para o administrador de emergência criado pelo `create-admin`, que entra mesmo
   com o Datasul fora do ar. Só eles têm senha (Argon2id), senha provisória e troca de
   senha. O login é único entre os dois tipos; se existir um usuário local com o login
   digitado, a senha é conferida aqui e o TOTVS não é consultado.
4. **Sessões numa tabela do banco, no lugar do JWT.** O cookie `HttpOnly` leva um token
   aleatório de 256 bits, e o banco guarda só o SHA-256 dele. A sessão termina:
   - por **inatividade**: 7 dias sem uso (`APP_AUTH_SESSION_IDLE_DAYS`);
   - pelo **prazo absoluto**: 30 dias depois do login, mesmo com uso diário
     (`APP_AUTH_SESSION_MAX_DAYS`). O cookie vale até esse prazo;
   - no **logout**, que apaga a sessão no banco: o cookie deixa de valer mesmo que alguém
     tenha copiado.

   O último uso é gravado no máximo a cada 5 minutos, para não escrever no banco a cada
   requisição.
5. **Sem consulta periódica ao TOTVS.** Uma senha trocada ou um usuário bloqueado no
   Datasul só é percebido no próximo login. Para casos urgentes (ex.: desligamento), o
   administrador desativa o usuário aqui, com efeito imediato, já que o status é
   conferido a cada requisição. Assim o backend não precisa de um usuário técnico do
   Datasul.
6. **Bloqueio por tentativas, por login digitado**, numa tabela própria
   (`login_attempts`): 5 erros seguidos bloqueiam por 15 minutos. Ele é conferido
   **antes** de chamar o TOTVS, para que ninguém consiga bloquear a conta TOTVS de um
   colega errando a senha aqui de propósito. Como quem ainda não tem cadastro também
   pode errar, o bloqueio deixou de ficar na tabela de usuários.
7. **Mensagens:**
   - login inexistente ou senha errada: a mesma, "Usuário ou senha inválidos";
   - senha vencida no TOTVS: pede para redefini-la no TOTVS;
   - usuário desativado: avisa que o acesso foi desativado. Como a senha já foi
     conferida, isso não revela quais logins existem;
   - Datasul fora do ar: pede para tentar de novo (HTTP 503). Não conta como tentativa
     errada.

## Consequências

- ⚠️ **Sem HTTPS, a senha do TOTVS trafega aberta na rede interna**, do navegador até o
  backend e do backend até o Datasul. Hoje todos já acessam o Datasul por HTTP pelo IP,
  então o sistema não cria uma exposição nova, mas o risco existe e foi aceito. O cookie
  de sessão também pode ser capturado; por isso o logout invalida a sessão no banco.
  Quando houver certificado interno: `APP_AUTH_COOKIE_SECURE=true` e URLs `https://`.
- **Login do TOTVS depende do Datasul no ar.** Sessões abertas continuam funcionando, e
  os usuários locais entram normalmente.
- **Logins do TOTVS fora do formato aceito** (3 a 50 caracteres: letras, números, `.`,
  `_` ou `-`) não conseguem entrar. Precisam de um usuário local.
- **`APP_AUTH_SECRET_KEY` deixou de existir** e o `pyjwt` saiu das dependências.
  Configuração nova: `APP_TOTVS_LOGIN_URL` (vazia = login pelo TOTVS desligado) e
  `APP_TOTVS_TIMEOUT_SECONDS`.
- **Na migração, todos os usuários existentes viram locais**, com a senha e o perfil que
  já têm. Para passar alguém a entrar com a senha do Datasul, mantendo o perfil, há um
  comando no servidor: `python -m manual_assistant.cli use-totvs --username <login>`.
