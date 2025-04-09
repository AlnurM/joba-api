from pydantic import BaseModel
from typing import List

class JobQueryGenerateRequest(BaseModel):
    resume_id: str

class JobQueryKeywords(BaseModel):
    job_titles: List[str]
    required_skills: List[str]
    work_arrangements: List[str]
    positions: List[str]
    exclude_words: List[str]

class JobQueryResponse(BaseModel):
    keywords: JobQueryKeywords 