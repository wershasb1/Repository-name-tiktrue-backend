from django.db import models
from django.conf import settings
import uuid

class ModelFile(models.Model):
    """Model file information and metadata"""
    
    MODEL_TYPES = [
        ('llama3_1_8b_fp16', 'Llama 3.1 8B FP16'),
        ('mistral_7b_int4', 'Mistral 7B INT4'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, choices=MODEL_TYPES, unique=True)
    display_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    version = models.CharField(max_length=50, default='1.0.0')
    file_size = models.BigIntegerField(help_text='Size in bytes')
    block_count = models.IntegerField(help_text='Number of model blocks')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.display_name

class ModelAccess(models.Model):
    """Track model access and downloads per user"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    model = models.ForeignKey(ModelFile, on_delete=models.CASCADE)
    access_granted = models.BooleanField(default=True)
    download_count = models.IntegerField(default=0)
    last_download = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'model']
    
    def __str__(self):
        return f"{self.user.email} - {self.model.name}"

class ModelDownload(models.Model):
    """Track individual model download sessions"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    model = models.ForeignKey(ModelFile, on_delete=models.CASCADE)
    download_token = models.CharField(max_length=64, unique=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    is_completed = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.model.name} - {self.started_at}"