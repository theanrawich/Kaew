# Kaew full CAD assembly — design brief and verification plan

User request, 31 October 2026: model the whole dispenser in CAD, install every BOM part, and make the assembly accurate. FreeCAD 1.1.4 is installed. Work is a mechanical assembly design, not a change to the published website or a release for manufacture.

## Deliverable

An editable FreeCAD document, assembly STEP, individual custom-part STEP/STL, a dimension/source register tied to all 23 current BOM rows, assembly/cutaway/exploded images, and a machine-readable fit report. Buying packs of six bottles/cups corresponds to one installed item and five spares each. The unselected flow meter remains a transparent reserved envelope and is never called an installed, fitted sensor.

## Mechanical arrangement

- Retain 220 × 350 mm footprint. A 5 mm acrylic base sits at z11..16 on feet. This maintains the previous reference top at z16.
- Reuse the two PETG clamshell spout halves, adding a separate electrical passage. The silicone hose and electrical trunk remain separate. Tip remains at z165 and cup rim at z131.5.
- Place the pump sideways at the rear: estimated housing 125 across × 80 fore/aft × 40 high, with motor/head and controls represented. It does not support the bottle. A 200 × 120 × 5 mm acrylic shelf on four metal posts carries the bottle independently, with removable retaining rings and a level-sensor saddle.
- Add the 126 × 54 × 135 mm upper electronics housing, removable front, OLED aperture, emergency button and speaker/microphone openings. Board cradles grip PCB edges rather than inventing mounting holes on the holeless S3 board. Keep antenna zones and USB insertion volumes clear.
- Load cell is between a fixed end spacer and moving end spacer. The floating 132 mm platform is supported only by its load-cell end. Fixed drip surround and HX711 guard stay clear of the moving platform.
- Put buck, MOSFET, interface/protection protoboard, fuse and connectors in a separate base service bay beside the pump. XY-3606 is provisionally 63 × 27 mm, not a small 26 mm board. Two external power sources are represented because pump voltage/interface is still unconfirmed.
- Show TDS and temperature probes, pickup, vent and cable seals at the existing bottle cap. No invented bottle-cap thread is released. Include actual 3D harness paths and fasteners, distinguish wiring route proposals from an electrically validated circuit.

## Accuracy policy

Each item carries `BomId`, `DimensionStatus`, `Source`, `ManufacturingStatus` and material metadata inside CAD. Status is one of manufacturer reference, supplier/reference variant, estimate, design dimension, or reserved. Manufacturer dimensions of a different PCB revision are not promoted to verified dimensions of the selected marketplace item. Geometry must not be visually scaled to disguise an interference. Exact outside fit requires measuring the delivered pump, bottle, load cell and generic modules.

Sources already in the project govern chosen SKUs. Further sources: Espressif DevKitC-1 v1.1 mechanical documentation, LCDWIKI MC130GX module size, Ocean Nova Rock catalogue, XKC-Y25 documentation and Adafruit MAX98357A dimensions as a clearly labelled reference only. A full source register accompanies the files.

## Approaches

1. All printed body: gives a unified exterior but uses more material and requires splitting the long base for common printer beds.
2. Acrylic load-bearing base/shelf with PETG spine, cradles and housings: selected as the designer's working proposal, matching the existing low-cost plan and avoiding a large unverified printed bottle shelf.
3. Aluminium profile skeleton with covers: adjustable but bulkier and adds joints at this small footprint.

## Build and verification sequence

1. Define a component register with numeric dimensions, their provenance, uncertainties and installed quantities. Create independent purchased-part solids with visible connectors/headers and relevant interfaces.
2. Build the base, shelf, posts, spout, bottle retainers, floating scale assembly and removable electronics enclosure around those parts. Derive holes from shared coordinates. Export fabrication solids separately from purchased items.
3. Route hose and wiring through dedicated apertures, add fasteners and mark candidate interfaces. Record contacts intentionally used for mounting. Reserve space, rather than a fabricated model, for the unspecified flow sensor.
4. Read back STEP/STL, check BRep validity, closed printed meshes, BOM coverage, selected rigid-body intersections, hose/frame intersections, load path clearances, nozzle alignment and board/USB service spaces. Report physical/supplier confirmation gaps separately.
5. Render assembled/cutaway/exploded CAD views, save files with names and visual properties, package deliverables and the source builder.

## Explicit limitations

No supplier quote, actual metrology, FEA, wiring approval, food-contact certification, pump interface validation or physical test is implied. A nonzero unknown-dimension list means the result is an assembly study for fit review, not a ready-to-order manufacturing release.
