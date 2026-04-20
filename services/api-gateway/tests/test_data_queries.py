"""Tests for data_queries pure computation helpers."""
import pytest
from api_gateway.data_queries import (
    _infer_outcome,
    _compute_calibration,
    _compute_brier_timeline,
    _compute_per_source,
)
from datetime import datetime, timezone


# ── _infer_outcome ──────────────────────────────────────────────────────────

def test_infer_outcome_yes():
    # prob=0.3, outcome=YES: brier = (0.3 - 1)^2 = 0.49
    assert _infer_outcome(0.3, 0.49) == 1

def test_infer_outcome_no():
    # prob=0.3, outcome=NO: brier = (0.3 - 0)^2 = 0.09
    assert _infer_outcome(0.3, 0.09) == 0

def test_infer_outcome_high_prob_yes():
    # prob=0.9, outcome=YES: brier = (0.9 - 1)^2 = 0.01
    assert _infer_outcome(0.9, 0.01) == 1

def test_infer_outcome_high_prob_no():
    # prob=0.9, outcome=NO: brier = (0.9 - 0)^2 = 0.81
    assert _infer_outcome(0.9, 0.81) == 0


# ── _compute_calibration ────────────────────────────────────────────────────

class _FakePred:
    def __init__(self, probability, brier_score):
        self.probability = probability
        self.brier_score = brier_score
        self.is_resolved = True
        self.source = 'kalshi'
        self.resolved_at = datetime(2026, 1, 15, tzinfo=timezone.utc)


def test_compute_calibration_empty():
    result = _compute_calibration([])
    assert len(result) == 10
    assert all(b['count'] == 0 for b in result)
    assert all(b['actual'] is None for b in result)
    # bins are 0.05, 0.15, ..., 0.95
    assert [b['bin'] for b in result] == [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95]

def test_compute_calibration_single_yes():
    # prob=0.7, outcome=YES: brier = (0.7 - 1)^2 = 0.09
    # bin index = int(0.7 * 10) = 7 → midpoint 0.75
    pred = _FakePred(0.7, 0.09)
    result = _compute_calibration([pred])
    bin_7 = result[7]
    assert bin_7['count'] == 1
    assert bin_7['actual'] == 1.0

def test_compute_calibration_single_no():
    # prob=0.3, outcome=NO: brier = (0.3)^2 = 0.09
    # bin index = int(0.3 * 10) = 3 → midpoint 0.35
    pred = _FakePred(0.3, 0.09)
    result = _compute_calibration([pred])
    bin_3 = result[3]
    assert bin_3['count'] == 1
    assert bin_3['actual'] == 0.0

def test_compute_calibration_bin_predicted_equals_midpoint():
    pred = _FakePred(0.5, 0.25)  # prob=0.5, outcome=NO: (0.5)^2=0.25
    result = _compute_calibration([pred])
    for b in result:
        assert b['predicted'] == b['bin']


# ── _compute_brier_timeline ─────────────────────────────────────────────────

def test_compute_brier_timeline_empty():
    assert _compute_brier_timeline([]) == []

def test_compute_brier_timeline_single_month():
    pred = _FakePred(0.7, 0.09)
    result = _compute_brier_timeline([pred])
    assert result == [{'date': '2026-01', 'score': 0.09}]

def test_compute_brier_timeline_groups_by_month():
    p1 = _FakePred(0.7, 0.10)
    p1.resolved_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    p2 = _FakePred(0.8, 0.20)
    p2.resolved_at = datetime(2026, 1, 15, tzinfo=timezone.utc)
    p3 = _FakePred(0.6, 0.30)
    p3.resolved_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
    result = _compute_brier_timeline([p1, p2, p3])
    assert len(result) == 2
    assert result[0]['date'] == '2026-01'
    assert abs(result[0]['score'] - 0.15) < 0.001  # mean(0.10, 0.20)
    assert result[1] == {'date': '2026-02', 'score': 0.3}

def test_compute_brier_timeline_ordered_ascending():
    p_feb = _FakePred(0.5, 0.25)
    p_feb.resolved_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
    p_jan = _FakePred(0.5, 0.25)
    p_jan.resolved_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = _compute_brier_timeline([p_feb, p_jan])
    assert result[0]['date'] == '2026-01'
    assert result[1]['date'] == '2026-02'


# ── _compute_per_source ─────────────────────────────────────────────────────

def test_compute_per_source_empty():
    assert _compute_per_source([]) == {}

def test_compute_per_source_groups_by_source():
    p1 = _FakePred(0.7, 0.10)
    p1.source = 'kalshi'
    p2 = _FakePred(0.6, 0.20)
    p2.source = 'kalshi'
    p3 = _FakePred(0.5, 0.30)
    p3.source = 'manifold'
    result = _compute_per_source([p1, p2, p3])
    assert abs(result['kalshi'] - 0.15) < 0.001  # mean(0.10, 0.20)
    assert result['manifold'] == 0.3
