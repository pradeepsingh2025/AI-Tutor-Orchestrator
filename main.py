"""
FastAPI Application for AI Tutor Orchestrator
Main entry point for the API server
"""
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import os
from dotenv import load_dotenv

from models import OrchestrateRequest, OrchestratorResponse, ErrorResponse
from parameter_extractor import ParameterExtractor
from tools import create_tool_client, EducationalToolClient
from orchestrator import AITutorOrchestrator

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# APPLICATION LIFECYCLE
# ============================================================================

# Global instances (initialized on startup)
orchestrator: AITutorOrchestrator = None
tool_client: EducationalToolClient = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    Handles startup and shutdown events
    """
    # Startup
    logger.info("Starting AI Tutor Orchestrator...")
    
    global orchestrator, tool_client
    
    # Initialize components
    try:
        # Check if we should use mock tools (for development)
        use_mock = os.getenv("USE_MOCK_TOOLS", "false").lower() == "true"
        
        logger.info(f"Initializing tools (mock={use_mock})...")
        tool_client = create_tool_client(use_mock=use_mock)
        
        logger.info("Initializing parameter extractor...")
        parameter_extractor = ParameterExtractor(
            model_name=os.getenv("LLM_MODEL", "gpt-4"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.1"))
        )
        
        logger.info("Initializing orchestrator...")
        orchestrator = AITutorOrchestrator(
            parameter_extractor=parameter_extractor,
            tool_client=tool_client
        )
        
        logger.info("✅ AI Tutor Orchestrator started successfully!")
        
    except Exception as e:
        logger.error(f"Failed to start orchestrator: {str(e)}")
        raise
    
    yield  # Application runs here
    
    # Shutdown
    logger.info("Shutting down AI Tutor Orchestrator...")
    if tool_client:
        await tool_client.close()
    logger.info("Shutdown complete")


# ============================================================================
# FASTAPI APP INITIALIZATION
# ============================================================================

app = FastAPI(
    title="AI Tutor Orchestrator",
    description="Intelligent middleware for autonomous educational tool orchestration",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware (allow frontend to call API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - API info"""
    return {
        "service": "AI Tutor Orchestrator",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "orchestrate": "/orchestrate",
            "docs": "/docs"
        }
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "orchestrator_initialized": orchestrator is not None,
        "tool_client_initialized": tool_client is not None
    }


@app.post(
    "/orchestrate",
    response_model=OrchestratorResponse,
    tags=["Orchestration"],
    summary="Main orchestration endpoint",
    description="Analyzes student message, extracts parameters, and calls appropriate educational tool"
)
async def orchestrate_endpoint(request: OrchestrateRequest) -> OrchestratorResponse:
    """
    Main orchestration endpoint
    
    This is the primary API that external systems call.
    It handles the entire workflow from message analysis to tool execution.
    
    Args:
        request: OrchestrateRequest containing message, user_info, and chat_history
        
    Returns:
        OrchestratorResponse with tool output or clarification request
        
    Raises:
        HTTPException: If orchestration fails
    """
    try:
        logger.info(f"Received orchestration request from user: {request.user_info.user_id}")
        logger.info(f"Message: {request.message[:100]}...")  # Log first 100 chars
        
        # Run orchestration
        response = await orchestrator.orchestrate(
            message=request.message,
            user_info=request.user_info,
            chat_history=request.chat_history
        )
        
        logger.info(f"Orchestration completed. Tool used: {response.tool_used}")
        
        return response
    
    except Exception as e:
        logger.error(f"Orchestration failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Orchestration failed: {str(e)}"
        )


@app.post(
    "/validate",
    tags=["Utilities"],
    summary="Validate request without execution",
    description="Test parameter extraction without actually calling tools"
)
async def validate_endpoint(request: OrchestrateRequest):
    """
    Validation-only endpoint for testing
    
    Extracts and validates parameters but doesn't call tools.
    Useful for debugging and testing parameter extraction logic.
    """
    try:
        logger.info("Validation-only request")
        
        # Extract parameters
        parameter_extractor = orchestrator.parameter_extractor
        extracted = parameter_extractor.extract(
            message=request.message,
            user_info=request.user_info,
            chat_history=request.chat_history
        )
        
        # Validate and fill defaults
        extracted = parameter_extractor.validate_and_fill_defaults(
            extracted,
            request.user_info
        )
        
        return {
            "validation": "success",
            "extracted_parameters": extracted.model_dump(),
            "tool_would_be_called": extracted.tool_needed.value,
            "confidence": extracted.confidence,
            "reasoning": extracted.reasoning
        }
    
    except Exception as e:
        logger.error(f"Validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation failed: {str(e)}"
        )


@app.get(
    "/tools",
    tags=["Utilities"],
    summary="List available tools",
    description="Get information about available educational tools"
)
async def list_tools():
    """List all available educational tools"""
    return {
        "tools": [
            {
                "name": "note_maker",
                "description": "Creates structured study notes on a topic",
                "required_params": ["topic", "subject", "note_taking_style"],
                "optional_params": ["include_examples", "include_analogies"]
            },
            {
                "name": "flashcard_generator",
                "description": "Generates practice flashcards",
                "required_params": ["topic", "count", "difficulty", "subject"],
                "optional_params": ["include_examples"]
            },
            {
                "name": "concept_explainer",
                "description": "Explains specific concepts in detail",
                "required_params": ["concept_to_explain", "current_topic", "desired_depth"],
                "optional_params": []
            }
        ]
    }


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "error_code": f"HTTP_{exc.status_code}",
            "suggestions": [
                "Check your request parameters",
                "Verify API is running correctly",
                "Check logs for more details"
            ]
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "error_code": "INTERNAL_ERROR",
            "details": str(exc) if os.getenv("DEBUG", "false") == "true" else None,
            "suggestions": [
                "This is an unexpected error",
                "Please check server logs",
                "Contact support if issue persists"
            ]
        }
    )


# ============================================================================
# RUN SERVER (for development)
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,  # Auto-reload on code changes (development only)
        log_level="info"
    )