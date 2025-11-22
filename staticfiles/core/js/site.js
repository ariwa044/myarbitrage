// UI Components and Behaviors
class UIManager {
    constructor() {
        // Component references
        this.navbar = document.getElementById('navbar');
        this.mobileMenuBtn = document.getElementById('mobileMenuBtn');
        this.navLinks = document.querySelector('.nav-links');
        this.navButtons = document.querySelector('.nav-buttons');
        this.languageSelect = document.getElementById('languageSelect');
        
        // State
        this.isMenuOpen = false;
        
        // Bind methods
        this.onScroll = this.onScroll.bind(this);
        this.toggleMobileMenu = this.toggleMobileMenu.bind(this);
        this.handleClickOutside = this.handleClickOutside.bind(this);
    }

    init() {
        this.initIcons();
        this.setupEventListeners();
        this.initSmoothScroll();
        this.onScroll(); // Set initial navbar state
    }

    initIcons() {
        // Initialize Lucide icons if available
        if (typeof lucide !== 'undefined' && lucide?.createIcons) {
            try {
                lucide.createIcons();
            } catch (e) {
                console.warn('Failed to initialize Lucide icons:', e);
            }
        }
    }

    setupEventListeners() {
        // Navbar scroll effect
        window.addEventListener('scroll', this.onScroll, { passive: true });

        // Mobile menu
        if (this.mobileMenuBtn) {
            this.mobileMenuBtn.addEventListener('click', this.toggleMobileMenu);
            document.addEventListener('click', this.handleClickOutside);
        }

        // Language selector
        if (this.languageSelect) {
            this.languageSelect.addEventListener('change', this.handleLanguageChange.bind(this));
        }
    }

    onScroll() {
        if (!this.navbar) return;
        
        if (window.scrollY > 10) {
            this.navbar.classList.add('scrolled');
        } else {
            this.navbar.classList.remove('scrolled');
        }
    }

    toggleMobileMenu(event) {
        event?.stopPropagation();
        
        if (!this.navLinks || !this.navButtons) return;

        this.isMenuOpen = !this.isMenuOpen;
        const display = this.isMenuOpen ? 'flex' : 'none';
        
        this.navLinks.style.display = display;
        this.navButtons.style.display = display;
        
        // Update button state
        this.mobileMenuBtn?.classList.toggle('active');
        
        // Add/remove body scroll lock
        document.body.style.overflow = this.isMenuOpen ? 'hidden' : '';
    }

    handleClickOutside(event) {
        if (this.isMenuOpen && 
            !this.mobileMenuBtn?.contains(event.target) && 
            !this.navLinks?.contains(event.target) && 
            !this.navButtons?.contains(event.target)) {
            this.toggleMobileMenu();
        }
    }

    handleLanguageChange(event) {
        const selectedOption = event.target.options[event.target.selectedIndex];
        const currentUrl = new URL(window.location.href);
        
        // Update language parameter
        currentUrl.searchParams.set('lang', event.target.value);
        
        // Redirect to new URL
        window.location.href = currentUrl.toString();
    }

    initSmoothScroll() {
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', (e) => {
                const targetId = anchor.getAttribute('href');
                const target = document.querySelector(targetId);
                
                if (!target) return; // Allow normal link behavior
                
                e.preventDefault();
                target.scrollIntoView({ 
                    behavior: 'smooth',
                    block: 'start'
                });
                
                // Update URL without reload
                history.pushState(null, '', targetId);
            });
        });
    }
}

// Theme management
class ThemeManager {
    constructor() {
        this.theme = localStorage.getItem('theme') || 'light';
    }

    init() {
        this.applyTheme();
        this.setupThemeToggle();
    }

    applyTheme() {
        document.documentElement.setAttribute('data-theme', this.theme);
        document.body.classList.toggle('dark-mode', this.theme === 'dark');
    }

    setupThemeToggle() {
        const toggle = document.getElementById('themeToggle');
        if (!toggle) return;

        toggle.addEventListener('click', () => {
            this.theme = this.theme === 'light' ? 'dark' : 'light';
            localStorage.setItem('theme', this.theme);
            this.applyTheme();
        });
    }
}

// Initialize everything on page load
document.addEventListener('DOMContentLoaded', () => {
    const ui = new UIManager();
    const theme = new ThemeManager();
    
    ui.init();
    theme.init();
});
