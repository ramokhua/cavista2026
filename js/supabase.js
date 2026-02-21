// ================================================================
// ⚠️  ADD YOUR CLAUDE API KEY HERE BEFORE RUNNING
// ================================================================
const CLAUDE_API_KEY = 'YOUR_CLAUDE_API_KEY_HERE';
const CLAUDE_MODEL = 'claude-sonnet-4-20250514';

let chatHistory = [];
let isTyping = false;

// ── LOAD PERSISTED HISTORY ──
function loadHistory() {
  const saved = localStorage.getItem('geneshield_chat_history');
  if (saved) {
    chatHistory = JSON.parse(saved);
    chatHistory.forEach(msg => {
      if (msg.role === 'user') renderUserMessage(msg.content, false);
      else renderAIMessage(msg.content, false);
    });
  }
}

function saveHistory() {
  localStorage.setItem('geneshield_chat_history', JSON.stringify(chatHistory.slice(-50)));
}

// ── BUILD SYSTEM PROMPT FROM USER'S PROFILE + VITALS ──
function getUserContext() {
  const profile = JSON.parse(localStorage.getItem('geneshield_profile') || '{}');
  const vitals = JSON.parse(localStorage.getItem('geneshield_vitals') || '[]');
  const latest = vitals[0] || {};

  return `
You are GeneShield AI, a caring and knowledgeable hereditary cancer companion for ${profile.firstName || 'the user'}.

Your PRIMARY focus is cancer — specifically hereditary cancer risk, screening guidance, prevention, and early detection. The three generic NCDs (diabetes, hypertension, cardiovascular) are in future scope and should NOT be the focus of your responses.

USER PROFILE:
- Name: ${profile.firstName || 'User'} ${profile.lastName || ''}
- District: ${profile.district || 'Botswana'}
- Current conditions: ${profile.currentConditions?.join(', ') || 'None reported'}
- Medications: ${profile.medications || 'None'}
- Exercise: ${profile.exercise || 'Unknown'} | Diet: ${profile.diet || 'Unknown'}
- Smoking: ${profile.smoke || 'Unknown'} | Alcohol: ${profile.alcohol || 'Unknown'}

FAMILY CANCER HISTORY (Hereditary Risk Factors):
- Father's side: ${profile.fatherHistory?.join(', ') || 'Unknown'}
- Mother's side: ${profile.motherHistory?.join(', ') || 'Unknown'}
- Grandparents: ${profile.grandHistory?.join(', ') || 'Unknown'}

AI HEREDITARY CANCER RISK SCORES:
- Breast Cancer: 72% (HIGH) | Colorectal Cancer: 54% (MODERATE) | Cervical Cancer: 48% (MODERATE) | Prostate Cancer: 19% (LOW)

LATEST REPORTED SYMPTOMS:
- Symptoms: ${latest.symptoms?.join(', ') || 'None reported'}
- Weight: ${latest.weight || 'Unknown'} kg
- Notes: ${latest.notes || 'None'}

GUIDELINES:
- Be warm, encouraging, and conversational — not clinical or robotic
- Focus on CANCER — risk, screening, prevention, early detection, family history implications
- Give practical, actionable screening advice (mammograms, Pap smears, colonoscopy, PSA tests)
- Reference their actual hereditary risk data when relevant
- Always remind them to consult a doctor or oncologist for serious concerns
- Keep responses concise (2-4 paragraphs max)
- NEVER diagnose — provide information and guidance only
- This is a Botswana context — be aware of local health realities and available resources
- Encourage regular screening — early detection is the single most powerful tool against cancer mortality
`.trim();
}

// ── RENDER ──
function renderUserMessage(text, scroll = true) {
  const messages = document.getElementById('chatMessages');
  const row = document.createElement('div');
  row.className = 'msg-row user';
  row.innerHTML = `
    <div class="msg-avatar">B</div>
    <div class="msg-bubble user"><p>${text}</p><span class="msg-time">${getTime()}</span></div>
  `;
  messages.appendChild(row);
  if (scroll) messages.scrollTop = messages.scrollHeight;
}

function renderAIMessage(text, scroll = true) {
  const messages = document.getElementById('chatMessages');
  const row = document.createElement('div');
  row.className = 'msg-row ai';
  const formatted = text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n\n/g, '</p><p style="margin-top:8px;">')
    .replace(/\n/g, '<br/>');
  row.innerHTML = `
    <div class="msg-avatar"><i class='bx bx-bot'></i></div>
    <div class="msg-bubble ai"><p>${formatted}</p><span class="msg-time">${getTime()}</span></div>
  `;
  messages.appendChild(row);
  if (scroll) messages.scrollTop = messages.scrollHeight;
}

function showTyping() {
  const messages = document.getElementById('chatMessages');
  const row = document.createElement('div');
  row.className = 'msg-row ai'; row.id = 'typingRow';
  row.innerHTML = `<div class="msg-avatar"><i class='bx bx-bot'></i></div><div class="typing-bubble"><span></span><span></span><span></span></div>`;
  messages.appendChild(row);
  messages.scrollTop = messages.scrollHeight;
}

function removeTyping() {
  const t = document.getElementById('typingRow');
  if (t) t.remove();
}

function getTime() {
  return new Date().toLocaleTimeString('en-BW', { hour: '2-digit', minute: '2-digit' });
}

// ── SEND ──
async function sendMessage(userText) {
  if (!userText.trim() || isTyping) return;
  isTyping = true;

  const promptsEl = document.getElementById('suggestedPrompts');
  if (promptsEl) promptsEl.style.display = 'none';

  const sendBtn = document.getElementById('sendBtn');
  if (sendBtn) sendBtn.disabled = true;

  renderUserMessage(userText);
  chatHistory.push({ role: 'user', content: userText });
  showTyping();

  try {
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': CLAUDE_API_KEY,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: CLAUDE_MODEL,
        max_tokens: 800,
        system: getUserContext(),
        messages: chatHistory.map(m => ({ role: m.role, content: m.content }))
      })
    });

    const data = await response.json();
    const aiReply = data.content?.[0]?.text || "I'm sorry, I couldn't process that. Please try again.";
    chatHistory.push({ role: 'assistant', content: aiReply });
    saveHistory();
    removeTyping();
    renderAIMessage(aiReply);
  } catch (err) {
    removeTyping();
    renderAIMessage("I'm having trouble connecting right now. Please check your internet connection and try again. 💙");
    console.error('Claude API error:', err);
  }

  isTyping = false;
  if (sendBtn) sendBtn.disabled = false;
}

// ── PROMPT CHIPS ──
function sendPrompt(el) {
  const text = el.textContent;
  document.getElementById('chatInput').value = text;
  sendMessage(text);
  document.getElementById('chatInput').value = '';
}

// ── INPUT EVENTS ──
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');

if (chatInput) {
  chatInput.addEventListener('input', () => {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
  });
  chatInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const text = chatInput.value.trim();
      if (text) { sendMessage(text); chatInput.value = ''; chatInput.style.height = 'auto'; }
    }
  });
}

if (sendBtn) {
  sendBtn.addEventListener('click', () => {
    const text = chatInput.value.trim();
    if (text) { sendMessage(text); chatInput.value = ''; chatInput.style.height = 'auto'; }
  });
}

// ── CLEAR CHAT ──
const clearChatBtn = document.getElementById('clearChat');
if (clearChatBtn) {
  clearChatBtn.addEventListener('click', () => {
    if (confirm('Clear all chat history? This cannot be undone.')) {
      chatHistory = [];
      localStorage.removeItem('geneshield_chat_history');
      const messages = document.getElementById('chatMessages');
      messages.innerHTML = `
        <div class="msg-row ai">
          <div class="msg-avatar"><i class='bx bx-bot'></i></div>
          <div class="msg-bubble ai">
            <p>Chat cleared! 👋 I'm still here. How can I help you today?</p>
            <span class="msg-time">${getTime()}</span>
          </div>
        </div>
      `;
      const promptsEl = document.getElementById('suggestedPrompts');
      if (promptsEl) promptsEl.style.display = 'block';
    }
  });
}

// ── INIT ──
loadHistory();
