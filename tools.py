"""
Tool Integration Layer
Handles API calls to educational tools with error handling and retries
"""
import httpx
import asyncio
from typing import Optional, Dict, Any
from models import (
    NoteMakerRequest, NoteMakerResponse,
    FlashcardRequest, FlashcardResponse,
    ConceptExplainerRequest, ConceptExplainerResponse
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ToolIntegrationError(Exception):
    """Custom exception for tool integration failures"""
    pass


class EducationalToolClient:
    """
    Client for calling educational tool APIs
    Handles authentication, retries, error handling
    """
    
    def __init__(
        self, 
        note_maker_url: str,
        flashcard_url: str,
        concept_explainer_url: str,
        timeout: float = 30.0,
        max_retries: int = 3
    ):
        """
        Initialize tool client
        
        Args:
            note_maker_url: Note Maker API endpoint
            flashcard_url: Flashcard Generator API endpoint
            concept_explainer_url: Concept Explainer API endpoint
            timeout: Request timeout in seconds
            max_retries: Number of retry attempts
        """
        self.note_maker_url = note_maker_url
        self.flashcard_url = flashcard_url
        self.concept_explainer_url = concept_explainer_url
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Create async HTTP client
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def call_note_maker(
        self, 
        request: NoteMakerRequest
    ) -> NoteMakerResponse:
        """
        Call Note Maker tool
        
        Args:
            request: Validated NoteMakerRequest
            
        Returns:
            NoteMakerResponse with generated notes
            
        Raises:
            ToolIntegrationError: If API call fails
        """
        logger.info(f"Calling Note Maker for topic: {request.topic}")
        
        try:
            response_data = await self._make_request(
                url=self.note_maker_url,
                payload=request.model_dump()
            )
            
            # Parse response
            return NoteMakerResponse(**response_data)
        
        except Exception as e:
            logger.error(f"Note Maker call failed: {str(e)}")
            raise ToolIntegrationError(f"Note Maker failed: {str(e)}")
    
    async def call_flashcard_generator(
        self, 
        request: FlashcardRequest
    ) -> FlashcardResponse:
        """
        Call Flashcard Generator tool
        
        Args:
            request: Validated FlashcardRequest
            
        Returns:
            FlashcardResponse with generated flashcards
            
        Raises:
            ToolIntegrationError: If API call fails
        """
        logger.info(f"Calling Flashcard Generator for topic: {request.topic}")
        
        try:
            response_data = await self._make_request(
                url=self.flashcard_url,
                payload=request.model_dump()
            )
            
            return FlashcardResponse(**response_data)
        
        except Exception as e:
            logger.error(f"Flashcard Generator call failed: {str(e)}")
            raise ToolIntegrationError(f"Flashcard Generator failed: {str(e)}")
    
    async def call_concept_explainer(
        self, 
        request: ConceptExplainerRequest
    ) -> ConceptExplainerResponse:
        """
        Call Concept Explainer tool
        
        Args:
            request: Validated ConceptExplainerRequest
            
        Returns:
            ConceptExplainerResponse with explanation
            
        Raises:
            ToolIntegrationError: If API call fails
        """
        logger.info(f"Calling Concept Explainer for: {request.concept_to_explain}")
        
        try:
            response_data = await self._make_request(
                url=self.concept_explainer_url,
                payload=request.model_dump()
            )
            
            return ConceptExplainerResponse(**response_data)
        
        except Exception as e:
            logger.error(f"Concept Explainer call failed: {str(e)}")
            raise ToolIntegrationError(f"Concept Explainer failed: {str(e)}")
    
    async def _make_request(
        self, 
        url: str, 
        payload: Dict[str, Any],
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Make HTTP POST request with retry logic
        
        Args:
            url: API endpoint
            payload: Request body
            retry_count: Current retry attempt
            
        Returns:
            Response JSON
            
        Raises:
            ToolIntegrationError: If all retries fail
        """
        try:
            response = await self.client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            # Check status code
            if response.status_code == 200:
                return response.json()
            
            elif response.status_code == 429:  # Rate limit
                if retry_count < self.max_retries:
                    wait_time = 2 ** retry_count  # Exponential backoff
                    logger.warning(f"Rate limited, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    return await self._make_request(url, payload, retry_count + 1)
                else:
                    raise ToolIntegrationError("Rate limit exceeded")
            
            elif response.status_code == 400:
                error_data = response.json()
                raise ToolIntegrationError(f"Bad request: {error_data.get('error', 'Unknown')}")
            
            elif response.status_code >= 500:  # Server error
                if retry_count < self.max_retries:
                    wait_time = 2 ** retry_count
                    logger.warning(f"Server error, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    return await self._make_request(url, payload, retry_count + 1)
                else:
                    raise ToolIntegrationError("Server error after retries")
            
            else:
                raise ToolIntegrationError(f"Unexpected status code: {response.status_code}")
        
        except httpx.TimeoutException:
            if retry_count < self.max_retries:
                logger.warning(f"Request timeout, retrying...")
                return await self._make_request(url, payload, retry_count + 1)
            else:
                raise ToolIntegrationError("Request timeout after retries")
        
        except httpx.RequestError as e:
            raise ToolIntegrationError(f"Network error: {str(e)}")
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# ============================================================================
# MOCK TOOL CLIENT (For Development/Testing)
# ============================================================================

class MockToolClient(EducationalToolClient):
    """
    Mock client that returns dummy data
    Use this for development when real APIs aren't available
    """
    
    def __init__(self):
        """Initialize without real URLs"""
        self.note_maker_url = "mock://note-maker"
        self.flashcard_url = "mock://flashcard"
        self.concept_explainer_url = "mock://concept"
        self.timeout = 1.0
        self.max_retries = 1
    
    async def call_note_maker(self, request: NoteMakerRequest) -> NoteMakerResponse:
        """Return mock notes"""
        logger.info(f"[MOCK] Generating notes for: {request.topic}")
        await asyncio.sleep(0.5)  # Simulate API delay
        
        return NoteMakerResponse(
            topic=request.topic,
            title=f"Study Notes: {request.topic}",
            summary=f"Comprehensive notes on {request.topic} tailored for {request.user_info.name}",
            note_sections=[
                {
                    "title": "Introduction",
                    "content": f"This section covers the basics of {request.topic}.",
                    "key_points": ["Point 1", "Point 2", "Point 3"],
                    "examples": ["Example 1"] if request.include_examples else [],
                    "analogies": ["Analogy 1"] if request.include_analogies else []
                },
                {
                    "title": "Core Concepts",
                    "content": f"Deep dive into {request.topic} fundamentals.",
                    "key_points": ["Concept A", "Concept B"],
                    "examples": ["Example 2"] if request.include_examples else [],
                    "analogies": []
                }
            ],
            key_concepts=[request.topic, f"{request.topic} applications"],
            connections_to_prior_learning=["Related to previous lessons"],
            practice_suggestions=["Try practice problems", "Review examples"],
            source_references=["Textbook Chapter 5"],
            note_taking_style=request.note_taking_style
        )
    
    async def call_flashcard_generator(self, request: FlashcardRequest) -> FlashcardResponse:
        """Return mock flashcards"""
        logger.info(f"[MOCK] Generating {request.count} flashcards for: {request.topic}")
        await asyncio.sleep(0.5)
        
        flashcards = []
        for i in range(request.count):
            flashcards.append({
                "title": f"{request.topic} - Card {i+1}",
                "question": f"What is an important aspect of {request.topic}? (Question {i+1})",
                "answer": f"Answer about {request.topic} that explains concept {i+1}",
                "example": f"Example: {request.topic} in practice" if request.include_examples else None
            })
        
        return FlashcardResponse(
            flashcards=flashcards,
            topic=request.topic,
            adaptation_details=f"Adapted for {request.user_info.name}'s {request.difficulty} level",
            difficulty=request.difficulty
        )
    
    async def call_concept_explainer(self, request: ConceptExplainerRequest) -> ConceptExplainerResponse:
        """Return mock explanation"""
        logger.info(f"[MOCK] Explaining: {request.concept_to_explain}")
        await asyncio.sleep(0.5)
        
        return ConceptExplainerResponse(
            explanation=f"Here's a {request.desired_depth} explanation of {request.concept_to_explain}: "
                       f"This concept is fundamental to {request.current_topic}. "
                       f"It involves understanding the core principles and applying them effectively.",
            examples=[
                f"Example 1 of {request.concept_to_explain}",
                f"Example 2 showing practical application"
            ],
            related_concepts=[
                f"Related concept A",
                f"Related concept B",
                request.current_topic
            ],
            visual_aids=[
                "Diagram showing the relationship",
                "Flowchart of the process"
            ],
            practice_questions=[
                f"Question 1: Apply {request.concept_to_explain} to solve...",
                f"Question 2: Explain how {request.concept_to_explain} works in..."
            ],
            source_references=["Textbook reference", "Online resource"]
        )
    
    async def close(self):
        """No-op for mock client"""
        pass


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_tool_client(use_mock: bool = False) -> EducationalToolClient:
    """
    Factory function to create appropriate tool client
    
    Args:
        use_mock: If True, return MockToolClient for testing
        
    Returns:
        EducationalToolClient instance
    """
    if use_mock:
        return MockToolClient()
    else:
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        return EducationalToolClient(
            note_maker_url=os.getenv("NOTE_MAKER_API_URL", "http://localhost:8001/api/note-maker"),
            flashcard_url=os.getenv("FLASHCARD_API_URL", "http://localhost:8002/api/flashcards"),
            concept_explainer_url=os.getenv("CONCEPT_API_URL", "http://localhost:8003/api/concept-explainer")
        )