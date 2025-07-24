"""Утилита для обеспечения запуска единственного экземпляра бота."""
import os
import sys
import atexit
from pathlib import Path
from typing import Optional

class SingleInstance:
    """Класс для обеспечения запуска только одного экземпляра приложения."""
    
    def __init__(self, lock_file: str = "bot.lock"):
        """
        Инициализация проверки единственного экземпляра.
        
        Args:
            lock_file: Имя файла блокировки
        """
        self.lock_file = Path(lock_file)
        self.lock_fd: Optional[int] = None
        
    def __enter__(self):
        """Вход в контекстный менеджер - создание блокировки."""
        try:
            # Создаем файл блокировки
            self.lock_fd = os.open(str(self.lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            
            # Записываем PID текущего процесса
            os.write(self.lock_fd, str(os.getpid()).encode())
            os.fsync(self.lock_fd)
            
            # Регистрируем функцию очистки при выходе
            atexit.register(self._cleanup)
            
            print(f"✅ Блокировка создана: {self.lock_file}")
            return self
            
        except FileExistsError:
            # Файл блокировки уже существует
            if self._is_process_running():
                print(f"❌ Другой экземпляр бота уже запущен!")
                print(f"📁 Файл блокировки: {self.lock_file.absolute()}")
                
                # Получаем PID запущенного процесса
                try:
                    with open(self.lock_file, 'r') as f:
                        pid = f.read().strip()
                    print(f"🔍 PID запущенного процесса: {pid}")
                    print(f"💡 Остановите процесс командой: kill {pid}")
                except Exception:
                    print(f"💡 Удалите файл блокировки: rm {self.lock_file}")
                
                sys.exit(1)
            else:
                # Процесс не запущен, удаляем старый lock файл
                print(f"🧹 Удаляю устаревший файл блокировки...")
                self._cleanup()
                return self.__enter__()  # Пробуем снова
                
        except Exception as e:
            print(f"❌ Ошибка создания блокировки: {e}")
            # НЕ завершаем программу при ошибке блокировки
            print(f"⚠️ Продолжаю работу без блокировки...")
            return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Выход из контекстного менеджера - удаление блокировки."""
        self._cleanup()
    
    def _is_process_running(self) -> bool:
        """Проверяет, запущен ли процесс с PID из файла блокировки."""
        try:
            with open(self.lock_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Проверяем существование процесса
            # На Unix/Linux используем os.kill(pid, 0)
            if os.name == 'posix':
                os.kill(pid, 0)  # Сигнал 0 - проверка существования
                return True
            else:
                # На Windows используем альтернативный метод
                try:
                    import subprocess
                    result = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], 
                                          capture_output=True, text=True)
                    return str(pid) in result.stdout
                except Exception:
                    return False
            
        except (ValueError, FileNotFoundError, ProcessLookupError, PermissionError):
            return False
    
    def _cleanup(self):
        """Очистка ресурсов - закрытие файла и удаление блокировки."""
        try:
            if self.lock_fd is not None:
                os.close(self.lock_fd)
                self.lock_fd = None
                
            if self.lock_file.exists():
                self.lock_file.unlink()
                print(f"🧹 Блокировка удалена: {self.lock_file}")
                
        except Exception as e:
            print(f"⚠️ Ошибка очистки блокировки: {e}")


def ensure_single_instance(lock_file: str = "bot.lock") -> SingleInstance:
    """
    Утилита для обеспечения запуска единственного экземпляра.
    
    Args:
        lock_file: Имя файла блокировки
        
    Returns:
        Контекстный менеджер SingleInstance
        
    Example:
        with ensure_single_instance():
            # Код приложения
            pass
    """
    return SingleInstance(lock_file)