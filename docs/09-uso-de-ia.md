# 9. Relatório sobre o Uso da Inteligência Artificial

> Entrega da RT03. Esqueleto pronto; completar com exemplos reais de prompts e código.

## 9.1 Ferramentas utilizadas

| Ferramenta | Onde | Para quê |
|---|---|---|
| Claude (Anthropic) | Desenvolvimento | Comparação de temas, escopo, pesquisa de mercado, rascunho da documentação, plano de tarefas, apoio no código |
| Gemini via Vertex AI (Google Cloud) | Dentro do produto | Explicar e priorizar os erros do jogador em português |
| _outras (Copilot etc.), se usadas_ |  |  |

## 9.2 Como o Claude foi usado no desenvolvimento

- Comparação entre o tema antigo (Central de Rotinas) e o LogCoach.
- Pesquisa de mercado: ferramentas concorrentes, premiações (MDI, AWC), API do Warcraft Logs.
- Rascunho da documentação retroativa (itens 1 a 7) e reorganização no formato deste GitBook.
- Plano de tarefas da RT03.
- Apoio na escrita de código e testes: _detalhar_.

## 9.3 Trechos gerados por IA

| Trecho | Gerado por | O que foi alterado pelo time |
|---|---|---|
| _ex.: prompt do coach_ |  |  |
| _ex.: regra de tempo parado_ |  |  |

## 9.4 Prompt do coach (produto)

```text
Você é um coach de Mago Arcano em World of Warcraft.
Receba os resultados das regras (JSON) e explique, em português do Brasil,
os 3 erros de maior impacto, do mais grave ao menos grave.
Use só os números fornecidos. Não invente dados.
Para cada erro: o que aconteceu, quanto custou e o que fazer na próxima tentativa.
```

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
