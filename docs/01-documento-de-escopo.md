---
description: O que será e o que não será feito no LogCoach.
---

# 1. Documento de Escopo

{% hint style="info" %}
O **LogCoach** transforma o log de combate do World of Warcraft, hoje um dado bruto, técnico e em inglês, em um diagnóstico em português: quais erros o jogador cometeu, quanto cada um custou e o que corrigir primeiro.
{% endhint %}

## Visão geral

| Item                  | Descrição                                                                                                                                                                                          |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Nome do projeto**   | LogCoach                                                                                                                                                                                           |
| **Tipo de aplicação** | Web responsiva (funciona também no celular)                                                                                                                                                        |
| **Setor**             | Entretenimento e Esportes Eletrônicos (e-sports)                                                                                                                                                   |
| **Público-alvo**      | Jogadores competitivos brasileiros de World of Warcraft que gravam suas lutas no Warcraft Logs e querem melhorar o próprio desempenho                                                              |
| **Objetivo geral**    | Reduzir o tempo e o conhecimento técnico necessários para transformar um log de combate em informação útil, indicando em português os erros de maior impacto e a ordem em que devem ser corrigidos |
| **Papel da IA**       | Explicar os erros em linguagem simples e indicar o que corrigir primeiro                                                                                                                           |

{% hint style="info" %}
_Não joga World of Warcraft?_ Os termos do jogo e do LogCoach usados nesta documentação estão explicados no glossário abaixo.
{% endhint %}

<details>

<summary><strong>O jogo</strong></summary>

* _Chefe:_ inimigo principal de um encontro, mais forte que os demais, que exige coordenação do grupo para ser derrotado.
* _Dificuldade:_ nível de desafio de um chefe: Normal, Heroico e Mítico, do mais fácil ao mais difícil. Quanto maior, mais exigente a luta. O MVP analisa as dificuldades Heroico e Mítico.
* _Encontro:_ a luta contra um chefe específico, com regras e mecânicas próprias.
* _Expansão:_ grande atualização do jogo, com história, raides e masmorras novas. A expansão atual é Midnight.
* _Guilda:_ grupo organizado de jogadores que jogam juntos com frequência. No nível mais alto, as guildas competem como equipes, como na Race to World First.
* _JxJ (jogador contra jogador):_ modo em que jogadores enfrentam outros jogadores, em vez de chefes. É o modo disputado no AWC, em arenas: combates entre pequenas equipes de jogadores.
* _Masmorra:_ conteúdo para grupos de 5 jogadores, com uma sequência de inimigos e chefes.
* _Mítica+:_ modo competitivo das masmorras, com tempo limite e dificuldade que cresce a cada nível de chave. É a modalidade disputada no MDI. _Mítica+ alta_ são as chaves de nível mais alto, jogadas pelos jogadores mais competitivos.
* _Patch:_ atualização do jogo que pode mudar habilidades e números. Por isso, as regras do LogCoach ficam em arquivos que podem ser atualizados a cada patch.
* _Raide:_ conteúdo para grupos grandes, de até 30 jogadores, com uma sequência de chefes. Cada raide nova abre uma nova Race to World First.
* _Reino:_ servidor do jogo em que o personagem foi criado. No LogCoach, o personagem é identificado pelo nome e pelo reino.
* _Temporada:_ período dentro de uma expansão, com um conjunto próprio de raides e masmorras competitivas. The Venomous Abyss é a raide da Temporada 2 de Midnight.

</details>

<details>

<summary><strong>Competições</strong></summary>

* _AWC (Arena World Championship):_ campeonato mundial oficial de JxJ em arenas. Em 2026, distribui US$ 300 mil em prêmios na temporada.
* _BlizzCon:_ evento da Blizzard, empresa que desenvolve o World of Warcraft. Sediou a final global do MDI 2026, nos Estados Unidos.
* _MDI (Mythic Dungeon International):_ campeonato mundial oficial de Mítica+. Em 2026, teve US$ 300 mil em prêmios.
* _Race to World First:_ corrida entre as melhores guildas do mundo para derrotar primeiro o chefe final de cada raide nova, acompanhada ao vivo pela comunidade.

</details>

<details>

<summary><strong>O recorte do MVP</strong></summary>

* _Entombed Sentinels:_ segundo chefe na ordem de implementação, previsto para a versão beta. A raide se divide em dois grupos, um em cada chefe, e por isso a escolha de alvo pesa muito no dano.
* _Mago Arcano:_ especialização arcana da classe Mago e a única analisada no MVP. É a especialização que o especialista do grupo joga em alto nível.
* _Midnight:_ expansão atual do World of Warcraft.
* _Nek'zali, a Enrosca-almas_ (em inglês, Nek'zali the Soulcoiler)_:_ primeiro chefe suportado e o único analisado na versão alfa. A luta tem um alvo principal e fases bem marcadas, o que torna a comparação com os melhores logs mais justa.
* _The Lost Explorers:_ terceiro chefe na ordem de implementação, previsto para a versão beta. Três chefes lutam ao mesmo tempo, o que exige mais cuidado nas regras.
* _The Venomous Abyss:_ raide da Temporada 2 de Midnight e a única analisada no MVP. Foi nela que a Team Liquid venceu a Race to World First pela quinta vez seguida.

</details>

<details>

<summary><strong>O personagem</strong></summary>

* _Acúmulos (stacks):_ cargas de um efeito que se somam e o deixam mais forte. Algumas habilidades rendem mais quando usadas com mais acúmulos.
* _Buff:_ efeito positivo e temporário no personagem, como um aumento de dano.
* _Classe:_ tipo de personagem (por exemplo, Mago), que define o conjunto de habilidades disponíveis.
* _Especialização (spec):_ variação dentro de uma classe, com estilo de jogo e habilidades próprios. O Mago, por exemplo, tem as especializações Arcano, Fogo e Gelo.
* _Item level:_ número que mede a força do equipamento do personagem. Por isso, o LogCoach compara o jogador apenas com quem está na mesma faixa de item level (ver Bracket).
* _Poção:_ item consumível que dá um bônus temporário. O momento em que o jogador usa a segunda poção da luta é uma das métricas comparadas com os melhores.
* _Proc:_ efeito que ativa por chance ao usar uma habilidade, normalmente deixando a próxima mais forte ou gratuita. Proc perdido é o efeito que expira sem ser aproveitado.
* _Recurso:_ o que as habilidades gastam para serem usadas, como mana. Recurso desperdiçado é o que se perde sem virar dano.
* _Rotação:_ sequência e prioridade de habilidades que o jogador repete para causar o máximo de dano. Quem ainda está aprendendo a rotação básica fica fora do público do MVP.

</details>

<details>

<summary><strong>A luta</strong></summary>

* _Adds:_ inimigos secundários que aparecem durante a luta contra o chefe.
* _Cast:_ o uso de uma habilidade (lançar uma magia). Casts por minuto é quantas vezes a habilidade foi usada a cada minuto. O LogCoach compara por minuto porque a duração das fases muda de uma luta para outra.
* _Cooldown (CD):_ habilidade forte que, depois de usada, leva um tempo para ficar disponível de novo. Usá-la no momento errado do encontro desperdiça seu potencial.
* _Defensivos:_ habilidades que reduzem o dano recebido ou ajudam o jogador a não morrer. No LogCoach, o defensivo só é cobrado nos picos de dano em que duas mecânicas do chefe caem juntas (ver Overlap de mecânicas).
* _DPS (dano por segundo):_ principal medida de desempenho de quem causa dano. É o número que o LogCoach compara com a média dos melhores.
* _Escolha de alvo:_ decidir qual inimigo atacar quando há mais de um ao mesmo tempo. Em lutas com vários chefes ou adds, essa escolha muda muito o dano.
* _Fase:_ etapa da luta, com mecânicas próprias. Nos logs em inglês, as fases aparecem como Stage (por exemplo, Stage Two = Fase 2).
* _Golpe de raide:_ ataque do chefe que atinge o grupo inteiro de uma vez.
* _Intermissão:_ intervalo entre fases em que o chefe não pode ser atacado. O tempo parado durante a intermissão não conta como erro.
* _Janela de burst:_ momento da luta em que vale concentrar os cooldowns ofensivos para causar o máximo de dano, como o início de uma fase.
* _Kill:_ tentativa em que o chefe foi derrotado.
* _Log de combate:_ registro detalhado de uma luta, com cada habilidade usada, cada segundo parado e cada morte.
* _Mecânica:_ ação do chefe que o grupo precisa tratar, como um golpe em toda a raide ou uma troca de fase.
* _Overlap de mecânicas:_ quando duas mecânicas do chefe acontecem ao mesmo tempo, formando um pico de dano. É o momento em que se espera o uso de defensivo.
* _Tempo ativo:_ parte da luta em que o jogador está usando habilidades. É o contrário do tempo parado.
* _Tempo parado:_ período em que o jogador não está usando habilidades. Na prática, é desempenho perdido.
* _Tentativa (pull):_ cada vez que o grupo enfrenta o chefe, do início da luta até a vitória (kill) ou a derrota (wipe).
* _Wipe:_ tentativa em que o grupo inteiro morreu antes de derrotar o chefe.

</details>

<details>

<summary><strong>Habilidades do Mago Arcano</strong></summary>

* _Surto Arcano_ (em inglês, Arcane Surge)_:_ principal cooldown ofensivo do Mago Arcano. Nos melhores logs, é usado a cada 93 segundos, em média.
* _Toque dos Magos_ (em inglês, Touch of the Magi)_:_ cooldown que marca o alvo e, alguns segundos depois, causa um dano extra proporcional ao dano acumulado nele. Os melhores jogadores usam o Toque e o Surto Arcano com poucos segundos de diferença.

</details>

<details>

<summary><strong>Termos do LogCoach</strong></summary>

* _1º colocado geral:_ o melhor log do chefe naquela dificuldade, sem filtro de item level. É usado como comparação quando o jogador já está no Top 10 do seu bracket.
* _Bracket:_ faixa de item level usada pelo Warcraft Logs, de 3 em 3 níveis (por exemplo, 326–328). O LogCoach compara o jogador só com quem está no mesmo bracket, para que a diferença mostrada seja de execução, e não de equipamento.
* _Coach:_ a parte do LogCoach que, com IA, explica os erros em português e diz o que corrigir primeiro.
* _Diferença não explicada:_ parte da diferença de dano de uma fase que nenhuma regra explica. Serve de sinal para a IA investigar a tabela de habilidades daquela fase.
* _Hipótese do coach:_ algo que a IA apontou fora das regras. Aparece no relatório marcado como hipótese, com os números ao lado.
* _Ranking:_ lista dos melhores desempenhos em cada chefe e dificuldade, publicada pelo Warcraft Logs.
* _Regras da especialização:_ regras fixas que valem em qualquer luta, como tempo parado, uso de cooldowns, recurso desperdiçado, procs perdidos e mortes.
* _Regras do encontro:_ regras que descrevem cada chefe (fases, intermissões, janelas de burst e golpes de raide) e ajustam as regras da especialização.
* _Relatório (report):_ registro de uma sessão de raide enviado ao Warcraft Logs, com várias lutas. É o link desse relatório que o jogador cola no LogCoach.
* _Top 10 (tops):_ os 10 melhores logs de Mago Arcano no mesmo chefe, dificuldade e bracket do jogador. A média deles é a referência de comparação.

</details>

<details>

<summary><strong>As ferramentas</strong></summary>

* _ParsePal e WowCoach:_ ferramentas que usam IA para dar feedback automático. São genéricas para todas as classes e em inglês.
* _Raider.IO:_ site de pontuação e ranking de Mítica+. Não analisa a luta.
* _Warcraft Logs:_ site onde os jogadores enviam seus logs de combate para visualizá-los e compará-los em rankings. É a fonte dos dados analisados pelo LogCoach.
* _WoWAnalyzer:_ ferramenta gratuita que gera um checklist automático por especialização a partir do log. É em inglês e usa regras rígidas, que dão alerta falso por ignorar o contexto da luta.

</details>

***

## 1.1 Introdução e Contextualização

**Tipo de aplicação:** Web (responsiva, funciona no celular).

**Setor:** Entretenimento e Esportes Eletrônicos (e-sports).

World of Warcraft (WoW) é um jogo online em que grupos de 5 a 30 jogadores enfrentam chefes difíceis. No nível mais alto, isso virou competição de verdade, com torneios oficiais e premiação em dinheiro:

{% tabs %}
{% tab title="MDI 2026" %}
**Mythic Dungeon International (MDI) 2026**

A final global aconteceu na BlizzCon 2026, nos Estados Unidos, com **US$ 300 mil em prêmios**.
{% endtab %}

{% tab title="AWC 2026" %}
**Arena World Championship (AWC) 2026**

Representa o lado JxJ (jogador contra jogador) do jogo e também distribui **US$ 300 mil em prêmios** na temporada.
{% endtab %}

{% tab title="Race to World First" %}
**Race to World First**

Corrida entre as melhores guildas do mundo para derrotar primeiro o chefe final de cada raide nova. O evento é patrocinado por diversas grandes empresas de tecnologia e acompanhado ao vivo pela comunidade. Na raide atual, _The Venomous Abyss_, a **Team Liquid venceu pela quinta vez seguida**.
{% endtab %}
{% endtabs %}

Chegar a esse nível exige mais do que horas de jogo. O jogador precisa **estudar o próprio desempenho**. Para isso, toda luta pode ser gravada em um **log de combate** e enviada ao site **Warcraft Logs**. O log registra cada habilidade usada, cada segundo em que o jogador ficou parado e cada morte.

O obstáculo é que esse log é um **dado bruto**: tabelas e gráficos que exigem horas de análise e muito conhecimento do jogo para virar informação útil. A informação necessária para evoluir já existe, mas não está pronta para ser usada.

{% hint style="info" %}
**Recorte brasileiro:** o Brasil tem comunidade própria no jogo desde 2011, com servidores nacionais e fórum oficial em português. Mesmo assim, quase todo o conteúdo avançado (guias, ferramentas e análises) está em inglês.
{% endhint %}

***

## 1.2 Identificação e Descrição do Problema

### Contexto e impacto

O jogador competitivo que quer melhorar tem três caminhos hoje, e todos têm custo alto:

| Caminho                                         | Problema                                                                   |
| ----------------------------------------------- | -------------------------------------------------------------------------- |
| Analisar o log sozinho no Warcraft Logs         | Leva horas por luta e exige saber exatamente o que procurar                |
| Usar ferramentas automáticas (ex.: WoWAnalyzer) | Checklists rígidos, que dão alerta falso porque ignoram o contexto da luta |
| Pagar um coach humano                           | Caro, depende de agenda, quase sempre em inglês                            |

Esse custo aparece em três dimensões:

{% tabs %}
{% tab title="Tempo" %}
São horas de análise manual que poderiam ser horas de prática. Cada sessão gasta interpretando um log é uma sessão a menos de treino dentro do jogo.
{% endtab %}

{% tab title="Desempenho" %}
Erros finos passam despercebidos, como usar uma habilidade no momento errado do encontro ou ficar parado sem lançar magia. Como não são identificados, se repetem semana após semana.
{% endtab %}

{% tab title="Acesso" %}
O jogador brasileiro que não domina inglês técnico fica para trás, porque não tem acesso à maior parte do material avançado do jogo, que é produzido em inglês.
{% endtab %}
{% endtabs %}

### Evidências do problema

{% stepper %}
{% step %}
#### Relato de especialista do grupo

**Arthur**, integrante do grupo, joga de **Mago Arcano** e está entre o **1% melhor** da base de jogadores.

Mesmo nesse patamar, Arthur relata não encontrar conteúdo avançado específico da sua especialização. Ele também aponta que o WoWAnalyzer marca como erros ações que, no contexto daquela luta, não são erros. A análise automática genérica, portanto, não só deixa de ajudar: pode levar o jogador a "corrigir" o que estava certo.

Os colegas de jogo de Arthur confirmam a dificuldade de analisar o registro e extrair dele informação útil. Com isso, evoluir exige não só mais tempo, mas também muito mais repetições até que o erro seja percebido e corrigido.
{% endstep %}

{% step %}
#### Mercado

Já existem ferramentas de análise, do Warcraft Logs ao WoWAnalyzer e a soluções com IA como ParsePal e WowCoach, mas todas em inglês. As automáticas aplicam regras rígidas ou genéricas, sem considerar o contexto da luta. Nenhuma é focada no jogador brasileiro, e as que trazem informações avançadas não fazem isso de forma intuitiva e fácil de digerir.
{% endstep %}

{% step %}
#### Premiações

Torneios com US$ 300 mil em prêmios mostram que desempenho no WoW tem valor real e não é só lazer. Para quem compete, cada melhoria de desempenho tem impacto concreto.
{% endstep %}
{% endstepper %}

### Relação com princípios de usabilidade

O problema central do LogCoach é de **usabilidade**: a informação existe, mas está em um formato difícil de usar. O jogador já tem acesso aos dados. O que falta é chegar ao que importa sem horas de análise e sem domínio de inglês técnico.<br>

<details>

<summary>O que diz a ABNT NBR ISO 9241-11</summary>

A norma define usabilidade como a medida em que um produto pode ser usado por usuários específicos para atingir objetivos específicos com **eficácia**, **eficiência** e **satisfação**, em um contexto de uso específico.

Aplicado ao problema:

* **Eficácia:** o jogador consegue descobrir o que corrigir? Hoje, erros finos passam despercebidos e a análise genérica aponta falsos erros.
* **Eficiência:** com quanto esforço? Hoje, horas de análise manual e muito conhecimento técnico.

</details>

A tabela abaixo reúne os princípios de usabilidade (heurísticas de Nielsen) mais críticos para este problema: como cada um falha hoje e como o LogCoach responde.

| Princípio (Nielsen)                       | Como o problema aparece hoje           | O que o LogCoach faz                           |
| ----------------------------------------- | -------------------------------------- | ---------------------------------------------- |
| **H1 · Visibilidade do status**           | Sem retorno de "estou melhorando?"     | Histórico de análises e evolução               |
| **H2 · Correspondência com o mundo real** | Termos técnicos e em inglês            | Feedback em português, na linguagem do jogador |
| **H6 · Reconhecer em vez de lembrar**     | O jogador precisa saber o que procurar | O sistema já diz onde olhar                    |
| **H8 · Design estético e minimalista**    | Dezenas de tabelas e gráficos          | Mostra primeiro os erros que mais custam       |

***

## 1.3 Proposta de Solução

O LogCoach começa com uma ação simples: **o jogador cola o link do seu log do Warcraft Logs**. A partir daí, o sistema executa quatro etapas:

{% stepper %}
{% step %}
#### Busca dos dados

O LogCoach busca os dados da luta pela API oficial do Warcraft Logs. O jogador não precisa baixar nem enviar nenhum arquivo.
{% endstep %}

{% step %}
#### Comparação com os melhores

A luta é comparada com a média dos 10 melhores logs do mesmo chefe e da mesma dificuldade, na mesma faixa de item level do jogador. Assim, o jogador é medido contra quem enfrentou o mesmo desafio com equipamento equivalente.
{% endstep %}

{% step %}
#### Regras da especialização

O sistema aplica regras fixas da especialização e avalia quatro pontos: tempo parado, uso de cooldowns, uso de defensivos e mortes.
{% endstep %}

{% step %}
#### Explicação pela IA

A IA explica os erros encontrados em português simples e indica o que corrigir primeiro.
{% endstep %}
{% endstepper %}

{% hint style="info" %}
**Dados e regras encontram os erros; a IA explica.** A identificação dos erros vem de dados reais (a comparação com os melhores logs) e de regras fixas da especialização. A IA entra na etapa final: traduz o resultado em linguagem simples e indica a prioridade de correção.
{% endhint %}

#### Funcionalidades principais

| Funcionalidade             | O que entrega ao jogador                                                |
| -------------------------- | ----------------------------------------------------------------------- |
| **Análise por link**       | Análise a partir do link do Warcraft Logs, sem precisar baixar arquivo  |
| **Relatório priorizado**   | Erros que mais custaram desempenho, do maior para o menor impacto       |
| **Comparação lado a lado** | Desempenho do jogador ao lado da média dos melhores jogadores           |
| **Explicação por IA**      | Erros explicados em português, em linguagem simples                     |
| **Histórico e evolução**   | Acompanhamento da evolução ao longo do tempo, para usuários cadastrados |

#### Planos

{% columns %}
{% column %}
**Grátis**

5 análises por mês.
{% endcolumn %}

{% column %}
**Pago**

Análises ilimitadas.
{% endcolumn %}
{% endcolumns %}



***

## 1.4 Justificativa da Arquitetura: Web

{% hint style="info" %}
**Decisão:** aplicação Web responsiva.
{% endhint %}

A escolha parte do contexto real de uso. O jogador já está no computador quando o log é gerado e enviado, e a única entrada de que o LogCoach precisa é um link.

| Critério                | Análise                                                                                                                     |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| **Perfil do usuário**   | O jogador está no computador, onde o jogo roda e onde o log é enviado. O fluxo natural é copiar o link e colar no navegador |
| **Hardware necessário** | Nenhum recurso de celular é necessário (GPS, câmera). Só internet                                                           |
| **Distribuição**        | Basta um link, sem loja de aplicativos e sem instalação. Fácil de compartilhar em Discord de guilda                         |
| **Uso no celular**      | O layout responsivo permite rever o relatório no celular depois                                                             |

Além disso, os dados vêm da API oficial do Warcraft Logs, que é uma integração web. Assim, todo o fluxo, da origem do log ao relatório final, acontece dentro do navegador.

A escolha vem do próprio fluxo de uso:

* **A entrada é um link de site.** O jogador pega o link do log no Warcraft Logs, que é um site, e cola no LogCoach.
* **A integração é web.** Os dados vêm da API oficial do Warcraft Logs.
* **Nenhum recurso de hardware é necessário.** A solução não depende de GPS, câmera ou outros recursos do aparelho.
* **Acesso em qualquer tela.** Por ser responsiva, a aplicação também funciona no celular, sem instalação.

***

## 1.5 Fontes de Pesquisa e Referências

### Benchmarking

| Ferramenta                                       | O que faz                                       | Limite                                  |
| ------------------------------------------------ | ----------------------------------------------- | --------------------------------------- |
| **Warcraft Logs**                                | Guarda e mostra os logs, com rankings           | Dado bruto, a análise é manual          |
| **WoWAnalyzer**                                  | Checklist automático por especialização, grátis | Regras rígidas, alerta falso, inglês    |
| **Raider.IO**                                    | Pontuação e ranking de Mítica+                  | Não analisa a luta                      |
| **Ferramentas com IA** (ex.: ParsePal, WowCoach) | Feedback automático com IA                      | Genéricas para todas as classes, inglês |

O mercado se divide em dois grupos:

* Ferramentas que **guardam e ranqueiam** dados (Warcraft Logs, Raider.IO). Elas deixam toda a interpretação para o jogador.
* Ferramentas que **analisam** (WoWAnalyzer e soluções com IA). Elas automatizam a análise, mas com regras rígidas ou abordagem genérica, e em inglês.

{% hint style="info" %}
**Diferencial do LogCoach:** especialista em uma especialização, em português e focado em dizer o que corrigir primeiro.
{% endhint %}

### Referências (ABNT)

<details>

<summary>Referências</summary>

BLIZZARD ENTERTAINMENT. **The Mythic Dungeon International returns!** 2026. Disponível em: https://worldofwarcraft.blizzard.com/news/24276958. Acesso em: 12 out. 2026.

BLIZZARD ENTERTAINMENT. **Curse of Ula'tek: The Venomous Abyss raid goes live August 18**. 2026. Disponível em: https://worldofwarcraft.blizzard.com/news/24294062. Acesso em: 12 out. 2026.

BROOKE, J. SUS: a quick and dirty usability scale. _In_: JORDAN, P. W. _et al_. (ed.). **Usability evaluation in industry**. London: Taylor & Francis, 1996. p. 189-194.

INTERNATIONAL ORGANIZATION FOR STANDARDIZATION. **ISO 9241-11:2018**: ergonomics of human-system interaction — part 11: usability: definitions and concepts. Genebra: ISO, 2018.

KRUG, S. **Não me faça pensar**: atualizado. Rio de Janeiro: Alta Books, 2014.

NIELSEN, J. **10 usability heuristics for user interface design**. Nielsen Norman Group, 1994. Disponível em: https://www.nngroup.com/articles/ten-usability-heuristics/. Acesso em: 12 out. 2026.

NORMAN, D. A. **O design do dia a dia**. Rio de Janeiro: Rocco, 2006.

TECMUNDO. **World of Warcraft**: como migrar para um servidor brasileiro? 2011. Disponível em: https://www.tecmundo.com.br/jogos/16654-world-of-warcraft-como-migrar-para-um-servidor-brasileiro-.htm. Acesso em: 12 out. 2026.

WARCRAFT LOGS. **API v2 documentation**. Disponível em: https://www.warcraftlogs.com/v2-api-docs/warcraft/. Acesso em: 12 out. 2026.

WOWHEAD. **Unveiling the AWC and MDI road to BlizzCon in 2026**. 2026. Disponível em: https://www.wowhead.com/news=380845. Acesso em: 12 out. 2026.

</details>

***

## 1.6Limitações (fora do escopo)

Para entregar uma análise de fato especializada, o LogCoach tem um escopo propositalmente restrito nesta versão. O que fica dentro e o que fica fora:

{% columns %}
{% column %}
**✅ Dentro do escopo**

* Especialização **Mago Arcano**
* Lutas contra **chefes de raide**, comparadas por chefe e dificuldade
* Análise a partir do **link do Warcraft Logs**
* Feedback em **português**
* Aplicação **web responsiva**
{% endcolumn %}

{% column %}
**❌ Fora do escopo**

* Outras especializações e classes
* Modo JxJ (arenas)
* Masmorras Mítica+
* Envio de arquivo de log
* Logs privados ou inacessíveis pelo link
* Outros idiomas
* Aplicativo móvel nativo
* Análise em tempo real, durante a luta
{% endcolumn %}
{% endcolumns %}

{% hint style="success" %}
**O recorte é a estratégia, não uma fraqueza.** As ferramentas atuais cobrem todas as classes e, por isso, aplicam regras rígidas que dão alerta falso fora do contexto da luta. Concentrar o LogCoach em uma única especialização é o que permite ter regras que entendem esse contexto, validadas por um jogador que está entre o 1% melhor dessa especialização.
{% endhint %}

**Por que cada item fica fora**

<details>

<summary>Outras especializações e classes</summary>

O diferencial do LogCoach é ser especialista em uma especialização. As regras fixas de análise (tempo parado, uso de cooldowns, uso de defensivos e mortes) são próprias de cada especialização, e as do Mago Arcano são validadas pelo especialista do grupo. Incluir novas especializações exigiria escrever novas regras e ter alguém com domínio delas para validá-las.

</details>

<details>

<summary>Modo JxJ (arenas)</summary>

O LogCoach compara a luta do jogador com os melhores logs do mesmo chefe e da mesma dificuldade. No JxJ, modo disputado no AWC, o adversário são outros jogadores. Não existe chefe nem dificuldade fixa que sirva de base de comparação.

</details>

<details>

<summary>Envio de arquivo de log</summary>

A análise parte do link do Warcraft Logs, e os dados são buscados pela API oficial. O jogador não precisa baixar nem enviar nenhum arquivo, e essa simplicidade faz parte da proposta.

</details>

<details>

<summary>Logs privados ou inacessíveis pelo link</summary>

O LogCoach depende dos dados que a API oficial do Warcraft Logs disponibiliza a partir do link. Logs que não estejam acessíveis por esse caminho não podem ser analisados. Nesses casos, o sistema informa claramente o motivo e o que o jogador pode fazer (heurística 9: ajudar o usuário a reconhecer e se recuperar de erros).

</details>

<details>

<summary>Outros idiomas</summary>

O problema que o LogCoach resolve é justamente a barreira do inglês para o jogador brasileiro. Todo o feedback é em português.

</details>

<details>

<summary>Aplicativo móvel nativo</summary>

A plataforma escolhida é web responsiva. O jogador já está no computador quando envia o log, e o uso no celular é atendido pelo layout responsivo, sem instalação.

</details>

<details>

<summary>Análise em tempo real, durante a luta</summary>

O fluxo do LogCoach começa depois da luta: o log já foi enviado ao Warcraft Logs e o jogador cola o link. O sistema analisa lutas concluídas e não acompanha a luta enquanto ela acontece.

</details>

