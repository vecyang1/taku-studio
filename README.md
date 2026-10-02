# Taku Studio (`taku-studio`)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![CI](https://github.com/vecyang1/taku-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/vecyang1/taku-studio/actions)

> Production-grade Management, Observability, and Interactive Preview Studio for [Taku](https://dashboard.taku.cool) website popups, banners, and engagement widgets.

---

## 1. Architectural Highlights & Invariants

1. **Single Source of Truth (SSOT)**:
   - Data is truth; the upstream Taku REST API (`https://api.taku.cool/v1`) is the authoritative source; the Studio UI is its real-time projection.
   - Spaces and project keys are mapped in `space_catalog.py` with multi-tenant configuration support.
2. **Unidirectional Data Flow**:
   - **Read Flow**: Taku API -> Backend REST -> Store -> Frontend UI.
   - **Write Flow**: UI -> Backend REST -> Taku API -> Authoritative Re-read -> Re-render.
   - Never trust local optimistic state: every mutation confirms by re-fetching the authoritative object from the upstream server.
3. **UI Observability Mandate**:
   - Any configured business rule must be inspectable and auditable.
   - The embedded **Audience & Trigger Evaluator** (`evaluator.py`) executes the identical business logic used by production scripts (`startsWith`, `contains`, `eq`, `wildcard`, `notEq`, `notStartsWith`, `notWildcard`, `notContains`, `regex`, `exit_intent`, `location`, `device`).
4. **Push-Based Realtime Synchronization**:
   - Server-Sent Events (SSE) stream (`/api/events`) broadcasts live mutation events (`popup_toggled`, `popup_updated`, `popup_created`, `popup_deleted`, `diagnose_checked`) to connected clients with automatic heartbeat resilience.
5. **Multi-Viewport Device Simulator**:
   - High-fidelity interactive preview supporting **Desktop (1024px)**, **Tablet (768px)**, and **Mobile (375px)** viewports.
   - Distinct rendering modes: Centered modal cards with dimmed backdrops vs sticky top notification banners (`.taku-banner-bar`).

---

## 2. Multi-Space Catalog Configuration

Taku Studio supports managing multiple customer spaces. By default, it ships with clean demo workspaces and dynamically loads configured spaces from `.spaces.json` or the `TAKU_SPACES_FILE` environment variable:

| Space ID | Name | Slug | Public Project Key | Primary Domain |
|---|---|---|---|---|
| **1001** | E-Commerce Store | `demo-store` | `demo_pk_9a8b7c6d5e4f3a2b1c0d` | `store.example.com` |
| **1002** | SaaS Web Application | `demo-saas` | `demo_pk_1f2e3d4c5b6a7b8c9d0e` | `app.example.com` |
| **1003** | Digital Media Hub | `demo-media` | `demo_pk_3b4c5d6e7f8a9b0c1d2e` | `media.example.com` |

### Custom Spaces Configuration

To configure your own spaces, copy `.spaces.example.json` to `.spaces.json`:

```bash
cp .spaces.example.json .spaces.json
```

Edit `.spaces.json` with your real Taku Space IDs and Public Project Keys (found under **Space Settings > Embed Code** in your Taku Dashboard). `.spaces.json` is ignored by Git by default to protect private account information.

---

## 3. Quick Start

### Installation
```bash
git clone https://github.com/vecyang1/taku-studio.git
cd taku-studio
pip install -r requirements.txt
cp .env.example .env
# Edit .env and supply your TAKU_API_KEY
```

### Start Server

```bash
python3 server.py --port 8765
```
Open [http://127.0.0.1:8765](http://127.0.0.1:8765) in any modern browser.

### Run with Docker

```bash
docker compose up -d
```

---

## 4. API Endpoints

- `GET /api/health` — Basic service status.
- `GET /api/diagnose` — Deep diagnostic across API keys and all spaces.
- `GET /api/spaces` — Lists configured spaces and embed snippets.
- `GET /api/spaces/{space_id}/popups` — Queries live popups for a space.
- `GET /api/popups/{popup_id}` — Retrieves full authoritative popup JSON.
- `POST /api/popups/{popup_id}/toggle` — Toggles active state and re-fetches authoritative object.
- `PUT /api/popups/{popup_id}` — Updates campaign configuration and re-fetches.
- `POST /api/spaces/{space_id}/popups` — Creates a new campaign in space.
- `DELETE /api/popups/{popup_id}` — Deletes campaign.
- `POST /api/simulate` — Evaluates audience conditions and trigger rules against URL, exit intent, device, and location.
- `GET /api/snippet/{space_id}` — Gets script embed snippet and feed URL.
- `GET /api/events` — Real-time Server-Sent Events (SSE) push stream.

---

## 5. Verification Record & Test Suite

Run the full automated test suite:
```bash
python3 -m pytest tests/ -v
```

### Captured Visual Evidence

| Viewport | Campaign Mode | Screenshot Reference |
|---|---|---|
| Desktop (1440x900) | Full Studio Cockpit | `screenshots/e2e_taku_studio_desktop.png` |
| Mobile (375px) | Mobile Simulator Preview | `screenshots/e2e_taku_studio_mobile.png` |
| Desktop (1440x900) | Modal Overlay Preview | `screenshots/e2e_taku_studio_modal.png` |
| Desktop (1440x900) | Announcement Banner Preview | `screenshots/e2e_taku_studio_banner.png` |

---

## 6. License

MIT License. Copyright (c) 2026 Vec.
