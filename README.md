# Media Organization System

Organizador de mídia com foco em música, livros e quadrinhos, com fluxo principal via CLI interativo e comandos diretos.

## Escopo Atual

- Organização por hardlink (economia de espaço em disco)
- Classificação automática por extensão e contexto
- Organização de letras `.lrc` junto da música
- Organização de capas/arte (`.jpg`, `.jpeg`, `.png`, `.webp`) como `artwork`
- Enriquecimento opcional de metadados online (música e livros)
- Validação e limpeza de gêneros com Genre Guard
- Sugestões de nome de arquivo para livros e quadrinhos
- Relatórios de qualidade de metadados

## Formatos Suportados

- Music: `.mp3`, `.flac`, `.wav`, `.m4a`, `.ogg`, `.opus`, `.aac`, `.wma`, `.m4b`
- Lyrics: `.lrc`
- Artwork: `.jpg`, `.jpeg`, `.png`, `.webp`
- Books: `.epub`, `.pdf`, `.mobi`, `.azw`, `.azw3`
- Comics: `.cbz`, `.cbr`, `.cb7`, `.cbt`

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Execução

### Menu interativo (recomendado)

```bash
./run.sh interactive
```

Menu principal atual:

- `[1]` Organize media files
- `[2]` Filename suggestions
- `[3]` System information
- `[4]` Genre catalog management
- `[5]` Exit
- `[9]` `[Admin] Music genre backfill` (aparece apenas com `ENABLE_ADMIN_BACKFILL_MENU=true`)

### Comandos diretos disponíveis

```bash
./run.sh organize
./run.sh interactive
./run.sh process-new-media
./run.sh preview-music-metadata --path "/path/to/music"
./run.sh music-genre-backfill
./run.sh music-genre-backfill --execute
./run.sh backup-integrity
./run.sh backup-integrity --cleanup
./run.sh suggest-filenames --root "/path/to/folder" --media all
./run.sh edit-filename-suggestion --report data/filename_suggestions_report.json --index 0 --new-name "Novo Nome.pdf"
./run.sh apply-filename-suggestions --report data/filename_suggestions_report.json
./run.sh apply-filename-suggestions --report data/filename_suggestions_report.json --execute
./run.sh backfill-book-covers --limit 0
./run.sh backfill-book-years --limit 0
./run.sh stats
./run.sh test
```

## Fluxo de Organização

O comando principal de ciclo manual é:

```bash
./run.sh process-new-media
```

Comportamento atual por ciclo:

1. Escaneia downloads de música, livros e quadrinhos.
2. Em música, executa pré-limpeza de gêneros inválidos nos arquivos de entrada.
3. Organiza arquivos por tipo e estratégia de conflito (`skip`, `rename`, `overwrite`).
4. Em música, reavalia o banco para detectar faixas com gêneros inválidos e reprocessa quando necessário.

## Gerenciamento de Catálogos de Gênero

No menu principal (`interactive`), a opção `Genre catalog management` permite:

- Gerenciar gêneros inválidos (`data/invalid_music_genres.json`)
	- Listar catálogo
	- Adicionar/remover termo exato
	- Adicionar/remover padrão regex
- Gerenciar palavras-chave musicais (`data/musical_keywords.json`)
	- Listar/adicionar/remover keyword
- Gerenciar exceções de gênero (`data/genre_exceptions.json`)
	- Listar/adicionar/remover exceção

As alterações geram snapshots em `data/backups/`.

## Configuração Essencial

Defina no `.env`:

```env
LIBRARY_PATH_MUSIC=/path/to/library/music
LIBRARY_PATH_BOOKS=/path/to/library/books
LIBRARY_PATH_COMICS=/path/to/library/comics

DOWNLOAD_PATH_MUSIC=/path/to/downloads/music
DOWNLOAD_PATH_BOOKS=/path/to/downloads/books
DOWNLOAD_PATH_COMICS=/path/to/downloads/comics
```

Opções importantes:

```env
CONFLICT_STRATEGY=skip
ENRICH_MUSIC_METADATA_ONLINE=false
ENRICH_BOOK_METADATA_ONLINE=false
ENRICH_BOOK_METADATA_GOOGLE_BOOKS=true
GOOGLE_BOOKS_API_KEY=
BOOK_METADATA_TRUST_MODE=missing_only
ENABLE_ADMIN_BACKFILL_MENU=false
```

`BOOK_METADATA_TRUST_MODE`:

- `missing_only`: preserva tags existentes e só completa lacunas
- `replace_with_online`: substitui campos principais por dados online quando confiáveis

## Dados e Relatórios

- Banco principal: `data/organization.json`
- Registro de links: `data/link_registry.json`
- Catálogo de inválidos: `data/invalid_music_genres.json`
- Catálogo suspeito: `data/suspect_music_genres.json`
- Exceções de gênero: `data/genre_exceptions.json`
- Keywords musicais: `data/musical_keywords.json`
- Relatório de ciclo do guard: `data/genre_guard_cycle_report.json`
- Auditoria de decisões do guard: `data/genre_guard_decisions_latest.json`
- Sugestões de regras do guard: `data/genre_guard_rule_suggestions.json`
- Relatórios de qualidade: `data/quality_report_latest.json`, `data/genre_quality_report_latest.json`
- Relatórios de sugestão de nomes: `data/filename_suggestions_report.json`, `data/filename_suggestions_apply_report.json`
- Logs: `logs/organizer.log`
- Backups: `data/backups/`

## Notas Importantes

- O projeto neste workspace não expõe scripts de daemon (`run-daemon.sh`) nem de subtitles (`subtitle-daemon.sh`).
- O `run.sh` é o ponto de entrada oficial e executa `python -m app.main`.
- O sistema suporta `--dry-run` em comandos Click (`./run.sh --dry-run <comando>`), além de variáveis de ambiente de dry-run já existentes.

## Privacidade

- Nunca versione `.env` com credenciais/chaves.
- Arquivos `data/*.json` e `logs/*.log` podem conter caminhos reais da biblioteca.

## Troubleshooting

### O dashboard de qualidade aparece vazio

- Execute primeiro `./run.sh process-new-media` para popular `data/organization.json`.

### Gêneros válidos sendo removidos

- Revise `data/genre_exceptions.json` e `data/musical_keywords.json`.
- Use o submenu `Genre catalog management` para ajustes.
- Verifique `data/genre_guard_cycle_report.json` para diagnóstico do último ciclo.
