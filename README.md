# 🧠 CriticalMind SaaS Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![React 18](https://img.shields.io/badge/react-18+-blue.svg)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/typescript-5.0+-blue.svg)](https://www.typescriptlang.org/)

A modern, production-ready SaaS platform designed to help users develop critical thinking and problem-solving skills through interactive learning modules, AI-powered guidance, and gamified experiences.

## ✨ Features

### 🎯 Core Learning Features
- **Interactive Learning Modules** - Engaging exercises and case studies
- **AI-Powered Guidance** - Personalized feedback and recommendations
- **Real-time Progress Tracking** - Detailed analytics and insights
- **Gamification System** - Badges, points, and achievements
- **Community Forum** - Discussion and collaboration space

### 🔧 Technical Features
- **Modern Tech Stack** - React 18, TypeScript, Flask, PostgreSQL
- **Mobile-First Design** - Responsive and touch-friendly interface
- **Progressive Web App** - Offline capabilities and native app experience
- **Real-time Updates** - WebSocket integration for live features
- **Secure Authentication** - JWT-based auth with refresh tokens
- **Payment Integration** - Stripe for subscription management
- **Docker Support** - Containerized deployment
- **Production Ready** - Security headers, rate limiting, monitoring

## 🏗️ Architecture

```
CriticalMind/
├── backend/                 # Flask API server
│   ├── src/
│   │   ├── models/         # Database models
│   │   ├── routes/         # API endpoints
│   │   ├── utils/          # Utilities and helpers
│   │   └── main.py         # Application entry point
│   ├── requirements.txt    # Python dependencies
│   └── Dockerfile         # Backend container
├── frontend/               # React TypeScript app
│   ├── src/
│   │   ├── components/     # Reusable UI components
│   │   ├── pages/          # Page components
│   │   ├── hooks/          # Custom React hooks
│   │   ├── store/          # State management (Zustand)
│   │   ├── api/            # API client and services
│   │   └── types/          # TypeScript definitions
│   ├── package.json        # Node.js dependencies
│   └── vite.config.ts      # Build configuration
├── documentation/          # Project documentation
├── docker-compose.yml      # Multi-container setup
└── .env.example           # Environment variables template
```

## 📚 Documentation

- [Technical Documentation](./documentation/CriticalMind_SaaS_Technical_Documentation.md) - Full system architecture, data model, security, and API reference
- [User Guide](./documentation/CriticalMind_SaaS_User_Guide.md) - Platform usage guide for end users
- [Architecture Overview](./documentation/CriticalMind_SaaS_Architecture.md) - Technical architecture and database schema
- [SaaS Research Report](./documentation/CriticalMind_SaaS_Research_Report.md) - Best practices for building a scalable and secure SaaS
- [App Overview](./documentation/CriticalMind_SaaS_App_Overview.md) - Original application concept and feature description

## 🚀 Quick Start

### Prerequisites
- **Node.js** 18+ and **pnpm**
- **Python** 3.11+
- **PostgreSQL** 15+ (or use Docker)
- **Redis** 7+ (for caching and sessions)

### Option 1: Docker Setup (Recommended)

1. **Clone the repository**
   ```bash
   git clone https://github.com/FrancKINANI/criticalMind.git
   cd criticalMind
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start with Docker Compose**
   ```bash
   docker-compose up -d
   ```

4. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:5000
   - API Documentation: http://localhost:5000/api

### Option 2: Manual Setup

#### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env
# Configure your .env file
python src/main.py
```

#### Frontend Setup
```bash
cd frontend
pnpm install
pnpm dev
```

## 🔧 Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/criticalmind_db

# Security
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-here

# Stripe (for payments)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...

# AI Services
OPENAI_API_KEY=your-openai-key
MISTRAL_API_KEY=your-mistral-key

# LLM provider (openai | ollama) — optional, defaults to openai
LLM_PROVIDER=openai
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-3.5-turbo

# Email
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
```

## 🤖 Interchangeable LLM Provider (cloud / edge)

The LLM provider (AI hint generation and essay grading) is **abstracted and configurable** without code changes:

- **Cloud** (default): any OpenAI API-compatible endpoint — configurable `base_url` (OpenAI, OpenRouter, Mistral, vLLM, ...). Key via `OPENAI_API_KEY`.
- **Edge**: **Ollama** locally (`http://localhost:11434`), configurable model (e.g., `llama3.2:1b`).

The switch is done in the database via `GET/PUT /api/admin/llm-settings` (admin role):

```json
{ "provider": "ollama", "base_url": "http://localhost:11434", "model_name": "llama3.2:1b" }
```

If no row exists in the database, default values come from environment: `LLM_PROVIDER`, `LLM_BASE_URL` (or `OPENAI_API_BASE`), `LLM_MODEL` (or `OPENAI_MODEL`).

### Ollama Prerequisites (edge mode)

1. Install Ollama: [https://ollama.com](https://ollama.com) (Linux, macOS, Windows).
2. Download the model: `ollama pull llama3.2:1b` (~1.3 GB) — comparable to QVAC/smart_notes benchmark.
3. Verify the server responds: `curl http://localhost:11434`.

**Expected sizing (llama3.2:1b)**: ~1.3 GB disk, ~2-4 GB free RAM recommended, CPU sufficient (response in a few seconds per request). For better essay grading, prefer `llama3.2:3b` or `qwen2.5:7b` (~8 GB RAM) if the machine allows.

### ⚠️ Quality Warning (essay grading — paid feature)

When the active provider is `ollama` (edge), the API returns `"evaluation_warning": true` on `POST /api/learning/exercises/<id>/submit` and an explicit warning is issued in the logs. The frontend should display a warning like *"evaluation generated by a local model, quality not guaranteed equivalent to cloud mode"* until a quality benchmark validates parity.

### Documented Divergence from smart_notes (intentional choice, not an oversight)

smart_notes uses the **QVAC (Node)** SDK for AI. This repo (criticalMind) is **100% Python/Flask**: the chosen edge provider is **Ollama** via its local HTTP API, which avoids introducing a Node microservice + the b4a workaround encountered in smart_notes, and maintains a single tech stack. QVAC cross-repo consistency is intentionally sacrificed for internal repo consistency — intentional and traceable choice in the code (`backend/src/services/llm_provider.py`).

## 📱 Mobile & PWA Support

The application is built with mobile-first principles:

- **Responsive Design** - Optimized for all screen sizes
- **Touch-Friendly** - 44px minimum touch targets
- **Progressive Web App** - Install on mobile devices
- **Offline Support** - Core features work offline
- **Push Notifications** - Real-time updates

## 🔒 Security Features

- **Authentication** - JWT with refresh tokens
- **Authorization** - Role-based access control
- **Rate Limiting** - API endpoint protection
- **Security Headers** - CSRF, XSS, and clickjacking protection
- **Input Validation** - Comprehensive data sanitization
- **SQL Injection Protection** - Parameterized queries
- **HTTPS Enforcement** - Secure communication

## 🧪 Testing

### Backend Tests
```bash
cd backend
pytest
pytest --cov=src  # With coverage
```

### Frontend Tests
```bash
cd frontend
pnpm test
pnpm test:coverage
pnpm e2e  # End-to-end tests
```

## 📦 Deployment

### Production Docker
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Manual Production Deployment
1. **Build frontend**
   ```bash
   cd frontend
   pnpm build
   ```

2. **Deploy backend**
   ```bash
   cd backend
   gunicorn --bind 0.0.0.0:5000 src.main:app
   ```

## 🤝 Contributing

We welcome contributions! Please see our [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute to CriticalMind.

- [Report a bug](https://github.com/FrancKINANI/criticalMind/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/FrancKINANI/criticalMind/issues/new?template=feature_request.md)
- [Submit a pull request](https://github.com/FrancKINANI/criticalMind/pulls)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **React Team** - For the amazing frontend framework
- **Flask Team** - For the lightweight and powerful backend framework
- **Tailwind CSS** - For the utility-first CSS framework
- **Stripe** - For payment processing
- **OpenAI** - For AI capabilities

## 📞 Support

For support, email support@criticalmind.app or join our [Discord community](https://discord.gg/criticalmind).

---

**Made with ❤️ by the CriticalMind Team**
