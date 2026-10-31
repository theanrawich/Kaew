# Kaew CAD working files

Start with [the handoff](../CAD_HANDOFF.md). These are mechanical design proposals, not a manufacturing release.

- `spout-v1/`: two-half PETG mast/spout, checked independently; source, original estimate and export-verification report.
- `full-assembly-v1/`: all 23 BOM rows represented across 156 CAD objects in the last generated snapshot. This snapshot has known interference findings. Builder and checker have subsequent, **unexecuted** edits.
- `kaew-cad-snapshots-20261031.zip`: native FreeCAD/STEP/STL snapshots, custom-part exports and images. Extract **into this `cad` directory**, preserving the two subdirectories. The archive contains geometry/images only; current Python sources and status documents are stored separately in Git.

The full-assembly file must be rebuilt and checked before its dimensions, print mass or clearances are described as current or passing. Scripts are relative to the repository and can be run from another machine. Install FreeCAD separately; the application/installer is not stored here.
