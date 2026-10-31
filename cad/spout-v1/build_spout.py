"""Kaew spout assembly study. Run with FreeCADCmd; units are millimetres.

This is a dimensioned design proposal, not a released or load-tested part.
The existing production viewer is deliberately not a dependency of this model.
"""
import json
import math
from pathlib import Path
import FreeCAD as App
import Part
import MeshPart

OUT = Path(__file__).resolve().parent
OUT.mkdir(parents=True, exist_ok=True)
V = App.Vector
P = dict(wall_mm=2.4, width_mm=42.0, mast_depth_mm=36.0,
         base_top_mm=16.0, top_mm=206.0, reach_mm=112.0,
         nozzle_forward_mm=92.0, nozzle_tip_mm=165.0,
         hose_od_assumed_mm=8.0, bend_center_radius_proposed_mm=20.0,
         petg_density_assumed_g_cm3=1.27)
doc = App.newDocument("KaewSpoutConceptV1")
params = doc.addObject("App::FeaturePython", "DesignParameters")
params.Label = "Proposal parameters - verify actual hose and base"
for name, value in P.items():
    params.addProperty("App::PropertyFloat", name, "Concept").__setattr__(name, value)

def side_face(inner=False):
    # Explicit circular corners avoid approximate mesh booleans.
    if not inner:
        path = [(-36,16), (-36,194),
                ((-32.485281,202.485281),(-24,206)), (100,206),
                ((108.485281,202.485281),(112,194)), (112,184),
                ((108.485281,175.514719),(100,172)), (14,172),
                ((4.100505,167.899495),(0,158)), (0,16), (-36,16)]
    else:
        path = [(-33.6,18.4), (-33.6,194),
                ((-30.788225,200.788225),(-24,203.6)), (100,203.6),
                ((106.788225,200.788225),(109.6,194)), (109.6,184),
                ((106.788225,177.211775),(100,174.4)), (14,174.4),
                ((2.403449,169.596551),(-2.4,158)), (-2.4,18.4), (-33.6,18.4)]
    edges=[]
    prev=V(0,*path[0])
    for item in path[1:]:
        if isinstance(item[0], tuple):
            mid,end=item
            nxt=V(0,*end)
            edges.append(Part.Arc(prev,V(0,*mid),nxt).toShape())
        else:
            nxt=V(0,*item)
            edges.append(Part.makeLine(prev,nxt))
        prev=nxt
    return Part.Face(Part.Wire(edges))

def feature(name, label, shape, group, color):
    obj=doc.addObject("PartDesign::Feature",name)
    obj.Label=label
    obj.Shape=shape
    group.addObject(obj)
    if App.GuiUp:
        obj.ViewObject.ShapeColor=color
        obj.ViewObject.LineColor=(0.23,0.31,0.29)
    return obj

printed=doc.addObject("App::DocumentObjectGroup","PrintedParts")
printed.Label="PRINT - two PETG clamshell halves"
context=doc.addObject("App::DocumentObjectGroup","ContextOnly")
context.Label="REFERENCE ONLY - excluded from print mass and STL"

outer=side_face().extrude(V(42,0,0))
outer.translate(V(-21,0,0))
inner=side_face(True).extrude(V(37.2,0,0))
inner.translate(V(-18.6,0,0))
foot=Part.makeBox(42,68,8,V(-21,-52,16))
vertical_edges=[e for e in foot.Edges if abs(e.Vertexes[-1].Point.z-e.Vertexes[0].Point.z)>7.99]
foot=foot.makeFillet(5,vertical_edges)
shell=outer.fuse(foot).cut(inner)

# Four base fixings outside the thin mast walls, bearing through the foot.
base_holes=[(x,y) for x in [-13,13] for y in [-45,9]]
for x,y in base_holes:
    shell=shell.cut(Part.makeCylinder(2.25,12,V(x,y,14),V(0,0,1)))
shell=shell.cut(Part.makeCylinder(4.75,28,V(0,-18,8),V(0,0,1)))

# Bosses are kept clear of the assumed hose sweep and carry the clamp screws.
screw_locations=[(-29,37),(-29,107),(-28,192),(22,200.2),(60,179),(102,190)]
for y,z in screw_locations:
    shell=shell.fuse(Part.makeCylinder(5.5,42,V(-21,y,z),V(1,0,0)))

# Split exit guide retains the existing silicone hose; no printed water lumen.
shell=shell.fuse(Part.makeBox(16,16,8,V(-8,84,172)))
shell=shell.cut(Part.makeCylinder(4.4,40,V(0,92,157),V(0,0,1)))
for y,z in screw_locations:
    shell=shell.cut(Part.makeCylinder(1.7,44,V(-22,y,z),V(1,0,0)))
    shell=shell.cut(Part.makeCylinder(3.0,3.0,V(18,y,z),V(1,0,0)))
    radius=5.8/math.sqrt(3)
    pts=[V(-21.1,y+radius*math.cos(k*math.pi/3),z+radius*math.sin(k*math.pi/3)) for k in range(6)]
    pts.append(pts[0])
    nut=Part.Face(Part.makePolygon(pts)).extrude(V(2.8,0,0))
    shell=shell.cut(nut)
shell=shell.removeSplitter()

# Proposed continuous OD8 mm hose, including generous routing at both elbows.
points=[V(0,-18,16),V(0,-18,170),V(0,2,190),V(0,72,190),V(0,92,170),V(0,92,165)]
hose_path=Part.Wire([
    Part.makeLine(points[0],points[1]),
    Part.Arc(points[1],V(0,-12.142136,184.142136),points[2]).toShape(),
    Part.makeLine(points[2],points[3]),
    Part.Arc(points[3],V(0,86.142136,184.142136),points[4]).toShape(),
    Part.makeLine(points[4],points[5])])
hose_circle=Part.Wire([Part.makeCircle(4,points[0],V(0,0,1))])
hose=hose_path.makePipeShell([hose_circle],True,False)
feature("Hose","Existing continuous silicone hose - OD8 assumed",hose,context,(0.10,0.57,0.62))

# Clearance follows the curved hose, including its exit turn. A vertical bore
# alone clipped the hose before the bend reached its vertical tangent.
clearance_circle=Part.Wire([Part.makeCircle(4.75,points[0],V(0,0,1))])
shell=shell.cut(hose_path.makePipeShell([clearance_circle],True,False)).removeSplitter()
halves=[]
for name,label,clip in [
    ("LeftShell","01 Left shell - M3 nut pockets",Part.makeBox(100,300,300,V(-100,-100,0))),
    ("RightShell","02 Right shell - M3 head pockets",Part.makeBox(100,300,300,V(0,-100,0)))
]:
    shape=shell.common(clip).removeSplitter()
    if not shape.isValid() or len(shape.Solids)!=1:
        raise RuntimeError(f"Invalid part: {name}; solids={len(shape.Solids)}")
    halves.append(feature(name,label,shape,printed,(0.86,0.90,0.84)))

# Verify swept hose does not collide with either half at this nominal OD.
interference=[obj.Shape.common(hose).Volume for obj in halves]
if max(interference)>0.05:
    raise RuntimeError(f"Hose interference in mm3: {interference}")
base=Part.makeBox(220,350,16,V(-110,-175,0))
feature("ReferenceBase","Reference base envelope 220 x 350 - NOT PRINTED",base,context,(0.77,0.82,0.76))
cup_outer=Part.makeCone(31.5,41.5,90,V(0,92,41.5))
cup_inner=Part.makeCone(29.0,39.5,87.5,V(0,92,44.0))
cup=feature("ReferenceCup","Reference cup - rim z131.5",cup_outer.cut(cup_inner),context,(0.78,0.90,0.91))
if App.GuiUp:
    cup.ViewObject.Transparency=75
display=Part.makeBox(126,54,135,V(-63,-54,206))
feature("ReferenceDisplay","Display enclosure envelope - mounting TBD - NOT PRINTED",display,context,(0.85,0.89,0.83))

doc.recompute()
rows=[]
for obj in halves:
    mesh=MeshPart.meshFromShape(Shape=obj.Shape,LinearDeflection=0.08,AngularDeflection=0.15,Relative=False)
    mesh.write(str(OUT/(obj.Name+".stl")))
    # Mesh JSON is for a portable design preview, not a second source of shape.
    verts,faces=mesh.Topology
    geometry={"vertices":[[v.x,v.y,v.z] for v in verts],"faces":[list(f) for f in faces]}
    (OUT/(obj.Name+".mesh.json")).write_text(json.dumps(geometry,separators=(",",":")))
    volume=obj.Shape.Volume/1000
    rows.append(dict(part=obj.Name,volume_cm3=round(volume,3),
                     solid_petg_mass_g=round(volume*P["petg_density_assumed_g_cm3"],1),
                     valid=obj.Shape.isValid(),solids=len(obj.Shape.Solids),
                     closed_mesh=mesh.isSolid(),triangles=mesh.CountFacets,
                     bbox_mm=[round(v,2) for v in [obj.Shape.BoundBox.XLength,obj.Shape.BoundBox.YLength,obj.Shape.BoundBox.ZLength]]))

total=sum(r["solid_petg_mass_g"] for r in rows)
summary={"status":"CONCEPT - fit and load not physically validated", "parameters":P,"parts":rows,
         "nominal_cad_plastic_mass_g":round(total,1),
         "allowance_with_brim_support_and_slicer_variation_g":[math.ceil(total),math.ceil(total*1.2)],
         "hose_interference_mm3":interference,
         "nozzle_to_cup_rim_clearance_mm":33.5,
         "base_mount_holes_xy_mm":base_holes,
         "screws":"6 x M3x40 with M3 nuts; 4 x M4 through base, length after actual base thickness",
         "print_orientation":"Each half outer flat x-face on the build plate; open mating face up. The foot stays within the shell width. Slicer review still required.",
         "verify_before_print":["Actual silicone tube OD and manufacturer bend radius; R20 is a proposal, not a verified minimum", "Hose guide clearance, screw and nut fit using a small test coupon", "Actual base and upper display mounting interfaces", "Print orientation and slicer support/mass", "Cantilever stiffness, sustained load/creep and splash behaviour"]}
(OUT/"estimate.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
Part.export(halves,str(OUT/"kaew-spout-v1.step"))
doc.saveAs(str(OUT/"kaew-spout-v1.FCStd"))
print(json.dumps(summary,indent=2))
