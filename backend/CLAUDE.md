# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`brainpace` backend: a FastAPI service that pulls single-channel EEG from the
AWEAR B2B API and derives **mood**, **tiredness**, and **cognition** metrics from
frequency-band power. The AWEAR API exposes one channel (RIGHT_TEMP / TP10) as
256 samples @ 256 Hz per record (1 s of signal); all "bands" are split out of
that single channel via FFT band-pass.

The git repo root is `brainpace/`, but all backend work happens in `backend/`.
Run every command below from `backend/`.

## Commands

```bash
uv sync                                   # install/sync deps (incl. dev group)
uv run fastapi dev app/main.py            # dev server + reload; OpenAPI at /docs
uv run fastapi run app/main.py            # production server
uv run scripts/pull_today_bands.py        # batch: dump today's per-band CSVs to artifacts/
uv run ruff check                         # lint
uv run ruff format                        # format
uv run ty check                           # type-check (Astral's `ty`)
```

The batch script takes `--tz`, `--date YYYY-MM-DD`, `--participants P-A,P-B`, `--out DIR`.
There is no test suite yet.

Requires `AWEAR_API_KEY` in `backend/.env` (see `.env.example`). Python 3.14.

## Architecture

A request flows top-to-bottom through these layers; the dependency direction is
strictly downward (routes → services → clients/signal/analysis → core):

- **`app/main.py`** — `create_app()` builds the FastAPI app and registers every
  router. Add a new endpoint group by creating `app/api/routes/<x>.py` with a
  `router = APIRouter(...)` and including it here.
- **`app/api/routes/`** — thin routers, one per concern (health, members, mood,
  tiredness, cognition, live, summary). They parse query params, call a service,
  and shape a pydantic response. No signal math lives here.
- **`app/api/deps.py`** — `get_awear_client` yields a per-request `AwearClient`
  and closes it after; injected into routes via `Depends`.
- **`app/services/eeg.py`** — the orchestration glue and the *only* place the
  AWEAR client, signal, and analysis layers meet. Owns the pull→band-power
  pipeline, caching, and the `bucket_means` downsampler.
- **`app/clients/awear.py`** — async AWEAR client (`/members`, `/members/{id}/data`)
  with cursor pagination and 429 backoff. Raises `AwearError`.
- **`app/signal/bands.py`** — pure signal math: `BANDS` registry (delta…gamma),
  FFT band-pass (`split_bands`), and band-power features (`band_powers`,
  `aggregate_band_powers`).
- **`app/analysis/{mood,tiredness,cognition}.py`** — heuristic estimators that map
  band powers → metrics. **All thresholds/ratios are uncalibrated placeholders**
  (noted in each module's docstring); treat them as a baseline to replace, not
  ground truth.
- **`app/core/`** — `config.py` (pydantic `Settings` via `get_settings()`,
  lru-cached), `cache.py` (SQLite TTL cache), `timewindow.py` (day/recent window
  builders + `parse_duration`).
- **`app/models/schemas.py`** — pydantic request/response models.

## Conventions and cross-cutting behavior

- **Per-second-first, then bucket.** Cognition ratios and band metrics are
  computed *per EEG record* (1 Hz) and only then averaged into display buckets —
  never the reverse. So `bucket=1s` returns the raw per-second analysis unchanged.
  Preserve this ordering when adding metrics (see `routes/cognition.py`).
- **Ingestion lag.** AWEAR data lands ~`data_delay_seconds` (default 300s) late,
  so "live"/recent windows are shifted back by that much (`recent_window`) to land
  on data that has actually arrived. "Live" means the latest available record in
  the window, not a realtime stream.
- **Caching.** Day-aggregate endpoints (`/summary`, `/mood`, `/tiredness`) share a
  SQLite TTL cache at `artifacts/cache.db`, keyed `bandpowers:{pid}:{date}:{tz}`,
  to spare the rate-limited AWEAR API during demo polling. Live/cognition-series
  endpoints are *not* cached. Set `cache_ttl_seconds=0` to disable; delete
  `cache.db` to reset.
- **Registries extend without plumbing.** Adding an entry to `signal/bands.py`
  `BANDS` or `analysis/cognition.py` `RATIOS` flows through the service and API
  automatically — no other file needs editing.
- **AWEAR rate limits** are real: 60 req/min for raw EEG `data`, 500 req/min
  general, plus a monthly GB quota. The client already retries on 429; avoid
  adding tight polling loops. Full contract in `../docs/awear-api.md`.
- **`scripts/pull_today_bands.py` is intentionally standalone** — it re-implements
  the band-pass/pagination logic with `requests` instead of importing from `app/`,
  so it can run as a self-contained data-export tool. Changes to the app's signal
  logic are not automatically reflected there.
- `artifacts/` (CSV dumps, `cache.db`) is git-ignored data. The packaged module is
  `app` only (`pyproject.toml` scopes discovery to `app*`).
- Every module uses `from __future__ import annotations`.
