# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *

from dataclasses import dataclass
import json


# ---------------------------------------------------------------------------
# Runtime helpers
# ---------------------------------------------------------------------------
def _run_nondet(leader_fn, validator_fn):
    """Prefer the sandboxed ``run_nondet``; fall back only if the Studio build
    on this network does not expose it (see GEN_RULES Rule #7)."""
    fn = (
        getattr(gl.vm, "run_nondet_default", None)
        or getattr(gl.vm, "run_nondet", None)
        or gl.vm.run_nondet_unsafe
    )
    return fn(leader_fn, validator_fn)


def _addr_str(addr: Address) -> str:
    try:
        return addr.as_hex
    except Exception:
        return str(addr)


def _now_epoch() -> bigint:
    try:
        return bigint(int(gl.vm.get_timestamp().timestamp()))
    except Exception:
        return bigint(0)


# Verdict -> % of the milestone amount released, basis points of 10000.
VERDICT_PAYOUT_BP = {
    "APPROVED": 10000,  # 100%
    "PARTIAL": 5000,    # 50%
    "REJECTED": 0,
}

MIN_MILESTONE_AMOUNT = 100000000000000000    # 0.1 GEN
MIN_BUILDER_BOND = 50000000000000000         # 0.05 GEN
CHALLENGE_WINDOW_SECS = 120
CONFIDENCE_FLOOR = 60


# ---------------------------------------------------------------------------
# Storage structs
# ---------------------------------------------------------------------------
@allow_storage
@dataclass
class Grant:
    sponsor: str
    title: str
    spec_url: str          # pinned public acceptance-criteria document
    vault: bigint          # escrowed funds not yet released
    committed: bigint      # sum of milestone amounts allocated
    milestone_count: u16
    active: bool


@allow_storage
@dataclass
class Milestone:
    grant_id: str
    index: u16
    title: str
    criteria: str          # acceptance criteria for THIS milestone
    amount: bigint
    builder: str
    evidence_blob: str     # newline-joined evidence URLs (avoids DynArray field mutation)
    state: str             # LOCKED | CLAIMED | APPROVED | REJECTED | CHALLENGED | RELEASED
    verdict: str           # "" | APPROVED | PARTIAL | REJECTED
    payout_bp: u16
    completeness: u8       # 0..100
    confidence: u8
    reason: str
    builder_bond: bigint
    challenge_deadline: bigint
    challenger: str
    challenge_bond: bigint
    rebuttal_url: str
    challenged_once: bool
    payout_done: bool


class Contract(gl.Contract):
    admin: Address
    grants: TreeMap[str, Grant]
    milestones: TreeMap[str, Milestone]   # key = f"{grant_id}:{index}"
    next_grant_id: bigint

    def __init__(self):
        self.admin = gl.message.sender_address
        self.next_grant_id = bigint(1)

    def _mkey(self, grant_id: str, index: int) -> str:
        return grant_id + ":" + str(index)

    # -------------------------------------------------------------------
    # Sponsor: create + fund a grant, then define milestones
    # -------------------------------------------------------------------
    @gl.public.write.payable
    def create_grant(self, title: str, spec_url: str) -> str:
        if gl.message.value <= u256(0):
            raise gl.vm.UserError("Grant must be funded with GEN")
        if not title or len(title.strip()) == 0:
            raise gl.vm.UserError("Title cannot be empty")
        if len(title) > 160:
            raise gl.vm.UserError("Title too long")
        if not spec_url.startswith("https://"):
            raise gl.vm.UserError("Spec URL must be a public https:// link")

        gid = int(self.next_grant_id)
        self.next_grant_id = bigint(gid + 1)
        gid_str = str(gid)
        self.grants[gid_str] = Grant(
            sponsor=_addr_str(gl.message.sender_address),
            title=title.strip(),
            spec_url=spec_url.strip(),
            vault=bigint(int(gl.message.value)),
            committed=bigint(0),
            milestone_count=u16(0),
            active=True,
        )
        return gid_str

    @gl.public.write
    def add_milestone(self, grant_id: str, title: str, criteria: str, amount: int) -> int:
        if grant_id not in self.grants:
            raise gl.vm.UserError("Grant not found")
        g = self.grants[grant_id]
        if _addr_str(gl.message.sender_address).lower() != g.sponsor.lower():
            raise gl.vm.UserError("Only the sponsor can add milestones")
        if amount < MIN_MILESTONE_AMOUNT:
            raise gl.vm.UserError("Milestone amount below minimum (0.1 GEN)")
        if int(g.committed) + amount > int(g.vault):
            raise gl.vm.UserError("Milestone amount exceeds unallocated vault funds")
        if len(criteria.strip()) == 0:
            raise gl.vm.UserError("Acceptance criteria cannot be empty")

        idx = int(g.milestone_count)
        g.milestone_count = u16(idx + 1)
        g.committed = g.committed + bigint(amount)
        self.milestones[self._mkey(grant_id, idx)] = Milestone(
            grant_id=grant_id,
            index=u16(idx),
            title=title.strip(),
            criteria=criteria.strip(),
            amount=bigint(amount),
            builder="",
            evidence_blob="",
            state="LOCKED",
            verdict="",
            payout_bp=u16(0),
            completeness=u8(0),
            confidence=u8(0),
            reason="",
            builder_bond=bigint(0),
            challenge_deadline=bigint(0),
            challenger="",
            challenge_bond=bigint(0),
            rebuttal_url="",
            challenged_once=False,
            payout_done=False,
        )
        return idx

    # -------------------------------------------------------------------
    # Builder: submit a deliverable for review
    # -------------------------------------------------------------------
    @gl.public.write.payable
    def submit_deliverable(
        self, grant_id: str, index: int, evidence_urls: DynArray[str]
    ) -> None:
        key = self._mkey(grant_id, index)
        if key not in self.milestones:
            raise gl.vm.UserError("Milestone not found")
        m = self.milestones[key]
        if m.state not in ["LOCKED"]:
            raise gl.vm.UserError("Milestone is not open for submission")
        if gl.message.value < u256(MIN_BUILDER_BOND):
            raise gl.vm.UserError("Builder bond below minimum (0.05 GEN)")
        if len(evidence_urls) == 0:
            raise gl.vm.UserError("At least one evidence URL is required")
        if len(evidence_urls) > 3:
            raise gl.vm.UserError("Maximum 3 evidence URLs allowed")

        m.builder = _addr_str(gl.message.sender_address)
        m.evidence_blob = "\n".join([u.strip() for u in list(evidence_urls) if u.strip()])
        m.builder_bond = bigint(int(gl.message.value))
        m.state = "CLAIMED"

    @gl.public.write
    def review(self, grant_id: str, index: int) -> None:
        key = self._mkey(grant_id, index)
        if key not in self.milestones:
            raise gl.vm.UserError("Milestone not found")
        m = self.milestones[key]
        if m.state != "CLAIMED":
            raise gl.vm.UserError("Milestone is not awaiting review")
        self._adjudicate(key, is_rereview=False)

    @gl.public.write.payable
    def challenge(self, grant_id: str, index: int, rebuttal_url: str, note: str) -> None:
        key = self._mkey(grant_id, index)
        if key not in self.milestones:
            raise gl.vm.UserError("Milestone not found")
        m = self.milestones[key]
        if m.state not in ["APPROVED", "REJECTED"]:
            raise gl.vm.UserError("Only a reviewed milestone can be challenged")
        if m.challenged_once:
            raise gl.vm.UserError("Milestone already challenged once")
        if int(m.challenge_deadline) != 0 and _now_epoch() > m.challenge_deadline:
            raise gl.vm.UserError("Challenge window has closed")
        if gl.message.value < u256(int(m.builder_bond)):
            raise gl.vm.UserError("Challenge bond must be >= the builder bond")

        g = self.grants[grant_id]
        sender = _addr_str(gl.message.sender_address)
        if m.verdict == "REJECTED":
            if sender.lower() != m.builder.lower():
                raise gl.vm.UserError("Only the builder can challenge a rejection")
        else:  # APPROVED / PARTIAL recorded as APPROVED-state
            if sender.lower() != g.sponsor.lower():
                raise gl.vm.UserError("Only the sponsor can challenge an approval")

        if rebuttal_url and not rebuttal_url.startswith("https://"):
            raise gl.vm.UserError("Rebuttal URL must be https://")

        m.rebuttal_url = rebuttal_url.strip() if rebuttal_url else ""
        m.challenger = sender
        m.challenge_bond = bigint(int(gl.message.value))
        m.challenged_once = True
        m.reason = f"{m.reason} | CHALLENGE by {sender}: {note[:300]}"
        m.state = "CHALLENGED"

    @gl.public.write
    def rereview(self, grant_id: str, index: int) -> None:
        key = self._mkey(grant_id, index)
        if key not in self.milestones:
            raise gl.vm.UserError("Milestone not found")
        m = self.milestones[key]
        if m.state != "CHALLENGED":
            raise gl.vm.UserError("Milestone is not under challenge")
        self._adjudicate(key, is_rereview=True)

    def _adjudicate(self, key: str, is_rereview: bool) -> None:
        m = self.milestones[key]
        g = self.grants[m.grant_id]

        spec_url = g.spec_url
        grant_title = g.title
        m_title = m.title
        criteria = m.criteria
        evidence = [u for u in m.evidence_blob.split("\n") if u]
        rebuttal_url = m.rebuttal_url

        def leader_fn():
            sources = []
            sources.append(_fetch(spec_url, "SPEC"))
            for url in evidence[:3]:
                sources.append(_fetch(url, "DELIVERABLE"))
            if rebuttal_url:
                sources.append(_fetch(rebuttal_url, "REBUTTAL"))

            prompt = f"""You are a decentralized AI reviewer on GenLayer deciding whether a grant milestone deliverable meets its acceptance criteria.

GRANT: {grant_title}
MILESTONE: {m_title}
ACCEPTANCE CRITERIA: {criteria}

SOURCES FETCHED LIVE ON-CHAIN (the pinned spec first, then the builder's deliverable evidence):
{json.dumps(sources, indent=2)[:12000]}

Judge strictly against the acceptance criteria:
1. Do the deliverable artifacts (PR/commit, deployed demo, docs/article) actually exist and load?
2. Do they implement what the criteria require, not merely mention it?
3. Rate completeness 0-100.
Verdict rules: APPROVED (fully meets criteria, completeness >= 85), PARTIAL (substantive but incomplete, 40-84), REJECTED (missing/broken/off-topic, < 40).

RESPOND WITH ONLY VALID JSON:
{{
  "verdict": "APPROVED" | "PARTIAL" | "REJECTED",
  "completeness": 0-100,
  "confidence": 0-100,
  "reason": "2-4 sentences citing the criteria and the specific artifact evidence"
}}"""
            return gl.nondet.exec_prompt(prompt, response_format="json")

        def validator_fn(leader_res) -> bool:
            # Compare MEANING: verdict + completeness tier + confidence floor.
            if not isinstance(leader_res, gl.vm.Return):
                return False
            leader = leader_res.calldata
            if not isinstance(leader, dict):
                return False
            for k in ("verdict", "completeness", "confidence"):
                if k not in leader:
                    return False
            mine = leader_fn()
            if not isinstance(mine, dict):
                return False
            for k in ("verdict", "completeness", "confidence"):
                if k not in mine:
                    return False
            if str(mine["verdict"]).upper() != str(leader["verdict"]).upper():
                return False
            # agree on the completeness tier (which selects the payout bracket)
            if _tier(int(mine["completeness"])) != _tier(int(leader["completeness"])):
                return False
            mc = int(mine["confidence"])
            lc = int(leader["confidence"])
            if (mc >= CONFIDENCE_FLOOR) != (lc >= CONFIDENCE_FLOOR):
                return False
            if abs(mc - lc) > 15:
                return False
            return True

        result = _run_nondet(leader_fn, validator_fn)
        verdict = str(result.get("verdict", "REJECTED")).upper()
        if verdict not in ["APPROVED", "PARTIAL", "REJECTED"]:
            verdict = "REJECTED"
        completeness = max(0, min(100, int(result.get("completeness", 0))))
        confidence = max(0, min(100, int(result.get("confidence", 70))))
        reason = str(result.get("reason", ""))

        m.verdict = verdict
        m.completeness = u8(completeness)
        m.confidence = u8(confidence)
        m.payout_bp = u16(VERDICT_PAYOUT_BP.get(verdict, 0))
        m.reason = (m.reason + " | " if is_rereview else "") + reason
        # APPROVED and PARTIAL both sit in the "APPROVED" settle-state (funds owed);
        # REJECTED sits in "REJECTED".
        m.state = "REJECTED" if verdict == "REJECTED" else "APPROVED"

        if is_rereview:
            m.challenge_deadline = bigint(0)
            self._release(key)
        else:
            # Open a challenge window. If the runtime clock is unavailable
            # (studionet's get_timestamp can return 0), fall back to deadline 0,
            # meaning "no timed lock — the window stays open until someone releases".
            now = _now_epoch()
            if int(now) > 0:
                window = CHALLENGE_WINDOW_SECS * (2 if confidence < CONFIDENCE_FLOOR else 1)
                m.challenge_deadline = now + bigint(window)
            else:
                m.challenge_deadline = bigint(0)

    @gl.public.write
    def release(self, grant_id: str, index: int) -> None:
        key = self._mkey(grant_id, index)
        if key not in self.milestones:
            raise gl.vm.UserError("Milestone not found")
        m = self.milestones[key]
        if m.state == "CHALLENGED":
            raise gl.vm.UserError("Milestone is under challenge; call rereview first")
        if m.state not in ["APPROVED", "REJECTED"]:
            raise gl.vm.UserError("Milestone is not in a releasable state")
        if m.payout_done:
            raise gl.vm.UserError("Milestone already released")
        if int(m.challenge_deadline) != 0 and _now_epoch() < m.challenge_deadline:
            raise gl.vm.UserError("Challenge window is still open")
        self._release(key)

    def _release(self, key: str) -> None:
        m = self.milestones[key]
        g = self.grants[m.grant_id]

        builder = m.builder
        sponsor = g.sponsor
        amount = int(m.amount)
        builder_bond = int(m.builder_bond)
        challenge_bond = int(m.challenge_bond)
        challenger = m.challenger

        if m.verdict in ["APPROVED", "PARTIAL"]:
            payout = (amount * int(m.payout_bp)) // 10000
            if payout > int(g.vault):
                payout = int(g.vault)
            g.vault = bigint(int(g.vault) - payout)
            g.committed = bigint(max(0, int(g.committed) - amount))
            # unreleased remainder (PARTIAL) frees back to the sponsor's vault allocation
            to_builder = payout + builder_bond
            if challenger and challenger.lower() == sponsor.lower():
                to_builder += challenge_bond  # sponsor challenged and lost
            _pay(builder, to_builder)
            m.state = "RELEASED"
            m.payout_done = True
        else:  # REJECTED — builder bond forfeited to the sponsor; milestone reopens
            to_sponsor = builder_bond
            if challenger and challenger.lower() == builder.lower():
                to_sponsor += challenge_bond  # builder challenged and lost
            _pay(sponsor, to_sponsor)
            # reopen for another attempt
            m.builder = ""
            m.builder_bond = bigint(0)
            m.challenger = ""
            m.challenge_bond = bigint(0)
            m.rebuttal_url = ""
            m.challenged_once = False
            m.challenge_deadline = bigint(0)
            m.payout_done = False
            m.state = "LOCKED"

    # -------------------------------------------------------------------
    # Admin demo seeding (pre-baked verdicts; no LLM call)
    # -------------------------------------------------------------------
    @gl.public.write.payable
    def admin_seed_grant(
        self, sponsor: str, title: str, spec_url: str, vault: int
    ) -> str:
        if gl.message.sender_address != self.admin:
            raise gl.vm.UserError("Only admin can seed")
        gid = int(self.next_grant_id)
        self.next_grant_id = bigint(gid + 1)
        gid_str = str(gid)
        self.grants[gid_str] = Grant(
            sponsor=sponsor,
            title=title,
            spec_url=spec_url,
            vault=bigint(vault),
            committed=bigint(0),
            milestone_count=u16(0),
            active=True,
        )
        return gid_str

    @gl.public.write
    def admin_seed_milestone(
        self,
        grant_id: str,
        title: str,
        criteria: str,
        amount: int,
        builder: str,
        evidence_urls: DynArray[str],
        state: str,
        verdict: str,
        completeness: int,
        confidence: int,
        reason: str,
    ) -> int:
        if gl.message.sender_address != self.admin:
            raise gl.vm.UserError("Only admin can seed")
        if grant_id not in self.grants:
            raise gl.vm.UserError("Grant not found")
        g = self.grants[grant_id]
        idx = int(g.milestone_count)
        g.milestone_count = u16(idx + 1)
        g.committed = g.committed + bigint(amount)
        v = verdict.upper() if verdict else ""
        self.milestones[self._mkey(grant_id, idx)] = Milestone(
            grant_id=grant_id,
            index=u16(idx),
            title=title,
            criteria=criteria,
            amount=bigint(amount),
            builder=builder,
            evidence_blob="\n".join([u.strip() for u in list(evidence_urls) if u.strip()]),
            state=state,
            verdict=v,
            payout_bp=u16(VERDICT_PAYOUT_BP.get(v, 0)),
            completeness=u8(max(0, min(100, completeness))),
            confidence=u8(max(0, min(100, confidence))),
            reason=reason,
            builder_bond=bigint(0),
            challenge_deadline=bigint(0),
            challenger="",
            challenge_bond=bigint(0),
            rebuttal_url="",
            challenged_once=False,
            payout_done=(state == "RELEASED"),
        )
        return idx

    # -------------------------------------------------------------------
    # Views
    # -------------------------------------------------------------------
    @gl.public.view
    def get_grant(self, grant_id: str) -> str:
        if grant_id not in self.grants:
            raise gl.vm.UserError("Grant not found")
        g = self.grants[grant_id]
        ms = []
        for i in range(int(g.milestone_count)):
            k = self._mkey(grant_id, i)
            if k in self.milestones:
                ms.append(self._milestone_json(self.milestones[k]))
        return json.dumps(
            {
                "grant_id": grant_id,
                "sponsor": g.sponsor,
                "title": g.title,
                "spec_url": g.spec_url,
                "vault": str(g.vault),
                "committed": str(g.committed),
                "milestone_count": int(g.milestone_count),
                "active": g.active,
                "milestones": ms,
            }
        )

    @gl.public.view
    def get_milestone(self, grant_id: str, index: int) -> str:
        k = self._mkey(grant_id, index)
        if k not in self.milestones:
            raise gl.vm.UserError("Milestone not found")
        return json.dumps(self._milestone_json(self.milestones[k]))

    def _milestone_json(self, m: Milestone) -> dict:
        return {
            "grant_id": m.grant_id,
            "index": int(m.index),
            "title": m.title,
            "criteria": m.criteria,
            "amount": str(m.amount),
            "builder": m.builder,
            "evidence_urls": [u for u in m.evidence_blob.split("\n") if u],
            "state": m.state,
            "verdict": m.verdict,
            "payout_bp": int(m.payout_bp),
            "completeness": int(m.completeness),
            "confidence": int(m.confidence),
            "reason": m.reason,
            "builder_bond": str(m.builder_bond),
            "challenge_deadline": int(m.challenge_deadline),
            "challenger": m.challenger,
            "challenge_bond": str(m.challenge_bond),
            "rebuttal_url": m.rebuttal_url,
            "challenged_once": m.challenged_once,
            "payout_done": m.payout_done,
        }

    @gl.public.view
    def get_grant_count(self) -> u256:
        return u256(int(self.next_grant_id) - 1)

    @gl.public.view
    def list_grants(self, offset: int, limit: int) -> str:
        total = int(self.next_grant_id) - 1
        out = []
        start = max(1, offset + 1)
        end = min(total + 1, start + limit)
        for i in range(start, end):
            k = str(i)
            if k in self.grants:
                g = self.grants[k]
                released = 0
                approved = 0
                for j in range(int(g.milestone_count)):
                    mk = self._mkey(k, j)
                    if mk in self.milestones:
                        st = self.milestones[mk].state
                        if st == "RELEASED":
                            released += 1
                        elif st == "APPROVED":
                            approved += 1
                out.append(
                    {
                        "grant_id": k,
                        "sponsor": g.sponsor,
                        "title": g.title,
                        "spec_url": g.spec_url,
                        "vault": str(g.vault),
                        "committed": str(g.committed),
                        "milestone_count": int(g.milestone_count),
                        "released": released,
                        "approved_pending": approved,
                        "active": g.active,
                    }
                )
        return json.dumps(out)


# ---------------------------------------------------------------------------
# Module-level helpers (called inside methods / nondet closures only)
# ---------------------------------------------------------------------------
def _tier(completeness: int) -> str:
    if completeness >= 85:
        return "FULL"
    if completeness >= 40:
        return "PARTIAL"
    return "FAIL"


def _fetch(url: str, kind: str) -> dict:
    try:
        res = gl.nondet.web.get(url)
        body = res.body.decode("utf-8", errors="replace") if hasattr(res, "body") else str(res)
        return {"url": url, "kind": kind, "content": body[:3500]}
    except Exception:
        try:
            body = gl.nondet.web.render(url, mode="text")
            return {"url": url, "kind": kind, "content": body[:3500]}
        except Exception as e:
            return {"url": url, "kind": kind, "error": str(e)[:200]}


def _pay(recipient: str, amount: int) -> None:
    if amount <= 0 or not recipient:
        return
    try:
        gl.get_contract_at(Address(recipient)).emit_transfer(value=u256(int(amount)))
    except Exception:
        pass
