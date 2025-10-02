#!/usr/bin/env python3
"""
Simple test script for the simplified conversational service.

This script demonstrates the simplified approach and validates
that the service works correctly.
"""

import asyncio
import sys
import os
import logging

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from healthnavi.services.simple_conversational_service import (
    ConversationRequest, 
    process_conversation,
    generate_response,
    get_conversational_service
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_basic_functionality():
    """Test basic service functionality."""
    logger.info("Testing basic functionality...")
    
    try:
        # Test service info
        service = get_conversational_service()
        info = service.get_service_info()
        logger.info(f"✓ Service: {info['service_name']} v{info['version']}")
        logger.info(f"✓ Model: {info['model']}")
        logger.info(f"✓ Query types: {info['supported_query_types']}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Basic functionality test failed: {e}")
        return False


async def test_legacy_interface():
    """Test the legacy interface for backward compatibility."""
    logger.info("Testing legacy interface...")
    
    try:
        # Test legacy interface
        response_text, is_complete = await generate_response(
            query="What is hypertension?",
            chat_history="",
            patient_data="General medical question"
        )
        
        if response_text and len(response_text) > 10:
            logger.info(f"✓ Legacy interface working: {len(response_text)} characters")
            logger.info(f"✓ Response complete: {is_complete}")
            return True
        else:
            logger.error("✗ Legacy interface returned empty response")
            return False
            
    except Exception as e:
        logger.error(f"✗ Legacy interface test failed: {e}")
        return False


async def test_enhanced_interface():
    """Test the enhanced interface with metadata."""
    logger.info("Testing enhanced interface...")
    
    try:
        # Test enhanced interface
        request = ConversationRequest(
            query="What are the side effects of aspirin?",
            patient_data="65-year-old male with hypertension",
            chat_history="",
            user_id="test_user"
        )
        
        response = await process_conversation(request)
        
        logger.info(f"✓ Enhanced interface working")
        logger.info(f"  - Query type: {response.query_type.value}")
        logger.info(f"  - Confidence: {response.confidence:.2f}")
        logger.info(f"  - Complete: {response.is_complete}")
        logger.info(f"  - Processing time: {response.processing_time:.2f}s")
        logger.info(f"  - Sources: {len(response.sources)}")
        logger.info(f"  - Response length: {len(response.response)} characters")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Enhanced interface test failed: {e}")
        return False


async def test_query_classification():
    """Test query classification for different types."""
    logger.info("Testing query classification...")
    
    test_cases = [
        ("What are the side effects of metformin?", "Type 2 diabetes patient", "drug_info"),
        ("45-year-old female presents with chest pain", "Patient has hypertension", "diagnosis"),
        ("What is diabetes?", "General medical question", "general")
    ]
    
    try:
        for query, patient_data, expected_type in test_cases:
            request = ConversationRequest(
                query=query,
                patient_data=patient_data,
                chat_history=""
            )
            
            response = await process_conversation(request)
            
            success = response.query_type.value == expected_type
            status = "✓" if success else "✗"
            logger.info(f"{status} '{query[:30]}...' -> {response.query_type.value} (expected: {expected_type})")
            
            if not success:
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Query classification test failed: {e}")
        return False


async def test_error_handling():
    """Test error handling with invalid inputs."""
    logger.info("Testing error handling...")
    
    try:
        # Test empty query
        try:
            await generate_response("", "", "")
            logger.error("✗ Should have failed with empty query")
            return False
        except Exception:
            logger.info("✓ Empty query properly rejected")
        
        # Test very long query
        long_query = "test " * 10000  # Very long query
        try:
            response_text, _ = await generate_response(long_query, "", "test")
            if len(response_text) > 0:
                logger.info("✓ Long query handled gracefully")
            else:
                logger.error("✗ Long query returned empty response")
                return False
        except Exception as e:
            logger.info(f"✓ Long query properly handled: {type(e).__name__}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Error handling test failed: {e}")
        return False


async def test_response_formatting():
    """Test response formatting for different query types."""
    logger.info("Testing response formatting...")
    
    try:
        # Test drug information formatting
        request = ConversationRequest(
            query="What are the side effects of aspirin?",
            patient_data="65-year-old male"
        )
        
        response = await process_conversation(request)
        
        # Check for expected sections in drug info response
        if response.query_type.value == "drug_info":
            response_text = response.response.lower()
            expected_sections = ["drug overview", "side effects", "sources"]
            
            for section in expected_sections:
                if section in response_text:
                    logger.info(f"✓ Found expected section: {section}")
                else:
                    logger.warning(f"⚠ Missing expected section: {section}")
        
        logger.info("✓ Response formatting test completed")
        return True
        
    except Exception as e:
        logger.error(f"✗ Response formatting test failed: {e}")
        return False


async def main():
    """Run all tests."""
    logger.info("Starting simplified conversational service tests...")
    logger.info("=" * 60)
    
    tests = [
        ("Basic Functionality", test_basic_functionality),
        ("Legacy Interface", test_legacy_interface),
        ("Enhanced Interface", test_enhanced_interface),
        ("Query Classification", test_query_classification),
        ("Error Handling", test_error_handling),
        ("Response Formatting", test_response_formatting)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n--- {test_name} ---")
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        logger.info(f"{status}: {test_name}")
        if result:
            passed += 1
    
    logger.info(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! The simplified service is working correctly.")
        return 0
    else:
        logger.error("❌ Some tests failed. Please check the logs above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

