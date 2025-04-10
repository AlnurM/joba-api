import os
import json
import logging
import httpx
from typing import Dict, Any
from fastapi import HTTPException
import base64
from httpx import Timeout, Limits
import asyncio
import time
from models.job_queries import JobQueryKeywords

logger = logging.getLogger(__name__)

class ClaudeClient:
    def __init__(self):
        self.api_key = os.getenv("CLAUDE_API_KEY")
        if not self.api_key:
            raise ValueError("CLAUDE_API_KEY is not set in environment variables")
        
        self.base_url = "https://api.anthropic.com/v1"
        self.headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        # Optimized HTTP client settings
        self.timeout = Timeout(
            connect=10.0,  # Connection establishment timeout
            read=120.0,    # Response read timeout
            write=10.0,    # Write timeout
            pool=10.0      # Pool connection acquisition timeout
        )
        self.limits = Limits(
            max_keepalive_connections=5,
            max_connections=10
        )
        
    async def analyze_text(self, text: str, prompt: str) -> Dict[str, Any]:
        """
        Analyze text using Claude API
        
        Args:
            text: Text to analyze
            prompt: Prompt for Claude
            
        Returns:
            Dict with analysis results
        """
        start_time = time.time()
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                limits=self.limits
            ) as client:
                logger.info(f"Sending request to Claude API (text length: {len(text)} characters)")
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers=self.headers,
                    json={
                        "model": "claude-3-7-sonnet-20250219",
                        "max_tokens": 4000,
                        "messages": [
                            {
                                "role": "user",
                                "content": f"{prompt}\n\nText to analyze:\n{text}"
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
                        detail=f"Error analyzing text: {response.text}"
                    )
                
                result = response.json()
                logger.debug(f"Response from Claude API: {json.dumps(result, ensure_ascii=False)}")
                return result
                
        except httpx.TimeoutException as e:
            logger.error(f"Timeout in Claude API request: {str(e)}")
            raise HTTPException(
                status_code=504,
                detail="API request timeout"
            )
        except Exception as e:
            logger.error(f"Error in Claude API request: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error analyzing text: {str(e)}"
            )
            
    async def extract_json(self, text: str, prompt: str) -> Dict[str, Any]:
        """
        Extract structured data in JSON format from text
        
        Args:
            text: Text to analyze
            prompt: Prompt for Claude with data extraction instructions
            
        Returns:
            Dict with extracted data
        """
        try:
            result = await self.analyze_text(text, prompt)
            content = result.get("content", [{}])[0].get("text", "")
            
            logger.debug(f"Raw response from Claude: {content}")
            
            # Find JSON in response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start == -1 or end == 0:
                logger.error("Could not find JSON in response")
                raise ValueError("Could not find JSON in response")
                
            json_str = content[start:end]
            logger.debug(f"Extracted JSON: {json_str}")
            
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON: {str(e)}")
                logger.error(f"Problematic JSON: {json_str}")
                raise ValueError(f"Error parsing JSON: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error extracting JSON: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error extracting data: {str(e)}"
            )

    async def analyze_file(self, file_content: bytes, file_extension: str, prompt: str) -> Dict[str, Any]:
        """
        Analyze file using Claude API
        
        Args:
            file_content: File content in bytes
            file_extension: File extension (with dot)
            prompt: Prompt for Claude
            
        Returns:
            Dict with analysis results
        """
        start_time = time.time()
        try:
            # Determine file MIME type
            mime_types = {
                '.pdf': 'application/pdf',
                '.doc': 'application/msword',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            }
            mime_type = mime_types.get(file_extension.lower())
            if not mime_type:
                raise ValueError(f"Unsupported file format: {file_extension}")

            # Encode file in base64
            file_base64 = base64.b64encode(file_content).decode('utf-8')
            logger.info(f"File encoded in base64 (size: {len(file_base64)} characters)")
            
            # Create HTTP client with settings
            async with httpx.AsyncClient(
                timeout=self.timeout,
                limits=self.limits
            ) as client:
                for attempt in range(3):  # Maximum 3 attempts
                    try:
                        logger.info(f"Attempt {attempt + 1} of 3")
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
                        
                        if response.status_code == 200:
                            break
                        elif response.status_code == 429:  # Rate limit
                            if attempt < 2:  # Don't sleep on last attempt
                                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                                continue
                        
                        logger.error(f"Claude API error (HTTP {response.status_code}): {response.text}")
                        raise HTTPException(
                            status_code=500,
                            detail=f"Error analyzing file: {response.text}"
                        )
                        
                    except Exception as e:
                        if attempt < 2:
                            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                            await asyncio.sleep(2 ** attempt)
                            continue
                        raise
                        
                elapsed_time = time.time() - start_time
                logger.info(f"Claude API request completed in {elapsed_time:.2f} seconds")
                
                result = response.json()
                logger.debug(f"Response from Claude API: {json.dumps(result, ensure_ascii=False)}")
                return result
                
        except httpx.TimeoutException as e:
            logger.error(f"Timeout in Claude API request: {str(e)}")
            raise HTTPException(
                status_code=504,
                detail="API request timeout"
            )
        except Exception as e:
            logger.error(f"Error in Claude API request: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error analyzing file: {str(e)}"
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
                limits=self.limits
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

    async def render_cover_letter(
        self,
        job_description: str,
        content: Dict[str, str]
    ) -> str:
        """
        Renders cover letter by filling placeholders based on job description
        
        Args:
            job_description: Full text of the job description
            content: Cover letter content with placeholders
            
        Returns:
            Rendered text with filled placeholders
        """
        start_time = time.time()
        try:
            system_prompt = f"""You are an expert in analyzing job descriptions and writing cover letters.
                Job Description:
                {job_description}

                Cover Letter Content:
                {json.dumps(content, ensure_ascii=False, indent=2)}

                Important instructions:
                1. Analyze the job description and extract key requirements, skills, and company information
                2. For each section of the cover letter content:
                   - Find all placeholders in the format {{placeholder_key}}
                   - Replace them with relevant information from the job description
                   - Ensure the text flows naturally and maintains professional tone
                3. Return ONLY the rendered text with filled placeholders
                4. Do not add any comments or explanations
                5. Preserve the original structure and formatting of the content
                6. Make sure all placeholders are replaced with meaningful content
                """

            async with httpx.AsyncClient(
                timeout=self.timeout,
                limits=self.limits
            ) as client:
                logger.info("Sending request to Claude API for rendering cover letter")
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
                        detail=f"Error rendering text: {response.text}"
                    )
                
                result = response.json()
                rendered_text = result.get("content", [{}])[0].get("text", "")
                
                if not rendered_text:
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to render text"
                    )
                
                return rendered_text
                
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
                detail=f"Error rendering text: {str(e)}"
            )

    async def analyze_resume(self, candidate_data: dict) -> dict:
        """
        Analyze resume using Claude and return structured scoring results.
        
        Args:
            candidate_data: Candidate data from MongoDB resume document
            
        Returns:
            Structured scoring results
        """
        prompt = f"""
        Please analyze this resume data and provide a detailed scoring based on the following exact criteria:

        1. Presence of key sections (30%):
        - Check if resume contains all required sections: Summary, Experience, Skills, Education
        - Each missing section reduces the score proportionally
        - Maximum score: 30%

        2. Work experience quality using STAR method (40%):
        - Evaluate how well each work experience is described using Situation, Task, Action, Result
        - Check for specific achievements and measurable results
        - Maximum score: 40%

        3. Education and certifications relevance (10%):
        - Evaluate relevance of education to the target position
        - Check for additional relevant certifications and courses
        - Maximum score: 10%

        4. Timeline consistency (10%):
        - Check for any date contradictions in work history
        - Identify employment gaps longer than 2 months
        - Maximum score: 10%

        5. Language and grammar (10%):
        - Check for grammatical errors
        - Evaluate overall language quality, conciseness, and formal tone
        - Maximum score: 10%

        Resume Data:
        {json.dumps(candidate_data, indent=2, ensure_ascii=False)}

        Please provide your analysis in the following JSON format:
        {{
            "scoring": {{
                "total_score": <total_score>,
                "sections_score": <score_0_to_30>,
                "experience_score": <score_0_to_40>,
                "education_score": <score_0_to_10>,
                "timeline_score": <score_0_to_10>,
                "language_score": <score_0_to_10>
            }},
            "feedback": {{
                "sections": "<detailed_feedback_about_sections>",
                "experience": "<detailed_feedback_about_experience>",
                "education": "<detailed_feedback_about_education>",
                "timeline": "<detailed_feedback_about_timeline>",
                "language": "<detailed_feedback_about_language>"
            }}
        }}

        Important:
        - Each score must be within its specified range
        - Total score should be the sum of all individual scores
        - Provide specific, actionable feedback for each category
        """
        
        try:
            # Call Claude API with the prompt
            response = await self.analyze_text(prompt, "Analyze this resume and provide a detailed scoring based on the following criteria:")
            
            # Extract text content from response
            content = response.get("content", [{}])[0].get("text", "")
            if not content:
                raise ValueError("Empty response from Claude API")
            
            # Find JSON in response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start == -1 or end == 0:
                raise ValueError("Could not find JSON in response")
            
            json_str = content[start:end]
            
            # Parse JSON and return structured data
            return json.loads(json_str)
            
        except Exception as e:
            logger.error(f"Error analyzing resume with Claude: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to analyze resume"
            )

    async def generate_job_query_keywords(self, candidate_data: dict) -> JobQueryKeywords:
        """
        Generate job query keywords based on candidate data
        
        Args:
            candidate_data: Dictionary with candidate information
            
        Returns:
            JobQueryKeywords object with generated keywords
        """
        prompt = f"""
        Based on the following candidate data, generate job search keywords.
        For each category, provide exactly 2 words or phrases that would be most relevant for job search.
        
        Categories:
        - job_titles: Desired job titles
        - required_skills: Key skills to look for
        - work_arrangements: Preferred work arrangements
        - positions: Desired positions/levels
        - exclude_words: Words to exclude from search
        
        Candidate data:
        {json.dumps(candidate_data, indent=2, ensure_ascii=False)}
        
        Return the response in JSON format with the following structure:
        {{
            "job_titles": ["word1", "word2"],
            "required_skills": ["word1", "word2"],
            "work_arrangements": ["word1", "word2"],
            "positions": ["word1", "word2"],
            "exclude_words": ["word1", "word2"]
        }}
        """
        
        try:
            # Call Claude API with the prompt
            response = await self.analyze_text(prompt, "Generate job search keywords based on the candidate data")
            
            # Extract text content from response
            content = response.get("content", [{}])[0].get("text", "")
            if not content:
                raise ValueError("Empty response from Claude API")
            
            # Find JSON in response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start == -1 or end == 0:
                raise ValueError("Could not find JSON in response")
            
            json_str = content[start:end]
            
            # Parse JSON and validate with Pydantic model
            return JobQueryKeywords.model_validate_json(json_str)
            
        except Exception as e:
            logger.error(f"Error generating job query keywords: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to generate job query keywords"
            ) 