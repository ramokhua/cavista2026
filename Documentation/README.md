# 🧬 GeneShield
### *Protecting Generations. Predicting Risk. Empowering Health.*

> **Cavista Hackathon 2026 — Botswana Edition**  
> Botswana Accountancy College (BAC) | February 21–22, 2026  
> Theme A: AI-Driven Preventive Health Companion

---

## 📌 Overview

GeneShield is an AI-powered **hereditary cancer risk and prevention platform** built for Botswana and the broader Southern African region. It combines a generational cancer risk engine, a symptom and wellness monitoring interface, and an AI-powered cancer companion chatbot — all designed to shift cancer care from reactive treatment to proactive prevention.

Botswana faces a mounting cancer crisis: **70% of cancers are diagnosed at advanced stages**, cervical cancer is the leading cancer in women, and genetic susceptibility is poorly understood and almost never assessed at the population level. GeneShield closes this gap.

---

## 🎯 The Problem

- **Cervical cancer** is the #1 cancer in Botswana women (19.6% of all new cases — GLOBOCAN 2022)
- **Breast cancer** is the #2 cancer in women; 64.7% of patients present at advanced stage
- **70%** of all cancers in Botswana are diagnosed at Stage III or IV (National Cancer Registry)
- **1 in 4 cancers** globally has a hereditary component — yet genetic risk assessment is virtually non-existent in Botswana
- Cancer incidence is **projected to nearly double** from 1,953 (2018) to 3,760 by 2040
- There is **no consumer-facing tool** to help Batswana assess their hereditary cancer risk

GeneShield is built to address this gap — before the diagnosis, not after.

---

## ✨ Core Features

### 🔬 1. Hereditary Cancer Risk Engine
- Collects personal health data and **multi-generational family cancer history** at onboarding
- Runs a **Logistic Regression model** (trained on open-source health datasets) to generate personalised risk scores for:
  - **Breast Cancer** (BRCA1/BRCA2 family weighting, maternal/paternal line differentiation)
  - **Cervical Cancer** (HPV risk factors, screening history)
  - **Colorectal Cancer** (polyp history, diet, lifestyle modifiers)
  - **Prostate Cancer** (age, family history, gender-gated — males only)
- Risk scores bucketed into **Low / Moderate / High** tiers with visual dashboard display
- Claude API generates a **personalised health narrative** from the risk output

### 📊 2. Symptom & Wellness Monitoring
- Mobile-friendly interface for regularly logging **cancer early-warning symptoms**:
  - Unexplained lump or mass
  - Unexplained weight loss
  - Abnormal bleeding
  - Persistent cough
  - Bowel changes
  - Night sweats
  - Fatigue
- Tracks vitals: blood pressure, heart rate, blood glucose, BMI/weight
- Stores all logs in **Supabase** with timestamping
- AI monitors for **threshold breaches and pattern changes**

### 🤖 3. AI Cancer Companion (Chatbot)
- Powered by the **Claude API (Anthropic)**
- Persistent **conversation history stored in Supabase** — the companion remembers you
- Contextual Q&A based on the user's specific risk profile, logged symptoms, and family history
- Covers:
  - BRCA1/BRCA2 testing guidance
  - Mammogram and Pap smear scheduling
  - Early warning sign identification
  - Screening programme information
  - When to escalate to a clinician
- Proactive check-ins and logging reminders

### 👩‍⚕️ 4. Clinician Dashboard *(in scope)*
- Summarised view of flagged high-risk patients
- Enables clinicians to prioritise outreach and follow-up

---

## 🏗️ Technical Architecture

### Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | HTML, CSS, JavaScript (Vanilla) |
| **Database & Auth** | Supabase (PostgreSQL + Auth + Realtime) |
| **AI / LLM** | Claude API (Anthropic) — companion & risk narrative |
| **ML Model** | Logistic Regression, served via TensorFlow.js |
| **Hosting** | Vercel |

### System Workflow

```
User Registration & Login (Supabase Auth)
        ↓
Onboarding: Personal Profile + Family Cancer History
        ↓
Logistic Regression Model → Cancer Risk Scores
        ↓
Claude API → Personalised Health Narrative
        ↓
Dashboard: Risk Tiers, Trends, Recommendations
        ↓
Regular Symptom & Vitals Logging
        ↓
AI Monitors for Threshold Breaches / Pattern Changes
        ↓
AI Companion Chatbot ← → User (persistent history)
        ↓
Clinician View: Flagged High-Risk Users
```

### Data Architecture (Supabase)

```
users              — Auth profile, personal details
health_profiles    — vitals, conditions, family cancer history
risk_scores        — breast | cervical | colorectal | prostate (per user, timestamped)
vitals_logs        — ongoing symptom & monitoring entries
chat_history       — full conversation records per user (linked to user ID)
```

---

## 📁 Project Structure

```
geneshield/
├── index.html          # Landing page (cancer-focused hero, stats, features)
├── login.html          # User login
├── sign_up.html        # User registration
├── onboarding.html     # Health profile + family cancer history collection
├── dashboard.html      # Hereditary Cancer Risk Assessment dashboard
├── chat.html           # AI Cancer Companion chatbot interface
├── vitals.html         # Symptom & vitals logging page
├── main.js             # Core application logic
├── chat.js             # Chatbot logic + Claude API integration (cancer system prompt)
├── cdashboard.js       # Dashboard rendering + risk visualisation
├── onboarding.js       # Onboarding flow + risk score calculation trigger
├── vitals.js           # Vitals/symptom logging logic
└── README.md           # This file
```

---

## 🧬 Cancer Risk Engine — Detail

### Risk Factors Assessed

**Breast Cancer**
- First-degree relatives (mother, sisters) with breast/ovarian cancer
- Paternal line BRCA carriers (father's mother/sisters)
- BRCA1/BRCA2 family history (high-weight factor)
- Age, BMI, alcohol use, hormone factors

**Cervical Cancer** *(females only)*
- HPV exposure / vaccination status
- Screening history (last Pap smear)
- Smoking status
- HIV status (HIV+ significantly elevates cervical cancer risk in Botswana)

**Colorectal Cancer**
- Family history of colorectal cancer or polyps
- Red/processed meat consumption
- Physical activity level
- BMI, alcohol use, fibre intake

**Prostate Cancer** *(males only)*
- First-degree male relatives with prostate cancer
- Age (risk rises sharply after 50)
- Diet and lifestyle modifiers

### Modifiers Applied
- **Smoking**: +15% base risk modifier across all cancer types
- **Alcohol**: +10% modifier (breast and colorectal)
- **High BMI (>30)**: +10% modifier
- **Poor diet quality**: +8% modifier
- **Physical inactivity**: +5% modifier
- **Gender gating**: Cervical cancer excluded for males; Prostate cancer excluded for females

---

## 🚀 Getting Started

### Prerequisites
- Supabase project (free tier sufficient for hackathon)
- Anthropic Claude API key
- Vercel account (for deployment)
- Modern web browser

### Environment Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-team/geneshield.git
   cd geneshield
   ```

2. **Configure Supabase**
   - Create a new Supabase project
   - Run the schema SQL (see `supabase-schema.sql`)
   - Copy your `SUPABASE_URL` and `SUPABASE_ANON_KEY`

3. **Configure the Claude API**
   - Add your `ANTHROPIC_API_KEY` to your environment or Vercel project settings

4. **Deploy to Vercel**
   ```bash
   vercel deploy
   ```
   Or connect your GitHub repo to Vercel for automatic deploys.

5. **Local Development**
   ```bash
   # Serve locally (e.g. using VS Code Live Server or Python)
   python3 -m http.server 8080
   # Then visit http://localhost:8080
   ```

### Database Schema

Run `supabase-schema.sql` in your Supabase SQL editor. Key table: `risk_scores` contains columns for `breast`, `cervical`, `colorectal`, and `prostate` risk outputs.

---

## 🗺️ Roadmap

| Phase | Milestone |
|-------|-----------|
| **Now (v1.0)** | Core platform: cancer risk engine, symptom logging, AI chatbot, clinician view |
| **v1.1** | SMS-based companion for feature phone users in rural Botswana |
| **v1.2** | Integration with Botswana Ministry of Health cancer registry data |
| **v2.0** | Wearable device connectivity (glucometers, smart wearables) |
| **v2.1** | Expand to additional hereditary conditions: sickle cell, ovarian cancer |
| **v3.0** | Regional expansion: Zimbabwe, Zambia, South Africa |
| **Future** | NCD risk module (cardiovascular, diabetes, hypertension) — originally scoped as v1 |

---

## 👥 Team

| Name | Role | Responsibilities |
|------|------|-----------------|
| **Boitsholo** | Full Stack Developer & PM | Frontend lead, backend support, AI integration, project management |
| **Jemima** | Backend Engineer & Pitch Presenter | Backend architecture, AI/LLM integration, final presentation |
| **Abigail** | Full Stack Developer | Presentation slides, frontend support, fullstack tasks |
| **Atlang** | Frontend Engineer & UI/UX Designer | UI/UX design, frontend implementation, user experience |

---

## 📚 Data Sources & References

- **GLOBOCAN 2022** — Botswana cancer incidence & mortality (IARC, 2024)
- **Botswana National Cancer Registry** — Historical cancer trends
- **PMC / NCBI** — Advanced-stage presentation studies (Princess Marina Hospital cohort)
- **NCI** — BRCA1/BRCA2 risk statistics
- **ASCO Global Oncology** — Hereditary breast cancer in sub-Saharan Africa
- **MDPI Cancers (2025)** — Trends in cancer incidence in Botswana, 1990–2021

---

## ⚖️ Scope Clarification

**In Scope (v1.0):**
- Hereditary cancer risk engine (Breast, Cervical, Colorectal, Prostate)
- Symptom & vitals logging
- AI Cancer Companion (Claude API)
- Clinician dashboard
- Supabase Auth + data persistence

**Out of Scope (Future Roadmap):**
- NCD risk prediction (cardiovascular disease, Type 2 diabetes, hypertension, kidney disease)
- Wearable device integration
- Native mobile app
- Real-time national health records integration
- Prescription/medication management

---

## 📄 License

Built for the Cavista Hackathon 2026. All rights reserved by Team GeneShield.

---

*GeneShield — Protecting Generations. Predicting Risk. Empowering Health.*
