document.addEventListener("DOMContentLoaded", function () {
  // Navigation SPA for internal sections; external for dashboard.html
  const navLinks = document.querySelectorAll('nav a[data-page]');
  const sections = document.querySelectorAll('main > section[id]');
  const mobileMenuBtn = document.getElementById('mobileMenuBtn');
  const navMenu = document.getElementById('mainNav');
  const loginBtn = document.getElementById('loginBtn');

  // Internal SPA navigation (except Dashboard)
  navLinks.forEach(link => {
    link.addEventListener('click', function (e) {
      const page = link.getAttribute('data-page');
      if (page === 'dashboard') {
        window.location.href = "dashboard.html";
        return;
      }
      if (!document.getElementById(page)) return;
      e.preventDefault();
      sections.forEach(sec => sec.style.display = 'none');
      document.getElementById(page).style.display = 'block';
      navLinks.forEach(l => l.classList.remove('active'));
      link.classList.add('active');
      if (window.innerWidth <= 600) navMenu.classList.remove('active');
    });
  });

  // Initial display (show home section)
  sections.forEach(sec => sec.style.display = 'none');
  if (document.getElementById('home')) document.getElementById('home').style.display = 'block';

  // Mobile menu toggle
  mobileMenuBtn.addEventListener('click', () => {
    navMenu.classList.toggle('active');
  });

  // Hide mobile nav after click (for small screens)
  navMenu.addEventListener('click', e => {
    if (e.target.tagName === "A" && window.innerWidth <= 600) {
      navMenu.classList.remove('active');
    }
  });

  // Responsive: show nav by default on large screens
  window.addEventListener('resize', () => {
    if (window.innerWidth > 600) {
      navMenu.classList.remove('active');
      navMenu.style.display = 'flex';
    } else {
      navMenu.style.display = '';
    }
  });

  // Login button (stub; replace with modal or real auth as needed)
  if (loginBtn) {
    loginBtn.addEventListener('click', function(e){
      e.preventDefault();
      alert('Login functionality coming soon!');
    });
  }
});
