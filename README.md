# README.md

## 🚀 Onboarding & Local Deployment Guide

Welcome to the team! Getting this powerful backend engine running locally on your computer is a seamless, automated process designed to take less than two minutes. Follow these simple tactical steps to boot up the system, protect your files, and fire up your local server:

### 📦 Phase 1: Creating Your Sandbox Workspace

Before we turn the engine on, we create a secure, isolated sandbox on your computer. This ensures our project ingredients never conflict with your other computer software.

1. **Clone the Project Blueprint**
   Bring the secure source code files from GitHub directly onto your local machine:

   ```bash
   git clone https://github.com
   cd poker-bankroll-analyzer
   ```

2. **Activate Your Private Workspace Vault (`venv`)**
   Spin up an isolated virtual environment sandbox. Think of this like a clean, dedicated kitchen counter where we can cook up this app without making a mess on the rest of your computer:

   ```bash
   # On macOS / Linux:
   python3 -m venv venv
   source venv/bin/activate
   ```

   _Visual Check: You will see `(venv)` appear at the front of your terminal line, showing your safe workspace is active!_

3. **Deploy the Verified Ingredient List**
   Download the exact version-pinned packages (like Flask and Dotenv) with a single command. No guesswork, no missing pieces:
   ```bash
   pip install -r requirements.txt
   ```

### ⚡ Phase 2: Ignition & Boot Up

4. **Synchronize Your Local Environment Safe**
   Duplicate the safe blueprint template to create your personal hidden vault for security keys:

   ```bash
   cp .env.example .env
   ```

   _Action Item: Open a brand-new `.env` file and type a strong, random password for your `JWT_SECRET` key!_

5. **Fire Up the Engine**
   Launch the live development server. This system is custom-configured to execute directly via the main switch script. It automatically routes onto port `5001` to prevent native Mac hardware streaming line conflicts, giving you a smooth, error-free boot experience:
   ```bash
   python app.py
   ```

_✨ Success Milestone: the server is now officially alive! Open your terminal split-screen or a browser and head over to `http://localhost:5001/api/status` to watch the live JSON dashboard salute you!_

## 🔒 Secure Configuration Dashboard

To safeguard user privacy and account data, this ecosystem keeps all security credentials, system passwords, and database connection paths completely locked away in a private local file vault named `.env`.

Think of this like the app's secret control center. It is strictly hidden from the public to guarantee absolute security.

To make setup effortless for new developers or team members, I included a public blueprint guide called `.env.example`. Here is what the control center powers behind the scenes:

### 🎛️ The Core Control Panel Keys

| Key Feature           | System Purpose             | Human Layman Meaning                                                                                                                                                                |
| :-------------------- | :------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 🛡️ **`JWT_SECRET`**   | Digital Security Passwords | The master digital key used to sign and encrypt your personal user login passes. This keeps your secure data strictly yours.                                                        |
| 📊 **`DATABASE_URL`** | Core Information Storage   | The cloud storage address for the main database engine. If this note is missing, the app activates a smart, risk-free local sandbox file (`dev.db`) on your computer automatically. |

### 🛠️ Turning on Your Control Center (1-Click Prep)

Ready to prime the engine? Just run this command in your computer's terminal to copy the template blueprint and spin up your personal local vault:

```bash
cp .env.example .env
```

_Next Step: Simply open your brand-new `.env` file and type in a random, strong secret password for your security keys!_

## 📐 Data Architecture & Evolutionary Blueprint Tracking

As the platform scales, its core information architecture naturally grows and evolves. To handle these expansions seamlessly—**without ever disrupting your live system or risking a single byte of your saved historical data**—this platform utilizes an automated synchronization engine powered by **Flask-Migrate**.

Think of this like an intelligent version-control system for our database tables. If our team introduces an exciting new tracking feature tomorrow (like adding game duration metrics), this engine acts as our Master Architect. It automatically scans the new updates and safely reshapes your local storage database behind the scenes so everything stays perfectly aligned in real-time.

### 🔄 The Synchronization Routine (Keeping The App in Harmony)

Whenever you pull down new product updates, or when we deploy cutting-edge features, running this simple command routine ensures your local data engine is in absolute harmony with the global master source code:

1. **Confirm Your Sandbox Is Engaged**
   Ensure your secure command center is turned on:

   ```bash
   source venv/bin/activate
   ```

2. **Execute the Structural Upgrade Switch**
   Run the master upgrade command. This instantly updates your local storage vault, molding it to support all the latest data tables and premium analytical fields with zero friction:
   ```bash
   flask db upgrade
   ```

### 🛠️ The Two-Step Innovation Dance (For Developers & Creators)

When it's time to build a new feature or expand our tracking metrics, your deployment pipeline remains beautifully simple and automated:

- **Step A: Draft the Structural Shift** (This automatically calculates what changed and writes a smart, risk-free update script):
  ```bash
  flask db migrate -m "Add new high-value tracking column to user sessions"
  ```
- **Step B: Apply the Innovation** (This physically locks the new design into your database file instantly):
  ```bash
  flask db upgrade
  ```
