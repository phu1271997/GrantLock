import React, { useState, useEffect, useCallback } from 'react';
import { getGenLayerClient } from './lib/client';
import { connectWallet } from './lib/wallet';
import { GRANTLOCK_CONTRACT } from './lib/addresses';
import {
  Lock,
  ExternalLink,
  PlusCircle,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RefreshCw,
  FileCheck2,
  Scale,
  Clock,
  Layers,
} from 'lucide-react';

interface Milestone {
  grant_id: string;
  index: number;
  title: string;
  criteria: string;
  amount: string;
  builder: string;
  evidence_urls: string[];
  state: string;
  verdict: string;
  payout_bp: number;
  completeness: number;
  confidence: number;
  reason: string;
  builder_bond: string;
  challenge_deadline: number;
  challenger: string;
  challenge_bond: string;
  rebuttal_url: string;
  challenged_once: boolean;
  payout_done: boolean;
}

interface GrantSummary {
  grant_id: string;
  sponsor: string;
  title: string;
  spec_url: string;
  vault: string;
  committed: string;
  milestone_count: number;
  released?: number;
  approved_pending?: number;
  active: boolean;
}

interface GrantDetail extends GrantSummary {
  milestones: Milestone[];
}

const EXPLORER = 'https://genlayer-explorer.vercel.app';
const toGen = (wei: string | number) => (Number(wei) / 1e18).toFixed(3);
const short = (a: string) => (a ? `${a.slice(0, 6)}...${a.slice(-4)}` : '—');
const nowSec = () => Math.floor(Date.now() / 1000);

const STATE_STYLES: Record<string, string> = {
  LOCKED: 'bg-gray-600/20 text-gray-300 border-gray-600/40',
  CLAIMED: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  APPROVED: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  REJECTED: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
  CHALLENGED: 'bg-purple-500/10 text-purple-400 border-purple-500/20 animate-pulse',
  RELEASED: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
};

export default function App() {
  const [account, setAccount] = useState<string | null>(null);
  const [balance, setBalance] = useState('0');
  const [tab, setTab] = useState<'grants' | 'detail' | 'about'>('grants');
  const [grants, setGrants] = useState<GrantSummary[]>([]);
  const [selectedGrantId, setSelectedGrantId] = useState<string | null>(null);
  const [grant, setGrant] = useState<GrantDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [waitMsg, setWaitMsg] = useState('');
  const [txHash, setTxHash] = useState<string | null>(null);

  const [showCreate, setShowCreate] = useState(false);
  const [showMilestone, setShowMilestone] = useState(false);
  const [showSubmit, setShowSubmit] = useState<number | null>(null);
  const [showChallenge, setShowChallenge] = useState<Milestone | null>(null);

  // create grant
  const [gTitle, setGTitle] = useState('');
  const [gSpec, setGSpec] = useState('https://');
  const [gFund, setGFund] = useState('1');
  // add milestone
  const [mTitle, setMTitle] = useState('');
  const [mCriteria, setMCriteria] = useState('');
  const [mAmount, setMAmount] = useState('0.5');
  // submit deliverable
  const [sUrls, setSUrls] = useState('');
  const [sBond, setSBond] = useState('0.05');
  // challenge
  const [cUrl, setCUrl] = useState('https://');
  const [cNote, setCNote] = useState('');

  const handleConnect = async () => {
    try { setBusy(true); const addr = await connectWallet(); setAccount(addr); fetchBalance(addr); }
    catch (e: any) { alert(e.message || 'Connection failed'); }
    finally { setBusy(false); }
  };

  const fetchBalance = async (addr: string) => {
    try {
      if (window.ethereum) {
        const res: any = await window.ethereum.request({ method: 'eth_getBalance', params: [addr, 'latest'] });
        if (res) setBalance((Number(BigInt(res)) / 1e18).toFixed(3));
      }
    } catch { /* ignore */ }
  };

  const fetchGrants = useCallback(async () => {
    try {
      const raw: any = await getGenLayerClient().readContract({ address: GRANTLOCK_CONTRACT, functionName: 'list_grants', args: [0, 100] });
      if (raw) setGrants(typeof raw === 'string' ? JSON.parse(raw) : raw);
    } catch (e) { console.error('grants', e); }
  }, []);

  const fetchDetail = useCallback(async (id: string) => {
    try {
      setBusy(true);
      const raw: any = await getGenLayerClient().readContract({ address: GRANTLOCK_CONTRACT, functionName: 'get_grant', args: [id] });
      setGrant(typeof raw === 'string' ? JSON.parse(raw) : raw);
    } catch (e) { console.error('detail', e); } finally { setBusy(false); }
  }, []);

  useEffect(() => { fetchGrants(); }, [fetchGrants]);
  useEffect(() => { if (tab === 'detail' && selectedGrantId) fetchDetail(selectedGrantId); }, [tab, selectedGrantId, fetchDetail]);

  const runWrite = async (functionName: string, args: any[], value: bigint, msg: string) => {
    if (!account) { alert('Connect your MetaMask wallet first'); return false; }
    try {
      setBusy(true); setWaitMsg(msg); setTxHash(null);
      const client = getGenLayerClient(account as `0x${string}`);
      const tx = await client.writeContract({ address: GRANTLOCK_CONTRACT, functionName, args, value });
      setTxHash(tx as string);
      await (client as any).waitForTransactionReceipt({ hash: tx as any });
      fetchBalance(account);
      return true;
    } catch (e: any) {
      alert('Transaction error: ' + (e.shortMessage || e.message || String(e)));
      return false;
    } finally { setBusy(false); setWaitMsg(''); }
  };

  const doCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const fund = BigInt(Math.round(Number(gFund) * 1e18));
    const ok = await runWrite('create_grant', [gTitle, gSpec], fund, 'Funding grant vault...');
    if (ok) { setShowCreate(false); setGTitle(''); setGSpec('https://'); fetchGrants(); }
  };

  const doMilestone = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!grant) return;
    const amt = BigInt(Math.round(Number(mAmount) * 1e18));
    const ok = await runWrite('add_milestone', [grant.grant_id, mTitle, mCriteria, amt], 0n, 'Allocating milestone from vault...');
    if (ok) { setShowMilestone(false); setMTitle(''); setMCriteria(''); fetchDetail(grant.grant_id); }
  };

  const doSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!grant || showSubmit === null) return;
    const urls = sUrls.split('\n').map((u) => u.trim()).filter(Boolean).slice(0, 3);
    if (urls.length === 0) { alert('Add at least one evidence URL'); return; }
    const bond = BigInt(Math.round(Number(sBond) * 1e18));
    const ok = await runWrite('submit_deliverable', [grant.grant_id, showSubmit, urls], bond, 'Submitting bonded deliverable...');
    if (ok) { setShowSubmit(null); setSUrls(''); fetchDetail(grant.grant_id); }
  };

  const doReview = async (idx: number) => {
    if (!grant) return;
    const ok = await runWrite('review', [grant.grant_id, idx], 0n, 'AI reviewer reading the pinned spec + the deliverable artifacts on-chain and reaching consensus...');
    if (ok) fetchDetail(grant.grant_id);
  };
  const doRereview = async (idx: number) => {
    if (!grant) return;
    const ok = await runWrite('rereview', [grant.grant_id, idx], 0n, 'Re-reviewing with the challenger rebuttal (final)...');
    if (ok) fetchDetail(grant.grant_id);
  };
  const doRelease = async (idx: number) => {
    if (!grant) return;
    const ok = await runWrite('release', [grant.grant_id, idx], 0n, 'Releasing milestone funds on-chain...');
    if (ok) fetchDetail(grant.grant_id);
  };
  const doChallenge = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!grant || !showChallenge) return;
    const bond = BigInt(showChallenge.builder_bond);
    const ok = await runWrite('challenge', [grant.grant_id, showChallenge.index, cUrl, cNote], bond, 'Posting bonded challenge...');
    if (ok) { setShowChallenge(null); setCNote(''); setCUrl('https://'); fetchDetail(grant.grant_id); }
  };

  const isSponsor = grant && account && account.toLowerCase() === grant.sponsor.toLowerCase();
  const unallocated = grant ? Number(grant.vault) - Number(grant.committed) : 0;

  return (
    <div className="min-h-screen flex flex-col bg-[#070B14] text-gray-100">
      <header className="border-b border-gray-800 bg-[#0B0F19]/80 backdrop-blur sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3 cursor-pointer" onClick={() => setTab('grants')}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-violet-500 to-fuchsia-600 flex items-center justify-center text-xl shadow-lg shadow-violet-500/20">🔐</div>
            <div>
              <div className="font-bold text-lg tracking-tight bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent">GrantLock</div>
              <div className="text-[10px] text-violet-400 font-medium tracking-wide">GENLAYER STUDIONET · MILESTONE ESCROW</div>
            </div>
          </div>
          <nav className="hidden md:flex items-center space-x-1 text-sm font-medium">
            {(['grants', 'about'] as const).map((t) => (
              <button key={t} onClick={() => setTab(t)} className={`px-3 py-1.5 rounded-lg transition capitalize ${tab === t ? 'bg-gray-800 text-white' : 'text-gray-400 hover:text-white'}`}>{t === 'about' ? 'How It Works' : t}</button>
            ))}
          </nav>
          <div>
            {account ? (
              <div className="flex items-center space-x-2 bg-gray-900 border border-gray-800 px-3 py-1.5 rounded-xl text-xs">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <span className="font-mono text-gray-300">{short(account)}</span>
                <span className="text-violet-400 font-semibold pl-1 border-l border-gray-700">{balance} GEN</span>
              </div>
            ) : (
              <button onClick={handleConnect} disabled={busy} className="bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold px-4 py-2 rounded-xl transition shadow-lg shadow-violet-600/20">Connect Wallet</button>
            )}
          </div>
        </div>
      </header>

      {account && Number(balance) === 0 && (
        <div className="bg-amber-950/40 border-b border-amber-800/60 px-4 py-2 text-xs text-amber-200 flex items-center justify-center space-x-2">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          <span>Connected wallet has 0 GEN on studionet. Fund it from <a href="https://studio.genlayer.com" target="_blank" rel="noreferrer" className="underline font-bold text-amber-300 hover:text-white">GenLayer Studio → Accounts panel</a> (do NOT use the testnet faucet).</span>
        </div>
      )}

      {busy && waitMsg && (
        <div className="bg-indigo-950/80 border-b border-indigo-700/60 px-4 py-3 text-xs text-indigo-100 flex items-center justify-center space-x-3">
          <RefreshCw className="w-4 h-4 text-indigo-400 animate-spin" />
          <div className="text-center">
            <span className="font-bold text-indigo-300">{waitMsg}</span>{' '}
            <span>Non-deterministic consensus is slower than a normal tx — validators fetch artifacts and agree on the verdict.</span>
            {txHash && <a href={`${EXPLORER}/tx/${txHash}`} target="_blank" rel="noreferrer" className="ml-2 underline text-indigo-300 hover:text-white inline-flex items-center">Explorer <ExternalLink className="w-3 h-3 ml-1" /></a>}
          </div>
        </div>
      )}

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* GRANTS */}
        {tab === 'grants' && (
          <div>
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
              <div>
                <h1 className="text-2xl font-extrabold text-white tracking-tight">Grants</h1>
                <p className="text-sm text-gray-400 mt-1 max-w-2xl">Sponsors escrow funds against milestones with a pinned acceptance spec. Builders submit deliverables; a GenLayer AI reviewer reads the spec + the artifacts (PR, live demo, docs) on-chain and rules whether the criteria are met before funds release.</p>
              </div>
              <button onClick={() => setShowCreate(true)} className="bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-500 hover:to-fuchsia-500 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition flex items-center space-x-2 shadow-lg shadow-violet-600/20 self-start">
                <PlusCircle className="w-4 h-4" /><span>Create Grant</span>
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {grants.map((g) => (
                <div key={g.grant_id} onClick={() => { setSelectedGrantId(g.grant_id); setTab('detail'); }} className="bg-gray-900/60 border border-gray-800 hover:border-violet-500/50 rounded-2xl p-5 cursor-pointer transition flex flex-col">
                  <div className="flex items-center justify-between mb-3 text-xs">
                    <span className="font-mono text-gray-400">Grant #{g.grant_id}</span>
                    <span className="px-2.5 py-0.5 rounded-full font-semibold text-[10px] border bg-violet-500/10 text-violet-300 border-violet-500/20 flex items-center gap-1"><Layers className="w-3 h-3" />{g.milestone_count} milestones</span>
                  </div>
                  <h3 className="text-base font-bold text-gray-100 mb-3 leading-snug line-clamp-2">{g.title}</h3>
                  <div className="text-xs text-gray-400 border-t border-gray-800/80 pt-3 mt-auto space-y-1.5">
                    <div className="flex justify-between"><span>Vault:</span><span className="text-emerald-400 font-semibold">{toGen(g.vault)} GEN</span></div>
                    <div className="flex justify-between"><span>Committed:</span><span className="text-gray-300">{toGen(g.committed)} GEN</span></div>
                    <div className="flex justify-between"><span>Released:</span><span className="text-blue-400">{g.released ?? 0}/{g.milestone_count}</span></div>
                    <div className="flex justify-between"><span>Sponsor:</span><span className="font-mono text-gray-300">{short(g.sponsor)}</span></div>
                  </div>
                </div>
              ))}
            </div>
            {grants.length === 0 && <Empty icon={<Lock className="w-12 h-12 mx-auto text-gray-600 mb-3" />} title="No grants yet" sub="Create the first milestone-escrowed grant." />}
          </div>
        )}

        {/* DETAIL */}
        {tab === 'detail' && grant && (
          <div className="space-y-6 max-w-4xl mx-auto">
            <button onClick={() => setTab('grants')} className="text-xs text-gray-400 hover:text-white">&larr; Back to grants</button>
            <div className="bg-gray-900 border border-gray-800 rounded-3xl p-6 sm:p-8">
              <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-6">
                <div className="max-w-2xl">
                  <div className="text-xs font-mono text-gray-400 mb-2">Grant #{grant.grant_id}</div>
                  <h1 className="text-2xl font-extrabold text-white leading-tight mb-3">{grant.title}</h1>
                  <a href={grant.spec_url} target="_blank" rel="noreferrer" className="text-xs text-violet-400 hover:underline inline-flex items-center gap-1">Pinned acceptance spec <ExternalLink className="w-3 h-3" /></a>
                  <div className="text-xs text-gray-500 mt-1">Sponsor: <span className="font-mono text-gray-300">{short(grant.sponsor)}</span></div>
                </div>
                <div className="bg-gray-950/80 border border-gray-800 rounded-2xl p-5 min-w-[240px] text-xs space-y-2">
                  <div className="flex justify-between"><span className="text-gray-400">Vault</span><span className="text-emerald-400 font-bold">{toGen(grant.vault)} GEN</span></div>
                  <div className="flex justify-between"><span className="text-gray-400">Committed</span><span className="text-gray-200">{toGen(grant.committed)} GEN</span></div>
                  <div className="flex justify-between"><span className="text-gray-400">Unallocated</span><span className="text-gray-200">{toGen(unallocated)} GEN</span></div>
                  {isSponsor && (
                    <button onClick={() => setShowMilestone(true)} className="mt-2 w-full bg-violet-600 hover:bg-violet-500 text-white text-xs font-bold py-2 rounded-xl transition">+ Add Milestone</button>
                  )}
                </div>
              </div>
            </div>

            <div className="space-y-4">
              {grant.milestones.map((m) => {
                const windowOpen = m.challenge_deadline === 0 || nowSec() < m.challenge_deadline;
                const isBuilder = account && m.builder && account.toLowerCase() === m.builder.toLowerCase();
                const canChallenge = !m.challenged_once && windowOpen &&
                  ((m.state === 'APPROVED' && isSponsor) || (m.state === 'REJECTED' && isBuilder));
                const canRelease = ['APPROVED', 'REJECTED'].includes(m.state) && !m.payout_done && (m.challenge_deadline === 0 || nowSec() >= m.challenge_deadline);
                return (
                  <div key={m.index} className="bg-gray-900/70 border border-gray-800 rounded-2xl p-5">
                    <div className="flex items-center justify-between mb-2 text-xs">
                      <span className="font-mono text-gray-400">M{m.index} · {toGen(m.amount)} GEN</span>
                      <StateBadge state={m.state} />
                    </div>
                    <h3 className="text-base font-bold text-gray-100 mb-1">{m.title}</h3>
                    <p className="text-xs text-gray-400 mb-3"><span className="text-gray-500">Acceptance criteria: </span>{m.criteria}</p>
                    {m.builder && <div className="text-[11px] text-gray-500 mb-2">Builder: <span className="font-mono text-gray-300">{short(m.builder)}</span> · bond {toGen(m.builder_bond)} GEN</div>}
                    {m.evidence_urls.length > 0 && (
                      <div className="flex flex-wrap gap-2 mb-3">
                        <span className="text-[11px] text-gray-500 self-center">Artifacts read on-chain:</span>
                        {m.evidence_urls.map((u, i) => <a key={i} href={u} target="_blank" rel="noreferrer" className="bg-gray-800/80 hover:bg-gray-700 px-2.5 py-1 rounded text-violet-400 flex items-center gap-1 text-xs"><span className="underline max-w-[220px] truncate">{u}</span><ExternalLink className="w-3 h-3" /></a>)}
                      </div>
                    )}
                    {m.verdict && (
                      <div className={`rounded-xl p-4 border mt-2 ${m.verdict === 'REJECTED' ? 'bg-rose-950/30 border-rose-500/30' : 'bg-emerald-950/30 border-emerald-500/30'}`}>
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
                          <div className="flex items-center gap-2">
                            {m.verdict === 'REJECTED' ? <XCircle className="w-4 h-4 text-rose-400" /> : <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
                            <span className={`font-bold text-sm ${m.verdict === 'REJECTED' ? 'text-rose-300' : 'text-emerald-300'}`}>AI Verdict: {m.verdict} · pays {(m.payout_bp / 100).toFixed(0)}%</span>
                          </div>
                          <div className="flex items-center gap-2 text-xs"><span className="text-gray-400">Confidence</span><div className="w-20 bg-gray-800 rounded-full h-2 overflow-hidden"><div className="bg-violet-400 h-full" style={{ width: `${m.confidence}%` }} /></div><span className="font-bold text-violet-400">{m.confidence}%</span></div>
                        </div>
                        <div className="flex items-center gap-2 text-[11px] text-gray-400 mb-2"><span>Completeness</span><div className="flex-1 bg-gray-800 rounded-full h-1.5 overflow-hidden"><div className="bg-emerald-400 h-full" style={{ width: `${m.completeness}%` }} /></div><span>{m.completeness}%</span></div>
                        <p className="text-sm text-gray-300 italic leading-relaxed">"{m.reason}"</p>
                        {m.challenge_deadline > 0 && !m.payout_done && <div className="mt-2 text-[11px] text-gray-400 flex items-center gap-1.5"><Clock className="w-3.5 h-3.5" /> Challenge window {windowOpen ? 'open until' : 'closed at'} epoch {m.challenge_deadline}.</div>}
                      </div>
                    )}
                    <div className="mt-4 flex flex-wrap gap-2">
                      {m.state === 'LOCKED' && account && (
                        <button onClick={() => setShowSubmit(m.index)} className="bg-violet-600 hover:bg-violet-500 text-white text-xs font-bold px-4 py-2 rounded-xl transition flex items-center gap-2"><FileCheck2 className="w-4 h-4" /> Submit Deliverable</button>
                      )}
                      {m.state === 'CLAIMED' && (
                        <button onClick={() => doReview(m.index)} disabled={busy} className="bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold px-4 py-2 rounded-xl transition flex items-center gap-2"><Scale className="w-4 h-4" /> Run AI Review</button>
                      )}
                      {canChallenge && (
                        <button onClick={() => setShowChallenge(m)} className="bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold px-4 py-2 rounded-xl transition flex items-center gap-2"><Scale className="w-4 h-4" /> Challenge</button>
                      )}
                      {m.state === 'CHALLENGED' && (
                        <button onClick={() => doRereview(m.index)} disabled={busy} className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold px-4 py-2 rounded-xl transition flex items-center gap-2"><RefreshCw className="w-4 h-4" /> Re-review (final)</button>
                      )}
                      {canRelease && (
                        <button onClick={() => doRelease(m.index)} disabled={busy} className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold px-4 py-2 rounded-xl transition flex items-center gap-2"><CheckCircle2 className="w-4 h-4" /> Release Funds</button>
                      )}
                    </div>
                  </div>
                );
              })}
              {grant.milestones.length === 0 && <Empty icon={<Layers className="w-12 h-12 mx-auto text-gray-600 mb-3" />} title="No milestones yet" sub={isSponsor ? 'Add one from the vault panel above.' : 'The sponsor has not defined milestones.'} />}
            </div>
          </div>
        )}

        {/* ABOUT */}
        {tab === 'about' && (
          <div className="max-w-3xl mx-auto space-y-6">
            <h1 className="text-2xl font-extrabold text-white tracking-tight">How GrantLock Works</h1>
            <div className="text-sm text-gray-300 space-y-4 leading-relaxed">
              <p>GrantLock is autonomous milestone escrow for grants and bounties. A sponsor funds a vault and defines milestones, each with a pinned acceptance spec. Whether a deliverable actually meets the criteria — and thus whether funds release — is decided by GenLayer validator consensus, not by the sponsor's discretion.</p>
              <h3 className="text-lg font-bold text-white pt-2">Why it dies without GenLayer</h3>
              <ul className="list-disc pl-5 space-y-2">
                <li><b>On-chain web reading:</b> the contract runs <code>gl.nondet.web.render</code> to fetch the pinned acceptance spec <i>and</i> the builder's artifacts — a GitHub PR/commit, a live demo, a published article — directly, no oracle.</li>
                <li><b>Subjective judgment:</b> an LLM reviewer decides whether the artifacts <i>implement</i> the criteria (not merely mention them) and scores completeness 0-100 → APPROVED / PARTIAL / REJECTED.</li>
                <li><b>Semantic consensus:</b> a custom <code>validator_fn</code> makes validators agree on the <i>verdict and completeness tier</i> (which selects the 100% / 50% / 0% payout bracket), not the wording.</li>
                <li><b>Bonded challenge:</b> the sponsor can dispute an approval and the builder can dispute a rejection with a bonded rebuttal, triggering a final re-review before funds move.</li>
              </ul>
              <p className="text-gray-400 text-xs pt-2">Contract on studionet: <a className="text-violet-400 hover:underline" href={`${EXPLORER}/address/${GRANTLOCK_CONTRACT}`} target="_blank" rel="noreferrer">{GRANTLOCK_CONTRACT}</a></p>
            </div>
          </div>
        )}
      </main>

      {/* CREATE GRANT */}
      {showCreate && (
        <Modal title="Create & Fund a Grant" onClose={() => setShowCreate(false)}>
          <form onSubmit={doCreate} className="space-y-4">
            <Field label="Grant title"><input value={gTitle} onChange={(e) => setGTitle(e.target.value)} required placeholder="Open-source SDK examples bounty" className={inputCls} /></Field>
            <Field label="Pinned acceptance spec URL (public https)"><input value={gSpec} onChange={(e) => setGSpec(e.target.value)} required type="url" className={inputCls} /></Field>
            <Field label="Vault funding (GEN)"><input value={gFund} onChange={(e) => setGFund(e.target.value)} type="number" step="0.1" min="0.1" className={inputCls} /></Field>
            <ModalButtons busy={busy} onCancel={() => setShowCreate(false)} label="Fund Vault & Create" />
          </form>
        </Modal>
      )}

      {/* ADD MILESTONE */}
      {showMilestone && grant && (
        <Modal title="Add Milestone" onClose={() => setShowMilestone(false)}>
          <div className="bg-violet-950/30 border border-violet-800/40 rounded-xl p-3 text-xs text-violet-200 mb-4">Unallocated vault: {toGen(unallocated)} GEN. The milestone amount cannot exceed this.</div>
          <form onSubmit={doMilestone} className="space-y-4">
            <Field label="Milestone title"><input value={mTitle} onChange={(e) => setMTitle(e.target.value)} required className={inputCls} /></Field>
            <Field label="Acceptance criteria"><textarea value={mCriteria} onChange={(e) => setMCriteria(e.target.value)} required rows={3} placeholder="A working demo + linked commit that connects MetaMask and reads a view." className={inputCls} /></Field>
            <Field label="Amount (GEN)"><input value={mAmount} onChange={(e) => setMAmount(e.target.value)} type="number" step="0.1" min="0.1" className={inputCls} /></Field>
            <ModalButtons busy={busy} onCancel={() => setShowMilestone(false)} label="Allocate Milestone" />
          </form>
        </Modal>
      )}

      {/* SUBMIT DELIVERABLE */}
      {showSubmit !== null && (
        <Modal title={`Submit Deliverable — M${showSubmit}`} onClose={() => setShowSubmit(null)}>
          <form onSubmit={doSubmit} className="space-y-4">
            <Field label="Evidence URLs (one per line — PR, live demo, docs; up to 3)"><textarea value={sUrls} onChange={(e) => setSUrls(e.target.value)} required rows={3} placeholder={'https://github.com/org/repo/pull/42\nhttps://my-demo.vercel.app'} className={inputCls} /></Field>
            <Field label="Builder bond (GEN, min 0.05)"><input value={sBond} onChange={(e) => setSBond(e.target.value)} type="number" step="0.01" min="0.05" className={inputCls} /></Field>
            <ModalButtons busy={busy} onCancel={() => setShowSubmit(null)} label="Post Bond & Submit" />
          </form>
        </Modal>
      )}

      {/* CHALLENGE */}
      {showChallenge && (
        <Modal title="Challenge the Verdict" onClose={() => setShowChallenge(null)}>
          <div className="bg-purple-950/30 border border-purple-800/40 rounded-xl p-3 text-xs text-purple-200 mb-4">Post a bond of at least {toGen(showChallenge.builder_bond)} GEN. A new rebuttal URL is read on-chain during a final re-review.</div>
          <form onSubmit={doChallenge} className="space-y-4">
            <Field label="Rebuttal / evidence URL (https)"><input value={cUrl} onChange={(e) => setCUrl(e.target.value)} type="url" className={inputCls} /></Field>
            <Field label="Note"><textarea value={cNote} onChange={(e) => setCNote(e.target.value)} rows={2} required className={inputCls} /></Field>
            <ModalButtons busy={busy} onCancel={() => setShowChallenge(null)} label={`Post ${toGen(showChallenge.builder_bond)} GEN & Challenge`} />
          </form>
        </Modal>
      )}

      <footer className="border-t border-gray-800 text-center py-4 text-[11px] text-gray-600">
        GrantLock · Intelligent Contract on GenLayer studionet · deployed at <span className="font-mono">{short(GRANTLOCK_CONTRACT)}</span>
      </footer>
    </div>
  );
}

const inputCls = 'w-full bg-gray-950 border border-gray-800 rounded-xl p-3 text-sm text-gray-100 focus:outline-none focus:border-violet-500';

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (<div><label className="block text-xs font-semibold text-gray-300 mb-1">{label}</label>{children}</div>);
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-gray-900 border border-gray-800 rounded-3xl max-w-lg w-full p-6 sm:p-8 space-y-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between"><h3 className="text-lg font-bold text-white">{title}</h3><button onClick={onClose} className="text-gray-400 hover:text-white text-xl leading-none">&times;</button></div>
        {children}
      </div>
    </div>
  );
}

function ModalButtons({ busy, onCancel, label }: { busy: boolean; onCancel: () => void; label: string }) {
  return (
    <div className="pt-2 flex gap-3">
      <button type="button" onClick={onCancel} className="flex-1 bg-gray-800 hover:bg-gray-700 text-white text-xs font-semibold py-3 rounded-xl transition">Cancel</button>
      <button type="submit" disabled={busy} className="flex-1 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white text-xs font-bold py-3 rounded-xl transition">{busy ? 'Submitting…' : label}</button>
    </div>
  );
}

function StateBadge({ state }: { state: string }) {
  return <span className={`px-2.5 py-0.5 rounded-full font-semibold text-[10px] border ${STATE_STYLES[state] || 'bg-gray-700/30 text-gray-300 border-gray-700'}`}>{state}</span>;
}

function Empty({ icon, title, sub }: { icon: React.ReactNode; title: string; sub: string }) {
  return (
    <div className="text-center py-16 bg-gray-900/30 rounded-2xl border border-gray-800/60">
      {icon}
      <h3 className="text-base font-semibold text-gray-300">{title}</h3>
      <p className="text-xs text-gray-500 mt-1">{sub}</p>
    </div>
  );
}
