from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.http import HttpResponse, Http404
from django.conf import settings
import os
import secrets
from .models import ModelFile, ModelAccess, ModelDownload
from .serializers import ModelFileSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def available_models(request):
    """Get list of models available to user based on their subscription"""
    user = request.user
    allowed_models = user.get_allowed_models()
    
    # Get active models that user has access to
    models = ModelFile.objects.filter(
        name__in=allowed_models,
        is_active=True
    )
    
    # Create or update model access records
    for model in models:
        ModelAccess.objects.get_or_create(
            user=user,
            model=model,
            defaults={'access_granted': True}
        )
    
    serializer = ModelFileSerializer(models, many=True)
    return Response({
        'models': serializer.data,
        'user_plan': user.subscription_plan,
        'total_models': models.count()
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_download_token(request, model_id):
    """Create a secure download token for model"""
    user = request.user
    
    try:
        model = ModelFile.objects.get(id=model_id, is_active=True)
    except ModelFile.DoesNotExist:
        return Response({'error': 'Model not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Check if user has access to this model
    allowed_models = user.get_allowed_models()
    if model.name not in allowed_models:
        return Response({'error': 'Access denied to this model'}, status=status.HTTP_403_FORBIDDEN)
    
    # Generate download token
    download_token = secrets.token_urlsafe(32)
    
    # Create download record
    download_record = ModelDownload.objects.create(
        user=user,
        model=model,
        download_token=download_token,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )
    
    # Update model access
    model_access, created = ModelAccess.objects.get_or_create(
        user=user,
        model=model,
        defaults={'access_granted': True}
    )
    model_access.download_count += 1
    model_access.last_download = timezone.now()
    model_access.save()
    
    return Response({
        'download_token': download_token,
        'model_info': ModelFileSerializer(model).data,
        'expires_in': 3600,  # 1 hour
        'download_url': f'/api/v1/models/download/{download_token}/'
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_model(request, download_token):
    """Download model using secure token"""
    try:
        download_record = ModelDownload.objects.get(
            download_token=download_token,
            user=request.user,
            is_completed=False
        )
    except ModelDownload.DoesNotExist:
        return Response({'error': 'Invalid or expired download token'}, status=status.HTTP_404_NOT_FOUND)
    
    # Check if token is not too old (1 hour)
    if (timezone.now() - download_record.started_at).seconds > 3600:
        return Response({'error': 'Download token expired'}, status=status.HTTP_410_GONE)
    
    model = download_record.model
    
    # For MVP, return model metadata and block information
    # In production, this would serve actual model files
    return Response({
        'model_name': model.name,
        'display_name': model.display_name,
        'version': model.version,
        'block_count': model.block_count,
        'file_size': model.file_size,
        'blocks': [
            {
                'block_id': i + 1,
                'filename': f'block_{i + 1}.onnx',
                'download_url': f'/api/v1/models/download/{download_token}/block/{i + 1}/'
            }
            for i in range(model.block_count)
        ],
        'tokenizer': {
            'download_url': f'/api/v1/models/download/{download_token}/tokenizer/'
        },
        'metadata': {
            'download_url': f'/api/v1/models/download/{download_token}/metadata/'
        }
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def model_metadata(request, model_id):
    """Get model metadata without downloading"""
    user = request.user
    
    try:
        model = ModelFile.objects.get(id=model_id, is_active=True)
    except ModelFile.DoesNotExist:
        return Response({'error': 'Model not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Check access
    allowed_models = user.get_allowed_models()
    if model.name not in allowed_models:
        return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
    
    return Response(ModelFileSerializer(model).data)

def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip