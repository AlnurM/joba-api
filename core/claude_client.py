import os
import json
import logging
import httpx
from typing import Dict, Any, Optional
from fastapi import HTTPException
import base64
from httpx import Timeout, Limits
import asyncio
import time

logger = logging.getLogger(__name__)

class ClaudeClient:
    def __init__(self):
        self.api_key = os.getenv("CLAUDE_API_KEY")
        if not self.api_key:
            raise ValueError("CLAUDE_API_KEY не установлен в переменных окружения")
        
        self.base_url = "https://api.anthropic.com/v1"
        self.headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        # Оптимизированные настройки HTTP-клиента
        self.timeout = Timeout(
            connect=10.0,  # Таймаут на установку соединения
            read=120.0,    # Таймаут на чтение ответа
            write=10.0,    # Таймаут на запись
            pool=10.0      # Таймаут на получение соединения из пула
        )
        self.limits = Limits(
            max_keepalive_connections=5,
            max_connections=10
        )
        
    async def analyze_text(self, text: str, prompt: str) -> Dict[str, Any]:
        """
        Анализирует текст с помощью Claude API
        
        Args:
            text: Текст для анализа
            prompt: Промпт для Claude
            
        Returns:
            Dict с результатами анализа
        """
        start_time = time.time()
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                limits=self.limits,
                http2=True
            ) as client:
                logger.info(f"Отправка запроса к Claude API (текст длиной {len(text)} символов)")
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers=self.headers,
                    json={
                        "model": "claude-3-7-sonnet-20250219",
                        "max_tokens": 4000,
                        "messages": [
                            {
                                "role": "user",
                                "content": f"{prompt}\n\nТекст для анализа:\n{text}"
                            }
                        ]
                    }
                )
                
                elapsed_time = time.time() - start_time
                logger.info(f"Запрос к Claude API выполнен за {elapsed_time:.2f} секунд")
                
                if response.status_code != 200:
                    logger.error(f"Ошибка Claude API (HTTP {response.status_code}): {response.text}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Ошибка при анализе текста: {response.text}"
                    )
                
                result = response.json()
                logger.debug(f"Ответ от Claude API: {json.dumps(result, ensure_ascii=False)}")
                return result
                
        except httpx.TimeoutException as e:
            logger.error(f"Таймаут при запросе к Claude API: {str(e)}")
            raise HTTPException(
                status_code=504,
                detail="Таймаут при запросе к API"
            )
        except Exception as e:
            logger.error(f"Ошибка при запросе к Claude API: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при анализе текста: {str(e)}"
            )
            
    async def extract_json(self, text: str, prompt: str) -> Dict[str, Any]:
        """
        Извлекает структурированные данные в формате JSON из текста
        
        Args:
            text: Текст для анализа
            prompt: Промпт для Claude с инструкциями по извлечению данных
            
        Returns:
            Dict с извлеченными данными
        """
        try:
            result = await self.analyze_text(text, prompt)
            content = result.get("content", [{}])[0].get("text", "")
            
            logger.debug(f"Сырой ответ от Claude: {content}")
            
            # Ищем JSON в ответе
            start = content.find("{")
            end = content.rfind("}") + 1
            if start == -1 or end == 0:
                logger.error("Не удалось найти JSON в ответе")
                raise ValueError("Не удалось найти JSON в ответе")
                
            json_str = content[start:end]
            logger.debug(f"Извлеченный JSON: {json_str}")
            
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка при парсинге JSON: {str(e)}")
                logger.error(f"Проблемный JSON: {json_str}")
                raise ValueError(f"Ошибка при парсинге JSON: {str(e)}")
            
        except Exception as e:
            logger.error(f"Ошибка при извлечении JSON: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при извлечении данных: {str(e)}"
            )

    async def analyze_file(self, file_content: bytes, file_extension: str, prompt: str) -> Dict[str, Any]:
        """
        Анализирует файл с помощью Claude API
        
        Args:
            file_content: Содержимое файла в байтах
            file_extension: Расширение файла (с точкой)
            prompt: Промпт для Claude
            
        Returns:
            Dict с результатами анализа
        """
        start_time = time.time()
        try:
            # Определяем MIME-тип файла
            mime_types = {
                '.pdf': 'application/pdf',
                '.doc': 'application/msword',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            }
            mime_type = mime_types.get(file_extension.lower())
            if not mime_type:
                raise ValueError(f"Неподдерживаемый формат файла: {file_extension}")

            # Кодируем файл в base64
            file_base64 = base64.b64encode(file_content).decode('utf-8')
            logger.info(f"Файл закодирован в base64 (размер: {len(file_base64)} символов)")
            
            # Создаем HTTP-клиент с настройками
            async with httpx.AsyncClient(
                timeout=self.timeout,
                limits=self.limits,
                http2=True
            ) as client:
                for attempt in range(3):  # Максимум 3 попытки
                    try:
                        logger.info(f"Попытка {attempt + 1} из 3")
                        response = await client.post(
                            f"{self.base_url}/messages",
                            headers=self.headers,
                            json={
                                "model": "claude-3-7-sonnet-20250219",
                                "max_tokens": 4000,
                                "messages": [
                                    {
                                        "role": "user",
                                        "content": [
                                            {
                                                "type": "text",
                                                "text": prompt
                                            },
                                            {
                                                "type": "document",
                                                "source": {
                                                    "type": "base64",
                                                    "media_type": mime_type,
                                                    "data": file_base64
                                                }
                                            }
                                        ]
                                    }
                                ]
                            }
                        )
                        
                        elapsed_time = time.time() - start_time
                        logger.info(f"Запрос к Claude API выполнен за {elapsed_time:.2f} секунд")
                        
                        if response.status_code == 200:
                            return response.json()
                        
                        # Если ошибка 429 (слишком много запросов), ждем и пробуем снова
                        if response.status_code == 429:
                            if attempt < 2:  # Не ждем на последней попытке
                                wait_time = 2 ** attempt
                                logger.info(f"Получен код 429, ждем {wait_time} секунд")
                                await asyncio.sleep(wait_time)  # Экспоненциальная задержка
                                continue
                                
                        logger.error(f"Ошибка Claude API (HTTP {response.status_code}): {response.text}")
                        raise HTTPException(
                            status_code=500,
                            detail=f"Ошибка при анализе файла: {response.text}"
                        )
                        
                    except httpx.TimeoutException:
                        if attempt < 2:  # Не ждем на последней попытке
                            wait_time = 2 ** attempt
                            logger.warning(f"Таймаут, ждем {wait_time} секунд")
                            await asyncio.sleep(wait_time)
                            continue
                        raise HTTPException(
                            status_code=504,
                            detail="Таймаут при запросе к API"
                        )
                    except Exception as e:
                        if attempt < 2:  # Не ждем на последней попытке
                            wait_time = 2 ** attempt
                            logger.warning(f"Ошибка: {str(e)}, ждем {wait_time} секунд")
                            await asyncio.sleep(wait_time)
                            continue
                        raise
                
                # Если все попытки неудачны
                raise HTTPException(
                    status_code=500,
                    detail="Не удалось выполнить запрос после нескольких попыток"
                )
                
        except Exception as e:
            logger.error(f"Ошибка при запросе к Claude API: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при анализе файла: {str(e)}"
            )

    async def generate_cover_letter_content(
        self,
        candidate_data: Dict[str, Any],
        prompt: str,
        content_type: str
    ) -> str:
        """
        Generates cover letter text based on candidate data
        
        Args:
            candidate_data: Candidate data from resume
            prompt: User prompt
            content_type: Content type (introduction, body_part_1, body_part_2, conclusion)
            
        Returns:
            Generated text
        """
        start_time = time.time()
        try:
            system_prompt = f"""You are an expert in writing cover letters.
                Candidate data:
                {json.dumps(candidate_data, ensure_ascii=False, indent=2)}

                Content type: {content_type}

                User prompt: {prompt}

                Important instructions:
                0: Do not ever leave your comments in the generated text
                1. Use placeholders in the format {{placeholder_key}} for places where job description data will be inserted (there have to be double brackets)
                2. The text should be:
                - Professional and formal
                - Match the candidate's data
                - Consider the user prompt
                - Be unique and personalized
                - Avoid clichés and generic phrases
                3. Generate the text in the same language as the resume content
                4. For each content type:
                - Introduction:
                    1. Start with an appropriate greeting and briefly introduce yourself
                    2. Maximum: 1 paragraph
                - Body Part 1: 
                    1. Highlight your skills, experience, and achievements
                    2. Do not contain introduction manner
                    3. Do not use the same words as in the introduction
                    4. Bullet points preferred
                    5. Maximum: 2 paragraphs
                - Body Part 2: 
                    1. Explain your interest in the company and how you match their needs
                    2. Do not contain introduction manner
                    3. Do not use the same words as in the introduction
                    5. Maximum: 1 paragraph
                - Conclusion: 
                    1. Summarize your fit and express your desire to discuss further
                    2. Maximum: 1 paragraph
                5. Check the content type given and check if it matches the requirements above and check if every placeholder wrapper with double brackets
                6. Return ONLY the generated text without any additional comments, explanations, or notes
                """

            async with httpx.AsyncClient(
                timeout=self.timeout,
                limits=self.limits,
                http2=True
            ) as client:
                logger.info(f"Sending request to Claude API for generating {content_type}")
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers=self.headers,
                    json={
                        "model": "claude-3-7-sonnet-20250219",
                        "max_tokens": 4000,
                        "messages": [
                            {
                                "role": "user",
                                "content": system_prompt
                            }
                        ]
                    }
                )
                
                elapsed_time = time.time() - start_time
                logger.info(f"Claude API request completed in {elapsed_time:.2f} seconds")
                
                if response.status_code != 200:
                    logger.error(f"Claude API error (HTTP {response.status_code}): {response.text}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Error generating text: {response.text}"
                    )
                
                result = response.json()
                generated_text = result.get("content", [{}])[0].get("text", "")
                
                if not generated_text:
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to generate text"
                    )
                
                return generated_text
                
        except httpx.TimeoutException as e:
            logger.error(f"Timeout while requesting Claude API: {str(e)}")
            raise HTTPException(
                status_code=504,
                detail="API request timeout"
            )
        except Exception as e:
            logger.error(f"Error while requesting Claude API: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error generating text: {str(e)}"
            )