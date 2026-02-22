// ── NAVBAR SCROLL ──
const navbar = document.getElementById('navbar');
window.addEventListener('scroll', () => {
  navbar.classList.toggle('scrolled', window.scrollY > 50);
});

// ── HAMBURGER ──
const hamburger = document.getElementById('hamburger');
hamburger.addEventListener('click', () => {
  const navLinks = document.querySelector('.nav-links');
  const navActions = document.querySelector('.nav-actions');
  navLinks.style.display = navLinks.style.display === 'flex' ? 'none' : 'flex';
  if (navActions) navActions.style.display = navActions.style.display === 'flex' ? 'none' : 'flex';
});

// ── STAT COUNTERS ──
const animateCounters = () => {
  document.querySelectorAll('.stat-number').forEach(counter => {
    const target = parseInt(counter.getAttribute('data-target'));
    const step = target / (2000 / 16);
    let current = 0;
    const timer = setInterval(() => {
      current += step;
      if (current >= target) { current = target; clearInterval(timer); }
      counter.textContent = Math.floor(current);
    }, 16);
  });
};
const statsSection = document.querySelector('.stats');
if (statsSection) {
  const observer = new IntersectionObserver(entries => {
    if (entries[0].isIntersecting) { animateCounters(); observer.disconnect(); }
  }, { threshold: 0.3 });
  observer.observe(statsSection);
}

// ── SMOOTH SCROLL ──
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', e => {
    e.preventDefault();
    const target = document.querySelector(anchor.getAttribute('href'));
    if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
});

// ── SCROLL REVEAL ──
const revealElements = document.querySelectorAll('.feature-card, .step-card, .stat-item');
const revealObserver = new IntersectionObserver(entries => {
  entries.forEach((entry, i) => {
    if (entry.isIntersecting) {
      setTimeout(() => {
        entry.target.style.opacity = '1';
        entry.target.style.transform = 'translateY(0)';
      }, i * 100);
      revealObserver.unobserve(entry.target);
    }
  });
}, { threshold: 0.1 });

revealElements.forEach(el => {
  el.style.opacity = '0';
  el.style.transform = 'translateY(30px)';
  el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
  revealObserver.observe(el);
});