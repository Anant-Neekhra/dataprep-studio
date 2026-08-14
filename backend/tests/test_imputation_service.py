import pandas as pd
import pytest

from app.services.imputation_service import (
    apply_imputation,
    impute_column_in_dataframe,
    validate_strategy_for_column,
    summarize_column,
)


class TestApplyImputation:
    def test_mean_fills_missing_with_column_mean(self):
        series = pd.Series([1, 2, None, 4])
        result = apply_imputation(series, "mean")
        assert result.iloc[2] == pytest.approx(2.333, abs=0.01)
        assert result.isna().sum() == 0

    def test_median_fills_missing_with_column_median(self):
        series = pd.Series([1, 2, None, 100])
        result = apply_imputation(series, "median")
        assert result.iloc[2] == 2.0

    def test_mode_fills_missing_with_most_frequent_value(self):
        series = pd.Series(["a", "a", "b", None])
        result = apply_imputation(series, "mode")
        assert result.iloc[3] == "a"

    def test_constant_fills_missing_with_given_value(self):
        series = pd.Series(["a", None, "c"])
        result = apply_imputation(series, "constant", constant_value="Unknown")
        assert result.iloc[1] == "Unknown"

    def test_constant_without_value_raises(self):
        series = pd.Series(["a", None])
        with pytest.raises(ValueError):
            apply_imputation(series, "constant", constant_value=None)

    def test_forward_fill_uses_previous_value(self):
        series = pd.Series([1, None, None, 4])
        result = apply_imputation(series, "forward_fill")
        assert result.iloc[1] == 1
        assert result.iloc[2] == 1

    def test_backward_fill_uses_next_value(self):
        series = pd.Series([1, None, None, 4])
        result = apply_imputation(series, "backward_fill")
        assert result.iloc[1] == 4
        assert result.iloc[2] == 4

    def test_original_series_is_not_mutated(self):
        series = pd.Series([1, 2, None, 4])
        original_missing_count = series.isna().sum()
        apply_imputation(series, "mean")
        assert series.isna().sum() == original_missing_count  # unchanged


class TestValidateStrategyForColumn:
    def test_mean_on_numeric_column_passes(self):
        series = pd.Series([1, 2, 3])
        validate_strategy_for_column(series, "mean")  # should not raise

    def test_mean_on_text_column_raises(self):
        series = pd.Series(["a", "b", "c"])
        with pytest.raises(ValueError, match="requires a numeric column"):
            validate_strategy_for_column(series, "mean")

    def test_median_on_text_column_raises(self):
        series = pd.Series(["a", "b", "c"])
        with pytest.raises(ValueError):
            validate_strategy_for_column(series, "median")

    def test_mode_on_text_column_passes(self):
        series = pd.Series(["a", "b", "c"])
        validate_strategy_for_column(series, "mode")  # should not raise


class TestImputeColumnInDataframe:
    def test_drop_rows_removes_rows_with_missing_values(self):
        df = pd.DataFrame({"a": [1, None, 3], "b": [10, 20, 30]})
        result = impute_column_in_dataframe(df, "a", "drop_rows")
        assert len(result) == 2
        assert result["a"].isna().sum() == 0

    def test_original_dataframe_is_not_mutated(self):
        df = pd.DataFrame({"a": [1, None, 3]})
        original_na_count = df["a"].isna().sum()
        impute_column_in_dataframe(df, "a", "median")
        assert df["a"].isna().sum() == original_na_count

    def test_invalid_strategy_raises_before_mutating(self):
        df = pd.DataFrame({"a": ["x", "y", None]})
        with pytest.raises(ValueError):
            impute_column_in_dataframe(df, "a", "mean")


class TestSummarizeColumn:
    def test_summarizes_numeric_column_correctly(self):
        series = pd.Series([1, 2, 3, None])
        summary = summarize_column(series)
        assert summary.mean == 2.0
        assert summary.missing_count == 1
        assert summary.row_count == 4

    def test_summarizes_text_column_with_none_stats(self):
        series = pd.Series(["a", "b", None])
        summary = summarize_column(series)
        assert summary.mean is None
        assert summary.median is None
        assert summary.missing_count == 1