let paymentCheckInterval;
const POLL_INTERVAL = 30000; // 30 seconds
const MAX_RETRIES = 20; // 10 minutes total

class DepositManager {
    constructor() {
        this.form = document.getElementById('depositForm');
        this.currencySelect = document.getElementById('crypto_currency');
        this.amountInput = document.getElementById('amount');
        this.estimateDisplay = document.getElementById('estimate');
        this.addressDisplay = document.getElementById('payment_address');
        this.qrCodeDisplay = document.getElementById('qr_code');
        this.retryCount = 0;
    }

    init() {
        this.loadCryptoCurrencies();
        this.setupEventListeners();
    }

    async loadCryptoCurrencies() {
        try {
            const response = await fetch('/crypto/currencies/');
            const data = await response.json();
            
            if (data.success) {
                data.currencies.forEach(currency => {
                    const option = new Option(currency.toUpperCase(), currency);
                    this.currencySelect.add(option);
                });
            }
        } catch (error) {
            console.error('Failed to load cryptocurrencies:', error);
            utils.showToast('Failed to load cryptocurrencies', 'error');
        }
    }

    setupEventListeners() {
        // Handle form submission
        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.createDeposit();
        });

        // Update estimate when amount or currency changes
        [this.amountInput, this.currencySelect].forEach(el => 
            el.addEventListener('change', () => this.updateEstimate()));
            
        // Copy address to clipboard
        this.addressDisplay?.addEventListener('click', () => {
            if (this.addressDisplay.textContent) {
                utils.copyToClipboard(this.addressDisplay.textContent);
            }
        });
    }

    async updateEstimate() {
        const amount = this.amountInput.value;
        const currency = this.currencySelect.value;

        if (!amount || !currency) return;

        try {
            loadingOverlay.show();
            const response = await fetch(`/crypto/estimate/?amount=${amount}&currency=${currency}`);
            const data = await response.json();
            
            if (data.success) {
                this.estimateDisplay.textContent = utils.formatCrypto(data.estimate);
            } else {
                throw new Error(data.message || 'Failed to get estimate');
            }
        } catch (error) {
            console.error('Failed to update estimate:', error);
            utils.showToast(error.message || 'Failed to update estimate', 'error');
        } finally {
            loadingOverlay.hide();
        }
    }

    async createDeposit() {
        try {
            loadingOverlay.show();
            const formData = new FormData(this.form);
            
            const response = await fetch('/deposit/create/', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': getCsrfToken()
                }
            });

            const data = await response.json();
            
            if (data.success) {
                this.handleSuccessfulDeposit(data);
            } else {
                throw new Error(data.message || 'Failed to create deposit');
            }
        } catch (error) {
            console.error('Failed to create deposit:', error);
            utils.showToast(error.message || 'Failed to create deposit', 'error');
        } finally {
            loadingOverlay.hide();
        }
    }

    handleSuccessfulDeposit(data) {
        // Update UI
        this.addressDisplay.textContent = data.payment_address;
        this.qrCodeDisplay.src = data.qr_code_url;
        
        // Show success message
        utils.showToast('Deposit created successfully');
        
        // Start checking payment status
        this.startPaymentCheck(data.payment_id);
        
        // Update form state
        this.form.classList.add('payment-pending');
        this.form.querySelectorAll('input, select, button').forEach(el => el.disabled = true);
    }

    startPaymentCheck(paymentId) {
        clearInterval(paymentCheckInterval);
        this.retryCount = 0;
        
        paymentCheckInterval = setInterval(async () => {
            try {
                const response = await fetch(`/deposit/status/${paymentId}/`);
                const data = await response.json();
                
                if (data.success) {
                    if (data.status === 'completed') {
                        this.handlePaymentSuccess();
                        clearInterval(paymentCheckInterval);
                    }
                }
                
                this.retryCount++;
                if (this.retryCount >= MAX_RETRIES) {
                    clearInterval(paymentCheckInterval);
                    utils.showToast('Payment check timed out. Please contact support.', 'warning');
                }
            } catch (error) {
                console.error('Failed to check payment status:', error);
            }
        }, POLL_INTERVAL);
    }

    handlePaymentSuccess() {
        utils.showToast('Payment received successfully!', 'success');
        setTimeout(() => window.location.href = '/dashboard/', 2000);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    const depositManager = new DepositManager();
    depositManager.init();
});

// ... Add remaining JavaScript functions for deposit handling ...
