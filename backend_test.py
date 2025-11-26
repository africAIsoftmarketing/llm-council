#!/usr/bin/env python3
"""
Backend API Testing for LLM Council Configuration Dashboard
Tests all configuration, model, and document management endpoints.
"""

import requests
import sys
import json
import tempfile
import os
from datetime import datetime
from typing import Dict, Any, List

class LLMCouncilAPITester:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.session = requests.Session()
        
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
        """Test GET / - Health check endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/")
            
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
                expected_fields = ["council_models", "chairman_model", "has_api_key"]
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
                        f"Has API key: {data.get('has_api_key')}, Council models: {len(data.get('council_models', []))}",
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
            # Test updating theme (safe update)
            update_data = {"theme": "dark"}
            response = self.session.put(
                f"{self.base_url}/api/config",
                json=update_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("theme") == "dark":
                    self.log_test(
                        "PUT Config", 
                        True, 
                        "Successfully updated theme to dark",
                        data
                    )
                else:
                    self.log_test(
                        "PUT Config", 
                        False, 
                        "Theme not updated correctly",
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

    def run_all_tests(self):
        """Run all backend API tests"""
        print("🚀 Starting LLM Council Backend API Tests")
        print(f"Testing endpoint: {self.base_url}")
        print("=" * 60)
        
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
    # Use localhost for internal testing
    tester = LLMCouncilAPITester("http://localhost:8001")
    exit_code = tester.run_all_tests()
    
    # Save detailed results
    results = tester.get_test_results()
    with open("/app/backend_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: /app/backend_test_results.json")
    return exit_code

if __name__ == "__main__":
    sys.exit(main())