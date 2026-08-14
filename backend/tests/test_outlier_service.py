import pandas as pd
import pytest

from app.services.outlier_service import (
    detect_outliers_iqr,
    detect_outliers_zscore,
    detect_outliers_modified_zscore,
    detect_outliers,
    remove_outliers,
    cap_outliers,
)


class TestDetectOutliersIQR:
    def test_flags_obvious_high_outlier(self):
        series = pd.Series([10, 11, 12, 13, 14, 100])
        mask = detect_outliers_iqr(series)
        assert mask.iloc[5] == True
        assert mask.iloc[0] == False

    def test_no_outliers_in_uniform_data(self):
        series = pd.Series([10, 11, 12, 13, 14, 15])
        mask = detect_outliers_iqr(series)
        assert mask.sum() == 0

    def test_flags_obvious_low_outlier(self):
        series = pd.Series([-500, 10, 11, 12, 13, 14])
        mask = detect_outliers_iqr(series)
        assert mask.iloc[0] == True


class TestDetectOutliersZScore:
    def test_flags_extreme_value(self):
        # A larger, less easily-distorted sample, with a genuinely
        # extreme outlier relative to it.
        series = pd.Series([10, 11, 12, 13, 14, 12, 11, 13, 10, 12, 11, 13, 14, 12, 5000])
        mask = detect_outliers_zscore(series)
        assert mask.iloc[-1] == True

    def test_small_sample_outlier_can_mask_itself(self):
        # Documents a known weakness of standard Z-score: in small
        # samples, one extreme value can inflate the mean/std enough
        # that its own Z-score no longer crosses the threshold. This
        # is exactly why Modified Z-score (median/MAD-based) exists as
        # a more robust alternative — see the corresponding test below.
        series = pd.Series([10, 11, 12, 13, 14, 12, 11, 13, 500])
        mask = detect_outliers_zscore(series)
        assert mask.iloc[-1] == False  # masked by its own influence on std

    def test_zero_std_returns_no_outliers(self):
        series = pd.Series([5, 5, 5, 5])
        mask = detect_outliers_zscore(series)
        assert mask.sum() == 0


class TestDetectOutliersModifiedZScore:
    def test_flags_extreme_value(self):
        series = pd.Series([10, 11, 12, 13, 14, 12, 11, 13, 500])
        mask = detect_outliers_modified_zscore(series)
        assert mask.iloc[-1] == True

    def test_zero_mad_returns_no_outliers(self):
        series = pd.Series([5, 5, 5, 5])
        mask = detect_outliers_modified_zscore(series)
        assert mask.sum() == 0


class TestDetectOutliers:
    def test_unknown_method_raises(self):
        series = pd.Series([1, 2, 3])
        with pytest.raises(ValueError):
            detect_outliers(series, "not_a_real_method")

    def test_returns_expected_keys(self):
        series = pd.Series([10, 11, 12, 100])
        result = detect_outliers(series, "iqr")
        assert "outlier_count" in result
        assert "outlier_percentage" in result
        assert "outlier_values" in result
        assert result["outlier_count"] == 1


class TestRemoveOutliers:
    def test_removes_flagged_rows(self):
        df = pd.DataFrame({"value": [10, 11, 12, 13, 1000]})
        result = remove_outliers(df, "value", "iqr")
        assert len(result) == 4
        assert 1000 not in result["value"].values

    def test_original_dataframe_not_mutated(self):
        df = pd.DataFrame({"value": [10, 11, 12, 13, 1000]})
        original_len = len(df)
        remove_outliers(df, "value", "iqr")
        assert len(df) == original_len


class TestCapOutliers:
    def test_caps_extreme_value_without_removing_row(self):
        df = pd.DataFrame({"value": [10, 11, 12, 13, 1000]})
        result = cap_outliers(df, "value", "iqr")
        assert len(result) == len(df)  # same row count
        assert result["value"].max() < 1000  # capped down

    def test_values_within_bounds_are_unchanged(self):
        df = pd.DataFrame({"value": [10, 11, 12, 13, 14]})
        result = cap_outliers(df, "value", "iqr")
        # no real outliers here, values should stay close to original
        assert result["value"].tolist() == pytest.approx(df["value"].tolist())