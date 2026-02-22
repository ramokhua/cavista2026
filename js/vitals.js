// ── DATE LABEL ──
const logDate = document.getElementById('logDate');
if (logDate) {
  logDate.textContent = new Date().toLocaleDateString('en-BW', { weekday: 'short', month: 'short', day: 'numeric' });
}

// ── LOAD VITALS HISTORY FROM API ──
async function loadVitalsHistory() {
  try {
    const vitals = await getVitalsHistory(20);
    const historyList = document.getElementById('historyList');
    if (!historyList) return;

    if (!vitals || vitals.length === 0) {
      historyList.innerHTML = '<p style="color:var(--gray);font-size:0.85rem;text-align:center;padding:20px;">No vitals logged yet.</p>';
      return;
    }

    historyList.innerHTML = '';
    // Update quick stats
    const totalLogsEl = document.getElementById('totalLogs');
    if (totalLogsEl) totalLogsEl.textContent = vitals.length;

    const lastLoggedEl = document.getElementById('lastLogged');
    if (lastLoggedEl && vitals[0].logged_at) {
      const d = new Date(vitals[0].logged_at);
      lastLoggedEl.textContent = d.toLocaleDateString('en-BW', { month: 'short', day: 'numeric' });
    }

    vitals.forEach(v => {
      const date = v.logged_at ? new Date(v.logged_at).toLocaleDateString('en-BW', { weekday: 'short', month: 'short', day: 'numeric' }) : 'Recently';
      const bpStr = v.bp_systolic && v.bp_diastolic ? `${v.bp_systolic}/${v.bp_diastolic}` : '--';
      const bpClass = v.bp_systolic > 130 ? 'high' : v.bp_systolic > 120 ? 'warn' : 'ok';
      const glucClass = v.glucose > 7 ? 'high' : v.glucose > 5.5 ? 'warn' : 'ok';

      const entry = document.createElement('div');
      entry.className = 'history-entry';
      entry.innerHTML = `
        <div class="he-date">${date}</div>
        <div class="he-metrics">
          <div class="he-metric"><span class="he-label">BP</span><span class="he-val ${bpClass}">${bpStr}</span></div>
          <div class="he-metric"><span class="he-label">Glucose</span><span class="he-val ${glucClass}">${v.glucose || '--'}</span></div>
          <div class="he-metric"><span class="he-label">HR</span><span class="he-val ok">${v.heart_rate || '--'}</span></div>
          <div class="he-metric"><span class="he-label">Weight</span><span class="he-val ok">${v.weight || '--'}</span></div>
        </div>
        <span class="he-sym">${v.symptoms && v.symptoms.length ? (Array.isArray(v.symptoms) ? v.symptoms.join(', ') : v.symptoms) : 'No symptoms'}</span>
      `;
      historyList.appendChild(entry);
    });
  } catch (err) {
    console.error('Failed to load vitals history:', err);
  }
}

// ── SAVE VITALS ──
const saveBtn = document.getElementById('saveVitals');
const toast = document.getElementById('toast');

if (saveBtn) {
  saveBtn.addEventListener('click', async () => {
    // Disable button to prevent double-clicks
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<i class="bx bx-loader-alt bx-spin"></i> Saving...';

    const entry = {
      bpSystolic: document.getElementById('bpSystolic').value || null,
      bpDiastolic: document.getElementById('bpDiastolic').value || null,
      glucose: document.getElementById('glucose').value || null,
      heartRate: document.getElementById('heartRate').value || null,
      weight: document.getElementById('weight').value || null,
      temperature: document.getElementById('temperature').value || null,
      oxygen: document.getElementById('oxygen')?.value || null,
      symptoms: [...document.querySelectorAll('.sym-item input:checked')].map(i => i.value),
      notes: document.getElementById('vitalNotes').value || '',
    };

    try {
      // Save to Flask backend
      const result = await saveVitals(entry);
      console.log('Vitals saved successfully:', result);

      // Toast
      if (toast) { toast.classList.add('show'); setTimeout(() => toast.classList.remove('show'), 3500); }

      // Reset form
      ['bpSystolic','bpDiastolic','glucose','heartRate','weight','temperature','oxygen'].forEach(id => {
        const el = document.getElementById(id); if (el) el.value = '';
      });
      document.querySelectorAll('.sym-item input').forEach(cb => cb.checked = false);
      document.getElementById('vitalNotes').value = '';

      // Reload history
      await loadVitalsHistory();

    } catch (err) {
      console.error('Failed to save vitals:', err);
      showToast('Failed to save vitals: ' + err.message, 'error');
    } finally {
      // Re-enable button
      saveBtn.disabled = false;
      saveBtn.innerHTML = '<i class="bx bx-save"></i> Save Today\'s Reading';
    }
  });
}

// ── INIT: load history after auth check completes ──
document.addEventListener('DOMContentLoaded', () => {
  // Small delay to let the auth check in vitals.html finish first
  setTimeout(() => loadVitalsHistory(), 500);
});
