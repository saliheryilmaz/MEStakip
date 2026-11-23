(() => {
    const results = document.querySelector('.mesbul-sonuclar');
    const quoteLink = document.getElementById('mesbul-open-quotation');
    const feedback = document.getElementById('mesbul-action-feedback');
    let feedbackTimer;
    const key = results.dataset.quoteKey;
    const orderDialog = document.getElementById('mesbul-order-dialog');
    const orderForm = orderDialog.querySelector('form');
    const orderQuantity = orderForm.elements.adet;
    const orderTotal = document.getElementById('mesbul-order-total');

    function updateOrderTotal() {
        const price = Number(orderForm.elements.birim_fiyat.value);
        orderTotal.textContent = orderQuantity.validity.valid
            ? formatMesbulPrice(orderQuantity.valueAsNumber * price)
            : '—';
    }

    orderQuantity.addEventListener('input', updateOrderTotal);
    orderDialog.querySelector('[data-order-cancel]').addEventListener('click', () => orderDialog.close());

    function notify(message) {
        feedback.textContent = message;
        window.clearTimeout(feedbackTimer);
        feedbackTimer = window.setTimeout(() => { feedback.textContent = ''; }, 3500);
    }

    function readDraft() {
        const items = JSON.parse(sessionStorage.getItem(key) || '[]');
        return Array.isArray(items) ? items : [];
    }

    window.addEventListener('pageshow', () => {
        try {
            updateQuoteLink(readDraft().length);
        } catch {
            updateQuoteLink(0);
        }
    });

    function updateQuoteLink(count) {
        quoteLink.hidden = count === 0;
        quoteLink.textContent = count ? `Teklifi aç (${count})` : '';
    }

    results.addEventListener('click', (event) => {
        const button = event.target.closest('.mesbul-row-actions :is([data-action="quote"], [data-action="note"], [data-order-trigger])');
        if (!button || button.disabled) return;
        const action = button.closest('.mesbul-row-actions').dataset;
        const product = button.closest('.data-row, .m-card').dataset;
        const dot = product.dot === '0' ? '' : product.dot;

        if (button.dataset.action === 'note') {
            satirNotAc(action.toptanci, product.marka, action.urun, dot, action.fiyatMetni);
            return;
        }

        const price = Number(product.fiyat);
        const isOrder = button.hasAttribute('data-order-trigger');
        if (!Number.isFinite(price) || price <= 0) {
            notify(isOrder ? 'Bu ürünün sipariş için geçerli bir fiyatı yok.' : 'Bu ürünün teklif için geçerli bir fiyatı yok.');
            return;
        }

        const season = { 'Yaz': 'yaz', 'Kış': 'kis', '4 Mevsim': 'dort-mevsim' }[mesbulSeason(product.mevsim)] || '';
        const size = results.dataset.ebat;
        const model = action.urun.toUpperCase().includes(size.toUpperCase()) ? action.urun : `${size} ${action.urun}`;

        if (isOrder) {
            const stock = Number(product.stok);
            if (!Number.isInteger(stock) || stock < 1) {
                notify('Bu ürün için stok bilgisi bulunamadı.');
                return;
            }
            orderForm.reset();
            orderForm.elements.cari_firma.value = action.toptanci || '';
            orderForm.elements.marka.value = product.marka.slice(0, 100);
            orderForm.elements.urun.value = model.slice(0, 300);
            orderForm.elements.mevsim.value = season;
            orderForm.elements.birim_fiyat.value = price.toFixed(2);
            orderForm.elements.aciklama.value = [
                action.toptanci && `Toptancı: ${action.toptanci}`,
                dot && `DOT: ${dot}`,
            ].filter(Boolean).join('\n');
            orderQuantity.value = '1';
            orderQuantity.max = stock;
            document.getElementById('mesbul-order-product').textContent = [product.marka, model].filter(Boolean).join(' · ');
            document.getElementById('mesbul-order-stock').textContent = `Listelenen stok: ${stock} adet`;
            updateOrderTotal();
            orderDialog.showModal();
            return;
        }

        if (button.dataset.action !== 'quote') return;
        try {
            const draft = readDraft();
            const item = {
                id: JSON.stringify([results.dataset.ebat, action.toptanci, product.marka, action.urun, dot, price]),
                brand: product.marka,
                product: (dot ? `${model} DOT ${dot}` : model).slice(0, 300),
                season,
                price,
            };
            if (draft.some(existing => existing.id === item.id)) {
                notify('Bu ürün taslakta zaten var.');
                return;
            }
            draft.push(item);
            sessionStorage.setItem(key, JSON.stringify(draft));
            updateQuoteLink(draft.length);
            notify('Teklif taslağına eklendi.');
        } catch {
            notify('Teklif taslağı kaydedilemedi.');
        }
    });

    results.querySelector('.mesbul-quick-search').addEventListener('toggle', (event) => {
        if (event.target.open) document.getElementById('mesbul-quick-ebat').focus();
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && document.getElementById('mesbul-filters').classList.contains('open')) closeFilters();
    });
})();
