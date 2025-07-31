// Reveal card animations on scroll
function revealOnScroll() {
  document.querySelectorAll('.card').forEach(card => {
    const rect = card.getBoundingClientRect();
    if (rect.top < window.innerHeight - 90) {
      card.classList.add('reveal');
    }
  });
}
window.addEventListener('scroll', revealOnScroll);
window.addEventListener('DOMContentLoaded', revealOnScroll);

// Smooth scrolling for anchor links
document.querySelectorAll('nav ul li a').forEach(link => {
  link.addEventListener('click', function(e) {
    const targetId = this.getAttribute('href');
    if (targetId && document.querySelector(targetId)) {
      e.preventDefault();
      document.querySelector(targetId).scrollIntoView({ behavior: 'smooth' });
    }
  });
});

// Contact form: show success message
const contactForm = document.getElementById('contact-form');
if (contactForm) {
  contactForm.addEventListener('submit', function(e) {
    e.preventDefault();
    fetch(contactForm.action, {
      method: 'POST',
      body: new FormData(contactForm),
      headers: { 'Accept': 'application/json' }
    }).then(response => {
      if (response.ok) {
        alert("Thank you for reaching out! Your message was sent successfully.");
        contactForm.reset();
      } else {
        alert("Oops! Something went wrong. Please try again later.");
      }
    });
  });
}

// Theme toggle
const themeToggle = document.getElementById('theme-toggle');
const themeIcon = document.querySelector('.theme-icon');
function setTheme(dark) {
  document.body.classList.toggle('dark', dark);
  themeIcon.textContent = dark ? '☀️' : '🌙';
  localStorage.setItem('aphiwe_theme', dark ? 'dark' : 'light');
}
if (themeToggle) {
  themeToggle.addEventListener('click', () => {
    setTheme(!document.body.classList.contains('dark'));
  });
}
window.addEventListener('DOMContentLoaded', () => {
  setTheme(localStorage.getItem('aphiwe_theme') === 'dark');
});

// Animated background for projects page
function animateProjectsBG() {
  const canvas = document.getElementById('project-bg-canvas');
  if (!canvas) return;
  const parent = document.querySelector('.projects-animated-bg');
  if (!parent) return;
  let w = parent.offsetWidth, h = parent.offsetHeight;
  canvas.width = w; canvas.height = h;
  const ctx = canvas.getContext('2d');
  let t = 0;
  function draw() {
    ctx.clearRect(0, 0, w, h);
    // Colorful animated particles
    for (let i = 0; i < 40; i++) {
      const angle = (i * Math.PI * 2 / 40) + t * 0.03;
      const radius = 100 + 80 * Math.sin(t * 0.01 + i);
      const x = w/2 + Math.cos(angle) * radius + Math.sin(i + t*0.014) * 40;
      const y = h/2 + Math.sin(angle) * radius + Math.cos(i - t*0.018) * 40;
      ctx.beginPath();
      ctx.arc(x, y, 8 + 4 * Math.sin(t*0.06 + i), 0, Math.PI*2);
      ctx.fillStyle = `hsl(${(i*40 + t)%360}, 82%, 60%)`;
      ctx.globalAlpha = 0.55 + 0.45*Math.sin(t*0.1 + i);
      ctx.fill();
    }
    ctx.globalAlpha = 1.0;
    t += 1;
    requestAnimationFrame(draw);
  }
  draw();
}
window.addEventListener('DOMContentLoaded', animateProjectsBG);
window.addEventListener('resize', animateProjectsBG);