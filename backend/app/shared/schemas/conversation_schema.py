from pydantic import BaseModel, Field
from typing import List, Optional


class QuestionDefinition(BaseModel):
    sequence: int
    type: str = "question"  # "question" | "instruction"
    text: str
    expected_context: str


class ConversationDefinitionSchema(BaseModel):
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = "1.0"
    intro_line: str
    questions: List[QuestionDefinition]
