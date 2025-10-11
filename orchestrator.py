from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from models import (
    UserInfo,
    ChatMessage,
    ExtractedParameters,
    ToolSelection,
    NoteMakerRequest,
    FlashcardRequest,
    ConceptExplainerRequest,
    OrchestratorResponse,
)
from parameter_extractor import ParameterExtractor
from tools import EducationalToolClient
import logging

logger = logging.getLogger(__name__)


# state definition


class OrchestratorState(TypedDict):
    """
    State object that flows through the LangGraph workflow
    This is the "memory" of our orchestration process
    """

    # Input
    message: str
    user_info: UserInfo
    chat_history: list[ChatMessage]

    # Extracted data
    extracted_parameters: ExtractedParameters | None

    # Tool execution
    tool_request: dict | None
    tool_response: dict | None

    # Output
    final_response: OrchestratorResponse | None
    error: str | None

    # Control flow
    needs_clarification: bool
    clarification_questions: list[str]


# orchestrator class


class AITutorOrchestrator:
    """
    Main orchestrator that coordinates parameter extraction and tool execution
    Uses LangGraph for workflow management
    """

    def __init__(
        self,
        parameter_extractor: ParameterExtractor,
        tool_client: EducationalToolClient,
    ):
        """
        Initialize orchestrator

        Args:
            parameter_extractor: ParameterExtractor instance
            tool_client: EducationalToolClient instance
        """
        self.parameter_extractor = parameter_extractor
        self.tool_client = tool_client

        # Build the workflow graph
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        """
        Build LangGraph workflow

        Workflow steps:
        1. analyze_message: Extract parameters from conversation
        2. validate_parameters: Check if we have everything needed
        3. route_to_tool: Decide which tool to call (or if clarification needed)
        4. execute_tool: Make API call to selected tool
        5. format_response: Create final response for user
        """
        workflow = StateGraph(OrchestratorState)

        # Add nodes (steps in the workflow)
        workflow.add_node("analyze_message", self.analyze_message)
        workflow.add_node("validate_parameters", self.validate_parameters)
        workflow.add_node("execute_note_maker", self.execute_note_maker)
        workflow.add_node(
            "execute_flashcard_generator", self.execute_flashcard_generator
        )
        workflow.add_node("execute_concept_explainer", self.execute_concept_explainer)
        workflow.add_node("handle_no_tool", self.handle_no_tool)
        workflow.add_node("format_response", self.format_response)
        workflow.add_node("handle_error", self.handle_error)

        # Define edges (flow between steps)
        workflow.set_entry_point("analyze_message")

        workflow.add_edge("analyze_message", "validate_parameters")

        # Conditional routing based on validation
        workflow.add_conditional_edges(
            "validate_parameters",
            self.route_after_validation,
            {
                "note_maker": "execute_note_maker",
                "flashcard_generator": "execute_flashcard_generator",
                "concept_explainer": "execute_concept_explainer",
                "no_tool": "handle_no_tool",
                "needs_clarification": "format_response",
                "error": "handle_error",
            },
        )

        # All tool executions go to format_response
        workflow.add_edge("execute_note_maker", "format_response")
        workflow.add_edge("execute_flashcard_generator", "format_response")
        workflow.add_edge("execute_concept_explainer", "format_response")
        workflow.add_edge("handle_no_tool", "format_response")
        workflow.add_edge("handle_error", "format_response")

        # Final step
        workflow.add_edge("format_response", END)

        return workflow.compile()

    # workflow nodes (Steps)

    def analyze_message(self, state: OrchestratorState) -> OrchestratorState:

        logger.info("Step 1: Analyzing message...")

        try:
            extracted = self.parameter_extractor.extract(
                message=state["message"],
                user_info=state["user_info"],
                chat_history=state["chat_history"],
            )

            # Apply validation and defaults
            extracted = self.parameter_extractor.validate_and_fill_defaults(
                extracted, state["user_info"]
            )

            state["extracted_parameters"] = extracted
            logger.info(
                f"Extracted tool: {extracted.tool_needed}, confidence: {extracted.confidence}"
            )

        except Exception as e:
            logger.error(f"Parameter extraction failed: {str(e)}")
            state["error"] = f"Failed to analyze message: {str(e)}"

        return state

    def validate_parameters(self, state: OrchestratorState) -> OrchestratorState:

        logger.info("Step 2: Validating parameters...")

        extracted = state["extracted_parameters"]

        if not extracted:
            state["error"] = "No parameters extracted"
            return state

        # Check if clarification is needed
        if extracted.missing_parameters:
            state["needs_clarification"] = True
            state["clarification_questions"] = self._generate_clarification_questions(
                extracted
            )
            logger.info(f"Clarification needed: {extracted.missing_parameters}")
        else:
            state["needs_clarification"] = False
            logger.info("All parameters validated successfully")

        return state

    def route_after_validation(self, state: OrchestratorState) -> str:
        # Conditional routing: decide which node to go to next
        if state.get("error"):
            return "error"

        if state.get("needs_clarification"):
            return "needs_clarification"

        extracted = state["extracted_parameters"]

        if extracted.tool_needed == ToolSelection.NOTE_MAKER:
            return "note_maker"
        elif extracted.tool_needed == ToolSelection.FLASHCARD_GENERATOR:
            return "flashcard_generator"
        elif extracted.tool_needed == ToolSelection.CONCEPT_EXPLAINER:
            return "concept_explainer"
        else:
            return "no_tool"

    async def execute_note_maker(self, state: OrchestratorState) -> OrchestratorState:
        # Execute Note Maker tool
        logger.info("Step 3a: Executing Note Maker...")

        try:
            extracted = state["extracted_parameters"]

            # Build request
            request = NoteMakerRequest(
                user_info=state["user_info"],
                chat_history=state["chat_history"],
                topic=extracted.topic,
                subject=extracted.subject or extracted.topic or "General",
                note_taking_style=extracted.note_taking_style,
                include_examples=extracted.include_examples,
                include_analogies=extracted.include_analogies,
            )

            # Call tool
            response = await self.tool_client.call_note_maker(request)

            state["tool_request"] = request.model_dump()
            state["tool_response"] = response.model_dump()
            logger.info("Note Maker executed successfully")

        except Exception as e:
            logger.error(f"Note Maker execution failed: {str(e)}")
            state["error"] = f"Tool execution failed: {str(e)}"

        return state

    async def execute_flashcard_generator(
        self, state: OrchestratorState
    ) -> OrchestratorState:
        # Execute Flashcard Generator tool
        logger.info("Step 3b: Executing Flashcard Generator...")

        try:
            extracted = state["extracted_parameters"]

            # Build request
            request = FlashcardRequest(
                user_info=state["user_info"],
                topic=extracted.topic,
                count=extracted.flashcard_count,
                difficulty=extracted.difficulty,
                subject=extracted.subject or extracted.topic or "General",
                include_examples=extracted.include_examples,
            )

            # Call tool
            response = await self.tool_client.call_flashcard_generator(request)

            state["tool_request"] = request.model_dump()
            state["tool_response"] = response.model_dump()
            logger.info("Flashcard Generator executed successfully")

        except Exception as e:
            logger.error(f"Flashcard Generator execution failed: {str(e)}")
            state["error"] = f"Tool execution failed: {str(e)}"

        return state

    async def execute_concept_explainer(
        self, state: OrchestratorState
    ) -> OrchestratorState:
        # Execute Concept Explainer tool
        logger.info("Step 3c: Executing Concept Explainer...")

        try:
            extracted = state["extracted_parameters"]

            # Build request
            request = ConceptExplainerRequest(
                user_info=state["user_info"],
                chat_history=state["chat_history"],
                concept_to_explain=extracted.concept_to_explain or extracted.topic,
                current_topic=extracted.subject or extracted.topic,
                desired_depth=extracted.desired_depth,
            )

            # Call tool
            response = await self.tool_client.call_concept_explainer(request)

            state["tool_request"] = request.model_dump()
            state["tool_response"] = response.model_dump()
            logger.info("Concept Explainer executed successfully")

        except Exception as e:
            logger.error(f"Concept Explainer execution failed: {str(e)}")
            state["error"] = f"Tool execution failed: {str(e)}"

        return state

    def handle_no_tool(self, state: OrchestratorState) -> OrchestratorState:
        #  Handle case where no tool is needed (general conversation)
        logger.info("No tool needed - general conversation")
        state["tool_response"] = {
            "message": "I'm here to help! Feel free to ask about concepts, request notes, or practice with flashcards."
        }
        return state

    def handle_error(self, state: OrchestratorState) -> OrchestratorState:
        """
        Handle errors gracefully
        """
        logger.error(f"Error in workflow: {state.get('error')}")
        return state

    def format_response(self, state: OrchestratorState) -> OrchestratorState:
        # Format final response for user
        logger.info("Step 4: Formatting response...")

        extracted = state.get("extracted_parameters")

        if state.get("error"):
            # Error response
            state["final_response"] = OrchestratorResponse(
                success=False,
                tool_used="none",
                extracted_parameters={},
                tool_response={},
                message=f"Sorry, something went wrong: {state['error']}",
                needs_clarification=False,
            )

        elif state.get("needs_clarification"):
            # Clarification needed
            state["final_response"] = OrchestratorResponse(
                success=False,
                tool_used="none",
                extracted_parameters=extracted.model_dump() if extracted else {},
                tool_response={},
                message="I need a bit more information to help you better.",
                needs_clarification=True,
                clarification_questions=state["clarification_questions"],
            )

        else:
            # Success response
            tool_name = extracted.tool_needed.value if extracted else "none"
            message = self._generate_success_message(tool_name, state["tool_response"])

            state["final_response"] = OrchestratorResponse(
                success=True,
                tool_used=tool_name,
                extracted_parameters=extracted.model_dump() if extracted else {},
                tool_response=state["tool_response"] or {},
                message=message,
                needs_clarification=False,
            )

        logger.info("Response formatted successfully")
        return state

    # HELPER METHODS

    def _generate_clarification_questions(
        self, extracted: ExtractedParameters
    ) -> list[str]:
        # Generate clarification questions for missing parameters
        questions = []

        for param in extracted.missing_parameters:
            if param == "topic":
                questions.append("What specific topic would you like to focus on?")
            elif param == "subject":
                questions.append("Which subject area does this relate to?")
            elif param == "difficulty":
                questions.append(
                    "What difficulty level would you prefer? (easy, medium, or hard)"
                )
            elif param == "count":
                questions.append("How many flashcards would you like? (1-20)")

        return questions or ["Could you provide more details about what you need?"]

    def _generate_success_message(self, tool_name: str, tool_response: dict) -> str:
        # Generate human-friendly success message
        if tool_name == "note_maker":
            return f"I've created structured notes on **{tool_response.get('topic')}** for you! Check out the sections below."

        elif tool_name == "flashcard_generator":
            count = len(tool_response.get("flashcards", []))
            topic = tool_response.get("topic")
            return f"I've generated **{count} flashcards** on {topic} to help you practice!"

        elif tool_name == "concept_explainer":
            return f"Here's an explanation of the concept you asked about. Let me know if you need more detail!"

        else:
            return "I'm here to help! What would you like to learn about?"

    # PUBLIC API

    async def orchestrate(
        self, message: str, user_info: UserInfo, chat_history: list[ChatMessage] = None
    ) -> OrchestratorResponse:
        """
        Main orchestration method - this is what external code calls

        Args:
            message: Student's current message
            user_info: Student profile
            chat_history: Recent conversation

        Returns:
            OrchestratorResponse with tool output or clarification request
        """
        logger.info(f"Orchestrating request for user: {user_info.user_id}")

        # Initialize state
        initial_state: OrchestratorState = {
            "message": message,
            "user_info": user_info,
            "chat_history": chat_history or [],
            "extracted_parameters": None,
            "tool_request": None,
            "tool_response": None,
            "final_response": None,
            "error": None,
            "needs_clarification": False,
            "clarification_questions": [],
        }

        # Run workflow
        final_state = await self.workflow.ainvoke(initial_state)

        return final_state["final_response"]
