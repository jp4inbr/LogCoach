# 9. Relatório sobre o Uso da Inteligência Artificial

> Estado em 04/11/2026: seções 9.2 e 9.3 com as frentes A a F. A IA dentro do produto (Gemini) é o passo 5 e ainda não está ligada; hoje o relatório sai só das regras do motor, que é o comportamento previsto no RF17 quando a IA não responde.

## 9.1 Ferramentas utilizadas

| Ferramenta | Onde | Para quê |
|---|---|---|
| Claude (Anthropic), no chat do claude.ai e como agente na IDE (Claude Code) | Desenvolvimento | Comparação de temas, escopo, pesquisa de mercado, rascunho da documentação, plano de tarefas, escrita de código e testes |
| Gemini via Vertex AI (Google Cloud) | Dentro do produto | Explicar e priorizar os erros do jogador em português |

## 9.2 Como o Claude foi usado no desenvolvimento

- Comparação entre o tema antigo (HIO) e o LogCoach.
- Pesquisa de mercado: ferramentas concorrentes, premiações (MDI, AWC), API do Warcraft Logs.
- Rascunho da documentação retroativa (itens 1 a 7) e reorganização no formato deste GitBook.
- Plano de tarefas da RT03.
- Escrita de código e testes. Em todos os casos, um integrante descreveu o que precisava, o Claude escreveu o código numa branch separada, o CI rodou lint e testes, e o código só entrou na `main` depois de testado no computador e revisado num pull request.
  - **Base técnica (frente A, Pedro, PR #1):** estrutura do backend e do frontend, linters, pre-commit e CI. O Claude no chat montou o plano e as instruções, e o agente do Claude na IDE do Pedro escreveu os arquivos. O Pedro conferiu cada etapa rodando o projeto no próprio computador.
  - **Contas, histórico e telas (frentes E e F, Pedro, PR #2):** cadastro e login, limite do plano, rotas de análise, 29 testes e as telas em React. O Claude escreveu o código e os testes; o Pedro testou o fluxo no PC e no celular; o Arthur revisou e ajustou antes do merge (ver 9.3).
  - **Documentação da RT03:** rascunho dos itens 8.1 (prints tirados da alfa), 8.3 (roteiro do teste e SUS), 10 e 12, revisados pelo grupo.
  - **Cliente do Warcraft Logs (frente B, Arthur):** cliente único da API v2 (GraphQL), lista leve de lutas, Magos Arcanos buscados por luta, pré-busca dos eventos quando o jogador é escolhido, cache de 6 h, pausa de consultas depois de falha (respeitando o `Retry-After`), limites de pontos por cliente e por hora, e erro `wcl_unavailable` com mensagem por causa (limite, fora do ar, timeout, rede). O Claude escreveu o código e os testes; o Arthur definiu os limites e conferiu as respostas na API real.
  - **Regras e guias (frente C, Arthur):** regras do Mago Arcano e do Nek'zali em YAML (`arcane_mage.yaml`, `nekzali.yaml`) e guias em português que vão para a IA. O Arthur ditou as regras como jogador; o Claude organizou em YAML e redigiu os guias, que o Arthur revisou termo a termo.
  - **Motor de análise (frente D, Arthur, passo 4, PR #27):** fases da luta, tabelas por habilidade e por alvo (jogador × tops, sempre em %), regras com limites tirados dos 10 melhores do bracket, impacto de cada erro em % do dano do próprio jogador, diferença para os tops dividida em erros + sorte + não explicado, defensivo pelos picos de dano, busca dos tops com cache de 24 h e RF21, DPS oficial do Warcraft Logs, desconto do dano creditado ao Evocador Aumentação e, por fim, o `EngineAnalyzer` ligado à rota de análises e à tela de resultado (o exemplo escrito à mão saiu).

**Método de trabalho nas frentes do Arthur (Claude Code):**

| Prática | Como funcionou |
|---|---|
| Planejamento em áreas | Antes de implementar, o pedido era dividido em áreas (features que mexem nos mesmos arquivos ou dependem umas das outras), cada uma com seu ponto de revisão. O plano do motor, por exemplo, foi aprovado em 03/11 em quatro etapas |
| Agentes em paralelo | Vários agentes implementavam ao mesmo tempo, cada um em uma worktree e com arquivos separados (ex.: agentes A, B e C em 26/10: contrato e API, configuração e WCL, frontend), em esforço médio |
| Autorrevisão | Cada agente relia o próprio diff, rodava testes e lint e apontava dúvidas antes de entregar |
| Revisão de especialista | Ao fechar cada área, uma revisão minuciosa em esforço alto sobre o diff inteiro; as correções entravam antes da área seguinte. Exemplos: `7be4265` (dados do WCL), `9ccfe6d` (picos de dano), `fa12d18` (busca dos tops), `457b15f` (DPS oficial), `e85b12d` e `02d946a` (desconto do Evocador) |
| Memória do projeto | O `CLAUDE.md` da raiz guarda contexto, decisões tomadas com data e próximos passos; toda sessão nova começa por ele, e decisões registradas não são reabertas sem falar com o Arthur |
| CI no GitHub | Lint e testes a cada push, também no Windows; nada entra na `main` com o CI vermelho |

## 9.3 Trechos gerados por IA

| Trecho | Gerado por | O que foi alterado pelo time |
|---|---|---|
| Estrutura inicial do backend e do frontend, linters e CI (PR #1) | Claude (chat) + Claude Code (IDE) | O Pedro rodou backend e frontend no PC antes de abrir o PR; o ESLint foi fixado na versão 9 porque o plugin de React pedido no item 7 não funciona na 10; o arquivo de instruções da IA e a pasta `*.egg-info` ficaram fora do Git |
| Backend de contas: cadastro, login com JWT, senha com argon2, histórico e limite de 5 análises/mês (PR #2) | Claude | Na revisão, o Arthur passou a tratar token vencido como "sem login" nas rotas públicas, aumentou a chave JWT dos testes para 32+ bytes e acrescentou a escolha do jogador por nome + reino (erro `player_ambiguous`) |
| Telas em React: início, escolha da luta, andamento, resultado, perfil e planos (PR #2) | Claude | O Pedro testou o fluxo no PC e no celular. O Arthur acrescentou a lista dos comparados com o botão de olho (RF25, requisito novo), a distinção de Magos com o mesmo nome em reinos diferentes e a checagem da sessão vencida ao abrir o site |
| Resultado de exemplo usado pelas telas antes do motor (`app/samples/analysis_*.json`) | Claude | Os números eram ilustrativos. O Arthur trocou o DPS pelos valores do kill real e apontou que os erros somavam 8,2% de perda contra uma diferença real de −14,8%. Em 04/11 o exemplo saiu, substituído pelo resultado do motor real (passo 4.3), e a conta do kill de referência fecha: 18,0% = 6,6% de erros + 9,5% de sorte + 1,9% não explicado |
| Roteiro do teste de usabilidade e questionário SUS (item 8.3) | Claude | Revisão do grupo antes do teste; o exemplo de cálculo da nota SUS foi conferido refazendo a conta |
| Cliente do Warcraft Logs: cache, pré-busca, limites e erros (frente B) | Claude Code | O Arthur definiu os tetos (pré-buscas por hora, pontos por cliente, trava de 8 s, espera de 10 s e 60 s), pediu a lista guardada com aviso quando o WCL cai e a separação entre erro do WCL (`wcl_unavailable`) e erro nosso (`unexpected_error`) |
| Regras do Arcano e do Nek'zali em YAML e guias (frente C) | Claude | O Arthur corrigiu a mecânica: Barrage com menos de 12 de Salvo é erro pelo snowball de procs de Clearcasting, não pela chance de Prismatic Bolt; entrada no Arcane Soul com menos de 12 é erro e 20+ é só o ideal; poção junto do primeiro lust e a 2ª junto de um Surge |
| Cálculo do DPS no motor | Claude Code | A IA somava o dano dos eventos. O Arthur exigiu o DPS oficial do Warcraft Logs (o mesmo do ranking): a soma incluía o dano que o WCL credita ao Evocador Aumentação que apoiou o jogador (um dos tops ficava 11% acima) |
| Desconto do Evocador Aumentação | Claude Code | O Arthur pediu que as proporções (impacto, sorte, tabelas) também saíssem sem o crédito do Evocador, descontado de cada golpe pelos buffs ativos nele; com isso o dano do motor bate com o total oficial |
| Comparação com o top 10 (RF21) | Claude Code | A proposta era tirar do top 10 qualquer log do jogador. O Arthur redefiniu: só o log analisado sai e entra o 11º; outro log do mesmo personagem (outro dia, outro grupo) conta como um top qualquer |
| Limites das regras | Claude | A IA propôs números fixos. O Arthur decidiu que os limites de desempenho saem dos 10 melhores puxados (mediana e pior dos tops), e o relatório mostra a referência usada; no YAML ficam só mecânicas do jogo e valores reserva |
| Defensivo | Claude | A versão inicial cobrava defensivo por sobreposição fixa de mecânicas. O Arthur trocou por picos de dano no log (evitável, defensivo cabia, faltou cura ou ok) |
| Prismatic Bolt | Claude Code | O Arthur pediu separar decisão (procs esperados) de sorte: azar nunca vira erro nem impacto, entra só na linha de sorte da diferença |

## 9.4 Prompt do coach (produto)

```text
Você é um coach de Mago Arcano em World of Warcraft.
Você recebe três coisas (nunca o log bruto):
1. Fatos calculados pelo motor (JSON): resultado das regras da especialização
   e do encontro, com a comparação por fase com os 10 melhores do mesmo item level.
2. O guia da luta e da especialização: como o chefe funciona, como o Mago
   Arcano deve jogar e o que NÃO é erro (ex.: segurar o Surge até 15 s para
   casar com a poção; defensivo só é cobrado em pico de dano em que a vida caiu de verdade
   e havia um disponível; dano de mecânica evitável é erro de posicionamento; vida baixa
   com pouca cura é problema da cura, não do Mago).
3. Uma tabela por fase com casts por minuto e % do dano de cada habilidade,
   do jogador e da média dos 10 melhores.
A diferença para os 10 melhores já vem dividida em três partes: erros
(soma dos impactos), sorte (procs abaixo do esperado) e não explicado.
Cada regra traz a referência usada (mediana ou pior dos tops); cite-a.
Sorte nunca é erro.
Explique, em português do Brasil, os erros de maior impacto, do mais grave
ao menos grave. Use só os números fornecidos. Não invente dados.
Para cada erro: o que aconteceu, em que fase, quanto custou e o que fazer
na próxima tentativa.

Antes de concluir, responda para si mesmo:
- O cooldown fora da janela foi erro ou uma escolha válida (ex.: segurar
  para uma janela de burst mais valiosa)?
- O erro se repete ao longo da luta ou foi pontual?
- É erro de execução (mão) ou de planejamento (quando usar)?
- O erro tem relação com uma mecânica do chefe naquele momento?
- A parte "não explicado" aparece na tabela por habilidade ou por alvo?
  Se sim, aponte como HIPÓTESE, citando os números da tabela.
Se os fatos não bastarem para responder, diga isso em vez de supor.
```

As perguntas acima são a **camada 3** do motor (ver item 12): o que não dá para virar regra fixa fica para a IA julgar, sempre a partir dos fatos calculados pelo código.

## 9.5 Validação humana vs. automação

- Todo conteúdo de WoW (regras, termos, recomendações) revisado pelo Arthur, jogador de alto nível de Mago Arcano.
- Dados de mercado e premiações conferidos nas fontes oficiais (Blizzard, Wowhead).
- Código gerado com IA só entra no repositório depois da autorrevisão, da revisão de especialista da área e dos testes passarem (604 testes Pytest passando em 04/11, com as fixtures do kill de referência e do top 10).
- Números do motor conferidos pelo Arthur contra o Warcraft Logs (DPS, tempo ativo, mortes) e contra a conta da diferença no kill de referência.

## 9.6 Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Alucinação | A IA do produto só recebe números calculados pelo código, nunca o log bruto; o prompt proíbe inventar dados |
| Informação desatualizada | Datas e números conferidos em fontes de 2026; regras em YAML atualizadas a cada patch |
| Erros de sintaxe / código errado | Linters, CI e testes Pytest; revisão de especialista ao fechar cada área |
| Regra de jogo errada proposta pela IA | Decisões de jogo só do Arthur, registradas com data no `CLAUDE.md` |
| Dependência da IA | Se a IA cair, o relatório sai só com as regras (RF17) |
| Custo | Limite de tamanho de entrada e saída por análise (RNF13) |
