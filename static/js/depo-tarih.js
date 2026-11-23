(() => {
    const trigger = document.querySelector('#tarihSec');
    const panel = document.querySelector('#tarihPanel');
    const form = trigger.form;
    const start = panel.querySelector('[data-start]');
    const end = panel.querySelector('[data-end]');
    const apply = panel.querySelector('[data-apply]');
    const date = (year, month, day) => new Date(Date.UTC(year, month, day));
    const iso = d => d.toISOString().slice(0, 10);
    const parse = value => new Date(value + 'T00:00:00Z');
    const today = parse(panel.dataset.today);
    const year = today.getUTCFullYear(), month = today.getUTCMonth(), day = today.getUTCDate();
    const monthTitle = new Intl.DateTimeFormat('tr-TR', {month:'long', year:'numeric', timeZone:'UTC'});
    const presets = [
        ['Bugün', today, today],
        ['Dün', date(year, month, day - 1), date(year, month, day - 1)],
        ['7 Gün', date(year, month, day - 6), today],
        ['Bu Ay', date(year, month, 1), date(year, month + 1, 0)],
        ['Geçen Ay', date(year, month - 1, 1), date(year, month, 0)],
        ['Son 3 Ay', date(year, month - 3, Math.min(day, date(year, month - 2, 0).getUTCDate())), today],
        ['Bu Yıl', date(year, 0, 1), date(year, 11, 31)],
        ['Geçen Yıl', date(year - 1, 0, 1), date(year - 1, 11, 31)],
    ];
    let firstMonth, selectingEnd;
    const setMonth = d => { firstMonth = date(d.getUTCFullYear(), d.getUTCMonth(), 1); };
    const shiftMonth = n => date(firstMonth.getUTCFullYear(), firstMonth.getUTCMonth() + n, 1);
    function button(label, click) {
        const el = document.createElement('button');
        el.type = 'button';
        el.textContent = label;
        el.onclick = click;
        return el;
    }
    const presetButtons = presets.map(([name, from, to]) => {
        const el = button(name, () => {
            start.value = iso(from);
            end.value = iso(to);
            selectingEnd = false;
            setMonth(from);
            render();
        });
        panel.querySelector('.tarih-presets').append(el);
        return el;
    });
    function pick(value) {
        if (selectingEnd) {
            const dates = [start.value, value].sort();
            [start.value, end.value] = dates;
        } else {
            start.value = value;
            end.value = '';
        }
        selectingEnd = !selectingEnd;
        render();
    }
    function render() {
        const months = panel.querySelector('.tarih-months');
        months.replaceChildren();
        for (const offset of [0, 1]) {
            const first = shiftMonth(offset);
            const section = document.createElement('section');
            const heading = document.createElement('h6');
            heading.textContent = monthTitle.format(first);
            const grid = document.createElement('div');
            grid.className = 'tarih-grid';
            for (const label of ['Pt','Sa','Ça','Pe','Cu','Ct','Pa']) {
                const text = document.createElement('small');
                text.textContent = label;
                grid.append(text);
            }
            for (let n = 1; n <= date(first.getUTCFullYear(), first.getUTCMonth()+1, 0).getUTCDate(); n++) {
                const value = iso(date(first.getUTCFullYear(), first.getUTCMonth(), n));
                const el = button(n, () => pick(value));
                el.setAttribute('aria-label', n + ' ' + heading.textContent);
                if (n === 1) el.style.gridColumnStart = (first.getUTCDay()+6)%7+1;
                if (value === start.value || value === end.value) el.className = 'edge';
                else if (value > start.value && value < end.value && start.value) el.className = 'between';
                grid.append(el);
            }
            section.append(heading, grid);
            months.append(section);
        }
        presets.forEach(([,a,b], i) => presetButtons[i].setAttribute('aria-pressed',
            start.value === iso(a) && end.value === iso(b)));
        apply.disabled = !start.value || !end.value || start.value > end.value;
        panel.querySelector('.tarih-footer span').textContent = apply.disabled
            ? (start.value && end.value ? 'Bitiş başlangıçtan önce olamaz.' : 'Tarih aralığını seçin.')
            : ((parse(end.value)-parse(start.value))/86400000+1) + ' gün seçili';
    }
    const savedStart = form.elements.baslangic, savedEnd = form.elements.bitis;
    const display = value => value.split('-').reverse().join('.');
    if (savedStart.value || savedEnd.value) trigger.querySelector('span').textContent =
        [savedStart.value,savedEnd.value].map(v => v ? display(v) : '…').join(' – ');
    function position() {
        const rect = trigger.getBoundingClientRect();
        panel.style.left = Math.max(12, Math.min(rect.left, innerWidth-panel.offsetWidth-12)) + 'px';
        panel.style.top = Math.max(12, Math.min(rect.bottom+6, innerHeight-panel.offsetHeight-12)) + 'px';
    }
    panel.addEventListener('toggle', event => {
        if (event.newState !== 'open') return;
        start.value = savedStart.value;
        end.value = savedEnd.value;
        selectingEnd = false;
        setMonth(start.value ? parse(start.value) : today);
        render();
        position();
    });
    window.addEventListener('resize', () => { if (panel.matches(':popover-open')) position(); });
    panel.querySelectorAll('.tarih-nav button').forEach((el,i) => {
        el.onclick = () => { firstMonth = shiftMonth(i ? 1 : -1); render(); };
    });
    for (const field of [start,end]) field.onchange = () => {
        if (field.value) setMonth(parse(field.value));
        selectingEnd = !!start.value && !end.value;
        render();
    };
    apply.onclick = () => {
        savedStart.value = start.value;
        savedEnd.value = end.value;
        panel.hidePopover();
        form.requestSubmit();
    };
})();
