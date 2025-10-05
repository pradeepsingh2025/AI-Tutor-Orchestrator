# AI Tutor Orchestrator - System Architecture

## Overview

The AI Tutor Orchestrator is an intelligent middleware system that sits between conversational AI tutors and educational tools. It autonomously extracts parameters from natural language conversations and orchestrates appropriate tool calls without manual configuration.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Student Layer                            │
│                    (External AI Tutor UI)                        │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               │ HTTP POST /orchestrate
                               │ {message, user_info, chat_history}
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Application                         │
│                         (main.py)                                │
│  ┌────────────────────────────────────────────────────────┐     │
│  │              Endpoint Handlers                          │     │
│  │  • /orchestrate  • /validate  • /health  • /tools      │     │
│  └────────────────────┬───────────────────────────────────┘     │
└───────────────────────┼─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LangGraph Orchestrator                        │
│                     (orchestrator.py)                            │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  State Graph Workflow                     │   │
│  │                                                           │   │
│  │  1. analyze_message                                       │   │
│  │         ↓                                                 │   │
│  │  2. validate_parameters                                   │   │
│  │         ↓                                                 │   │
│  │  3. route_to_tool (conditional)                           │   │
│  │         ├─→ execute_note_maker                            │   │
│  │         ├─→ execute_flashcard_generator                   │   │
│  │         ├─→ execute_concept_explainer                     │   │
│  │         ├─→ handle_no_tool                                │   │
│  │         └─→ handle_clarification                          │   │
│  │         ↓                                                 │   │
│  │  4. format_response                                       │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────┬───────────────────┬────────────────────────┘
                      │                   │
                      ▼                   ▼
         ┌────────────────────┐  ┌──────────────────────┐
         │ ParameterExtractor │  │  ToolIntegrationClient│
         │ (parameter_        │  │    (tools.py)         │
         │  extractor.py)     │  └──────────┬───────────┘
         │                    │             │
         │ ┌────────────────┐ │             │
         │ │   GPT-4 LLM    │ │             │
         │ │  (OpenAI API)  │ │             │
         │ └────────────────┘ │             │
         └────────────────────┘             │
                                            │
                                            ▼
              ┌─────────────────────────────────────────┐
              │    Educational Tool APIs                │
              │                                         │
              │  ┌───────────────┐  ┌────────────────┐ │
              │  │  Note Maker   │  │   Flashcard    │ │
              │  │      API      │  │   Generator    │ │
              │  └───────────────┘  └────────────────┘ │
              │                                         │
              │  ┌───────────────┐                     │
              │  │   Concept     │                     │
              │  │   Explainer   │                     │
              │  └───────────────┘                     │
              └─────────────────────────────────────────┘
```

## Component Details

### 1. FastAPI Application Layer (`main.py`)

**Responsibilities:**
- HTTP endpoint management
- Request/response handling
- Application lifecycle management
- CORS configuration
- Error handling and logging

**Key Endpoints:**
- `POST /orchestrate`: Main orchestration endpoint
- `POST /validate`: Validation-only (no tool execution)
- `GET /health`: Health check
- `GET /tools`: List available tools

**Technology:**
- FastAPI 0.109.0
- Uvicorn ASGI server
- Pydantic for validation

### 2. LangGraph Orchestrator (`orchestrator.py`)

**Responsibilities:**
- Workflow state management
- Conditional routing logic
- Tool selection and execution coordination
- Response formatting

**Workflow States:**
```python
OrchestratorState = {
    message: str,              # Student message
    user_info: UserInfo,       # Student profile
    chat_history: List,        # Conversation history
    extracted_parameters: ExtractedParameters,
    tool_request: dict,        # Request sent to tool
    tool_response: dict,       # Response from tool
    final_response: OrchestratorResponse,
    error: str | None,
    needs_clarification: bool,
    clarification_questions: List[str]
}
```

**Graph Nodes:**
1. **analyze_message**: Extract parameters using LLM
2. **validate_parameters**: Check completeness and apply defaults
3. **route_after_validation**: Conditional routing decision
4. **execute_***: Tool-specific execution nodes
5. **format_response**: Create user-friendly response

**Technology:**
- LangGraph 0.0.20 for workflow management
- Async/await for concurrent operations
- Type-safe state transitions

### 3. Parameter Extractor (`parameter_extractor.py`)

**Responsibilities:**
- Natural language understanding
- Intent classification (which tool?)
- Parameter extraction from conversation
- Intelligent inference for missing parameters
- Personalization based on student context

**Extraction Process:**

```
Input: "I'm struggling with derivatives"
      + UserInfo (mastery_level: 5, emotional_state: anxious)
      
↓ LLM Prompt Engineering ↓

Prompt includes:
• Available tools and their purposes
• Student profile (learning style, emotion, mastery)
• Conversation history
• Extraction rules and examples
• Output schema (JSON)

↓ GPT-4 Processing ↓

Output: {
  tool_needed: "flashcard_generator",
  topic: "derivatives",
  subject: "calculus",
  difficulty: "easy",  ← Inferred from anxiety + low mastery
  count: 5,            ← Default
  confidence: 0.85,
  reasoning: "Student expressed struggle, needs practice"
}
```

**Intelligence Features:**
- **Difficulty Inference**: Maps mastery level + emotional state → difficulty
- **Learning Style Adaptation**: Visual learners get more examples
- **Default Filling**: Smart defaults for missing parameters
- **Validation**: Ensures parameters meet tool schema requirements

**Technology:**
- LangChain 0.1.6
- OpenAI GPT-4 (via langchain-openai)
- Pydantic output parser for structured responses
- Low temperature (0.1) for deterministic extraction

### 4. Tool Integration Layer (`tools.py`)

**Responsibilities:**
- HTTP client management
- API request/response handling
- Retry logic and error handling
- Response parsing and validation
- Mock client for development

**Features:**

**Retry Strategy:**
```python
Attempt 1: Immediate
Attempt 2: Wait 2 seconds (exponential backoff)
Attempt 3: Wait 4 seconds
Attempt 4: Fail with error
```

**Error Handling:**
- **200**: Success → Parse response
- **400**: Bad Request → Return validation error
- **429**: Rate Limit → Retry with backoff
- **500+**: Server Error → Retry
- **Timeout**: Network issue → Retry

**Mock vs Real Client:**
```python
if USE_MOCK_TOOLS:
    client = MockToolClient()  # Returns dummy data
else:
    client = EducationalToolClient(api_urls...)  # Real HTTP calls
```

**Technology:**
- httpx (async HTTP client)
- Exponential backoff algorithm
- Configurable timeouts and retries

### 5. Data Models (`models.py`)

**Responsibilities:**
- Data validation
- Type safety
- Schema enforcement
- Serialization/deserialization

**Key Models:**

```python
UserInfo
├── user_id: str
├── name: str
├── grade_level: str
├── learning_style_summary: str
├── emotional_state_summary: str
└── mastery_level_summary: str

ExtractedParameters
├── tool_needed: ToolSelection (enum)
├── confidence: float (0.0-1.0)
├── topic: Optional[str]
├── subject: Optional[str]
├── difficulty: Optional[Literal["easy", "medium", "hard"]]
├── count: Optional[int] (1-20)
├── reasoning: str
└── missing_parameters: List[str]

OrchestratorResponse
├── success: bool
├── tool_used: str
├── extracted_parameters: dict
├── tool_response: dict
├── message: str (human-friendly)
├── needs_clarification: bool
└── clarification_questions: List[str]
```

**Technology:**
- Pydantic 2.6.0
- Automatic validation
- JSON schema generation

## Data Flow Sequence

### Scenario: Student Requests Flashcards

```
1. Student → API
   POST /orchestrate
   {
     message: "I need practice with derivatives",
     user_info: {...},
     chat_history: [...]
   }

2. FastAPI → Orchestrator
   orchestrate(message, user_info, chat_history)

3. Orchestrator → ParameterExtractor
   extract(message, user_info, chat_history)
   
4. ParameterExtractor → GPT-4
   Prompt: "Analyze this message and extract parameters..."
   
5. GPT-4 → ParameterExtractor
   {
     tool: "flashcard_generator",
     topic: "derivatives",
     subject: "calculus",
     difficulty: "medium",
     count: 5,
     confidence: 0.9
   }

6. Orchestrator: validate_and_fill_defaults()
   • Check all required parameters present
   • Apply smart defaults for missing values
   
7. Orchestrator → LangGraph Workflow
   State flows through graph nodes

8. LangGraph: route_after_validation()
   Decision: Go to execute_flashcard_generator

9. Orchestrator → ToolClient
   call_flashcard_generator(FlashcardRequest{...})

10. ToolClient → Flashcard API
    POST /api/flashcards
    {user_info, topic, count, difficulty, subject}

11. Flashcard API → ToolClient
    {flashcards: [{question, answer}, ...]}

12. ToolClient → Orchestrator
    FlashcardResponse parsed and validated

13. Orchestrator: format_response()
    Create human-friendly message

14. Orchestrator → FastAPI
    OrchestratorResponse

15. FastAPI → Student
    {
      success: true,
      tool_used: "flashcard_generator",
      message: "I've generated 5 flashcards...",
      tool_response: {...}
    }
```

## Personalization Logic

### Mastery Level Adaptation

```
Level 1-3 (Foundation)
├── Difficulty: easy
├── Depth: basic
└── Support: Maximum scaffolding

Level 4-6 (Developing)
├── Difficulty: medium
├── Depth: intermediate
└── Support: Guided practice

Level 7-9 (Advanced)
├── Difficulty: hard
├── Depth: advanced
└── Support: Challenge-focused

Level 10 (Mastery)
├── Difficulty: hard
├── Depth: comprehensive
└── Support: Innovation-focused
```

### Emotional State Adaptation

```
Anxious/Confused
├── Lower difficulty
├── Simpler explanations
├── More scaffolding
└── Encouraging tone

Focused/Motivated
├── Appropriate challenge
├── Standard depth
└── Empowering tone

Tired
├── Minimal cognitive load
├── Shorter content
└── Gentle interaction
```

### Learning Style Adaptation

```
Visual Learner
├── include_examples: true
├── include_analogies: true
├── note_style: "structured"
└── Diagram suggestions

Kinesthetic Learner
├── Practice-focused
├── Application examples
└── Hands-on suggestions

Auditory Learner
├── Step-by-step explanations
├── Verbal descriptions
└── Discussion prompts
```

## Scalability Considerations

### Current Architecture (3 Tools)

```
Parameter Extractor
  ↓ One LLM call
Tool Selection
  ↓ Single decision
Tool Execution
  ↓ One API call
```

**Performance**: < 5 seconds total

### Scaling to 80 Tools

**Strategies:**

1. **Tool Categorization**
   ```
   Tools grouped by category:
   • Content Generation (notes, summaries, outlines)
   • Practice & Assessment (quizzes, flashcards, tests)
   • Explanation & Tutoring (concept explainer, step-by-step)
   • Analysis & Feedback (essay grading, code review)
   ```

2. **Hierarchical Routing**
   ```
   Step 1: Identify category (4-5 options)
   Step 2: Select specific tool within category
   ```

3. **Tool Registry**
   ```python
   TOOL_REGISTRY = {
       "flashcard_generator": {
           "category": "practice",
           "schema": FlashcardRequest,
           "api_url": "...",
           "priority": 5
       },
       # ... 79 more tools
   }
   ```

4. **Caching Layer**
   ```
   Cache common parameter extractions
   Cache tool selection decisions
   Cache API responses (when appropriate)
   ```

## Error Handling Strategy

### Levels of Fallback

```
Level 1: Retry with backoff
  ↓ (if fails)
Level 2: Try alternative parameters
  ↓ (if fails)
Level 3: Suggest clarification
  ↓ (if fails)
Level 4: Graceful degradation (no tool)
```

### Example Error Flow

```
1. Tool API timeout
   → Retry 3 times with exponential backoff

2. All retries fail
   → Return error with suggestions
   → needs_clarification = true
   → "I'm having trouble connecting to the tool.
      Would you like to try again or rephrase?"

3. User rephrases
   → Extract parameters again
   → Try different approach
```

## Performance Metrics

### Target Latencies

- Parameter Extraction: < 2 seconds
- Tool API Call: < 3 seconds
- Total Orchestration: < 5 seconds

### Optimization Techniques

1. **Async Operations**: All I/O is non-blocking
2. **Parallel Requests**: Multiple tool calls can run concurrently (if needed)
3. **Connection Pooling**: Reuse HTTP connections
4. **Caching**: Cache common extractions

## Security Considerations

1. **Input Validation**: All inputs validated with Pydantic
2. **API Key Management**: Environment variables, never in code
3. **Rate Limiting**: Respect tool API rate limits
4. **Error Messages**: Don't expose sensitive internal details
5. **Logging**: Log for debugging, but sanitize sensitive data

## Testing Strategy

### Unit Tests
- Parameter extraction accuracy
- Tool integration (with mocks)
- State transitions in workflow
- Error handling

### Integration Tests
- End-to-end orchestration
- Real tool API calls (in staging)
- Edge cases and error scenarios

### Demo Scenarios
- 5 predefined scenarios covering all tools
- Interactive mode for manual testing

## Deployment Architecture

```
┌────────────────────────────┐
│   Load Balancer (Optional) │
└──────────────┬─────────────┘
               │
        ┌──────┴──────┐
        │   FastAPI   │
        │   Instance  │
        └──────┬──────┘
               │
        ┌──────┴──────────┐
        │  Redis (Future) │  ← State persistence
        │    Optional     │
        └─────────────────┘
```

### Environment Variables
- `OPENAI_API_KEY`: Required
- `USE_MOCK_TOOLS`: Development flag
- Tool API URLs
- Timeout and retry settings

## Future Enhancements

1. **Streaming Responses**: Return data as it's generated
2. **Multi-Tool Orchestration**: Call multiple tools in one request
3. **Learning from Feedback**: Improve parameter extraction over time
4. **Advanced Personalization**: ML-based student modeling
5. **Tool Recommendation**: Suggest tools proactively
6. **Analytics Dashboard**: Monitor usage and performance

---

**Last Updated**: 2025
**Version**: 1.0.0