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
