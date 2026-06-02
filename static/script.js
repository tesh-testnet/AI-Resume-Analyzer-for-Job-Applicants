'use strict';

/* THEME */
(function(){
  const r=document.documentElement;
  let d=r.getAttribute('data-theme')||(matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light');
  r.setAttribute('data-theme',d);
  function icon(){
    const t=document.querySelector('[data-theme-toggle]');
    if(!t)return;
    t.innerHTML=d==='dark'
      ?'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>'
      :'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
  }
  icon();
  document.querySelector('[data-theme-toggle]')?.addEventListener('click',()=>{d=d==='dark'?'light':'dark';r.setAttribute('data-theme',d);icon();});
})();

/* NAV SCROLL */
window.addEventListener('scroll',()=>document.getElementById('main-nav').classList.toggle('scrolled',scrollY>50),{passive:true});

/* HERO ANIMATE IN */
window.addEventListener('load',()=>{
  [['h-eyebrow',80,{opacity:'1',transform:'translateY(0)'}],
   ['h-heading',240,{opacity:'1'}],
   ['h-sub',400,{opacity:'1',transform:'translateY(0)'}],
   ['h-cta',560,{opacity:'1',transform:'translateY(0)'}]
  ].forEach(([id,d,p])=>setTimeout(()=>{const el=document.getElementById(id);if(el)Object.assign(el.style,p);},d));
});

/* REVEAL ON SCROLL */
const revealObs=new IntersectionObserver((entries)=>{
  entries.forEach(e=>{if(e.isIntersecting)e.target.classList.add('in');});
},{threshold:.1,rootMargin:'0px 0px -40px 0px'});
document.querySelectorAll('.reveal').forEach(el=>revealObs.observe(el));

/* STAT COUNTERS */
function animCount(el,to,dur){
  const dec=to<10?0:0;let start=null;
  function tick(ts){
    if(!start)start=ts;
    const p=Math.min((ts-start)/dur,1);
    const ease=1-Math.pow(1-p,3);
    el.textContent=Math.round(to*ease);
    if(p<1)requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}
const countObs=new IntersectionObserver((entries)=>{
  entries.forEach(e=>{
    if(!e.isIntersecting)return;
    const el=e.target.querySelector('[data-count]');
    if(el&&!el.dataset.done){el.dataset.done='1';animCount(el,+el.dataset.count,1200);}
    countObs.unobserve(e.target);
  });
},{threshold:.4});
document.querySelectorAll('.stat-cell').forEach(el=>countObs.observe(el));

/* DEMO BAR ANIMATION */
const demoObs=new IntersectionObserver((entries)=>{
  entries.forEach(e=>{
    if(!e.isIntersecting)return;
    // score counter
    const sc=document.getElementById('demo-score');
    if(sc&&!sc.dataset.done){sc.dataset.done='1';animCountDec(sc,0,74.2,1600);}
    // bars
    document.querySelectorAll('.demo-fill[data-w]').forEach(b=>{
      if(!b.dataset.done){b.dataset.done='1';setTimeout(()=>{b.style.width=b.dataset.w+'%'},150);}
    });
    demoObs.unobserve(e.target);
  });
},{threshold:.25});
const demoWrap=document.querySelector('.demo-wrap');
if(demoWrap)demoObs.observe(demoWrap);

function animCountDec(el,from,to,dur){
  let start=null;
  function tick(ts){
    if(!start)start=ts;
    const p=Math.min((ts-start)/dur,1);
    const ease=1-Math.pow(1-p,3);
    el.textContent=(from+(to-from)*ease).toFixed(1);
    if(p<1)requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

lucide.createIcons();