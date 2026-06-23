from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.hashers import check_password
from .models import Distributor, DistributorActivityLog, DistributorPasswordResetOTP

class DistributorModelTest(TestCase):
    def setUp(self):
        self.distributor = Distributor.objects.create(
            username="TestDistributor",
            email="test@example.com",
            phone="1234567890",
            company_name="Test Company",
            address="123 Street",
            city="New York",
            state="NY",
            pincode="100001",
            password="hashed_password_placeholder"
        )

    def test_distributor_creation(self):
        self.assertEqual(self.distributor.username, "TestDistributor")
        self.assertEqual(self.distributor.email, "test@example.com")
        self.assertTrue(self.distributor.is_active)

    def test_profile_completion_percent(self):
        # Username, Email, Phone, Company, Address, City, State, Pincode = 8 fields * 10% = 80%
        # Profile image is blank/null. Total completion should be 80%
        completion = self.distributor.profile_completion_percent()
        self.assertEqual(completion, 80)

class DistributorViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.register_url = reverse('register')
        self.login_url = reverse('login')
        self.profile_url = reverse('profile')
        
        # Create a test user with hashed password
        from django.contrib.auth.hashers import make_password
        self.user_password = "Password@123"
        self.user = Distributor.objects.create(
            username="JohnDoe",
            email="john@example.com",
            phone="9876543210",
            password=make_password(self.user_password)
        )

    def test_register_view_get(self):
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'register.html')

    def test_register_view_post_success(self):
        response = self.client.post(self.register_url, {
            'username': 'NewUser',
            'email': 'new@example.com',
            'phone': '1122334455',
            'password': 'Password@123',
            'c_password': 'Password@123'
        })
        self.assertEqual(response.status_code, 302) # Redirects to login
        self.assertTrue(Distributor.objects.filter(email='new@example.com').exists())

    def test_login_view_post_success(self):
        response = self.client.post(self.login_url, {
            'email': 'john@example.com',
            'password': self.user_password
        })
        self.assertEqual(response.status_code, 302) # Redirects to profile
        self.assertEqual(self.client.session['email'], 'john@example.com')

    def test_profile_view_requires_login(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 302) # Redirects to login

    def test_profile_view_authenticated(self):
        # Simulate log in
        session = self.client.session
        session['email'] = 'john@example.com'
        session.save()
        
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'profile.html')

    def test_export_pdf_requires_login(self):
        response = self.client.get(reverse('export_pdf'))
        self.assertEqual(response.status_code, 302)

    def test_export_pdf_success(self):
        session = self.client.session
        session['email'] = 'john@example.com'
        session.save()

        response = self.client.get(reverse('export_pdf'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

