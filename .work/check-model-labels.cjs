const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const layoutPath=path.join(__dirname,'kaew-callout-layout.cjs');
assert.ok(fs.existsSync(layoutPath),'Model callouts need a collision-aware layout');
const {layoutCallouts}=require(layoutPath),catalog=require('./kaew-model-parts.cjs');
assert.equal(catalog.length,24);
assert.equal(new Set(catalog.map(p=>p.id)).size,24);
assert.equal(new Set(catalog.map(p=>p.number)).size,24);
for(const p of catalog){assert.ok(p.label&&p.title&&p.description);assert.equal(p.point.length,3);assert.ok(['external','internal'].includes(p.group));}
assert.notEqual(catalog.find(p=>p.id==='cup').description,catalog.find(p=>p.id==='tray').description);
assert.ok(catalog.find(p=>p.id==='flow').pending);
let cases=0;
for(const [width,height] of [[320,460],[390,574],[667,754],[938,590]])for(const count of [5,12,24])for(const distribution of ['same','spread','offscreen'])for(const compact of [false,true]){
 const input=Array.from({length:count},(_,i)=>({id:String(i),x:distribution==='same'?width/3:(i%2?width-30:30),y:distribution==='same'?height/2:distribution==='offscreen'?(i-4)*100:90+i*19}));
 const output=layoutCallouts(input,{width,height,top:130,bottom:height-100,compact});
 assert.equal(output.length,count);
 for(const a of output){assert.ok(Number.isFinite(a.left)&&Number.isFinite(a.top));assert.ok(a.left>=8&&a.left+a.width<=width-8+.01);assert.ok(a.top>=130-.01&&a.top+a.height<=height-100+.01);}
 for(let i=0;i<output.length;i++)for(let j=i+1;j<output.length;j++){
  const a=output[i],b=output[j];
  assert.ok(a.left+a.width<=b.left||b.left+b.width<=a.left||a.top+a.height<=b.top+.01||b.top+b.height<=a.top+.01,'Callouts must not overlap');
 }
 cases++;
}
console.log(JSON.stringify({catalog:catalog.length,layoutCases:cases,overlaps:0}));
