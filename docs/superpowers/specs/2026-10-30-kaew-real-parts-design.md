# Kaew — real-parts 3D and shopping design

Final session revision: user selected the504THB boxed10–250ml/min pump and downgraded to139THB1.3-inch OLED. The current planning total is4,742THB. KPHM400/3.5-inch choices below are historical alternatives, not the implemented BOM. The new pump envelope80×125×40mm,72mmwithhead is explicitly estimated from photos. Low-flow sensing remains a300THBhold with no confirmed SKU. See `KAEW_SHOPPING_LIST.md` and `kaew-bom.json` for the current sources and uncertainty.

User choices: continue the existing tabletop design; Crystal 1.5 L upright bottle; choose a suitable glass; flexible budget; deliver a realistic interactive HTML, not production CAD. The user directed online dimension research instead of requesting bottle measurements. Work proceeds with supported dimensions and explicit uncertainty.

Approaches: continue the existing Three.js viewer (selected by user), or replace the enclosure/layout entirely (not selected). Keep one self-contained offline HTML and its existing simulation. No physical orders or firmware work.

Selected glass: Ocean Nova Rock B06511, nominal 300 ml, top diameter 83 mm, base 63 mm, height 90 mm from the manufacturer catalogue. ILI9488 3.5-inch display reference: active 73.44×48.96 mm, MSP3520 board 98×56.34 mm; the seller revision still needs matching. Kamoer KPHM400 brush-motor drawing: 111.6×68.6×62.7 mm; use a dedicated rear pump pod below the bottle.

Proposed enclosure footprint: 220×350 mm, overall 450 mm with hose arch. Bottle study dimensions: diameter 85, height 320, cap diameter 30 mm, explicitly estimated. Online pack dimensions are 171.3×250×327.5 mm for six bottles including packaging, NOT individual-bottle dimensions or a cap-thread drawing. Do not relabel them as verified individual dimensions. Reconstruct the bottle's faceted shape, blue cap and label from the Lotus reference photo.

Materials: porcelain polymer shell, fine surface roughness, dark silicone feet, brushed metal nozzle, optically clear thick glass, PET bottle, clear water. Retain Kaew's quiet mint identity. Colors: shell #e9eeea, background #edf1ef, ink #203c43, accent #32796b, Crystal cap #079bc7, metal #bdc7c6. Typography uses local Tahoma/Segoe UI for offline Thai readability. The dominant visual is the product, with a narrow right-hand inspector and budget list; no decorative card grid.

Interaction: orbit/zoom, four fixed views, exploded slider, cutaway internals, dimension annotations, optional desk context, fill/sip/stop/reminder simulation, PNG export, downloadable budget CSV. Explain that scale in the model is millimetres; screen pixels are not physical 1:1. Maintain separation between purchased specifications, reference-series dimensions and proposed/estimated geometry. A point level switch must not be described as measuring continuous bottle volume; remaining ml in the viewer is simulation only.

Budget: data-driven list with actual required pack quantities, Shopee listing links and search date. Separate displayed listing prices, mixed-variant candidates, fabrication allowances, shipping allowance and contingency. Do not claim checkout prices, confirmed stocks or drinking-water material certification. No API recurring cost is bundled into hardware.

Validation: build the standalone HTML, independently recompute totals, verify each BOM link and quantity, inspect desktop/mobile and front/rear/exploded/cutaway screenshots, exercise cup/stop/refill controls and export, check no external runtime resources and no console/runtime errors. Preserve the earlier HTML as a local backup before rebuilding.
