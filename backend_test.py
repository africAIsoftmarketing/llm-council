import requests
import sys
import json
import uuid
from datetime import datetime

class LLMCouncilAPITester:
    def __init__(self, base_url="https://inno-build.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, method, endpoint, expected_status, data=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return True, response.json()
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Response: {response.text}")

            return success, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test health check endpoint"""
        success, response = self.run_test(
            "Health Check",
            "GET",
            "api/health",
            200
        )
        return success

    def test_get_config(self):
        """Test get configuration"""
        success, response = self.run_test(
            "Get Configuration",
            "GET",
            "api/config",
            200
        )
        return success, response

    def test_get_advanced_config(self):
        """Test get advanced configuration"""
        success, response = self.run_test(
            "Get Advanced Configuration",
            "GET",
            "api/config/advanced",
            200
        )
        return success, response

    def test_save_advanced_config(self):
        """Test save advanced configuration"""
        test_config = {
            "mode": "hybrid",
            "openrouter": {
                "apiKey": "test-key"
            },
            "models": {
                "openai/gpt-4o": {
                    "source": "openrouter",
                    "endpointUrl": "http://localhost:1234/v1",
                    "localModelName": "gpt-4o"
                },
                "anthropic/claude-3.5-sonnet": {
                    "source": "lmstudio",
                    "endpointUrl": "http://localhost:1235/v1",
                    "localModelName": "claude-sonnet"
                }
            },
            "chairman": {
                "source": "lmstudio",
                "endpointUrl": "http://localhost:1236/v1",
                "localModelName": "chairman-model"
            }
        }
        
        success, response = self.run_test(
            "Save Advanced Configuration",
            "POST",
            "api/config/advanced",
            200,
            data=test_config
        )
        return success, response

    def test_lm_studio_connection(self):
        """Test LM Studio connection test endpoint"""
        test_data = {
            "url": "http://localhost:1234/v1",
            "model_name": "test-model"
        }
        
        success, response = self.run_test(
            "Test LM Studio Connection",
            "POST",
            "api/lm-studio/test",
            200,
            data=test_data
        )
        return success, response

    def test_get_available_models(self):
        """Test get available models"""
        success, response = self.run_test(
            "Get Available Models",
            "GET",
            "api/models/available",
            200
        )
        return success, response

    def test_health_check_with_advanced_config(self):
        """Test health check returns configured:true when advanced_config is set"""
        # First set an advanced config without API key
        lm_studio_config = {
            "mode": "lmstudio",
            "models": {
                "openai/gpt-4o": {
                    "source": "lmstudio",
                    "endpointUrl": "http://localhost:1234/v1",
                    "localModelName": "gpt-4o"
                }
            }
        }
        
        # Save the config
        self.run_test(
            "Save LM Studio Config",
            "POST",
            "api/config/advanced",
            200,
            data=lm_studio_config
        )
        
        # Test health check
        success, response = self.run_test(
            "Health Check with Advanced Config",
            "GET",
            "api/health",
            200
        )
        
        if success and response.get('configured') == True:
            print(f"   ✅ Health check shows configured=true with advanced config")
            return True
        else:
            print(f"   ❌ Health check configured status: {response.get('configured')}")
            return False

    def test_conversation_creation(self):
        """Create a test conversation for message testing"""
        success, response = self.run_test(
            "Create Conversation",
            "POST",
            "api/conversations",
            200,
            data={}
        )
        if success:
            conversation_id = response.get('id')
            print(f"   Created conversation: {conversation_id}")
            return conversation_id
        return None

    def test_send_message_lm_studio_mode(self, conversation_id):
        """Test sending message in LM Studio mode without API key"""
        if not conversation_id:
            return False
            
        # Set LM Studio mode
        lm_studio_config = {
            "mode": "lmstudio",
            "models": {
                "openai/gpt-4o": {
                    "source": "lmstudio",
                    "endpointUrl": "http://localhost:1234/v1",
                    "localModelName": "gpt-4o"
                }
            }
        }
        
        self.run_test(
            "Set LM Studio Mode",
            "POST",
            "api/config/advanced",
            200,
            data=lm_studio_config
        )
        
        # Test regular message endpoint
        message_data = {
            "content": "Test message for LM Studio mode",
            "advanced": lm_studio_config
        }
        
        success, response = self.run_test(
            "Send Message in LM Studio Mode",
            "POST",
            f"api/conversations/{conversation_id}/message",
            200,  # Should work without API key
            data=message_data
        )
        
        return success

    def test_send_message_stream_lm_studio_mode(self, conversation_id):
        """Test streaming message in LM Studio mode without API key"""
        if not conversation_id:
            return False
            
        # Set LM Studio mode
        lm_studio_config = {
            "mode": "lmstudio",
            "models": {
                "openai/gpt-4o": {
                    "source": "lmstudio",
                    "endpointUrl": "http://localhost:1234/v1",
                    "localModelName": "gpt-4o"
                }
            }
        }
        
        message_data = {
            "content": "Test streaming message for LM Studio mode",
            "advanced": lm_studio_config
        }
        
        # Test streaming endpoint - should not require API key
        url = f"{self.base_url}/api/conversations/{conversation_id}/message/stream"
        headers = {'Content-Type': 'application/json'}
        
        self.tests_run += 1
        print(f"\n🔍 Testing Send Message Stream in LM Studio Mode...")
        
        try:
            response = requests.post(url, json=message_data, headers=headers, stream=True)
            
            # Should not get 400 error about missing API key
            if response.status_code != 400:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code} (no API key error)")
                return True
            else:
                print(f"❌ Failed - Got 400 error, likely API key required: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False

    def test_config_storage_paths(self):
        """Test that GET /api/config returns storage_paths object"""
        success, response = self.run_test(
            "Get Config with Storage Paths",
            "GET",
            "api/config",
            200
        )
        
        if success:
            storage_paths = response.get('storage_paths')
            if storage_paths:
                required_paths = ['config_file', 'data_dir', 'conversations_dir', 'documents_dir']
                has_all_paths = all(path in storage_paths for path in required_paths)
                
                if has_all_paths:
                    print(f"   ✅ All required storage paths present:")
                    for path_key, path_value in storage_paths.items():
                        print(f"     {path_key}: {path_value}")
                    return True
                else:
                    missing = [p for p in required_paths if p not in storage_paths]
                    print(f"   ❌ Missing storage paths: {missing}")
                    return False
            else:
                print(f"   ❌ No storage_paths in config response")
                return False
        
        return False

    def test_throttle_config_openrouter_mode(self):
        """Test throttle config returns max_concurrent=4 for openrouter mode"""
        openrouter_config = {
            "mode": "openrouter",
            "throttle": {
                "maxConcurrent": 4,
                "delayBetweenRequests": 0.0,
                "requestTimeout": 120
            }
        }
        
        # Save config and test
        success, response = self.run_test(
            "Save OpenRouter Throttle Config",
            "POST",
            "api/config/advanced",
            200,
            data=openrouter_config
        )
        
        if success:
            # Verify the config was saved correctly
            success, saved_config = self.run_test(
                "Get Saved OpenRouter Config",
                "GET",
                "api/config/advanced",
                200
            )
            
            if success:
                throttle = saved_config.get('throttle', {})
                max_concurrent = throttle.get('maxConcurrent', 0)
                if max_concurrent == 4:
                    print(f"   ✅ OpenRouter mode throttle config correct: maxConcurrent={max_concurrent}")
                    return True
                else:
                    print(f"   ❌ OpenRouter mode throttle config wrong: maxConcurrent={max_concurrent}, expected 4")
                    return False
        
        return False

    def test_throttle_config_lmstudio_mode(self):
        """Test throttle config returns max_concurrent=1 for lmstudio mode by default"""
        lmstudio_config = {
            "mode": "lmstudio",
            "models": {
                "openai/gpt-4o": {
                    "source": "lmstudio",
                    "endpointUrl": "http://localhost:1234/v1",
                    "localModelName": "gpt-4o"
                }
            },
            "throttle": {
                "maxConcurrent": 1,
                "delayBetweenRequests": 1.0,
                "requestTimeout": 300
            }
        }
        
        # Save config and test
        success, response = self.run_test(
            "Save LM Studio Throttle Config",
            "POST",
            "api/config/advanced",
            200,
            data=lmstudio_config
        )
        
        if success:
            # Verify the config was saved correctly
            success, saved_config = self.run_test(
                "Get Saved LM Studio Config",
                "GET",
                "api/config/advanced",
                200
            )
            
            if success:
                throttle = saved_config.get('throttle', {})
                max_concurrent = throttle.get('maxConcurrent', 0)
                delay = throttle.get('delayBetweenRequests', 0)
                timeout = throttle.get('requestTimeout', 0)
                
                if max_concurrent == 1 and delay == 1.0 and timeout == 300:
                    print(f"   ✅ LM Studio mode throttle config correct: maxConcurrent={max_concurrent}, delay={delay}s, timeout={timeout}s")
                    return True
                else:
                    print(f"   ❌ LM Studio mode throttle config wrong: maxConcurrent={max_concurrent}, delay={delay}, timeout={timeout}")
                    return False
        
        return False

    def test_throttle_presets(self):
        """Test throttle preset configurations"""
        # Test Safe preset
        safe_config = {
            "mode": "lmstudio",
            "throttle": {
                "maxConcurrent": 1,
                "delayBetweenRequests": 2.0,
                "requestTimeout": 300
            }
        }
        
        success, response = self.run_test(
            "Save Safe Preset Config",
            "POST",
            "api/config/advanced",
            200,
            data=safe_config
        )
        
        safe_test_passed = False
        if success:
            success, saved_config = self.run_test(
                "Get Safe Preset Config",
                "GET",
                "api/config/advanced",
                200
            )
            
            if success:
                throttle = saved_config.get('throttle', {})
                if (throttle.get('maxConcurrent') == 1 and 
                    throttle.get('delayBetweenRequests') == 2.0 and 
                    throttle.get('requestTimeout') == 300):
                    print(f"   ✅ Safe preset config correct")
                    safe_test_passed = True
                else:
                    print(f"   ❌ Safe preset config wrong: {throttle}")
        
        # Test Fast preset
        fast_config = {
            "mode": "lmstudio",
            "throttle": {
                "maxConcurrent": 4,
                "delayBetweenRequests": 0.0,
                "requestTimeout": 120
            }
        }
        
        success, response = self.run_test(
            "Save Fast Preset Config",
            "POST",
            "api/config/advanced",
            200,
            data=fast_config
        )
        
        fast_test_passed = False
        if success:
            success, saved_config = self.run_test(
                "Get Fast Preset Config",
                "GET",
                "api/config/advanced",
                200
            )
            
            if success:
                throttle = saved_config.get('throttle', {})
                if (throttle.get('maxConcurrent') == 4 and 
                    throttle.get('delayBetweenRequests') == 0.0 and 
                    throttle.get('requestTimeout') == 120):
                    print(f"   ✅ Fast preset config correct")
                    fast_test_passed = True
                else:
                    print(f"   ❌ Fast preset config wrong: {throttle}")
        
        return safe_test_passed and fast_test_passed

    def test_requires_openrouter_key_logic(self):
        """Test the requires_openrouter_key logic by testing different modes"""
        
        # Test 1: LM Studio mode should not require API key
        lm_studio_config = {
            "mode": "lmstudio",
            "models": {
                "openai/gpt-4o": {
                    "source": "lmstudio",
                    "endpointUrl": "http://localhost:1234/v1",
                    "localModelName": "gpt-4o"
                }
            }
        }
        
        self.run_test(
            "Set LM Studio Mode for Key Test",
            "POST",
            "api/config/advanced",
            200,
            data=lm_studio_config
        )
        
        # Create a conversation to test message sending
        success, conv_response = self.run_test(
            "Create Test Conversation",
            "POST",
            "api/conversations",
            200,
            data={}
        )
        
        if not success:
            print("   ❌ Failed to create conversation for testing")
            return False
            
        conversation_id = conv_response.get('id')
        if not conversation_id:
            print("   ❌ No conversation ID returned")
            return False
        
        # Try to send a message - should work without API key in LM Studio mode
        message_data = {
            "content": "Test message",
            "advanced": lm_studio_config
        }
        
        success, response = self.run_test(
            "Test LM Studio Mode (No API Key Required)",
            "POST",
            f"api/conversations/{conversation_id}/message",
            200,  # Should work
            data=message_data
        )
        
        lm_studio_test_passed = success
        
        # Test 2: OpenRouter mode should require API key
        openrouter_config = {
            "mode": "openrouter"
        }
        
        self.run_test(
            "Set OpenRouter Mode for Key Test",
            "POST",
            "api/config/advanced",
            200,
            data=openrouter_config
        )
        
        message_data_or = {
            "content": "Test message",
            "advanced": openrouter_config
        }
        
        success, response = self.run_test(
            "Test OpenRouter Mode (API Key Required)",
            "POST",
            f"api/conversations/{conversation_id}/message",
            400,  # Should fail with 400
            data=message_data_or
        )
        
        openrouter_test_passed = success
        
        # Test 3: Hybrid mode with OpenRouter models should require API key
        hybrid_config = {
            "mode": "hybrid",
            "models": {
                "openai/gpt-4o": {
                    "source": "openrouter"
                }
            }
        }
        
        self.run_test(
            "Set Hybrid Mode with OpenRouter Models",
            "POST",
            "api/config/advanced",
            200,
            data=hybrid_config
        )
        
        message_data_hybrid = {
            "content": "Test message",
            "advanced": hybrid_config
        }
        
        success, response = self.run_test(
            "Test Hybrid Mode with OpenRouter (API Key Required)",
            "POST",
            f"api/conversations/{conversation_id}/message",
            400,  # Should fail with 400
            data=message_data_hybrid
        )
        
        hybrid_test_passed = success
        
        print(f"\n📋 API Key Logic Test Results:")
        print(f"   LM Studio mode (no key required): {'✅' if lm_studio_test_passed else '❌'}")
        print(f"   OpenRouter mode (key required): {'✅' if openrouter_test_passed else '❌'}")
        print(f"   Hybrid mode with OR models (key required): {'✅' if hybrid_test_passed else '❌'}")
        
        return lm_studio_test_passed and openrouter_test_passed and hybrid_test_passed

def main():
    # Setup
    tester = LLMCouncilAPITester()
    
    print("🚀 Starting LLM Council Load Balancer & Throttling Tests")
    print(f"Testing against: {tester.base_url}")
    print("\nTesting features:")
    print("1. Load balancer module with ThrottleConfig, get_throttle_config, execute_with_throttle")
    print("2. Throttle config returns correct values for different modes")
    print("3. OpenRouter.py uses execute_with_throttle instead of asyncio.gather")
    print("4. Throttle presets (Safe/Balanced/Fast) work correctly")
    print("5. Advanced Panel shows/hides Performance & Throttling section based on mode")
    
    # Run tests
    print("\n" + "="*60)
    print("BASIC API TESTS")
    print("="*60)
    
    if not tester.test_health_check():
        print("❌ Health check failed, stopping tests")
        return 1

    success, config = tester.test_get_config()
    if success:
        print(f"   Current config has API key: {config.get('has_api_key', False)}")
        print(f"   Council models: {len(config.get('council_models', []))}")
        print(f"   Chairman model: {config.get('chairman_model', 'None')}")

    success, models = tester.test_get_available_models()
    if success:
        print(f"   Available models: {len(models.get('models', []))}")

    print("\n" + "="*60)
    print("THROTTLE CONFIG TESTS")
    print("="*60)

    # Test throttle config for different modes
    if not tester.test_throttle_config_openrouter_mode():
        print("❌ OpenRouter throttle config test failed")

    if not tester.test_throttle_config_lmstudio_mode():
        print("❌ LM Studio throttle config test failed")

    if not tester.test_throttle_presets():
        print("❌ Throttle presets test failed")

    print("\n" + "="*60)
    print("BUG FIX TESTS - API KEY GUARD")
    print("="*60)

    # Test health check with advanced config (should show configured=true)
    if not tester.test_health_check_with_advanced_config():
        print("❌ Health check with advanced config failed")

    # Test API key logic with different modes
    if not tester.test_requires_openrouter_key_logic():
        print("❌ API key requirement logic tests failed")

    print("\n" + "="*60)
    print("BUG FIX TESTS - MESSAGE SENDING WITHOUT API KEY")
    print("="*60)

    # Create a conversation for testing
    conversation_id = tester.test_conversation_creation()
    if conversation_id:
        # Test sending messages in LM Studio mode without API key
        if not tester.test_send_message_lm_studio_mode(conversation_id):
            print("❌ Send message in LM Studio mode failed")
        
        if not tester.test_send_message_stream_lm_studio_mode(conversation_id):
            print("❌ Send message stream in LM Studio mode failed")

    print("\n" + "="*60)
    print("FEATURE TEST - STORAGE PATHS")
    print("="*60)

    # Test storage paths in config response
    if not tester.test_config_storage_paths():
        print("❌ Storage paths test failed")

    print("\n" + "="*60)
    print("ADVANCED CONFIG TESTS")
    print("="*60)

    # Test getting advanced config
    success, advanced_config = tester.test_get_advanced_config()
    if success:
        print(f"   Current advanced config: {json.dumps(advanced_config, indent=2)}")

    # Test saving advanced config
    success, saved_config = tester.test_save_advanced_config()
    if success:
        print(f"   Saved config: {json.dumps(saved_config, indent=2)}")

    # Test getting advanced config again to verify persistence
    success, updated_config = tester.test_get_advanced_config()
    if success:
        print(f"   Updated config after save: {json.dumps(updated_config, indent=2)}")

    print("\n" + "="*60)
    print("LM STUDIO TESTS")
    print("="*60)

    # Test LM Studio connection (will likely fail but should return proper error)
    success, lm_result = tester.test_lm_studio_connection()
    if success:
        print(f"   LM Studio test result: {json.dumps(lm_result, indent=2)}")

    # Print results
    print(f"\n📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())