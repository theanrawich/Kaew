import * as THREE from 'three';
import catalog from './kaew-model-parts.cjs';
import {layoutCallouts} from './kaew-callout-layout.cjs';

export function createModelLabels({stage,scene,camera,parents}){
 const $=id=>document.getElementById(id),area=stage.parentElement;
 const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');
 svg.classList.add('model-leaders');svg.setAttribute('aria-hidden','true');area.appendChild(svg);
 const layer=document.createElement('div');layer.className='model-callouts';area.appendChild(layer);
 const entries=new Map(),projected=new THREE.Vector3(),world=new THREE.Vector3();
 let shown=true,lastUpdate=-Infinity,lastLayout=[],selected='pump';
 for(const part of catalog){
  const button=document.createElement('button');button.type='button';button.id='tag-'+part.id;button.className='hotspot model-hotspot';button.dataset.part=part.id;button.hidden=true;
  button.setAttribute('aria-label',part.number+'. '+part.label+(part.pending?' — รอยืนยัน':''));button.title=part.title;
  const number=document.createElement('b');number.textContent=part.number;number.className='part-number';
  const name=document.createElement('span');name.className='part-label';name.textContent=part.label;button.append(number,name);layer.appendChild(button);
  const path=document.createElementNS(ns,'path'),dot=document.createElementNS(ns,'circle');dot.setAttribute('r','2.8');svg.append(path,dot);
  entries.set(part.id,{part,button,path,dot,point:new THREE.Vector3(...part.point)});
  const item=document.createElement('button');item.type='button';item.dataset.part=part.id;item.className='part-index-button';
  const n=document.createElement('b');n.textContent=part.number;const text=document.createElement('span');text.textContent=part.label;
  const status=document.createElement('small');status.textContent=part.pending?'รอยืนยัน':part.group==='internal'?'ภายใน':'ภายนอก';item.append(n,text,status);$('model-parts-list').appendChild(item);
 }
 $('toggle-labels').addEventListener('click',()=>{
  shown=!shown;$('toggle-labels').setAttribute('aria-pressed',String(shown));lastUpdate=-Infinity;
 });
 $('model-parts-button').addEventListener('click',()=>{
  $('explore-tab').click();$('model-parts-index').open=true;
  $('model-parts-index').scrollIntoView({block:'nearest',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
  $('model-parts-index').querySelector('summary').focus({preventScroll:true});
 });
 function update({inside,exploded,selected:current,force=false}){
  const now=performance.now();if(!force&&now-lastUpdate<32)return;lastUpdate=now;selected=current;
  scene.updateMatrixWorld(true);
  const width=stage.clientWidth,height=stage.clientHeight,mode=exploded?'all':inside?'internal':'external';
  const candidates=[];
  for(const entry of entries.values()){
   const {part,button,path,dot,point}=entry;
   button.hidden=true;path.style.display=dot.style.display='none';
   if(!shown||(mode!=='all'&&part.group!==mode&&part.id!==selected))continue;
   world.copy(point).applyMatrix4(parents[part.parent].matrixWorld);projected.copy(world).project(camera);
   if(projected.z<0||projected.z>1||Math.abs(projected.x)>1.04||Math.abs(projected.y)>1.04)continue;
   candidates.push({id:part.id,x:(projected.x*.5+.5)*width,y:(-.5*projected.y+.5)*height,back:!!part.front&&camera.position.z<world.z});
  }
  const compact=width<500||(candidates.length>16&&height<540);
  area.classList.toggle('compact-labels',compact);
  lastLayout=layoutCallouts(candidates,{width,height,top:width<500?128:146,bottom:height-(width<500?116:148),compact});
  for(const item of lastLayout){
   const {button,path,dot,part}=entries.get(item.id),active=part.id===selected;
   button.hidden=false;button.style.left=item.left+'px';button.style.top=item.top+'px';button.style.width=item.width+'px';button.style.height=item.height+'px';
   button.dataset.anchorX=item.x.toFixed(2);button.dataset.anchorY=item.y.toFixed(2);button.classList.toggle('back-facing',item.back);button.classList.toggle('pending',!!part.pending);
   button.title=part.title+(item.back?' — อยู่ด้านหลังมุมนี้':'');
   const endX=item.side?item.left:item.left+item.width,endY=item.top+item.height/2;
   const elbowX=item.side?endX-10:endX+10;
   item.points=[[item.x,item.y],[elbowX,endY],[endX,endY]];item.compact=compact;
   path.setAttribute('d',`M${item.x},${item.y} L${elbowX},${endY} L${endX},${endY}`);
   path.setAttribute('stroke',active?'#216e60':'#7b9488');path.setAttribute('stroke-dasharray',item.back||part.pending?'4 3':'');path.style.display='';
   path.style.opacity=active?'1':exploded?'.34':'.6';
   dot.setAttribute('cx',item.x);dot.setAttribute('cy',item.y);dot.setAttribute('fill',active?'#216e60':'#688a7a');dot.style.display='';
  }
  svg.setAttribute('viewBox',`0 0 ${width} ${height}`);
  $('model-label-count').textContent=shown?`${lastLayout.length}/24`:'ซ่อนอยู่';
  canvasMode(mode,compact);
 }
 function canvasMode(mode,compact){stage.dataset.labelMode=mode;stage.dataset.labelStyle=compact?'numbers':'names';stage.dataset.labelCount=String(lastLayout.length);}
 function drawAnnotations(ctx){
  if(!shown)return;
  for(const item of lastLayout){
   const part=entries.get(item.id).part,active=part.id===selected;
   ctx.beginPath();item.points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.strokeStyle=active?'#216e60':'#7b9488';ctx.lineWidth=1.1;ctx.setLineDash(part.pending||item.back?[4,3]:[]);ctx.stroke();ctx.setLineDash([]);
   ctx.fillStyle=active?'#204d51':'#fbfdf8';ctx.fillRect(item.left,item.top,item.width,item.height);ctx.fillStyle=active?'#ffffff':'#274e44';ctx.textBaseline='middle';ctx.font='12px Tahoma, sans-serif';
   const text=item.compact?String(part.number):part.number+'  '+part.label;ctx.fillText(text,item.left+6,item.top+item.height/2,item.width-12);
  }
 }
 function reset(){shown=true;$('toggle-labels').setAttribute('aria-pressed','true');lastUpdate=-Infinity;}
 return {update,drawAnnotations,reset,get shown(){return shown;},catalog};
}
