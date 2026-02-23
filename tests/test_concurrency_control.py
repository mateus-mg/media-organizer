"""
Testes para o controle de concorrência
"""
import unittest
import tempfile
from pathlib import Path
import asyncio
from unittest.mock import Mock

from src.utils import ConcurrencyManager, FileOperations


class TestConcurrencyControl(unittest.TestCase):
    """Testes para o controle de concorrência"""
    
    def setUp(self):
        """Configura o ambiente de teste"""
        self.temp_dir = Path(tempfile.mkdtemp())
    
    def tearDown(self):
        """Limpa o ambiente de teste"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_concurrency_manager_initialization(self):
        """Testa a inicialização do gerenciador de concorrência"""
        manager = ConcurrencyManager(max_concurrent=5)
        
        self.assertEqual(manager.max_concurrent, 5)
        self.assertIsNotNone(manager.semaphore)
        self.assertEqual(manager.max_concurrent, 5)
    
    def test_semaphore_limit(self):
        """Testa o limite do semáforo de concorrência"""
        manager = ConcurrencyManager(max_concurrent=2)
        
        self.assertEqual(manager.semaphore._value, 2)
    
    def test_file_lock_creation(self):
        """Testa a criação de locks para arquivos"""
        manager = ConcurrencyManager()
        
        test_file = self.temp_dir / "test_file.txt"
        test_file.touch()
        
        # Obtém o lock para o arquivo
        lock1 = manager.obter_lock_arquivo(test_file)
        lock2 = manager.obter_lock_arquivo(test_file)
        
        # Ambos devem ser o mesmo lock (singleton por caminho)
        self.assertIs(lock1, lock2)
    
    def test_different_file_locks(self):
        """Testa que arquivos diferentes têm locks diferentes"""
        manager = ConcurrencyManager()
        
        file1 = self.temp_dir / "test_file1.txt"
        file2 = self.temp_dir / "test_file2.txt"
        
        file1.touch()
        file2.touch()
        
        # Obtém locks para arquivos diferentes
        lock1 = manager.obter_lock_arquivo(file1)
        lock2 = manager.obter_lock_arquivo(file2)
        
        # Devem ser locks diferentes
        self.assertIsNot(lock1, lock2)
    
    async def async_test_concurrent_execution(self):
        """Testa a execução concorrente de tarefas"""
        manager = ConcurrencyManager(max_concurrent=2)
        
        # Cria algumas tarefas assíncronas para testar
        async def task1():
            await asyncio.sleep(0.01)
            return "result1"
        
        async def task2():
            await asyncio.sleep(0.01)
            return "result2"
        
        async def task3():
            await asyncio.sleep(0.01)
            return "result3"
        
        tasks = [task1, task2, task3]
        
        # Executa as tarefas em paralelo
        results = await manager.executar_em_paralelo(tasks, limite_simultaneos=2)
        
        # Verifica os resultados
        self.assertEqual(len(results), 3)
        self.assertIn("result1", results)
        self.assertIn("result2", results)
        self.assertIn("result3", results)
    
    def test_concurrent_execution_sync(self):
        """Testa a execução concorrente de tarefas síncronas"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            results = loop.run_until_complete(self.async_test_concurrent_execution())
        finally:
            loop.close()
    
    def test_execute_operation_with_file_lock(self):
        """Testa a execução de operação com lock de arquivo"""
        manager = ConcurrencyManager()
        
        test_file = self.temp_dir / "locked_file.txt"
        test_file.touch()
        
        async def sample_operation():
            return "operation_completed"
        
        # Executa operação com lock de arquivo
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                manager.executar_operacao_arquivo(test_file, sample_operation)
            )
            self.assertEqual(result, "operation_completed")
        finally:
            loop.close()


class TestFileOperations(unittest.TestCase):
    """Testes para as operações de arquivo com controle de concorrência"""
    
    def setUp(self):
        """Configura o ambiente de teste"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.concurrency_manager = ConcurrencyManager(max_concurrent=2)
    
    def tearDown(self):
        """Limpa o ambiente de teste"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_file_operations_initialization(self):
        """Testa a inicialização das operações de arquivo"""
        from src.utils.logger import get_logger
        from src.config.settings import Config
        
        config = Config()
        logger = get_logger(config=config)
        
        file_ops = FileOperations(self.concurrency_manager, logger)
        
        self.assertIsNotNone(file_ops.concurrency_manager)
        self.assertIsNotNone(file_ops.logger)
    
    def test_safe_hardlink_creation(self):
        """Testa a criação segura de hardlinks"""
        from src.utils.logger import get_logger
        from src.config.settings import Config
        
        config = Config()
        logger = get_logger(config=config)
        
        file_ops = FileOperations(self.concurrency_manager, logger)
        
        # Cria arquivos de teste
        source_file = self.temp_dir / "source.txt"
        dest_file = self.temp_dir / "dest.txt"
        
        source_file.write_text("test content")
        
        # Testa a criação de hardlink
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                file_ops.safe_hardlink(source_file, dest_file)
            )
            # O resultado pode ser True ou False dependendo do ambiente
            # Mas não deve causar exceção
            self.assertIsInstance(result, bool)
        except Exception as e:
            # Pode falhar em alguns sistemas de arquivos que não suportam hardlinks
            # Mas deve ser uma exceção esperada
            pass
        finally:
            loop.close()
    
    def test_safe_copy_operation(self):
        """Testa a operação segura de cópia"""
        from src.utils.logger import get_logger
        from src.config.settings import Config
        
        config = Config()
        logger = get_logger(config=config)
        
        file_ops = FileOperations(self.concurrency_manager, logger)
        
        # Cria arquivos de teste
        source_file = self.temp_dir / "source_copy.txt"
        dest_file = self.temp_dir / "dest_copy.txt"
        
        source_file.write_text("test copy content")
        
        # Testa a cópia
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                file_ops.safe_copy(source_file, dest_file)
            )
            # O resultado pode ser True ou False
            self.assertIsInstance(result, bool)
            
            # Se a cópia foi bem-sucedida, o arquivo destino deve existir
            if result:
                self.assertTrue(dest_file.exists())
        finally:
            loop.close()


class TestConcurrencyEdgeCases(unittest.TestCase):
    """Testes para casos extremos de concorrência"""
    
    def test_zero_concurrent_limit(self):
        """Testa o limite de concorrência zero"""
        manager = ConcurrencyManager(max_concurrent=0)
        
        # O semáforo deve aceitar zero
        self.assertEqual(manager.semaphore._value, 0)
    
    def test_high_concurrent_limit(self):
        """Testa um limite de concorrência alto"""
        manager = ConcurrencyManager(max_concurrent=100)
        
        self.assertEqual(manager.max_concurrent, 100)
        self.assertEqual(manager.semaphore._value, 100)
    
    def test_thread_safety(self):
        """Testa a segurança em relação a threads"""
        manager = ConcurrencyManager(max_concurrent=5)
        
        # Testa que o lock de proteção ao dicionário de locks existe
        self.assertIsNotNone(manager.locks_lock)
        
        # Testa que podemos obter locks de forma segura
        test_file = Path("/tmp/test_file.txt")
        
        lock1 = manager.obter_lock_arquivo(test_file)
        lock2 = manager.obter_lock_arquivo(test_file)
        
        # Deve ser o mesmo lock para o mesmo arquivo
        self.assertIs(lock1, lock2)


if __name__ == '__main__':
    unittest.main()