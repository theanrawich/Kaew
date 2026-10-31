"""Read the exported formats back independently before handing them over."""
import json
from pathlib import Path
import FreeCAD as App
import Part
import Mesh

root=Path(__file__).resolve().parent
doc=App.openDocument(str(root/'kaew-spout-v1.FCStd'))
parts=[doc.getObject(name) for name in ['LeftShell','RightShell']]
assert all(p.Shape.isValid() and len(p.Shape.Solids)==1 for p in parts)
cad_volume=sum(p.Shape.Volume for p in parts)
step=Part.read(str(root/'kaew-spout-v1.step'))
assert step.isValid() and len(step.Solids)==2
assert abs(step.Volume-cad_volume)<0.1
meshes=[]
for part in parts:
    mesh=Mesh.Mesh(str(root/(part.Name+'.stl')))
    assert mesh.isSolid()
    assert abs(abs(mesh.Volume)-part.Shape.Volume)/part.Shape.Volume<0.005
    meshes.append({'name':part.Name,'closed':mesh.isSolid(),'triangles':mesh.CountFacets,'volume_cm3':round(abs(mesh.Volume)/1000,3)})
report={'freecad_version':App.Version()[:3],'native_valid_solids':2,'step_valid_solids':len(step.Solids),
        'step_volume_difference_mm3':step.Volume-cad_volume,'stl':meshes,
        'checks_do_not_establish':'Physical stiffness, tube bend suitability, slicer settings or assembly fit'}
(root/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
