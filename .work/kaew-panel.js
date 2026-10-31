// Keep exploration and simulation reachable without a long scrolling control list.
export function mountControlPanel() {
 const panel=document.querySelector('.panel');
 const tabs=[...panel.querySelectorAll('[role="tab"]')];
 const activate=tab=>{
  for(const button of tabs){
   const active=button===tab;
   button.setAttribute('aria-selected',String(active));
   button.tabIndex=active?0:-1;
   document.getElementById(button.getAttribute('aria-controls')).hidden=!active;
  }
  panel.scrollTop=0;
 };
 tabs.forEach((tab,index)=>{
  tab.addEventListener('click',()=>activate(tab));
  tab.addEventListener('keydown',event=>{
   let next;
   if(event.key==='ArrowRight')next=(index+1)%tabs.length;
   if(event.key==='ArrowLeft')next=(index-1+tabs.length)%tabs.length;
   if(event.key==='Home')next=0;
   if(event.key==='End')next=tabs.length-1;
   if(next===undefined)return;
   event.preventDefault();activate(tabs[next]);tabs[next].focus();
  });
 });
 const desk=document.getElementById('desk-scene');
 const placement=document.getElementById('desk-placement');
 const syncDesk=()=>{
  document.getElementById('desk-placement-controls').hidden=!desk.checked;
  placement.disabled=!desk.checked;
 };
 desk.addEventListener('change',syncDesk);
 document.getElementById('reset-view').addEventListener('click',syncDesk);
 document.querySelectorAll('[data-part]').forEach(button=>button.addEventListener('click',()=>{
  activate(tabs[0]);document.getElementById('part-detail').open=true;
 }));
 syncDesk();
}
