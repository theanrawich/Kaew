import * as THREE from '../.work/toolchain/node_modules/three/build/three.module.js';
import {OrbitControls} from '../.work/toolchain/node_modules/three/examples/jsm/controls/OrbitControls.js';
import {createWireSimulation} from './wire-simulation.mjs';
import {encodeFrame} from './wire-codec.mjs';
import {createLocalPipeline} from './telemetry.mjs';

const wireSimulation = createWireSimulation();
const simulation = wireSimulation.plant;
const state = simulation.state;
const telemetry = createLocalPipeline({capacity: 5, historyLimit: 100});
let telemetrySequence = 0;
let wireSequence = 0, wireOnline = true, nextWire = 0;
const telemetryPanel = document.createElement('section');
telemetryPanel.innerHTML = `<h3>ข้อมูลจำลองในหน่วยความจำ</h3>
<p><small>Node ส่งเฟรม UART จำลองทุกวินาที ข้อมูลระดับหมดอายุใน 5 วินาที; ที่เก็บอยู่ในแท็บ ไม่ใช่ cloud หรือเซนเซอร์จริง</small></p>
<div class="actions"><button id="telemetry-send">ส่งตัวอย่างจำลอง</button><button id="telemetry-link">จำลองปลายทางออฟไลน์</button><button id="wire-link">ตัดสาย UART จำลอง</button></div>
<p id="telemetry-status" aria-live="polite"></p><ol id="telemetry-history"></ol>`;
document.querySelector('#events').previousElementSibling.before(telemetryPanel);
function renderTelemetry(message = '') {
  const snap = telemetry.snapshot();
  document.querySelector('#telemetry-link').textContent = snap.online ? 'จำลองปลายทางออฟไลน์' : 'เชื่อมปลายทางจำลองอีกครั้ง';
  document.querySelector('#telemetry-status').textContent = `${message} · ${snap.online ? 'ปลายทางจำลองออนไลน์' : 'ปลายทางจำลองออฟไลน์'} · คิว ${snap.pending.length}/${snap.capacity} · เก็บ ${snap.history.length} รายการ`;
  document.querySelector('#telemetry-history').replaceChildren(...snap.history.slice(-5).reverse().map(m => {
    const li = document.createElement('li');
    li.textContent = `${m.nodeId} #${m.seq} · ${m.timeS.toFixed(1)} วินาที · น้ำในถังจำลอง ${m.readings.tankMl.toFixed(1)} มล.`;
    return li;
  }));
}
document.querySelector('#telemetry-send').onclick = () => {
  const sample = {nodeId: 'node-1', sessionId: 'browser-session', seq: telemetrySequence, timeS: state.time, readings: {tankMl: state.tankMl}};
  const result = telemetry.receive(sample);
  telemetrySequence = (telemetrySequence + 1) >>> 0;
  const labels = {forwarded: 'ส่งถึงที่เก็บจำลอง', buffered: 'เก็บในคิวชั่วคราว', queue_full: 'คิวเต็ม: ไม่รับข้อมูลใหม่', duplicate: 'ข้อความซ้ำ', invalid: 'ข้อมูลไม่ถูกต้อง'};
  renderTelemetry(labels[result]);
};
document.querySelector('#telemetry-link').onclick = () => { telemetry.setOnline(!telemetry.snapshot().online); renderTelemetry(''); };
document.querySelector('#wire-link').onclick = () => { wireOnline=!wireOnline; document.querySelector('#wire-link').textContent=wireOnline?'ตัดสาย UART จำลอง':'ต่อสาย UART จำลอง'; };
renderTelemetry();
const scene = new THREE.Scene(); scene.background = new THREE.Color('#101a22');
const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 5000); camera.position.set(600, 440, 700);
const renderer = new THREE.WebGLRenderer({antialias:true}); renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
const host = document.querySelector('#scene'); host.appendChild(renderer.domElement);
const controls = new OrbitControls(camera,renderer.domElement); controls.target.set(0,160,0); controls.update();
scene.add(new THREE.HemisphereLight(0xe3ffff,0x405657,2.1));
const light = new THREE.DirectionalLight(0xffffff,2); light.position.set(200,500,300); scene.add(light);
const solid = (color, opacity=1) => new THREE.MeshStandardMaterial({color,transparent:opacity<1,opacity,roughness:0.5});
function box(w,h,d,color,x,y,z) {const m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),solid(color));m.position.set(x,y,z);scene.add(m);return m;}
function cylinder(top,bottom,height,color,x,y,z,opacity=1) {const m=new THREE.Mesh(new THREE.CylinderGeometry(top,bottom,height,40),solid(color,opacity));m.position.set(x,y,z);scene.add(m);return m;}
// One scene unit is one millimetre; bottle and enclosure dimensions are provisional.
box(220,16,350,0xd3d8d1,0,8,0); box(126,135,54,0xeeeeeb,0,83,-120);
box(50,25,2,0x204b50,0,100,-92); box(25,180,25,0xc5d1ce,78,100,80);
box(100,20,25,0xc5d1ce,35,190,80);
cylinder(42.5,42.5,300,0xb9d8ed,0,166,-20,0.25);
const tank = cylinder(39,39,1,0x44a8c4,0,17,-20,0.65);
const cup = cylinder(41.5,31.5,90,0xe1f5ff,35,61,105,0.32);
const water = cylinder(35,30,1,0x47b7d3,35,17,105,0.8);
const jet = cylinder(2,2,90,0x54dbed,35,150,105,0.8);
const scalePause = document.createElement('button'); scalePause.textContent = 'หยุดข้อมูลเครื่องชั่ง';
const scaleResume = document.createElement('button'); scaleResume.textContent = 'ให้ข้อมูลเครื่องชั่งกลับมา';
document.querySelector('#fail').after(scalePause, scaleResume);
const scaleNote = document.createElement('small'); scaleNote.textContent = 'ทดลองข้อมูลเครื่องชั่งค้าง: หยุดหลัง 2 วินาทีจำลอง ค่านี้ไม่ใช่ค่าทดสอบจริง';
document.querySelector('#fail').parentElement.after(scaleNote);
scalePause.onclick = () => {simulation.pauseScaleUpdates(); renderState();};
scaleResume.onclick = () => {simulation.resumeScaleUpdates(); renderState();};
function renderState(){
  document.querySelector('#cup').textContent=state.cupPresent?'วางอยู่':'ไม่อยู่';
  document.querySelector('#cupVolume').textContent=`${state.cupMl.toFixed(1)} มล.`;
  document.querySelector('#tankVolume').textContent=`${state.tankMl.toFixed(1)} มล.`;
  document.querySelector('#pump').textContent=state.pump?'ทำงาน':'หยุด';
  document.querySelector('#fault').textContent=state.fault||'ไม่มี';
  cup.visible=state.cupPresent; water.visible=state.cupPresent && state.cupMl>0; jet.visible=state.pump;
  const ch=Math.max(0.01,state.cupMl/300*75); water.scale.y=ch; water.position.y=17+ch/2;
  const th=Math.max(0.01,state.tankMl/1500*280); tank.scale.y=th; tank.position.y=17+th/2;
  document.querySelector('#events').replaceChildren(...state.events.slice(0,12).map(e=>{const li=document.createElement('li');li.textContent=`${e.time.toFixed(1)}s: ${e.message}`;return li;}));
}
for(const [id,method] of Object.entries({place:'placeCup',remove:'removeCup',stop:'pressStop',release:'releaseStop',fail:'failScale',repair:'repairScale',reset:'reset',reboot:'reboot'})) document.querySelector('#'+id).onclick=()=>{simulation[method]();renderState();};
document.querySelector('#start').onclick=()=>{wireSimulation.start(Number(document.querySelector('#target').value));renderState();};
const resize=()=>{const {clientWidth:w,clientHeight:h}=host;renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();};new ResizeObserver(resize).observe(host);
let last;function frame(now){const dt=last === undefined ? 0 : Math.max(0,Math.min((now-last)/1000,0.1));last=now;if(wireOnline && state.time>=nextWire){wireSimulation.receive(encodeFrame({node:1,session:1,seq:wireSequence,centiC:2500,adc:1000,level:state.tankMl>0?1:2}));wireSequence=(wireSequence+1)>>>0;nextWire=state.time+1;}wireSimulation.step(dt);renderState();renderer.render(scene,camera);requestAnimationFrame(frame);}renderState();requestAnimationFrame(frame);
