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

// ─── Lastik Saklama — Üç Nokta Menü ───────────────────────
(function() {
    'use strict';

    function acilirMenuKapat() {
        document.querySelectorAll('.acilir-menu').forEach(function(m) {
            m.style.display = 'none';
        });
    }

    function acilirMenuAc(btn, menuId) {
        var menu = document.getElementById(menuId);
        if (!menu) return;
        var isOpen = menu.style.display === 'block';
        acilirMenuKapat();
        if (isOpen) return;
        var rect = btn.getBoundingClientRect();
        var menuW = 230;
        var menuH = 320;
        var top  = rect.bottom + window.scrollY + 4;
        var left = rect.right  + window.scrollX - menuW;
        if (left < 8) left = 8;
        if (rect.bottom + menuH > window.innerHeight) {
            top = rect.top + window.scrollY - menuH - 4;
        }
        menu.style.position = 'absolute';
        menu.style.top  = top  + 'px';
        menu.style.left = left + 'px';
        menu.style.display = 'block';
    }

    // Butonlara event ekle (delegated — dinamik içerik için)
    document.addEventListener('click', function(e) {
        var btn = e.target.closest('.acilir-menu-btn');
        if (btn) {
            var menuId = 'menu-' + btn.getAttribute('data-kayit');
            acilirMenuAc(btn, menuId);
            e.stopPropagation();
        } else if (!e.target.closest('.acilir-menu')) {
            acilirMenuKapat();
        }
    });
})();
