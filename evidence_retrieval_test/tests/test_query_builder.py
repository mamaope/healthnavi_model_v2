from evidence_retrieval_test.src.services.query_builder import (
    build_evidence_query,
    build_provider_query,
    normalize_question,
)


def test_normalize_question_removes_punctuation_and_age_numbers() -> None:
    assert normalize_question("30 year old female has HIV, what treatment?") == (
        "30 year old female has hiv what treatment"
    )


def test_build_evidence_query_uses_only_user_terms() -> None:
    query = build_evidence_query(
        "30 year old female has HIV, what is the treatment for her?"
    )

    assert "30 year old" in query
    assert "hiv" in query
    assert "treatment" in query
    assert "clinical guideline" not in query


def test_build_evidence_query_is_not_disease_specific() -> None:
    query = build_evidence_query(
        "What are the treatment options for severe malnutrition in children under 5?"
    )

    assert "severe" in query
    assert "malnutrition" in query
    assert "children" in query
    assert "under 5" in query
    assert "RUTF" not in query


def test_build_provider_query_keeps_literature_search_clean() -> None:
    query = build_provider_query(
        "What are the treatment options for severe malnutrition in children under 5?",
        "pubmed",
    )

    assert "malnutrition" in query
    assert "treatment" in query
    assert "clinical guideline" not in query
    assert "population specific" not in query
