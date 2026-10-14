// Dropdown Initialization
(function() {
    'use strict';
    
    function initDropdowns() {
        if (typeof bootstrap === 'undefined' || !bootstrap.Dropdown) {
            console.warn('Bootstrap Dropdown not available');
            return;
        }
        
        // Tüm dropdown butonlarını bul ve başlat
        const dropdownElements = document.querySelectorAll('[data-bs-toggle="dropdown"]');
        
        dropdownElements.forEach(function(element) {
            try {
                // Eğer zaten başlatılmışsa, yeniden başlatma
                if (!bootstrap.Dropdown.getInstance(element)) {
                    new bootstrap.Dropdown(element);
                    console.log('Dropdown initialized:', element.id || element.className);
                }
            } catch (error) {
                console.error('Error initializing dropdown:', error);
            }
        });
        
        console.log('Total dropdowns initialized:', dropdownElements.length);
    }
    
    // DOM yüklendiğinde başlat
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initDropdowns);
    } else {
        initDropdowns();
    }
    
    // Biraz gecikmeyle tekrar dene (custom JS yüklendikten sonra)
    setTimeout(initDropdowns, 500);
})();
