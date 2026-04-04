#!/usr/bin/env python3
"""
Integration test to verify LM Studio query fixes work end-to-end
"""

import asyncio
import sys
import json
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

# Add backend to path
sys.path.insert(0, '/app/backend')

from openrouter import query_lm_studio, query_models_parallel, get_model_source


async def test_lm_studio_integration():
    """Test LM Studio integration with the fixes"""
    
    print("🔍 Testing LM Studio Integration with Fixes...")
    
    # Test configuration that would use LM Studio
    test_config = {
        'mode': 'lmstudio',
        'models': {
            'openai/gpt-4o': {
                'source': 'lmstudio',
                'endpointUrl': 'http://localhost:8080/v1',  # User's working example
                'localModelName': 'gpt-4o'
            }
        }
    }
    
    # Mock LM Studio response with reasoning_content
    mock_response_data = {
        'choices': [{
            'message': {
                'content': 'This is a test response from LM Studio',
                'reasoning_content': 'I analyzed the request and provided a helpful response'
            }
        }],
        'model': 'gpt-4o'
    }
    
    with patch('openrouter.httpx.AsyncClient') as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status.return_value = None
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        
        # Test single model query
        result = await query_lm_studio(
            'http://localhost:8080/v1',
            'gpt-4o',
            [{"role": "user", "content": "Hello, test message"}]
        )
        
        # Verify the result
        assert result is not None, "Result should not be None"
        assert result['content'] == 'This is a test response from LM Studio', f"Content mismatch: {result['content']}"
        assert result['reasoning_details'] == 'I analyzed the request and provided a helpful response', f"Reasoning mismatch: {result['reasoning_details']}"
        assert result['source'] == 'lm_studio', f"Source mismatch: {result['source']}"
        
        # Check the URL that was called
        called_args = mock_client.return_value.__aenter__.return_value.post.call_args
        actual_url = called_args[0][0]
        expected_url = 'http://localhost:8080/v1/chat/completions'
        assert actual_url == expected_url, f"URL mismatch: expected {expected_url}, got {actual_url}"
        
        # Check the payload
        payload = called_args[1]['json']
        assert payload['stream'] == False, f"Stream should be False, got {payload['stream']}"
        assert payload['model'] == 'gpt-4o', f"Model mismatch: {payload['model']}"
        
        print("✅ Single model query test passed")
        
        # Test parallel model queries
        models = ['openai/gpt-4o', 'anthropic/claude-3.5-sonnet']
        
        # Mock query_model for parallel test
        async def mock_query_model(model, messages, advanced_config=None):
            await asyncio.sleep(0.01)  # Simulate async work
            return {
                'content': f'Response from {model}',
                'reasoning_details': f'Reasoning for {model}',
                'source': 'lm_studio'
            }
        
        with patch('openrouter.query_model', mock_query_model):
            results = await query_models_parallel(
                models,
                [{"role": "user", "content": "Test parallel query"}],
                test_config
            )
            
            # Verify parallel results
            assert len(results) == 2, f"Expected 2 results, got {len(results)}"
            assert all(results.values()), f"All results should be non-None: {results}"
            
            for model in models:
                assert model in results, f"Model {model} not in results"
                assert results[model]['content'] == f'Response from {model}', f"Content mismatch for {model}"
                
        print("✅ Parallel model query test passed")
        
    print("✅ All LM Studio integration tests passed!")
    return True


async def test_url_edge_cases():
    """Test URL normalization edge cases"""
    
    print("🔍 Testing URL Edge Cases...")
    
    # Test cases that could cause double /v1 issue
    edge_cases = [
        ("http://localhost:8080", "http://localhost:8080/v1/chat/completions"),
        ("http://localhost:8080/", "http://localhost:8080/v1/chat/completions"),
        ("http://localhost:8080/v1", "http://localhost:8080/v1/chat/completions"),
        ("http://localhost:8080/v1/", "http://localhost:8080/v1/chat/completions"),
        ("https://api.example.com/v1", "https://api.example.com/v1/chat/completions"),
        ("https://api.example.com/v1/models", "https://api.example.com/v1/models/chat/completions"),
    ]
    
    for base_url, expected_url in edge_cases:
        with patch('openrouter.httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                'choices': [{'message': {'content': 'test'}}]
            }
            mock_response.raise_for_status.return_value = None
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            await query_lm_studio(base_url, "test-model", [{"role": "user", "content": "test"}])
            
            called_args = mock_client.return_value.__aenter__.return_value.post.call_args
            actual_url = called_args[0][0]
            
            # Check that we don't have double /v1
            assert '/v1/v1' not in actual_url, f"Double /v1 found in URL: {actual_url}"
            print(f"   ✅ {base_url} -> {actual_url} (no double /v1)")
    
    print("✅ URL edge cases test passed!")
    return True


async def main():
    """Run all integration tests"""
    print("🚀 Starting LM Studio Integration Tests")
    print("="*60)
    
    try:
        await test_lm_studio_integration()
        await test_url_edge_cases()
        
        print("\n🎉 All integration tests passed!")
        return 0
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))