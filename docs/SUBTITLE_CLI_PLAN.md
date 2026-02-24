# 📋 Plano de Implementação - Funções CLI para Subtitle Daemon

## 🔍 Análise do Menu CLI Atual

### Comandos Existentes (`src/main.py`)

| Comando | Descrição | Contexto |
|---------|-----------|----------|
| `organize` | Organizar arquivos de mídia | Interativo |
| `unorganized` | Listar arquivos não organizados | Info |
| `stats` | Mostrar estatísticas | Info |
| `test` | Testar configuração | Utilidade |
| `process-new-media` | Processar novos downloads | Automático |
| `daemon` | Modo daemon (organização) | Contínuo |

### Scripts Shell na Raiz

| Script | Função |
|--------|--------|
| `run.sh` | Entry point principal |
| `media-daemon.sh` | Controle do daemon de organização |
| `subtitle-daemon.sh` | Controle do daemon de legendas |

---

## 📊 O Que Precisa Ser Criado/Alterado

### ✅ CRIAR

1. **Novos comandos CLI em `src/main.py`:**
   - `subtitle-download` - Download manual de legendas
   - `subtitle-status` - Status do banco de legendas
   - `subtitle-config` - Configurar OpenSubtitles

2. **Módulo de integração:**
   - `src/subtitle_cli.py` - Funções CLI reutilizáveis

3. **Atualizar menu interativo:**
   - Adicionar opção "Subtitle Downloader" no menu principal

### ✏️ ALTERAR

1. **`src/main.py`:**
   - Adicionar imports do subtitle
   - Adicionar 3 novos comandos `@cli.command()`
   - Atualizar menu interativo `organize()`

2. **`README.md`:**
   - Adicionar seção de comandos CLI
   - Exemplos de uso

3. **`run.sh`:**
   - Garantir que passe argumentos corretamente

### ❌ REMOVER

- Nada (abordagem aditiva)

---

## 🏗️ Arquitetura Proposta

```
CLI Commands (main.py)
│
├── organize              # Menu interativo
│   └── + Opção 8: Subtitles
│
├── subtitle-download     # NOVO
│   ├── --manual          # Rodar uma vez
│   ├── --media-type      # Filtrar por tipo
│   └── --language        # Idioma específico
│
├── subtitle-status       # NOVO
│   ├── --show-all        # Mostrar todos
│   └── --missing         # Apenas sem legenda
│
└── subtitle-config       # NOVO
    ├── --setup           # Wizard de configuração
    └── --test            # Testar API
```

---

## 📋 Plano de Execução

### FASE 1: Criar Módulo CLI de Legendas (Dia 1)

#### 1.1 Criar `src/subtitle_cli.py`

```python
#!/usr/bin/env python3
"""
CLI helpers for Subtitle Downloader

Reusable functions for subtitle-related CLI commands.
"""

from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm

from src.subtitle_config import SubtitleConfig
from src.subtitle_downloader import SubtitleDownloader
from src.persistence import OrganizationDatabase
from src.log_config import get_logger, log_success, log_error, log_info


def run_manual_download(
    media_type: Optional[str] = None,
    language: Optional[str] = None,
    dry_run: bool = False
) -> dict:
    """
    Run manual subtitle download
    
    Args:
        media_type: Filter by media type (movie, tv, etc.)
        language: Specific language to download
        dry_run: Show what would be done
        
    Returns:
        Statistics dictionary
    """
    # Implementation...


def show_subtitle_status(
    show_missing: bool = False,
    show_all: bool = False
) -> dict:
    """
    Show subtitle statistics
    
    Args:
        show_missing: Only show files without subtitles
        show_all: Show all files with details
        
    Returns:
        Statistics dictionary
    """
    # Implementation...


def setup_subtitle_config() -> bool:
    """
    Interactive setup wizard for OpenSubtitles
    
    Returns:
        True if setup successful
    """
    # Implementation...


def test_subtitle_config() -> bool:
    """
    Test OpenSubtitles configuration
    
    Returns:
        True if configuration valid
    """
    # Implementation...
```

---

### FASE 2: Adicionar Comandos CLI (Dia 2)

#### 2.1 Comando `subtitle-download`

```python
@cli.command()
@click.option('--manual', is_flag=True, help='Run manual download (one-time)')
@click.option('--media-type', type=click.Choice(['movie', 'tv', 'dorama', 'anime']), 
              help='Filter by media type')
@click.option('--language', type=str, help='Specific language (e.g., pt, en)')
@click.pass_context
def subtitle_download(ctx, manual, media_type, language):
    """
    Download subtitles from OpenSubtitles
    
    Run manual download or check daemon status.
    """
    console = Console()
    console.print("\n[bold cyan]Subtitle Downloader[/bold cyan]\n")
    
    if manual:
        # Run manual download
        from src.subtitle_cli import run_manual_download
        stats = run_manual_download(
            media_type=media_type,
            language=language
        )
        
        # Show results
        console.print(f"[green]✓ Downloaded: {stats['subtitles_downloaded']}[/green]")
        console.print(f"[yellow]Skipped: {stats['subtitles_skipped']}[/yellow]")
    else:
        # Show daemon status
        from src.subtitle_cli import show_daemon_status
        show_daemon_status()
```

#### 2.2 Comando `subtitle-status`

```python
@cli.command()
@click.option('--missing', is_flag=True, help='Show only files without subtitles')
@click.option('--detailed', is_flag=True, help='Show detailed information')
def subtitle_status(missing, detailed):
    """
    Show subtitle statistics and status
    
    Display coverage statistics and files missing subtitles.
    """
    from src.subtitle_cli import show_subtitle_status
    
    stats = show_subtitle_status(
        show_missing=missing,
        show_all=detailed
    )
    
    # Display formatted results
```

#### 2.3 Comando `subtitle-config`

```python
@cli.command()
@click.option('--setup', is_flag=True, help='Run setup wizard')
@click.option('--test', is_flag=True, help='Test API configuration')
@click.option('--show', is_flag=True, help='Show current configuration')
def subtitle_config(setup, test, show):
    """
    Configure OpenSubtitles integration
    
    Setup API credentials and test connectivity.
    """
    from src.subtitle_cli import setup_subtitle_config, test_subtitle_config
    
    if setup:
        success = setup_subtitle_config()
        if success:
            print("✓ Configuration saved!")
    elif test:
        success = test_subtitle_config()
        if success:
            print("✓ API connection successful!")
    elif show:
        # Show current config
        pass
```

---

### FASE 3: Atualizar Menu Interativo (Dia 3)

#### 3.1 Adicionar Opção no Menu Principal

```python
def show_main_menu():
    """Show interactive main menu"""
    console.print("\n[bold cyan]🗄️  Media Organizer System[/bold cyan]")
    console.print("[bold]Select an operation:[/bold]")

    options = {
        "1": "Organize media files",
        "2": "Subtitle Downloader",      # NOVO
        "3": "View system status",
        "4": "View unorganized files",
        "5": "View organization logs",
        "6": "Start daemon",
        "7": "Stop daemon",
        "8": "View daemon status",
        "9": "View statistics",
        "10": "Exit"
    }
    
    # ... rest of menu logic
```

#### 3.2 Criar Submenu de Legendas

```python
def show_subtitle_menu():
    """Show subtitle downloader submenu"""
    console.print("\n[bold cyan]📺 Subtitle Downloader[/bold cyan]")
    console.print("[bold]Select an operation:[/bold]")

    options = {
        "1": "Download subtitles (manual)",
        "2": "View subtitle status",
        "3": "Files missing subtitles",
        "4": "Start subtitle daemon",
        "5": "Stop subtitle daemon",
        "6": "Restart subtitle daemon",
        "7": "Configure OpenSubtitles",
        "8": "Test API connection",
        "0": "Back to main menu"
    }
    
    # Handle choices...
    
    if choice == "1":
        # Run manual download
        run_manual_download()
    elif choice == "2":
        # Show status
        show_subtitle_status()
    elif choice == "3":
        # Show missing
        show_subtitle_status(show_missing=True)
    elif choice == "4":
        # Start daemon
        start_subtitle_daemon()
    elif choice == "5":
        # Stop daemon
        stop_subtitle_daemon()
    elif choice == "6":
        # Restart daemon
        restart_subtitle_daemon()
    elif choice == "7":
        # Setup wizard
        setup_subtitle_config()
    elif choice == "8":
        # Test API
        test_subtitle_config()
```

---

### FASE 4: Integração e Testes (Dia 4)

#### 4.1 Atualizar `src/__init__.py`

```python
# Export CLI helpers
from src.subtitle_cli import (
    run_manual_download,
    show_subtitle_status,
    setup_subtitle_config,
    test_subtitle_config
)
```

#### 4.2 Atualizar `run.sh`

```bash
# Ensure subtitle daemon script exists
if [ -f "./subtitle-daemon.sh" ]; then
    echo "✓ Subtitle daemon available"
else
    echo "⚠ Subtitle daemon not found"
fi
```

#### 4.3 Atualizar `README.md`

Adicionar seção:

```markdown
## CLI Commands - Subtitle Downloader

### Download Subtitles
```bash
# Manual download (all media)
./run.sh subtitle-download --manual

# Download for movies only
./run.sh subtitle-download --manual --media-type movie

# Download Portuguese subtitles only
./run.sh subtitle-download --manual --language pt
```

### Check Status
```bash
# Show statistics
./run.sh subtitle-status

# Show files missing subtitles
./run.sh subtitle-status --missing

# Detailed view
./run.sh subtitle-status --detailed
```

### Configuration
```bash
# Setup wizard
./run.sh subtitle-config --setup

# Test API
./run.sh subtitle-config --test

# Show current config
./run.sh subtitle-config --show
```
```

---

## 📅 Cronograma

| Dia | Fase | Tarefas | Status |
|-----|------|---------|--------|
| 1 | CLI Module | Criar `subtitle_cli.py` | ⏳ Pendente |
| 2 | CLI Commands | Adicionar 3 comandos | ⏳ Pendente |
| 3 | Menu | Atualizar menu interativo | ⏳ Pendente |
| 4 | Testes | Integrar e testar | ⏳ Pendente |

---

## ✅ Critérios de Aceite

1. [ ] 3 novos comandos CLI funcionando
2. [ ] Menu interativo com opção de legendas
3. [ ] Submenu com 8 opções (inclui start/stop/restart)
4. [ ] `--help` documentando todas as opções
5. [ ] Logs estruturados nos comandos
6. [ ] Testes passando (40+)
7. [ ] README atualizado

---

## 🎯 Exemplo de Uso

```bash
# Via CLI direta
./run.sh subtitle-download --manual
./run.sh subtitle-status --missing
./run.sh subtitle-config --test

# Via menu interativo
./run.sh organize
  → 2: Subtitle Downloader
    → 1: Download subtitles (manual)
    → 2: View subtitle status
    → 3: Files missing subtitles
```

---

**Aguardando aprovação para iniciar implementação.**
