    // CV Request Modal Functionality
    const requestCvBtn = document.getElementById('request-cv-btn');
    const cvModal = document.getElementById('cv-modal');
    const closeModal = document.getElementById('close-modal');
    const cvForm = document.getElementById('cv-form');
    const uniqueIdInput = document.getElementById('unique-id');
    const idError = document.getElementById('id-error');
    const successMessage = document.getElementById('success-message');
    const downloadBtn = document.getElementById('download-btn');
    
    // Open modal when Request CV button is clicked
    requestCvBtn.addEventListener('click', () => {
      cvModal.style.display = 'flex';
      setTimeout(() => {
        cvModal.classList.add('active');
      }, 10);
    });
    
    // Close modal when X button is clicked
    closeModal.addEventListener('click', () => {
      cvModal.classList.remove('active');
      setTimeout(() => {
        cvModal.style.display = 'none';
        idError.style.display = 'none';
        successMessage.style.display = 'none';
        downloadBtn.style.display = 'none';
        uniqueIdInput.value = '';
      }, 300);
    });
    
    // Close modal when clicking outside the modal content
    cvModal.addEventListener('click', (e) => {
      if (e.target === cvModal) {
        cvModal.classList.remove('active');
        setTimeout(() => {
          cvModal.style.display = 'none';
          idError.style.display = 'none';
          successMessage.style.display = 'none';
          downloadBtn.style.display = 'none';
          uniqueIdInput.value = '';
        }, 300);
      }
    });
    
    // Handle form submission
    cvForm.addEventListener('submit', (e) => {
      e.preventDefault();
      
      // Check if the ID is correct (0000)
      if (uniqueIdInput.value === '0000') {
        // Show success message and download button
        idError.style.display = 'none';
        successMessage.style.display = 'block';
        downloadBtn.style.display = 'flex';
      } else {
        // Show error message
        idError.style.display = 'block';
        successMessage.style.display = 'none';
        downloadBtn.style.display = 'none';
      }
    });
    
    // Mobile menu toggle
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const navMenu = document.getElementById('nav-menu');
    
    mobileMenuBtn.addEventListener('click', () => {
      navMenu.classList.toggle('active');
      mobileMenuBtn.innerHTML = navMenu.classList.contains('active') ? 
        '<i class="fas fa-times"></i>' : '<i class="fas fa-bars"></i>';
    });
    
    // Close mobile menu when clicking on a link
    document.querySelectorAll('.nav-link').forEach(link => {
      link.addEventListener('click', () => {
        navMenu.classList.remove('active');
        mobileMenuBtn.innerHTML = '<i class="fas fa-bars"></i>';
      });
    });
    
    // Theme toggle
    const themeToggle = document.getElementById('theme-toggle');
    const themeIcon = themeToggle.querySelector('i');
    
    themeToggle.addEventListener('click', () => {
  document.body.classList.toggle('dark');
  if (document.body.classList.contains('dark')) {
    themeIcon.classList.remove('fa-moon');
    themeIcon.classList.add('fa-sun');
    localStorage.setItem('theme', 'dark');
  } else {
    themeIcon.classList.remove('fa-sun');
    themeIcon.classList.add('fa-moon');
    localStorage.setItem('theme', 'light');
  }
});

    
    // Check for saved theme preference
    if (localStorage.getItem('theme') === 'dark') {
      document.body.classList.add('dark');
      themeIcon.classList.remove('fa-moon');
      themeIcon.classList.add('fa-sun');
    }
    
    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
      anchor.addEventListener('click', function(e) {
        if (this.getAttribute('href') === '#') return;
        
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
          target.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
          });
        }
      });
    });
    
    // Contact form submission
    const contactForm = document.getElementById('contact-form');
    if (contactForm) {
      contactForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const formData = new FormData(contactForm);
        
        fetch(contactForm.action, {
          method: 'POST',
          body: formData,
          headers: {
            'Accept': 'application/json'
          }
        })
        .then(response => {
          if (response.ok) {
            alert('Thank you for your message! I will get back to you soon.');
            contactForm.reset();
          } else {
            throw new Error('Form submission failed');
          }
        })
        .catch(error => {
          alert('There was a problem sending your message. Please try again later.');
        });
      });
    }
    
    // Reveal animations
    function reveal() {
      const reveals = document.querySelectorAll(".reveal");
      for (let i = 0; i < reveals.length; i++) {
        const windowHeight = window.innerHeight;
        const elementTop = reveals[i].getBoundingClientRect().top;
        const elementVisible = 150;
        if (elementTop < windowHeight - elementVisible) {
          reveals[i].classList.add("active");
        }
      }
    }
    
    window.addEventListener("scroll", reveal);
    window.addEventListener("load", reveal);