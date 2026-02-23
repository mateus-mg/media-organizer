"""
Integration tests for the media organization orchestrator
"""
import unittest
import tempfile
import os
from pathlib import Path
import asyncio

from src.core.main_orchestrator import MediaOrganizerOrchestrator
from src.config.settings import Config


class TestOrchestratorIntegration(unittest.TestCase):
    """Test the orchestrator integration"""
    
    def setUp(self):
        # Create a temporary directory for testing
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = Config()
        
        # Override some config paths to use temp directory
        self.config.library_path_movies = self.temp_dir / "movies"
        self.config.download_path_movies = self.temp_dir / "downloads" / "movies"
        
        # Create necessary directories
        self.config.library_path_movies.mkdir(parents=True, exist_ok=True)
        self.config.download_path_movies.mkdir(parents=True, exist_ok=True)
    
    def tearDown(self):
        # Clean up temporary directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_orchestrator_initialization(self):
        """Test that orchestrator initializes correctly"""
        orchestrator = MediaOrganizerOrchestrator(self.config, dry_run=True)
        
        # Check that orchestrator has all required components
        self.assertIsNotNone(orchestrator.config)
        self.assertIsNotNone(orchestrator.validators)
        self.assertIsNotNone(orchestrator.organizadores)
        self.assertIsNotNone(orchestrator.classifier)
        self.assertIsNotNone(orchestrator.scanner)
        self.assertIsNotNone(orchestrator.database)
        
        # Check that dry run mode is respected
        self.assertTrue(orchestrator.dry_run)
    
    def test_create_validators(self):
        """Test that validators are created properly"""
        orchestrator = MediaOrganizerOrchestrator(self.config, dry_run=True)
        
        # Check that validators are created
        self.assertGreater(len(orchestrator.validators), 0)
        
        # Check specific validators exist
        from src.core.validator import (
            FileExistenceValidator, FileTypeValidator, 
            IncompleteFileValidator, JunkFileValidator, AmazonFormatValidator
        )
        
        validator_types = [type(v).__name__ for v in orchestrator.validators]
        expected_validators = [
            'FileExistenceValidator',
            'FileTypeValidator', 
            'IncompleteFileValidator',
            'JunkFileValidator',
            'AmazonFormatValidator'
        ]
        
        for expected in expected_validators:
            self.assertIn(expected, validator_types)
    
    def test_create_organizers(self):
        """Test that organizers are created properly"""
        orchestrator = MediaOrganizerOrchestrator(self.config, dry_run=True)
        
        # Check that organizers are created
        self.assertGreater(len(orchestrator.organizadores), 0)
        
        # Check specific organizers exist
        from src.core.types import MediaType
        
        expected_media_types = [
            MediaType.MOVIE,
            MediaType.TV_SHOW,
            MediaType.ANIME,
            MediaType.DORAMA,
            MediaType.MUSIC,
            MediaType.BOOK,
            MediaType.AUDIOBOOK,
            MediaType.COMIC
        ]
        
        for media_type in expected_media_types:
            self.assertIn(media_type, orchestrator.organizadores)


class TestOrchestratorFunctionality(unittest.TestCase):
    """Test orchestrator functionality"""
    
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = Config()
        
        # Set up test paths
        self.config.library_path_movies = self.temp_dir / "movies"
        self.config.download_path_movies = self.temp_dir / "downloads" / "movies"
        self.config.database_path = self.temp_dir / "test_db.json"
        
        # Create necessary directories
        self.config.library_path_movies.mkdir(parents=True, exist_ok=True)
        self.config.download_path_movies.mkdir(parents=True, exist_ok=True)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_organize_single_file(self):
        """Test organizing a single file"""
        # Create a test file
        test_file = self.config.download_path_movies / "test_movie.mkv"
        test_file.write_text("dummy content")
        
        orchestrator = MediaOrganizerOrchestrator(self.config, dry_run=True)
        
        # Test that the file can be processed
        result = asyncio.run(orchestrator.organizar_arquivo(test_file))
        
        # Since we're in dry-run mode and no mapping exists for movies,
        # the file should be skipped
        self.assertIsNotNone(result)
        
        orchestrator.cleanup()


if __name__ == '__main__':
    unittest.main()