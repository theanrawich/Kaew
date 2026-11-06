"""Read exports back and report mechanical clearances; not a release test."""
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
import FreeCAD as App
import Part, Mesh

out = Path(__file__).resolve().parent
doc = App.openDocument(str(out / 'kaew-full-assembly-v1.FCStd'))
objects = [o for o in doc.Objects if hasattr(o, 'ObjectKind')]
normal = [o for o in objects if o.ObjectKind not in ('service', 'reserved')]
assembly = Part.read(str(out / 'kaew-full-assembly-v1.step'))
native_volume = sum(o.Shape.Volume for o in normal)
exports = []
for step_path in sorted((out / 'custom-parts-current').glob('*.step')):
    obj = doc.getObject(step_path.stem)
    shape = Part.read(str(step_path))
    row = {'name': step_path.stem, 'step_valid': shape.isValid(),
           'step_volume_delta_mm3': round(shape.Volume - obj.Shape.Volume, 4),
           'step_solids': len(shape.Solids)}
    stl = step_path.with_suffix('.stl')
    if stl.exists():
        mesh = Mesh.Mesh(str(stl))
        row.update(stl_closed=mesh.isSolid(),
                   stl_relative_volume_error=abs(abs(mesh.Volume)-obj.Shape.Volume)/obj.Shape.Volume)
    exports.append(row)
service = []
for envelope in [o for o in objects if o.ObjectKind == 'service']:
    for item in normal:
        if item.Material in ('Cable', 'Silicone') or item.AssemblyZone in ('Fasteners','ExternalPower'):
            continue
        if not envelope.Shape.BoundBox.intersect(item.Shape.BoundBox):
            continue
        volume = envelope.Shape.common(item.Shape).Volume
        if volume > 0.1:
            service.append({'envelope': envelope.Name, 'item': item.Name, 'volume_mm3': round(volume, 2)})
platform = doc.getObject('Floating_cup_platform')
distances = {}
for name in ['Fixed_drip_surround','HX711_guard','Loadcell_fixed_spacer','Loadcell_moving_spacer','Load_cell_1kg']:
    distances[name] = round(platform.Shape.distToShape(doc.getObject(name).Shape)[0], 4)
report = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
          'sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                     [out/'build_assembly.py',out/'check_fit.py',out/'kaew-full-assembly-v1.FCStd',out/'kaew-full-assembly-v1.step']},
          'freecad_version': App.Version()[:3], 'assembly_step_valid': assembly.isValid(),
          'assembly_step_volume_delta_mm3': round(assembly.Volume-native_volume, 4),
          'exports': exports, 'service_envelope_intersections_unreviewed': service,
          'platform_minimum_distances_mm': distances,
          'limitations': 'Intersection and distance checks do not establish physical strength, mounting, cable bend clearance, water safety or serviceability.'}
(out/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
