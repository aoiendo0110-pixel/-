// ふわふわ落ちてくるハート
(() => {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const marks = ['♡', '♥', '✿', '❀', '✦'];
  setInterval(() => {
    const el = document.createElement('span');
    el.className = 'floaty';
    el.textContent = marks[Math.floor(Math.random() * marks.length)];
    el.style.left = Math.random() * 100 + 'vw';
    el.style.fontSize = 12 + Math.random() * 16 + 'px';
    el.style.animationDuration = 7 + Math.random() * 6 + 's';
    document.body.appendChild(el);
    el.addEventListener('animationend', () => el.remove());
  }, 900);
})();

// スクロールで出現 & メーター
(() => {
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      e.target.classList.add('show');
      e.target.querySelectorAll('.meter > span').forEach((s) => (s.style.width = s.dataset.value + '%'));
      io.unobserve(e.target);
    }
  }, { threshold: 0.15 });
  document.querySelectorAll('.reveal').forEach((el) => io.observe(el));
})();
