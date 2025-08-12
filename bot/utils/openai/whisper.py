"""Распознавание речи через Whisper."""
import io
from bot.utils.log import logger
from .base import client, oai_limiter


class WhisperManager:
    """Управление распознаванием речи через Whisper."""
    
    @staticmethod
    async def transcribe_audio(audio_file: io.BytesIO, chat_id: int, user_id: int) -> str:
        """Распознаёт речь с помощью OpenAI Whisper и возвращает текст."""
        async with oai_limiter(chat_id):
            try:
                logger.info(f"Отправка аудио в Whisper для chat_id={chat_id}, user_id={user_id}")
                audio_file.seek(0)
                transcript = await client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-1",
                    response_format="text",
                    language="ru"
                )
                logger.info(f"Whisper результат: {transcript}")
                return transcript
            except Exception as e:
                logger.error(f"Ошибка Whisper: {e}")
                raise