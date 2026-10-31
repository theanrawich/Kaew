const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const filename=path.join(__dirname,'kaew-water-circuit.cjs');
assert.ok(fs.existsSync(filename),'A complete water circuit must remain visible outside the internal electronics group');
const THREE=require(path.join(__dirname,'toolchain/node_modules/three'));
const {waterRoutes,resolveRoute,createWaterCircuit}=require(filename);
const near=(a,b)=>a.every((v,i)=>Math.abs(v-b[i])<1e-7);
for(const offsets of [{reservoir:[0,0,0],pumpModule:[0,0,0],spout:[0,0,0]},{reservoir:[0,14,-7],pumpModule:[-9,8,-7],spout:[1,8,17]},{reservoir:[3,8,-2],pumpModule:[-5,4,3],spout:[2,5,10]}]){
 const routes=waterRoutes.map(r=>resolveRoute(r,offsets));
 for(let i=1;i<routes.length;i++)assert.ok(near(routes[i-1].at(-1),routes[i][0]),'Every hose must meet the next stage, including during explosion');
 assert.ok(near(routes[0][0],[14.62+offsets.reservoir[0],.2+offsets.reservoir[1],-10.5+offsets.reservoir[2]]));
 assert.ok(near(routes.at(-1).at(-1),[11.5+offsets.spout[0],5.03+offsets.spout[1],7.3+offsets.spout[2]]));
}
const appliance=new THREE.Group(),internals=new THREE.Group();internals.visible=false;appliance.add(internals);
const parts={reservoir:new THREE.Group(),pumpModule:new THREE.Group(),spout:new THREE.Group()};Object.values(parts).forEach(p=>appliance.add(p));
const circuit=createWaterCircuit(THREE,{parent:appliance,parts});
assert.equal(circuit.group.parent,appliance);
assert.ok(circuit.group.visible&&circuit.guideGroup.visible,'Normal view shows the full water circuit by default');
assert.equal(circuit.hoses.length,3);
assert.equal(circuit.guides.length,4);
assert.ok(circuit.guides.every(g=>!g.material.depthTest),'Guidance must remain readable behind the shell');
assert.equal(circuit.update(),false,'Unchanged assemblies must not rebuild hose geometry');
circuit.setGuide(false);assert.ok(!circuit.guideGroup.visible&&circuit.hoses.every(h=>h.visible));
circuit.setGuide(true);parts.reservoir.position.set(0,14,-7);parts.pumpModule.position.set(-9,8,-7);parts.spout.position.set(1,8,17);assert.equal(circuit.update(),true);
for(const hose of circuit.hoses)assert.ok([...hose.geometry.attributes.position.array].every(Number.isFinite));
assert.equal(circuit.update(),false);
console.log(JSON.stringify({waterStages:4,physicalHoses:3,continuousConfigurations:3,normalView:'visible',occludedGuide:'visible',staticRebuilds:0}));
