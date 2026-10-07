# ADR 0004 — Leitura de PDF e divisão em trechos

- **Status:** aceito
- **Data:** 2026-10-06

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
