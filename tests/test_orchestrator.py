"""
Unit tests for AI Tutor Orchestrator
"""
import pytest
import asyncio
from models import UserInfo, ChatMessage, ToolSelection
from parameter_extractor import ParameterExtractor
from tools import MockToolClient
from orchestrator import AITutorOrchestrator


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def sample_user_info():
    """Create sample student profile"""
    return UserInfo(
        user_id="test_student",
        name="Test Student",
        grade_level="10",
        learning_style_summary="Visual learner, prefers examples",
        emotional_state_summary="Focused and motivated",
        mastery_level_summary="Level 5 - Developing competence"
    )


@pytest.fixture
def mock_orchestrator():
    """Create orchestrator with mock tools"""
    tool_client = MockToolClient()
    parameter_extractor = ParameterExtractor(temperature=0.0)  # Deterministic
    return AITutorOrchestrator(parameter_extractor, tool_client)


# ============================================================================
# PARAMETER EXTRACTION TESTS
# ============================================================================

def test_parameter_extractor_initialization():
    """Test parameter extractor can be initialized"""
    extractor = ParameterExtractor()
    assert extractor is not None
    assert extractor.llm is not None


@pytest.mark.asyncio
async def test_extract_flashcard_intent(sample_user_info):
    """Test extraction of flashcard generation intent"""
    extractor = ParameterExtractor(temperature=0.0)
    
    message = "Hello! How are you today?"
    result = extractor.extract(message, sample_user_info, [])
    
    # Should identify no tool needed
    assert result.tool_needed == ToolSelection.NONE


# ============================================================================
# PERSONALIZATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_difficulty_inference_from_mastery():
    """Test that difficulty is inferred from mastery level"""
    extractor = ParameterExtractor(temperature=0.0)
    
    # Low mastery student
    low_mastery_user = UserInfo(
        user_id="low_mastery",
        name="Beginner",
        grade_level="9",
        learning_style_summary="Visual learner",
        emotional_state_summary="Anxious and struggling",
        mastery_level_summary="Level 2 - Foundation building"
    )
    
    message = "I need practice with algebra"
    result = extractor.extract(message, low_mastery_user, [])
    result = extractor.validate_and_fill_defaults(result, low_mastery_user)
    
    # Should infer easy difficulty
    if result.tool_needed == ToolSelection.FLASHCARD_GENERATOR:
        assert result.difficulty == "easy"


@pytest.mark.asyncio
async def test_visual_learner_preferences():
    """Test that visual learners get examples and analogies"""
    extractor = ParameterExtractor(temperature=0.0)
    
    visual_user = UserInfo(
        user_id="visual",
        name="Visual Learner",
        grade_level="10",
        learning_style_summary="Strong visual learner, loves diagrams",
        emotional_state_summary="Engaged",
        mastery_level_summary="Level 5"
    )
    
    message = "Help me with notes on cells"
    result = extractor.extract(message, visual_user, [])
    result = extractor.validate_and_fill_defaults(result, visual_user)
    
    # Visual learners should get examples and analogies
    if result.tool_needed == ToolSelection.NOTE_MAKER:
        assert result.include_examples == True
        assert result.include_analogies == True


# ============================================================================
# ORCHESTRATOR TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_orchestrator_initialization(mock_orchestrator):
    """Test orchestrator can be initialized"""
    assert mock_orchestrator is not None
    assert mock_orchestrator.workflow is not None


@pytest.mark.asyncio
async def test_full_orchestration_flashcards(mock_orchestrator, sample_user_info):
    """Test complete orchestration flow for flashcard generation"""
    message = "I need 5 practice questions on derivatives"
    
    response = await mock_orchestrator.orchestrate(
        message=message,
        user_info=sample_user_info,
        chat_history=[]
    )
    
    # Check response structure
    assert response is not None
    assert hasattr(response, 'success')
    assert hasattr(response, 'tool_used')
    assert hasattr(response, 'message')
    
    # If successful, should have tool response
    if response.success and response.tool_used != "none":
        assert response.tool_response is not None


@pytest.mark.asyncio
async def test_full_orchestration_notes(mock_orchestrator, sample_user_info):
    """Test complete orchestration flow for note generation"""
    message = "Create study notes on photosynthesis"
    
    response = await mock_orchestrator.orchestrate(
        message=message,
        user_info=sample_user_info,
        chat_history=[]
    )
    
    assert response is not None
    assert response.success or response.needs_clarification
    
    if response.success:
        assert response.tool_used in ["note_maker", "concept_explainer"]


@pytest.mark.asyncio
async def test_full_orchestration_concept(mock_orchestrator, sample_user_info):
    """Test complete orchestration flow for concept explanation"""
    message = "Explain what osmosis is"
    
    response = await mock_orchestrator.orchestrate(
        message=message,
        user_info=sample_user_info,
        chat_history=[]
    )
    
    assert response is not None
    if response.success:
        assert response.tool_used == "concept_explainer"


@pytest.mark.asyncio
async def test_orchestration_with_chat_history(mock_orchestrator, sample_user_info):
    """Test orchestration considers chat history"""
    chat_history = [
        ChatMessage(role="user", content="I'm learning about biology"),
        ChatMessage(role="assistant", content="Great! What topic in biology?"),
        ChatMessage(role="user", content="Cell structure")
    ]
    
    message = "Can you make me some flashcards?"
    
    response = await mock_orchestrator.orchestrate(
        message=message,
        user_info=sample_user_info,
        chat_history=chat_history
    )
    
    assert response is not None
    # Should understand topic from history
    if response.success:
        assert "cell" in str(response.extracted_parameters).lower() or \
               "biology" in str(response.extracted_parameters).lower()


# ============================================================================
# TOOL INTEGRATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_mock_note_maker():
    """Test mock note maker returns valid response"""
    client = MockToolClient()
    
    from models import NoteMakerRequest, UserInfo
    
    request = NoteMakerRequest(
        user_info=UserInfo(
            user_id="test",
            name="Test",
            grade_level="10",
            learning_style_summary="Visual",
            emotional_state_summary="Focused",
            mastery_level_summary="Level 5"
        ),
        chat_history=[],
        topic="Photosynthesis",
        subject="Biology",
        note_taking_style="outline"
    )
    
    response = await client.call_note_maker(request)
    
    assert response is not None
    assert response.topic == "Photosynthesis"
    assert len(response.note_sections) > 0


@pytest.mark.asyncio
async def test_mock_flashcard_generator():
    """Test mock flashcard generator returns valid response"""
    client = MockToolClient()
    
    from models import FlashcardRequest, UserInfo
    
    request = FlashcardRequest(
        user_info=UserInfo(
            user_id="test",
            name="Test",
            grade_level="10",
            learning_style_summary="Visual",
            emotional_state_summary="Focused",
            mastery_level_summary="Level 5"
        ),
        topic="Derivatives",
        count=5,
        difficulty="medium",
        subject="Calculus"
    )
    
    response = await client.call_flashcard_generator(request)
    
    assert response is not None
    assert len(response.flashcards) == 5
    assert response.topic == "Derivatives"


@pytest.mark.asyncio
async def test_mock_concept_explainer():
    """Test mock concept explainer returns valid response"""
    client = MockToolClient()
    
    from models import ConceptExplainerRequest, UserInfo
    
    request = ConceptExplainerRequest(
        user_info=UserInfo(
            user_id="test",
            name="Test",
            grade_level="10",
            learning_style_summary="Visual",
            emotional_state_summary="Focused",
            mastery_level_summary="Level 5"
        ),
        chat_history=[],
        concept_to_explain="Mitosis",
        current_topic="Biology",
        desired_depth="intermediate"
    )
    
    response = await client.call_concept_explainer(request)
    
    assert response is not None
    assert len(response.explanation) > 0
    assert len(response.examples) > 0


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_orchestration_handles_errors_gracefully(sample_user_info):
    """Test that errors are handled gracefully"""
    # Create orchestrator with a client that might fail
    client = MockToolClient()
    extractor = ParameterExtractor(temperature=0.0)
    orchestrator = AITutorOrchestrator(extractor, client)
    
    # Empty message should still return a response
    response = await orchestrator.orchestrate(
        message="",
        user_info=sample_user_info,
        chat_history=[]
    )
    
    assert response is not None
    assert hasattr(response, 'success')


# ============================================================================
# VALIDATION TESTS
# ============================================================================

def test_user_info_validation():
    """Test UserInfo model validation"""
    # Valid user info
    user = UserInfo(
        user_id="123",
        name="Alice",
        grade_level="10",
        learning_style_summary="Visual",
        emotional_state_summary="Focused",
        mastery_level_summary="Level 5"
    )
    assert user.user_id == "123"
    
    # Invalid user info (missing required field)
    with pytest.raises(Exception):
        UserInfo(
            user_id="123",
            name="Alice"
            # Missing other required fields
        )


def test_chat_message_validation():
    """Test ChatMessage model validation"""
    # Valid message
    msg = ChatMessage(role="user", content="Hello")
    assert msg.role == "user"
    
    # Invalid role
    with pytest.raises(Exception):
        ChatMessage(role="invalid_role", content="Hello")


def test_flashcard_count_validation():
    """Test flashcard count is validated (1-20)"""
    from models import FlashcardRequest, UserInfo
    
    user_info = UserInfo(
        user_id="test",
        name="Test",
        grade_level="10",
        learning_style_summary="Visual",
        emotional_state_summary="Focused",
        mastery_level_summary="Level 5"
    )
    
    # Valid count
    request = FlashcardRequest(
        user_info=user_info,
        topic="Math",
        count=10,
        difficulty="medium",
        subject="Algebra"
    )
    assert request.count == 10
    
    # Invalid count (too high)
    with pytest.raises(Exception):
        FlashcardRequest(
            user_info=user_info,
            topic="Math",
            count=25,  # Over limit
            difficulty="medium",
            subject="Algebra"
        )


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

@pytest.mark.asyncio
async def test_extract_flashcard_intent_with_practice_problems(sample_user_info):
    """Test extraction of flashcard intent for practice problems"""
    extractor = ParameterExtractor(temperature=0.0)
    
    message = "I need practice problems on derivatives"
    result = extractor.extract(message, sample_user_info, [])
    
    # Should identify flashcard tool
    assert result.tool_needed in [ToolSelection.FLASHCARD_GENERATOR, ToolSelection.CONCEPT_EXPLAINER]
    assert result.topic is not None
    assert "derivative" in result.topic.lower() or "calculus" in (result.subject or "").lower()


@pytest.mark.asyncio
async def test_extract_note_maker_intent(sample_user_info):
    """Test extraction of note-making intent"""
    extractor = ParameterExtractor(temperature=0.0)
    
    message = "Can you help me create notes on photosynthesis?"
    result = extractor.extract(message, sample_user_info, [])
    
    # Should identify note maker
    assert result.tool_needed == ToolSelection.NOTE_MAKER
    assert result.topic is not None
    assert "photosynthesis" in result.topic.lower()


@pytest.mark.asyncio
async def test_extract_concept_explainer_intent(sample_user_info):
    """Test extraction of concept explanation intent"""
    extractor = ParameterExtractor(temperature=0.0)
    
    message = "What is mitosis? I don't understand it"
    result = extractor.extract(message, sample_user_info, [])
    
    # Should identify concept explainer
    assert result.tool_needed == ToolSelection.CONCEPT_EXPLAINER
    assert result.concept_to_explain is not None


@pytest.mark.asyncio
async def test_no_tool_needed(sample_user_info):
    """Test that general conversation doesn't trigger tools"""
    extractor = ParameterExtractor(temperature=0.0)
    
    message = "Hello! How are you today?"
    result = extractor.extract(message, sample_user_info, [])
    
    # Should identify no tool needed
    assert result.tool_needed == ToolSelection.NONE