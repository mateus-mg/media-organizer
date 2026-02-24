# 📋 Plano de Implementação - OpenSubtitles Auto-Downloader

## 🔍 Análise do Sistema Atual

### Estrutura Atual do `organized.json`

```json
{
  "media": {
    "file_hash": {
      "original_path": "...",
      "organized_path": "...",
      "metadata": {
        "title": "...",
        "year": 2020,
        "tmdb_id": 12345,
        "media_type": "movie"
      },
      "errors": []
    }
  }
}
```

**Problema Identificado:** Não há campo para tracking de legendas.

### Funcionalidades Existentes de Legendas

1. **`move_subtitles_with_video()`** (src/utils.py)
   - Move legendas existentes (.srt, .ass, .vtt) junto com o vídeo
   - Renomeia para combinar com o vídeo organizado

2. **`log_subtitle_moved()`** (src/log_config.py)
   - Log de operações de legendas

3. **Integração nos organizers** (src/organizers.py)
   - Move legendas automaticamente durante organização

---

## 📊 O Que Precisa Ser Criado/Alterado/Removido

### ✅ CRIAR

1. **`src/subtitle_downloader.py`** (NOVO)
   - Cliente da API OpenSubtitles
   - Autenticação e gerenciamento de sessão
   - Busca e download de legendas
   - Controle de rate limit (20 downloads/dia)

2. **`src/subtitle_config.py`** (NOVO)
   - Configurações específicas para downloader de legendas
   - API keys, preferências de idioma, etc.

3. **`src/subtitle_daemon.py`** (NOVO)
   - Daemon para execução a cada 24 horas
   - Gerenciamento de ciclo de download
   - Logs estruturados

4. **`scripts/run-subtitle-daemon.sh`** (NOVO)
   - Script para iniciar o daemon
   - Script para verificar status
   - Script para parar o daemon

5. **Campo `subtitles` no `organized.json`**
   - Adicionar tracking de legendas por arquivo

### ✏️ ALTERAR

1. **`src/persistence.py`**
   - Adicionar campo `subtitles` no schema do banco de dados
   - Métodos para atualizar status de legendas

2. **`src/__init__.py`**
   - Exportar novas classes do subtitle downloader

3. **`requirements.txt`**
   - Adicionar dependência: `opensubtitlescom` ou `requests`

4. **`README.md`**
   - Documentar novo recurso de download de legendas
   - Instruções de configuração da API OpenSubtitles

5. **`.env.example`**
   - Adicionar configurações do OpenSubtitles

### ❌ REMOVER

- Nada precisa ser removido (sistema é aditivo)

---

## 🏗️ Arquitetura Proposta

```
media-organizer/
├── src/
│   ├── subtitle_config.py        # Configurações OpenSubtitles
│   ├── subtitle_downloader.py    # Cliente API + Download logic
│   ├── subtitle_daemon.py        # Daemon de execução (24h)
│   ├── persistence.py            # (ALTERADO) + campo subtitles
│   └── ...
├── scripts/
│   ├── run-subtitle-daemon.sh    # Iniciar daemon
│   ├── status-subtitle-daemon.sh # Ver status
│   └── stop-subtitle-daemon.sh   # Parar daemon
├── data/
│   └── organized.json            # (ALTERADO) + campo subtitles
└── .env                          # (ALTERADO) + OpenSubtitles creds
```

---

## 📋 Plano de Execução

### FASE 1: Configuração e Estrutura Base (Dia 1)

#### 1.1 Criar `src/subtitle_config.py`
```python
"""
Configuração para OpenSubtitles Downloader
"""
import os
from pathlib import Path
from typing import List

class SubtitleConfig:
    def __init__(self):
        # API Credentials
        self.api_key = os.getenv('OPENSUBTITLES_API_KEY', '')
        self.api_username = os.getenv('OPENSUBTITLES_USERNAME', '')
        self.api_password = os.getenv('OPENSUBTITLES_PASSWORD', '')
        
        # API Settings
        self.api_url = 'https://api.opensubtitles.com/api/v1'
        self.download_limit = 20  # downloads por dia
        self.reset_time = '00:00'  # horário que reset
        
        # Preferences
        self.preferred_languages = os.getenv(
            'SUBTITLE_LANGUAGES', 'pt,en,es'
        ).split(',')
        
        # Paths
        self.database_path = Path(os.getenv(
            'DATABASE_PATH', './data/organization.json'
        ))
        
        # Logging
        self.log_file = Path(os.getenv(
            'SUBTITLE_LOG_FILE', './logs/subtitle_downloader.log'
        ))
```

#### 1.2 Atualizar `.env.example`
```bash
# OpenSubtitles API
# Get API key at: https://www.opensubtitles.com/en/consumers
OPENSUBTITLES_API_KEY="your_api_key_here"
OPENSUBTITLES_USERNAME="your_username"
OPENSUBTITLES_PASSWORD="your_password"

# Subtitle Downloader
SUBTITLE_LANGUAGES="pt,en,es"
SUBTITLE_LOG_FILE="./logs/subtitle_downloader.log"
SUBTITLE_DOWNLOAD_INTERVAL="86400"  # 24 hours in seconds
```

#### 1.3 Atualizar `requirements.txt`
```txt
# OpenSubtitles Integration
requests>=2.31.0
python-dotenv>=1.0.0
```

---

### FASE 2: Cliente API OpenSubtitles (Dia 2)

#### 2.1 Criar `src/subtitle_downloader.py`

**Estrutura:**
```python
"""
OpenSubtitles API Client and Subtitle Downloader
"""
import requests
import hashlib
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime, timedelta

class OpenSubtitlesClient:
    """Client for OpenSubtitles.com API"""
    
    def __init__(self, config):
        self.config = config
        self.api_key = config.api_key
        self.base_url = config.api_url
        self.session = requests.Session()
        self.token = None
        self.user_agent = "MediaOrganizer v2.0"
        
    def login(self) -> bool:
        """Authenticate with OpenSubtitles API"""
        # Implement OAuth2 or API key auth
        
    def search_subtitles(
        self,
        tmdb_id: int,
        media_type: str,
        languages: List[str]
    ) -> List[Dict]:
        """Search for subtitles"""
        
    def download_subtitle(
        self,
        file_id: int,
        save_path: Path
    ) -> Optional[Path]:
        """Download subtitle file"""
        
    def get_remaining_downloads(self) -> int:
        """Get remaining downloads for today"""
        
    def check_rate_limit(self) -> bool:
        """Check if we can download more today"""


class SubtitleDownloader:
    """Main downloader logic"""
    
    def __init__(self, config, database, logger):
        self.config = config
        self.database = database
        self.logger = logger
        self.client = OpenSubtitlesClient(config)
        self.downloads_today = 0
        
    def process_organized_media(self):
        """Process all organized media looking for subtitles"""
        
    def extract_video_hash(self, video_path: Path) -> str:
        """Calculate hash for subtitle matching"""
        
    def download_for_file(
        self,
        file_info: Dict,
        organized_path: Path
    ) -> bool:
        """Download subtitle for single file"""
        
    def save_subtitle(
        self,
        subtitle_data: bytes,
        video_path: Path,
        language: str
    ) -> Path:
        """Save subtitle file next to video"""
        
    def update_database(
        self,
        file_hash: str,
        subtitle_path: Path,
        language: str
    ):
        """Update organized.json with subtitle info"""
```

---

### FASE 3: Atualizar Banco de Dados (Dia 3)

#### 3.1 Atualizar `src/persistence.py`

**Adicionar campo `subtitles`:**
```python
def adicionar_midia(self, file_hash, original_path, organized_path, metadata):
    record = {
        "file_hash": file_hash,
        "original_path": original_path,
        "organized_path": organized_path,
        "metadata": metadata,
        "subtitles": [],  # NOVO CAMPO
        "errors": []
    }
```

**Adicionar métodos:**
```python
def add_subtitle(
    self,
    file_hash: str,
    subtitle_path: str,
    language: str
) -> bool:
    """Add subtitle to media record"""
    
def has_subtitle(
    self,
    file_hash: str,
    language: str = None
) -> bool:
    """Check if media has subtitle"""
    
def get_files_without_subtitles(
    self,
    media_type: str = None
) -> List[Dict]:
    """Get list of files without subtitles"""
```

---

### FASE 4: Daemon de Execução (Dia 4)

#### 4.1 Criar `src/subtitle_daemon.py`

```python
#!/usr/bin/env python3
"""
Subtitle Downloader Daemon
Runs every 24 hours to download missing subtitles
"""

import asyncio
import time
from pathlib import Path
from datetime import datetime
from src.subtitle_config import SubtitleConfig
from src.subtitle_downloader import SubtitleDownloader
from src.log_config import (
    get_logger, set_console_log_level,
    log_info, log_success, log_error, log_stats
)
from src.log_formatter import LogSection

class SubtitleDaemon:
    """Daemon for automatic subtitle downloads"""
    
    def __init__(self, check_interval: int = 86400):
        self.config = SubtitleConfig()
        self.logger = get_logger(
            name="SubtitleDaemon",
            log_file=self.config.log_file
        )
        self.check_interval = check_interval
        self.downloader = SubtitleDownloader(
            self.config, None, self.logger
        )
        self.running = False
        
    async def run_cycle(self):
        """Run one download cycle"""
        log_info(self.logger, "Starting subtitle download cycle")
        
        # Check rate limit
        remaining = self.downloader.client.get_remaining_downloads()
        log_info(self.logger, f"Remaining downloads today: {remaining}")
        
        if remaining <= 0:
            log_warning(self.logger, "No downloads remaining today")
            return
        
        # Get files without subtitles (by priority)
        priorities = ['movie', 'tv', 'dorama', 'anime']
        
        for media_type in priorities:
            if remaining <= 0:
                break
                
            files = self.downloader.database.get_files_without_subtitles(
                media_type=media_type
            )
            
            for file_info in files:
                if remaining <= 0:
                    break
                    
                success = await self.downloader.download_for_file(
                    file_info,
                    Path(file_info['organized_path'])
                )
                
                if success:
                    remaining -= 1
        
        # Log summary
        self.log_cycle_summary()
        
    def log_cycle_summary(self):
        """Log cycle summary"""
        summary = {
            'Downloads today': self.downloader.downloads_today,
            'Remaining': self.downloader.client.get_remaining_downloads(),
            'Next cycle': '24 hours'
        }
        log_stats(self.logger, str(summary))
        
    async def run(self):
        """Run daemon continuously"""
        self.running = True
        log_info(self.logger, "Subtitle Daemon started")
        log_info(self.logger, f"Check interval: {self.check_interval}s")
        
        while self.running:
            try:
                await self.run_cycle()
                
                # Wait for next cycle
                log_info(
                    self.logger,
                    f"Next check in {self.check_interval // 3600} hours"
                )
                await asyncio.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                self.stop()
            except Exception as e:
                log_error(self.logger, f"Cycle error: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour on error
                
    def stop(self):
        """Stop daemon"""
        self.running = False
        log_info(self.logger, "Subtitle Daemon stopped")


async def main():
    daemon = SubtitleDaemon()
    await daemon.run()

if __name__ == "__main__":
    asyncio.run(main())
```

---

### FASE 5: Scripts de Controle (Dia 5)

#### 5.1 Criar `scripts/run-subtitle-daemon.sh`

```bash
#!/bin/bash
# Subtitle Daemon Manager

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
PID_FILE=".subtitle_daemon.pid"
LOG_FILE="logs/subtitle_downloader.log"

case "$1" in
    "start")
        if [ -f "$PID_FILE" ]; then
            echo "Daemon already running (PID: $(cat $PID_FILE))"
            exit 1
        fi
        
        source venv/bin/activate
        nohup python -m src.subtitle_daemon >> "$LOG_FILE" 2>&1 &
        echo $! > "$PID_FILE"
        
        echo "✓ Subtitle Daemon started"
        echo "  PID: $(cat $PID_FILE)"
        echo "  Log: $LOG_FILE"
        ;;
        
    "stop")
        if [ ! -f "$PID_FILE" ]; then
            echo "Daemon not running"
            exit 0
        fi
        
        kill $(cat $PID_FILE)
        rm -f "$PID_FILE"
        echo "✓ Subtitle Daemon stopped"
        ;;
        
    "status")
        if [ -f "$PID_FILE" ]; then
            PID=$(cat $PID_FILE)
            if ps -p $PID > /dev/null 2>&1; then
                echo "✓ Running (PID: $PID)"
                echo "  Log: $LOG_FILE"
                tail -n 10 "$LOG_FILE"
            else
                echo "✗ Stale PID file (process not running)"
                rm -f "$PID_FILE"
            fi
        else
            echo "✗ Not running"
        fi
        ;;
        
    *)
        echo "Usage: $0 {start|stop|status}"
        exit 1
        ;;
esac
```

#### 5.2 Criar `scripts/status-subtitle-daemon.sh`
- Verifica status do daemon
- Mostra últimas entradas do log
- Mostra estatísticas de downloads

#### 5.3 Criar `scripts/stop-subtitle-daemon.sh`
- Para o daemon graciosamente

---

### FASE 6: Integração e Testes (Dia 6-7)

#### 6.1 Atualizar `src/__init__.py`
```python
# Subtitle Downloader
from src.subtitle_config import SubtitleConfig
from src.subtitle_downloader import OpenSubtitlesClient, SubtitleDownloader
from src.subtitle_daemon import SubtitleDaemon

__all__ = [
    # ... existing exports
    "SubtitleConfig",
    "OpenSubtitlesClient",
    "SubtitleDownloader",
    "SubtitleDaemon",
]
```

#### 6.2 Atualizar `README.md`
- Adicionar seção sobre download de legendas
- Instruções de configuração
- Exemplos de uso

#### 6.3 Criar testes
- `tests/test_subtitle_downloader.py`
- Testar autenticação
- Testar busca de legendas
- Testar download
- Testar rate limit

---

## 📅 Cronograma de Execução

| Dia | Fase | Tarefas | Status |
|-----|------|---------|--------|
| 1 | Configuração | subtitle_config.py, .env, requirements | ⏳ Pendente |
| 2 | API Client | OpenSubtitlesClient, SubtitleDownloader | ⏳ Pendente |
| 3 | Database | persistence.py + campo subtitles | ⏳ Pendente |
| 4 | Daemon | subtitle_daemon.py | ⏳ Pendente |
| 5 | Scripts | run/stop/status-daemon.sh | ⏳ Pendente |
| 6 | Integração | __init__.py, README, testes | ⏳ Pendente |
| 7 | Testes | Testes manuais e validação | ⏳ Pendente |

---

## ⚠️ Riscos e Mitigações

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| API Key inválida | Alto | Validar no startup |
| Rate limit excedido | Médio | Controle rigoroso + log |
| Legendas em idioma errado | Baixo | Configuração de preferências |
| Download falha | Baixo | Retry com backoff |
| Database corruption | Alto | Backup antes de atualizar |

---

## ✅ Critérios de Aceite

1. [ ] Daemon roda a cada 24 horas sem falhas
2. [ ] Respeita limite de 20 downloads/dia
3. [ ] Baixa legendas em português prioritariamente
4. [ ] Salva legendas na pasta correta
5. [ ] Atualiza organized.json após download
6. [ ] Logs estruturados e claros
7. [ ] Scripts de controle funcionam
8. [ ] 40+ testes passando

---

**Aguardando aprovação para iniciar implementação.**
