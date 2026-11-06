"""Measure proposed mounting interfaces, without assuming zero gap is a joint."""
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
import FreeCAD as App

out=Path(__file__).resolve().parent
doc=App.openDocument(str(out/'kaew-full-assembly-v1.FCStd'))
pairs=[
 ('Front_panel','Upper_case'),
 ('Head_mount_bridge','Upper_case'),('Head_mount_bridge','Spout_left'),
 ('Head_mount_bridge','Spout_right'),('Bottle_rear_rail','Bottle_shelf'),
 ('Bottle_rear_rail','Bottle_ring_111_rear'),('Bottle_rear_rail','Bottle_ring_250_rear'),
 ('Level_sensor_saddle','Bottle_shelf'),('Pump_side_keeper__66','Base_plate'),
 ('Pump_side_keeper_63','Base_plate'),('Base_service_bay','Base_plate'),
 ('Base_bay_lid','Base_service_bay'),('Fixed_drip_surround','Base_plate'),
 ('HX711_guard','Base_plate'),('OLED_edge_clip__20','Front_panel'),
 ('OLED_edge_clip_18','Front_panel'),('Loadcell_fixed_spacer','Base_plate'),
 ('Loadcell_moving_spacer','Floating_cup_platform'),
]
measurements=[]
for a,b in pairs:
    x,y=doc.getObject(a),doc.getObject(b)
    if not x or not y:
        raise ValueError('Missing object: '+a+' or '+b)
    measurements.append({'a':a,'b':b,'distance_mm':round(x.Shape.distToShape(y.Shape)[0],4),
                         'overlap_mm3':round(x.Shape.common(y.Shape).Volume,4)})
report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),
        'native_sha256':hashlib.sha256((out/'kaew-full-assembly-v1.FCStd').read_bytes()).hexdigest(),
        'upper_case_solids':len(doc.getObject('Upper_case').Shape.Solids),
        'pairs':measurements,
        'interpretation':'Contact alone is not a mechanical joint; positive gaps require a separate fixing or redesign. Cable and bolt load paths and fastener engagement are not proven by these distances.'}
(out/'mount-diagnostic.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
