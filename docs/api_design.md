# API Design

## `POST /session/submit`

Fraud gate — must pass before document upload is offered.

**Request body** (`OnboardingFormSubmission`): `full_name`, `dob`, `address`, `country` ("Country A" | "Country B"), `typing_cadence_mean_ms`, `typing_cadence_std_ms`, `session_duration_sec`, `mouse_move_count`, `paste_detected`.

**Response** (`SubmissionResult`): `{"status": "passed" | "flagged"}`. Deliberately thin — no risk score, no threshold, no feature values sent back. A bad actor probing the endpoint learns nothing about how close they came to slipping through. Full detail is logged server-side only, in `data/session_logs.jsonl`.

## `POST /session/score`

Same scoring logic as `/submit`, exposed standalone for testing the rule directly without going through the full form flow. Returns `{"is_bot": bool, "reasons": [...]}`.

## `POST /kyc/verify`

Document + identity verification, streamed.

**Request** (multipart form): `id_image` (required file), `selfie_image` (optional file — required for Country A, omitted for Country B), `full_name`, `dob`, `country`.

Country validated against `cdd_configs/cdd_configs.json` *before* the stream opens — an unsupported country returns a normal `400` JSON error (`{"detail": "Unsupported country: ..."}`), not a broken stream.

**Response**: `media_type: application/x-ndjson` — one JSON object per line, streamed as each pipeline stage completes:

```
{"event": "step", "step": "document_check", "message": "Extracting information from ID..."}
{"event": "step", "step": "document_check_done", "message": "ID extraction complete."}
{"event": "step", "step": "face_match", "message": "Matching selfie photo to ID photo..."}
{"event": "step", "step": "face_match_done", "message": "Face match complete."}
{"event": "step", "step": "identity_check", "message": "Verifying form details match ID..."}
{"event": "step", "step": "identity_check_done", "message": "Identity match confirmed."}
{"event": "step", "step": "osint_check", "message": "Running background check (sanctions + adverse media)..."}
{"event": "step", "step": "osint_check_done", "message": "Background check complete (LOW risk)."}
{"event": "step", "step": "finalize", "message": "Submitted successfully."}
{"event": "result", "status": "approved", "reason": null}
```

The final `result` line is intentionally thin too: `status` (`approved` | `review` | `rejected` | `not_implemented`) plus a `reason` string, populated only when the reason is safe to show the client directly (currently just "Selfie image required for eKYC verification." — a client-fixable error, not a signal about how the fraud/OSINT decision was made). The full decision detail (OCR fields, face-match similarity score, liveness score, OSINT risk summary) is written server-side only to `data/kyc_logs.jsonl`.

Country A gets `document_check` → `face_match` → `identity_check` → `osint_check` → `finalize`. Country B skips `face_match` entirely (no selfie collected) and goes straight from `document_check` to `identity_check`.

## Design choices worth flagging in a code walkthrough

- **Why NDJSON, not WebSockets/SSE**: simplest thing that lets the frontend read a live stream with `fetch()` + `response.body.getReader()`, no extra protocol or library needed on either side.
- **Why the same generator backs both the streaming endpoint and the CLI script**: `run_onboarding_steps()` in `src/onboarding_engine/router.py` is the single source of truth for the routing/decision logic. `kyc_routes.py` streams every event it yields; `scripts/run_onboarding_demo.py` calls `run_onboarding()`, a thin wrapper that drains the same generator and keeps only the final result. No business rule is duplicated between a "quiet" and "verbose" code path.
- **Why country validation happens before the stream opens**: once a `StreamingResponse` starts, you can't cleanly return an HTTP error status anymore — the headers are already sent. Validating first means a bad `country` value still gets a normal `400` your frontend's existing error-handling code can catch, instead of a malformed stream.
