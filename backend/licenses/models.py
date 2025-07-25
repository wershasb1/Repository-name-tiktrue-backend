from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid
import secrets
import string

class License(models.Model):
    """License model for TikTrue desktop application"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='licenses')
    license_key = models.CharField(max_length=64, unique=True)
    hardware_bound = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    usage_count = models.IntegerField(default=0)
    last_validated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        if not self.license_key:
            self.license_key = self.generate_license_key()
        super().save(*args, **kwargs)
    
    def generate_license_key(self):
        """Generate a unique license key"""
        chars = string.ascii_uppercase + string.digits
        key = ''.join(secrets.choice(chars) for _ in range(32))
        # Format as XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX
        formatted_key = '-'.join([key[i:i+4] for i in range(0, len(key), 4)])
        return formatted_key
    
    def is_valid(self):
        """Check if license is valid"""
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True
    
    def __str__(self):
        return f"{self.user.email} - {self.license_key[:16]}..."

class LicenseValidation(models.Model):
    """Track license validation attempts"""
    
    license = models.ForeignKey(License, on_delete=models.CASCADE, related_name='validations')
    hardware_fingerprint = models.CharField(max_length=256)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    validated_at = models.DateTimeField(auto_now_add=True)
    is_successful = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-validated_at']
    
    def __str__(self):
        return f"{self.license.license_key[:16]}... - {self.validated_at}"