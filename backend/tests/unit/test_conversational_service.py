import asyncio

from healthnavi.services import conversational_service
from healthnavi.services.conversational_service import _chunk_text
from healthnavi.services.evidence_retrieval_adapter import AnswerGenerationError


def test_chunk_text_preserves_original_spacing_across_boundaries():
    text = (
        "Treatment for severe acute malnutrition includes outpatient therapeutic care "
        "when the child has appetite and no complications, and inpatient stabilization "
        "when danger signs or medical complications are present."
    )

    chunks = _chunk_text(text, chunk_size=58)

    assert len(chunks) > 1
    assert "".join(chunks) == text
    assert "carewhen" not in "".join(chunks)
    assert "stabilizationwhen" not in "".join(chunks)


def test_generate_response_returns_safe_message_and_does_not_cache_failures(monkeypatch):
    calls = []

    async def failing_generation(**kwargs):
        calls.append(kwargs["query"])
        raise AnswerGenerationError("model service did not return an answer")

    monkeypatch.setattr(
        conversational_service, "generate_model_service_response", failing_generation
    )
    conversational_service.RESPONSE_CACHE.clear()

    for _ in range(2):
        response, complete, prompt_type, followups = asyncio.run(
            conversational_service.generate_response(
                query="What is the dose of amoxicillin for otitis media?",
                chat_history="",
                patient_data="What is the dose of amoxicillin for otitis media?",
            )
        )
        assert response == conversational_service.USER_SAFE_GENERATION_ERROR
        assert complete is False
        assert prompt_type == "model_service_error"
        assert followups == []

    # A failure is never cached, so the next request retries instead of
    # replaying the error for the cache lifetime.
    assert len(calls) == 2
    assert not conversational_service.RESPONSE_CACHE
