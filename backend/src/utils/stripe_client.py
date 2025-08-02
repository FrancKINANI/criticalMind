import stripe
import os
from flask import current_app
from typing import Dict, Any, Optional

class StripeClient:
    """Client Stripe pour la gestion des paiements et abonnements"""
    
    def __init__(self):
        # En production, utiliser des variables d'environnement
        # Pour la démo, utiliser des clés de test
        stripe.api_key = "sk_test_demo_key"  # Remplacer par une vraie clé de test
        self.webhook_secret = "whsec_demo_secret"  # Remplacer par le vrai secret webhook
    
    def create_customer(self, email: str, name: str = None, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Créer un client Stripe"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            return {
                'success': True,
                'customer': customer
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_product(self, name: str, description: str = None) -> Dict[str, Any]:
        """Créer un produit Stripe"""
        try:
            product = stripe.Product.create(
                name=name,
                description=description,
                type='service'
            )
            return {
                'success': True,
                'product': product
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_price(self, product_id: str, amount: int, currency: str = 'eur', 
                    interval: str = 'month') -> Dict[str, Any]:
        """Créer un prix Stripe pour un abonnement"""
        try:
            price = stripe.Price.create(
                product=product_id,
                unit_amount=amount,  # en centimes
                currency=currency,
                recurring={'interval': interval}
            )
            return {
                'success': True,
                'price': price
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_subscription(self, customer_id: str, price_id: str, 
                          trial_period_days: int = None) -> Dict[str, Any]:
        """Créer un abonnement Stripe"""
        try:
            subscription_data = {
                'customer': customer_id,
                'items': [{'price': price_id}],
                'payment_behavior': 'default_incomplete',
                'payment_settings': {'save_default_payment_method': 'on_subscription'},
                'expand': ['latest_invoice.payment_intent']
            }
            
            if trial_period_days:
                subscription_data['trial_period_days'] = trial_period_days
            
            subscription = stripe.Subscription.create(**subscription_data)
            
            return {
                'success': True,
                'subscription': subscription,
                'client_secret': subscription.latest_invoice.payment_intent.client_secret
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def update_subscription(self, subscription_id: str, price_id: str = None, 
                          cancel_at_period_end: bool = None) -> Dict[str, Any]:
        """Mettre à jour un abonnement"""
        try:
            update_data = {}
            
            if price_id:
                # Récupérer l'abonnement actuel
                subscription = stripe.Subscription.retrieve(subscription_id)
                update_data['items'] = [{
                    'id': subscription['items']['data'][0].id,
                    'price': price_id
                }]
                update_data['proration_behavior'] = 'create_prorations'
            
            if cancel_at_period_end is not None:
                update_data['cancel_at_period_end'] = cancel_at_period_end
            
            subscription = stripe.Subscription.modify(subscription_id, **update_data)
            
            return {
                'success': True,
                'subscription': subscription
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def cancel_subscription(self, subscription_id: str, immediately: bool = False) -> Dict[str, Any]:
        """Annuler un abonnement"""
        try:
            if immediately:
                subscription = stripe.Subscription.cancel(subscription_id)
            else:
                subscription = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True
                )
            
            return {
                'success': True,
                'subscription': subscription
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_payment_intent(self, amount: int, currency: str = 'eur', 
                            customer_id: str = None) -> Dict[str, Any]:
        """Créer un PaymentIntent pour un paiement unique"""
        try:
            payment_intent_data = {
                'amount': amount,
                'currency': currency,
                'automatic_payment_methods': {'enabled': True}
            }
            
            if customer_id:
                payment_intent_data['customer'] = customer_id
            
            payment_intent = stripe.PaymentIntent.create(**payment_intent_data)
            
            return {
                'success': True,
                'payment_intent': payment_intent,
                'client_secret': payment_intent.client_secret
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def retrieve_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Récupérer les détails d'un abonnement"""
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            return {
                'success': True,
                'subscription': subscription
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def list_invoices(self, customer_id: str, limit: int = 10) -> Dict[str, Any]:
        """Lister les factures d'un client"""
        try:
            invoices = stripe.Invoice.list(
                customer=customer_id,
                limit=limit
            )
            return {
                'success': True,
                'invoices': invoices
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_billing_portal_session(self, customer_id: str, return_url: str) -> Dict[str, Any]:
        """Créer une session du portail de facturation"""
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url
            )
            return {
                'success': True,
                'session': session
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def construct_webhook_event(self, payload: bytes, signature: str) -> Optional[Dict[str, Any]]:
        """Construire et vérifier un événement webhook"""
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            return event
        except ValueError:
            # Payload invalide
            return None
        except stripe.error.SignatureVerificationError:
            # Signature invalide
            return None

# Instance globale du client Stripe
stripe_client = StripeClient()

