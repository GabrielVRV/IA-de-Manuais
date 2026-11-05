# ADR 0013 — Acesso por assistente e fim da liberação manual

- **Status:** aceito
- **Data:** 2026-11-05
- **Substitui:** a liberação manual de quem entra pelo AD ("aguardando liberação"), da
  [ADR 0011](0011-login-pelo-active-directory.md)

## Contexto

Hoje o chat tem um assistente só, o de **Engenharia** (manuais técnicos). A ideia é ter
outros, como um assistente da **TI** que tenta resolver o problema e, se não conseguir,
abre um chamado. Cada assistente vai ter um público diferente: a TI atende todo mundo,
e os manuais interessam a quem trabalha com eles.

O controle de acesso que existia era um só, para o sistema inteiro: quem entrava pelo
AD ficava "aguardando liberação" até um administrador clicar em **Liberar**. Com mais de
um assistente, isso não serve:

- quem precisa abrir um chamado não pode ficar travado esperando aprovação;
- liberar a pessoa no sistema não diz **quais** assistentes ela pode usar.

## Decisão

1. **Cada assistente tem um acesso padrão**, definido na tela **Administração → Acessos**:
   - **Liberado para todos:** qualquer usuário ativo usa. É o padrão.
   - **Só para quem for liberado:** só administradores e quem tiver uma exceção.
2. **Exceções por usuário**, na tela **Usuários**: para cada assistente, a pessoa segue o
   padrão, fica **liberada** ou fica **bloqueada**. A exceção vale mesmo se o padrão mudar.
3. **Instruções para pedir acesso**, por assistente, com até 300 caracteres (ex.: "Abra um
   chamado no GLPI pedindo acesso ao Assistente de Engenharia."). Quem não tem acesso vê o
   texto no lugar do chat, e a API devolve o mesmo texto ao recusar. Sem texto, vale
   "Peça o acesso a um administrador do sistema.".
4. **Administradores usam todos os assistentes.** Perfil (usuário ou administrador) diz
   quem administra o sistema; acesso diz quais chats a pessoa usa. Os dois ficam separados.
5. **Fim do "aguardando liberação".** No primeiro login pelo AD, a pessoa entra como
   usuário comum e usa os assistentes liberados para todos. A migração `0010` passa os
   pendentes a usuários comuns. Para barrar alguém do sistema inteiro, continua valendo
   **Desativar**. O filtro por grupo do AD (`APP_AD_REQUIRED_GROUP_DN`) também continua.
6. **A API confere o acesso**, e não só a tela: perguntar ao assistente
   (`POST /questions`) e abrir o PDF de um manual (`GET /manuals/{id}/file`) respondem
   **403** sem acesso, antes de chamar o modelo. Ou seja, a recusa não gasta tokens.
7. **Os assistentes ficam no código** (`domain/assistant.py`): cada um precisa de
   implementação própria (de onde vem a resposta, o que ele faz). O banco guarda só o
   acesso: `assistant_access_policies` (padrão e instruções de cada assistente) e
   `user_assistant_access` (exceções). Sem linha na primeira tabela, o assistente está
   liberado para todos.
8. **Rotas:** `GET /assistants` (os assistentes e se o usuário da sessão pode usar cada
   um); só para administradores, `GET /assistants/access`, `PUT /assistants/{id}/access`
   e `PUT /users/{id}/assistants/{assistant_id}`. A lista de usuários (`GET /users`)
   traz as exceções de cada um em `assistant_access`.

## Consequências

- **Com o filtro por grupo vazio, qualquer usuário do AD entra** e usa os assistentes
  liberados para todos, sem aprovação. Para restringir quem entra no sistema, use um grupo
  do AD; para restringir um assistente, use o acesso padrão.
- **Fluxo previsto para os manuais:** começar liberado para todos e, quando fizer sentido,
  mudar para "só para quem for liberado", com o texto apontando para o GLPI. Quem já
  precisa continuar usando pode ser liberado antes da mudança.
- **Um assistente novo** entra em `AssistantId`/`ASSISTANTS` no backend e no frontend. Ele
  aparece sozinho nas telas Acessos e Usuários. A conversa vai precisar guardar a qual
  assistente pertence, e "Nova conversa" vai precisar oferecer a escolha.
- **Mais para frente, se precisar:** liberação por grupo do AD (todo o grupo
  "Engenharia" recebe os manuais) e um responsável por assistente (alguém que cuida só
  daquele assistente, sem ser administrador geral).
