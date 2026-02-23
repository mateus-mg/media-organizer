"""
Teste de integração do sistema de organização de mídia
"""
import unittest
import tempfile
import os
from pathlib import Path
import asyncio

from src.config.settings import Config
from src.core.main_orchestrator import MediaOrganizerOrchestrator
from src.core.types import MediaType
from src.organizers.movie import MovieOrganizer
from src.organizers.tv import TVOrganizer
from src.organizers.music import MusicOrganizer
from src.organizers.book import BookOrganizer


class TestSystemIntegration(unittest.TestCase):
    """Testes de integração do sistema refatorado"""
    
    def setUp(self):
        """Configura o ambiente de teste"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = Config()
        
        # Cria diretórios temporários para testes
        self.movies_dir = self.temp_dir / "movies"
        self.tv_dir = self.temp_dir / "tv"
        self.music_dir = self.temp_dir / "music"
        self.books_dir = self.temp_dir / "books"
        
        for directory in [self.movies_dir, self.tv_dir, self.music_dir, self.books_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def tearDown(self):
        """Limpa o ambiente de teste"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_orchestrator_initialization(self):
        """Testa a inicialização do orchestrator"""
        orchestrator = MediaOrganizerOrchestrator(self.config, dry_run=True)
        
        # Verifica se todos os componentes necessários foram criados
        self.assertIsNotNone(orchestrator.config)
        self.assertIsNotNone(orchestrator.validators)
        self.assertIsNotNone(orchestrator.organizadores)
        self.assertIsNotNone(orchestrator.classifier)
        self.assertIsNotNone(orchestrator.scanner)
        self.assertIsNotNone(orchestrator.database)
        
        # Verifica se o modo dry-run está ativado
        self.assertTrue(orchestrator.dry_run)
        
        orchestrator.cleanup()
    
    def test_organizers_creation(self):
        """Testa a criação dos organizadores"""
        orchestrator = MediaOrganizerOrchestrator(self.config, dry_run=True)
        
        # Verifica se todos os organizadores foram criados
        expected_types = [
            MediaType.MOVIE,
            MediaType.TV_SHOW,
            MediaType.ANIME,
            MediaType.DORAMA,
            MediaType.MUSIC,
            MediaType.BOOK,
            MediaType.AUDIOBOOK,
            MediaType.COMIC
        ]
        
        for media_type in expected_types:
            self.assertIn(media_type, orchestrator.organizadores)
            organizer = orchestrator.organizadores[media_type]
            self.assertIsNotNone(organizer)
        
        orchestrator.cleanup()
    
    def test_file_scanning(self):
        """Testa a varredura de arquivos"""
        # Cria arquivos de teste
        test_files = [
            self.movies_dir / "test_movie.mkv",
            self.music_dir / "test_song.mp3",
            self.books_dir / "test_book.epub"
        ]
        
        for test_file in test_files:
            test_file.touch()
        
        orchestrator = MediaOrganizerOrchestrator(self.config, dry_run=True)
        
        # Testa a varredura
        found_files = orchestrator.scanner.escanear_diretorio(self.temp_dir)
        
        # Verifica se encontrou os arquivos criados
        found_names = [f.name for f in found_files]
        for test_file in test_files:
            self.assertIn(test_file.name, found_names)
        
        orchestrator.cleanup()


class TestOrganizerSpecific(unittest.TestCase):
    """Testes específicos para cada organizador"""
    
    def setUp(self):
        """Configura o ambiente de teste"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = Config()
        
        # Configura caminhos temporários
        self.config.library_path_movies = self.temp_dir / "library" / "movies"
        self.config.library_path_tv = self.temp_dir / "library" / "tv"
        self.config.library_path_music = self.temp_dir / "library" / "music"
        self.config.library_path_books = self.temp_dir / "library" / "books"
        
        # Cria os diretórios
        for path in [self.config.library_path_movies, self.config.library_path_tv, 
                     self.config.library_path_music, self.config.library_path_books]:
            path.mkdir(parents=True, exist_ok=True)
    
    def tearDown(self):
        """Limpa o ambiente de teste"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_movie_organizer(self):
        """Testa o organizador de filmes"""
        from src.persistence.mapping_db import SimpleMappingDB
        from src.persistence.unorganized_db import UnorganizedDatabase
        
        # Cria um banco de mapeamento temporário
        mapping_path = self.temp_dir / "manual_mapping.json"
        mapping_db = SimpleMappingDB(str(mapping_path))
        mapping_db.data = {
            "movies": [{
                "file_path": str(self.temp_dir / "test_movie.mkv"),
                "title_pt": "Filme de Teste",
                "title_en": "Test Movie",
                "year": 2023,
                "tmdb_id": 12345,
                "category": "movie"
            }],
            "tv": []
        }
        mapping_db.save()
        
        # Cria o organizador de filmes
        organizer = MovieOrganizer(
            config=self.config,
            database=None,  # Usaremos None para testes
            conflict_handler=None,
            logger=None
        )
        
        # Verifica se o organizador foi criado corretamente
        self.assertIsNotNone(organizer)
        self.assertEqual(organizer.obter_tipo_midia(), MediaType.MOVIE)
        
        # Testa a capacidade de processar arquivos
        test_file = self.temp_dir / "test_movie.mkv"
        test_file.touch()
        
        can_process = organizer.pode_processar(test_file)
        self.assertTrue(can_process)
    
    def test_music_organizer(self):
        """Testa o organizador de música"""
        # Cria o organizador de música
        organizer = MusicOrganizer(
            config=self.config,
            database=None,
            conflict_handler=None,
            logger=None
        )
        
        # Verifica se o organizador foi criado corretamente
        self.assertIsNotNone(organizer)
        self.assertEqual(organizer.obter_tipo_midia(), MediaType.MUSIC)
        
        # Testa a capacidade de processar arquivos de música
        test_file = self.temp_dir / "test_song.mp3"
        test_file.touch()
        
        can_process = organizer.pode_processar(test_file)
        self.assertTrue(can_process)
    
    def test_book_organizer(self):
        """Testa o organizador de livros"""
        # Cria o organizador de livros
        organizer = BookOrganizer(
            config=self.config,
            database=None,
            conflict_handler=None,
            logger=None,
            book_type='book'
        )
        
        # Verifica se o organizador foi criado corretamente
        self.assertIsNotNone(organizer)
        self.assertEqual(organizer.obter_tipo_midia(), MediaType.BOOK)
        
        # Testa a capacidade de processar arquivos de livro
        test_file = self.temp_dir / "test_book.epub"
        test_file.touch()
        
        can_process = organizer.pode_processar(test_file)
        self.assertTrue(can_process)


if __name__ == '__main__':
    unittest.main()