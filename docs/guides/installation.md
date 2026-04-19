# Installation

## System Requirements

- Linux (required for hardlink support)
- Python 3.9 or higher
- Git

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/mateus-mg/media-organizer.git
cd media-organizer
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your paths:

```bash
# Library paths (where organized media goes)
LIBRARY_PATH_MUSIC=/path/to/library/music
LIBRARY_PATH_BOOKS=/path/to/library/books
LIBRARY_PATH_COMICS=/path/to/library/comics

# Download paths (where downloads are located)
DOWNLOAD_PATH_MUSIC=/path/to/downloads/music
DOWNLOAD_PATH_BOOKS=/path/to/downloads/books
DOWNLOAD_PATH_COMICS=/path/to/downloads/comics
```

### 5. Verify Installation

```bash
./run.sh test
```

## Running the Application

```bash
# Interactive menu
./run.sh interactive

# Process new media
./run.sh process-new-media

# Dry run (preview only)
./run.sh process-new-media --dry-run
```
