from rest_framework import serializers
from .models import License, LicenseValidation

class LicenseSerializer(serializers.ModelSerializer):
    is_valid = serializers.SerializerMethodField()
    
    class Meta:
        model = License
        fields = [
            'id', 'license_key', 'hardware_bound', 'expires_at',
            'is_active', 'usage_count', 'last_validated', 'created_at',
            'is_valid'
        ]
        read_only_fields = ['id', 'license_key', 'usage_count', 'last_validated', 'created_at']
    
    def get_is_valid(self, obj):
        return obj.is_valid()

class LicenseValidationSerializer(serializers.ModelSerializer):
    class Meta:
        model = LicenseValidation
        fields = [
            'id', 'hardware_fingerprint', 'ip_address', 'user_agent',
            'validated_at', 'is_successful'
        ]
        read_only_fields = ['id', 'validated_at']