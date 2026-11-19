import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {test} from 'node:test';

const html=readFileSync(new URL('./../static/dashboard.html',import.meta.url),'utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const reading=(seq=1)=>({id:seq,received_at:1700000000,source:'device',level:'wet',temperature_c:26.5,tds_adc:65535,seq});
const scale=(weight=123.4)=>({weight_g:weight,stable:true,cup:true,calibrated:true,age_s:0});
function element(){return {style:{},dataset:{},append(){},reset(){},replaceChildren(...children){this.children=children},setAttribute(){}}}
function harness(){
 const nodes=new Map(),timers=new Map(),streams=[];let now=0,nextTimer=0;
 const document={querySelector(id){if(!nodes.has(id))nodes.set(id,element());return nodes.get(id)},querySelectorAll(){return []},createElement:element};
 const rest={'status':{device:{id:'node-1',online:true}},telemetry:{items:[reading(2)]},scale:{scale:scale()},events:{items:[]},summary:{by_source:{}},notifications:{items:[]},reminder:{reminder:null},advice:{advice:null},profile:{body_weight_kg:null,goal_ml:null}};
 const fetches=[],control={restGate:null};
 const context=vm.createContext({document,console,TextDecoder,AbortController,
  Date:class extends Date{static now(){return now}},
  setInterval(){},setTimeout(fn,delay){const id=++nextTimer;timers.set(id,{fn,at:now+delay});return id},clearTimeout(id){timers.delete(id)},
  fetch:async(url,options)=>{
   fetches.push({url,options});
   if(url!=='/api/telemetry/stream'){
    if(control.restGate)await control.restGate;
    return {ok:true,json:async()=>rest[url.split('/api/')[1].split('?')[0]]};
   }
   const queue=[];let pending;
   const emit=value=>{if(pending){const {resolve}=pending;pending=null;resolve(value)}else queue.push(value)};
   options.signal.addEventListener('abort',()=>{if(pending){pending.reject(Error('aborted'));pending=null}});
   const stream={signal:options.signal,send(frame){emit({value:new TextEncoder().encode(frame),done:false})},sendBytes(value){emit({value,done:false})}};
   streams.push(stream);
   return {ok:true,body:{getReader(){return {read(){if(options.signal.aborted)return Promise.reject(Error('aborted'));return queue.length?Promise.resolve(queue.shift()):new Promise((resolve,reject)=>{pending={resolve,reject}})},async cancel(){emit({done:true})},releaseLock(){}}}}};
  }
 });
 vm.runInContext(script,context);
 const run=code=>vm.runInContext(code,context);
 return {nodes,streams,fetches,rest,control,run,
  async start(){run("token='admin'");this.task=run('startTelemetryStream()');await tick()},
  async snapshot(items=[reading()],value=scale()) {streams.at(-1).send('event: telemetry\ndata: '+JSON.stringify({items,scale:value})+'\n\n');await tick()},
  async advance(ms){const end=now+ms;while(true){const due=[...timers].filter(([,t])=>t.at<=end).sort((a,b)=>a[1].at-b[1].at)[0];if(!due)break;now=due[1].at;timers.delete(due[0]);due[1].fn();await tick()}now=end;await tick()},
  async stop(){run('streamGeneration++;streamController?.abort()');await tick();await this.advance(2000);await this.task}
 };
}

test('fragmented SSE renders the actual table, chart and gateway weight',async()=>{
 const h=harness();await h.start();
 try{
  const bytes=new TextEncoder().encode(': heartbeat\n\nevent: telemetry\ndata: '+JSON.stringify({items:[reading()],scale:scale()})+'\n\n');
  for(let at=0;at<bytes.length;at+=7)h.streams[0].sendBytes(bytes.slice(at,at+7));
  await tick();
  assert.equal(h.fetches[0].options.headers.Authorization,'Bearer admin');
  assert.equal(h.nodes.get('#rows').children.length,1);
  assert.match(h.nodes.get('#telemetry-chart').innerHTML,/<svg/);
  assert.equal(h.nodes.get('#scale-g').textContent,'123.4');
  assert.equal(h.run('streamLive'),true);
 }finally{await h.stop()}
});

test('headers without snapshots retain REST fallback and watchdog reconnects',async()=>{
 const h=harness();await h.start();
 try{
  assert.equal(h.run('streamLive'),false);
  await h.run('refresh()');await h.run('refreshScale()');
  assert.equal(h.run('chartData.telemetry[0].seq'),2);
  assert.equal(h.nodes.get('#scale-g').textContent,'123.4');
  await h.advance(25000);assert.ok(h.streams[0].signal.aborted);
  await h.advance(2000);assert.equal(h.streams.length,2);
  await h.snapshot([reading(3)],scale(150));
  assert.equal(h.run('chartData.telemetry[0].seq'),3);
  assert.equal(h.nodes.get('#scale-g').textContent,'150.0');
 }finally{await h.stop()}
});

test('a stalled live stream falls back and a new login cancels the old reader',async()=>{
 const h=harness();await h.start();
 try{
  await h.snapshot();await h.advance(25000);
  assert.equal(h.run('streamLive'),false);
  await h.run('refresh()');assert.equal(h.run('chartData.telemetry[0].seq'),2);
  await h.advance(2000);await h.snapshot([reading(3)]);
  const old=h.streams.at(-1);const previousTask=h.task;
  h.run("token='new-admin'");h.task=h.run('startTelemetryStream()');await tick();await previousTask;
  assert.ok(old.signal.aborted);
  assert.equal(h.fetches.at(-1).options.headers.Authorization,'Bearer new-admin');
 }finally{await h.stop()}
});

test('heartbeats preserve the stream while unchanged scale values expire',async()=>{
 const h=harness();await h.start();
 try{
  await h.snapshot();await h.advance(11000);h.run('renderScale()');
  assert.equal(h.nodes.get('#scale-g').textContent,'—');
  assert.match(h.nodes.get('#scale-status').textContent,/ไม่มีข้อมูลใหม่/);
  h.streams[0].send(': heartbeat\n\n');await tick();await h.advance(15000);
  assert.equal(h.streams[0].signal.aborted,false);
  assert.equal(h.run('streamLive'),true);
  const count=h.fetches.length;await h.run('refreshScale()');assert.equal(h.fetches.length,count);
 }finally{await h.stop()}
});

test('REST responses in flight cannot replace a newer SSE snapshot',async()=>{
 const h=harness();await h.start();
 try{
  let release;h.control.restGate=new Promise(resolve=>{release=resolve});
  const pending=h.run('refresh()');
  await h.snapshot([reading(9)]);
  // With SSE down again, only the version guard can reject this old REST result.
  await h.advance(25000);assert.equal(h.run('streamLive'),false);
  release();await pending;
  assert.equal(h.run('chartData.telemetry[0].seq'),9);
 }finally{await h.stop()}
});
