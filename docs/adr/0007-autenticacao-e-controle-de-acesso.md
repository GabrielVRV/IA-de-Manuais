# ADR 0007 — Autenticação e controle de acesso

- **Status:** aceito
- **Data:** 2026-10-07

## Contexto

Sem login, qualquer pessoa da rede podia enviar ou excluir manuais. Para o login, foram
avaliados quatro caminhos:

- **Login automático do Windows (SSO):** exige Kerberos, servidor no domínio e HTTPS.
- **Uma API no Datasul/Progress:** só atende quem tem usuário no Datasul.
- **Validar no Active Directory via LDAP.**
- **Cadastro próprio de usuários.**

## Decisão

1. **Cadastro próprio no PostgreSQL agora**, sem depender da TI nem de desenvolvimento no
   Progress. A validação da senha é uma porta (`PasswordHasher` + `UserRepository`). Um
   adaptador LDAP/AD pode ser adicionado depois, e o perfil e as permissões continuam no
   nosso banco, porque o AD só confirma a identidade.
2. **Dois perfis:** `admin` (chat, manuais e usuários) e `user` (só o chat). **Todos**
   precisam de login, o que permite auditoria e custo por usuário no degrau 11.
3. **Senhas com Argon2id** (recomendado pela OWASP). Os hashes são refeitos
   automaticamente no login quando os parâmetros evoluem. A política é: de 8 a 128
   caracteres, e diferente do login. O comprimento importa mais que regras de símbolo
   (NIST SP 800-63B).
4. **Sessão em cookie `HttpOnly` + `SameSite=Lax`**, contendo um JWT HS256 com validade
   (10 h). O cookie, e não um token guardado pelo JavaScript, foi escolhido porque:
   - os links das fontes abrem o PDF em outra aba, e uma navegação não envia cabeçalhos,
     mas envia cookies;
   - scripts não conseguem ler o cookie, então um XSS não rouba a sessão;
   - cookies não separam por porta, então o XAMPP (porta 80) e a API (porta 8000) no
     mesmo servidor compartilham a sessão.
5. **O token carrega só o ID do usuário.** O perfil e o status são lidos do banco a cada
   requisição: desativar ou rebaixar alguém tem efeito imediato.
6. **Proteções:**
   - **Bloqueio temporário** depois de 5 senhas erradas seguidas (15 min).
   - **Mesma mensagem e mesmo tempo de resposta** para login inexistente e senha errada,
     para não revelar quais logins existem.
   - **Senha provisória** criada pelo administrador, com troca obrigatória no primeiro
     acesso. Até a troca, só `/auth/me` e `/auth/change-password` funcionam.
   - **Um administrador não pode desativar nem rebaixar a si mesmo.**
   - **A regra "só administradores"** é verificada nos casos de uso, não só na API.
7. **O primeiro administrador é criado por um comando no servidor**
   (`python -m manual_assistant.cli create-admin`). Quem tem acesso ao servidor já é de
   confiança, e o mesmo comando serve para recuperar o acesso.

## Consequências

- ⚠️ **Sem HTTPS, as senhas trafegam abertas na rede interna.** Elas são exclusivas deste
  sistema, o que limita o estrago, mas muita gente repete senha. Antes da produção:
  certificado interno + `APP_AUTH_COOKIE_SECURE=true`.
- **A sessão termina por expiração ou logout.** Desativar o usuário também a encerra na
  hora, já que o status é conferido a cada requisição.
- **Desligamentos dependem de alguém desativar o usuário.** Com o AD, isso seria
  automático: é um argumento para o adaptador LDAP no futuro.
- **`APP_AUTH_SECRET_KEY` passa a ser obrigatória.** Se ela vazar, alguém consegue forjar
  sessões. Ela fica só no `.env` do servidor; trocá-la encerra todas as sessões.
