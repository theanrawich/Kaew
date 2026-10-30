const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.dirname(__dirname),html=fs.readFileSync(path.join(root,'kaew-3d.html'),'utf8');
const start=html.indexOf('<script>'),end=html.lastIndexOf('</script>');
if(start<0||end<start)throw Error('Missing inline script');
const script=html.slice(start+8,end);
if(script.includes('<!-- KAEW_BUNDLE -->')){
 const i=script.indexOf('<!-- KAEW_BUNDLE -->');console.log(JSON.stringify({unexpectedMarkerAt:i,context:script.slice(i-90,i+110)}));
}
try{new vm.Script(script,{filename:'embedded-kaew.js'});}catch(e){console.error(e.stack.split('\n').slice(0,6).join('\n'));process.exit(1);}
if(/<script\b[^>]*\bsrc\s*=|<link\b[^>]*rel=["']stylesheet/i.test(html))throw Error('External runtime asset');
const bom=JSON.parse(fs.readFileSync(path.join(root,'kaew-bom.json'),'utf8'));
const lines=bom.rows.reduce((s,r)=>s+r.qty*r.unitBudget,0);
if(lines+bom.totals.shipping+bom.totals.contingency!==bom.totals.total)throw Error('Budget total mismatch');
if(bom.totals.total>4800)throw Error('Budget exceeds selected ceiling');
console.log(JSON.stringify({inlineScript:'parses',externalRuntimeAssets:0,budgetTotal:bom.totals.total,budgetRows:bom.rows.length,bytes:Buffer.byteLength(html)}));
