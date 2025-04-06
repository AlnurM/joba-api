"""Resume processing module"""

import os
import json
import logging
from typing import Dict, Any
from fastapi import HTTPException
from .claude_client import ClaudeClient
from datetime import datetime

logger = logging.getLogger(__name__)

class ResumeProcessor:
    """
    Processes resumes and extracts information using Claude API.
    """
    
    async def process_resume(self, file_content: bytes, file_extension: str) -> Dict[str, Any]:
        """
        Process resume and extract information.
        
        Args:
            file_content: Resume file content in bytes
            file_extension: File extension (with dot)
            
        Returns:
            Dictionary with extracted information
        """
        try:
            # Convert file content to text
            text_content = file_content.decode('utf-8')
            
            # Initialize Claude client
            claude_client = ClaudeClient()
            
            # Extract information using Claude
            extracted_info = await claude_client.extract_resume_info(text_content)
            
            return extracted_info
            
        except Exception as e:
            logger.error(f"Error processing resume: {str(e)}")
            raise

async def process_resume(file_content: bytes, file_extension: str) -> Dict[str, Any]:
    """
    Process resume and extract information using Claude API.
    
    Args:
        file_content: Resume file content in bytes
        file_extension: File extension (with dot)
        
    Returns:
        Dict with extracted resume information
    """
    try:
        # Read sample JSON structure
        with open("assets/json/CV_sample.json", "r", encoding='utf-8') as f:
            sample_json = json.load(f)
        
        # Create prompt for Claude
        prompt = f"""
        Analyze the provided resume and extract information in JSON format.
        Use the following structure, but include only fields that have information in the resume:
        {json.dumps(sample_json, indent=2, ensure_ascii=False)}
        
        Instructions:
        1. Carefully examine the resume text
        2. Extract only available information, skipping empty fields
        3. Return the result in JSON format
        4. Make sure all strings are properly escaped
        5. Do not add comments or text outside JSON
        6. Use compact format for arrays if they contain simple values
        """
        
        logger.info("Starting resume processing")
        
        # Initialize Claude client
        client = ClaudeClient()
        
        # Analyze resume
        result = await client.analyze_file(file_content, file_extension, prompt)
        
        # Extract JSON from response
        content = result.get("content", [{}])[0].get("text", "")
        logger.debug(f"Raw response from Claude: {content}")
        
        # Find JSON in response, skipping any text before and after
        start = content.find("{")
        end = content.rfind("}") + 1
        if start == -1 or end == 0:
            logger.error("Could not find JSON in response")
            raise ValueError("Could not find JSON in response")
            
        json_str = content[start:end]
        logger.debug(f"Extracted JSON: {json_str}")
        
        try:
            result = json.loads(json_str)
        except json.JSONDecodeError as e:
            # Try to clean string from invisible characters
            json_str = "".join(char for char in json_str if ord(char) >= 32)
            try:
                result = json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON: {str(e)}")
                logger.error(f"Problematic JSON: {json_str}")
                raise ValueError(f"Error parsing JSON: {str(e)}")
        
        # Check result structure
        if not isinstance(result, dict):
            raise ValueError("Result is not a dictionary")
            
        # Add metadata
        if "metadata" not in result:
            result["metadata"] = {}
            
        result["metadata"]["source"] = {
            "type": "upload",
            "uploaded_at": datetime.utcnow().isoformat()
        }
        
        logger.info("Resume processed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Error processing resume: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process resume: {str(e)}"
        ) 