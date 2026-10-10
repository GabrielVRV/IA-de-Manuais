# ADR 0010 — Histórico de conversas

- **Status:** aceito
- **Data:** 2026-10-10
- **Altera:** a [ADR 0006](0006-chat-no-frontend.md), em que a conversa vivia só na tela

## Contexto

Até aqui cada pergunta era independente e a conversa sumia ao recarregar a página. Isso
tinha dois problemas:

- quem voltava a um assunto (ex.: a montagem de um equipamento ao longo do dia) precisava
  perguntar tudo de novo;
- perguntas de continuação, como "e no modelo maior?", não funcionavam, porque o modelo
  não sabia do que se falava antes.

## Decisão

1. **As conversas ficam no servidor, por usuário**, nas tabelas `conversations` e
   `conversation_exchanges`. Cada troca guarda a pergunta, a resposta e as fontes citadas
   como eram naquele momento (título do manual e páginas). Assim a pessoa vê o histórico
   em qualquer computador em que entrar.
2. **Só o dono vê a própria conversa**, nem administradores. A conversa de outra pessoa
   responde 404, como se não existisse. As perguntas podem citar problemas de produção e
   dúvidas pessoais; quem pergunta precisa estar à vontade.
3. **Só perguntas respondidas entram no histórico.** Se a IA falhar, nada é gravado e a
   tela oferece "Tentar novamente". A primeira resposta cria a conversa, com a pergunta
   como título (encurtado numa palavra inteira, até 60 caracteres). O usuário pode
   renomear e apagar.
4. **Retenção de 90 dias sem uso**, configurável em `APP_CONVERSATION_RETENTION_DAYS`
   (`0` = guardar para sempre). A API apaga as conversas vencidas na partida e a cada 6
   horas. Apagar um usuário apaga as conversas dele.
5. **Perguntas de continuação usam o contexto da conversa:**
   - as **3 últimas trocas** vão no prompt, dentro de `<conversa>`, com as respostas
     resumidas em 600 caracteres. Uma regra nova no prompt diz que esse contexto serve só
     para entender a pergunta: a resposta continua vindo **apenas dos trechos dos
     manuais**, com as mesmas citações;
   - a **busca** usa a pergunta anterior junto com a atual. Sem isso, "e a mínima?"
     sozinha não encontraria os trechos do equipamento certo;
   - o texto da conversa recebe a mesma proteção dos trechos contra quem tenta fechar as
     marcações e se passar por instrução.
6. **Na tela**, cada conversa tem uma URL própria (`#/c/<id>`), que pode ser favoritada.
   O histórico fica numa barra lateral, agrupado por data (Hoje, Ontem, 7 dias, 30 dias,
   mais antigas) e com busca que ignora acentos. Em telas pequenas, a barra vira uma
   gaveta.

## Consequências

- **Cada pergunta de continuação custa um pouco mais** (algumas centenas de tokens de
  contexto). As 3 trocas e os 600 caracteres limitam esse custo.
- **As respostas antigas não mudam quando um manual é atualizado.** É proposital: o
  histórico mostra o que foi respondido na época. O link da fonte abre o PDF atual, e
  deixa de funcionar se o manual for removido.
- **O banco passa a guardar o que as pessoas perguntam.** Está coberto pela retenção e
  pelo acesso só do dono. Relatórios sobre o que mais se pergunta ficam para uma decisão
  futura, provavelmente com dados agregados e anônimos.
- **Conversa nova**: a API responde com `conversation` (id e título) junto da resposta,
  e o frontend envia `conversation_id` nas perguntas seguintes. Rotas novas:
  `GET/PATCH/DELETE /api/v1/conversations[/{id}]`.
