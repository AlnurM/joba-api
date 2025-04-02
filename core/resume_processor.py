import os
import json
import logging
from typing import Dict, Any
from fastapi import HTTPException
from .claude_client import ClaudeClient
from datetime import datetime

logger = logging.getLogger(__name__)

async def process_resume(file_content: bytes, file_extension: str) -> Dict[str, Any]:
    """
    Обрабатывает резюме и извлекает информацию из него с помощью Claude API.
    
    Args:
        file_content: Содержимое файла резюме в байтах
        file_extension: Расширение файла (с точкой)
        
    Returns:
        Dict с извлеченной информацией из резюме
    """
    try:
        # Читаем пример JSON структуры
        with open("assets/json/CV_sample.json", "r", encoding='utf-8') as f:
            sample_json = json.load(f)
        
        # Создаем промпт для Claude
        prompt = f"""
        Проанализируй предоставленное резюме и извлеки из него информацию в формате JSON.
        Используй следующую структуру, но включай только поля, для которых есть информация в резюме:
        {json.dumps(sample_json, indent=2, ensure_ascii=False)}
        
        Инструкции:
        1. Внимательно изучи текст резюме
        2. Извлеки только доступную информацию, пропуская пустые поля
        3. Верни результат в формате JSON
        4. Убедись, что все строки правильно экранированы
        5. Не добавляй комментарии или текст вне JSON
        6. Используй компактный формат для массивов, если они содержат простые значения
        """
        
        logger.info("Начинаем обработку резюме")
        
        # Инициализируем клиент Claude
        client = ClaudeClient()
        
        # Анализируем резюме
        result = await client.analyze_file(file_content, file_extension, prompt)
        
        # Извлекаем JSON из ответа
        content = result.get("content", [{}])[0].get("text", "")
        logger.debug(f"Сырой ответ от Claude: {content}")
        
        # Ищем JSON в ответе, пропуская любой текст до и после
        start = content.find("{")
        end = content.rfind("}") + 1
        if start == -1 or end == 0:
            logger.error("Не удалось найти JSON в ответе")
            raise ValueError("Не удалось найти JSON в ответе")
            
        json_str = content[start:end]
        logger.debug(f"Извлеченный JSON: {json_str}")
        
        try:
            result = json.loads(json_str)
        except json.JSONDecodeError as e:
            # Попробуем очистить строку от невидимых символов
            json_str = "".join(char for char in json_str if ord(char) >= 32)
            try:
                result = json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка при парсинге JSON: {str(e)}")
                logger.error(f"Проблемный JSON: {json_str}")
                raise ValueError(f"Ошибка при парсинге JSON: {str(e)}")
        
        # Проверяем структуру результата
        if not isinstance(result, dict):
            raise ValueError("Результат не является словарем")
            
        # Добавляем метаданные
        if "metadata" not in result:
            result["metadata"] = {}
            
        result["metadata"]["source"] = {
            "type": "upload",
            "uploaded_at": datetime.utcnow().isoformat()
        }
        
        logger.info("Резюме успешно обработано")
        return result
        
    except Exception as e:
        logger.error(f"Ошибка при обработке резюме: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось обработать резюме: {str(e)}"
        ) 