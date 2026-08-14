import pandas as pd
import pytest

from app.services.pipeline_service import execute_operation, replay_pipeline


class TestExecuteOperation:
    def test_impute_operation(self):
        df = pd.DataFrame({"a": [1, 2, None, 4]})
        result = execute_operation(df, "impute", {"column": "a", "strategy": "mean", "constant_value": None})
        assert result["a"].isna().sum() == 0

    def test_drop_column_operation(self):
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        result = execute_operation(df, "drop_column", {"column": "b"})
        assert "b" not in result.columns
        assert "a" in result.columns

    def test_remove_duplicate_rows_operation(self):
        df = pd.DataFrame({"a": [1, 1, 2]})
        result = execute_operation(df, "remove_duplicate_rows", {"keep": "first"})
        assert len(result) == 2

    def test_convert_dtype_operation(self):
        df = pd.DataFrame({"a": ["1.0", "2.0", "3.0"]})
        result = execute_operation(df, "convert_dtype", {"column": "a", "target_type": "float"})
        assert pd.api.types.is_float_dtype(result["a"])

    def test_scale_operation(self):
        df = pd.DataFrame({"a": [10, 20, 30]})
        result = execute_operation(df, "scale", {"column": "a", "method": "minmax"})
        assert result["a"].min() == 0.0
        assert result["a"].max() == 1.0

    def test_unknown_operation_raises(self):
        df = pd.DataFrame({"a": [1, 2]})
        with pytest.raises(ValueError, match="Unknown operation"):
            execute_operation(df, "not_a_real_operation", {})

    def test_unknown_encoding_method_raises(self):
        df = pd.DataFrame({"a": ["x", "y"]})
        with pytest.raises(ValueError, match="Unknown encoding method"):
            execute_operation(df, "encode", {"column": "a", "method": "not_real"})


class TestReplayPipeline:
    def test_replays_single_step_correctly(self):
        original = pd.DataFrame({"a": [1, 2, None, 4]})
        steps = [{"operation": "impute", "operation_params": {"column": "a", "strategy": "median", "constant_value": None}}]
        result = replay_pipeline(original, steps)
        assert result["a"].isna().sum() == 0

    def test_replays_multiple_steps_in_order(self):
        original = pd.DataFrame({"a": [1, 2, None, 4], "b": [10, 20, 30, 40]})
        steps = [
            {"operation": "impute", "operation_params": {"column": "a", "strategy": "median", "constant_value": None}},
            {"operation": "drop_column", "operation_params": {"column": "b"}},
        ]
        result = replay_pipeline(original, steps)
        assert result["a"].isna().sum() == 0
        assert "b" not in result.columns

    def test_replay_does_not_mutate_original(self):
        original = pd.DataFrame({"a": [1, 2, None, 4]})
        original_na_count = original["a"].isna().sum()
        steps = [{"operation": "impute", "operation_params": {"column": "a", "strategy": "mean", "constant_value": None}}]
        replay_pipeline(original, steps)
        assert original["a"].isna().sum() == original_na_count

    def test_empty_steps_list_returns_unchanged_copy(self):
        original = pd.DataFrame({"a": [1, 2, 3]})
        result = replay_pipeline(original, [])
        assert result["a"].tolist() == original["a"].tolist()

    def test_skips_steps_with_none_operation(self):
        # defensive case: a malformed/legacy history entry shouldn't
        # crash the whole replay
        original = pd.DataFrame({"a": [1, 2, 3]})
        steps = [{"operation": None, "operation_params": None}]
        result = replay_pipeline(original, steps)
        assert result["a"].tolist() == original["a"].tolist()

    def test_order_matters_for_dependent_steps(self):
        # Converting to float BEFORE scaling should succeed; this test
        # documents that replay genuinely respects step order, not just
        # applying them in some arbitrary sequence.
        original = pd.DataFrame({"a": ["10", "20", "30"]})
        steps = [
            {"operation": "convert_dtype", "operation_params": {"column": "a", "target_type": "float"}},
            {"operation": "scale", "operation_params": {"column": "a", "method": "minmax"}},
        ]
        result = replay_pipeline(original, steps)
        assert result["a"].min() == 0.0
        assert result["a"].max() == 1.0