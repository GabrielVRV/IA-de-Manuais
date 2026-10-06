# ADR 0001 — Stack e arquitetura base

- **Status:** aceito
- **Data:** 2026-10-06

## Contexto

Os setores da empresa consultam a Engenharia com frequência sobre os manuais dos
equipamentos. Já existe um agente no Copilot/Teams que resolve o problema, mas ele exige
licença de Copilot para cada usuário, o que torna o custo inviável em escala.

Restrições do ambiente:

- O frontend é hospedado no XAMPP já usado para as aplicações web do TOTVS.
- O backend roda em Docker no servidor interno.
- O acesso é só pela rede interna e sem HTTPS.

## Decisão

1. **Backend em Python + FastAPI.** É o ecossistema mais maduro para IA com documentos
   (extração de PDF, OCR, SDKs oficiais de Gemini/OpenAI). O FastAPI tem tipagem forte,
   validação via Pydantic e documentação OpenAPI automática.
2. **Frontend em React (Vite + TypeScript)**, compilado como arquivos estáticos e servido
   pelo XAMPP.
3. **Clean Architecture** com quatro camadas (`domain`, `application`, `infrastructure`,
   `presentation`) e uma raiz de composição (`main.py`). A regra de dependência é
   verificada no CI pelo `import-linter`.
4. **Provedor de LLM atrás de uma porta.** Gemini e OpenAI viram adaptadores
   intercambiáveis (OCP/DIP), escolhidos por configuração. Isso evita aprisionamento a
   um fornecedor e permite comparar custo e qualidade.
5. **RAG** como técnica de resposta, com citação obrigatória da fonte (manual + página).

## Consequências

### Sobre a ausência de HTTPS

- **Backend → LLM:** sem impacto. As chamadas saem do servidor para a internet e usam o
  HTTPS do próprio provedor.
- **Navegador → backend:** funciona normalmente. Os pontos de atenção são:
  - o tráfego interno (perguntas e respostas) circula sem criptografia na rede local;
  - algumas APIs do navegador exigem contexto seguro (HTTPS ou `localhost`), como
    `navigator.clipboard` (botão "copiar resposta"), microfone e Service Workers/PWA.
    Teremos alternativas para essas funções.
  - CORS precisa estar configurado (`APP_CORS_ORIGINS`), porque frontend e backend ficam
    em origens diferentes.
- **Recomendação futura:** um certificado interno (ex.: da CA do AD) num reverse proxy.
  Nenhuma mudança de código seria necessária.

### Sobre privacidade dos manuais

Trechos dos manuais são enviados ao provedor de LLM. É obrigatório usar o **plano pago**
da API: nos planos gratuitos, os provedores podem usar os dados enviados para treinar
modelos. A chave de API fica só no backend, nunca no frontend.
