# CAD continuation

- Read `../CAD_HANDOFF.md` and `full-assembly-v1/DESIGN.md` before changing the assembly.
- The checked-in Python builder/checker are newer than the archived full-assembly geometry and diagnostic reports. Rebuild and inspect fresh logs/results before relying on a snapshot. FreeCADCmd can exit with code 0 after a Python exception.
- The user has no physical parts and explicitly chose using specifications. Preserve source/revision uncertainty for undocumented marketplace dimensions; do not silently scale parts or promote estimates to confirmed manufacturer dimensions.
- Keep the flow meter as a reservation until a real model is selected. Separate physical mounting/clearance validation from unverified electrical or food-contact claims.
- Native CAD/STEP/STL/image snapshots are distributed in the archive described in `README.md`. Keep logs, caches, installers and unrelated coursework out of Git.
