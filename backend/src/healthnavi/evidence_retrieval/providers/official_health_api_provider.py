from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, wait
from urllib.parse import urlencode

import httpx

from healthnavi.evidence_retrieval.config import EvidenceRetrievalSettings
from healthnavi.evidence_retrieval.models import EvidenceItem, EvidenceSource
from healthnavi.evidence_retrieval.providers.base import BaseEvidenceProvider, ProviderError

QUERY_TOKEN_STOPWORDS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "can",
    "do",
    "does",
    "female",
    "for",
    "from",
    "has",
    "have",
    "how",
    "initial",
    "line",
    "male",
    "old",
    "or",
    "should",
    "standard",
    "the",
    "this",
    "that",
    "these",
    "those",
    "what",
    "when",
    "where",
    "which",
    "who",
    "with",
    "without",
    "year",
}


class OfficialHealthAPIProvider(BaseEvidenceProvider):
    source_name = EvidenceSource.OFFICIAL_HEALTH_API.value
    CDC_MEDIA_URL = "https://tools.cdc.gov/api/v2/resources/media"
    WHO_INDICATOR_URL = "https://ghoapi.azureedge.net/api/Indicator"
    WHO_API_BASE = "https://ghoapi.azureedge.net/api"
    WORLD_BANK_API_BASE = "https://api.worldbank.org/v2"
    WORLD_BANK_INDICATORS_URL = "https://api.worldbank.org/v2/topic/8/indicator"

    def search(self, query: str, max_results: int) -> list[EvidenceItem]:
        if not self.settings.enable_official_health_apis:
            return []

        items: list[EvidenceItem] = []
        errors: list[str] = []
        source_limits = {
            "cdc": 2,
            "who": 1,
            "world_bank": 2,
        }
        started_at = time.perf_counter()
        fetchers = {
            "cdc": lambda: self._search_cdc_content(query, source_limits["cdc"]),
            "who": lambda: self._search_who_gho(query, source_limits["who"]),
            "world_bank": lambda: self._search_world_bank_country_health(
                query,
                source_limits["world_bank"],
            ),
        }
        executor = ThreadPoolExecutor(max_workers=len(fetchers))
        try:
            futures = {executor.submit(fetcher): name for name, fetcher in fetchers.items()}
            done, pending = wait(
                futures,
                timeout=min(max(self.settings.request_timeout_seconds - 0.5, 1.0), 3.5),
            )
            for future in done:
                try:
                    items.extend(future.result())
                except httpx.HTTPError as exc:
                    errors.append(f"{futures[future]}: {exc}")
            for future in pending:
                errors.append(
                    f"{futures[future]} exceeded official API source budget "
                    f"({(time.perf_counter() - started_at):.1f}s)"
                )
                future.cancel()
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        if errors and not items:
            raise ProviderError(f"Official health API search failed: {'; '.join(errors)}")
        return items[:max_results]

    def _country_codes(self) -> tuple[str, ...]:
        return tuple(self.settings.official_health_api_country_codes or ["UGA"])

    def _search_cdc_content(self, query: str, max_results: int) -> list[EvidenceItem]:
        params = {
            "q": query,
            "max": max_results,
            "fields": ",".join(
                [
                    "id",
                    "name",
                    "description",
                    "featuredText",
                    "source",
                    "sourceUrl",
                    "targetUrl",
                    "persistentUrl",
                    "datePublished",
                    "dateModified",
                    "dateContentUpdated",
                    "domainName",
                ]
            ),
        }
        with httpx.Client(timeout=self.timeout) as client:
            data = self._get_json(client, self.CDC_MEDIA_URL, params)

        results = _result_list(data)
        return [
            self._cdc_result_to_item(result, query)
            for result in results[:max_results]
            if result.get("name") and _best_url(result)
        ]

    def _cdc_result_to_item(self, result: dict, query: str) -> EvidenceItem:
        url = _best_url(result) or "https://www.cdc.gov/"
        source = result.get("source") if isinstance(result.get("source"), dict) else {}
        snippet = result.get("description") or result.get("featuredText")
        return EvidenceItem(
            id=f"official_health_api:cdc:{result.get('id') or _slug(result.get('name', url))}",
            source=EvidenceSource.OFFICIAL_HEALTH_API,
            title=str(result.get("name")).strip(),
            snippet=_clean_snippet(snippet),
            journal_or_publisher=source.get("name") or "Centers for Disease Control and Prevention",
            publication_date=result.get("dateContentUpdated")
            or result.get("dateModified")
            or result.get("datePublished"),
            year=_safe_year(
                result.get("dateContentUpdated")
                or result.get("dateModified")
                or result.get("datePublished")
            ),
            url=url,
            evidence_type="official_guidance",
            raw={"provider": "CDC Content Services API", "query_used": query, **result},
        )

    def _search_who_gho(self, query: str, max_results: int) -> list[EvidenceItem]:
        terms = _search_terms(query)
        if not terms:
            return []

        items: list[EvidenceItem] = []
        with httpx.Client(timeout=self.timeout) as client:
            indicators = self._find_who_indicators(client, terms, max_results)
            for indicator in indicators[:max_results]:
                code = indicator.get("IndicatorCode")
                name = indicator.get("IndicatorName")
                if not code or not name:
                    continue
                country_codes = self._country_codes()
                country_rows = self._fetch_who_country_rows(client, code, country_codes)
                items.append(_who_indicator_to_item(code, name, country_rows, query, country_codes))
        return items

    def _find_who_indicators(
        self,
        client: httpx.Client,
        terms: list[str],
        max_results: int,
    ) -> list[dict]:
        indicator_candidates: dict[str, dict] = {}
        for term in terms[:4]:
            data = self._get_json(
                client,
                self.WHO_INDICATOR_URL,
                {
                    "$filter": f"contains(tolower(IndicatorName),'{_odata_literal(term)}')",
                    "$top": 20,
                    "$select": "IndicatorCode,IndicatorName",
                },
            )
            for indicator in data.get("value", []):
                code = indicator.get("IndicatorCode")
                if code:
                    indicator_candidates[str(code)] = indicator

        scored = [
            (_metadata_score(terms, indicator.get("IndicatorName", "")), indicator)
            for indicator in indicator_candidates.values()
        ]
        return [
            indicator
            for score, indicator in sorted(scored, key=lambda item: item[0], reverse=True)
            if score > 0
        ][:max_results]

    def _fetch_who_country_rows(
        self,
        client: httpx.Client,
        indicator_code: str,
        country_codes: tuple[str, ...],
    ) -> list[dict]:
        data = self._get_json(
            client,
            f"{self.WHO_API_BASE}/{indicator_code}",
            {
                "$filter": _who_country_filter(country_codes),
                "$orderby": "TimeDimensionBegin desc",
                "$top": 20,
            },
        )
        return data.get("value", [])

    def _search_world_bank_country_health(
        self,
        query: str,
        max_results: int,
    ) -> list[EvidenceItem]:
        terms = _search_terms(query)
        if not terms:
            return []

        matched = self._find_world_bank_indicators(terms, max_results)
        if not matched:
            return []

        items: list[EvidenceItem] = []
        with httpx.Client(timeout=self.timeout) as client:
            for indicator in matched:
                country_codes = self._country_codes()
                country_path = ";".join(country_codes)
                url = (
                    f"{self.WORLD_BANK_API_BASE}/country/{country_path}/indicator/"
                    f"{_world_bank_indicator_code(indicator)}"
                )
                data = self._get_json(
                    client,
                    url,
                    {"format": "json", "mrv": 1, "per_page": 10},
                )
                rows = data[1] if isinstance(data, list) and len(data) > 1 else []
                items.append(
                    _world_bank_indicator_to_item(indicator, rows, query, url, country_codes)
                )
        return items

    def _find_world_bank_indicators(
        self,
        terms: list[str],
        max_results: int,
    ) -> list[dict[str, object]]:
        indicators: dict[str, dict[str, object]] = {}
        with httpx.Client(timeout=self.timeout) as client:
            for page in range(1, 4):
                data = self._get_json(
                    client,
                    self.WORLD_BANK_INDICATORS_URL,
                    {
                        "format": "json",
                        "per_page": 100,
                        "page": page,
                    },
                )
                rows = data[1] if isinstance(data, list) and len(data) > 1 else []
                for row in rows:
                    code = row.get("id")
                    if code:
                        indicators[str(code)] = row

        scored = [
            (_world_bank_indicator_score(terms, indicator), indicator)
            for indicator in indicators.values()
        ]
        return [
            indicator
            for score, indicator in sorted(scored, key=lambda item: item[0], reverse=True)
            if score > 0
        ][:max_results]


def _result_list(data: dict) -> list[dict]:
    for key in ("results", "items", "data"):
        value = data.get(key)
        if isinstance(value, list):
            return value
    return []


def _best_url(result: dict) -> str | None:
    for key in ("targetUrl", "persistentUrl", "sourceUrl"):
        value = result.get(key)
        if value:
            return str(value)
    return None


def _who_indicator_to_item(
    code: str,
    name: str,
    country_rows: list[dict],
    query: str,
    country_codes: tuple[str, ...],
) -> EvidenceItem:
    latest = _latest_by_country(country_rows, country_key="SpatialDim")
    snippet = _country_value_snippet(
        latest,
        country_key="SpatialDim",
        label_key="SpatialDim",
        value_key="Value",
        year_key="TimeDim",
        country_codes=country_codes,
    )
    api_url = _url_with_params(
        f"https://ghoapi.azureedge.net/api/{code}",
        {
            "$filter": _who_country_filter(country_codes),
            "$orderby": "TimeDimensionBegin desc",
        },
    )
    return EvidenceItem(
        id=f"official_health_api:who:{code}",
        source=EvidenceSource.OFFICIAL_HEALTH_API,
        title=f"WHO GHO indicator: {name}",
        snippet=snippet or "WHO Global Health Observatory indicator metadata.",
        journal_or_publisher="World Health Organization Global Health Observatory",
        year=_latest_year(latest, "TimeDim"),
        url=api_url,
        evidence_type="official_indicator",
        raw={"provider": "WHO GHO OData API", "indicator_code": code, "query_used": query},
    )


def _world_bank_indicator_to_item(
    indicator: dict[str, object],
    rows: list[dict],
    query: str,
    api_url: str,
    country_codes: tuple[str, ...],
) -> EvidenceItem:
    latest = _latest_by_country(rows, country_key="countryiso3code")
    snippet = _country_value_snippet(
        latest,
        country_key="countryiso3code",
        label_key="countryiso3code",
        value_key="value",
        year_key="date",
        country_codes=country_codes,
    )
    return EvidenceItem(
        id=f"official_health_api:world_bank:{_world_bank_indicator_code(indicator)}",
        source=EvidenceSource.OFFICIAL_HEALTH_API,
        title=f"World Bank indicator: {indicator.get('name')}",
        snippet=snippet
        or "World Bank health/development indicator.",
        journal_or_publisher="World Bank Indicators API",
        year=_latest_year(latest, "date"),
        url=_url_with_params(api_url, {"format": "json", "mrv": 1, "per_page": 10}),
        evidence_type="official_indicator",
        raw={
            "provider": "World Bank Indicators API",
            "indicator_code": _world_bank_indicator_code(indicator),
            "query_used": query,
        },
    )


def _latest_by_country(rows: list[dict], country_key: str) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for row in rows:
        country = row.get(country_key)
        if not country:
            continue
        year = _safe_year(row.get("TimeDim") or row.get("date"))
        previous_year = _safe_year(latest.get(country, {}).get("TimeDim") or latest.get(country, {}).get("date"))
        if country not in latest or (year or 0) > (previous_year or 0):
            latest[str(country)] = row
    return latest


def _country_value_snippet(
    latest: dict[str, dict],
    *,
    country_key: str,
    label_key: str,
    value_key: str,
    year_key: str,
    country_codes: tuple[str, ...],
) -> str | None:
    if not latest:
        return None
    parts = []
    for code in country_codes:
        row = latest.get(code)
        if not row:
            continue
        label = _country_label(str(row.get(label_key) or row.get(country_key) or code))
        value = row.get(value_key)
        year = row.get(year_key)
        if value is not None:
            parts.append(f"{label}: {value} ({year or 'year not stated'})")
    if not parts:
        return None
    return "Latest official country data retrieved through API. " + "; ".join(parts) + "."


def _matching_world_bank_indicators(query: str) -> list[dict[str, object]]:
    """Test helper: score dynamic indicator-like metadata without API calls."""
    terms = _query_tokens(query)
    if not terms:
        return []

    scored: list[tuple[int, dict[str, object]]] = []
    for indicator in _WORLD_BANK_HEALTH_INDICATOR_EXAMPLES:
        score = _world_bank_indicator_score(terms, indicator)
        if score:
            scored.append((score, indicator))
    return [indicator for _, indicator in sorted(scored, key=lambda item: item[0], reverse=True)]


def _search_terms(query: str) -> list[str]:
    return _query_tokens(query)


def _metadata_score(terms: list[str], *metadata_values: object) -> int:
    haystack = " ".join(str(value or "").lower() for value in metadata_values)
    return sum(1 for term in terms if term in haystack)


def _world_bank_indicator_score(terms: list[str], indicator: dict[str, object]) -> int:
    topic_values = indicator.get("topics") or indicator.get("topic") or []
    if isinstance(topic_values, list):
        topic_text = " ".join(
            str(topic.get("value") or topic.get("id") or topic)
            for topic in topic_values
            if topic
        )
    else:
        topic_text = str(topic_values)
    return _metadata_score(
        terms,
        indicator.get("name"),
        indicator.get("sourceNote"),
        topic_text,
    )


def _world_bank_indicator_code(indicator: dict[str, object]) -> str:
    return str(indicator.get("id") or indicator.get("code") or "")


def _query_tokens(query: str) -> list[str]:
    seen: set[str] = set()
    tokens: list[str] = []
    for token in re.sub(r"[^a-zA-Z0-9\s]", " ", query.lower()).split():
        if (
            token.isdigit()
            or len(token) < 3
            or token in QUERY_TOKEN_STOPWORDS
            or token in seen
        ):
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def _clean_snippet(value: object) -> str | None:
    if not value:
        return None
    text = re.sub(r"<[^>]+>", " ", str(value))
    return re.sub(r"\s+", " ", text).strip() or None


def _safe_year(value: object) -> int | None:
    if value is None:
        return None
    text = str(value)
    match = re.search(r"\d{4}", text)
    return int(match.group(0)) if match else None


def _latest_year(latest: dict[str, dict], key: str) -> int | None:
    years = [_safe_year(row.get(key)) for row in latest.values()]
    years = [year for year in years if year is not None]
    return max(years) if years else None


def _country_label(code: str) -> str:
    return {
        "UGA": "Uganda",
        "KEN": "Kenya",
        "TZA": "Tanzania",
    }.get(code, code)


def _who_country_filter(country_codes: tuple[str, ...]) -> str:
    return " or ".join(f"SpatialDim eq '{_odata_literal(country)}'" for country in country_codes)


def _odata_literal(value: str) -> str:
    return value.replace("'", "''")


def _url_with_params(url: str, params: dict[str, object]) -> str:
    return f"{url}?{urlencode(params)}"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:80] or "item"


_WORLD_BANK_HEALTH_INDICATOR_EXAMPLES: list[dict[str, object]] = [
    {
        "id": "SH.STA.MMRT",
        "name": "Maternal mortality ratio (modeled estimate, per 100,000 live births)",
        "sourceNote": "Maternal deaths per 100,000 live births.",
        "topics": [{"value": "Health"}],
    },
    {
        "id": "SH.DYN.MORT",
        "name": "Mortality rate, under-5 (per 1,000 live births)",
        "sourceNote": "Probability per 1,000 that a newborn baby will die before age five.",
        "topics": [{"value": "Health"}],
    },
    {
        "id": "SP.DYN.LE00.IN",
        "name": "Life expectancy at birth, total (years)",
        "sourceNote": "Life expectancy at birth indicates expected years of life.",
        "topics": [{"value": "Health"}],
    },
    {
        "id": "SH.MED.PHYS.ZS",
        "name": "Physicians (per 1,000 people)",
        "sourceNote": "Physicians include generalist and specialist medical practitioners.",
        "topics": [{"value": "Health"}],
    },
    {
        "id": "SH.MED.NUMW.P3",
        "name": "Nurses and midwives (per 1,000 people)",
        "sourceNote": "Nursing and midwifery personnel.",
        "topics": [{"value": "Health"}],
    },
    {
        "id": "SH.XPD.CHEX.PC.CD",
        "name": "Current health expenditure per capita (current US$)",
        "sourceNote": "Current health expenditures per capita.",
        "topics": [{"value": "Health"}],
    },
]
