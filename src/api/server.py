from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
import asyncio
from typing import Optional

# Global reference to the assistant
_assistant = None

app = FastAPI(title="Aida Assistant API")

# Enable CORS (so you can potentially develop the frontend separately)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (the Web App)
app.mount("/static", StaticFiles(directory="src/api/static"), name="static")

class ChatRequest(BaseModel):
    message: str

class VisionRequest(BaseModel):
    image: str  # Base64 encoded image
    prompt: Optional[str] = "Describe this image"

class ChatResponse(BaseModel):
    response: str
    status: str

def set_assistant_instance(assistant):
    """Set the running AidaAssistant instance."""
    global _assistant
    _assistant = assistant

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main Web App interface."""
    with open("src/api/static/index.html", "r") as f:
        return f.read()

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message to Aida and get a text response."""
    global _assistant
    if _assistant is None:
        raise HTTPException(status_code=503, detail="Assistant not initialized")

    logger = logging.getLogger("aida.api")
    logger.info(f"API received message: {request.message}")

    try:
        # Pass speak=False to prevent server from speaking out loud
        response_text = _assistant.process_message(request.message, speak=False)
        
        return ChatResponse(
            response=response_text,
            status="success"
        )
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        return ChatResponse(
            response=f"Error: {str(e)}",
            status="error"
        )

@app.post("/api/vision", response_model=ChatResponse)
async def vision_chat(request: VisionRequest):
    """Send an image to Aida for analysis."""
    global _assistant
    if _assistant is None:
        raise HTTPException(status_code=503, detail="Assistant not initialized")

    logger = logging.getLogger("aida.api")
    logger.info("API received vision request")

    try:
        # Use the assistant's LLM directly for vision
        # We assume the image string is a clean base64 string or data URI
        image_data = request.image
        if "base64," in image_data:
            image_data = image_data.split("base64,")[1]

        response_text = _assistant.llm.vision_chat(request.prompt, [image_data])
        
        # We manually emit signals so the GUI updates
        _assistant.status_changed.emit("Processed mobile image")
        _assistant.response_ready.emit(response_text)
        
        # Add to memory context if possible? 
        # For now, just return the description.
        
        return ChatResponse(
            response=response_text,
            status="success"
        )
    except Exception as e:
        logger.error(f"Error processing vision request: {e}")
        return ChatResponse(
            response=f"Error: {str(e)}",
            status="error"
        )

@app.get("/api/status")
async def get_status():
    """Check if Aida is ready."""
    global _assistant
    if _assistant is None:
        return {"status": "starting"}
    return {"status": "ready"}
