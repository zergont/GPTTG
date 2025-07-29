"""Утилиты для проверки версий и обновлений."""
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import re

from bot.config import VERSION, settings
from bot.utils.log import logger


class UpdateChecker:
    """Класс для проверки доступности обновлений."""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent.parent
        self.current_version = VERSION
    
    async def check_updates_available(self, branch: str = "master") -> Dict[str, Any]:
        """
        Проверяет доступность обновлений.
        
        Args:
            branch: Ветка для проверки (по умолчанию master)
            
        Returns:
            dict: Информация об обновлении
                - available: bool - есть ли обновления
                - current_version: str - текущая версия
                - latest_version: str - последняя версия (если доступна)
                - current_hash: str - текущий commit hash
                - latest_hash: str - последний commit hash (если доступен)
                - commits_behind: int - количество коммитов отставания
                - error: str - ошибка, если есть
        """
        result = {
            "available": False,
            "current_version": self.current_version,
            "latest_version": None,
            "current_hash": None,
            "latest_hash": None,
            "commits_behind": 0,
            "error": None
        }
        
        try:
            # Получаем текущий commit hash
            current_hash_result = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "--short", "HEAD",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.project_root)
            )
            stdout, stderr = await current_hash_result.communicate()
            
            if current_hash_result.returncode == 0:
                result["current_hash"] = stdout.decode().strip()
            else:
                result["error"] = f"Не удалось получить текущий hash: {stderr.decode()}"
                return result
            
            # Проверяем удаленный репозиторий
            fetch_result = await asyncio.create_subprocess_exec(
                "git", "fetch", "origin", branch,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.project_root)
            )
            await fetch_result.communicate()
            
            if fetch_result.returncode != 0:
                result["error"] = "Не удалось обновить информацию о репозитории"
                return result
            
            # Получаем hash последнего коммита
            latest_hash_result = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "--short", f"origin/{branch}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.project_root)
            )
            stdout, stderr = await latest_hash_result.communicate()
            
            if latest_hash_result.returncode == 0:
                result["latest_hash"] = stdout.decode().strip()
            else:
                result["error"] = f"Не удалось получить последний hash: {stderr.decode()}"
                return result
            
            # Проверяем количество коммитов отставания
            behind_result = await asyncio.create_subprocess_exec(
                "git", "rev-list", "--count", f"HEAD..origin/{branch}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.project_root)
            )
            stdout, stderr = await behind_result.communicate()
            
            if behind_result.returncode == 0:
                commits_behind = int(stdout.decode().strip())
                result["commits_behind"] = commits_behind
                result["available"] = commits_behind > 0
            else:
                result["error"] = f"Не удалось подсчитать отставание: {stderr.decode()}"
                return result
            
            # Если есть обновления, пытаемся получить версию из pyproject.toml
            if result["available"]:
                try:
                    version_result = await asyncio.create_subprocess_exec(
                        "git", "show", f"origin/{branch}:pyproject.toml",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=str(self.project_root)
                    )
                    stdout, stderr = await version_result.communicate()
                    
                    if version_result.returncode == 0:
                        pyproject_content = stdout.decode()
                        version_match = re.search(r'version\s*=\s*"([^"]+)"', pyproject_content)
                        if version_match:
                            result["latest_version"] = version_match.group(1)
                except Exception as e:
                    logger.debug(f"Не удалось получить версию из pyproject.toml: {e}")
            
            return result
            
        except Exception as e:
            result["error"] = f"Ошибка проверки обновлений: {str(e)}"
            logger.error(f"Ошибка при проверке обновлений: {e}")
            return result
    
    async def get_recent_commits(self, branch: str = "master", count: int = 5) -> list:
        """
        Получает список последних коммитов.
        
        Args:
            branch: Ветка для проверки
            count: Количество коммитов для получения
            
        Returns:
            list: Список коммитов с информацией
        """
        commits = []
        
        try:
            # Получаем последние коммиты
            commits_result = await asyncio.create_subprocess_exec(
                "git", "log", f"origin/{branch}", 
                "--oneline", f"-{count}", "--pretty=format:%h|%s|%an|%ar",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.project_root)
            )
            stdout, stderr = await commits_result.communicate()
            
            if commits_result.returncode == 0:
                lines = stdout.decode().strip().split('\n')
                for line in lines:
                    if '|' in line:
                        parts = line.split('|', 3)
                        if len(parts) >= 4:
                            commits.append({
                                "hash": parts[0],
                                "message": parts[1],
                                "author": parts[2],
                                "date": parts[3]
                            })
            
        except Exception as e:
            logger.error(f"Ошибка при получении коммитов: {e}")
        
        return commits
    
    def format_update_info(self, update_info: Dict[str, Any]) -> str:
        """
        Форматирует информацию об обновлении для отображения в Telegram.
        
        Args:
            update_info: Результат check_updates_available()
            
        Returns:
            str: Отформатированный текст
        """
        if update_info.get("error"):
            return f"❌ <b>Ошибка проверки обновлений:</b>\n<code>{update_info['error']}</code>"
        
        current_version = update_info["current_version"]
        current_hash = update_info.get("current_hash", "неизвестен")
        
        if not update_info["available"]:
            return (
                f"✅ <b>Обновления не требуются</b>\n\n"
                f"📋 Текущая версия: <code>{current_version}</code>\n"
                f"🔹 Commit: <code>{current_hash}</code>\n\n"
                f"🎯 Вы используете последнюю версию!"
            )
        
        latest_version = update_info.get("latest_version", "неизвестна")
        latest_hash = update_info.get("latest_hash", "неизвестен")
        commits_behind = update_info.get("commits_behind", 0)
        
        text = (
            f"🔄 <b>Доступно обновление</b>\n\n"
            f"📋 Текущая версия: <code>{current_version}</code> ({current_hash})\n"
            f"🆕 Новая версия: <code>{latest_version}</code> ({latest_hash})\n"
            f"📊 Отставание: <code>{commits_behind}</code> коммит(ов)\n\n"
            f"💡 Используйте /update для обновления"
        )
        
        return text


# Глобальный экземпляр для использования в других модулях
update_checker = UpdateChecker()

__all__ = ['UpdateChecker', 'update_checker']