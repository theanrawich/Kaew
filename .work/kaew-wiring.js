import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import data from './kaew-wiring-data.cjs';

// Separate, lazy scene: the product viewer keeps its camera and simulation.
export function mountWiringViewer() {
 const $ = id => document.getElementById(id);
 const dialog = $('wiring-dialog'), stage = $('wiring-stage');
 let renderer, scene, camera, controls, root, observer;
 let boardId = 'gateway', selected = 'oled', selectedWire = -1;
 let wires = [], targets = [], pads = new Map(), labels = [], frame = 0;
 let pointerStart = null;
 const raycaster = new THREE.Raycaster(), pointer = new THREE.Vector2();
 const board = () => data.boards[boardId];
 const involves = (c,id) => id==='all'||c.device===id||c.from.startsWith(id+'.')||c.to.startsWith(id+'.');
 const endpointName = end => {
  const dot=end.indexOf('.'), id=end.slice(0,dot), pin=end.slice(dot+1).replace(/_\d+$/, '');
  return (id==='board' ? board().label : board().devices.find(d=>d.id===id).label) + ' · ' + (pin==='5V' && id==='board' && boardId==='node' ? 'VIN / 5V' : pin);
 };
 const displayPin = pin => pin.replace(/^GPIO/,'').replace(/_\d+$/, '');
 const mat = (color, other={}) => new THREE.MeshStandardMaterial({color,roughness:.55,...other});
 function block(w,h,d,color,x,y,z=.3,parent=root) {
  const m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),mat(color));m.position.set(x,y,z);parent.add(m);return m;
 }
 function textLabel(text,x,y,z,width,height,color='#eef8ef',background=null) {
  const c=document.createElement('canvas');let ctx=c.getContext('2d');ctx.font='500 60px Tahoma, sans-serif';
  c.width=Math.ceil(ctx.measureText(text).width)+24;c.height=84;ctx=c.getContext('2d');
  if(background){ctx.fillStyle=background;ctx.fillRect(0,0,c.width,c.height);}
  ctx.fillStyle=color;ctx.textAlign='center';ctx.textBaseline='middle';ctx.font='500 60px Tahoma, sans-serif';ctx.fillText(text,c.width/2,43);
  const texture=new THREE.CanvasTexture(c);texture.colorSpace=THREE.SRGBColorSpace;
  const naturalWidth=height*c.width/c.height,scale=Math.min(1,width/naturalWidth);
  const m=new THREE.Mesh(new THREE.PlaneGeometry(naturalWidth*scale,height*scale),new THREE.MeshBasicMaterial({map:texture,transparent:true,depthWrite:false,side:THREE.DoubleSide}));
  m.position.set(x,y,z);root.add(m);labels.push(m);return m;
 }
 function terminal(key,x,y,caption,inside=0) {
  const m=block(.68,.68,.8,'#cfb774',x,y,.92);m.userData.end=key;targets.push(m);
  block(.33,.33,.24,'#233b35',x,y,1.42);
  const p=new THREE.Vector3(x,y,1.6);pads.set(key,{p,mesh:m});
  textLabel(caption,x+inside,y,1.52,inside?3.3:4,key.startsWith('board.')?1.45:1.14,inside?'#ffffff':'#183e48',inside?null:'#e9f1eb');
 }
 function buildBoard() {
  const b=board(), count=b.left.length, pitch=1.48, top=(count-1)*pitch/2;
  block(13,40,.65,'#226f56',0,0,.2);
  // Shield, antenna, USB sockets and visible 2.54 mm style header housings.
  block(4.4,9,.8,'#aab9ba',0,10,1);
  block(7.4,3,.3,'#233d36',0,17.5,.7);
  for(let i=0;i<5;i++)block(4.8,.16,.12,'#d6b866',i%2?.7:0,16.5+i*.45,.92);
  block(4,4,.4,'#253634',0,-1,.95);
  for(const x of [-5.8,5.8])block(1.2,top*2+1.4,.55,'#283731',x,0,.75);
  if(boardId==='gateway')for(const x of [-2,2])block(2.7,2.6,1.2,'#b8c4c6',x,-19.4,1);
  else block(4.2,2.6,1.2,'#b8c4c6',0,-19.4,1);
  textLabel(b.label,0,4.8,1.5,6.2,1.25);
  textLabel(boardId==='gateway'?'N16R8':'DevKit V1',0,2.8,1.5,5.7,.95);
  textLabel('USB',0,-16.4,1.5,3,.8);
  for(const [side,list] of [[-1,b.left],[1,b.right]])list.forEach((pin,i)=>terminal('board.'+pin,side*5.8,top-i*pitch,displayPin(pin),-side*2.4));
  textLabel(boardId==='gateway'?'J1':'ซ้าย',-6,21.6,.9,4,1.1,'#3d6556');
  textLabel(boardId==='gateway'?'J3':'ขวา',6,21.6,.9,4,1.1,'#3d6556');
  textLabel('เสาอากาศอยู่ด้านบน',0,24.5,1,15,1.2,'#44685b');
 }
 function buildDevice(d) {
  const h=Math.max(8,d.pins.length*1.2+3), w=18;
  const body=block(w,h,.7,d.status==='hold'?'#8e8066':'#316f64',d.x,d.y,.2);
  body.userData.device=d.id;targets.push(body);
  textLabel(d.label,d.x,d.y+h/2+1.5,1,w+5,1.45,'#183e48');
  textLabel(d.subtitle,d.x,d.y-h/2-1.3,1,w+5,1.02,d.status==='hold'?'#8c632a':'#547b6d');
  const toward=d.x===0?0:(d.x<0?1:-1);
  if(d.pins.length) {
   const top=(d.pins.length-1)*1.2/2;
   d.pins.forEach((pin,i)=>{
    const x=d.x+(toward||1)*(w/2-.5),y=d.y+top-i*1.2;
    terminal(d.id+'.'+pin,x,y,pin,-(toward||1)*3.1);
   });
  }
  if(d.id==='oled') {
   block(8,4,.3,'#152e2b',d.x-2,d.y,1);
   textLabel('kaew.  25:00',d.x-2,d.y+.1,1.3,7.5,.9,'#b6efe5');
  } else if(d.id==='speaker') {
   const m=new THREE.Mesh(new THREE.CylinderGeometry(3.1,3.3,.7,40),mat('#263f3b'));m.rotation.x=Math.PI/2;m.position.set(d.x+2,d.y,.8);root.add(m);
  } else if(d.id==='pullup') {
   block(7,1.3,.5,'#d5c896',d.x-1,d.y,1);
   for(const [x,c] of [[-2.8,'#dfba37'],[-1.3,'#9c4d86'],[.2,'#d24c3a'],[2.3,'#a89149']])block(.5,1.4,.55,c,d.x+x,d.y,1.1);
  } else if(d.pins.length) {
   block(5.8,3.2,.4,'#263b35',d.x+(toward? -toward*2:0),d.y,1);
   textLabel(d.id==='rail'?'3.3V / GND':d.id==='supply'?'5V / GND':d.id==='load'?'E± / A±':'IC',d.x+(toward?-toward*2:0),d.y,1.3,5.3,.95);
  }
 }
 function makeWire(c,index) {
  const a=pads.get(c.from).p,b=pads.get(c.to).p;
  const distance=a.distanceTo(b),lift=2.3+(index%5)*.48;
  const viaA=a.clone().lerp(b,.22),viaB=a.clone().lerp(b,.78);
  // Give every cable a physical endpoint and a distinct rising loop.
  viaA.z=viaB.z=lift+Math.min(distance*.04,2.6);
  viaA.y+=(index%3-1)*.8;viaB.y+=(index%3-1)*.8;
  const curve=new THREE.CatmullRomCurve3([a,viaA,viaB,b]);
  let m;
  if(c.status==='hold') {
   const geo=new THREE.BufferGeometry().setFromPoints(curve.getPoints(64));
   m=new THREE.Line(geo,new THREE.LineDashedMaterial({color:c.color,dashSize:.65,gapSize:.45,transparent:true,opacity:.8}));m.computeLineDistances();
  } else m=new THREE.Mesh(new THREE.TubeGeometry(curve,48,.095,6,false),mat(c.color,{transparent:true,opacity:.9}));
  m.userData.wire=index;root.add(m);targets.push(m);
  const ends=[a,b].map(p=>{
   const end=block(.52,.52,.9,c.color,p.x,p.y,p.z+.35);end.userData.wire=index;targets.push(end);return end;
  });
  wires.push({mesh:m,ends,connection:c});
 }
 function disposeScene() {
  if(!root)return;
  root.traverse(o=>{o.geometry?.dispose();for(const m of (Array.isArray(o.material)?o.material:[o.material]))if(m){m.map?.dispose();m.dispose();}});
  scene.remove(root);
 }
 function renderBoard() {
  disposeScene();root=new THREE.Group();scene.add(root);wires=[];targets=[];pads=new Map();labels=[];
  buildBoard();board().devices.forEach(buildDevice);board().connections.forEach(makeWire);
  $('wiring-board-name').textContent=board().label+' · '+board().model;
  $('wiring-board-note').textContent=board().note;
  stage.dataset.board=boardId;
  const nav=$('wiring-devices');nav.replaceChildren();
  const all=document.createElement('button');all.type='button';all.dataset.wiringDevice='all';all.textContent='ดูสายทั้งหมด';all.addEventListener('click',()=>{choose('all');fit();});nav.appendChild(all);
  for(const d of board().devices){
   const b=document.createElement('button');b.type='button';b.dataset.wiringDevice=d.id;b.textContent=d.label;b.addEventListener('click',()=>{choose(d.id);fit();});nav.appendChild(b);
  }
  document.querySelectorAll('[data-wiring-board]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.wiringBoard===boardId)));
  choose(selected);fit();
 }
 function highlight() {
  wires.forEach(({mesh,ends,connection},i)=>{
   const active=selectedWire>=0?i===selectedWire:involves(connection,selected);
   mesh.material.opacity=active?1:.1;
   if(mesh.material.emissive){mesh.material.emissive.set(active?connection.color:'#000000');mesh.material.emissiveIntensity=active?.22:0;}
   ends.forEach(e=>{e.material.color.set(active?connection.color:'#b7c5bc');e.scale.setScalar(active?1.35:.8);});
  });
  for(const {mesh} of pads.values())mesh.material.color.set('#cfb774');
  const active=selectedWire>=0?[board().connections[selectedWire]]:board().connections.filter(c=>involves(c,selected));
  for(const c of active)for(const end of [c.from,c.to])pads.get(end).mesh.material.color.set(c.color);
  stage.dataset.selectedDevice=selected;stage.dataset.selectedWire=String(selectedWire);
 }
 function choose(id,index=-1) {
  selected=id;selectedWire=index;const d=id==='all'?{label:'สายทั้งหมด',note:'เลือกสายจากรายการเพื่อเน้นต้นทางและปลายทางของเส้นนั้น หรือเลือกอุปกรณ์เพื่อดูเฉพาะชุดสายที่สนใจ',status:'proposal'}:board().devices.find(d=>d.id===id);
  $('wiring-part-name').textContent=d.label;
  $('wiring-part-note').textContent=d.note;
  $('wiring-part-status').textContent=d.status==='hold'?'รอยืนยัน interface':'ผังเสนอ';
  document.querySelectorAll('[data-wiring-device]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.wiringDevice===id)));
  const list=$('wiring-connections');list.replaceChildren();
  board().connections.forEach((c,i)=>{
   if(!involves(c,id))return;
   const row=document.createElement('button');row.type='button';row.className='wire-row';row.dataset.wireIndex=String(i);row.setAttribute('aria-pressed',String(index===i));
   const swatch=document.createElement('i');swatch.style.setProperty('--wire-color',c.color);swatch.className=c.status==='hold'?'wire-dot pending':'wire-dot';
   const content=document.createElement('span');
   const from=document.createElement('strong');from.textContent=endpointName(c.from);
   const to=document.createElement('span');to.className='wire-to';to.textContent='→ '+endpointName(c.to);
   const note=document.createElement('small');note.textContent=c.note;
   content.append(from,to,note);row.append(swatch,content);row.addEventListener('click',()=>choose(id==='all'?c.device:id,index===i?-1:i));list.appendChild(row);
  });
  if(!list.childElementCount){const p=document.createElement('p');p.textContent='อุปกรณ์นี้ไม่มีสายต่อระหว่างบอร์ด';list.appendChild(p);}
  $('wiring-selection').textContent=index>=0?endpointName(board().connections[index].from)+' → '+endpointName(board().connections[index].to):'แสดงสายของ '+d.label;
  highlight();
 }
 function fit(mode='top') {
  const aspect=stage.clientWidth/Math.max(stage.clientHeight,1);
  let minX=-44,maxX=44,minY=-45,maxY=35;
  if(selected!=='all') {
   minX=-9;maxX=9;minY=-22;maxY=25;
   const ids=new Set([selected]);
   for(const c of board().connections.filter(c=>involves(c,selected)))for(const end of [c.from,c.to])ids.add(end.split('.')[0]);
   for(const d of board().devices.filter(d=>ids.has(d.id))){const h=Math.max(8,d.pins.length*1.2+3);minX=Math.min(minX,d.x-12);maxX=Math.max(maxX,d.x+12);minY=Math.min(minY,d.y-h/2-3);maxY=Math.max(maxY,d.y+h/2+3);}
  }
  const cx=(minX+maxX)/2,cy=(minY+maxY)/2;
  const distance=Math.max(maxY-minY,(maxX-minX)/aspect)/(2*Math.tan(THREE.MathUtils.degToRad(38/2)))*1.12;
  controls.target.set(cx,cy,0);
  camera.position.set(cx+(mode==='angle'?distance*.15:0),cy-(mode==='angle'?distance*.25:0),distance);
  controls.update();
 }
 function resize() {
  const w=stage.clientWidth,h=stage.clientHeight;if(!w||!h)return;
  renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();fit();
 }
 function zoom(factor) {camera.position.sub(controls.target).multiplyScalar(factor).add(controls.target);controls.update();}
 function draw() {frame=0;if(!dialog.open)return;controls.update();renderer.render(scene,camera);frame=requestAnimationFrame(draw);}
 function init() {
  renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));
  renderer.outputColorSpace=THREE.SRGBColorSpace;stage.appendChild(renderer.domElement);
  const c=renderer.domElement;c.tabIndex=0;c.setAttribute('aria-label','ผังต่อสายสามมิติ ลากเพื่อหมุน เลื่อนเพื่อซูม เลือกอุปกรณ์และสายจากรายการได้ด้วยคีย์บอร์ด');
  scene=new THREE.Scene();scene.background=new THREE.Color('#e8f0eb');
  scene.add(new THREE.HemisphereLight('#ffffff','#a3b5ac',2.5));
  const light=new THREE.DirectionalLight('#ffffff',2);light.position.set(-20,30,80);scene.add(light);
  camera=new THREE.PerspectiveCamera(38,1,.1,1000);controls=new OrbitControls(camera,c);controls.enableDamping=false;controls.minDistance=15;controls.maxDistance=450;controls.maxPolarAngle=Math.PI;
  raycaster.params.Line.threshold=.35;
  c.addEventListener('pointerdown',e=>{pointerStart={x:e.clientX,y:e.clientY};});
  c.addEventListener('pointerup',e=>{
   if(!pointerStart||Math.hypot(e.clientX-pointerStart.x,e.clientY-pointerStart.y)>5)return;
   const r=c.getBoundingClientRect();pointer.set((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1);raycaster.setFromCamera(pointer,camera);
   const hit=raycaster.intersectObjects(targets,false)[0]?.object;if(!hit)return;
   if(hit.userData.wire!==undefined){const i=hit.userData.wire;choose(board().connections[i].device,i);}
   else if(hit.userData.device)choose(hit.userData.device);
   else if(hit.userData.end){const i=board().connections.findIndex(c=>c.from===hit.userData.end||c.to===hit.userData.end);if(i>=0)choose(board().connections[i].device,i);}
  });
  c.addEventListener('keydown',e=>{
   if(['+','=','-','Home','ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))e.preventDefault();
   if(e.key==='Home')fit();if(e.key==='+'||e.key==='=')zoom(.8);if(e.key==='-')zoom(1.25);
   if(e.key.startsWith('Arrow')){const offset=camera.position.clone().sub(controls.target),s=new THREE.Spherical().setFromVector3(offset);s.theta+=(e.key==='ArrowLeft'?-.12:e.key==='ArrowRight'?.12:0);s.phi=THREE.MathUtils.clamp(s.phi+(e.key==='ArrowUp'?-.12:e.key==='ArrowDown'?.12:0),.05,Math.PI-.05);camera.position.setFromSpherical(s).add(controls.target);controls.update();}
  });
  observer=new ResizeObserver(resize);observer.observe(stage);
  renderBoard();resize();stage.dataset.ready='true';
 }
 $('wiring-button').addEventListener('click',()=>{
  dialog.showModal();
  try{if(!renderer)init();else resize();if(!frame)draw();}
  catch(e){$('wiring-selection').textContent='เปิดผัง 3D ไม่สำเร็จ กรุณาเปิดด้วยเบราว์เซอร์ที่รองรับ WebGL';throw e;}
 });
 $('close-wiring').addEventListener('click',()=>dialog.close());
 dialog.addEventListener('close',()=>{cancelAnimationFrame(frame);frame=0;});
 document.querySelectorAll('[data-wiring-board]').forEach(b=>b.addEventListener('click',()=>{boardId=b.dataset.wiringBoard;selected=boardId==='gateway'?'oled':'temperature';selectedWire=-1;renderBoard();}));
 $('wiring-top').addEventListener('click',()=>fit());$('wiring-angle').addEventListener('click',()=>fit('angle'));
 $('wiring-board-zoom').addEventListener('click',()=>{controls.target.set(0,0,0);camera.position.set(0,0,72);controls.update();});
 $('wiring-zoom-in').addEventListener('click',()=>zoom(.8));$('wiring-zoom-out').addEventListener('click',()=>zoom(1.25));
 $('wiring-export').addEventListener('click',()=>{
  renderer.render(scene,camera);
  const image=document.createElement('canvas'),source=renderer.domElement;
  image.width=source.width;image.height=source.height+110;
  const ctx=image.getContext('2d');ctx.drawImage(source,0,0);ctx.fillStyle='#f6f9f2';ctx.fillRect(0,source.height,image.width,110);ctx.fillStyle='#244b3b';ctx.font='18px Tahoma, sans-serif';ctx.fillText('Kaew · '+board().label+' · ผังเสนอ 31 ต.ค. 2026',18,source.height+28,image.width-36);ctx.font='14px Tahoma, sans-serif';ctx.fillText($('wiring-selection').textContent,18,source.height+56,image.width-36);ctx.fillStyle='#816d45';ctx.fillText('เทียบสกรีนของจริงก่อนต่อ · เส้นประรอยืนยัน · ไม่ใช่ผังพร้อมประกอบปั๊ม/ไฟกำลัง',18,source.height+84,image.width-36);
  image.toBlob(blob=>{if(!blob)return;const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='kaew-wiring-'+boardId+'.png';a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);});
 });
 for(const s of data.sources){const a=document.createElement('a');a.href=s.url;a.textContent=s.label;a.target='_blank';a.rel='noopener noreferrer';$('wiring-sources').appendChild(a);}
}
