let currentStep = 1;
const totalSteps = 4;

function changeStep(direction) {
  const newStep = currentStep + direction;
  if (newStep < 1 || newStep > totalSteps) return;

  document.getElementById(`step-${currentStep}`).classList.remove('active');
  document.querySelector(`[data-step="${currentStep}"]`).classList.remove('active');
  document.querySelector(`[data-step="${currentStep}"]`).classList.add('done');

  const lines = document.querySelectorAll('.prog-line');
  if (direction > 0) {
    if (currentStep - 1 < lines.length) lines[currentStep - 1].classList.add('done');
  } else {
    if (currentStep - 2 >= 0) lines[currentStep - 2].classList.remove('done');
    document.querySelector(`[data-step="${currentStep}"]`).classList.remove('done');
  }

  currentStep = newStep;
  document.getElementById(`step-${currentStep}`).classList.add('active');
  const newProgStep = document.querySelector(`[data-step="${currentStep}"]`);
  newProgStep.classList.remove('done');
  newProgStep.classList.add('active');

  document.getElementById('progressFill').style.width = `${(currentStep / totalSteps) * 100}%`;
  document.getElementById('stepCounter').textContent = `Step ${currentStep} of ${totalSteps}`;
  document.getElementById('backBtn').disabled = currentStep === 1;

  const nextBtn = document.getElementById('nextBtn');
  if (currentStep === totalSteps) {
    nextBtn.innerHTML = `<i class='bx bx-check-circle'></i> Generate My Risk Score`;
    nextBtn.onclick = submitOnboarding;
  } else {
    nextBtn.innerHTML = `Next <i class='bx bx-right-arrow-alt'></i>`;
    nextBtn.onclick = () => changeStep(1);
  }

  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Option cards
document.querySelectorAll('.option-cards').forEach(group => {
  group.querySelectorAll('.option-card').forEach(card => {
    card.addEventListener('click', () => {
      group.querySelectorAll('.option-card').forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
    });
  });
});

// Toggle options
document.querySelectorAll('.toggle-options').forEach(group => {
  group.querySelectorAll('.toggle-opt').forEach(opt => {
    opt.addEventListener('click', () => {
      group.querySelectorAll('.toggle-opt').forEach(o => o.classList.remove('selected'));
      opt.classList.add('selected');
    });
  });
});

// None checkbox — deselects others in the same grid
const noneCheck = document.getElementById('noneCheck');
if (noneCheck) {
  noneCheck.addEventListener('change', () => {
    if (noneCheck.checked) {
      const grid = noneCheck.closest('.checkbox-grid');
      if (grid) {
        grid.querySelectorAll('input[type="checkbox"]').forEach(cb => {
          if (cb !== noneCheck) cb.checked = false;
        });
      }
    }
  });
}

document.getElementById('backBtn').disabled = true;

async function submitOnboarding() {
  // Collect all form data with cancer-specific field names
  const data = {
    firstName: document.getElementById('firstName').value,
    lastName: document.getElementById('lastName').value,
    dob: document.getElementById('dob').value,
    gender: document.getElementById('gender').value,
    phone: document.getElementById('phone').value,
    district: document.getElementById('district').value,
    height: document.getElementById('height').value,
    weight: document.getElementById('weight').value,
    bloodType: document.getElementById('bloodType').value,
    // Cancer-specific conditions from step 2
    currentConditions: [...document.querySelectorAll('#conditionsGrid input:checked')].map(i => i.value).filter(v => v !== 'none'),
    medications: document.getElementById('medications').value,
    // Cancer-specific family history from step 3
    fatherHistory: [...document.querySelectorAll('input[name="father"]:checked')].map(i => i.value).filter(v => v !== 'unknown'),
    motherHistory: [...document.querySelectorAll('input[name="mother"]:checked')].map(i => i.value).filter(v => v !== 'unknown'),
    grandHistory: [...document.querySelectorAll('input[name="grand"]:checked')].map(i => i.value).filter(v => v !== 'unknown'),
    // Lifestyle from step 4
    exercise: document.querySelector('#exerciseOptions .selected')?.dataset.value || '',
    diet: document.querySelector('#dietOptions .selected')?.dataset.value || '',
    smoke: document.querySelector('#smokeOptions .selected')?.dataset.value || '',
    alcohol: document.querySelector('#alcoholOptions .selected')?.dataset.value || '',
    sleep: document.querySelector('#sleepOptions .selected')?.dataset.value || '',
  };

  // Cache in localStorage
  localStorage.setItem('geneshield_profile', JSON.stringify(data));

  // Show loading overlay
  const overlay = document.createElement('div');
  overlay.className = 'ob-loading-overlay';
  overlay.innerHTML = `
    <div style="width:64px;height:64px;background:rgba(255,255,255,0.15);border-radius:16px;display:flex;align-items:center;justify-content:center;font-size:2rem;animation:spin 1s linear infinite;">
      <i class='bx bx-shield-plus' style="color:white;font-size:2rem;"></i>
    </div>
    <h2 style="font-size:1.4rem;font-weight:800;">Analysing your health profile...</h2>
    <p style="color:rgba(255,255,255,0.6);font-size:0.95rem;">Running your hereditary cancer risk assessment with ML engine</p>
    <style>@keyframes spin{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}</style>
  `;
  document.body.appendChild(overlay);

  try {
    // Save profile to Flask backend
    await saveProfile(data);

    // Calculate risks using ML engine (server-side), falls back to client-side
    const scores = await calculateMLRiskScores(data);

    // Cache scores in localStorage
    localStorage.setItem('geneshield_risk_scores', JSON.stringify(scores));
  } catch (err) {
    console.error('Onboarding save error:', err);
    // Even if server fails, try client-side fallback
    try {
      const fallbackScores = calculateRiskScores(data);
      localStorage.setItem('geneshield_risk_scores', JSON.stringify(fallbackScores));
      await saveRiskScores(fallbackScores);
    } catch (e2) {
      console.error('Fallback also failed:', e2);
    }
  }

  setTimeout(() => { window.location.href = 'dashboard.html'; }, 2500);
}
