from risk_rules import label_risk, score_transaction

# ---------------------------------------------------------------------------
# Base transaction: a clean, low-risk profile used as a control for signal
# isolation tests. Each signal test changes exactly one field at a time.
# ---------------------------------------------------------------------------
BASE_TX = {
    "device_risk_score": 5,
    "is_international": 0,
    "amount_usd": 50,
    "velocity_24h": 1,
    "failed_logins_24h": 0,
    "prior_chargebacks": 0,
}


def _tx(**overrides):
    return {**BASE_TX, **overrides}


# ---------------------------------------------------------------------------
# label_risk thresholds
# ---------------------------------------------------------------------------

def test_label_risk_thresholds():
    assert label_risk(10) == "low"
    assert label_risk(35) == "medium"
    assert label_risk(75) == "high"


def test_label_risk_exact_boundaries():
    # Values exactly at the boundary belong to the higher tier.
    assert label_risk(30) == "medium"
    assert label_risk(60) == "high"
    assert label_risk(29) == "low"
    assert label_risk(59) == "medium"


# ---------------------------------------------------------------------------
# Clean transaction scores low
# A transaction with no risk signals should never be flagged for review.
# False positives waste analyst time and frustrate good customers.
# ---------------------------------------------------------------------------

def test_clean_transaction_scores_low():
    assert label_risk(score_transaction(BASE_TX)) == "low"


# ---------------------------------------------------------------------------
# Signal direction — each risk factor tested in isolation.
# These tests would have caught all four bugs fixed in the scoring logic.
# ---------------------------------------------------------------------------

def test_high_device_risk_increases_score():
    low_device = _tx(device_risk_score=5)
    mid_device = _tx(device_risk_score=50)
    high_device = _tx(device_risk_score=80)
    assert score_transaction(high_device) > score_transaction(mid_device)
    assert score_transaction(mid_device) > score_transaction(low_device)


def test_international_transaction_increases_score():
    domestic = _tx(is_international=0)
    international = _tx(is_international=1)
    assert score_transaction(international) > score_transaction(domestic)


def test_large_amount_adds_risk():
    small = _tx(amount_usd=100)
    medium = _tx(amount_usd=600)
    large = _tx(amount_usd=1200)
    assert score_transaction(large) > score_transaction(medium)
    assert score_transaction(medium) > score_transaction(small)


def test_high_velocity_increases_score():
    low_vel = _tx(velocity_24h=1)
    mid_vel = _tx(velocity_24h=4)
    high_vel = _tx(velocity_24h=8)
    assert score_transaction(high_vel) > score_transaction(mid_vel)
    assert score_transaction(mid_vel) > score_transaction(low_vel)


def test_failed_logins_increase_score():
    no_failures = _tx(failed_logins_24h=0)
    some_failures = _tx(failed_logins_24h=3)
    many_failures = _tx(failed_logins_24h=6)
    assert score_transaction(many_failures) > score_transaction(some_failures)
    assert score_transaction(some_failures) > score_transaction(no_failures)


def test_prior_chargebacks_increase_score():
    no_cb = _tx(prior_chargebacks=0)
    one_cb = _tx(prior_chargebacks=1)
    two_plus_cb = _tx(prior_chargebacks=3)
    assert score_transaction(two_plus_cb) > score_transaction(one_cb)
    assert score_transaction(one_cb) > score_transaction(no_cb)


# ---------------------------------------------------------------------------
# Score compounding — multiple simultaneous signals should stack.
# A transaction with several risk factors must outscore any single factor.
# ---------------------------------------------------------------------------

def test_multiple_risk_factors_compound():
    single_risk = _tx(device_risk_score=80)
    all_risks = _tx(
        device_risk_score=80,
        is_international=1,
        velocity_24h=8,
        failed_logins_24h=6,
        prior_chargebacks=2,
    )
    assert score_transaction(all_risks) > score_transaction(single_risk)


def test_high_risk_transaction_labeled_high():
    tx = _tx(
        device_risk_score=80,
        is_international=1,
        amount_usd=1500,
        velocity_24h=8,
        failed_logins_24h=6,
        prior_chargebacks=2,
    )
    assert label_risk(score_transaction(tx)) == "high"


# ---------------------------------------------------------------------------
# Score clamping — score must always stay within [0, 100].
# ---------------------------------------------------------------------------

def test_score_never_exceeds_100():
    tx = _tx(
        device_risk_score=99,
        is_international=1,
        amount_usd=9999,
        velocity_24h=100,
        failed_logins_24h=99,
        prior_chargebacks=99,
    )
    assert score_transaction(tx) <= 100


def test_score_never_below_zero():
    # Even a fully clean transaction should not produce a negative score.
    assert score_transaction(BASE_TX) >= 0
