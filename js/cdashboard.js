// ── GREETING ──
const greetingMsg = document.getElementById('greetingMsg');
const greetingDate = document.getElementById('greetingDate');
const hour = new Date().getHours();
const timeOfDay = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
const profile = JSON.parse(localStorage.getItem('geneshield_profile') || '{}');
const name = profile.firstName || 'there';
if (greetingMsg) greetingMsg.textContent = `${timeOfDay}, ${name} 👋`;
if (greetingDate) {
  greetingDate.textContent = new Date().toLocaleDateString('en-BW', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
  });
}

// ── SIDEBAR TOGGLE (mobile) ──
const menuToggle = document.getElementById('menuToggle');
const sidebar = document.getElementById('sidebar');
if (menuToggle && sidebar) {
  menuToggle.addEventListener('click', () => sidebar.classList.toggle('open'));
  document.addEventListener('click', e => {
    if (!sidebar.contains(e.target) && !menuToggle.contains(e.target)) sidebar.classList.remove('open');
  });
}

// ── ANIMATE GAUGES ──
window.addEventListener('load', () => {
  document.querySelectorAll('.gauge-fill').forEach(fill => {
    const target = fill.style.width;
    fill.style.width = '0%';
    setTimeout(() => { fill.style.width = target; }, 300);
  });
});

// ── TYPING INDICATOR RESOLVE ──
const typingIndicator = document.getElementById('typingIndicator');
if (typingIndicator) {
  setTimeout(() => {
    typingIndicator.style.display = 'none';
    const newMsg = document.createElement('div');
    newMsg.className = 'cp-msg ai';
    newMsg.innerHTML = '<p>Not necessarily — but it\'s a sign to keep monitoring. I\'ll remind you tomorrow. 😊</p>';
    typingIndicator.parentNode.appendChild(newMsg);
  }, 3000);
}
