/* ============================================
   GeneShield — Supabase Core Module
   Auth, DB, Risk Engine
   ============================================ */

const SUPABASE_URL = 'https://kgyuekwdelkjerwwhgyn.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtneXVla3dkZWxramVyd3doZ3luIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE2ODQ2OTAsImV4cCI6MjA4NzI2MDY5MH0.qMoXH7KIcPxP41EZ7Kjlb9UB3niHRhlcpwBt0nRZ8dQ';

// Initialize Supabase Client (via CDN global)
const supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// ============================================
// AUTH FUNCTIONS
// ============================================

async function signUp(email, password, firstName, lastName) {
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: { data: { first_name: firstName, last_name: lastName } }
  });
  if (error) throw error;
  return data;
}

async function signIn(email, password) {
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw error;
  return data;
}

async function signOut() {
  const { error } = await supabase.auth.signOut();
  if (error) throw error;
  window.location.href = 'login.html';
}

async function getCurrentUser() {
  const { data: { user } } = await supabase.auth.getUser();
  return user;
}

async function requireAuth() {
  const user = await getCurrentUser();
  if (!user) {
    window.location.href = 'login.html';
    return null;
  }
  return user;
}

// Keep session consistent across tabs
supabase.auth.onAuthStateChange((event) => {
  if (event === 'SIGNED_OUT') window.location.href = 'login.html';
});

// ============================================
// PROFILE FUNCTIONS
// ============================================

async function saveProfile(profileData) {
  const user = await getCurrentUser();
  if (!user) throw new Error('Not authenticated');

  const { data, error } = await supabase
    .from('health_profiles')
    .upsert({
      user_id: user.id,
      first_name: profileData.firstName,
      last_name: profileData.lastName,
      dob: profileData.dob || null,
      gender: profileData.gender,
      phone: profileData.phone,
      district: profileData.district,
      height: profileData.height ? parseFloat(profileData.height) : null,
      weight: profileData.weight ? parseFloat(profileData.weight) : null,
      blood_type: profileData.bloodType,
      current_conditions: profileData.currentConditions || [],
      medications: profileData.medications,
      father_history: profileData.fatherHistory || [],
      mother_history: profileData.motherHistory || [],
      grand_history: profileData.grandHistory || [],
      exercise: profileData.exercise,
      diet: profileData.diet,
      smoke: profileData.smoke,
      alcohol: profileData.alcohol,
      sleep: profileData.sleep,
      updated_at: new Date().toISOString()
    }, { onConflict: 'user_id' })
    .select();

  if (error) throw error;
  localStorage.setItem('geneshield_profile', JSON.stringify(profileData));
  return data;
}

async function getProfile() {
  const user = await getCurrentUser();
  if (!user) return null;

  const { data, error } = await supabase
    .from('health_profiles')
    .select('*')
    .eq('user_id', user.id)
    .single();

  if (error && error.code !== 'PGRST116') throw error; // PGRST116 = no rows
  return data;
}

// ============================================
// HEREDITARY CANCER RISK ENGINE (client-side heuristic)
// Primary focus: Breast, Cervical, Colorectal, Prostate Cancer
// NCDs (diabetes, hypertension, CVD, kidney) are FUTURE SCOPE
// ============================================

function calculateRiskScores(profile) {
  let breast = 8, cervical = 8, colorectal = 8, prostate = 8;

  const fatherH = profile.fatherHistory || profile.father_history || [];
  const motherH = profile.motherHistory || profile.mother_history || [];
  const grandH = profile.grandHistory || profile.grand_history || [];
  const allHistory = [...fatherH, ...motherH, ...grandH];

  // ── Family history weights ──
  allHistory.forEach(condition => {
    const c = condition.toLowerCase();
    // Breast / Ovarian strongly linked (BRCA genes)
    if (c.includes('breast')) breast += 18;
    if (c.includes('ovarian')) breast += 12; // BRCA overlap
    // Cervical
    if (c.includes('cervical')) cervical += 16;
    // Colorectal / colon
    if (c.includes('colorectal') || c.includes('colon') || c.includes('rectal') || c.includes('bowel')) colorectal += 16;
    if (c.includes('stomach')) colorectal += 6; // Lynch syndrome overlap
    // Prostate
    if (c.includes('prostate')) prostate += 18;
    // Lung (general modifier)
    if (c.includes('lung')) { breast += 4; colorectal += 4; }
    // Generic cancer flag — distribute across all
    if (c === 'other_cancer' || c === 'cancer') { breast += 5; cervical += 5; colorectal += 5; prostate += 5; }
  });

  // ── Paternal vs maternal weighting for breast cancer ──
  const motherHist = profile.motherHistory || profile.mother_history || [];
  motherHist.forEach(c => {
    if (c.toLowerCase().includes('breast') || c.toLowerCase().includes('ovarian')) breast += 10; // extra weight for maternal line
  });

  // ── Age modifiers ──
  const age = profile.dob ? Math.floor((Date.now() - new Date(profile.dob)) / 31557600000) : 35;
  if (age >= 60) { breast += 18; cervical += 8; colorectal += 20; prostate += 20; }
  else if (age >= 50) { breast += 12; cervical += 6; colorectal += 14; prostate += 16; }
  else if (age >= 40) { breast += 8; cervical += 5; colorectal += 8; prostate += 8; }
  else if (age >= 30) { breast += 4; cervical += 8; colorectal += 3; prostate += 2; }

  // ── Gender modifiers ──
  const gender = (profile.gender || '').toLowerCase();
  if (gender === 'male') { breast = Math.max(breast - 20, 3); cervical = 0; }
  if (gender === 'female') { prostate = 0; }

  // ── Lifestyle risk amplifiers ──
  const smoke = (profile.smoke || '').toLowerCase();
  if (smoke === 'yes' || smoke === 'current') { cervical += 14; colorectal += 10; breast += 6; }
  else if (smoke === 'occasionally') { cervical += 7; colorectal += 5; }

  const alcohol = (profile.alcohol || '').toLowerCase();
  if (alcohol === 'yes' || alcohol === 'regularly' || alcohol === 'heavy' || alcohol === 'daily') {
    breast += 10; colorectal += 8;
  } else if (alcohol === 'occasionally') {
    breast += 5; colorectal += 3;
  }

  const diet = (profile.diet || '').toLowerCase();
  if (diet === 'poor') { colorectal += 10; breast += 5; }
  else if (diet === 'average') { colorectal += 5; }

  const exercise = (profile.exercise || '').toLowerCase();
  if (exercise === 'never' || exercise === 'sedentary') { breast += 8; colorectal += 8; prostate += 5; }
  else if (exercise === 'rarely') { breast += 4; colorectal += 4; }

  const bmi_weight = parseFloat(profile.weight) || 70;
  const bmi_height = parseFloat(profile.height) || 170;
  const bmi = bmi_weight / ((bmi_height / 100) ** 2);
  if (bmi >= 35) { breast += 12; colorectal += 10; prostate += 6; }
  else if (bmi >= 30) { breast += 8; colorectal += 6; prostate += 4; }
  else if (bmi >= 25) { breast += 4; colorectal += 3; }

  // ── Cap at realistic bounds ──
  const cap = v => Math.min(Math.max(Math.round(v), 3), 95);
  return {
    breast: cap(breast),
    cervical: cap(cervical),
    colorectal: cap(colorectal),
    prostate: cap(prostate)
  };
}

async function saveRiskScores(scores) {
  const user = await getCurrentUser();
  if (!user) throw new Error('Not authenticated');
  const { data, error } = await supabase
    .from('risk_scores')
    .insert({
      user_id: user.id,
      breast: scores.breast,
      cervical: scores.cervical,
      colorectal: scores.colorectal,
      prostate: scores.prostate
    })
    .select();
  if (error) throw error;
  return data;
}

async function getLatestRiskScores() {
  const user = await getCurrentUser();
  if (!user) return null;
  const { data, error } = await supabase
    .from('risk_scores')
    .select('*')
    .eq('user_id', user.id)
    .order('created_at', { ascending: false })
    .limit(1)
    .single();
  if (error && error.code !== 'PGRST116') throw error;
  return data;
}

// ============================================
// VITALS FUNCTIONS
// ============================================

async function saveVitals(vitalsData) {
  const user = await getCurrentUser();
  if (!user) throw new Error('Not authenticated');
  const { data, error } = await supabase
    .from('vitals_logs')
    .insert({
      user_id: user.id,
      bp_systolic: vitalsData.bpSystolic ? parseInt(vitalsData.bpSystolic) : null,
      bp_diastolic: vitalsData.bpDiastolic ? parseInt(vitalsData.bpDiastolic) : null,
      glucose: vitalsData.glucose ? parseFloat(vitalsData.glucose) : null,
      heart_rate: vitalsData.heartRate ? parseInt(vitalsData.heartRate) : null,
      weight: vitalsData.weight ? parseFloat(vitalsData.weight) : null,
      temperature: vitalsData.temperature ? parseFloat(vitalsData.temperature) : null,
      oxygen: vitalsData.oxygen ? parseFloat(vitalsData.oxygen) : null,
      symptoms: vitalsData.symptoms || [],
      notes: vitalsData.notes || ''
    })
    .select();
  if (error) throw error;
  return data;
}

async function getVitalsHistory(limit = 20) {
  const user = await getCurrentUser();
  if (!user) return [];
  const { data, error } = await supabase
    .from('vitals_logs')
    .select('*')
    .eq('user_id', user.id)
    .order('logged_at', { ascending: false })
    .limit(limit);
  if (error) throw error;
  return data || [];
}

// ============================================
// CHAT HISTORY (optional persistence)
// ============================================

async function saveChatMessage(role, content) {
  const user = await getCurrentUser();
  if (!user) return;
  const { error } = await supabase
    .from('chat_history')
    .insert({ user_id: user.id, role, content });
  if (error) console.error('Chat save error:', error);
}

async function getChatHistory(limit = 50) {
  const user = await getCurrentUser();
  if (!user) return [];
  const { data, error } = await supabase
    .from('chat_history')
    .select('*')
    .eq('user_id', user.id)
    .order('created_at', { ascending: true })
    .limit(limit);
  if (error) throw error;
  return data || [];
}

async function clearChatHistory() {
  const user = await getCurrentUser();
  if (!user) return;
  const { error } = await supabase
    .from('chat_history')
    .delete()
    .eq('user_id', user.id);
  if (error) throw error;
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
    padding: 14px 24px; border-radius: 12px; font-family: 'Sora', 'Inter', sans-serif;
    font-size: 0.88rem; font-weight: 600; color: white;
    box-shadow: 0 8px 30px rgba(0,0,0,0.2);
    animation: toastIn 0.3s ease;
    background: ${type === 'error' ? '#EF4444' : type === 'warning' ? '#F59E0B' : '#22C55E'};
  `;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// ============================================
// CONNECTIVITY CHECK
// ============================================
async function checkSupabaseConnectivity() {
  try {
    // Auth endpoint ping proves keys, URL, and CORS are OK
    const { error } = await supabase.auth.getSession();
    if (error) throw error;
    return true;
  } catch (err) {
    console.error('Supabase connectivity issue:', err);
    return false;
  }
}
