# Fraud Detection Code Review — Session Recap

**Date:** April 29, 2026
**Prepared for:** Business Leadership
**Project:** NimbusPay Fraud Detection

---

## Background

NimbusPay's fraud detection system scores every payment transaction on a scale of 0–100 and labels it low, medium, or high risk. Transactions flagged as medium or high are queued for review; low-risk transactions pass through automatically. This session was a structured review of the Python code behind that scoring system.

---

## What We Found

The scoring logic contained **four bugs where the signs were reversed** — meaning signals that should have *increased* a fraud score were instead *decreasing* it. The system was actively rewarding the most dangerous-looking transactions with lower risk scores.

All four bugs existed in the same file (`risk_rules.py`) and had been silently producing incorrect results.

### Bug 1 — High-Risk Devices Were Treated as Safe

NimbusPay uses a third-party device fingerprinting service that assigns each transaction a device risk score. A score of 70 or above flags the device as highly suspicious (known fraud device, emulator, or stolen hardware).

**The bug:** A device score of 70+ *subtracted* 25 points from the fraud score. The most dangerous devices were being marked safer than moderate-risk ones.

### Bug 2 — International Transactions Were Treated as Safe

When the IP address of a transaction doesn't match the account holder's home country, that mismatch is a well-established fraud signal — often indicating an account takeover by someone operating from abroad.

**The bug:** An international IP mismatch *subtracted* 15 points from the fraud score. Every transaction where this red flag appeared received a discount on its risk level.

### Bug 3 — High Transaction Velocity Was Treated as Safe

Fraudsters who gain access to an account typically move fast — making many transactions in a short window before the account is locked. Six or more transactions in 24 hours is a classic card-testing and account-takeover pattern.

**The bug:** Six or more transactions in 24 hours *subtracted* 20 points. Moderate velocity (3–5 transactions) correctly added 5 points, but the most extreme tier did the opposite.

### Bug 4 — Prior Chargeback History Was Treated as Exculpatory

Accounts with a history of chargebacks — meaning confirmed prior fraud — are among the highest-risk accounts in any portfolio. This history should raise immediate suspicion on any new transaction.

**The bug:** One prior chargeback *subtracted* 5 points. Two or more prior chargebacks *subtracted* 20 points. Past confirmed fraud was being used as evidence of trustworthiness.

---

## Business Impact

The dataset included **8 transactions confirmed as fraud** via chargebacks, representing **$4,854.98 in losses**. We manually traced what score each of these received under the broken rules.

Every single one scored **0 out of 100 — the lowest possible risk rating.**

The reason is that all 8 confirmed fraud transactions shared the same profile: high device risk, international IP, high velocity, and prior chargeback history. Each of those signals was subtracting points rather than adding them, causing the scores to collapse to zero before the amount or login failure signals could compensate.

Under the broken system, these transactions would have passed through automatically without any analyst review.

The two signals that were working correctly — high transaction amounts and failed login attempts — were not enough on their own to surface these transactions. The four broken signals were cancelling them out.

---

## What Was Fixed

All four bugs were corrected by flipping the sign on the affected rules. Each fix was documented in the code with an explanation of the original error and the correction. The changes are minimal and targeted — no other logic was altered.

| Signal | Before | After |
|---|---|---|
| Device risk score ≥ 70 | −25 points | +25 points |
| International IP mismatch | −15 points | +15 points |
| Velocity ≥ 6 transactions / 24h | −20 points | +20 points |
| Prior chargebacks ≥ 2 | −20 points | +20 points |
| Prior chargebacks = 1 | −5 points | +5 points |

After the fix, all 8 confirmed fraud transactions now score **medium or high** and would be routed for analyst review before passing through.

---

## What Was Built to Prevent Recurrence

A suite of **22 automated tests** was written and committed alongside the fixes. These tests run automatically and will catch any future regressions before they reach production.

The tests are organized in three groups:

**Signal direction tests** — One test per risk signal, confirming that each factor moves the score in the correct direction. These are the tests that would have caught all four bugs before they were deployed.

**Pipeline integrity tests** — Tests that load the real transaction and account data, run the full scoring pipeline end-to-end, and assert that every confirmed chargeback scores medium or high. If a future code change causes fraud to slip through, this test will fail immediately.

**False positive tests** — Tests that confirm clean, low-risk transactions are not being incorrectly flagged. Over-flagging good customers wastes analyst time and creates unnecessary friction for legitimate transactions.

---

## What Remains to Monitor

**Risk label thresholds** — The boundaries between low, medium, and high (currently 30 and 60 out of 100) were calibrated against the broken scoring function. Now that scores are higher for risky transactions, leadership should review whether the analyst review queue volume has changed and whether the thresholds need adjustment.

**Small-dollar fraud** — The current scoring gives no additional weight to transactions under $500. Two of the confirmed chargebacks were under $150. Fraudsters commonly test stolen cards with small amounts before attempting larger ones. A future enhancement could flag small amounts in high-risk merchant categories (gift cards, crypto, gaming) more aggressively.

**Data path issue** — A separate, pre-existing bug was noted in the main reporting script: it looks for data files in a folder that does not exist. This does not affect transaction scoring or the automated tests, but it does prevent the summary report from running. This should be addressed in a follow-up session.

---

## Summary

Four inverted logic bugs in the fraud scoring system were causing every confirmed fraud transaction in the dataset to receive the lowest possible risk score. The fixes were straightforward sign corrections, each documented in the code. An automated test suite was added to ensure the same class of error cannot go undetected in the future. Total fraud exposure in the reviewed dataset was $4,854.98 across 8 transactions, all of which are now correctly flagged for review.
