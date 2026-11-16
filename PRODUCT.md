# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**Foco principal:** jogadores competitivos brasileiros de World of Warcraft, que buscam o top 1% ou top 0,1%, jogam Mago Arcano em raide e já gravam suas lutas no Warcraft Logs. São quem mais usa esse tipo de ferramenta. Depois de uma sessão de raide, querem saber o que mudar na próxima tentativa sem gastar horas lendo tabelas.

**Também precisam conseguir usar:** jogadores que querem melhorar, mas ainda não estão nesse nível, ou que jogam de forma mais relaxada. O produto serve a eles sem baixar a precisão que o público principal exige.

**Quem avalia o trabalho acadêmico:** a banca da UNA e os participantes do teste de usabilidade (3 jogadores e 2 leigos). Precisam conseguir acompanhar o fluxo e o relatório, mas não definem o nível de detalhe do produto.

## Product Purpose

O LogCoach transforma o log de combate do World of Warcraft, um dado bruto, técnico e em inglês, em um diagnóstico em português: quais erros o jogador cometeu, quanto cada um custou e o que corrigir primeiro.

O jogador cola o link público do relatório, escolhe a luta e o personagem e recebe o resultado. O sucesso é o jogador chegar à primeira correção útil sem horas de análise manual e confiar no que leu.

Metas registradas: primeira análise em até 5 minutos (RNF09), análise completa em até 2 minutos com progresso visível (RNF02), nota SUS de pelo menos 68 (RNF10) e taxa de sucesso nas tarefas de pelo menos 80%.

## Positioning

Especialista em uma única especialização, em português e focado em dizer o que corrigir primeiro.

O mecanismo: as regras do Mago Arcano e de cada chefe foram definidas por um jogador do 1% melhor dessa especialização, e cada limite de desempenho sai dos 10 melhores logs do mesmo chefe, dificuldade e faixa de item level do jogador. O motor encontra os erros com dados e a IA só explica. Isso evita o alerta falso dos checklists rígidos, que ignoram o contexto da luta, e a resposta genérica das ferramentas de IA para todas as classes.

Referências de mercado registradas: Warcraft Logs e Raider.IO guardam e ranqueiam, deixando a interpretação para o jogador; WoWAnalyzer, ParsePal e WowCoach analisam, mas em inglês e com regras rígidas ou abordagem genérica.

## Operating Context

- O jogador está no computador, onde o jogo roda e o log é enviado: copia o link do Warcraft Logs e cola no navegador. O celular serve para rever o relatório depois.
- O link circula em Discord de guilda; basta um link, sem instalação.
- O fluxo é: início, escolher luta e personagem, resultado; perfil com histórico e evolução; planos. Dá para fazer 1 análise sem conta.
- A análise acontece depois da luta. Com o log ao vivo, a lista de lutas se atualiza durante a sessão de raide.
- O relatório será demonstrado na entrega acadêmica, e o modo de exemplo garante a demonstração sem internet.

## Capabilities and Constraints

**Recorte atual:** Mago Arcano, raide The Venomous Abyss, Nek'zali, a Enrosca-almas, somente na dificuldade Mítica. Outros chefes aparecem na lista, mas não podem ser analisados.

**O que existe:** análise por link público do Warcraft Logs; comparação com os 10 melhores do mesmo bracket; regras com a referência usada; diferença para os tops separada em erros, sorte e não explicado; tabelas por habilidade e por alvo, por fase; linha do tempo; contas, histórico e evolução; tema claro e escuro.

**Ainda não ligado:** a explicação pela IA (Gemini via Vertex AI). Por enquanto o relatório sai só com as regras, e esse também é o comportamento reserva quando a IA falhar (RF17).

**Fora do escopo do trabalho acadêmico:** outras classes e especializações, JxJ, Mítica+, envio de arquivo de log, logs privados, outros idiomas, aplicativo nativo e análise em tempo real.

**Regras de produto que não mudam sem falar com o especialista do grupo:** comparação só com o mesmo bracket; valores em porcentagem, nunca dano bruto; a IA não consulta o Warcraft Logs nem faz contas; nunca enviar o log bruto ou nomes reais à IA. As decisões detalhadas estão no `CLAUDE.md`.

**Planos:** Grátis com 5 análises por mês. Pro aparece como "Em breve", sem preço e sem pagamento real.

**Terminologia:** interface e relatório em português do Brasil, com os nomes do cliente do jogo em pt-BR. Termos como bracket, tops e tempo ativo fazem parte da linguagem do jogador e têm explicação disponível na interface.

**Decisões em aberto:**

- Depois da banca final (fim de novembro de 2026), a intenção é criar um fork para uso real e divulgar entre amigos, o que exige trabalho adicional, inclusive adaptar o produto para inglês. Escopo, data e público desse fork não estão definidos.
- Preço, lançamento e conteúdo definitivo do plano Pro não estão definidos.

## Brand Commitments

- O nome do produto é LogCoach, e "coach" é a parte que explica os erros em português.
- A voz é a de um coach direto, em linguagem simples, que diz o que mudar. Azar nunca é cobrado como erro, e o que for hipótese da IA aparece marcado como hipótese.
- O padrão de cores existente está em `docs/15-padrao-de-cores.md`. Decisões visuais não pertencem a este arquivo.

## Evidence on Hand

- Kill de referência do Nek'zali Mítico e top 10 do bracket, usados no modo de exemplo (`backend/app/samples/`) e nos testes (`backend/tests/fixtures/`).
- Relato do especialista do grupo, no 1% melhor de Mago Arcano, sobre alertas falsos do WoWAnalyzer e falta de conteúdo avançado (`docs/01-documento-de-escopo.md`).
- Prints da versão alfa em `docs/08-principios-de-usabilidade.md`.

**Ausências que não podem ser inventadas:** não há depoimentos, clientes, números de uso, preço nem benchmarks de melhora dos jogadores. Os resultados do teste de usabilidade (SUS e tarefas) ainda não foram preenchidos.

## Product Principles

1. **Confiança no diagnóstico vem primeiro.** Quando houver conflito, não se sacrifica a confiança: sem alerta falso, azar separado de erro, toda cobrança com a referência usada e hipóteses marcadas, mesmo que a tela fique mais longa.
2. **Dizer o que corrigir primeiro.** O jogador recebe prioridades pelo custo real, não um inventário de métricas.
3. **Dados e regras encontram os erros; a IA explica.** Todo número vem do código, e o relatório continua útil sem a IA.
4. **Comparação justa.** A diferença mostrada deve ser de execução, não de equipamento: mesmo chefe, dificuldade e bracket, sempre em porcentagem.
5. **Profundidade para o competitivo, caminho para quem quer melhorar.** O nível de detalhe atende quem disputa o topo, e quem joga de forma mais relaxada ainda consegue entender o que fazer.

## Accessibility & Inclusion

- Interface e explicações em português do Brasil, porque a barreira do inglês técnico é parte do problema (RNF11).
- Layout utilizável a partir de 360 px de largura (RNF08).
- Contraste WCAG 2.x AA nos dois temas: 4,5:1 para texto e 3:1 para elementos gráficos, verificado por teste automatizado.
- Cor nunca é a única pista: erros e avisos sempre têm texto, ícone ou selo.
- Nomes dos outros jogadores ocultos por padrão, com opção de exibir (RF25); o jogador analisado nunca é ocultado.
