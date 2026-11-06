# ADR 0004 — Leitura de PDF e divisão em trechos

- **Status:** aceito
- **Data:** 2026-10-06
- **Complementada por:** a [ADR 0014](0014-descricao-de-figuras-por-ia.md), que descreve as
  figuras por IA e passa a ler os PDFs escaneados

## Contexto

Os manuais chegam em PDF. O texto precisa ser extraído página a página (para citar a
página na resposta) e dividido em trechos do tamanho certo para a busca semântica.

## Decisão

### Leitura: pypdfium2

- O **PyMuPDF** foi descartado por causa da licença **AGPL**: um sistema acessado pela
  rede que use essa biblioteca pode ser obrigado a abrir o código-fonte, a menos que se
  compre a licença comercial.
- O **pypdfium2** usa o PDFium, o motor de PDF do Chrome, com licença BSD/Apache. É livre
  para uso comercial e a qualidade de extração é muito boa.
- O PDFium **não é thread-safe**. O adaptador serializa o acesso com um lock e roda fora
  do event loop (`asyncio.to_thread`), para não travar a API.
- PDFs sem texto selecionável (escaneados) são recusados com uma mensagem explicativa.
  OCR fica para uma evolução futura.
- **Fontes sem ToUnicode** (2026-11-06). Alguns PDFs, como os gerados pelo Word, embutem
  a fonte com codificação Identity e sem a tabela ToUnicode. O PDFium então devolve o
  número do glifo no lugar da letra: "Óleo mineral ISO 460" vira `ÏOHRPLQHUDO,62`, e
  espaços e dígitos viram caracteres de controle, que eram descartados. A busca não acha
  nada e o assistente responde "não encontrei". Isso aconteceu no manual do comedouro
  S-70 (95.007.008). O parser reconhece essas fontes de dois jeitos: o texto tem caracteres
  de controle (exceto o U+0002, que o PDFium usa para marcar hifenização), ou o PDFium não
  consegue voltar de caractere para glifo (todo caractere cai no `.notdef`). Uma fonte com
  mais espaços de verdade (U+0020) que glifos de espaço nunca é traduzida. Para essas
  fontes, o texto da página é refeito caractere a caractere, traduzindo glifo → caractere
  pela tabela `cmap` da própria fonte embutida. Só fontes TrueType são traduzidas, e só
  quando a `cmap` cobre pelo menos 90% dos códigos usados. Validação na pasta da
  Engenharia (357 PDFs): 84 manuais ficaram com o texto corrigido (46 deles em versão
  vigente), nenhum piorou, e a leitura ficou ~20% mais lenta. Manuais indexados antes
  da correção precisam ser **reprocessados**.

### Divisão: por linhas, com sobreposição

- O texto extraído do PDF **não preserva linhas em branco entre parágrafos**, então dividir
  por parágrafo não funciona. A divisão agrupa **linhas consecutivas** até ~1500
  caracteres (~375 tokens). Isso também preserva a estrutura de listas e tabelas.
- Cada trecho repete até ~200 caracteres do final do anterior (**sobreposição**), para que
  uma instrução não seja cortada ao meio entre dois trechos.
- Um trecho pode atravessar páginas. O intervalo (ex.: p. 12–13) é guardado para a citação.

### Fluxo de ingestão

1. **Cadastro** (`RegisterManualUseCase`): valida o conteúdo (assinatura `%PDF-`, não a
   extensão) e o tamanho, guarda o arquivo original e cria o manual como *pendente*.
2. **Indexação** (`IndexManualUseCase`): lê → divide → gera embeddings → substitui os
   trechos antigos → marca como *indexado*. Roda em segundo plano, porque um manual grande
   pode levar minutos.
3. Qualquer falha fica registrada no próprio manual, com uma mensagem legível.
4. Os embeddings são gerados **antes** de apagar os trechos antigos. Se o provedor de IA
   falhar num reprocessamento, o índice anterior continua intacto.

## Consequências

- Manuais escaneados ainda não são suportados.
- O tamanho dos trechos foi escolhido por boas práticas. Será ajustado com perguntas reais,
  quando houver métricas de qualidade das respostas (degrau 10).
- O arquivo original fica guardado. Isso permite reprocessar o manual (ex.: ao trocar de
  provedor de embeddings) e, no futuro, abrir o PDF na página citada.
