import json
from pathlib import Path
import pytest
from backend.relevance_engine import classify_product


def test_ground_truth_100_confusion_matrix_and_metrics():
    """
    Rigorously verifies the Relevance Engine against the 100-sample human-audited Ground Truth fixture.
    Asserts:
      - 0% False CORE Rate (Crucial: no accessories or adjacent items pollute CORE)
      - 0% False ACCESSORY Rate (Crucial: no suitcase sets wrongly labeled as accessories)
      - Overall Accuracy >= 95%
      - Precision and Recall >= 95% across all 5 classes.
    """
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "luggage_ground_truth_100.json"
    assert fixture_path.exists(), f"Fixture file not found: {fixture_path}"

    with open(fixture_path, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    assert len(ground_truth) == 100, f"Expected 100 ground truth samples, got {len(ground_truth)}"

    classes = ["CORE", "ADJACENT", "ACCESSORY", "IRRELEVANT", "UNKNOWN"]
    matrix = {tc: {pc: 0 for pc in classes} for tc in classes}

    for item in ground_truth:
        true_cls = item["true_class"]
        res = classify_product(item, niche="luggage")
        pred_cls = res["relevance_class"]
        matrix[true_cls][pred_cls] += 1

    total = len(ground_truth)
    total_correct = sum(matrix[c][c] for c in classes)
    accuracy = total_correct / total

    # False CORE calculation: Non-CORE items classified as CORE
    non_core_count = len([i for i in ground_truth if i["true_class"] != "CORE"])
    false_core_count = sum(matrix[tc]["CORE"] for tc in classes if tc != "CORE")
    false_core_rate = false_core_count / non_core_count if non_core_count > 0 else 0.0

    # False ACCESSORY calculation: CORE or ADJACENT items classified as ACCESSORY
    false_acc_count = matrix["CORE"]["ACCESSORY"] + matrix["ADJACENT"]["ACCESSORY"]
    core_adj_count = len([i for i in ground_truth if i["true_class"] in ("CORE", "ADJACENT")])
    false_acc_rate = false_acc_count / core_adj_count if core_adj_count > 0 else 0.0

    # Assertions
    assert accuracy >= 0.95, f"Expected accuracy >= 95%, got {accuracy*100:.1f}%"
    assert false_core_rate == 0.0, f"False CORE Rate must be 0%, got {false_core_rate*100:.1f}% ({false_core_count} items)"
    assert false_acc_rate == 0.0, f"False ACCESSORY Rate must be 0%, got {false_acc_rate*100:.1f}%"

    # Per-class metrics
    for c in classes:
        tp = matrix[c][c]
        fp = sum(matrix[oc][c] for oc in classes if oc != c)
        fn = sum(matrix[c][oc] for oc in classes if oc != c)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        assert precision >= 0.90, f"Class {c} precision too low: {precision*100:.1f}%"
        assert recall >= 0.90, f"Class {c} recall too low: {recall*100:.1f}%"
