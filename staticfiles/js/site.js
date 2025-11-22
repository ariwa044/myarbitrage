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
            // Close on Escape
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && this.isMenuOpen) {
                    this.toggleMobileMenu();
                }
            });
        }

        // Close mobile menu when clicking nav links
        if (this.navLinks) {
            this.navLinks.querySelectorAll('a').forEach(link => {
                link.addEventListener('click', (e) => {
                    // Don't close if link is a dropdown toggle or anchor to a local page section
                    if (link.classList.contains('dropdown-toggle') || link.getAttribute('href') === '#') return;
                    if (this.isMenuOpen) this.toggleMobileMenu();
                });
            });
        }
        if (this.navButtons) {
            this.navButtons.querySelectorAll('a').forEach(link => {
                link.addEventListener('click', (e) => {
                    // Don't close if link is a dropdown toggle or anchor to a local page section
                    if (link.classList.contains('dropdown-toggle') || link.getAttribute('href') === '#') return;
                    if (this.isMenuOpen) this.toggleMobileMenu();
                });
            });
        }

        // Language selector
        if (this.languageSelect) {
            this.languageSelect.addEventListener('change', this.handleLanguageChange.bind(this));
        }

        // Dropdowns: make dropdown toggle work well on mobile (tap to expand, chevron rotate)
        const dropdownToggles = Array.from(document.querySelectorAll('.dropdown-toggle'));
        dropdownToggles.forEach(toggle => {
            toggle.addEventListener('click', (e) => {
                // On mobile, use custom toggle behavior to ensure tap opens/toggles dropdown
                if (window.innerWidth <= 768) {
                    e.preventDefault();
                    const parent = toggle.closest('.dropdown');
                    if (!parent) return;

                    const isOpen = parent.classList.contains('show');
                    // Close other open dropdowns
                    document.querySelectorAll('.dropdown.show').forEach(d => {
                        if (d !== parent) {
                            d.classList.remove('show');
                            const t = d.querySelector('.dropdown-toggle');
                            t?.setAttribute('aria-expanded', 'false');
                            d.querySelector('.dropdown-chevron')?.classList.remove('rotate');
                        }
                    });

                    if (isOpen) {
                        parent.classList.remove('show');
                        toggle.setAttribute('aria-expanded', 'false');
                        toggle.querySelector('.dropdown-chevron')?.classList.remove('rotate');
                    } else {
                        parent.classList.add('show');
                        toggle.setAttribute('aria-expanded', 'true');
                        toggle.querySelector('.dropdown-chevron')?.classList.add('rotate');
                    }
                }
            });
        });

        // Close dropdown when a dropdown item is clicked (useful in mobile)
        const dropdownItems = Array.from(document.querySelectorAll('.dropdown-menu .dropdown-item'));
        dropdownItems.forEach(item => {
            item.addEventListener('click', (e) => {
                // find parent dropdown and close
                const parent = item.closest('.dropdown');
                if (parent) {
                    parent.classList.remove('show');
                    const t = parent.querySelector('.dropdown-toggle');
                    t?.setAttribute('aria-expanded', 'false');
                    parent.querySelector('.dropdown-chevron')?.classList.remove('rotate');
                }
            });
        });
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

        this.navLinks.classList.toggle('mobile-menu-open', this.isMenuOpen);
        this.navButtons.classList.toggle('mobile-menu-open', this.isMenuOpen);

        // Update button aria-expanded and state
        this.mobileMenuBtn?.setAttribute('aria-expanded', String(this.isMenuOpen));
        this.mobileMenuBtn?.classList.toggle('active', this.isMenuOpen);
        const icon = this.mobileMenuBtn?.querySelector('i');
        if (icon) {
            icon.classList.toggle('fa-bars', !this.isMenuOpen);
            icon.classList.toggle('fa-times', this.isMenuOpen);
        }

        // Add/remove body scroll lock
        document.body.style.overflow = this.isMenuOpen ? 'hidden' : '';
    }

    handleClickOutside(event) {
        // Close mobile menu if open and click is outside
        if (this.isMenuOpen && 
            !this.mobileMenuBtn?.contains(event.target) && 
            !this.navLinks?.contains(event.target) && 
            !this.navButtons?.contains(event.target)) {
            this.toggleMobileMenu();
        }

        // Close any open dropdowns if click outside of them
        document.querySelectorAll('.dropdown.show').forEach(d => {
            if (!d.contains(event.target)) {
                d.classList.remove('show');
                const t = d.querySelector('.dropdown-toggle');
                t?.setAttribute('aria-expanded', 'false');
                d.querySelector('.dropdown-chevron')?.classList.remove('rotate');
            }
        });
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
