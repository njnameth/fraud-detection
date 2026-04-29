from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from features import build_model_frame
from risk_rules import label_risk, score_transaction

DATA_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_accounts():
    return pd.DataFrame({
        "account_id": [1, 2, 3],
        "customer_name": ["Alice", "Bob", "Carol"],
        "prior_chargebacks": [0, 1, 3],
    })


@pytest.fixture
def sample_transactions():
    return pd.DataFrame({
        "transaction_id": [101, 102, 103],
        "account_id": [1, 2, 3],
        "amount_usd": [50.0, 1200.0, 300.0],
        "failed_logins_24h": [0, 1, 6],
    })


# ---------------------------------------------------------------------------
# build_model_frame — join correctness
# ---------------------------------------------------------------------------

def test_model_frame_joins_account_data(sample_transactions, sample_accounts):
    df = build_model_frame(sample_transactions, sample_accounts)
    assert "customer_name" in df.columns
    assert df.loc[df["account_id"] == 1, "customer_name"].iloc[0] == "Alice"


def test_model_frame_row_count_unchanged(sample_transactions, sample_accounts):
    # A left join must not drop or duplicate transaction rows.
    df = build_model_frame(sample_transactions, sample_accounts)
    assert len(df) == len(sample_transactions)


def test_model_frame_unmatched_account_produces_nulls(sample_accounts):
    # Transactions with no matching account should not be silently dropped.
    txns = pd.DataFrame({
        "transaction_id": [999],
        "account_id": [9999],
        "amount_usd": [100.0],
        "failed_logins_24h": [0],
    })
    df = build_model_frame(txns, sample_accounts)
    assert len(df) == 1
    assert pd.isna(df.iloc[0]["customer_name"])


# ---------------------------------------------------------------------------
# build_model_frame — derived columns
# ---------------------------------------------------------------------------

def test_is_large_amount_flag(sample_transactions, sample_accounts):
    df = build_model_frame(sample_transactions, sample_accounts)
    assert df.loc[df["amount_usd"] >= 1000, "is_large_amount"].eq(1).all()
    assert df.loc[df["amount_usd"] < 1000, "is_large_amount"].eq(0).all()


def test_is_large_amount_boundary(sample_accounts):
    txns = pd.DataFrame({
        "transaction_id": [1, 2],
        "account_id": [1, 1],
        "amount_usd": [999.99, 1000.0],
        "failed_logins_24h": [0, 0],
    })
    df = build_model_frame(txns, sample_accounts)
    assert df.loc[df["amount_usd"] == 999.99, "is_large_amount"].iloc[0] == 0
    assert df.loc[df["amount_usd"] == 1000.0, "is_large_amount"].iloc[0] == 1


def test_login_pressure_categories(sample_transactions, sample_accounts):
    df = build_model_frame(sample_transactions, sample_accounts)
    pressure = df.set_index("transaction_id")["login_pressure"]
    assert str(pressure[101]) == "none"   # 0 failed logins
    assert str(pressure[102]) == "low"    # 1 failed login
    assert str(pressure[103]) == "high"   # 6 failed logins


# ---------------------------------------------------------------------------
# Known fraud detection — integration test against real data files.
# Every confirmed chargeback must score medium or high, never low.
# This directly measures whether the system would catch actual fraud losses.
# ---------------------------------------------------------------------------

def test_known_fraud_not_scored_low():
    accounts = pd.read_csv(DATA_DIR / "accounts.csv")
    transactions = pd.read_csv(DATA_DIR / "transactions.csv")
    chargebacks = pd.read_csv(DATA_DIR / "chargebacks.csv")

    model_frame = build_model_frame(transactions, accounts)
    model_frame["risk_score"] = model_frame.apply(
        lambda row: score_transaction(row.to_dict()), axis=1
    )
    model_frame["risk_label"] = model_frame["risk_score"].apply(label_risk)

    fraud_ids = set(chargebacks["transaction_id"])
    fraud_rows = model_frame[model_frame["transaction_id"].isin(fraud_ids)]

    for _, row in fraud_rows.iterrows():
        assert row["risk_label"] != "low", (
            f"Transaction {int(row['transaction_id'])} (confirmed fraud, "
            f"${row['amount_usd']:.2f}) scored '{row['risk_label']}' "
            f"(score={row['risk_score']}). Fraud is slipping through unreviewed."
        )


def test_all_chargebacks_present_in_transactions():
    # Guard against data drift — if a chargeback ID has no matching transaction,
    # the fraud detection test above would silently pass with nothing checked.
    transactions = pd.read_csv(DATA_DIR / "transactions.csv")
    chargebacks = pd.read_csv(DATA_DIR / "chargebacks.csv")

    missing = set(chargebacks["transaction_id"]) - set(transactions["transaction_id"])
    assert not missing, f"Chargeback transaction IDs not found in transactions: {missing}"


def test_low_risk_legitimate_transactions_not_over_flagged():
    # Transactions with no fraud signals should not be flagged for review.
    # Over-flagging wastes analyst time and creates friction for good customers.
    accounts = pd.read_csv(DATA_DIR / "accounts.csv")
    transactions = pd.read_csv(DATA_DIR / "transactions.csv")

    model_frame = build_model_frame(transactions, accounts)
    model_frame["risk_score"] = model_frame.apply(
        lambda row: score_transaction(row.to_dict()), axis=1
    )
    model_frame["risk_label"] = model_frame["risk_score"].apply(label_risk)

    # These specific transactions have no risk signals (domestic, low device score,
    # low amount, low velocity, no failed logins, no prior chargebacks).
    clean_ids = {50001, 50004, 50009, 50012, 50016, 50020}
    clean_rows = model_frame[model_frame["transaction_id"].isin(clean_ids)]

    for _, row in clean_rows.iterrows():
        assert row["risk_label"] == "low", (
            f"Transaction {int(row['transaction_id'])} has no risk signals but "
            f"was flagged '{row['risk_label']}' (score={row['risk_score']})."
        )
