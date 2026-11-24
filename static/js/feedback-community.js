(() => {
  const dialog = document.getElementById('fb-editor');
  if (!dialog) return;
  let opener = null;
  const open = (event) => {
    if (event && event.currentTarget) opener = event.currentTarget;
    if (!dialog.open) dialog.showModal();
  };
  const close = () => dialog.close();
  dialog.addEventListener('close', () => {
    if (dialog.dataset.editReturn) window.location.assign(dialog.dataset.editReturn);
    else if (opener) opener.focus();
  });
  if (dialog.hasAttribute('data-auto-open')) {
    dialog.removeAttribute('open'); open();
    const invalid = dialog.querySelector('.errorlist');
    if (invalid) invalid.scrollIntoView({block: 'nearest'});
  }
  document.querySelectorAll('[data-open-review]').forEach(btn => btn.addEventListener('click', open));
  document.querySelectorAll('[data-close-review]').forEach(btn => btn.addEventListener('click', close));
  const stars = [...dialog.querySelectorAll('input[name="rating"]')];
  const labels = ['', 'Rất không hài lòng', 'Không hài lòng', 'Bình thường', 'Hài lòng', 'Rất hài lòng'];
  const starLabel = document.getElementById('fb-star-label');
  function paint(value) {
    stars.forEach(star => star.closest('label').classList.toggle('is-filled', Number(star.value) <= value));
    starLabel.textContent = labels[value] || 'Chọn từ 1 đến 5 sao';
  }
  const selected = () => Number(stars.find(star => star.checked)?.value || 0);
  stars.forEach(star => {
    star.addEventListener('change', () => paint(selected()));
    star.closest('label').addEventListener('pointerenter', event => { if (event.pointerType === 'mouse') paint(Number(star.value)); });
  });
  dialog.querySelector('.fb-star-options').addEventListener('pointerleave', () => paint(selected()));
  paint(selected());
  const content = dialog.querySelector('textarea');
  const counter = document.getElementById('fb-count');
  function count() {
    const length = content.value.length;
    counter.textContent = `${length} / 2000 ký tự`;
    counter.classList.toggle('is-near-limit', length >= 1800);
  }
  content.addEventListener('input', count); count();
  const form = dialog.querySelector('[data-review-form]');
  const submit = form.querySelector('[data-submit-review]');
  let submitting = false;
  const initialLabel = submit.textContent;
  form.addEventListener('submit', event => {
    if (submitting) { event.preventDefault(); return; }
    submitting = true; submit.disabled = true; submit.textContent = 'Đang lưu…';
    form.setAttribute('aria-busy', 'true');
  });
  window.addEventListener('pageshow', () => {
    submitting = false; submit.disabled = false; submit.textContent = initialLabel;
    form.removeAttribute('aria-busy');
  });
  document.querySelectorAll('[data-expand]').forEach(btn => {
    const text = document.getElementById(btn.dataset.expand);
    const check = () => { if (!text.classList.contains('is-expanded')) btn.hidden = text.scrollHeight <= text.clientHeight + 1; };
    btn.addEventListener('click', () => {
      const expanded = text.classList.toggle('is-expanded');
      btn.setAttribute('aria-expanded', String(expanded));
      btn.textContent = expanded ? 'Thu gọn ↑' : 'Đọc toàn bộ →';
    });
    check(); if (window.ResizeObserver) new ResizeObserver(check).observe(text);
  });
})();
