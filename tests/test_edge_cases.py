"""Edge cases and guard rails."""

import json
import pytest
from gltest import get_contract_factory


def _deploy(admin):
    return get_contract_factory("Contract").deploy(account=admin)


def test_create_grant_requires_funding(admin, sponsor):
    c = _deploy(admin)
    with pytest.raises(Exception):
        c.connect(sponsor).create_grant(
            args=["Unfunded", "https://example.com/spec"]
        ).transact(value=0)


def test_spec_url_must_be_https(admin, sponsor):
    c = _deploy(admin)
    with pytest.raises(Exception):
        c.connect(sponsor).create_grant(
            args=["No TLS", "http://example.com/spec"]
        ).transact(value=1_000_000_000_000_000_000)


def test_only_sponsor_adds_milestone(admin, sponsor, builder):
    c = _deploy(admin)
    c.connect(sponsor).create_grant(
        args=["Grant", "https://example.com/spec"]
    ).transact(value=2_000_000_000_000_000_000)
    with pytest.raises(Exception):
        c.connect(builder).add_milestone(
            args=["1", "M", "criteria", 1_000_000_000_000_000_000]
        ).transact()


def test_milestone_cannot_exceed_vault(admin, sponsor):
    c = _deploy(admin)
    c.connect(sponsor).create_grant(
        args=["Grant", "https://example.com/spec"]
    ).transact(value=1_000_000_000_000_000_000)
    with pytest.raises(Exception):
        c.connect(sponsor).add_milestone(
            args=["1", "M", "criteria", 5_000_000_000_000_000_000]
        ).transact()


def test_submit_requires_bond_and_evidence(admin, sponsor, builder):
    c = _deploy(admin)
    c.connect(sponsor).create_grant(
        args=["Grant", "https://example.com/spec"]
    ).transact(value=2_000_000_000_000_000_000)
    c.connect(sponsor).add_milestone(
        args=["1", "M", "criteria", 1_000_000_000_000_000_000]
    ).transact()

    with pytest.raises(Exception):  # no evidence
        c.connect(builder).submit_deliverable(
            args=["1", 0, []]
        ).transact(value=100_000_000_000_000_000)

    with pytest.raises(Exception):  # bond too low
        c.connect(builder).submit_deliverable(
            args=["1", 0, ["https://example.com/pr"]]
        ).transact(value=1)


def test_seeded_released_cannot_double_release(admin, sponsor, builder):
    c = _deploy(admin)
    spo = str(getattr(sponsor, "address", sponsor))
    bld = str(getattr(builder, "address", builder))
    c.connect(admin).admin_seed_grant(
        args=[spo, "Grant", "https://example.com/spec", 3_000_000_000_000_000_000]
    ).transact(value=0)
    c.connect(admin).admin_seed_milestone(
        args=["1", "M", "criteria", 1_000_000_000_000_000_000, bld,
              ["https://example.com/pr"], "RELEASED", "APPROVED", 95, 90, "seeded"]
    ).transact()

    ms = json.loads(c.get_milestone(args=["1", 0]).call())
    assert ms["state"] == "RELEASED"
    assert ms["payout_done"] is True
    with pytest.raises(Exception):
        c.connect(admin).release(args=["1", 0]).transact()
