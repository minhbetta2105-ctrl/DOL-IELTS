/* Reading/Listening MVT enhancement. No answers are sent except through the normal CSRF POST. */
(() => {
  'use strict';
  const root = document.getElementById('rt-test');
  if (!root) return;
  const form = document.getElementById('rt-form');
  const questions = [...root.querySelectorAll('.rt-question')];
  const navButtons = [...root.querySelectorAll('.rt-qnav')];
  const flags = new Set();
  let index = 0;
  let submitting = false;
  const audioAvailable = root.dataset.audioAvailable !== '0';
  const isExam = root.dataset.exam === '1';
  const deadline = root.dataset.deadline ? new Date(root.dataset.deadline).getTime() : 0;
  const start = root.dataset.start ? new Date(root.dataset.start).getTime() : Date.now();
  const isAnswered = (question) => [...question.querySelectorAll('input[name^="answer_"]')].some(el => el.type === 'radio' ? el.checked : el.value.trim() !== '');
  function repaint() {
    let n = 0;
    questions.forEach((q,i) => {
      const answered = isAnswered(q);
      if (answered) n += 1;
      if(navButtons[i]){
        navButtons[i].classList.toggle('is-answered', answered);
        navButtons[i].classList.toggle('is-flagged', flags.has(q.dataset.questionId));
        navButtons[i].classList.toggle('is-current', i === index);
      }
    });
    document.getElementById('rt-count').textContent = `${n}/${questions.length} đã làm`;
  }
  function mobileQuestions() {
    if(root.dataset.skill !== 'reading' || window.innerWidth > 760) return;
    root.classList.add('rt-mobile-questions');
    root.querySelectorAll('.rt-mobile-tab').forEach(b => b.classList.toggle('is-active', b.dataset.pane === 'questions'));
  }
  const passageTabs = [...root.querySelectorAll('[data-passage-tab]')];
  const passages = [...root.querySelectorAll('[data-passage]')];
  const materialPane = root.querySelector('.rt-pane-material');
  const questionPane = root.querySelector('.rt-pane-questions');
  let activePassage = null;
  const questionNumber = q => Number(q.dataset.order || q.querySelector('.rt-question-number').textContent.match(/\d+/)?.[0]);
  function selectPassage(section, reset = false) {
    if (!section) return;
    const changed = activePassage !== section;
    activePassage = section;
    passageTabs.forEach(b => b.setAttribute('aria-pressed', String(b.dataset.passageTab === section.dataset.passage)));
    // Keep all text in the DOM, but display the selected passage only. Highlights survive switching.
    if (passageTabs.length) passages.forEach(p => { p.hidden = p !== section; });
    if (changed || reset) materialPane.scrollTop = 0;
  }
  function goTo(i, {keepMaterial = false, resetPassage = false} = {}) {
    if(i < 0 || i >= questions.length) return;
    index = i;
    const number = questionNumber(questions[i]);
    const section = passages.find(el => number >= Number(el.dataset.first) && number <= Number(el.dataset.last));
    if(section) selectPassage(section, resetPassage);
    const isMobileReading = root.dataset.skill === 'reading' && window.innerWidth <= 760;
    if(!keepMaterial) mobileQuestions();
    const behavior=window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth';
    if(!(keepMaterial && isMobileReading)) {
      if(window.innerWidth>760 && questionPane.scrollHeight>questionPane.clientHeight+2){
        const heading = questions[i].previousElementSibling;
        const target = resetPassage && heading?.classList.contains('rt-part-heading') ? heading : questions[i];
        questionPane.scrollTo({top: Math.max(0,questionPane.scrollTop+target.getBoundingClientRect().top-questionPane.getBoundingClientRect().top-16),behavior:resetPassage?'auto':behavior});
      } else questions[i].scrollIntoView({behavior,block:'start'});
      if(!keepMaterial) questions[i].focus({preventScroll:true});
    }
    root.querySelector('.rt-nav-prev').disabled = index === 0;
    root.querySelector('.rt-nav-next').disabled = index === questions.length-1;
    repaint();
  }
  passageTabs.forEach(b => b.addEventListener('click', () => {
    const section = passages.find(p => p.dataset.passage === b.dataset.passageTab);
    if(!section) return;
    const first = questions.findIndex(q => questionNumber(q) === Number(section.dataset.first));
    selectPassage(section, true);
    if(first >= 0) goTo(first, {keepMaterial:true, resetPassage:true});
  }));
  if(passages.length) selectPassage(passages[0], true);
  questions.forEach((q,i) => {
    q.addEventListener('input', repaint);
    q.addEventListener('change', repaint);
    q.addEventListener('focusin', () => {index=i; const n=questionNumber(q); const p=passages.find(el=>n>=Number(el.dataset.first)&&n<=Number(el.dataset.last)); if(p) selectPassage(p); root.querySelector('.rt-nav-prev').disabled=i===0; root.querySelector('.rt-nav-next').disabled=i===questions.length-1; repaint();});
  });
  navButtons.forEach((b,i)=>b.addEventListener('click',()=>goTo(i)));
  root.querySelector('.rt-nav-prev').addEventListener('click',()=>goTo(index-1));
  root.querySelector('.rt-nav-next').addEventListener('click',()=>goTo(index+1));
  root.querySelectorAll('.rt-flag').forEach(btn => btn.addEventListener('click', () => {
    const id = btn.dataset.flag;
    if(flags.has(id)) flags.delete(id); else flags.add(id);
    btn.setAttribute('aria-pressed', flags.has(id) ? 'true' : 'false');
    repaint();
  }));
  root.querySelectorAll('.rt-mobile-tab').forEach(btn=>btn.addEventListener('click',()=>{
    root.classList.toggle('rt-mobile-questions', btn.dataset.pane === 'questions');
    root.querySelectorAll('.rt-mobile-tab').forEach(b=>b.classList.toggle('is-active', b===btn));
    if(btn.dataset.pane==='questions' && questions.length) goTo(index);
  }));
  const dialog = document.getElementById('rt-submit-dialog');
  const confirm = document.getElementById('rt-confirm');
  const cancel = document.getElementById('rt-cancel');
  root.querySelectorAll('.rt-submit-open').forEach(btn=>btn.addEventListener('click',()=>{
    const answered = questions.filter(isAnswered).length;
    document.getElementById('rt-submit-summary').textContent = `Đã trả lời ${answered}/${questions.length} câu. Còn ${questions.length-answered} câu bỏ trống, ${flags.size} câu đánh dấu xem lại. Bạn chắc chắn muốn nộp bài?`;
    dialog.showModal();
  }));
  cancel.addEventListener('click',()=>dialog.close());
  function submitOnce() {
    if(submitting || !audioAvailable || !questions.length) return;
    submitting = true;
    confirm.disabled = true;
    form.dataset.submitting = 'yes';
    form.requestSubmit();
  }
  confirm.addEventListener('click',submitOnce);
  form.addEventListener('submit',e=>{if(!audioAvailable || !questions.length){e.preventDefault();return;}submitting=true; form.dataset.submitting='yes'; confirm.disabled=true;});
  // A server-issued absolute deadline survives F5. No answer autosave is performed.
  const timer = document.getElementById('rt-timer');
  function formatTime(seconds) {
    const s = Math.max(0,seconds);
    return `${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`;
  }
  function tick(){
    const now=Date.now();
    const value=isExam ? Math.ceil((deadline-now)/1000) : Math.floor((now-start)/1000);
    timer.textContent=formatTime(value);
    if(isExam){
      timer.classList.toggle('rt-time-low', value <= 60);
      if(value <= 0){submitOnce();}
    }
  }
  tick();
  if(!submitting) setInterval(tick, 500);
  window.addEventListener('beforeunload',e=>{
    if(!submitting && questions.some(isAnswered)) {e.preventDefault(); e.returnValue='';}
  });
  const audio=document.getElementById('rt-audio');
  if(audio){
    const btn=document.getElementById('rt-audio-play');
    const state=document.getElementById('rt-play-state');
    const seek=document.getElementById('rt-audio-seek');
    const current=document.getElementById('rt-audio-current');
    const total=document.getElementById('rt-audio-total');
    const speed=document.getElementById('rt-audio-speed');
    const help=document.getElementById('rt-audio-help');
    let maxPlayed=0;let restoring=false;
    // All sample files are real PCM-WAV speech. Keep a browser-level fallback on errors.
    audio.muted=false;audio.volume=1;
    document.getElementById("rt-audio-volume")?.addEventListener("input",e=>{audio.volume=Number(e.target.value);audio.muted=false;});
    audio.addEventListener('canplay',()=>{if(state.textContent==='Đang tải audio…')state.textContent='Sẵn sàng';});
    audio.addEventListener('waiting',()=>{if(!audio.paused)state.textContent='Đang tải audio…';});
    audio.addEventListener('playing',()=>{state.textContent='Đang phát';btn.textContent='Tạm dừng';if(help)help.hidden=true;});
    audio.addEventListener('pause',()=>{if(!audio.ended && audio.currentTime>0){state.textContent='Tạm dừng';btn.textContent='Tiếp tục';}});
    const fmt=(seconds)=>Number.isFinite(seconds)?formatTime(Math.floor(seconds)):'--:--';
    audio.addEventListener('loadedmetadata',()=>{total.textContent=fmt(audio.duration);}); if(audio.readyState >= 1) total.textContent=fmt(audio.duration);
    audio.addEventListener('timeupdate',()=>{
      if(!audio.seeking) maxPlayed=Math.max(maxPlayed,audio.currentTime);
      current.textContent=fmt(audio.currentTime);
      if(Number.isFinite(audio.duration) && audio.duration>0){seek.value=String(audio.currentTime/audio.duration*100);}
    });
    audio.addEventListener('seeking',()=>{
      if(isExam && !restoring && Math.abs(audio.currentTime - maxPlayed)>0.5){
        restoring=true;audio.currentTime=maxPlayed;restoring=false;
      }
    });
    audio.addEventListener('ratechange',()=>{if(isExam && audio.playbackRate!==1) audio.playbackRate=1;});
    audio.addEventListener('error',()=>{state.textContent='Không tải được file âm thanh. Kiểm tra kết nối hoặc đường dẫn media.';if(help)help.hidden=false;if(!isExam)audio.controls=true;});
    audio.addEventListener('ended',()=>{btn.textContent=isExam ? 'Đã kết thúc bài nghe' : 'Phát lại';state.textContent='Đã nghe xong';if(isExam) btn.disabled=true;});
    btn.addEventListener('click',async()=>{
      if(isExam && audio.ended) return;
      if(audio.paused){
        try{if(audio.readyState===0)audio.load();audio.muted=false;await audio.play();btn.textContent='Tạm dừng';state.textContent='Đang phát';}
        catch(err){state.textContent='Không thể phát audio. Thử mở trực tiếp file hoặc trình phát dự phòng.';if(help)help.hidden=false;if(!isExam)audio.controls=true;}
      } else {audio.pause();btn.textContent='Tiếp tục';state.textContent='Tạm dừng';}
    });
    if(!isExam){
      seek.addEventListener('input',()=>{if(Number.isFinite(audio.duration))audio.currentTime=audio.duration*Number(seek.value)/100;});
      document.getElementById('rt-audio-back').addEventListener('click',()=>audio.currentTime=Math.max(0,audio.currentTime-5));
      document.getElementById('rt-audio-forward').addEventListener('click',()=>audio.currentTime=Math.min(audio.duration || Infinity,audio.currentTime+5));
      speed.addEventListener('change',()=>audio.playbackRate=Number(speed.value)||1);
    }
  }
  const passage=document.getElementById('rt-passage');
  if(passage){
    let size=16;
    document.getElementById('rt-smaller').addEventListener('click',()=>{size=Math.max(13,size-1); passage.style.fontSize=size+'px';});
    document.getElementById('rt-larger').addEventListener('click',()=>{size=Math.min(24,size+1); passage.style.fontSize=size+'px';});
    const toolbar=document.getElementById('rt-annotation-tools');
    let selection=null;
    passage.addEventListener('mouseup',()=>{
      const userSelection=window.getSelection();
      if(userSelection && userSelection.toString().trim() && userSelection.rangeCount){
        const range=userSelection.getRangeAt(0);
        if(passage.contains(range.commonAncestorContainer)){selection=range.cloneRange();toolbar.hidden=false;}
      }
    });
    function highlight(note){
      if(!selection || !passage.contains(selection.commonAncestorContainer))return;
      const mark=document.createElement('mark');
      if(note) mark.title=note;
      try{selection.surroundContents(mark);mark.addEventListener('click',()=>{if(mark.title) alert(mark.title);});}
      catch(err){ /* Selection crossed existing markup; ignore instead of corrupting text. */ }
      selection=null;toolbar.hidden=true;window.getSelection()?.removeAllRanges();
    }
    document.getElementById('rt-highlight').addEventListener('click',()=>highlight(''));
    document.getElementById('rt-note').addEventListener('click',()=>{const note=prompt('Ghi chú cho đoạn đã chọn (chỉ tồn tại trong trang này):');if(note!==null)highlight(note.slice(0,500));});
    document.getElementById('rt-clear-annotations').addEventListener('click',()=>{
      passage.querySelectorAll('mark').forEach(mark=>mark.replaceWith(document.createTextNode(mark.textContent)));
      passage.normalize();toolbar.hidden=true;
    });
  }
  repaint();
  if(questions.length){
    root.querySelector('.rt-nav-prev').disabled = true;
    root.querySelector('.rt-nav-next').disabled = questions.length === 1;
  }
})();
