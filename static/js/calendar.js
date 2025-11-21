
document.addEventListener('alpine:init', () => {
  Alpine.data('calendarComponent', () => ({
    // UI State
    sidebarVisible: false,
    currentView: 'month',
    selectedDate: null,
    selectedDay: null,

    // Calendar State
    currentDate: new Date(),
    miniCalendarDate: new Date(),

    // Event Types and Filters
    visibleTypes: ['event', 'meeting', 'task', 'reminder', 'deadline'],

    // Sample Events Data
    events: [],

    // Time slots for week/day view
    hours: [
      '6:00', '7:00', '8:00', '9:00', '10:00', '11:00',
      '12:00', '13:00', '14:00', '15:00', '16:00', '17:00',
      '18:00', '19:00', '20:00', '21:00', '22:00'
    ],

    init() {
      this.loadEvents();

      // Bugünün tarihini doğru şekilde al
      const today = new Date();
      const year = today.getFullYear();
      const month = String(today.getMonth() + 1).padStart(2, '0');
      const day = String(today.getDate()).padStart(2, '0');
      const todayString = `${year}-${month}-${day}`;

      this.selectedDate = today;
      this.selectedDay = todayString;

      // Initialize calendar view
      this.currentDate = today;
      this.miniCalendarDate = today;
    },

    loadSampleEvents() {
      const today = new Date();
      const currentYear = today.getFullYear();
      const currentMonth = today.getMonth();
      const currentDay = today.getDate();

      // Get current month name for display
      const monthNames = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz',
        'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara'];
      const currentMonthName = monthNames[currentMonth];

      // Generate future events for the current month
      const eventTemplates = [
        { title: 'Ekip Toplantısı', type: 'meeting', time: '10:00', description: 'Haftalık ekip senkronizasyonu ve proje güncellemeleri' },
        { title: 'Ürün Lansmanı', type: 'event', time: '14:00', description: 'Yeni ürün hattı için lansman etkinliği' },
        { title: 'Günlük Toplantı', type: 'meeting', time: '09:00', description: 'Günlük ekip toplantısı' },
        { title: 'Müşteri Sunumu', type: 'task', time: '11:30', description: 'Çeyrek sonuçları müşteriye sunum' },
        { title: 'Ödeme Hatırlatıcısı', type: 'reminder', time: '09:00', description: 'Aylık abonelik ödeme hatırlatıcısı' },
        { title: 'Atölye Çalışması', type: 'event', time: '14:00', description: 'Tasarım düşüncesi atölyesi' },
        { title: 'Proje Son Tarihi', type: 'deadline', time: '17:00', description: 'Q1 projesi için son teslim tarihi' },
        { title: 'Ekip Yemeği', type: 'event', time: '12:00', description: 'Aylık ekip yemeği buluşması' },
        { title: 'Yönetim Kurulu', type: 'meeting', time: '15:00', description: 'Aylık yönetim kurulu toplantısı ve strateji incelemesi' },
        { title: 'Eğitim Oturumu', type: 'event', time: '13:00', description: 'Yeni yazılım araçları üzerine çalışan eğitimi' }
      ];

      // Get the number of days in current month
      const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();

      // Generate events for future dates in current month
      this.events = [];
      let eventIndex = 0;

      // Create events distributed across remaining days of the month
      for (let day = currentDay; day <= daysInMonth && eventIndex < eventTemplates.length; day++) {
        // Skip some days to avoid too many events
        if ((day - currentDay) % 2 === 0 || day === currentDay || day === daysInMonth) {
          const template = eventTemplates[eventIndex];
          const eventDate = new Date(currentYear, currentMonth, day);
          const dateString = `${currentYear}-${String(currentMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;

          // Create time string based on day
          let timeStr, dateStr;
          if (day === currentDay) {
            timeStr = template.time;
            dateStr = 'Bugün';
          } else if (day === currentDay + 1) {
            timeStr = template.time;
            dateStr = 'Yarın';
          } else {
            timeStr = template.time;
            dateStr = `${currentMonthName} ${day}`;
          }

          this.events.push({
            id: eventIndex + 1,
            title: template.title,
            type: template.type,
            time: template.time,
            timeStr: timeStr,
            dateStr: dateStr,
            description: template.description,
            date: dateString,
            dateObj: new Date(eventDate.getTime()),
            read: Math.random() > 0.3 // Most events are read
          });

          eventIndex++;
        }
      }
    },

    // Computed Properties
    get currentMonthYear() {
      return this.miniCalendarDate.toLocaleDateString('tr-TR', {
        month: 'long',
        year: 'numeric'
      });
    },

    get currentPeriodTitle() {
      if (this.currentView === 'month') {
        return this.currentDate.toLocaleDateString('tr-TR', {
          month: 'long',
          year: 'numeric'
        });
      } else if (this.currentView === 'week') {
        const startOfWeek = new Date(this.currentDate);
        startOfWeek.setDate(this.currentDate.getDate() - this.currentDate.getDay());
        const endOfWeek = new Date(startOfWeek);
        endOfWeek.setDate(startOfWeek.getDate() + 6);

        return `${startOfWeek.toLocaleDateString('tr-TR', { month: 'short', day: 'numeric' })} - ${endOfWeek.toLocaleDateString('tr-TR', { month: 'short', day: 'numeric', year: 'numeric' })}`;
      } else {
        return this.currentDate.toLocaleDateString('tr-TR', {
          weekday: 'long',
          month: 'long',
          day: 'numeric',
          year: 'numeric'
        });
      }
    },

    get selectedDayTitle() {
      const dateToUse = this.selectedDay || this.getCurrentDateString();
      const date = new Date(dateToUse + 'T12:00:00');
      return date.toLocaleDateString('tr-TR', { weekday: 'long' });
    },

    get selectedDayDate() {
      const dateToUse = this.selectedDay || this.getCurrentDateString();
      const date = new Date(dateToUse + 'T12:00:00');
      return date.toLocaleDateString('tr-TR', {
        month: 'long',
        day: 'numeric',
        year: 'numeric'
      });
    },

    getCurrentDateString() {
      const date = this.currentDate;
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      return `${year}-${month}-${day}`;
    },

    get miniCalendarDays() {
      const year = this.miniCalendarDate.getFullYear();
      const month = this.miniCalendarDate.getMonth();
      const firstDay = new Date(year, month, 1);
      const lastDay = new Date(year, month + 1, 0);
      const startDate = new Date(firstDay);
      startDate.setDate(startDate.getDate() - firstDay.getDay());

      const days = [];
      for (let i = 0; i < 42; i++) {
        const date = new Date(startDate);
        date.setDate(startDate.getDate() + i);

        // Doğru tarih formatı oluştur
        const year = date.getFullYear();
        const month_num = String(date.getMonth() + 1).padStart(2, '0');
        const day_num = String(date.getDate()).padStart(2, '0');
        const dateString = `${year}-${month_num}-${day_num}`;

        const hasEvents = this.events.some(event => event.date === dateString);

        days.push({
          date: dateString,
          day: date.getDate(),
          isToday: this.isToday(date),
          isOtherMonth: date.getMonth() !== month,
          isSelected: dateString === this.selectedDay,
          hasEvents: hasEvents
        });
      }
      return days;
    },

    get calendarDays() {
      const year = this.currentDate.getFullYear();
      const month = this.currentDate.getMonth();
      const firstDay = new Date(year, month, 1);
      const lastDay = new Date(year, month + 1, 0);
      const startDate = new Date(firstDay);
      startDate.setDate(startDate.getDate() - firstDay.getDay());

      const days = [];
      for (let i = 0; i < 42; i++) {
        const date = new Date(startDate);
        date.setDate(startDate.getDate() + i);

        // Doğru tarih formatı oluştur
        const year = date.getFullYear();
        const month_num = String(date.getMonth() + 1).padStart(2, '0');
        const day_num = String(date.getDate()).padStart(2, '0');
        const dateString = `${year}-${month_num}-${day_num}`;

        const dayEvents = this.getEventsForDate(dateString).filter(event =>
          this.visibleTypes.includes(event.type)
        );

        days.push({
          date: dateString,
          day: date.getDate(),
          isToday: this.isToday(date),
          isOtherMonth: date.getMonth() !== month,
          isSelected: dateString === this.selectedDay,
          events: dayEvents
        });
      }
      return days;
    },

    get weekDays() {
      const startOfWeek = new Date(this.currentDate);
      startOfWeek.setDate(this.currentDate.getDate() - this.currentDate.getDay());

      const days = [];
      for (let i = 0; i < 7; i++) {
        const date = new Date(startOfWeek);
        date.setDate(startOfWeek.getDate() + i);

        // Doğru tarih formatı oluştur
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const dateString = `${year}-${month}-${day}`;

        days.push({
          date: dateString,
          dayName: date.toLocaleDateString('tr-TR', { weekday: 'short' }),
          dayNumber: date.getDate(),
          isToday: this.isToday(date)
        });
      }
      return days;
    },

    get upcomingEvents() {
      const now = new Date();
      return this.events
        .filter(event => {
          if (!this.visibleTypes.includes(event.type)) return false;
          if (!event.dateObj || typeof event.dateObj.getTime !== 'function') return false;
          return event.dateObj >= now;
        })
        .sort((a, b) => {
          if (!a.dateObj || !b.dateObj) return 0;
          return a.dateObj.getTime() - b.dateObj.getTime();
        })
        .slice(0, 8);
    },

    // Navigation Methods
    previousMonth() {
      const newDate = new Date(this.miniCalendarDate);
      newDate.setMonth(newDate.getMonth() - 1);
      this.miniCalendarDate = newDate;
    },

    nextMonth() {
      const newDate = new Date(this.miniCalendarDate);
      newDate.setMonth(newDate.getMonth() + 1);
      this.miniCalendarDate = newDate;
    },

    previousPeriod() {
      const newDate = new Date(this.currentDate);
      if (this.currentView === 'month') {
        newDate.setMonth(newDate.getMonth() - 1);
      } else if (this.currentView === 'week') {
        newDate.setDate(newDate.getDate() - 7);
      } else {
        newDate.setDate(newDate.getDate() - 1);
      }
      this.currentDate = newDate;
      
      // Gün görünümündeyken selectedDay'i de güncelle
      if (this.currentView === 'day') {
        const year = newDate.getFullYear();
        const month = String(newDate.getMonth() + 1).padStart(2, '0');
        const day = String(newDate.getDate()).padStart(2, '0');
        this.selectedDay = `${year}-${month}-${day}`;
      }
    },

    nextPeriod() {
      const newDate = new Date(this.currentDate);
      if (this.currentView === 'month') {
        newDate.setMonth(newDate.getMonth() + 1);
      } else if (this.currentView === 'week') {
        newDate.setDate(newDate.getDate() + 7);
      } else {
        newDate.setDate(newDate.getDate() + 1);
      }
      this.currentDate = newDate;
      
      // Gün görünümündeyken selectedDay'i de güncelle
      if (this.currentView === 'day') {
        const year = newDate.getFullYear();
        const month = String(newDate.getMonth() + 1).padStart(2, '0');
        const day = String(newDate.getDate()).padStart(2, '0');
        this.selectedDay = `${year}-${month}-${day}`;
      }
    },

    goToToday() {
      const today = new Date();
      const year = today.getFullYear();
      const month = String(today.getMonth() + 1).padStart(2, '0');
      const day = String(today.getDate()).padStart(2, '0');
      const todayString = `${year}-${month}-${day}`;

      this.currentDate = today;
      this.miniCalendarDate = today;
      this.selectedDay = todayString;
    },

    switchView(view) {
      this.currentView = view;
      if (view === 'day') {
        if (!this.selectedDay) {
          const today = new Date();
          const year = today.getFullYear();
          const month = String(today.getMonth() + 1).padStart(2, '0');
          const day = String(today.getDate()).padStart(2, '0');
          this.selectedDay = `${year}-${month}-${day}`;
          this.currentDate = today;
        } else {
          // Seçili günü currentDate olarak ayarla
          const date = new Date(this.selectedDay + 'T12:00:00');
          this.currentDate = date;
        }
      }
    },

    // Date Methods
    selectDate(dateString) {
      this.selectedDay = dateString;
      // Timezone offset'ini düzelt
      const date = new Date(dateString + 'T12:00:00');
      this.selectedDate = date;
      this.currentDate = date; // Her zaman currentDate'i güncelle
      
      // Gün görünümündeyken seçilen günü güncelle
      if (this.currentView === 'day') {
        // Force refresh of day view
        this.$nextTick(() => {
          // Trigger reactivity
          this.currentView = 'day';
        });
      }
    },

    selectDay(day) {
      this.selectDate(day.date);
      // Eğer gün görünümündeyken bir gün seçilirse, o güne geç
      if (this.currentView === 'day') {
        const date = new Date(day.date + 'T12:00:00');
        this.currentDate = date;
      }
    },

    isToday(date) {
      const today = new Date();
      if (!date || typeof date.getTime !== 'function') {
        return false;
      }
      // Sadece tarih kısmını karşılaştır (saat dilimi sorunlarını önlemek için)
      const dateStr = date.getFullYear() + '-' +
        String(date.getMonth() + 1).padStart(2, '0') + '-' +
        String(date.getDate()).padStart(2, '0');
      const todayStr = today.getFullYear() + '-' +
        String(today.getMonth() + 1).padStart(2, '0') + '-' +
        String(today.getDate()).padStart(2, '0');
      return dateStr === todayStr;
    },

    isCurrentHour(hour) {
      const now = new Date();
      const currentHour = now.getHours();
      const hourNumber = parseInt(hour.split(':')[0]);

      return hourNumber === currentHour;
    },

    // Event Methods
    getEventsForDate(dateString) {
      return this.events.filter(event => event.date === dateString);
    },

    getEventsForDateTime(dateString, hour) {
      // Önce tarih kontrolü yap
      const dayEvents = this.events.filter(event => event.date === dateString);
      
      // Eğer saat belirtilmemişse, o günün tüm etkinliklerini döndür
      if (!hour) {
        return dayEvents;
      }
      
      // Saat kontrolü yap
      return dayEvents.filter(event => {
        return this.eventMatchesHour(event, hour);
      });
    },

    eventMatchesHour(event, hour) {
      const eventHour = parseInt(event.time.split(':')[0]);
      const hourNumber = parseInt(hour.split(':')[0]);

      return eventHour === hourNumber;
    },

    getDayEventCount(dateString) {
      return this.getEventsForDate(dateString).length;
    },

    getCategoryCount(type) {
      return this.events.filter(event => event.type === type).length;
    },

    getCategoryColor(type) {
      const colors = {
        event: 'var(--bs-primary)',
        meeting: 'var(--bs-success)',
        task: 'var(--bs-warning)',
        reminder: '#8b5cf6',
        deadline: 'var(--bs-danger)'
      };
      return colors[type] || 'var(--bs-secondary)';
    },

    // Event Actions
    viewEvent(event) {
      this.showNotification(`Etkinlik görüntüleniyor: ${event.title}`, 'info');
    },

    addEvent() {
      // Open the add event modal
      const modalElement = document.getElementById('addEventModal');
      if (modalElement) {
        try {
          const modal = new bootstrap.Modal(modalElement);
          modal.show();
        } catch (error) {
          // Fallback: jQuery modal açma
          if (typeof $ !== 'undefined') {
            $('#addEventModal').modal('show');
          }
        }
      } else {
        this.showNotification('Modal bulunamadı. Sayfayı yenileyin.', 'error');
      }
    },

    addEventForDay(day) {
      this.selectDay(day);
      // Pre-fill the date in the modal
      const addEventModalComponent = Alpine.$data(document.querySelector('[x-data*="addEventModal"]'));
      if (addEventModalComponent) {
        addEventModalComponent.eventData.date = day.date;
      }
      this.addEvent();
    },

    addEventAtTime(dateString, hour) {
      this.selectDate(dateString);
      // Pre-fill the date and time in the modal
      const addEventModalComponent = Alpine.$data(document.querySelector('[x-data*="addEventModal"]'));
      if (addEventModalComponent) {
        addEventModalComponent.eventData.date = dateString;
        addEventModalComponent.eventData.time = hour;
      }
      this.addEvent();
    },

    showMoreEvents(day) {
      this.selectDay(day);
      this.showNotification(`${day.date} için tüm etkinlikler gösteriliyor`, 'info');
    },

    exportCalendar() {
      this.showNotification('Takvim dışa aktarma burada başlayacak', 'info');
    },

    toggleSidebar() {
      this.sidebarVisible = !this.sidebarVisible;
    },

    showNotification(message, type = 'info') {
      if (typeof Swal !== 'undefined') {
        Swal.fire({
          title: message,
          icon: type === 'success' ? 'success' : type === 'error' ? 'error' : 'info',
          toast: true,
          position: 'top-end',
          showConfirmButton: false,
          timer: 3000
        });
      } else {
        alert(message);
      }
    },

    // Load events from backend
    async loadEvents() {
      try {
        const response = await fetch('/dashboard/api/events/');
        const data = await response.json();

        if (data.success) {
          this.events = data.events.map(event => {
            const dateObj = new Date(event.date + 'T00:00:00');
            return {
              ...event,
              dateObj: dateObj
            };
          });
        } else {
          this.loadSampleEvents(); // Fallback to sample events
        }
      } catch (error) {
        this.loadSampleEvents(); // Fallback to sample events
      }
    }
  }));

  // Add Event Modal Component
  Alpine.data('addEventModal', () => ({
    eventData: {
      title: '',
      type: 'reminder',
      date: '',
      time: '',
      description: '',
      duration: '60',
      recurring: false,
      recurrence: 'none',
      priority: 'high',
      reminders: ['15'],
      selectedReminders: ['15'],
      attendees: '',
      location: ''
    },

    priorityOptions: [
      { value: 'low', label: 'Düşük Öncelik', color: 'var(--bs-success)' },
      { value: 'medium', label: 'Orta Öncelik', color: 'var(--bs-warning)' },
      { value: 'high', label: 'Yüksek Öncelik', color: 'var(--bs-danger)' }
    ],

    reminderOptions: [
      { value: '0', label: 'Etkinlik zamanında' },
      { value: '5', label: '5 dakika önce' },
      { value: '15', label: '15 dakika önce' },
      { value: '30', label: '30 dakika önce' },
      { value: '60', label: '1 saat önce' },
      { value: '1440', label: '1 gün önce' }
    ],

    init() {
      // Initialize with today's date (doğru tarih formatı)
      const today = new Date();
      const year = today.getFullYear();
      const month = String(today.getMonth() + 1).padStart(2, '0');
      const day = String(today.getDate()).padStart(2, '0');
      const todayString = `${year}-${month}-${day}`;

      this.eventData.date = todayString;
      this.eventData.time = '13:50';
      this.eventData.recurrence = 'none';
      this.eventData.selectedReminders = ['15'];

      // selectedReminders değişikliklerini reminders ile senkronize et
      this.$watch('eventData.selectedReminders', (newValue) => {
        this.eventData.reminders = newValue;
      });
    },

    async submitEvent() {

      if (!this.eventData.title.trim()) {
        this.showValidationError('Lütfen etkinlik başlığı girin');
        return;
      }

      if (!this.eventData.date) {
        this.showValidationError('Lütfen bir tarih seçin');
        return;
      }

      if (!this.eventData.time) {
        this.showValidationError('Lütfen bir saat seçin');
        return;
      }

      // Recurring validation
      if (this.eventData.recurring && this.eventData.recurrence === 'none') {
        this.showValidationError('Tekrarlanan etkinlik için tekrar deseni seçmelisiniz');
        return;
      }

      try {
        // CSRF token al - daha güvenilir yöntem
        let csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
        if (!csrfToken) {
          // Meta tag'den al
          csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        }
        if (!csrfToken) {
          // Cookie'den al
          const cookies = document.cookie.split(';');
          for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') {
              csrfToken = value;
              break;
            }
          }
        }

        if (!csrfToken) {
          this.showValidationError('CSRF token bulunamadı. Sayfayı yenileyin.');
          return;
        }

        // Event data hazırla
        const eventData = {
          ...this.eventData,
          recurring: this.eventData.recurring,
          recurrence: this.eventData.recurring ? this.eventData.recurrence : 'none',
          reminders: Array.isArray(this.eventData.selectedReminders) ? this.eventData.selectedReminders : ['15']
        };

        console.log('Sending event data:', eventData);

        // API çağrısı yap
        console.log('API çağrısı yapılıyor...');
        console.log('URL:', '/dashboard/api/events/create/');
        console.log('Headers:', {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        });

        const response = await fetch('/dashboard/api/events/create/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
          },
          body: JSON.stringify(eventData)
        });

        const result = await response.json();

        if (result.success) {
          // Önce hemen alert göster (sayfa yenilenmeden önce)
          const reminderCount = Array.isArray(this.eventData.selectedReminders) ? this.eventData.selectedReminders.length : 1;
          const reminderText = reminderCount > 0 ? ` ${reminderCount} hatırlatıcı ayarlandı ve zamanı geldiğinde bildirim alacaksınız.` : '';
          
          // Sağ üstten toast bildirimi göster (hemen)
          if (typeof Swal !== 'undefined') {
            // Önce toast göster
            Swal.fire({
              title: '✅ Etkinlik Oluşturuldu!',
              text: `"${this.eventData.title}" etkinliği ${this.eventData.date} tarihinde ${this.eventData.time} saatinde oluşturuldu.${reminderText}`,
              icon: 'success',
              toast: true,
              position: 'top-end',
              showConfirmButton: false,
              timer: 5000,
              timerProgressBar: true,
              didOpen: (toast) => {
                toast.addEventListener('mouseenter', Swal.stopTimer)
                toast.addEventListener('mouseleave', Swal.resumeTimer)
              }
            });
          }

          // Bildirim sistemini güncelle
          if (window.notificationSystem) {
            // Biraz bekle sonra bildirimleri yükle (backend'de oluşturulması için)
            setTimeout(() => {
              window.notificationSystem.loadNotifications();
              
              // Tekrar toast göster (bildirim sistemi üzerinden)
              if (reminderCount > 0) {
                window.notificationSystem.showToast(
                  `"${this.eventData.title}" etkinliği oluşturuldu!${reminderText}`,
                  'success'
                );
              }
            }, 500);
          }

          // Modal'ı kapat ve formu sıfırla
          this.closeModal();

          // Sayfayı yenile (etkinlikleri görmek için) - daha uzun bekle
          setTimeout(() => {
            window.location.reload();
          }, 3000);

        } else {
          this.showValidationError('Hata: ' + (result.error || 'Etkinlik oluşturulamadı'));
        }

      } catch (error) {
        this.showValidationError('Sunucu ile iletişim kurulurken hata oluştu: ' + error.message);
      }
    },

    getTypeDisplayName(type) {
      const typeNames = {
        'event': 'Etkinlik',
        'meeting': 'Toplantı',
        'task': 'Görev',
        'reminder': 'Hatırlatıcı',
        'deadline': 'Son Tarih'
      };
      return typeNames[type] || type;
    },

    getDurationLabel(duration) {
      const hours = Math.floor(duration / 60);
      const minutes = duration % 60;

      if (duration == 480) return 'Tüm gün';
      if (hours === 0) return `${minutes} dakika`;
      if (minutes === 0) return `${hours} saat`;
      return `${hours}s ${minutes}d`;
    },

    showValidationError(message) {
      if (typeof Swal !== 'undefined') {
        Swal.fire({
          title: 'Doğrulama Hatası',
          text: message,
          icon: 'error',
          confirmButtonText: 'Tamam',
          confirmButtonColor: 'var(--bs-danger)'
        });
      } else {
        alert(message);
      }
    },

    closeModal() {
      const modal = document.getElementById('addEventModal');
      if (modal) {
        // Bootstrap 5 modal kapatma
        const bsModal = bootstrap.Modal.getInstance(modal) || new bootstrap.Modal(modal);
        bsModal.hide();
      }
      this.resetForm();
    },

    resetForm() {
      const today = new Date();
      const year = today.getFullYear();
      const month = String(today.getMonth() + 1).padStart(2, '0');
      const day = String(today.getDate()).padStart(2, '0');
      const todayString = `${year}-${month}-${day}`;

      this.eventData = {
        title: '',
        type: 'reminder',
        date: todayString,
        time: '13:50',
        description: '',
        duration: '60',
        recurring: false,
        recurrence: 'none',
        priority: 'high',
        reminders: ['15'],
        selectedReminders: ['15'],
        attendees: '',
        location: ''
      };
    },

    getTypeColor(type) {
      const colors = {
        event: 'var(--bs-primary)',
        meeting: 'var(--bs-success)',
        task: 'var(--bs-warning)',
        reminder: '#8b5cf6',
        deadline: 'var(--bs-danger)'
      };
      return colors[type] || 'var(--bs-secondary)';
    }
  }));
});