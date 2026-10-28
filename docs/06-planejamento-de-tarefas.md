---
description: Organização das tarefas e prazos do time.
---

# 6. Planejamento de Tarefas (Cronograma)

O grupo acompanha o trabalho em dois lugares, que se completam:

**Planilha de entregas:** controle de prazos do grupo, mantido pelo Luiz.

{% embed url="https://docs.google.com/spreadsheets/d/1usVGNxfKOdTOzPsQEzIczHR9qQlqXamn/edit?gid=2102548923#gid=2102548923" %}

**Quadro de tarefas (GitHub Projects):** _link a adicionar_. Colunas *A fazer → Fazendo → Revisão → Feito*. Cada cartão é uma frente de trabalho; quem é responsável move o próprio cartão, e a frente concluída vai sozinha para *Feito* quando a issue é fechada.

**Detalhe de cada frente:** cada cartão do quadro é uma issue no GitHub, de #3 a #17, com responsável, situação e dependências: [issues com o rótulo `frente`](https://github.com/jp4inbr/LogCoach/issues?q=label%3Afrente). As concluídas ficam fechadas. O rótulo `RT03` marca o que é da entrega de 28/10 e `banca`, o que fica para o fim de novembro.

**Meta da RT03 (04/11/2026, adiada pelo professor; era 28/10):** versão alfa rodando com o 1º chefe (Nek'zali), documentação consolidada, relatório de IA, testes e roteiro da banca.

## 6.1 Papéis

> Cada linha é uma frente de trabalho. As frentes "a definir" estão abertas: os integrantes se inscrevem de acordo com o que conseguem entregar.

| Pessoa | Papel | Entregas |
|---|---|---|
| **Arthur** | Líder técnico + especialista do jogo | Motor de análise, regras do Mago Arcano e do encontro (mapa do Nek'zali), integração com Warcraft Logs e IA, validação de todo conteúdo de WoW |
| **Pedro** | Frontend, backend de contas e qualidade | Base técnica (linters, CI), telas em React ligadas ao backend, contas, histórico e limite do plano; evidências de usabilidade (8.1) e métricas (11) |
| **João** | GitBook | Organização e revisão das páginas no GitBook |
| **Luiz** | Gestão | Planilha de entregas, quadro no GitHub Projects, checagem de prazos |
| **Danilo** | Design | Mockups das telas no Figma (item 3) |
| **Matheus Damasceno** | Planejamento estratégico | Product Vision Board (item 2.B) |
| **Matheus Morgado** | Qualidade da Apresentação | Elaborar os slides e garantir que o material estará disponível e correto na hora da apresentação à banca |
| **Arthur** | Relatório de IA | Item 9, a partir dos prompts, interações e relatórios dos membros do grupo |
| **Arthur** | Casos de teste | Cenários de erro e validação em linguagem simples (base dos testes Pytest) e item 10 |
| _a definir_ | Teste de usabilidade | Aplicar o roteiro e o questionário SUS (8.3) e registrar os resultados |
| _a definir_ | Pesquisa | Formulário com jogadores brasileiros (evidências do problema) |
| _a definir_ | Aplicação da Usabilidade | Acompanhar como os princípios de usabilidade entram na aplicação, junto ao front/backend, e manter o item 8 |
| _a definir_ | Diagramas | Converter os fluxogramas em Mermaid (arquitetura, fluxo de telas, motor de análise, cronograma) em diagramas apresentáveis para o GitBook e os slides |

## 6.2 Cronograma

```mermaid
gantt
    dateFormat  YYYY-MM-DD
    title RT03 — LogCoach
    section Base
    Repositório, linters, CI          :2026-10-13, 2d
    Planilha e quadro de tarefas      :2026-10-13, 2d
    Docs RT01/RT02 no GitBook         :2026-10-14, 3d
    Chaves WCL + Google Cloud         :2026-10-13, 2d
    Dados de exemplo do Nek'zali      :2026-10-14, 3d
    Mapa do encontro Nek'zali         :2026-10-14, 3d
    Formulário de pesquisa            :2026-10-14, 2d
    section Construção
    Regras do Mago Arcano             :2026-10-17, 4d
    Regras do encontro + correlação   :2026-10-17, 4d
    Comparador por fase com top logs  :2026-10-19, 3d
    Integração com IA                 :2026-10-20, 3d
    Telas 1-3 em React                :2026-10-17, 6d
    Telas 4-5                         :2026-10-21, 3d
    Mockups Figma                     :2026-10-15, 5d
    Testes Pytest                     :2026-10-20, 4d
    Diagramas apresentáveis           :2026-10-20, 5d
    section Validação
    Teste de usabilidade + SUS        :2026-10-24, 2d
    Roteiro da banca                  :2026-10-24, 3d
    Docs consolidadas                 :2026-10-24, 4d
    Ensaio                            :2026-10-27, 1d
```

| Fase | Período | Principais tarefas |
|---|---|---|
| Base | 13/10 – 16/10 | Repositório e CI, quadro, docs no GitBook, chaves de API, dados de exemplo, mapa do encontro Nek'zali, formulário, mockups 1–2 |
| Construção | 17/10 – 23/10 | Regras da spec e do encontro, correlação, comparador por fase, IA, telas React, mockups 3–5, testes, diagramas apresentáveis, rascunho do relatório de IA |
| Validação | 24/10 – 27/10 | Documentação consolidada, evidências de usabilidade, testes e métricas |
| Ajuste (prazo adiado) | 28/10 – 03/11 | Motor ligado nas análises, teste de usabilidade com 5 pessoas e SUS, quadro do GitHub Projects, ensaio e divisão de fala |
| Entrega | 04/11 | RT03 |

## 6.3 Tarefas abertas depois da RT03 (para o cronograma)

Levantadas no review técnico de 26–28/10. O detalhe (onde mexer e por quê) está no `CLAUDE.md`, "Próximos passos". Falta definir dono e data no quadro.

| Tarefa | Por quê | Dono |
|---|---|---|
| Buffs externos no motor (Power Infusion, Bloodlust etc.) | A busca já traz os externos (corrigida em 28/10); falta o motor contar e mostrar como contexto, já que um top com PI a cada Surge tem vantagem | |
| Conferir no Wowhead todos os nomes em pt-BR (magias, buffs, talentos) | Há nomes divergentes entre guia, exemplo e cliente (ex.: Clearcasting = "Abstração" no Warcraft Logs em português) | |
| Motor de análise (regras, tabela por habilidade) | Hoje só o exemplo do Harmonist tem resultado | Arthur |
| Pacote da IA (Gemini) + resposta reserva | RF17, RF24 | |
| Cache e cliente único do Warcraft Logs | Cada busca pede token e baixa o relatório de novo (limite de 1000 pontos/h) | |
| Jogador pelo id do ator do Warcraft Logs | Hoje há duas regras de nome + reino | |
| Código de erro próprio para "Warcraft Logs fora do ar" | Hoje aparece como "relatório privado" | |
| Testes T03–T05, T07, T11–T14 | Dependem do motor e da IA | |

## 6.4 Riscos e plano B

| Risco                                        | Plano B                                                                   |
| -------------------------------------------- | ------------------------------------------------------------------------- |
| Arthur é o único que domina o jogo e o motor | Regras documentadas em linguagem simples (item 12) e código revisado por pelo menos mais um integrante |
| Integração com IA atrasa                     | Demo usa resposta reserva salva, informando isso ao professor             |
| Internet falha na apresentação               | Log de exemplo já processado e salvo                                      |
| Não dá tempo dos 3 chefes                    | Alfa entrega só Nek'zali; os outros serão validados perante o tempo hábil |
| Membros sem entregar                         | Luiz cobra no quadro; tarefas sem dono até 16/10 são redistribuídas       |
