# SQLfy Design System

The SQLfy design system is defined in a single SASS token file (`app/src/styles/_tokens.scss`).
All values are compile-time SCSS variables (`$xx`) or runtime CSS custom properties (`var(--xx)`).
Theme switching is driven by a `$themes` SASS map — dark is the default; light activates via `[data-theme="light"]` on `<html>` or `<body>`.

---

## Themed Tokens

These tokens vary between dark and light themes. They are emitted as CSS custom properties via the `emit-theme()` mixin.

| Token       | CSS var         | Dark                        | Light                     | Usage                                |
|-------------|-----------------|-----------------------------|-----------------------------|--------------------------------------|
| `bg`        | `--bg`          | `#0f172a`                   | `#f8f7ff`                   | Page / shell background              |
| `bg-card`   | `--bg-card`     | `#1e2235`                   | `#ffffff`                   | Elevated card / panel surface        |
| `bg-header` | `--bg-header`   | `#1a1040`                   | `#f3f0ff`                   | Tinted header surface (table `<th>`) |
| `text`      | `--text`        | `#f1f5f9`                   | `#111827`                   | Primary text                         |
| `text-2`    | `--text-2`      | `#94a3b8`                   | `#4b5563`                   | Secondary text (labels, descriptions)|
| `text-3`    | `--text-3`      | `#64748b`                   | `#9ca3af`                   | Tertiary text (meta, placeholders)   |
| `border`    | `--border`      | `rgba(255,255,255,0.10)`     | `rgba(0,0,0,0.12)`          | Standard border                      |
| `border-sub`| `--border-sub`  | `rgba(255,255,255,0.05)`     | `rgba(0,0,0,0.06)`          | Subtle separator / hover background  |

---

## Invariant Tokens

These tokens do not change between themes. They are emitted once in `:root`.

### Accent (violet)

| CSS var          | Value                       | Usage                            |
|------------------|-----------------------------|----------------------------------|
| `--accent`       | `#7c3aed`                   | Primary interactive colour       |
| `--accent-hover` | `#6d28d9`                   | Hover / active state of accent   |
| `--accent-subtle`| `rgba(124,58,237,0.10)`     | Tinted accent background         |

### Semantic colours

| CSS var    | Value      | Usage                                 |
|------------|------------|---------------------------------------|
| `--error`  | `#dc2626`  | Errors, destructive badges, NOT NULL  |
| `--warn`   | `#d97706`  | Warnings, FK badges                   |
| `--ok`     | `#059669`  | Success, UQ badges (HTML export)      |
| `--fk`     | `#0891b2`  | Foreign key badges, info accents      |
| `--info`   | `#60a5fa`  | Info inserts, informational rows      |

### Typography

| CSS var       | Value                                     | Usage         |
|---------------|-------------------------------------------|---------------|
| `--font-mono` | `'Courier New', Courier, monospace`       | All body text |
| `--font-sans` | `'Inter', system-ui, sans-serif`          | Headings, UI  |

---

## Alpha Ramps (SCSS only)

Compile-time only — used in component SCSS, never emitted as CSS custom properties.

| Variable     | Value                        | Used for                   |
|--------------|------------------------------|----------------------------|
| `$accent-06` | `rgba(124,58,237,0.06)`      | Sidebar active item bg     |
| `$accent-08` | `rgba(124,58,237,0.08)`      | Active tab background      |
| `$accent-12` | `rgba(124,58,237,0.12)`      | —                          |
| `$accent-15` | `rgba(124,58,237,0.15)`      | PK badge background        |
| `$accent-20` | `rgba(124,58,237,0.20)`      | —                          |
| `$accent-30` | `rgba(124,58,237,0.30)`      | PK badge border, mode ring |
| `$error-04`  | `rgba(220,38,38,0.04)`       | Insight error row bg       |
| `$error-08`  | `rgba(220,38,38,0.08)`       | Error bar background       |
| `$error-10`  | `rgba(220,38,38,0.10)`       | NN badge background        |
| `$error-25`  | `rgba(220,38,38,0.25)`       | NN badge border            |
| `$error-30`  | `rgba(220,38,38,0.30)`       | Error bar border           |
| `$warn-04`   | `rgba(217,119,6,0.04)`       | Insight warning row bg     |
| `$warn-10`   | `rgba(217,119,6,0.10)`       | FK badge background        |
| `$warn-25`   | `rgba(217,119,6,0.25)`       | FK badge border            |
| `$ok-10`     | `rgba(5,150,105,0.10)`       | UQ badge background        |
| `$ok-20`     | `rgba(5,150,105,0.20)`       | UQ badge border            |
| `$fk-08`     | `rgba(8,145,178,0.08)`       | —                          |
| `$fk-10`     | `rgba(8,145,178,0.10)`       | UQ badge bg (app)          |
| `$fk-25`     | `rgba(8,145,178,0.25)`       | UQ badge border (app)      |
| `$fk-30`     | `rgba(8,145,178,0.30)`       | Active link border         |
| `$info-04`   | `rgba(96,165,250,0.04)`      | Info insert row bg         |

---

## Code Block Tokens (SCSS only)

| Variable          | Value       | Usage                    |
|-------------------|-------------|--------------------------|
| `$color-code-bg`  | `#0d1117`   | Code block background    |
| `$color-code-text`| `#a5f3fc`   | Code block text (cyan)   |
| `$color-col-type` | `#7dd3fc`   | Column type label colour |

---

## Type Scale

| Variable       | Value    | Usage                         |
|----------------|----------|-------------------------------|
| `$fs-badge`    | `9px`    | Badge labels                  |
| `$fs-meta`     | `10px`   | Meta / footnotes              |
| `$fs-preview`  | `10.5px` | Preview text                  |
| `$fs-sub`      | `11px`   | Sub-labels                    |
| `$fs-data`     | `11.5px` | Table cell data               |
| `$fs-body`     | `12px`   | Body base (`:root` font-size) |
| `$fs-body-lg`  | `13px`   | Larger body text              |
| `$fs-title-sm` | `13px`   | Small section titles          |
| `$fs-title-md` | `14px`   | Medium section titles         |
| `$fs-title-lg` | `15px`   | Large section titles          |
| `$fs-title-xl` | `18px`   | XL headings                   |
| `$fs-display`  | `24px`   | Display / hero headings       |

**Font weights:** `$fw-medium: 500` · `$fw-semibold: 600` · `$fw-bold: 700`

**Line heights:** `$lh-tight: 1.5` · `$lh-base: 1.6` · `$lh-relaxed: 1.7`

---

## Spacing Scale

| Variable    | Value | Variable    | Value |
|-------------|-------|-------------|-------|
| `$space-1`  | `1px` | `$space-14` | `14px`|
| `$space-2`  | `2px` | `$space-16` | `16px`|
| `$space-3`  | `3px` | `$space-18` | `18px`|
| `$space-4`  | `4px` | `$space-20` | `20px`|
| `$space-5`  | `5px` | `$space-24` | `24px`|
| `$space-6`  | `6px` | `$space-32` | `32px`|
| `$space-8`  | `8px` | `$space-40` | `40px`|
| `$space-10` | `10px`| `$space-12` | `12px`|

---

## Border Radius

| Variable       | Value  | Usage                          |
|----------------|--------|--------------------------------|
| `$radius-sm`   | `3px`  | Badges                         |
| `$radius-md`   | `4px`  | Inputs, small elements         |
| `$radius-lg`   | `6px`  | Cards, panels                  |
| `$radius-xl`   | `8px`  | Modals, large panels           |
| `$radius-2xl`  | `10px` | Extra-large containers         |
| `$radius-full` | `50%`  | Pills, avatars                 |

---

## Layout Constants

| Variable             | Value    | Usage                           |
|----------------------|----------|---------------------------------|
| `$sidebar-width`     | `200px`  | Default sidebar width           |
| `$sidebar-width-lg`  | `240px`  | Wide sidebar (HTML export)      |
| `$content-max-width` | `1100px` | Maximum content column width    |
| `$shell-min-height`  | `600px`  | Minimum app shell height        |
| `$logo-dot-size`     | `18px`   | Logo dot / accent element size  |

---

## Shell Pattern

The app uses a flex column shell:

```
.shell          flex column, 100vh, min-height: $shell-min-height
  .topbar       fixed-height header bar
  .content      flex:1, overflow hidden, flex column
    .tab-bar    tab navigation row
    .split      flex:1, overflow hidden
      .sidebar  fixed-width sidebar
      .panel    flex:1, overflow auto, padding $space-12
```

---

## Badge Variants

All badges use `border-radius: $radius-sm`, `font-size: $fs-badge`, `font-weight: $fw-semibold`, `padding: $space-2 $space-4`.

| Class       | Background   | Border       | Text colour     | Meaning              |
|-------------|--------------|--------------|-----------------|----------------------|
| `.badge.pk` | `$accent-15` | `$accent-30` | `--accent`      | Primary key          |
| `.badge.nn` | `$error-10`  | `$error-25`  | `$color-error`  | Not null             |
| `.badge.uq` | `$fk-10`     | `$fk-25`     | `$color-fk`     | Unique (app)         |
| `.badge.fk` | `$warn-10`   | `$warn-25`   | `$color-warn`   | Foreign key          |

---

## Theme Switching

Apply the `data-theme` attribute to switch themes at runtime:

```html
<!-- Light mode -->
<html data-theme="light">

<!-- Dark mode (default — no attribute needed) -->
<html>
```

To toggle programmatically:

```ts
document.documentElement.setAttribute('data-theme', 'light');
document.documentElement.removeAttribute('data-theme'); // back to dark
```
