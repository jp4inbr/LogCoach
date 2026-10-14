# 2. Planejamento Estratégico do Produto

## 2.1 Feedback incorporado após a RT01

| Feedback do professor | Mudança no escopo |
|---|---|
| Focar no jogador competitivo, de alto nível | Público definido como quem joga raide Heroica/Mítica e Mítica+ alta. Quem está aprendendo a rotação básica fica fora do MVP |
| Destacar as premiações para mostrar valor | O contexto do projeto abre com MDI e AWC 2026 (US$ 300 mil cada) e com a Race to World First |
| Focar no público brasileiro no MVP | Interface, relatório e respostas da IA só em português. Inglês fica para depois |

## 2.2 Recorte do MVP

| Item | Decisão |
|---|---|
| Especialização | Mago Arcano |
| Conteúdo | Raide The Venomous Abyss (Midnight, Temporada 2) |
| Chefes | 1º Nek'zali the Soulcoiler (obrigatório na demo), 2º Entombed Sentinels, 3º The Lost Explorers |
| Dificuldades | Heroico e Mítico |
| Entrada | Link do relatório no Warcraft Logs |
| Comparação | Média dos 10 a 20 melhores logs de Mago Arcano no mesmo chefe e dificuldade |
| IA | Gemini via Vertex AI (Google Cloud) |
| Idioma | Português |

**Por que Nek'zali primeiro:** é uma luta de um alvo principal, com fases bem marcadas, o que deixa a comparação com os melhores logs mais justa. Entombed Sentinels divide a raide em dois grupos, um em cada chefe, e The Lost Explorers tem três chefes ao mesmo tempo. Nessas duas, a escolha de alvo muda muito o dano, então as regras precisam de mais cuidado.

## 2.3 Lean Canvas

| Bloco | Conteúdo |
|---|---|
| **Problema** | 1) Log de combate é dado bruto, difícil de interpretar. 2) Ferramentas atuais são rígidas e geram alerta falso. 3) Conteúdo avançado quase todo em inglês |
| **Segmento de clientes** | Jogadores brasileiros de WoW no nível competitivo (raide Heroica/Mítica, Mítica+ alta). Early adopters: jogadores de Mago Arcano |
| **Proposta única de valor** | "Cole o link do seu log e saiba, em português, os erros que mais estão te custando dano, sem horas de análise manual" |
| **Solução** | Regras fixas da especialização + comparação com os melhores logs + explicação por IA |
| **Canais** | Discords de guildas e de classe, fórum oficial em português, criadores de conteúdo brasileiros |
| **Fontes de receita** | Plano grátis (5 análises/mês) e plano pago (proposta: R$ 14,90/mês, ilimitado) |
| **Estrutura de custos** | Hospedagem e IA no Google Cloud (créditos disponíveis), domínio, manutenção das regras a cada atualização do jogo |
| **Métricas-chave** | Análises por semana, usuários que voltam para uma 2ª análise, conversão grátis → pago, nota SUS |
| **Vantagem injusta** | Conhecimento profundo de jogador de alto nível dentro do time e foco exclusivo no público brasileiro |

## 2.4 Roadmap

| Fase    | Quando                      | Entrega                                                         |
| ------- | --------------------------- | --------------------------------------------------------------- |
| Alfa    | RT03 (28/10/2026)           | Nek'zali, análise elaborada, IA, histórico                      |
| Beta    | Banca / Expo Una (nov/2026) | + Entombed Sentinels e The Lost Explorers, teste com jogadores  |
| Pós-MVP | 2027                        | Mais especializações, Mítica+, versão em inglês, pagamento real |
