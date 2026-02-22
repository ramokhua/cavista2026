// ── DATE LABEL ──
const logDate = document.getElementById('logDate');
if (logDate) {
  logDate.textContent = new Date().toLocaleDateString('en-BW', { weekday: 'short', month: 'short', day: 'numeric' });
}

// ── SAVE VITALS ──
const saveBtn = document.getElementById('saveVitals');
const toast = document.getElementById('toast');

if (saveBtn) {
  saveBtn.addEventListener('click', () => {
    const entry = {
      date: new Date().toISOString(),
      bpSystolic: document.getElementById('bpSystolic').value,
      bpDiastolic: document.getElementById('bpDiastolic').value,
      glucose: document.getElementById('glucose').value,
      heartRate: document.getElementById('heartRate').value,
      weight: document.getElementById('weight').value,
      temperature: document.getElementById('temperature').value,
      oxygen: document.getElementById('oxygen').value,
      symptoms: [...document.querySelectorAll('.sym-item input:checked')].map(i => i.value),
      notes: document.getElementById('vitalNotes').value,
    };

    // Save to localStorage (swap for Supabase insert when backend is ready)
    const existing = JSON.parse(localStorage.getItem('geneshield_vitals') || '[]');
    existing.unshift(entry);
    localStorage.setItem('geneshield_vitals', JSON.stringify(existing));

    // Append to history UI
    const historyList = document.getElementById('historyList');
    const newEntry = document.createElement('div');
    newEntry.className = 'history-entry';
    const bpStr = entry.bpSystolic && entry.bpDiastolic ? `${entry.bpSystolic}/${entry.bpDiastolic}` : '--';
    const bpClass = entry.bpSystolic > 130 ? 'high' : entry.bpSystolic > 120 ? 'warn' : 'ok';
    const glucClass = entry.glucose > 7 ? 'high' : entry.glucose > 5.5 ? 'warn' : 'ok';
    newEntry.innerHTML = `
      <div class="he-date">Just now</div>
      <div class="he-metrics">
        <div class="he-metric"><span class="he-label">BP</span><span class="he-val ${bpClass}">${bpStr}</span></div>
        <div class="he-metric"><span class="he-label">Glucose</span><span class="he-val ${glucClass}">${entry.glucose || '--'}</span></div>
        <div class="he-metric"><span class="he-label">HR</span><span class="he-val ok">${entry.heartRate || '--'}</span></div>
        <div class="he-metric"><span class="he-label">Weight</span><span class="he-val ok">${entry.weight || '--'}</span></div>
      </div>
      <span class="he-sym">${entry.symptoms.length ? entry.symptoms.join(', ') : 'No symptoms'}</span>
    `;
    historyList.insertBefore(newEntry, historyList.firstChild);

    // Toast
    if (toast) { toast.classList.add('show'); setTimeout(() => toast.classList.remove('show'), 3500); }

    // Reset form
    ['bpSystolic','bpDiastolic','glucose','heartRate','weight','temperature','oxygen'].forEach(id => {
      const el = document.getElementById(id); if (el) el.value = '';
    });
    document.querySelectorAll('.sym-item input').forEach(cb => cb.checked = false);
    document.getElementById('vitalNotes').value = '';
  });
}