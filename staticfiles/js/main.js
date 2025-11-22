// Constants
const TOAST_DURATION = 5000;
const AJAX_TIMEOUT = 30000;

// Loading overlay management
const loadingOverlay = {
    init: function() {
        if (!document.getElementById('loading-overlay')) {
            const overlay = document.createElement('div');
            overlay.id = 'loading-overlay';
            overlay.classList.add('d-none');
            overlay.innerHTML = `
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            `;
            document.body.appendChild(overlay);
        }
    },
    show: function() {
        document.getElementById('loading-overlay')?.classList.remove('d-none');
    },
    hide: function() {
        document.getElementById('loading-overlay')?.classList.add('d-none');
    }
};

// Utilities
const utils = {
    formatCurrency: function(amount, currency = 'USD') {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency
        }).format(amount);
    },
    
    formatCrypto: function(amount) {
        return parseFloat(amount).toFixed(8);
    },
    
    formatDate: function(date) {
        return new Date(date).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    },
    
    copyToClipboard: async function(text) {
        try {
            await navigator.clipboard.writeText(text);
            this.showToast('Copied to clipboard!');
            return true;
        } catch (err) {
            console.error('Failed to copy:', err);
            return false;
        }
    },

    showToast: function(message, type = 'success') {
        const toast = document.createElement('div');
        toast.classList.add('toast', `toast-${type}`);
        toast.textContent = message;
        document.body.appendChild(toast);
        
        setTimeout(() => toast.classList.add('show'), 100);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
};

// Form validation and handling
const forms = {
    validate: function(form) {
        const inputs = form.querySelectorAll('input, select, textarea');
        let isValid = true;

        inputs.forEach(input => {
            if (input.hasAttribute('required') && !input.value.trim()) {
                isValid = false;
                this.showError(input);
            }
        });

        return isValid;
    },

    showError: function(input) {
        input.classList.add('error');
        const errorMessage = input.getAttribute('data-error') || 'This field is required';
        
        let errorElement = input.nextElementSibling;
        if (!errorElement?.classList.contains('error-message')) {
            errorElement = document.createElement('div');
            errorElement.classList.add('error-message');
            input.parentNode.insertBefore(errorElement, input.nextSibling);
        }
        errorElement.textContent = errorMessage;
    },

    clearError: function(input) {
        input.classList.remove('error');
        const errorElement = input.nextElementSibling;
        if (errorElement?.classList.contains('error-message')) {
            errorElement.remove();
        }
    },

    handleSubmit: async function(form, options = {}) {
        if (!this.validate(form)) return;

        loadingOverlay.show();
        const submitBtn = form.querySelector('[type="submit"]');
        const originalText = submitBtn?.textContent;
        
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = 'Processing...';
        }

        try {
            const response = await fetch(form.action, {
                method: form.method,
                body: new FormData(form),
                headers: {
                    'X-CSRFToken': getCsrfToken()
                }
            });

            const data = await response.json();
            if (options.onSuccess) options.onSuccess(data);
        } catch (error) {
            console.error('Form submission error:', error);
            if (options.onError) options.onError(error);
        } finally {
            loadingOverlay.hide();
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
            }
        }
    }
};

// CSRF token management
function getCsrfToken() {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, 'csrftoken'.length + 1) === ('csrftoken=')) {
                cookieValue = decodeURIComponent(cookie.substring('csrftoken'.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Initialize everything
document.addEventListener('DOMContentLoaded', function() {
    // Initialize loading overlay
    loadingOverlay.init();
    
    // Auto-dismiss alerts (only if Bootstrap is loaded)
    if (typeof bootstrap !== 'undefined') {
        setTimeout(function() {
            document.querySelectorAll('.alert').forEach(function(alert) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            });
        }, TOAST_DURATION);
    }

    // Initialize forms
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', (e) => {
            if (!forms.validate(form)) {
                e.preventDefault();
            }
        });

        form.addEventListener('input', (e) => {
            if (['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName)) {
                forms.clearError(e.target);
            }
        });
    });
});

// Set up AJAX defaults (only if jQuery is loaded)
if (typeof jQuery !== 'undefined') {
    jQuery.ajaxSetup({
        timeout: AJAX_TIMEOUT,
        beforeSend: function(xhr, settings) {
            if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", getCsrfToken());
            }
        }
    });
}

// Export utilities for use in other scripts
window.utils = utils;
window.forms = forms;
window.loadingOverlay = loadingOverlay;
