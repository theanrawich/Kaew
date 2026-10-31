// Screen-space callout rails: labels keep their 3D anchors but never stack.
function layoutCallouts(items,{width,height,top=136,bottom=height-112,compact=false}){
 if(!items.length)return [];
 const columns=[[],[]],gap=compact?3:5,margin=12;
 for(const item of items)columns[item.x<width/2?0:1].push(item);
 // Balance dense same-side projections (e.g. looking straight at a board stack).
 while(Math.abs(columns[0].length-columns[1].length)>1){
  const from=columns[0].length>columns[1].length?0:1;
  columns[from].sort((a,b)=>Math.abs(a.x-width/2)-Math.abs(b.x-width/2));
  columns[1-from].push(columns[from].shift());
 }
 const out=[];
 columns.forEach((column,side)=>{
  column.sort((a,b)=>a.y-b.y||String(a.id).localeCompare(String(b.id)));
  const available=bottom-top;
  const boxHeight=Math.min(compact?28:34,(available-gap*(column.length-1))/Math.max(1,column.length));
  const boxWidth=compact?Math.max(22,boxHeight):Math.min(168,(width-40)/2);
  let end=top-gap;
  const placed=column.map(item=>{
   const y=Math.max(end+gap,Math.min(bottom-boxHeight,Math.max(top,item.y-boxHeight/2)));
   end=y+boxHeight;
   return {...item,side,left:side?width-margin-boxWidth:margin,top:y,width:boxWidth,height:boxHeight};
  });
  let next=bottom+gap;
  for(let i=placed.length-1;i>=0;i--){placed[i].top=Math.min(placed[i].top,next-gap-boxHeight);next=placed[i].top;}
  out.push(...placed);
 });
 return out;
}
module.exports={layoutCallouts};
