-- ============================================
-- GeneShield — Supabase Database Schema
-- Run this in Supabase SQL Editor
-- ============================================

-- 1. HEALTH PROFILES (filled during onboarding)
-- current_conditions and *_history arrays now store cancer types
-- e.g. 'breast_cancer', 'cervical_cancer', 'colorectal_cancer', 'prostate_cancer', 'ovarian_cancer', 'lung_cancer', 'other_cancer'
CREATE TABLE IF NOT EXISTS health_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL UNIQUE,
    first_name TEXT,
    last_name TEXT,
    dob DATE,
    gender TEXT,
    phone TEXT,
    district TEXT,
    height NUMERIC,
    weight NUMERIC,
    blood_type TEXT,
    current_conditions TEXT[] DEFAULT '{}',
    medications TEXT,
    father_history TEXT[] DEFAULT '{}',
    mother_history TEXT[] DEFAULT '{}',
    grand_history TEXT[] DEFAULT '{}',
    exercise TEXT,
    diet TEXT,
    smoke TEXT,
    alcohol TEXT,
    sleep TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 2. RISK SCORES — Primary focus: Hereditary Cancer
-- NCDs (hypertension, diabetes, cardiovascular, kidney) are future scope
CREATE TABLE IF NOT EXISTS risk_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    breast INTEGER DEFAULT 0,        -- Breast cancer hereditary risk %
    cervical INTEGER DEFAULT 0,      -- Cervical cancer risk %
    colorectal INTEGER DEFAULT 0,    -- Colorectal cancer hereditary risk %
    prostate INTEGER DEFAULT 0,      -- Prostate cancer hereditary risk %
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 3. VITALS LOGS
CREATE TABLE IF NOT EXISTS vitals_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    bp_systolic INTEGER,
    bp_diastolic INTEGER,
    glucose NUMERIC,
    heart_rate INTEGER,
    weight NUMERIC,
    temperature NUMERIC,
    oxygen NUMERIC,
    symptoms TEXT[] DEFAULT '{}',
    notes TEXT,
    logged_at TIMESTAMPTZ DEFAULT now()
);

-- 4. CHAT HISTORY
CREATE TABLE IF NOT EXISTS chat_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 5. HEALTH NARRATIVES (AI-generated summary)
CREATE TABLE IF NOT EXISTS health_narratives (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    narrative TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 6. DOCTOR REPORTS
CREATE TABLE IF NOT EXISTS doctor_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    report_content TEXT NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'reviewed')),
    reviewed_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    reviewed_at TIMESTAMPTZ
);

-- ============================================
-- ROW LEVEL SECURITY
-- ============================================

ALTER TABLE health_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE vitals_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE health_narratives ENABLE ROW LEVEL SECURITY;
ALTER TABLE doctor_reports ENABLE ROW LEVEL SECURITY;

-- Users can CRUD their own data
CREATE POLICY "Users manage own profile" ON health_profiles FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users manage own risk scores" ON risk_scores FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users manage own vitals" ON vitals_logs FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users manage own chat" ON chat_history FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users manage own narratives" ON health_narratives FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users view own reports" ON doctor_reports FOR SELECT USING (auth.uid() = user_id);

-- Doctors can view all reports (for demo, allow all authenticated users to read reports)
CREATE POLICY "Doctors view all reports" ON doctor_reports FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Doctors update reports" ON doctor_reports FOR UPDATE USING (auth.role() = 'authenticated');
CREATE POLICY "Users create own reports" ON doctor_reports FOR INSERT WITH CHECK (auth.uid() = user_id);

-- ============================================
-- INDEXES
-- ============================================

CREATE INDEX IF NOT EXISTS idx_profiles_user ON health_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_vitals_user ON vitals_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_vitals_date ON vitals_logs(logged_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_history(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_date ON chat_history(created_at);
CREATE INDEX IF NOT EXISTS idx_reports_status ON doctor_reports(status);
