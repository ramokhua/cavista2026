// ================================================================
// GeneShield Chat — uses Flask backend for Claude API
// ================================================================

let chatHistory = [];
let isTyping = false;

// ── LOAD PERSISTED HISTORY FROM SERVER ──
async function loadHistory() {
  try {
    const history = await getChatHistory();
    if (history && history.length) {
      chatHistory = history.map(m => ({ role: m.role, content: m.content }));
      chatHistory.forEach(msg => {
        if (msg.role === 'user') renderUserMessage(msg.content, false);
        else renderAIMessage(msg.content, false);
      });
    }
  } catch {
    // Fallback to localStorage
    const saved = localStorage.getItem('geneshield_chat_history');
    if (saved) {
      chatHistory = JSON.parse(saved);
      chatHistory.forEach(msg => {
        if (msg.role === 'user') renderUserMessage(msg.content, false);
        else renderAIMessage(msg.content, false);
      });
    }
  }
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

// ── SEND (via Flask backend) ──
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
    const aiReply = await sendChatMessage(userText);
    chatHistory.push({ role: 'assistant', content: aiReply });
    removeTyping();
    renderAIMessage(aiReply);
  } catch (err) {
    removeTyping();
    renderAIMessage("I'm having trouble connecting right now. Please check your internet connection and try again.");
    console.error('Chat error:', err);
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
  clearChatBtn.addEventListener('click', async () => {
    if (confirm('Clear all chat history? This cannot be undone.')) {
      chatHistory = [];
      localStorage.removeItem('geneshield_chat_history');
      try { await clearChatHistory(); } catch (e) { console.error('Clear chat error:', e); }
      const messages = document.getElementById('chatMessages');
      messages.innerHTML = `
        <div class="msg-row ai">
          <div class="msg-avatar"><i class='bx bx-bot'></i></div>
          <div class="msg-bubble ai">
            <p>Chat cleared! I'm still here. How can I help you today?</p>
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
