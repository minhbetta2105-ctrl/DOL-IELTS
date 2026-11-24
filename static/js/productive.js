(() => {
  'use strict';
  document.querySelectorAll('img[data-fallback]').forEach(img => {
    const fallback = () => { if (!img.dataset.failed) { img.dataset.failed = '1'; img.src = img.dataset.fallback; } };
    img.addEventListener('error', fallback); if (img.complete && !img.naturalWidth) fallback();
  });
  const root = document.querySelector('[data-report]'); if (!root) return;
  const panels = [...root.querySelectorAll('[data-criterion]')], tabs = [...root.querySelectorAll('.pd-tab')];
  const modes = root.querySelector('[data-mode-controls]');
  let selected = panels[0]?.dataset.criterion, mode = 'single';
  function update() {
    panels.forEach(p => p.hidden = mode === 'single' && p.dataset.criterion !== selected);
    tabs.forEach(t => {const active = t.dataset.selectCriterion === selected; t.classList.toggle('is-active', active); if (active) t.setAttribute('aria-current','true'); else t.removeAttribute('aria-current');});
    modes?.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.mode === mode)));
  }
  if (panels.length) {
    if (modes) modes.hidden = false;
    const hash = location.hash.slice(1); const initial = panels.find(p => p.id === hash); if (initial) selected = initial.dataset.criterion;
    update();
    root.querySelectorAll('[data-select-criterion]').forEach(a => a.addEventListener('click', e => {
      e.preventDefault(); selected = a.dataset.selectCriterion; update();
      if (!a.classList.contains('pd-tab') || mode === 'all') document.getElementById('criterion-' + selected)?.scrollIntoView({block:'start',behavior:'auto'});
    }));
    modes?.querySelectorAll('button').forEach(b => b.addEventListener('click', () => { mode = b.dataset.mode; update(); }));
  }
  const answer = root.querySelector('#pd-answer'), status = root.querySelector('.pd-highlight-status');
  if (!answer || !status) return;
  const original = answer.textContent.trim(); answer.textContent = original;
  function clear() {answer.textContent = original; status.hidden = true;}
  root.querySelector('[data-clear-highlight]')?.addEventListener('click',clear);
  root.querySelectorAll('[data-highlight]').forEach(b => b.addEventListener('click', () => {
    clear(); const quote = b.dataset.highlight.trim(); const index = original.toLocaleLowerCase().indexOf(quote.toLocaleLowerCase());
    status.hidden = false; status.querySelector('span').textContent = index < 0 || !quote ? 'Không tìm thấy trích dẫn nguyên văn trong bài làm.' : 'Đã đánh dấu đoạn tương ứng trong bài làm.';
    if(index >= 0 && quote) {const mark = document.createElement('mark'); mark.textContent = original.slice(index,index+quote.length); answer.replaceChildren(document.createTextNode(original.slice(0,index)),mark,document.createTextNode(original.slice(index+quote.length))); answer.scrollTop = Math.max(0,mark.offsetTop - answer.offsetTop - 30);}
    root.querySelector('#answer-review')?.scrollIntoView({block:'start',behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
    answer.focus({preventScroll:true});
    const marked=answer.querySelector('mark'); if(marked && answer.scrollHeight<=answer.clientHeight+2) marked.scrollIntoView({block:'center',behavior:'auto'});
  }));
})();
