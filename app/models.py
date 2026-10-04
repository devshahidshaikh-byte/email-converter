from typing import List, Optional
from pydantic import BaseModel, Field

class GenerateRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    domains: List[str] = Field(..., min_length=1, max_length=50)
    selected_patterns: Optional[List[str]] = None
    custom_patterns: Optional[List[str]] = None
    prefixes: Optional[List[str]] = None
    suffixes: Optional[List[str]] = None
    numbers: Optional[List[str]] = None
    case_mode: str = "lowercase"

class CustomPatternRequest(BaseModel):
    first_name: str
    last_name: str
    domain: str
    pattern: str
