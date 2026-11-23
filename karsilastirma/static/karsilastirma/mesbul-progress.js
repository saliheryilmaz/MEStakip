(() => {
    if (!window.fetch || !window.ReadableStream || !window.TextDecoder) return;
    const money = new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' });
    document.querySelectorAll('form[data-mesbul-progress]').forEach(form => {
        const button = form.querySelector('[type=submit]');
        const summary = document.createElement('p');
        summary.className = 'small text-body-secondary mb-1';
        summary.setAttribute('role', 'status');
        const list = document.createElement('ul');
        list.className = 'list-group list-group-flush';
        const panel = document.createElement('section');
        panel.className = 'card p-3 my-2 text-start';
        panel.hidden = true;
        panel.append(summary, list);
        const anchor = form.closest('.mesbul-results-search, .hata-banner') || form;
        anchor.after(panel);
        let busy = false;

        form.addEventListener('submit', async event => {
            event.preventDefault();
            if (busy) return;
            busy = true;
            button.disabled = true;
            const data = new FormData(form);
            panel.hidden = false;
            list.replaceChildren();
            summary.textContent = 'İlk teklifler bekleniyor…';
            const status = document.getElementById('mesbul-search-status');
            if (status) status.textContent = '';

            try {
                const response = await fetch(form.action, {
                    method: 'POST', body: data, headers: { Accept: 'application/x-ndjson' }
                });
                if (!response.ok) throw new Error();
                if (!response.headers.get('Content-Type')?.includes('application/x-ndjson')) {
                    // Oturum ve abonelik ekranlarına normal form akışıyla geç.
                    form.submit();
                    return;
                }
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                let firstOffers = true;
                while (true) {
                    const { value, done } = await reader.read();
                    buffer += decoder.decode(value, { stream: !done });
                    let end;
                    while ((end = buffer.indexOf('\n')) >= 0) {
                        const update = JSON.parse(buffer.slice(0, end));
                        buffer = buffer.slice(end + 1);
                        if (update.hazir) {
                            // Gönderim sırasında değişen form alanları arama sonucunu değiştirmesin.
                            const finalForm = document.createElement('form');
                            finalForm.method = 'post';
                            finalForm.action = form.action;
                            data.set('arama_teslim', update.hazir);
                            for (const [name, value] of data) {
                                const input = document.createElement('input');
                                Object.assign(input, { type: 'hidden', name, value });
                                finalForm.append(input);
                            }
                            document.body.append(finalForm);
                            finalForm.submit();
                            return;
                        }
                        if (!update.urunler) continue;
                        summary.textContent = update.biten + '/' + update.toplam + ' kaynak tamamlandı · ' +
                            (update.urunler.length ? 'Şu ana kadarki en uygun teklifler' : 'Eşleşen teklif bekleniyor');
                        list.replaceChildren(...update.urunler.map(product => {
                            const row = document.createElement('li');
                            row.className = 'list-group-item d-flex justify-content-between gap-2';
                            const label = document.createElement('span');
                            label.textContent = [product.toptanci, product.marka, product.model].filter(Boolean).join(' · ');
                            const price = document.createElement('strong');
                            price.className = 'text-nowrap';
                            price.textContent = money.format(product.fiyat);
                            row.append(label, price);
                            return row;
                        }));
                        if (firstOffers && update.urunler.length) {
                            firstOffers = false;
                            if (panel.getBoundingClientRect().top > window.innerHeight - 80) {
                                panel.scrollIntoView({ block: 'start' });
                            }
                        }
                    }
                    if (done) throw new Error();
                }
            } catch {
                summary.textContent = 'Arama bağlantısı kesildi. Tekrar arayabilirsiniz.';
            } finally {
                busy = false;
                button.disabled = false;
            }
        });
        window.addEventListener('pageshow', () => { panel.hidden = true; });
    });
})();
