from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from .models import License, LicenseValidation
from .serializers import LicenseSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def validate_license(request):
    """Validate user's license for desktop application"""
    user = request.user
    hardware_fingerprint = request.GET.get('hardware_fingerprint', '')
    
    # Get or create license for user
    license_obj, created = License.objects.get_or_create(
        user=user,
        defaults={
            'is_active': True,
            'expires_at': None,  # MVP: no expiration
        }
    )
    
    # Log validation attempt
    LicenseValidation.objects.create(
        license=license_obj,
        hardware_fingerprint=hardware_fingerprint,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        is_successful=license_obj.is_valid()
    )
    
    # Update usage count
    license_obj.usage_count += 1
    license_obj.save()
    
    if license_obj.is_valid():
        return Response({
            'valid': True,
            'license': LicenseSerializer(license_obj).data,
            'user_info': {
                'subscription_plan': user.subscription_plan,
                'max_clients': user.max_clients,
                'allowed_models': user.get_allowed_models(),
            }
        })
    else:
        return Response({
            'valid': False,
            'message': 'License is not valid or has expired'
        }, status=status.HTTP_403_FORBIDDEN)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def license_info(request):
    """Get detailed license information"""
    user = request.user
    
    try:
        license_obj = License.objects.get(user=user)
        return Response({
            'license': LicenseSerializer(license_obj).data,
            'user_info': {
                'email': user.email,
                'subscription_plan': user.subscription_plan,
                'max_clients': user.max_clients,
                'allowed_models': user.get_allowed_models(),
                'subscription_expires': user.subscription_expires,
            }
        })
    except License.DoesNotExist:
        return Response({
            'error': 'No license found for user'
        }, status=status.HTTP_404_NOT_FOUND)

def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip