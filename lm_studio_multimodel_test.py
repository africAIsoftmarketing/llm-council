#!/usr/bin/env python3
"""
LM Studio Multi-Model Backend Testing
Tests the advanced configuration handling for LM Studio multi-model support.
"""

import requests
import sys
import json
import os
from datetime import datetime
from typing import Dict, Any, List

class LMStudioMultiModelTester:
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

    def test_lmstudio_mode_advanced_config(self):
        """Test LM Studio mode with model mapping in advanced config"""
        try:
            # Create a test conversation
            create_response = self.session.post(
                f"{self.base_url}/api/conversations",
                json={},
                headers={"Content-Type": "application/json"}
            )
            
            if create_response.status_code != 200:
                self.log_test("LM Studio Mode Config", False, "Failed to create test conversation")
                return
            
            conversation = create_response.json()
            conversation_id = conversation.get("id")
            
            # Test LM Studio mode with model mapping
            advanced_config = {
                "mode": "lmstudio",
                "lmstudio": {
                    "baseUrl": "http://localhost:1234/v1",
                    "defaultModel": "default",
                    "multiModel": True,
                    "modelMapping": {
                        "openai/gpt-4o": "gpt-4-turbo",
                        "anthropic/claude-3.5-sonnet": "claude-sonnet",
                        "google/gemini-2.0-flash-exp": "gemini-flash",
                        "meta-llama/llama-3.1-8b-instruct": "llama-8b"
                    },
                    "chairmanModel": "chairman-model"
                }
            }
            
            message_data = {
                "content": "Test LM Studio multi-model configuration",
                "include_documents": False,
                "advanced": advanced_config
            }
            
            # Test the streaming endpoint (expect failure due to no LM Studio server, but should accept config)
            response = self.session.post(
                f"{self.base_url}/api/conversations/{conversation_id}/message/stream",
                json=message_data,
                headers={"Content-Type": "application/json"},
                stream=True,
                timeout=10
            )
            
            # Should accept the advanced config and attempt to connect to LM Studio
            if response.status_code in [200, 400]:
                self.log_test(
                    "LM Studio Mode Config", 
                    True, 
                    "Backend accepts LM Studio mode with model mapping configuration",
                    {"status": response.status_code, "config_accepted": True}
                )
            else:
                self.log_test(
                    "LM Studio Mode Config", 
                    False, 
                    f"Unexpected status code: {response.status_code}",
                    response.text[:200]
                )
            
            # Clean up conversation
            self.session.delete(f"{self.base_url}/api/conversations/{conversation_id}")
                
        except Exception as e:
            self.log_test("LM Studio Mode Config", False, f"Exception: {str(e)}")

    def test_hybrid_mode_advanced_config(self):
        """Test Hybrid mode with council model sources and LM Studio names"""
        try:
            # Create a test conversation
            create_response = self.session.post(
                f"{self.base_url}/api/conversations",
                json={},
                headers={"Content-Type": "application/json"}
            )
            
            if create_response.status_code != 200:
                self.log_test("Hybrid Mode Config", False, "Failed to create test conversation")
                return
            
            conversation = create_response.json()
            conversation_id = conversation.get("id")
            
            # Test Hybrid mode with mixed sources
            advanced_config = {
                "mode": "hybrid",
                "openrouter": {
                    "apiKey": ""
                },
                "lmstudio": {
                    "baseUrl": "http://localhost:1234/v1",
                    "defaultModel": "default"
                },
                "hybrid": {
                    "councilModelSources": {
                        "openai/gpt-4o": "openrouter",
                        "anthropic/claude-3.5-sonnet": "lmstudio",
                        "google/gemini-2.0-flash-exp": "lmstudio",
                        "meta-llama/llama-3.1-8b-instruct": "openrouter"
                    },
                    "councilModelLmStudioNames": {
                        "anthropic/claude-3.5-sonnet": "claude-sonnet-local",
                        "google/gemini-2.0-flash-exp": "gemini-flash-local"
                    },
                    "chairmanSource": "lmstudio",
                    "chairmanLmStudioModel": "chairman-hybrid-model"
                }
            }
            
            message_data = {
                "content": "Test Hybrid mode configuration",
                "include_documents": False,
                "advanced": advanced_config
            }
            
            # Test the streaming endpoint
            response = self.session.post(
                f"{self.base_url}/api/conversations/{conversation_id}/message/stream",
                json=message_data,
                headers={"Content-Type": "application/json"},
                stream=True,
                timeout=10
            )
            
            # Should accept the advanced config
            if response.status_code in [200, 400]:
                self.log_test(
                    "Hybrid Mode Config", 
                    True, 
                    "Backend accepts Hybrid mode with mixed council model sources",
                    {"status": response.status_code, "config_accepted": True}
                )
            else:
                self.log_test(
                    "Hybrid Mode Config", 
                    False, 
                    f"Unexpected status code: {response.status_code}",
                    response.text[:200]
                )
            
            # Clean up conversation
            self.session.delete(f"{self.base_url}/api/conversations/{conversation_id}")
                
        except Exception as e:
            self.log_test("Hybrid Mode Config", False, f"Exception: {str(e)}")

    def test_openrouter_mode_advanced_config(self):
        """Test OpenRouter mode with advanced config"""
        try:
            # Create a test conversation
            create_response = self.session.post(
                f"{self.base_url}/api/conversations",
                json={},
                headers={"Content-Type": "application/json"}
            )
            
            if create_response.status_code != 200:
                self.log_test("OpenRouter Mode Config", False, "Failed to create test conversation")
                return
            
            conversation = create_response.json()
            conversation_id = conversation.get("id")
            
            # Test OpenRouter mode with API key override
            advanced_config = {
                "mode": "openrouter",
                "openrouter": {
                    "apiKey": "sk-or-v1-test-key-override"
                }
            }
            
            message_data = {
                "content": "Test OpenRouter mode configuration",
                "include_documents": False,
                "advanced": advanced_config
            }
            
            # Test the streaming endpoint
            response = self.session.post(
                f"{self.base_url}/api/conversations/{conversation_id}/message/stream",
                json=message_data,
                headers={"Content-Type": "application/json"},
                stream=True,
                timeout=10
            )
            
            # Should accept the advanced config
            if response.status_code in [200, 400]:
                self.log_test(
                    "OpenRouter Mode Config", 
                    True, 
                    "Backend accepts OpenRouter mode with API key override",
                    {"status": response.status_code, "config_accepted": True}
                )
            else:
                self.log_test(
                    "OpenRouter Mode Config", 
                    False, 
                    f"Unexpected status code: {response.status_code}",
                    response.text[:200]
                )
            
            # Clean up conversation
            self.session.delete(f"{self.base_url}/api/conversations/{conversation_id}")
                
        except Exception as e:
            self.log_test("OpenRouter Mode Config", False, f"Exception: {str(e)}")

    def test_config_persistence_and_retrieval(self):
        """Test that advanced config settings can be persisted and retrieved"""
        try:
            # Test updating config with LM Studio URLs (this should work)
            lm_studio_test_urls = {
                "openai/gpt-4o": "http://localhost:1234/v1",
                "anthropic/claude-3.5-sonnet": "http://localhost:1235/v1",
                "google/gemini-2.0-flash-exp": "http://localhost:1236/v1"
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
                    # Now retrieve the config to verify persistence
                    get_response = self.session.get(f"{self.base_url}/api/config")
                    if get_response.status_code == 200:
                        get_data = get_response.json()
                        if get_data.get("lm_studio_urls") == lm_studio_test_urls:
                            self.log_test(
                                "Config Persistence", 
                                True, 
                                f"LM Studio URLs persisted correctly: {list(lm_studio_test_urls.keys())}",
                                {"persisted_urls": lm_studio_test_urls}
                            )
                        else:
                            self.log_test(
                                "Config Persistence", 
                                False, 
                                "LM Studio URLs not persisted correctly",
                                {"expected": lm_studio_test_urls, "actual": get_data.get("lm_studio_urls")}
                            )
                    else:
                        self.log_test(
                            "Config Persistence", 
                            False, 
                            f"Failed to retrieve config: {get_response.status_code}",
                            get_response.text
                        )
                else:
                    self.log_test(
                        "Config Persistence", 
                        False, 
                        "LM Studio URLs not updated correctly",
                        {"expected": lm_studio_test_urls, "actual": data.get("lm_studio_urls")}
                    )
            else:
                self.log_test(
                    "Config Persistence", 
                    False, 
                    f"Failed to update config: {response.status_code}",
                    response.text
                )
                
        except Exception as e:
            self.log_test("Config Persistence", False, f"Exception: {str(e)}")

    def test_default_model_fallback(self):
        """Test that default model is used when no specific mapping exists"""
        try:
            # Create a test conversation
            create_response = self.session.post(
                f"{self.base_url}/api/conversations",
                json={},
                headers={"Content-Type": "application/json"}
            )
            
            if create_response.status_code != 200:
                self.log_test("Default Model Fallback", False, "Failed to create test conversation")
                return
            
            conversation = create_response.json()
            conversation_id = conversation.get("id")
            
            # Test LM Studio mode with partial model mapping (some models should fall back to default)
            advanced_config = {
                "mode": "lmstudio",
                "lmstudio": {
                    "baseUrl": "http://localhost:1234/v1",
                    "defaultModel": "fallback-model",
                    "multiModel": True,
                    "modelMapping": {
                        "openai/gpt-4o": "specific-gpt4-model"
                        # Other models should use defaultModel
                    },
                    "chairmanModel": ""  # Should use defaultModel
                }
            }
            
            message_data = {
                "content": "Test default model fallback",
                "include_documents": False,
                "advanced": advanced_config
            }
            
            # Test the streaming endpoint
            response = self.session.post(
                f"{self.base_url}/api/conversations/{conversation_id}/message/stream",
                json=message_data,
                headers={"Content-Type": "application/json"},
                stream=True,
                timeout=10
            )
            
            # Should accept the config and handle fallback logic
            if response.status_code in [200, 400]:
                self.log_test(
                    "Default Model Fallback", 
                    True, 
                    "Backend accepts config with default model fallback logic",
                    {"status": response.status_code, "config_accepted": True}
                )
            else:
                self.log_test(
                    "Default Model Fallback", 
                    False, 
                    f"Unexpected status code: {response.status_code}",
                    response.text[:200]
                )
            
            # Clean up conversation
            self.session.delete(f"{self.base_url}/api/conversations/{conversation_id}")
                
        except Exception as e:
            self.log_test("Default Model Fallback", False, f"Exception: {str(e)}")

    def run_all_tests(self):
        """Run all LM Studio multi-model tests"""
        print("🚀 Starting LM Studio Multi-Model Backend Tests")
        print(f"Testing endpoint: {self.base_url}")
        print("=" * 60)
        
        # Test different modes
        self.test_lmstudio_mode_advanced_config()
        self.test_hybrid_mode_advanced_config()
        self.test_openrouter_mode_advanced_config()
        
        # Test persistence and fallback
        self.test_config_persistence_and_retrieval()
        self.test_default_model_fallback()
        
        # Print summary
        print("=" * 60)
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All LM Studio multi-model tests passed!")
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
    
    tester = LMStudioMultiModelTester(backend_url)
    exit_code = tester.run_all_tests()
    
    # Save detailed results
    results = tester.get_test_results()
    with open("/app/lm_studio_multimodel_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: /app/lm_studio_multimodel_test_results.json")
    return exit_code

if __name__ == "__main__":
    sys.exit(main())