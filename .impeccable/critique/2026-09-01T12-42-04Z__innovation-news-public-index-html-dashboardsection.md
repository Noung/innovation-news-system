---
target: "Admin dashboard section (fetch-innovation-news/public/index.html#dashboardSection)"
total_score: 19
max_score: 36
na_heuristics: 10
p0_count: 1
p1_count: 2
target_identity: "file:D:\\ข้อมูลหนึ่ง\\git\\innovation-news-system\\fetch-innovation-news\\public\\index.html#dashboardSection"
timestamp: 2026-09-01T12-42-04Z
slug: innovation-news-public-index-html-dashboardsection
---
Method: dual-agent (A: design-review subagent · B: detector+browser subagent)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3/4 | Global spinner + `dashboardGeneratedAt` timestamp work, but refresh gives no per-click/button-level feedback; live evidence shows a 500 response after login with no visible change on screen (see Design Specificity Verdict) |
| 2 | Match System / Real World | 3/4 | Correct Thai domain vocabulary, but source-type labels (`WP API`, `Generic JSON API`, `RSS`) code-mix English/Thai in the same table aimed at both technical and non-technical staff |
| 3 | User Control and Freedom | 1/4 | No dismiss/ack on alerts, no jump from an unhealthy source row to the Sources tab to fix it, no page-size control |
| 4 | Consistency and Standards | 3/4 | Card chrome consistent with DESIGN.md; badge-color logic is duplicated between `getDashboardHealthBadge` and `getDashboardAlertBadge` (same colors today, drift risk later) |
| 5 | Error Prevention | 2/4 | Refresh is non-destructive, but no fallback UI distinguishes "genuinely zero" from "no data returned" when `kpis` is empty |
| 6 | Recognition Rather Than Recall | 2/4 | KPI "tone" colors (primary/success/warning/danger) have no legend; meaning must be inferred |
| 7 | Flexibility and Efficiency of Use | 1/4 | No keyboard shortcuts, no sort on the Source Health table, KPI cards aren't clickable — weakest heuristic on the page |
| 8 | Aesthetic and Minimalist Design | 3/4 | Restrained and on-brand; the KPI icon dot adds a small decorative flourish that doesn't carry information |
| 9 | Help Recognize/Diagnose/Recover from Errors | 1/4 | Fetch failures only produce a transient toast with no persistent on-page state |
| 10 | Help and Documentation | n/a | Internal daily-use tool for trained staff; no help system expected per PRODUCT.md |
| **Total** | | **19/36** | **Acceptable (53%), bordering Poor** |

## Design Specificity Verdict

**LLM assessment**: The Dashboard is partially authored for this product — Thai-first copy and domain-accurate KPIs (`ส่ง LINE สำเร็จ`, `Fetch 24 ชั่วโมง`, fields like `health_status`/`fetch_method`) prove this isn't template filler. But the *interaction model* is generic-admin-shaped: four KPI cards are visually identical to genuinely interactive cards elsewhere in the app yet have no `onclick`/href, and nothing connects the "Source ที่ควรตรวจ: 3" KPI to the actual rows in the Source Health table that caused it. The visual language ("Ministry Desk") is well executed; the information architecture that would make this feel purpose-built for a daily triage workflow is not there yet.

**Deterministic scan**: `node .github/skills/impeccable/scripts/detect.mjs --json fetch-innovation-news/public/index.html` exited non-zero after falling back to **regex matching** (HTML parser modules — htmlparser2/css-select/css-tree/domutils — were unavailable in this environment), so this is a degraded, undercount-only scan; no selector/computed-contrast rules ran. It reported 20 advisory `quality` findings, all either `design-system-color` (`#cbd5e1`, `#94a3b8`, `#64748b`) or `design-system-radius`/`design-system-font-size` (4px radii, 11px text) that fall outside the color/type tokens formally listed in `DESIGN.md`'s frontmatter. On inspection these are **mostly false positives relative to intent, not relative to the file**: DESIGN.md was authored today from this exact code and already describes an 11px "Micro" type role and neutral grays in prose — it simply doesn't enumerate every neutral shade/11px size as a named frontmatter token yet. Action item: tighten DESIGN.md's frontmatter (add `ink-400`/scrollbar-gray tokens and a `micro` typography entry) so future scans measure against the full palette instead of re-flagging known, already-approved values.

**Visual overlays**: No in-browser detector overlay was injected (Assessment B used login + screenshots + `read_page` accessibility snapshots, not the live-server/`detect.js` injection flow), so there is no highlighted overlay to point you to in a browser tab — treat the CLI table above as the deterministic evidence instead. Live evidence did surface one item outside the detector's scope: the browser session logged an HTTP **500** response shortly after login (alongside repeated SVG `<path>` attribute console errors), which the detector cannot see. This wasn't isolated to a confirmed endpoint, but it directly reinforces heuristic 1 and 9 findings below — a stale/broken load on this dashboard currently produces no visible signal to the user.

## Overall Impression

Visually, this dashboard is a faithful, restrained execution of the "Ministry Desk" system — calm, on-brand, no generic AI-slop tells. The gap is entirely in the interaction layer: the one number an admin most wants to act on (`Source ที่ควรตรวจ`) is disconnected from the table that would let them act on it, and there's no visible recovery path when a load silently fails (which live evidence shows can actually happen). Fix the KPI→table connection and the error-state gap first; everything else here is refinement.

## What's Working

- **Empty/loading states match DESIGN.md exactly**: `ยังไม่มีข้อควรตรวจสอบ` and `ยังไม่มีข้อมูล source` reuse the existing card chrome with plain centered gray text instead of inventing new UI — correct restraint.
- **The trend bar's `Math.max(3, …)` floor** ensures a near-zero value still renders a visible sliver instead of disappearing — a small, genuinely considered touch.
- **Accessible names are present on every button** checked in the live DOM (refresh, pagination, logout, tabs) and heading levels are sequential (`h1 → h2 → h3×4`) with no skipped levels — the static structure is more accessible than the dynamic regions built on top of it.

## Priority Issues

**[P0] KPI cards look interactive but are functionally inert**
- **Why it matters**: "Source ที่ควรตรวจ: 3" is the single most action-oriented number on the page, styled identically to genuinely clickable cards elsewhere in the app — the natural next action (click it) does nothing, which is the direct cause of the working-memory gap between the KPI row and the Source Health table.
- **Fix**: Make the 4th KPI card (ideally all four) filter/scroll/jump to the matching rows in `dashboardSourceHealthBody`, or route to a pre-filtered Sources tab.
- **Suggested command**: `/impeccable shape`

**[P1] No persistent, visible state when a dashboard load fails — and this isn't hypothetical**
- **Why it matters**: `fetchDashboard()`'s catch path only shows a transient toast; live evidence in this session recorded an actual HTTP 500 shortly after login with no lasting on-screen indicator. For a tool whose entire purpose is being the source of truth on pipeline health, an admin who steps away mid-toast has no way to know the numbers on screen are stale or wrong.
- **Fix**: On fetch failure, show a persistent inline banner near `dashboardGeneratedAt` (e.g. "ไม่สามารถอัปเดตข้อมูลล่าสุดได้") with a retry action, and confirm/fix whatever produced the observed 500.
- **Suggested command**: `/impeccable harden`

**[P1] Source Health table has no default triage ordering**
- **Why it matters**: `renderDashboardSourceHealth` renders rows in raw API order with pagination only — an `error`-status source can sit on page 2, buried behind healthy rows on page 1, defeating the "see what needs attention in a few seconds" goal.
- **Fix**: Sort unhealthy rows (`error`/`warning`/`needs_test`) to the top by default, or add a sort toggle on the "Health" column header.
- **Suggested command**: `/impeccable layout`

**[P2] Dynamic regions and the Source Health table lack ARIA semantics — confirmed live**
- **Why it matters**: Live DOM evidence found **zero `aria-live` regions anywhere on the page**, so a screen-reader user who clicks "รีเฟร็ช" gets no announcement that data changed; the 7 `<th>` cells in the Source Health table have no `scope="col"`/caption either. This directly contradicts DESIGN.md's own stated accessibility commitment.
- **Fix**: Add `scope="col"` to all 7 `<th>`, `aria-live="polite"` on `#dashboardKpis`/`#dashboardSourceHealthBody`, and `aria-label` on the refresh button.
- **Suggested command**: `/impeccable audit`

**[P3] Duplicated badge-color logic between health and alert badges**
- **Why it matters**: `getDashboardHealthBadge` and `getDashboardAlertBadge` independently hardcode near-identical warning/error color+label pairs; a future edit to one without the other silently breaks the Status-Color Rule's promise that color always maps to one consistent status vocabulary.
- **Fix**: Extract one shared status-badge map consumed by both render paths.
- **Suggested command**: `/impeccable distill`

## Persona Red Flags

**Alex (impatient power user)**: The inert KPI cards are the biggest failure for Alex's actual workflow ("glance at the danger number → click it → go fix it"); nothing happens. There's also no sort control on the Health column, forcing manual pagination to hunt for red/amber badges.

**Sam (accessibility-dependent)**: Confirmed live — 0 `aria-live` regions anywhere on the page, so triggering "รีเฟร็ช" gives no auditory confirmation of a data change; the loading spinner has no `role="status"` either, so the only feedback is purely visual. The Source Health table's missing `scope="col"`/caption compounds this in the densest, most information-critical part of the page.

## Minor Observations

- Console evidence (live session): repeated SVG `<path>` "Expected number…" attribute errors (5×) — a malformed icon path worth a quick technical cleanup, independent of this critique's design scope.
- `.text-gray-500` computed contrast measured ≈4.83:1 on white — passes WCAG AA (4.5:1) but with very little margin; avoid darkening the background or lightening this gray further.
- Only one source exists in the current local dataset, so alternate `health_status`/`สถานะ` states (inactive, warning, error) could not be visually verified this run — re-run browser evidence once more varied local data is available.
- The Trends card shares one bar scale across two different units (article count vs. fetch count, `renderDashboardTrends`) with no legend distinguishing the blue vs. green bars.
- The KPI icon dot (`w-2.5 h-2.5 rounded-full bg-current`) is a small decorative flourish that doesn't map to DESIGN.md's "icons are functional signals, never decoration" rule.

## Questions to Consider

- If "Source ที่ควรตรวจ" is the most action-oriented number on the page, what would this dashboard look like designed backward from "what does the admin click first"?
- The KPI's `sources_need_attention` count and the separate "ข้อควรตรวจสอบ" alerts feed use two different taxonomies (`health_status` vs. `severity`) for what looks like the same underlying condition — should these unify into one alert model before more dashboard sections are added?
- Given two distinct user types (content-approval staff vs. Dev/IT) share this one Dashboard tab, does showing fetch-method jargon (`WP API`/`Generic JSON API`) to content-approval staff work against the calm "Ministry Desk" goal for that audience?
