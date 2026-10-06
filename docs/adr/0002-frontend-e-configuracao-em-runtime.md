# ADR 0002 — Organização do frontend e configuração em tempo de execução

- **Status:** aceito
- **Data:** 2026-10-06

## Contexto

O frontend é servido como arquivos estáticos pelo XAMPP. O endereço da API muda entre
ambientes (máquina do desenvolvedor, servidor interno). O padrão do Vite (`VITE_*`)
embute esse endereço no momento do build, o que obrigaria a gerar um build por ambiente.

## Decisão

1. **Configuração em runtime:** a aplicação lê `config.json` (ao lado do `index.html`)
   antes de renderizar. O arquivo é validado com Zod e, se estiver ausente ou inválido,
   aparece uma tela de erro explicativa em vez de uma página em branco.
2. **Build com caminhos relativos** (`base: './'`), para funcionar em qualquer subpasta
   do `htdocs`.
3. **Organização por funcionalidade** (`features/<nome>/`), cada uma com as camadas
   `domain`, `infrastructure` e `presentation`. A regra de dependência é verificada pelo
   ESLint (`no-restricted-imports`).
4. **Injeção de dependência via Context do React:** os componentes dependem só das
   portas (ex.: `HealthGateway`). As implementações concretas são criadas em `main.tsx`.
   Nos testes, entram implementações falsas, sem precisar mockar `fetch`.
5. **Dados externos sempre validados** (Zod) na camada de infraestrutura, antes de
   chegarem ao domínio.

## Consequências

- Um único build serve para todos os ambientes. O deploy é copiar arquivos e, na primeira
  vez, editar o `config.json`.
- O `config.json` não pode ser cacheado pelo navegador (`cache: 'no-store'` + `.htaccess`).
- O carregamento inicial faz uma requisição a mais (o `config.json`, de poucos bytes).
- Com as rotas de várias telas (a partir do degrau 8), o uso de caminhos relativos vai
  exigir um roteamento por hash ou o ajuste do `base`. Essa decisão fica para quando o
  roteador entrar.
