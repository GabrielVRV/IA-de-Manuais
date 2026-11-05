/**
 * Quem responde no chat. Hoje há um só assistente; quando chegarem outros (ex.: o da TI),
 * cada conversa passa a pertencer a um deles e a escolha acontece em "Nova conversa".
 */
export interface Assistant {
  /** Nome mostrado no chat. */
  readonly name: string
  /** Do que ele trata, em poucas palavras. */
  readonly topic: string
  /** O que perguntar e de onde vem a resposta, para a tela inicial. */
  readonly description: string
}

export const ENGINEERING_ASSISTANT: Assistant = {
  name: 'Assistente de Engenharia',
  topic: 'Manuais técnicos',
  description:
    'Tire dúvidas sobre os manuais técnicos dos equipamentos. Eu procuro nos manuais da ' +
    'Engenharia e mostro de qual manual e página veio cada informação.',
}
