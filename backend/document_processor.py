"""Document processing module for extracting text from various file formats with OCR support."""

import os
import sys
import uuid
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import mimetypes
import logging

# Document processing libraries
from PyPDF2 import PdfReader
from docx import Document as DocxDocument
from pptx import Presentation
from PIL import Image
import io

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OCR libraries - loaded lazily to avoid startup delay
_easyocr_reader = None
_tesseract_available = None


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
    '.bmp': 'image/bmp',
    '.tiff': 'image/tiff',
    '.tif': 'image/tiff',
    '.md': 'text/markdown',
}

# Image extensions that support OCR
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tiff', '.tif'}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_CHUNK_SIZE = 4000  # Characters per chunk for context window


# ===== OCR Functions =====

def is_tesseract_available() -> bool:
    """Check if Tesseract OCR is installed and available."""
    global _tesseract_available
    
    if _tesseract_available is not None:
        return _tesseract_available
    
    try:
        import pytesseract
        # Try to get tesseract version to verify it's installed
        pytesseract.get_tesseract_version()
        _tesseract_available = True
        logger.info("Tesseract OCR is available")
    except Exception:
        _tesseract_available = False
        logger.info("Tesseract OCR not available, will use EasyOCR")
    
    return _tesseract_available


def get_easyocr_reader():
    """Get or initialize the EasyOCR reader (lazy loading)."""
    global _easyocr_reader
    
    if _easyocr_reader is None:
        try:
            import easyocr
            logger.info("Initializing EasyOCR reader (this may take a moment on first run)...")
            # Support English by default, can be extended
            _easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            logger.info("EasyOCR reader initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR: {e}")
            return None
    
    return _easyocr_reader


def perform_ocr_tesseract(image: Image.Image) -> str:
    """Perform OCR using Tesseract."""
    try:
        import pytesseract
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Perform OCR
        text = pytesseract.image_to_string(image, lang='eng')
        return text.strip()
    except Exception as e:
        logger.error(f"Tesseract OCR failed: {e}")
        return ""


def perform_ocr_easyocr(image: Image.Image) -> str:
    """Perform OCR using EasyOCR."""
    try:
        reader = get_easyocr_reader()
        if reader is None:
            return ""
        
        # Convert PIL Image to numpy array
        import numpy as np
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        img_array = np.array(image)
        
        # Perform OCR
        results = reader.readtext(img_array, detail=0, paragraph=True)
        
        # Join all detected text
        text = "\n".join(results)
        return text.strip()
    except Exception as e:
        logger.error(f"EasyOCR failed: {e}")
        return ""


def perform_ocr(image: Image.Image, prefer_tesseract: bool = True) -> Tuple[str, str]:
    """
    Perform OCR on an image using available OCR engine.
    
    Args:
        image: PIL Image object
        prefer_tesseract: If True, use Tesseract if available (faster)
    
    Returns:
        Tuple of (extracted_text, ocr_engine_used)
    """
    # Try Tesseract first if preferred and available
    if prefer_tesseract and is_tesseract_available():
        text = perform_ocr_tesseract(image)
        if text:
            return text, "tesseract"
    
    # Fall back to EasyOCR
    text = perform_ocr_easyocr(image)
    if text:
        return text, "easyocr"
    
    # If Tesseract wasn't tried and EasyOCR failed, try Tesseract as last resort
    if not prefer_tesseract and is_tesseract_available():
        text = perform_ocr_tesseract(image)
        if text:
            return text, "tesseract"
    
    return "", "none"


# ===== Directory Management =====

def ensure_directories():
    """Ensure document storage directories exist."""
    Path(DOCUMENTS_DIR).mkdir(parents=True, exist_ok=True)
    Path(BASE_DATA_DIR).mkdir(parents=True, exist_ok=True)


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


# ===== Text Extraction Functions =====

def extract_text_from_pdf(file_path: str, use_ocr: bool = True) -> Tuple[str, Dict[str, Any]]:
    """
    Extract text from a PDF file.
    Uses OCR for scanned PDFs when text extraction yields little/no content.
    
    Returns:
        Tuple of (extracted_text, metadata_dict)
    """
    metadata = {
        "pages": 0,
        "ocr_used": False,
        "ocr_engine": None,
        "ocr_pages": []
    }
    
    try:
        reader = PdfReader(file_path)
        metadata["pages"] = len(reader.pages)
        
        text_parts = []
        ocr_pages = []
        
        for page_num, page in enumerate(reader.pages, 1):
            page_text = page.extract_text() or ""
            
            # Check if page has minimal text (might be scanned)
            if use_ocr and len(page_text.strip()) < 50:
                # Try to extract images from PDF page for OCR
                try:
                    # Check if page has images
                    if '/XObject' in page['/Resources']:
                        xobjects = page['/Resources']['/XObject'].get_object()
                        for obj_name in xobjects:
                            obj = xobjects[obj_name]
                            if obj['/Subtype'] == '/Image':
                                # Extract image data
                                try:
                                    size = (obj['/Width'], obj['/Height'])
                                    data = obj.get_data()
                                    
                                    # Try to create image from data
                                    if '/Filter' in obj:
                                        filter_type = obj['/Filter']
                                        if filter_type == '/DCTDecode':  # JPEG
                                            img = Image.open(io.BytesIO(data))
                                        elif filter_type == '/FlateDecode':  # PNG-like
                                            if '/ColorSpace' in obj:
                                                mode = 'RGB' if obj['/ColorSpace'] == '/DeviceRGB' else 'L'
                                            else:
                                                mode = 'RGB'
                                            img = Image.frombytes(mode, size, data)
                                        else:
                                            continue
                                        
                                        # Perform OCR on extracted image
                                        ocr_text, engine = perform_ocr(img)
                                        if ocr_text:
                                            page_text = ocr_text
                                            ocr_pages.append(page_num)
                                            metadata["ocr_engine"] = engine
                                            break
                                except Exception as img_err:
                                    logger.debug(f"Could not process image from PDF: {img_err}")
                except Exception as ocr_err:
                    logger.debug(f"PDF OCR extraction failed for page {page_num}: {ocr_err}")
            
            if page_text.strip():
                text_parts.append(f"--- Page {page_num} ---\n{page_text}")
        
        metadata["ocr_used"] = len(ocr_pages) > 0
        metadata["ocr_pages"] = ocr_pages
        
        return "\n\n".join(text_parts), metadata
    except Exception as e:
        return f"[Error extracting PDF text: {str(e)}]", metadata


def extract_text_from_docx(file_path: str) -> Tuple[str, Dict[str, Any]]:
    """Extract text from a DOCX file."""
    metadata = {"paragraphs": 0, "tables": 0}
    
    try:
        doc = DocxDocument(file_path)
        text_parts = []
        
        for para in doc.paragraphs:
            if para.text.strip():
                text_parts.append(para.text)
                metadata["paragraphs"] += 1
        
        # Also extract from tables
        for table in doc.tables:
            metadata["tables"] += 1
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    text_parts.append(row_text)
        
        return "\n\n".join(text_parts), metadata
    except Exception as e:
        return f"[Error extracting DOCX text: {str(e)}]", metadata


def extract_text_from_pptx(file_path: str) -> Tuple[str, Dict[str, Any]]:
    """Extract text from a PowerPoint file."""
    metadata = {"slides": 0}
    
    try:
        prs = Presentation(file_path)
        text_parts = []
        
        for slide_num, slide in enumerate(prs.slides, 1):
            metadata["slides"] += 1
            slide_texts = [f"--- Slide {slide_num} ---"]
            
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    slide_texts.append(shape.text)
            
            if len(slide_texts) > 1:  # More than just the header
                text_parts.append("\n".join(slide_texts))
        
        return "\n\n".join(text_parts), metadata
    except Exception as e:
        return f"[Error extracting PPTX text: {str(e)}]", metadata


def extract_text_from_txt(file_path: str) -> Tuple[str, Dict[str, Any]]:
    """Extract text from a plain text file."""
    metadata = {"encoding": "utf-8"}
    
    try:
        # Try UTF-8 first, then fall back to other encodings
        encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                metadata["encoding"] = encoding
                return content, metadata
            except UnicodeDecodeError:
                continue
        
        # Last resort: read with error replacement
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read(), metadata
    except Exception as e:
        return f"[Error reading text file: {str(e)}]", metadata


def extract_text_from_image(file_path: str, use_ocr: bool = True) -> Tuple[str, Dict[str, Any]]:
    """
    Extract text from an image file using OCR.
    
    Returns:
        Tuple of (extracted_text, metadata_dict)
    """
    metadata = {
        "width": 0,
        "height": 0,
        "format": "Unknown",
        "mode": "Unknown",
        "ocr_used": False,
        "ocr_engine": None
    }
    
    try:
        img = Image.open(file_path)
        metadata["width"] = img.size[0]
        metadata["height"] = img.size[1]
        metadata["format"] = img.format or "Unknown"
        metadata["mode"] = img.mode
        
        if not use_ocr:
            return f"[Image: {metadata['format']} format, {metadata['width']}x{metadata['height']} pixels. OCR disabled.]", metadata
        
        # Perform OCR
        logger.info(f"Performing OCR on image: {file_path}")
        ocr_text, engine = perform_ocr(img)
        
        if ocr_text:
            metadata["ocr_used"] = True
            metadata["ocr_engine"] = engine
            
            # Format the result
            header = f"[OCR extracted from {metadata['format']} image ({metadata['width']}x{metadata['height']} px) using {engine}]\n\n"
            return header + ocr_text, metadata
        else:
            return f"[Image: {metadata['format']} format, {metadata['width']}x{metadata['height']} pixels. OCR found no text.]", metadata
            
    except Exception as e:
        return f"[Error processing image: {str(e)}]", metadata


def extract_text_from_file(file_path: str, extension: str, use_ocr: bool = True) -> Tuple[str, Dict[str, Any]]:
    """
    Extract text from a file based on its extension.
    
    Args:
        file_path: Path to the file
        extension: File extension (e.g., '.pdf')
        use_ocr: Whether to use OCR for images and scanned documents
    
    Returns:
        Tuple of (extracted_text, metadata_dict)
    """
    ext = extension.lower()
    
    if ext == '.pdf':
        return extract_text_from_pdf(file_path, use_ocr)
    elif ext in ['.docx', '.doc']:
        return extract_text_from_docx(file_path)
    elif ext in ['.pptx', '.ppt']:
        return extract_text_from_pptx(file_path)
    elif ext in ['.txt', '.rtf', '.md']:
        return extract_text_from_txt(file_path)
    elif ext in IMAGE_EXTENSIONS:
        return extract_text_from_image(file_path, use_ocr)
    else:
        return f"[Unsupported file format: {ext}]", {}


# ===== Text Chunking =====

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


# ===== Document Management =====

async def process_uploaded_file(
    file_content: bytes,
    filename: str,
    content_type: Optional[str] = None,
    use_ocr: bool = True
) -> Dict[str, Any]:
    """
    Process an uploaded file and store it.
    
    Args:
        file_content: Raw file bytes
        filename: Original filename
        content_type: MIME type
        use_ocr: Whether to use OCR for images and scanned documents
    
    Returns:
        Document metadata dictionary
    """
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
    
    # Extract text (with OCR if enabled)
    extracted_text, extraction_metadata = extract_text_from_file(file_path, ext, use_ocr)
    
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
        "is_active": True,
        "extraction_metadata": extraction_metadata,
        "ocr_used": extraction_metadata.get("ocr_used", False)
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
        "ocr_used": document["ocr_used"],
        "ocr_engine": extraction_metadata.get("ocr_engine"),
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
            "ocr_used": doc.get("ocr_used", False),
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
            ocr_note = " (OCR extracted)" if doc.get("ocr_used", False) else ""
            if text:
                context_parts.append(f"=== Document: {filename}{ocr_note} ===\n{text}")
    
    if context_parts:
        return "\n\n".join(context_parts)
    return ""


def get_active_document_ids() -> List[str]:
    """Get IDs of all active documents."""
    registry = load_document_registry()
    return [doc_id for doc_id, doc in registry["documents"].items() if doc.get("is_active", True)]


def get_ocr_status() -> Dict[str, Any]:
    """Get the current OCR engine status."""
    tesseract = is_tesseract_available()
    easyocr = False
    
    try:
        import easyocr
        easyocr = True
    except ImportError:
        pass
    
    return {
        "tesseract_available": tesseract,
        "easyocr_available": easyocr,
        "ocr_enabled": tesseract or easyocr,
        "preferred_engine": "tesseract" if tesseract else ("easyocr" if easyocr else "none")
    }
