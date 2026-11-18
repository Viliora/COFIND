# Cofind UI/UX Redesign — Phase 0 Audit

**Date:** 2026-11-19  
**Branch:** `main` (no code changed in this phase)  
**References:** `PRODUCT.md`, `DESIGN.md`, `docs/COFIND-UI-REDESIGN-PLAN.md`  
**Impeccable:** `context --target frontend-cofind` · `detect frontend-cofind/src` (regex on 74 source files)

---

## 1. Executive summary

The consumer UI is **functionally buildable** (Vite production build passes; backend tests pass) but **visually split**: `About.jsx` uses warm stone/serif editorial cues, while **home, discovery, pills, modals, and chrome** lean on **indigo/violet gradients**, Vite default `:root` link colors, and `theme-color` indigo `#4F46E5`.  

`DESIGN.md` describes a complete **Warm Editorial v2** system (`tokens.css`, `components/ui/*`, roast/river palette) that **is not present in the repository**. `hasVisualImplementation: false` from Impeccable context confirms the gap.

**Static detect:** **36** anti-patterns (full regex scan; tiny-text / parsed contrast rules **not** run — undercount).  
**Remediation target:** Phase 1–6 in redesign plan; detect → **0** on consumer surfaces before final sign-off.

---

## 2. Automated baseline

| Check | Result | Notes |
|--------|--------|--------|
| `impeccable detect frontend-cofind/src` | **36 findings** | See §3 |
| `npm run lint` (frontend) | **Fail** — 7 errors, 7 warnings | Was “0 errors” in older `DESIGN.md` note — baseline regressed or config stricter |
| `npm test` (vitest) | **Pass** — 3 tests, 1 file | Very narrow frontend test surface |
| `npm run build` | **Pass** — 9.15s | 214 modules |
| `pytest tests/` | **Pass** — 125 passed ~47s | Backend guard; no UI |
| `npm run test:e2e` | **Not run** | Playwright; requires env + running stack |
| Browser smoke (375/768/1280) | **Not run** | Dev server not up in audit session |
| `impeccable detect http://localhost:5173` | **Not run** | Needs Vite + URL scan for tiny-text/contrast |

### Lint errors (pre-existing; fix only if blocking or in touched files)

| File | Issue |
|------|--------|
| `FacilityAttributePicker.jsx` | react-refresh/only-export-components |
| `ShopOverallExperience.jsx` | react-refresh/only-export-components |
| `ShopVoteModal.jsx` | react-refresh/only-export-components |
| `AdminDashboardCharts.jsx` | unused `pct` |
| `AuthContext.jsx` | unused `username` |
| `Login.jsx` | unused `authService` |
| `ShopDetail.jsx` | unused `openVoteModal` |

---

## 3. Impeccable detect — findings by file

| File | Count | Rules |
|------|-------|--------|
| `pages/ShopList.jsx` | 6 | `gradient-text`, multiple `ai-color-palette` (indigo/purple) |
| `pages/Admin.jsx` | 14 | `gray-on-color` (stone-50 on amber/red/emerald/violet) |
| `constants/reviewPills.js` | 4 | violet/indigo gradient pill themes |
| `pages/ShopDetail.jsx` | 2 | indigo header gradient |
| `RecommendationModal.jsx` | 2 | indigo wash gradients |
| `config/facilityTabsConfig.js` | 2 | indigo/violet tab gradients |
| `FacilityAttributePicker.jsx` | 1 | indigo selected pill gradient |
| `Navbar.jsx` | 1 | gradient text (brand/search) |
| `CoffeeShopCard.jsx` | 1 | indigo heading accent |

**Grep breadth (heuristic):** indigo/violet/purple gradient tokens appear across **~30** files; heavy `rounded-2xl` / large shadows on **~25** files; `transition-all` on **~20** files (DESIGN.md bans `transition-all` globally).

---

## 4. Design drift — `DESIGN.md` vs codebase

| DESIGN.md claims | Repo reality |
|------------------|--------------|
| `src/styles/tokens.css` | **Missing** |
| `src/components/ui/**` primitives | **Missing** |
| `Libre Baskerville` / `Source Sans 3` | **Not loaded** in `index.html` |
| Colors `#5c3d2e`, `#faf6f0`, etc. | **Not in Tailwind** — default Vite `:root` + Tailwind utilities only |
| `voteAspectIcons.jsx`, `CollectionPageLayout.jsx` | **Missing** |
| `font-display`, `cofind-*` shell tokens | **Absent** (except map route CSS class) |
| `theme-color` / PWA | Still **indigo** `#4F46E5` in `index.html` / `manifest.json` |
| Anti–gradient-text on hero | **Violated** on `ShopList` line ~1052 |
| “impeccable detect — 0” (2026-03-25 note) | **Stale** — current **36** |

**Partial alignment:** `About.jsx` warm stone, serif title, paper background — closest to target world but isolated; not wired to shared tokens.

---

## 5. Route-by-route UX audit (static / code review)

### P0 — Discovery core

| Route / surface | Hierarchy & layout | Visual identity | UX / IA | Responsive notes | Priority |
|-----------------|---------------------|-----------------|---------|-------------------|----------|
| `/` `ShopList` | Hero + stats + pills + carousels + map + aside; very long single file (~1.4k LOC) | Indigo/purple stats cards, gradient hero text, mixed amber + indigo | Rich but noisy; recommendation CTA competes with catalog | Many breakpoints in classes; horizontal scrollers need retest | **P0** |
| `/shop/:id` | Photo, meta, facilities, reviews, vote, pros/cons | Indigo CTA bands; nested rounded panels | Dense; risk nested cards | — | **P0** |
| `RecommendationModal` + overlay | Multi-step SSE progress | Indigo panels; progress overlay heavy gradients | Critical path — must stay readable during load | Modal max-height/scroll — verify mobile | **P0** |
| `Navbar` / `Footer` | Global chrome | Amber **and** indigo accents; gradient brand text | Search + theme + auth clear | Mobile menu — verify focus trap | **P0** |
| `CoffeeShopCard` / carousels | Card grid pattern | Indigo price/rating accents | Consistent card template (generic marketplace feel) | Carousel wheel handler — preserve behavior | **P0** |
| Map (`CoffeeShopMap`, etc.) | Split with list | Blue route button on map popup (not tokenized) | Geo + markers — OK functionally | — | **P1** |
| Pills (`reviewPills`, pickers) | Filter chips | Violet/indigo gradient selected states | Core to recommendation — tokenize carefully | — | **P0** |

### P1 — Account & collections

| Route | Notes | Priority |
|-------|--------|----------|
| `/login` | Split layout exists; still `transition-all`; unused import lint | **P1** |
| `/favorite`, `/want-to-visit` | Similar list patterns; `LatestReviewsAside` pattern differs from DESIGN “no aside” | **P1** |
| `/profile` | Indigo accents; cover band not tokenized | **P1** |

### P2 — Supporting

| Route | Notes | Priority |
|-------|--------|----------|
| `/about` | Warmest page — use as **reference tone**, not separate system | **P2** |
| `/admin` | Separate shell; many `gray-on-color` detect hits; keep semantic red/green actions | **P2** |

### Global / cross-cutting

| Topic | Finding | Priority |
|-------|---------|----------|
| Typography | `system-ui` + Avenir in `index.css`; no display/body pairing | **P0** |
| `#root` max-width 1300px | May fight DESIGN `72rem` editorial width — reconcile in Phase 1 | **P1** |
| Dark mode | `class` strategy OK; colors not token-driven | **P1** |
| A11y | Focus outline `amber-400` in CSS — OK direction; contrast not fully scanned | **P1** |
| Loading | `PageLoadingFallback` uses **indigo** spinner | **P1** |
| States | Empty/error patterns vary per page — unify in harden phase | **P2** |

---

## 6. Functional smoke matrix

Legend: **Auto** = tested this session · **Manual** = needs browser + credentials · **N/A**

| # | Flow | Phase 0 status |
|---|------|----------------|
| 1 | All routes resolve (no blank root) | **Manual** — build only |
| 2 | `/` catalog + API `coffeeshops` | **Manual** |
| 3 | Navbar search → shop detail | **Manual** (per old DESIGN QA: Pass) |
| 4 | Pills + map load | **Manual** |
| 5 | Recommendation SSE (auth) | **Manual** — login required |
| 6 | Shop detail reviews/media | **Manual** |
| 7 | Review submit (auth) | **Manual** |
| 8 | Favorites / want-to-visit | **Manual** |
| 9 | Login / logout / session | **Manual** |
| 10 | Admin `/admin` | **Manual** — admin user |
| 11 | Geolocation + map markers | **Manual** |
| 12 | Responsive 375/768/1280 | **Manual** |
| 13 | Backend APIs unchanged | **Auto** — pytest 125 pass |

**Action before Phase 2+:** Run manual matrix with `python app.py` + `npm run dev`; record in appendix when done.

---

## 7. Prioritized improvement backlog

### P0 (blocks “editorial identity” — Phase 1–3)

1. Add design tokens + Tailwind extension + font loading (`DESIGN.md` slice #1).  
2. Remove indigo/violet **consumer** gradients; map pills/modals/home to roast/river/paper.  
3. Replace gradient text on home hero and navbar.  
4. Introduce `components/ui/*` and migrate primary buttons/inputs/modals without changing handlers.  
5. Retokenize `reviewPills.js` + `facilityTabsConfig.js` (behavior-preserving class swaps).  
6. Update `theme-color`, manifest, loading spinner to roast primary.

### P1 (Phase 4–5)

7. Unify `Login`, collections, `Profile` with `CollectionPageLayout`.  
8. Home layout vs DESIGN (aside removal / full-width catalog) — **confirm with product** before deleting `LatestReviewsAside` on `/`.  
9. Map popup route button: blue → secondary/primary token.  
10. Reduce `transition-all` to purposeful transitions.

### P2 (Phase 6 + polish)

11. Admin `gray-on-color` cleanup (use `text-white` / tinted foreground).  
12. Lint error cleanup in files we touch.  
13. URL-based `impeccable detect http://localhost:5173` after dev server up.  
14. Playwright E2E if CI/env available.  
15. Refresh `DESIGN.md` QA table to match reality.

---

## 8. Regression risks for redesign (watch list)

- `ShopList.jsx` size and state — recommendation stream, pill limits, auth gates.  
- `RecommendationModal` SSE + progress overlay timing.  
- Leaflet map + scroll sync + popup HTML strings.  
- `FacilityAttributePicker` / `PreferencePillPicker` controlled state tied to recommendation API payload.  
- Admin route redirect (`UserRoute` / `AdminRoute`) — do not alter logic.  
- Prop/signature changes — **avoid** unless shimmed.

---

## 9. Phase 0 gate

| Criterion | Met? |
|-----------|------|
| Audit doc written | Yes |
| Detect baseline recorded | Yes (36) |
| Build/test baseline recorded | Yes |
| No UI code changed | Yes |
| User approval for Phase 1 | **Done** |

## Appendix B — Phase 1 foundation (2026-11-19)

**Shipped (presentation tokens + primitives; routes not restyled yet):**

- `frontend-cofind/src/styles/tokens.css`, wired in `main.jsx`
- `tailwind.config.js` → `cofind-*` colors, fonts, shadows, `max-w-cofind`
- `index.css` base (paper/ink links, focus ring, `#root` 72rem)
- `index.html` fonts + `theme-color` `#5c3d2e`; `manifest.json` aligned
- `src/components/ui/*` (Button, Input, Textarea, Badge, Card, ModalShell), `src/utils/cn.js`
- `reviewPills.js` + `facilityTabsConfig.js` — solid chips, no violet/indigo pill gradients

**Verify:** `npm run build` pass · `npm test` pass · re-run `impeccable detect` before Phase 2 (home still has indigo until Phase 2).

---

## Appendix C — Phase 3 detail & recommendation (2026-11-19)

**Touched (styling only; SSE/vote/review handlers unchanged):**

- `RecommendationModal.jsx` — header wash, focus rings, chips → `cofind-*`
- `RecommendationProgressOverlay.jsx` — full token pass (spinner, stages, elapsed pill)
- `RecommendationReviewSourcePills.jsx` — links/hover → river/roast
- `RecommendationMap.jsx` — distance label → `cofind-secondary`
- `ShopOverallExperience.jsx` — section icon; kenyamanan slider teal (no purple/indigo gradient)
- `ShopVoteModal.jsx` — kenyamanan `accent-teal-600`
- `ShopOpeningHoursBlock.jsx` — summary link tone → `cofind-secondary`

**Verify:** `npm run build` pass · `impeccable detect frontend-cofind/src` → **17** (all `Admin.jsx` `gray-on-color`; no consumer indigo/violet in Phase 3 scope)

**Remaining before Phase 6 on other routes:** `CoffeeShopMap` (home), `OptimizedImage` spinner.

---

## Appendix D — Phase 4 auth, collections, profile (2026-11-19)

**Shipped:**

- `CollectionPageLayout.jsx` — shared shell, empty/auth gates, CTA classes; **Favorite** / **WantToVisit** drop `PageWithLatestReviews` aside
- `Login.jsx` — editorial split (solid form panel + photo column), `Input` / `Button` tokens
- `Profile.jsx` — `cofind-background`, primary cover band, `font-display`, no hero gradients
- `About.jsx` — full-width tokens, no reviews aside

**Verify:** `npm run build` pass · `impeccable detect` — consumer indigo cleared on Phase 4 routes (admin/map remnants remain)

---

## Appendix E — Phase 5 admin shell (2026-11-19)

**Shipped (presentation only):**

- `Admin.jsx` — `cofind-background` shell, primary/secondary CTAs, `text-cofind-on-*` / `text-white` on colored buttons, modal inputs focus rings
- `components/admin/*` — sidebar, topbar, table, modal, stat card, chart trend bars (no violet/gradient chrome)

**Verify:** `npm run build` pass · `impeccable detect` — expect 0 or near-0 on static regex scan

---

## Appendix F — Phase 6 polish (2026-11-19)

**Shipped:**

- `CoffeeShopMap.jsx` — `cofind-*` chrome, river marker/circle, no indigo
- `OptimizedImage.jsx` — paper skeleton + primary spinner
- `Navbar.jsx` — solid favorite/want/login chips (no orange/pink gradients)
- `FacilitiesTab.jsx`, `ReviewForm.jsx` guest CTA, `ReviewCard` avatar, `ShopList` rank badge
- `ShopDetail.jsx` floating action hints

**Verify:** `npm run build` pass · `npm test` pass (3) · `impeccable detect frontend-cofind/src` → **0**

**Manual smoke:** jalankan matrix §6 audit + login/rekomendasi logged-in bila belum.

---

## 10. Redesign status

**Phases 0–6 complete** on `main` (belum commit kecuali user minta). Opsional: `impeccable detect http://localhost:5173` dengan dev server aktif.

Re-run gates:

```powershell
cd c:\Users\User\cofind\frontend-cofind
npm run lint; npm test; npm run build
cd c:\Users\User\cofind
.\.cursor\skills\impeccable\scripts\impeccable.cmd detect frontend-cofind/src
```

**Optional before Phase 1:** Start dev servers and complete §6 manual matrix; append results to this file under “Appendix A — Manual smoke (date)”.