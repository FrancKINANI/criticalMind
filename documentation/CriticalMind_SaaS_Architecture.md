# Technical Architecture and Database Schema for CriticalMind SaaS

## Introduction

This document presents the complete technical architecture for transforming CriticalMind into a robust and scalable SaaS solution. The proposed architecture follows industry best practices to ensure the security, performance, and scalability required for a million-dollar SaaS.

## 1. Architecture Overview

### Microservices Architecture

The CriticalMind SaaS application will be built on a modular microservices architecture, enabling horizontal scalability and simplified maintenance. This approach offers several advantages:

- **Service isolation**: Each service can be developed, deployed, and scaled independently
- **Resilience**: A service failure does not affect the whole system
- **Technology diversity**: Different technologies can be used based on the specific needs of each service
- **Autonomous teams**: Teams can work on different services in parallel

### Main Services

The architecture will include the following services:

1. **Authentication Service**: User management, authentication, and authorization
2. **Content Management Service**: Learning modules, exercises, and educational resources
3. **Gamification Service**: Badges, points, leaderboards, and reward system
4. **Payment Service**: Subscription, invoice, and transaction management
5. **Analytics Service**: Performance tracking, analytics, and reporting
6. **Communication Service**: Forum, notifications, and messaging
7. **Administration Service**: Admin panel and tenant management
8. **AI Service**: Integration with Mistral AI for intelligent assistance

### Key Technologies

- **Backend**: Flask (Python) for REST APIs
- **Database**: PostgreSQL for relational data, Redis for cache
- **Authentication**: JWT with refresh tokens, OAuth 2.0 for SSO
- **Payments**: Stripe for payment processing
- **Cache**: Redis for sessions and frequently accessed data
- **Message Queue**: Celery with Redis for asynchronous tasks
- **Monitoring**: Prometheus and Grafana for observability
- **Deployment**: Docker containers with orchestration

## 2. Database Schema

### Multi-tenant Data Model

The database architecture follows a multi-tenant model with tenant_id isolation, allowing multiple organizations to be served while maintaining data separation.

### Main Tables

#### User Management and Authentication

```sql
-- Organizations (tenants) table
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    domain VARCHAR(255) UNIQUE,
    subscription_plan VARCHAR(50) NOT NULL DEFAULT 'free',
    subscription_status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Users table
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

-- User sessions table
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    refresh_token VARCHAR(255) UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Roles and permissions table
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),
    name VARCHAR(100) NOT NULL,
    permissions JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Content Management and Learning

```sql
-- Learning modules table
CREATE TABLE learning_modules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    content JSONB NOT NULL,
    difficulty_level INTEGER DEFAULT 1,
    estimated_duration INTEGER, -- in minutes
    is_premium BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Exercises table
CREATE TABLE exercises (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id UUID REFERENCES learning_modules(id),
    title VARCHAR(255) NOT NULL,
    question TEXT NOT NULL,
    exercise_type VARCHAR(50) NOT NULL, -- 'multiple_choice', 'essay', 'scenario'
    options JSONB, -- for multiple choice questions
    correct_answer JSONB,
    explanation TEXT,
    points INTEGER DEFAULT 10,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User progress table
CREATE TABLE user_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    module_id UUID REFERENCES learning_modules(id),
    completion_percentage DECIMAL(5,2) DEFAULT 0,
    score INTEGER DEFAULT 0,
    time_spent INTEGER DEFAULT 0, -- in minutes
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User responses table
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

#### Gamification System

```sql
-- Badges table
CREATE TABLE badges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    icon_url VARCHAR(255),
    criteria JSONB NOT NULL, -- conditions to earn the badge
    points_value INTEGER DEFAULT 0,
    rarity VARCHAR(20) DEFAULT 'common', -- 'common', 'rare', 'epic', 'legendary'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User badges table
CREATE TABLE user_badges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    badge_id UUID REFERENCES badges(id),
    earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, badge_id)
);

-- User points table
CREATE TABLE user_points (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    points INTEGER NOT NULL,
    source VARCHAR(100) NOT NULL, -- 'exercise_completion', 'badge_earned', 'daily_login'
    description TEXT,
    earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Leaderboards table
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

#### Payments and Subscriptions Management

```sql
-- Subscription plans table
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

-- Subscriptions table
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

-- Invoices table
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

-- Payment methods table
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

#### Communication and Forum

```sql
-- Forum categories table
CREATE TABLE forum_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    color VARCHAR(7), -- hex color code
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Discussions table
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

-- Replies table
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

-- Notifications table
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

#### Analytics and Reporting

```sql
-- Analytics events table
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

-- Aggregated metrics table
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

### Indexes and Optimizations

```sql
-- Indexes for frequent queries
CREATE INDEX idx_users_organization_id ON users(organization_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_user_progress_user_id ON user_progress(user_id);
CREATE INDEX idx_user_progress_module_id ON user_progress(module_id);
CREATE INDEX idx_forum_topics_category_id ON forum_topics(category_id);
CREATE INDEX idx_forum_replies_topic_id ON forum_replies(topic_id);
CREATE INDEX idx_notifications_user_id_unread ON notifications(user_id) WHERE is_read = false;
CREATE INDEX idx_analytics_events_organization_created ON analytics_events(organization_id, created_at);

-- Composite indexes for complex queries
CREATE INDEX idx_user_badges_user_earned ON user_badges(user_id, earned_at DESC);
CREATE INDEX idx_subscriptions_org_status ON subscriptions(organization_id, status);
```

## 3. API Architecture

### REST API Structure

The APIs will follow REST principles with a consistent structure:

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

### Authentication and Authorization

Authentication will use JWT (JSON Web Tokens) with the following characteristics:

- **Access tokens**: Short lifespan (15 minutes)
- **Refresh tokens**: Long lifespan (30 days)
- **Token rotation**: New refresh token on every renewal
- **Revocation**: Tokens can be revoked in case of compromise

### Security Middleware

Each API request will go through several middleware layers:

1. **CORS**: Configuration to allow cross-origin requests
2. **Rate Limiting**: Limiting the number of requests per user/IP
3. **Authentication**: JWT token verification
4. **Authorization**: Role-based permission checks
5. **Validation**: Input data validation
6. **Logging**: Request logging for audit and debugging

## 4. Deployment Architecture

### Containerization with Docker

Each service will be containerized with Docker to ensure portability and consistency across environments:

```dockerfile
# Example Dockerfile for a Flask service
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "app:app"]
```

### Orchestration and Scalability

Container orchestration will enable:

- **Auto-scaling**: Automatic adjustment of instance count based on load
- **Load balancing**: Traffic distribution across instances
- **Health checks**: Service health monitoring
- **Rolling updates**: Deployments without service interruption

### Monitoring and Observability

The monitoring system will include:

- **Application metrics**: Performance, errors, resource usage
- **Centralized logs**: Log aggregation from all services
- **Distributed traces**: Request tracking across microservices
- **Alerts**: Notifications in case of critical issues

This technical architecture provides a solid foundation for developing CriticalMind as a scalable and secure SaaS, capable of handling thousands of concurrent users while maintaining optimal performance and an exceptional user experience.
