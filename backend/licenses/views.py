from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from .models import License, LicenseValidation
from .serializers import LicenseSerializer
from .hardware_fingerprint import (
    HardwareFingerprintValidator,
    LicenseHardwareBinding,
    generate_hardware_fingerprint
)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def validate_license(request):
    """Validate user's license for desktop application with hardware fingerprinting"""
    user = request.user
    hardware_fingerprint = request.GET.get('hardware_fingerprint', '')
    
    # Validate hardware fingerprint format if provided
    if hardware_fingerprint and not HardwareFingerprintValidator.is_fingerprint_format_valid(hardware_fingerprint):
        return Response({
            'valid': False,
            'message': 'Invalid hardware fingerprint format'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get or create license for user
    license_obj, created = License.objects.get_or_create(
        user=user,
        defaults={
            'is_active': True,
            'expires_at': None,  # MVP: no expiration
        }
    )
    
    # Check if license is valid
    license_valid = license_obj.is_valid()
    
    # Check hardware binding if license is valid
    hardware_valid = True
    if license_valid and hardware_fingerprint:
        hardware_valid = LicenseHardwareBinding.validate_license_hardware(
            license_obj, hardware_fingerprint
        )
    
    # Overall validation result
    validation_successful = license_valid and hardware_valid
    
    # Log validation attempt
    LicenseValidation.objects.create(
        license=license_obj,
        hardware_fingerprint=hardware_fingerprint,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        is_successful=validation_successful
    )
    
    # Update usage count
    license_obj.usage_count += 1
    license_obj.save()
    
    if validation_successful:
        return Response({
            'valid': True,
            'license': LicenseSerializer(license_obj).data,
            'user_info': {
                'subscription_plan': user.subscription_plan,
                'max_clients': user.max_clients,
                'allowed_models': user.get_allowed_models(),
            },
            'hardware_info': {
                'bound': license_obj.hardware_bound,
                'fingerprint_provided': bool(hardware_fingerprint),
                'fingerprint_valid': hardware_valid,
            }
        })
    else:
        error_message = 'License is not valid or has expired'
        if license_valid and not hardware_valid:
            error_message = 'License is not valid for this hardware'
        
        return Response({
            'valid': False,
            'message': error_message,
            'hardware_info': {
                'bound': license_obj.hardware_bound,
                'fingerprint_provided': bool(hardware_fingerprint),
                'fingerprint_valid': hardware_valid,
            }
        }, status=status.HTTP_403_FORBIDDEN)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def license_info(request):
    """Get detailed license information"""
    user = request.user
    
    try:
        license_obj = License.objects.get(user=user)
        
        # Get hardware fingerprint info if available
        hardware_info = {}
        if user.hardware_fingerprint:
            from .hardware_fingerprint import LicenseHardwareBinding
            hardware_info = LicenseHardwareBinding.get_hardware_info_summary(
                user.hardware_fingerprint
            )
        
        return Response({
            'license': LicenseSerializer(license_obj).data,
            'user_info': {
                'email': user.email,
                'subscription_plan': user.subscription_plan,
                'max_clients': user.max_clients,
                'allowed_models': user.get_allowed_models(),
                'subscription_expires': user.subscription_expires,
            },
            'hardware_info': hardware_info
        })
    except License.DoesNotExist:
        return Response({
            'error': 'No license found for user'
        }, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_fingerprint(request):
    """Generate hardware fingerprint for current system (for testing/development)"""
    try:
        fingerprint = generate_hardware_fingerprint()
        
        return Response({
            'hardware_fingerprint': fingerprint,
            'format_valid': HardwareFingerprintValidator.is_fingerprint_format_valid(fingerprint),
            'length': len(fingerprint),
            'type': 'SHA-256 Hash',
            'note': 'This endpoint is for development/testing purposes only'
        })
    except Exception as e:
        return Response({
            'error': f'Failed to generate hardware fingerprint: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip