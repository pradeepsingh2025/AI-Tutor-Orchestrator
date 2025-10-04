"""
Parameter Extraction Engine
Uses LLM to analyze conversation and extract tool parameters
"""
import json
from typing import List
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from models import (
    ExtractedParameters, 
    ChatMessage, 
    UserInfo,
    ToolSelection
)


class ParameterExtractor:
    """
    Analyzes student messages and extracts parameters for educational tools
    This is the "intelligence" of our orchestrator
    """
    
    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.1):
        """
        Initialize with LLM
        
        Args:
            model_name: OpenAI model to use (gpt-4 recommended for accuracy)
            temperature: Lower = more deterministic (0.1 is good for extraction)
        """
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
        self.output_parser = PydanticOutputParser(pydantic_object=ExtractedParameters)
        
    def extract(
        self, 
        message: str, 
        user_info: UserInfo,
        chat_history: List[ChatMessage]
    ) -> ExtractedParameters:
        """
        Main extraction method
        
        Args:
            message: Current student message
            user_info: Student profile
            chat_history: Recent conversation
            
        Returns:
            ExtractedParameters with tool selection and parameters
        """
        prompt = self._build_extraction_prompt(message, user_info, chat_history)
        
        # Call LLM
        response = self.llm.invoke(prompt)
        
        # Parse into structured format
        try:
            extracted = self.output_parser.parse(response.content)
            return extracted
        except Exception as e:
            # Fallback if parsing fails
            return ExtractedParameters(
                tool_needed=ToolSelection.NONE,
                confidence=0.0,
                reasoning=f"Failed to parse LLM response: {str(e)}",
                missing_parameters=["all"]
            )
    
    def _build_extraction_prompt(
        self,
        message: str,
        user_info: UserInfo,
        chat_history: List[ChatMessage]
    ) -> str:
        """Build the prompt for the LLM"""
        
        # Format chat history
        history_text = "\n".join([
            f"{msg.role.upper()}: {msg.content}" 
            for msg in chat_history[-5:]  # Last 5 messages for context
        ])
        
        prompt_template = ChatPromptTemplate.from_template("""
You are an intelligent parameter extraction system for an AI tutor orchestrator.
Your job is to analyze student messages and determine:
1. Which educational tool is needed (if any)
2. What parameters to extract from the conversation
3. What information is missing and needs clarification

AVAILABLE TOOLS:
- note_maker: Creates structured study notes on a topic
- flashcard_generator: Creates practice flashcards
- concept_explainer: Explains specific concepts in detail
- none: No tool needed (just conversation)

STUDENT PROFILE:
Name: {name}
Grade Level: {grade_level}
Learning Style: {learning_style}
Emotional State: {emotional_state}
Mastery Level: {mastery_level}

CONVERSATION HISTORY:
{chat_history}

CURRENT MESSAGE:
{message}

EXTRACTION RULES:

1. **Tool Selection Logic**:
   - "I need notes on..." or "help me summarize..." → note_maker
   - "I need practice" or "quiz me" or "flashcards" → flashcard_generator
   - "What is..." or "explain..." or "I don't understand..." → concept_explainer
   - General chat, greetings, off-topic → none

2. **Parameter Inference**:
   - Topic/Subject: Extract from message (e.g., "derivatives" from "help with derivatives")
   - Difficulty: Infer from mastery level and emotional state:
     * Mastery Level 1-3 OR "struggling/confused" → easy
     * Mastery Level 4-6 OR neutral → medium
     * Mastery Level 7-10 OR "confident/advanced" → hard
   - Count (flashcards): Default 5, or extract if mentioned ("10 questions")
   - Note style: Default "outline", use "bullet_points" if mentioned
   - Depth: Infer from question complexity:
     * "What is X?" → basic
     * "Explain X" → intermediate
     * "Deep dive into X" or "comprehensive" → advanced/comprehensive

3. **Personalization Adaptation**:
   - If emotional_state contains "anxious/confused" → prefer easier difficulty
   - If learning_style mentions "visual" → set include_examples=true, include_analogies=true
   - If mastery_level is low → prefer "basic" depth

4. **Missing Parameters**:
   - If topic/subject unclear, add to missing_parameters
   - If tool needs specific info not in message, note it

{format_instructions}

Respond ONLY with valid JSON matching the schema. Be precise and confident.
""")
        
        prompt = prompt_template.format(
            name=user_info.name,
            grade_level=user_info.grade_level,
            learning_style=user_info.learning_style_summary,
            emotional_state=user_info.emotional_state_summary,
            mastery_level=user_info.mastery_level_summary,
            chat_history=history_text if history_text else "No previous messages",
            message=message,
            format_instructions=self.output_parser.get_format_instructions()
        )
        
        return prompt
    
    def validate_and_fill_defaults(
        self, 
        extracted: ExtractedParameters,
        user_info: UserInfo
    ) -> ExtractedParameters:
        """
        Validate extracted parameters and fill in smart defaults
        
        This method ensures all required parameters are present
        """
        
        # If no tool needed, return as-is
        if extracted.tool_needed == ToolSelection.NONE:
            return extracted
        
        # Fill defaults based on tool type
        if extracted.tool_needed == ToolSelection.NOTE_MAKER:
            if not extracted.note_taking_style:
                # Default based on learning style
                if "visual" in user_info.learning_style_summary.lower():
                    extracted.note_taking_style = "structured"
                else:
                    extracted.note_taking_style = "outline"
            
            # Visual learners get more examples/analogies
            if "visual" in user_info.learning_style_summary.lower():
                extracted.include_examples = True
                extracted.include_analogies = True
        
        elif extracted.tool_needed == ToolSelection.FLASHCARD_GENERATOR:
            if not extracted.flashcard_count:
                extracted.flashcard_count = 5  # Safe default
            
            if not extracted.difficulty:
                # Infer from mastery level
                mastery_num = self._extract_mastery_number(user_info.mastery_level_summary)
                if mastery_num <= 3:
                    extracted.difficulty = "easy"
                elif mastery_num <= 6:
                    extracted.difficulty = "medium"
                else:
                    extracted.difficulty = "hard"
        
        elif extracted.tool_needed == ToolSelection.CONCEPT_EXPLAINER:
            if not extracted.desired_depth:
                # Infer from mastery level
                mastery_num = self._extract_mastery_number(user_info.mastery_level_summary)
                if mastery_num <= 3:
                    extracted.desired_depth = "basic"
                elif mastery_num <= 6:
                    extracted.desired_depth = "intermediate"
                else:
                    extracted.desired_depth = "advanced"
        
        return extracted
    
    def _extract_mastery_number(self, mastery_summary: str) -> int:
        """Extract numeric mastery level from summary"""
        import re
        match = re.search(r'Level (\d+)', mastery_summary)
        if match:
            return int(match.group(1))
        return 5  # Default middle level


# ============================================================================
# HELPER FUNCTION FOR QUICK TESTING
# ============================================================================

async def test_extraction():
    """Test the parameter extractor"""
    extractor = ParameterExtractor()
    
    # Test case
    user_info = UserInfo(
        user_id="test123",
        name="Alice",
        grade_level="10",
        learning_style_summary="Visual learner, prefers diagrams and examples",
        emotional_state_summary="Slightly anxious but motivated",
        mastery_level_summary="Level 5 - Developing competence"
    )
    
    message = "I'm struggling with calculus derivatives and need some practice problems"
    
    result = extractor.extract(message, user_info, [])
    
    print("Extracted Parameters:")
    print(f"Tool: {result.tool_needed}")
    print(f"Confidence: {result.confidence}")
    print(f"Topic: {result.topic}")
    print(f"Subject: {result.subject}")
    print(f"Difficulty: {result.difficulty}")
    print(f"Reasoning: {result.reasoning}")
    
    return result


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_extraction())