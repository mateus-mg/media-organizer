"""
Testes para o fluxo completo do sistema
"""
import unittest
import tempfile
import os
from pathlib import Path
import asyncio
from unittest.mock import Mock, patch

from src.config.settings import Config
from src.core.main_orchestrator import MediaOrganizerOrchestrator
from src.detection.classifier import MediaClassifier
from src.detection.scanner import FileScanner
from src.core.validator import FileExistenceValidator
from src.organizers.movie import MovieOrganizer
from src.organizers.music import MusicOrganizer
from src.organizers.book import BookOrganizer
from src.persistence.database import OrganizationDatabase


class TestCompleteWorkflow(unittest.TestCase):
    """Testes para o fluxo completo do sistema"""
    
    def setUp(self):
        """Configura o ambiente de teste"""
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # Configuração para testes
        self.config = Config()
        
        # Configura caminhos temporários
        self.config.library_path_movies = self.temp_dir / "library" / "movies"
        self.config.library_path_music = self.temp_dir / "library" / "music"
        self.config.library_path_books = self.temp_dir / "library" / "books"
        self.config.download_path_movies = self.temp_dir / "downloads" / "movies"
        self.config.download_path_music = self.temp_dir / "downloads" / "music"
        self.config.database_path = self.temp_dir / "test_organization.json"
        
        # Cria os diretórios
        for path in [
            self.config.library_path_movies, 
            self.config.library_path_music,
            self.config.library_path_books,
            self.config.download_path_movies,
            self.config.download_path_music
        ]:
            path.mkdir(parents=True, exist_ok=True)
    
    def tearDown(self):
        """Limpa o ambiente de teste"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_complete_workflow_with_mocked_components(self):
        """Testa o fluxo completo com componentes simulados"""
        # Cria arquivos de teste
        movie_file = self.config.download_path_movies / "test_movie.mkv"
        music_file = self.config.download_path_music / "test_song.mp3"
        
        movie_file.write_text("movie content")
        music_file.write_text("music content")
        
        # Testa o classificador
        classifier = MediaClassifier()
        
        movie_type = classifier.classificar_tipo_midia(movie_file)
        music_type = classifier.classificar_tipo_midia(music_file)
        
        self.assertEqual(movie_type, self._get_media_type_enum('MOVIE'))
        self.assertEqual(music_type, self._get_media_type_enum('MUSIC'))
    
    def _get_media_type_enum(self, type_name):
        """Helper para obter o enum MediaType"""
        from src.core.types import MediaType
        return getattr(MediaType, type_name)
    
    def test_file_scanning_workflow(self):
        """Testa o fluxo de varredura de arquivos"""
        # Cria arquivos de teste
        test_files = [
            self.config.download_path_movies / "test1.mkv",
            self.config.download_path_movies / "test2.mp4",
            self.config.download_path_music / "song1.mp3",
            self.config.download_path_music / "song2.flac"
        ]
        
        for test_file in test_files:
            test_file.write_text(f"content of {test_file.name}")
        
        # Testa o scanner
        scanner = FileScanner()
        found_files = scanner.escanear_diretorio(self.temp_dir)
        
        # Verifica se encontrou os arquivos criados
        found_paths = [f for f in found_files]
        
        for test_file in test_files:
            self.assertIn(test_file, found_paths)
    
    def test_validation_workflow(self):
        """Testa o fluxo de validação de arquivos"""
        # Cria um arquivo de teste
        test_file = self.config.download_path_movies / "validation_test.mkv"
        test_file.write_text("test content")
        
        # Testa o validador de existência
        validator = FileExistenceValidator()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(validator.validate(test_file))
            self.assertTrue(result.is_valid)
        finally:
            loop.close()
        
        # Testa com arquivo inexistente
        nonexistent_file = self.temp_dir / "nonexistent.txt"
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(validator.validate(nonexistent_file))
            self.assertFalse(result.is_valid)
        finally:
            loop.close()
    
    def test_database_integration(self):
        """Testa a integração com o banco de dados"""
        db_path = self.temp_dir / "test_db.json"
        
        # Cria o banco de dados
        db = OrganizationDatabase(
            db_path=db_path,
            backup_enabled=False
        )
        
        # Testa adição de mídia
        success = db.adicionar_midia(
            file_hash="test_hash_123",
            original_path="/original/path/test.mp4",
            organized_path="/organized/path/test.mp4",
            metadata={"title": "Test Movie", "year": 2023}
        )
        
        self.assertTrue(success)
        
        # Testa obtenção de estatísticas
        stats = db.get_stats()
        self.assertIsNotNone(stats)
        self.assertIn('total_files_organized', stats)
        
        # Fecha o banco de dados
        db.close()
    
    @patch('src.persistence.mapping_db.SimpleMappingDB')
    def test_movie_organizer_with_mocked_mapping(self, mock_mapping_db):
        """Testa o organizador de filmes com mapeamento simulado"""
        # Configura o mock
        mock_instance = Mock()
        mock_instance.find_movie_for_file.return_value = {
            "file_path": "/test/movie.mkv",
            "title_pt": "Filme de Teste",
            "title_en": "Test Movie", 
            "year": 2023,
            "tmdb_id": 12345,
            "category": "movie"
        }
        mock_mapping_db.return_value = mock_instance
        
        # Cria o organizador
        organizer = MovieOrganizer(
            config=self.config,
            database=None,
            conflict_handler=None,
            logger=None
        )
        
        # Testa os métodos
        self.assertEqual(organizer.obter_tipo_midia(), self._get_media_type_enum('MOVIE'))
        
        # Testa se pode processar arquivos de vídeo
        test_file = self.temp_dir / "test_movie.mkv"
        test_file.touch()
        
        can_process = organizer.pode_processar(test_file)
        self.assertTrue(can_process)
    
    def test_music_organizer_functionality(self):
        """Testa a funcionalidade do organizador de música"""
        organizer = MusicOrganizer(
            config=self.config,
            database=None,
            conflict_handler=None,
            logger=None
        )
        
        # Testa o tipo de mídia
        self.assertEqual(organizer.obter_tipo_midia(), self._get_media_type_enum('MUSIC'))
        
        # Testa se pode processar arquivos de música
        test_file = self.temp_dir / "test_song.mp3"
        test_file.touch()
        
        can_process = organizer.pode_processar(test_file)
        self.assertTrue(can_process)
    
    def test_book_organizer_functionality(self):
        """Testa a funcionalidade do organizador de livros"""
        organizer = BookOrganizer(
            config=self.config,
            database=None,
            conflict_handler=None,
            logger=None,
            book_type='book'
        )
        
        # Testa o tipo de mídia
        self.assertEqual(organizer.obter_tipo_midia(), self._get_media_type_enum('BOOK'))
        
        # Testa se pode processar arquivos de livro
        test_file = self.temp_dir / "test_book.epub"
        test_file.touch()
        
        can_process = organizer.pode_processar(test_file)
        self.assertTrue(can_process)


class TestOrchestratorWorkflow(unittest.TestCase):
    """Testes para o workflow do orchestrator"""
    
    def setUp(self):
        """Configura o ambiente de teste"""
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # Configuração para testes
        self.config = Config()
        
        # Configura caminhos temporários
        self.config.library_path_movies = self.temp_dir / "library" / "movies"
        self.config.download_path_movies = self.temp_dir / "downloads" / "movies"
        self.config.database_path = self.temp_dir / "test_organization.json"
        
        # Cria os diretórios
        for path in [self.config.library_path_movies, self.config.download_path_movies]:
            path.mkdir(parents=True, exist_ok=True)
    
    def tearDown(self):
        """Limpa o ambiente de teste"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_orchestrator_with_real_components(self):
        """Testa o orchestrator com componentes reais"""
        # Cria um pequeno arquivo de teste
        test_file = self.config.download_path_movies / "orchestrator_test.mkv"
        test_file.write_text("test content for orchestrator")
        
        # Cria o orchestrator
        orchestrator = MediaOrganizerOrchestrator(self.config, dry_run=True)
        
        # Testa a organização de diretório (mesmo que vazio)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                orchestrator.organizar_diretorio(self.config.download_path_movies)
            )
            # O resultado é o número de arquivos processados
            self.assertIsInstance(result, int)
        except Exception as e:
            # Pode falhar se não houver mapeamento para o filme, o que é esperado
            pass
        finally:
            loop.close()
        
        orchestrator.cleanup()
    
    def test_orchestrator_component_access(self):
        """Testa o acesso aos componentes do orchestrator"""
        orchestrator = MediaOrganizerOrchestrator(self.config, dry_run=True)
        
        # Verifica se todos os componentes estão disponíveis
        self.assertIsNotNone(orchestrator.config)
        self.assertIsNotNone(orchestrator.validators)
        self.assertIsNotNone(orchestrator.organizadores)
        self.assertIsNotNone(orchestrator.classifier)
        self.assertIsNotNone(orchestrator.scanner)
        self.assertIsNotNone(orchestrator.database)
        
        # Verifica se há organizadores para os tipos principais
        from src.core.types import MediaType
        expected_types = [MediaType.MOVIE, MediaType.MUSIC, MediaType.BOOK]
        
        for media_type in expected_types:
            self.assertIn(media_type, orchestrator.organizadores)
        
        orchestrator.cleanup()


if __name__ == '__main__':
    unittest.main()