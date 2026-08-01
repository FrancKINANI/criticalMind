import stripe
import os
from flask import current_app
from typing import Dict, Any, Optional

class StripeClient:
    """Stripe client for payment and subscription management"""
    
    def __init__(self):
        # In production, use environment variables
        # For the demo, use test keys
        stripe.api_key = "sk_test_demo_key"  # Replace with a real test key
        self.webhook_secret = "whsec_demo_secret"  # Replace with the real webhook secret
    
    def create_customer(self, email: str, name: str = None, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a Stripe customer"""
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
        """Create a Stripe product"""
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
        """Create a Stripe price for a subscription"""
        try:
            price = stripe.Price.create(
                product=product_id,
                unit_amount=amount,  # in cents
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
        """Create a Stripe subscription"""
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
        """Update a subscription"""
        try:
            update_data = {}
            
            if price_id:
                # Retrieve the current subscription
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
        """Cancel a subscription"""
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
        """Create a PaymentIntent for a one-time payment"""
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
        """Retrieve the details of a subscription"""
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
        """List a customer's invoices"""
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
        """Create a billing portal session"""
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
        """Construct and verify a webhook event"""
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            return event
        except ValueError:
            # Invalid payload
            return None
        except stripe.error.SignatureVerificationError:
            # Invalid signature
            return None

# Global instance of the Stripe client
stripe_client = StripeClient()

