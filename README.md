# 🔐 GrantLock — Autonomous Milestone Escrow on GenLayer

**GrantLock decides whether a grant deliverable is actually done.** A sponsor escrows
funds against milestones, each with a pinned acceptance spec. When a builder submits a
deliverable, whether the funds release is **not** the sponsor's call — it is decided by
**GenLayer validator consensus**, which reads the pinned acceptance criteria *and* the
builder's actual artifacts (a GitHub PR/commit, a live demo, a published article)
**directly on-chain** and judges whether the criteria are genuinely met.

> **One-line pitch:** *GrantLock dies without GenLayer — judging whether a deliverable
> "implements feature X" or "adequately documents the API" means reading real artifacts on
> the web and forming a qualitative opinion on-chain, which no Solidity contract can do.*

- **Network:** GenLayer **studionet** (chain id `61999`) — deployed via `genlayer-py`.
- **Contract (studionet):** `0x82602Bcd45e359059FE7354d4143a8E5e9db1474`
  · [View on Explorer](https://genlayer-explorer.vercel.app/address/0x82602Bcd45e359059FE7354d4143a8E5e9db1474)
- **Live dApp:** see the deployment URL in this repo's About / release notes.

---

## Why this needs GenLayer (Axis 1 — GenLayer Fit)

Strip out the AI + web-reading and you are left with a sponsor manually approving payouts —
the exact trust bottleneck GrantLock removes. The core decision is **subjective**, has
**real money staked**, and depends on **live web artifacts**:

1. **On-chain web reading** — the contract runs `gl.nondet.web.get` / `web.render` to fetch
   the pinned acceptance spec **and** each deliverable artifact. No oracle.
2. **Subjective judgment** — an LLM reviewer decides whether the artifacts *implement* the
   criteria (not merely mention them) and scores completeness `0–100`
   → `APPROVED / PARTIAL / REJECTED`.
3. **Money at stake** — the escrowed vault, a builder submission bond, and challenge bonds,
   all paid out by the contract.

## Contract design (Axis 2 — Contract Quality)

`contracts/grantlock.py` — a single `gl.Contract` managing a funded vault, milestones, and
a full review lifecycle:

```
LOCKED ─submit─▶ CLAIMED ─review─▶ APPROVED / REJECTED ─challenge─▶ CHALLENGED ─rereview─▶ RELEASED
                                     └────────────── release (after window) ────────────▶ RELEASED
```

**Semantic consensus, not schema consensus.** The non-deterministic block returns a JSON
verdict; the custom `validator_fn` (via `gl.vm.run_nondet`) compares the **meaning**:

```python
if str(mine["verdict"]) != str(leader["verdict"]):              return False  # verdict must agree
if _tier(mine["completeness"]) != _tier(leader["completeness"]):return False  # payout bracket must agree
if (mine_conf >= FLOOR) != (leader_conf >= FLOOR):              return False  # finality threshold
if abs(mine_conf - leader_conf) > 15:                           return False  # confidence proximity
```

The completeness *tier* (`FULL ≥85` / `PARTIAL 40–84` / `FAIL <40`) selects the payout
bracket (`100% / 50% / 0%`), so validators must agree on the tier, not the exact number or
the wording. Two validators that disagree on the outcome cannot reach consensus.

**Advanced non-determinism (Axis 2 → 5):** multi-source cross-check — each review fetches
the acceptance spec plus up to three artifact URLs, and a **bonded challenge + final
re-review** appeal flow lets the sponsor dispute an approval and the builder dispute a
rejection (a rebuttal URL is read on-chain during re-review).

**Edge cases handled** (each raises `gl.vm.UserError`): unfunded grant, non-`https` spec
URL, non-sponsor adding milestones, milestone amount exceeding unallocated vault, missing
bond/evidence, double-release, releasing inside an open window, and wrong-party challenge.
A `REJECTED` milestone **reopens to `LOCKED`** (builder bond forfeited to the sponsor) so a
new attempt can be made.

**Storage safety** (per the GenLayer field rules): `bigint` for money, sized ints for
bounded values, all `TreeMap` keys are `str`, custom structs are `@allow_storage @dataclass`,
and evidence is stored as a joined string rather than mutating a stored `DynArray`.

## Architecture

```
contracts/grantlock.py     # the Intelligent Contract
tests/                     # gltest suite (happy path, edge cases, challenge flow)
scripts/deploy_studionet.py
scripts/seed_demo_data.py  # admin-seeded demo grants + milestones
scripts/live_test.py       # real multi-wallet end-to-end lifecycle
frontend/                  # Vite + React + Tailwind dApp (genlayer-js)
```

The frontend calls the deployed contract for real: MetaMask signs writes, reads go through
`genlayer-js`, the AI `reason` + completeness + confidence are shown for every verdict, and
each pending consensus tx links to the Explorer.

## Deploy to studionet

```bash
source ~/.genlayer/env.sh
python3 scripts/deploy_studionet.py  # deploys, writes deployments.json + frontend/.env
python3 scripts/seed_demo_data.py    # optional: seed demo grants/milestones
```

## Run the frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
npm run build
```

Connect a MetaMask wallet **already funded on studionet** (fund it from GenLayer Studio →
Accounts panel — never the testnet faucet).

## Tests

```bash
source ~/.genlayer/env.sh
gltest --network studionet
```

`tests/` installs LLM/web mocks before non-deterministic transactions and covers the happy
path (including the `PARTIAL` 50% payout), guard rails, and the challenge → re-review flow.

## Verified live

`scripts/live_test.py` was run against studionet with two funded wallets: the sponsor
(wallet 2) funded a grant and defined a milestone, the builder (wallet 3) submitted a bonded
deliverable, **real on-chain AI consensus** produced a verdict + reason, and the milestone
resolved end to end — no mocks.
