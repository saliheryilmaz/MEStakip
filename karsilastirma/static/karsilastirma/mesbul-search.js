(() => {
    const form = document.getElementById('mesbul-search-form');
    if (!form) return;
    const size = form.elements.ebat;
    const brand = form.elements.marka;
    const season = form.elements.mevsim;

    document.querySelectorAll('.mesbul-history-item').forEach((item) => {
        item.addEventListener('click', () => {
            size.value = item.dataset.ebat;
            brand.value = "";
            season.value = "";
            form.elements.min_dot.value = "";
            size.focus();
        });
    });

    form.addEventListener('submit', () => {
        const raw = size.value.trim();
        if (!/^\d{3}\/\d{2}R\d{2}[A-Z]?$/i.test(raw)) {
            const digits = raw.replace(/\D/g, '');
            const compact = raw.match(/^(\d{3})(\d{2})R(\d{2}[A-Z]?)$/i);
            if (compact) size.value = `${compact[1]}/${compact[2]}R${compact[3].toUpperCase()}`;
            else if (digits.length === 7) size.value = `${digits.slice(0, 3)}/${digits.slice(3, 5)}R${digits.slice(5)}`;
            else size.value = raw;
        }
        document.getElementById('mesbul-search-submit').disabled = true;
        document.getElementById('mesbul-search-status').textContent = 'Toptancılar sorgulanıyor…';
    });
    window.addEventListener('pageshow', () => {
        document.getElementById('mesbul-search-submit').disabled = false;
        document.getElementById('mesbul-search-status').textContent = '';
    });
})();

(() => {
    const viewport = document.querySelector('.mesbul-supplier-viewport');
    if (!viewport) return;
    const toggle = document.querySelector('.mesbul-motion-toggle');
    const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
    let paused = false;
    let direction = 1;
    let position = 0;
    let lastFrame;

    function updateToggle() {
        toggle.hidden = reducedMotion.matches || viewport.scrollWidth <= viewport.clientWidth;
        toggle.setAttribute('aria-label', paused ? 'Toptancı şeridini oynat' : 'Toptancı şeridini duraklat');
        toggle.firstElementChild.className = paused ? 'bi bi-play-fill' : 'bi bi-pause-fill';
    }

    toggle.addEventListener('click', () => {
        paused = !paused;
        updateToggle();
    });
    reducedMotion.addEventListener('change', updateToggle);
    new ResizeObserver(updateToggle).observe(viewport);
    updateToggle();

    function animate(now) {
        const elapsed = Math.min(now - (lastFrame ?? now), 50);
        lastFrame = now;
        const end = viewport.scrollWidth - viewport.clientWidth;
        if (!paused && !reducedMotion.matches && end > 0 && !viewport.matches(':hover, :focus-within')) {
            if (Math.abs(position - viewport.scrollLeft) > 1) position = viewport.scrollLeft;
            position = Math.max(0, Math.min(end, position + direction * elapsed * 0.024));
            if (position === end) direction = -1;
            if (position === 0) direction = 1;
            viewport.scrollLeft = position;
        }
        requestAnimationFrame(animate);
    }
    requestAnimationFrame(animate);
})();
