from flask import Blueprint, request, jsonify, g
from src.models import db
from src.models.subscription import SubscriptionPlan, Subscription, Invoice, PaymentMethod
from src.models.organization import Organization
from src.utils.auth import token_required, role_required, organization_required
from src.utils.validators import validate_json, validate_pagination_params
from src.utils.stripe_client import stripe_client
from datetime import datetime, timedelta

payments_bp = Blueprint('payments', __name__)

@payments_bp.route('/plans', methods=['GET'])
def get_subscription_plans():
    """Obtenir tous les plans d'abonnement disponibles"""
    plans = SubscriptionPlan.query.filter_by(is_active=True).all()
    
    return jsonify({
        'plans': [plan.to_dict() for plan in plans]
    }), 200

@payments_bp.route('/plans', methods=['POST'])
@token_required
@role_required('admin')
@validate_json('name', 'price', 'billing_cycle')
def create_subscription_plan():
    """Créer un nouveau plan d'abonnement (admin seulement)"""
    data = request.get_json()
    
    # Créer le produit dans Stripe
    stripe_result = stripe_client.create_product(
        name=data['name'],
        description=data.get('description', '')
    )
    
    if not stripe_result['success']:
        return jsonify({'error': f'Stripe error: {stripe_result["error"]}'}), 400
    
    stripe_product = stripe_result['product']
    
    # Créer le prix dans Stripe
    amount_in_cents = int(float(data['price']) * 100)
    price_result = stripe_client.create_price(
        product_id=stripe_product.id,
        amount=amount_in_cents,
        currency=data.get('currency', 'eur'),
        interval=data['billing_cycle']
    )
    
    if not price_result['success']:
        return jsonify({'error': f'Stripe price error: {price_result["error"]}'}), 400
    
    stripe_price = price_result['price']
    
    # Créer le plan dans la base de données
    plan = SubscriptionPlan(
        name=data['name'],
        description=data.get('description'),
        price=data['price'],
        currency=data.get('currency', 'eur'),
        billing_cycle=data['billing_cycle'],
        features=data.get('features', {}),
        max_users=data.get('max_users'),
        stripe_price_id=stripe_price.id
    )
    
    db.session.add(plan)
    db.session.commit()
    
    return jsonify({
        'message': 'Subscription plan created successfully',
        'plan': plan.to_dict()
    }), 201

@payments_bp.route('/subscribe', methods=['POST'])
@token_required
@organization_required
@validate_json('plan_id')
def create_subscription():
    """Créer un nouvel abonnement pour l'organisation"""
    data = request.get_json()
    
    plan = SubscriptionPlan.query.get(data['plan_id'])
    if not plan or not plan.is_active:
        return jsonify({'error': 'Invalid subscription plan'}), 404
    
    organization = g.current_user.organization
    
    # Vérifier s'il y a déjà un abonnement actif
    existing_subscription = Subscription.query.filter_by(
        organization_id=organization.id,
        status='active'
    ).first()
    
    if existing_subscription:
        return jsonify({'error': 'Organization already has an active subscription'}), 409
    
    # Créer ou récupérer le client Stripe
    stripe_customer_result = stripe_client.create_customer(
        email=g.current_user.email,
        name=organization.name,
        metadata={
            'organization_id': organization.id,
            'user_id': g.current_user.id
        }
    )
    
    if not stripe_customer_result['success']:
        return jsonify({'error': f'Stripe customer error: {stripe_customer_result["error"]}'}), 400
    
    stripe_customer = stripe_customer_result['customer']
    
    # Créer l'abonnement Stripe
    trial_days = data.get('trial_days', 14)  # 14 jours d'essai par défaut
    subscription_result = stripe_client.create_subscription(
        customer_id=stripe_customer.id,
        price_id=plan.stripe_price_id,
        trial_period_days=trial_days
    )
    
    if not subscription_result['success']:
        return jsonify({'error': f'Stripe subscription error: {subscription_result["error"]}'}), 400
    
    stripe_subscription = subscription_result['subscription']
    
    # Créer l'abonnement dans la base de données
    subscription = Subscription(
        organization_id=organization.id,
        plan_id=plan.id,
        stripe_subscription_id=stripe_subscription.id,
        status=stripe_subscription.status,
        current_period_start=datetime.fromtimestamp(stripe_subscription.current_period_start),
        current_period_end=datetime.fromtimestamp(stripe_subscription.current_period_end)
    )
    
    db.session.add(subscription)
    
    # Mettre à jour l'organisation
    organization.subscription_plan = plan.name
    organization.subscription_status = stripe_subscription.status
    
    db.session.commit()
    
    return jsonify({
        'message': 'Subscription created successfully',
        'subscription': subscription.to_dict(),
        'client_secret': subscription_result.get('client_secret'),
        'requires_payment': stripe_subscription.status == 'incomplete'
    }), 201

@payments_bp.route('/subscription', methods=['GET'])
@token_required
@organization_required
def get_current_subscription():
    """Obtenir l'abonnement actuel de l'organisation"""
    subscription = Subscription.query.filter_by(
        organization_id=g.current_user.organization_id
    ).order_by(Subscription.created_at.desc()).first()
    
    if not subscription:
        return jsonify({'error': 'No subscription found'}), 404
    
    # Synchroniser avec Stripe
    stripe_result = stripe_client.retrieve_subscription(subscription.stripe_subscription_id)
    if stripe_result['success']:
        stripe_subscription = stripe_result['subscription']
        
        # Mettre à jour le statut local
        subscription.status = stripe_subscription.status
        subscription.current_period_start = datetime.fromtimestamp(stripe_subscription.current_period_start)
        subscription.current_period_end = datetime.fromtimestamp(stripe_subscription.current_period_end)
        subscription.cancel_at_period_end = stripe_subscription.cancel_at_period_end
        
        db.session.commit()
    
    subscription_data = subscription.to_dict()
    subscription_data['plan'] = subscription.plan.to_dict()
    
    return jsonify({
        'subscription': subscription_data
    }), 200

@payments_bp.route('/subscription/change-plan', methods=['POST'])
@token_required
@organization_required
@role_required('admin')
@validate_json('plan_id')
def change_subscription_plan():
    """Changer le plan d'abonnement"""
    data = request.get_json()
    
    new_plan = SubscriptionPlan.query.get(data['plan_id'])
    if not new_plan or not new_plan.is_active:
        return jsonify({'error': 'Invalid subscription plan'}), 404
    
    subscription = Subscription.query.filter_by(
        organization_id=g.current_user.organization_id,
        status='active'
    ).first()
    
    if not subscription:
        return jsonify({'error': 'No active subscription found'}), 404
    
    # Mettre à jour l'abonnement dans Stripe
    stripe_result = stripe_client.update_subscription(
        subscription_id=subscription.stripe_subscription_id,
        price_id=new_plan.stripe_price_id
    )
    
    if not stripe_result['success']:
        return jsonify({'error': f'Stripe error: {stripe_result["error"]}'}), 400
    
    # Mettre à jour dans la base de données
    subscription.plan_id = new_plan.id
    g.current_user.organization.subscription_plan = new_plan.name
    
    db.session.commit()
    
    return jsonify({
        'message': 'Subscription plan changed successfully',
        'subscription': subscription.to_dict()
    }), 200

@payments_bp.route('/subscription/cancel', methods=['POST'])
@token_required
@organization_required
@role_required('admin')
def cancel_subscription():
    """Annuler l'abonnement"""
    data = request.get_json()
    immediately = data.get('immediately', False)
    
    subscription = Subscription.query.filter_by(
        organization_id=g.current_user.organization_id,
        status='active'
    ).first()
    
    if not subscription:
        return jsonify({'error': 'No active subscription found'}), 404
    
    # Annuler dans Stripe
    stripe_result = stripe_client.cancel_subscription(
        subscription_id=subscription.stripe_subscription_id,
        immediately=immediately
    )
    
    if not stripe_result['success']:
        return jsonify({'error': f'Stripe error: {stripe_result["error"]}'}), 400
    
    stripe_subscription = stripe_result['subscription']
    
    # Mettre à jour dans la base de données
    if immediately:
        subscription.status = 'canceled'
        g.current_user.organization.subscription_status = 'canceled'
    else:
        subscription.cancel_at_period_end = True
    
    db.session.commit()
    
    return jsonify({
        'message': 'Subscription canceled successfully',
        'subscription': subscription.to_dict()
    }), 200

@payments_bp.route('/invoices', methods=['GET'])
@token_required
@organization_required
def get_invoices():
    """Obtenir les factures de l'organisation"""
    page = request.args.get('page', 1)
    per_page = request.args.get('per_page', 20)
    
    page, per_page = validate_pagination_params(page, per_page)
    
    pagination = Invoice.query.filter_by(
        organization_id=g.current_user.organization_id
    ).order_by(Invoice.created_at.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    invoices = [invoice.to_dict() for invoice in pagination.items]
    
    return jsonify({
        'invoices': invoices,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    }), 200

@payments_bp.route('/billing-portal', methods=['POST'])
@token_required
@organization_required
@role_required('admin')
def create_billing_portal_session():
    """Créer une session du portail de facturation Stripe"""
    subscription = Subscription.query.filter_by(
        organization_id=g.current_user.organization_id
    ).order_by(Subscription.created_at.desc()).first()
    
    if not subscription:
        return jsonify({'error': 'No subscription found'}), 404
    
    # Récupérer l'abonnement Stripe pour obtenir le customer_id
    stripe_result = stripe_client.retrieve_subscription(subscription.stripe_subscription_id)
    if not stripe_result['success']:
        return jsonify({'error': 'Failed to retrieve subscription'}), 400
    
    customer_id = stripe_result['subscription'].customer
    return_url = request.get_json().get('return_url', 'https://app.criticalmind.com/billing')
    
    # Créer la session du portail
    portal_result = stripe_client.create_billing_portal_session(
        customer_id=customer_id,
        return_url=return_url
    )
    
    if not portal_result['success']:
        return jsonify({'error': f'Stripe error: {portal_result["error"]}'}), 400
    
    return jsonify({
        'url': portal_result['session'].url
    }), 200

@payments_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    """Gérer les webhooks Stripe"""
    payload = request.get_data()
    signature = request.headers.get('Stripe-Signature')
    
    event = stripe_client.construct_webhook_event(payload, signature)
    if not event:
        return jsonify({'error': 'Invalid webhook signature'}), 400
    
    # Traiter les différents types d'événements
    if event['type'] == 'invoice.payment_succeeded':
        handle_payment_succeeded(event['data']['object'])
    elif event['type'] == 'invoice.payment_failed':
        handle_payment_failed(event['data']['object'])
    elif event['type'] == 'customer.subscription.updated':
        handle_subscription_updated(event['data']['object'])
    elif event['type'] == 'customer.subscription.deleted':
        handle_subscription_deleted(event['data']['object'])
    
    return jsonify({'status': 'success'}), 200

def handle_payment_succeeded(invoice):
    """Gérer un paiement réussi"""
    subscription_id = invoice.get('subscription')
    if not subscription_id:
        return
    
    subscription = Subscription.query.filter_by(
        stripe_subscription_id=subscription_id
    ).first()
    
    if subscription:
        # Créer ou mettre à jour la facture
        invoice_record = Invoice.query.filter_by(
            stripe_invoice_id=invoice['id']
        ).first()
        
        if not invoice_record:
            invoice_record = Invoice(
                organization_id=subscription.organization_id,
                subscription_id=subscription.id,
                stripe_invoice_id=invoice['id'],
                amount=invoice['amount_paid'] / 100,  # Convertir de centimes
                currency=invoice['currency'],
                status='paid',
                invoice_date=datetime.fromtimestamp(invoice['created']),
                paid_at=datetime.fromtimestamp(invoice['status_transitions']['paid_at'])
            )
            db.session.add(invoice_record)
        else:
            invoice_record.status = 'paid'
            invoice_record.paid_at = datetime.fromtimestamp(invoice['status_transitions']['paid_at'])
        
        # Mettre à jour le statut de l'abonnement
        subscription.status = 'active'
        subscription.organization.subscription_status = 'active'
        
        db.session.commit()

def handle_payment_failed(invoice):
    """Gérer un échec de paiement"""
    subscription_id = invoice.get('subscription')
    if not subscription_id:
        return
    
    subscription = Subscription.query.filter_by(
        stripe_subscription_id=subscription_id
    ).first()
    
    if subscription:
        # Mettre à jour le statut
        subscription.status = 'past_due'
        subscription.organization.subscription_status = 'past_due'
        
        # Créer la facture avec le statut failed
        invoice_record = Invoice(
            organization_id=subscription.organization_id,
            subscription_id=subscription.id,
            stripe_invoice_id=invoice['id'],
            amount=invoice['amount_due'] / 100,
            currency=invoice['currency'],
            status='failed',
            invoice_date=datetime.fromtimestamp(invoice['created'])
        )
        db.session.add(invoice_record)
        db.session.commit()

def handle_subscription_updated(subscription_data):
    """Gérer la mise à jour d'un abonnement"""
    subscription = Subscription.query.filter_by(
        stripe_subscription_id=subscription_data['id']
    ).first()
    
    if subscription:
        subscription.status = subscription_data['status']
        subscription.current_period_start = datetime.fromtimestamp(subscription_data['current_period_start'])
        subscription.current_period_end = datetime.fromtimestamp(subscription_data['current_period_end'])
        subscription.cancel_at_period_end = subscription_data['cancel_at_period_end']
        
        subscription.organization.subscription_status = subscription_data['status']
        
        db.session.commit()

def handle_subscription_deleted(subscription_data):
    """Gérer la suppression d'un abonnement"""
    subscription = Subscription.query.filter_by(
        stripe_subscription_id=subscription_data['id']
    ).first()
    
    if subscription:
        subscription.status = 'canceled'
        subscription.organization.subscription_status = 'canceled'
        subscription.organization.subscription_plan = 'free'
        
        db.session.commit()

