# Trading Maven

Trading Maven is an institutional-grade desktop trading application built with a modern tech stack centered on performance, security, and scalability.

## 🚀 Tech Stack

- **Backend**: FastAPI (Python) - High-performance asynchronous API.
- **Frontend**: React + Vite (Modern UI/UX with a premium institutional look).
- **Database**: SQLite (ORM via SQLAlchemy) - Reliable local data management.
- **Authentication**: JWT-based secure auth with password hashing.

## 📁 Project Structure

### Backend (`/backend`)
- **`routers/`**: Centralized API endpoints (Auth, Broker management, etc.).
- **`auth/`**: Authentication schemas and security utilities.
- **`database/`**: SQL models and session handling.
- **`broker/`**: Independent broker integrations (Angel One, etc.).
- **`strategy/`**: Core trading logic and signal generation.

### Frontend (`/frontend`)
- **Premium UI**: Dark-themed, institutional dashboard with a focus on responsiveness.
- **Modular Components**: Clean architecture for fast development.

## 🛠️ Setup Instructions

### Backend
1. Go to the backend directory: `cd backend`
2. Create virtual environment: `python -m venv venv`
3. Activate venv: `.\venv\Scripts\activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Run the server: `python main.py`

### Frontend
1. Go to the frontend directory: `cd frontend`
2. Install dependencies: `npm install`
3. Start the app: `npm run dev`

## 🔒 Security & Monetization
The app is built with monetization in mind, featuring:
- Secure JWT authentication.
- Premium feature toggles (Pro/Premium badges).
- Modular architecture for easy feature expansion.

---
*Developed by Rahul Edward*
