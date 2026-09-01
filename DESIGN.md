---
name: Innovation News Management System
description: Admin console for the automated innovation-news fetch, review, and multi-channel publishing pipeline
colors:
  signal-blue: "#2563eb"
  signal-blue-deep: "#1d4ed8"
  signal-blue-tint: "#eff6ff"
  signal-blue-soft: "#dbeafe"
  confirmed-green: "#16a34a"
  confirmed-green-tint: "#f0fdf4"
  caution-amber: "#d97706"
  caution-amber-tint: "#fffbeb"
  alert-red: "#dc2626"
  alert-red-tint: "#fef2f2"
  ink-900: "#111827"
  ink-700: "#374151"
  ink-500: "#6b7280"
  surface-bg: "#f9fafb"
  surface-border: "#e5e7eb"
  overlay-scrim: "rgba(2, 6, 23, 0.5)"
typography:
  title:
    fontFamily: "Noto Sans Thai, Tahoma, Arial, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.3
  heading:
    fontFamily: "Noto Sans Thai, Tahoma, Arial, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "Noto Sans Thai, Tahoma, Arial, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Noto Sans Thai, Tahoma, Arial, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    letterSpacing: "0.2em"
rounded:
  sm: "8px"
  md: "12px"
  lg: "16px"
  full: "9999px"
spacing:
  xs: "8px"
  sm: "16px"
  md: "20px"
  lg: "24px"
components:
  button-primary:
    backgroundColor: "{colors.signal-blue}"
    textColor: "#ffffff"
    rounded: "{rounded.sm}"
    padding: "12px 20px"
  button-primary-hover:
    backgroundColor: "{colors.signal-blue-deep}"
  button-tinted:
    backgroundColor: "{colors.surface-bg}"
    textColor: "{colors.ink-700}"
    rounded: "{rounded.sm}"
    padding: "10px 20px"
  card:
    backgroundColor: "#ffffff"
    rounded: "{rounded.md}"
    padding: "20px"
  badge:
    backgroundColor: "{colors.signal-blue-soft}"
    textColor: "{colors.signal-blue-deep}"
    rounded: "{rounded.full}"
    padding: "2px 8px"
---

# Design System: Innovation News Management System

## Overview

**Creative North Star: "The Ministry Desk"**

This is an internal operate console for staff who verify and approve automated innovation-news before it goes out to WordPress, Telegram, and LINE, and for Dev/IT staff who watch source health and fetch logs. The voice is calm, trustworthy, and clear: a civil-service control desk, not a startup marketing page. Every visual decision should read as precise and verifiable first, expressive second. The system explicitly rejects the generic AI-SaaS look: purple-to-blue gradients, decorative icon tiles above headings, and any ornament that doesn't carry status information.

**Key Characteristics:**

- Flat white cards on a light gray canvas, bordered rather than heavily shadowed
- One dominant accent (signal blue) for interactive/active state; semantic status colors elsewhere
- Thai-first typography (Noto Sans Thai) with a single type family across the whole app
- Icons and badges are functional signals (counts, status), never decoration

## Colors

The palette is a single blue accent plus a semantic status triad (green/amber/red), on a near-white neutral scale. There is a defined but currently unused secondary purple scale in the Tailwind config; it must stay unused rather than become a decorative gradient.

### Primary

- **Trusted Signal Blue** (`#2563eb` / `primary-600`): interactive elements, active tab state, focus rings, count badges, primary CTA (login submit).
- **Signal Blue Deep** (`#1d4ed8` / `primary-700`): hover state for primary CTA and links.
- **Signal Blue Tint** (`#eff6ff` / `primary-50`): hover backgrounds, tab hover, badge backgrounds.

### Neutral

- **Ink 900** (`#111827` / `gray-900`): headings and primary text.
- **Ink 700** (`#374151` / `gray-700`): table headers, secondary emphasis text.
- **Ink 500** (`#6b7280` / `gray-500`): meta text, placeholders, helper copy.
- **Surface Background** (`#f9fafb` / `gray-50`): page canvas and tinted input backgrounds.
- **Surface Border** (`#e5e7eb` / `gray-200`): card borders, dividers, input borders.

### Status colors

- **Confirmed Green** (`#16a34a` / `success-600`): positive actions ("เพิ่มแหล่ง"), healthy source status.
- **Caution Amber** (`#d97706` / `warning-600`): warnings and degraded health states.
- **Alert Red** (`#dc2626` / `danger-600`): destructive actions (logout), errors, failed fetch status.

### Named Rules

**The Status-Color Rule.** Color communicates state, not decoration. Green/amber/red only appear tied to a real status (health, success/failure, destructive action). Never use them as arbitrary accent variety.

**The One Accent Rule.** Signal blue is the only expressive accent. The secondary purple scale defined in `tailwind.config.js` stays reserved/unused; do not activate it for gradients or highlights.

## Typography

**Body/UI Font:** Noto Sans Thai, with Tahoma, Arial, sans-serif fallback
**Character:** One type family for the whole app; hierarchy comes from size/weight, not from mixing fonts. Calm and legible at small sizes since most content is dense tabular/status data.

### Hierarchy

- **Title** (700, 1.5rem/`text-2xl`, 1.3): page-level headings inside a section (e.g. "ภาพรวมการให้บริการ").
- **Heading** (600, 1.125rem/`text-lg`–`font-semibold`, 1.4): card/section titles (e.g. "Source Health").
- **Body** (400, 0.875rem/`text-sm`, 1.6): table cells, form labels, button text, most UI copy.
- **Label** (600, 0.75rem/`text-xs`, uppercase, `tracking-[0.2em]`): section eyebrows ("System Overview").
- **Micro** (500, 0.6875rem/`text-[11px]`): auxiliary meta like "Signed In".

### Named Rules

**The Single-Family Rule.** Don't introduce a second display/serif font for "polish." Hierarchy is size and weight only.

## Layout

Container caps at `max-w-[1920px]`, centered, with responsive horizontal padding `px-4 sm:px-6 lg:px-8`. The header is `sticky top-0 z-40`; the tab bar sits directly below it `sticky top-16 z-30`, so both stay reachable while scrolling long tables. Content sections stack vertically with `mb-6` rhythm. Card interiors use `p-4`–`p-6`. Grids adapt from 1 column on mobile up to 3–4 columns on `xl` (`sm:grid-cols-2 xl:grid-cols-4` for KPIs, `md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4` for source cards). Tables scroll horizontally within a card (`overflow-x-auto custom-scrollbar`) rather than compressing columns below a usable width.

## Elevation & Depth

Layered but conservative: most surfaces are flat (`border` + `shadow-sm`) at rest. Shadow escalates only with importance or interactivity — primary buttons carry a tinted `shadow-lg shadow-{color}-200` that matches their semantic color, and the login modal/overlay uses `shadow-2xl shadow-slate-900/20` because it floats above a scrim. Depth is the exception that marks "this matters more," not an ambient style applied everywhere.

### Shadow Vocabulary

- **Resting card** (`shadow-sm` + `border border-gray-200`): default container depth.
- **Emphasized action** (`shadow-lg shadow-{color}-200`): primary/CTA buttons, using the button's own semantic color.
- **Floating overlay** (`shadow-2xl shadow-slate-900/20`): modals over a `bg-slate-950/50 backdrop-blur-sm` scrim.

### Named Rules

**The Earned-Shadow Rule.** A heavier shadow must correspond to a real elevation change (floating over a scrim) or a call to real action (primary CTA), never applied for visual interest alone.

## Shapes

Corners scale with a component's weight: `rounded-lg`/`rounded-xl` (8–12px) for buttons, inputs, and cards; `rounded-2xl` (16px) for the login modal; `rounded-full` for count badges, pills, and the spinner. Borders are a consistent 1px `border-gray-200`, used on nearly every card, input, and divider instead of relying on shadow alone to separate surfaces.

## Components

### Buttons

- **Shape:** `rounded-lg` (`8px`), consistent across all variants.
- **Primary (CTA):** solid `bg-primary-600 text-white`, `shadow-lg shadow-primary-200`, hover `bg-primary-700`. Reserved for the single most important action per view (e.g. login submit).
- **Tinted action:** `bg-{color}-50 text-{color}-600 border border-{color}-200`, hover `bg-{color}-100 border-{color}-300` — used for "เพิ่มแหล่ง" (success), "รีเฟร็ช" (neutral gray), logout (danger). This is the default button style; solid primary is the exception.
- **Focus:** `focus:ring-4 focus:ring-{color}-200` on every interactive control, no exceptions (accessibility floor).
- **Micro-interaction:** `btn-ripple` (click ripple) and `btn-shimmer` (hover shimmer) classes mark the highest-emphasis actions only; do not apply to every button.

### Badges

- **Style:** `rounded-full`, `bg-primary-100 text-primary-700`, small `text-xs font-semibold` counts on tabs.
- **Use:** counts only (sources/articles/logs/audit counts on tabs), not general-purpose chips.

### Cards / Containers

- **Corner Style:** `rounded-xl`.
- **Background:** white on a `gray-50` page canvas.
- **Shadow Strategy:** `shadow-sm` at rest (see Elevation & Depth); never nested inside another card.
- **Border:** `border border-gray-200` on every card.
- **Internal Padding:** `p-4` (toolbars) to `p-5`/`p-6` (content sections); section headers get their own `px-5 py-4 border-b border-gray-200` strip.

### Inputs / Fields

- **Style:** `border border-gray-200 rounded-lg` (or `rounded-xl` in the login form), tinted `bg-gray-50`.
- **Focus:** background flips to white (`focus:bg-white`), border becomes `primary-300`, and a `focus:ring-2`–`ring-4 focus:ring-primary-100/200` halo appears.
- **Search inputs:** leading icon absolutely positioned at `left-3`.

### Navigation (Tabs)

- **Style:** underline tabs (`border-b-2`), not pills. Inactive: `text-gray-500` (`#64748b`), hover `text-primary-600 bg-primary-50`. Active: `border-primary-600 text-primary-600 font-semibold`.
- **Mobile:** icon-only with `hidden sm:inline` labels; tab strip scrolls horizontally with `hide-scrollbar`.

### Login Overlay (signature component)

Full-screen scrim `bg-slate-950/50 backdrop-blur-sm` behind a centered `rounded-2xl` white card with `shadow-2xl shadow-slate-900/20`. An "Admin Access" eyebrow pill (`bg-primary-50 text-primary-600 rounded-full`) sits above the heading. This is the only place a heavy scrim + large shadow combination is allowed.

### Loading / Empty States

- **Loading:** centered spinner, `border-4 border-primary-600 border-t-transparent`, `animate-spin`, inside a plain card.
- **Empty:** centered `bg-gray-100 rounded-full` icon circle above a short message and a tinted CTA button — never a bare "no data" text with no next action.

## Do's and Don'ts

### Do:

- **Do** keep Noto Sans Thai as the only UI typeface; never substitute a Latin-only default when adding new screens.
- **Do** use status color (blue/green/amber/red) only when it maps to a real state; keep everything else neutral gray.
- **Do** keep cards flat (`border` + `shadow-sm`) at rest, reserving `shadow-lg`/`shadow-2xl` for genuine CTAs and floating overlays.
- **Do** give every interactive control a visible `focus:ring` — this is an internal ops tool used all day, keyboard access matters.

### Don't:

- **Don't** activate the unused secondary purple scale for gradients or accents; the one-accent rule (signal blue) stays.
- **Don't** nest cards inside cards; one `bg-white rounded-xl border` container per section, tables/content live directly inside it.
- **Don't** use bounce/elastic easing; existing transitions are simple `duration-200`/`duration-300` ease.
- **Don't** add decorative icon tiles above section headings; icons here are functional (buttons, tabs, empty states), not ornamental markers.
