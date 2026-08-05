# Jarvis DESIGN.md

## 1) Visual Theme & Atmosphere

- Product type: personal trading cockpit for A-share decision support.
- Target mood: calm, professional, data-first, low-noise.
- Style keywords: fintech dashboard, institutional trust, compact clarity.
- Avoid: oversized glow, excessive gradients, gaming/cyberpunk overload.

## 2) Color Palette & Roles

### Dark Theme

- `bg-canvas`: `#0b1020` - app background
- `bg-surface`: `#161b22` - cards/panels
- `bg-surface-hover`: `#1c2128`
- `border`: `#30363d`
- `text-primary`: `#c9d1d9`
- `text-secondary`: `#8b949e`
- `text-strong`: `#f0f6fc`
- `primary`: `#58a6ff`
- `primary-soft`: `rgba(88, 166, 255, 0.12)`
- `success`: `#3fb950`
- `success-soft`: `rgba(63, 185, 80, 0.12)`
- `danger`: `#f85149`
- `danger-soft`: `rgba(248, 81, 73, 0.12)`
- `warning`: `#d29922`
- `warning-soft`: `rgba(210, 153, 34, 0.12)`

### Light Theme

- `bg-canvas`: `#f3f6fb`
- `bg-surface`: `#ffffff`
- `bg-surface-hover`: `#f6f9ff`
- `border`: `#d7e0ec`
- `text-primary`: `#1f2f45`
- `text-secondary`: `#607089`
- `text-strong`: `#0f223a`
- `primary`: `#3f6fb4`
- `primary-soft`: `rgba(63, 111, 180, 0.12)`
- `success`: `#207a57`
- `danger`: `#d14f4f`
- `warning`: `#b6782a`

## 3) Typography Rules

- Base font family: system sans stack.
- Base text size: `14px`.
- Header brand: `18px`, weight `600`.
- Section title: `15px`, weight `700`.
- Body: `13-14px`.
- Assistive/meta text: `11-12px`.
- Numeric values should use stable spacing and clear contrast.

## 4) Component Stylings

- Buttons:
  - Radius `8px`, subtle border.
  - Primary button uses `primary-soft` background in dark mode.
  - Hover state changes border/text first, avoid heavy glow.
- Cards/Panels:
  - Radius `10px`.
  - Border visible at all times for data-density readability.
- Inputs:
  - Border-led focus with `primary` color.
  - Keep background close to surface color.
- Badges/Chips:
  - Use soft semantic backgrounds, never pure neon.

## 5) Layout Principles

- Keep dashboard compact and information-dense.
- Major spacing scale: `4 / 8 / 12 / 16 / 24`.
- Sidebar and content should preserve predictable alignment.
- Sticky regions (header/filter) keep strong contrast with body.

## 6) Depth & Elevation

- Prefer border + tiny shadow over large blur.
- Base card shadow should be subtle (`0 2px 10px` low opacity range).
- Reserve stronger shadow only for overlays and drawers.

## 7) Do's and Don'ts

### Do

- Keep semantic colors consistent across cards, tables, and dialogs.
- Prioritize readability over visual effect intensity.
- Maintain clear states for stale/loading/error.

### Don't

- Don't mix multiple accent systems in the same page section.
- Don't rely on color alone for critical status; keep text labels.
- Don't introduce heavy motion in data-dense screens.

## 8) Responsive Behavior

- `<= 960px`: sidebar becomes top stacked module.
- `<= 640px`: chat drawer becomes full width.
- Touch targets maintain minimum `32px` effective height.

## 9) Agent Prompt Guide

- "Use Jarvis DESIGN.md with compact fintech styling."
- "Prefer restrained elevation, crisp borders, and semantic status chips."
- "Keep dark/light parity for all core components."
