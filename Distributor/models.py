from django.db import models
from django.utils import timezone


class Distributor(models.Model):
    distributorid = models.AutoField(primary_key=True)

    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, unique=True, blank=True, null=True)


    company_name = models.CharField(max_length=200, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=120, blank=True, null=True)
    state = models.CharField(max_length=120, blank=True, null=True)
    pincode = models.CharField(max_length=10, blank=True, null=True)

    profile_image = models.ImageField(
        upload_to="distributor_profiles/",
        blank=True,
        null=True,
    )

    registration_date = models.DateTimeField(default=timezone.now)
    last_updated = models.DateTimeField(auto_now=True)
    last_login = models.DateTimeField(blank=True, null=True)

    is_active = models.BooleanField(default=True)

    # Keep as char to align with existing project behavior.
    # Django auth User model is intentionally not used in this app.
    password = models.CharField(max_length=128)

    def __str__(self):
        return self.username

    def profile_completion_percent(self):
        # Name = 10%, Email = 10% (email is always known), Phone = 10%, Company = 10%,
        # Address = 10%, City = 10%, State = 10%, Pincode = 10%, Profile Image = 20%
        weights = {
            "username": 10,
            "email": 10,
            "phone": 10,
            "company_name": 10,
            "address": 10,
            "city": 10,
            "state": 10,
            "pincode": 10,
            "profile_image": 20,
        }

        filled = 0

        if (self.username or "").strip():
            filled += weights["username"]
        if (self.email or "").strip():
            filled += weights["email"]
        if (self.phone or "").strip():
            filled += weights["phone"]
        if (self.company_name or "").strip():
            filled += weights["company_name"]
        if (self.address or "").strip():
            filled += weights["address"]
        if (self.city or "").strip():
            filled += weights["city"]
        if (self.state or "").strip():
            filled += weights["state"]
        if (self.pincode or "").strip():
            filled += weights["pincode"]
        if self.profile_image:
            filled += weights["profile_image"]

        return min(100, filled)


class DistributorActivityLog(models.Model):
    ACTION_LOGIN_SUCCESS = "LOGIN_SUCCESS"
    ACTION_LOGIN_FAILED = "LOGIN_FAILED"
    ACTION_LOGOUT = "LOGOUT"
    ACTION_REGISTER = "REGISTER"
    ACTION_PROFILE_UPDATE = "PROFILE_UPDATE"
    ACTION_PASSWORD_CHANGE = "PASSWORD_CHANGE"
    ACTION_FORGOT_PASSWORD_REQUEST = "FORGOT_PASSWORD_REQUEST"
    ACTION_RESET_PASSWORD_SUCCESS = "RESET_PASSWORD_SUCCESS"
    ACTION_RESET_PASSWORD_FAILED = "RESET_PASSWORD_FAILED"

    distributor = models.ForeignKey(
        Distributor,
        on_delete=models.CASCADE,
        related_name="activity_logs",
        blank=True,
        null=True,
    )

    email = models.EmailField(blank=True, null=True)
    action = models.CharField(max_length=64)
    ip_address = models.CharField(max_length=45, blank=True, null=True)
    user_agent = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=["email", "action", "created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} - {self.email or (self.distributor and self.distributor.email) or 'unknown'}"


class DistributorPasswordResetOTP(models.Model):
    distributor = models.ForeignKey(
        Distributor,
        on_delete=models.CASCADE,
        related_name="password_reset_otps",
        blank=True,
        null=True,
    )

    email = models.EmailField()
    # Store only hashed OTP for security.
    otp_hash = models.CharField(max_length=128)

    # Used prevents OTP replay
    is_used = models.BooleanField(default=False)

    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()

    class Meta:
        indexes = [
            models.Index(fields=["email", "expires_at", "is_used"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"OTP reset for {self.email} (used={self.is_used})"

