# ADR 0012 — Consumo de tokens, limite de perguntas e sincronização agendada

- **Status:** aceito
- **Data:** 2026-11-05
- **Complementa:** a [ADR 0009](0009-sincronizacao-com-a-pasta-da-engenharia.md) (sincronização)
  e a [ADR 0010](0010-historico-de-conversas.md) (histórico)

## Contexto

Com a chave paga da API de IA, cada pergunta passa a ter custo. Faltava:

- saber **quanto se gasta** e **quem mais usa**, para acompanhar o custo e justificar a chave;
- impedir que um uso fora do normal (um script, alguém repetindo perguntas) esgote a cota;
- manter os manuais em dia **sem depender de alguém clicar** em "Sincronizar".

Também ficou decidido que esses ajustes são feitos **pela tela**, sem editar o `.env` e
sem reiniciar a API.

## Decisão

1. **Consumo por pergunta, só com números.** A tabela `question_usage` guarda usuário,
   data, modelo e tokens de entrada e de saída de cada pergunta respondida. **O texto
   da pergunta não é guardado ali**: ele continua só no histórico, visível apenas para o
   dono (ADR 0010). Perguntas respondidas sem chamar o modelo (nenhum trecho encontrado)
   entram com modelo nulo e zero tokens: contam como pergunta e não custam nada.
2. **Tela Consumo (administradores):** período de 7, 30 ou 90 dias, totais, tokens por
   dia, ranking de quem mais usou e consumo por modelo. O "dia" é o do relógio da
   empresa (`APP_TIMEZONE`, padrão `America/Sao_Paulo`), e não o UTC do servidor.
3. **Custo calculado na hora, com o preço de cada modelo** informado na tela
   Configurações, em dólares por milhão de tokens. O preço fica ligado ao **modelo**:
   trocar de modelo não muda o custo calculado do que já passou. Modelo usado sem preço
   aparece com um aviso, e o custo é marcado como incompleto.
4. **Retenção do consumo:** 12 meses por padrão, alterável na tela (`0` = para sempre). A
   limpeza roda com a das conversas, na partida e a cada 6 horas.
5. **Limite de perguntas por usuário:** por minuto (padrão 10) e em 24 horas (padrão 200),
   alteráveis na tela (`0` desliga). O limite vale também para administradores. Acima
   dele, a API responde **429** com uma mensagem clara, **antes de chamar o modelo**, ou
   seja, sem gastar tokens. A contagem usa a própria tabela de consumo.
6. **Sincronização diária agendada:** ligada ou desligada e com horário (HH:MM, no fuso da
   empresa) escolhidos no painel da pasta da Engenharia, na tela Manuais. A API confere o
   agendamento a cada minuto e dispara a mesma sincronização do botão, registrada como
   "Agendamento automático".
   - Roda **uma vez por dia**. Um horário que já passou no dia em que foi salvo só vale a
     partir do dia seguinte.
   - Se a API estava fora do ar no horário, a sincronização do dia roda **quando ela voltar**.
   - Se não conseguir começar (pasta inacessível, outra sincronização em andamento), o
     motivo fica registrado e aparece na tela. Ela **não tenta de novo a cada minuto**: a
     próxima tentativa é no horário do dia seguinte.
7. **Configurações no banco:** `system_settings` (uma linha: retenção e limites),
   `model_prices` (preço por modelo) e `sync_schedule` (uma linha: o agendamento).
   Rotas novas, todas só para administradores: `GET /usage`, `GET/PATCH /settings`,
   `GET/PUT/DELETE /settings/model-prices` e `GET/PUT /sync/schedule`.

## Consequências

- **O consumo é dado pessoal** (fica ligado a uma pessoa identificada), mesmo sem o texto
  das perguntas. A finalidade é o controle de custo e o acesso é só de administradores.
  Convém avisar os usuários de que o uso é registrado para esse fim. A análise jurídica
  (LGPD) fica com o jurídico ou o encarregado de dados da empresa.
- **Os tokens da indexação (embeddings) não entram no relatório:** o provedor não informa
  essa contagem. O relatório mostra o custo contínuo, o do chat.
- **A sincronização agendada gasta API de IA** com os manuais novos ou alterados, como a
  manual. Com a pasta sem mudanças, ela não gasta nada.
- **A API roda num processo só.** Com mais de uma réplica, o limite de perguntas e o
  agendamento precisariam de uma trava compartilhada (no banco, por exemplo).
- **O limite é aproximado sob concorrência:** duas perguntas exatamente simultâneas do
  mesmo usuário podem passar juntas no último lugar livre. Para proteger a cota, basta.
