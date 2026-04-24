# Testes de Integração Navidrome

Esta pasta contém testes de integração que se comunicam com um servidor Navidrome real via Docker.

## Por que testes de integração?

Os testes unitários (em `tests/`) usam mocks para simular o Navidrome. Os testes de integração verificam:

- Conexão real com a API Subsonic
- Criação/leitura/escrita de arquivos `.nsp`
- Validação de regras contra o formato real do Navidrome
- Comportamento end-to-end do `PlaylistService`

## Requisitos

- Docker e Docker Compose instalados
- Python 3.12+ com ambiente virtual configurado

## Executar Testes

### Método 1: Script automático (recomendado)

```bash
./scripts/run-integration-tests.sh
```

Isso irá:
1. Subir um container Navidrome isolado na porta 4534
2. Aguardar o servidor ficar pronto
3. Executar todos os testes de integração
4. Parar e remover o container

### Método 2: Manual

Subir o servidor:
```bash
docker-compose -f docker-compose.test.yml up -d
```

Aguardar estar pronto (verificar em http://localhost:4534):
```bash
curl http://localhost:4534/app
```

Executar testes:
```bash
python -m pytest tests/integration/ -v
```

Parar o servidor:
```bash
docker-compose -f docker-compose.test.yml down -v
```

## Configuração

Variáveis de ambiente para customizar:

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `NAVIDROME_TEST_URL` | `http://localhost:4534` | URL do servidor de teste |
| `NAVIDROME_TEST_USER` | `admin` | Usuário admin |
| `NAVIDROME_TEST_PASS` | `test123` | Senha do admin |

## Estrutura dos Testes

- `test_navidrome_integration.py` — Testes principais
  - `TestNavidromeConnection` — Ping e conectividade
  - `TestSmartPlaylistIntegration` — Criação/edição de smart playlists
  - `TestSimplePlaylistIntegration` — CRUD de playlists simples
  - `TestPlaylistStoreIntegration` — Persistência local

## Dados de Teste

O servidor usa:
- Pasta `tests/integration/fixtures/music/` — música para scan (vazia inicialmente)
- Pasta `tests/integration/fixtures/data/` — dados do Navidrome
- Pasta `tests/integration/fixtures/playlists/` — playlists importadas

## Isolamento

Cada teste:
- Cria playlists com prefixo `TEST_`
- Limpa playlists após execução
- Usa diretório temporário para arquivos locais

## CI/CD

Para usar em pipelines:
```yaml
- name: Integration Tests
  run: |
    docker-compose -f docker-compose.test.yml up -d
    sleep 10
    python -m pytest tests/integration/ -v
    docker-compose -f docker-compose.test.yml down -v
```
