---
description: Requisitos funcionais e não funcionais do LogCoach.
---

# 4. Documento de Requisitos

## 4.1 Requisitos Funcionais (RF)

<details>

<summary><strong>RF01. Análise demo sem cadastro</strong></summary>

O sistema deve permitir analisar um log sem criar conta (1 análise de demonstração).

{% hint style="info" %}
**Prioridade:** **Alta**
{% endhint %}

</details>

<details>

<summary><strong>RF02. Cadastro e login</strong></summary>

O sistema deve permitir cadastro e login com e-mail e senha.

{% hint style="info" %}
**Prioridade:** **Alta**
{% endhint %}

</details>

<details>

<summary><strong>RF03. Envio e validação do link do relatório</strong></summary>

O sistema deve receber o link de um relatório do Warcraft Logs e validar o formato antes de enviar.

{% hint style="info" %}
**Prioridade:** **Alta**
{% endhint %}

</details>

<details>

<summary><strong>RF04. Seleção de luta e jogador</strong></summary>

O sistema deve listar as lutas do relatório e os Magos Arcanos presentes, para o usuário escolher.

{% hint style="info" %}
**Prioridade:** **Alta**
{% endhint %}

</details>

<details>

<summary><strong>RF05. Coleta de eventos da luta</strong></summary>

O sistema deve buscar os eventos da luta escolhida pela API do Warcraft Logs.

{% hint style="info" %}
**Prioridade:** **Alta**
{% endhint %}

</details>

<details>

<summary><strong>RF06. Benchmark dos melhores logs (com cache)</strong></summary>

O sistema deve buscar e guardar em cache os melhores logs de Mago Arcano do mesmo chefe, dificuldade e faixa de item level do jogador (bracket do Warcraft Logs).

{% hint style="info" %}
**Prioridade:** **Alta**
{% endhint %}

</details>

<details>

<summary><strong>RF07. Regras da especialização</strong></summary>

O sistema deve aplicar as regras da especialização, válidas em qualquer luta (tempo parado, uso de cooldowns, recurso desperdiçado, procs perdidos, mortes).

{% hint style="info" %}
**Prioridade:** **Alta**
{% endhint %}

</details>

<details>

<summary><strong>RF08. Comparação com a média dos melhores</strong></summary>

O sistema deve calcular a diferença entre o jogador e a média dos melhores logs em cada regra.

{% hint style="info" %}
**Prioridade:** **Alta**
{% endhint %}

</details>

<details>

<summary><strong>RF09. Explicação por IA com contexto estruturado</strong></summary>

O sistema deve enviar à IA, sem o log bruto: os fatos calculados pelas regras, o guia da luta e da especialização, a tabela comparativa por habilidade (RF22) e as perguntas de julgamento; e receber a explicação em português.

{% hint style="info" %}
**Prioridade:** **Alta**
{% endhint %}

</details>

<details>

<summary><strong>RF10. Relatório de erros por impacto</strong></summary>

O sistema deve mostrar um relatório com os erros ordenados do maior para o menor impacto.

{% hint style="info" %}
**Prioridade:** **Alta**
{% endhint %}

</details>

<details>

<summary><strong>RF11. Timeline comparativa de cooldowns</strong></summary>

O sistema deve mostrar uma linha do tempo comparando o uso de cooldowns do jogador com o dos melhores.

{% hint style="info" %}
**Prioridade:** **Média**
{% endhint %}

</details>

<details>

<summary><strong>RF12. Histórico de análises</strong></summary>

O sistema deve salvar o histórico de análises do usuário cadastrado.

{% hint style="info" %}
**Prioridade:** **Média**
{% endhint %}

</details>

<details>

<summary><strong>RF13. Evolução por chefe</strong></summary>

O sistema deve mostrar a evolução do usuário entre análises do mesmo chefe.

{% hint style="info" %}
**Prioridade:** **Média**
{% endhint %}

</details>

<details>

<summary><strong>RF14. Limite do plano grátis</strong></summary>

O sistema deve controlar o limite do plano grátis (5 análises por mês).

{% hint style="info" %}
**Prioridade:** **Média**
{% endhint %}

</details>

<details>

<summary><strong>RF15. Tela de planos</strong></summary>

O sistema deve mostrar a tela de planos (sem pagamento real no MVP).

{% hint style="info" %}
**Prioridade:** **Baixa**
{% endhint %}

</details>

<details>

<summary><strong>RF16. Chat com o coach</strong></summary>

O usuário deve poder perguntar ao coach sobre um erro específico do relatório.

{% hint style="info" %}
**Prioridade:** **Baixa**
{% endhint %}

</details>

<details>

<summary><strong>RF17. Fallback sem IA</strong></summary>

Se a IA falhar, o sistema deve mostrar o relatório só com as regras.

{% hint style="info" %}
**Prioridade:** **Alta**
{% endhint %}

</details>

<details>

<summary><strong>RF18. Regras do encontro</strong></summary>

O sistema deve aplicar as regras do encontro (fases, intermissões, janelas de burst, golpes de raide e períodos em que o chefe não pode ser atacado), que ajustam as regras da especialização.

{% hint style="info" %}
**Prioridade:** **Alta**
{% endhint %}

</details>

<details>

<summary><strong>RF19. Linha do tempo unificada da luta</strong></summary>

O sistema deve montar uma linha do tempo única da luta e cruzar os eventos do chefe com os cooldowns e defensivos do jogador.

{% hint style="info" %}
**Prioridade:** **Alta**
{% endhint %}

</details>

<details>

<summary><strong>RF20. Comparação por fase</strong></summary>

A comparação com os melhores logs deve ser feita por fase (tempo relativo ao início de cada fase), não pelo tempo absoluto da luta.

{% hint style="info" %}
**Prioridade:** **Alta**
{% endhint %}

</details>

<details>

<summary><strong>RF21. Comparação para jogadores Top 10</strong></summary>

Se o jogador já estiver entre os 10 melhores da sua faixa de item level, o sistema deve reconhecer isso no relatório e comparar com o 1º colocado geral do chefe.

{% hint style="info" %}
**Prioridade:** **Média**
{% endhint %}

</details>

<details>

<summary><strong>RF22. Tabela de habilidades por fase</strong></summary>

O sistema deve montar, por fase, uma tabela com casts por minuto e % do dano de cada habilidade do jogador, ao lado da média dos 10 melhores da mesma faixa de item level, mesmo para habilidades sem regra própria.

{% hint style="info" %}
**Prioridade:** **Alta**
{% endhint %}

</details>

<details>

<summary><strong>RF23. Diferença não explicada</strong></summary>

O sistema deve marcar a diferença de dano por fase que as regras não explicam ("diferença não explicada"), para a IA investigar na tabela do RF22.

{% hint style="info" %}
**Prioridade:** **Média**
{% endhint %}

</details>

<details>

<summary><strong>RF24. Hipóteses da IA e revisão de regras</strong></summary>

O que a IA apontar fora das regras deve aparecer no relatório como hipótese, com os números do código ao lado, e ficar registrado para revisão (possível regra nova).

{% hint style="info" %}
**Prioridade:** **Média**
{% endhint %}

</details>

<details>

<summary><strong>RF25. Nomes de outros jogadores no</strong> relatório</summary>

Os nomes dos outros jogadores no relatório (os melhores logs comparados e o resto da raide) devem vir ocultos por padrão, com pseudônimos ("Top 1", "Top 2"…), e o usuário deve poder exibi-los com um botão, como o "ocultar saldo" de um app de banco. O jogador analisado aparece sempre com o próprio nome

{% hint style="info" %}
**Prioridade:** **Média**
{% endhint %}

</details>

**Vantagens para usuário cadastrado:** histórico de análises, gráfico de evolução por chefe, comparação entre duas análises suas e personagem salvo.

## 4.2 Requisitos Não Funcionais (RNF)

<details>

<summary><strong>RNF01. Carregamento de páginas em até 3 s</strong></summary>

As páginas do sistema devem carregar em menos de 3 segundos.

{% hint style="info" %}
**Categoria: Desempenho**
{% endhint %}

</details>

<details>

<summary><strong>RNF02. Análise completa em até 2 min, com progresso</strong></summary>

Uma análise completa, que inclui a busca dos dados, a aplicação das regras e a geração da explicação pela IA, deve terminar em menos de 2 minutos. Enquanto a análise roda, o sistema deve mostrar ao usuário um indicador de progresso.

{% hint style="info" %}
**Categoria: Desempenho**
{% endhint %}

</details>

<details>

<summary><strong>RNF03. Cache de 24 h dos melhores logs</strong></summary>

Os melhores logs consultados devem ficar em cache por 24 horas. Isso evita requisições repetidas e economiza o limite de uso da API do Warcraft Logs.

{% hint style="info" %}
**Categoria: Desempenho**
{% endhint %}

</details>

<details>

<summary><strong>RNF04. Comunicação via HTTPS</strong></summary>

Toda a comunicação do sistema deve ser feita por HTTPS, para que os dados trafeguem criptografados.

{% hint style="info" %}
**Categoria: Segurança**
{% endhint %}

</details>

<details>

<summary><strong>RNF05. Senhas armazenadas com hash</strong></summary>

As senhas dos usuários devem ser guardadas apenas como hash, gerado com bcrypt ou argon2. A senha nunca deve ser armazenada em texto puro.

{% hint style="info" %}
**Categoria: Segurança**
{% endhint %}

</details>

<details>

<summary><strong>RNF06. Chaves de API fora do repositório</strong></summary>

As chaves de API usadas pelo sistema devem ficar em variáveis de ambiente e nunca devem ser incluídas no repositório de código.

{% hint style="info" %}
**Categoria: Segurança**
{% endhint %}

</details>

<details>

<summary><strong>RNF07. Conformidade com a LGPD</strong></summary>

O sistema deve seguir a LGPD e coletar como dados pessoais apenas o e-mail e a senha do usuário. O usuário deve poder excluir a própria conta.

{% hint style="info" %}
**Categoria: Privacidade**
{% endhint %}

</details>

<details>

<summary><strong>RNF08. Layout responsivo a partir de 360 px</strong></summary>

A interface deve funcionar corretamente em telas de qualquer largura entre 360 px, tamanho de um celular, e um desktop.

{% hint style="info" %}
**Categoria: Responsividade**
{% endhint %}

</details>

<details>

<summary><strong>RNF09. Primeira análise em até 5 min</strong></summary>

Um jogador que nunca recebeu treinamento no sistema deve conseguir concluir a primeira análise em até 5 minutos.

{% hint style="info" %}
**Categoria: Usabilidade**
{% endhint %}

</details>

<details>

<summary><strong>RNF10. Nota SUS mínima de 68</strong></summary>

No teste com usuários, o sistema deve alcançar nota de pelo menos 68 na escala SUS (System Usability Scale).

{% hint style="info" %}
**Categoria: Usabilidade**
{% endhint %}

</details>

<details>

<summary><strong>RNF11. Interface e IA em português do Brasil</strong></summary>

Toda a interface do sistema e todas as respostas geradas pela IA devem estar em português do Brasil.

{% hint style="info" %}
**Categoria: Idioma**
{% endhint %}

</details>

<details>

<summary><strong>RNF12. Regras configuráveis por arquivo</strong></summary>

As regras de análise devem ficar em arquivos de configuração: um arquivo para cada especialização e um para cada chefe. Assim, as regras podem ser atualizadas a cada patch sem alterar o código.

{% hint style="info" %}
**Categoria: Manutenção**
{% endhint %}

</details>

<details>

<summary><strong>RNF13. Limite de uso de IA por análise</strong></summary>

O uso de IA em cada análise deve ser limitado, com um tamanho máximo para o conteúdo enviado e para a resposta recebida, para controlar o custo.

{% hint style="info" %}
**Categoria: Custo**
{% endhint %}

</details>

## 4.3 Rastreabilidade com usabilidade

| Heurística (Nielsen)                 | Requisitos                                           |
| ------------------------------------ | ---------------------------------------------------- |
| Visibilidade do status do sistema    | RF13, RNF02 (barra de progresso)                     |
| Correspondência com o mundo real     | RF09, RNF11                                          |
| Prevenção de erros                   | RF03, RF04 (lutas não suportadas em cinza)           |
| Reconhecer em vez de lembrar         | RF10, RF11, RF19                                     |
| Design estético e minimalista        | RF10 (erros de maior impacto primeiro)               |
| Ajudar a reconhecer e corrigir erros | RF17 e mensagens de erro (item 10)                   |
| Controle e liberdade do usuário      | RF25 (o usuário escolhe mostrar ou ocultar os nomes) |
