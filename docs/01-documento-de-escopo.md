# 1. Documento de Escopo

## 1.1 Ficha de Inscrição

**Título provisório:** LogCoach — coach de desempenho para jogadores competitivos de World of Warcraft

**Tema:** análise automática de registros de combate com regras determinísticas e Inteligência Artificial, para jogadores brasileiros de alto nível.

**Integrantes**

| Nome                | RA  | E-mail UNA |
| ------------------- | --- | ---------- |
| Arthur Justi Beiral |     |            |
| Pedro               |     |            |
| João                |     |            |
| Luiz                |     |            |
|                     |     |            |
|                     |     |            |
|                     |     |            |
|                     |     |            |
|                     |     |            |

> Este documento é público (sincronizado com o GitHub). Não incluir e-mail pessoal, telefone ou outros dados pessoais.

## 1.2 Introdução e Contextualização

**Tipo de aplicação:** Web (responsiva, funciona no celular).

**Setor:** Entretenimento e Esportes Eletrônicos (e-sports).

World of Warcraft (WoW) é um jogo online em que grupos de 5 a 30 jogadores enfrentam chefes difíceis. No nível mais alto, isso virou competição de verdade, com torneios oficiais e premiação em dinheiro:

- **Mythic Dungeon International (MDI) 2026:** a final global aconteceu na BlizzCon 2026, nos EUA, com **US$ 300 mil** em prêmios.
- **Arena World Championship (AWC) 2026:** o lado JxJ do jogo também tem **US$ 300 mil** em prêmios na temporada.
- **Race to World First:** corrida entre as melhores guildas do mundo para derrotar primeiro o chefe final de cada raide nova, patrocinada por diversas grandes empresas de tecnologia e acompanhada ao vivo pela comunidade. Na raide atual (The Venomous Abyss), a Team Liquid venceu pela quinta vez seguida.

Para chegar nesse nível, o jogador precisa estudar o próprio desempenho. Toda luta pode ser gravada num **log de combate**, enviado ao site Warcraft Logs. O log registra cada habilidade usada, cada segundo parado, cada morte. O problema é que ele é um dado bruto: tabelas e gráficos que exigem horas e muito conhecimento para virar informação útil.

O Brasil tem comunidade própria no jogo desde 2011, com servidores nacionais e fórum oficial em português. Mesmo assim, quase todo o conteúdo avançado (guias, ferramentas, análises) está em inglês.

## 1.3 Identificação e Descrição do Problema

### Contexto e impacto

O jogador competitivo que quer melhorar tem três caminhos hoje, e todos têm custo alto:

| Caminho | Problema |
|---|---|
| Analisar o log sozinho no Warcraft Logs | Leva horas por luta e exige saber exatamente o que procurar |
| Usar ferramentas automáticas (ex.: WoWAnalyzer) | Checklists rígidos, que dão alerta falso porque ignoram o contexto da luta |
| Pagar um coach humano | Caro, depende de agenda, quase sempre em inglês |

**Impacto:**
- **Tempo:** horas de análise manual que poderiam ser horas de prática.
- **Desempenho:** erros finos (usar habilidade no momento errado do encontro, ficar parado sem lançar magia) passam despercebidos e se repetem semana após semana.
- **Acesso:** o jogador brasileiro que não domina inglês técnico fica para trás devido à não ter acesso a massiva parte do material avançado do jogo, que é em inglês.

### Evidências do problema

- **Relato de especialista do grupo:** Arthur joga de Mago Arcano, está entre os 1% da base de jogadores. Ele relata não encontrar conteúdo avançado específico da sua especialização e que o WoWAnalyzer aponta erros que, no contexto da luta, não são erros. Seus colegas de jogo também apontam a dificuldade de analisar o registro e conseguir extrair informação útil do mesmo, fazendo com que a evolução exija além de tempo, uma quantidade bem maior de repetições.
- **Mercado:** já existem ferramentas de análise (WoWAnalyzer, Warcraft Logs, WipeFest), mas são em inglês e genéricas para todas as classes. Nenhuma é focada no jogador brasileiro e as que trazem informações avançadas, não fazem de forma intuitiva e facilmente digerível.
- **Premiações:** torneios com US$ 300 mil em prêmios mostram que desempenho no WoW tem valor real, não é só lazer.
- **A coletar (até a RT03):** formulário com jogadores brasileiros em Discords e grupos de guilda, perguntando quanto tempo gastam analisando logs e quais ferramentas usam.

### Relação com princípios de usabilidade

O problema central é de usabilidade: a informação existe, mas está em formato difícil de usar.

| Princípio (Nielsen) | Como o problema aparece hoje | O que o LogCoach faz |
|---|---|---|
| Correspondência com o mundo real | Termos técnicos e em inglês | Feedback em português, na linguagem do jogador |
| Design estético e minimalista | Dezenas de tabelas e gráficos | Mostra primeiro os 3 erros que mais custam |
| Reconhecer em vez de lembrar | O jogador precisa saber o que procurar | O sistema já diz onde olhar |
| Visibilidade do status | Sem retorno de "estou melhorando?" | Histórico de análises e evolução |

## 1.4 Proposta de Solução

O jogador cola o link do seu log do Warcraft Logs. O LogCoach:

1. **Busca os dados** pela API oficial do Warcraft Logs.
2. **Compara** a luta com a média dos 10 a 20 melhores logs do mesmo chefe e dificuldade.
3. **Aplica regras fixas** da especialização (tempo parado, uso de cooldowns, uso de defensivos, mortes).
4. **A IA explica** os erros em português simples e diz o que corrigir primeiro.

**Funcionalidades principais:**
- Análise por link do Warcraft Logs, sem precisar baixar arquivo.
- Relatório com os 3 erros que mais custaram desempenho.
- Comparação lado a lado com os melhores jogadores.
- Explicação da IA em linguagem simples.
- Histórico e evolução para usuários cadastrados.
- Plano grátis (5 análises por mês) e plano pago (ilimitado).

## 1.5 Justificativa da Arquitetura: Web

| Critério | Análise |
|---|---|
| Perfil do usuário | O jogador está no computador, onde o jogo roda e onde o log é enviado. O fluxo natural é copiar o link e colar no navegador |
| Hardware necessário | Nenhum recurso de celular é necessário (GPS, câmera). Só internet |
| Distribuição | Basta um link, sem loja de aplicativos e sem instalação. Fácil de compartilhar em Discord de guilda |
| Uso no celular | O layout responsivo permite rever o relatório no celular depois |

**Decisão:** aplicação Web responsiva.

## 1.6 Fontes de Pesquisa e Referências

### Benchmarking

| Ferramenta | O que faz | Limite |
|---|---|---|
| Warcraft Logs | Guarda e mostra os logs, com rankings | Dado bruto, a análise é manual |
| WoWAnalyzer | Checklist automático por especialização, grátis | Regras rígidas, alerta falso, inglês |
| Raider.IO | Pontuação e ranking de Mítica+ | Não analisa a luta |
| Ferramentas com IA (ex.: ParsePal, WowCoach) | Feedback automático com IA | Genéricas para todas as classes, inglês |

**Diferencial do LogCoach:** especialista em uma especialização, em português, focado em dizer o que corrigir primeiro.

### Referências (ABNT)

BLIZZARD ENTERTAINMENT. **The Mythic Dungeon International returns!** 2026. Disponível em: https://worldofwarcraft.blizzard.com/news/24276958. Acesso em: 12 out. 2026.

BLIZZARD ENTERTAINMENT. **Curse of Ula'tek: The Venomous Abyss raid goes live August 18**. 2026. Disponível em: https://worldofwarcraft.blizzard.com/news/24294062. Acesso em: 12 out. 2026.

BROOKE, J. SUS: a quick and dirty usability scale. *In*: JORDAN, P. W. *et al*. (ed.). **Usability evaluation in industry**. London: Taylor & Francis, 1996. p. 189-194.

INTERNATIONAL ORGANIZATION FOR STANDARDIZATION. **ISO 9241-11:2018**: ergonomics of human-system interaction — part 11: usability: definitions and concepts. Genebra: ISO, 2018.

KRUG, S. **Não me faça pensar**: atualizado. Rio de Janeiro: Alta Books, 2014.

NIELSEN, J. **10 usability heuristics for user interface design**. Nielsen Norman Group, 1994. Disponível em: https://www.nngroup.com/articles/ten-usability-heuristics/. Acesso em: 12 out. 2026.

NORMAN, D. A. **O design do dia a dia**. Rio de Janeiro: Rocco, 2006.

TECMUNDO. **World of Warcraft**: como migrar para um servidor brasileiro? 2011. Disponível em: https://www.tecmundo.com.br/jogos/16654-world-of-warcraft-como-migrar-para-um-servidor-brasileiro-.htm. Acesso em: 12 out. 2026.

WARCRAFT LOGS. **API v2 documentation**. Disponível em: https://www.warcraftlogs.com/v2-api-docs/warcraft/. Acesso em: 12 out. 2026.

WOWHEAD. **Unveiling the AWC and MDI road to BlizzCon in 2026**. 2026. Disponível em: https://www.wowhead.com/news=380845. Acesso em: 12 out. 2026.
