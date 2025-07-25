from rest_framework import serializers
from .models import ModelFile, ModelAccess, ModelDownload

class ModelFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelFile
        fields = [
            'id', 'name', 'display_name', 'description', 'version',
            'file_size', 'block_count', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class ModelAccessSerializer(serializers.ModelSerializer):
    model = ModelFileSerializer(read_only=True)
    
    class Meta:
        model = ModelAccess
        fields = [
            'id', 'model', 'access_granted', 'download_count',
            'last_download', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

class ModelDownloadSerializer(serializers.ModelSerializer):
    model = ModelFileSerializer(read_only=True)
    
    class Meta:
        model = ModelDownload
        fields = [
            'id', 'model', 'download_token', 'is_completed',
            'started_at', 'completed_at'
        ]
        read_only_fields = ['id', 'download_token', 'started_at', 'completed_at']