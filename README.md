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

## 🤖 Provider LLM interchangeable (cloud / edge)

Le provider LLM (génération d'indices IA et correction d'essais) est **abstrait et pilotable par configuration**, sans changement de code :

- **Cloud** (défaut) : tout endpoint compatible avec l'API OpenAI — `base_url` configurable (OpenAI, OpenRouter, Mistral, vLLM, ...). Clé via `OPENAI_API_KEY`.
- **Edge** : **Ollama** en local (`http://localhost:11434`), modèle configurable (ex. `llama3.2:1b`).

La bascule se fait dans la base de données via `GET/PUT /api/admin/llm-settings` (rôle admin) :

```json
{ "provider": "ollama", "base_url": "http://localhost:11434", "model_name": "llama3.2:1b" }
```

À défaut de ligne en base, les valeurs par défaut viennent de l'environnement : `LLM_PROVIDER`, `LLM_BASE_URL` (ou `OPENAI_API_BASE`), `LLM_MODEL` (ou `OPENAI_MODEL`).

### Prérequis Ollama (mode edge)

1. Installer Ollama : [https://ollama.com](https://ollama.com) (Linux, macOS, Windows).
2. Télécharger le modèle : `ollama pull llama3.2:1b` (~1.3 Go) — ordre de grandeur comparable au benchmark QVAC/smart_notes.
3. Vérifier que le serveur répond : `curl http://localhost:11434`.

**Dimensionnement attendu (llama3.2:1b)** : ~1.3 Go disque, ~2-4 Go RAM libre recommandés, CPU seul suffisant (réponse en quelques secondes par requête). Pour de meilleures corrections d'essais, préférer `llama3.2:3b` ou `qwen2.5:7b` (~8 Go RAM) si la machine le permet.

### ⚠️ Warning qualité (correction d'essais — fonctionnalité payante)

Quand le provider actif est `ollama` (edge), l'API renvoie `"evaluation_warning": true` sur `POST /api/learning/exercises/<id>/submit` et un warning explicite est émis dans les logs. Le frontend doit afficher un avertissement de type *« évaluation générée par un modèle local, qualité non garantie équivalente au mode cloud »* tant qu'aucun benchmark de qualité n'a validé la parité.

### Divergence assumée avec smart_notes (choix documenté, pas un oubli)

smart_notes utilise le SDK **QVAC (Node)** pour l'IA. Ce repo (criticalMind) est **100 % Python/Flask** : le provider edge choisi est **Ollama** via son API HTTP locale, ce qui évite d'introduire un microservice Node + le workaround b4a rencontré sur smart_notes, et conserve une seule stack technique. La cohérence transversale QVAC est volontairement sacrifiée au profit de la cohérence interne au repo — choix assumé et traçable dans le code (`backend/src/services/llm_provider.py`).

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
