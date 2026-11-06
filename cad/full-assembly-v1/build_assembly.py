"""Full Kaew mechanical assembly study; FreeCAD 1.1.4, millimetres.

Run with FreeCADCmd. Purchased-part geometry is explicitly a documented
reference or an envelope when the selected vendor has no mechanical drawing.
"""
import csv, json, math
from pathlib import Path
import FreeCAD as App
import Part, MeshPart

OUT=Path(__file__).resolve().parent
ROOT=OUT.parent.parent
STL=OUT/'custom-parts-current'
STL.mkdir(parents=True,exist_ok=True)
V=App.Vector
BOM=json.loads((ROOT/'kaew-bom.json').read_text(encoding='utf-8-sig'))
REG={r['id']:{'id':r['id'],'label':r['label'],'purchase_quantity':r['qty'],
              'source':r.get('url') or 'Kaew mechanical design',
              'status':'supplier_variant_unconfirmed','objects':[],'notes':r.get('note','')}
     for r in BOM['rows']}
SOURCES={
 'gateway':'https://documentation.espressif.com/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.1.html',
 'display':'https://www.lcdwiki.com/1.3inch_IIC_OLED_Module_SKU:MC130GX',
 'cup':'https://www.ocean-glassware.com/products/nova-rock/',
 'level':'https://www.sz-xkc.com/detail/1432.html',
 'tds':'https://wiki.dfrobot.com/sen0244',
 'amplifier':'https://www.adafruit.com/product/3006',
 'buck':'https://www.gotronik.pl/przetwornica-napiecia-ladowarka-usb-5v-p-6422.html'}
DIMS={'gateway':[25.4,62.74,12],'node':[28,51.5,12],'display':[33.5,35.4,9],
      'pump':[125,80,72],'scale':[80,12.7,12.7],'flow':[30,36,30],
      'tds':[42,32,12],'temperature':[6,50],'level':[28,17],
      'microphone':[16,14,5],'amplifier':[19.4,17.8,10],
      'speaker':[40,15],'power':[80,42,32],'buck':[27,63,12],
      'driver':[17,17,12],'stop':[24,16,38],'tube':[8,5,2000],
      'cup':[83,63,90],'bottle':[85,320,30]}
for k,r in REG.items():
    r['nominal_dimensions_mm']=DIMS.get(k,[])
    r['reference_source']=SOURCES.get(k,'')
    r['actual_delivered_part_measured']=False
for k in ['pump','bottle','power']: REG[k]['status']='estimated_vendor_has_no_dimensioned_drawing'
for k in ['gateway','display','tds','amplifier','buck','level']: REG[k]['status']='reference_model_not_verified_selected_revision'
REG['cup']['status']='manufacturer_external_dimensions_internal_shape_simplified'
for k in ['enclosure','fittings','electrical','assembly']: REG[k]['status']='design_proposal'
REG['flow']['status']='reserved_no_sensor_selected'
REG['cup']['installed_quantity']=REG['bottle']['installed_quantity']=1
REG['cup']['spares_quantity']=REG['bottle']['spares_quantity']=5
REG['flow']['installed_quantity']=0

doc=App.newDocument('KaewFullAssemblyV1')
GROUPS={}
for name in ['Structure','Pump','Reservoir','Weighing','HeadElectronics','BaseElectronics','Fluid','Harness','Fasteners','ExternalPower','ServiceEnvelopes','Reserved']:
    GROUPS[name]=doc.addObject('App::DocumentObjectGroup',name)
COL={'PETG':(0.80,0.88,0.81),'Acrylic':(0.88,0.92,0.88),'Metal':(0.65,0.70,0.72),
     'PCB':(0.12,0.39,0.29),'Rubber':(0.13,0.18,0.17),'Silicone':(0.12,0.58,0.67),
     'Glass':(0.71,0.88,0.91),'Bottle':(0.66,0.83,0.87),'Pump':(0.91,0.90,0.82),
     'Cable':(0.20,0.26,0.25),'Reference':(0.95,0.66,0.24),'Black':(0.11,0.17,0.17)}
CUSTOM=[]; ITEMS=[]; CONTACTS=set(); ROUTES=[]; CRITICAL=[]

def box(w,d,h,p): return Part.makeBox(w,d,h,V(*p))
def cyl(r,h,p,axis=(0,0,1)): return Part.makeCylinder(r,h,V(*p),V(*axis))
def rounded(w,d,h,p,r=3):
    s=box(w,d,h,p)
    edges=[e for e in s.Edges if abs(e.Vertexes[-1].Point.z-e.Vertexes[0].Point.z)>h-.001]
    return s.makeFillet(min(r,w/3,d/3),edges)
def ring(ro,ri,h,p,axis=(0,0,1)): return cyl(ro,h,p,axis).cut(cyl(ri,h,p,axis))
def contact(a,b): CONTACTS.add(tuple(sorted((a.Name,b.Name))))
def add(name,shape,bom,group='Structure',mat='PETG',custom=False,notes='',kind='part',colors=None):
    if shape.isNull() or not shape.isValid(): raise RuntimeError('Invalid BRep: '+name)
    o=doc.addObject('PartDesign::Feature',name); o.Label=name.replace('_',' '); o.Shape=shape
    for key,value in {'BomId':bom,'Material':mat,'DimensionStatus':REG[bom]['status'],
                      'Source':REG[bom]['reference_source'] or REG[bom]['source'],
                      'ManufacturingStatus':'PROPOSAL - not a production release','Notes':notes,
                      'ObjectKind':kind,'AssemblyZone':group,'ColorJSON':json.dumps(COL.get(mat,COL['Reference']))}.items():
        o.addProperty('App::PropertyString',key,'Kaew'); setattr(o,key,value)
    if colors:
        o.addProperty('App::PropertyString','FaceColorsJSON','Kaew');o.FaceColorsJSON=json.dumps(colors)
    GROUPS[group].addObject(o); REG[bom]['objects'].append(name);ITEMS.append(o)
    if custom:CUSTOM.append(o)
    return o

def colored(pieces):
    return Part.makeCompound([s for s,c in pieces]),[c for s,c in pieces for f in s.Faces]

def screw(name,p,axis=(0,0,1),diam=3,length=10,group='Fasteners'):
    shaft=cyl(diam/2,length,p,axis); end=V(*p)+V(*axis)*length
    head=cyl(diam*.95,diam*.7,end.__iter__() if hasattr(end,'__iter__') else (end.x,end.y,end.z),axis)
    return add(name,shaft.fuse(head),'assembly',group,'Metal',notes='Nominal screw envelope; thread detail omitted')

def routed(points,radius=1.0,rounding=16):
    pts=[V(*p) for p in points];edges=[];last=pts[0];radii=[]
    for i in range(1,len(pts)-1):
        p=pts[i];u=pts[i-1]-p;v=pts[i+1]-p;la=u.Length;lb=v.Length;u.normalize();v.normalize()
        angle=math.acos(max(-1,min(1,u.dot(v))))
        if abs(math.pi-angle)<.001:continue
        if angle<.02:raise ValueError('Reversing route')
        trim=min(rounding,la*.45,lb*.45)
        a=p+u*trim;b=p+v*trim;bis=u+v;bis.normalize()
        bend=trim*math.tan(angle/2); mid=p+bis*(trim/math.cos(angle/2)-bend)
        if (a-last).Length>.001:edges.append(Part.makeLine(last,a))
        edges.append(Part.Arc(a,mid,b).toShape());last=b;radii.append(bend)
    if (pts[-1]-last).Length>.001:edges.append(Part.makeLine(last,pts[-1]))
    path=Part.Wire(edges);normal=edges[0].tangentAt(edges[0].FirstParameter)
    circ=Part.Wire([Part.makeCircle(radius,pts[0],normal)])
    return path.makePipeShell([circ],True,False),path.Length,min(radii) if radii else None

def route(name,points,r,bom='electrical',mat='Cable',rounding=16):
    shape,length,bend=routed(points,r,rounding)
    o=add(name,shape,bom,'Fluid' if mat=='Silicone' else 'Harness',mat,notes='Mechanical routing proposal; electrical interface and actual tube radius require confirmation')
    ROUTES.append({'name':name,'length_mm':round(length,2),'radius_mm':r,'minimum_center_bend_mm':round(bend,2) if bend else None})
    return o

def pcb_vertical(name,bom,w,h,x,z,y=-44,pins=0,dual_usb=False,rf=False):
    pieces=[(box(w,1.6,h,(x-w/2,y,z-h/2)),COL['PCB'])]
    if rf:
        pieces += [(box(18,2.6,21,(x-9,y+1.6,z+h/2-34)),COL['Metal']),
                   (box(17,1,11,(x-8.5,y+1.6,z+h/2-12)),COL['Black'])]
    else:pieces.append((box(min(w*.6,12),2.2,min(h*.35,9),(x-min(w*.6,12)/2,y+1.6,z-3)),COL['Black']))
    if pins:
        for side in [-1,1]:
            xp=x+side*(w/2-1.27)
            pieces.append((box(2.4,2.8,(pins-1)*2.54+2,(xp-1.2,y+1.6,z-(pins-1)*1.27-1)),COL['Black']))
            for i in range(pins):pieces.append((box(.64,6,.64,(xp-.32,y+4.4,z-(pins-1)*1.27+i*2.54-.32)),COL['Metal']))
    if rf:
        for dx in ([-6,6] if dual_usb else [0]):
            pieces.append((box(8.5,3.2,6.5,(x+dx-4.25,y+1.6,z-h/2-.8)),COL['Metal']))
    s,c=colored(pieces);return add(name,s,bom,'HeadElectronics','PCB',colors=c)

def pcb_horizontal(name,bom,w,d,x,y,z=24):
    pieces=[(box(w,d,1.6,(x-w/2,y-d/2,z)),COL['PCB']),
            (box(min(12,w*.6),min(12,d*.3),5,(x-min(12,w*.6)/2,y-4,z+1.6)),COL['Black']),
            (box(w-3,5,7,(x-w/2+1.5,y+d/2-5,z+1.6)),(0.15,.35,.65))]
    if bom=='buck':
        pieces +=[(cyl(6,5,(x,y,z+1.6)),COL['Metal']),
                  (box(14,14,6,(x-7,y+d/2-14,z+1.6)),COL['Metal'])]
    s,c=colored(pieces);return add(name,s,bom,'BaseElectronics' if bom not in ['scale'] else 'Weighing','PCB',colors=c)

# Main base: drilled acrylic rather than an unprintable 350 mm monolithic body.
spout_holes=[(x,y) for x in [-13,13] for y in [-45,9]]
post_holes=[(x,y) for x in [-90,90] for y in [-156,-56]]
base_shape=rounded(220,350,5,(-110,-175,11),6)
for x,y in spout_holes+post_holes:base_shape=base_shape.cut(cyl(2.25,7,(x,y,10)))
for x,y in [(0,-18),(11,-18)]:base_shape=base_shape.cut(cyl(5 if x==0 else 4.5,7,(x,y,10)))
base=add('Base_plate',base_shape,'enclosure',custom=True,mat='Acrylic',notes='220 x350 x5, feet raise top to z16')
for i,(x,y) in enumerate([(-95,-155),(95,-155),(-95,150),(95,150)]):
    add('Foot_'+str(i+1),ring(9,2.2,11,(x,y,0)),'assembly','Fasteners','Rubber')
for i,(x,y) in enumerate(post_holes):
    add('Shelf_post_'+str(i+1),ring(5,2.2,80,(x,y,16)),'assembly','Fasteners','Metal')
    screw('Shelf_lower_bolt_'+str(i+1),(x,y,8),diam=4,length=14)
    screw('Shelf_upper_bolt_'+str(i+1),(x,y,89),diam=4,length=12)
shelf_shape=rounded(200,120,5,(-100,-166,96),4)
for x,y in post_holes:shelf_shape=shelf_shape.cut(cyl(2.25,7,(x,y,95)))
for x,y in [(-85,-108),(-72,-93)]:shelf_shape=shelf_shape.cut(cyl(5,7,(x,y,95)))
shelf=add('Bottle_shelf',shelf_shape,'enclosure',custom=True,mat='Acrylic',notes='Removable shelf, independent pump load path')

# Import the previously checked actual spout solids, add a cable passage.
old=App.openDocument(str(ROOT/'cad/spout-v1/kaew-spout-v1.FCStd'))
spout_shapes=[old.getObject(n).Shape.copy() for n in ['LeftShell','RightShell']]
App.closeDocument(old.Name);App.setActiveDocument(doc.Name)
spout_parts=[]
for name,s in zip(['Spout_left','Spout_right'],spout_shapes):
    s=s.cut(cyl(4.5,40,(11,-18,8))).cut(cyl(4.5,22,(11,-18,195))).removeSplitter()
    spout_parts.append(add(name,s,'enclosure',custom=True,notes='Two removable halves; separate hose and electrical entries'))
for i,(y,z) in enumerate([(-29,37),(-29,107),(-28,192),(22,200.2),(60,179),(102,190)]):
    screw('Spout_M3_'+str(i+1),(-21,y,z),axis=(1,0,0),length=39)
for i,(x,y) in enumerate(spout_holes):screw('Spout_base_M4_'+str(i+1),(x,y,8),diam=4,length=17)

# Purchased pump envelope reconstructed from chosen vendor photos, not scaled to fit.
pump_shape=rounded(125,80,40,(-62.5,-151,18),3)
head=cyl(22,27.5,(-29,-122,58))
pump_shape=pump_shape.fuse(head).fuse(cyl(6.5,11,(34,-107,58)))
pump=add('Pump_10_250ml',pump_shape,'pump','Pump','Pump',notes='125x80x40 housing plus head are unverified estimates from project references; DC/interface unknown')
add('Pump_knob',cyl(5,2,(34,-107,69)),'pump','Pump','Black',kind='detail')
for x in [-55,55]:
    for y in [-144,-78]:
        add('Pump_pad_'+str(x)+'_'+str(y),cyl(5,2,(x,y,16)),'assembly','Pump','Rubber')
for x in [-66,63]:
    bracket=box(3,65,10,(x,-144,16));add('Pump_side_keeper_'+str(x),bracket,'enclosure','Pump',custom=True,notes='Side retention with slots, not guessed pump screw centres')
for i,y in enumerate([-131,-114]):
    add('Pump_hose_port_'+str(i+1),ring(3,2,13,(-64,y,72),(1,0,0)),'pump','Pump','Pump',notes='Proposed hose port location, verify pump head')

# Bottle and cap: simplified external profile, true hollow shell; no fake thread.
bx,by,bz=35,-108,101
profile=[(0,0),(28,0),(39,4),(42.5,12),(42.5,250),(40,264),(30,283),(14,298),(14,306),(0,306),(0,0)]
wire=Part.makePolygon([V(bx+r,by,bz+z) for r,z in profile])
outer=Part.Face(wire).revolve(V(bx,by,bz),V(0,0,1),360)
inner_profile=[(0,1.2),(27,1.2),(38,5),(41.3,13),(41.3,249),(39,263),(29,282),(12.8,298),(12.8,307),(0,307),(0,1.2)]
inner=Part.Face(Part.makePolygon([V(bx+r,by,bz+z) for r,z in inner_profile])).revolve(V(bx,by,bz),V(0,0,1),360)
bottle=add('Crystal_bottle_1p5L',outer.cut(inner),'bottle','Reservoir','Bottle',notes='OD85 total h320 including cap is a project estimate; not a manufacturer drawing')
cap_shape=cyl(15,14,(bx,by,407))
cap_shape=cap_shape.cut(cyl(13.3,11.5,(bx,by,406.5)))
cap_holes=[(29,-108,4.75),(40,-114,2.5),(40,-102,2.5),(45,-108,1.6)]
for x,y,r in cap_holes:cap_shape=cap_shape.cut(cyl(r,17,(x,y,406)))
cap=add('Original_cap_modified',cap_shape,'fittings','Reservoir','Black',notes='Original cap retained; holes/seals proposed. Thread/neck not verified, do not print as threaded replacement')
for i,(x,y,r) in enumerate(cap_holes):
    add('Cap_seal_'+str(i+1),ring(r+1.3,r,2,(x,y,421)),'fittings','Reservoir','Rubber')
add('Vent_tube',ring(1.6,1,8,(45,-108,420)),'fittings','Reservoir','Silicone')
rail=box(12,4,197,(29,-158,101));add('Bottle_rear_rail',rail,'enclosure','Reservoir',custom=True)
for level in [111,250]:
    full=ring(47,43.5,6,(bx,by,level))
    for suffix,clip in [('rear',box(200,100,30,(-65,by-100,level-1))),('front',box(200,100,30,(-65,by,level-1)))]:
        half=full.common(clip)
        for sx in [-47.5,47.5]:
            ear=box(8,8,8,(bx+sx-4,by-8 if suffix=='rear' else by,level-1))
            half=half.fuse(ear).cut(cyl(1.7,20,(bx+sx,by-10,level+3),(0,1,0)))
        if suffix=='rear':half=half.cut(box(12.4,5,10,(28.8,-158.2,level-2)))
        add('Bottle_ring_'+str(level)+'_'+suffix,half,'enclosure','Reservoir',custom=True,notes='Split removable ring with rear-rail clearance; not a force fit on bottle')
    for n,sx in enumerate([-47.5,47.5]):screw('Ring_M3_'+str(level)+'_'+str(n),(bx+sx,by-8,level+3),(0,1,0),length=17)
level_sensor=add('XKC_Y25_NPN',cyl(14,17,(77.5,-108,140),(1,0,0)),'level','Reservoir','Pump',notes='Reference OD28 x17, verify NPN revision and cable')
holder=ring(17,14.3,18,(77.8,-108,140),(1,0,0)).fuse(box(4,34,60,(95,-125,101)))
holder=holder.cut(cyl(2.5,8,(94,-108,140),(1,0,0)))  # level-sensor cable exit
add('Level_sensor_saddle',holder,'enclosure','Reservoir',custom=True)
tds_probe=add('TDS_probe',cyl(6,28,(43,-116,114)),'tds','Reservoir','Black')
add('TDS_electrode_A',cyl(.6,8,(40,-116,108)),'tds','Reservoir','Metal',kind='detail')
add('TDS_electrode_B',cyl(.6,8,(46,-116,108)),'tds','Reservoir','Metal',kind='detail')
temp_probe=add('DS18B20_probe',cyl(3,50,(27,-104,116)),'temperature','Reservoir','Metal')

# Scale: only one fixed end and one moving end; no platform/rim contact.
tray_shape=rounded(144,144,19,(-72,20,16),5).cut(rounded(138,138,20,(-69,23,15.5),3))
tray_shape=tray_shape.cut(box(7,6,7,(-58.5,19,22)))  # HX711 cable slot
tray=add('Fixed_drip_surround',tray_shape,'enclosure','Weighing',custom=True)
beam_shape=box(80,12.7,12.7,(-40,85.65,20))
beam_shape=beam_shape.cut(cyl(4.8,15,(0,84.5,26.35),(0,1,0)))
for x in [-35,-25,25,35]:beam_shape=beam_shape.cut(cyl(1.8,15,(x,92,19)))
beam=add('Load_cell_1kg',beam_shape,'scale','Weighing','Metal',notes='80x12.7x12.7 reference envelope; hole pitch/threads are proposed, not verified 1kg vendor drawing')
fixed_shape=box(20,12.7,4,(-40,85.65,16));moving_shape=box(20,12.7,3.8,(20,85.65,32.7))
platform_shape=rounded(132,132,5,(-66,26,36.5),4)
for x in [-35,-25]:
    fixed_shape=fixed_shape.cut(cyl(1.8,7,(x,92,15)))
    base.Shape=base.Shape.cut(cyl(1.8,7,(x,92,10)))
for x in [25,35]:
    moving_shape=moving_shape.cut(cyl(1.8,7,(x,92,31)))
    platform_shape=platform_shape.cut(cyl(1.8,7,(x,92,35))).cut(Part.makeCone(1.8,3.5,2,V(x,92,39.5)))
fixed=add('Loadcell_fixed_spacer',fixed_shape,'enclosure','Weighing',custom=True)
moving=add('Loadcell_moving_spacer',moving_shape,'enclosure','Weighing',custom=True)
platform=add('Floating_cup_platform',platform_shape,'enclosure','Weighing',custom=True,mat='Acrylic')
for i,x in enumerate([-35,-25]):screw('Loadcell_fixed_M3_'+str(i),(x,92,7.7),length=25)
for i,x in enumerate([25,35]):
    flat=cyl(1.5,9.3,(x,92,30.5)).fuse(Part.makeCone(1.5,3.2,1.7,V(x,92,39.8)))
    add('Loadcell_flush_M3_'+str(i),flat,'assembly','Fasteners','Metal',notes='Countersunk head flush with cup platform')
for i,(x,y) in enumerate([(-53,31),(53,31),(-53,145),(53,145)]):
    add('Overload_stop_'+str(i+1),cyl(2,19.5,(x,y,16)),'assembly','Weighing','Metal',notes='Proposed 1mm gap to moving plate; set after actual load-cell deflection')
hx=pcb_horizontal('HX711','scale',34,20,-40,52,21)
guard=rounded(44,30,17,(-62,37,16),3).cut(box(39,25,15,(-59.5,39.5,16)))
guard=guard.cut(box(10,5,5,(-45,62,18)))
guard=guard.cut(box(8,8,8,(-44,61,21))).cut(box(8,8,8,(-59,35,21)))
add('HX711_guard',guard,'enclosure','Weighing',custom=True)
cup_shape=Part.makeCone(31.5,41.5,90,V(0,92,41.5)).cut(Part.makeCone(29,39.5,87.5,V(0,92,44)))
cup=add('Ocean_Nova_Rock_B06511',cup_shape,'cup','Weighing','Glass',notes='Manufacturer outside diameters/height; wall and inner surface simplified')

# Electronics case and removable front, with actual openings and shared datums.
body_shape=rounded(126,54,135,(-63,-54,206),4).cut(box(121.2,60,130.2,(-60.6,-51.6,208.4)))
body_shape=body_shape.cut(cyl(4.5,8,(11,-18,203)))
# Three separate cable entrances through the right wall, with clearance.
for z in (215,239,282):
    body_shape=body_shape.cut(box(12,10,14,(57,-55,z-7)))
body_shape=body_shape.cut(box(12,19,14,(57,-55,232)))  # TDS approaches ahead of cradle
case=add('Upper_case',body_shape,'enclosure',custom=True,notes='Upper electronics; removable front')
front_shape=box(126,3,135,(-63,0,206))
front_shape=front_shape.cut(box(31,5,16.3,(-15.5,-1,305.85)))
for x,z,r in [(-30,247,17.5),(0,249,8.2),(25,220,1.5)]:front_shape=front_shape.cut(cyl(r,6,(x,-1,z),(0,1,0)))
for x,z in [(-56,214),(56,214),(-56,333),(56,333)]:front_shape=front_shape.cut(cyl(1.7,6,(x,-1,z),(0,1,0)))
front=add('Front_panel',front_shape,'enclosure',custom=True)
# Back-of-case through bolts secure case to mast; no floating enclosure.
bridge=box(40,24,4,(-20,-30,208.4)).cut(cyl(4.5,6,(11,-18,207.4)))
for x in [-14,14]:
    bridge=bridge.cut(cyl(1.8,7,(x,-11,207)))
    case.Shape=case.Shape.cut(cyl(1.8,7,(x,-11,204)))
    for sp in spout_parts:sp.Shape=sp.Shape.cut(cyl(1.8,12,(x,-11,197)))
add('Head_mount_bridge',bridge,'enclosure',custom=True,notes='Shared attachment plate, M3 through fixings to mast/case')
for i,x in enumerate([-14,14]):screw('Head_bridge_M3_'+str(i),(x,-11,192.4),length=20)
for i,(x,z) in enumerate([(-56,214),(56,214),(-56,333),(56,333)]):
    # Integrate the screw boss with the side wall; a tangential or gapped
    # separate part would not provide a physical load path.
    boss=cyl(4.8,10,(x,-10,z),(0,1,0)).cut(cyl(1.7,12,(x,-11,z),(0,1,0)))
    case.Shape=case.Shape.fuse(boss).removeSplitter()
    screw('Front_M3_'+str(i),(x,-9,z),(0,1,0),length=12)
gateway=pcb_vertical('ESP32_S3_N16R8','gateway',25.4,62.74,-30,291,pins=22,dual_usb=True,rf=True)
node=pcb_vertical('ESP32_30pin_TypeC','node',28,51.5,30,310,pins=15,rf=True)
tds_board=pcb_vertical('TDS_interface','tds',42,32,29,239)
amp=pcb_vertical('MAX98357A','amplifier',19.4,17.8,-35,221)
for name,w,h,x,z in [('S3',25.4,62.74,-30,291),('Node',28,51.5,30,310),('TDS',42,32,29,239),('Amp',19.4,17.8,-35,221)]:
    rails=[]
    for side in [-1,1]:
        rail=box(2,7.8,h-8,(x+side*(w/2+1.4)-1,-51.8,z-h/2+4))
        case.Shape=case.Shape.fuse(rail).removeSplitter()
oled_pieces=[(box(33.5,1.6,35.4,(-16.75,-9,296.3)),COL['PCB']),
             (box(31.5,3.4,19,(-15.75,-7.4,304.5)),COL['Black']),
             (box(29.42,.15,14.7,(-14.71,-4,306.65)),(.12,.35,.39))]
os,oc=colored(oled_pieces);oled=add('OLED_SH1106_1p3',os,'display','HeadElectronics','PCB',colors=oc)
for x in [-20,18]:add('OLED_edge_clip_'+str(x),box(2,8,30,(x,-8,299)),'enclosure',custom=True)
stop_shape=cyl(8,36,(0,-33,249),(0,1,0)).fuse(cyl(12,5,(0,3,249),(0,1,0)))
stop=add('LA16_emergency_stop',stop_shape,'stop','HeadElectronics','Black',notes='16mm panel interface and 24mm head are reference variant dimensions')
add('Stop_red_head',cyl(11.5,2,(0,8,249),(0,1,0)),'stop','HeadElectronics','Reference',kind='detail')
speaker_shape=cyl(20,3,(-30,-6,247),(0,1,0)).fuse(cyl(10,12,(-30,-18,247),(0,1,0)))
speaker=add('Speaker_40mm',speaker_shape,'speaker','HeadElectronics','Black')
add('Speaker_cone',Part.makeCone(8,17,3,V(-30,-3,247),V(0,1,0)),'speaker','HeadElectronics','Rubber',kind='detail')
mic=pcb_vertical('INMP441','microphone',16,14,25,220,y=-11)
add('Mic_port_gasket',ring(4,1.5,2,(25,-2,220),(0,1,0)),'assembly','HeadElectronics','Rubber')

# Base bay enlarged for insertion/bend spaces, not just bare PCB footprints.
bay_shape=rounded(38,182,40,(-106,-164,16),3).cut(box(33.2,177.2,42,(-103.6,-161.6,18.4)))
bay_shape=bay_shape.cut(box(10,18,12,(-108,-154,31))).cut(box(10,16,12,(-108,-114,31)))
bay_shape=bay_shape.cut(box(8,10,10,(-72,-17,30)))  # main harness outlet
bay=add('Base_service_bay',bay_shape,'enclosure',custom=True)
lid=add('Base_bay_lid',rounded(38,182,2.4,(-106,-164,56),3),'enclosure',custom=True)
buck=pcb_horizontal('XY3606_63x27','buck',27,63,-87,-128,24)
driver=pcb_horizontal('D4184_module','driver',17,17,-87,-55,24)
proto=pcb_horizontal('Interface_protoboard','electrical',28,42,-87,-12,24)
add('Inline_fuse_holder',cyl(4,22,(-92,-34,38),(0,1,0)),'electrical','BaseElectronics','Black',notes='Fuse rating not selected; mechanical envelope')
fuse_clip=ring(6,4.2,10,(-92,-27,38),(0,1,0)).fuse(box(8.2,10,4,(-104.5,-27,35)))
bay.Shape=bay.Shape.fuse(fuse_clip).removeSplitter()
add('Flyback_provision',cyl(1.8,6,(-77,-25,29),(0,1,0)),'electrical','BaseElectronics','Black',notes='Provision only; actual diode/interface depends on pump')
add('Pullup_4k7',cyl(1.2,6,(5,-41,280),(1,0,0)),'electrical','HeadElectronics','Reference',notes='DS18B20 pull-up position, electrical implementation still to verify')
for i,y in enumerate([-145,-105]):
    add('DC_input_'+str(i+1),ring(5.5,2.75,10,(-109,y,37),(1,0,0)),'electrical','BaseElectronics','Black',notes='Separate control/pump power; pump DC voltage remains unknown')

# Proposed service/plug envelopes are visible on demand, never exported as parts.
envelopes=[('S3_USB_insertion',box(22,15,25,(-41,-44,234)), 'gateway'),
           ('Node_USB_insertion',box(12,15,24,(24,-44,260)), 'node'),
           ('Buck_USB_bend',box(18,24,16,(-96,-96.5,25)), 'buck'),
           ('Pump_lift_with_shelf_removed',box(135,90,120,(-67.5,-156,18)), 'pump'),
           ('Bottle_lift_clearance',cyl(48,80,(35,-108,421)), 'bottle')]
for name,s,b in envelopes:add(name,s,b,'ServiceEnvelopes','Reference',kind='service')
add('Flow_sensor_reserve',box(30,36,30,(72,-28,20)),'flow','Reserved','Reference',notes='NO sensor selected; reserved envelope is not an installed flow sensor',kind='reserved')

# Liquid routes. Each plotted tube remains a separate replaceable physical item.
intake=route('Silicone_pickup_to_pump',[(29,-108,113),(29,-108,441),(-114,-131,441),(-114,-131,72),(-64,-131,72)],4,'tube','Silicone',20)
feed,feed_length,feed_bend=routed([(-64,-114,72),(-114,-114,72),(-114,-18,76),(-20,-18,76)],4,20)
ep=[V(-20,-18,76),V(0,-18,96),V(0,-18,170),V(0,2,190),V(0,72,190),V(0,92,170),V(0,92,165)]
entry_path=Part.Wire([Part.Arc(ep[0],V(-5.857864,-18,81.857864),ep[1]).toShape(),
    Part.makeLine(ep[1],ep[2]),Part.Arc(ep[2],V(0,-12.142136,184.142136),ep[3]).toShape(),
    Part.makeLine(ep[3],ep[4]),Part.Arc(ep[4],V(0,86.142136,184.142136),ep[5]).toShape(),Part.makeLine(ep[5],ep[6])])
entry_circle=Part.Wire([Part.makeCircle(4,ep[0],V(1,0,0))])
inner_hose=entry_path.makePipeShell([entry_circle],True,False)
outlet=add('Silicone_pump_to_spine',feed.fuse(inner_hose),'tube','Fluid','Silicone')
ROUTES.append({'name':outlet.Name,'length_mm':round(feed_length+entry_path.Length,2),'radius_mm':4,'minimum_center_bend_mm':round(min(20,feed_bend),2)})
clear=entry_path.makePipeShell([Part.Wire([Part.makeCircle(4.8,ep[0],V(1,0,0))])],True,False)
clear=clear.fuse(cyl(4.8,12,(-28,-18,76),(1,0,0)))
for obj in spout_parts:obj.Shape=obj.Shape.cut(clear).removeSplitter()
tds_cable=route('TDS_probe_cable',[(43,-116,142),(40,-114,426),(60,-114,436),(75,-80,436),(75,-58,239),(66,-40,239),(45,-40,239)],1.3,'tds',rounding=6)
temp_cable=route('DS18B20_cable',[(27,-104,166),(40,-102,426),(55,-102,432),(65,-75,432),(65,-50,280),(30,-39,280)],1.5,'temperature',rounding=8)
route('Level_sensor_cable',[(94.5,-108,140),(102,-108,140),(102,-50,140),(60,-50,220),(29,-39,230)],1.5,'level',rounding=10)
route('Main_electrical_trunk',[(-87,-12,35),(-50,-12,35),(11,-18,35),(11,-18,210),(11,-30,236)],2.5,rounding=10)
route('HX711_loadcell_lead',[(0,85.65,26),(0,70,24),(-40,70,24),(-40,60,25)],1,'scale',rounding=5)
route('HX711_to_gateway',[(-53,52,25),(-55,45,25),(-55,12,25),(-30,-18,25),(11,-18,25),(11,-18,210),(-30,-30,273)],1.2,'electrical',rounding=5)
route('OLED_harness',[(0,-7.4,298),(0,-23,294),(-30,-23,294),(-30,-33,294)],1.2,'electrical',rounding=6)
route('Speaker_pair',[(-30,-18,247),(-48,-22,247),(-48,-26,221),(-35,-35,221)],1,'electrical',rounding=6)
route('Mic_harness',[(25,-9,220),(25,-23,220),(-4,-23,265),(-25,-33,265)],1,'electrical',rounding=6)
route('Stop_harness',[(0,-33,249),(0,-28,239),(11,-28,225),(11,-18,210)],1.4,'electrical',rounding=5)

# Side entries to the separate electrical passage in the spout.  These are
# local openings, not a blanket exclusion from the interference checks.
for sp in spout_parts:
    for z,rad in [(35,3.5),(25,2.2)]:
        sp.Shape=sp.Shape.cut(cyl(rad,16,(-25,-18,z),(1,0,0))).removeSplitter()
    # The trunk approaches this entry obliquely; extend the opening to its
    # swept path instead of forcing an unrealistically sharp cable bend.
    sp.Shape=sp.Shape.cut(box(8,10,8,(-24,-20,31))).removeSplitter()

# External power adapters and their separate DC cables.
add('Glink_12V3A_external',rounded(80,42,32,(-220,-160,0),4),'power','ExternalPower','Black',notes='External adapter envelope, not measured GAC12-3 dimensions')
add('Pump_OEM_adapter_assumed',rounded(75,40,30,(-215,-75,0),4),'pump','ExternalPower','Black',notes='Assumed accessory shown separately; exact inclusion/voltage not confirmed')
route('Control_DC_cable',[(-140,-139,16),(-125,-139,16),(-125,-145,37),(-109,-145,37)],1.7,'electrical',rounding=6)
route('Pump_DC_cable',[(-140,-55,15),(-120,-55,15),(-120,-105,37),(-109,-105,37)],1.7,'electrical',rounding=6)

# Board and enclosure fastener detail uses removable rail screws.
for n,(x,y,z) in enumerate([(-49,-47,250),(48,-47,280),(-87,-158,20),(-87,10,20)]):
    add('Standoff_'+str(n+1),ring(3,1.7,5,(x,y,z)),'assembly','Fasteners','Metal')
    screw('Standoff_screw_'+str(n+1),(x,y,z-2),length=9)
for i,(x,y) in enumerate(post_holes+spout_holes):
    add('Base_washer_'+str(i+1),ring(4.5,2.3,1,(x,y,10)),'assembly','Fasteners','Metal')

# Dimensional register embedded in the native CAD file.
sheet=doc.addObject('Spreadsheet::Sheet','BOM_and_dimensions')
headers=['BOM id','Item','Status','Nominal dimensions mm','Objects','Source']
for j,v in enumerate(headers):sheet.set(chr(65+j)+'1',v)
for row,(k,r) in enumerate(REG.items(),2):
    vals=[k,r['label'],r['status'],' x '.join(map(str,r['nominal_dimensions_mm'])),str(len(r['objects'])),r['reference_source'] or r['source']]
    for j,v in enumerate(vals):sheet.set(chr(65+j)+str(row),v)
doc.recompute()

# Persist independent source/coverage metadata before expensive export checks.
installed_tube=sum(r['length_mm'] for r in ROUTES if r['name'].startswith('Silicone_'))
REG['tube']['installed_route_length_mm']=round(installed_tube,1)
REG['tube']['purchased_length_mm']=2000
REG['tube']['remainder_mm']=round(2000-installed_tube,1)
(OUT/'component-register.json').write_text(json.dumps(REG,indent=2,ensure_ascii=False),encoding='utf-8')
(OUT/'routes.json').write_text(json.dumps(ROUTES,indent=2),encoding='utf-8')
with (OUT/'component-register.csv').open('w',newline='',encoding='utf-8-sig') as f:
    writer=csv.writer(f);writer.writerow(headers)
    for k,r in REG.items():writer.writerow([k,r['label'],r['status'],r['nominal_dimensions_mm'],', '.join(r['objects']),r['reference_source'] or r['source']])
printed=[]
for obj in CUSTOM:
    Part.export([obj],str(STL/(obj.Name+'.step')))
    if obj.Material=='PETG':
        mesh=MeshPart.meshFromShape(Shape=obj.Shape,LinearDeflection=.12,AngularDeflection=.18,Relative=False)
        if not mesh.isSolid():raise RuntimeError('Open print mesh: '+obj.Name)
        mesh.write(str(STL/(obj.Name+'.stl')))
        printed.append({'name':obj.Name,'volume_cm3':obj.Shape.Volume/1000,'petg_solid_mass_g':obj.Shape.Volume/1000*1.27})
normal=[o for o in ITEMS if o.ObjectKind not in ['service','reserved']]
Part.export(normal,str(OUT/'kaew-full-assembly-v1.step'))
doc.saveAs(str(OUT/'kaew-full-assembly-v1.FCStd'))
summary={'object_count':len(ITEMS),'bom_rows':len(REG),'covered_rows':sum(bool(r['objects']) for r in REG.values()),
         'custom_parts':len(CUSTOM),'petg_print_parts':printed,'petg_nominal_mass_g':sum(r['petg_solid_mass_g'] for r in printed),
         'all_actual_delivered_parts_unmeasured':True,'flow_is_reservation_only':True,
         'installed_tube_mm':round(installed_tube,1),'status':'FULL ASSEMBLY STUDY - fit checks pending; not manufacturing release'}
(OUT/'assembly-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='petg_print_parts'},indent=2))
