"""
Basic test suite for the refactored media organization system
"""
import unittest
import tempfile
import os
from pathlib import Path
import asyncio

from src.core.types import MediaType, OrganizationResult
from src.core.validator import FileExistenceValidator, FileTypeValidator
from src.detection.classifier import MediaClassifier
from src.organizers.base import BaseOrganizer


class TestMediaClassifier(unittest.TestCase):
    """Test the media classifier functionality"""
    
    def setUp(self):
        self.classifier = MediaClassifier()
    
    def test_classify_movie_file(self):
        """Test classification of movie files"""
        with tempfile.NamedTemporaryFile(suffix='.mkv', delete=False) as tmp:
            result = self.classifier.classificar_tipo_midia(Path(tmp.name))
            self.assertEqual(result, MediaType.MOVIE)
            os.unlink(tmp.name)
    
    def test_classify_music_file(self):
        """Test classification of music files"""
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            result = self.classifier.classificar_tipo_midia(Path(tmp.name))
            self.assertEqual(result, MediaType.MUSIC)
            os.unlink(tmp.name)
    
    def test_classify_book_file(self):
        """Test classification of book files"""
        with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as tmp:
            result = self.classifier.classificar_tipo_midia(Path(tmp.name))
            self.assertEqual(result, MediaType.BOOK)
            os.unlink(tmp.name)


class TestFileValidators(unittest.TestCase):
    """Test the file validation functionality"""
    
    def setUp(self):
        self.existence_validator = FileExistenceValidator()
        self.type_validator = FileTypeValidator(['.mp4', '.mkv', '.mp3', '.epub'])
    
    def test_file_existence_validation(self):
        """Test file existence validation"""
        # Test with non-existent file
        result = asyncio.run(self.existence_validator.validate(Path('/nonexistent/file.txt')))
        self.assertFalse(result.is_valid)
        
        # Test with existing file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            result = asyncio.run(self.existence_validator.validate(Path(tmp.name)))
            self.assertTrue(result.is_valid)
            os.unlink(tmp.name)
    
    def test_file_type_validation(self):
        """Test file type validation"""
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
            result = asyncio.run(self.type_validator.validate(Path(tmp.name)))
            self.assertTrue(result.is_valid)
            os.unlink(tmp.name)
        
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
            result = asyncio.run(self.type_validator.validate(Path(tmp.name)))
            self.assertFalse(result.is_valid)
            os.unlink(tmp.name)


class TestBaseOrganizer(unittest.TestCase):
    """Test the base organizer functionality"""
    
    def test_sanitize_title(self):
        """Test title sanitization"""
        organizer = BaseOrganizer(None, None, None, None)
        
        # Test basic sanitization
        result = organizer.sanitize_title("Test Title: With Special Characters?")
        self.assertEqual(result, "Test Title With Special Characters")
        
        # Test long title truncation
        long_title = "A" * 150
        result = organizer.sanitize_title(long_title)
        self.assertLess(len(result), len(long_title))
        self.assertTrue(result.endswith("..."))
    
    def test_sanitize_author(self):
        """Test author sanitization"""
        organizer = BaseOrganizer(None, None, None, None)
        
        result = organizer.sanitize_author("John Doe")
        self.assertEqual(result, "John Doe")
        
        result = organizer.sanitize_author("")
        self.assertEqual(result, "Unknown Author")


class TestOrganizationResult(unittest.TestCase):
    """Test the OrganizationResult dataclass"""
    
    def test_organization_result_creation(self):
        """Test creating an organization result"""
        result = OrganizationResult(
            success=True,
            organized_path=Path("/test/path/file.mp4")
        )
        
        self.assertTrue(result.success)
        self.assertIsNotNone(result.organized_path)
        self.assertFalse(result.skipped)


if __name__ == '__main__':
    unittest.main()