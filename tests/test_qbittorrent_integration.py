"""
Testes para a integração com QBittorrent
"""
import unittest
import tempfile
from pathlib import Path
import asyncio
from unittest.mock import Mock, patch, MagicMock

from src.integration.qbittorrent_validator import QBittorrentValidator
from src.integration.qbittorrent_client import QBittorrentClientWrapper, QBittorrentConfig
from src.config.settings import Config


class TestQBittorrentIntegration(unittest.TestCase):
    """Testes para a integração com QBittorrent"""
    
    def setUp(self):
        """Configura o ambiente de teste"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = Config()
        
        # Configurações de teste para QBittorrent
        self.qb_config = QBittorrentConfig(
            host="http://localhost:8080",
            username="admin",
            password="adminadmin",
            min_progress=1.0,
            path_mapping={},
            ignored_categories=["outros", "others"]
        )
    
    def tearDown(self):
        """Limpa o ambiente de teste"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('src.integration.qbittorrent_client.QBittorrentClient')
    def test_qbittorrent_client_initialization(self, mock_client):
        """Testa a inicialização do cliente QBittorrent"""
        # Configura o mock
        mock_instance = Mock()
        mock_instance.app.version = "4.5.0"
        mock_client.return_value = mock_instance
        
        client = QBittorrentClientWrapper(self.qb_config)
        
        # Testa a conexão
        connected = asyncio.run(client.connect())
        self.assertTrue(connected)
        
        # Verifica se o cliente foi chamado corretamente
        mock_client.assert_called_once_with(
            host=self.qb_config.host,
            username=self.qb_config.username,
            password=self.qb_config.password
        )
    
    def test_qbittorrent_config_creation(self):
        """Testa a criação da configuração QBittorrent"""
        config = QBittorrentConfig(
            host="http://test:8080",
            username="test_user",
            password="test_pass",
            min_progress=0.9,
            path_mapping={"/container": "/host"},
            ignored_categories=["test"]
        )
        
        self.assertEqual(config.host, "http://test:8080")
        self.assertEqual(config.username, "test_user")
        self.assertEqual(config.password, "test_pass")
        self.assertEqual(config.min_progress, 0.9)
        self.assertEqual(config.path_mapping, {"/container": "/host"})
        self.assertEqual(config.ignored_categories, ["test"])
    
    @patch('src.integration.qbittorrent_client.QBittorrentClientWrapper')
    def test_qbittorrent_validator_initialization(self, mock_client_wrapper):
        """Testa a inicialização do validador QBittorrent"""
        # Configura o mock
        mock_instance = Mock()
        mock_instance.get_completed_torrents = AsyncMock(return_value=[])
        mock_client_wrapper.return_value = mock_instance
        
        validator = QBittorrentValidator(self.qb_config)
        
        self.assertIsNotNone(validator)
        self.assertEqual(validator.config, self.qb_config)
    
    @patch('src.integration.qbittorrent_client.QBittorrentClientWrapper')
    def test_qbittorrent_validator_file_validation(self, mock_client_wrapper):
        """Testa a validação de arquivos pelo validador QBittorrent"""
        # Cria arquivos de teste
        test_file1 = self.temp_dir / "test_movie.mkv"
        test_file2 = self.temp_dir / "test_song.mp3"
        
        test_file1.touch()
        test_file2.touch()
        
        test_files = [test_file1, test_file2]
        
        # Simula torrents completados
        from src.core.types import TorrentFileInfo
        completed_files = [
            TorrentFileInfo(
                hash="hash1",
                name="test_movie.mkv",
                state="seeding",
                progress=1.0,
                save_path=self.temp_dir,
                file_path=test_file1,
                is_complete=True
            )
        ]
        
        # Configura o mock
        mock_instance = Mock()
        mock_instance.get_completed_torrents = AsyncMock(return_value=completed_files)
        mock_client_wrapper.return_value = mock_instance
        
        validator = QBittorrentValidator(self.qb_config)
        
        # Testa a validação
        valid_files = asyncio.run(validator.validar_arquivos(test_files))
        
        # Apenas o arquivo que está na lista de torrents completados deve ser retornado
        self.assertEqual(len(valid_files), 1)
        self.assertIn(test_file1, valid_files)
        self.assertNotIn(test_file2, valid_files)
    
    def test_qbittorrent_enabled_check(self):
        """Testa a verificação se o QBittorrent está habilitado"""
        # Testa com QBittorrent desabilitado
        config_disabled = Config()
        # Simula configuração com QBittorrent desabilitado
        config_disabled.qbittorrent_enabled = False
        
        self.assertFalse(config_disabled.qbittorrent_enabled)
        
        # Testa com QBittorrent habilitado
        config_enabled = Config()
        # Simula configuração com QBittorrent habilitado
        config_enabled.qbittorrent_enabled = True
        
        self.assertTrue(config_enabled.qbittorrent_enabled)


class TestQBittorrentPathMapping(unittest.TestCase):
    """Testes para o mapeamento de caminhos do QBittorrent"""
    
    def test_path_mapping_functionality(self):
        """Testa a funcionalidade de mapeamento de caminhos"""
        config = QBittorrentConfig(
            host="http://localhost:8080",
            username="admin",
            password="adminadmin",
            path_mapping={
                "/container/downloads": "/host/downloads",
                "/container/media": "/host/media"
            }
        )
        
        client = QBittorrentClientWrapper(config)
        
        # Testa o mapeamento de caminho
        container_path = Path("/container/downloads/movie.mkv")
        mapped_path = client._map_path(container_path)
        
        # O caminho deve ser mapeado para o host
        expected_path = Path("/host/downloads/movie.mkv")
        self.assertEqual(mapped_path, expected_path)
    
    def test_no_mapping_scenario(self):
        """Testa quando não há mapeamento configurado"""
        config = QBittorrentConfig(
            host="http://localhost:8080",
            username="admin",
            password="adminadmin",
            path_mapping={}
        )
        
        client = QBittorrentClientWrapper(config)
        
        # Testa o mapeamento de caminho sem mapeamentos
        original_path = Path("/some/path/movie.mkv")
        mapped_path = client._map_path(original_path)
        
        # O caminho deve permanecer o mesmo
        self.assertEqual(mapped_path, original_path)


# Mock assíncrono para testes
class AsyncMock(Mock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)


if __name__ == '__main__':
    unittest.main()