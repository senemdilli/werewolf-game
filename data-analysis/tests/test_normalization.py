import pytest

from data.models.trust_metric import TrustScale
from data.normalization import (
    TRUST_LIKERT_VALUES,
    confidence_ordinal,
    infer_trust_scale,
    normalize_confidence,
    normalize_trust,
)


class TestNormalizeTrust:
    @pytest.mark.parametrize("value,expected", [(1, 0.0), (4, 0.5), (7, 1.0)])
    def test_seven_point(self, value, expected):
        assert normalize_trust(value, TrustScale.SEVEN_POINT) == expected

    @pytest.mark.parametrize("value,expected", [(1, 0.0), (100, 1.0)])
    def test_numeric_100_endpoints(self, value, expected):
        assert normalize_trust(value, TrustScale.NUMERIC_100) == expected

    def test_numeric_100_midrange(self):
        assert normalize_trust(50, TrustScale.NUMERIC_100) == pytest.approx(49 / 99)

    def test_none_passthrough(self):
        assert normalize_trust(None, TrustScale.SEVEN_POINT) is None

    def test_out_of_range_clamped(self):
        assert normalize_trust(0, TrustScale.SEVEN_POINT) == 0.0
        assert normalize_trust(9, TrustScale.SEVEN_POINT) == 1.0


class TestNormalizeConfidence:
    @pytest.mark.parametrize("value,expected", [
        ("LOW", 0.0), ("MEDIUM", 0.5), ("HIGH", 1.0),
        ("low", 0.0), (" high ", 1.0),
        ("LOW_CONFIDENCE", 0.0), ("HIGH_CONFIDENCE", 1.0),
        (1, 0.0), (2, 0.5), (3, 1.0),
    ])
    def test_values(self, value, expected):
        assert normalize_confidence(value) == expected

    def test_unknown_string(self):
        assert normalize_confidence("WHATEVER") is None

    def test_none(self):
        assert normalize_confidence(None) is None

    def test_ordinal(self):
        assert confidence_ordinal("MEDIUM") == 2
        assert confidence_ordinal(3) == 3
        assert confidence_ordinal(None) is None


class TestLikertValues:
    def test_both_scales_cover_1_to_7(self):
        legacy = [v for k, v in TRUST_LIKERT_VALUES.items() if k.endswith("_TRUST")]
        agree = [v for k, v in TRUST_LIKERT_VALUES.items() if not k.endswith("_TRUST")]
        assert sorted(legacy) == list(range(1, 8))
        assert sorted(agree) == list(range(1, 8))


class TestInferTrustScale:
    def test_explicit_modes(self):
        assert infer_trust_scale("numeric", [1, 2]) == TrustScale.NUMERIC_100
        assert infer_trust_scale("likert", [1, 2]) == TrustScale.SEVEN_POINT

    def test_inferred_from_values(self):
        assert infer_trust_scale(None, [3, 80, 5]) == TrustScale.NUMERIC_100
        assert infer_trust_scale(None, [1, 4, 7]) == TrustScale.SEVEN_POINT

    def test_empty_defaults_to_seven_point(self):
        assert infer_trust_scale(None, []) == TrustScale.SEVEN_POINT
