// A separate always-visible fluid assembly. Electronics cutaway must not hide it.
// The pump's internal curve is a flow illustration, not a verified roller layout.
const waterRoutes=[
 {id:'pickup',from:'reservoir',to:'reservoir',points:[[14.62,.2,-10.5],[14.62,16,-10.5],[14.62,31.825,-10.5]]},
 {id:'inlet',from:'reservoir',to:'pumpModule',points:[[14.62,31.825,-10.5],[14.62,33.6,-10.5],[4.1,33.6,-11],[3.4,20,-11],[3.4,-3.77,-12.75],[8.45,-3.77,-12.75]]},
 {id:'pump',from:'pumpModule',to:'pumpModule',schematic:true,points:[[8.45,-3.77,-12.75],[9.5,-3.77,-13.4],[11.7,-3.77,-13.75],[13.1,-3.77,-12],[11.7,-3.77,-10.25],[9.5,-3.77,-10.6],[8.45,-3.77,-11.3]]},
 {id:'outlet',from:'pumpModule',to:'spout',points:[[8.45,-3.77,-11.3],[4.3,-3.77,-10],[4.5,4,-1],[9.7,7,3],[11.5,6.4,7.3],[11.5,5.03,7.3]]}
];
function resolveRoute(route,offsets){
 const a=offsets[route.from]||[0,0,0],b=offsets[route.to]||[0,0,0];
 return route.points.map((p,i)=>{const t=i/(route.points.length-1);return p.map((v,j)=>v+a[j]*(1-t)+b[j]*t);});
}
function createWaterCircuit(THREE,{parent,parts}){
 const group=new THREE.Group();group.name='water-circuit';parent.add(group);
 const guideGroup=new THREE.Group();guideGroup.name='water-flow-guide';group.add(guideGroup);
 const silicone=new THREE.MeshPhysicalMaterial({color:'#b3d6cf',transparent:true,opacity:.86,roughness:.18,transmission:.18,depthWrite:false});
 const blue=new THREE.MeshBasicMaterial({color:'#087f9e',depthTest:false,depthWrite:false,transparent:true,opacity:.94,toneMapped:false});
 const dashed=new THREE.LineDashedMaterial({color:'#087f9e',depthTest:false,depthWrite:false,transparent:true,opacity:.94,dashSize:.42,gapSize:.24,toneMapped:false});
 const hoses=[],guides=[],arrows=[],entries=[];let previous='';
 for(const route of waterRoutes){
  let hose=null;
  if(!route.schematic){hose=new THREE.Mesh(new THREE.BufferGeometry(),silicone);hose.name='hose-'+route.id;group.add(hose);hoses.push(hose);}
  const guide=route.schematic?new THREE.Line(new THREE.BufferGeometry(),dashed):new THREE.Mesh(new THREE.BufferGeometry(),blue);
  guide.name='water-guide-'+route.id;guide.renderOrder=30;guideGroup.add(guide);guides.push(guide);
  let arrow=null;
  if(route.id!=='pump'){
   arrow=new THREE.ArrowHelper(new THREE.Vector3(0,1,0),new THREE.Vector3(),1.7,'#087f9e',.8,.5);
   for(const m of [arrow.line,arrow.cone]){m.material.depthTest=false;m.material.depthWrite=false;m.material.toneMapped=false;m.renderOrder=31;}
   guideGroup.add(arrow);arrows.push(arrow);
  }
  entries.push({route,hose,guide,arrow});
 }
 function update(){
  const offsets=Object.fromEntries(Object.entries(parts).map(([name,p])=>[name,p.position.toArray()]));
  const signature=JSON.stringify(offsets);if(signature===previous)return false;previous=signature;
  for(const {route,hose,guide,arrow} of entries){
   const curve=new THREE.CatmullRomCurve3(resolveRoute(route,offsets).map(p=>new THREE.Vector3(...p)));
   if(hose){hose.geometry.dispose();hose.geometry=new THREE.TubeGeometry(curve,76,.18,10,false);}
   guide.geometry.dispose();
   if(route.schematic){guide.geometry=new THREE.BufferGeometry().setFromPoints(curve.getPoints(64));guide.computeLineDistances();}
   else guide.geometry=new THREE.TubeGeometry(curve,76,.075,6,false);
   if(arrow){const t=route.id==='pickup'?.38:route.id==='inlet'?.58:.72;arrow.position.copy(curve.getPointAt(t));arrow.setDirection(curve.getTangentAt(t));}
  }
  return true;
 }
 function setGuide(value){guideGroup.visible=!!value;}
 update();
 return {group,guideGroup,hoses,guides,arrows,update,setGuide};
}
module.exports={waterRoutes,resolveRoute,createWaterCircuit};
