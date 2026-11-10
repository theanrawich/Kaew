# Kaew real-parts viewer implementation plan

> **For agentic workers:** use native execution in the current session. Steps use checkbox syntax for tracking.

**Goal:** Deliver the existing Kaew viewer with realistic purchased-part geometry and an inspectable Shopee budget.

**Architecture:** Keep the existing Three.js/esbuild single-file build. Import `kaew-bom.json` into the viewer and generate the shopping document from the same data. Model in millimetres with explicit status for every critical dimension.

**Tech Stack:** Three.js 0.180, esbuild, HTML/CSS, local Node.js.

**Spec:** `docs/superpowers/specs/2026-10-30-kaew-real-parts-design.md`

## Global constraints

- Crystal 1.5 L; chosen Ocean 300 ml glass; HTML only; no purchase or deployment.
- Bottle dimensions remain explicitly estimated; pack dimensions are not individual-bottle dimensions.
- Show hardware, fabrication, shipping and contingency separately; no misleading variant price confirmation.
- Self-contained offline HTML; retain simulation; no firmware/API integration claims.

## Review focus

- A narrow/mobile viewport must retain usable orbit controls and inspector.
- Exploded/cutaway transitions must stop filling and reveal the actual pump layout.
- Removing the cup or pressing stop must stop simulated flow immediately.
- Pack quantities, variant flags and all allowance totals must remain visible and correct.
- Reset must restore geometry, camera, water, controls and dimension visibility consistently.

### Task 1: shopping evidence and budget

- [x] Save dated Shopee search-card evidence with links and raw displayed amounts.
- [x] Build `kaew-bom.json` with quantities, confidence/variant flags and allowances.
- [x] Generate `KAEW_SHOPPING_LIST.md`; independently recompute the revised4,742THB planning total after the user selected504THBpump and139THBOLED.

### Task 2: real-part viewer

- [x] Back up `kaew-3d.html` and existing viewer source.
- [x] Update `.work/kaew-viewer.js`, `.work/kaew-template.html`, `.work/build-kaew.cjs`.
- [x] Build standalone viewer with cup83/63×90mm, reference OLED active area29.42×14.7mm, and photo-based pump/PET shapes explicitly marked estimated.
- [x] Include budget, source links, scale statuses, dimension overlay and existing simulation actions.

### Task 3: verification and delivery

- [x] Run `node .work/build-kaew.cjs`; extracted final script parser and offline checks pass.
- [x] Inspect desktop/mobile, assembled/exploded/cutaway views and test cup/stop/reset/export.
- [x] Save representative screenshots and a verification report; update project draft with user choices and supported limitations. Independent read-only review found noCritical/Important defects; corrected its minor7mm desk-clearance finding.
