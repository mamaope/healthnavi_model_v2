from evidence_retrieval_test.src.providers.europe_pmc_provider import (
    _query_token_and_search as europe_pmc_token_search,
)
from evidence_retrieval_test.src.providers.pubmed_provider import (
    _parse_corrected_query,
    _query_token_and_search as pubmed_token_search,
)
from evidence_retrieval_test.src.providers.semantic_scholar_provider import (
    SEMANTIC_SCHOLAR_MIN_INTERVAL_SECONDS,
    _semantic_scholar_headers,
    _query_token_and_search as semantic_scholar_token_search,
)


def test_provider_fallback_queries_are_strict_and_topic_derived() -> None:
    query = "how to manage menstration in girls"

    assert pubmed_token_search(query) == "menstration AND girls"
    assert europe_pmc_token_search(query) == "menstration AND girls"
    assert semantic_scholar_token_search(query) == "menstration girls"


def test_pubmed_spelling_correction_parser() -> None:
    xml = """
    <eSpellResult>
      <Database>pubmed</Database>
      <Query>how to manage menstration in girls</Query>
      <CorrectedQuery>how to manage menstruation in girls</CorrectedQuery>
    </eSpellResult>
    """

    assert _parse_corrected_query(xml) == "how to manage menstruation in girls"


def test_semantic_scholar_auth_uses_required_header_name() -> None:
    assert _semantic_scholar_headers("test-key") == {"x-api-key": "test-key"}
    assert _semantic_scholar_headers(None) == {}


def test_semantic_scholar_rate_limit_has_buffer_below_one_rps() -> None:
    assert SEMANTIC_SCHOLAR_MIN_INTERVAL_SECONDS > 1.0
