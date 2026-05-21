from evidence_retrieval_test.src.providers.official_health_api_provider import (
    OfficialHealthAPIProvider,
    _matching_world_bank_indicators,
    _who_indicator_to_item,
    _world_bank_indicator_to_item,
)
from evidence_retrieval_test.src.config import EvidenceRetrievalSettings


def test_cdc_result_to_item_uses_verified_source_link() -> None:
    provider = OfficialHealthAPIProvider(EvidenceRetrievalSettings())

    item = provider._cdc_result_to_item(
        {
            "id": 123,
            "name": "Clinical guidance",
            "description": "<p>CDC clinical guidance.</p>",
            "targetUrl": "https://www.cdc.gov/healthcare-providers/index.html",
            "dateContentUpdated": "2026-01-10T00:00:00Z",
            "source": {"name": "Centers for Disease Control and Prevention"},
        },
        "clinical guidance",
    )

    assert item.source == "official_health_api"
    assert item.url == "https://www.cdc.gov/healthcare-providers/index.html"
    assert item.year == 2026
    assert item.evidence_type == "official_guidance"
    assert "CDC clinical guidance" in (item.snippet or "")


def test_who_indicator_item_summarizes_uganda_and_zambia_rows() -> None:
    item = _who_indicator_to_item(
        "HEALTH_TEST",
        "Health service coverage",
        [
            {"SpatialDim": "UGA", "TimeDim": 2024, "Value": "120"},
            {"SpatialDim": "ZMB", "TimeDim": 2023, "Value": "85"},
        ],
        "health service coverage Uganda Zambia",
    )

    assert item.journal_or_publisher == "World Health Organization Global Health Observatory"
    assert "Uganda: 120 (2024)" in (item.snippet or "")
    assert "Zambia: 85 (2023)" in (item.snippet or "")
    assert "ghoapi.azureedge.net" in str(item.url)


def test_world_bank_indicator_matching_prioritizes_country_health_terms() -> None:
    matched = _matching_world_bank_indicators("maternal mortality in Uganda and Zambia")

    assert matched
    assert matched[0]["id"] == "SH.STA.MMRT"


def test_world_bank_indicator_item_summarizes_latest_country_values() -> None:
    item = _world_bank_indicator_to_item(
        {
            "id": "SH.STA.MMRT",
            "name": "Maternal mortality ratio",
            "sourceNote": "Maternal deaths per 100,000 live births.",
            "topics": [{"value": "Health"}],
        },
        [
            {"countryiso3code": "UGA", "date": "2022", "value": 200},
            {"countryiso3code": "UGA", "date": "2023", "value": 180},
            {"countryiso3code": "ZMB", "date": "2023", "value": 90},
        ],
        "maternal mortality",
        "https://api.worldbank.org/v2/country/UGA;ZMB/indicator/SH.STA.MMRT",
    )

    assert item.year == 2023
    assert "Uganda: 180 (2023)" in (item.snippet or "")
    assert "Zambia: 90 (2023)" in (item.snippet or "")
