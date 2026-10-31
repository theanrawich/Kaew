import json
from pathlib import Path
import FreeCAD as App
import Part, Mesh

OUT=Path(__file__).resolve().parent
doc=App.openDocument(str(OUT/'kaew-full-assembly-v1.FCStd'))
objects=[o for o in doc.Objects if hasattr(o,'Shape') and hasattr(o,'BomId')]
solids=[o for o in objects if o.ObjectKind=='part' and o.AssemblyZone not in ['Fasteners','ExternalPower']]
issues=[]
def overlaps(a,b):
    aa=a.Shape.BoundBox;bb=b.Shape.BoundBox
    return all([aa.XMax>bb.XMin+.001,bb.XMax>aa.XMin+.001,aa.YMax>bb.YMin+.001,bb.YMax>aa.YMin+.001,aa.ZMax>bb.ZMin+.001,bb.ZMax>aa.ZMin+.001])
for i,a in enumerate(solids):
    for b in solids[i+1:]:
        if not overlaps(a,b):continue
        if a.Material in ['Cable','Silicone'] or b.Material in ['Cable','Silicone']:continue
        v=a.Shape.common(b.Shape).Volume
        if v>.1:issues.append({'a':a.Name,'b':b.Name,'volume_mm3':round(v,3)})
frame=[o for o in objects if o.Material in ['PETG','Acrylic'] and o.ObjectKind=='part']
fluid=[o for o in objects if o.Material=='Silicone' and o.AssemblyZone=='Fluid']
hose_issues=[]
for h in fluid:
    for f in frame:
        if not overlaps(h,f):continue
        v=h.Shape.common(f.Shape).Volume
        if v>.1:hose_issues.append({'hose':h.Name,'frame':f.Name,'volume_mm3':round(v,3)})
harness_issues=[]
for h in [o for o in objects if o.Material=='Cable']:
    for f in frame:
        if not overlaps(h,f):continue
        v=h.Shape.common(f.Shape).Volume
        if v>.1:harness_issues.append({'harness':h.Name,'frame':f.Name,'volume_mm3':round(v,3)})
report={'valid_objects':sum(o.Shape.isValid() for o in objects),'object_count':len(objects),
        'rigid_intersections':issues,'hose_frame_intersections':hose_issues,
        'harness_frame_intersections':harness_issues,
        'status':'DIAGNOSTIC - contacts reviewed individually before release'}
(OUT/'fit-diagnostic.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
