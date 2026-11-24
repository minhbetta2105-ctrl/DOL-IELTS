"""Reference conversion for full 40-question practice tests; never scale short quizzes.
Source: https://ielts.idp.com/vietnam/about/news-and-articles/article-ielts-test-format-explained
Cutoffs vary by test version. Low-score ranges are supplementary practice estimates (see https://ieltsm.com/band-score-calculator/ and https://ece.edu.vn/en/how-to-calculate-your-ielts-band-score-for-all-4-skills-and-overall-2/). No score is official.
"""
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

_THRESHOLDS = {
    "READING": ((39,"9.0"),(37,"8.5"),(35,"8.0"),(33,"7.5"),(30,"7.0"),(27,"6.5"),(23,"6.0"),(20,"5.5"),(16,"5.0"),(13,"4.5"),(10,"4.0"),(7,"3.5"),(5,"3.0"),(4,"2.5"),(2,"2.0"),(0,"1.0")),
    "LISTENING": ((39,"9.0"),(37,"8.5"),(35,"8.0"),(32,"7.5"),(30,"7.0"),(26,"6.5"),(23,"6.0"),(18,"5.5"),(16,"5.0"),(13,"4.5"),(10,"4.0"),(8,"3.5"),(6,"3.0"),(4,"2.5"),(2,"2.0"),(0,"1.0")),
}
ANCHORS = _THRESHOLDS  # retained import for other modules

def reference_band_40(correct, skill):
    if correct is None or not 0 <= correct <= 40:
        return None
    return next((Decimal(band) for raw, band in _THRESHOLDS.get(skill, ()) if correct >= raw), None)

def band_for_result(correct, total, skill, mode="EXAM"):
    return reference_band_40(correct, skill) if total == 40 and mode == "EXAM" else None

def band_ranges(skill):
    upper=40
    for lower,band in _THRESHOLDS.get(skill, ()):
        yield (f"{lower}–{upper}" if lower != upper else str(lower), band)
        upper=lower-1
    if upper >= 0:
        yield (f"0–{upper}", "Dưới mốc nguồn công bố")

def full_test_minutes(skill, count, fallback):
    return (60 if skill == "READING" else 30) if count == 40 else fallback

def overall_reference(values):
    if len(values) != 4 or any(v is None for v in values):
        return None
    try:
        values=[Decimal(str(v)) for v in values]
        if any(not v.is_finite() or v<0 or v>9 or v*2 != (v*2).to_integral_value() for v in values): return None
        return ((sum(values)/4*2).quantize(Decimal('1'), rounding=ROUND_HALF_UP)/2).quantize(Decimal('0.1'))
    except (InvalidOperation, ValueError, TypeError):
        return None
