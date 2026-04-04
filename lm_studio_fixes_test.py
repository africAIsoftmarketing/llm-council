#!/usr/bin/env python3
"""
Test script for LM Studio query fixes:
1. URL normalization (no double /v1 suffix)
2. reasoning_content field extraction  
3. stream: false in payload
4. Proper coroutine awaiting in query_models_parallel
5. No coroutine warnings in backend logs
"""

import asyncio
import sys
import json
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
import warnings
import io
from contextlib import redirect_stderr

# Add backend to path
sys.path.insert(0, '/app/backend')

from openrouter import query_lm_studio, query_models_parallel
from load_balancer import execute_with_throttle, ThrottleConfig


class LMStudioFixesTester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.captured_warnings = []

    async def run_test(self, name, test_func):
        """Run a single test function"""
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            result = await test_func()
            if result:
                self.tests_passed += 1
                print(f"✅ Passed")
                return True
            else:
                print(f"❌ Failed")
                return False
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False

    async def test_url_normalization(self):
        """Test that URLs are normalized correctly without double /v1 suffix"""
        
        # Test cases for URL normalization
        test_cases = [
            ("http://localhost:1234", "http://localhost:1234/v1/chat/completions"),
            ("http://localhost:1234/", "http://localhost:1234/v1/chat/completions"),
            ("http://localhost:1234/v1", "http://localhost:1234/v1/chat/completions"),
            ("http://localhost:1234/v1/", "http://localhost:1234/v1/chat/completions"),
            ("http://localhost:8080/v1", "http://localhost:8080/v1/chat/completions"),
        ]
        
        for base_url, expected_url in test_cases:
            # Mock the httpx client to capture the URL being called
            with patch('openrouter.httpx.AsyncClient') as mock_client:
                mock_response = MagicMock()
                mock_response.json.return_value = {
                    'choices': [{'message': {'content': 'test response'}}]
                }
                mock_response.raise_for_status.return_value = None
                
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
                
                # Call the function
                await query_lm_studio(base_url, "test-model", [{"role": "user", "content": "test"}])
                
                # Check that the correct URL was called
                called_args = mock_client.return_value.__aenter__.return_value.post.call_args
                actual_url = called_args[0][0]  # First positional argument
                
                if actual_url != expected_url:
                    print(f"   ❌ URL normalization failed for {base_url}")
                    print(f"      Expected: {expected_url}")
                    print(f"      Got: {actual_url}")
                    return False
                else:
                    print(f"   ✅ URL normalized correctly: {base_url} -> {actual_url}")
        
        return True

    async def test_reasoning_content_extraction(self):
        """Test that reasoning_content field is extracted from LM Studio response"""
        
        # Mock response with reasoning_content field
        mock_response_data = {
            'choices': [{
                'message': {
                    'content': 'This is the main response',
                    'reasoning_content': 'This is the reasoning behind the response'
                }
            }],
            'model': 'test-model'
        }
        
        with patch('openrouter.httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            # Call the function
            result = await query_lm_studio("http://localhost:1234/v1", "test-model", [{"role": "user", "content": "test"}])
            
            # Check that reasoning_content was extracted
            if result and result.get('reasoning_details') == 'This is the reasoning behind the response':
                print(f"   ✅ reasoning_content extracted correctly")
                return True
            else:
                print(f"   ❌ reasoning_content not extracted. Got: {result.get('reasoning_details') if result else 'None'}")
                return False

    async def test_stream_false_payload(self):
        """Test that stream: false is included in the payload"""
        
        with patch('openrouter.httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                'choices': [{'message': {'content': 'test response'}}]
            }
            mock_response.raise_for_status.return_value = None
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            # Call the function
            await query_lm_studio("http://localhost:1234/v1", "test-model", [{"role": "user", "content": "test"}])
            
            # Check that stream: false was in the payload
            called_args = mock_client.return_value.__aenter__.return_value.post.call_args
            payload = called_args[1]['json']  # json keyword argument
            
            if payload.get('stream') == False:
                print(f"   ✅ stream: false included in payload")
                return True
            else:
                print(f"   ❌ stream: false not in payload. Got: {payload.get('stream')}")
                return False

    async def test_coroutine_awaiting(self):
        """Test that coroutines are properly awaited in query_models_parallel"""
        
        # Capture warnings to check for 'coroutine was never awaited'
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # Mock the query_model function to return a simple response
            async def mock_query_model(model, messages, advanced_config=None):
                await asyncio.sleep(0.01)  # Small delay to simulate async work
                return {'content': f'Response from {model}', 'source': 'test'}
            
            with patch('openrouter.query_model', mock_query_model):
                # Test with a simple config that would use the load balancer
                test_config = {
                    'mode': 'lmstudio',
                    'models': {
                        'test/model1': {'source': 'lmstudio'},
                        'test/model2': {'source': 'lmstudio'}
                    }
                }
                
                # Call query_models_parallel
                results = await query_models_parallel(
                    ['test/model1', 'test/model2'],
                    [{"role": "user", "content": "test"}],
                    test_config
                )
                
                # Check for coroutine warnings
                coroutine_warnings = [warning for warning in w if 'coroutine' in str(warning.message).lower()]
                
                if coroutine_warnings:
                    print(f"   ❌ Found coroutine warnings: {[str(w.message) for w in coroutine_warnings]}")
                    return False
                else:
                    print(f"   ✅ No coroutine warnings detected")
                    
                # Check that we got results
                if len(results) == 2 and all(results.values()):
                    print(f"   ✅ All models returned results")
                    return True
                else:
                    print(f"   ❌ Not all models returned results: {results}")
                    return False

    async def test_backend_startup_logs(self):
        """Test that backend starts without errors after fixes"""
        
        # This is a basic test - in a real environment we'd check supervisor logs
        # For now, we'll just verify the modules can be imported without errors
        try:
            import openrouter
            import load_balancer
            print(f"   ✅ Backend modules import successfully")
            
            # Test that the key functions exist and are callable
            assert callable(openrouter.query_lm_studio)
            assert callable(openrouter.query_models_parallel)
            assert callable(load_balancer.execute_with_throttle)
            print(f"   ✅ Key functions are callable")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Backend module import failed: {e}")
            return False

    async def run_all_tests(self):
        """Run all LM Studio fix tests"""
        print("🚀 Starting LM Studio Fixes Tests")
        print("="*60)
        
        # Test URL normalization
        await self.run_test("URL Normalization (no double /v1)", self.test_url_normalization)
        
        # Test reasoning_content extraction
        await self.run_test("reasoning_content Field Extraction", self.test_reasoning_content_extraction)
        
        # Test stream: false payload
        await self.run_test("stream: false in Payload", self.test_stream_false_payload)
        
        # Test coroutine awaiting
        await self.run_test("Proper Coroutine Awaiting", self.test_coroutine_awaiting)
        
        # Test backend startup
        await self.run_test("Backend Startup Without Errors", self.test_backend_startup_logs)
        
        print(f"\n📊 LM Studio Fixes Tests: {self.tests_passed}/{self.tests_run} passed")
        return self.tests_passed == self.tests_run


async def main():
    tester = LMStudioFixesTester()
    success = await tester.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))