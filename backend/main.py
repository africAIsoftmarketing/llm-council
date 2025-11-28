"""FastAPI backend for LLM Council with configuration and document management."""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from pathlib import Path
import uuid
import json
import asyncio
import os
import sys

# Handle imports for both module and direct execution
try:
    from . import storage
    from .council import (
        run_full_council, generate_conversation_title, 
        stage1_collect_responses, stage2_collect_rankings, 
        stage3_synthesize_final, calculate_aggregate_rankings
    )
    from .config_manager import (
        get_config, update_config, validate_api_key, get_available_models,
        add_custom_model, load_config, get_api_key, apply_config_to_env
    )
    from .document_processor import (
        process_uploaded_file, list_documents, get_document, 
        delete_document, toggle_document_active, get_active_documents_context,
        get_active_vision_images, SUPPORTED_EXTENSIONS
    )
except ImportError:
    import storage
    from council import (
        run_full_council, generate_conversation_title, 
        stage1_collect_responses, stage2_collect_rankings, 
        stage3_synthesize_final, calculate_aggregate_rankings
    )
    from config_manager import (
        get_config, update_config, validate_api_key, get_available_models,
        add_custom_model, load_config, get_api_key, apply_config_to_env
    )
    from document_processor import (
        process_uploaded_file, list_documents, get_document, 
        delete_document, toggle_document_active, get_active_documents_context,
        get_active_vision_images, SUPPORTED_EXTENSIONS
    )


app = FastAPI(title="LLM Council API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:8001", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Determine frontend path
def get_frontend_path():
    """Get the path to frontend dist folder."""
    # Get the directory where this file is located
    backend_dir = Path(__file__).parent.resolve()
    
    # Check various possible locations
    possible_paths = [
        # Production: frontend dist is sibling to backend
        backend_dir.parent / "frontend" / "dist",
        backend_dir.parent / "frontend",
        # Development: frontend/dist relative to backend parent
        Path(os.getcwd()) / "frontend" / "dist",
        Path(os.getcwd()) / "frontend",
    ]
    
    for p in possible_paths:
        index_file = p / "index.html"
        if index_file.exists():
            print(f"Found frontend at: {p}")
            return p
    
    print("Frontend not found in any expected location")
    return None

FRONTEND_PATH = get_frontend_path()

# Apply configuration on startup
@app.on_event("startup")
async def startup_event():
    apply_config_to_env()
    if FRONTEND_PATH:
        print(f"Frontend path: {FRONTEND_PATH}")
    else:
        print("Frontend not found - API-only mode")


# ===== Request/Response Models =====

class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    pass


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str
    include_documents: Optional[bool] = True
    document_ids: Optional[List[str]] = None


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    message_count: int


class Conversation(BaseModel):
    """Full conversation with all messages."""
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]


class ConfigUpdateRequest(BaseModel):
    """Request to update configuration."""
    openrouter_api_key: Optional[str] = None
    council_models: Optional[List[str]] = None
    chairman_model: Optional[str] = None
    backend_port: Optional[int] = None
    frontend_port: Optional[int] = None
    auto_credit_reminder: Optional[bool] = None
    credit_reminder_threshold: Optional[float] = None
    document_settings: Optional[Dict[str, Any]] = None
    storage_location: Optional[str] = None
    theme: Optional[str] = None


class ValidateKeyRequest(BaseModel):
    """Request to validate an API key."""
    api_key: str


class CustomModelRequest(BaseModel):
    """Request to add a custom model."""
    model_id: str
    model_name: str
    provider: str


class ToggleDocumentRequest(BaseModel):
    """Request to toggle document active status."""
    is_active: bool


# ===== Health Check =====

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    config = load_config()
    has_key = bool(config.get("openrouter_api_key"))
    return {
        "status": "ok", 
        "service": "LLM Council API",
        "configured": has_key,
        "version": "2.0.0"
    }


# ===== Configuration Endpoints =====

@app.get("/api/config")
async def get_configuration():
    """Get current configuration (API key masked)."""
    return get_config()


@app.put("/api/config")
async def update_configuration(request: ConfigUpdateRequest):
    """Update configuration."""
    updates = request.model_dump(exclude_none=True)
    updated_config = update_config(updates)
    apply_config_to_env()
    return updated_config


@app.post("/api/config/validate-key")
async def validate_openrouter_key(request: ValidateKeyRequest):
    """Validate an OpenRouter API key."""
    result = await validate_api_key(request.api_key)
    return result


@app.get("/api/models/available")
async def get_models():
    """Get list of available models."""
    return {"models": get_available_models()}


@app.post("/api/models/custom")
async def add_custom_model_endpoint(request: CustomModelRequest):
    """Add a custom model."""
    model = add_custom_model(request.model_id, request.model_name, request.provider)
    return {"model": model}


# ===== Document Endpoints =====

@app.get("/api/documents")
async def get_documents():
    """List all uploaded documents."""
    return {"documents": list_documents()}


@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a document for processing."""
    try:
        content = await file.read()
        result = await process_uploaded_file(
            content, 
            file.filename or "unnamed",
            file.content_type
        )
        return {"success": True, "document": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@app.get("/api/documents/{doc_id}")
async def get_document_details(doc_id: str):
    """Get document details and content."""
    doc = get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {
        "id": doc["id"],
        "filename": doc["filename"],
        "extension": doc["extension"],
        "size": doc["size"],
        "uploaded_at": doc["uploaded_at"],
        "chunk_count": doc.get("chunk_count", 1),
        "text_length": doc.get("text_length", 0),
        "is_active": doc.get("is_active", True),
        "extracted_text": doc.get("extracted_text", "")
    }


@app.delete("/api/documents/{doc_id}")
async def delete_document_endpoint(doc_id: str):
    """Delete a document."""
    success = delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"success": True}


@app.patch("/api/documents/{doc_id}/toggle")
async def toggle_document(doc_id: str, request: ToggleDocumentRequest):
    """Toggle document active status."""
    success = toggle_document_active(doc_id, request.is_active)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"success": True, "is_active": request.is_active}


@app.get("/api/documents/supported-types")
async def get_supported_types():
    """Get list of supported file types."""
    return {"supported_extensions": list(SUPPORTED_EXTENSIONS.keys())}


@app.get("/api/documents/{doc_id}/status")
async def get_document_status(doc_id: str):
    """Get the processing status of a document (useful for OCR progress tracking)."""
    doc = get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Build status response
    status_info = {
        "id": doc["id"],
        "filename": doc["filename"],
        "status": "completed",  # Once document is in registry, processing is done
        "ocr_used": doc.get("ocr_used", False),
        "ocr_engine": doc.get("extraction_metadata", {}).get("ocr_engine"),
        "text_length": doc.get("text_length", 0),
        "chunk_count": doc.get("chunk_count", 1),
        "is_active": doc.get("is_active", True),
    }
    
    # Add OCR-specific metadata if available
    extraction_meta = doc.get("extraction_metadata", {})
    if extraction_meta:
        status_info["extraction_details"] = {
            "ocr_pages": extraction_meta.get("ocr_pages", []),
            "width": extraction_meta.get("width"),
            "height": extraction_meta.get("height"),
            "format": extraction_meta.get("format"),
        }
    
    return status_info


@app.get("/api/ocr/status")
async def get_ocr_engine_status():
    """Get the status of available OCR engines."""
    try:
        from document_processor import get_ocr_status
        return get_ocr_status()
    except ImportError:
        from .document_processor import get_ocr_status
        return get_ocr_status()


# ===== Conversation Endpoints =====

@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    """List all conversations (metadata only)."""
    return storage.list_conversations()


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id)
    return conversation


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    success = storage.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"success": True}


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and run the 3-stage council process.
    Returns the complete response with all stages.
    """
    # Check API key
    api_key = get_api_key()
    if not api_key:
        raise HTTPException(
            status_code=400, 
            detail="OpenRouter API key not configured. Please go to Settings to add your API key."
        )
    
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Build query with document context if requested
    query_content = request.content
    if request.include_documents:
        doc_context = get_active_documents_context()
        if doc_context:
            query_content = f"""I have uploaded the following documents for reference:

{doc_context}

---

My question: {request.content}"""

    # Add user message
    storage.add_user_message(conversation_id, request.content)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title)

    # Run the 3-stage council process
    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        query_content
    )

    # Add assistant message with all stages
    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result
    )

    # Return the complete response with metadata
    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and stream the 3-stage council process.
    Returns Server-Sent Events as each stage completes.
    """
    # Check API key
    api_key = get_api_key()
    if not api_key:
        raise HTTPException(
            status_code=400, 
            detail="OpenRouter API key not configured. Please go to Settings to add your API key."
        )
    
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    async def event_generator():
        try:
            # Build query with document context if requested
            query_content = request.content
            if request.include_documents:
                doc_context = get_active_documents_context()
                if doc_context:
                    query_content = f"""I have uploaded the following documents for reference:

{doc_context}

---

My question: {request.content}"""

            # Add user message
            storage.add_user_message(conversation_id, request.content)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            # Stage 1: Collect responses
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results = await stage1_collect_responses(query_content)
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # Stage 2: Collect rankings
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_results, label_to_model = await stage2_collect_rankings(query_content, stage1_results)
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}})}\n\n"

            # Stage 3: Synthesize final answer
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result = await stage3_synthesize_final(query_content, stage1_results, stage2_results)
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            # Wait for title generation if it was started
            if title_task:
                title = await title_task
                storage.update_conversation_title(conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # Save complete assistant message
            storage.add_assistant_message(
                conversation_id,
                stage1_results,
                stage2_results,
                stage3_result
            )

            # Send completion event
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            # Send error event
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ===== Static File Serving for Frontend =====

# Mount static files if frontend exists
if FRONTEND_PATH and FRONTEND_PATH.exists():
    # Serve static assets (JS, CSS, images) if the assets directory exists
    assets_path = FRONTEND_PATH / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")
    
    # Serve index.html for the root and any non-API routes (SPA routing)
    @app.get("/", response_class=HTMLResponse)
    async def serve_frontend_root():
        """Serve the frontend application."""
        index_path = FRONTEND_PATH / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path), media_type="text/html")
        return HTMLResponse(content="<h1>LLM Council API</h1><p>Frontend not found. API is running at /api/</p>")
    
    # Catch-all for SPA routing - serve index.html for non-API routes
    @app.get("/{full_path:path}")
    async def serve_frontend_spa(full_path: str):
        """Serve frontend for SPA routing."""
        # Don't serve index.html for API routes
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        
        # Try to serve the exact file first
        file_path = FRONTEND_PATH / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        
        # Otherwise serve index.html for SPA routing
        index_path = FRONTEND_PATH / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path), media_type="text/html")
        
        raise HTTPException(status_code=404, detail="Not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
