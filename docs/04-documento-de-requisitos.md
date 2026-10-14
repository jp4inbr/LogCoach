# 4. Documento de Requisitos

## 4.1 Requisitos Funcionais (RF)

| ID | Requisito | Prioridade |
|---|---|---|
| RF01 | O sistema deve permitir analisar um log sem criar conta (1 análise de demonstração) | Alta |
| RF02 | O sistema deve permitir cadastro e login com e-mail e senha | Alta |
| RF03 | O sistema deve receber o link de um relatório do Warcraft Logs e validar o formato antes de enviar | Alta |
| RF04 | O sistema deve listar as lutas do relatório e os Magos Arcanos presentes, para o usuário escolher | Alta |
| RF05 | O sistema deve buscar os eventos da luta escolhida pela API do Warcraft Logs | Alta |
| RF06 | O sistema deve buscar e guardar em cache os melhores logs de Mago Arcano do mesmo chefe e dificuldade | Alta |
| RF07 | O sistema deve aplicar as regras da especialização, válidas em qualquer luta (tempo parado, uso de cooldowns, recurso desperdiçado, procs perdidos, mortes) | Alta |
| RF08 | O sistema deve calcular a diferença entre o jogador e a média dos melhores logs em cada regra | Alta |
| RF09 | O sistema deve enviar à IA só os fatos calculados pelas regras (não o log bruto), junto com as perguntas de julgamento definidas, e receber a explicação em português | Alta |
| RF10 | O sistema deve mostrar um relatório com os erros ordenados do maior para o menor impacto | Alta |
| RF11 | O sistema deve mostrar uma linha do tempo comparando o uso de cooldowns do jogador com o dos melhores | Média |
| RF12 | O sistema deve salvar o histórico de análises do usuário cadastrado | Média |
| RF13 | O sistema deve mostrar a evolução do usuário entre análises do mesmo chefe | Média |
| RF14 | O sistema deve controlar o limite do plano grátis (5 análises por mês) | Média |
| RF15 | O sistema deve mostrar a tela de planos (sem pagamento real no MVP) | Baixa |
| RF16 | O usuário deve poder perguntar ao coach sobre um erro específico do relatório | Baixa |
| RF17 | Se a IA falhar, o sistema deve mostrar o relatório só com as regras | Alta |
| RF18 | O sistema deve aplicar as regras do encontro (fases, intermissões, janelas de burst, golpes de raide e períodos em que o chefe não pode ser atacado), que ajustam as regras da especialização | Alta |
| RF19 | O sistema deve montar uma linha do tempo única da luta e cruzar os eventos do chefe com os cooldowns e defensivos do jogador | Alta |
| RF20 | A comparação com os melhores logs deve ser feita por fase (tempo relativo ao início de cada fase), não pelo tempo absoluto da luta | Alta |

> As regras funcionam em três camadas (especialização, encontro e perguntas de julgamento da IA). Detalhes no item 12.

**Vantagens para usuário cadastrado:** histórico de análises, gráfico de evolução por chefe, comparação entre duas análises suas e personagem salvo.

## 4.2 Requisitos Não Funcionais (RNF)

| ID    | Categoria      | Requisito                                                                                                     |
| ----- | -------------- | ------------------------------------------------------------------------------------------------------------- |
| RNF01 | Desempenho     | Páginas devem carregar em menos de 3 s                                                                        |
| RNF02 | Desempenho     | Uma análise completa (busca + regras + IA) deve levar menos de 2 minutos, com indicador de progresso          |
| RNF03 | Desempenho     | Os melhores logs ficam em cache por 24 h, para economizar o limite da API do Warcraft Logs                    |
| RNF04 | Segurança      | Toda comunicação por HTTPS                                                                                    |
| RNF05 | Segurança      | Senhas guardadas com hash (bcrypt ou argon2), nunca em texto                                                  |
| RNF06 | Segurança      | Chaves de API em variáveis de ambiente, fora do repositório                                                   |
| RNF07 | Privacidade    | Seguir a LGPD: só e-mail e senha como dados pessoais, com opção de excluir a conta                            |
| RNF08 | Responsividade | Funcionar de 360 px (celular) até desktop                                                                     |
| RNF09 | Usabilidade    | Um jogador sem treino deve concluir a primeira análise em até 5 minutos                                       |
| RNF10 | Usabilidade    | Nota SUS de pelo menos 68 no teste com usuários                                                               |
| RNF11 | Idioma         | Toda a interface e as respostas da IA em português do Brasil                                                  |
| RNF12 | Manutenção     | As regras ficam em arquivos de configuração (um por especialização e um por chefe), para atualizar a cada patch sem mexer no código |
| RNF13 | Custo          | Uso de IA limitado por análise (tamanho máximo de entrada e saída)                                            |

## 4.3 Rastreabilidade com usabilidade

| Heurística (Nielsen) | Requisitos |
|---|---|
| Visibilidade do status do sistema | RF13, RNF02 (barra de progresso) |
| Correspondência com o mundo real | RF09, RNF11 |
| Prevenção de erros | RF03, RF04 (lutas não suportadas em cinza) |
| Reconhecer em vez de lembrar | RF10, RF11, RF19 |
| Design estético e minimalista | RF10 (erros de maior impacto primeiro) |
| Ajudar a reconhecer e corrigir erros | RF17 e mensagens de erro (item 10) |
