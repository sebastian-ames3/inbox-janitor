# Inbox Janitor — Agreed Direction (Summary)

_Last updated: Oct 25, 2025_

## 1) What we’re building
A **headless, background email hygiene service** that keeps important mail front‑and‑center while quietly cleaning the rest. **Email-only UX**: users configure once and receive summaries/actions **via email**—no app or portal required (a minimal web page exists only for export/consent).

## 2) Delivery model (agreed)
- **Primary:** **Headless SaaS + Email-only UI** (Gmail first, Microsoft 365 next). Server subscribes to mailbox changes; users interact via emails (welcome, summaries, receipts, undo).
- **Not primary for MVP:** Mail-client plug‑ins (Gmail/Outlook/Apple Mail). Useful later for convenience (inline explain/undo), but **not** required for background automation.
- **Optional later:** Local desktop agent for “privacy‑max” users; deferred until traction.

## 3) User experience (email-only surfaces)
- **Welcome Email (post-connect):** sandbox mode by default; buttons (signed links) to enable Action Mode, set confidence thresholds, schedule digest.
- **Weekly Summary (inbox):** “Top 5 important”, “Cleaned automatically”, “Borderline to review”. One‑click actions: Undo last 24h, Promote sender, Tighten promos.
- **Action Receipts (optional daily):** counts of archived/trashed/undos; links to Pause or Emergency Stop.
- **Reply Commands:** users can reply with simple commands like `allow domain brand.com`, `block sender`, `lower promos`.
- **Emergency:** email `stop@inboxjanitor.app` pauses all actions and restores from quarantine.
- **Visible labels:** `Janitor/Auto‑Archived`, `Janitor/Quarantine (7d)`, `Janitor/Log`.

## 4) Safety, privacy, and trust
- **Least‑privilege OAuth**; tokens encrypted (KMS); HTTPS only.
- **Data minimization:** store headers/IDs/metadata by default; no message bodies unless user opts in (short cache).
- **Reversible by design:** 7‑day **quarantine before delete**; **30‑day Undo** for actions.
- **Auditability:** immutable audit log; user‑triggered full purge; export available.
- **Kill switches:** per‑user and global pause; email-based Emergency Stop.

## 5) Core features (MVP → V1)
- **Classifier & rules engine** (headers, Gmail categories, unsubscribe headers, sender/domain, thread history).
- **Confidence thresholds:** Auto ≥0.85; Review 0.55–0.84; Ignore <0.55 (user‑tunable).
- **Rules:** allow/block lists; per‑sender/domain actions via email commands.
- **Sandbox first;** **Action Mode** (archive/move/trash) opt‑in.
- **Weekly digest** delivered by email; no separate app.
- Minimal web page only for **consent, export, and account deletion**.

## 6) Integrations & scopes
- **Gmail (MVP):** `gmail.readonly` (sandbox), `gmail.modify` (action), `gmail.metadata` (optional). **Push watch + history delta** for changes.
- **Microsoft 365 (V1):** `Mail.Read` (sandbox), `Mail.ReadWrite` (action). **Change notifications + delta query** for continuity.
- **Email delivery:** Postmark/SendGrid with **signed, expiring magic links**.

## 7) Architecture (at a glance)
```
OAuth (Google/M365) -> Auth -> Token Vault (KMS)
        Gmail Push / M365 Webhooks -> Ingest -> Queue
        Queue -> Classifier -> Rules Engine -> Action Executor
        -> Mailbox (archive/move/quarantine) -> Digest Builder -> Email
        Storage: Postgres (events, decisions), Redis (jobs, locks)
        Observability: logs, traces, SLOs; Kill switches
```

## 8) Guardrails & defaults
- **No hard delete automation.** Trash flows through **Quarantine (7d)**.
- **Retention:** Message metadata 30d; decisions/digests 90d; audit logs 1y (exportable).
- **Undo latency target:** <5 seconds; webhook‑to‑action P95 <60 seconds.
- **Transparency:** every automated action is reflected in a receipt or digest.

## 9) Pricing (tentative; to test)
- **Starter $6/mo:** 1 mailbox, Sandbox + Weekly Summary + Action Receipts, 30‑day logs.
- **Pro $12/mo:** 2 mailboxes, Action Mode + Undo/Quarantine, per‑sender rules, export.
- **Team $20/user/mo:** shared policies, multi‑mailbox, audit exports, priority support.

## 10) Success metrics
- **North Star:** hours of inbox time saved per user/week.
- **Inputs:** triage precision (1−undo rate), % messages auto‑handled, digest CTR, D14/D30 retention, ARPU.

## 11) Near‑term roadmap (solo‑founder friendly)
- **Weeks 0–2:** OAuth + Gmail watch; Sandbox ingest; email templates (welcome, summary, receipts); audit log.
- **Weeks 3–4:** Rules via email commands; thresholds tuning; metrics pipeline; Stripe.
- **Weeks 5–6:** Action Mode + Undo/Quarantine; safety kill switches; limited beta.
- **Weeks 7–8:** Microsoft 365 change notifications + delta; refine digests; optional Slack alerts (Pro).

## 12) Open items (for later decisions)
- Lightweight Gmail/Outlook add‑ins (inline “why/undo”) for V1+.
- Privacy‑max local agent (deferred); pricing for that tier.
- Team admin policies & role management.
- Exact digest default schedule; localization.
- Referral program (“Give 1 month, get 1 month”).

---

**Source repo:** https://github.com/sebastian-ames3/inbox-janitor
