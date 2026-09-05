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
        stage3_synthesize_final, calculate_aggregate_rankings, aggregate_run_cost
    )
    from .config_manager import (
        get_config, update_config, validate_api_key, get_available_models,
        DEFAULT_AVAILABLE_MODELS, load_config, get_api_key, apply_config_to_env,
        test_lm_studio_connection, get_lm_studio_urls,
        get_advanced_config, save_advanced_config
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
        stage3_synthesize_final, calculate_aggregate_rankings, aggregate_run_cost
    )
    from config_manager import (
        get_config, update_config, validate_api_key, get_available_models,
        DEFAULT_AVAILABLE_MODELS, load_config, get_api_key, apply_config_to_env,
        test_lm_studio_connection, get_lm_studio_urls,
        get_advanced_config, save_advanced_config
    )
    from document_processor import (
        process_uploaded_file, list_documents, get_document, 
        delete_document, toggle_document_active, get_active_documents_context,
        get_active_vision_images, SUPPORTED_EXTENSIONS
    )


app = FastAPI(title="LLM Council API")

# ===== Monetization layer (v9): auth, payments, admin, credits =====
import os as _os
from fastapi import Depends
from starlette.middleware.sessions import SessionMiddleware

try:
    from . import db as _db
    from . import settings_store
    from .auth import router as auth_router, get_current_user, get_current_admin
    from .payments import router as payments_router
    from .admin import router as admin_router
    from .admin import _openrouter_model_ids
    from .db import SessionLocal, debit_user, credit_user
except ImportError:
    import db as _db
    import settings_store
    from auth import router as auth_router, get_current_user, get_current_admin
    from payments import router as payments_router
    from admin import router as admin_router
    from admin import _openrouter_model_ids
    from db import SessionLocal, debit_user, credit_user

# SessionMiddleware is required by authlib for OAuth state (CSRF) handling.
app.add_middleware(
    SessionMiddleware,
    secret_key=_os.environ.get("JWT_SECRET", "dev-secret"),
    same_site="lax",
    https_only=_os.environ.get("COOKIE_SECURE", "1") == "1",
)


async def _request_cost(has_vision: bool) -> int:
    cost = await settings_store.get_setting("request_cost", {"standard": 10, "vision": 15})
    return int(cost.get("vision", 15) if has_vision else cost.get("standard", 10))


async def _debit_or_402(user, cost: int, conversation_id: str) -> int:
    """Atomic debit; raise HTTP 402 with balance info if insufficient."""
    async with SessionLocal() as session:
        new_balance = await debit_user(session, user.id, cost, conversation_id=conversation_id)
        if new_balance is None:
            fresh = await session.get(_db.User, user.id)
            balance = fresh.credits if fresh else 0
            raise HTTPException(
                status_code=402,
                detail={"error": "insufficient_credits", "required": cost, "balance": balance},
            )
        await session.commit()
        return new_balance


async def _refund(user_id, cost: int, conversation_id: str):
    async with SessionLocal() as session:
        await credit_user(session, user_id, cost, "refund", conversation_id=conversation_id,
                          reason="Remboursement échec pipeline")
        await session.commit()


async def _record_run_cost_safe(user_id, conversation_id, stage1_results, stage2_results,
                                stage3_result, title_model=None, title_cost=None, title_tokens=None):
    """Persist the real OpenRouter cost for a council run. Best-effort: any failure
    (including a provider that omitted usage.cost) is swallowed and logged."""
    try:
        breakdown, total_cost, total_tokens = aggregate_run_cost(
            stage1_results=stage1_results,
            stage2_results=stage2_results,
            stage3_result=stage3_result,
            title_model=title_model, title_cost=title_cost, title_tokens=title_tokens,
        )
        async with SessionLocal() as session:
            await _db.record_run_cost(session, user_id, conversation_id, breakdown, total_cost, total_tokens)
            await session.commit()
    except Exception as e:
        print(f"[run_cost] failed to record run cost (non-fatal): {e}")


async def _get_catalogue():
    """Load the model catalogue from app_settings, seeding from defaults if absent."""
    models = await settings_store.get_setting("available_models", None)
    if not models:
        models = [dict(m) for m in DEFAULT_AVAILABLE_MODELS]
    return [dict(m) for m in models]


# ===== Per-user council selection helpers =====

def _user_council_key(uid) -> str:
    return f"user_council:{uid}"


def _user_chairman_key(uid) -> str:
    return f"user_chairman:{uid}"


async def _get_user_council(user):
    """Return the user's personal council selection, or None if not set."""
    models = await settings_store.get_setting(_user_council_key(user.id), None)
    if not models:
        return None
    chairman = await settings_store.get_setting(_user_chairman_key(user.id), None)
    return {"council_models": models, "chairman_model": chairman}


async def _inject_user_council(user, advanced):
    """Inject the user's personal council into the advanced_config dict passed to
    the pipeline. Falls back to the global admin selection when the user has no
    personal council."""
    uc = await _get_user_council(user)
    if not uc:
        return advanced
    advanced = dict(advanced or {})
    advanced["_user_council_models"] = uc["council_models"]
    if uc.get("chairman_model"):
        advanced["_user_chairman_model"] = uc["chairman_model"]
    return advanced



# ===== Helper Functions =====

def requires_openrouter_key(advanced_config: Optional[Dict] = None) -> bool:
    """
    Return True if the request needs an OpenRouter API key.
    In LM Studio mode, no OpenRouter key is needed.
    In hybrid mode, key is needed only if any model uses OpenRouter.
    """
    if not advanced_config:
        return True  # Default mode is openrouter
    
    mode = advanced_config.get('mode', 'openrouter')
    
    if mode == 'lmstudio':
        return False
    
    if mode == 'hybrid':
        # Need key if any model or chairman uses openrouter
        models_cfg = advanced_config.get('models', {})
        has_openrouter_model = any(
            m.get('source', 'openrouter') == 'openrouter'
            for m in models_cfg.values()
        )
        chairman_source = advanced_config.get('chairman', {}).get('source', 'openrouter')
        return has_openrouter_model or chairman_source == 'openrouter'
    
    return True  # openrouter mode


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
    """Get the path to the built frontend (Vite dist) folder.

    Only a real production build (index.html + assets/) is accepted. The Vite
    DEV entry at frontend/index.html (which loads /src/main.jsx) must never be
    served in production, otherwise the SPA — including the auth gate — breaks.
    """
    backend_dir = Path(__file__).parent.resolve()

    possible_paths = [
        backend_dir.parent / "frontend" / "dist",
        Path(os.getcwd()) / "frontend" / "dist",
    ]

    for p in possible_paths:
        index_file = p / "index.html"
        assets_dir = p / "assets"
        if index_file.exists() and assets_dir.is_dir():
            print(f"Found built frontend at: {p}")
            return p

    print("Built frontend (frontend/dist) not found — running API-only. "
          "Run `npm run build` in frontend/ and redeploy.")
    return None

FRONTEND_PATH = get_frontend_path()

# Apply configuration on startup
@app.on_event("startup")
async def startup_event():
    apply_config_to_env()
    await _db.init_db()
    await settings_store.seed_defaults()
    if FRONTEND_PATH:
        print(f"Frontend path: {FRONTEND_PATH}")
    else:
        print("Frontend not found - API-only mode")


# Register monetization routers
app.include_router(auth_router)
app.include_router(payments_router)
app.include_router(admin_router)


# ===== Request/Response Models =====

class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    pass


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str
    include_documents: Optional[bool] = True
    document_ids: Optional[List[str]] = None
    advanced: Optional[Dict[str, Any]] = None


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
    lm_studio_urls: Optional[Dict[str, str]] = None
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


class UpdateCatalogModelRequest(BaseModel):
    """Request to edit a catalogue model's OpenRouter id (and optional name/provider)."""
    new_id: str
    model_name: Optional[str] = None
    provider: Optional[str] = None


class TestLmStudioRequest(BaseModel):
    """Request to test LM Studio connection."""
    url: str
    model_name: Optional[str] = None


class ToggleDocumentRequest(BaseModel):
    """Request to toggle document active status."""
    is_active: bool


# ===== Health Check =====

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    config = load_config()
    has_key = bool(get_api_key())
    # Also consider configured if LM Studio URLs or advanced config is set
    has_lm_studio = bool(config.get("lm_studio_urls")) or bool(config.get("advanced_config"))
    return {
        "status": "ok", 
        "service": "LLM Council API",
        "configured": has_key or has_lm_studio,
        "version": "2.0.0"
    }


# ===== Configuration Endpoints =====

@app.get("/api/config")
async def get_configuration(user=Depends(get_current_user)):
    """Get current configuration.

    council_models / chairman_model are overlaid from Postgres app_settings (the
    persistent source of truth) so an admin's selection survives dyno restarts.
    has_api_key reflects the persisted key (DB) too, not just the ephemeral
    config.json.
    """
    cfg = get_config()
    cfg["council_models"] = await settings_store.get_setting("council_models", cfg.get("council_models"))
    cfg["chairman_model"] = await settings_store.get_setting("chairman_model", cfg.get("chairman_model"))
    # Non-admins see their personal council overlaid on top of the global default.
    if user.role != "admin":
        uc = await _get_user_council(user)
        if uc:
            cfg["council_models"] = uc["council_models"]
            if uc.get("chairman_model"):
                cfg["chairman_model"] = uc["chairman_model"]
    key = get_api_key()
    cfg["has_api_key"] = bool(key)
    if key:
        cfg["openrouter_api_key_masked"] = (key[:8] + "..." + key[-4:]) if len(key) > 10 else "*" * len(key)
    return cfg


@app.put("/api/config")
async def update_configuration(request: ConfigUpdateRequest, user=Depends(get_current_user)):
    """Update configuration.

    Non-admins may update non-sensitive fields (council_models, chairman_model,
    theme) — these let them use the Council Models / Chairman tabs. API-sensitive
    fields (OpenRouter key, LM Studio URLs, advanced provider config) are admin
    only. The OpenRouter key + council selection are mirrored into Postgres
    app_settings (persistent across dyno restarts).
    """
    updates = request.model_dump(exclude_none=True)
    admin_only_fields = {"openrouter_api_key", "lm_studio_urls", "advanced_config", "storage_location"}
    if user.role != "admin" and (admin_only_fields & set(updates.keys())):
        raise HTTPException(status_code=403, detail="Admin privileges required to modify API settings")
    updated_config = update_config(updates)
    apply_config_to_env()
    if updates.get("openrouter_api_key"):
        await settings_store.set_setting("openrouter_api_key", updates["openrouter_api_key"], updated_by=user.id)
        # Invalidate the cached OpenRouter key-status so the admin panel reflects the
        # new key immediately (not after the ~3-min TTL).
        try:
            from .admin import bust_key_status_cache
        except ImportError:
            from admin import bust_key_status_cache
        bust_key_status_cache()
    if updates.get("council_models"):
        await settings_store.set_setting("council_models", updates["council_models"])
    if updates.get("chairman_model"):
        await settings_store.set_setting("chairman_model", updates["chairman_model"])
    return updated_config


class UserCouncilRequest(BaseModel):
    """Per-user council selection request."""
    council_models: List[str]
    chairman_model: Optional[str] = None


@app.get("/api/config/council")
async def get_user_council_endpoint(user=Depends(get_current_user)):
    """Get the caller's council selection (personal if set, else global default)."""
    global_models = await settings_store.get_setting("council_models", [])
    global_chairman = await settings_store.get_setting("chairman_model", "")
    uc = await _get_user_council(user)
    if uc:
        return {
            "council_models": uc["council_models"],
            "chairman_model": uc.get("chairman_model") or "",
            "is_custom": True,
            "default_council_models": global_models,
            "default_chairman_model": global_chairman,
        }
    return {
        "council_models": global_models,
        "chairman_model": global_chairman,
        "is_custom": False,
        "default_council_models": global_models,
        "default_chairman_model": global_chairman,
    }


@app.put("/api/config/council")
async def update_user_council_endpoint(request: UserCouncilRequest, user=Depends(get_current_user)):
    """Save the caller's personal council selection (≥ 2 models, chairman ∈ council)."""
    # De-duplicate while preserving order.
    seen = set()
    models = [m for m in (request.council_models or []) if not (m in seen or seen.add(m))]
    if len(models) < 2:
        raise HTTPException(status_code=400, detail="Please select at least 2 council models")
    chairman = request.chairman_model or models[0]
    if chairman not in models:
        raise HTTPException(status_code=400, detail="The chairman must be one of the selected council models")
    await settings_store.set_setting(_user_council_key(user.id), models, updated_by=str(user.id))
    await settings_store.set_setting(_user_chairman_key(user.id), chairman, updated_by=str(user.id))
    return {"council_models": models, "chairman_model": chairman, "is_custom": True}


@app.delete("/api/config/council")
async def reset_user_council_endpoint(user=Depends(get_current_user)):
    """Reset the caller's council back to the global admin default."""
    await settings_store.set_setting(_user_council_key(user.id), None, updated_by=str(user.id))
    await settings_store.set_setting(_user_chairman_key(user.id), None, updated_by=str(user.id))
    global_models = await settings_store.get_setting("council_models", [])
    global_chairman = await settings_store.get_setting("chairman_model", "")
    return {
        "council_models": global_models,
        "chairman_model": global_chairman,
        "is_custom": False,
    }


@app.post("/api/config/validate-key")
async def validate_openrouter_key(request: ValidateKeyRequest, user=Depends(get_current_admin)):
    """Validate an OpenRouter API key (admin only)."""
    result = await validate_api_key(request.api_key)
    return result


@app.get("/api/models/available")
async def get_models():
    """Get list of available models."""
    return {"models": get_available_models()}


@app.post("/api/models/custom")
async def add_custom_model_endpoint(request: CustomModelRequest, user=Depends(get_current_user)):
    """Add a custom model to the catalogue (persisted in app_settings)."""
    catalogue = await _get_catalogue()
    existing = next((m for m in catalogue if m["id"] == request.model_id), None)
    if existing:
        return {"model": existing}
    new_model = {"id": request.model_id, "name": request.model_name, "provider": request.provider}
    catalogue.append(new_model)
    await settings_store.set_setting("available_models", catalogue)
    return {"model": new_model}


@app.put("/api/models/custom/{model_id:path}")
async def update_catalog_model(model_id: str, request: UpdateCatalogModelRequest, user=Depends(get_current_user)):
    """Edit a catalogue model's OpenRouter id (and optionally name/provider).

    Validates a changed id against the public OpenRouter catalogue and cascades
    the rename into council_models / chairman_model.
    """
    catalogue = await _get_catalogue()
    idx = next((i for i, m in enumerate(catalogue) if m["id"] == model_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="model_not_found")

    new_id = (request.new_id or "").strip()
    if not new_id:
        raise HTTPException(status_code=400, detail="L'identifiant OpenRouter ne peut pas être vide")

    if new_id != model_id:
        if any(m["id"] == new_id for m in catalogue):
            raise HTTPException(status_code=400, detail=f"'{new_id}' existe déjà dans le catalogue")
        ids = await _openrouter_model_ids()
        if ids is not None and new_id not in ids:
            raise HTTPException(status_code=400, detail=f"Modèle invalide : '{new_id}' introuvable sur OpenRouter")

    old = catalogue[idx]
    updated = {
        "id": new_id,
        "name": (request.model_name or old.get("name") or new_id),
        "provider": (request.provider or old.get("provider") or ""),
    }
    catalogue[idx] = updated
    await settings_store.set_setting("available_models", catalogue)

    # Cascade the rename into council_models / chairman_model.
    if new_id != model_id:
        council = list(await settings_store.get_setting("council_models", []))
        if model_id in council:
            await settings_store.set_setting("council_models", [new_id if c == model_id else c for c in council])
        chairman = await settings_store.get_setting("chairman_model", "")
        if chairman == model_id:
            await settings_store.set_setting("chairman_model", new_id)

    # Keep config.json (read by the Settings UI via GET /api/config) in sync.
    update_config({
        "council_models": await settings_store.get_setting("council_models", []),
        "chairman_model": await settings_store.get_setting("chairman_model", ""),
    })
    return {"model": updated}


@app.delete("/api/models/custom/{model_id:path}")
async def delete_catalog_model(model_id: str, user=Depends(get_current_user)):
    """Remove a model from the catalogue, cascading to council_models/chairman.

    Refuses if the model is in the council and removing it would leave < 2
    council models.
    """
    catalogue = await _get_catalogue()
    if not any(m["id"] == model_id for m in catalogue):
        raise HTTPException(status_code=404, detail="model_not_found")

    council = list(await settings_store.get_setting("council_models", []))
    if model_id in council and len(council) <= 2:
        raise HTTPException(status_code=400, detail="Suppression refusée : le council doit conserver au moins 2 modèles")

    catalogue = [m for m in catalogue if m["id"] != model_id]
    await settings_store.set_setting("available_models", catalogue)

    if model_id in council:
        council = [c for c in council if c != model_id]
        await settings_store.set_setting("council_models", council)
        chairman = await settings_store.get_setting("chairman_model", "")
        if chairman == model_id:
            await settings_store.set_setting("chairman_model", council[0] if council else "")

    # Keep config.json (read by the Settings UI via GET /api/config) in sync.
    update_config({
        "council_models": await settings_store.get_setting("council_models", []),
        "chairman_model": await settings_store.get_setting("chairman_model", ""),
    })
    return {"ok": True, "council_models": council}


@app.post("/api/lm-studio/test")
async def test_lm_studio_endpoint(request: TestLmStudioRequest):
    """Test connection to an LM Studio server."""
    result = await test_lm_studio_connection(request.url, request.model_name)
    return result


@app.get("/api/lm-studio/urls")
async def get_lm_studio_urls_endpoint():
    """Get all configured LM Studio URLs."""
    return {"urls": get_lm_studio_urls()}


# ===== Advanced Config Endpoints =====

class AdvancedConfigRequest(BaseModel):
    """Request body for saving advanced config."""
    mode: Optional[str] = None
    openrouter: Optional[Dict[str, Any]] = None
    models: Optional[Dict[str, Any]] = None
    chairman: Optional[Dict[str, Any]] = None
    throttle: Optional[Dict[str, Any]] = None


@app.get("/api/config/advanced")
async def get_advanced_config_endpoint(user=Depends(get_current_admin)):
    """Get advanced LLM configuration (admin only)."""
    return get_advanced_config()


@app.post("/api/config/advanced")
async def save_advanced_config_endpoint(request: AdvancedConfigRequest, user=Depends(get_current_admin)):
    """Save advanced LLM configuration (admin only)."""
    config_data = request.model_dump(exclude_none=True)
    saved_config = save_advanced_config(config_data)
    return saved_config


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


@app.get("/api/documents/supported-types")
async def get_supported_types():
    """Get list of supported file types."""
    return {"supported_extensions": list(SUPPORTED_EXTENSIONS.keys())}


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


@app.get("/api/documents/{doc_id}/status")
async def get_document_status(doc_id: str):
    """Get the processing status of a document."""
    doc = get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Build status response
    status_info = {
        "id": doc["id"],
        "filename": doc["filename"],
        "status": "completed",  # Once document is in registry, processing is done
        "is_vision_image": doc.get("is_vision_image", False),
        "text_length": doc.get("text_length", 0),
        "chunk_count": doc.get("chunk_count", 1),
        "is_active": doc.get("is_active", True),
    }
    
    # Add image metadata if available
    extraction_meta = doc.get("extraction_metadata", {})
    if extraction_meta:
        status_info["extraction_details"] = {
            "width": extraction_meta.get("width"),
            "height": extraction_meta.get("height"),
            "format": extraction_meta.get("format"),
            "type": extraction_meta.get("type"),
        }
    
    return status_info


# ===== Conversation Endpoints =====

@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations(user=Depends(get_current_user)):
    """List all conversations for the current user (metadata only)."""
    return storage.list_conversations(str(user.id))


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest, user=Depends(get_current_user)):
    """Create a new conversation owned by the current user."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id, str(user.id))
    return conversation


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str, user=Depends(get_current_user)):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id, str(user.id))
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, user=Depends(get_current_user)):
    """Delete a conversation."""
    success = storage.delete_conversation(conversation_id, str(user.id))
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"success": True}


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest, user=Depends(get_current_user)):
    """
    Send a message and run the 3-stage council process.
    Debits credits atomically BEFORE running; refunds automatically if the
    pipeline fails after the debit. Returns the complete response.
    """
    # Check if conversation exists and belongs to the user
    conversation = storage.get_conversation(conversation_id, str(user.id))
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Apply the user's personal council selection (falls back to global default)
    request.advanced = await _inject_user_council(user, request.advanced)

    # Build query with document context if requested
    query_content = request.content
    vision_images = []
    
    if request.include_documents:
        # Get text document context
        doc_context = get_active_documents_context()
        if doc_context:
            query_content = f"""I have uploaded the following documents for reference:

{doc_context}

---

My question: {request.content}"""
        
        # Get vision images for analysis
        vision_images = get_active_vision_images()
        if vision_images:
            image_note = f"\n\n[Note: {len(vision_images)} image(s) attached for visual analysis]"
            query_content += image_note

    # ===== Credit debit (atomic, server-priced) BEFORE running =====
    cost = await _request_cost(bool(vision_images))
    await _debit_or_402(user, cost, conversation_id)

    # Add user message
    storage.add_user_message(conversation_id, request.content)

    # If this is the first message, generate a title
    title_model = title_cost = title_tokens = None
    if is_first_message:
        title, title_cost, title_tokens, title_model = await generate_conversation_title(
            request.content, advanced_config=request.advanced, return_usage=True
        )
        storage.update_conversation_title(conversation_id, title)

    try:
        # Run the 3-stage council process
        stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
            query_content,
            vision_images=vision_images if vision_images else None,
            advanced_config=request.advanced
        )
        # run_full_council returns a soft-error stub (no exception) when all models
        # fail. Treat that as a pipeline failure so credits are refunded.
        pipeline_failed = (not stage1_results) or (
            isinstance(stage3_result, dict) and stage3_result.get("model") == "error"
        )
        if pipeline_failed:
            raise RuntimeError("Aucun modèle n'a répondu (clé OpenRouter manquante/invalide).")
    except Exception as e:
        # Pipeline failed after debit -> automatic refund
        await _refund(user.id, cost, conversation_id)
        raise HTTPException(status_code=502, detail=f"Council pipeline failed (crédits remboursés): {e}")

    # Add assistant message with all stages
    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result
    )

    # Record real OpenRouter cost for this run (best-effort; never blocks the response).
    await _record_run_cost_safe(user.id, conversation_id, stage1_results, stage2_results,
                                stage3_result, title_model, title_cost, title_tokens)

    # Return the complete response with metadata
    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest, user=Depends(get_current_user)):
    """
    Send a message and stream the 3-stage council process (SSE).
    Debits credits atomically before running; refunds on pipeline failure.
    """
    # Check if conversation exists and belongs to the user
    conversation = storage.get_conversation(conversation_id, str(user.id))
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    is_first_message = len(conversation["messages"]) == 0

    # Apply the user's personal council selection (falls back to global default)
    request.advanced = await _inject_user_council(user, request.advanced)

    # Build query with document context / vision images (needed to price request)
    query_content = request.content
    vision_images = []
    if request.include_documents:
        doc_context = get_active_documents_context()
        if doc_context:
            query_content = f"""I have uploaded the following documents for reference:

{doc_context}

---

My question: {request.content}"""
        vision_images = get_active_vision_images()
        if vision_images:
            query_content += f"\n\n[Note: {len(vision_images)} image(s) attached for visual analysis]"

    # ===== Credit debit (atomic, server-priced) BEFORE running =====
    cost = await _request_cost(bool(vision_images))
    await _debit_or_402(user, cost, conversation_id)

    async def event_generator():
        refunded = False

        # Heroku's router terminates a request if no bytes are sent within 30s and
        # closes idle connections after 55s. Some proxies also buffer the stream.
        # This helper awaits a coroutine while emitting SSE keep-alive comments
        # (`: keep-alive\n\n`, ignored by the frontend parser) so the connection
        # stays open and the stream is flushed during long Stage 1 waits.
        async def run_with_heartbeat(coro, interval=10.0):
            """Async generator: yields keep-alive SSE lines, then finally the result
            wrapped as ('__result__', value)."""
            task = asyncio.ensure_future(coro)
            while not task.done():
                done, _ = await asyncio.wait({task}, timeout=interval)
                if not done:
                    yield ": keep-alive\n\n"
            yield ("__result__", task.result())

        try:
            # Force the stream open immediately (before any long work) so proxies
            # flush headers and the client starts reading right away.
            yield ": ping\n\n"

            # Add user message
            storage.add_user_message(conversation_id, request.content)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(
                    generate_conversation_title(request.content, advanced_config=request.advanced, return_usage=True)
                )

            # Stage 1 (long-running: emit heartbeats while models respond)
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results = None
            async for item in run_with_heartbeat(
                stage1_collect_responses(
                    query_content,
                    vision_images=vision_images if vision_images else None,
                    advanced_config=request.advanced,
                )
            ):
                if isinstance(item, tuple) and item[0] == "__result__":
                    stage1_results = item[1]
                else:
                    yield item
            if not stage1_results:
                raise RuntimeError("Le pipeline du council a échoué : aucun modèle n'a répondu (clé OpenRouter manquante/invalide).")
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # Stage 2 (long-running: emit heartbeats while models rank)
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_pair = None
            async for item in run_with_heartbeat(
                stage2_collect_rankings(query_content, stage1_results, advanced_config=request.advanced)
            ):
                if isinstance(item, tuple) and item[0] == "__result__":
                    stage2_pair = item[1]
                else:
                    yield item
            stage2_results, label_to_model = stage2_pair
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}})}\n\n"

            # Stage 3 (long-running: emit heartbeats while the chairman synthesizes)
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result = None
            async for item in run_with_heartbeat(
                stage3_synthesize_final(query_content, stage1_results, stage2_results, advanced_config=request.advanced)
            ):
                if isinstance(item, tuple) and item[0] == "__result__":
                    stage3_result = item[1]
                else:
                    yield item
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            # Title
            title_model = title_cost = title_tokens = None
            if title_task:
                try:
                    title, title_cost, title_tokens, title_model = await title_task
                    storage.update_conversation_title(conversation_id, title)
                    yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"
                except Exception as title_err:
                    print(f"Title generation failed (non-fatal): {title_err}")
                    fallback = request.content[:47] + "..." if len(request.content) > 50 else request.content
                    storage.update_conversation_title(conversation_id, fallback)
                    yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': fallback}})}\n\n"

            storage.add_assistant_message(conversation_id, stage1_results, stage2_results, stage3_result)

            # Record real OpenRouter cost for this run (best-effort; never blocks the stream).
            await _record_run_cost_safe(user.id, conversation_id, stage1_results, stage2_results,
                                        stage3_result, title_model, title_cost, title_tokens)
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            # Pipeline failed after debit -> automatic refund
            if not refunded:
                try:
                    await _refund(user.id, cost, conversation_id)
                except Exception:
                    pass
            yield f"data: {json.dumps({'type': 'error', 'message': str(e), 'refunded': True})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            # Anti-buffering: ensure Heroku's router / any proxy / uvicorn flush
            # SSE events to the client immediately instead of buffering them.
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
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
