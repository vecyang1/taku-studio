# Changelog

All notable changes to **Taku Studio** (`26.10.02-taku-studio`) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.1.1] - 2026-10-02

### Added
- **GitHub Actions CI Workflow**: Added `.github/workflows/ci.yml` for automated testing on push and pull requests on `main`.
- **Docker Containerization**: Added multi-stage `Dockerfile` and `docker-compose.yml` for containerized zero-setup deployment.

## [1.1.0] - 2026-10-02

### Fixed
- **OpenAPI Operators Coverage**: Added full support in `evaluator.py` for all 8 OpenAPI operators (`wildcard`, `notWildcard`, `notStartsWith`, `notContains`, `eq`, `notEq`, `startsWith`, `contains`) plus regex.
- **Root URL Wildcard Matching**: Fixed evaluator failure where root URL rules with trailing slashes (`operator: wildcard`, `value: http://example.com/`) falsely failed against subpath visitor URLs.
- **Device Schema Alignment**: Corrected device condition evaluation to inspect OpenAPI schema property `device` in addition to fallback `value`.
- **Hallucinated Form Block Suppression**: Fixed preview engine so announcement banners and informational cards without form blocks do not hallucinate fake email input fields.
- **Announcement Banner Surface**: Built dedicated `.taku-banner-bar` rendering at top/bottom of mock viewport adhering to `banner_configuration` (background color, text color, position).
- **Proxy-Resilient E2E Server Fixture**: Fixed E2E test harness to automatically launch and manage server instances while bypassing macOS proxy interception.

### Added
- **Full Campaign Lifecycle in UI**:
  - Implemented interactive "New Campaign" modal dialog (`#createCampaignModal`) connected to `POST /api/spaces/{space_id}/popups`.
  - Added "Delete Campaign" button in Inspector (`#btnDeleteCampaign`) connected to `DELETE /api/popups/{popup_id}` with authoritative re-sync.
- **Dynamic Popup Sandbox Harness**: Rebuilt `static/preview_sandbox.html` to dynamically fetch and render any campaign via `?popup_id=...` or cross-frame `postMessage`.
- **Exit Intent & Location Targeting**: Extended evaluator and UI simulator to support simulating exit intent gestures and ISO country code filters.
- **Primary Domain Metadata**: Extended `SpaceInfo` and space catalog with primary domain mapping support.

## [1.0.0] - 2026-10-02

### Added
- Initial release of **Taku Studio**: A customer-facing, production-grade management and observability platform for Taku (taku.cool) popups, spaces, and widgets.
- Backend server powered by `aiohttp.web` with typed REST endpoints:
  - Space switching & discovery (`/api/spaces`)
  - Campaign CRUD operations with live re-read (`/api/spaces/{id}/popups`, `/api/popups/{id}`)
  - Live diagnostic health checker (`/api/diagnose`)
  - Audience & Trigger Simulator (`/api/simulate`) for testing page URL matchers and conditions
  - Embed snippet & standalone public feed generator (`/api/snippet/{id}`)
  - Realtime SSE live update event stream (`/api/live-stream`)
- Modern, high-craft Web UI:
  - Responsive multi-device simulator frame (Desktop 1280px, Tablet 768px, Mobile 375px)
  - Interactive popup card renderer displaying real typography, images, and lead capture forms
  - Form submission test runner with feedback and Albato webhook inspection
  - Complete Inspector panel (Display Type, Delay, Priority, Retrigger limits, Conditions)
  - Audience & Trigger Simulator testing real customer match rules
  - Copyable embed scripts and direct feed previews
  - System diagnostics with API latency, key masking, and live SSE activity logs
  - Pure SVG Lucide icons (zero emojis) and accessible zinc/slate color system
- CLI integration:
  - Embedded `studio` subcommand in `taku-ops` CLI (`python3 taku_cli.py studio`)
- End-to-end and unit testing suite:
  - Unit tests with `pytest`
  - Playwright E2E tests executing real browser interactions on desktop and mobile viewports with screenshots
