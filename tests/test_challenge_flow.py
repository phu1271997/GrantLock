"""Challenge flow: a rejection is disputed by the builder, re-reviewed, finalized."""

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
                    "confidence": confidence, "reason": "mock"})},
                "web_mocks": {".*": {"status": 200, "body": "mock artifact"}},
            },
        )
    except Exception:
        pass


def test_rejected_then_builder_challenges_then_rereviewed(admin, sponsor, builder):
    c = get_contract_factory("Contract").deploy(account=admin)
    c.connect(sponsor).create_grant(
        args=["Grant", "https://example.com/spec"]
    ).transact(value=3_000_000_000_000_000_000)
    c.connect(sponsor).add_milestone(
        args=["1", "M", "criteria", 2_000_000_000_000_000_000]
    ).transact()
    c.connect(builder).submit_deliverable(
        args=["1", 0, ["https://example.com/pr"]]
    ).transact(value=100_000_000_000_000_000)

    # First review REJECTED
    _mocks(admin, "REJECTED", 20, 82)
    c.connect(builder).review(args=["1", 0]).transact()
    ms = json.loads(c.get_milestone(args=["1", 0]).call())
    assert ms["verdict"] == "REJECTED"
    assert ms["state"] == "REJECTED"

    # Builder challenges the rejection
    c.connect(builder).challenge(
        args=["1", 0, "https://example.com/rebuttal", "The demo was live, you fetched a cached error page"]
    ).transact(value=100_000_000_000_000_000)
    ms = json.loads(c.get_milestone(args=["1", 0]).call())
    assert ms["state"] == "CHALLENGED"

    # Re-review flips to APPROVED and releases (final)
    _mocks(admin, "APPROVED", 90, 86)
    c.connect(admin).rereview(args=["1", 0]).transact()
    ms = json.loads(c.get_milestone(args=["1", 0]).call())
    assert ms["verdict"] == "APPROVED"
    assert ms["state"] == "RELEASED"
    assert ms["payout_done"] is True


def test_sponsor_cannot_challenge_a_rejection(admin, sponsor, builder):
    c = get_contract_factory("Contract").deploy(account=admin)
    c.connect(sponsor).create_grant(
        args=["Grant", "https://example.com/spec"]
    ).transact(value=3_000_000_000_000_000_000)
    c.connect(sponsor).add_milestone(
        args=["1", "M", "criteria", 2_000_000_000_000_000_000]
    ).transact()
    c.connect(builder).submit_deliverable(
        args=["1", 0, ["https://example.com/pr"]]
    ).transact(value=100_000_000_000_000_000)

    _mocks(admin, "REJECTED", 20, 82)
    c.connect(builder).review(args=["1", 0]).transact()

    # only the builder may challenge a rejection
    with pytest.raises(Exception):
        c.connect(sponsor).challenge(
            args=["1", 0, "https://example.com/x", "no"]
        ).transact(value=100_000_000_000_000_000)
