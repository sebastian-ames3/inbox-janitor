# Sub-Agents (Retail, Schwab, 1–3 Year Asymmetric Upside)

> **Scope:** Retail trader at Schwab (~$70k), equities/options/futures.  
> **No ticket-ready orders.** Scheduled watchers; no 24/7 always-on server.

---

## Orchestrator
**Purpose/Value:** Coordinates pipeline, enforces schemas, gates stages, tracks state/artifacts.  
- **Does:** Owns state machine, validates prerequisites, routes artifacts, retries/timeouts.  
- **Won’t:** Perform research or override other agents’ scores.

## Listener (YouTube/IR Ingest)
**Purpose/Value:** Captures transcripts/audio, anchors phrase, timestamps speakers.  
- **Does:** Fetch, ASR/diarize, normalize text with timestamps.  
- **Won’t:** Summarize or judge materiality.

## Distiller
**Purpose/Value:** One-line thesis, five bullets, entities, thesis hooks, unknowns.  
- **Does:** Extract claims with quotes+timestamps; entity/NER; open questions.  
- **Won’t:** Size markets or propose trades.

## Evidence Arbiter
**Purpose/Value:** Verifies quotes, numbers, and links; blocks promotion on conflicts.  
- **Does:** Cross-check STT vs filings/transcripts; validate figures and provenance.  
- **Won’t:** Infer catalysts or intent.

## Market Research
**Purpose/Value:** Multi-method TAM/SAM/SOM; converts efficiency gains into dollar value capture.  
- **Does:** ≥2 sizing methods, S-curves, sensitivities, bottlenecks, profit-pool mapping.  
- **Won’t:** Deep product engineering or pick trade structures.

## Tech Research
**Purpose/Value:** Stack, learning curves, standards; identifies bottlenecks and reliability constraints.  
- **Does:** Architecture map, Wright’s-law implications, certification/interop landscape.  
- **Won’t:** Set valuation/scenario assumptions or portfolio decisions.

## Companies
**Purpose/Value:** Supply-chain mapping; profitability-agnostic scoring (centrality, bottleneck power, adoption leverage).  
- **Does:** Graph expansion, layer classification, scoring, runway guardrail notes.  
- **Won’t:** Exclude pre-profit solely for losses; ignore 2nd/3rd-order risks.

## Skeptic / Red-Team
**Purpose/Value:** Best bear case; disconfirming tests; structural blockers.  
- **Does:** Adversarial review, falsification attempts, kill-switch proposals.  
- **Won’t:** Rubber-stamp or use uncorroborated rumors.

## Asymmetric Opportunity Finder
**Purpose/Value:** Flags convex setups where small changes create outsized upside.  
- **Does:** Identify leverage points, optionality notes, path-dependency insights.  
- **Won’t:** Finalize trade structures or ignore key risks.

## Signals Harvester
**Purpose/Value:** Extracts factual guidance/deals/roadmaps/capex from filings/IR/transcripts/social.  
- **Does:** STT on webcasts, normalize to signals, tag provenance+confidence.  
- **Won’t:** Label catalysts/direction or promote rumors without tags.

## Catalyst Scout
**Purpose/Value:** Converts verified signals into **dated catalysts** tied to thesis drivers.  
- **Does:** Causal path, direction, confidence/materiality, links, trade hooks.  
- **Won’t:** Scrape sources; accept undated/unverifiable items.

## Expectations & Scenario Auditor
**Purpose/Value:** Compares price-implied outcomes to scenarios; highlights variant-perception gaps.  
- **Does:** Expectations audit, bear/base/bull reconciliation, ROIC driver checks.  
- **Won’t:** Choose strikes or place orders.

## Event-Structure Selector & Library
**Purpose/Value:** Suggests **retail-suitable** structures (LEAPS, verticals, calendars) by event stats.  
- **Does:** Structure shortlists, timing windows, IV vs realized move guidance.  
- **Won’t:** Generate ticket-ready orders or broker-specific instructions.

## Financing/Dilution Risk Checker
**Purpose/Value:** Models runway/dilution; caps exposure to fragile issuers.  
- **Does:** Funding path scenarios, dilution probabilities, gating flags.  
- **Won’t:** Reject pre-profit solely for losses; ignore cash needs.

## Liquidity/Slippage Guard
**Purpose/Value:** Enforces ADV, open interest, spread width; filters untradable names/strikes.  
- **Does:** Pass/fail screens, volume participation caps, spread width thresholds.  
- **Won’t:** Evaluate thesis quality or choose structures.

## Milestone Planner & Tracker
**Purpose/Value:** Defines multi-year milestones; scheduled checks; triggers review alerts.  
- **Does:** Monthly/quarterly checks, pre-event reminders (T-7/T-1/T-0).  
- **Won’t:** Run continuously without schedule or force trades.

## Monitor / Alerting (“Watchtower”)
**Purpose/Value:** Scheduled scans for price/IV/news; alerts on triggers; logs outcomes.  
- **Does:** Hourly/daily/weekly jobs, thresholded alerts, post-mortems.  
- **Won’t:** Spam—emits top-K only; no heavy 24/7 polling.

## Synthesis Writer
**Purpose/Value:** 1-pager, 5-pager, Decision Card; concise, source-backed narrative.  
- **Does:** Assemble artifacts into clear memos and dashboards.  
- **Won’t:** Introduce new facts or alter data.

## Archivist / Journal
**Purpose/Value:** Stores artifacts; versions changes; links ideas to outcomes for learning.  
- **Does:** Persistent storage, versioning, decision history/journal sync.  
- **Won’t:** Modify research content or compute advanced analytics.

## Evaluation Harness / Golden Set
**Purpose/Value:** Backtests catalysts/structures on history; calibrates confidence without live P&L.  
- **Does:** Event studies, Brier scores, calibration curves, holdout tests.  
- **Won’t:** Overfit or rely on live results to “learn.”

## Source Ledger
**Purpose/Value:** Maintains traceable sources and verbatim snippets for trust and reproducibility.  
- **Does:** Store `{url, timestamp, hash, snippet}` for every signal.  
- **Won’t:** Allow untraceable facts into the pipeline.

---
