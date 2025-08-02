# Architecture Technique et Schéma de Base de Données pour CriticalMind SaaS

## Introduction

Ce document présente l'architecture technique complète pour transformer CriticalMind en une solution SaaS robuste et scalable. L'architecture proposée suit les meilleures pratiques de l'industrie pour assurer la sécurité, la performance et la scalabilité nécessaires pour un SaaS d'un million de dollars.

## 1. Vue d'ensemble de l'Architecture

### Architecture Microservices

L'application CriticalMind SaaS sera construite selon une architecture microservices modulaire, permettant une scalabilité horizontale et une maintenance simplifiée. Cette approche offre plusieurs avantages :

- **Isolation des services** : Chaque service peut être développé, déployé et mis à l'échelle indépendamment
- **Résilience** : La défaillance d'un service n'affecte pas l'ensemble du système
- **Technologie diverse** : Possibilité d'utiliser différentes technologies selon les besoins spécifiques de chaque service
- **Équipes autonomes** : Les équipes peuvent travailler sur différents services en parallèle

### Services Principaux

L'architecture comprendra les services suivants :

1. **Service d'Authentification** : Gestion des utilisateurs, authentification et autorisation
2. **Service de Gestion des Contenus** : Modules d'apprentissage, exercices et ressources pédagogiques
3. **Service de Gamification** : Badges, points, classements et système de récompenses
4. **Service de Paiement** : Gestion des abonnements, factures et transactions
5. **Service d'Analyse** : Suivi des performances, analytics et reporting
6. **Service de Communication** : Forum, notifications et messagerie
7. **Service d'Administration** : Panneau d'administration et gestion des locataires
8. **Service d'IA** : Intégration avec Mistral AI pour l'assistance intelligente

### Technologies Clés

- **Backend** : Flask (Python) pour les API REST
- **Base de données** : PostgreSQL pour les données relationnelles, Redis pour le cache
- **Authentification** : JWT avec refresh tokens, OAuth 2.0 pour SSO
- **Paiements** : Stripe pour le traitement des paiements
- **Cache** : Redis pour les sessions et données fréquemment consultées
- **Message Queue** : Celery avec Redis pour les tâches asynchrones
- **Monitoring** : Prometheus et Grafana pour la surveillance
- **Déploiement** : Docker containers avec orchestration

## 2. Schéma de Base de Données

### Modèle de Données Multi-tenant

L'architecture de base de données suit un modèle multi-tenant avec isolation par tenant_id, permettant de servir plusieurs organisations tout en maintenant la séparation des données.

### Tables Principales

#### Gestion des Utilisateurs et Authentification

```sql
-- Table des organisations (tenants)
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    domain VARCHAR(255) UNIQUE,
    subscription_plan VARCHAR(50) NOT NULL DEFAULT 'free',
    subscription_status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des utilisateurs
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    role VARCHAR(50) NOT NULL DEFAULT 'student',
    is_active BOOLEAN DEFAULT true,
    email_verified BOOLEAN DEFAULT false,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des sessions utilisateur
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    refresh_token VARCHAR(255) UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des rôles et permissions
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),
    name VARCHAR(100) NOT NULL,
    permissions JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Gestion des Contenus et Apprentissage

```sql
-- Table des modules d'apprentissage
CREATE TABLE learning_modules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    content JSONB NOT NULL,
    difficulty_level INTEGER DEFAULT 1,
    estimated_duration INTEGER, -- en minutes
    is_premium BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des exercices
CREATE TABLE exercises (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id UUID REFERENCES learning_modules(id),
    title VARCHAR(255) NOT NULL,
    question TEXT NOT NULL,
    exercise_type VARCHAR(50) NOT NULL, -- 'multiple_choice', 'essay', 'scenario'
    options JSONB, -- pour les questions à choix multiples
    correct_answer JSONB,
    explanation TEXT,
    points INTEGER DEFAULT 10,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des progrès utilisateur
CREATE TABLE user_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    module_id UUID REFERENCES learning_modules(id),
    completion_percentage DECIMAL(5,2) DEFAULT 0,
    score INTEGER DEFAULT 0,
    time_spent INTEGER DEFAULT 0, -- en minutes
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des réponses utilisateur
CREATE TABLE user_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    exercise_id UUID REFERENCES exercises(id),
    response JSONB NOT NULL,
    is_correct BOOLEAN,
    points_earned INTEGER DEFAULT 0,
    ai_feedback TEXT,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Système de Gamification

```sql
-- Table des badges
CREATE TABLE badges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    icon_url VARCHAR(255),
    criteria JSONB NOT NULL, -- conditions pour obtenir le badge
    points_value INTEGER DEFAULT 0,
    rarity VARCHAR(20) DEFAULT 'common', -- 'common', 'rare', 'epic', 'legendary'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des badges utilisateur
CREATE TABLE user_badges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    badge_id UUID REFERENCES badges(id),
    earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, badge_id)
);

-- Table des points utilisateur
CREATE TABLE user_points (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    points INTEGER NOT NULL,
    source VARCHAR(100) NOT NULL, -- 'exercise_completion', 'badge_earned', 'daily_login'
    description TEXT,
    earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des classements
CREATE TABLE leaderboards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),
    name VARCHAR(100) NOT NULL,
    type VARCHAR(50) NOT NULL, -- 'weekly', 'monthly', 'all_time'
    start_date DATE,
    end_date DATE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Gestion des Paiements et Abonnements

```sql
-- Table des plans d'abonnement
CREATE TABLE subscription_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'EUR',
    billing_cycle VARCHAR(20) NOT NULL, -- 'monthly', 'yearly'
    features JSONB NOT NULL DEFAULT '{}',
    max_users INTEGER,
    is_active BOOLEAN DEFAULT true,
    stripe_price_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des abonnements
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),
    plan_id UUID REFERENCES subscription_plans(id),
    stripe_subscription_id VARCHAR(255) UNIQUE,
    status VARCHAR(50) NOT NULL, -- 'active', 'canceled', 'past_due', 'unpaid'
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,
    cancel_at_period_end BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des factures
CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),
    subscription_id UUID REFERENCES subscriptions(id),
    stripe_invoice_id VARCHAR(255) UNIQUE,
    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'EUR',
    status VARCHAR(50) NOT NULL, -- 'paid', 'pending', 'failed'
    invoice_date DATE NOT NULL,
    due_date DATE,
    paid_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des méthodes de paiement
CREATE TABLE payment_methods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),
    stripe_payment_method_id VARCHAR(255) UNIQUE NOT NULL,
    type VARCHAR(50) NOT NULL, -- 'card', 'bank_account'
    card_brand VARCHAR(50),
    card_last4 VARCHAR(4),
    is_default BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Communication et Forum

```sql
-- Table des catégories de forum
CREATE TABLE forum_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    color VARCHAR(7), -- code couleur hex
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des discussions
CREATE TABLE forum_topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id UUID REFERENCES forum_categories(id),
    user_id UUID REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    is_pinned BOOLEAN DEFAULT false,
    is_locked BOOLEAN DEFAULT false,
    views_count INTEGER DEFAULT 0,
    replies_count INTEGER DEFAULT 0,
    last_reply_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des réponses
CREATE TABLE forum_replies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id UUID REFERENCES forum_topics(id),
    user_id UUID REFERENCES users(id),
    content TEXT NOT NULL,
    is_solution BOOLEAN DEFAULT false,
    likes_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des notifications
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    type VARCHAR(50) NOT NULL, -- 'badge_earned', 'reply_received', 'payment_failed'
    title VARCHAR(255) NOT NULL,
    message TEXT,
    data JSONB,
    is_read BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Analytics et Reporting

```sql
-- Table des événements d'analyse
CREATE TABLE analytics_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),
    user_id UUID REFERENCES users(id),
    event_type VARCHAR(100) NOT NULL,
    event_data JSONB NOT NULL DEFAULT '{}',
    session_id VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des métriques agrégées
CREATE TABLE analytics_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(15,4) NOT NULL,
    dimensions JSONB DEFAULT '{}',
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Index et Optimisations

```sql
-- Index pour les requêtes fréquentes
CREATE INDEX idx_users_organization_id ON users(organization_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_user_progress_user_id ON user_progress(user_id);
CREATE INDEX idx_user_progress_module_id ON user_progress(module_id);
CREATE INDEX idx_forum_topics_category_id ON forum_topics(category_id);
CREATE INDEX idx_forum_replies_topic_id ON forum_replies(topic_id);
CREATE INDEX idx_notifications_user_id_unread ON notifications(user_id) WHERE is_read = false;
CREATE INDEX idx_analytics_events_organization_created ON analytics_events(organization_id, created_at);

-- Index composites pour les requêtes complexes
CREATE INDEX idx_user_badges_user_earned ON user_badges(user_id, earned_at DESC);
CREATE INDEX idx_subscriptions_org_status ON subscriptions(organization_id, status);
```

## 3. Architecture des API

### Structure des API REST

Les API suivront les principes REST avec une structure cohérente :

```
/api/v1/
├── auth/
│   ├── login
│   ├── logout
│   ├── register
│   ├── refresh
│   └── reset-password
├── users/
│   ├── profile
│   ├── progress
│   └── preferences
├── organizations/
│   ├── settings
│   ├── members
│   └── billing
├── learning/
│   ├── modules
│   ├── exercises
│   └── progress
├── gamification/
│   ├── badges
│   ├── leaderboards
│   └── points
├── forum/
│   ├── categories
│   ├── topics
│   └── replies
├── payments/
│   ├── plans
│   ├── subscriptions
│   └── invoices
└── admin/
    ├── users
    ├── content
    └── analytics
```

### Authentification et Autorisation

L'authentification utilisera JWT (JSON Web Tokens) avec les caractéristiques suivantes :

- **Access tokens** : Durée de vie courte (15 minutes)
- **Refresh tokens** : Durée de vie longue (30 jours)
- **Rotation des tokens** : Nouveau refresh token à chaque renouvellement
- **Révocation** : Possibilité de révoquer les tokens en cas de compromission

### Middleware de Sécurité

Chaque requête API passera par plusieurs couches de middleware :

1. **CORS** : Configuration pour permettre les requêtes cross-origin
2. **Rate Limiting** : Limitation du nombre de requêtes par utilisateur/IP
3. **Authentification** : Vérification des tokens JWT
4. **Autorisation** : Vérification des permissions basées sur les rôles
5. **Validation** : Validation des données d'entrée
6. **Logging** : Enregistrement des requêtes pour audit et debugging

## 4. Architecture de Déploiement

### Containerisation avec Docker

Chaque service sera containerisé avec Docker pour assurer la portabilité et la cohérence entre les environnements :

```dockerfile
# Exemple de Dockerfile pour un service Flask
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "app:app"]
```

### Orchestration et Scalabilité

L'orchestration des containers permettra :

- **Auto-scaling** : Ajustement automatique du nombre d'instances selon la charge
- **Load balancing** : Distribution du trafic entre les instances
- **Health checks** : Surveillance de la santé des services
- **Rolling updates** : Déploiements sans interruption de service

### Monitoring et Observabilité

Le système de monitoring comprendra :

- **Métriques applicatives** : Performance, erreurs, utilisation des ressources
- **Logs centralisés** : Agrégation des logs de tous les services
- **Traces distribuées** : Suivi des requêtes à travers les microservices
- **Alertes** : Notifications en cas de problèmes critiques

Cette architecture technique fournit une base solide pour développer CriticalMind en tant que SaaS scalable et sécurisé, capable de gérer des milliers d'utilisateurs simultanés tout en maintenant des performances optimales et une expérience utilisateur exceptionnelle.

