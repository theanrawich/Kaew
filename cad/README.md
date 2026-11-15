# Kaew CAD working files

Start with [the handoff](../docs/CAD_HANDOFF.md). These are mechanical design proposals, not a manufacturing release.

`kaew-full-assembly-20261106.zip` is the current geometry snapshot (6 November 2026), including native FreeCAD, STEP/STL and custom-part exports. Extract into `cad/`, preserving the subdirectories. It is self-contained; the older October 31 archive has been removed. Native exports remain ignored by `cad/.gitignore`.

- `spout-v1/`: two-half PETG mast/spout sources, estimate and export verification.
- `full-assembly-v1/`: assembly builder/checker and diagnostic reports. Sources have subsequent unexecuted edits; rebuild and inspect fresh logs before treating geometry as current. Known interference findings remain.
- `site/cad-model.json`: optional local FreeCAD mesh export made by `.work/export-cad-colors.py`, ignored and not stored in git. The Pages CAD viewer offers the zip when no mesh is exported. The conceptual 3D homepage is built independently.

The November 6 snapshot and hash-linked diagnostics describe that revision. A later supplier listing indicated a 13 × 13 mm load cell rather than the modeled 12.7 × 12.7 mm envelope; the fit proposal has not been rebuilt or checked. See the handoff for remaining work. Install FreeCAD separately; no installer is stored here.
