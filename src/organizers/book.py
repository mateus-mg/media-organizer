"""
Book organizer (books, audiobooks, comics)
Organizes books into Author/Title structure
"""

from pathlib import Path
from typing import Dict, Optional
import logging
from .base import BaseOrganizer, OrganizationResult
from ..metadata.parsers import parse_book_filename

logger = logging.getLogger(__name__)


class BookOrganizer(BaseOrganizer):
    """Organizes book files"""

    def __init__(self, *args, book_type: str = 'book', **kwargs):
        """
        Initialize book organizer

        Args:
            book_type: Type of book (book, audiobook, comic)
        """
        super().__init__(*args, **kwargs)
        self.book_type = book_type

        # Set library path based on book type
        if book_type == 'audiobook':
            self.library_path = self.config.library_path_audiobooks
        elif book_type == 'comic':
            self.library_path = self.config.library_path_comics
        else:
            self.library_path = self.config.library_path_books

    async def organize(self, file_path: Path) -> OrganizationResult:
        """Organize a book file"""
        # Parse filename
        book_info = parse_book_filename(file_path.name)

        # Detect book type from extension
        book_type = self.book_type  # Default from constructor
        if file_path.suffix.lower() in {'.cbz', '.cbr', '.cb7', '.cbt'}:
            book_type = 'comic'
            # Update library path for comics
            self.library_path = self.config.library_path_comics
        elif file_path.suffix.lower() in {'.mp3', '.m4a', '.ogg'}:
            book_type = 'audiobook'
            # Update library path for audiobooks
            self.library_path = self.config.library_path_audiobooks
        else:
            # Check if this PDF/EPUB is in an audiobook folder
            # (folder contains MP3 files = it's audiobook material)
            parent_folder = file_path.parent
            has_mp3 = any(parent_folder.glob('*.mp3'))
            has_m4a = any(parent_folder.glob('*.m4a'))

            if has_mp3 or has_m4a:
                book_type = 'audiobook'
                # Update library path for audiobooks
                self.library_path = self.config.library_path_audiobooks
            else:
                # PDF, EPUB, MOBI, etc - regular book
                book_type = 'book'
                # Update library path for books
                self.library_path = self.config.library_path_books

        # Build metadata
        # For audiobooks in folders, ALWAYS use folder name to keep all files together
        if book_type == 'audiobook':
            # Get parent folder name (audiobook title)
            folder_name = file_path.parent.name
            # Try to extract author and title from folder name
            if ' - ' in folder_name:
                parts = folder_name.split(' - ', 1)
                book_info['title'] = parts[0].strip()
                book_info['author'] = parts[1].strip() if len(
                    parts) > 1 else None
            else:
                # No separator, use whole folder name as title
                book_info['title'] = folder_name
                # Keep author from file metadata if available
                if not book_info.get('author'):
                    book_info['author'] = None

        metadata = {
            'media_type': 'book',
            'media_subtype': book_type,
            'author': book_info.get('author') or 'Unknown Author',
            'title': book_info.get('title') or file_path.stem,
            'year': book_info.get('year'),
            'series': book_info.get('series'),
            'series_number': book_info.get('series_number'),
            'language': book_info.get('language', 'en')
        }

        # Get destination path
        dest_path = self.get_destination_path(file_path, metadata)

        # Organize file
        result = await self.organize_file(file_path, dest_path, metadata)

        # Update EPUB metadata after organization (if it's an EPUB)
        if result and result.organized_path and Path(result.organized_path).suffix.lower() == '.epub':
            self._update_epub_metadata(Path(result.organized_path), metadata)

        # Generate ComicInfo.xml for comics
        if result and result.organized_path and book_type == 'comic':
            self._generate_comic_info(Path(result.organized_path), metadata)

        return result

    def get_destination_path(self, file_path: Path, metadata: Dict) -> Path:
        """
        Get destination path for book
        Format depends on book type:
        - books: books/books/Author/Title (Year)/Title.epub
        - audiobooks: books/audiobooks/Author or Title/Book.mp3
        - comics: books/comics/Series Name (Year)/Series #001.cbz
        """
        book_type = metadata['media_subtype']

        if book_type == 'audiobook':
            # Audiobooks: library/audiobooks/Title/files
            # Use title as folder name (all files from same audiobook together)
            # Keep original filename to preserve chapter/part numbering
            identifier = self.sanitize_title(metadata['title'])
            file_name = file_path.name  # Keep original filename with chapter numbers
            return self.library_path / identifier / file_name

        elif book_type == 'comic':
            # Comics: library/comics/Series (Year)/Series #001.cbz
            title = self.sanitize_title(metadata['title'])
            year = metadata.get('year')

            if year:
                series_folder = f"{title} ({year})"
            else:
                series_folder = title

            # Use series number if available
            if metadata.get('series_number'):
                file_name = f"{title} #{metadata['series_number']:03d}{file_path.suffix}"
            else:
                file_name = f"{title}{file_path.suffix}"

            return self.library_path / series_folder / file_name

        else:
            # Regular books: library/books/Author/Title (Year)/Title.epub
            author = self.sanitize_title(metadata['author'])
            title = self.sanitize_title(metadata['title'])
            year = metadata.get('year')

            if year:
                title_folder = f"{title} ({year})"
            else:
                title_folder = title

            file_name = f"{title}{file_path.suffix}"

            return self.library_path / author / title_folder / file_name

    def _update_epub_metadata(self, epub_path: Path, metadata: Dict) -> bool:
        """
        Update EPUB metadata using epub_meta or similar.
        This ensures media servers can read proper metadata from EPUB files.
        """
        try:
            import zipfile
            import xml.etree.ElementTree as ET
            from datetime import datetime

            # Note: Full EPUB metadata update requires specialized library
            # For now, log that we would update it
            # TODO: Implement with ebooklib or similar when available

            logger.info(
                f"EPUB metadata update (TODO): {epub_path.name} - "
                f"Author: {metadata['author']}, Title: {metadata['title']}, "
                f"Language: {metadata['language']}"
            )

            # Basic metadata that should be set:
            # - dc:title
            # - dc:creator (author)
            # - dc:language
            # - dc:date (year)
            # - dc:identifier (ISBN if available)

            return True

        except Exception as e:
            logger.warning(
                f"Failed to update EPUB metadata for {epub_path.name}: {e}")
            return False

    def _generate_comic_info(self, comic_path: Path, metadata: Dict) -> bool:
        """
        Generate ComicInfo.xml for comic files.
        This file contains metadata that comic readers can read.
        """
        try:
            import zipfile
            import xml.etree.ElementTree as ET
            from io import BytesIO

            # Create ComicInfo.xml content
            root = ET.Element('ComicInfo')

            # Add metadata fields
            if metadata.get('title'):
                ET.SubElement(root, 'Title').text = metadata['title']

            if metadata.get('series'):
                ET.SubElement(root, 'Series').text = metadata['series']

            if metadata.get('series_number'):
                ET.SubElement(root, 'Number').text = str(
                    metadata['series_number'])

            if metadata.get('year'):
                ET.SubElement(root, 'Year').text = str(metadata['year'])

            if metadata.get('author'):
                ET.SubElement(root, 'Writer').text = metadata['author']

            # Language
            lang = metadata.get('language', 'en')
            ET.SubElement(root, 'LanguageISO').text = lang

            # Generate XML string
            tree = ET.ElementTree(root)
            xml_buffer = BytesIO()
            tree.write(xml_buffer, encoding='utf-8', xml_declaration=True)
            xml_content = xml_buffer.getvalue()

            # Add ComicInfo.xml to CBZ file
            if comic_path.suffix.lower() == '.cbz':
                with zipfile.ZipFile(comic_path, 'a') as zf:
                    # Check if ComicInfo.xml already exists
                    if 'ComicInfo.xml' not in zf.namelist():
                        zf.writestr('ComicInfo.xml', xml_content)
                        logger.info(
                            f"Added ComicInfo.xml to: {comic_path.name}")
                    else:
                        logger.debug(
                            f"ComicInfo.xml already exists in: {comic_path.name}")

                return True
            else:
                logger.warning(
                    f"Cannot add ComicInfo.xml to non-CBZ file: {comic_path.name}")
                return False

        except Exception as e:
            logger.warning(
                f"Failed to generate ComicInfo.xml for {comic_path.name}: {e}")
            return False
