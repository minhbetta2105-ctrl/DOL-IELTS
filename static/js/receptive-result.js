(() => {
  const root = document.querySelector('#rt-report'); if (!root) return;
  const rows = [...root.querySelectorAll('[data-answer-status]')];
  const buttons = [...root.querySelectorAll('[data-review-filter]')];
  const targets = [...root.querySelectorAll('[data-review-target]')];
  function filter(key) {
    let count=0;
    rows.forEach(row=>{row.hidden=key!=='all'&&row.dataset.answerStatus!==key;if(!row.hidden)count++;});
    buttons.forEach(btn=>btn.setAttribute('aria-pressed',String(btn.dataset.reviewFilter===key)));
    root.querySelector('#rt-review-count').textContent = `Hiển thị ${count}/${rows.length} câu`;
    root.querySelector('#rt-no-results').hidden=count!==0;
  }
  buttons.forEach(btn=>btn.addEventListener('click',()=>filter(btn.dataset.reviewFilter)));
  targets.forEach(link=>link.addEventListener('click',e=>{
    const row=document.getElementById(link.dataset.reviewTarget);if(!row)return;e.preventDefault();if(row.hidden)filter('all');
    targets.forEach(a=>a.classList.toggle('is-current',a===link));
    row.scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});row.focus({preventScroll:true});
  }));
  root.querySelectorAll('[data-elapsed]').forEach(e=>{const n=Math.max(0,Number(e.dataset.elapsed)||0);e.textContent=`${Math.floor(n/60)} phút ${n%60} giây`;});
  filter('all');
})();
