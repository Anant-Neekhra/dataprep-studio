from pathlib import Path

import yaml
from simpleeval import simple_eval

from app.schemas import Recommendation, LearningContent

KNOWLEDGE_BASE_DIR = Path(__file__).parent.parent / "knowledge_base"


def load_rules() -> list[dict]:
    """
    Loads every .yaml file in the knowledge_base folder and combines them
    into one flat list of rule dicts. This runs once at startup — rules
    aren't hot-reloaded mid-request, so adding a new YAML file requires
    restarting the server (fine for now; --reload picks it up anyway
    since it's triggered by file changes in the backend folder).
    """
    all_rules = []
    for yaml_file in KNOWLEDGE_BASE_DIR.glob("*.yaml"):
        with open(yaml_file, "r") as f:
            rules = yaml.safe_load(f)
            if rules:
                all_rules.extend(rules)
    return all_rules


# Loaded once when this module is first imported.
RULES = load_rules()


def evaluate_rules(column: str, effective_type: str, facts: dict) -> list[Recommendation]:
    """
    Checks every loaded rule against one column's facts. A rule matches
    if its applies_to matches the column's effective_type AND its
    condition expression evaluates to True against the facts dict.

    simple_eval is used instead of Python's eval() — it can only evaluate
    expressions (comparisons, and/or, arithmetic) against the names we
    explicitly hand it, with no access to imports, file I/O, or arbitrary
    function calls. A malformed or malicious condition string can't do
    anything beyond return True/False or raise an error.
    """
    matched = []

    for rule in RULES:
        if rule["applies_to"] == "dataset":
            continue
        if rule["applies_to"] != effective_type and rule["applies_to"] != "any":
            continue

        try:
            condition_result = simple_eval(rule["condition"], names=facts)
        except Exception:
            # A rule whose condition references a fact that doesn't exist
            # for this column type (e.g. "skewness" on a categorical
            # column) simply doesn't match, rather than crashing the
            # whole recommendation pass for one column.
            continue

        if condition_result:
            matched.append(
                Recommendation(
                    rule_id=rule["id"],
                    category=rule["category"],
                    severity=rule["severity"],
                    column=column,
                    recommendation=rule["recommendation"],
                    reason=rule["reason"],
                    advantages=rule.get("advantages", []),
                    disadvantages=rule.get("disadvantages", []),
                    alternatives=rule.get("alternatives", []),
                    docs_url=rule.get("docs_url"),
                    learning_content=LearningContent(**rule["learning_content"]) if rule.get("learning_content") else None,
                )
            )

    return matched

def evaluate_dataset_rules(facts: dict) -> list[Recommendation]:
    """
    Same matching logic as evaluate_rules, but for rules scoped to the
    whole dataset (applies_to: dataset) rather than a single column —
    e.g. duplicate rows/columns, where no one column is responsible.
    The "column" field is set to a sentinel string since these
    recommendations aren't about any specific column.
    """
    matched = []

    for rule in RULES:
        if rule["applies_to"] != "dataset":
            continue

        try:
            condition_result = simple_eval(rule["condition"], names=facts)
        except Exception:
            continue

        if condition_result:
            matched.append(
                Recommendation(
                    rule_id=rule["id"],
                    category=rule["category"],
                    severity=rule["severity"],
                    column="(entire dataset)",
                    recommendation=rule["recommendation"],
                    reason=rule["reason"],
                    advantages=rule.get("advantages", []),
                    disadvantages=rule.get("disadvantages", []),
                    alternatives=rule.get("alternatives", []),
                    docs_url=rule.get("docs_url"),
                    learning_content=LearningContent(**rule["learning_content"]) if rule.get("learning_content") else None,
                )
            )

    return matched