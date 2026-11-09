import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import bottlePhoto from '../references/crystal-1500-reference.jpg';
import pumpPhoto from '../references/pump-250-0.jpg';
import oledPhoto from '../references/part-display-oled13.jpg';
import bom from '../kaew-bom.json';
import { mountWiringViewer } from './kaew-wiring.js';
import { mountControlPanel } from './kaew-panel.js';
import modelParts from './kaew-model-parts.cjs';
import { createModelLabels } from './kaew-model-labels.js';
import { createWaterCircuit } from './kaew-water-circuit.cjs';

const $=id=>document.getElementById(id);
const stage=$('stage');
const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
const scene=new THREE.Scene();
scene.background=new THREE.Color('#dce6e1');
scene.fog=new THREE.Fog('#dce6e1',135,260);
let renderer;
try{
 renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,preserveDrawingBuffer:true});
 renderer.setPixelRatio(Math.min(devicePixelRatio,2));
 renderer.shadowMap.enabled=true;
 renderer.shadowMap.type=THREE.PCFSoftShadowMap;
 renderer.toneMapping=THREE.ACESFilmicToneMapping;
 renderer.toneMappingExposure=.78;
 renderer.outputColorSpace=THREE.SRGBColorSpace;
 stage.appendChild(renderer.domElement);
}catch(error){
 $('loader').classList.add('error');
 $('loader').textContent='เบราว์เซอร์นี้ยังเปิด WebGL ไม่ได้ ลองเปิดไฟล์ด้วย Edge หรือ Chrome ที่เปิดใช้การเร่งกราฟิก';
 throw error;
}
const canvas=renderer.domElement;
canvas.tabIndex=0;
canvas.setAttribute('aria-label','แบบจำลอง Kaew สามมิติ ลากเพื่อหมุน เลื่อนเพื่อซูม ใช้ปุ่มลูกศรหมุนและ Home คืนมุมมอง');
const camera=new THREE.PerspectiveCamera(36,1,.1,400);
const controls=new OrbitControls(camera,canvas);
controls.enableDamping=!reduced;
controls.dampingFactor=.09;
controls.minDistance=38;
controls.maxDistance=155;
controls.maxPolarAngle=Math.PI*.82;
controls.minPolarAngle=.1;
controls.enablePan=true;
controls.target.set(3,14,0);
camera.position.set(70,50,78);
controls.update();
const environment=new THREE.PMREMGenerator(renderer);
scene.environment=environment.fromScene(new RoomEnvironment(),.04).texture;
environment.dispose();
scene.environmentIntensity=.7;
scene.add(new THREE.HemisphereLight('#ffffff','#809287',.7));
const keyLight=new THREE.DirectionalLight('#fff4e8',2.3);
keyLight.position.set(18,70,35);
keyLight.castShadow=true;
keyLight.shadow.mapSize.set(2048,2048);
Object.assign(keyLight.shadow.camera,{left:-70,right:70,top:70,bottom:-70,near:.5,far:160});
keyLight.shadow.bias=-.00025;
keyLight.shadow.normalBias=.06;
keyLight.shadow.radius=4;
scene.add(keyLight);
const rimLight=new THREE.DirectionalLight('#d3f2ef',.9);
rimLight.position.set(-25,27,-24);
scene.add(rimLight);

function material(color,roughness=.5,metalness=0){return new THREE.MeshStandardMaterial({color,roughness,metalness});}
const shell=material('#e8eee3',.3,.06);
const soft=material('#d7e2d3',.67);
const teal=material('#317d6d',.38,.1);
const dark=material('#254651',.36,.22);
const rubber=material('#33423d',.94);
const steel=material('#b9c5c3',.27,.85);
const black=material('#24332f',.76);
const waterMat=new THREE.MeshPhysicalMaterial({color:'#b8dfe4',transparent:true,opacity:.30,roughness:.055,metalness:0,transmission:.22,ior:1.333,thickness:.7,depthWrite:false});
const glass=new THREE.MeshPhysicalMaterial({color:'#f1fcfa',transparent:false,opacity:1,roughness:.035,metalness:0,transmission:.98,ior:1.5,thickness:.25,clearcoat:1,clearcoatRoughness:.05,side:THREE.DoubleSide});
const tankGlass=new THREE.MeshPhysicalMaterial({color:'#edf7f6',transparent:false,opacity:1,roughness:.045,metalness:0,transmission:.98,ior:1.47,thickness:.04,clearcoat:1,side:THREE.DoubleSide});
const mesh=(geo,mat,parent,x=0,y=0,z=0)=>{const m=new THREE.Mesh(geo,mat);m.position.set(x,y,z);m.castShadow=!mat.transparent;m.receiveShadow=true;parent.add(m);return m;};
const box=(w,h,d,mat,parent,x=0,y=0,z=0,r=.3)=>mesh(new RoundedBoxGeometry(w,h,d,3,Math.min(r,w/2.01,h/2.01,d/2.01)),mat,parent,x,y,z);
const cylinder=(rt,rb,h,mat,parent,x=0,y=0,z=0)=>mesh(new THREE.CylinderGeometry(rt,rb,h,48),mat,parent,x,y,z);
function tube(points,r,mat,parent){return mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points.map(p=>new THREE.Vector3(...p))),60,r,10,false),mat,parent);}
function torus(radius,tub,mat,parent,x,y,z){return mesh(new THREE.TorusGeometry(radius,tub,12,64),mat,parent,x,y,z);}
function line(points,color,parent){const l=new THREE.Line(new THREE.BufferGeometry().setFromPoints(points.map(p=>new THREE.Vector3(...p))),new THREE.LineBasicMaterial({color,transparent:true,opacity:.65}));parent.add(l);return l;}
const group=()=>{const g=new THREE.Group();scene.add(g);return g;};
const desk=group(),base=group(),body=group(),reservoir=group(),spout=group(),tray=group(),cup=group(),internals=group();
const appliance=group();appliance.position.y=11.4;
for(const part of [base,body,reservoir,spout,tray,cup,internals])appliance.add(part);

const woodCanvas=document.createElement('canvas');woodCanvas.width=512;woodCanvas.height=512;
const wood=woodCanvas.getContext('2d');wood.fillStyle='#b99b70';wood.fillRect(0,0,512,512);
let seed=187;const random=()=>{seed=(seed*16807)%2147483647;return(seed-1)/2147483646;};
for(let i=0;i<1200;i++){const x=random()*512;wood.strokeStyle=`rgba(${random()>.5?'82,58,30':'236,212,171'},${.02+random()*.045})`;wood.lineWidth=.3+random()*1.3;wood.beginPath();wood.moveTo(x,0);wood.bezierCurveTo(x+random()*15,170,x-random()*15,340,x+random()*7,512);wood.stroke();}
const woodTex=new THREE.CanvasTexture(woodCanvas);woodTex.colorSpace=THREE.SRGBColorSpace;woodTex.wrapS=woodTex.wrapT=THREE.RepeatWrapping;
const deskMat=new THREE.MeshStandardMaterial({map:woodTex,color:'#dfc596',roughness:.73});
const deskTop=box(84,1,58,deskMat,desk,-17,-1.6,-1,.4);deskTop.scale.y=3.2;
box(3,33,3,dark,desk,-48,-20,-19,.3);
box(3,33,3,dark,desk,-48,-20,18,.3);
box(3,33,3,dark,desk,21,-20,22,.3);
const deskEdge=line([[25.02,-.2,-30],[25.02,-.2,28]],'#f2e0b5',desk);

// The dispenser stands on the desktop, beside the keyboard and monitor.
const keyboard=box(21,.65,8,material('#d4ded2',.6),desk,-25,.45,11,.45);
for(let r=0;r<4;r++)for(let c=0;c<13;c++)box(1.2,.16,1.1,shell,desk,-34.1+c*1.52,.86,8.3+r*1.55,.12);
box(7,.16,.8,shell,desk,-25,.88,14.5,.08);
const monitorStand=box(9,.35,6,steel,desk,-30,.3,-14,.2);
box(1.2,7,1.2,steel,desk,-30,3.8,-15,.25);
box(25,16,1,material('#b9cbbf',.45,.2),desk,-30,15,-16,.7);
const monitorCanvas=document.createElement('canvas');monitorCanvas.width=512;monitorCanvas.height=320;
const mc=monitorCanvas.getContext('2d');mc.fillStyle='#d5e4d8';mc.fillRect(0,0,512,320);mc.fillStyle='#bdcfc0';mc.fillRect(36,38,65,248);mc.fillStyle='#e7eee4';mc.fillRect(122,38,350,248);mc.fillStyle='#c9dacf';for(let y=70;y<260;y+=27)mc.fillRect(148,y,140+(y%70),7);
const monitorTex=new THREE.CanvasTexture(monitorCanvas);monitorTex.colorSpace=THREE.SRGBColorSpace;
mesh(new THREE.PlaneGeometry(23.2,14.2),new THREE.MeshBasicMaterial({map:monitorTex}),desk,-30,15,-15.47);

// Physical dimensions: one Three.js unit = 10 millimetres.
// Proposed enclosure; pump and bottle dimensions are explicitly estimates.
const pumpModule=group();appliance.add(pumpModule);
const pumpIvory=material('#f1eee4',.48,.02),capBlue=material('#049fcb',.23,.04);
const polymerNoise=document.createElement('canvas');polymerNoise.width=polymerNoise.height=128;
const pn=polymerNoise.getContext('2d');
for(let y=0;y<128;y++)for(let x=0;x<128;x++){const v=140+Math.floor(random()*45);pn.fillStyle=`rgb(${v},${v},${v})`;pn.fillRect(x,y,1,1);}
const polymerBump=new THREE.CanvasTexture(polymerNoise);polymerBump.wrapS=polymerBump.wrapT=THREE.RepeatWrapping;polymerBump.repeat.set(3,3);shell.bumpMap=polymerBump;shell.bumpScale=.012;
box(22,1.6,35,shell,base,11.5,-10.25,.5,.42);
box(21.5,.18,34.5,soft,base,11.5,-9.37,.5,.2);
for(const x of [3,20])for(const z of [-13.5,14.5])cylinder(.9,.9,.35,rubber,base,x,-11.225,z);
// A separate shelf carries the bottle, without loading the pump's enclosure.
box(20,.4,13,shell,base,11.5,-1.1,-10.5,.35);
for(const x of [2.7,20.3])for(const z of [-15.6,-5.4])box(.55,8.05,.65,soft,base,x,-5.325,z,.12);
for(const x of [2.7,20.3])for(const z of [-15.6,-5.4]){const screw=cylinder(.20,.20,.05,steel,base,x,-.87,z);line([[x-.11,-.84,z],[x+.11,-.84,z]],'#5a6966',base);}

// Selected pump: boxed dosing unit, recreated from seller photographs.
// 80 x 125 x 40 mm box, 72 mm overall are layout estimates, NOT seller dimensions.
box(8,4,12.5,pumpIvory,pumpModule,11.5,-7.35,-10,.35);
box(7.94,.13,12.44,soft,pumpModule,11.5,-5.42,-10,.22);
box(8.01,.045,12.51,material('#c3c3b7',.8),pumpModule,11.5,-6.3,-10,.13);
for(const x of [8.15,14.85])for(const z of [-15.5,-4.5]){
 cylinder(.28,.28,.10,steel,pumpModule,x,-5.28,z);line([[x-.15,-5.22,z],[x+.15,-5.22,z]],'#5c625b',pumpModule);line([[x,-5.22,z-.15],[x,-5.22,z+.15]],'#5c625b',pumpModule);
}
box(5.1,.22,5.2,dark,pumpModule,11.5,-5.16,-12,.3);
cylinder(2.12,2.12,2.35,pumpIvory,pumpModule,11.5,-3.9,-12);
cylinder(1.89,2.04,.18,shell,pumpModule,11.5,-2.64,-12);
cylinder(.20,.20,.13,steel,pumpModule,11.5,-2.49,-12);
for(let i=0;i<8;i++){const a=i*Math.PI/4;box(.28,.3,.7,pumpIvory,pumpModule,11.5+Math.cos(a)*2.08,-3.85,-12+Math.sin(a)*2.08,.06);}
for(const z of [-12.75,-11.3]){const port=cylinder(.18,.25,1.0,pumpIvory,pumpModule,8.95,-3.77,z);port.rotation.z=Math.PI/2;}
cylinder(.64,.64,1.05,black,pumpModule,11.5,-4.73,-6.6);
cylinder(.48,.48,.12,capBlue,pumpModule,11.5,-4.15,-6.6);
box(.11,.06,.61,capBlue,pumpModule,11.5,-4.07,-6.45,.025);
cylinder(.12,.12,.09,material('#b94e36',.27),pumpModule,13.4,-5.21,-6.6);
const jack=cylinder(.32,.32,.15,steel,pumpModule,11.5,-7.4,-3.67);jack.rotation.x=Math.PI/2;
const jackHole=cylinder(.20,.20,.16,black,pumpModule,11.5,-7.4,-3.56);jackHole.rotation.x=Math.PI/2;

// Crystal 1.5 L photograph-based bottle. Study dimensions: diameter85 x height320mm.
const bottleX=15.2,bottleZ=-10.5,bottleBottom=-.9;
const bProfile=[[0,0],[2.7,0],[3.7,.35],[4.05,.9],[4.25,1.8],[4.25,2.5],[4.02,2.8],[4.25,3.15],[4.1,3.6],[4.25,4.1],[4.25,4.5],[4.10,4.8],[4.25,5.25],[4.25,10.8],[4.05,11.2],[4.20,11.7],[4.20,19.3],[4.05,19.7],[4.25,20.1],[4.25,23.8],[4.03,24.2],[4.02,25.2],[3.6,26.2],[2.8,27.5],[1.9,29],[1.38,29.9],[1.38,30.6]];
function bottleSegment(points){return mesh(new THREE.LatheGeometry(points.map(([r,y])=>new THREE.Vector2(r,y)),96),tankGlass,reservoir,bottleX,bottleBottom,bottleZ);}
// Omit the two faceted bands from the smooth shell, then tessellate them.
for(const segment of [bProfile.filter(p=>p[1]<=5.25),bProfile.filter(p=>p[1]>=10.8&&p[1]<=20.1),bProfile.filter(p=>p[1]>=23.8)])bottleSegment(segment);
function facetBand(low,high){
 const verts=[],n=18,mid=(low+high)/2;
 const point=(a,y,r)=>[bottleX+Math.sin(a)*r,bottleBottom+y,bottleZ+Math.cos(a)*r];
 for(let i=0;i<n;i++){
  const a=i/n*Math.PI*2,b=(i+1)/n*Math.PI*2,m=(a+b)/2;
  const A=point(a,low,4.25),B=point(b,low,4.25),C=point(m,mid,3.94),D=point(a,high,4.25),E=point(b,high,4.25);
  verts.push(...A,...C,...B,...A,...D,...C,...D,...E,...C,...B,...C,...E);
 }
 const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(verts,3));geo.computeVertexNormals();return mesh(geo,tankGlass,reservoir);
}
facetBand(5.25,10.8);facetBand(20.1,23.8);
for(const h of [2.6,3.3,4.3,11.3,19.6,24.1]){const rib=torus(4.18,.055,tankGlass,reservoir,bottleX,bottleBottom+h,bottleZ);rib.rotation.x=Math.PI/2;}
for(let i=0;i<5;i++){const a=i*Math.PI*2/5;const foot=mesh(new THREE.SphereGeometry(.9,18,12),tankGlass,reservoir,bottleX+Math.sin(a)*2.75,bottleBottom+.28,bottleZ+Math.cos(a)*2.75);foot.scale.y=.4;}
const tankWater=cylinder(4.02,4.02,1,waterMat,reservoir,bottleX,bottleBottom+10,bottleZ);
const labelCanvas=document.createElement('canvas');labelCanvas.width=768;labelCanvas.height=192;
const labelContext=labelCanvas.getContext('2d');
function drawBottleLabel(photo){
 labelContext.fillStyle='#0874a9';labelContext.fillRect(0,0,768,192);
 for(let i=0;i<3;i++){
  if(photo)labelContext.drawImage(photo,398,398,204,205,i*256,0,256,192);
  else{labelContext.textAlign='center';labelContext.fillStyle='#fff';labelContext.font='46px Tahoma';labelContext.fillText('คริสตัล',i*256+128,110);}
 }
 labelTexture.needsUpdate=true;
}
const labelTexture=new THREE.CanvasTexture(labelCanvas);labelTexture.colorSpace=THREE.SRGBColorSpace;
drawBottleLabel();
const bottleImage=new Image();bottleImage.onload=()=>drawBottleLabel(bottleImage);bottleImage.src=bottlePhoto;
mesh(new THREE.CylinderGeometry(4.215,4.215,7.6,96,1,true),new THREE.MeshStandardMaterial({map:labelTexture,roughness:.30,metalness:0}),reservoir,bottleX,bottleBottom+15.5,bottleZ);
// Blue original cap shown with proposed pickup/vent/cable fittings.
cylinder(1.50,1.50,1.4,capBlue,reservoir,bottleX,bottleBottom+31.3,bottleZ);
for(let i=0;i<44;i++){const a=i*Math.PI*2/44;box(.065,1.12,.065,capBlue,reservoir,bottleX+Math.sin(a)*1.50,bottleBottom+31.3,bottleZ+Math.cos(a)*1.50,.015);}
const neckRing=torus(1.55,.09,tankGlass,reservoir,bottleX,bottleBottom+30.5,bottleZ);neckRing.rotation.x=Math.PI/2;
cylinder(.28,.28,.85,steel,reservoir,bottleX-.58,bottleBottom+32.30,bottleZ);
cylinder(.16,.16,.55,steel,reservoir,bottleX+.60,bottleBottom+32.25,bottleZ);
cylinder(.34,.34,.24,shell,reservoir,bottleX+.60,bottleBottom+32.65,bottleZ);
for(const h of [1.1,16.8]){const holder=torus(4.66,.15,teal,base,bottleX,bottleBottom+h,bottleZ);holder.rotation.x=Math.PI/2;}
box(.6,18,.6,soft,base,bottleX,bottleBottom+8.4,bottleZ-4.7,.12);
const levelBody=cylinder(1.40,1.40,1.7,material('#eee9dd',.53),base,bottleX+4.8,bottleBottom+4.1,bottleZ);levelBody.rotation.z=Math.PI/2;
// Two immersed probes are layout illustrations. Cable seals and materials require verification.
cylinder(.64,.64,2.9,black,reservoir,bottleX-1.1,bottleBottom+3.5,bottleZ+.25);
for(const dx of [-.28,.28])cylinder(.065,.065,.85,steel,reservoir,bottleX-1.1+dx,bottleBottom+1.7,bottleZ+.25);
cylinder(.30,.30,3.0,steel,reservoir,bottleX+1.1,bottleBottom+3.3,bottleZ+.3);
for(const [dx,c] of [[-1.1,'#404d49'],[1.1,'#7c8c85']])tube([[bottleX+dx,bottleBottom+5,bottleZ+.3],[bottleX+dx,bottleBottom+26,bottleZ+.3],[bottleX+dx*.3,bottleBottom+31.8,bottleZ+.45]],.045,material(c,.6),reservoir);

// Retain the tabletop silhouette, with a smaller real-size OLED window.
box(12.6,13.5,5.4,shell,body,11.5,14.0,-2.7,.5);
box(4.4,4.8,.34,dark,body,11.5,16.0,.12,.22);
const screenCanvas=document.createElement('canvas');screenCanvas.width=128;screenCanvas.height=64;
const screenContext=screenCanvas.getContext('2d');
const screenTexture=new THREE.CanvasTexture(screenCanvas);screenTexture.colorSpace=THREE.SRGBColorSpace;screenTexture.magFilter=THREE.NearestFilter;
const display=mesh(new THREE.PlaneGeometry(2.942,1.470),new THREE.MeshBasicMaterial({map:screenTexture,toneMapped:false}),body,11.5,16.30,.31);
canvas.dataset.display='SH1106 OLED 1.3 inch';canvas.dataset.displayActiveMm='29.42x14.70';
const indicatorMat=new THREE.MeshStandardMaterial({color:'#68b9a1',emissive:'#4c9b87',emissiveIntensity:.35,roughness:.5});
box(6.2,.12,.12,indicatorMat,body,11.5,11.8,.13,.035);
const emergency=cylinder(.86,.86,.48,material('#bd6042',.42),body,15.05,10,.28);emergency.rotation.x=Math.PI/2;
for(let i=0;i<6;i++)box(.09,.7,.10,dark,body,7.65+i*.38,10,.12,.025);
const microphonePort=cylinder(.16,.16,.15,black,body,11.5,8.5,.20);microphonePort.rotation.x=Math.PI/2;
for(const x of [5.6,17.4])box(1.4,17.4,2.6,shell,base,x,-.7,-2.0,.22);

// Proposed spout. Tip 165mm above tabletop; 33.5mm gap above the selected glass.
box(5.8,2.7,13.1,shell,spout,11.5,7.95,4.6,.52);
box(4.8,.18,10.6,soft,spout,11.5,6.54,4.5,.08);
cylinder(.48,.48,1.70,steel,spout,11.5,6.02,7.3);
cylinder(.31,.31,.14,black,spout,11.5,5.10,7.3);
const streamMat=new THREE.MeshBasicMaterial({color:'#a9e4ea',transparent:true,opacity:.38,depthWrite:false});
const stream=cylinder(.12,.10,1,streamMat,appliance,11.5,1,7.3);stream.visible=false;
const drops=[];for(let i=0;i<5;i++){const drop=mesh(new THREE.SphereGeometry(.10,8,6),streamMat,appliance,11.5,0,7.3);drop.visible=false;drops.push(drop);}

// Floating weighing platform with a physical clearance from the fixed drip tray.
box(17.4,1.7,17.5,shell,tray,11.5,-8.75,7.0,.48);
box(14.4,.30,14.4,soft,tray,11.5,-7.40,7.3,.22);
box(8.0,1.27,1.27,steel,internals,11.5,-8.50,7.3,.08);
// Fixed-end and moving-end spacers meet the load cell and platform surfaces.
box(2.0,.315,1.27,dark,internals,8.7,-9.2925,7.3,.025);
box(2.0,.315,1.27,dark,internals,14.1,-7.7075,7.3,.025);
for(const x of [8.6,9.4,13.6,14.4]){cylinder(.18,.18,.14,steel,internals,x,-7.81,7.3);}
const dockRing=torus(4.6,.065,teal,tray,11.5,-7.21,7.3);dockRing.rotation.x=Math.PI/2;
for(let r=0;r<3;r++)for(let c=0;c<8;c++)box(.7,.025,.1,dark,tray,6.6+c*1.4,-7.51,1.4+r*.55,.025);

// Ocean Nova Rock B06511: top83 / base63 / height90mm; no handle.
cup.position.set(11.5,-7.25,7.3);
const cupOutline=[[0,0],[2.9,0],[3.15,.12],[3.15,.55],[3.23,1.2],[3.57,4.6],[4.15,8.96],[4.14,9.0],[3.92,8.96],[3.76,7.7],[3.01,1.10],[2.91,.86],[0,.86]];
const cupShell=mesh(new THREE.LatheGeometry(cupOutline.map(([r,y])=>new THREE.Vector2(r,y)),96),glass,cup);
const lip=torus(4.035,.115,glass,cup,0,8.885,0);lip.rotation.x=Math.PI/2;
const baseRim=torus(3.05,.09,glass,cup,0,.25,0);baseRim.rotation.x=Math.PI/2;
const cupWater=cylinder(3.65,2.93,1,waterMat,cup,0,2,0);
const meniscus=cylinder(3.65,3.65,.035,new THREE.MeshBasicMaterial({color:'#d1ecec',transparent:true,opacity:.35,side:THREE.DoubleSide,depthWrite:false}),cup,0,4,0);

// Gateway/node envelopes and signal wiring, shown in cutaway / exploded views.
function pcb(w,h,x,y,z,label){
 const board=box(w,h,.14,material('#286c4b',.6),internals,x,y,z,.04);
 box(w*.52,h*.48,.14,steel,internals,x,y+.15,z+.14,.05);
 for(let i=0;i<Math.floor(h/.254);i++){box(.15,.14,.32,steel,internals,x-w*.45,y-h*.45+i*.254,z+.17,.015);box(.15,.14,.32,steel,internals,x+w*.45,y-h*.45+i*.254,z+.17,.015);}
 return board;
}
pcb(2.8,6.25,9.0,14,-2.6,'ESP32-S3');pcb(2.8,5.2,14.2,14.2,-2.6,'ESP32');
// Keep the HX711 outside the moving platform's swept volume.
pcb(2.0,3.2,6.5,-7.5,-7.0,'HX711');
box(4.2,3.2,.16,material('#267552',.55),internals,14.3,8.6,-2.6,.06);
pcb(.9,1.2,11.5,8.5,-.8,'INMP441');
pcb(2.8,3.0,4.5,-7.6,-4.0,'Buck');
pcb(2.8,3.0,17.8,-7.6,-4.0,'Driver');
const speakerFrame=cylinder(2,2,.8,black,internals,8.2,8.7,-1.3);speakerFrame.rotation.x=Math.PI/2;
const speakerCone=cylinder(1.65,.65,.25,dark,internals,8.2,8.7,-.85);speakerCone.rotation.x=Math.PI/2;
// A dashed volume marks an unselected part; this is not a real flow sensor.
const flowEnvelope=box(2.2,2.2,2.6,new THREE.MeshBasicMaterial({color:'#a77a37',wireframe:true,transparent:true,opacity:.7}),internals,6,4,.1,.04);
flowEnvelope.userData.pending=true;
// Control-power adapter envelope; its dimensions and cable entry are proposals.
box(6,3.4,8,black,appliance,31,-9.6,-9,.45);
for(let i=0;i<5;i++)box(4,.035,.08,dark,appliance,31,-7.88,-11+i*.8,.02);
tube([[28,-9.6,-9],[25,-10,-8],[23.4,-9.8,-6],[22.4,-9.4,-5]],.10,rubber,appliance);
const waterCircuit=createWaterCircuit({Group:THREE.Group,MeshPhysicalMaterial:THREE.MeshPhysicalMaterial,MeshBasicMaterial:THREE.MeshBasicMaterial,LineDashedMaterial:THREE.LineDashedMaterial,Mesh:THREE.Mesh,BufferGeometry:THREE.BufferGeometry,Line:THREE.Line,ArrowHelper:THREE.ArrowHelper,Vector3:THREE.Vector3,CatmullRomCurve3:THREE.CatmullRomCurve3,TubeGeometry:THREE.TubeGeometry},{parent:appliance,parts:{reservoir,pumpModule,spout}});
for(const [dx,color] of [[0,'#b47f5d'],[.25,'#8aa59c'],[.5,'#4c6366']])tube([[8.3+dx,13,-2.5],[7+dx,9,-3],[6.5+dx,-6,-5],[6.5+dx,-7.5,-6.8]],.035,material(color,.7),internals);
tube([[6.5,-7.5,-6.8],[5.4,-8,-2],[6,-8.5,5],[8,-8.5,7.3]],.06,rubber,internals);
internals.visible=false;

const floor=mesh(new THREE.PlaneGeometry(400,400),material('#e7eeea',.87),scene,0,-.12,0);floor.rotation.x=-Math.PI/2;floor.receiveShadow=true;
desk.visible=false;
const dims=group();appliance.add(dims);dims.visible=false;
function dimLabel(text,x,y,z,tint='#326f63'){
 const c=document.createElement('canvas');c.width=512;c.height=88;const ct=c.getContext('2d');ct.fillStyle='#f7faf6';ct.fillRect(0,0,512,88);ct.fillStyle=tint;ct.textAlign='center';ct.font='42px Tahoma, sans-serif';ct.fillText(text,256,59,490);
 const tx=new THREE.CanvasTexture(c);tx.colorSpace=THREE.SRGBColorSpace;const s=new THREE.Sprite(new THREE.SpriteMaterial({map:tx,depthTest:false,depthWrite:false,transparent:true,toneMapped:false,fog:false}));s.position.set(x,y,z);s.scale.set(15.5,2.66,1);s.renderOrder=20;dims.add(s);return s;
}
function dimension(a,b,text,position,color='#5a8d7e'){
 line([a,b],color,dims);for(const p of [a,b])line([[p[0]-.4,p[1]-.25,p[2]],[p[0]+.4,p[1]+.25,p[2]]],color,dims);dimLabel(text,...position,color);
}
dimension([.5,-10.8,20.5],[22.5,-10.8,20.5],'ฐานเสนอ 220 มม.',[11.5,-9.9,22]);
dimension([25,-10.8,-17],[25,-10.8,18],'ลึกเสนอ 350 มม.',[28,-9.5,1]);
dimension([27,-11.4,-17],[27,33.6,-17],'สูงเสนอ 450 มม.',[29,22,-17]);
dimension([7.35,2.0,8],[15.65,2.0,8],'ปากแก้ว 83 มม.',[11.5,4.5,10]);
dimLabel('ขวด Ø85 × 320 mm*',15.2,32.2,-10.5,'#9a6c32');
canvas.dataset.units='mm';canvas.dataset.footprintMm='220x350';canvas.dataset.heightMm='450';canvas.dataset.cupMm='83x63x90';canvas.dataset.pumpPrice=String(bom.rows.find(row=>row.id==='pump').unitBudget);

const profiles={small:{volume:160,minutes:18},normal:{volume:220,minutes:25},late:{volume:240,minutes:20}};
const bottleCapacity=1500;
let profile='normal',targetVolume=220,reminderMinutes=25,cupVolume=160,tankVolume=bottleCapacity;
let remaining=25*60,cupAway=false,filling=false,stopped=false,returnPending=false,returnWait=0,exploded=false,explosion=0;
let finish='porcelain',selectedPart='base',cameraTween=null,lastScreenUpdate=-1,activeView='hero';
const cupDocked=new THREE.Vector3(11.5,-7.25,7.3);
const cupLifted=new THREE.Vector3(27,5,19);
const cupDest=cupDocked.clone();
const parts=[
 {object:reservoir,offset:new THREE.Vector3(0,14,-7)},
 {object:body,offset:new THREE.Vector3(13,8,7)},
 {object:spout,offset:new THREE.Vector3(1,8,17)},
 {object:tray,offset:new THREE.Vector3(0,5,16)},
 {object:base,offset:new THREE.Vector3(0,0,0)},
 {object:internals,offset:new THREE.Vector3(3,5,9)},
 {object:pumpModule,offset:new THREE.Vector3(-9,8,-7)}
];
const descriptions=Object.fromEntries(modelParts.map(p=>[p.id,[p.title,p.description]]));
const modelLabels=createModelLabels({stage,scene,camera,parents:{base,body,reservoir,spout,tray,cup,internals,pumpModule,appliance}});
function selectPart(name){
 selectedPart=name;
 $('part-name').textContent=descriptions[name][0];$('part-description').textContent=descriptions[name][1];
 const photo=$('part-photo');photo.hidden=!['pump','display'].includes(name);if(!photo.hidden){photo.src=name==='pump'?pumpPhoto:oledPhoto;photo.alt=name==='pump'?'รูปปั๊มจริงจากร้านที่เลือก':'รูปOLED1.3นิ้วจากร้าน';}
 document.querySelectorAll('[data-part]').forEach(b=>b.classList.toggle('selected',b.dataset.part===name));
}
document.querySelectorAll('[data-part]').forEach(b=>b.addEventListener('click',()=>{
 const part=modelParts.find(p=>p.id===b.dataset.part);
 if(part.group==='internal'&&!exploded)setInsideView(true);
 selectPart(part.id);
}));
selectPart('base');

function status(message,short,kind=''){
 $('status-text').textContent=message;$('scene-status').textContent=short;
 $('live-pill').className='live-pill'+(kind?' '+kind:'');
}
function updateUI(){
 $('cup-volume').textContent=Math.round(cupVolume);
 $('bottle-volume').textContent=Math.round(tankVolume);
 $('target-volume').textContent=targetVolume+' มล.';
 $('ai-volume').textContent=targetVolume+' มล.';
 $('ai-interval').textContent=reminderMinutes+' นาที';
 $('cup-action').textContent=cupAway?'วางแก้วกลับที่แท่น':'ยกแก้วไปดื่ม';
 $('cup-action').disabled=exploded;
 $('sip').disabled=!cupAway||exploded;
 $('stop').disabled=!filling;
 $('remind').disabled=exploded||remaining<=0;
 canvas.dataset.cup=cupAway?'removed':'docked';
 canvas.dataset.dispensing=String(filling);
 canvas.dataset.exploded=String(exploded);
 canvas.dataset.cupMl=String(Math.round(cupVolume));canvas.dataset.bottleMl=String(Math.round(tankVolume));canvas.dataset.flowMlMin='250';
}
function takeCup(){
 if(exploded)return;
 if(!cupAway){
  cupAway=true;cupDest.copy(cupLifted);filling=false;returnPending=false;stopped=false;
  remaining=reminderMinutes*60;
  status('ยกแก้วแล้ว รีเซ็ตเวลาเตือนรอบใหม่ ลองจำลองการจิบแล้ววางแก้วกลับ','รีเซ็ตเวลาแล้ว');
 }else{
  cupAway=false;cupDest.copy(cupDocked);returnPending=true;returnWait=0;stopped=false;
  status('กำลังวางแก้วและรอตรวจให้นิ่ง ก่อนเติมส่วนที่ขาด','กำลังตรวจแก้ว');
 }
 updateUI();drawScreen();
}
$('cup-action').addEventListener('click',takeCup);
$('sip').addEventListener('click',()=>{
 if(!cupAway)return;
 cupVolume=Math.max(0,cupVolume-60);
 status('จำลองจิบน้ำ 60 มล. วางแก้วกลับเพื่อดูการเติมอัตโนมัติ','ยกแก้วไปดื่ม');
 updateWater();updateUI();drawScreen();
});
$('stop').addEventListener('click',()=>{
 filling=false;stopped=true;returnPending=false;
 status('หยุดจ่ายแล้ว ต้องยกแก้วและวางกลับใหม่จึงเริ่มรอบเติมอีกครั้ง','หยุดจ่ายน้ำ','stop');
 updateUI();drawScreen();
});
$('remind').addEventListener('click',()=>{
 remaining=0;
 status('ถึงเวลาดื่มน้ำแล้ว ยกแก้วเพื่อรีเซ็ตเวลาเตือน','ถึงเวลาดื่มน้ำ','warn');
 updateUI();drawScreen();
});
document.querySelectorAll('[data-profile]').forEach(b=>b.addEventListener('click',()=>{
 profile=b.dataset.profile;targetVolume=profiles[profile].volume;reminderMinutes=profiles[profile].minutes;
 remaining=reminderMinutes*60;
 document.querySelectorAll('[data-profile]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));
 if(filling&&cupVolume>=targetVolume)filling=false;
 status('เปลี่ยนชุดค่าตัวอย่างแล้ว เป้าหมายนี้ใช้กับการวางแก้วกลับรอบถัดไป','เปลี่ยนค่าตัวอย่าง');
 updateUI();drawScreen();
}));

let waterSurfaceY=4,lastCupGeometry=-1,lastTankGeometry=-1;
function updateWater(){
 // Fit the water to the tapered simulated interior, calibrated to nominal300ml.
 const r0=2.94,slope=(3.91-r0)/8.0;
 const vol=h=>Math.PI*(r0*r0*h+r0*slope*h*h+slope*slope*h*h*h/3);
 let low=0,high=8.0;const target=THREE.MathUtils.clamp(cupVolume/300,0,1)*vol(8);
 for(let i=0;i<16;i++){const m=(low+high)/2;if(vol(m)<target)low=m;else high=m;}
 const h=Math.max(.01,(low+high)/2),rt=r0+slope*h;
 if(Math.abs(cupVolume-lastCupGeometry)>.4){cupWater.geometry.dispose();cupWater.geometry=new THREE.CylinderGeometry(rt,r0,h,64);lastCupGeometry=cupVolume;}
 cupWater.position.y=.86+h/2;cupWater.visible=cupVolume>1;waterSurfaceY=.86+h;
 meniscus.scale.set(rt/3.65,1,rt/3.65);meniscus.position.y=waterSurfaceY+.015;meniscus.visible=cupVolume>1;
 if(Math.abs(tankVolume-lastTankGeometry)>1){
  const th=.05+Math.max(0,tankVolume/1500)*27.9;
  const waterProfile=[[0,0],[3.1,0],[3.90,.8],[3.90,23.9],[3.75,25.3],[3.2,26.6],[2.0,28.0]];
  const pts=waterProfile.filter(p=>p[1]<th);let radius=3.90;
  for(let i=1;i<waterProfile.length;i++)if(th<=waterProfile[i][1]){const a=waterProfile[i-1],b=waterProfile[i];radius=THREE.MathUtils.lerp(a[0],b[0],(th-a[1])/(b[1]-a[1]));break;}
  pts.push([radius,th],[0,th]);tankWater.geometry.dispose();tankWater.geometry=new THREE.LatheGeometry(pts.map(([r,y])=>new THREE.Vector2(r,y)),64);
  tankWater.position.y=bottleBottom+.3;lastTankGeometry=tankVolume;
 }
 tankWater.visible=tankVolume>1;
}

function drawScreen(){
 const ctx=screenContext;const alert=remaining<=0;
 ctx.fillStyle='#020303';ctx.fillRect(0,0,128,64);
 ctx.fillStyle='#ffffff';ctx.textAlign='left';ctx.font='10px Tahoma, sans-serif';ctx.fillText('kaew.',3,10);
 ctx.textAlign='right';ctx.fillText(Math.round(cupVolume)+' mL',125,10);
 const mm=Math.floor(Math.max(0,remaining)/60).toString().padStart(2,'0'),ss=Math.floor(Math.max(0,remaining)%60).toString().padStart(2,'0');
 ctx.textAlign='center';ctx.font='bold 27px Consolas, monospace';ctx.fillText(mm+':'+ss,64,37);
 ctx.font='12px Tahoma, sans-serif';
 ctx.fillText(stopped?'หยุดจ่ายน้ำ':filling?'กำลังเติมน้ำ':cupAway?'ยกแก้วแล้ว':returnPending?'กำลังตรวจแก้ว':alert?'ถึงเวลาดื่มน้ำ':'รอบเตือนถัดไป',64,57);
 screenTexture.needsUpdate=true;
}
function updatePlacement(value){
 appliance.position.x=2.5-value/10;
 $('placement-value').textContent=value+' มม.';
 canvas.dataset.edgeClearance=String(value);
}
$('desk-placement').addEventListener('input',e=>updatePlacement(Number(e.target.value)));
updatePlacement(40);
function setInsideView(value){
 $('inside').checked=value;internals.visible=value||exploded;
 shell.transparent=value;shell.opacity=value?.24:1;shell.depthWrite=!value;shell.needsUpdate=true;
}
function updateWaterGuide(){
 const visible=$('show-water-path').checked;waterCircuit.setGuide(visible);
 $('scene-note').replaceChildren();
 const first=document.createTextNode(visible?'น้ำ: ขวด → ปั๊ม → หัวจ่าย (เส้นฟ้า)':'ท่อน้ำสีอ่อนเป็นตำแหน่งจัดวางเสนอ');
 const second=document.createTextNode(visible?'ช่วยมองทะลุ · ช่วงในปั๊มเป็นภาพจำลอง':'เปิดเส้นทางน้ำเพื่อดูช่วงที่ตัวเครื่องบัง');
 $('scene-note').append(first,document.createElement('br'),second);
 canvas.dataset.waterGuide=String(visible);
}
$('show-water-path').addEventListener('change',updateWaterGuide);updateWaterGuide();
$('inside').addEventListener('change',e=>{setInsideView(e.target.checked);selectPart(e.target.checked?'gateway':'base');});
$('show-dimensions').addEventListener('change',e=>{dims.visible=e.target.checked;$('dimensions').classList.toggle('visible',e.target.checked);});
document.querySelectorAll('[data-finish]').forEach(b=>b.addEventListener('click',()=>{
 finish=b.dataset.finish;shell.color.set(finish==='porcelain'?'#e8eee3':'#34515a');soft.color.set(finish==='porcelain'?'#d7e2d3':'#29404a');
 document.querySelectorAll('[data-finish]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));
}));

const views={hero:{p:[67,48,77],t:[11.5,21,0]},front:{p:[11.5,28,114],t:[11.5,21,0]},rear:{p:[50,43,-90],t:[11.5,22,-4]},base:{p:[46,30,59],t:[11.5,7,0]},exploded:{p:[93,63,122],t:[11.5,23,0]}};
function setCamera(view){
 const v=views[view];
 cameraTween={from:camera.position.clone(),to:new THREE.Vector3(...v.p),targetFrom:controls.target.clone(),targetTo:new THREE.Vector3(...v.t),time:0};
 activeView=view;controls.maxDistance=view==='exploded'?230:155;
 canvas.dataset.cameraView=view;
 if(camera.aspect<.85){cameraTween.to.sub(cameraTween.targetTo).multiplyScalar(1.15).add(cameraTween.targetTo);}
 if(view==='exploded'&&camera.aspect<.85){cameraTween.to.set(150,82,145);cameraTween.targetTo.set(13,17,2);}
 if(reduced){camera.position.copy(cameraTween.to);controls.target.copy(cameraTween.targetTo);cameraTween=null;controls.update();}
 document.querySelectorAll('[data-camera]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.camera===view)));
 if(view==='base')selectPart('base');
}
document.querySelectorAll('[data-camera]').forEach(b=>b.addEventListener('click',()=>setCamera(b.dataset.camera)));
controls.addEventListener('start',()=>{cameraTween=null;activeView=null;canvas.dataset.cameraView='manual';});
$('exploded').addEventListener('change',e=>{
 exploded=e.target.checked;filling=false;returnPending=false;
 if(exploded){cupAway=false;cupDest.copy(cupDocked);setCamera('exploded');status('แยกชิ้นส่วนเพื่อดูการจัดวาง ปิดโหมดนี้เพื่อลองวงจรเติมน้ำ','มุมแยกชิ้นส่วน');}
 else{setCamera('hero');status('กลับมุมประกอบแล้ว ยกแก้วเพื่อเริ่มลองใช้งาน','พร้อมใช้งาน');}
 updateUI();drawScreen();
});
$('reset-view').addEventListener('click',()=>{
 profile='normal';targetVolume=220;reminderMinutes=25;finish='porcelain';shell.color.set('#e8eee3');soft.color.set('#d7e2d3');
 document.querySelectorAll('[data-profile]').forEach(x=>x.setAttribute('aria-pressed',String(x.dataset.profile==='normal')));
 document.querySelectorAll('[data-finish]').forEach(x=>x.setAttribute('aria-pressed',String(x.dataset.finish==='porcelain')));
 $('desk-scene').checked=false;desk.visible=false;floor.position.y=-.12;
 $('desk-placement').value='40';updatePlacement(40);$('show-dimensions').checked=false;dims.visible=false;$('dimensions').classList.remove('visible');
 cupAway=false;filling=false;stopped=false;returnPending=false;cupVolume=160;tankVolume=bottleCapacity;remaining=reminderMinutes*60;cupDest.copy(cupDocked);
 exploded=false;$('exploded').checked=false;$('inside').checked=false;internals.visible=false;shell.transparent=false;shell.opacity=1;shell.depthWrite=true;shell.needsUpdate=true;
 status('คืนสถานะตัวอย่างเริ่มต้นแล้ว','พร้อมใช้งาน');selectPart('base');setCamera('hero');updateWater();updateUI();drawScreen();
 modelLabels.reset();
 $('show-water-path').checked=true;updateWaterGuide();
});
canvas.addEventListener('keydown',e=>{
 if(e.key==='Home'){e.preventDefault();setCamera('hero');return;}
 if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','-','='].includes(e.key))return;
 e.preventDefault();cameraTween=null;activeView=null;canvas.dataset.cameraView='manual';
 const off=camera.position.clone().sub(controls.target),s=new THREE.Spherical().setFromVector3(off);
 if(e.key==='ArrowLeft')s.theta-=.13;if(e.key==='ArrowRight')s.theta+=.13;
 if(e.key==='ArrowUp')s.phi-=.1;if(e.key==='ArrowDown')s.phi+=.1;
 if(e.key==='+'||e.key==='=')s.radius*=.92;if(e.key==='-')s.radius*=1.08;
 s.phi=THREE.MathUtils.clamp(s.phi,.15,Math.PI*.8);s.radius=THREE.MathUtils.clamp(s.radius,controls.minDistance,controls.maxDistance);
 camera.position.copy(new THREE.Vector3().setFromSpherical(s).add(controls.target));controls.update();
});
function resize(){const w=stage.clientWidth,h=stage.clientHeight;renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();if(activeView)setCamera(activeView);}
new ResizeObserver(resize).observe(stage);resize();
function positionLabels(){
 modelLabels.update({inside:$('inside').checked,exploded,selected:selectedPart});
}
const clock=new THREE.Clock();let elapsed=0,ready=false;
function animate(){
 requestAnimationFrame(animate);
 const dt=Math.min(clock.getDelta(),.08);elapsed+=dt;
 const ease=reduced?1:1-Math.exp(-dt*8);
 explosion=THREE.MathUtils.lerp(explosion,exploded?1:0,ease);
 for(const p of parts)p.object.position.copy(p.offset).multiplyScalar(explosion);
 waterCircuit.update();
 canvas.dataset.waterStages='4';canvas.dataset.waterCircuitVisible=String(waterCircuit.group.visible&&appliance.visible);
 const cupGoal=cupDest.clone().add(new THREE.Vector3(10*explosion,6*explosion,13*explosion));cup.position.lerp(cupGoal,ease);
 if(cameraTween){
  cameraTween.time=Math.min(1,cameraTween.time+dt*1.8);const t=1-Math.pow(1-cameraTween.time,3);
  camera.position.lerpVectors(cameraTween.from,cameraTween.to,t);controls.target.lerpVectors(cameraTween.targetFrom,cameraTween.targetTo,t);
  if(cameraTween.time>=1)cameraTween=null;
 }
 if(!exploded&&remaining>0){const wasPositive=remaining>0;remaining=Math.max(0,remaining-dt);if(wasPositive&&remaining===0)status('ถึงเวลาดื่มน้ำแล้ว ยกแก้วเพื่อเริ่มรอบใหม่','ถึงเวลาดื่มน้ำ','warn');}
 if(returnPending&&!cupAway&&!exploded){
  returnWait+=dt;
  if(returnWait>.7&&cup.position.distanceTo(cupDocked)<.18){
   returnPending=false;
   if(cupVolume<targetVolume&&tankVolume>1){filling=true;status('แก้วนิ่งแล้ว กำลังเติมส่วนที่ขาดถึงเป้าหมายตัวอย่าง','กำลังเติมน้ำ');}
   else if(tankVolume<=1){stopped=true;status('น้ำในขวดจำลองหมด หยุดจ่ายแล้ว กดรีเซ็ตเพื่อเริ่มใหม่','น้ำในขวดหมด','stop');}
   else status('น้ำในแก้วถึงเป้าหมายแล้ว ไม่ต้องเติมเพิ่ม','น้ำถึงเป้าหมายแล้ว');
  }
 }
 if(filling){
  if(cupAway||exploded){filling=false;}
  else{const amount=Math.min((250/60)*dt,Math.max(0,targetVolume-cupVolume),tankVolume);cupVolume+=amount;tankVolume-=amount;
   if(cupVolume>=targetVolume-.01){cupVolume=targetVolume;filling=false;status('เติมถึงเป้าหมายแล้ว พร้อมสำหรับการดื่มรอบต่อไป','เติมเสร็จแล้ว');}
   else if(tankVolume<=.01){filling=false;stopped=true;status('ขวดน้ำจำลองหมด หยุดจ่ายแล้ว','น้ำในขวดหมด','stop');}
  }
 }
 updateWater();
 const bottom=cupDocked.y+waterSurfaceY;const streamHeight=5.05-bottom;
 stream.visible=filling;stream.scale.y=Math.max(.1,streamHeight);stream.position.y=(5.05+bottom)/2;
 drops.forEach((drop,i)=>{drop.visible=filling;drop.position.y=5.0-((elapsed*9+i*1.3)%Math.max(.1,streamHeight));});
 const color=stopped?'#c87a5b':remaining<=0?'#d3a04d':'#68b9a1';indicatorMat.color.set(color);indicatorMat.emissive.set(color);
 if(remaining<=0&&!reduced)indicatorMat.emissiveIntensity=.35+.2*Math.sin(elapsed*3);else indicatorMat.emissiveIntensity=.4;
 internals.visible=$('inside').checked||exploded;
 canvas.dataset.cameraAnimating=String(!!cameraTween);
 canvas.dataset.assemblySettled=String(Math.abs(explosion-(exploded?1:0))<.002);
 canvas.dataset.cupSettled=String(cup.position.distanceTo(cupGoal)<.02);
 controls.update();updateUI();positionLabels();
 if(elapsed-lastScreenUpdate>.2){drawScreen();lastScreenUpdate=elapsed;}
 renderer.render(scene,camera);
 if(!ready){ready=true;$('loader').classList.add('hidden');canvas.dataset.ready='true';canvas.dataset.meshCount=String(renderer.info.render.calls);}
}

const money=n=>new Intl.NumberFormat('th-TH').format(n);
const statusLabels={selected:'เลือกแล้ว',candidate:'ราคาหน้าค้นหา',variant:'ตรวจตัวเลือก',hold:'งบเผื่อ / รอรุ่น',allowance:'ประมาณการ'};
$('budget-total').textContent=money(bom.totals.total);$('budget-button').textContent='รายการซื้อ · '+money(bom.totals.total)+' บาท';
for(const row of bom.rows){
 const tr=document.createElement('tr');
 const title=document.createElement('td');
 if(row.url){const a=document.createElement('a');a.href=row.url;a.target='_blank';a.rel='noopener noreferrer';a.textContent=row.label;title.appendChild(a);}else title.textContent=row.label;
 const badge=document.createElement('small');badge.className='price-status '+row.status;badge.textContent=statusLabels[row.status];title.appendChild(badge);
 const note=document.createElement('p');note.textContent=row.note;title.appendChild(note);tr.appendChild(title);
 for(const v of [row.qty+' '+row.unit,money(row.lineBudget)]){const td=document.createElement('td');td.textContent=v;tr.appendChild(td);}
 $('bom-body').appendChild(tr);
}
for(const [label,key] of [['อุปกรณ์ตามรายการ','parts'],['โครงและของประกอบ','fabrication'],['ค่าส่ง Shopee ตามข้อตกลง','shipping'],['เงินสำรอง','contingency']]){
 const d=document.createElement('div');const dt=document.createElement('span');dt.textContent=label;const dd=document.createElement('strong');dd.textContent=money(bom.totals[key])+' บาท';d.append(dt,dd);$('budget-breakdown').appendChild(d);
}
for(const source of bom.sources){const a=document.createElement('a');a.href=source.url;a.textContent=source.label;a.target='_blank';a.rel='noopener noreferrer';$('source-links').appendChild(a);}
$('budget-button').addEventListener('click',()=>$('budget-dialog').showModal());$('close-budget').addEventListener('click',()=>$('budget-dialog').close());
$('desk-scene').addEventListener('change',e=>{desk.visible=e.target.checked;floor.position.y=e.target.checked?-37:-.12;});
$('export-png').addEventListener('click',()=>{
 renderer.render(scene,camera);modelLabels.update({inside:$('inside').checked,exploded,selected:selectedPart,force:true});
 const w=stage.clientWidth,h=stage.clientHeight,ratio=canvas.width/w,columns=w<520?1:2;
 const footer=modelLabels.shown?104+Math.ceil(modelParts.length/columns)*23:58;
 const output=document.createElement('canvas');output.width=canvas.width;output.height=Math.ceil((h+footer)*ratio);
 const ctx=output.getContext('2d');ctx.scale(ratio,ratio);ctx.drawImage(canvas,0,0,w,h);modelLabels.drawAnnotations(ctx);
 ctx.fillStyle='#f6f9f2';ctx.fillRect(0,h,w,footer);ctx.fillStyle='#244f42';ctx.textBaseline='alphabetic';ctx.font='14px Tahoma, sans-serif';ctx.fillText('Kaew · แบบศึกษาและป้ายกำกับชิ้นส่วน · 31 ต.ค. 2026',16,h+27,w-32);
 if(modelLabels.shown){
  ctx.font='12px Tahoma, sans-serif';const rows=Math.ceil(modelParts.length/columns),colWidth=(w-32)/columns;
  modelParts.forEach((p,i)=>{const col=Math.floor(i/rows),row=i%rows;ctx.fillStyle=p.pending?'#916c31':'#385e4f';ctx.fillText(`${p.number}. ${p.label}${p.pending?' (รอยืนยัน)':p.group==='internal'?' (ภายใน)':''}`,16+col*colWidth,h+56+row*23,colWidth-12);});
 }
 ctx.font='11px Tahoma, sans-serif';ctx.fillStyle='#7a6741';ctx.fillText('เส้นฟ้าเป็นทางน้ำช่วยมองทะลุ · ขนาดและตำแหน่งบางชิ้นเป็นข้อเสนอ',16,h+footer-28,w-32);ctx.fillText('ยังไม่ใช่แบบผลิตหรือวงจรพร้อมต่อ',16,h+footer-11,w-32);
 output.toBlob(blob=>{if(!blob)return;const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='kaew-model-labelled.png';a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);});
});

mountWiringViewer();
mountControlPanel();
selectPart('pump');setCamera('hero');updateWater();updateUI();drawScreen();animate();
