# ADR 0009 — Sincronização com a pasta de manuais da Engenharia

- **Status:** aceito (comando e tela de administração; agendamento fica para depois)
- **Data:** 2026-10-10
- **Substitui:** o degrau 10 do roadmap ("sincronização com o SharePoint")

## Contexto

O plano era buscar os manuais no SharePoint pelo Microsoft Graph. Só que a Engenharia já
mantém os manuais vigentes numa pasta de rede (`\\srv-file-02\arquivos\engpub_consulta\
Manuais`, a `J:` das máquinas), e continuaria mantendo. Ler direto dessa pasta dispensa
registrar um aplicativo no Azure, pedir permissões no Graph e renovar tokens. A Engenharia
continua trabalhando do jeito de sempre, e um segundo lugar para manter atualizado deixa
de existir.

Estrutura da pasta (outubro/2026, ~280 PDFs, 1,6 GB):

```
Manuais/
  MANUAIS PRODUTO.xlsm        código, descrição, segmento, situação, idioma...
  ARMAZENAGEM/*.pdf           manuais vigentes
  ARMAZENAGEM/Versões Anteriores/, Versões Obsoletas/
  PROTEÍNA/*.pdf
  PROTEÍNA/Versões Anteriores/, Versões Obsoletas/
```

Os arquivos seguem o padrão `código-revisãoIdioma.pdf` (ex.: `95007003-01P.pdf`: revisão
01, português). Há versões em inglês (`E`) de parte dos manuais, todas com equivalente em
português. Parte dos secadores usa a variante `código-vRevisão-modelo.pdf` (ex.:
`95021401-v2-ca10.pdf`), sem letra de idioma: são manuais em português, e a planilha os
lista no padrão normal (`95021401-02P`). O sistema trata as duas formas como o mesmo manual.

## Decisão

1. **A pasta é somente leitura para o sistema.** Ela pertence à Engenharia: o sistema
   nunca cria, altera, move ou apaga nada nela. A porta `ManualSource` só tem métodos de
   leitura, e um teste confere que listar e ler não muda nenhum arquivo. No Docker, a pasta
   é montada com `:ro`. O sistema continua guardando a própria cópia de cada PDF (como no
   upload): o link "abrir na página X" não depende da pasta de rede estar no ar, e a
   reindexação usa exatamente o arquivo que gerou os trechos.
2. **Só contam os PDFs do primeiro nível de cada subpasta.** Isso deixa de fora, sem regra
   extra, as `Versões Anteriores` e `Versões Obsoletas`: a IA nunca responde com um manual
   desatualizado. Arquivos fora do padrão de nome (ex.: o procedimento `P&D 08`) são
   ignorados.
3. **O manual é identificado por código + idioma, não pelo caminho** (`source_key`, ex.:
   `95007003P`). Quando sai a revisão `-02P` e a `-01P` vai para "Versões Anteriores", o
   sistema atualiza o mesmo manual (arquivo, nome, reindexação) em vez de apagar um e criar
   outro. Se duas revisões do mesmo código estiverem soltas na pasta, vale a maior.
4. **Só português por padrão** (`APP_SYNC_LANGUAGES=P`). Indexar também o inglês dobraria
   o custo de embeddings e faria a busca trazer trechos repetidos.
5. **O título vem da planilha** (coluna "Descrição", pelo código com revisão). Sem a
   planilha, ou se ela não puder ser lida, o título é o nome do arquivo e a sincronização
   segue normalmente.
6. **Detecção de mudanças em dois níveis.** A "impressão digital" (tamanho + data do
   arquivo) evita reler 1,6 GB pela rede a cada sincronização. Quando ela muda, o arquivo é
   lido e comparado pelo SHA-256: se o conteúdo é o mesmo (alguém só copiou de novo), não
   reindexa nem gasta API.
7. **Remoção:** o manual que sai da pasta é removido do sistema (trechos, cópia do PDF e
   cadastro). Trava de segurança: se a pasta aparecer vazia ou não puder ser lida, a
   sincronização para sem alterar nada. Falhas momentâneas de rede são repetidas
   (3 tentativas) antes de desistir.
8. **Manuais enviados pela tela não são tocados** pela sincronização (`source_key` nulo).
9. **Primeira etapa: comando `sync-manuals`**, com `--dry-run` (só mostra o plano, sem
   alterar nada e sem precisar de chave de IA), `--limit N` (indexa no máximo N, para
   testar com poucos) e confirmação antes de gastar API.

10. **Segunda etapa: verificar e sincronizar pela tela** (`/api/v1/sync`, só
    administradores). "Verificar" é o `--dry-run`; "Sincronizar" refaz o plano (a pasta
    pode ter mudado desde a verificação) e o aplica em segundo plano, porque a primeira
    sincronização com a pasta inteira leva muito mais que uma requisição HTTP. Uma por vez.
    O andamento e o resultado da última ficam **em memória**: a API roda num processo só, e
    reiniciá-la apaga esse resumo, não os manuais (um manual interrompido no meio fica com
    falha e pode ser reprocessado). Se o histórico das sincronizações passar a importar,
    ele vai para uma tabela.

## Consequências

- Para produção, a infra precisa de uma conta de serviço do AD com **somente leitura** na
  pasta e acesso SMB (porta 445) do servidor Linux do Docker ao `srv-file-02`.
- Próxima etapa: rodar a sincronização periodicamente dentro da API (ex.: toda noite).
- Com a pasta como fonte, o upload pela tela fica para casos pontuais; um manual enviado
  pela tela com o mesmo código de um da pasta aparece duplicado.
