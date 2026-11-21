(() => {
  // Mobile menu
  const burger = document.getElementById('burger'), links = document.getElementById('links');
  if (burger && links) burger.addEventListener('click', () => {
    const open = links.classList.toggle('open');
    burger.setAttribute('aria-expanded', String(open));
  });

  // Scroll-driven navbar fade & smooth hero photo zoom
  const nav = document.querySelector('.nav');
  const heroPhoto = document.querySelector('.hero-photo');
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  let lastY = window.scrollY;
  let currentScale = 1;
  let targetScale = 1;

  const updateScrollTargets = () => {
    const y = window.scrollY;

    // Fade/slide navbar out when scrolling down (unless mobile menu is open)
    if (nav) {
      const menuOpen = links && links.classList.contains('open');
      if (!menuOpen && y > 60 && y > lastY) {
        nav.classList.add('nav-hidden');
      } else if (y < lastY || y <= 60) {
        nav.classList.remove('nav-hidden');
      }
    }

    // Target zoom: 1.0x at top -> 1.35x after 500px of scrolling
    if (heroPhoto) {
      const progress = Math.min(Math.max(y / 500, 0), 1);
      targetScale = 1 + progress * 0.35;
    }

    lastY = y;
  };

  const animateHero = () => {
    if (heroPhoto) {
      currentScale += (targetScale - currentScale) * 0.12;
      if (Math.abs(targetScale - currentScale) > 0.0005) {
        const s = currentScale.toFixed(4);
        heroPhoto.style.transform = window.innerWidth <= 900
          ? `scale(${s})`
          : `translateX(-50%) scale(${s})`;
      }
    }
    requestAnimationFrame(animateHero);
  };

  window.addEventListener('scroll', updateScrollTargets, { passive: true });
  updateScrollTargets();
  if (heroPhoto) requestAnimationFrame(animateHero);

  // Fade-up on scroll (content is visible without JS; this only enhances)
  if ('IntersectionObserver' in window && !reduceMotion) {
    const io = new IntersectionObserver(es => es.forEach(e => {
      if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
    }), { threshold: 0.12 });
    document.querySelectorAll('.work,.step,.skill,.row,.stats>div').forEach(el => { el.classList.add('rv'); io.observe(el); });
  }

  // Contact form: send to the form endpoint without leaving the page
  const form = document.getElementById('contact-form'), status = document.getElementById('form-status');
  if (form && form.action) form.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = form.querySelector('button'); btn.disabled = true; status.textContent = 'Sending…';
    try {
      const r = await fetch(form.action, { method: 'POST', body: new FormData(form), headers: { Accept: 'application/json' } });
      if (!r.ok) throw new Error();
      form.reset(); status.textContent = 'Thank you, your message was sent. I will get back to you soon.';
    } catch { status.textContent = 'Something went wrong. Please email me directly instead.'; }
    btn.disabled = false;
  });

  // Count clicks on project links/files
  document.querySelectorAll('[data-track]').forEach(a => a.addEventListener('click', () => {
    try {
      navigator.sendBeacon('/api/track', new Blob([JSON.stringify({
        type: 'link_click', path: location.pathname, ref: '', label: a.dataset.track })], { type: 'application/json' }));
    } catch {}
  }));
})();