"""
How operationally specific a passage is.

Lexical overlap alone cannot tell the page that *names* a care pathway from the
page that says what to actually give. Both mention the condition; only one is
usable at the bedside. This module scores that difference with signals that hold
for any clinical question in any specialty: quantities with units, weight-based
doses, administration frequencies, numeric thresholds, and treatment durations.

There is deliberately no medical vocabulary here. Nothing is matched against
drug names, conditions, or specialties, so the signal behaves the same for a
question about malnutrition, anticoagulation, or neonatal resuscitation. It is
used only to break ties between passages of equal source authority, never to
decide relevance, so a question whose answer is genuinely qualitative (a
mechanism, a definition) is unaffected because no candidate scores on it.
"""

from __future__ import annotations

import re

# Each entry is one family of "this passage carries an executable instruction"
# evidence. Families are counted, not occurrences, so a dosing table full of
# milligram values does not outweigh a passage that gives a dose, a frequency
# and a duration.
_SPECIFICITY_PATTERNS: tuple[re.Pattern[str], ...] = (
    # A quantity with a clinical unit: 500 mg, 2.5 mL, 200 000 IU, 12.5 cm, 37.5 °C.
    re.compile(
        r"\b\d+(?:[.,]\d+)?\s*"
        r"(?:mcg|microgram|micrograms|mg|g|kg|gram|grams|ml|millilitre|milliliter|l|litre|liter"
        r"|iu|units?|mmol|mol|mval|meq|mmhg|kcal|cal|cm|mm|m|%|°c|º c|degrees)\b",
        re.IGNORECASE,
    ),
    # A dose expressed per unit of body weight, surface area or time.
    re.compile(
        r"\b\d+(?:[.,]\d+)?\s*(?:mcg|mg|g|ml|iu|units?|mmol|kcal)\s*/\s*"
        r"(?:kg|m2|m²|day|dose|hour|hr|h|min|minute|week)",
        re.IGNORECASE,
    ),
    # How often it is given.
    re.compile(
        r"\b(?:every\s+(?:\d+|other|second|third)\s*(?:hour|hours|hr|hrs|h|minute|minutes|min|day|days|week|weeks)"
        r"|(?:\d+|one|two|three|four|five|six)\s*(?:times|x)\s*(?:a|per|each)?\s*(?:day|week|daily)"
        r"|once|twice|thrice)\s*(?:daily|a day|per day|weekly|a week|per week)?\b"
        r"|\b(?:od|bd|bid|tds|tid|qds|qid|prn|stat|nocte)\b",
        re.IGNORECASE,
    ),
    # A numeric decision threshold.
    re.compile(r"(?:<|>|≤|≥|<=|>=|less than|greater than|at least|below|above)\s*[-–]?\s*\d"),
    # How long treatment runs.
    re.compile(
        r"\bfor\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
        r"\s*(?:-|–|to|or)?\s*(?:\d+\s*)?"
        r"(?:hour|hours|day|days|week|weeks|month|months)\b",
        re.IGNORECASE,
    ),
)

_FAMILY_COUNT = len(_SPECIFICITY_PATTERNS)


def clinical_specificity_score(text: str) -> float:
    """Fraction of specificity families present in ``text``, from 0.0 to 1.0."""
    if not text:
        return 0.0
    sample = text[:4000]
    matched = sum(1 for pattern in _SPECIFICITY_PATTERNS if pattern.search(sample))
    return matched / _FAMILY_COUNT
