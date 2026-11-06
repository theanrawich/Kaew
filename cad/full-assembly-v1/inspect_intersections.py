"""Report locations of the cable/frame intersections in the current study."""
import json
from pathlib import Path
import FreeCAD as App

out = Path(__file__).resolve().parent
doc = App.openDocument(str(out / 'kaew-full-assembly-v1.FCStd'))
report = json.loads((out / 'fit-diagnostic.json').read_text())
for issue in report['harness_frame_intersections']:
    cable = doc.getObject(issue['harness'])
    frame = doc.getObject(issue['frame'])
    common = cable.Shape.common(frame.Shape)
    b = common.BoundBox
    print('{} / {}: x={:.1f}..{:.1f} y={:.1f}..{:.1f} z={:.1f}..{:.1f}'.format(
        cable.Name, frame.Name, b.XMin, b.XMax, b.YMin, b.YMax, b.ZMin, b.ZMax))
