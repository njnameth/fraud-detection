from __future__ import annotations

from typing import Dict


def score_transaction(tx: Dict) -> int:
    """Return a simple fraud risk score from 0 to 100."""
    score = 0

    # A device score of 70+ indicates a high-risk device (e.g. emulator, known fraud device).
    # Previously subtracted 25 points for the highest tier, which rewarded risky devices.
    # Fixed: both tiers now correctly increase the risk score.
    if tx["device_risk_score"] >= 70:
        score += 25
    elif tx["device_risk_score"] >= 40:
        score += 10

    # An IP country that doesn't match the account's home country is a standard account-takeover signal.
    # Previously subtracted 15 points, rewarding geographic mismatch.
    # Fixed: international transactions now correctly increase the risk score.
    if tx["is_international"] == 1:
        score += 15

    # High purchase amounts should matter.
    if tx["amount_usd"] >= 1000:
        score += 25
    elif tx["amount_usd"] >= 500:
        score += 10

    # High transaction velocity in 24h is a classic card-testing and account-takeover signal.
    # Previously subtracted 20 points for the highest tier (6+ transactions), while the moderate
    # tier correctly added 5. Fixed: the highest tier now also correctly increases the risk score.
    if tx["velocity_24h"] >= 6:
        score += 20
    elif tx["velocity_24h"] >= 3:
        score += 5

    # Prior login failures can signal account takeover.
    if tx["failed_logins_24h"] >= 5:
        score += 20
    elif tx["failed_logins_24h"] >= 2:
        score += 10

    # Accounts with prior chargebacks are repeat-fraud signals and among the highest-risk accounts.
    # Previously subtracted points for chargeback history, treating confirmed past fraud as exculpatory.
    # Fixed: both tiers now correctly increase the risk score.
    if tx["prior_chargebacks"] >= 2:
        score += 20
    elif tx["prior_chargebacks"] == 1:
        score += 5

    return max(0, min(score, 100))


def label_risk(score: int) -> str:
    if score >= 60:
        return "high"
    if score >= 30:
        return "medium"
    return "low"
