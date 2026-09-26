#!/usr/bin/env python3
"""Seed GrantLock with demo grants + milestones on studionet (admin pre-baked
verdicts so the live app has content without waiting on the LLM every time).

Usage:
    source ~/.genlayer/env.sh
    python3 scripts/seed_demo_data.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from genlayer_py import create_account, create_client
from genlayer_py.chains import studionet
from genlayer_py.types import TransactionStatus

ROOT = Path(__file__).resolve().parent.parent
DEP = ROOT / "deployments.json"

DOC = "https://raw.githubusercontent.com/genlayerlabs/genlayer-docs/main/README.md"


def retry(fn, tries=5, delay=3):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            if i == tries - 1:
                raise
            print(f"    [!] {str(e)[:120]} — retry in {delay}s")
            time.sleep(delay)


def main() -> int:
    key = os.environ.get("GENLAYER_PRIVATE_KEY")
    if not key:
        print("ERROR: source ~/.genlayer/env.sh first", file=sys.stderr)
        return 1
    if not DEP.exists():
        print("ERROR: deploy first (deployments.json missing)", file=sys.stderr)
        return 1

    addr = json.loads(DEP.read_text())["contracts"]["GrantLock"]["address"]
    account = create_account(key)
    client = create_client(chain=studionet, account=account)

    def addr_of(env):
        k = os.environ.get(env)
        return create_account(k).address if k and "REPLACE_ME" not in k else account.address

    sponsor1 = addr_of("GENLAYER_PRIVATE_KEY_2")
    builder1 = addr_of("GENLAYER_PRIVATE_KEY_3")
    builder2 = addr_of("GENLAYER_PRIVATE_KEY_4")

    print("=" * 55)
    print(f"Seeding GrantLock @ {addr}")
    print("=" * 55)

    grant_cnt = int(retry(lambda: client.read_contract(address=addr, function_name="get_grant_count")) or 0)

    if grant_cnt < 1:
        print("[+] Grant 1: Open-source SDK bounty (funded 6 GEN)")
        tx = retry(lambda: client.write_contract(
            address=addr, function_name="admin_seed_grant",
            args=[sponsor1, "GenLayer TypeScript SDK examples bounty", DOC, 6000000000000000000],
            account=account, value=0,
        ))
        retry(lambda: client.wait_for_transaction_receipt(tx, status=TransactionStatus.ACCEPTED, interval=3000, retries=40))

        milestones = [
            # title, criteria, amount, builder, urls, state, verdict, completeness, confidence, reason
            ("M1: Wallet-connect example",
             "A working Vite example that connects MetaMask, switches to studionet, and reads a contract view. Must include a live demo URL and a linked commit.",
             2000000000000000000, builder1, [DOC], "RELEASED", "APPROVED", 92, 88,
             "The linked commit implements MetaMask connect + wallet_switchEthereumChain and the demo loads and reads a view. Fully meets the acceptance criteria; released in full."),
            ("M2: Write-path tutorial",
             "A tutorial article plus code showing a signed write transaction and waiting for the receipt, with screenshots.",
             2000000000000000000, builder2, [DOC], "APPROVED", "PARTIAL", 63, 79,
             "The tutorial covers the write call and receipt wait, but omits the required screenshots and error handling. Substantive but incomplete → PARTIAL (50%)."),
            ("M3: End-to-end test suite",
             "A gltest suite covering happy path and at least three edge cases, runnable with `gltest --network studionet`.",
             2000000000000000000, "", [], "LOCKED", "", 0, 0, ""),
        ]
        gid = "1"
        for i, (mt, cr, amt, b, urls, st, vd, comp, conf, rs) in enumerate(milestones):
            print(f"    - milestone {i}: {st} {vd}")
            tx = retry(lambda mt=mt, cr=cr, amt=amt, b=b, urls=urls, st=st, vd=vd, comp=comp, conf=conf, rs=rs: client.write_contract(
                address=addr, function_name="admin_seed_milestone",
                args=[gid, mt, cr, amt, b, urls, st, vd, comp, conf, rs],
                account=account,
            ))
            retry(lambda: client.wait_for_transaction_receipt(tx, status=TransactionStatus.ACCEPTED, interval=3000, retries=40))

    if grant_cnt < 2:
        print("[+] Grant 2: Research report grant (funded 3 GEN)")
        tx = retry(lambda: client.write_contract(
            address=addr, function_name="admin_seed_grant",
            args=[account.address, "Optimistic-democracy consensus explainer", DOC, 3000000000000000000],
            account=account, value=0,
        ))
        retry(lambda: client.wait_for_transaction_receipt(tx, status=TransactionStatus.ACCEPTED, interval=3000, retries=40))
        tx = retry(lambda: client.write_contract(
            address=addr, function_name="admin_seed_milestone",
            args=["2", "M1: Published explainer",
                  "A published long-form article (>= 1500 words) explaining Optimistic Democracy with diagrams, publicly reachable.",
                  3000000000000000000, builder1, [DOC], "REJECTED", "REJECTED", 22, 81,
                  "The linked page is a stub of under 300 words with no diagrams and does not explain the appeal/finality mechanics required by the criteria. Rejected; builder may resubmit."],
            account=account,
        ))
        retry(lambda: client.wait_for_transaction_receipt(tx, status=TransactionStatus.ACCEPTED, interval=3000, retries=40))

    print("\n" + "=" * 55)
    print(f"SEED COMPLETE. grants={client.read_contract(address=addr, function_name='get_grant_count')}")
    print("=" * 55)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
