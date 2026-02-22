/* ============================================
   GeneShield — API Module
   Flask backend + ML cancer risk engine
   ============================================ */

const API_BASE = '';  // Same origin — Flask serves everything

// ============================================
// AUTH FUNCTIONS
// ============================================

async function signUp(email, password, firstName, lastName) {
  const res = await fetch(`${API_BASE}/api/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ email, password, firstName, lastName })
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Signup failed');
  return data;
}

async function signIn(email, password) {
  const res = await fetch(`${API_BASE}/api/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ email, password })
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Login failed');
  return data;
}

async function signOut() {
  await fetch(`${API_BASE}/api/logout`, {
    method: 'POST',
    credentials: 'include'
  });
  window.location.href = 'login.html';
}

async function getCurrentUser() {
  try {
    const res = await fetch(`${API_BASE}/api/me`, { credentials: 'include' });
    if (!res.ok) return null;
    const data = await res.json();
    return data.user || null;
  } catch {
    return null;
  }
}

async function requireAuth() {
  const user = await getCurrentUser();
  if (!user) {
    window.location.href = 'login.html';
    return null;
  }
  return user;
}

// ============================================
// PROFILE FUNCTIONS
// ============================================

async function saveProfile(profileData) {
  const res = await fetch(`${API_BASE}/api/profile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(profileData)
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Failed to save profile');
  localStorage.setItem('geneshield_profile', JSON.stringify(profileData));
  return data;
}

async function getProfile() {
  const res = await fetch(`${API_BASE}/api/profile`, { credentials: 'include' });
  if (!res.ok) return null;
  const data = await res.json();
  return data.profile || null;
}

// ============================================
// ML RISK CALCULATION (server-side)
// ============================================

async function calculateMLRiskScores(profile) {
  try {
    const res = await fetch(`${API_BASE}/api/calculate-risks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(profile)
    });
    if (!res.ok) throw new Error('ML calculation failed');
    const data = await res.json();
    const scores = data.scores || {};
    // Cache in localStorage
    localStorage.setItem('geneshield_risk_scores', JSON.stringify(scores));
    return scores;
  } catch (err) {
    console.warn('ML risk calculation failed, falling back to client-side:', err);
    // Fallback to client-side heuristic
    const fallbackScores = calculateRiskScores(profile);
    await saveRiskScores(fallbackScores);
    return fallbackScores;
  }
}

// ============================================
// CANCER RISK CALCULATION (client-side fallback)
// ============================================

function calculateRiskScores(profile) {
  let breast_cancer = 10, cervical_cancer = 10, prostate_cancer = 10, colorectal_cancer = 10;

  const fatherH = profile.fatherHistory || profile.father_history || [];
  const motherH = profile.motherHistory || profile.mother_history || [];
  const grandH = profile.grandHistory || profile.grand_history || [];
  const allHistory = [...fatherH, ...motherH, ...grandH];

  // Cancer-specific family history scoring
  allHistory.forEach(condition => {
    const c = condition.toLowerCase();
    if (c.includes('breast_cancer') || c.includes('breast')) breast_cancer += 15;
    if (c.includes('cervical_cancer') || c.includes('cervical')) cervical_cancer += 15;
    if (c.includes('prostate_cancer') || c.includes('prostate')) prostate_cancer += 15;
    if (c.includes('colorectal_cancer') || c.includes('colorectal') || c.includes('colon')) colorectal_cancer += 15;
    if (c.includes('ovarian') || c.includes('ovarian_cancer')) { breast_cancer += 8; cervical_cancer += 5; }
    if (c.includes('lung_cancer') || c.includes('lung')) { breast_cancer += 3; colorectal_cancer += 3; }
    if (c.includes('skin_cancer') || c.includes('skin')) { breast_cancer += 2; }
    if (c.includes('stomach_cancer') || c.includes('stomach')) { colorectal_cancer += 5; }
  });

  // First-degree (parent) history counts more
  const parentHistory = [...fatherH, ...motherH];
  parentHistory.forEach(condition => {
    const c = condition.toLowerCase();
    if (c.includes('breast_cancer')) breast_cancer += 10;
    if (c.includes('cervical_cancer')) cervical_cancer += 10;
    if (c.includes('prostate_cancer')) prostate_cancer += 10;
    if (c.includes('colorectal_cancer')) colorectal_cancer += 10;
  });

  // Age factor
  const age = profile.dob ? Math.floor((Date.now() - new Date(profile.dob)) / 31557600000) : 35;
  if (age >= 60) { breast_cancer += 20; cervical_cancer += 8; prostate_cancer += 20; colorectal_cancer += 18; }
  else if (age >= 45) { breast_cancer += 12; cervical_cancer += 5; prostate_cancer += 12; colorectal_cancer += 10; }
  else if (age >= 30) { breast_cancer += 5; prostate_cancer += 5; colorectal_cancer += 4; }

  // BMI
  const weight = parseFloat(profile.weight) || 70;
  const height = parseFloat(profile.height) || 170;
  const bmi = weight / ((height / 100) ** 2);
  if (bmi >= 30) { breast_cancer += 10; colorectal_cancer += 8; }
  else if (bmi >= 25) { breast_cancer += 5; colorectal_cancer += 4; }

  // Lifestyle
  const exercise = (profile.exercise || '').toLowerCase();
  if (exercise === 'never' || exercise === 'none') {
    breast_cancer += 8; colorectal_cancer += 8; prostate_cancer += 5;
  }

  const smoke = (profile.smoke || '').toLowerCase();
  if (smoke === 'yes') {
    breast_cancer += 5; cervical_cancer += 10; colorectal_cancer += 8; prostate_cancer += 5;
  }

  const alcohol = (profile.alcohol || '').toLowerCase();
  if (alcohol === 'yes' || alcohol === 'regularly') {
    breast_cancer += 8; colorectal_cancer += 6;
  }

  const diet = (profile.diet || '').toLowerCase();
  if (diet === 'poor') {
    colorectal_cancer += 8; breast_cancer += 4;
  } else if (diet === 'excellent' || diet === 'good') {
    colorectal_cancer -= 5; breast_cancer -= 3;
  }

  // Gender filtering
  const gender = (profile.gender || '').toLowerCase();
  const cap = v => Math.min(Math.max(Math.round(v), 3), 95);

  const scores = {};
  scores.breast_cancer = cap(breast_cancer);
  scores.colorectal_cancer = cap(colorectal_cancer);

  if (gender !== 'male') {
    scores.cervical_cancer = cap(cervical_cancer);
  }
  if (gender !== 'female') {
    scores.prostate_cancer = cap(prostate_cancer);
  }

  return scores;
}

// Keep old function name as alias for backwards compatibility
function calculateRiskScoresFallback(profile) {
  return calculateRiskScores(profile);
}

async function saveRiskScores(scores) {
  const res = await fetch(`${API_BASE}/api/risk-scores`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(scores)
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Failed to save risk scores');
  return data;
}

async function getLatestRiskScores() {
  try {
    const res = await fetch(`${API_BASE}/api/risk-scores`, { credentials: 'include' });
    if (!res.ok) return null;
    const data = await res.json();
    return data.scores || null;
  } catch {
    return null;
  }
}

// ============================================
// VITALS FUNCTIONS
// ============================================

async function saveVitals(vitalsData) {
  const res = await fetch(`${API_BASE}/api/vitals`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(vitalsData)
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Failed to save vitals');
  return data;
}

async function getVitalsHistory(limit = 20) {
  try {
    const res = await fetch(`${API_BASE}/api/vitals`, { credentials: 'include' });
    if (!res.ok) return [];
    const data = await res.json();
    return data.vitals || [];
  } catch {
    return [];
  }
}

// ============================================
// CHAT FUNCTIONS
// ============================================

async function sendChatMessage(message) {
  const res = await fetch(`${API_BASE}/api/chat/send`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ message })
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Failed to send message');
  return data.reply;
}

async function getChatHistory(limit = 50) {
  try {
    const res = await fetch(`${API_BASE}/api/chat/history`, { credentials: 'include' });
    if (!res.ok) return [];
    const data = await res.json();
    return data.history || [];
  } catch {
    return [];
  }
}

async function clearChatHistory() {
  const res = await fetch(`${API_BASE}/api/chat/history`, {
    method: 'DELETE',
    credentials: 'include'
  });
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.error || 'Failed to clear chat');
  }
}

// ============================================
// UTILITY: TOAST NOTIFICATIONS
// ============================================

function showToast(message, type = 'success') {
  const existing = document.querySelector('.gs-toast');
  if (existing) existing.remove();
  const toast = document.createElement('div');
  toast.className = `gs-toast gs-toast-${type}`;
  toast.textContent = message;
  toast.style.cssText = `
    position: fixed; bottom: 24px; right: 24px; z-index: 10000;
    padding: 14px 24px; border-radius: 12px; font-family: 'Inter', sans-serif;
    font-size: 0.88rem; font-weight: 600; color: white;
    box-shadow: 0 8px 30px rgba(0,0,0,0.2);
    animation: toastIn 0.3s ease;
    background: ${type === 'error' ? '#EF4444' : type === 'warning' ? '#F59E0B' : '#22C55E'};
  `;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}
