# Cofind UI/UX Redesign Plan — Warm Minimalist & Editorial Discovery

**Status:** Plan only — no UI implementation in this document.  
**Git:** Work stays on `main` (no branch switches, no merge, no force ops).  
**Commits:** None without explicit user approval.  
**Authority:** `PRODUCT.md` (product) · `DESIGN.md` (visual) · this plan (execution order).

---

## 0. Readiness (completed in prep)

| Item | State | Notes |
|------|--------|--------|
| `PRODUCT.md` | ✅ Written | Schema `impeccable:product-schema 1` at repo root |
| `DESIGN.md` | ✅ Exists | Tokens + route matrix; **not yet implemented in code** (`hasVisualImplementation: false`) |
| Impeccable CLI | ✅ v4.9.1 | `npx impeccable@latest install` refreshed skills + engine |
| Context loader | ✅ | `.cursor/skills/impeccable/scripts/impeccable.cmd context --target frontend-cofind` |
| Live config | ✅ | `.impeccable/live/config.json` → `frontend-cofind/index.html` |
| `buildPath` | ✅ `code` | `.impeccable/config.json` — app UI is Operate mode, code-first |
| Design hook | ✅ | `.cursor/hooks.json` (post-edit detect) |
| Dev entrypoints | ✅ | API `python app.py` :5000 · UI `cd frontend-cofind && npm run dev` :5173 |

**Drift to fix before phase 1 ships:** `DESIGN.md` lists v2 files (`tokens.css`, `components/ui/**`, `voteAspectIcons.jsx`, `CollectionPageLayout.jsx`) that are **missing** from the tree. Phase 1 creates them; do not treat “shipped routes” in DESIGN.md as already built.

**Baseline detect (2026-11-19):** `impeccable detect frontend-cofind/src` → **36** anti-patterns (indigo/violet gradients, gradient text, gray-on-color, etc.). Re-run after each phase; target → **0** on consumer surfaces before final report.

---

## 1. Design direction (locked)

**World:** Warm Minimalist & Editorial Discovery — align code to existing `DESIGN.md` tokens:

- Roast primary `#5c3d2e`, river secondary `#1f6b5c`, paper `#faf6f0`, ink `#1c1917`
- Display: Libre Baskerville · Body: Source Sans 3
- Editorial layout: photography-forward, hairline rules, minimal nested cards, no indigo SaaS gradients, no gradient text
- Mode: **Operate** (discovery app) — precision and scanability over marketing flash

User brief adds: cream/beige/coffee tones, purposeful whitespace, professional marketplace feel, preserve **all** behavior (highest priority).

---

## 2. Scope inventory

### Routes (`App.jsx`)

| Route | Page / shell | Priority |
|-------|----------------|----------|
| `/` | `ShopList.jsx` | P0 |
| `/shop/:id` | `ShopDetail.jsx` | P0 |
| Modals/overlays | `RecommendationModal`, progress, vote | P0 |
| `/login` | `Login.jsx` | P1 |
| `/favorite`, `/want-to-visit` | Collection pages | P1 |
| `/profile`, `/profile/:userId` | `Profile.jsx` | P1 |
| `/about` | `About.jsx` | P2 |
| `/admin` | `Admin.jsx` + `components/admin/*` | P2 (shell tokens, keep CRUD logic) |

### Shared chrome & systems

| Area | Files | Priority |
|------|--------|----------|
| Nav / footer | `Navbar.jsx`, `Footer.jsx`, `App.jsx` | P0 |
| Cards / hero / map | `CoffeeShopCard`, `HeroSwiper`, `CoffeeShopMap`, `RecommendationMap*` | P0 |
| Pills / filters | `PreferencePillPicker`, `FacilityAttributePicker`, `reviewPills.js` | P0 |
| Reviews / UGC | `Review*`, `ShopProsCons`, `ShopOverallExperience`, `FacilitiesTab` | P1 |
| Primitives (new) | `src/styles/tokens.css`, `tailwind.config.js`, `index.css`, `components/ui/*`, `utils/cn.js` | P0 foundation |

**Out of scope:** Flask API, Supabase schema, recommendation pipeline logic, new routes, prop/API renames unless required for a11y and verified safe.

---

## 3. Phase 0 — Audit (no feature code yet)

**Goal:** Document baseline UX/UI and functional smoke list before edits.

1. Run `impeccable context --target frontend-cofind` at start of each implementation session.
2. **Static audit**
   - `impeccable detect frontend-cofind/src` (save count + top files)
   - Read-heavy pass: hierarchy, typography, spacing, indigo/gradient usage (grep already shows heavy use on `ShopList`, `Navbar`, modals)
3. **Impeccable evaluate** (in-thread, using references — no code change)
   - `/impeccable critique` mental model: per-route hierarchy + IA
   - Checklist from user brief §2 (responsive, states, a11y)
4. **Functional baseline** (record pass/fail; do not claim untested flows)
   - `cd frontend-cofind && npm run lint && npm test && npm run build`
   - `pytest tests/` at repo root (backend unchanged but regression guard)
   - Manual matrix from `DESIGN.md` QA table + logged-in flows (recommendation SSE, review submit, favorites)
5. **Deliverable:** `docs/COFIND-UI-REDESIGN-AUDIT.md` (findings, P0/P1/P2, detect delta vs 36)

**Gate:** User approves audit + phase order before Phase 1 coding.

---

## 4. Phase 1 — Design system foundation (P0)

Implement `DESIGN.md` commit slice **#1** only:

- `frontend-cofind/src/styles/tokens.css` + wire in `main.jsx`
- Extend `tailwind.config.js` (`colors`, `fontFamily`, `borderRadius`, `boxShadow` → `shadow-cofind-*`)
- Replace Vite default `:root` link colors in `index.css` with token-driven base
- Load fonts in `index.html` (Google fonts: Libre Baskerville, Source Sans 3)
- `src/components/ui/`: `Button`, `Input`, `Textarea`, `Badge`, `ModalShell`, `Card` (single border layer)
- `src/utils/cn.js` if not present
- Retokenize `reviewPills.js` / facility config to roast/river (remove indigo/violet gradient chips)

**Tests after phase:** lint, vitest, build, `impeccable detect` (expect large drop in ai-color-palette hits).

**Gate:** No route page rewrites yet except imports if needed for smoke.

---

## 5. Phase 2 — Global chrome + homepage (P0)

Slices **#2–#3**:

- `Navbar`, `Footer`, `App.jsx` shell (paper background, ink text, focus rings)
- `HeroSwiper` (editorial scrim per DESIGN — solid badges, no gradient text)
- `ShopList.jsx`: hero, stats, pill row, carousels, map section, recommendation entry
- `CoffeeShopCard.jsx`, `LatestReviewsAside` (if still used on home), progress overlay hooks

**Preserve:** `streamRecommendations`, pill state, auth gates, map geo, API_BASE usage.

**Test:** Home load, scroll carousels, map markers, guest vs auth CTAs, 375/768/1280 layout spot-check.

---

## 6. Phase 3 — Discovery detail & recommendation (P0)

- `ShopDetail.jsx` + review/vote/hours components
- `RecommendationModal.jsx`, `RecommendationReviewSourcePills.jsx`, `RecommendationProgressOverlay.jsx`
- Remove indigo washes; keep SSE/progress semantics

**Test:** Deep link shop, review list, vote modal, recommendation modal (logged-in).

---

## 7. Phase 4 — Auth, collections, profile (P1)

Slices **#5–#7** (partial):

- `Login.jsx` editorial split
- `Favorite.jsx`, `WantToVisit.jsx` + shared `CollectionPageLayout.jsx` (new)
- `Profile.jsx`
- `About.jsx` alignment (already warmer — unify tokens)

---

## 8. Phase 5 — Admin shell (P2)

- Token pass on `Admin.jsx`, `components/admin/*` — `cofind-*` shell, no CRUD logic edits
- Keep admin separate chrome policy (already hidden Navbar on admin routes)

---

## 9. Phase 6 — Polish & harden

Impeccable commands as needed:

- `polish`, `adapt` (breakpoints), `audit` (a11y/responsive), `harden` (empty/error/loading)
- `impeccable detect frontend-cofind/src` → 0
- Optional: `/impeccable live` for variant iteration on `/` and `/shop/:id` (requires dev server + browser)

Update `DESIGN.md` only to reflect **actual** shipped state (routes table, QA results).

---

## 10. Regression & quality gates (every phase)

After **each** phase:

```powershell
cd c:\Users\User\cofind\frontend-cofind
npm run lint
npm test
npm run build
cd c:\Users\User\cofind
.\.cursor\skills\impeccable\scripts\impeccable.cmd detect frontend-cofind/src
```

Optional E2E when env allows: `npm run test:e2e` (Playwright).

**Never:** dummy API data, removed handlers, prop renames without compatibility shim, backend/schema changes for cosmetic reasons.

---

## 11. Git workflow (user rules)

- Confirm `git branch --show-current` → `main` before each session
- Stage UI paths in logical chunks matching `DESIGN.md` commit slices (when user asks to commit)
- Do **not** `git add` `__pycache__`, backend-only files in UI commits
- Untracked today: `PRODUCT.md`, `.impeccable/`, Impeccable script updates — user decides when to commit

---

## 12. Final report template (after phase 6)

1. Pages/components redesigned
2. Design system artifacts (tokens, ui primitives)
3. Functionality preserved (checklist)
4. Files touched (grouped by phase)
5. Tests run + results (lint, vitest, build, pytest, manual matrix)
6. Bugs found/fixed
7. Unverified items (e.g. production Vercel, logged-in SSE)
8. Confirm branch remained `main`

---

## 13. Suggested next action

1. **You approve this plan** (or request edits).
2. Agent runs **Phase 0** only → produces `docs/COFIND-UI-REDESIGN-AUDIT.md`.
3. After approval → **Phase 1** foundation on `main`, one phase per session with gates.

**Impeccable session kickoff command:**

```powershell
cd c:\Users\User\cofind
.\.cursor\skills\impeccable\scripts\impeccable.cmd context --target frontend-cofind
```