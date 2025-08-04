# 🚀 CriticalMind SaaS Production Deployment Guide

This comprehensive guide will help you deploy CriticalMind as a production-ready SaaS application.

## 📋 Prerequisites

### System Requirements
- **Server**: Ubuntu 20.04+ or CentOS 8+ (minimum 4GB RAM, 2 CPU cores, 50GB storage)
- **Docker**: Version 20.10+
- **Docker Compose**: Version 2.0+
- **Domain**: Registered domain with DNS access
- **SSL Certificate**: Let's Encrypt (automated) or custom certificate

### Required Accounts & Services
- **Stripe Account**: For payment processing
- **Email Service**: Gmail, SendGrid, or AWS SES
- **Cloud Storage**: AWS S3 for backups (optional)
- **Monitoring**: Sentry for error tracking (optional)
- **AI Services**: OpenAI and/or Mistral API keys

## 🔧 Pre-Deployment Setup

### 1. Server Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Create application directory
sudo mkdir -p /opt/criticalmind-production
sudo chown $USER:$USER /opt/criticalmind-production
```

### 2. Clone Repository

```bash
cd /opt/criticalmind-production
git clone https://github.com/FrancKINANI/criticalMind.git .
```

### 3. Environment Configuration

```bash
# Copy production environment template
cp .env.production .env

# Edit environment variables
nano .env
```

**Critical Environment Variables to Update:**

```env
# Security (Generate strong random strings)
SECRET_KEY=your-super-secure-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here

# Database
POSTGRES_PASSWORD=your-secure-database-password

# Redis
REDIS_PASSWORD=your-secure-redis-password

# Domain
DOMAIN=yourdomain.com
SSL_EMAIL=admin@yourdomain.com

# Stripe (Production keys)
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Email
MAIL_USERNAME=noreply@yourdomain.com
MAIL_PASSWORD=your-email-app-password

# AI Services
OPENAI_API_KEY=your-openai-key
MISTRAL_API_KEY=your-mistral-key

# Monitoring
SENTRY_DSN=your-sentry-dsn-url
```

## 🚀 Deployment Process

### 1. Initial Deployment

```bash
# Make deployment script executable
chmod +x scripts/deploy.sh

# Run initial deployment
./scripts/deploy.sh production
```

### 2. SSL Certificate Setup

```bash
# Generate SSL certificates with Let's Encrypt
docker-compose --profile ssl-setup run --rm certbot

# Restart Nginx with SSL
docker-compose restart nginx
```

### 3. Database Setup

```bash
# Run database migrations
docker-compose exec backend flask db upgrade

# Create admin user (optional)
docker-compose exec backend python -c "
from src.models import db, User
from werkzeug.security import generate_password_hash
admin = User(
    email='admin@yourdomain.com',
    password_hash=generate_password_hash('secure-admin-password'),
    first_name='Admin',
    last_name='User',
    role='admin',
    is_active=True,
    email_verified=True
)
db.session.add(admin)
db.session.commit()
print('Admin user created')
"
```

## 🔒 Security Configuration

### 1. Firewall Setup

```bash
# Configure UFW firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 2. SSL/TLS Configuration

The deployment includes automatic SSL certificate generation and renewal:

- **Let's Encrypt**: Automated certificate generation
- **HTTPS Redirect**: All HTTP traffic redirected to HTTPS
- **HSTS**: HTTP Strict Transport Security enabled
- **Modern TLS**: Only TLS 1.2+ supported

### 3. Security Headers

All security headers are automatically configured:
- Content Security Policy (CSP)
- X-Frame-Options
- X-Content-Type-Options
- X-XSS-Protection
- Referrer-Policy

## 📊 Monitoring Setup

### 1. Enable Monitoring Stack

```bash
# Start monitoring services
docker-compose --profile monitoring up -d
```

### 2. Access Monitoring Dashboards

- **Grafana**: `https://yourdomain.com:3000` (admin/your-grafana-password)
- **Prometheus**: `https://yourdomain.com:9090`

### 3. Configure Alerts

Edit `monitoring/prometheus.yml` to configure alerting rules and notification channels.

## 💾 Backup Configuration

### 1. Automated Backups

```bash
# Enable backup service
docker-compose --profile backup up -d
```

### 2. Manual Backup

```bash
# Create manual backup
./scripts/backup.sh
```

### 3. Restore from Backup

```bash
# Restore from specific backup
./scripts/restore.sh backup_20240101_120000.tar.gz
```

## 🔄 CI/CD Setup

### 1. GitHub Actions

The repository includes a complete CI/CD pipeline:

- **Security Scanning**: Trivy, Bandit
- **Testing**: Backend (pytest), Frontend (Vitest, Playwright)
- **Building**: Docker images
- **Deployment**: Automated to staging/production

### 2. Required Secrets

Add these secrets to your GitHub repository:

```
STAGING_HOST=your-staging-server-ip
STAGING_USER=deploy
STAGING_SSH_KEY=your-ssh-private-key

PRODUCTION_HOST=your-production-server-ip
PRODUCTION_USER=deploy
PRODUCTION_SSH_KEY=your-ssh-private-key

SLACK_WEBHOOK=your-slack-webhook-url
```

## 🎯 Performance Optimization

### 1. Database Optimization

```sql
-- Create indexes for better performance
CREATE INDEX CONCURRENTLY idx_users_email ON users(email);
CREATE INDEX CONCURRENTLY idx_user_sessions_token ON user_sessions(session_token);
CREATE INDEX CONCURRENTLY idx_learning_progress_user ON user_progress(user_id);
```

### 2. Redis Configuration

```bash
# Optimize Redis for production
docker-compose exec redis redis-cli CONFIG SET maxmemory 512mb
docker-compose exec redis redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

### 3. Application Scaling

```bash
# Scale backend services
docker-compose up -d --scale backend=3
```

## 🔍 Health Checks & Monitoring

### 1. Application Health

```bash
# Check application health
curl https://yourdomain.com/health
curl https://api.yourdomain.com/health
```

### 2. Service Status

```bash
# Check all services
docker-compose ps

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f nginx
```

### 3. Performance Metrics

Access metrics at:
- Application metrics: `https://api.yourdomain.com/metrics`
- System metrics: Grafana dashboard

## 🚨 Troubleshooting

### Common Issues

1. **SSL Certificate Issues**
   ```bash
   # Regenerate certificates
   docker-compose --profile ssl-setup run --rm certbot renew
   ```

2. **Database Connection Issues**
   ```bash
   # Check database status
   docker-compose exec db pg_isready -U criticalmind_user
   ```

3. **Memory Issues**
   ```bash
   # Check memory usage
   docker stats
   # Restart services if needed
   docker-compose restart
   ```

### Log Analysis

```bash
# View application logs
docker-compose logs -f --tail=100 backend

# View Nginx access logs
docker-compose exec nginx tail -f /var/log/nginx/access.log

# View system logs
journalctl -u docker -f
```

## 📈 Scaling Considerations

### Horizontal Scaling

1. **Load Balancer**: Use AWS ALB, Cloudflare, or similar
2. **Database**: Consider PostgreSQL clustering or managed services
3. **File Storage**: Move to S3 or similar object storage
4. **CDN**: Implement CloudFront or Cloudflare for static assets

### Vertical Scaling

1. **Increase server resources** as user base grows
2. **Optimize database queries** and add indexes
3. **Implement caching** at multiple levels
4. **Use connection pooling** for database connections

## 🔐 Security Best Practices

1. **Regular Updates**: Keep all dependencies updated
2. **Security Scanning**: Run regular vulnerability scans
3. **Access Control**: Use strong passwords and 2FA
4. **Monitoring**: Monitor for suspicious activities
5. **Backups**: Regular automated backups with testing
6. **Incident Response**: Have a plan for security incidents

## 📞 Support & Maintenance

### Regular Maintenance Tasks

1. **Weekly**: Review logs and metrics
2. **Monthly**: Update dependencies and security patches
3. **Quarterly**: Review and test backup/restore procedures
4. **Annually**: Security audit and penetration testing

### Getting Help

- **Documentation**: Check this guide and code comments
- **Issues**: Create GitHub issues for bugs
- **Security**: Email security@yourdomain.com for security issues
- **Support**: Contact support@yourdomain.com for general help

---

## 🎉 Congratulations!

Your CriticalMind SaaS application is now deployed and ready for production use. The platform includes:

✅ **Production-ready security** with HTTPS, security headers, and input validation  
✅ **Scalable architecture** with Docker containers and load balancing  
✅ **Comprehensive monitoring** with metrics, logging, and alerting  
✅ **Automated backups** with disaster recovery procedures  
✅ **CI/CD pipeline** for automated testing and deployment  
✅ **Performance optimization** with caching and database tuning  

Your application is now accessible at `https://yourdomain.com` and ready to serve real users!
