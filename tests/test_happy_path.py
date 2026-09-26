"""Happy path: fund a grant, add a milestone, submit, review (APPROVED), release."""

import json
import pytest
from gltest import get_contract_factory
from genlayer_py import create_client
from genlayer_py.chains import studionet


def _mocks(admin, verdict, completeness, confidence):
    client = create_client(chain=studionet, account=admin)
    try:
        client.provider.make_request(
            method="sim_installMocks",
            params={
                "llm_mocks": {".*": json.dumps({
                    "verdict": verdict, "completeness": completeness,
                    "confidence": confidence,
                    "reason": "Mock review: the deliverable meets the acceptance criteria per the fetched artifacts."})},
                "web_mocks": {".*": {"status": 200, "body": "Repo README + live demo: implements MetaMask connect and reads a view. Criteria satisfied."}},
            },
        )
    except Exception:
        pass


def test_fund_add_submit_review_release(admin, sponsor, builder):
    c = get_contract_factory("Contract").deploy(account=admin)

    # Sponsor funds a 3 GEN grant
    c.connect(sponsor).create_grant(
        args=["SDK examples bounty", "https://example.com/spec"]
    ).transact(value=3_000_000_000_000_000_000)
    assert c.get_grant_count().call() == 1

    # Sponsor adds a 1 GEN milestone
    c.connect(sponsor).add_milestone(
        args=["1", "Wallet connect example", "Working demo + linked commit", 1_000_000_000_000_000_000]
    ).transact()

    grant = json.loads(c.get_grant(args=["1"]).call())
    assert grant["milestone_count"] == 1
    assert grant["milestones"][0]["state"] == "LOCKED"

    # Builder submits a bonded deliverable
    c.connect(builder).submit_deliverable(
        args=["1", 0, ["https://example.com/pr", "https://example.com/demo"]]
    ).transact(value=100_000_000_000_000_000)
    ms = json.loads(c.get_milestone(args=["1", 0]).call())
    assert ms["state"] == "CLAIMED"
    assert len(ms["evidence_urls"]) == 2

    # AI review -> APPROVED
    _mocks(admin, "APPROVED", 92, 88)
    c.connect(builder).review(args=["1", 0]).transact()
    ms = json.loads(c.get_milestone(args=["1", 0]).call())
    assert ms["verdict"] == "APPROVED"
    assert ms["payout_bp"] == 10000
    assert ms["state"] == "APPROVED"
    assert ms["confidence"] >= 60


def test_partial_verdict_sets_half_payout(admin, sponsor, builder):
    c = get_contract_factory("Contract").deploy(account=admin)
    c.connect(sponsor).create_grant(
        args=["Docs grant", "https://example.com/spec"]
    ).transact(value=2_000_000_000_000_000_000)
    c.connect(sponsor).add_milestone(
        args=["1", "Tutorial", "Article + code + screenshots", 2_000_000_000_000_000_000]
    ).transact()
    c.connect(builder).submit_deliverable(
        args=["1", 0, ["https://example.com/article"]]
    ).transact(value=100_000_000_000_000_000)

    _mocks(admin, "PARTIAL", 63, 80)
    c.connect(builder).review(args=["1", 0]).transact()
    ms = json.loads(c.get_milestone(args=["1", 0]).call())
    assert ms["verdict"] == "PARTIAL"
    assert ms["payout_bp"] == 5000
    assert ms["state"] == "APPROVED"
