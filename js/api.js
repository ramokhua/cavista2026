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
// REPORT GENERATION (PDF)
// ============================================

async function getReportData() {
  const res = await fetch(`${API_BASE}/api/generate-report`, { credentials: 'include' });
  if (!res.ok) throw new Error('Failed to fetch report data');
  const data = await res.json();
  return data.report;
}

async function generatePDFReport() {
  showToast('Generating your report...', 'success');

  const report = await getReportData();
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF('p', 'mm', 'a4');
  const W = doc.internal.pageSize.getWidth();
  const margin = 18;
  const contentW = W - margin * 2;
  let y = 15;

  // Colors
  const PRIMARY = [0, 181, 255];
  const DARK = [30, 41, 59];
  const GRAY = [100, 116, 139];
  const WHITE = [255, 255, 255];
  const RED = [239, 68, 68];
  const AMBER = [245, 158, 11];
  const GREEN = [34, 197, 94];

  function addPage() {
    doc.addPage();
    y = 15;
  }

  function checkPageBreak(needed) {
    if (y + needed > 275) { addPage(); return true; }
    return false;
  }

  // ── HEADER ──
  doc.setFillColor(...PRIMARY);
  doc.rect(0, 0, W, 42, 'F');
  doc.setTextColor(...WHITE);
  doc.setFontSize(22);
  doc.setFont('helvetica', 'bold');
  doc.text('GeneShield', margin, 18);
  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  doc.text('Hereditary Cancer Risk Assessment Report', margin, 26);
  doc.setFontSize(8);
  const dateStr = new Date(report.generated_at).toLocaleDateString('en-BW', { year: 'numeric', month: 'long', day: 'numeric' });
  doc.text(`Generated: ${dateStr}`, margin, 33);
  doc.text('CONFIDENTIAL - For Patient & Healthcare Provider Use Only', W - margin, 33, { align: 'right' });

  y = 52;

  // ── PATIENT INFO ──
  doc.setTextColor(...DARK);
  doc.setFontSize(13);
  doc.setFont('helvetica', 'bold');
  doc.text('Patient Information', margin, y);
  y += 2;
  doc.setDrawColor(...PRIMARY);
  doc.setLineWidth(0.8);
  doc.line(margin, y, margin + 50, y);
  y += 7;

  const p = report.profile || {};
  const u = report.user || {};
  doc.setFontSize(9);
  doc.setFont('helvetica', 'normal');

  const infoRows = [
    ['Name', `${p.first_name || u.first_name || '--'} ${p.last_name || u.last_name || ''}`],
    ['Gender', p.gender || '--'],
    ['Date of Birth', p.dob || '--'],
    ['District', p.district || '--'],
    ['Blood Type', p.blood_type || '--'],
    ['BMI', report.bmi ? `${report.bmi} (${report.bmi_category})` : '--'],
  ];

  infoRows.forEach(([label, value]) => {
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(...GRAY);
    doc.text(`${label}:`, margin, y);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(...DARK);
    doc.text(String(value), margin + 35, y);
    y += 5.5;
  });

  // Lifestyle
  y += 3;
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(...GRAY);
  doc.setFontSize(8);
  const lifestyle = `Exercise: ${p.exercise || '--'}  |  Diet: ${p.diet || '--'}  |  Smoking: ${p.smoke || '--'}  |  Alcohol: ${p.alcohol || '--'}`;
  doc.text(lifestyle, margin, y);
  y += 10;

  // ── RISK SCORES ──
  checkPageBreak(60);
  doc.setTextColor(...DARK);
  doc.setFontSize(13);
  doc.setFont('helvetica', 'bold');
  doc.text('Hereditary Cancer Risk Assessment', margin, y);
  y += 2;
  doc.setDrawColor(...PRIMARY);
  doc.line(margin, y, margin + 60, y);
  y += 8;

  const scores = report.risk_scores || {};
  const riskTypes = [
    { key: 'breast_cancer', label: 'Breast Cancer' },
    { key: 'cervical_cancer', label: 'Cervical Cancer' },
    { key: 'prostate_cancer', label: 'Prostate Cancer' },
    { key: 'colorectal_cancer', label: 'Colorectal Cancer' },
  ];

  riskTypes.forEach(({ key, label }) => {
    const val = scores[key];
    if (val === undefined || val === null) return;
    checkPageBreak(14);

    const level = val >= 60 ? 'HIGH' : val >= 40 ? 'MODERATE' : 'LOW';
    const color = val >= 60 ? RED : val >= 40 ? AMBER : GREEN;

    // Risk bar background
    doc.setFillColor(240, 240, 240);
    doc.roundedRect(margin, y, contentW, 11, 2, 2, 'F');

    // Risk bar fill
    const fillW = Math.max((val / 100) * contentW, 2);
    doc.setFillColor(...color);
    doc.roundedRect(margin, y, fillW, 11, 2, 2, 'F');

    // Label + percentage
    doc.setFontSize(9);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(...WHITE);
    const labelX = margin + 4;
    doc.text(label, labelX, y + 7.2);

    doc.setTextColor(...DARK);
    doc.text(`${val}%  (${level})`, W - margin, y + 7.2, { align: 'right' });

    y += 15;
  });

  // ── FAMILY HISTORY ──
  y += 3;
  checkPageBreak(40);
  doc.setTextColor(...DARK);
  doc.setFontSize(13);
  doc.setFont('helvetica', 'bold');
  doc.text('Family Cancer History', margin, y);
  y += 2;
  doc.setDrawColor(...PRIMARY);
  doc.line(margin, y, margin + 45, y);
  y += 8;

  doc.setFontSize(9);
  const fatherH = p.father_history || [];
  const motherH = p.mother_history || [];
  const grandH = p.grand_history || [];

  const historyItems = [
    ["Father's Side", fatherH],
    ["Mother's Side", motherH],
    ["Grandparents", grandH],
  ];

  historyItems.forEach(([rel, cancers]) => {
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(...GRAY);
    doc.text(`${rel}:`, margin, y);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(...DARK);
    const cancerStr = cancers.length > 0
      ? cancers.map(c => c.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())).join(', ')
      : 'No cancer history reported';
    doc.text(cancerStr, margin + 32, y);
    y += 6;
  });

  // ── SCREENING RECOMMENDATIONS ──
  y += 5;
  checkPageBreak(40);
  doc.setTextColor(...DARK);
  doc.setFontSize(13);
  doc.setFont('helvetica', 'bold');
  doc.text('Screening Recommendations', margin, y);
  y += 2;
  doc.setDrawColor(...PRIMARY);
  doc.line(margin, y, margin + 52, y);
  y += 8;

  const recs = report.recommendations || [];
  if (recs.length === 0) {
    doc.setFontSize(9);
    doc.setFont('helvetica', 'italic');
    doc.setTextColor(...GRAY);
    doc.text('Complete your health profile to receive personalized screening recommendations.', margin, y);
    y += 8;
  } else {
    recs.forEach(rec => {
      checkPageBreak(16);
      const urgColor = rec.urgency === 'HIGH' ? RED : GREEN;
      doc.setFillColor(...urgColor);
      doc.circle(margin + 2, y - 1, 1.5, 'F');
      doc.setFontSize(9);
      doc.setFont('helvetica', 'bold');
      doc.setTextColor(...DARK);
      doc.text(`${rec.type}  [${rec.urgency}]`, margin + 7, y);
      y += 5;
      doc.setFont('helvetica', 'normal');
      doc.setTextColor(...GRAY);
      const lines = doc.splitTextToSize(rec.detail, contentW - 7);
      doc.text(lines, margin + 7, y);
      y += lines.length * 4.5 + 4;
    });
  }

  // ── VITALS HISTORY ──
  const vitals = report.vitals || [];
  if (vitals.length > 0) {
    y += 3;
    checkPageBreak(30);
    doc.setTextColor(...DARK);
    doc.setFontSize(13);
    doc.setFont('helvetica', 'bold');
    doc.text('Recent Vitals', margin, y);
    y += 2;
    doc.setDrawColor(...PRIMARY);
    doc.line(margin, y, margin + 30, y);
    y += 8;

    // Table header
    doc.setFillColor(240, 245, 250);
    doc.rect(margin, y - 4, contentW, 7, 'F');
    doc.setFontSize(7.5);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(...GRAY);
    const cols = [margin + 2, margin + 30, margin + 55, margin + 78, margin + 100, margin + 120, margin + 142];
    const headers = ['Date', 'BP (mmHg)', 'Glucose', 'Heart Rate', 'Weight', 'Temp', 'SpO2'];
    headers.forEach((h, i) => doc.text(h, cols[i], y));
    y += 6;

    doc.setFont('helvetica', 'normal');
    doc.setTextColor(...DARK);
    vitals.slice(0, 8).forEach(v => {
      checkPageBreak(7);
      const date = v.logged_at ? new Date(v.logged_at).toLocaleDateString('en-BW', { month: 'short', day: 'numeric' }) : '--';
      const bp = v.bp_systolic ? `${v.bp_systolic}/${v.bp_diastolic || '--'}` : '--';
      const vals = [date, bp, v.glucose || '--', v.heart_rate || '--', v.weight || '--', v.temperature || '--', v.oxygen || '--'];
      vals.forEach((val, i) => doc.text(String(val), cols[i], y));
      y += 5;
    });
  }

  // ── FOOTER ──
  y += 8;
  checkPageBreak(25);
  doc.setDrawColor(220, 220, 220);
  doc.line(margin, y, W - margin, y);
  y += 6;
  doc.setFontSize(7.5);
  doc.setFont('helvetica', 'italic');
  doc.setTextColor(...GRAY);
  const disclaimer = [
    'DISCLAIMER: This report is generated by GeneShield AI and is intended for informational purposes only.',
    'It does not constitute a medical diagnosis. Risk scores are based on hereditary analysis, machine learning models,',
    'and self-reported data. Please consult a qualified healthcare professional for medical advice.',
    '',
    'For screening services in Botswana: Princess Marina Hospital (Gaborone) | Nyangabgwe Referral Hospital (Francistown)',
  ];
  disclaimer.forEach(line => {
    doc.text(line, W / 2, y, { align: 'center' });
    y += 3.8;
  });

  // Page numbers
  const totalPages = doc.internal.getNumberOfPages();
  for (let i = 1; i <= totalPages; i++) {
    doc.setPage(i);
    doc.setFontSize(7);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(...GRAY);
    doc.text(`Page ${i} of ${totalPages}`, W / 2, 290, { align: 'center' });
    doc.text('GeneShield - Confidential', W - margin, 290, { align: 'right' });
  }

  // Save / download
  const fname = `GeneShield_Report_${(p.first_name || 'User').replace(/\s/g, '_')}_${new Date().toISOString().slice(0, 10)}.pdf`;
  doc.save(fname);
  showToast('Report downloaded successfully!', 'success');
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
