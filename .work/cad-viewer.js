import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
const canvas=document.querySelector('#viewer'), status=document.querySelector('#status');
const renderer=new THREE.WebGLRenderer({canvas,antialias:true}); renderer.setPixelRatio(Math.min(devicePixelRatio,2)); renderer.setClearColor(0xe8efeb);
const scene=new THREE.Scene(); const camera=new THREE.PerspectiveCamera(38,1,.1,10000); camera.up.set(0,0,1);
scene.add(new THREE.HemisphereLight(0xffffff,0x647970,2.2)); const light=new THREE.DirectionalLight(0xffffff,2.5);light.position.set(3,-4,8);scene.add(light);
const controls=new OrbitControls(camera,canvas);controls.enableDamping=true;
const root=new THREE.Group();scene.add(root);
function resize(){const w=canvas.clientWidth,h=canvas.clientHeight;renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix()};window.addEventListener('resize',resize);resize();
fetch('cad-model.json?v=20261106-color').then(r=>{if(!r.ok)throw Error('load');return r.json()}).then(meshes=>{for(const m of meshes){let g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(m.attributes.position.array,3));g.setIndex(m.index.array);if(m.attributes.normal)g.setAttribute('normal',new THREE.Float32BufferAttribute(m.attributes.normal.array,3));else g.computeVertexNormals();let material=new THREE.MeshStandardMaterial({color:new THREE.Color().setRGB(...m.color),roughness:.66,metalness:.08,transparent:m.transparent,opacity:m.transparent ? .32 : 1,depthWrite:!m.transparent,side:THREE.DoubleSide});root.add(new THREE.Mesh(g,material))}let box=new THREE.Box3().setFromObject(root),center=box.getCenter(new THREE.Vector3()),size=box.getSize(new THREE.Vector3()),d=Math.max(size.x,size.y,size.z);controls.target.copy(center);camera.position.copy(center).add(new THREE.Vector3(d*1.15,-d*1.55,d*.9));camera.near=d/1000;camera.far=d*20;camera.updateProjectionMatrix();controls.update();status.textContent='แบบ CAD ชุดประกอบ · 6 พ.ย. 2026';document.querySelector('#reset').onclick=()=>{camera.position.copy(center).add(new THREE.Vector3(d*1.15,-d*1.55,d*.9));controls.target.copy(center);controls.update()};}).catch(()=>status.textContent='โหลดโมเดลไม่สำเร็จ กรุณาลองเปิดหน้านี้อีกครั้ง');
(function animate(){requestAnimationFrame(animate);controls.update();renderer.render(scene,camera)})();


