"""
Pydantic models for AI Tutor Orchestrator
These models validate all input/output data and match the API specifications
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from enum import Enum


# ============================================================================
# USER CONTEXT MODELS
# ============================================================================


class UserInfo(BaseModel):
    """Student profile information - required by all tools"""

    user_id: str = Field(..., description="Unique identifier for the student")
    name: str = Field(..., description="Student's full name")
    grade_level: str = Field(..., description="Student's current grade level")
    learning_style_summary: str = Field(
        ..., description="Summary of student's preferred learning style"
    )
    emotional_state_summary: str = Field(
        ..., description="Current emotional state of the student"
    )
    mastery_level_summary: str = Field(
        ..., description="Current mastery level description"
    )


class ChatMessage(BaseModel):
    """Individual chat message in conversation history"""

    role: Literal["user", "assistant"] = Field(..., description="Role of sender")
    content: str = Field(..., description="Message content")


# ============================================================================
# INCOMING REQUEST MODELS
# ============================================================================


class OrchestrateRequest(BaseModel):
    """Main request to the orchestrator endpoint"""

    message: str = Field(..., description="Current student message")
    user_info: UserInfo = Field(..., description="Student profile")
    chat_history: List[ChatMessage] = Field(
        default_factory=list, description="Recent conversation history"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "I'm struggling with calculus derivatives",
                "user_info": {
                    "user_id": "student123",
                    "name": "Alice",
                    "grade_level": "11",
                    "learning_style_summary": "Visual learner, prefers diagrams",
                    "emotional_state_summary": "Slightly anxious but motivated",
                    "mastery_level_summary": "Level 5 - Developing competence",
                },
                "chat_history": [
                    {"role": "user", "content": "Can you help me with math?"},
                    {"role": "assistant", "content": "Of course! What topic?"},
                ],
            }
        }


# ============================================================================
# TOOL-SPECIFIC REQUEST MODELS (what we send to educational APIs)
# ============================================================================


class NoteMakerRequest(BaseModel):
    """Request model for Note Maker tool"""

    user_info: UserInfo
    chat_history: List[ChatMessage]
    topic: str
    subject: str
    note_taking_style: Literal["outline", "bullet_points", "narrative", "structured"]
    include_examples: bool = True
    include_analogies: bool = False


class FlashcardRequest(BaseModel):
    """Request model for Flashcard Generator tool"""

    user_info: UserInfo
    topic: str
    count: int = Field(..., ge=1, le=20, description="Number of flashcards (1-20)")
    difficulty: Literal["easy", "medium", "hard"]
    subject: str
    include_examples: bool = True


class ConceptExplainerRequest(BaseModel):
    """Request model for Concept Explainer tool"""

    user_info: UserInfo
    chat_history: List[ChatMessage]
    concept_to_explain: str
    current_topic: str
    desired_depth: Literal["basic", "intermediate", "advanced", "comprehensive"]


# ============================================================================
# TOOL RESPONSE MODELS
# ============================================================================


class NoteSection(BaseModel):
    """Individual section in generated notes"""

    title: str
    content: str
    key_points: List[str] = []
    examples: List[str] = []
    analogies: List[str] = []


class NoteMakerResponse(BaseModel):
    """Response from Note Maker tool"""

    topic: str
    title: str
    summary: str
    note_sections: List[NoteSection]
    key_concepts: List[str]
    connections_to_prior_learning: List[str]
    practice_suggestions: List[str]
    source_references: List[str] = []
    note_taking_style: str


class Flashcard(BaseModel):
    """Individual flashcard"""

    title: str
    question: str
    answer: str
    example: Optional[str] = None


class FlashcardResponse(BaseModel):
    """Response from Flashcard Generator tool"""

    flashcards: List[Flashcard]
    topic: str
    adaptation_details: str
    difficulty: str


class ConceptExplainerResponse(BaseModel):
    """Response from Concept Explainer tool"""

    explanation: str
    examples: List[str]
    related_concepts: List[str]
    visual_aids: List[str]
    practice_questions: List[str]
    source_references: List[str] = []


# ============================================================================
# PARAMETER EXTRACTION MODELS (LLM output)
# ============================================================================


class ToolSelection(str, Enum):
    """Available educational tools"""

    NOTE_MAKER = "note_maker"
    FLASHCARD_GENERATOR = "flashcard_generator"
    CONCEPT_EXPLAINER = "concept_explainer"
    NONE = "none"  # When no tool is needed


class ExtractedParameters(BaseModel):
    """Parameters extracted from conversation by LLM"""

    tool_needed: ToolSelection
    confidence: float = Field(..., ge=0.0, le=1.0)

    # Common parameters
    topic: Optional[str] = None
    subject: Optional[str] = None

    # Note Maker specific
    note_taking_style: Optional[
        Literal["outline", "bullet_points", "narrative", "structured"]
    ] = None
    include_examples: bool = True
    include_analogies: bool = False

    # Flashcard specific
    flashcard_count: Optional[int] = Field(None, ge=1, le=20)
    difficulty: Optional[Literal["easy", "medium", "hard"]] = None

    # Concept Explainer specific
    concept_to_explain: Optional[str] = None
    desired_depth: Optional[
        Literal["basic", "intermediate", "advanced", "comprehensive"]
    ] = None

    # Reasoning
    reasoning: str = Field(
        ..., description="Why this tool and these parameters were chosen"
    )
    missing_parameters: List[str] = Field(
        default_factory=list, description="Parameters that need clarification"
    )


# ============================================================================
# ORCHESTRATOR RESPONSE MODEL
# ============================================================================


class OrchestratorResponse(BaseModel):
    """Final response from orchestrator to client"""

    success: bool
    tool_used: str
    extracted_parameters: dict
    tool_response: dict
    message: str  # Human-friendly message
    needs_clarification: bool = False
    clarification_questions: List[str] = []

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "tool_used": "flashcard_generator",
                "extracted_parameters": {
                    "topic": "derivatives",
                    "subject": "calculus",
                    "difficulty": "medium",
                    "count": 5,
                },
                "tool_response": {"flashcards": [{"question": "...", "answer": "..."}]},
                "message": "I've generated 5 flashcards on calculus derivatives for you!",
                "needs_clarification": False,
            }
        }


# ============================================================================
# ERROR MODELS
# ============================================================================


class ErrorResponse(BaseModel):
    """Standard error response"""

    error: str
    error_code: str
    details: Optional[dict] = None
    suggestions: List[str] = []
