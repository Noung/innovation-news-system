---
target: "Admin dashboard section (fetch-innovation-news/public/index.html#dashboardSection)"
total_score: 29
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
target_identity: "file:D:\\ข้อมูลหนึ่ง\\git\\innovation-news-system\\fetch-innovation-news\\public\\index.html#dashboardSection"
timestamp: 2026-09-03T22-35-53Z
slug: innovation-news-public-index-html-dashboardsection
---
## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of system status | 3/4 | Timestamp + spinner + aria-live + staleness banner are real, but `showLoading()` blanks the entire section on every refresh |
| 2 | Match system and real world | 3/4 | Thai-first status labels match ops vocabulary; failure toasts still show raw English ("Failed to load dashboard") |
| 3 | User control and freedom | 2/4 | Dismissible chip + retry exist, but refresh destroys scroll/context and alert rows offer no action or expansion |
| 4 | Consistency and standards | 3/4 | STATUS_BADGE_MAP unifies badge colors; minor drift (fallback text-gray-700 vs map text-gray-600, English toast) |
| 5 | Error prevention | 3/4 | Read-only dashboard, page clamping, type="button" — nothing critical missing |
| 6 | Recognition rather than recall | 4/4 | Every card/panel has explanatory subtitle, trend legend dots, visible filter chip — excellent |
| 7 | Flexibility and efficiency | 3/4 | KPI deep-links + one-click filter+scroll; no shortcuts/exports; alerts panel dead-ends |
| 8 | Aesthetic and minimalist | 3/4 | Calm Ministry Desk; KPI dot-tiles are decorative color not signal (Status-Color Rule breach) |
| 9 | Recognize/diagnose/recover errors | 3/4 | Persistent role=alert banner + Thai staleness copy + retry is strong; cold-start failure leaves silent empty zones; toast double-announces |
| 10 | Help and documentation | 2/4 | None in-product; acceptable for trained staff, but no tooltips on health states |
| **Total** | | **29/40** | **Good (72.5%), up from 19/36 (Acceptable 53%)** |

Note: all 10 heuristics scored this round (previous round scored 9, n/a on #10), so totals use different denominators: 19/36 → 29/40.

## Design Specificity Verdict

DESIGN.md is strongly product-specific: the "Ministry Desk" north star names this exact console's users and decisions, named rules (Status-Color, One Accent, Single-Family) are tied to real operational semantics, and PRODUCT.md grounds everything in Thai-first Noto Sans Thai for internal approval staff. The triage spine — severity-sorted Source Health table, dismissible filter chip, Thai status vocabulary, honest staleness messaging — is genuinely authored for this approval workflow. The one place generic dashboard decoration survives is the KPI tone system: fixed per-card colors that quietly violate the system's own Status-Color Rule.

## Deterministic Scan

Detector exit 0, 0 findings (was 20 advisory). DESIGN.md frontmatter now documents the values the code actually uses (slate scrollbar colors, ink-400, micro 11px, scrollbar-thumb 4px, slate-500 inactive tab). Browser evidence: 0 console errors (SVG path parse errors and /api/audit-logs HTTP 500 both confirmed fixed), dashboard + audit-logs APIs return 200, mobile 390px has no horizontal overflow, all buttons have accessible names, chip clear button has focus ring, banner hidden when healthy, severity sort verified with mixed-status data (error→warning→ok).

## Overall Impression

The dashboard has crossed from "acceptable" to genuinely good. The P0-P3 fixes are all real, well-integrated, and follow the design system. What remains is the interaction-layer detail work: refresh still blanks the screen, KPI color is decorative rather than threshold-driven, and the alerts panel still dead-ends.

## Priority Issues

**[P1] Refresh blanks the whole dashboard** — showLoading() hides #dashboardSection; every manual refresh costs scroll position and visual context, contradicting the calm-desk goal. Fix: dim the section (opacity-60 pointer-events-none) + spin the in-button icon; reserve full-screen spinner for first load only.

**[P1] KPI tones are decorative, not threshold-driven** — card 4 is danger-red even at 0; card 2 green even when sends fail. Violates the Status-Color Rule and creates alarm fatigue. Fix: derive tone from data (sources_need_attention > 0 ? danger : neutral; fetch24h.failed > 0 ? warning : success).

**[P2] Cold-start failure renders silent empty zones** — first-load failure runs no render, leaving KPI/summary/trends/alerts blank under the banner. Fix: per-zone placeholder rows ("ไม่มีข้อมูล — กดลองอีกครั้ง").

**[P2] Alerts panel is a dead end** — rows non-interactive, line-clamp-3 with no expansion, no link to the offending source/log. Fix: expandable rows deep-linking to Sources/Logs filtered by that source.

**[P3] Toast + banner double-announce failure in the wrong language** — English toast duplicates the persistent Thai banner. Fix: suppress toast when banner shown; localize remaining toast strings.

## Minor Observations

- getFallbackStatusBadge returns text-gray-700 while STATUS_BADGE_MAP.gray uses text-gray-600 — 1-shade drift inside the anti-drift map.
- #dashboardSourceHealthCount shows total sources even when filter chip is active, contradicting the filtered pagination line below.
- aria-live="polite" on the whole #dashboardKpis grid re-announces all four cards per refresh; a visually-hidden status line would be quieter.
- Banner retry button is solid bg-danger-600; a tinted danger variant would better match the button-tinted system pattern.

## Persona Red Flags

**Alex (impatient power user)**: KPI deep-links + severity sort now serve his "glance → click → fix" loop; remaining friction is the screen-blanking refresh and alerts that can't be clicked through.

**Sam (accessibility-dependent)**: aria-live regions now exist (2), all buttons named, focus rings present including chip clear; remaining risk is the whole-grid live region being noisy, and cold-start failure presenting silent blank zones with no textual state.

## Questions to Consider

- Should the Ministry Desk go quiet when all is well, so that color means something the day it appears?
- Are you training staff to avoid refreshing — the exact behavior the staleness banner depends on?
- If alerts "ควรให้ admin ตรวจต่อ", what is the designed next action — read and remember, or act?
