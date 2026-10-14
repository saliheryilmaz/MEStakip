from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase, override_settings
from django.urls import reverse
from openpyxl import load_workbook

from .models import CikmaLastik, UserProfile
from .used_tire_inventory import can_manage_admin_note


@override_settings(
    SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False,
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class UsedTireAdminNoteTests(TestCase):
    secret = 'CONFIDENTIAL-NOTE-9471'

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username='note-admin')
        UserProfile.objects.update_or_create(user=cls.admin, defaults={'role': 'admin'})
        cls.manager = User.objects.create_user(username='note-manager')
        cls.guest = User.objects.create_user(username='note-guest')
        UserProfile.objects.update_or_create(user=cls.guest, defaults={'role': 'misafir'})

    def setUp(self):
        self.url = reverse('dashboard:cikma_lastikler')

    def tire(self, user=None, **kwargs):
        values = dict(user=user or self.admin, marka='Michelin', ebat='205/55R16',
                      mevsim='yaz', adet=4, durum='depolandi', depo_konumu='A1',
                      aciklama='Public description', admin_aciklama=self.secret)
        values.update(kwargs)
        return CikmaLastik.objects.create(**values)

    def edit_url(self, tire):
        return reverse('dashboard:cikma_lastik_duzenle', args=[tire.pk])

    def test_admin_sees_note_in_list_and_both_forms(self):
        tire = self.tire()
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertContains(response, self.secret, count=2)  # Desktop and mobile only.
        self.assertContains(response, 'name="admin_aciklama"', count=1)
        response = self.client.get(self.edit_url(tire))
        self.assertContains(response, self.secret)
        self.assertContains(response, 'name="admin_aciklama"')

    def test_manager_cannot_read_note_even_on_own_record(self):
        tire = self.tire(user=self.manager)
        self.client.force_login(self.manager)
        for url in (self.url, self.edit_url(tire)):
            response = self.client.get(url)
            self.assertContains(response, 'Public description')
            self.assertNotContains(response, self.secret)
            self.assertNotContains(response, 'admin_aciklama')
            self.assertFalse(response.context['can_edit_admin_note'])

    def test_guest_cannot_read_notes_or_edit(self):
        tire = self.tire()
        self.client.force_login(self.guest)
        response = self.client.get(self.url)
        self.assertContains(response, 'Public description')
        self.assertNotContains(response, self.secret)
        self.assertNotContains(response, 'admin_aciklama')
        self.client.post(self.edit_url(tire), {'admin_aciklama': 'forged'})
        tire.refresh_from_db()
        self.assertEqual(tire.admin_aciklama, self.secret)

    def test_admin_can_create_note_without_logging_it(self):
        self.client.force_login(self.admin)
        with patch('builtins.print') as logged:
            response = self.client.post(self.url, {
                'marka': 'Michelin', 'ebat': '205/55R16', 'mevsim': 'yaz',
                'adet': 4, 'depo_konumu': 'A1', 'admin_aciklama': self.secret,
            })
        self.assertRedirects(response, self.url)
        self.assertEqual(CikmaLastik.objects.get(user=self.admin).admin_aciklama, self.secret)
        self.assertNotIn(self.secret, str(logged.call_args_list))

    def test_manager_forged_create_cannot_set_note(self):
        self.client.force_login(self.manager)
        self.client.post(self.url, {
            'marka': 'Michelin', 'ebat': '205/55R16', 'mevsim': 'yaz',
            'adet': 4, 'depo_konumu': 'A1', 'admin_aciklama': self.secret,
        })
        self.assertEqual(CikmaLastik.objects.get(user=self.manager).admin_aciklama, '')

    def test_admin_can_update_clear_and_omit_note(self):
        tire = self.tire()
        self.client.force_login(self.admin)
        for payload, expected in (({'admin_aciklama': 'Changed'}, 'Changed'),
                                  ({'aciklama': 'Public changed'}, 'Changed'),
                                  ({'admin_aciklama': ''}, '')):
            self.assertRedirects(self.client.post(self.edit_url(tire), payload), self.url)
            tire.refresh_from_db()
            self.assertEqual(tire.admin_aciklama, expected)

    def test_manager_cannot_replace_or_clear_existing_note(self):
        tire = self.tire(user=self.manager)
        self.client.force_login(self.manager)
        for payload in ({'admin_aciklama': 'forged'}, {'admin_aciklama': ''}, {}):
            payload['aciklama'] = 'Public updated'
            self.assertRedirects(self.client.post(self.edit_url(tire), payload), self.url)
            tire.refresh_from_db()
            self.assertEqual(tire.admin_aciklama, self.secret)
            self.assertEqual(tire.aciklama, 'Public updated')

    def test_existing_record_ownership_is_unchanged(self):
        tire = self.tire(user=self.manager)
        self.client.force_login(self.admin)
        self.assertNotContains(self.client.get(self.url), self.secret)
        self.assertEqual(self.client.get(self.edit_url(tire)).status_code, 404)
        self.assertEqual(self.client.post(self.edit_url(tire), {'admin_aciklama': 'x'}).status_code, 404)

    def test_admin_definition_matches_dashboard_and_denies_missing_profiles(self):
        self.assertFalse(can_manage_admin_note(AnonymousUser()))
        for flag in ('is_staff', 'is_superuser'):
            user = User.objects.create_user(username=flag, **{flag: True})
            UserProfile.objects.filter(user=user).update(role='yonetici')
            self.assertTrue(can_manage_admin_note(User.objects.get(pk=user.pk)))
        self.assertFalse(can_manage_admin_note(self.manager))
        self.assertFalse(can_manage_admin_note(self.guest))
        UserProfile.objects.filter(user=self.manager).delete()
        self.assertFalse(can_manage_admin_note(User.objects.get(pk=self.manager.pk)))
        self.admin.is_active = False
        self.assertFalse(can_manage_admin_note(self.admin))

    def test_note_is_escaped_in_list_and_edit_form(self):
        malicious = '<script>alert(9471)</script>'
        tire = self.tire(admin_aciklama=malicious)
        self.client.force_login(self.admin)
        for url in (self.url, self.edit_url(tire)):
            response = self.client.get(url)
            self.assertNotContains(response, malicious)
            self.assertContains(response, '&lt;script&gt;alert(9471)&lt;/script&gt;')

    def test_note_is_not_exported_for_any_role(self):
        self.tire()
        self.tire(user=self.manager)
        for user in (self.admin, self.manager, self.guest):
            self.client.force_login(user)
            response = self.client.get(reverse('dashboard:export_cikma_lastikler_excel'))
            rows = list(load_workbook(BytesIO(response.content)).active.values)
            self.assertNotIn(self.secret, str(rows))
            self.assertNotIn('Admin', str(rows))

    def test_note_is_not_in_assistant_tool_results(self):
        from .ai_tools import get_used_tire_inventory, get_used_tire_waiting_long
        self.tire()
        for result in (get_used_tire_inventory(), get_used_tire_waiting_long(days=0)):
            self.assertNotIn(self.secret, str(result))
            self.assertNotIn('admin_aciklama', str(result))

    def test_anonymous_visitors_are_redirected(self):
        tire = self.tire()
        for url in (self.url, self.edit_url(tire)):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertNotIn(self.secret, response.content.decode())
