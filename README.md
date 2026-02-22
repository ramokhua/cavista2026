# GeneShield - Hereditary Cancer Risk Assessment & Prevention Platform

GeneShield is an AI-powered healthcare application that helps users understand their hereditary cancer risks through ML-based prediction, Bayesian hereditary risk calculation from family history, a personalized medical chatbot, and vital signs tracking.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Database Setup (MySQL)](#database-setup-mysql)
4. [Configuration](#configuration)
5. [Running the Application](#running-the-application)
6. [Accessing the App](#accessing-the-app)
7. [Demo Credentials](#demo-credentials)
8. [Troubleshooting](#troubleshooting)
9. [Project Structure](#project-structure)

---

## Prerequisites

Make sure the following are installed on your machine before proceeding:

| Requirement | Version | Download Link |
|---|---|---|
| **Python** | 3.8 or higher | https://www.python.org/downloads/ |
| **MySQL Server** | 5.7 or higher | https://dev.mysql.com/downloads/installer/ |
| **MySQL Workbench** (optional) | Any | https://dev.mysql.com/downloads/workbench/ |
| **pip** | Comes with Python | Included with Python installer |

> **Tip:** When installing Python, check the box **"Add Python to PATH"** during setup.

---

## Installation

### 1. Clone or Extract the Project

Place the project folder anywhere on your system. Open a terminal/command prompt and navigate into the project directory:

```bash
cd path/to/Cavista-Hackerthon-main
```

### 2. Install Python Dependencies

Run the following command from inside the project folder:

```bash
pip install -r requirements.txt
```

This installs:
- **Flask** - Web server framework
- **flask-cors** - Cross-origin request handling
- **mysql-connector-python** - MySQL database driver
- **bcrypt** - Password hashing
- **scikit-learn** - Machine learning models
- **pandas** - Data processing
- **numpy** - Numerical computing
- **joblib** - Model caching

> If you encounter permission errors, try: `pip install --user -r requirements.txt`

---

## Database Setup (MySQL)

The application uses MySQL as its database. You need to create the database before running the app. The tables are created automatically on first run.

### Option A: Using MySQL Workbench

1. Open **MySQL Workbench**
2. Connect to your local MySQL server (usually `localhost`, port `3306`)
3. Enter your **root password** (the one you set during MySQL installation)
4. Click the **"Create New Schema"** icon (cylinder icon) or go to the menu and run:
   ```sql
   CREATE DATABASE geneshield_db;
   ```
5. Click **Apply** and then **Finish**

### Option B: Using MySQL Command Line

```bash
mysql -u root -p
```

Enter your MySQL root password when prompted, then run:

```sql
CREATE DATABASE geneshield_db;
EXIT;
```

> **Important:** You only need to create the database. All tables (users, health_profiles, risk_scores, vitals_logs, chat_history, doctor_reports) are created automatically when the app starts.

---

## Configuration

The app reads database credentials from **environment variables**. If none are set, it falls back to the defaults in the code. You will likely need to change the password to match your own MySQL setup.

### What You Might Need to Change

| Setting | Default Value | Description |
|---|---|---|
| `DB_HOST` | `localhost` | MySQL server address |
| `DB_USER` | `root` | MySQL username |
| `DB_PASSWORD` | `53704468mom` | MySQL password |
| `DB_NAME` | `geneshield_db` | Database name |

### How to Set Your MySQL Password

**You must update the password to match your MySQL root password.** Choose one of the methods below:

#### Method 1: Edit `app.py` Directly (Simplest)

Open `app.py` and find this block near the top (around line 35):

```python
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', '53704468mom'),
    'database': os.environ.get('DB_NAME', 'geneshield_db'),
}
```

Replace `53704468mom` with **your MySQL root password**. For example, if your password is `mypassword123`:

```python
    'password': os.environ.get('DB_PASSWORD', 'mypassword123'),
```

If you named your database something other than `geneshield_db`, change that too.

#### Method 2: Set Environment Variables (No Code Changes)

**Windows (Command Prompt):**
```cmd
set DB_PASSWORD=your_mysql_password
set DB_NAME=geneshield_db
```

**Windows (PowerShell):**
```powershell
$env:DB_PASSWORD = "your_mysql_password"
$env:DB_NAME = "geneshield_db"
```

**macOS / Linux:**
```bash
export DB_PASSWORD=your_mysql_password
export DB_NAME=geneshield_db
```

> **Note:** Environment variables only last for the current terminal session. You need to set them each time you open a new terminal, or edit `app.py` directly for a permanent change.

---

## Running the Application

Once dependencies are installed, the database is created, and the password is configured:

```bash
python app.py
```

### What Happens on Startup

1. **Database tables** are automatically created if they don't exist
2. **ML models** (cervical & prostate cancer) are trained/loaded (may take a moment on first run)
3. **Chatbot engine** loads the medical Q&A dataset (first run may take longer as it builds the TF-IDF index)
4. **Flask server** starts on port 5000

You should see output similar to:

```
[DB] Tables initialized
[ML] Models loaded successfully
[Chatbot] Initializing medical chatbot engine...
[Chatbot] Engine ready
 * Running on http://0.0.0.0:5000
```

> **First-run note:** The chatbot loads a large dataset (~267MB CSV) and builds a TF-IDF index. This may take 1-2 minutes on the first run. Subsequent runs use cached models and start much faster.

---

## Accessing the App

Open your web browser and navigate to:

```
http://localhost:5000/
```

This loads the landing page. From there you can sign up, log in, and explore the application.

### Key Pages

| URL | Page |
|---|---|
| `http://localhost:5000/` | Landing page |
| `http://localhost:5000/login.html` | Login |
| `http://localhost:5000/signup.html` | Sign up |
| `http://localhost:5000/onboarding.html` | Health profile wizard |
| `http://localhost:5000/dashboard.html` | Main dashboard |
| `http://localhost:5000/chat.html` | AI medical chatbot |
| `http://localhost:5000/vitals.html` | Vitals tracking |

---

## Demo Credentials

To quickly test the app without signing up:

- **Email:** `demo@example.com`
- **Password:** `password`

You can also sign up with any email address to create a new account.

---

## Troubleshooting

### "Access denied for user 'root'@'localhost'"

Your MySQL password doesn't match what's in the app. Update the password in `app.py` (see [Configuration](#configuration)).

### "Can't connect to MySQL server on 'localhost'"

- Make sure MySQL Server is **running**
- On Windows: Open **Services** (search "Services" in Start), find **MySQL**, and make sure it's **Started**
- On macOS: Run `brew services start mysql` or start MySQL from System Preferences
- On Linux: Run `sudo systemctl start mysql`

### "Unknown database 'geneshield_db'"

You haven't created the database yet. Follow the [Database Setup](#database-setup-mysql) steps.

### "ModuleNotFoundError: No module named 'flask'"

Dependencies aren't installed. Run:
```bash
pip install -r requirements.txt
```

### "Port 5000 already in use"

Another process is using port 5000. Either stop that process or change the port in `app.py` at the bottom:
```python
app.run(debug=True, host='0.0.0.0', port=5001)  # Changed to 5001
```
Then access the app at `http://localhost:5001/`.

### ML or Chatbot features not working

These are optional and the app runs without them. If you see warnings like `[WARNING] ml_engine not available`, make sure `scikit-learn`, `pandas`, and `numpy` are installed:
```bash
pip install scikit-learn pandas numpy joblib
```

### Chatbot is slow on first run

This is normal. The chatbot builds a TF-IDF index from ~257,000 medical Q&A pairs on first startup. After that, it caches the model and starts faster.

---

## Project Structure

```
Cavista-Hackerthon-main/
|
|-- app.py                  # Flask backend (API routes, database, auth)
|-- ml_engine.py            # ML models & hereditary risk calculator
|-- chatbot_engine.py       # TF-IDF medical chatbot engine
|-- requirements.txt        # Python dependencies
|-- ai-medical-chatbot.csv  # Medical Q&A dataset (267MB)
|
|-- css/
|   |-- style.css           # Landing page styles
|   |-- dashboard.css       # Dashboard & layout styles
|   |-- chat.css            # Chat interface styles
|   |-- onboarding.css      # Onboarding form styles
|   |-- vitals.css          # Vitals page styles
|
|-- js/
|   |-- api.js              # Frontend API client
|   |-- main.js             # Landing page scripts
|   |-- dashboard.js        # Dashboard interactions
|   |-- onboarding.js       # Multi-step form logic
|   |-- chat.js             # Chat UI logic
|   |-- vitals.js           # Vitals form handling
|
|-- landing.html            # Landing page
|-- index.html              # Main features page
|-- login.html              # Login page
|-- signup.html             # Registration page
|-- onboarding.html         # Health profile wizard (4 steps)
|-- dashboard.html          # Risk assessment dashboard
|-- chat.html               # AI chatbot interface
|-- vitals.html             # Vitals logging page
|
|-- models/                 # Auto-generated ML model cache (created at runtime)
|-- data/                   # Dataset directory
```

---

## Quick Start Summary

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create the MySQL database
#    (via MySQL Workbench or command line)
#    CREATE DATABASE geneshield_db;

# 3. Update the MySQL password in app.py (line 38)
#    Change '53704468mom' to your MySQL root password

# 4. Run the app
python app.py

# 5. Open browser
#    http://localhost:5000/
```
