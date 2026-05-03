# Work Plan: Smart Playlist Genre Expansion

## TL;DR

> **Quick Summary**: Implementar expansão de gêneros em playlists smart, permitindo que um gênero pai (ex: Electronic) expanda automaticamente para todos seus subgêneros (House, Techno, Trance, etc.)
> 
> **Deliverables**:
> - `data/genre_hierarchy.json` - Mapeamento pai→filhos
> - `app/features/smart_playlists/expansion.py` - Lógica de expansão
> - Parser estendido com sintaxe `:expand`
> - Builder com método `.with_subgenres()`
> - Comando CLI `analyze-genres` para sugerir grupos
> 
> **Estimated Effort**: Medium (3-4 dias)
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Task 1 → Task 2 → Task 5 → Task 9 → F1-F4

---

## Context

### Original Request
Usuário quer criar playlists smart baseadas em gêneros musicais que englobam todos seus subgêneros. Exemplo: "Música Eletrônica" incluiria House, Techno, Trance, Drum & Bass, EDM, etc.

### Interview Summary
**Key Discussions**:
- Sistema atual usa formato NSP (Navidrome Smart Playlist) sem suporte nativo a hierarquia
- Genre Guard já mantém 596 keywords em `data/musical_keywords.json`
- Estratégia híbrida escolhida: mapeamento manual + inferência automática + análise de biblioteca

**Technical Decisions**:
1. Sintaxe de query: `genre:electronic:expand`
2. Inferência por padrão de nome: "Deep House" contém "House"
3. Máximo 5 gêneros pais iniciais
4. Comando de análise read-only (sugestões, não modificação)

### Metis Review
**Identified Gaps** (addressed in plan):
- **Critical**: Definir 5 gêneros pais exatos + seus filhos
- **Critical**: Validar estrutura atual do query_parser.py antes de estender
- **Guardrail**: Análise de biblioteca é read-only, nunca modifica arquivos
- **Guardrail**: Sem expansão multinível (avô→pai→filho)
- **Edge cases**: Tratar gêneros não encontrados, case sensitivity, caracteres especiais

---

## Work Objectives

### Core Objective
Implementar sistema de expansão de gêneros que permita queries do tipo `genre:electronic:expand` serem convertidas automaticamente para múltiplas regras OR com todos subgêneros de Electronic.

### Concrete Deliverables
- `data/genre_hierarchy.json` com 5 gêneros pais + ~20 subgêneros cada
- Extensão do parser para suportar `:expand` suffix
- Extensão do builder com método `.with_subgenres()`
- Módulo `expansion.py` com lógica de inferência automática
- Comando CLI `./run.sh analyze-genres` para análise da biblioteca
- Testes unitários para parser, builder e expansion

### Definition of Done
- [ ] `./run.sh analyze-genres --help` funciona
- [ ] Query `genre:electronic:expand` expande para subgêneros
- [ ] Inferência automática detecta padrões (ex: "Deep House" → "House")
- [ ] Todos testes passam: `python -m unittest tests/test_smart_playlists/`
- [ ] Documentação atualizada (se houver)

### Must Have
- 5 gêneros pais definidos: Electronic, Rock, Hip Hop, Jazz, Brasileiras
- ~20 subgêneros por pai (mínimo 10)
- Sintaxe `:expand` funcionando no parser
- Inferência por substring case-insensitive
- Fallback para match literal se expansão falhar
- Validação de schema do JSON de hierarquia

### Must NOT Have (Guardrails)
- **MUST NOT**: Modificar metadados/tags dos arquivos de música
- **MUST NOT**: Criar mudanças de schema no banco de dados
- **MUST NOT**: Adicionar UI web ou APIs REST
- **MUST NOT**: Integrar com APIs externas (MusicBrainz, etc.)
- **MUST NOT**: Suportar exclusões (ex: `:expand:-house`)
- **MUST NOT**: Suportar expansão multinível (avô→pai→filho)
- **MUST NOT**: Auto-modificar hierarchy.json (sugestões apenas)
- **MUST NOT**: Modificar módulo genre_guard (read-only)
- **MUST NOT**: Modificar navidrome_client.py

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (unittest já configurado)
- **Automated tests**: Tests-after (implementar testes após código)
- **Framework**: Python unittest (padrão do projeto)

### QA Policy
Every task MUST include agent-executed QA scenarios:
- **Backend**: Use Bash (unittest runner) - Executar testes, verificar output
- **CLI**: Use Bash (command execution) - Validar comandos funcionam
- Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation - pode começar imediatamente):
├── Task 1: Validar estrutura atual do sistema
├── Task 2: Criar genre_hierarchy.json com 5 pais
└── Task 3: Criar módulo expansion.py com inferência

Wave 2 (Core - depende Wave 1):
├── Task 4: Estender query_parser.py com :expand
├── Task 5: Estender builder.py com .with_subgenres()
└── Task 6: Adicionar validação de schema

Wave 3 (CLI & Tests - depende Wave 2):
├── Task 7: Criar comando CLI analyze-genres
├── Task 8: Escrever testes unitários
└── Task 9: Testes de integração e edge cases

Wave FINAL (Review - 4 agentes paralelos):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)
```

### Dependency Matrix
- **Task 2**: - → Task 3, 4, 5, 1
- **Task 3**: Task 2 → Task 4, 5, 2
- **Task 4**: Task 2, 3 → Task 7, 8, 3
- **Task 5**: Task 2, 3 → Task 7, 8, 3
- **Task 7**: Task 4, 5 → Task 9, 4
- **Task 8**: Task 4, 5 → Task 9, 4
- **Task 9**: Task 7, 8 → F1-F4, 5

### Agent Dispatch Summary
- **Wave 1**: quick (3 tasks - validação e estrutura base)
- **Wave 2**: quick/unspecified-high (3 tasks - parser e builder)
- **Wave 3**: quick/unspecified-high (3 tasks - CLI e testes)
- **FINAL**: oracle/unspecified-high/deep (4 tasks - review)

---

## TODOs

- [x] 1. Validar Estrutura Atual do Sistema

  **What to do**:
  - Ler e analisar `app/features/smart_playlists/query_parser.py` - confirmar como o parser funciona atualmente
  - Ler `app/features/smart_playlists/builder.py` - entender API fluente atual
  - Ler `data/musical_keywords.json` - confirmar estrutura dos dados
  - Documentar pontos de extensão identificados

  **Must NOT do**:
  - Não modificar nenhum arquivo existente nesta task
  - Não assumir estrutura sem confirmar no código

  **Recommended Agent Profile**:
  - **Category**: `deep` - Análise profunda do código existente
  - **Skills**: N/A - apenas leitura e análise

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 4, 5
  - **Blocked By**: None

  **References**:
  - `app/features/smart_playlists/query_parser.py:1-88` - Parser atual
  - `app/features/smart_playlists/builder.py:1-139` - Builder atual
  - `data/musical_keywords.json:1-622` - Keywords existentes

  **Acceptance Criteria**:
  - [ ] Documento de análise criado com pontos de extensão identificados
  - [ ] Confirmado que parser usa split por `:` (para adicionar `:expand`)
  - [ ] Confirmado que builder tem estrutura fluente compatível

  **QA Scenarios**:
  ```
  Scenario: Validar estrutura do parser
    Tool: Read
    Steps:
      1. Ler query_parser.py completo
      2. Identificar método _parse_term (linha 45)
      3. Confirmar que usa split por ':' (linha 51)
    Expected Result: Parser usa split por dois-pontos, permite extensão
    Evidence: .sisyphus/evidence/task-1-parser-structure.txt
  ```

  **Commit**: NO (análise apenas)

- [x] 2. Criar genre_hierarchy.json com 5 Gêneros Pais

  **What to do**:
  - Criar `data/genre_hierarchy.json` com estrutura JSON válida
  - Definir 5 gêneros pais: Electronic, Rock, Hip Hop, Jazz, Brasileiras
  - Cada pai deve ter ~20 subgêneros (mínimo 10)
  - Usar dados de `musical_keywords.json` como base
  - Adicionar schema version no JSON

  **Conteúdo sugerido (Electronic)**:
  ```json
  {
    "version": 1,
    "updated_at": "2026-01-01T00:00:00",
    "hierarchy": {
      "electronic": [
        "house", "techno", "trance", "drum & bass", "dubstep",
        "edm", "ambient", "idm", "electro", "synthpop",
        "breakbeat", "downtempo", "trip hop", "glitch", "hardcore",
        "industrial", "minimal", "progressive", "tech house", "deep house"
      ],
      "rock": [...],
      "hip_hop": [...],
      "jazz": [...],
      "brasileiras": [...]
    }
  }
  ```

  **Must NOT do**:
  - Não criar mais de 5 pais nesta versão inicial
  - Não usar caracteres especiais não-ASCII sem normalização

  **Recommended Agent Profile**:
  - **Category**: `quick` - Criação de arquivo JSON
  - **Skills**: N/A

  **Parallelization**:
  - **Can Run In Parallel**: YES (com Task 1)
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 3, 4, 5
  - **Blocked By**: None

  **References**:
  - `data/musical_keywords.json` - Fonte de subgêneros válidos

  **Acceptance Criteria**:
  - [ ] Arquivo `data/genre_hierarchy.json` criado
  - [ ] JSON válido com campos: version, updated_at, hierarchy
  - [ ] 5 gêneros pais definidos
  - [ ] Mínimo 10 subgêneros por pai
  - [ ] `python -c "import json; json.load(open('data/genre_hierarchy.json'))"` → sucesso

  **QA Scenarios**:
  ```
  Scenario: Validar JSON structure
    Tool: Bash
    Steps:
      1. python -c "import json; data=json.load(open('data/genre_hierarchy.json')); print('OK')"
      2. Verificar que 'hierarchy' tem 5 keys
      3. Verificar que cada key tem lista de strings
    Expected Result: JSON válido, estrutura correta
    Evidence: .sisyphus/evidence/task-2-json-validation.txt
  ```

  **Commit**: YES
  - Message: `feat(smart-playlists): add genre hierarchy data file`
  - Files: `data/genre_hierarchy.json`

- [x] 3. Criar Módulo expansion.py com Inferência Automática

  **What to do**:
  - Criar `app/features/smart_playlists/expansion.py`
  - Implementar classe `GenreExpander` com métodos:
    - `__init__(hierarchy_file_path)` - carrega hierarchy.json
    - `expand(parent_genre)` → lista de subgêneros
    - `infer_parent(child_genre)` → pai inferido ou None
    - `find_matches(pattern)` → subgêneros que contêm padrão
  - Implementar inferência por substring case-insensitive
  - Implementar cache em memória para performance

  **Algoritmo de Inferência**:
  ```python
  def infer_parent(self, child_genre: str) -> Optional[str]:
      """Ex: 'Deep House' → 'electronic' (porque contém 'house')"""
      normalized = child_genre.lower()
      for parent, children in self.hierarchy.items():
          # Check if child contains any parent's subgenre
          for sub in children:
              if sub.lower() in normalized:
                  return parent
      return None
  ```

  **Must NOT do**:
  - Não implementar fuzzy matching complexo (apenas substring)
  - Não implementar ML ou heurísticas complexas

  **Recommended Agent Profile**:
  - **Category**: `quick` - Módulo Python simples
  - **Skills**: N/A

  **Parallelization**:
  - **Can Run In Parallel**: NO (depende Task 2)
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 4, 5
  - **Blocked By**: Task 2

  **References**:
  - `app/features/smart_playlists/definition.py` - Modelos de dados

  **Acceptance Criteria**:
  - [ ] Módulo `expansion.py` criado com classe `GenreExpander`
  - [ ] Método `expand("electronic")` retorna lista de subgêneros
  - [ ] Método `infer_parent("Deep House")` retorna "electronic"
  - [ ] Cache funciona (múltiplas chamadas não re-leem arquivo)

  **QA Scenarios**:
  ```
  Scenario: Testar expansão e inferência
    Tool: Bash (python REPL)
    Steps:
      1. python -c "from app.features.smart_playlists.expansion import GenreExpander; e = GenreExpander(); print(e.expand('electronic'))"
      2. Verificar que retorna lista com 'house', 'techno', etc.
      3. python -c "print(e.infer_parent('Deep House'))"
      4. Verificar que retorna 'electronic'
    Expected Result: Expansão e inferência funcionam
    Evidence: .sisyphus/evidence/task-3-expansion-test.txt
  ```

  **Commit**: YES
  - Message: `feat(smart-playlists): add genre expansion module with inference`
  - Files: `app/features/smart_playlists/expansion.py`
  - Pre-commit: `python -c "from app.features.smart_playlists.expansion import GenreExpander"`

- [x] 4. Estender query_parser.py com Suporte a :expand

  **What to do**:
  - Modificar `app/features/smart_playlists/query_parser.py`
  - Adicionar suporte a sintaxe `:expand` no campo genre
  - Modificar `_parse_term` para detectar `:expand` como terceiro componente
  - Quando detectado, usar GenreExpander para expandir em múltiplas regras OR
  - Ex: `genre:electronic:expand` → cria múltiplas regras no any_rules

  **Modificações necessárias**:
  ```python
  # Em _parse_term, após split por ':'
  if len(parts) == 3 and parts[2] == 'expand':
      field = parts[0]  # "genre"
      parent = parts[1]  # "electronic"
      expander = GenreExpander()
      subgenres = expander.expand(parent)
      # Retornar lista de Rules em vez de uma única Rule
      return [Rule("is", field, sub) for sub in subgenres]
  ```

  **Must NOT do**:
  - Não modificar comportamento existente (apenas adicionar)
  - Não quebrar queries existentes sem `:expand`

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` - Modificação em código existente
  - **Skills**: N/A

  **Parallelization**:
  - **Can Run In Parallel**: NO (depende Tasks 1, 2, 3)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 7, 8
  - **Blocked By**: Tasks 1, 2, 3

  **References**:
  - `app/features/smart_playlists/query_parser.py:45-64` - _parse_term atual
  - `app/features/smart_playlists/expansion.py` - GenreExpander (Task 3)

  **Acceptance Criteria**:
  - [ ] Parser aceita `genre:electronic:expand`
  - [ ] Query sem `:expand` continua funcionando (retrocompatibilidade)
  - [ ] Expansão cria regras no any_rules (OR)
  - [ ] Parser retorna SmartPlaylistDefinition válida

  **QA Scenarios**:
  ```
  Scenario: Testar parser com :expand
    Tool: Bash (python)
    Steps:
      1. python -c "from app.features.smart_playlists.query_parser import QueryStringParser; p = QueryStringParser(); d = p.parse('genre:electronic:expand'); print(len(d.any_rules))"
      2. Verificar que any_rules tem múltiplas entradas (>10)
      3. Testar query sem expand: p.parse('genre:house') → any_rules vazio, all_rules com 1
    Expected Result: Expansão funciona, retrocompatibilidade mantida
    Evidence: .sisyphus/evidence/task-4-parser-test.txt
  ```

  **Commit**: YES
  - Message: `feat(smart-playlists): extend query parser with :expand syntax`
  - Files: `app/features/smart_playlists/query_parser.py`
  - Pre-commit: `python -m unittest tests.test_smart_playlists.test_query_parser -v`

- [x] 5. Estender builder.py com Método .with_subgenres()

  **What to do**:
  - Modificar `app/features/smart_playlists/builder.py`
  - Adicionar método `.with_subgenres(field, parent_genre)` na classe FieldCondition
  - Método deve usar GenreExpander para obter subgêneros
  - Adicionar regras ao any_rules (OR logic)
  - Permitir composição: `builder.all_of(field("genre").with_subgenres("electronic"))`

  **Implementação sugerida**:
  ```python
  class FieldCondition:
      # ... métodos existentes ...
      
      def with_subgenres(self, parent_genre: str) -> List[Rule]:
          """Expande parent_genre em múltiplas regras OR."""
          from .expansion import GenreExpander
          expander = GenreExpander()
          subgenres = expander.expand(parent_genre)
          return [self.is_(sub) for sub in subgenres]
  ```

  **Must NOT do**:
  - Não modificar métodos existentes (apenas adicionar)
  - Não quebrar API fluente atual

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` - Extensão de API existente
  - **Skills**: N/A

  **Parallelization**:
  - **Can Run In Parallel**: NO (depende Tasks 1, 2, 3)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 7, 8
  - **Blocked By**: Tasks 1, 2, 3

  **References**:
  - `app/features/smart_playlists/builder.py:8-77` - FieldCondition atual
  - `app/features/smart_playlists/expansion.py` - GenreExpander

  **Acceptance Criteria**:
  - [ ] Método `.with_subgenres()` existe e funciona
  - [ ] Retorna lista de Rules para uso com `any_of()`
  - [ ] API fluente continua funcionando normalmente
  - [ ] Exemplo funciona: `builder.any_of(*field("genre").with_subgenres("electronic"))`

  **QA Scenarios**:
  ```
  Scenario: Testar builder com with_subgenres
    Tool: Bash (python)
    Steps:
      1. python -c "from app.features.smart_playlists.builder import SmartPlaylistBuilder, field; b = SmartPlaylistBuilder('Test'); rules = field('genre').with_subgenres('electronic'); b.any_of(*rules); d = b.build(); print(len(d.any_rules))"
      2. Verificar que any_rules tem múltiplas regras
      3. Verificar que cada regra tem operator='is', field='genre'
    Expected Result: Builder cria múltiplas regras OR corretamente
    Evidence: .sisyphus/evidence/task-5-builder-test.txt
  ```

  **Commit**: YES
  - Message: `feat(smart-playlists): extend builder with with_subgenres method`
  - Files: `app/features/smart_playlists/builder.py`
  - Pre-commit: `python -c "from app.features.smart_playlists.builder import field; f = field('genre'); f.with_subgenres('electronic')"`

- [x] 6. Adicionar Validação de Schema e Error Handling

  **What to do**:
  - Criar schema validation para `genre_hierarchy.json`
  - Adicionar tratamento de erros no expansion.py:
    - Arquivo não existe → cria default
    - JSON inválido → log error, usa default
    - Gênero não encontrado → retorna lista vazia + log warning
  - Adicionar tests para edge cases

  **Must NOT do**:
  - Não deixar app crashar se hierarchy.json estiver corrompido
  - Não silenciar erros (sempre logar)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` - Error handling robusto
  - **Skills**: N/A

  **Parallelization**:
  - **Can Run In Parallel**: NO (depende Tasks 2, 3)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 9
  - **Blocked By**: Tasks 2, 3

  **Acceptance Criteria**:
  - [ ] Schema validation implementado
  - [ ] Arquivo inexistente cria default automaticamente
  - [ ] JSON inválido não quebra app (usa default + log)
  - [ ] Gênero não encontrado retorna vazio + warning (não crasha)

  **QA Scenarios**:
  ```
  Scenario: Testar error handling
    Tool: Bash
    Steps:
      1. Mover hierarchy.json para hierarchy.json.bak
      2. python -c "from app.features.smart_playlists.expansion import GenreExpander; e = GenreExpander()" → deve criar novo arquivo
      3. Restaurar backup
    Expected Result: App tolera arquivo ausente/corrompido
    Evidence: .sisyphus/evidence/task-6-error-handling.txt
  ```

  **Commit**: YES
  - Message: `feat(smart-playlists): add schema validation and error handling`
  - Files: `app/features/smart_playlists/expansion.py`
  - Pre-commit: `python -c "from app.features.smart_playlists.expansion import GenreExpander; e = GenreExpander()"`

- [x] 7. Criar Comando CLI analyze-genres

  **What to do**:
  - Adicionar comando em `app/main.py`
  - Comando: `./run.sh analyze-genres`
  - Flags: `--suggest`, `--library-path`, `--output-format`
  - Funcionalidade:
    - Lê banco de dados da biblioteca
    - Extrai todos gêneros únicos
    - Agrupa por padrão de nome (inference)
    - Sugere grupos com 3+ subgêneros
    - Output em formato legível (stdout)

  **Implementação**:
  ```python
  @cli.command()
  @click.option('--suggest', is_flag=True, help='Sugerir grupos baseado na biblioteca')
  @click.option('--library-path', type=click.Path(), help='Caminho da biblioteca')
def analyze_genres(suggest, library_path):
      """Analisa gêneros da biblioteca e sugere agrupamentos."""
      if suggest:
          genres = extract_genres_from_library(library_path)
          suggestions = analyze_groupings(genres)
          print_groupings(suggestions)
  ```

  **Must NOT do**:
  - Não modificar nenhum arquivo (read-only)
  - Não criar/alterar banco de dados
  - Não modificar hierarchy.json automaticamente

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` - CLI command com integração
  - **Skills**: N/A

  **Parallelization**:
  - **Can Run In Parallel**: NO (depende Tasks 4, 5)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 9
  - **Blocked By**: Tasks 4, 5

  **References**:
  - `app/main.py` - CLI entry point existente
  - `app/features/smart_playlists/expansion.py` - GenreExpander

  **Acceptance Criteria**:
  - [ ] Comando `./run.sh analyze-genres --help` funciona
  - [ ] Comando `./run.sh analyze-genres --suggest` mostra sugestões
  - [ ] Output é legível e agrupado
  - [ ] Não modifica nenhum arquivo

  **QA Scenarios**:
  ```
  Scenario: Testar comando CLI
    Tool: Bash
    Steps:
      1. ./run.sh analyze-genres --help
      2. Verificar que mostra usage e opções
      3. ./run.sh analyze-genres --suggest (com biblioteca pequena de teste)
      4. Verificar que sugere grupos baseado nos gêneros encontrados
    Expected Result: CLI funciona e é read-only
    Evidence: .sisyphus/evidence/task-7-cli-test.txt
  ```

  **Commit**: YES
  - Message: `feat(cli): add analyze-genres command`
  - Files: `app/main.py`
  - Pre-commit: `./run.sh analyze-genres --help`

- [x] 8. Escrever Testes Unitários

  **What to do**:
  - Criar `tests/test_smart_playlists/test_expansion.py`
  - Testar GenreExpander:
    - `test_expand_returns_subgenres()`
    - `test_infer_parent_finds_match()`
    - `test_expand_unknown_returns_empty()`
    - `test_case_insensitive_matching()`
  - Criar `tests/test_smart_playlists/test_query_parser_expand.py`
  - Testar parser com :expand:
    - `test_parse_expand_creates_multiple_rules()`
    - `test_parse_without_expand_unchanged()`
    - `test_parse_expand_case_insensitive()`
  - Criar `tests/test_smart_playlists/test_builder_expand.py`
  - Testar builder com with_subgenres:
    - `test_with_subgenres_returns_rules()`
    - `test_with_subgenres_integration()`

  **Must NOT do**:
  - Não testar com Navidrome real (mock apenas)
  - Não testar edge cases impossíveis

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` - Testes unitários
  - **Skills**: N/A

  **Parallelization**:
  - **Can Run In Parallel**: NO (depende Tasks 4, 5)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 9
  - **Blocked By**: Tasks 4, 5

  **References**:
  - `tests/` - Estrutura existente de testes
  - `tests/run_all_tests.py` - Runner de testes

  **Acceptance Criteria**:
  - [ ] 3 arquivos de teste criados
  - [ ] Mínimo 12 test cases (4 por arquivo)
  - [ ] Todos testes passam: `python -m unittest tests.test_smart_playlists -v`
  - [ ] Cobertura de casos básicos, edge cases, e integração

  **QA Scenarios**:
  ```
  Scenario: Rodar testes unitários
    Tool: Bash
    Steps:
      1. python -m unittest tests.test_smart_playlists.test_expansion -v
      2. python -m unittest tests.test_smart_playlists.test_query_parser_expand -v
      3. python -m unittest tests.test_smart_playlists.test_builder_expand -v
      4. Verificar que todos passam (OK)
    Expected Result: 12+ testes passando
    Evidence: .sisyphus/evidence/task-8-unit-tests.txt
  ```

  **Commit**: YES
  - Message: `test(smart-playlists): add unit tests for genre expansion`
  - Files: `tests/test_smart_playlists/test_expansion.py`, `test_query_parser_expand.py`, `test_builder_expand.py`
  - Pre-commit: `python -m unittest tests.test_smart_playlists -v`

- [x] 9. Testes de Integração e Edge Cases

  **What to do**:
  - Testar fluxo completo: parser → builder → expansion
  - Testar edge cases específicos:
    - Gênero com caracteres especiais: "R&B", "Drum & Bass"
    - Case sensitivity: "ELECTRONIC", "Electronic", "electronic"
    - Gênero não existente: "unknown_genre"
    - Múltiplos :expand na mesma query
    - Combinação com outros operadores (AND)
  - Testar performance com biblioteca grande (simulada)

  **Must NOT do**:
  - Não ignorar edge cases de caracteres especiais
  - Não assumir case sensitivity

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` - Integration testing
  - **Skills**: N/A

  **Parallelization**:
  - **Can Run In Parallel**: NO (depende Tasks 7, 8)
  - **Parallel Group**: Wave 3
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 7, 8

  **Acceptance Criteria**:
  - [ ] Fluxo completo parser→builder testado
  - [ ] Edge cases de caracteres especiais testados
  - [ ] Case insensitive confirmado
  - [ ] Comportamento com gênero inexistente definido

  **QA Scenarios**:
  ```
  Scenario: Testar fluxo completo
    Tool: Bash (python)
    Steps:
      1. python -c "from app.features.smart_playlists.query_parser import QueryStringParser; p = QueryStringParser(); d = p.parse('genre:electronic:expand'); print(f'Any rules: {len(d.any_rules)}')"
      2. python -c "from app.features.smart_playlists.builder import SmartPlaylistBuilder, field; b = SmartPlaylistBuilder('Test'); b.all_of(*field('genre').with_subgenres('rock')); print(f'Rules: {len(b.build().all_rules)}')"
    Expected Result: Fluxo completo funciona
    Evidence: .sisyphus/evidence/task-9-integration.txt
  
  Scenario: Testar edge cases
    Tool: Bash (python)
    Steps:
      1. Testar 'genre:R&B:expand' (caracteres especiais)
      2. Testar 'genre:ELECTRONIC:expand' (uppercase)
      3. Testar 'genre:unknown:expand' (não existente)
    Expected Result: Trata todos casos gracefully
    Evidence: .sisyphus/evidence/task-9-edge-cases.txt
  ```

  **Commit**: YES
  - Message: `test(smart-playlists): add integration tests and edge case handling`
  - Files: `tests/test_smart_playlists/test_integration.py`
  - Pre-commit: `python -m unittest tests.test_smart_playlists.test_integration -v`

---

## Final Verification Wave

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists. For each "Must NOT Have": search codebase for forbidden patterns. Check evidence files exist.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | VERDICT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `python -m unittest tests/test_smart_playlists/` + check for AI slop patterns.
  Output: `Tests [N pass/N fail] | Code Quality [PASS/FAIL] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high`
  Execute:
  - `./run.sh analyze-genres --help`
  - `./run.sh analyze-genres --dry-run` (se existir)
  - Validar expansão com query de teste
  Save to `.sisyphus/evidence/final-qa/`
  Output: `CLI Commands [N/N] | Expansion [N/N] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff. Verify 1:1 compliance.
  Output: `Tasks [N/N compliant] | VERDICT`

---

## Commit Strategy

- **Task 1**: `feat(smart-playlists): add genre hierarchy validation` - data/genre_hierarchy.json, tests
- **Task 2**: `feat(smart-playlists): create expansion module with inference` - expansion.py, tests
- **Task 3**: `feat(smart-playlists): extend query parser with :expand syntax` - query_parser.py, tests
- **Task 4**: `feat(smart-playlists): extend builder with with_subgenres method` - builder.py, tests
- **Task 5**: `feat(cli): add analyze-genres command` - main.py
- **Task 6**: `test(smart-playlists): add comprehensive tests and edge cases` - tests/

---

## Success Criteria

### Verification Commands
```bash
# Testes unitários
python -m unittest tests/test_smart_playlists/ -v

# CLI help
./run.sh analyze-genres --help

# Validação de expansão (exemplo)
./run.sh create-smart-playlist --query "genre:electronic:expand" --dry-run
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass
- [ ] CLI commands funcionam
- [ ] Expansão de gênero funciona corretamente
