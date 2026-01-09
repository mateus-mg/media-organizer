"""
Filename parsers for extracting metadata from media filenames
Supports movies, TV shows, anime, and other media types
"""

import re
from pathlib import Path
from typing import Optional, Dict, Tuple, List
from datetime import datetime


class MediaInfo:
    """Container for parsed media information"""

    def __init__(self):
        self.title: str = ""
        self.year: Optional[int] = None
        self.season: Optional[int] = None
        self.episode: Optional[int] = None
        self.episode_title: Optional[str] = None
        self.quality: Optional[str] = None
        self.codec: Optional[str] = None
        self.audio: Optional[str] = None
        self.release_group: Optional[str] = None
        self.is_proper: bool = False
        self.is_repack: bool = False
        self.is_3d: bool = False
        self.media_type: str = "unknown"


def detect_media_type(file_path: Path) -> str:
    """
    Detect media type based on filename patterns and parent folder context

    Args:
        file_path: Path to media file

    Returns:
        Media type: 'movie', 'tv', 'anime', 'music', 'book', 'audiobook', 'comic', 'unknown'
    """
    filename = file_path.name.lower()

    # Check parent folder context for books
    # MP3 files inside books folder are audiobooks
    parent_folders = [p.name.lower() for p in file_path.parents]
    if 'books' in parent_folders or 'audiobooks' in parent_folders:
        music_exts = {'.mp3', '.flac', '.m4a', '.ogg', '.opus'}
        if file_path.suffix.lower() in music_exts:
            return 'audiobook'

    # Check parent folder context for doramas
    # Video files inside doramas folder are doramas
    if 'doramas' in parent_folders:
        video_exts = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v', '.webm'}
        if file_path.suffix.lower() in video_exts:
            return 'dorama'

    # Check parent folder context for animes
    # Video files inside animes folder are animes
    if 'animes' in parent_folders or 'anime' in parent_folders:
        video_exts = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v', '.webm'}
        if file_path.suffix.lower() in video_exts:
            return 'anime'

    # Check parent folder context for TV
    # Video files inside TV/series folder are series (not anime)
    if 'tv' in parent_folders or 'series' in parent_folders or 'séries' in parent_folders:
        video_exts = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v', '.webm'}
        if file_path.suffix.lower() in video_exts:
            return 'tv'

    # Check for season/episode patterns
    episode_patterns = [
        r's\d{1,2}e\d{1,2}',  # S01E01
        r'\d{1,2}x\d{1,2}',   # 1x01
        r'season[\s\._-]*\d+',  # Season 1
        r'episode[\s\._-]*\d+',  # Episode 1
        r'ep[\s\._-]*\d+',      # Ep 01
    ]

    for pattern in episode_patterns:
        if re.search(pattern, filename, re.IGNORECASE):
            # Check if anime by specific patterns (not just brackets)
            # Anime typically has: fansub groups at start like [GroupName], or keywords
            anime_indicators = [
                r'^\[[\w-]+\]',  # Fansub group at start: [GroupName]
                r'\b(anime|episode)\b',  # Keywords anime or episode
            ]
            if any(re.search(ind, filename, re.IGNORECASE) for ind in anime_indicators):
                return 'anime'
            return 'tv'

    # Check for anime-style numbering with fansub groups
    # Pattern: [FansubGroup] Title - 01.mkv or similar
    anime_episode_pattern = r'^\[[\w-]+\].*[-\s]+\d{1,3}(?:\.\w+)?$'
    if re.search(anime_episode_pattern, filename, re.IGNORECASE):
        return 'anime'

    # Check for music extensions
    music_exts = {'.mp3', '.flac', '.wav', '.m4a', '.ogg', '.opus'}
    if file_path.suffix.lower() in music_exts:
        return 'music'

    # Check for book extensions
    book_exts = {'.epub', '.pdf', '.mobi', '.azw', '.azw3'}
    if file_path.suffix.lower() in book_exts:
        return 'book'

    # Check for comic extensions
    comic_exts = {'.cbz', '.cbr', '.cb7', '.cbt'}
    if file_path.suffix.lower() in comic_exts:
        return 'comic'

    # Check for video extensions (likely a movie)
    video_exts = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v', '.webm'}
    if file_path.suffix.lower() in video_exts:
        return 'movie'

    return 'unknown'


def is_spam_file(filename: str) -> bool:
    """
    Check if file is spam/advertisement that should be ignored

    Args:
        filename: Filename to check

    Returns:
        True if file is spam/advertisement
    """
    filename_lower = filename.lower()

    # Common spam/advertisement patterns
    spam_patterns = [
        'comando',  # COMANDOTORRENTS
        'torrent',  # Various torrent site ads
        'www.',  # Website URLs
        'http',  # URLs
        'baixe',  # Download ads in Portuguese
        'acesse',  # Access ads
        'visite',  # Visit ads
        'sample',  # Sample files
        'trailer',  # Trailer files
        'reklama',  # Ads in other languages
        'ad_',  # Ad prefix
        'advertisement',
        'promo',
    ]

    # Check if filename contains spam patterns
    for pattern in spam_patterns:
        if pattern in filename_lower:
            return True

    # Check if filename is only domain/site name (very short)
    if len(filename) < 15 and any(c in filename_lower for c in ['.com', '.net', '.org', '.br']):
        return True

    return False


def parse_movie_name(filename: str) -> MediaInfo:
    """
    Parse movie filename

    Supports formats:
    - Movie Name (2024)
    - Movie.Name.2024.1080p.BluRay.x264-GROUP
    - Movie Name 2024 720p HDTV

    Args:
        filename: Movie filename (without path)

    Returns:
        MediaInfo object
    """
    info = MediaInfo()
    info.media_type = 'movie'

    # Remove extension
    name = Path(filename).stem

    # Remove quality/codec info
    quality_pattern = r'\b(2160p|1080p|720p|480p|4K|UHD|HDR|HDR10|10bit|8bit|SDR|HDRip|WEBRip|CAMRip|DVDScr)\b'
    codec_pattern = r'(x264|x265|h264|h265|H\s?\.?\s?\d{3,4}|HEVC|AVC|XviD|DivX|VP9|AV1)'
    source_pattern = r'\b(BluRay|Blu-Ray|BRRip|WEBRip|WEB-DL|HDTV|DVDRip|BDRip|DSNP|AMZN|NF|HMAX|ATVP|PCOK|PMTP|BHDStudio|MA|CMaRioG)\b'
    audio_pattern = r'(DTS[\s\-]?HD|DTS|AC3|AAC|EAC3|DD\s?5\s?\.?\s?1|DDP\s?5\s?\.?\s?1|DD|DDP|TrueHD|FLAC|Atmos|Dolby|6CH|5\s?\.?\s?1|7\s?\.?\s?1|DualAudio|Dual[\s\-\.]?Áudio|Dublado|DUAL|Dual|dual)'
    hdr_pattern = r'\b(DV|DoVi|Dolby\s?Vision|HDR10\+?|PQ|HLG)\b'
    format_pattern = r'(IMAX|OPEN[\s\.]?MATTE|Enhanced|Extended|Unrated|Directors?[\s\.]?Cut|Theatrical|Remastered|REMASTER|PROPER|REPACK|Sem[\s\.]?Cortes|Vers[aã]o[\s\.]?Estendida|FULL)'

    # Extract quality info before removing
    quality_match = re.search(quality_pattern, name, re.IGNORECASE)
    if quality_match:
        info.quality = quality_match.group(1)

    codec_match = re.search(codec_pattern, name, re.IGNORECASE)
    if codec_match:
        info.codec = codec_match.group(1)

    audio_match = re.search(audio_pattern, name, re.IGNORECASE)
    if audio_match:
        info.audio = audio_match.group(1)

    # Check for 3D
    if re.search(r'\b3D\b', name, re.IGNORECASE):
        info.is_3d = True

    # Extract release group (after dash)
    group_match = re.search(r'-([A-Za-z0-9]+)$', name)
    if group_match:
        info.release_group = group_match.group(1)
        name = name[:group_match.start()]

    # Remove quality/codec markers
    for pattern in [quality_pattern, codec_pattern, source_pattern, audio_pattern, hdr_pattern, format_pattern]:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)

    # Remove common release group patterns/websites
    release_group_patterns = [
        r'WWW\.\w+\.\w+',  # WWW.BLUDV.COM, WWW.BLUDV.TV
        r'www\.\w+\.\w+',  # www.bludv.com
        r'\bCOMANDO\.?TO\b',  # COMANDO.TO
        r'\bCOMANDOTORRENTS\.?COM\b',  # COMANDOTORRENTS.COM
        r'\bWOLVERDONFILMES\.?COM\b',  # WOLVERDONFILMES.COM
        r'\bBRSHARES\.?COM\b',  # BRSHARES.COM
        r'\bBLUDV\b',  # BLUDV standalone
        r'\bLAPUMiA\b',  # LAPUMiA
        r'\bToTTi9\b',  # ToTTi9
        r'\bHon3yHD\b',  # Hon3yHD
        r'\bHONE\b',  # HONE
        r'\bNoUsEr\b',  # NoUsEr
        r'\bSPARKS\b',  # SPARKS
        r'\bSPx\b',  # SPx
        r'\bPRoDJi\b',  # PRoDJi
        r'\bYIFY\b',  # YIFY
        r'\bAlan_\d+\b',  # Alan_680
        r'\bAndreTPF\b',  # AndreTPF
        r'\bJohnL\b',  # JohnL
        r'\b210GJI\b',  # 210GJI
        r'\bBy[\s\-]?LuanHarper\b',  # By-LuanHarper
        r'\bSpeedBR\b',  # SpeedBR
        r'\bBHDStudio\b',  # BHDStudio
        r'\bCMaRioG\b',  # CMaRioG
        r'\bWeasley\b',  # Weasley
    ]
    for pattern in release_group_patterns:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)

    # Remove brackets and their content
    name = re.sub(r'\[.*?\]', '', name)
    name = re.sub(r'\((?!\d{4}\)).*?\)', '', name)  # Keep (year) only

    # Extract year FIRST to avoid conflicts
    year_match = re.search(r'[\(\[]?(\d{4})[\)\]]?', name)
    if year_match:
        year = int(year_match.group(1))
        current_year = datetime.now().year
        if 1900 <= year <= current_year + 1:
            info.year = year
            # Remove year and everything after it
            name = name[:year_match.start()].strip()

    # Clean up title
    # Replace dots, dashes, underscores with spaces
    name = re.sub(r'[\.\-_]+', ' ', name)

    # Remove common actor/director name patterns
    # Remove everything after comma (actors often listed after comma)
    if ',' in name:
        name = name.split(',')[0].strip()

    # Remove "hallowed" and similar nonsense words FIRST
    name = re.sub(r'\s+(hallowed|weasley|hone)\s*$',
                  '', name, flags=re.IGNORECASE)

    # Remove orphaned single letters/numbers at the end
    # (P, P2, P2 0, etc - but preserve "N1" for "Jogador N1", "Vol 3", "Part 2", etc)
    # First remove patterns like "P2 0", "P 0" (letter + digit + space + digit)
    name = re.sub(r'\s+[A-Z]\d*\s+\d+\s*$', '', name, flags=re.IGNORECASE)
    # Then remove MOST single letters at end - cover all except N
    name = re.sub(r'\s+[A-MOP-Z](?!\d)\s*$', '', name,
                  flags=re.IGNORECASE)  # Single letter (not N)
    name = re.sub(r'\s+[A-MOP-Z]\d+\s*$', '', name,
                  flags=re.IGNORECASE)  # Letter + digit

    # Multiple spaces to single
    name = re.sub(r'\s+', ' ', name)
    name = name.strip()

    info.title = name

    return info


def parse_tv_episode(filename: str) -> MediaInfo:
    """
    Parse TV show episode filename

    Supports formats:
    - Show.Name.S01E01.Episode.Title.1080p
    - Show Name 1x01 Episode Title
    - Show Name - 01 - Episode Title
    - Show.Name.Season.1.Episode.01

    Args:
        filename: Episode filename (without path)

    Returns:
        MediaInfo object
    """
    info = MediaInfo()
    info.media_type = 'tv'

    # Remove extension
    name = Path(filename).stem

    # Pattern 1: S01E01 format
    se_match = re.search(r'[Ss](\d{1,2})[Ee](\d{1,2})', name)
    if se_match:
        info.season = int(se_match.group(1))
        info.episode = int(se_match.group(2))
        # Extract title before season marker
        info.title = name[:se_match.start()].strip()
        # Extract episode title after
        remaining = name[se_match.end():].strip()
        if remaining:
            # Remove quality markers
            remaining = re.sub(
                r'\b(1080p|720p|480p|WEB|BluRay|x264|x265).*$', '', remaining, flags=re.IGNORECASE)
            info.episode_title = remaining.strip()

    # Pattern 2: 1x01 format
    elif (x_match := re.search(r'(\d{1,2})x(\d{1,2})', name, re.IGNORECASE)):
        info.season = int(x_match.group(1))
        info.episode = int(x_match.group(2))
        info.title = name[:x_match.start()].strip()
        remaining = name[x_match.end():].strip()
        if remaining:
            remaining = re.sub(
                r'\b(1080p|720p|480p|WEB|BluRay|x264|x265).*$', '', remaining, flags=re.IGNORECASE)
            info.episode_title = remaining.strip()

    # Pattern 3: Season X Episode Y format
    elif (season_match := re.search(r'[Ss]eason[\s\._-]*(\d+).*?[Ee]pisode[\s\._-]*(\d+)', name, re.IGNORECASE)):
        info.season = int(season_match.group(1))
        info.episode = int(season_match.group(2))
        info.title = name[:season_match.start()].strip()

    # Pattern 4: EP## format (Episode without season)
    elif (ep_match := re.search(r'\b[Ee][Pp][\s\._-]*(\d{1,3})\b', name)):
        info.season = 1  # Default to season 1 when no season specified
        info.episode = int(ep_match.group(1))
        info.title = name[:ep_match.start()].strip()

    # Pattern 5: - 01 - format (anime style)
    elif (dash_match := re.search(r'[\s\-]+(\d{1,3})[\s\-]+', name)):
        # Try to detect if there's a season marker before
        season_before = re.search(
            r'[Ss](\d+)[\s\-]*$', name[:dash_match.start()])
        if season_before:
            info.season = int(season_before.group(1))
            info.title = name[:season_before.start()].strip()
        else:
            info.season = 1  # Default to season 1
            info.title = name[:dash_match.start()].strip()

        info.episode = int(dash_match.group(1))
        remaining = name[dash_match.end():].strip()
        if remaining:
            remaining = re.sub(r'\b(1080p|720p|480p).*$', '',
                               remaining, flags=re.IGNORECASE)
            info.episode_title = remaining.strip()

    # Pattern 6: Just episode number with E prefix at end
    elif (e_match := re.search(r'[Ee][\s\._-]*(\d{1,3})(?:\s|$)', name)):
        info.season = 1
        info.episode = int(e_match.group(1))
        info.title = name[:e_match.start()].strip()

    # Clean up title
    if info.title:
        info.title = re.sub(r'[\.\-_]+', ' ', info.title)
        info.title = re.sub(r'\s+', ' ', info.title)
        info.title = info.title.strip()

    # Clean up episode title
    if info.episode_title:
        info.episode_title = re.sub(r'[\.\-_]+', ' ', info.episode_title)
        info.episode_title = re.sub(r'\s+', ' ', info.episode_title)
        info.episode_title = info.episode_title.strip()

    return info


def parse_anime_name(filename: str) -> MediaInfo:
    """
    Parse anime filename

    Supports formats:
    - [Group] Anime Name - 01 [1080p]
    - Anime Name S01E01
    - Anime.Name.Episode.01

    Args:
        filename: Anime filename (without path)

    Returns:
        MediaInfo object
    """
    info = parse_tv_episode(filename)
    info.media_type = 'anime'

    # Extract release group from brackets
    group_match = re.search(r'^\[([^\]]+)\]', filename)
    if group_match:
        info.release_group = group_match.group(1)

    return info


def normalize_artist_name(artist: str) -> tuple[str, list[str]]:
    """
    Normalize artist name by extracting featuring artists.
    Returns (main_artist, featured_artists)

    Examples:
        "Drake feat. Rihanna" -> ("Drake", ["Rihanna"])
        "Artist ft The Weeknd" -> ("Artist", ["The Weeknd"])
        "Lady Gaga Featuring Bradley Cooper" -> ("Lady Gaga", ["Bradley Cooper"])
    """
    if not artist:
        return (artist, [])

    # Patterns for featuring variations (case-insensitive)
    feat_patterns = [
        r'\s+feat\.?\s+',
        r'\s+ft\.?\s+',
        r'\s+featuring\s+',
        r'\s+ft\s+',
        r'\s+feat\s+',
        r'\s+with\s+',
        r'\s*\(feat\.?\s+',
        r'\s*\(ft\.?\s+',
        r'\s*\(featuring\s+',
    ]

    featured_artists = []
    main_artist = artist

    for pattern in feat_patterns:
        match = re.search(pattern, artist, re.IGNORECASE)
        if match:
            # Split into main and featured
            main_artist = artist[:match.start()].strip()
            featured_part = artist[match.end():].strip()

            # Remove trailing parenthesis if present
            featured_part = re.sub(r'\)$', '', featured_part).strip()

            # Split multiple featured artists by comma or &
            featured_list = re.split(
                r'[,&]|\s+and\s+', featured_part, flags=re.IGNORECASE)
            featured_artists = [f.strip() for f in featured_list if f.strip()]
            break

    return (main_artist, featured_artists)


def detect_various_artists(artist: str, album: str) -> bool:
    """
    Detect if this is a Various Artists compilation.
    """
    various_keywords = ['various', 'varios', 'compilation',
                        'coletanea', 'soundtrack', 'trilha sonora']

    artist_lower = artist.lower() if artist else ''
    album_lower = album.lower() if album else ''

    for keyword in various_keywords:
        if keyword in artist_lower or keyword in album_lower:
            return True

    return False


def parse_music_file(file_path: Path) -> Dict[str, str]:
    """
    Parse music filename

    Supports formats:
    - 01 - Track Name.mp3
    - Artist - Track Name.mp3
    - Track Name.mp3

    Args:
        file_path: Music file path

    Returns:
        Dictionary with artist, album, track info
    """
    filename = file_path.stem

    # Try to extract track number
    track_match = re.match(r'^(\d{1,3})[\s\-\.]+(.+)$', filename)

    info = {
        'filename': filename,
        'track_number': None,
        'artist': None,
        'album': None,
        'track_name': filename
    }

    if track_match:
        info['track_number'] = int(track_match.group(1))
        info['track_name'] = track_match.group(2).strip()

    # Try to extract artist from "Artist - Track" format
    if ' - ' in info['track_name']:
        parts = info['track_name'].split(' - ', 1)
        info['artist'] = parts[0].strip()
        info['track_name'] = parts[1].strip()

    # Get album from directory structure if it looks like an album folder
    # (not a generic "downloads" or "musics" folder)
    parent_name = file_path.parent.name.lower()
    if parent_name and parent_name not in ['musics', 'music', 'downloads', 'download']:
        info['album'] = file_path.parent.name

        # Get artist from grandparent if album is in parent
        grandparent_name = file_path.parent.parent.name.lower()
        if grandparent_name and grandparent_name not in ['musics', 'music', 'downloads', 'download']:
            # Only use grandparent as artist if we don't have one yet from filename
            if not info['artist']:
                info['artist'] = file_path.parent.parent.name

    return info


def detect_language(text: str) -> str:
    """
    Detect language from text (simple heuristic-based detection).
    Returns ISO 639-1 language code: 'pt', 'en', 'es', etc.
    """
    if not text:
        return 'en'

    text_lower = text.lower()

    # Portuguese indicators (strong signals)
    pt_chars = ['ã', 'õ', 'ç', 'á', 'é', 'ê', 'í', 'ó', 'ô', 'ú']
    pt_words = ['ção', 'ões', 'ência', 'ário']
    pt_common = [' e a ', ' e o ', ' que ', ' com a ',
                 ' para o ', ' pela ', ' pelo ', ' dos ', ' das ', ' aos ']

    # Spanish indicators
    es_chars = ['ñ']
    es_words = ['ción', 'español', 'año']

    # English indicators
    en_common = [' the ', ' and ', ' with ', ' from ', ' who ']

    # Count indicators
    # Strong signal
    pt_score = sum(3 for char in pt_chars if char in text_lower)
    pt_score += sum(2 for word in pt_words if word in text_lower)
    pt_score += sum(1 for word in pt_common if word in text_lower)

    es_score = sum(3 for char in es_chars if char in text_lower)
    es_score += sum(2 for word in es_words if word in text_lower)

    en_score = sum(1 for word in en_common if word in text_lower)

    # Decide based on scores
    if pt_score > es_score and pt_score > en_score:
        return 'pt'
    elif es_score > pt_score and es_score > en_score:
        return 'es'

    return 'en'  # Default to English


def parse_book_filename(filename: str) -> Dict[str, str]:
    """
    Parse book filename

    Supports formats:
    - Author Name - Book Title (Year).epub
    - Book Title - Author Name.pdf
    - Title (Author).ext
    - Book Title (Year).mobi

    Args:
        filename: Book filename

    Returns:
        Dictionary with author, title, year, language info
    """
    name = Path(filename).stem

    info = {
        'author': None,
        'title': None,
        'year': None,
        'series': None,
        'series_number': None,
        'language': None
    }

    # Extract year
    year_match = re.search(r'\((\d{4})\)', name)
    if year_match:
        info['year'] = int(year_match.group(1))
        name = name[:year_match.start()] + name[year_match.end():]

    # Remove leading numbers and separators (e.g., "01 - Title" → "Title")
    # Common in ebook collections/series
    leading_num = re.match(r'^(\d+\.?\d*)\s*[-–—]\s*', name)
    if leading_num:
        # Store as series number if not already found
        if not info['series_number']:
            try:
                info['series_number'] = int(float(leading_num.group(1)))
            except:
                pass
        name = name[leading_num.end():].strip()

    # For comics: Remove leading issue number (e.g., "#03 " or "03 ")
    comic_leading_num = re.match(r'^[#]?(\d+)\s+', name)
    if comic_leading_num and not info['series_number']:
        info['series_number'] = int(comic_leading_num.group(1))
        name = name[comic_leading_num.end():].strip()

    # For comics: Remove trailing "XX de YY" pattern
    # Example: "Marvel - Guerra Civil I  03 de 07" → "Marvel - Guerra Civil I"
    issue_pattern = re.search(r'\s+\d{2}\s+de\s+\d{2}', name)
    if issue_pattern:
        name = name[:issue_pattern.start()].strip()

    # Extract series info from middle (Book Title #1, Book Title Vol 1)
    if not info['series_number']:
        series_match = re.search(
            r'[#](\d+)|Vol\.?\s*(\d+)', name, re.IGNORECASE)
        if series_match:
            info['series_number'] = int(
                series_match.group(1) or series_match.group(2))
            name = name[:series_match.start()].strip()

    # Extract author from parentheses: "Title (Author1, Author2)"
    author_in_parens = re.search(r'\(([^)]+)\)$', name)
    if author_in_parens:
        potential_author = author_in_parens.group(1).strip()
        # Check if it looks like author names (not a year or number)
        if not re.match(r'^\d+$', potential_author):
            info['author'] = potential_author
            info['title'] = name[:author_in_parens.start()].strip()
            return info

    # Try "Author - Title" or "Title - Author" format
    if ' - ' in name:
        parts = name.split(' - ')

        # If there are multiple " - " separators, the last part is often the author
        # Example: "Title - Subtitle - Author Name"
        if len(parts) > 2:
            # Last part is likely the author
            potential_author = parts[-1].strip()
            potential_title = ' - '.join(parts[:-1]).strip()

            # Check if last part looks like a person's name
            author_words = potential_author.split()
            looks_like_person = (
                len(author_words) >= 2 and
                len(author_words) <= 4 and
                all(word[0].isupper()
                    for word in author_words if word and len(word) > 1)
            )

            if looks_like_person:
                info['author'] = potential_author
                info['title'] = potential_title
                return info

        # Standard "Author - Title" or "Title - Author" with single separator
        left = parts[0].strip()
        right = parts[1].strip() if len(
            parts) == 2 else ' - '.join(parts[1:]).strip()

        # Heuristic: if left part looks like author name (2-3 words, capitalized)
        # and right part is longer, assume "Author - Title"
        # Otherwise, assume "Title - Author"
        left_words = left.split()
        right_words = right.split()

        # Check if left side looks like a person's name (2-3 capitalized words)
        looks_like_author = (
            len(left_words) <= 3 and
            all(word[0].isupper() for word in left_words if word) and
            not any(char.isdigit() for char in left)
        )

        if looks_like_author and len(right_words) > len(left_words):
            # "Author - Title" format
            info['author'] = left
            info['title'] = right
        else:
            # "Title - Author" format or ambiguous
            # Default to "Author - Title" unless right side clearly looks like author
            right_looks_like_author = (
                len(right_words) >= 2 and
                len(right_words) <= 3 and
                all(word[0].isupper() for word in right_words if word)
            )

            if right_looks_like_author and len(left_words) > len(right_words):
                # "Title - Author" format
                info['title'] = left
                info['author'] = right
            else:
                # Default: "Author - Title"
                info['author'] = left
                info['title'] = right
    else:
        # Just title
        info['title'] = name.strip()

    # Detect language from title and author
    text_to_analyze = f"{info.get('title', '')} {info.get('author', '')}"
    info['language'] = detect_language(text_to_analyze)

    return info


def extract_year_from_string(text: str) -> Optional[int]:
    """
    Extract year from string

    Args:
        text: String potentially containing year

    Returns:
        Year as integer or None
    """
    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', text)
    if year_match:
        year = int(year_match.group(1))
        current_year = datetime.now().year
        if 1900 <= year <= current_year + 1:
            return year
    return None


def clean_title(title: str) -> str:
    """
    Clean and normalize title string

    Args:
        title: Raw title string

    Returns:
        Cleaned title
    """
    # Replace separators with spaces
    title = re.sub(r'[\.\-_]+', ' ', title)

    # Remove brackets and their content (except year)
    title = re.sub(r'\[.*?\]', '', title)

    # Remove multiple spaces
    title = re.sub(r'\s+', ' ', title)

    # Capitalize properly
    title = title.strip()

    return title
