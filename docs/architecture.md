# Architecture

See `architecture_diagram.svg` / `.png` / `.excalidraw` in the repo root for the visual version. This doc is the text companion.

## Pipeline overview

```
Browser (fraud_demo.html)
  │
  ▼
POST /session/submit  ──────────────►  scorer.py (rule-based fraud gate)
  │                                        │
  │                                   flagged → rejected, stop here
  │                                        │
  │                                   passed
  ▼
POST /kyc/verify (NDJSON streaming)
  │
  ▼
router.py: run_onboarding_steps()
  │
  ├── Country A ("eKYC")                 ├── Country B ("Video KYC" config label)
  │   OCR ID → face match → liveness     │   OCR ID only (no webcam)
  │
  ▼
Identity cross-check (form name/DOB vs OCR'd ID fields, fuzzy match)
  │
  │  mismatch or doc failure → rejected, stop here
  ▼
run_agent.py (LangGraph OSINT agent)
  │
  ├── OFAC SDN check (rapidfuzz name/DOB match)
  │     └── HIGH-confidence hit → fast path, skip news search
  ├── Adverse media search (DuckDuckGo) → domain filter
  ├── Court records check (CourtListener)
  └── Ollama LLM risk summary → risk_flag (LOW/MEDIUM/HIGH)
  │
  ▼
Final decision: approved / review / rejected
```

## Why two countries route differently

`cdd_configs/cdd_configs.json` drives everything. Country A requires `biometric_required: true` (government ID + selfie, full eKYC: OCR, face match, liveness score). Country B has `biometric_required: false` (ID-only — no webcam, no face match). `src/regulatory_engine/cdd_validator.get_cdd_config(country)` is the single place that reads this config; `router.py` branches on `verification_method` ("eKYC" vs "Video KYC") to decide which checks to run. Adding a third country means adding one more entry to the JSON and one more `elif` branch — no other code changes.

## Why the fraud gate runs before document upload

Rejecting bot-like submissions at the cheapest point (before any file upload, OCR, or OSINT call) keeps the expensive part of the pipeline reserved for plausibly-real applicants. `src/fraud_scorer/scorer.py` is deliberately not ML-based — it's a two-signal rule: was any field pasted, or was typing suspiciously fast (`< 60ms` mean gap) *and* suspiciously uniform (`< 15ms` stddev)? Either alone isn't flagged; a slow, steady typist is still human, and a single fast keystroke pair is noise. This replaced an earlier IsolationForest model trained on a feature (`device_fingerprint_score`) the frontend never actually measured — see `src/fraud_scorer/scorer.py`'s docstring.

## Why /kyc/verify streams NDJSON instead of returning one response

The frontend shows a live step-by-step checklist ("Extracting information from ID... complete", "Running background check... pass") that has to reflect what the backend is *actually* doing at that moment, not a fake progress bar. `router.py`'s `run_onboarding_steps()` is a generator that yields one `{"event": "step", ...}` dict per stage as it happens (each one also `print()`s to the terminal from the same call site, so backend console and frontend UI never say different things), then a final `{"event": "result", ...}`. `kyc_routes.py` wraps that generator in a `StreamingResponse`. `run_onboarding()` (used by the CLI batch script) just drains the same generator and returns the last event — one implementation, two consumption modes, no duplicated business logic.

## Data flow / storage

| File | Written by | Contents |
|---|---|---|
| `data/session_logs.jsonl` | `session_routes.py` `/submit` | every form submission + fraud verdict (backlog, not shown to user) |
| `data/kyc_logs.jsonl` | `kyc_routes.py` `/verify` | every document-verification result (OCR fields, face match, liveness, OSINT summary) |
| `data/uploads/<name>_<timestamp>/` | `kyc_routes.py` | uploaded ID + selfie images, one folder per submission |
| `data/raw/sdn.csv` | downloaded manually (OFAC SDN list) | sanctions list used by `ofac_check.py` |
| `data/synthetic/` | `src/data_generation/generate_profiles.py`, `scripts/generate_synthetic_kyc_data.py` | generated synthetic identities, IDs, selfies (gitignored except `source_faces/`) |

## Known scope limits (see pitch deck closing slide)

- Sanctions/PEP screening covers OFAC only — no UN/EU blocklists or a distinct PEP flag yet.
- Country B is ID-only, not a live video call — "Video KYC" is the config's label, not yet the literal feature.
- Liveness is a heuristic proxy score, not a production-grade liveness model.
