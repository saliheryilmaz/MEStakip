from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from .models import UserProfile


class AccountPreferencesTests(TestCase):
    password = "Account-check-17!forest"

    def setUp(self):
        self.user = User.objects.create_user("account-check", password=self.password)
        self.client.force_login(self.user)

    def test_saved_start_page_is_used_and_safe_next_takes_precedence(self):
        settings_url = reverse("dashboard:settings")
        security_url = reverse("dashboard:security")
        login_url = reverse("dashboard:login")
        response = self.client.post(settings_url, {"action": "start_page", "start_page": "dashboard:lastik_saklama"})
        self.assertRedirects(response, settings_url, fetch_redirect_response=False)
        credentials = {"username": self.user.username, "password": self.password}
        self.assertRedirects(Client().post(login_url, credentials),
                             reverse("dashboard:lastik_saklama"), fetch_redirect_response=False)
        self.assertRedirects(Client().post(f"{login_url}?next={security_url}", credentials),
                             security_url, fetch_redirect_response=False)
        self.assertRedirects(Client().post(f"{login_url}?next=https://example.com", credentials),
                             reverse("dashboard:lastik_saklama"), fetch_redirect_response=False)

    def test_guest_cannot_choose_or_use_a_restricted_start_page(self):
        profile = self.user.userprofile
        profile.role = "misafir"
        profile.start_page = UserProfile.StartPage.STORAGE
        profile.save(update_fields=["role", "start_page"])
        response = self.client.post(reverse("dashboard:settings"),
                                    {"action": "start_page", "start_page": UserProfile.StartPage.ORDERS})
        self.assertTrue(response.context["start_form"].errors)
        response = self.client.get(reverse("dashboard:login"))
        self.assertRedirects(response, reverse("dashboard:cikma_lastikler"), fetch_redirect_response=False)

    def test_revoking_sessions_preserves_current_session_and_other_accounts(self):
        security_url = reverse("dashboard:security")
        second_device = Client()
        second_device.force_login(self.user)
        other_user = User.objects.create_user("another-account")
        other_device = Client()
        other_device.force_login(other_user)

        response = self.client.post(security_url, {"action": "revoke_sessions", "password": "wrong"})
        self.assertContains(response, "Mevcut şifre hatalı.")
        self.assertEqual(second_device.get(security_url).status_code, 200)
        response = self.client.post(security_url, {"action": "revoke_sessions", "password": self.password}, follow=True)
        self.assertContains(response, "1 diğer oturum kapatıldı.")
        self.assertEqual(self.client.get(security_url).status_code, 200)
        self.assertEqual(second_device.get(security_url).status_code, 302)
        self.assertEqual(other_device.get(security_url).status_code, 200)
