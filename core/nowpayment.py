import requests
import hmac
import hashlib
import json
import logging
import time
from typing import Optional, Dict, Any, Union
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from .models import Deposit

logger = logging.getLogger(__name__)

class NOWPaymentsException(Exception):
    """Base exception for NOWPayments API errors"""
    pass

class APIError(NOWPaymentsException):
    """Exception raised for API-related errors"""
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[Dict] = None):
        self.status_code = status_code
        self.response = response
        super().__init__(message)

class NOWPaymentsAPI:
    """NOWPayments API Integration Class"""
    
    RATE_LIMIT_KEY = "nowpayments_rate_limit"
    RATE_LIMIT_REQUESTS = 10  # Maximum requests per window
    RATE_LIMIT_WINDOW = 60    # Window size in seconds
    
    # Payment status flow
    PAYMENT_STATUSES = {
        'waiting': 'Payment is waiting for customer funds',
        'confirming': 'Payment is being confirmed on blockchain',
        'confirmed': 'Payment is confirmed on blockchain',
        'sending': 'Payment is being sent to merchant wallet',
        'partially_paid': 'Customer sent less than expected',
        'finished': 'Payment is successfully processed',
        'failed': 'Payment failed',
        'refunded': 'Payment was refunded',
        'expired': 'Payment expired',
        'cancelled': 'Payment was cancelled'
    }
    
    FINAL_STATUSES = {'finished', 'failed', 'refunded', 'expired', 'cancelled'}
    SUCCESS_STATUSES = {'finished'}
    FAILED_STATUSES = {'failed', 'expired', 'cancelled'}

    def __init__(self):
        """Initialize the API client with settings from Django configuration"""
        config = settings.NOWPAYMENTS
        
        self.api_key = config['API_KEY']
        self.ipn_secret = config['IPN_SECRET']
        self.sandbox = config['SANDBOX']
        self.base_url = config['BASE_URL']
        self.min_amount = config['MIN_AMOUNT']
        self.max_amount = config['MAX_AMOUNT']
        self.supported_networks = config['SUPPORTED_NETWORKS']
        self.webhooks = config['WEBHOOKS']
        
        if not self.api_key:
            raise NOWPaymentsException("NOWPayments API key is not configured")
            
        self.session = requests.Session()
        self.session.headers.update({
            'x-api-key': self.api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def check_rate_limit(self) -> bool:
        """
        Check if we're within rate limits
        Returns: bool indicating if request can proceed
        """
        now = int(time.time())
        cache_key = f"{self.RATE_LIMIT_KEY}:{now // self.RATE_LIMIT_WINDOW}"
        
        # Get current request count
        request_count = cache.get(cache_key, 0)
        
        if request_count >= self.RATE_LIMIT_REQUESTS:
            return False
            
        # Increment request count
        cache.set(cache_key, request_count + 1, self.RATE_LIMIT_WINDOW)
        return True
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make an HTTP request to the NOWPayments API with rate limiting and error handling
        
        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint path
            data: Request data for GET params or POST body
            
        Returns:
            Dict containing the API response
            
        Raises:
            APIError: If the API request fails
            NOWPaymentsException: For other errors
        """
        if not self.check_rate_limit():
            raise NOWPaymentsException("Rate limit exceeded")
            
        url = f"{self.base_url}/{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(url, params=data, timeout=30)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data, timeout=30)
            else:
                raise NOWPaymentsException(f"Unsupported HTTP method: {method}")
                
            try:
                response_data = response.json()
            except ValueError:
                raise APIError(
                    "Invalid JSON response",
                    status_code=response.status_code,
                    response=response.text
                )
                
            if not response.ok:
                raise APIError(
                    response_data.get('message', 'Unknown API error'),
                    status_code=response.status_code,
                    response=response_data
                )
                
            return response_data
        except requests.exceptions.RequestException as e:
            # Network-level errors (connection, timeouts, etc.)
            raise APIError(f"Request failed: {str(e)}")
        except APIError:
            # Re-raise APIError as-is so callers can inspect status_code/response
            raise
        except Exception as e:
            # Any other unexpected errors
            raise NOWPaymentsException(f"Unexpected error: {str(e)}")

    def validate_amount(self, amount: Union[Decimal, float, str]) -> Decimal:
        """
        Validate payment amount against configured limits
        
        Args:
            amount: The amount to validate
            
        Returns:
            Decimal: The validated amount
            
        Raises:
            ValueError: If amount is invalid
        """
        try:
            amount = Decimal(str(amount))
        except (TypeError, ValueError):
            raise ValueError("Invalid amount format")
            
        if amount < self.min_amount:
            raise ValueError(f"Amount must be at least {self.min_amount}")
        if amount > self.max_amount:
            raise ValueError(f"Amount cannot exceed {self.max_amount}")
            
        return amount

    def validate_currency(self, currency: str) -> str:
        """
        Validate cryptocurrency code
        
        Args:
            currency: Cryptocurrency code to validate
            
        Returns:
            str: Normalized currency code
            
        Raises:
            ValueError: If currency is not supported
        """
        if not currency:
            raise ValueError("Cryptocurrency must be selected")
            
        currency = str(currency).strip().lower()
        if currency not in self.supported_networks:
            raise ValueError(
                f"Unsupported cryptocurrency: {currency}. "
                f"Supported: {', '.join(self.supported_networks.keys())}"
            )
        return currency

    def create_payment(self, amount: Union[Decimal, float, str], user=None, 
                      currency_from: str = "usd", currency_to: str = "btc") -> Dict[str, Any]:
        """
        Create a new payment request with improved validation and error handling
        
        Args:
            amount: Amount in currency_from
            user: User making the deposit
            currency_from: Source currency (default: usd)
            currency_to: Target cryptocurrency (default: btc)
            
        Returns:
            Dict containing payment details including payment_id and pay_address
            
        Raises:
            ValueError: For validation errors
            APIError: For API-related errors
            NOWPaymentsException: For other errors
        """
        try:
            # Validate inputs
            amount = self.validate_amount(amount)
            currency_to = self.validate_currency(currency_to)

            # Currency has already been validated against configured supported_networks
            # by validate_currency(). Rely on settings.NOWPAYMENTS['SUPPORTED_NETWORKS']
            # instead of querying external market-info here.

            # Determine what value to send as pay_currency to NOWPayments.
            # Allow an explicit mapping in settings.NOWPAYMENTS['SUPPORTED_NETWORKS']
            # so keys (used for validation/UI) can map to the API identifier if needed.
            details = self.supported_networks.get(currency_to)
            pay_currency_value = currency_to
            if isinstance(details, dict):
                # supported_networks entry can provide an explicit API value
                pay_currency_value = (
                    details.get('pay_currency') or
                    details.get('api_value') or
                    details.get('symbol') or
                    pay_currency_value
                )

            # Prepare payment data
            data = {
                "price_amount": float(amount),
                "price_currency": currency_from.lower(),
                "pay_currency": pay_currency_value,
                "ipn_callback_url": self.webhooks['IPN_CALLBACK_URL'],
                "success_url": self.webhooks['SUCCESS_URL'],
                "cancel_url": self.webhooks['CANCEL_URL'],
                "order_description": f"Deposit of {amount} {currency_from.upper()}",
                "is_fee_paid_by_user": True  # User pays network fees
            }
            if pay_currency_value != currency_to:
                logger.debug(f"Mapped pay_currency '{currency_to}' -> '{pay_currency_value}' using settings mapping")
            
            # Create payment
            result = self._make_request('POST', 'payment', data)
            
            # Create deposit record if user provided
            if user and result.get('payment_id'):
                deposit = Deposit.objects.create(
                    user=user,
                    amount=amount,
                    payment_id=result['payment_id'],
                    pay_address=result['pay_address'],
                    pay_amount=Decimal(str(result['pay_amount'])),
                    pay_currency=currency_to,
                    payment_status=result['payment_status']
                )
                result['deposit_id'] = deposit.deposit_id
                
            logger.info(
                f"Created payment {result.get('payment_id')} for "
                f"{amount} {currency_from} -> {currency_to}"
            )
            return result
            
        except APIError as e:
            # Log API response details to help diagnose 4xx/5xx errors
            logger.error(
                f"NOWPayments APIError while creating payment: {e} | status={getattr(e, 'status_code', None)} | response={getattr(e, 'response', None)}",
                exc_info=True
            )
            raise
        except Exception as e:
            logger.error(f"Failed to create payment: {e}", exc_info=True)
            raise

    def verify_ipn_request(self, request_data: Dict[str, Any], nowpayments_sig: str) -> bool:
        """
        Verify the authenticity of an IPN request using HMAC-SHA512
        
        Args:
            request_data: The IPN payload to verify
            nowpayments_sig: The X-NOWPAYMENTS-SIG header value
            
        Returns:
            bool: True if signature is valid, False otherwise
            
        Raises:
            NOWPaymentsException: If verification fails due to an error
        """
        if not self.ipn_secret:
            raise NOWPaymentsException("IPN secret key not configured")
            
        if not nowpayments_sig:
            logger.warning("Missing NOWPayments signature")
            return False
            
        try:
            # Sort the data and create a canonical string
            sorted_data = json.dumps(request_data, separators=(',', ':'), sort_keys=True)
            
            # Create HMAC signature
            signature = hmac.new(
                self.ipn_secret.encode('utf-8'),
                sorted_data.encode('utf-8'),
                hashlib.sha512
            ).hexdigest()
            
            # Compare signatures using constant-time comparison
            is_valid = hmac.compare_digest(signature, nowpayments_sig)
            
            log_msg = "IPN signature verification: {}"
            if is_valid:
                logger.info(log_msg.format("success"))
            else:
                logger.warning(log_msg.format("failed"))
                logger.debug(f"Expected: {signature}")
                logger.debug(f"Received: {nowpayments_sig}")
                
            return is_valid
            
        except Exception as e:
            logger.error(f"Failed to verify IPN signature: {str(e)}", exc_info=True)
            raise NOWPaymentsException(f"IPN verification failed: {str(e)}")

    def process_ipn_payment(self, payment_data: Dict[str, Any]) -> Optional[Deposit]:
        """
        Process IPN payment notification with improved validation and status handling
        
        Args:
            payment_data: Payment data from IPN webhook
            
        Returns:
            Optional[Deposit]: Updated deposit object or None if not found
            
        Raises:
            NOWPaymentsException: For processing errors
        """
        try:
            payment_id = payment_data.get('payment_id')
            if not payment_id:
                raise NOWPaymentsException("Missing payment_id in IPN data")
                
            payment_status = payment_data.get('payment_status')
            if not payment_status:
                raise NOWPaymentsException("Missing payment_status in IPN data")
                
            # Get deposit and lock for update
            from django.db import transaction
            with transaction.atomic():
                deposit = (Deposit.objects
                         .select_for_update()
                         .filter(payment_id=payment_id)
                         .first())
                
                if not deposit:
                    logger.error(f"No deposit found for payment_id: {payment_id}")
                    return None
                    
                # Validate status transition
                if payment_status not in self.PAYMENT_STATUSES:
                    logger.warning(f"Invalid payment status received: {payment_status}")
                    return deposit
                    
                # Use the centralized model helper to apply the payment status mapping
                old_status = deposit.payment_status
                try:
                    deposit.apply_payment_status(payment_status, actually_paid=payment_data.get('actually_paid', None))
                except Exception as e:
                    logger.error(f"Failed to apply payment status for deposit {deposit.deposit_id}: {e}", exc_info=True)
                    raise

                # Log status change
                logger.info(
                    f"Payment {payment_id} status updated: {old_status} -> {payment_status}. "
                    f"Deposit status: {deposit.status}"
                )

                return deposit
                
        except Exception as e:
            logger.error(f"Failed to process IPN payment: {str(e)}", exc_info=True)
            raise NOWPaymentsException(f"IPN processing failed: {str(e)}")

    def get_payment_status(self, payment_id: str) -> Dict[str, Any]:
        """
        Get detailed payment status with caching
        
        Args:
            payment_id: The payment ID to check
            
        Returns:
            Dict containing payment status details
            
        Raises:
            APIError: For API-related errors
            NOWPaymentsException: For other errors
        """
        cache_key = f"nowpayments_payment_{payment_id}"
        cached_status = cache.get(cache_key)
        
        try:
            # Return cached status for completed payments
            if cached_status and cached_status.get('payment_status') in self.FINAL_STATUSES:
                logger.debug(f"Returning cached status for payment {payment_id}")
                return cached_status
                
            # Get fresh status from API
            result = self._make_request('GET', f'payment/{payment_id}')
            
            # Cache the result (short TTL for pending, longer for final)
            if result.get('payment_status') in self.FINAL_STATUSES:
                cache_timeout = 86400  # 24 hours for final statuses
            else:
                cache_timeout = 300    # 5 minutes for pending statuses
                
            cache.set(cache_key, result, timeout=cache_timeout)
            
            logger.info(
                f"Payment {payment_id} status: {result.get('payment_status')} "
                f"(cached for {cache_timeout}s)"
            )
            return result
            
        except Exception as e:
            if cached_status:
                logger.warning(
                    f"Failed to get fresh status for {payment_id}, "
                    f"returning cached: {str(e)}"
                )
                return cached_status
            raise

    def get_currencies(self) -> Dict[str, Any]:
        """
        Get list of all supported cryptocurrencies from NOWPayments with caching
        
        Returns:
            Dict containing available cryptocurrencies and their details
            
        Raises:
            APIError: For API-related errors
            NOWPaymentsException: For other errors
        """
        cache_key = "nowpayments_currencies"
        cached_currencies = cache.get(cache_key)
        
        if cached_currencies:
            logger.debug("Returning cached currencies list")
            return cached_currencies
            
        try:
            result = self._make_request('GET', 'currencies')
            
            # Cache for 1 hour
            cache.set(cache_key, result, timeout=3600)
            
            logger.info("Retrieved and cached supported currencies list")
            return result
            
        except Exception as e:
            logger.error(f"Failed to get currencies list: {str(e)}", exc_info=True)
            if cached_currencies:
                logger.warning("Returning cached currencies due to error")
                return cached_currencies
            raise

    def get_supported_currencies(self) -> Dict[str, Dict[str, str]]:
        """
        Get list of cryptocurrencies specifically supported by this integration
        with network information
        
        Returns:
            Dict containing supported cryptocurrencies configuration
        """
        return self.supported_networks
    

    def estimate_exchange_rate(self, amount: Union[Decimal, float, str],
                             currency_from: str = "usd",
                             currency_to: str = "btc") -> Dict[str, Any]:
        """
        Get current exchange rate with improved caching and validation
        
        Args:
            amount: Amount to exchange
            currency_from: Source currency code
            currency_to: Target cryptocurrency code
            
        Returns:
            Dict containing exchange rate details
            
        Raises:
            ValueError: For validation errors
            APIError: For API-related errors
            NOWPaymentsException: For other errors
        """
        try:
            amount = self.validate_amount(amount)
            currency_to = self.validate_currency(currency_to)
            
            cache_key = f"nowpayments_rate_{currency_from}_{currency_to}_{amount}"
            cached_rate = cache.get(cache_key)
            
            if cached_rate:
                age = time.time() - cached_rate['timestamp']
                if age < 300:  # Use cache if less than 5 minutes old
                    logger.debug(f"Returning cached rate ({age:.1f}s old)")
                    return cached_rate['data']
                    
            data = {
                "amount": float(amount),
                "currency_from": currency_from.lower(),
                "currency_to": currency_to.lower()
            }
            
            result = self._make_request('GET', 'estimate', data)
            
            # Cache for 5 minutes
            cache.set(cache_key, {
                'timestamp': time.time(),
                'data': result
            }, timeout=300)
            
            logger.info(
                f"Got exchange rate: {amount} {currency_from} -> "
                f"{result.get('estimated_amount')} {currency_to}"
            )
            return result
            
        except Exception as e:
            logger.error(f"Failed to get exchange rate: {str(e)}", exc_info=True)
            if cached_rate:
                logger.warning("Returning cached rate due to error")
                return cached_rate['data']
            raise

    def estimate_price(self, amount, currency_from="usd", currency_to="btc"):
        """
        Get estimated price for the crypto payment
        
        Args:
            amount (Decimal): Amount in currency_from
            currency_from (str): Source currency (default: usd)
            currency_to (str): Target cryptocurrency (default: btc)
            
        Returns:
            dict: Estimated price details including estimated_amount
        """
        try:
            # Validate the currency first
            currency_to = self.validate_currency(currency_to)
            
            data = {
                "amount": float(amount),
                "currency_from": currency_from.lower(),
                "currency_to": currency_to
            }
            
            result = self._make_request('GET', 'estimate', data)
            logger.info(f"Got price estimate: {amount} {currency_from} to {currency_to}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to get price estimate: {e}")
            raise