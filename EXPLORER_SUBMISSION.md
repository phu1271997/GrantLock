# GENLAYER PROJECT EXPLORER — SUBMISSION DRAFT
**Project:** GrantLock · **Prepared:** 2026-09-26 · **Status: READY (Preview)**

> Paste each field below into the matching Portal Explorer form field. English, within the verified character caps. Logo is the only TO-BE-PROVIDED item.

---

## Section 01 — IDENTITY

### Project name
```
GrantLock
```

### Primary category
```
Dispute Resolution
```
Why: releasing escrowed funds hinges on an adjudicated verdict over whether a deliverable meets its criteria, with a sponsor/builder challenge and independent re-review — GenLayer's "adjudication layer" fit. Not `AI & Agents` (too generic to stand out); there is no `Escrow` primary option, so escrow is a tag.

### Category tag 1 — `Escrow Claims`
Maps to real functions: `create_grant` (payable vault), `add_milestone` (allocates from vault), `submit_deliverable` (payable builder bond), `release` → `_release` disburses the milestone amount on APPROVED/PARTIAL (100%/50%) or forfeits the bond and reopens on REJECTED. Two-sided escrow with a conditional, verdict-gated payout — the first thing every user meets.

### Category tag 2 — `Evidence Assessment`
Maps to `review`/`rereview` → `_adjudicate`: the nondet block fetches the pinned acceptance-criteria spec + the builder's deliverable artifacts (PR/commit, live demo, docs) via `gl.nondet.web.get/render` and weighs them in `gl.nondet.exec_prompt` to reach APPROVED / PARTIAL / REJECTED with a completeness score.

**Rejected tags (reviewer may check):** `Appeal Review` is defensible (challenge → re-review is a second ruling) but is an optional secondary branch, so not a primary tag. `License Claims` / `Moderation Appeals` / `Jury Selection` — not implemented (validator selection is GenLayer's, not the app's).

### Logo — TO BE PROVIDED
Spec: PNG/JPEG/WebP, 128–2048 px, max 2 MB, opaque background.
Concept: a single mark — a padlock silhouette with a milestone checkpoint/flag path clipped inside it, dark card, indigo/violet accent (`#6366F1`) to match the app. (I can generate this on request via the qlmanage recipe.)

---

## Section 02 — PROJECT SUMMARY

### One-liner  (174 / cap 180)
```
Escrow a grant against milestones; a builder submits proof of the work and a decentralized AI jury reads the spec and the deliverables on-chain to decide how much to release.
```

### Description  (998 / cap 1000)
```
GrantLock is an autonomous milestone escrow. A sponsor funds a grant vault and defines milestones, each pinning a public acceptance-criteria spec. A builder submits a deliverable — a PR or commit, a live demo, published docs — with a bond. GenLayer validators fetch the spec and the deliverable artifacts on-chain, and an LLM rules APPROVED, PARTIAL or REJECTED with a completeness score, releasing 100/50/0% of the milestone. A rejected milestone reopens and forfeits the builder bond to the sponsor.

Built for grant programs, bounties and freelance escrow, where releasing funds today means a human subjectively deciding whether qualitative work is done.

No trusted reviewer or oracle decides. Judging whether a PR implements a feature, or a demo works against written criteria, is a subjective reading of live web artifacts Solidity cannot do. Either side can post a bonded challenge forcing an independent re-review, and validator consensus — not our server — produces the verdict and reason.
```

---

## How to try it

**Prerequisites:** MetaMask. Browsing grants needs no wallet. To create/submit/review you need a GEN balance on GenLayer studionet — fund your address from the Studio **Accounts** panel (studio.genlayer.com → Accounts → transfer from a pre-funded account). Do NOT use a testnet faucet. Budget ~1–2 GEN (grant funding + 0.05 GEN builder bond + gas).

**Step 1 — Browse seeded grants.**
Open https://grantlock.vercel.app → "Grants". You'll see seeded grants whose milestones are RELEASED (approved), APPROVED (partial), LOCKED and REJECTED, each reviewed milestone showing verdict, completeness, confidence and the AI reason. No wallet needed.

**Step 2 — Connect wallet + switch network.**
Click "Connect Wallet"; approve MetaMask. The app auto-switches/adds GenLayer studionet (chain 61999). Confirm your GEN balance top-right.

**Step 3 — Fund a grant (sponsor) or submit a deliverable (builder).**
Sponsor path: "Create Grant" (title, https spec URL, funding) → open it → "Add Milestone" (title, acceptance criteria, amount). Builder path: open a grant with a LOCKED milestone → "Submit Deliverable" with 1–3 evidence URLs + bond (≥0.05 GEN). Sign in MetaMask.

**Step 4 — Trigger AI review.**
On a submitted (CLAIMED) milestone click "Review". A consensus-waiting overlay appears (validators fetch the spec + artifacts and run the LLM). When finalized, the milestone shows verdict + completeness + confidence + reason.

**Step 5 (optional) — Challenge or release.**
The losing side posts a bonded "Challenge" → "Rereview" for an independent second ruling. Otherwise "Release" disburses (100%/50%) or reopens the milestone on rejection.

**Expected end state:** the milestone reaches APPROVED/PARTIAL/REJECTED with an on-chain AI reason; RELEASED after payout.

**If something goes wrong:**
- MetaMask "from" / wrong-network error → re-run Step 2 (must be on studionet).
- Write rejected / insufficient funds → wallet not funded on studionet; see Prerequisites.
- Review seems stuck → nondet consensus is slower than a normal tx; wait, don't resend.

---

## Expected verification outcome  (455 / cap 500)
```
Reading needs no wallet: seeded milestones show verdicts RELEASED (approved, 100%), APPROVED (partial, 50%), LOCKED and REJECTED, each with a completeness score, confidence and a reason produced by validator consensus — not our backend. Submit a deliverable and click Review; after consensus the milestone gains an on-chain verdict + reason and a payout bracket. The studionet explorer lists the tx with GENVM RESULT SUCCESS and CONSENSUS RESULT Accepted.
```

---

## Contract link
```
https://explorer-studio.genlayer.com/address/0x82602Bcd45e359059FE7354d4143a8E5e9db1474
```
- **Address:** `0x82602Bcd45e359059FE7354d4143a8E5e9db1474`
- **Network:** studionet  → **Status: Preview**
- **Deploy tx:** `0xf640a0d5c6b147430057683f13a618b6bf38efac340a1538e3be10753304e807` (deployer `0x8b563A8c9eeF530300e92E26457D1AB001daEcC7`)
- Verified live: `gen_getContractSchema` returns the full method list; real multi-wallet lifecycle (create → add → submit → review → release) executed with GENVM RESULT SUCCESS.
- Alt explorer (also works): https://genlayer-explorer.vercel.app/address/0x82602Bcd45e359059FE7354d4143a8E5e9db1474

## Website
```
https://grantlock.vercel.app
```

## GitHub
```
https://github.com/phu1271997/GrantLock
```

## Community links (optional)
Leave blank.

---

### Pre-submission checklist
- [x] Live URL returns 200, no login wall (verified: bundle carries the final contract address + studionet RPC)
- [x] Contract schema live on studionet; real tx with SUCCESS/Accepted
- [x] Status marked **Preview** (studionet), not Live
- [x] Every tag maps to a named contract function
- [x] One-liner 174 ≤ 180 · Description 998 ≤ 1000 · Expected outcome 455 ≤ 500
- [ ] Logo uploaded (TO BE PROVIDED)
- [ ] (recommended) Re-seed if Studio storage was reset before review — `scripts/seed_demo_data.py`
```
```
