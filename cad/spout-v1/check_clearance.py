from pathlib import Path
source=Path(__file__).with_name('build_spout.py')
exec(compile(source.read_text(encoding='utf-8').split('# Verify swept hose')[0],str(source),'exec'))
checks=[('shell',shell),('wall_without_bosses',outer.fuse(foot).cut(inner).cut(Part.makeCylinder(4.75,28,V(0,-18,8),V(0,0,1))))]
checks += [(str((y,z)),Part.makeCylinder(5.5,42,V(-21,y,z),V(1,0,0))) for y,z in screw_locations]
for label,shape in checks:
    collision=shape.common(hose)
    solids=[]
    for s in collision.Solids:
        b=s.BoundBox
        solids.append({'volume':s.Volume,'bounds':[b.XMin,b.XMax,b.YMin,b.YMax,b.ZMin,b.ZMax]})
    print(label,collision.Volume,solids)
