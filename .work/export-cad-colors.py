import FreeCAD as App
import json, os, traceback
from pathlib import Path
try:
    root=Path(__file__).resolve().parent.parent
    doc=App.openDocument(str(root/'cad/full-assembly-v1/kaew-full-assembly-v1.FCStd'))
    result=[]
    for obj in doc.Objects:
        if not hasattr(obj,'ObjectKind') or obj.ObjectKind in ('service','reserved'): continue
        vertices, triangles=obj.Shape.tessellate(0.35)
        if not triangles: continue
        result.append({'name':obj.Name,'color':json.loads(obj.ColorJSON),'transparent':obj.Material in ('Glass','Bottle'),'attributes':{'position':{'array':[c for p in vertices for c in (p.x,p.y,p.z)]}},'index':{'array':[i for t in triangles for i in t]}})
    (root/'cad-model.json').write_text(json.dumps(result,separators=(',',':')),encoding='utf-8')
    print('KAEW_EXPORT_OK',len(result))
except Exception:
    traceback.print_exc()

