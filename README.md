# Hackathon Project: Adaptive KYC Engine

AI-driven KYC onboarding and compliance engine — behavioral fraud detection, jurisdiction-aware identity verification (eKYC for Country A, ID-only for Country B), and an OSINT compliance agent (OFAC sanctions, adverse media, court records) built with LangGraph.

Built for the HCLTech × UBC AI/ML Hackathon, Use Case #06 (Banking/FinTech).

## Prerequisites

- [uv](https://docs.astral.sh/uv/) for Python package management
- Homebrew (macOS) for installing Tesseract and Ollama
- An Ollama-compatible local LLM for OSINT risk summarization
- A CourtListener API token (free) for court records checks: https://www.courtlistener.com/help/api/rest/

## Setup

1. Install uv:

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Clone the repo and cd in:

```
git clone git@github.com:raymondww/kyc-onboarding-engine.git
cd kyc-onboarding-engine
```

3. Install dependencies:

```
uv sync
```

4. Install Tesseract (used for ID OCR):

```
brew install tesseract
```

5. Install and start Ollama, then pull the model used for risk summarization:

```
brew install ollama
brew services start ollama
ollama pull gemma3:4b
```

`brew services start ollama` runs Ollama in the background permanently, so you don't need to keep a terminal open with `ollama serve`. If you'd rather run it on-demand, `ollama serve` works too, just remember to start it before running the app.

6. Create your `.env` file and add your CourtListener token:

```
cp .env.example .env
```

Then open `.env` and set `COURTLISTENER_API_TOKEN` to your token.

## Generate synthetic demo data

The repo only tracks sample source faces (`data/synthetic/source_faces/`). Everything else under `data/synthetic/` is generated locally:

```
uv run python src/data_generation/generate_profiles.py
uv run python scripts/generate_synthetic_kyc_data.py
```

The second script pins any non-"random-person" photo in `data/synthetic/source_faces/` (e.g. your own selfie) to a guaranteed-pass Country A identity, so you can test the full webcam-capture flow against your own face.

## Run the app

```
cd backend
uv run uvicorn app.main:app --reload
```

Then open http://localhost:8000 to use the onboarding demo (fraud check → document upload → live pipeline progress).

## Run the CLI batch demo

```
uv run python scripts/run_onboarding_demo.py
```

## Notes

- `opencv-python` is pinned below v5 for compatibility.
- The liveness check is a heuristic, not a production-grade liveness model.
- Country B ("Video KYC" in `cdd_configs.json`) is implemented as ID-only verification (no webcam), by design for this demo's scope.
- `architecture_diagram.svg`/`.png` and `kyc_pitch_deck.pptx` in the repo root are the hackathon deliverables (architecture diagram and 3-minute pitch deck).
