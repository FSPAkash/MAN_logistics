# DCW SIOP — Design Language

A portable spec for the "industrial-window" UI aesthetic used in this dashboard. Copy this file into any unrelated project and an agent can rebuild the same look without seeing the original screens.

The feel: a desktop application window (Windows-chrome homage) sitting on a clean white sheet. Dense data tables, monospace numbers, uppercase micro-labels, a single iron-oxide-red accent, hairline borders everywhere. Serious, technical, paper-like. No rounded marketing fluff, no big shadows, no gradients except two specific brand strips.

---

## 1. Core Principles

1. **Light, paper-flat surfaces.** Background is pure white. Chrome (title bar, status bar, table headers) is a barely-off-white (`#FAFAFA`). Depth comes from 1px hairline borders, not shadows. Shadows appear only on floating elements (modals, FAB, dropdowns).
2. **Hairlines, not boxes.** Every division is a 1px border in one of three grays. Cards = 1px border + small radius. Never use heavy borders or drop shadows for in-page structure.
3. **Monospace for data, sans for prose.** All numbers, IDs, codes, timestamps, and "machine" values render in the mono slot with `font-variant-numeric: tabular-nums`. Labels and body copy use the sans stack.
4. **Uppercase micro-labels.** Field labels, table headers, card headers, eyebrows: ~10–11px, uppercase, `letter-spacing: 0.08em`, color `--ink-3`. This is the single most identifying texture of the system.
5. **One accent, used sparingly.** Iron-oxide red (`--accent`) marks the primary action, focus rings, active states, and selection tints. It is never a background wash for large areas. Semantic colors (ok/warn/err) are reserved for status only.
6. **Density over whitespace.** Rows are tight (28px), padding is small (6–12px), font sizes run 10–14px. This is a data tool, not a landing page.
7. **NO left-edge color rails on cards.** Do not put a colored left-border strip / vertical accent bar on cards or rows. Use a tinted background, a halo (box-shadow ring), or an inset accent on a single cell instead. (This is a hard project rule.)

---

## 2. Design Tokens

Drop this `:root` block in verbatim. Colors use OKLCH for the accent/semantic ramp so tints stay perceptually even; hex for neutrals.

```css
:root {
  /* Type — Manrope everywhere, system fallback. Mono slot is ALSO Manrope
     (with tabular figures) — there is no separate monospace typeface. */
  --font-sans: "Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", Tahoma, Arial, sans-serif;
  --font-mono: "Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", Tahoma, Arial, sans-serif;

  /* Surfaces — clean light palette */
  --bg-app:        #FFFFFF;   /* page behind the window */
  --bg-chrome:     #FAFAFA;   /* title bar, status bar, menu strip */
  --bg-card:       #FFFFFF;   /* card / panel base */
  --bg-paper:      #FFFFFF;   /* table / form paper */
  --bg-input:      #FFFFFF;
  --bg-hover:      #F4F4F4;   /* hover row / hover button */
  --bg-stripe:     #FAFAFA;   /* zebra, table headers, sub-panels */

  /* Text ramp, darkest -> lightest */
  --ink:           #111111;   /* primary text, numbers */
  --ink-2:         #3F3F3F;   /* secondary text */
  --ink-3:         #757575;   /* labels, muted, captions */
  --ink-4:         #A8A8A8;   /* faint / disabled / hints */

  /* Borders, lightest -> strongest */
  --line:          #E5E5E5;   /* default hairline */
  --line-2:        #EFEFEF;   /* inner / row hairline */
  --line-strong:   #D0D0D0;   /* dropdown / modal edge */

  /* Accent — iron-oxide red (homage to Pigment Red 101) */
  --accent:        oklch(0.55 0.16 30);   /* primary buttons, focus, active */
  --accent-ink:    oklch(0.42 0.18 30);   /* darker accent for text/hover */
  --accent-soft:   oklch(0.92 0.05 30);   /* soft border on selected chips */
  --accent-tint:   oklch(0.96 0.03 30);   /* selection / focus-ring bg wash */

  /* Semantic — status only, never decoration */
  --ok:            oklch(0.55 0.12 150);
  --ok-soft:       oklch(0.94 0.05 150);
  --warn:          oklch(0.65 0.15 75);
  --warn-soft:     oklch(0.95 0.06 75);
  --err:           oklch(0.55 0.18 25);

  /* Window shadow — the ONLY large shadow, for the app shell / modals */
  --shadow-window: 0 1px 0 rgba(0,0,0,0.03),
                   0 12px 32px -8px rgba(60,40,20,0.18),
                   0 2px 6px rgba(60,40,20,0.08);

  /* Radii — small. Windows are 10px, cards 6px, inputs 4px. */
  --r-window: 10px;
  --r-card:   6px;
  --r-input:  4px;
}
```

### Brand gradient strips (the only gradients allowed)
Two specific decorative strips reuse raw hex (red → yellow), an iron-oxide-to-cadmium nod. Use as a thin top/bottom accent bar on the topbar, modals, and active tabs:

```css
/* full-width split: ~85% red, last ~15% yellow */
background: linear-gradient(to right,
  #a8321a 0, #a8321a 85%, #e8a317 85%, #e8a317 100%);
```

Use it ONLY as a 3–5px horizontal hairline (top of a modal, bottom of the brand bar, under the active tab). Never as a fill.

---

## 3. Typography

| Use | Size | Weight | Transform | Tracking | Color |
|---|---|---|---|---|---|
| Page title (home) | 26px | 700 | none | -0.015em | `--ink` |
| Login hero title | clamp(28–40px) | 700 | none | -0.02em | `--ink` |
| Section heading (`h2`) | 16–19px | 700 | none | -0.01em | `--ink` |
| Card / panel header | 11px | 600 | UPPER | 0.08em | `--ink-2`/`--ink-3` |
| Field label | 11px | 600 | UPPER | 0.08em | `--ink-3` |
| Eyebrow | 11px | 600 | UPPER | 0.16em | `--accent-ink` |
| Table header `th` | 10.5px | 600 | UPPER | 0.08em | `--ink-3` |
| Body / cell | 12.5–13px | 400 | none | 0 | `--ink` |
| Number / mono value | 12–13px | 400–600 | none | 0 | `--ink` (mono) |
| Tiny caption | 10–11px | 400 | none | 0 | `--ink-3`/`--ink-4` |

Global base: `font-size: 14px; line-height: 1.45; letter-spacing: -0.005em;` with `font-feature-settings: "tnum" 1, "ss01" 1;` and `-webkit-font-smoothing: antialiased`.

**Mono rule:** any element holding numbers/codes gets `font-family: var(--font-mono); font-variant-numeric: tabular-nums;`. Title accents (`em`) inside headings are often rendered in mono too — e.g. `<h1>Plan <em>SIOP-204</em></h1>` where the code is mono.

**Eyebrow pattern** (small uppercase kicker above a title, with a short accent bar):
```html
<div class="eyebrow"><span class="bar"></span>SECTION LABEL</div>
```
```css
.eyebrow { display:flex; align-items:center; gap:8px; font-size:11px; font-weight:600;
  letter-spacing:0.16em; text-transform:uppercase; color:var(--accent-ink); }
.eyebrow .bar { width:22px; height:2px; background:var(--accent); }
```

---

## 4. The Window Shell

The whole app lives inside a faux desktop window: title bar → menu strip → body → status bar, filling the viewport.

- **`.titlebar`** — 34px tall, `linear-gradient(180deg,#F8F4EB,#EFE9DB)` (warm parchment), 1px bottom border, 3-column grid `1fr auto 1fr` (logo left, centered uppercase title, window controls right). Title is 12px/600/uppercase/0.04em; an `<em>` inside it goes mono 11px `--ink-3`.
- **`.win-controls button`** — 44px wide, transparent, separated by `border-left: 1px solid --line`. `.close:hover` turns `--err` red with white glyph.
- **`.menustrip`** — 26px, `--bg-chrome`, fake "File Edit View" chrome, 12px text, hover items get `--bg-hover` 3px-radius highlight.
- **`.body`** — `flex:1`, scrolls, `scrollbar-gutter: stable`.
- **`.statusbar`** — 34px, `--bg-chrome`, top border, mono 12px `--ink-3`, horizontal row of `<span>` separated by 1px `.sep` dividers; a live `.dot` (green, with soft ring) signals connected; `.right` group is pushed via `margin-left:auto`.

If the target app isn't "windowed," keep the **status bar** and **uppercase chrome** texture even without the literal title bar — that's what carries the identity.

---

## 5. Components

### Card
```css
.card { background: var(--bg-paper); border: 1px solid var(--line); border-radius: var(--r-card); }
.card-head { height:32px; padding:0 12px; display:flex; align-items:center; gap:8px;
  border-bottom:1px solid var(--line-2); background:var(--bg-stripe);
  font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.08em; color:var(--ink-2); }
.card-body { padding:16px; }
```
A small accent dot (`.dot-r`, 7px, `--accent`) optionally leads a card header. Panels (`.input-panel-inner`, `.master-panel`, `.mo-section`, `.blend-*`) all follow the same recipe: 1px border, 6px radius, a `--bg-stripe` header strip with uppercase label, body padding 12–16px.

### Buttons
Base `.btn`: 36px tall, `--r-input` radius, 1px `--line` border, white bg, 13px/500, `gap:8px` for icon. Active state nudges `translateY(1px)`. Variants:

| Class | Look |
|---|---|
| `.btn-primary` | `--accent` bg, white text; hover → `--accent-ink` |
| `.btn-danger` | transparent, `--err` border+text; hover fills `--err` white |
| `.btn-ghost` | transparent border/bg, `--ink-2` text; hover `--bg-hover` |
| `.btn-sm` | 28px tall, 12px |
| `.btn-auto` (neutral CTA) | white bg, `--ink` border; hover inverts to `--ink` bg / white text |
| `.btn-allocate` (table action) | `--ink` bg white text; hover → `--accent` |

There are two "primary" idioms: **red** (`--accent`, headline actions) and **ink-inverting black** (`--ink`, secondary-but-strong table/toolbar actions). Pick red for the single most important action per screen; ink for the rest.

### Inputs
```css
input, select { height:36px; background:var(--bg-input); border:1px solid var(--line);
  border-radius:var(--r-input); padding:0 10px; color:var(--ink); width:100%; outline:none;
  transition:border-color 120ms, box-shadow 120ms; }
input:focus { border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-tint); }
```
**Focus ring = `--accent` border + 3px `--accent-tint` halo.** Universal. Compact inputs in dense tables drop to 24–30px height, mono font, right-aligned, 2–3px radius. Error inputs: `--err` border + faint red wash `oklch(0.97 0.03 25)`. "Dirty"/edited inputs: `--accent-tint` bg + `--accent` border + `--accent-ink` text.

### Field
```css
.field { display:flex; flex-direction:column; gap:6px; }
.field-label { font-size:11px; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:var(--ink-3); }
.field-hint { font-size:11px; color:var(--ink-4); }
```

### Chip
22px tall, 11px mono, `--bg-hover` bg, 1px `--line-2` border, 11px radius (pill). Status variants drop the border and use the soft tint + saturated text: `.ok`/`.warn`/`.err`/`.accent`. Pattern:
```css
.chip { display:inline-flex; align-items:center; gap:6px; height:22px; padding:0 8px;
  border-radius:11px; font-size:11px; font-family:var(--font-mono);
  background:var(--bg-hover); color:var(--ink-2); border:1px solid var(--line-2); }
.chip.ok   { background:var(--ok-soft);   color:var(--ok);   border-color:transparent; }
.chip.warn { background:var(--warn-soft); color:var(--warn); border-color:transparent; }
.chip.err  { background:oklch(0.96 0.04 25); color:var(--err); border-color:transparent; }
.chip.accent { background:var(--accent-tint); color:var(--accent-ink); border-color:transparent; }
```

### Stat tile
```css
.stat { border:1px solid var(--line); background:var(--bg-paper); border-radius:var(--r-card); padding:10px 12px; }
.stat .label { font-size:10.5px; text-transform:uppercase; letter-spacing:0.08em; color:var(--ink-3); }
.stat .value { font-family:var(--font-mono); font-size:22px; font-weight:600; color:var(--ink); margin-top:2px; }
.stat .unit  { font-size:11px; color:var(--ink-3); font-family:var(--font-mono); }
```
Big mono number, tiny uppercase label above. The signature KPI display.

### Key/Value list
```css
.kv { display:grid; grid-template-columns:110px 1fr; gap:4px 12px; font-size:12.5px; }
.kv dt { color:var(--ink-3); font-weight:500; }
.kv dd { margin:0; color:var(--ink); font-family:var(--font-mono); }
```

### Tooltip dot (`.info-dot`)
14px circle, lowercase `i`/`?`, hover reveals a `::after` tooltip card (mono 11px, white bg, `--line-strong` border, soft shadow, 260px wide) via `data-tip` attribute.

---

## 6. Data Tables (the heart of the UI)

```css
table.lots { width:100%; border-collapse:separate; border-spacing:0;
  background:var(--bg-paper); border:1px solid var(--line); border-radius:var(--r-card); overflow:hidden; }
.lots thead th { background:var(--bg-stripe); border-bottom:1px solid var(--line);
  padding:8px 10px; text-align:left; font-size:10.5px; text-transform:uppercase;
  letter-spacing:0.08em; color:var(--ink-3); font-weight:600;
  position:sticky; top:0; z-index:1; white-space:nowrap; }
.lots tbody td { padding:8px 10px; border-bottom:1px solid var(--line-2);
  font-size:13px; font-family:var(--font-mono); color:var(--ink); white-space:nowrap; }
.lots tbody tr:nth-child(even) td { background:rgba(0,0,0,0.012); }  /* whisper-zebra */
.lots tbody tr:hover td { background:var(--bg-hover); }
.lots tbody tr.selected td { background:var(--accent-tint); }
.lots tbody tr.selected td:first-child { box-shadow:inset 3px 0 0 var(--accent); }
.lots td.num, .lots th.num { text-align:right; }   /* numbers right-align, always */
```

Rules:
- Header row: sticky, `--bg-stripe`, uppercase 10.5px labels.
- Cells: mono, 13px (or 12.5px compact / 4px-pad ultra-compact at `height:28px`).
- Zebra is nearly invisible — `rgba(0,0,0,0.012)`.
- Hover = `--bg-hover`. Selected row = `--accent-tint` bg + an **inset 3px accent on the first cell only** (the allowed way to show a row accent — not a full left rail).
- Numbers: right-aligned, tabular.
- Delta coloring: `.delta-bad` → `--err`, `.delta-good` → `--ok`.
- **Zone divider rows** (`tr.zone-row`): full-width `--bg-stripe` band, uppercase 10px label, top+bottom border — used to group sections inside one table. An "allocated/done" zone tints the band green (`oklch(0.96 0.05 150)`).

### Inline bars
Tiny progress/score bars are 4px tall, `--line-2` track, accent or gradient fill:
```css
.bar { height:4px; background:var(--line-2); border-radius:2px; overflow:hidden; }
.bar > span { display:block; height:100%; background:var(--accent); }
```
A red→amber gradient fill is used for "score": `linear-gradient(90deg, oklch(0.55 0.16 30), oklch(0.78 0.10 50))`.

### Rank badges
22px square, 4px radius, mono 700. `.top1` = solid accent/white; `.top2/.top3` = `--accent-tint` bg / `--accent-ink` text.

---

## 7. Overlays & Modals

```css
.overlay { position:fixed; inset:0; background:rgba(20,20,22,0.45); z-index:200;
  display:flex; align-items:center; justify-content:center; animation:fadeIn 120ms ease-out; }
.dialog { background:var(--bg-card); border:1px solid var(--line-strong); border-radius:8px;
  padding:22px; box-shadow:0 18px 40px rgba(20,20,22,0.18), 0 3px 8px rgba(20,20,22,0.08);
  overflow:hidden; }
@keyframes fadeIn { from{opacity:0} to{opacity:1} }
```
- Scrim is dark ink at 45%.
- Modal radius 8px, `--line-strong` edge, two-layer shadow.
- A modal often gets the **brand gradient strip** as a 3px `::before` bar across its top.
- Header: uppercase mono label, 1px bottom border. Footer: right-aligned button row, 1px top border.
- A PIN/code input idiom: huge mono input, `letter-spacing:0.4em`, centered.

### Dropdowns / typeahead lists
`position:absolute; top:calc(100% + 4px)`, white bg, `--line-strong` border, 4px radius, `box-shadow:0 6px 20px rgba(0,0,0,0.08)`, items 8–12px padding with `--line-2` separators, hover `--bg-hover` / `--accent-tint`.

---

## 8. Motion

Restrained. Standard transitions 80–160ms.
- Buttons: `transform 80ms` (press), `background 120ms`.
- Inputs: `border-color/box-shadow 120ms`.
- Bars filling: `width 160ms ease`.
- Modal in: `fadeIn 120ms`.
- Spinner: 2px ring, `--accent` top, `0.8s linear` spin.
- A floating assistant FAB uses springier easing `cubic-bezier(.34,1.56,.64,1)` and a gentle 5s float — reserve bouncy motion for that one playful affordance only.
- `@keyframes blink { 50% { opacity: .35 } }` for attention pulses (locked/offline dots), used sparingly.

---

## 9. Iconography & Misc

- Icons are inline SVG, `stroke:currentColor; stroke-width:1.8; fill:none; stroke-linecap/linejoin:round`. 1.8 stroke weight is the house standard.
- Custom scrollbars: 10px, `--line` thumb, `--line-strong` on hover.
- Dashed `1px --line` borders signal "draft / preview / locked / editable" zones (e.g. `.coa-mini`, edit dividers, accordion footnotes).
- Tabs: bottom-border underline style. Inactive `--ink-3`, active `--ink` with a 2–3px bottom border (sometimes the brand gradient strip).

---

## 10. Do / Don't

**Do**
- White paper, hairline borders, uppercase micro-labels, mono numbers.
- One red accent for the single primary action; ink-black for strong-secondary.
- Tight density: 28px rows, 10–13px type.
- Soft semantic tints (`*-soft`) for status backgrounds.
- Focus ring = accent border + 3px tint halo, everywhere.

**Don't**
- ❌ Left-edge colored rails / vertical accent strips on cards or rows (hard rule). Use tinted bg, halo, or single-cell inset accent.
- ❌ Big drop shadows on in-page elements (shadows only on shell/modals/FAB/dropdowns).
- ❌ Gradients anywhere except the two brand strips and the parchment titlebar.
- ❌ Large accent-colored fills / hero washes.
- ❌ Rounded "friendly" radii — keep it 4/6/10px.
- ❌ Sans-serif numbers in data contexts — always mono + tabular.
- ❌ Sentence-case or large field labels — they stay uppercase, 10–11px, tracked.

---

## 11. Quick-start checklist for a new dashboard

1. Paste the `:root` token block (§2). Load Manrope.
2. Set global body: white bg, 14px, `tnum`/`ss01`, antialiased.
3. Build the shell: titlebar (parchment gradient) → menu strip → scrollable body → status bar. Or, if non-windowed, at least a `--bg-chrome` status bar + uppercase chrome.
4. Cards = `.card`/`.card-head`/`.card-body`. Headers uppercase on `--bg-stripe`.
5. Tables = `table.lots` recipe: sticky `--bg-stripe` headers, mono cells, whisper-zebra, `--accent-tint` selection with single-cell inset accent.
6. Buttons: `.btn` base + `.btn-primary` (red) for the one headline action, `.btn-auto`/ink for the rest.
7. Inputs: 36px, accent focus halo. Labels uppercase 11px `--ink-3`.
8. Stats: big mono number + tiny uppercase label.
9. Modals: dark scrim, `--line-strong` edge, optional brand-gradient top strip.
10. Status only ever uses ok/warn/err soft tints — never decoration.
```
