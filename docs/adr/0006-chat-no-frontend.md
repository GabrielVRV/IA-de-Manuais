# ADR 0006 — Chat no frontend

- **Status:** aceito
- **Data:** 2026-10-07

## Contexto

O chat é a tela que os setores vão usar. Ele precisa mostrar a resposta com as fontes,
deixar claro quando a informação não está nos manuais e funcionar no ambiente interno
(XAMPP, sem HTTPS).

## Decisão

1. **Resposta completa, sem streaming (por enquanto).** Com o Gemini Flash respondendo em
   1 a 5 segundos, um indicador de "Consultando os manuais…" resolve a espera. O streaming
   complica a extração das citações (que só ficam conhecidas no fim da resposta) e a
   repetição automática em erros 503 do provedor.
2. **Cada pergunta é independente (sem memória da conversa).** Perguntas de acompanhamento
   ("e a do modelo CX-300?") exigiriam reescrever a pergunta com o histórico antes da busca,
   o que dobra as chamadas ao modelo. A decisão fica para depois do piloto, com dados de uso.
3. **Fontes clicáveis:** cada citação abre o PDF original
   (`GET /api/v1/manuals/{id}/file`, com `Content-Disposition: inline`) na primeira página
   citada, usando `#page=N`, que os leitores de PDF do Chrome e do Edge entendem.
4. **Markdown seguro:** o texto do modelo é renderizado com `react-markdown`, que não
   interpreta HTML. Uma resposta com `<script>` não executa nada.
5. **"Não encontrei" com visual próprio** (borda tracejada, texto atenuado), para não ser
   confundido com uma resposta do manual.
6. **Restrições do HTTP sem TLS respeitadas:** `crypto.randomUUID()` e
   `navigator.clipboard` não existem fora de contexto seguro. Os ids das mensagens usam um
   contador, e não há botão de copiar por enquanto.
7. **Tempo limite de 150 s para perguntas:** com o provedor sobrecarregado, a API repete a
   chamada algumas vezes antes de desistir. O padrão de 10 s cortaria essas respostas.
8. **Mensagens de erro para o usuário final:** um 503 vira "assistente temporariamente
   indisponível". O detalhe técnico (cota, chave) fica no log do servidor. Um botão
   "Tentar novamente" refaz a pergunta sem duplicá-la na conversa.

## Consequências

- A conversa se perde ao recarregar a página (estado só em memória). Persistir histórico
  entra junto com a autenticação (degrau 9), quando houver um usuário a quem associá-lo.
- O streaming e a memória de conversa podem ser adicionados sem mudar a arquitetura: uma
  nova porta no backend (`stream`) e um novo caso de uso de reescrita da pergunta.
