# LogCoach - Coach de Desempenho para World of Warcraft

> **Status do Projeto:** Versão Alfa (Entrega RT03 - Consolidação, Usabilidade, IA e Testes)

## 1. Sobre o Projeto (Escopo RT01)

O **LogCoach** é uma aplicação web responsiva voltada ao setor de Entretenimento e Esportes Eletrônicos (e-sports) que transforma o log de combate do World of Warcraft (Warcraft Logs) — hoje um dado bruto, extenso e em inglês — em um diagnóstico claro e priorizado em português do Brasil.

A partir do link público de um relatório do Warcraft Logs, o sistema compara a luta do jogador com a média dos **10 melhores jogadores do mundo na mesma faixa de item level (bracket)**, aplica regras determinísticas da especialização e do chefe, e utiliza Inteligência Artificial para explicar em linguagem simples quais erros mais custaram dano (DPS) e o que corrigir primeiro.

- **Curso:** Engenharia de Software — Centro Universitário UNA
- **Unidade Curricular:** Usabilidade e Desenvolvimento Web (Projeto A3)
- **Recorte do MVP:** Especialização Mago Arcano (Sunfury) | Raide *The Venomous Abyss* (Midnight, Temporada 2) | Dificuldade Mítica | Chefe da Alfa: *Nek'zali, a Enrosca-almas* (Encontro 3470)

## 2. Arquitetura e Stack Tecnológica (RT02)

| Camada | Tecnologia | Responsabilidade |
| :--- | :--- | :--- |
| **Frontend** | React 19 + Vite | Interface responsiva (360px a desktop), validação de entrada e visualização do relatório |
| **Backend** | Python 3.12 + FastAPI | API REST, autenticação JWT + Argon2, controle de limite do plano e orquestração |
| **Motor de Análise** | Python (`app/engine/`) | Leitura de regras YAML (`arcane_mage.yaml` e `nekzali.yaml`), linha do tempo e comparação por fase |
| **Banco de Dados** | SQLModel (SQLite / PostgreSQL) | Persistência de usuários, histórico de análises e evolução por chefe, com atenção à conformidade com a LGPD |
| **Inteligência Artificial** | Gemini via Vertex AI (GCP) | Explicação e priorização dos erros em português a partir dos fatos estruturados |
| **Fonte de Dados** | Warcraft Logs API v2 (GraphQL) | Coleta de eventos de combate, fases e rankings por bracket de item level (OAuth2) |

## 3. Estrutura do Repositório

```text
LogCoach/
├── .github/workflows/ci.yml   # Pipeline CI: Ruff (lint/format), Pytest, ESLint e Vite Build
├── backend/                   # API FastAPI e Motor de Análise
│   ├── app/
│   │   ├── api/               # Rotas REST (/auth, /me, /reports/resolve, /analyses)
│   │   ├── engine/            # Motor determinístico (rules, timeline, prismatic_bolt, arcane_soul)
│   │   ├── rules/             # Regras da especialização (arcane_mage.yaml)
│   │   ├── encounters/        # Regras e mecânicas do chefe (nekzali.yaml)
│   │   ├── guides/            # Guias em português enviados como contexto para a IA
│   │   ├── i18n/              # Tradução de magias e NPCs por ID (pt_br.yaml)
│   │   ├── samples/           # Dados do kill de referência para modo offline/demo
│   │   ├── services/          # Interfaces ReportSource e Analyzer, planos e validação
│   │   └── wcl/               # Cliente GraphQL Warcraft Logs e anonimização (RF25)
│   ├── scripts/               # Script de coleta e anonimização de fixtures
│   └── tests/                 # Suíte de testes automatizados (Pytest + fixtures reais)
├── frontend/                  # SPA React + Vite
│   └── src/
│       ├── components/        # Componentes de UI (Timeline, MistakeCard, EvolutionChart, etc.)
│       ├── lib/               # Cliente de API, roteador hash, autenticação e formatação
│       └── pages/             # Telas (Home, Login, ChooseFight, Result, Profile, Plans)
├── docs/                      # Documentação completa sincronizada com o GitBook (Itens 01 a 14)
├── .pre-commit-config.yaml    # Hooks de pré-commit com Ruff
└── gitbook-docs.yaml          # Configuração de sincronização GitBook Git Sync
```

## 4. Gestão e Qualidade de Código (Clean Code / SOLID)

O projeto adota princípios de Clean Code e SOLID para garantir a manutenibilidade, a extensibilidade e a qualidade do código.

- **Single Responsibility (S):** Cada módulo do motor (`prismatic_bolt.py`, `arcane_soul.py` e `timeline.py`) e cada serviço possui uma responsabilidade única e isolada.

- **Open/Closed (O):** As regras da especialização e dos encontros são declaradas em arquivos YAML (`app/rules/` e `app/encounters/`), permitindo adicionar novos chefes ou ajustar parâmetros a cada patch sem alterar o código do motor (RNF12).

- **Dependency Inversion (D):** As rotas dependem das abstrações `ReportSource` e `Analyzer`, definidas em `app/services/sources.py`. Isso permite alternar entre a API real do Warcraft Logs (`DATA_SOURCE=wcl`) e os dados locais de demonstração (`DATA_SOURCE=exemplo`).

- **Análise Estática e Formatação:** O backend utiliza Ruff (`pyproject.toml`), enquanto o frontend utiliza ESLint 9 e Prettier (`eslint.config.js` e `.prettierrc`). As verificações são executadas automaticamente a cada Push ou Pull Request por meio do GitHub Actions.

- **Segurança e Privacidade (LGPD e RF25):**
  - Senhas armazenadas com hash Argon2 (RNF05).
  - Segredos isolados em variáveis de ambiente (RNF06).
  - Exclusão total da conta e do histórico (`DELETE /me`, RNF07).
  - Ocultação padrão dos nomes de outros jogadores por pseudônimos (`top01` a `top10`, RF25).

## 5. Usabilidade (ISO 9241-11 e Heurísticas de Nielsen — RT03)

O projeto implementa e demonstra as **10 heurísticas de usabilidade de Jakob Nielsen** nas telas da aplicação.

1. **Visibilidade do status:** Progresso apresentado em etapas durante a análise e medidor de uso mensal do plano na tela de perfil.

2. **Correspondência com o mundo real:** Interface e terminologia traduzidas para português do Brasil, incluindo os termos do jogo por meio de `pt_br.yaml`.

3. **Controle e liberdade:** Botões de retorno rápido, como "Trocar o link" e "Escolher outra luta", além de funcionalidades para troca de senha e exclusão da conta.

4. **Consistência e padrões:** Selos semânticos padronizados (`ok`, `atencao` e `erro`) em todas as abas da aplicação.

5. **Prevenção de erros:** Validação prévia de URLs e identificação de lutas incompatíveis. Encontros com menos de 60 segundos ou chefes não suportados são desabilitados visualmente, com explicações claras.

6. **Reconhecimento em vez de memorização:** Pré-seleção automática do personagem e apresentação da linha do tempo lado a lado com os melhores logs de referência.

7. **Flexibilidade e eficiência:** Atalho "Usar o log de exemplo" na tela inicial, permitindo testar a aplicação imediatamente, sem necessidade de cadastro (RF01).

8. **Design estético e minimalista:** Exibição priorizada dos erros de maior impacto no resumo, com informações complementares organizadas em abas.

9. **Reconhecimento e recuperação de erros:** Mensagens claras associadas a códigos de erro, como `invalid_link`, `fight_too_short` e `plan_limit`, além de mecanismo alternativo de resposta quando a IA não está disponível (RF17).

10. **Ajuda e documentação:** Glossário interativo implementado em `Term.jsx`, explicando conceitos como *bracket* de item level e tempo ativo.

## 6. Como Rodar Localmente

### 6.1. Pré-requisitos

Antes de iniciar, certifique-se de ter instalado:

- Python 3.12 ou superior, compatível com o ambiente do projeto.
- Node.js e npm.
- Git.

### 6.2. Backend (FastAPI)

No terminal, execute:

```bash
cd backend

# Criar e ativar o ambiente virtual
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1

# Instalar dependências de desenvolvimento
pip install -e ".[dev]"

# Criar arquivo de variáveis de ambiente
cp .env.example .env

# Iniciar a API
uvicorn app.main:app --reload
```

A API estará disponível em:

- **API REST:** http://localhost:8000
- **Documentação interativa (Swagger):** http://localhost:8000/docs

> **Modo de demonstração:** Sem as credenciais do Warcraft Logs configuradas, a aplicação utiliza automaticamente o modo de exemplo, conforme a configuração do projeto.

### 6.3. Frontend (React + Vite)

Em outro terminal, execute:

```bash
cd frontend

# Instalar dependências
npm install

# Iniciar o servidor de desenvolvimento
npm run dev
```

O frontend estará disponível em:

http://localhost:5173

### 6.4. Executar Testes e Verificações de Qualidade

#### Backend

```bash
cd backend

# Análise estática
ruff check

# Verificar formatação
ruff format --check

# Executar testes automatizados
pytest -v
```

#### Frontend

```bash
cd frontend

# Verificar padrões e possíveis problemas
npm run lint

# Validar a compilação de produção
npm run build
```

## 7. Documentação Completa (GitBook)

Toda a documentação acadêmica referente às entregas RT01, RT02, RT03 e à Banca Final está versionada no repositório, na pasta [`docs/`](docs/).

A estrutura de navegação e o índice dos documentos podem ser consultados em [`docs/SUMMARY.md`](docs/SUMMARY.md).

A documentação complementa este README com os requisitos, as decisões de arquitetura, os critérios de usabilidade, os detalhes de implementação e os registros das entregas acadêmicas.

## 8. Equipe de Desenvolvimento

- Arthur Beiral
- Danilo Félix
- João Nicacio
- Luís Carneiro
- Matheus Damasceno
- Matheus Morgado
- Pedro Nogueira
- Thales Almeida
- Yohanan Amaral
