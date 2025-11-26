"""Document processing module for extracting text from various file formats."""

import os
import sys
import uuid
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import mimetypes

# Document processing libraries
from PyPDF2 import PdfReader
from docx import Document as DocxDocument
from pptx import Presentation
from PIL import Image
import io


def get_base_data_dir():
    """Get the base data directory path - uses AppData on Windows."""
    env_data_dir = os.environ.get("DATA_DIR")
    if env_data_dir:
        return env_data_dir
    
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(appdata, "LLM Council", "data")
    
    return "data"


# Base data directory
BASE_DATA_DIR = get_base_data_dir()

# Storage directory for documents
DOCUMENTS_DIR = os.path.join(BASE_DATA_DIR, "documents")
DOCUMENT_REGISTRY_FILE = os.path.join(BASE_DATA_DIR, "document_registry.json")

# Supported file types
SUPPORTED_EXTENSIONS = {
    '.pdf': 'application/pdf',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.doc': 'application/msword',
    '.txt': 'text/plain',
    '.rtf': 'application/rtf',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    '.ppt': 'application/vnd.ms-powerpoint',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.md': 'text/markdown',
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_CHUNK_SIZE = 4000  # Characters per chunk for context window


def ensure_directories():
    """Ensure document storage directories exist."""
    Path(DOCUMENTS_DIR).mkdir(parents=True, exist_ok=True)
    Path("data").mkdir(parents=True, exist_ok=True)


def load_document_registry() -> Dict[str, Any]:
    """Load the document registry from file."""
    ensure_directories()
    if os.path.exists(DOCUMENT_REGISTRY_FILE):
        with open(DOCUMENT_REGISTRY_FILE, 'r') as f:
            return json.load(f)
    return {"documents": {}}


def save_document_registry(registry: Dict[str, Any]):
    """Save the document registry to file."""
    ensure_directories()
    with open(DOCUMENT_REGISTRY_FILE, 'w') as f:
        json.dump(registry, f, indent=2)


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from a PDF file."""
    try:
        reader = PdfReader(file_path)
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        return "\n\n".join(text_parts)
    except Exception as e:
        return f"[Error extracting PDF text: {str(e)}]"


def extract_text_from_docx(file_path: str) -> str:
    """Extract text from a DOCX file."""
    try:
        doc = DocxDocument(file_path)
        text_parts = []
        for para in doc.paragraphs:
            if para.text.strip():
                text_parts.append(para.text)
        # Also extract from tables
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    text_parts.append(row_text)
        return "\n\n".join(text_parts)
    except Exception as e:
        return f"[Error extracting DOCX text: {str(e)}]"


def extract_text_from_pptx(file_path: str) -> str:
    """Extract text from a PowerPoint file."""
    try:
        prs = Presentation(file_path)
        text_parts = []
        for slide_num, slide in enumerate(prs.slides, 1):
            slide_texts = [f"--- Slide {slide_num} ---"]
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    slide_texts.append(shape.text)
            if len(slide_texts) > 1:  # More than just the header
                text_parts.append("\n".join(slide_texts))
        return "\n\n".join(text_parts)
    except Exception as e:
        return f"[Error extracting PPTX text: {str(e)}]"


def extract_text_from_txt(file_path: str) -> str:
    """Extract text from a plain text file."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception as e:
        return f"[Error reading text file: {str(e)}]"


def extract_text_from_image(file_path: str) -> str:
    """Extract description from an image file (placeholder for OCR)."""
    try:
        img = Image.open(file_path)
        width, height = img.size
        format_type = img.format or "Unknown"
        mode = img.mode
        return f"[Image file: {format_type} format, {width}x{height} pixels, {mode} mode. OCR not available - image content cannot be automatically extracted. Consider describing the image content in your query.]"
    except Exception as e:
        return f"[Error processing image: {str(e)}]"


def extract_text_from_file(file_path: str, extension: str) -> str:
    """Extract text from a file based on its extension."""
    ext = extension.lower()
    
    if ext == '.pdf':
        return extract_text_from_pdf(file_path)
    elif ext in ['.docx', '.doc']:
        return extract_text_from_docx(file_path)
    elif ext in ['.pptx', '.ppt']:
        return extract_text_from_pptx(file_path)
    elif ext in ['.txt', '.rtf', '.md']:
        return extract_text_from_txt(file_path)
    elif ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
        return extract_text_from_image(file_path)
    else:
        return f"[Unsupported file format: {ext}]"


def chunk_text(text: str, max_chunk_size: int = MAX_CHUNK_SIZE) -> List[str]:
    """Split text into chunks for LLM context windows."""
    if len(text) <= max_chunk_size:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    # Split by paragraphs first
    paragraphs = text.split("\n\n")
    
    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 <= max_chunk_size:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para
        else:
            if current_chunk:
                chunks.append(current_chunk)
            # If paragraph itself is too long, split it
            if len(para) > max_chunk_size:
                words = para.split()
                current_chunk = ""
                for word in words:
                    if len(current_chunk) + len(word) + 1 <= max_chunk_size:
                        current_chunk += (" " if current_chunk else "") + word
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = word
            else:
                current_chunk = para
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks


async def process_uploaded_file(
    file_content: bytes,
    filename: str,
    content_type: Optional[str] = None
) -> Dict[str, Any]:
    """Process an uploaded file and store it."""
    ensure_directories()
    
    # Get file extension
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}. Supported types: {', '.join(SUPPORTED_EXTENSIONS.keys())}")
    
    # Check file size
    if len(file_content) > MAX_FILE_SIZE:
        raise ValueError(f"File too large. Maximum size is {MAX_FILE_SIZE / (1024*1024):.0f}MB")
    
    # Generate unique ID
    doc_id = str(uuid.uuid4())
    
    # Save file
    file_path = os.path.join(DOCUMENTS_DIR, f"{doc_id}{ext}")
    with open(file_path, 'wb') as f:
        f.write(file_content)
    
    # Extract text
    extracted_text = extract_text_from_file(file_path, ext)
    
    # Create chunks
    chunks = chunk_text(extracted_text)
    
    # Create document metadata
    document = {
        "id": doc_id,
        "filename": filename,
        "extension": ext,
        "content_type": content_type or SUPPORTED_EXTENSIONS.get(ext, 'application/octet-stream'),
        "size": len(file_content),
        "file_path": file_path,
        "uploaded_at": datetime.utcnow().isoformat(),
        "extracted_text": extracted_text,
        "chunks": chunks,
        "chunk_count": len(chunks),
        "text_length": len(extracted_text),
        "is_active": True  # Whether to include in council context
    }
    
    # Save to registry
    registry = load_document_registry()
    registry["documents"][doc_id] = document
    save_document_registry(registry)
    
    # Return metadata (without full text for response)
    return {
        "id": doc_id,
        "filename": filename,
        "extension": ext,
        "size": len(file_content),
        "uploaded_at": document["uploaded_at"],
        "chunk_count": len(chunks),
        "text_length": len(extracted_text),
        "is_active": True,
        "preview": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text
    }


def get_document(doc_id: str) -> Optional[Dict[str, Any]]:
    """Get a document by ID."""
    registry = load_document_registry()
    return registry["documents"].get(doc_id)


def get_document_text(doc_id: str) -> Optional[str]:
    """Get the extracted text from a document."""
    doc = get_document(doc_id)
    if doc:
        return doc.get("extracted_text", "")
    return None


def list_documents() -> List[Dict[str, Any]]:
    """List all documents (metadata only)."""
    registry = load_document_registry()
    documents = []
    for doc_id, doc in registry["documents"].items():
        documents.append({
            "id": doc["id"],
            "filename": doc["filename"],
            "extension": doc["extension"],
            "size": doc["size"],
            "uploaded_at": doc["uploaded_at"],
            "chunk_count": doc.get("chunk_count", 1),
            "text_length": doc.get("text_length", 0),
            "is_active": doc.get("is_active", True),
            "preview": doc.get("extracted_text", "")[:200] + "..." if len(doc.get("extracted_text", "")) > 200 else doc.get("extracted_text", "")
        })
    # Sort by upload time, newest first
    documents.sort(key=lambda x: x["uploaded_at"], reverse=True)
    return documents


def delete_document(doc_id: str) -> bool:
    """Delete a document and its file."""
    registry = load_document_registry()
    if doc_id not in registry["documents"]:
        return False
    
    doc = registry["documents"][doc_id]
    
    # Delete file
    file_path = doc.get("file_path")
    if file_path and os.path.exists(file_path):
        os.remove(file_path)
    
    # Remove from registry
    del registry["documents"][doc_id]
    save_document_registry(registry)
    
    return True


def toggle_document_active(doc_id: str, is_active: bool) -> bool:
    """Toggle whether a document is active in the conversation context."""
    registry = load_document_registry()
    if doc_id not in registry["documents"]:
        return False
    
    registry["documents"][doc_id]["is_active"] = is_active
    save_document_registry(registry)
    return True


def get_active_documents_context() -> str:
    """Get combined context from all active documents."""
    registry = load_document_registry()
    context_parts = []
    
    for doc_id, doc in registry["documents"].items():
        if doc.get("is_active", True):
            filename = doc.get("filename", "Unknown")
            text = doc.get("extracted_text", "")
            if text:
                context_parts.append(f"=== Document: {filename} ===\n{text}")
    
    if context_parts:
        return "\n\n".join(context_parts)
    return ""


def get_active_document_ids() -> List[str]:
    """Get IDs of all active documents."""
    registry = load_document_registry()
    return [doc_id for doc_id, doc in registry["documents"].items() if doc.get("is_active", True)]
