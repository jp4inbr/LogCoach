---
description: Visão e modelo de negócio do LogCoach em uma página.
---

# 2. Planejamento Estratégico do Produto

{% hint style="info" %}
Esta página registra como o LogCoach evoluiu depois da RT01: o feedback recebido, o recorte do MVP,  e o roadmap até a banca.
{% endhint %}

### 2.1 Feedback incorporado após a RT01

<table><thead><tr><th width="335.25">Feedback do professor</th><th width="402.75">Mudança no escopo</th></tr></thead><tbody><tr><td><strong>Focar no jogador competitivo, de alto nível</strong></td><td>Público definido como quem joga raide Heroica/Mítica e Mítica+ alta. Quem está aprendendo a rotação básica fica fora do MVP</td></tr><tr><td><strong>Destacar as premiações para mostrar valor</strong></td><td>O contexto do projeto abre com MDI e AWC 2026 (US$ 300 mil cada) e com a Race to World First</td></tr><tr><td><strong>Focar no público brasileiro no MVP</strong></td><td>Interface, relatório e respostas da IA só em português. Inglês fica para depois</td></tr></tbody></table>

{% hint style="success" %}
**Resultado:** o LogCoach ficou mais estreito e mais profundo. Em vez de atender qualquer jogador, atende quem já joga em alto nível e precisa de análise fina, em português.
{% endhint %}

***

### 2.2 Recorte do MVP

Para que a análise seja realmente especializada já na primeira versão, o MVP foi recortado em uma especialização, uma raide, três chefes e duas dificuldades:

<table data-search="false"><thead><tr><th width="192.75">Item</th><th width="545.25">Decisão</th></tr></thead><tbody><tr><td><strong>Especialização</strong></td><td>Mago Arcano</td></tr><tr><td><strong>Conteúdo</strong></td><td>Raide The Venomous Abyss (Midnight, Temporada 2)</td></tr><tr><td><strong>Chefes</strong></td><td>1º Nek'zali the Soulcoiler, 2º Entombed Sentinels, 3º The Lost Explorers</td></tr><tr><td><strong>Dificuldades</strong></td><td>Heroico e Mítico</td></tr><tr><td><strong>Entrada</strong></td><td>Link do relatório no Warcraft Logs</td></tr><tr><td><strong>Comparação</strong></td><td>Média dos 10 melhores logs de Mago Arcano no mesmo chefe e dificuldade, na mesma faixa de item level do jogador</td></tr><tr><td><strong>IA</strong></td><td>Gemini via Vertex AI (Google Cloud)</td></tr><tr><td><strong>Idioma</strong></td><td>Português</td></tr></tbody></table>

#### Ordem dos chefes

A ordem de implementação segue a complexidade de cada luta. Quanto mais alvos ao mesmo tempo, mais a escolha de alvo influencia o dano, e mais cuidado as regras de comparação exigem.

<table><thead><tr><th width="70.25">Ordem</th><th width="130.25">Chefe</th><th width="209.75">Como é a luta</th><th width="320.25">Impacto na análise</th></tr></thead><tbody><tr><td><strong>1º</strong></td><td>Nek'zali the Soulcoiler</td><td>Um alvo principal, com fases bem marcadas</td><td>Comparação com os melhores logs mais justa. </td></tr><tr><td><strong>2º</strong></td><td>Entombed Sentinels</td><td>A raide se divide em dois grupos, um em cada chefe</td><td>A escolha de alvo muda muito o dano; as regras precisam de mais cuidado</td></tr><tr><td><strong>3º</strong></td><td>The Lost Explorers</td><td>Três chefes ao mesmo tempo</td><td>A escolha de alvo muda muito o dano; as regras precisam de mais cuidado</td></tr></tbody></table>

{% hint style="info" %}
**Por que Nek'zali primeiro:** com um alvo principal e fases bem marcadas, a comparação com os 10 melhores logs fica mais justa. É o cenário ideal para validar o método antes de partir para as lutas com vários alvos.
{% endhint %}

***

### 2.3 Roadmap

{% stepper %}
{% step %}
#### Alfa · RT03 (28/10/2026)

Análise elaborada da luta contra Nek'zali, explicação por IA e histórico de análises.
{% endstep %}

{% step %}
#### Beta · Banca / Expo Una (nov/2026)

Inclusão dos chefes Entombed Sentinels e The Lost Explorers e teste com jogadores.
{% endstep %}

{% step %}
#### Pós-MVP · 2027

Mais especializações, Mítica+, versão em inglês e pagamento real.
{% endstep %}
{% endstepper %}
