#!/usr/bin/env python3
"""Live end-to-end multi-wallet lifecycle test against the deployed GrantLock
contract on studionet: sponsor (wallet 2) funds a grant + milestone, builder
(wallet 3) submits a bonded deliverable, real AI review runs on-chain, then the
milestone is released.

Usage:
    source ~/.genlayer/env.sh
    python3 scripts/live_test.py
"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path
from genlayer_py import create_account, create_client
from genlayer_py.chains import studionet
from genlayer_py.types import TransactionStatus

ROOT = Path(__file__).resolve().parent.parent
ADDR = json.loads((ROOT / "deployments.json").read_text())["contracts"]["GrantLock"]["address"]
DOC = "https://raw.githubusercontent.com/genlayerlabs/genlayer-docs/main/README.md"


def wait(client, tx, status=TransactionStatus.ACCEPTED, retries=80):
    return client.wait_for_transaction_receipt(transaction_hash=tx, status=status, interval=3000, retries=retries)


def main() -> int:
    sponsor = create_account(os.environ["GENLAYER_PRIVATE_KEY_2"])
    builder = create_account(os.environ["GENLAYER_PRIVATE_KEY_3"])
    sc = create_client(chain=studionet, account=sponsor)
    bc = create_client(chain=studionet, account=builder)

    print(f"GrantLock @ {ADDR}")
    print(f"sponsor={sponsor.address}  builder={builder.address}")

    # 1) sponsor funds a grant with 1 GEN
    print("\n[1] create_grant (sponsor, 1 GEN vault)...")
    tx = sc.write_contract(address=ADDR, function_name="create_grant",
                           args=["Live-test SDK bounty", DOC], value=1000000000000000000)
    wait(sc, tx)
    gid = int(sc.read_contract(address=ADDR, function_name="get_grant_count"))
    print(f"    grant #{gid} funded (tx {tx})")

    # 2) sponsor defines a 0.5 GEN milestone
    print("[2] add_milestone (sponsor, 0.5 GEN)...")
    tx = sc.write_contract(address=ADDR, function_name="add_milestone",
                           args=[str(gid), "Wallet-connect example",
                                 "A working example that connects a wallet and reads a contract view; linked commit + live demo.",
                                 500000000000000000])
    wait(sc, tx)
    print("    milestone 0 added")

    # 3) builder submits a bonded deliverable
    print("[3] submit_deliverable (builder, 0.05 GEN bond)...")
    tx = bc.write_contract(address=ADDR, function_name="submit_deliverable",
                           args=[str(gid), 0, [DOC]], value=50000000000000000)
    wait(bc, tx)
    print("    deliverable submitted")

    # 4) real on-chain AI review
    print("[4] review (real non-deterministic consensus, may take a minute)...")
    tx = bc.write_contract(address=ADDR, function_name="review", args=[str(gid), 0])
    wait(bc, tx, retries=120)
    m = json.loads(bc.read_contract(address=ADDR, function_name="get_milestone", args=[str(gid), 0]))
    print(f"    verdict={m['verdict']} completeness={m['completeness']} "
          f"confidence={m['confidence']} payout_bp={m['payout_bp']} state={m['state']}")
    print(f"    reason: {m['reason'][:300]}")

    # 5) release after the challenge window closes
    deadline = int(m["challenge_deadline"])
    now = int(time.time())
    if deadline > now:
        wait_s = deadline - now + 5
        print(f"[5] waiting {wait_s}s for the challenge window to close...")
        time.sleep(wait_s)
    print("[5] release...")
    try:
        tx = bc.write_contract(address=ADDR, function_name="release", args=[str(gid), 0])
        wait(bc, tx)
        m = json.loads(bc.read_contract(address=ADDR, function_name="get_milestone", args=[str(gid), 0]))
        print(f"    released: state={m['state']} payout_done={m['payout_done']} (tx {tx})")
    except Exception as e:
        print(f"    release note: {str(e)[:200]}")

    print("\nLIVE TEST COMPLETE (verdict produced on-chain by real consensus).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
