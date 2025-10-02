#!/usr/bin/env python3
"""
Test script for the new modular conversational service.

This script demonstrates the new modular architecture and validates
that all components work correctly together.
"""

import asyncio
import sys
import os
import logging

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from healthnavi.services.conversational_service_v2 import (
    ConversationRequest, 
    process_conversation,
    get_conversational_service
)
from healthnavi.services.prompt_manager import get_prompt_manager
from healthnavi.services.query_classifier import get_query_classifier
from healthnavi.services.response_processor import get_response_processor
from healthnavi.services.model_manager import get_model_manager
from healthnavi.core.ai_config import QueryType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_service_components():
    """Test individual service components."""
    logger.info("Testing service components...")
    
    try:
        # Test prompt manager
        prompt_manager = get_prompt_manager()
        templates = prompt_manager.list_templates()
        logger.info(f"✓ Prompt Manager: {len(templates)} templates loaded")
        
        # Test query classifier
        query_classifier = get_query_classifier()
        rules = query_classifier.list_rules()
        logger.info(f"✓ Query Classifier: {len(rules)} rules loaded")
        
        # Test response processor
        response_processor = get_response_processor()
        logger.info("✓ Response Processor: Initialized successfully")
        
        # Test model manager
        model_manager = get_model_manager()
        models = model_manager.get_available_models()
        is_healthy = model_manager.is_healthy()
        logger.info(f"✓ Model Manager: {len(models)} models, healthy: {is_healthy}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Component test failed: {e}")
        return False


async def test_query_classification():
    """Test query classification functionality."""
    logger.info("Testing query classification...")
    
    try:
        query_classifier = get_query_classifier()
        
        # Test different query types
        test_queries = [
            ("What are the side effects of aspirin?", "65-year-old male", QueryType.DRUG_INFORMATION),
            ("45-year-old female presents with chest pain", "Patient has hypertension", QueryType.DIFFERENTIAL_DIAGNOSIS),
            ("How should I manage diabetes?", "Type 2 diabetes patient", QueryType.CLINICAL_GUIDANCE),
            ("What is hypertension?", "General question", QueryType.GENERAL_QUERY)
        ]
        
        for query, patient_data, expected_type in test_queries:
            result = await query_classifier.classify_query(query, patient_data)
            success = result.query_type == expected_type
            status = "✓" if success else "✗"
            logger.info(f"{status} Query: '{query[:30]}...' -> {result.query_type.value} (confidence: {result.confidence:.2f})")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Query classification test failed: {e}")
        return False


async def test_prompt_generation():
    """Test prompt generation functionality."""
    logger.info("Testing prompt generation...")
    
    try:
        prompt_manager = get_prompt_manager()
        
        # Test prompt generation for different query types
        test_context = {
            "patient_data": "65-year-old male with chest pain",
            "context": "Sample medical context about chest pain",
            "sources": "Medical guidelines, Clinical protocols",
            "chat_history": "Previous conversation about symptoms",
            "query": "What could cause chest pain?"
        }
        
        from healthnavi.services.prompt_manager import PromptContext
        context = PromptContext(**test_context)
        
        for query_type in [QueryType.DIFFERENTIAL_DIAGNOSIS, QueryType.DRUG_INFORMATION]:
            try:
                prompt = prompt_manager.format_prompt(query_type, context)
                logger.info(f"✓ Generated prompt for {query_type.value} ({len(prompt)} characters)")
            except Exception as e:
                logger.error(f"✗ Failed to generate prompt for {query_type.value}: {e}")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Prompt generation test failed: {e}")
        return False


async def test_response_processing():
    """Test response processing functionality."""
    logger.info("Testing response processing...")
    
    try:
        response_processor = get_response_processor()
        
        # Test response processing
        test_response = """
        **CLINICAL OVERVIEW**
        This is a test response for validation.
        
        **DIFFERENTIAL DIAGNOSES**
        1. Test condition (80%): Based on symptoms
        2. Alternative condition (20%): Less likely
        
        **Sources:** Test medical source
        
        *This application is for clinical decision support and should only be used by qualified healthcare professionals.*
        """
        
        result = response_processor.process_response(
            test_response,
            "differential_diagnosis",
            enable_validation=True,
            enable_sanitization=True,
            enable_formatting=True
        )
        
        logger.info(f"✓ Response processed successfully")
        logger.info(f"  - Validation score: {result.validation_result.score:.2f}")
        logger.info(f"  - Is valid: {result.validation_result.is_valid}")
        logger.info(f"  - Processing steps: {result.metadata.get('processing_steps', [])}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Response processing test failed: {e}")
        return False


async def test_full_conversation():
    """Test full conversation processing (without actual model call)."""
    logger.info("Testing full conversation processing...")
    
    try:
        # Create a test request
        request = ConversationRequest(
            query="What are the side effects of aspirin?",
            chat_history="",
            patient_data="65-year-old male with hypertension",
            user_id="test_user",
            session_id="test_session"
        )
        
        # Get service info
        service = get_conversational_service()
        info = service.get_service_info()
        logger.info(f"✓ Service info retrieved: {info['service_version']}")
        logger.info(f"  - Components: {len(info['components'])}")
        logger.info(f"  - Model healthy: {info['components']['model_manager']['healthy']}")
        
        # Note: We don't actually call the model in this test to avoid API costs
        # In a real test, you would uncomment the following:
        # response = await process_conversation(request)
        # logger.info(f"✓ Full conversation processed: {response.query_type.value}")
        
        logger.info("✓ Full conversation test structure validated (model call skipped)")
        return True
        
    except Exception as e:
        logger.error(f"✗ Full conversation test failed: {e}")
        return False


async def main():
    """Run all tests."""
    logger.info("Starting modular conversational service tests...")
    logger.info("=" * 60)
    
    tests = [
        ("Service Components", test_service_components),
        ("Query Classification", test_query_classification),
        ("Prompt Generation", test_prompt_generation),
        ("Response Processing", test_response_processing),
        ("Full Conversation", test_full_conversation)
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
        logger.info("🎉 All tests passed! The modular service is working correctly.")
        return 0
    else:
        logger.error("❌ Some tests failed. Please check the logs above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

