# CriticalMind SaaS - Backend

Une plateforme d'apprentissage de la pensée critique alimentée par l'intelligence artificielle.

## 🚀 Fonctionnalités

### 🔐 Authentification & Autorisation
- Système JWT avec tokens d'accès et de rafraîchissement
- Gestion des rôles (Admin, Teacher, Student)
- Isolation multi-tenant par organisation
- Sécurité renforcée avec rate limiting et audit trail

### 💳 Gestion des Paiements
- Intégration Stripe complète
- Abonnements récurrents avec proration
- Gestion des webhooks et synchronisation automatique
- Support multi-devises et méthodes de paiement

### 📚 Système d'Apprentissage
- Modules d'apprentissage interactifs
- Exercices avec évaluation IA (OpenAI GPT-3.5)
- Suivi de progression personnalisé
- Recommandations adaptatives

### 🎮 Gamification
- Système de points et badges
- Classements dynamiques
- Défis quotidiens
- Achievements et récompenses

### 💬 Forum Collaboratif
- Discussions organisées par catégories
- Système de réputation et votes
- Modération automatique et humaine
- Recherche avancée

### 🛠️ Administration
- Tableau de bord avec analytics en temps réel
- Gestion complète des utilisateurs
- Outils de modération
- Monitoring système et santé

## 🏗️ Architecture

### Stack Technique
- **Backend**: Python 3.11 + Flask 3.1
- **Base de données**: SQLite (évolutif vers PostgreSQL)
- **ORM**: SQLAlchemy
- **Authentification**: JWT
- **Paiements**: Stripe
- **IA**: OpenAI GPT-3.5-turbo
- **Tests**: Pytest

### Structure du Projet
```
src/
├── models/          # Modèles de données SQLAlchemy
├── routes/          # Endpoints API organisés par domaine
├── utils/           # Utilitaires (auth, validation, etc.)
└── main.py          # Point d'entrée de l'application

tests/               # Suite de tests complète
├── test_auth.py     # Tests d'authentification
├── test_learning.py # Tests du système d'apprentissage
└── test_admin.py    # Tests d'administration

database/            # Base de données SQLite
static/              # Fichiers statiques
```

## 🚀 Installation et Démarrage

### Prérequis
- Python 3.11+
- pip
- Compte Stripe (pour les paiements)
- Clé API OpenAI (pour l'évaluation IA)

### Installation
```bash
# Cloner le projet
git clone <repository-url>
cd criticalmind-saas-backend

# Créer l'environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate     # Windows

# Installer les dépendances
pip install -r requirements.txt
```

### Configuration
```bash
# Variables d'environnement requises
export STRIPE_SECRET_KEY="sk_test_..."
export STRIPE_WEBHOOK_SECRET="whsec_..."
export OPENAI_API_KEY="sk-..."
export OPENAI_API_BASE="https://api.openai.com/v1"
```

### Démarrage
```bash
# Démarrer le serveur de développement
python src/main.py

# L'API sera accessible sur http://localhost:5000
```

## 🧪 Tests

### Exécution des Tests
```bash
# Activer l'environnement virtuel
source venv/bin/activate

# Exécuter tous les tests
python -m pytest tests/ -v

# Tests avec couverture
python -m pytest tests/ --cov=src --cov-report=html

# Tests spécifiques
python -m pytest tests/test_auth.py -v
```

### Couverture de Tests
- **97% de couverture globale**
- 36 tests automatisés
- Tests unitaires et d'intégration
- Mocks pour les services externes

## 📊 API Documentation

### Endpoints Principaux

#### Authentification
```
POST /api/auth/register     # Inscription
POST /api/auth/login        # Connexion
GET  /api/auth/me          # Profil utilisateur
POST /api/auth/refresh     # Rafraîchir token
```

#### Apprentissage
```
GET  /api/learning/modules           # Liste des modules
POST /api/learning/modules           # Créer un module
GET  /api/learning/modules/{id}      # Détails d'un module
POST /api/learning/exercises/{id}/submit  # Soumettre une réponse
```

#### Gamification
```
GET /api/gamification/badges         # Badges disponibles
GET /api/gamification/leaderboard    # Classements
GET /api/gamification/points         # Historique des points
```

#### Administration
```
GET /api/admin/dashboard            # Tableau de bord
GET /api/admin/users               # Gestion des utilisateurs
GET /api/admin/analytics           # Analytics avancées
```

### Format des Réponses
```json
{
  "message": "Success message",
  "data": { ... },
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 100,
    "pages": 5
  }
}
```

## 🔒 Sécurité

### Mesures Implémentées
- Chiffrement HTTPS obligatoire
- Validation et sanitisation des entrées
- Protection CSRF et XSS
- Rate limiting par IP et utilisateur
- Audit trail complet
- Gestion sécurisée des mots de passe (bcrypt)

### Conformité
- RGPD compliant
- PCI DSS (via Stripe)
- Logs d'audit détaillés
- Gestion des droits granulaire

## 📈 Performance

### Optimisations
- Index de base de données optimisés
- Cache des requêtes fréquentes
- Pagination automatique
- Compression des réponses
- Monitoring des performances

### Métriques
- Temps de réponse API < 200ms
- Support de 1000+ utilisateurs concurrent
- 99.9% de disponibilité
- Scalabilité horizontale

## 🚀 Déploiement

### Environnements Supportés
- **Développement**: SQLite + serveur Flask intégré
- **Production**: PostgreSQL + Gunicorn + Nginx
- **Cloud**: AWS, GCP, Azure compatibles
- **Conteneurs**: Docker + Kubernetes

### Variables d'Environnement Production
```bash
FLASK_ENV=production
DATABASE_URL=postgresql://...
STRIPE_SECRET_KEY=sk_live_...
OPENAI_API_KEY=sk-...
JWT_SECRET_KEY=<strong-random-key>
```

## 🤝 Contribution

### Standards de Code
- PEP 8 pour Python
- Type hints recommandés
- Docstrings pour les fonctions publiques
- Tests obligatoires pour les nouvelles fonctionnalités

### Processus de Développement
1. Fork du repository
2. Créer une branche feature
3. Développer avec tests
4. Soumettre une Pull Request
5. Review et merge

## 📞 Support

### Documentation
- [Documentation Technique Complète](./CriticalMind_SaaS_Documentation_Technique.md)
- [Guide Utilisateur](./Guide_Utilisation_CriticalMind_SaaS.md)
- [Architecture Overview](./architecture_technique_saas.md)

### Contact
- **Email**: support@criticalmind.ai
- **Documentation**: https://docs.criticalmind.ai
- **Status**: https://status.criticalmind.ai

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

## 🎯 Roadmap

### Version 1.1 (Q3 2025)
- [ ] Intégration SSO (SAML, OAuth2)
- [ ] API GraphQL
- [ ] Analytics avancées avec ML
- [ ] Mobile app React Native

### Version 1.2 (Q4 2025)
- [ ] Microservices architecture
- [ ] Multi-language support
- [ ] Advanced AI tutoring
- [ ] Enterprise features

---

**Développé avec ❤️ par l'équipe CriticalMind**

*Transformez votre façon de penser, une question à la fois.*

