from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid

class User(AbstractUser):
    """Custom User model for TikTrue platform"""
    
    PLAN_CHOICES = [
        ('free', 'Free'),
        ('pro', 'Pro'),
        ('enterprise', 'Enterprise'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    subscription_plan = models.CharField(
        max_length=20, 
        choices=PLAN_CHOICES, 
        default='enterprise'  # MVP: همه Enterprise
    )
    subscription_expires = models.DateTimeField(null=True, blank=True)
    hardware_fingerprint = models.CharField(max_length=256, blank=True)
    max_clients = models.IntegerField(default=999)  # MVP: نامحدود
    allowed_models = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    def __str__(self):
        return self.email
    
    def get_allowed_models(self):
        """Get list of models user can access"""
        # MVP: همه مدل‌ها برای همه
        return [
            'llama3_1_8b_fp16',
            'mistral_7b_int4',
        ]