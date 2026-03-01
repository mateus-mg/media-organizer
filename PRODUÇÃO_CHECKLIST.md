# 📋 Checklist Completo para Testes em Produção
## Media Organizer System

> **Descrição:** Checklist abrangente para validação do sistema de organização de mídia em ambiente de produção.
> 
> **Versão:** 1.0
> 
> **Última atualização:** Fevereiro de 2026

---

## Sumário

1. [Configuração Inicial e Ambiente](#1-configuração-inicial-e-ambiente)
2. [Testes de Funcionalidades Básicas](#2-testes-de-funcionalidades-básicas)
3. [Testes de Detecção e Classificação de Mídia](#3-testes-de-detecção-e-classificação-de-mídia)
4. [Testes de Organização por Tipo de Mídia](#4-testes-de-organização-por-tipo-de-mídia)
5. [Testes de Resolução de Conflitos](#5-testes-de-resolução-de-conflitos)
6. [Testes do Banco de Dados (TinyDB)](#6-testes-do-banco-de-dados-tinydb)
7. [Testes do Modo Daemon](#7-testes-do-modo-daemon)
8. [Testes de Integração com qBittorrent](#8-testes-de-integração-com-qbittorrent)
9. [Testes de Integração com TMDB API](#9-testes-de-integração-com-tmdb-api)
10. [Testes de Download de Legendas (OpenSubtitles)](#10-testes-de-download-de-legendas-opensubtitles)
11. [Testes de Concorrência e Performance](#11-testes-de-concorrência-e-performance)
12. [Testes de Metadados e Enriquecimento](#12-testes-de-metadados-e-enriquecimento)
13. [Testes de Conversão e Integração Calibre](#13-testes-de-conversão-e-integração-calibre)
14. [Testes de Dry-Run Mode](#14-testes-de-dry-run-mode)
15. [Testes de Health Check](#15-testes-de-health-check)
16. [Testes de Logging](#16-testes-de-logging)
17. [Testes de Estrutura de Arquivos](#17-testes-de-estrutura-de-arquivos)
18. [Testes de Workflow Completo](#18-testes-de-workflow-completo)
19. [Testes de Tratamento de Erros](#19-testes-de-tratamento-de-erros)
20. [Testes de Segurança](#20-testes-de-segurança)
21. [Testes de Migração e Upgrade](#21-testes-de-migração-e-upgrade)
22. [Testes de Monitoramento e Alertas](#22-testes-de-monitoramento-e-alertas)
23. [Checklist de Aprovação para Produção](#-checklist-de-aprovação-para-produção)
24. [Matriz de Prioridade de Testes](#-matriz-de-prioridade-de-testes)

---

## 1️⃣ Configuração Inicial e Ambiente

### 1.1 Verificação de Pré-requisitos

- [ ] Python 3.8+ instalado e acessível
- [ ] Virtual environment criado e ativado (`venv/`)
- [ ] Dependências instaladas (`pip install -r requirements.txt`)
- [ ] Arquivo `.env` configurado a partir de `.env.example`
- [ ] Diretórios de log e dados existem (`logs/`, `data/`, `data/backups/`)

### 1.2 Validação do Arquivo `.env`

- [ ] `LIBRARY_PATH_*` - Todos os caminhos das bibliotecas configurados e existentes
- [ ] `DOWNLOAD_PATH_*` - Todos os caminhos de download configurados e existentes
- [ ] `TMDB_API_KEY` - Chave de API configurada (se usar detecção automática)
- [ ] `QBITTORRENT_*` - Credenciais configuradas (se usar integração qBittorrent)
- [ ] `OPENSUBTITLES_*` - Credenciais configuradas (se usar download de legendas)
- [ ] `DATABASE_PATH` - Caminho do banco de dados configurado
- [ ] `LOG_LEVEL` - Nível de log apropriado para produção (INFO ou WARNING)

### 1.3 Validação de Permissões

- [ ] Usuário tem permissão de leitura nos diretórios de download
- [ ] Usuário tem permissão de escrita nos diretórios da biblioteca
- [ ] Usuário tem permissão de escrita em `logs/` e `data/`
- [ ] Permissão para criar hardlinks entre filesystems (se aplicável)

---

## 2️⃣ Testes de Funcionalidades Básicas

### 2.1 Comando `organize` (Modo Interativo)

- [ ] Menu interativo exibe todas as opções corretamente
- [ ] Opção "0" (Todos os diretórios) processa todos os paths configurados
- [ ] Opções 1-7 processam diretórios específicos individualmente
- [ ] Diretório inexistente é tratado com mensagem de erro apropriada
- [ ] Estatísticas são exibidas após organização
- [ ] Arquivos já organizados são detectados e pulados (via database)

### 2.2 Comando `stats` (Estatísticas)

- [ ] Exibe total de arquivos organizados
- [ ] Exibe contagem por tipo de mídia (movies, series, animes, doramas, music, books, comics)
- [ ] Exibe operações falhas
- [ ] Dados batem com conteúdo real da biblioteca

### 2.3 Comando `unorganized` (Arquivos Não Organizáveis)

- [ ] Lista arquivos que falharam na organização
- [ ] Exibe razão da falha para cada arquivo
- [ ] Arquivo `data/unorganized.json` é criado/atualizado corretamente

### 2.4 Comando `test` (Teste de Configuração)

- [ ] Valida configuração do ambiente Python
- [ ] Valida caminhos configurados no `.env`
- [ ] Valida acesso ao banco de dados
- [ ] Exibe mensagem de sucesso/erro apropriada

---

## 3️⃣ Testes de Detecção e Classificação de Mídia

### 3.1 Detecção por Extensão

- [ ] Vídeos: `.mkv`, `.mp4`, `.avi`, `.mov`, `.wmv`, `.flv`, `.webm`, `.m4v`
- [ ] Áudio: `.mp3`, `.flac`, `.m4a`, `.ogg`, `.opus`, `.aac`, `.wav`
- [ ] Livros: `.epub`, `.pdf`, `.mobi`, `.azw`, `.azw3`
- [ ] Comics: `.cbz`, `.cbr`, `.cb7`, `.cbt`

### 3.2 Classificação de Vídeo por Contexto

- [ ] Arquivos com padrão `SXXEXX` em pasta `animes/` → classificado como ANIME
- [ ] Arquivos com padrão `SXXEXX` em pasta `doramas/` → classificado como DORAMA
- [ ] Arquivos com padrão `SXXEXX` em pasta `tv/` → classificado como TV_SHOW
- [ ] Arquivos sem padrão de episódio → classificado como MOVIE
- [ ] Padrões detectados: `S01E01`, `1x01`, `Season 1`, `Episode 1`, `Ep 01`

### 3.3 Validação de Arquivos

- [ ] Arquivos inexistentes são rejeitados
- [ ] Arquivos com extensão incompleta (`.part`, `.tmp`, `.!qB`, `.crdownload`, `.download`) são rejeitados
- [ ] Arquivos com tamanho zero são rejeitados
- [ ] Arquivos junk (`SAMPLE`, `TRAILER`, `BLUDV`, `1XBET`) são rejeitados
- [ ] Arquivos promocionais (< 100MB com padrões no nome) são rejeitados

---

## 4️⃣ Testes de Organização por Tipo de Mídia

### 4.1 Filmes (MovieOrganizer)

- [ ] Extrai título e ano do nome do arquivo
- [ ] Busca TMDB ID automaticamente via API
- [ ] Cria estrutura: `movies/Título (Ano) [tmdbid-ID]/`
- [ ] Nomeia arquivo como: `Título (Ano).ext`
- [ ] Arquivo sem TMDB ID é adicionado a `unorganized.json`
- [ ] Legendas são movidas junto com o vídeo

### 4.2 Séries de TV (TVOrganizer - TV)

- [ ] Extrai título, temporada, episódio do nome do arquivo
- [ ] Extrai ano do diretório pai
- [ ] Busca TMDB ID automaticamente via API
- [ ] Cria estrutura: `tv/Série (Ano) [tmdbid-ID]/Season XX/`
- [ ] Nomeia arquivo como: `Série SXXEXX.ext`
- [ ] Remove de `unorganized.json` após organização bem-sucedida

### 4.3 Animes (TVOrganizer - Anime)

- [ ] Mesma lógica de séries de TV
- [ ] Usa caminho: `LIBRARY_PATH_ANIMES`
- [ ] Classifica baseado em contexto da pasta ou padrão de episódio

### 4.4 Doramas (TVOrganizer - Dorama)

- [ ] Mesma lógica de séries de TV
- [ ] Usa caminho: `LIBRARY_PATH_DORAMAS`
- [ ] Classifica baseado em contexto da pasta ou padrão de episódio

### 4.5 Músicas (MusicOrganizer)

- [ ] Extrai metadados ID3 do arquivo de áudio
- [ ] Integra com banco de dados `music-automation` (se configurado)
- [ ] Prioridade de metadados: Automation > ID3 > Filename
- [ ] Cria estrutura: `music/Artista/Álbum/`
- [ ] Nomeia arquivo como: `## - Faixa.ext`
- [ ] Atualiza tags ID3 com metadados enriquecidos

### 4.6 Livros (BookOrganizer - Book)

- [ ] Extrai título e autor do nome do arquivo
- [ ] Suporta enriquecimento de metadados via Calibre (se habilitado)
- [ ] Suporta busca online (OpenLibrary/Google Books) se habilitado
- [ ] Cria estrutura: `books/Autor/Título (Ano)/`
- [ ] Respeita prioridade de formatos: EPUB > MOBI > AZW3 > AZW > PDF

### 4.7 Comics (BookOrganizer - Comic)

- [ ] Detecta tipo por extensão (`.cbz`, `.cbr`, `.cb7`, `.cbt`)
- [ ] Extrai série, número, editora do nome do arquivo
- [ ] Cria estrutura: `comics/Série (Ano)/`
- [ ] Suporta busca de metadados online (ComicVine) se habilitado

---

## 5️⃣ Testes de Resolução de Conflitos

### 5.1 Estratégia `skip` (Padrão)

- [ ] Arquivo de destino existente é mantido
- [ ] Novo arquivo é pulado se já existir
- [ ] Database é atualizada corretamente

### 5.2 Estratégia `rename`

- [ ] Arquivo novo é renomeado com contador: `{name}_2{ext}`
- [ ] Testa até `CONFLICT_MAX_ATTEMPTS` tentativas
- [ ] Não sobrescreve arquivos existentes

### 5.3 Estratégia `overwrite`

- [ ] Arquivo de destino é removido
- [ ] Novo arquivo ocupa o lugar
- [ ] Database é atualizada com novo registro

### 5.4 Detecção de Arquivos Idênticos

- [ ] Compara por inode (mesmo filesystem)
- [ ] Compara por tamanho do arquivo
- [ ] Compara hash MD5 para arquivos < 100MB
- [ ] Arquivos idênticos são pulados automaticamente

---

## 6️⃣ Testes do Banco de Dados (TinyDB)

### 6.1 Operações de Leitura/Escrita

- [ ] `adicionar_midia()` registra novo arquivo organizado
- [ ] `is_file_organized()` detecta arquivos já processados
- [ ] `get_stats()` retorna estatísticas corretas
- [ ] Campos obrigatórios: `file_hash`, `original_path`, `organized_path`, `metadata`

### 6.2 Backups Automáticos

- [ ] Backup é criado a cada 7 dias (configurável)
- [ ] Backups são salvos em `data/backups/`
- [ ] Backups antigos (> 7 dias) são removidos
- [ ] Função `create_backup()` funciona manualmente

### 6.3 Tabela de Falhas

- [ ] `add_failure()` registra operações falhas
- [ ] `get_failures()` retorna falhas recentes
- [ ] Estatística `failed_operations` é incrementada

### 6.4 Gerenciamento de Legendas (Subtitle Tracking)

- [ ] `add_subtitle()` registra legenda baixada
- [ ] `has_subtitle()` verifica existência por idioma
- [ ] `get_files_without_subtitles()` lista arquivos sem legenda
- [ ] `get_subtitle_statistics()` retorna cobertura de legendas
- [ ] `save_subtitle_rate_limit()` salva estado do rate limit
- [ ] `load_subtitle_rate_limit()` carrega estado do rate limit

---

## 7️⃣ Testes do Modo Daemon

### 7.1 Inicialização do Daemon

- [ ] `media-organizer start` inicia processo em background
- [ ] PID é salvo em `.daemon.pid`
- [ ] Log é redirecionado para `logs/daemon.log`
- [ ] Verifica se já está rodando antes de iniciar

### 7.2 Ciclo de Processamento

- [ ] Processa todos os diretórios de download configurados
- [ ] Respeita intervalo `CHECK_INTERVAL` (padrão: 3600s)
- [ ] Exibe contagem de arquivos processados por ciclo
- [ ] Calcula e exibe duração do ciclo
- [ ] Trata erros sem interromper o daemon

### 7.3 Monitoramento e Controle

- [ ] `media-organizer status` exibe status correto
- [ ] Exibe PID, uptime, CPU, memória
- [ ] Mostra últimas entradas do log
- [ ] Detecta PID file obsoleto e limpa

### 7.4 Parada do Daemon

- [ ] `media-organizer stop` para processo graciosamente
- [ ] Aguarda até 10 segundos para parada suave
- [ ] Usa `kill -9` se necessário após timeout
- [ ] Remove arquivo `.daemon.pid`

### 7.5 Gerenciamento de Logs

- [ ] `media-organizer logs tail` segue logs em tempo real
- [ ] `media-organizer logs error` filtra apenas erros
- [ ] `media-organizer logs clear` limpa arquivo de log
- [ ] Log rotation: 50MB max, 5 backups

---

## 8️⃣ Testes de Integração com qBittorrent

### 8.1 Conexão e Autenticação

- [ ] Conecta ao qBittorrent via API (`/api/v2/auth/login`)
- [ ] Autentica com credenciais do `.env`
- [ ] Obtém cookie de sessão (SID)
- [ ] Trata falhas de conexão graciosamente

### 8.2 Validação de Torrents Completos

- [ ] Lista todos os torrents via `/api/v2/torrents/info`
- [ ] Filtra apenas torrents em estado `seeding`, `pausedUP`, `uploading`
- [ ] Verifica progresso >= 100%
- [ ] Obtém lista de arquivos por torrent

### 8.3 Validação de Arquivos

- [ ] Só processa arquivos de torrents completos
- [ ] Pula arquivos de torrents em download
- [ ] Respeita categorias ignoradas (`QBITTORRENT_IGNORED_CATEGORIES`)
- [ ] Suporta mapeamento de caminhos (container ↔ host)

### 8.4 Configurações

- [ ] `QBITTORRENT_ENABLED=true/false` habilita/desabilita integração
- [ ] `QBITTORRENT_STATES_TO_PROCESS` configura estados válidos
- [ ] `QBITTORRENT_MIN_PROGRESS` define progresso mínimo (padrão: 1.0)

---

## 9️⃣ Testes de Integração com TMDB API

### 9.1 Busca de Filmes

- [ ] `get_tmdb_id_for_movie()` busca ID por título e ano
- [ ] Limpa título (remove resoluções, codecs, etc.)
- [ ] Prioriza resultados por popularidade
- [ ] Match por ano com tolerância de ±1 ano
- [ ] Retorna `None` se API key não configurada

### 9.2 Busca de Séries de TV

- [ ] `get_tmdb_id_for_tv_show()` busca ID por título e ano
- [ ] Usa endpoint `/search/tv` com `first_air_date_year`
- [ ] Mesma lógica de limpeza e priorização de filmes

### 9.3 Rate Limiting

- [ ] Respeita limite de requisições da API (4/segundo)
- [ ] `TMDB_RATE_LIMIT_PER_SECOND` configurável
- [ ] Timeout de 30 segundos por requisição

### 9.4 Fallback Parsing

- [ ] `TMDB_USE_FALLBACK_PARSING=true` extrai ID do nome do arquivo
- [ ] Padrão: `[tmdbid-12345]` no nome da pasta/arquivo

---

## 🔟 Testes de Download de Legendas (OpenSubtitles)

### 10.1 Configuração e Autenticação

- [ ] `OPENSUBTITLES_API_KEY` configurada
- [ ] `OPENSUBTITLES_USERNAME` e `PASSWORD` configurados
- [ ] Autenticação via API funciona
- [ ] Trata credenciais inválidas

### 10.2 Download de Legendas

- [ ] Busca legendas por hash do arquivo de vídeo
- [ ] Respeita ordem de idiomas: `pt`, `en`, `es`
- [ ] Baixa apenas se legenda não existir
- [ ] Move legenda para diretório do vídeo organizado
- [ ] Nomeia legenda como: `Vídeo.pt.srt`

### 10.3 Rate Limiting

- [ ] Limite de 20 downloads/dia (conta free)
- [ ] `save_subtitle_rate_limit()` rastreia downloads
- [ ] Para ao atingir limite
- [ ] Reseta contagem à meia-noite (configurável)

### 10.4 Daemon de Legendas

- [ ] `subtitle-daemon start` inicia daemon
- [ ] Roda a cada `SUBTITLE_DOWNLOAD_INTERVAL` (padrão: 86400s)
- [ ] Prioridade: Movies → Series → Doramas → Animes
- [ ] `subtitle-daemon run` executa download manual
- [ ] `subtitle-daemon status` exibe estatísticas

### 10.5 Estatísticas de Legendas

- [ ] Total de arquivos com/sem legenda
- [ ] Porcentagem de cobertura
- [ ] Contagem por idioma
- [ ] `subtitle status --missing` lista arquivos sem legenda

---

## 1️⃣1️⃣ Testes de Concorrência e Performance

### 11.1 ConcurrencyManager

- [ ] `MAX_CONCURRENT_FILE_OPS` respeitado (padrão: 3)
- [ ] `MAX_CONCURRENT_API_CALLS` respeitado (padrão: 2)
- [ ] Semaphores controlam execução paralela
- [ ] File locks previnem race conditions

### 11.2 FileOperations

- [ ] `safe_hardlink()` cria hardlinks atomicamente
- [ ] `safe_move()` move arquivos com lock
- [ ] `safe_copy()` copia arquivos com lock
- [ ] `FILE_OP_DELAY_MS` entre operações (padrão: 100ms)

### 11.3 Validação de Completude de Arquivo

- [ ] Verifica extensão temporária
- [ ] Verifica lock de processo (fcntl)
- [ ] Verifica estabilidade de tamanho (5 segundos)
- [ ] Verifica idade mínima do arquivo (300 segundos)

---

## 1️⃣2️⃣ Testes de Metadados e Enriquecimento

### 12.1 Metadados de Áudio (Mutagen)

- [ ] Lê tags ID3 de arquivos MP3
- [ ] Lê tags de arquivos FLAC
- [ ] Extrai: título, artista, álbum, gênero, faixa, ano
- [ ] Atualiza tags com metadados enriquecidos

### 12.2 Enriquecimento Online de Livros

- [ ] `ENRICH_BOOK_METADATA_ONLINE=true` habilita busca
- [ ] Busca no OpenLibrary por título/autor
- [ ] Busca no Google Books API
- [ ] Extrai: ISBN, editora, ano, gêneros, sujeitos

### 12.3 Enriquecimento Online de Músicas

- [ ] `ENRICH_MUSIC_METADATA_ONLINE=true` habilita busca
- [ ] Busca no MusicBrainz
- [ ] Extrai: ISRC, disambiguation

### 12.4 Filtro de Gêneros Inválidos

- [ ] Filtra gêneros como "People & Blogs" (YouTube)
- [ ] Infere gêneros apropriados do título
- [ ] Mantém compatibilidade com servidores de mídia

---

## 1️⃣3️⃣ Testes de Conversão e Integração Calibre

### 13.1 Conversão PDF → EPUB

- [ ] `CALIBRE_ENABLED=true` habilita integração
- [ ] `CONVERT_PDF_TO_EPUB=true` habilita conversão
- [ ] `ebook-convert` disponível no PATH
- [ ] Preserva metadados na conversão
- [ ] Suporta OCR para PDFs escaneados

### 13.2 Enriquecimento via Calibre

- [ ] Atualiza metadados embutidos em EPUB/PDF/MOBI
- [ ] Adiciona: série, gêneros, ratings, ISBN
- [ ] Melhora compatibilidade com servidores (Kavita)

---

## 1️⃣4️⃣ Testes de Dry-Run Mode

### 14.1 Ativação e Comportamento

- [ ] `DRY_RUN_MODE=true` habilita modo de simulação
- [ ] `DRY_RUN_LOG_LEVEL=INFO` aumenta verbosidade
- [ ] Nenhum arquivo é modificado
- [ ] Hardlinks não são criados
- [ ] Database não é atualizado
- [ ] Logs indicam operações simuladas

---

## 1️⃣5️⃣ Testes de Health Check

### 15.1 Servidor de Health Check

- [ ] `HEALTH_CHECK_ENABLED=true` habilita servidor
- [ ] Escuta em `HEALTH_CHECK_HOST:HEALTH_CHECK_PORT`
- [ ] Retorna status do sistema
- [ ] Integrável com monitoramento externo

---

## 1️⃣6️⃣ Testes de Logging

### 16.1 Configuração de Logs

- [ ] `LOG_LEVEL` respeitado (DEBUG, INFO, WARNING, ERROR)
- [ ] `LOG_FILE` configurado corretamente
- [ ] `LOG_MAX_SIZE_MB` (50MB) trigger para rotation
- [ ] `LOG_BACKUP_COUNT` (5) backups mantidos

### 16.2 Formatos de Log

- [ ] Logs de organização com detalhes completos
- [ ] Logs de erro com stack traces
- [ ] Logs de database com operações
- [ ] Logs de integração (TMDB, qBittorrent, OpenSubtitles)

### 16.3 Logs por Tipo de Mídia

- [ ] `log_movie()`, `log_tv()`, `log_anime()`, `log_dorama()`
- [ ] `log_music()`, `log_book()`, `log_comic()`
- [ ] `log_subtitle()`, `log_database()`, `log_conflict()`

---

## 1️⃣7️⃣ Testes de Estrutura de Arquivos

### 17.1 Estrutura de Diretórios

```
media-organizer/
├── data/
│   ├── organization.json      # Database principal
│   ├── unorganized.json       # Arquivos falhos
│   └── backups/               # Backups automáticos
├── logs/
│   ├── organizer.log          # Log principal
│   ├── daemon.log             # Log do daemon
│   └── subtitle_downloader.log # Log de legendas
├── .daemon.pid                # PID do daemon
└── .subtitle_daemon.pid       # PID do daemon de legendas
```

### 17.2 Validação de Estrutura

- [ ] `data/organization.json` é válido JSON
- [ ] `data/unorganized.json` é válido JSON
- [ ] Backups são nomeados: `organization_YYYY-MM-DD_HH-MM-SS.json`
- [ ] Logs são rotacionados corretamente

---

## 1️⃣8️⃣ Testes de Workflow Completo

### 18.1 Fluxo de Organização de Filme

1. [ ] Arquivo detectado em `DOWNLOAD_PATH_MOVIES`
2. [ ] Validação: existe, tipo suportado, completo, não-junk
3. [ ] Classificação: MOVIE
4. [ ] Extração: título, ano do filename
5. [ ] TMDB: busca ID via API
6. [ ] Destino: `movies/Título (Ano) [tmdbid-ID]/`
7. [ ] Hardlink: criado atomicamente
8. [ ] Legendas: movidas junto
9. [ ] Database: registro adicionado
10. [ ] Stats: incrementadas

### 18.2 Fluxo de Organização de Série

1. [ ] Arquivo detectado em `DOWNLOAD_PATH_TV`
2. [ ] Validação completa
3. [ ] Classificação: TV_SHOW (ou ANIME/DORAMA)
4. [ ] Extração: título, temporada, episódio
5. [ ] TMDB: busca ID da série
6. [ ] Destino: `tv/Série (Ano) [tmdbid-ID]/Season XX/`
7. [ ] Hardlink criado
8. [ ] Database atualizado
9. [ ] Remove de `unorganized.json` se existir

### 18.3 Fluxo de Download de Legendas

1. [ ] Daemon inicia a cada 24h
2. [ ] Varre database por vídeos sem legenda
3. [ ] Prioriza por tipo de mídia
4. [ ] Busca no OpenSubtitles por hash
5. [ ] Baixa legenda em idioma prioritário
6. [ ] Move para diretório do vídeo
7. [ ] Atualiza database com registro da legenda
8. [ ] Rastreia rate limit (20/dia)

---

## 1️⃣9️⃣ Testes de Tratamento de Erros

### 19.1 Erros de Configuração

- [ ] `.env` ausente → erro claro com instrução
- [ ] Caminhos inválidos → lista erros específicos
- [ ] API keys faltando → feature desabilitada graciosamente

### 19.2 Erros de Rede

- [ ] TMDB API indisponível → arquivo vai para `unorganized.json`
- [ ] qBittorrent offline → processa sem validação
- [ ] OpenSubtitles offline → log de erro, continua próximo

### 19.3 Erros de Filesystem

- [ ] Sem permissão de escrita → log de erro, pula arquivo
- [ ] Disco cheio → log de erro crítico, para organização
- [ ] Hardlink falha (filesystems diferentes) → tenta copy

### 19.4 Erros de Database

- [ ] JSON corrompido → tenta recuperar, cria backup
- [ ] TinyDB lock → espera e retry
- [ ] Backup falha → log de warning, continua

---

## 2️⃣0️⃣ Testes de Segurança

### 20.1 Validação de Entrada

- [ ] Nomes de arquivo sanitizados (remove `< > : " / \ | ? *`)
- [ ] Títulos truncados (max 100 chars)
- [ ] Autores truncados (max 50 chars)

### 20.2 Proteção de Dados Sensíveis

- [ ] API keys não são logadas
- [ ] Senhas não são expostas em logs
- [ ] Credenciais qBittorrent mascaradas

### 20.3 Controle de Acesso

- [ ] Daemon só pode ser controlado pelo usuário dono
- [ ] PID files protegidos contra escrita indevida
- [ ] Logs não são world-readable

---

## 2️⃣1️⃣ Testes de Migração e Upgrade

### 21.1 Compatibilidade com Versões Anteriores

- [ ] `manual_mapping.json` antigo é migrado (se existir)
- [ ] Database antigo é compatível
- [ ] Estrutura de pastas antiga é reconhecida

### 21.2 Backup Pré-Upgrade

- [ ] Backup manual antes de upgrade
- [ ] Rollback testado
- [ ] Documentação de migração lida

---

## 2️⃣2️⃣ Testes de Monitoramento e Alertas

### 22.1 Métricas para Monitoramento

- [ ] Número de arquivos organizados por hora/dia
- [ ] Taxa de sucesso vs falha
- [ ] Tempo médio de processamento por arquivo
- [ ] Uso de CPU/memória do daemon
- [ ] Espaço em disco disponível

### 22.2 Alertas Configuráveis

- [ ] Falha consecutiva > N vezes
- [ ] Disco < X% livre
- [ ] Daemon parado > Y minutos
- [ ] Rate limit de API atingido

---

## ✅ Checklist de Aprovação para Produção

Antes de considerar o sistema pronto para produção, valide:

- [ ] **Todos os testes acima passaram**
- [ ] **Performance aceitável** (processa X arquivos/hora)
- [ ] **Recuperação de falhas testada** (reinício após crash)
- [ ] **Backup e restore testados**
- [ ] **Documentação atualizada**
- [ ] **Equipe treinada nos procedimentos**
- [ ] **Monitoramento configurado**
- [ ] **Plano de rollback definido**

---

## 📊 Matriz de Prioridade de Testes

| Prioridade | Área | Criticidade |
|------------|------|-------------|
| 🔴 Alta | Organização de Filmes/Séries | Crítico |
| 🔴 Alta | Validação de Arquivos | Crítico |
| 🔴 Alta | Database e Backups | Crítico |
| 🟠 Média | TMDB Integration | Importante |
| 🟠 Média | qBittorrent Integration | Importante |
| 🟠 Média | Modo Daemon | Importante |
| 🟡 Baixa | Download de Legendas | Nice-to-have |
| 🟡 Baixa | Enriquecimento Online | Nice-to-have |
| 🟡 Baixa | Conversão Calibre | Nice-to-have |

---

## 📝 Notas de Uso

### Como Utilizar Este Checklist

1. **Crie uma cópia** deste arquivo para seu ambiente de produção
2. **Marque os itens** conforme os testes são executados
3. **Documente falhas** com links para issues/bugs
4. **Revise periodicamente** e atualize conforme novas features

### Comandos Úteis para Testes

```bash
# Testar configuração
./run.sh test

# Organizar arquivos (interativo)
./run.sh organize

# Ver estatísticas
./run.sh stats

# Ver arquivos não organizados
./run.sh unorganized

# Iniciar daemon
./run-daemon.sh start

# Ver status do daemon
./run-daemon.sh status

# Ver logs em tempo real
./run-daemon.sh logs tail

# Testar configuração de legendas
./subtitle-daemon.sh test

# Download manual de legendas
./subtitle-daemon.sh run
```

### Scripts de Teste Automatizados

```bash
# Rodar todos os testes
python tests/run_all_tests.py

# Testes específicos
python tests/test_setup.py
python tests/test_core_functions.py
python tests/test_organizers.py
python tests/test_integration.py
python tests/test_cli_commands.py
```

---

## 2️⃣3️⃣ Testes de Trash & Deletion Manager (NOVO)

### 23.1 Link Registry

- [ ] `LinkRegistry` rastreia hardlinks por inode corretamente
- [ ] `register_link()` registra novo hardlink durante organização
- [ ] `get_all_links()` retorna todos os hardlinks de um arquivo
- [ ] `get_inode()` obtém inode de um arquivo
- [ ] `unregister_link()` remove link após exclusão
- [ ] `scan_filesystem()` varre diretórios e reconstrói registry
- [ ] `get_stats()` retorna estatísticas de inodes/links
- [ ] Database `data/link_registry.json` é criado/atualizado

### 23.2 Trash Manager

- [ ] `move_to_trash()` copia arquivo para lixeira e remove originais
- [ ] `restore_from_trash()` restaura arquivo para local original
- [ ] `empty_trash()` remove permanentemente itens da lixeira
- [ ] `list_items()` lista itens na lixeira com dias restantes
- [ ] `get_stats()` retorna estatísticas da lixeira
- [ ] `cleanup_expired()` remove itens expirados (> retention_days)
- [ ] Retention period configurável (`TRASH_RETENTION_DAYS=30`)
- [ ] Estrutura `data/trash/files/{trash_id}/` criada corretamente

### 23.3 Deletion Manager

- [ ] `delete_to_trash()` move arquivo para lixeira (reversível)
- [ ] `delete_permanent()` remove permanentemente com confirmação
- [ ] `get_deletion_preview()` mostra preview do que será deletado
- [ ] `print_preview()` exibe preview formatado no console
- [ ] Confirmação requer digitar "DELETE" para exclusão permanente
- [ ] Backup do database criado antes de exclusão permanente
- [ ] Database de organização atualizado após exclusão
- [ ] Link registry atualizado após exclusão

### 23.4 Comandos CLI - Trash

- [ ] `media-organizer trash` - Menu interativo funciona
- [ ] `media-organizer trash delete <path>` - Delete para lixeira
- [ ] `media-organizer trash delete-permanent <path>` - Delete permanente
- [ ] `media-organizer trash delete --dry-run` - Preview sem executar
- [ ] `media-organizer trash list` - Lista itens da lixeira
- [ ] `media-organizer trash restore <trash_id>` - Restaura item
- [ ] `media-organizer trash empty` - Esvazia lixeira
- [ ] `media-organizer trash empty --older-than 7` - Remove antigos
- [ ] `media-organizer trash status` - Exibe estatísticas
- [ ] `media-organizer trash lookup <path>` - Busca hardlinks
- [ ] `media-organizer trash scan` - Varre filesystem

### 23.5 Menu Interativo Unificado

- [ ] Opção 10: "Trash & Deletion" no menu principal
- [ ] Opção 11: "Subtitle Downloader" no menu principal
- [ ] Submenu trash exibe 8 opções corretamente
- [ ] Submenu subtitle exibe 8 opções corretamente
- [ ] Retorno ao menu principal funciona (opção 0)

### 23.6 Configurações (.env)

- [ ] `TRASH_ENABLED=true` habilita sistema de lixeira
- [ ] `TRASH_PATH="./data/trash"` configura caminho da lixeira
- [ ] `TRASH_RETENTION_DAYS=30` configura dias de retenção
- [ ] `LINK_REGISTRY_PATH="./data/link_registry.json"` configura registry
- [ ] `DELETE_CONFIRMATION_REQUIRED=true` requer confirmação
- [ ] `DELETE_DRY_RUN_DEFAULT=true` padrão é dry-run

### 23.7 Fluxos de Trabalho

**Fluxo: Delete para Lixeira**
1. [ ] Usuário solicita delete de arquivo
2. [ ] Sistema identifica todos os hardlinks via LinkRegistry
3. [ ] Preview exibido com todos os links afetados
4. [ ] Usuário confirma
5. [ ] Um link copiado para `data/trash/files/{id}/`
6. [ ] Todos os hardlinks originais removidos
7. [ ] Trash ID retornado para possível restore
8. [ ] Database de organização atualizado

**Fluxo: Delete Permanente**
1. [ ] Usuário solicita delete permanente
2. [ ] Preview exibido com aviso VERMELHO
3. [ ] Usuário digita "DELETE" para confirmar
4. [ ] Backup do database criado
5. [ ] Todos os hardlinks removidos
6. [ ] Espaço em disco liberado
7. [ ] Database de organização atualizado
8. [ ] Link registry limpo

**Fluxo: Restauração da Lixeira**
1. [ ] Usuário solicita restore com trash_id
2. [ ] Item buscado na lixeira
3. [ ] Arquivo copiado de volta para local original
4. [ ] Hardlinks recriados se múltiplos paths
5. [ ] Link registry atualizado
6. [ ] Database de organização restaurado

### 23.8 Segurança e Validações

- [ ] Confirmação explícita para exclusão permanente
- [ ] Dry-run obrigatório por padrão
- [ ] Backup pré-exclusão sempre criado
- [ ] Lock de concorrência durante exclusão
- [ ] Validação de inode antes de remover
- [ ] Permissões de escrita verificadas
- [ ] Mensagens de erro claras e informativas

---

## 2️⃣7️⃣ Testes de Renamer (NOVO)

### 27.1 RenamerOrganizer - Classe Nativa

- [ ] `RenamerOrganizer` herda de `BaseOrganizer` corretamente
- [ ] Implementa `OrganizadorInterface` completamente
- [ ] Registrado no `Orquestrador` com `MediaType.RENAMER`
- [ ] Usa `ConflictHandler` do sistema
- [ ] Usa `OrganizationDatabase` para tracking
- [ ] Logger centralizado via `get_logger("Renamer")`

### 27.2 Padrões de Renomeação

**Movies:**
- [ ] Padrão: `Title (Year).ext`
- [ ] Exemplo: `The Matrix (1999).mkv`
- [ ] Sanitização de título funciona
- [ ] Ano extraído do input do usuário

**TV Shows:**
- [ ] Padrão: `Series.S01E01.ext`
- [ ] Exemplo: `Breaking.Bad.S01E01.mkv`
- [ ] Detecção automática de episódio (S01E01, 1x01, Ep01, E01)
- [ ] Temporada formatada como `S01`, `S02`, etc.
- [ ] Episódio formatado como `E01`, `E02`, etc.

**Anime:**
- [ ] Mesma lógica de TV Shows
- [ ] Usa `LIBRARY_PATH_ANIMES` se organizado via organizer
- [ ] Metadata type: `anime`

**Doramas:**
- [ ] Mesma lógica de TV Shows
- [ ] Usa `LIBRARY_PATH_DORAMAS` se organizado via organizer
- [ ] Metadata type: `dorama`

**Music:**
- [ ] Padrão: `## - Track.ext`
- [ ] Exemplo: `01 - Track Name.mp3`
- [ ] Track number formatado com zero à esquerda
- [ ] Sanitização do título

**Books:**
- [ ] Padrão: `Author - Title (Year).ext`
- [ ] Exemplo: `J.R.R. Tolkien - The Hobbit (1937).epub`
- [ ] Autor sanitizado via `sanitize_author()`
- [ ] Título sanitizado via `sanitize_title()`

**Comics:**
- [ ] Padrão: `Series #Issue.ext`
- [ ] Exemplo: `Batman #001.cbz`
- [ ] Issue number formatado com 3 dígitos
- [ ] Suporta `.cbz`, `.cbr`, `.cb7`, `.cbt`

**Subtitles:**
- [ ] Padrão: `Series.S01E01.lang.ext`
- [ ] Exemplo: `Breaking.Bad.S01E01.pt.srt`
- [ ] Detecção de idioma existente (pt, en, es, fr)
- [ ] Adiciona `.pt` por padrão se não detectado
- [ ] Suporta `.srt`, `.ass`, `.vtt`, `.sub`

### 27.3 Detecção de Episódios

- [ ] Pattern `S01E01`, `s1e1`, `S01.E01`
- [ ] Pattern `1x01`, `01x02`, `1X01`
- [ ] Pattern `Ep01`, `EP01`, `ep.1`, `Episode 1`
- [ ] Pattern `E01`, `E1` (sem S)
- [ ] Retorna `None` se nenhum pattern detectado
- [ ] Arquivo sem episódio detectado é reportado

### 27.4 RenamerCLI - Interface de Linha de Comando

- [ ] Módulo `src/renamer.py` importável
- [ ] Classe `RenamerCLI` com menu interativo
- [ ] `run()` como entry point
- [ ] `_show_main_menu()` exibe opções corretamente
- [ ] `_handle_rename_choice()` processa escolha do usuário
- [ ] `_get_metadata_for_type()` coleta metadata por tipo
- [ ] `_show_results()` exibe estatísticas formatadas

### 27.5 Comandos CLI

- [ ] `./run.sh renamer` abre menu interativo
- [ ] `python -m src.renamer` funciona diretamente
- [ ] `python -m src.renamer --dry-run` preview mode
- [ ] `python -m src.renamer --help` exibe help
- [ ] Opção `--type` para modo direto (futuro)
- [ ] Opção `--path` para caminho (futuro)
- [ ] Opção `--title` para título (futuro)

### 27.6 Menu Principal Integrado

- [ ] Opção [2] "Rename media files (Renamer) 📝" no menu
- [ ] Acesso via `./run.sh organize` → Opção 2
- [ ] Acesso via `./run.sh renamer` direto
- [ ] Dry-run toggle dentro do submenu
- [ ] Retorno ao menu principal (opção 0) funciona

### 27.7 Dry-Run Mode

- [ ] `--dry-run` flag ativa modo de simulação
- [ ] Nenhum arquivo é modificado no dry-run
- [ ] Logs indicam `[DRY-RUN] Would rename: ...`
- [ ] Estatísticas são exibidas mesmo em dry-run
- [ ] Mensagem de aviso amarela no final

### 27.8 Conflict Resolution

- [ ] Integra com `ConflictHandler` do sistema
- [ ] Estratégia `skip` (padrão) mantém existente
- [ ] Estratégia `rename` adiciona contador
- [ ] Estratégia `overwrite` substitui arquivo
- [ ] Detecta arquivos idênticos por hash

### 27.9 Database Tracking

- [ ] `calculate_file_hash()` calcula MD5 do arquivo
- [ ] `adicionar_midia()` registra no `organization.json`
- [ ] `is_file_organized()` detecta renomeações prévias
- [ ] Metadata inclui: type, title, season, episode, year, etc.
- [ ] Stats incrementadas corretamente

### 27.10 Tratamento de Erros

- [ ] Pasta inexistente: erro claro
- [ ] Path não é diretório: erro claro
- [ ] Input inválido (ano, temporada): ValueError tratado
- [ ] KeyboardInterrupt: cancela graciosamente
- [ ] Exception genérica: log + mensagem de erro

### 27.10 Wrapper Shell Script

- [ ] `src/renamer.sh` existe e é executável
- [ ] Ativa virtual environment se existir
- [ ] Configura PYTHONPATH corretamente
- [ ] Executa `python -m src.renamer "$@"`
- [ ] Repassa argumentos para Python

### 27.11 Configurações (.env)

- [ ] Não requer configurações específicas
- [ ] Usa paths do sistema (DOWNLOAD_PATH_*)
- [ ] Respeita `CONFLICT_STRATEGY` do .env
- [ ] Respeita `DRY_RUN_MODE` do .env se setado

### 27.12 Fluxos de Trabalho

**Fluxo: Renomear Temporada de Série**
1. [ ] Usuário seleciona "TV Shows" no menu
2. [ ] Input: caminho da pasta
3. [ ] Input: nome da série
4. [ ] Input: número da temporada
5. [ ] Scan na pasta por vídeos e legendas
6. [ ] Detecção de episódio em cada arquivo
7. [ ] Geração do novo nome: `Serie.S01E01.ext`
8. [ ] Verificação de conflitos
9. [ ] Renomeação (ou dry-run)
10. [ ] Exibição de estatísticas

**Fluxo: Renomear Filmes**
1. [ ] Usuário seleciona "Movies" no menu
2. [ ] Input: caminho da pasta
3. [ ] Input: título do filme
4. [ ] Input: ano
5. [ ] Scan na pasta por vídeos
6. [ ] Geração do novo nome: `Titulo (Ano).ext`
7. [ ] Verificação de conflitos
8. [ ] Renomeação
9. [ ] Exibição de estatísticas

**Fluxo: Renomear Músicas**
1. [ ] Usuário seleciona "Music" no menu
2. [ ] Input: caminho da pasta
3. [ ] Input: número da track
4. [ ] Input: título da track
5. [ ] Scan na pasta por áudio
6. [ ] Geração do novo nome: `## - Titulo.ext`
7. [ ] Renomeação
8. [ ] Exibição de estatísticas

### 27.13 Validações e Segurança

- [ ] Títulos sanitizados (remove `< > : " / \ | ? *`)
- [ ] Títulos truncados (max 100 chars)
- [ ] Autores truncados (max 50 chars)
- [ ] Números validados (inteiros positivos)
- [ ] Extensões suportadas validadas
- [ ] Confirmação implícita no dry-run

### 27.14 Estatísticas e Logs

- [ ] `processed`: total de arquivos escaneados
- [ ] `renamed`: arquivos renomeados com sucesso
- [ ] `skipped`: arquivos já no padrão correto
- [ ] `failed`: arquivos com falha na renomeação
- [ ] Success rate calculado e exibido
- [ ] Logs em `logs/organizer.log`

---

## 2️⃣8️⃣ Testes de CLI Unificado (Atualizado)

### 28.1 Estrutura de Módulos

- [ ] `cli_manager.py` unifica todos os comandos CLI
- [ ] `renamer.py` módulo standalone completo
- [ ] `subtitle_config.py` separado (configuração específica)
- [ ] `subtitle_daemon.py` e `subtitle_downloader.py` intactos
- [ ] Módulos de deleção em `src/` (não em subpasta)

### 28.2 Imports e Dependências

- [ ] `from src.cli_manager import CLIManager` funciona
- [ ] `from src.cli_manager import show_trash_menu` funciona
- [ ] `from src.cli_manager import show_subtitle_menu` funciona
- [ ] `from src.cli_manager import show_renamer_menu` funciona
- [ ] `from src.renamer import RenamerCLI` funciona
- [ ] `from src.link_registry import LinkRegistry` funciona
- [ ] `from src.trash_manager import TrashManager` funciona
- [ ] `from src.deletion_manager import DeletionManager` funciona

### 28.3 Comandos Unificados

- [ ] `media-organizer interactive` - Menu unificado
- [ ] `media-organizer organize` - Organização de mídia
- [ ] `media-organizer renamer` - Renomeação de arquivos
- [ ] `media-organizer trash *` - Comandos de deleção
- [ ] `media-organizer subtitle-*` - Comandos de legendas
- [ ] `media-organizer help` - Help atualizado

### 28.4 Menu Interativo Principal

- [ ] Opção [1]: Organize media files
- [ ] Opção [2]: Rename media files (Renamer) 📝
- [ ] Opção [3]: Scan for new files
- [ ] Opção [4]: View system status
- [ ] Opção [5]: View unorganized files
- [ ] Opção [6]: View organization logs
- [ ] Opção [7]: Start daemon
- [ ] Opção [8]: Stop daemon
- [ ] Opção [9]: View daemon status
- [ ] Opção [10]: View statistics
- [ ] Opção [11]: Trash & Deletion 🗑️
- [ ] Opção [12]: Subtitle Downloader 📺
- [ ] Opção [13]: Exit

---

## 2️⃣9️⃣ Testes de Estrutura de Arquivos (Atualizado)

### 29.1 Nova Estrutura de Diretórios

```
media-organizer/
├── src/
│   ├── renamer.py               # Renamer CLI nativo
│   ├── renamer.sh               # Wrapper shell
│   ├── cli_manager.py           # CLI unificado
│   ├── organizers.py            # Inclui RenamerOrganizer
│   ├── core.py                  # Inclui MediaType.RENAMER
│   ├── link_registry.py         # Registro de hardlinks
│   ├── trash_manager.py         # Gerenciador de lixeira
│   ├── deletion_manager.py      # Orquestrador de exclusão
│   ├── subtitle_config.py       # Configuração OpenSubtitles
│   ├── subtitle_daemon.py       # Daemon de legendas
│   ├── subtitle_downloader.py   # Downloader de legendas
│   └── ... (outros módulos)
├── data/
│   ├── organization.json        # Database principal
│   ├── unorganized.json         # Arquivos falhos
│   ├── link_registry.json       # Registry de hardlinks
│   ├── backups/                 # Backups automáticos
│   └── trash/                   # Lixeira
│       ├── index.json           # Índice de itens
│       └── files/               # Arquivos preservados
├── logs/
│   ├── organizer.log
│   ├── daemon.log
│   └── subtitle_downloader.log
├── docs/
│   └── DELETION_GUIDE.md        # Guia de exclusão
└── .env.example                 # Atualizado com configs
```

### 29.2 Validação de Estrutura

- [ ] `src/renamer.py` existe e é importável
- [ ] `src/renamer.sh` existe e é executável
- [ ] `MediaType.RENAMER` em `src/core.py`
- [ ] `RenamerOrganizer` em `src/organizers.py`
- [ ] `data/link_registry.json` é válido JSON
- [ ] `data/trash/index.json` é válido JSON
- [ ] `docs/DELETION_GUIDE.md` existe e está atualizado
- [ ] `.env.example` inclui configurações de trash
- [ ] Pasta `src/deletion/` removida (arquivos em `src/`)

---

## 3️⃣0️⃣ Matriz de Rastreabilidade (Atualizada)

| Funcionalidade | Módulo | Testes | Status |
|----------------|--------|--------|--------|
| RenamerOrganizer | `src/organizers.py` | Seção 27.1 | ✅ Implementado |
| Renamer CLI | `src/renamer.py` | Seção 27.4-27.5 | ✅ Implementado |
| Renamer Menu | `src/cli_manager.py` | Seção 27.6 | ✅ Implementado |
| MediaType.RENAMER | `src/core.py` | - | ✅ Implementado |
| Link Registry | `src/link_registry.py` | Seção 23.1 | ✅ Implementado |
| Trash Manager | `src/trash_manager.py` | Seção 23.2 | ✅ Implementado |
| Deletion Manager | `src/deletion_manager.py` | Seção 23.3 | ✅ Implementado |
| CLI Trash Commands | `src/cli_manager.py` | Seção 23.4 | ✅ Implementado |
| CLI Unificado | `src/cli_manager.py` | Seção 28 | ✅ Implementado |
| Configurações | `.env.example` | Seção 23.6 | ✅ Implementado |
| Documentação | `README.md` | - | ✅ Implementado |

---

## ✅ Checklist de Aprovação para Produção (Atualizado)

Antes de considerar o sistema pronto para produção, valide:

- [ ] **Todos os testes acima passaram** (incluindo novas seções 23-30)
- [ ] **Renamer testado** para todos os tipos de mídia
- [ ] **Trash & Deletion testado** em ambiente controlado
- [ ] **Restauração da lixeira validada** com arquivos reais
- [ ] **Backup pré-exclusão verificado** e testado restore
- [ ] **Performance aceitável** (scan de filesystem < 5 min)
- [ ] **Recuperação de falhas testada** (reinício após crash)
- [ ] **Backup e restore testados** (database e lixeira)
- [ ] **Documentação atualizada** (`DELETION_GUIDE.md`, `README.md`)
- [ ] **Equipe treinada nos procedimentos** de exclusão/restore
- [ ] **Monitoramento configurado** (lixeira, registry, backups)
- [ ] **Plano de rollback definido** (restaurar backup + lixeira)

---

## 📊 Matriz de Prioridade de Testes (Atualizada)

| Prioridade | Área | Criticidade |
|------------|------|-------------|
| 🔴 Alta | Organização de Filmes/Séries | Crítico |
| 🔴 Alta | Validação de Arquivos | Crítico |
| 🔴 Alta | Database e Backups | Crítico |
| 🔴 Alta | **Trash & Deletion Manager** | **Crítico** |
| 🔴 Alta | **Link Registry** | **Crítico** |
| 🔴 Alta | **Renamer (NATIVO)** | **Crítico** |
| 🟠 Média | TMDB Integration | Importante |
| 🟠 Média | qBittorrent Integration | Importante |
| 🟠 Média | Modo Daemon | Importante |
| 🟠 Média | **CLI Unificado** | **Importante** |
| 🟡 Baixa | Download de Legendas | Nice-to-have |
| 🟡 Baixa | Enriquecimento Online | Nice-to-have |
| 🟡 Baixa | Conversão Calibre | Nice-to-have |

---

## 📞 Suporte e Referências

- **Documentação Principal:** `README.md`
- **Documentação Trash:** `docs/DELETION_GUIDE.md`
- **Logs do Sistema:** `logs/organizer.log`
- **Database:** `data/organization.json`
- **Arquivos Falhos:** `data/unorganized.json`
- **Link Registry:** `data/link_registry.json`
- **Lixeira:** `data/trash/`
- **Configuração:** `.env`

---

*Documento gerado para o Media Organizer System - Fevereiro de 2026*
*Atualizado com Trash & Deletion Manager - Fevereiro de 2026*
*Atualizado com Renamer Nativo - Fevereiro de 2026*

### 24.1 Estrutura de Módulos

- [ ] `cli_manager.py` unifica todos os comandos CLI
- [ ] `subtitle_config.py` separado (configuração específica)
- [ ] `subtitle_daemon.py` e `subtitle_downloader.py` intactos
- [ ] Módulos de deleção em `src/` (não em subpasta)

### 24.2 Imports e Dependências

- [ ] `from src.cli_manager import CLIManager` funciona
- [ ] `from src.cli_manager import show_trash_menu` funciona
- [ ] `from src.cli_manager import show_subtitle_menu` funciona
- [ ] `from src.link_registry import LinkRegistry` funciona
- [ ] `from src.trash_manager import TrashManager` funciona
- [ ] `from src.deletion_manager import DeletionManager` funciona

### 24.3 Comandos Unificados

- [ ] `media-organizer interactive` - Menu unificado
- [ ] `media-organizer organize` - Organização de mídia
- [ ] `media-organizer trash *` - Comandos de deleção
- [ ] `media-organizer subtitle-*` - Comandos de legendas
- [ ] `media-organizer help` - Help atualizado

---

## 2️⃣5️⃣ Testes de Estrutura de Arquivos (Atualização)

### 25.1 Nova Estrutura de Diretórios

```
media-organizer/
├── src/
│   ├── cli_manager.py           # CLI unificado
│   ├── link_registry.py         # Registro de hardlinks
│   ├── trash_manager.py         # Gerenciador de lixeira
│   ├── deletion_manager.py      # Orquestrador de exclusão
│   ├── subtitle_config.py       # Configuração OpenSubtitles
│   ├── subtitle_daemon.py       # Daemon de legendas
│   ├── subtitle_downloader.py   # Downloader de legendas
│   └── ... (outros módulos)
├── data/
│   ├── organization.json        # Database principal
│   ├── unorganized.json         # Arquivos falhos
│   ├── link_registry.json       # Registry de hardlinks
│   ├── backups/                 # Backups automáticos
│   └── trash/                   # Lixeira
│       ├── index.json           # Índice de itens
│       └── files/               # Arquivos preservados
├── logs/
│   ├── organizer.log
│   ├── daemon.log
│   └── subtitle_downloader.log
├── docs/
│   └── DELETION_GUIDE.md        # Guia de exclusão
└── .env.example                 # Atualizado com configs de trash
```

### 25.2 Validação de Estrutura

- [ ] `data/link_registry.json` é válido JSON
- [ ] `data/trash/index.json` é válido JSON
- [ ] `docs/DELETION_GUIDE.md` existe e está atualizado
- [ ] `.env.example` inclui configurações de trash
- [ ] Pasta `src/deletion/` removida (arquivos em `src/`)

---

## 2️⃣6️⃣ Matriz de Rastreabilidade (NOVO)

| Funcionalidade | Módulo | Testes | Status |
|----------------|--------|--------|--------|
| Link Registry | `src/link_registry.py` | Seção 23.1 | ✅ Implementado |
| Trash Manager | `src/trash_manager.py` | Seção 23.2 | ✅ Implementado |
| Deletion Manager | `src/deletion_manager.py` | Seção 23.3 | ✅ Implementado |
| CLI Trash Commands | `src/cli_manager.py` | Seção 23.4 | ✅ Implementado |
| Menu Interativo | `src/cli_manager.py` | Seção 23.5 | ✅ Implementado |
| Configurações | `.env.example` | Seção 23.6 | ✅ Implementado |
| Documentação | `docs/DELETION_GUIDE.md` | - | ✅ Implementado |

---

## ✅ Checklist de Aprovação para Produção (Atualizado)

Antes de considerar o sistema pronto para produção, valide:

- [ ] **Todos os testes acima passaram** (incluindo novas seções 23-26)
- [ ] **Trash & Deletion testado** em ambiente controlado
- [ ] **Restauração da lixeira validada** com arquivos reais
- [ ] **Backup pré-exclusão verificado** e testado restore
- [ ] **Performance aceitável** (scan de filesystem < 5 min)
- [ ] **Recuperação de falhas testada** (reinício após crash)
- [ ] **Backup e restore testados** (database e lixeira)
- [ ] **Documentação atualizada** (`DELETION_GUIDE.md`, `README.md`)
- [ ] **Equipe treinada nos procedimentos** de exclusão/restore
- [ ] **Monitoramento configurado** (lixeira, registry, backups)
- [ ] **Plano de rollback definido** (restaurar backup + lixeira)

---

## 📊 Matriz de Prioridade de Testes (Atualizada)

| Prioridade | Área | Criticidade |
|------------|------|-------------|
| 🔴 Alta | Organização de Filmes/Séries | Crítico |
| 🔴 Alta | Validação de Arquivos | Crítico |
| 🔴 Alta | Database e Backups | Crítico |
| 🔴 Alta | **Trash & Deletion Manager** | **Crítico** |
| 🔴 Alta | **Link Registry** | **Crítico** |
| 🟠 Média | TMDB Integration | Importante |
| 🟠 Média | qBittorrent Integration | Importante |
| 🟠 Média | Modo Daemon | Importante |
| 🟠 Média | **CLI Unificado** | **Importante** |
| 🟡 Baixa | Download de Legendas | Nice-to-have |
| 🟡 Baixa | Enriquecimento Online | Nice-to-have |
| 🟡 Baixa | Conversão Calibre | Nice-to-have |

---

## 📞 Suporte e Referências

- **Documentação Principal:** `README.md`
- **Documentação Trash:** `docs/DELETION_GUIDE.md`
- **Logs do Sistema:** `logs/organizer.log`
- **Database:** `data/organization.json`
- **Arquivos Falhos:** `data/unorganized.json`
- **Link Registry:** `data/link_registry.json`
- **Lixeira:** `data/trash/`
- **Configuração:** `.env`

---

*Documento gerado para o Media Organizer System - Fevereiro 2026*
*Atualizado com Trash & Deletion Manager - Fevereiro 2026*
