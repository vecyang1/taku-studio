# Design System - Taku Studio (`26.10.02-taku-studio`)

> Design system and brand/UI source of truth for Taku Studio.

## Creative North Star

- **Audience**: Growth engineers, marketers, and site operators configuring web engagement popups and notification banners across multi-tenant website spaces.
- **Product Feeling**: Sleek, high-precision engineering cockpit with instantaneous feedback, real device simulation, and zero-drift API truth.
- **Visual Mood**: Clean Zinc/Slate Dark-Tinted Surface (`#090d16` background, `#111827` cards) with electric indigo accent (`#4f46e5` / `#3345ee`), emerald operational indicators (`#10b981`), and amber warnings (`#f59e0b`).
- **Forbidden / Invariants**:
  - NO emojis anywhere in the UI (per workspace rule: forbidden as UI icons).
  - Premium SVG Lucide icons exclusively.
  - No fake mock state: Unidirectional data flow (Read = Taku API -> Store -> Render; Write = UI -> Taku API -> Authoritative Re-fetch -> Re-render).

## Tokens

| Token | Value | Role |
| --- | --- | --- |
| `--bg-base` | `#0b0f19` | Deep charcoal canvas background |
| `--bg-surface` | `#111827` | Card, sidebar, and container background |
| `--bg-surface-elevated` | `#1f2937` | Hover states, active items, tooltips |
| `--border-subtle` | `#1e293b` | Borders, subtle dividers |
| `--border-focus` | `#4f46e5` | Active focus rings and highlighted controls |
| `--text-primary` | `#f9fafb` | Primary readable copy and headings |
| `--text-secondary` | `#9ca3af` | Secondary labels, timestamps, metadata |
| `--text-muted` | `#6b7280` | Placeholders, inactive captions |
| `--color-primary` | `#4f46e5` | Core brand indigo, primary buttons |
| `--color-primary-hover`| `#4338ca` | Primary button hover |
| `--color-success` | `#10b981` | Online status, enabled toggles, pass results |
| `--color-warning` | `#f59e0b` | Retrigger notice, paused campaigns, cautions |
| `--color-danger` | `#ef4444` | Delete action, API errors, rule rejection |

## Typography

- **Font Family**: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif.
- **Monospace Family**: "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace (used for IDs, URLs, JSON, project keys).
- **Scale**:
  - Display Title: 1.25rem (20px), font-weight 600, tracking -0.02em
  - Section Header: 0.95rem (15px), font-weight 600, uppercase, tracking 0.05em
  - Body Text: 0.875rem (14px), font-weight 400, line-height 1.5
  - Caption / Metadata: 0.75rem (12px), font-weight 500, line-height 1.4

## Components

| Component | Rules |
| --- | --- |
| **Device Frame Switcher** | Desktop (1280px / 100%), Tablet (768px), Mobile (375px iPhone). Frame features realistic device bezel, subtle radius, and centered positioning. |
| **Campaign Card** | Dense, informative card showing: Title, ID badge, Type badge, Live Views count, Active/Paused switch, and condition summary. |
| **Interactive Preview** | Renders realistic popup cards with high-fidelity typography, image ratio maintenance, interactive input fields, and submit simulation with Albato webhook routing feedback. |
| **Inspector Tabs** | Segmented pill control: `Inspector`, `Trigger Simulator`, `Embed Snippet`, `Diagnostic Log`. |
| **Trigger Simulator** | Test input URL field with instant rule evaluation against active conditions (`startsWith`, `contains`, `eq`, `delay`, `retrigger`). Displays green pass or red fail badge with matching rationale. |
| **Embed Code Box** | One-click copy with toast notification, syntax-highlighted HTML script tag, and direct link to CDN. |

## Layout And Responsiveness

- **Desktop (>= 1200px)**: 3-column cockpit:
  - Left column (340px fixed): Space switcher, campaign list, filters.
  - Middle column (flex 1): Device viewport simulator with zoom/device bar.
  - Right column (380px fixed): Comprehensive Inspector & Trigger Simulator.
- **Tablet / Laptop (800px - 1199px)**: 2-column layout (Campaign list on left, preview & inspector tabbed on right).
- **Mobile (< 800px)**: Single column with sticky bottom navigation tabs (Campaigns, Preview, Inspector).
- **Touch Targets**: Minimum 44x44px for buttons and interactive controls.

