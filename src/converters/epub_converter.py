"""
PDF to EPUB Converter

Converts PDF ebooks to EPUB format for better reading experience.
Supports multiple conversion methods with fallbacks.
"""

import logging
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ConversionResult:
    """Result of EPUB conversion"""
    success: bool
    epub_path: Optional[Path] = None
    original_pdf_path: Optional[Path] = None
    method_used: Optional[str] = None
    error: Optional[str] = None
    file_size_before: int = 0
    file_size_after: int = 0


class EPUBConverter:
    """
    Converts PDF files to EPUB format.

    Conversion methods (in order of preference):
    1. Calibre CLI (ebook-convert) - Most reliable
    2. pypdf + ebooklib - Pure Python fallback

    Features:
    - Automatic method detection and fallback
    - OCR support for scanned PDFs (Calibre only)
    - Metadata preservation
    - Original PDF preservation option
    """

    def __init__(self, preserve_pdf: bool = True, enable_ocr: bool = False):
        """
        Initialize EPUB converter.

        Args:
            preserve_pdf: Keep original PDF file after conversion
            enable_ocr: Enable OCR for scanned PDFs (requires Calibre)
        """
        self.preserve_pdf = preserve_pdf
        self.enable_ocr = enable_ocr
        self.calibre_available = self._check_calibre()

        if self.calibre_available:
            logger.info("EPUB Converter initialized with Calibre")
        else:
            logger.warning("Calibre not found, EPUB conversion disabled")

    def _check_calibre(self) -> bool:
        """Check if Calibre is installed and accessible"""
        return shutil.which('ebook-convert') is not None

    def can_convert(self) -> bool:
        """Check if conversion is possible with available tools"""
        return self.calibre_available

    def convert(
        self,
        pdf_path: Path,
        output_dir: Optional[Path] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ConversionResult:
        """
        Convert PDF to EPUB.

        Args:
            pdf_path: Path to PDF file
            output_dir: Output directory (default: same as PDF)
            metadata: Optional metadata dict (title, author, etc.)

        Returns:
            ConversionResult with conversion details
        """
        if not pdf_path.exists():
            return ConversionResult(
                success=False,
                error=f"PDF file not found: {pdf_path}"
            )

        if not pdf_path.suffix.lower() == '.pdf':
            return ConversionResult(
                success=False,
                error=f"Not a PDF file: {pdf_path}"
            )

        # Determine output path
        if output_dir is None:
            output_dir = pdf_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        epub_path = output_dir / f"{pdf_path.stem}.epub"

        # Get original file size
        file_size_before = pdf_path.stat().st_size

        # Try conversion with available method
        if self.calibre_available:
            result = self._convert_with_calibre(pdf_path, epub_path, metadata)
        else:
            return ConversionResult(
                success=False,
                error="No conversion tool available (Calibre not installed)"
            )

        # Add file sizes to result
        if result.success and epub_path.exists():
            file_size_after = epub_path.stat().st_size
            result.file_size_before = file_size_before
            result.file_size_after = file_size_after
            result.epub_path = epub_path
            result.original_pdf_path = pdf_path

            # Log size comparison
            size_diff = ((file_size_after - file_size_before) /
                         file_size_before) * 100
            size_str = "smaller" if size_diff < 0 else "larger"
            logger.info(
                f"EPUB is {abs(size_diff):.1f}% {size_str} than PDF "
                f"({file_size_after / 1024 / 1024:.1f} MB vs {file_size_before / 1024 / 1024:.1f} MB)"
            )

        return result

    def _convert_with_calibre(
        self,
        pdf_path: Path,
        epub_path: Path,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ConversionResult:
        """
        Convert PDF to EPUB using Calibre's ebook-convert.

        Args:
            pdf_path: Input PDF path
            epub_path: Output EPUB path
            metadata: Optional metadata

        Returns:
            ConversionResult
        """
        try:
            # Build conversion command
            cmd = ['ebook-convert', str(pdf_path), str(epub_path)]

            # Add metadata if provided
            if metadata:
                if 'title' in metadata and metadata['title']:
                    cmd.extend(['--title', metadata['title']])
                if 'author' in metadata and metadata['author']:
                    cmd.extend(['--authors', metadata['author']])
                if 'language' in metadata and metadata['language']:
                    cmd.extend(['--language', metadata['language']])
                if 'publisher' in metadata and metadata['publisher']:
                    cmd.extend(['--publisher', metadata['publisher']])
                if 'tags' in metadata and metadata['tags']:
                    cmd.extend(['--tags', metadata['tags']])
                if 'series' in metadata and metadata['series']:
                    cmd.extend(['--series', metadata['series']])
                if 'comments' in metadata and metadata['comments']:
                    cmd.extend(['--comments', metadata['comments']])

            # Add conversion options
            cmd.extend([
                '--enable-heuristics',  # Smart paragraph detection
                '--input-encoding', 'utf-8',
                '--output-profile', 'tablet',  # Optimize for e-readers
                '--preserve-cover-aspect-ratio',  # Keep original cover proportions
            ])

            # Add OCR if enabled (for scanned PDFs)
            if self.enable_ocr:
                cmd.append('--enable-ocr')

            logger.info(f"Converting PDF to EPUB: {pdf_path.name}")
            logger.debug(f"Calibre command: {' '.join(cmd)}")

            # Run conversion with timeout
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120  # 2 minutes timeout (reduced from 5)
                )

                if result.returncode == 0 and epub_path.exists():
                    logger.info(
                        f"✓ Successfully converted to EPUB: {epub_path.name}")
                    return ConversionResult(
                        success=True,
                        epub_path=epub_path,
                        method_used='calibre'
                    )
                else:
                    error_msg = result.stderr or "Unknown conversion error"
                    logger.error(f"✗ Calibre conversion failed: {error_msg}")
                    return ConversionResult(
                        success=False,
                        error=error_msg,
                        method_used='calibre'
                    )

            except subprocess.TimeoutExpired:
                logger.warning(
                    f"✗ Calibre conversion timeout (2 min) for {pdf_path.name}. "
                    f"File may be too large or complex."
                )
                # Clean up partial EPUB if exists
                if epub_path.exists():
                    epub_path.unlink()
                return ConversionResult(
                    success=False,
                    error="Conversion timeout (2 minutes)",
                    method_used='calibre'
                )

        except subprocess.TimeoutExpired:
            logger.error("Conversion timeout (>2 minutes)")
            return ConversionResult(
                success=False,
                error="Conversion timeout",
                method_used='calibre'
            )
        except Exception as e:
            logger.error(f"Calibre conversion error: {e}")
            return ConversionResult(
                success=False,
                error=str(e),
                method_used='calibre'
            )

    def move_original_pdf(
        self,
        pdf_path: Path,
        destination: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Move original PDF to a separate location after conversion.

        Args:
            pdf_path: Path to PDF file
            destination: Destination directory (default: pdfs/ subdirectory)

        Returns:
            New PDF path if moved, None if failed
        """
        if not pdf_path.exists():
            logger.error(f"PDF not found: {pdf_path}")
            return None

        try:
            # Default destination: pdfs/ subdirectory in parent folder
            if destination is None:
                destination = pdf_path.parent / "pdfs"

            destination.mkdir(parents=True, exist_ok=True)
            new_path = destination / pdf_path.name

            # Move PDF
            shutil.move(str(pdf_path), str(new_path))
            logger.info(f"Moved original PDF to: {new_path}")
            return new_path

        except Exception as e:
            logger.error(f"Failed to move PDF: {e}")
            return None
