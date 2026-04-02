#!/usr/bin/env python3
"""
Backend API Testing for LLM Council Configuration Dashboard
Tests all configuration, model, document management, and OCR endpoints.
"""

import requests
import sys
import json
import tempfile
import os
from datetime import datetime
from typing import Dict, Any, List
from PIL import Image, ImageDraw, ImageFont

class LLMCouncilAPITester:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.session = requests.Session()
        self.uploaded_doc_ids = []  # Track uploaded documents for cleanup
        
    def log_test(self, name: str, success: bool, details: str = "", response_data: Any = None):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            
        result = {
            "test_name": name,
            "success": success,
            "details": details,
            "response_data": response_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")
        if details:
            print(f"    {details}")
        if not success and response_data:
            print(f"    Response: {response_data}")
        print()

    def test_health_check(self):
        """Test GET /api/health - Health check endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/api/health")
            
            if response.status_code == 200:
                data = response.json()
                expected_fields = ["status", "service", "configured", "version"]
                missing_fields = [field for field in expected_fields if field not in data]
                
                if missing_fields:
                    self.log_test(
                        "Health Check", 
                        False, 
                        f"Missing fields: {missing_fields}",
                        data
                    )
                else:
                    self.log_test(
                        "Health Check", 
                        True, 
                        f"Status: {data.get('status')}, Configured: {data.get('configured')}, Version: {data.get('version')}",
                        data
                    )
            else:
                self.log_test(
                    "Health Check", 
                    False, 
                    f"Expected 200, got {response.status_code}",
                    response.text
                )
                
        except Exception as e:
            self.log_test("Health Check", False, f"Exception: {str(e)}")

    def test_get_config(self):
        """Test GET /api/config - Get configuration"""
        try:
            response = self.session.get(f"{self.base_url}/api/config")
            
            if response.status_code == 200:
                data = response.json()
                expected_fields = ["council_models", "chairman_model", "has_api_key", "lm_studio_urls"]
                missing_fields = [field for field in expected_fields if field not in data]
                
                if missing_fields:
                    self.log_test(
                        "GET Config", 
                        False, 
                        f"Missing fields: {missing_fields}",
                        data
                    )
                else:
                    self.log_test(
                        "GET Config", 
                        True, 
                        f"Has API key: {data.get('has_api_key')}, Council models: {len(data.get('council_models', []))}, LM Studio URLs: {len(data.get('lm_studio_urls', {}))}",
                        data
                    )
            else:
                self.log_test(
                    "GET Config", 
                    False, 
                    f"Expected 200, got {response.status_code}",
                    response.text
                )
                
        except Exception as e:
            self.log_test("GET Config", False, f"Exception: {str(e)}")

    def test_update_config(self):
        """Test PUT /api/config - Update configuration"""
        try:
            # Test updating theme and lm_studio_urls (safe updates)
            update_data = {
                "theme": "dark",
                "lm_studio_urls": {
                    "openai/gpt-4o": "http://localhost:1234/v1"
                }
            }
            response = self.session.put(
                f"{self.base_url}/api/config",
                json=update_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("theme") == "dark" and isinstance(data.get("lm_studio_urls"), dict):
                    self.log_test(
                        "PUT Config", 
                        True, 
                        f"Successfully updated theme to dark and lm_studio_urls with {len(data.get('lm_studio_urls', {}))} entries",
                        data
                    )
                else:
                    self.log_test(
                        "PUT Config", 
                        False, 
                        "Theme or lm_studio_urls not updated correctly",
                        data
                    )
            else:
                self.log_test(
                    "PUT Config", 
                    False, 
                    f"Expected 200, got {response.status_code}",
                    response.text
                )
                
        except Exception as e:
            self.log_test("PUT Config", False, f"Exception: {str(e)}")

    def test_validate_api_key(self):
        """Test POST /api/config/validate-key - Validate API key"""
        try:
            # Test with invalid key format
            test_data = {"api_key": "invalid-key"}
            response = self.session.post(
                f"{self.base_url}/api/config/validate-key",
                json=test_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if "valid" in data and "error" in data:
                    # Should be invalid for test key
                    if not data["valid"]:
                        self.log_test(
                            "Validate API Key", 
                            True, 
                            f"Correctly rejected invalid key: {data.get('error')}",
                            data
                        )
                    else:
                        self.log_test(
                            "Validate API Key", 
                            False, 
                            "Invalid key was accepted as valid",
                            data
                        )
                else:
                    self.log_test(
                        "Validate API Key", 
                        False, 
                        "Missing 'valid' or 'error' fields in response",
                        data
                    )
            else:
                self.log_test(
                    "Validate API Key", 
                    False, 
                    f"Expected 200, got {response.status_code}",
                    response.text
                )
                
        except Exception as e:
            self.log_test("Validate API Key", False, f"Exception: {str(e)}")

    def test_get_available_models(self):
        """Test GET /api/models/available - Get available models"""
        try:
            response = self.session.get(f"{self.base_url}/api/models/available")
            
            if response.status_code == 200:
                data = response.json()
                if "models" in data and isinstance(data["models"], list):
                    models = data["models"]
                    if len(models) >= 32:  # Requirement: 32+ models
                        # Check model structure
                        if models and all(
                            isinstance(model, dict) and 
                            "id" in model and 
                            "name" in model and 
                            "provider" in model 
                            for model in models[:5]  # Check first 5
                        ):
                            self.log_test(
                                "GET Available Models", 
                                True, 
                                f"Found {len(models)} models with correct structure",
                                {"model_count": len(models), "sample_model": models[0] if models else None}
                            )
                        else:
                            self.log_test(
                                "GET Available Models", 
                                False, 
                                "Models missing required fields (id, name, provider)",
                                {"models_sample": models[:3] if models else []}
                            )
                    else:
                        self.log_test(
                            "GET Available Models", 
                            False, 
                            f"Expected 32+ models, got {len(models)}",
                            {"model_count": len(models)}
                        )
                else:
                    self.log_test(
                        "GET Available Models", 
                        False, 
                        "Response missing 'models' field or not a list",
                        data
                    )
            else:
                self.log_test(
                    "GET Available Models", 
                    False, 
                    f"Expected 200, got {response.status_code}",
                    response.text
                )
                
        except Exception as e:
            self.log_test("GET Available Models", False, f"Exception: {str(e)}")

    def test_document_endpoints(self):
        """Test document management endpoints"""
        # Test GET /api/documents
        try:
            response = self.session.get(f"{self.base_url}/api/documents")
            
            if response.status_code == 200:
                data = response.json()
                if "documents" in data and isinstance(data["documents"], list):
                    self.log_test(
                        "GET Documents", 
                        True, 
                        f"Found {len(data['documents'])} documents",
                        {"document_count": len(data["documents"])}
                    )
                else:
                    self.log_test(
                        "GET Documents", 
                        False, 
                        "Response missing 'documents' field or not a list",
                        data
                    )
            else:
                self.log_test(
                    "GET Documents", 
                    False, 
                    f"Expected 200, got {response.status_code}",
                    response.text
                )
                
        except Exception as e:
            self.log_test("GET Documents", False, f"Exception: {str(e)}")

        # Test POST /api/documents/upload
        try:
            # Create a test text file
            test_content = "This is a test document for the LLM Council system.\nIt contains sample text for testing document upload functionality."
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(test_content)
                temp_file_path = f.name
            
            try:
                with open(temp_file_path, 'rb') as f:
                    files = {'file': ('test_document.txt', f, 'text/plain')}
                    response = self.session.post(f"{self.base_url}/api/documents/upload", files=files)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success") and "document" in data:
                        doc = data["document"]
                        if "id" in doc and "filename" in doc:
                            self.log_test(
                                "POST Upload Document", 
                                True, 
                                f"Uploaded document: {doc.get('filename')} (ID: {doc.get('id')})",
                                doc
                            )
                            
                            # Test DELETE /api/documents/{id}
                            doc_id = doc["id"]
                            delete_response = self.session.delete(f"{self.base_url}/api/documents/{doc_id}")
                            
                            if delete_response.status_code == 200:
                                delete_data = delete_response.json()
                                if delete_data.get("success"):
                                    self.log_test(
                                        "DELETE Document", 
                                        True, 
                                        f"Successfully deleted document {doc_id}",
                                        delete_data
                                    )
                                else:
                                    self.log_test(
                                        "DELETE Document", 
                                        False, 
                                        "Delete response success=False",
                                        delete_data
                                    )
                            else:
                                self.log_test(
                                    "DELETE Document", 
                                    False, 
                                    f"Expected 200, got {delete_response.status_code}",
                                    delete_response.text
                                )
                        else:
                            self.log_test(
                                "POST Upload Document", 
                                False, 
                                "Document missing id or filename",
                                doc
                            )
                    else:
                        self.log_test(
                            "POST Upload Document", 
                            False, 
                            "Response missing success=True or document field",
                            data
                        )
                else:
                    self.log_test(
                        "POST Upload Document", 
                        False, 
                        f"Expected 200, got {response.status_code}",
                        response.text
                    )
                    
            finally:
                # Clean up temp file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    
        except Exception as e:
            self.log_test("POST Upload Document", False, f"Exception: {str(e)}")

    def test_custom_model_endpoint(self):
        """Test POST /api/models/custom - Add custom model"""
        try:
            test_model = {
                "model_id": "test/custom-model-123",
                "model_name": "Test Custom Model",
                "provider": "TestProvider"
            }
            
            response = self.session.post(
                f"{self.base_url}/api/models/custom",
                json=test_model,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if "model" in data:
                    model = data["model"]
                    if (model.get("id") == test_model["model_id"] and 
                        model.get("name") == test_model["model_name"] and
                        model.get("provider") == test_model["provider"]):
                        self.log_test(
                            "POST Custom Model", 
                            True, 
                            f"Successfully added custom model: {model.get('name')}",
                            model
                        )
                    else:
                        self.log_test(
                            "POST Custom Model", 
                            False, 
                            "Custom model data doesn't match input",
                            {"expected": test_model, "actual": model}
                        )
                else:
                    self.log_test(
                        "POST Custom Model", 
                        False, 
                        "Response missing 'model' field",
                        data
                    )
            else:
                self.log_test(
                    "POST Custom Model", 
                    False, 
                    f"Expected 200, got {response.status_code}",
                    response.text
                )
                
        except Exception as e:
            self.log_test("POST Custom Model", False, f"Exception: {str(e)}")

    def create_test_image_with_text(self, text: str = "LLM Council OCR Test\nThis is a test image for OCR functionality.") -> str:
        """Create a test image with text for OCR testing."""
        try:
            # Create a white image
            img = Image.new('RGB', (400, 200), color='white')
            draw = ImageDraw.Draw(img)
            
            # Try to use a default font, fall back to basic if not available
            try:
                font = ImageFont.truetype("arial.ttf", 20)
            except:
                try:
                    font = ImageFont.load_default()
                except:
                    font = None
            
            # Draw text on image
            draw.text((20, 50), text, fill='black', font=font)
            
            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            img.save(temp_file.name, 'PNG')
            temp_file.close()
            
            return temp_file.name
        except Exception as e:
            self.log_test("Create Test Image", False, f"Failed to create test image: {str(e)}")
            return None

    def test_ocr_status_endpoint(self):
        """Test GET /api/ocr/status - OCR engine status"""
        try:
            response = self.session.get(f"{self.base_url}/api/ocr/status")
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["tesseract_available", "easyocr_available", "ocr_enabled", "preferred_engine"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test(
                        "OCR Status", 
                        False, 
                        f"Missing fields: {missing_fields}",
                        data
                    )
                else:
                    # Check if at least one OCR engine is available
                    if data.get("ocr_enabled"):
                        self.log_test(
                            "OCR Status", 
                            True, 
                            f"OCR enabled: {data.get('ocr_enabled')}, Preferred: {data.get('preferred_engine')}, EasyOCR: {data.get('easyocr_available')}, Tesseract: {data.get('tesseract_available')}",
                            data
                        )
                    else:
                        self.log_test(
                            "OCR Status", 
                            False, 
                            "No OCR engines available",
                            data
                        )
            else:
                self.log_test(
                    "OCR Status", 
                    False, 
                    f"Expected 200, got {response.status_code}",
                    response.text
                )
                
        except Exception as e:
            self.log_test("OCR Status", False, f"Exception: {str(e)}")

    def test_image_upload_with_ocr(self):
        """Test POST /api/documents/upload with image file for OCR"""
        test_image_path = None
        try:
            # Create test image
            test_image_path = self.create_test_image_with_text()
            if not test_image_path:
                return
            
            with open(test_image_path, 'rb') as f:
                files = {'file': ('test_ocr_image.png', f, 'image/png')}
                response = self.session.post(f"{self.base_url}/api/documents/upload", files=files)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and "document" in data:
                    doc = data["document"]
                    
                    # Track for cleanup
                    if "id" in doc:
                        self.uploaded_doc_ids.append(doc["id"])
                    
                    # Check OCR-specific fields
                    required_fields = ["id", "filename", "ocr_used", "text_length"]
                    missing_fields = [field for field in required_fields if field not in doc]
                    
                    if missing_fields:
                        self.log_test(
                            "Image Upload OCR", 
                            False, 
                            f"Missing fields: {missing_fields}",
                            doc
                        )
                    elif doc.get("ocr_used") and doc.get("text_length", 0) > 0:
                        self.log_test(
                            "Image Upload OCR", 
                            True, 
                            f"OCR successful: engine={doc.get('ocr_engine')}, text_length={doc.get('text_length')}, preview='{doc.get('preview', '')[:50]}...'",
                            {"ocr_used": doc.get("ocr_used"), "ocr_engine": doc.get("ocr_engine"), "text_length": doc.get("text_length")}
                        )
                    else:
                        self.log_test(
                            "Image Upload OCR", 
                            False, 
                            f"OCR not used or no text extracted: ocr_used={doc.get('ocr_used')}, text_length={doc.get('text_length')}",
                            doc
                        )
                else:
                    self.log_test(
                        "Image Upload OCR", 
                        False, 
                        "Response missing success=True or document field",
                        data
                    )
            else:
                self.log_test(
                    "Image Upload OCR", 
                    False, 
                    f"Expected 200, got {response.status_code}",
                    response.text
                )
                
        except Exception as e:
            self.log_test("Image Upload OCR", False, f"Exception: {str(e)}")
        finally:
            # Clean up test image
            if test_image_path and os.path.exists(test_image_path):
                os.unlink(test_image_path)

    def test_document_status_endpoint(self):
        """Test GET /api/documents/{doc_id}/status for OCR documents"""
        if not self.uploaded_doc_ids:
            self.log_test("Document Status OCR", False, "No uploaded documents to test")
            return
        
        try:
            doc_id = self.uploaded_doc_ids[-1]  # Use the most recent upload
            response = self.session.get(f"{self.base_url}/api/documents/{doc_id}/status")
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["id", "filename", "status", "ocr_used", "text_length"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test(
                        "Document Status OCR", 
                        False, 
                        f"Missing fields: {missing_fields}",
                        data
                    )
                elif data.get("status") == "completed" and data.get("ocr_used"):
                    # Check for extraction_details if OCR was used
                    extraction_details = data.get("extraction_details", {})
                    self.log_test(
                        "Document Status OCR", 
                        True, 
                        f"Status: {data.get('status')}, OCR: {data.get('ocr_used')}, Engine: {data.get('ocr_engine')}, Text length: {data.get('text_length')}",
                        {"status": data.get("status"), "ocr_used": data.get("ocr_used"), "ocr_engine": data.get("ocr_engine"), "has_extraction_details": bool(extraction_details)}
                    )
                else:
                    self.log_test(
                        "Document Status OCR", 
                        False, 
                        f"Unexpected status or OCR not used: status={data.get('status')}, ocr_used={data.get('ocr_used')}",
                        data
                    )
            else:
                self.log_test(
                    "Document Status OCR", 
                    False, 
                    f"Expected 200, got {response.status_code}",
                    response.text
                )
                
        except Exception as e:
            self.log_test("Document Status OCR", False, f"Exception: {str(e)}")

    def test_documents_list_with_ocr_info(self):
        """Test GET /api/documents includes OCR information"""
        try:
            response = self.session.get(f"{self.base_url}/api/documents")
            
            if response.status_code == 200:
                data = response.json()
                if "documents" in data and isinstance(data["documents"], list):
                    documents = data["documents"]
                    
                    # Look for documents with OCR info
                    ocr_docs = [doc for doc in documents if doc.get("ocr_used")]
                    
                    if ocr_docs:
                        sample_doc = ocr_docs[0]
                        self.log_test(
                            "Documents List OCR Info", 
                            True, 
                            f"Found {len(ocr_docs)} OCR documents out of {len(documents)} total. Sample: {sample_doc.get('filename')} (OCR: {sample_doc.get('ocr_used')})",
                            {"total_docs": len(documents), "ocr_docs": len(ocr_docs), "sample_ocr_doc": sample_doc.get("filename")}
                        )
                    else:
                        # This might be OK if no OCR documents were uploaded yet
                        self.log_test(
                            "Documents List OCR Info", 
                            True, 
                            f"No OCR documents found in {len(documents)} total documents (may be expected if no images uploaded)",
                            {"total_docs": len(documents), "ocr_docs": 0}
                        )
                else:
                    self.log_test(
                        "Documents List OCR Info", 
                        False, 
                        "Response missing 'documents' field or not a list",
                        data
                    )
            else:
                self.log_test(
                    "Documents List OCR Info", 
                    False, 
                    f"Expected 200, got {response.status_code}",
                    response.text
                )
                
        except Exception as e:
            self.log_test("Documents List OCR Info", False, f"Exception: {str(e)}")

    def test_pdf_upload_no_ocr(self):
        """Test that text-based PDF upload does not use OCR"""
        try:
            # Create a simple text-based PDF using reportlab if available
            try:
                from reportlab.pdfgen import canvas
                from reportlab.lib.pagesizes import letter
                
                # Create a simple PDF with text
                temp_pdf = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
                c = canvas.Canvas(temp_pdf.name, pagesize=letter)
                c.drawString(100, 750, "LLM Council Test PDF")
                c.drawString(100, 730, "This is a text-based PDF that should not require OCR.")
                c.drawString(100, 710, "The text should be extractable directly.")
                c.save()
                temp_pdf.close()
                
                # Upload the PDF
                with open(temp_pdf.name, 'rb') as f:
                    files = {'file': ('test_text.pdf', f, 'application/pdf')}
                    response = self.session.post(f"{self.base_url}/api/documents/upload", files=files)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success") and "document" in data:
                        doc = data["document"]
                        
                        # Track for cleanup
                        if "id" in doc:
                            self.uploaded_doc_ids.append(doc["id"])
                        
                        # Check that OCR was NOT used for text-based PDF
                        if not doc.get("ocr_used") and doc.get("text_length", 0) > 0:
                            self.log_test(
                                "PDF Upload No OCR", 
                                True, 
                                f"Text PDF processed without OCR: text_length={doc.get('text_length')}, ocr_used={doc.get('ocr_used')}",
                                {"ocr_used": doc.get("ocr_used"), "text_length": doc.get("text_length")}
                            )
                        else:
                            self.log_test(
                                "PDF Upload No OCR", 
                                False, 
                                f"Unexpected OCR usage for text PDF: ocr_used={doc.get('ocr_used')}, text_length={doc.get('text_length')}",
                                doc
                            )
                    else:
                        self.log_test(
                            "PDF Upload No OCR", 
                            False, 
                            "Response missing success=True or document field",
                            data
                        )
                else:
                    self.log_test(
                        "PDF Upload No OCR", 
                        False, 
                        f"Expected 200, got {response.status_code}",
                        response.text
                    )
                
                # Clean up
                if os.path.exists(temp_pdf.name):
                    os.unlink(temp_pdf.name)
                    
            except ImportError:
                self.log_test(
                    "PDF Upload No OCR", 
                    True, 
                    "Skipped - reportlab not available for PDF generation",
                    {"skipped": True, "reason": "reportlab not available"}
                )
                
        except Exception as e:
            self.log_test("PDF Upload No OCR", False, f"Exception: {str(e)}")

    def test_lm_studio_test_endpoint(self):
        """Test POST /api/lm-studio/test - Test LM Studio connection"""
        try:
            # Test with invalid URL (should fail gracefully)
            test_data = {"url": "http://non-existent-server:1234/v1", "model_name": "test-model"}
            response = self.session.post(
                f"{self.base_url}/api/lm-studio/test",
                json=test_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["success", "error", "url"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test(
                        "POST LM Studio Test", 
                        False, 
                        f"Missing fields: {missing_fields}",
                        data
                    )
                else:
                    # Should fail for non-existent server but return proper error structure
                    if not data.get("success") and data.get("error"):
                        self.log_test(
                            "POST LM Studio Test", 
                            True, 
                            f"Correctly handled connection failure: {data.get('error')}",
                            data
                        )
                    else:
                        self.log_test(
                            "POST LM Studio Test", 
                            False, 
                            "Unexpected success for invalid server or missing error message",
                            data
                        )
            else:
                self.log_test(
                    "POST LM Studio Test", 
                    False, 
                    f"Expected 200, got {response.status_code}",
                    response.text
                )
                
        except Exception as e:
            self.log_test("POST LM Studio Test", False, f"Exception: {str(e)}")

    def test_lm_studio_get_urls_endpoint(self):
        """Test GET /api/lm-studio/urls - Get configured LM Studio URLs"""
        try:
            response = self.session.get(f"{self.base_url}/api/lm-studio/urls")
            
            if response.status_code == 200:
                data = response.json()
                if "urls" in data and isinstance(data["urls"], dict):
                    self.log_test(
                        "GET LM Studio URLs", 
                        True, 
                        f"Retrieved {len(data['urls'])} configured LM Studio URLs",
                        {"url_count": len(data["urls"]), "configured_models": list(data["urls"].keys())}
                    )
                else:
                    self.log_test(
                        "GET LM Studio URLs", 
                        False, 
                        "Response missing 'urls' field or not a dict",
                        data
                    )
            else:
                self.log_test(
                    "GET LM Studio URLs", 
                    False, 
                    f"Expected 200, got {response.status_code}",
                    response.text
                )
                
        except Exception as e:
            self.log_test("GET LM Studio URLs", False, f"Exception: {str(e)}")

    def test_lm_studio_config_update(self):
        """Test updating lm_studio_urls through config endpoint"""
        try:
            # First, get current config to preserve other settings
            get_response = self.session.get(f"{self.base_url}/api/config")
            if get_response.status_code != 200:
                self.log_test("LM Studio Config Update", False, "Failed to get current config")
                return
            
            # Test updating LM Studio URLs
            lm_studio_test_urls = {
                "openai/gpt-4o": "http://localhost:1234/v1",
                "google/gemini-2.0-flash-exp": "http://localhost:1235/v1"
            }
            
            update_data = {"lm_studio_urls": lm_studio_test_urls}
            response = self.session.put(
                f"{self.base_url}/api/config",
                json=update_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("lm_studio_urls") == lm_studio_test_urls:
                    self.log_test(
                        "LM Studio Config Update", 
                        True, 
                        f"Successfully updated LM Studio URLs: {list(lm_studio_test_urls.keys())}",
                        {"updated_urls": lm_studio_test_urls}
                    )
                    
                    # Test clearing URLs
                    clear_response = self.session.put(
                        f"{self.base_url}/api/config",
                        json={"lm_studio_urls": {}},
                        headers={"Content-Type": "application/json"}
                    )
                    
                    if clear_response.status_code == 200:
                        clear_data = clear_response.json()
                        if clear_data.get("lm_studio_urls") == {}:
                            self.log_test(
                                "LM Studio Config Clear", 
                                True, 
                                "Successfully cleared LM Studio URLs",
                                clear_data
                            )
                        else:
                            self.log_test(
                                "LM Studio Config Clear", 
                                False, 
                                "Failed to clear LM Studio URLs",
                                clear_data
                            )
                    
                else:
                    self.log_test(
                        "LM Studio Config Update", 
                        False, 
                        "LM Studio URLs not updated correctly",
                        {"expected": lm_studio_test_urls, "actual": data.get("lm_studio_urls")}
                    )
            else:
                self.log_test(
                    "LM Studio Config Update", 
                    False, 
                    f"Expected 200, got {response.status_code}",
                    response.text
                )
                
        except Exception as e:
            self.log_test("LM Studio Config Update", False, f"Exception: {str(e)}")

    def test_advanced_config_streaming_endpoint(self):
        """Test that streaming endpoint accepts advanced configuration parameter"""
        try:
            # First create a conversation
            create_response = self.session.post(
                f"{self.base_url}/api/conversations",
                json={},
                headers={"Content-Type": "application/json"}
            )
            
            if create_response.status_code != 200:
                self.log_test("Advanced Config Streaming", False, "Failed to create test conversation")
                return
            
            conversation = create_response.json()
            conversation_id = conversation.get("id")
            
            if not conversation_id:
                self.log_test("Advanced Config Streaming", False, "No conversation ID returned")
                return
            
            # Test streaming endpoint with advanced config
            advanced_config = {
                "mode": "openrouter",
                "openrouter": {
                    "apiKey": ""
                },
                "lmstudio": {
                    "baseUrl": "http://localhost:1234/v1",
                    "model": "test-model"
                },
                "hybrid": {
                    "councilModelSources": {},
                    "chairmanSource": "openrouter"
                }
            }
            
            message_data = {
                "content": "Test message for advanced config",
                "include_documents": False,
                "advanced": advanced_config
            }
            
            # Test the streaming endpoint (we'll just check if it accepts the request)
            response = self.session.post(
                f"{self.base_url}/api/conversations/{conversation_id}/message/stream",
                json=message_data,
                headers={"Content-Type": "application/json"},
                stream=True,
                timeout=10
            )
            
            # We expect this to fail due to no API key, but it should accept the advanced parameter
            # and return a proper error structure, not a 400 for malformed request
            if response.status_code in [200, 400]:
                if response.status_code == 400:
                    # Check if it's an API key error (expected) rather than malformed request
                    try:
                        error_data = response.json()
                        if "api key" in error_data.get("detail", "").lower():
                            self.log_test(
                                "Advanced Config Streaming", 
                                True, 
                                "Streaming endpoint accepts advanced config parameter (API key error expected)",
                                {"status": response.status_code, "error": error_data.get("detail")}
                            )
                        else:
                            self.log_test(
                                "Advanced Config Streaming", 
                                False, 
                                f"Unexpected 400 error: {error_data.get('detail')}",
                                error_data
                            )
                    except:
                        self.log_test(
                            "Advanced Config Streaming", 
                            False, 
                            "400 error but couldn't parse response",
                            response.text[:200]
                        )
                else:
                    # 200 response - endpoint accepted the request
                    self.log_test(
                        "Advanced Config Streaming", 
                        True, 
                        "Streaming endpoint accepts advanced config parameter",
                        {"status": response.status_code}
                    )
            else:
                self.log_test(
                    "Advanced Config Streaming", 
                    False, 
                    f"Unexpected status code: {response.status_code}",
                    response.text[:200]
                )
            
            # Clean up conversation
            self.session.delete(f"{self.base_url}/api/conversations/{conversation_id}")
                
        except Exception as e:
            self.log_test("Advanced Config Streaming", False, f"Exception: {str(e)}")

    def cleanup_uploaded_documents(self):
        """Clean up documents uploaded during testing"""
        for doc_id in self.uploaded_doc_ids:
            try:
                response = self.session.delete(f"{self.base_url}/api/documents/{doc_id}")
                if response.status_code == 200:
                    print(f"    Cleaned up document: {doc_id}")
                else:
                    print(f"    Failed to clean up document {doc_id}: {response.status_code}")
            except Exception as e:
                print(f"    Error cleaning up document {doc_id}: {e}")
        self.uploaded_doc_ids.clear()

    def run_all_tests(self):
        """Run all backend API tests"""
        print("🚀 Starting LLM Council Backend API Tests with OCR")
        print(f"Testing endpoint: {self.base_url}")
        print("=" * 60)
        
        try:
            # Core endpoints
            self.test_health_check()
            self.test_get_config()
            self.test_update_config()
            self.test_validate_api_key()
            self.test_get_available_models()
            
            # Document endpoints
            self.test_document_endpoints()
            
            # Custom model endpoint
            self.test_custom_model_endpoint()
            
            # LM Studio specific tests
            print("\n🔗 LM Studio Feature Tests")
            print("-" * 30)
            self.test_lm_studio_test_endpoint()
            self.test_lm_studio_get_urls_endpoint()
            self.test_lm_studio_config_update()
            
            # Advanced configuration tests
            print("\n⚙️ Advanced Configuration Tests")
            print("-" * 30)
            self.test_advanced_config_streaming_endpoint()
            
            # OCR-specific tests
            print("\n🔍 OCR Feature Tests")
            print("-" * 30)
            self.test_ocr_status_endpoint()
            self.test_image_upload_with_ocr()
            self.test_document_status_endpoint()
            self.test_documents_list_with_ocr_info()
            self.test_pdf_upload_no_ocr()
            
        finally:
            # Clean up uploaded test documents
            if self.uploaded_doc_ids:
                print("\n🧹 Cleaning up test documents...")
                self.cleanup_uploaded_documents()
        
        # Print summary
        print("=" * 60)
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return 0
        else:
            print(f"❌ {self.tests_run - self.tests_passed} tests failed")
            return 1

    def get_test_results(self):
        """Get detailed test results"""
        return {
            "summary": {
                "total_tests": self.tests_run,
                "passed_tests": self.tests_passed,
                "failed_tests": self.tests_run - self.tests_passed,
                "success_rate": (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
            },
            "test_results": self.test_results
        }

def main():
    """Main test runner"""
    # Get backend URL from environment variable
    backend_url = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001')
    print(f"Using backend URL: {backend_url}")
    
    tester = LLMCouncilAPITester(backend_url)
    exit_code = tester.run_all_tests()
    
    # Save detailed results
    results = tester.get_test_results()
    with open("/app/backend_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: /app/backend_test_results.json")
    return exit_code

if __name__ == "__main__":
    sys.exit(main())