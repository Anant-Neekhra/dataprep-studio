import pandas as pd

from app.rule_engine.engine import evaluate_rules, evaluate_dataset_rules
from app.rule_engine.facts import build_dataset_facts, build_facts
from app.services.dataset_service import get_effective_type
from app.services.profiling_service import profile_column


def compute_health_score(df: pd.DataFrame, overrides: dict) -> dict:
    """
    Computes a 0-100 health score by starting at 100 and subtracting
    weighted penalties for each detected issue. Deliberately simple and
    transparent (a linear penalty model, not a hidden formula) so the
    score itself is explainable — consistent with the rest of this
    project's philosophy. Returns the score plus a breakdown of what
    contributed to it, so nothing about the number is a black box.
    """
    score = 100.0
    breakdown = []

    total_cells = df.shape[0] * df.shape[1]
    missing_total = int(df.isna().sum().sum())
    missing_pct = (missing_total / total_cells) * 100 if total_cells else 0

    if missing_pct > 0:
        penalty = min(missing_pct * 0.5, 25)  # capped, so missing data alone can't zero out the score
        score -= penalty
        breakdown.append({"factor": "Missing data", "penalty": round(penalty, 1), "detail": f"{round(missing_pct, 1)}% of cells missing"})

    duplicate_pct = (df.duplicated().sum() / len(df)) * 100 if len(df) else 0
    if duplicate_pct > 0:
        penalty = min(duplicate_pct * 0.3, 15)
        score -= penalty
        breakdown.append({"factor": "Duplicate rows", "penalty": round(penalty, 1), "detail": f"{round(duplicate_pct, 1)}% duplicate rows"})

    # Gather all active recommendations, weighted by severity — this is
    # the piece that ties the score directly to the same rule engine
    # driving every other page, rather than being a separate, disconnected metric.
    all_recommendations = []
    for col in df.columns:
        _, effective_type, _ = get_effective_type(df[col], col, overrides)
        profile = profile_column(df[col], col, effective_type)
        facts = build_facts(profile, series=df[col])
        all_recommendations.extend(evaluate_rules(col, effective_type, facts))
    all_recommendations.extend(evaluate_dataset_rules(build_dataset_facts(df)))

    severity_weights = {"high": 5, "medium": 2, "low": 0.5}
    severity_counts = {"high": 0, "medium": 0, "low": 0}
    for rec in all_recommendations:
        severity_counts[rec.severity] += 1

    rec_penalty = sum(severity_counts[s] * severity_weights[s] for s in severity_weights)
    rec_penalty = min(rec_penalty, 40)
    if rec_penalty > 0:
        score -= rec_penalty
        breakdown.append({
            "factor": "Active recommendations",
            "penalty": round(rec_penalty, 1),
            "detail": f"{severity_counts['high']} high, {severity_counts['medium']} medium, {severity_counts['low']} low severity",
        })

    score = max(0, round(score, 1))

    return {
        "score": score,
        "breakdown": breakdown,
        "total_recommendations": len(all_recommendations),
        "high_severity_count": severity_counts["high"],
    }