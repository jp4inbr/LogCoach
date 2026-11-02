# 9. Relatório sobre o Uso da Inteligência Artificial

> Entrega da RT03. Seções 9.2 e 9.3 com os exemplos das frentes A, E e F; falta a parte do Arthur (frentes B, C e D).

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
  - _Arthur: acrescentar o uso na frente dele (cliente do Warcraft Logs, regras do Arcano e do Nek'zali, guias)._

## 9.3 Trechos gerados por IA

| Trecho | Gerado por | O que foi alterado pelo time |
|---|---|---|
| Estrutura inicial do backend e do frontend, linters e CI (PR #1) | Claude (chat) + Claude Code (IDE) | O Pedro rodou backend e frontend no PC antes de abrir o PR; o ESLint foi fixado na versão 9 porque o plugin de React pedido no item 7 não funciona na 10; o arquivo de instruções da IA e a pasta `*.egg-info` ficaram fora do Git |
| Backend de contas: cadastro, login com JWT, senha com argon2, histórico e limite de 5 análises/mês (PR #2) | Claude | Na revisão, o Arthur passou a tratar token vencido como "sem login" nas rotas públicas, aumentou a chave JWT dos testes para 32+ bytes e acrescentou a escolha do jogador por nome + reino (erro `player_ambiguous`) |
| Telas em React: início, escolha da luta, andamento, resultado, perfil e planos (PR #2) | Claude | O Pedro testou o fluxo no PC e no celular. O Arthur acrescentou a lista dos comparados com o botão de olho (RF25, requisito novo), a distinção de Magos com o mesmo nome em reinos diferentes e a checagem da sessão vencida ao abrir o site |
| Resultado de exemplo usado pelas telas antes do motor (`app/samples/analysis_*.json`) | Claude | Os números eram ilustrativos. O Arthur trocou o DPS pelos valores calculados do kill real e apontou na revisão que os erros listados somavam 8,2% de perda contra uma diferença real de −14,8%; a correção está com ele |
| Roteiro do teste de usabilidade e questionário SUS (item 8.3) | Claude | Revisão do grupo antes do teste; o exemplo de cálculo da nota SUS foi conferido refazendo a conta |
| _Arthur: cliente do Warcraft Logs, regras e guias_ |  |  |

## 9.4 Prompt do coach (produto)

```text
Você é um coach de Mago Arcano em World of Warcraft.
Você recebe três coisas (nunca o log bruto):
1. Fatos calculados pelo motor (JSON): resultado das regras da especialização
   e do encontro, com a comparação por fase com os 10 melhores do mesmo item level.
2. O guia da luta e da especialização: como o chefe funciona, como o Mago
   Arcano deve jogar e o que NÃO é erro (ex.: segurar o Surge até 15 s para
   casar com a poção; defensivo só é esperado em overlap de mecânicas).
3. Uma tabela por fase com casts por minuto e % do dano de cada habilidade,
   do jogador e da média dos 10 melhores.
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
- Na tabela por habilidade, existe alguma diferença grande que nenhuma regra
  explicou? Se sim, aponte como HIPÓTESE, citando os números da tabela.
Se os fatos não bastarem para responder, diga isso em vez de supor.
```

As perguntas acima são a **camada 3** do motor (ver item 12): o que não dá para virar regra fixa fica para a IA julgar, sempre a partir dos fatos calculados pelo código.

## 9.5 Validação humana vs. automação

- Todo conteúdo de WoW (regras, termos, recomendações) revisado pelo Arthur, jogador de alto nível de Mago Arcano.
- Dados de mercado e premiações conferidos nas fontes oficiais (Blizzard, Wowhead).
- Código gerado com IA só entra no repositório depois de revisão e dos testes passarem.

## 9.6 Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Alucinação | A IA do produto só recebe números calculados pelo código, nunca o log bruto; o prompt proíbe inventar dados |
| Informação desatualizada | Datas e números conferidos em fontes de 2026; regras em YAML atualizadas a cada patch |
| Erros de sintaxe / código errado | Linters, CI e testes Pytest |
| Dependência da IA | Se a IA cair, o relatório sai só com as regras (RF17) |
| Custo | Limite de tamanho de entrada e saída por análise (RNF13) |
