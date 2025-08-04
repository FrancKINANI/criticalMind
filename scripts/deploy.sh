#!/bin/bash

# CriticalMind SaaS Deployment Script
# This script handles production deployment with zero-downtime

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT="${1:-production}"
BACKUP_ENABLED="${BACKUP_ENABLED:-true}"
HEALTH_CHECK_TIMEOUT="${HEALTH_CHECK_TIMEOUT:-300}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Error handling
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Deployment failed with exit code $exit_code"
        if [ "$BACKUP_ENABLED" = "true" ]; then
            log_info "Attempting to restore from backup..."
            restore_backup
        fi
    fi
    exit $exit_code
}

trap cleanup EXIT

# Validation functions
validate_environment() {
    log_info "Validating environment: $ENVIRONMENT"
    
    case $ENVIRONMENT in
        production|staging|development)
            ;;
        *)
            log_error "Invalid environment: $ENVIRONMENT"
            log_error "Valid environments: production, staging, development"
            exit 1
            ;;
    esac
    
    # Check required environment variables
    local required_vars=(
        "SECRET_KEY"
        "JWT_SECRET_KEY"
        "DATABASE_URL"
        "REDIS_URL"
    )
    
    if [ "$ENVIRONMENT" = "production" ]; then
        required_vars+=(
            "STRIPE_SECRET_KEY"
            "STRIPE_PUBLISHABLE_KEY"
            "MAIL_USERNAME"
            "MAIL_PASSWORD"
            "DOMAIN"
            "SSL_EMAIL"
        )
    fi
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var:-}" ]; then
            log_error "Required environment variable $var is not set"
            exit 1
        fi
    done
    
    log_success "Environment validation passed"
}

# Pre-deployment checks
pre_deployment_checks() {
    log_info "Running pre-deployment checks..."
    
    # Check if Docker is running
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker is not running"
        exit 1
    fi
    
    # Check if Docker Compose is available
    if ! command -v docker-compose >/dev/null 2>&1; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    
    # Check disk space (require at least 2GB free)
    local available_space=$(df / | awk 'NR==2 {print $4}')
    local required_space=2097152  # 2GB in KB
    
    if [ "$available_space" -lt "$required_space" ]; then
        log_error "Insufficient disk space. Required: 2GB, Available: $(($available_space / 1024 / 1024))GB"
        exit 1
    fi
    
    # Check if ports are available
    local ports=(80 443 5432 6379)
    for port in "${ports[@]}"; do
        if netstat -tuln | grep -q ":$port "; then
            log_warning "Port $port is already in use"
        fi
    done
    
    log_success "Pre-deployment checks passed"
}

# Backup functions
create_backup() {
    if [ "$BACKUP_ENABLED" != "true" ]; then
        log_info "Backup disabled, skipping..."
        return 0
    fi
    
    log_info "Creating backup..."
    
    local backup_dir="/opt/backups/criticalmind"
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_path="$backup_dir/backup_$timestamp"
    
    mkdir -p "$backup_path"
    
    # Backup database
    if docker-compose ps db | grep -q "Up"; then
        log_info "Backing up database..."
        docker-compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "$backup_path/database.sql"
    fi
    
    # Backup uploaded files
    if [ -d "/opt/criticalmind/uploads" ]; then
        log_info "Backing up uploaded files..."
        cp -r "/opt/criticalmind/uploads" "$backup_path/"
    fi
    
    # Backup configuration
    cp "$PROJECT_ROOT/.env" "$backup_path/" 2>/dev/null || true
    
    # Create backup metadata
    cat > "$backup_path/metadata.json" << EOF
{
    "timestamp": "$timestamp",
    "environment": "$ENVIRONMENT",
    "git_commit": "$(git rev-parse HEAD 2>/dev/null || echo 'unknown')",
    "git_branch": "$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')"
}
EOF
    
    # Compress backup
    tar -czf "$backup_dir/backup_$timestamp.tar.gz" -C "$backup_dir" "backup_$timestamp"
    rm -rf "$backup_path"
    
    # Keep only last 10 backups
    ls -t "$backup_dir"/backup_*.tar.gz | tail -n +11 | xargs -r rm
    
    log_success "Backup created: backup_$timestamp.tar.gz"
    echo "$backup_dir/backup_$timestamp.tar.gz" > /tmp/latest_backup
}

restore_backup() {
    if [ ! -f "/tmp/latest_backup" ]; then
        log_error "No backup file found for restoration"
        return 1
    fi
    
    local backup_file=$(cat /tmp/latest_backup)
    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        return 1
    fi
    
    log_info "Restoring from backup: $backup_file"
    
    # Extract backup
    local temp_dir=$(mktemp -d)
    tar -xzf "$backup_file" -C "$temp_dir"
    
    # Restore database
    if [ -f "$temp_dir/backup_*/database.sql" ]; then
        log_info "Restoring database..."
        docker-compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$temp_dir/backup_*/database.sql"
    fi
    
    # Restore uploaded files
    if [ -d "$temp_dir/backup_*/uploads" ]; then
        log_info "Restoring uploaded files..."
        cp -r "$temp_dir/backup_*/uploads" "/opt/criticalmind/"
    fi
    
    # Cleanup
    rm -rf "$temp_dir"
    
    log_success "Backup restored successfully"
}

# Deployment functions
pull_latest_images() {
    log_info "Pulling latest Docker images..."
    
    local compose_file="docker-compose.${ENVIRONMENT}.yml"
    if [ ! -f "$compose_file" ]; then
        compose_file="docker-compose.yml"
    fi
    
    docker-compose -f "$compose_file" pull
    
    log_success "Docker images pulled successfully"
}

deploy_services() {
    log_info "Deploying services..."
    
    local compose_file="docker-compose.${ENVIRONMENT}.yml"
    if [ ! -f "$compose_file" ]; then
        compose_file="docker-compose.yml"
    fi
    
    # Start database and cache first
    docker-compose -f "$compose_file" up -d db redis
    
    # Wait for database to be ready
    log_info "Waiting for database to be ready..."
    local retries=30
    while [ $retries -gt 0 ]; do
        if docker-compose -f "$compose_file" exec -T db pg_isready -U "$POSTGRES_USER" >/dev/null 2>&1; then
            break
        fi
        retries=$((retries - 1))
        sleep 2
    done
    
    if [ $retries -eq 0 ]; then
        log_error "Database failed to start"
        exit 1
    fi
    
    # Run database migrations
    log_info "Running database migrations..."
    docker-compose -f "$compose_file" run --rm backend flask db upgrade
    
    # Start all services
    docker-compose -f "$compose_file" up -d
    
    log_success "Services deployed successfully"
}

# Health check functions
health_check() {
    log_info "Running health checks..."
    
    local backend_url="http://localhost:5000"
    local frontend_url="http://localhost:3000"
    
    if [ "$ENVIRONMENT" = "production" ]; then
        backend_url="https://api.criticalmind.app"
        frontend_url="https://criticalmind.app"
    fi
    
    # Check backend health
    local retries=$((HEALTH_CHECK_TIMEOUT / 10))
    while [ $retries -gt 0 ]; do
        if curl -f "$backend_url/health" >/dev/null 2>&1; then
            log_success "Backend health check passed"
            break
        fi
        retries=$((retries - 1))
        sleep 10
    done
    
    if [ $retries -eq 0 ]; then
        log_error "Backend health check failed"
        return 1
    fi
    
    # Check frontend
    retries=$((HEALTH_CHECK_TIMEOUT / 10))
    while [ $retries -gt 0 ]; do
        if curl -f "$frontend_url" >/dev/null 2>&1; then
            log_success "Frontend health check passed"
            break
        fi
        retries=$((retries - 1))
        sleep 10
    done
    
    if [ $retries -eq 0 ]; then
        log_error "Frontend health check failed"
        return 1
    fi
    
    log_success "All health checks passed"
}

# Cleanup functions
cleanup_old_images() {
    log_info "Cleaning up old Docker images..."
    
    # Remove dangling images
    docker image prune -f
    
    # Remove old images (keep last 3 versions)
    docker images --format "table {{.Repository}}:{{.Tag}}\t{{.CreatedAt}}" | \
        grep criticalmind | \
        sort -k2 -r | \
        tail -n +4 | \
        awk '{print $1}' | \
        xargs -r docker rmi
    
    log_success "Docker cleanup completed"
}

# Main deployment function
main() {
    log_info "Starting CriticalMind SaaS deployment..."
    log_info "Environment: $ENVIRONMENT"
    log_info "Timestamp: $(date)"
    
    cd "$PROJECT_ROOT"
    
    validate_environment
    pre_deployment_checks
    create_backup
    pull_latest_images
    deploy_services
    health_check
    cleanup_old_images
    
    log_success "Deployment completed successfully!"
    log_info "Application is now running at:"
    
    if [ "$ENVIRONMENT" = "production" ]; then
        log_info "  Frontend: https://criticalmind.app"
        log_info "  API: https://api.criticalmind.app"
    else
        log_info "  Frontend: http://localhost:3000"
        log_info "  API: http://localhost:5000"
    fi
}

# Script entry point
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
