import requests
import sys
import json
from datetime import datetime

class LLMCouncilAPITester:
    def __init__(self, base_url="https://llm-council-advanced.preview.emergentagent.com"):
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

def main():
    # Setup
    tester = LLMCouncilAPITester()
    
    print("🚀 Starting LLM Council Advanced Config API Tests")
    print(f"Testing against: {tester.base_url}")
    
    # Run tests
    print("\n" + "="*50)
    print("BASIC API TESTS")
    print("="*50)
    
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

    print("\n" + "="*50)
    print("ADVANCED CONFIG TESTS")
    print("="*50)

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

    print("\n" + "="*50)
    print("LM STUDIO TESTS")
    print("="*50)

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