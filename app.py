import os
import json
from datetime import datetime

from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
import mysql.connector
import bcrypt
import requests

# ML Engine import
try:
    from ml_engine import calculate_all_risks, calculate_hereditary_risk, init_models
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print('[WARNING] ml_engine not available — ML features disabled')

# ============================================
# CONFIG
# ============================================

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'geneshield-dev-secret-change-in-production')

CORS(app, supports_credentials=True)

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', '53704468mom'),
    'database': os.environ.get('DB_NAME', 'geneshield_db'),
}

CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY', '')
CLAUDE_MODEL = 'claude-sonnet-4-20250514'

# ============================================
# DATABASE HELPERS
# ============================================

def get_db():
    return mysql.connector.connect(**DB_CONFIG)


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            first_name VARCHAR(100),
            last_name VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_profiles (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT UNIQUE NOT NULL,
            first_name VARCHAR(100),
            last_name VARCHAR(100),
            dob DATE NULL,
            gender VARCHAR(50),
            phone VARCHAR(30),
            district VARCHAR(100),
            height FLOAT,
            weight FLOAT,
            blood_type VARCHAR(10),
            current_conditions JSON,
            medications TEXT,
            father_history JSON,
            mother_history JSON,
            grand_history JSON,
            exercise VARCHAR(50),
            diet VARCHAR(50),
            smoke VARCHAR(50),
            alcohol VARCHAR(50),
            sleep VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # New cancer-focused risk_scores table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS risk_scores (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            breast_cancer INT,
            cervical_cancer INT,
            prostate_cancer INT,
            colorectal_cancer INT,
            risk_details JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # Migration: add new columns if table existed with old schema
    migration_cols = [
        ('breast_cancer', 'INT'),
        ('cervical_cancer', 'INT'),
        ('prostate_cancer', 'INT'),
        ('colorectal_cancer', 'INT'),
        ('risk_details', 'JSON'),
    ]
    for col_name, col_type in migration_cols:
        try:
            cursor.execute(f'ALTER TABLE risk_scores ADD COLUMN {col_name} {col_type}')
        except mysql.connector.Error:
            pass  # Column already exists

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vitals_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            bp_systolic INT,
            bp_diastolic INT,
            glucose FLOAT,
            heart_rate INT,
            weight FLOAT,
            temperature FLOAT,
            oxygen FLOAT,
            symptoms JSON,
            notes TEXT,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS doctor_reports (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            report_content TEXT,
            status VARCHAR(50) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    conn.commit()
    cursor.close()
    conn.close()
    print('Database tables initialized.')


def get_user_id():
    return session.get('user_id')


# ============================================
# AUTH ROUTES
# ============================================

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    first_name = data.get('firstName', '').strip()
    last_name = data.get('lastName', '').strip()

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO users (email, password_hash, first_name, last_name) VALUES (%s, %s, %s, %s)',
            (email, password_hash, first_name, last_name)
        )
        conn.commit()
        user_id = cursor.lastrowid
        session['user_id'] = user_id
        session['email'] = email
        return jsonify({'message': 'Account created', 'user': {'id': user_id, 'email': email, 'first_name': first_name, 'last_name': last_name}}), 201
    except mysql.connector.IntegrityError:
        return jsonify({'error': 'An account with this email already exists'}), 409
    finally:
        cursor.close()
        conn.close()


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user or not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        return jsonify({'error': 'Invalid email or password'}), 401

    session['user_id'] = user['id']
    session['email'] = user['email']
    return jsonify({'message': 'Logged in', 'user': {'id': user['id'], 'email': user['email'], 'first_name': user['first_name'], 'last_name': user['last_name']}}), 200


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out'}), 200


@app.route('/api/me', methods=['GET'])
def me():
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT id, email, first_name, last_name, created_at FROM users WHERE id = %s', (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        session.clear()
        return jsonify({'error': 'User not found'}), 401

    if user.get('created_at'):
        user['created_at'] = user['created_at'].isoformat()

    return jsonify({'user': user}), 200


# ============================================
# PROFILE ROUTES
# ============================================

@app.route('/api/profile', methods=['POST'])
def save_profile():
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    dob = data.get('dob') or None

    conn = get_db()
    cursor = conn.cursor()

    # Check if profile exists
    cursor.execute('SELECT id FROM health_profiles WHERE user_id = %s', (user_id,))
    existing = cursor.fetchone()

    if existing:
        cursor.execute('''
            UPDATE health_profiles SET
                first_name=%s, last_name=%s, dob=%s, gender=%s, phone=%s, district=%s,
                height=%s, weight=%s, blood_type=%s, current_conditions=%s, medications=%s,
                father_history=%s, mother_history=%s, grand_history=%s,
                exercise=%s, diet=%s, smoke=%s, alcohol=%s, sleep=%s
            WHERE user_id=%s
        ''', (
            data.get('firstName'), data.get('lastName'), dob, data.get('gender'),
            data.get('phone'), data.get('district'),
            float(data['height']) if data.get('height') else None,
            float(data['weight']) if data.get('weight') else None,
            data.get('bloodType'),
            json.dumps(data.get('currentConditions', [])),
            data.get('medications'),
            json.dumps(data.get('fatherHistory', [])),
            json.dumps(data.get('motherHistory', [])),
            json.dumps(data.get('grandHistory', [])),
            data.get('exercise'), data.get('diet'), data.get('smoke'),
            data.get('alcohol'), data.get('sleep'),
            user_id
        ))
    else:
        cursor.execute('''
            INSERT INTO health_profiles
                (user_id, first_name, last_name, dob, gender, phone, district,
                 height, weight, blood_type, current_conditions, medications,
                 father_history, mother_history, grand_history,
                 exercise, diet, smoke, alcohol, sleep)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ''', (
            user_id,
            data.get('firstName'), data.get('lastName'), dob, data.get('gender'),
            data.get('phone'), data.get('district'),
            float(data['height']) if data.get('height') else None,
            float(data['weight']) if data.get('weight') else None,
            data.get('bloodType'),
            json.dumps(data.get('currentConditions', [])),
            data.get('medications'),
            json.dumps(data.get('fatherHistory', [])),
            json.dumps(data.get('motherHistory', [])),
            json.dumps(data.get('grandHistory', [])),
            data.get('exercise'), data.get('diet'), data.get('smoke'),
            data.get('alcohol'), data.get('sleep')
        ))

    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'message': 'Profile saved'}), 200


@app.route('/api/profile', methods=['GET'])
def get_profile():
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM health_profiles WHERE user_id = %s', (user_id,))
    profile = cursor.fetchone()
    cursor.close()
    conn.close()

    if not profile:
        return jsonify({'profile': None}), 200

    # Parse JSON fields
    for field in ['current_conditions', 'father_history', 'mother_history', 'grand_history', 'symptoms']:
        if field in profile and isinstance(profile[field], str):
            try:
                profile[field] = json.loads(profile[field])
            except (json.JSONDecodeError, TypeError):
                pass

    # Convert dates/datetimes to strings
    for key, val in profile.items():
        if isinstance(val, (datetime,)):
            profile[key] = val.isoformat()
        elif hasattr(val, 'isoformat'):
            profile[key] = val.isoformat()

    return jsonify({'profile': profile}), 200


# ============================================
# RISK SCORES ROUTES
# ============================================

@app.route('/api/risk-scores', methods=['POST'])
def save_risk_scores():
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    risk_details = data.get('details') or data.get('risk_details')

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO risk_scores
           (user_id, breast_cancer, cervical_cancer, prostate_cancer, colorectal_cancer, risk_details)
           VALUES (%s,%s,%s,%s,%s,%s)''',
        (
            user_id,
            data.get('breast_cancer'),
            data.get('cervical_cancer'),
            data.get('prostate_cancer'),
            data.get('colorectal_cancer'),
            json.dumps(risk_details) if risk_details else None,
        )
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'message': 'Risk scores saved'}), 201


@app.route('/api/risk-scores', methods=['GET'])
def get_risk_scores():
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        'SELECT * FROM risk_scores WHERE user_id = %s ORDER BY created_at DESC LIMIT 1',
        (user_id,)
    )
    scores = cursor.fetchone()
    cursor.close()
    conn.close()

    if scores:
        if scores.get('created_at'):
            scores['created_at'] = scores['created_at'].isoformat()
        # Parse risk_details JSON
        if scores.get('risk_details') and isinstance(scores['risk_details'], str):
            try:
                scores['risk_details'] = json.loads(scores['risk_details'])
            except (json.JSONDecodeError, TypeError):
                pass

    return jsonify({'scores': scores}), 200


# ============================================
# ML RISK CALCULATION ENDPOINT
# ============================================

@app.route('/api/calculate-risks', methods=['POST'])
def calculate_risks():
    """Run ML + hereditary risk calculation and save results."""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    if not ML_AVAILABLE:
        return jsonify({'error': 'ML engine not available'}), 503

    data = request.get_json()

    try:
        results = calculate_all_risks(data)
    except Exception as e:
        print(f'[ML] Risk calculation error: {e}')
        return jsonify({'error': 'Risk calculation failed'}), 500

    # Save to DB
    details = results.get('details')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO risk_scores
           (user_id, breast_cancer, cervical_cancer, prostate_cancer, colorectal_cancer, risk_details)
           VALUES (%s,%s,%s,%s,%s,%s)''',
        (
            user_id,
            results.get('breast_cancer'),
            results.get('cervical_cancer'),
            results.get('prostate_cancer'),
            results.get('colorectal_cancer'),
            json.dumps(details) if details else None,
        )
    )
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'scores': results}), 200


# ============================================
# VITALS ROUTES
# ============================================

@app.route('/api/vitals', methods=['POST'])
def save_vitals():
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO vitals_logs (user_id, bp_systolic, bp_diastolic, glucose, heart_rate, weight, temperature, oxygen, symptoms, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ''', (
        user_id,
        int(data['bpSystolic']) if data.get('bpSystolic') else None,
        int(data['bpDiastolic']) if data.get('bpDiastolic') else None,
        float(data['glucose']) if data.get('glucose') else None,
        int(data['heartRate']) if data.get('heartRate') else None,
        float(data['weight']) if data.get('weight') else None,
        float(data['temperature']) if data.get('temperature') else None,
        float(data['oxygen']) if data.get('oxygen') else None,
        json.dumps(data.get('symptoms', [])),
        data.get('notes', '')
    ))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'message': 'Vitals saved'}), 201


@app.route('/api/vitals', methods=['GET'])
def get_vitals():
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        'SELECT * FROM vitals_logs WHERE user_id = %s ORDER BY logged_at DESC LIMIT 20',
        (user_id,)
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    for row in rows:
        if isinstance(row.get('symptoms'), str):
            try:
                row['symptoms'] = json.loads(row['symptoms'])
            except (json.JSONDecodeError, TypeError):
                pass
        if row.get('logged_at'):
            row['logged_at'] = row['logged_at'].isoformat()

    return jsonify({'vitals': rows}), 200


# ============================================
# CHAT ROUTES
# ============================================

def build_system_prompt(user_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # Get profile
    cursor.execute('SELECT * FROM health_profiles WHERE user_id = %s', (user_id,))
    profile = cursor.fetchone() or {}

    # Parse JSON fields in profile
    for field in ['current_conditions', 'father_history', 'mother_history', 'grand_history']:
        if field in profile and isinstance(profile[field], str):
            try:
                profile[field] = json.loads(profile[field])
            except (json.JSONDecodeError, TypeError):
                profile[field] = []

    # Get latest risk scores
    cursor.execute('SELECT * FROM risk_scores WHERE user_id = %s ORDER BY created_at DESC LIMIT 1', (user_id,))
    scores = cursor.fetchone() or {}

    # Parse risk_details
    if scores.get('risk_details') and isinstance(scores['risk_details'], str):
        try:
            scores['risk_details'] = json.loads(scores['risk_details'])
        except (json.JSONDecodeError, TypeError):
            scores['risk_details'] = {}

    # Get last 5 vitals for trends
    cursor.execute('SELECT * FROM vitals_logs WHERE user_id = %s ORDER BY logged_at DESC LIMIT 5', (user_id,))
    vitals_rows = cursor.fetchall()

    cursor.close()
    conn.close()

    first_name = profile.get('first_name', 'User')
    last_name = profile.get('last_name', '')
    conditions = profile.get('current_conditions', [])
    if isinstance(conditions, str):
        try: conditions = json.loads(conditions)
        except: conditions = []

    father_h = profile.get('father_history', [])
    mother_h = profile.get('mother_history', [])
    grand_h = profile.get('grand_history', [])
    if isinstance(father_h, str):
        try: father_h = json.loads(father_h)
        except: father_h = []
    if isinstance(mother_h, str):
        try: mother_h = json.loads(mother_h)
        except: mother_h = []
    if isinstance(grand_h, str):
        try: grand_h = json.loads(grand_h)
        except: grand_h = []

    # Calculate BMI
    weight = float(profile.get('weight') or 0)
    height = float(profile.get('height') or 0)
    bmi_str = 'Unknown'
    if weight > 0 and height > 0:
        bmi = weight / ((height / 100) ** 2)
        bmi_str = f'{bmi:.1f}'

    def risk_label(val):
        if val is None:
            return 'Not assessed'
        if val >= 60:
            return f'{val}% (HIGH)'
        if val >= 40:
            return f'{val}% (MODERATE)'
        return f'{val}% (LOW)'

    # Vitals trends
    vitals_trend = 'No vitals logged yet.'
    if vitals_rows:
        latest = vitals_rows[0]
        bp = f"{latest.get('bp_systolic', '--')}/{latest.get('bp_diastolic', '--')} mmHg"
        readings = []
        for v in vitals_rows:
            if v.get('bp_systolic'):
                readings.append(f"  {v.get('logged_at', 'N/A')}: BP {v['bp_systolic']}/{v.get('bp_diastolic', '--')}, Glucose {v.get('glucose', '--')}, HR {v.get('heart_rate', '--')}")
        vitals_trend = f"Latest: BP {bp}, Glucose {latest.get('glucose', '--')} mmol/L, HR {latest.get('heart_rate', '--')} bpm, Weight {latest.get('weight', '--')} kg\n" + '\n'.join(readings[:5])

    # Risk details analysis
    risk_details = scores.get('risk_details', {})
    family_analysis = ''
    if isinstance(risk_details, dict) and risk_details.get('family_analysis'):
        fa = risk_details['family_analysis']
        for cancer, info in fa.items():
            if isinstance(info, dict):
                family_analysis += f"  - {cancer}: base {info.get('base_risk', '?')}%, family mult {info.get('family_multiplier', '?')}x ({info.get('family_source', 'unknown')}), combined mult {info.get('combined_multiplier', '?')}x\n"

    return f"""You are GeneShield AI, a caring and knowledgeable hereditary cancer risk companion for {first_name}.
You specialize in cancer prevention, genetic risk interpretation, and screening guidance.

USER PROFILE:
- Name: {first_name} {last_name}
- Gender: {profile.get('gender', 'Unknown')}
- District: {profile.get('district', 'Botswana')}
- BMI: {bmi_str}
- Current conditions: {', '.join(conditions) if conditions else 'None reported'}
- Medications: {profile.get('medications', 'None')}
- Exercise: {profile.get('exercise', 'Unknown')} | Diet: {profile.get('diet', 'Unknown')}
- Smoking: {profile.get('smoke', 'Unknown')} | Alcohol: {profile.get('alcohol', 'Unknown')}

FAMILY CANCER HISTORY:
- Father's side: {', '.join(father_h) if father_h else 'No cancer history reported'}
- Mother's side: {', '.join(mother_h) if mother_h else 'No cancer history reported'}
- Grandparents: {', '.join(grand_h) if grand_h else 'No cancer history reported'}

HEREDITARY CANCER RISK SCORES (ML + Epidemiological Analysis):
- Breast Cancer: {risk_label(scores.get('breast_cancer'))}
- Cervical Cancer: {risk_label(scores.get('cervical_cancer'))}
- Prostate Cancer: {risk_label(scores.get('prostate_cancer'))}
- Colorectal Cancer: {risk_label(scores.get('colorectal_cancer'))}

RISK FACTOR ANALYSIS:
{family_analysis if family_analysis else '  No detailed analysis available yet.'}

VITALS TRENDS (Last 5 readings):
{vitals_trend}

CANCER SCREENING GUIDELINES:
- Breast: Mammogram every 1-2 years from age 40 (or 10 years before youngest affected relative). BRCA testing if strong family history.
- Cervical: Pap smear every 3 years from age 21. HPV co-testing every 5 years from age 30. HPV vaccination if eligible.
- Prostate: PSA test discussion from age 50 (age 40 if family history or African descent).
- Colorectal: Colonoscopy every 10 years from age 45 (or age 40 if family history). Stool-based tests as alternative.

CONSULTATION MODE GUIDELINES:
- Be warm, encouraging, and conversational — not clinical or robotic
- Explain cancer risks in simple language, referencing their specific family history
- Give practical, actionable cancer prevention advice tailored to this user
- Recommend appropriate screening schedules based on their risk level and age
- Mention lifestyle modifications: diet (morogo, sorghum, vegetables), exercise, limiting alcohol
- Reference Botswana healthcare context: Princess Marina Hospital, local clinics, cancer screening programmes
- Remind them to consult a doctor or oncologist for serious concerns
- Keep responses concise (2-4 paragraphs max)
- NEVER diagnose — provide information and guidance only
- If asked about topics outside cancer/health, gently redirect to your area of expertise"""


@app.route('/api/chat/send', methods=['POST'])
def chat_send():
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    user_message = data.get('message', '').strip()
    if not user_message:
        return jsonify({'error': 'Message is required'}), 400

    conn = get_db()
    cursor = conn.cursor()

    # Save user message
    cursor.execute(
        'INSERT INTO chat_history (user_id, role, content) VALUES (%s, %s, %s)',
        (user_id, 'user', user_message)
    )
    conn.commit()

    # Get recent chat history for context
    cursor_dict = conn.cursor(dictionary=True)
    cursor_dict.execute(
        'SELECT role, content FROM chat_history WHERE user_id = %s ORDER BY created_at DESC LIMIT 20',
        (user_id,)
    )
    rows = cursor_dict.fetchall()
    cursor_dict.close()

    # Reverse to chronological order
    messages = list(reversed(rows))

    # Build system prompt from DB data
    system_prompt = build_system_prompt(user_id)

    # Call Claude API
    ai_reply = "I'm sorry, I couldn't process that right now. Please try again."
    if CLAUDE_API_KEY:
        try:
            resp = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers={
                    'Content-Type': 'application/json',
                    'x-api-key': CLAUDE_API_KEY,
                    'anthropic-version': '2023-06-01',
                },
                json={
                    'model': CLAUDE_MODEL,
                    'max_tokens': 1200,
                    'system': system_prompt,
                    'messages': [{'role': m['role'], 'content': m['content']} for m in messages],
                },
                timeout=30,
            )
            resp_data = resp.json()
            ai_reply = resp_data.get('content', [{}])[0].get('text', ai_reply)
        except Exception as e:
            print(f'Claude API error: {e}')
            ai_reply = "I'm having trouble connecting right now. Please try again shortly."
    else:
        ai_reply = "The AI service is not configured. Please set the CLAUDE_API_KEY environment variable."

    # Save assistant reply
    cursor.execute(
        'INSERT INTO chat_history (user_id, role, content) VALUES (%s, %s, %s)',
        (user_id, 'assistant', ai_reply)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'reply': ai_reply}), 200


@app.route('/api/chat/history', methods=['GET'])
def chat_history():
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        'SELECT role, content, created_at FROM chat_history WHERE user_id = %s ORDER BY created_at ASC LIMIT 50',
        (user_id,)
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    for row in rows:
        if row.get('created_at'):
            row['created_at'] = row['created_at'].isoformat()

    return jsonify({'history': rows}), 200


@app.route('/api/chat/history', methods=['DELETE'])
def clear_chat():
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM chat_history WHERE user_id = %s', (user_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'message': 'Chat history cleared'}), 200


# ============================================
# DOCTOR REPORTS ROUTES
# ============================================

@app.route('/api/reports', methods=['POST'])
def save_report():
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO doctor_reports (user_id, report_content, status) VALUES (%s, %s, %s)',
        (user_id, data.get('reportContent', ''), data.get('status', 'pending'))
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'message': 'Report saved'}), 201


@app.route('/api/reports', methods=['GET'])
def get_reports():
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        'SELECT * FROM doctor_reports WHERE user_id = %s ORDER BY created_at DESC',
        (user_id,)
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    for row in rows:
        if row.get('created_at'):
            row['created_at'] = row['created_at'].isoformat()

    return jsonify({'reports': rows}), 200


# ============================================
# SERVE STATIC FILES
# ============================================

@app.route('/')
def index():
    return send_from_directory('.', 'landing.html')


@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)


# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    init_db()
    if ML_AVAILABLE:
        init_models()
    app.run(debug=True, host='0.0.0.0', port=5000)
