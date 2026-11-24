document.addEventListener('DOMContentLoaded',function(){
 const toggle=document.querySelector('.mobile-nav-toggle'),menu=document.querySelector('#global-navigation');
 if(toggle&&menu){toggle.addEventListener('click',function(){const open=menu.classList.toggle('is-open');toggle.setAttribute('aria-expanded',String(open));toggle.setAttribute('aria-label',open?'Đóng menu':'Mở menu');});}
 if(!window.matchMedia('(prefers-reduced-motion: reduce)').matches&&'IntersectionObserver' in window){
  const observer=new IntersectionObserver(entries=>{entries.forEach(entry=>{if(entry.isIntersecting){entry.target.classList.add('is-visible');observer.unobserve(entry.target);}})},{threshold:.08});
  document.querySelectorAll('.reveal').forEach(el=>observer.observe(el));
 }else{document.querySelectorAll('.reveal').forEach(el=>el.classList.add('is-visible'));}
});

/* Shared, opt-in presentation effects. Content stays visible when JS is off. */
document.addEventListener('DOMContentLoaded',function(){
  const reduce=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if(!reduce && 'IntersectionObserver' in window){
    const appear=new IntersectionObserver(entries=>entries.forEach(entry=>{
      if(entry.isIntersecting){entry.target.classList.add('dol-reveal-enter');appear.unobserve(entry.target);}
    }),{threshold:.12});
    document.querySelectorAll('[data-dol-reveal]').forEach(el=>appear.observe(el));
  }
  // Do not overlay tools on the active Reading/Listening test.
  if(!document.querySelector('#rt-test') && !['prompt_detail','exercise_detail','practice'].includes(document.body.dataset.page) && !document.querySelector('audio[controls]')){
    const b=document.createElement('button');b.type='button';b.className='dol-back-top';b.textContent='↑';b.setAttribute('aria-label','Về đầu trang');b.hidden=true;document.body.append(b);
    const update=()=>{b.hidden=window.scrollY<650;};window.addEventListener('scroll',update,{passive:true});update();b.addEventListener('click',()=>window.scrollTo({top:0,behavior:reduce?'instant':'smooth'}));
  }
});

// Hover for mouse, native-style toggle for click/touch and keyboard.
document.addEventListener('DOMContentLoaded',()=>{
  const group=document.querySelector('.dol-nav-group');if(!group)return;
  const summary=group.querySelector('summary'),pointer=window.matchMedia('(hover: hover) and (pointer: fine)');
  let pinned=false,closeTimer;
  const close=()=>{clearTimeout(closeTimer);pinned=false;group.open=false;};
  const show=()=>{clearTimeout(closeTimer);group.open=true;};
  group.addEventListener('pointerenter',e=>{if(pointer.matches && e.pointerType==='mouse')show();});
  group.addEventListener('pointerleave',e=>{if(pointer.matches && e.pointerType==='mouse' && !pinned)closeTimer=setTimeout(()=>{if(!pinned && !group.querySelector('.dol-nav-pop :focus-visible'))group.open=false;},180);});
  summary.addEventListener('click',e=>{e.preventDefault();clearTimeout(closeTimer);if(pointer.matches && e.detail>0 && group.open && !pinned){pinned=true;return;}if(group.open)close();else{pinned=true;show();}});
  document.addEventListener('click',e=>{if(!group.contains(e.target))close();});
  group.addEventListener('focusout',()=>{setTimeout(()=>{if(!group.contains(document.activeElement) && !group.matches(':hover'))close();},0);});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&group.open){close();summary.focus();}});
});
