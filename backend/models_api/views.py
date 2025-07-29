from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.utils import timezone
from django.http import HttpResponse, Http404, FileResponse
from django.conf import settings
import os
import secrets
import mimetypes
import json
from .models import ModelFile, ModelAccess, ModelDownload
from .serializers import ModelFileSerializer
from .storage import secure_storage, download_manager

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def available_models(request):
    """Get list of models available to user based on their subscription"""
    user = request.user
    
    # Import access controller
    from .access_control import access_controller
    
    # Get user's access summary
    access_summary = access_controller.get_user_access_summary(user)
    
    # Get all active models
    all_models = ModelFile.objects.filter(is_active=True)
    
    # Filter models based on access control
    available_models = []
    restricted_models = []
    
    for model in all_models:
        access_check = access_controller.check_model_access(user, model.name)
        
        model_data = ModelFileSerializer(model).data
        model_data['access_status'] = access_check
        
        if access_check.get('allowed', False):
            available_models.append(model_data)
            
            # Create or update model access record
            ModelAccess.objects.get_or_create(
                user=user,
                model=model,
                defaults={'access_granted': True}
            )
        else:
            restricted_models.append(model_data)
    
    return Response({
        'available_models': available_models,
        'restricted_models': restricted_models,
        'user_plan': getattr(user, 'subscription_plan', 'free'),
        'subscription_expires': getattr(user, 'subscription_expires', None),
        'total_available': len(available_models),
        'total_restricted': len(restricted_models),
        'access_summary': access_summary,
        'upgrade_info': {
            'current_plan': getattr(user, 'subscription_plan', 'free'),
            'available_plans': ['free', 'pro', 'enterprise'],
            'upgrade_benefits': {
                'pro': ['Access to Mistral 7B model', 'Increased download limits', 'Priority support'],
                'enterprise': ['All models', 'Unlimited downloads', 'Custom model support']
            }
        }
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
    
    # Import access controller
    from .access_control import access_controller
    
    # Check if user has access to this model using access controller
    access_check = access_controller.check_model_access(user, model.name)
    
    if not access_check.get('allowed', False):
        return Response({
            'error': 'Access denied to this model',
            'reason': access_check.get('reason'),
            'message': access_check.get('message'),
            'access_details': access_check
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Check if model is available in secure storage
    storage_stats = secure_storage.get_storage_stats(model.name)
    if not storage_stats.get('exists'):
        return Response({
            'error': 'Model not available in secure storage',
            'message': 'Please contact administrator to initialize model storage'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    # Generate download token using authenticated download manager
    download_token = download_manager.create_download_url(
        user, model.name, expires_in=3600
    )
    
    if not download_token:
        return Response({
            'error': 'Failed to create download token'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Create download record for tracking
    download_record = ModelDownload.objects.create(
        user=user,
        model=model,
        download_token=download_token,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )
    
    # Record download attempt for analytics
    access_controller.record_download_attempt(
        user=user,
        model_name=model.name,
        success=True,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )
    
    # Get available blocks information
    available_blocks = secure_storage.list_model_blocks(model.name)
    
    return Response({
        'download_token': download_token,
        'model_info': ModelFileSerializer(model).data,
        'expires_in': 3600,  # 1 hour
        'download_url': f'/api/v1/models/download/{download_token}/',
        'access_info': access_check,
        'storage_info': {
            'encrypted': True,
            'total_size': storage_stats.get('total_size', 0),
            'block_count': len(available_blocks),
            'encryption_type': 'AES-256-GCM'
        },
        'available_endpoints': {
            'model_info': f'/api/v1/models/download/{download_token}/',
            'metadata': f'/api/v1/models/download/{download_token}/metadata/',
            'tokenizer': f'/api/v1/models/download/{download_token}/tokenizer/',
            'blocks': [
                f'/api/v1/models/download/{download_token}/block/{block["block_id"]}/'
                for block in available_blocks
            ]
        }
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
    
    # Get storage statistics
    storage_stats = secure_storage.get_storage_stats(model.name)
    
    if not storage_stats.get('exists'):
        return Response({
            'error': 'Model files not available in secure storage'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Get encrypted model metadata
    encrypted_metadata = secure_storage.retrieve_model_metadata(model.name)
    
    # List available blocks
    available_blocks = secure_storage.list_model_blocks(model.name)
    
    return Response({
        'model_name': model.name,
        'display_name': model.display_name,
        'version': model.version,
        'block_count': len(available_blocks),
        'file_size': model.file_size,
        'encrypted_size': storage_stats.get('total_size', 0),
        'blocks': [
            {
                'block_id': block['block_id'],
                'filename': f'block_{block["block_id"]}.onnx',
                'encrypted_size': block.get('file_size', 0),
                'original_size': block.get('original_size', 0),
                'download_url': f'/api/v1/models/download/{download_token}/block/{block["block_id"]}/'
            }
            for block in available_blocks
        ],
        'tokenizer': {
            'download_url': f'/api/v1/models/download/{download_token}/tokenizer/'
        },
        'metadata': {
            'download_url': f'/api/v1/models/download/{download_token}/metadata/',
            'encrypted': encrypted_metadata is not None
        },
        'security_info': {
            'encryption': 'AES-256-GCM',
            'integrity_check': True,
            'access_control': True
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

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_desktop_app_info(request):
    """Get desktop application download information"""
    user = request.user
    
    # Check user's subscription plan for download access
    if user.subscription_plan not in ['pro', 'enterprise']:
        return Response({
            'error': 'Desktop app download requires Pro or Enterprise subscription',
            'current_plan': user.subscription_plan,
            'upgrade_required': True
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Available desktop app versions
    app_versions = [
        {
            'name': 'TikTrue Desktop App (Production)',
            'version': '1.0.0',
            'filename': 'TikTrue_Real_Build.exe',
            'description': 'Production-ready desktop application with full features',
            'size_mb': 45.2,
            'requirements': 'Windows 10/11, 4GB RAM, 2GB Storage',
            'download_url': f'/api/v1/downloads/desktop-app/TikTrue_Real_Build.exe'
        },
        {
            'name': 'TikTrue Desktop App (GUI)',
            'version': '1.0.0',
            'filename': 'TikTrue_Working_GUI.exe',
            'description': 'GUI version with user-friendly interface',
            'size_mb': 42.8,
            'requirements': 'Windows 10/11, 4GB RAM, 2GB Storage',
            'download_url': f'/api/v1/downloads/desktop-app/TikTrue_Working_GUI.exe'
        },
        {
            'name': 'TikTrue Desktop App (Console)',
            'version': '1.0.0',
            'filename': 'TikTrue_Working_Console.exe',
            'description': 'Console version for advanced users',
            'size_mb': 38.5,
            'requirements': 'Windows 10/11, 4GB RAM, 2GB Storage',
            'download_url': f'/api/v1/downloads/desktop-app/TikTrue_Working_Console.exe'
        }
    ]
    
    return Response({
        'user_plan': user.subscription_plan,
        'download_access': True,
        'available_versions': app_versions,
        'installation_guide': '/api/v1/downloads/installation-guide/',
        'support_contact': 'support@tiktrue.com'
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_desktop_app(request, filename):
    """Download desktop application file"""
    user = request.user
    
    # Check user's subscription plan
    if user.subscription_plan not in ['pro', 'enterprise']:
        return Response({
            'error': 'Desktop app download requires Pro or Enterprise subscription'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Allowed filenames for security
    allowed_files = [
        'TikTrue_Real_Build.exe',
        'TikTrue_Working_GUI.exe',
        'TikTrue_Working_Console.exe',
        'TikTrue_GUI_Test.exe',
        'TikTrue_BuildTest.exe'
    ]
    
    if filename not in allowed_files:
        return Response({
            'error': 'File not found or access denied'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Construct file path
    file_path = os.path.join(settings.BASE_DIR.parent, 'dist', filename)
    
    # Check if file exists
    if not os.path.exists(file_path):
        return Response({
            'error': 'File not available for download'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Log download attempt
    try:
        from django.contrib.admin.models import LogEntry, ADDITION
        from django.contrib.contenttypes.models import ContentType
        
        LogEntry.objects.log_action(
            user_id=user.id,
            content_type_id=ContentType.objects.get_for_model(user.__class__).pk,
            object_id=user.id,
            object_repr=f"Desktop App Download: {filename}",
            action_flag=ADDITION,
            change_message=f"Downloaded {filename} from IP: {get_client_ip(request)}"
        )
    except Exception as e:
        # Log error but don't fail the download
        print(f"Failed to log download: {e}")
    
    # Determine content type
    content_type, _ = mimetypes.guess_type(file_path)
    if not content_type:
        content_type = 'application/octet-stream'
    
    # Create file response
    try:
        response = FileResponse(
            open(file_path, 'rb'),
            content_type=content_type,
            as_attachment=True,
            filename=filename
        )
        
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        
        return response
        
    except Exception as e:
        return Response({
            'error': f'Failed to serve file: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([AllowAny])
def installation_guide(request):
    """Get installation guide for desktop app"""
    guide = {
        'title': 'TikTrue Desktop App Installation Guide',
        'version': '1.0.0',
        'steps': [
            {
                'step': 1,
                'title': 'Download the Application',
                'description': 'Download the appropriate version for your needs from your dashboard',
                'note': 'Choose Production build for normal use, GUI for user-friendly interface, or Console for advanced features'
            },
            {
                'step': 2,
                'title': 'Run as Administrator',
                'description': 'Right-click the downloaded .exe file and select "Run as administrator"',
                'note': 'Administrator privileges are required for proper installation'
            },
            {
                'step': 3,
                'title': 'Follow Installation Wizard',
                'description': 'Follow the on-screen instructions to complete installation',
                'note': 'Default installation path is recommended'
            },
            {
                'step': 4,
                'title': 'First Run Setup',
                'description': 'Launch the application and complete the initial setup wizard',
                'note': 'You will need your TikTrue account credentials'
            },
            {
                'step': 5,
                'title': 'License Activation',
                'description': 'Enter your license key when prompted',
                'note': 'License key is available in your dashboard'
            }
        ],
        'system_requirements': {
            'os': 'Windows 10 or Windows 11',
            'ram': '4GB minimum, 8GB recommended',
            'storage': '2GB free space',
            'network': 'Internet connection for initial setup and updates'
        },
        'troubleshooting': [
            {
                'issue': 'Installation fails',
                'solution': 'Ensure you are running as administrator and antivirus is not blocking the file'
            },
            {
                'issue': 'License activation fails',
                'solution': 'Check your internet connection and verify your license key from the dashboard'
            },
            {
                'issue': 'Application won\'t start',
                'solution': 'Check Windows Event Viewer for error details and contact support'
            }
        ],
        'support': {
            'email': 'support@tiktrue.com',
            'documentation': 'https://docs.tiktrue.com',
            'community': 'https://community.tiktrue.com'
        }
    }
    
    return Response(guide)

def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_model_block(request, download_token, block_id):
    """Download specific model block using secure token"""
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
    
    try:
        block_id = int(block_id)
    except ValueError:
        return Response({'error': 'Invalid block ID'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Serve model block using authenticated download manager
    client_ip = get_client_ip(request)
    result = download_manager.serve_model_block(download_token, request.user.id, client_ip)
    
    if result is None:
        return Response({'error': 'Block not found or access denied'}, status=status.HTTP_404_NOT_FOUND)
    
    block_data, content_type = result
    
    # Create HTTP response with block data
    response = HttpResponse(block_data, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="block_{block_id}.onnx"'
    response['Content-Length'] = len(block_data)
    
    # Add security headers
    response['X-Content-Type-Options'] = 'nosniff'
    response['X-Frame-Options'] = 'DENY'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    
    return response

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_model_metadata(request, download_token):
    """Download model metadata using secure token"""
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
    
    # Get encrypted metadata from secure storage
    metadata = secure_storage.retrieve_model_metadata(model.name)
    
    if metadata is None:
        return Response({'error': 'Metadata not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Return metadata as JSON response
    response = HttpResponse(
        json.dumps(metadata, indent=2),
        content_type='application/json'
    )
    response['Content-Disposition'] = f'attachment; filename="{model.name}_metadata.json"'
    
    # Add security headers
    response['X-Content-Type-Options'] = 'nosniff'
    response['X-Frame-Options'] = 'DENY'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    
    return response

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_model_tokenizer(request, download_token):
    """Download model tokenizer using secure token"""
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
    
    # Look for tokenizer files in assets
    tokenizer_path = os.path.join(
        settings.BASE_DIR.parent, 'assets', 'models', 
        model.name, 'blocks', 'tokenizer'
    )
    
    if not os.path.exists(tokenizer_path):
        return Response({'error': 'Tokenizer not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Create a zip file with tokenizer contents
    import zipfile
    import io
    
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(tokenizer_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, tokenizer_path)
                zip_file.write(file_path, arcname)
    
    zip_buffer.seek(0)
    
    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{model.name}_tokenizer.zip"'
    response['Content-Length'] = len(zip_buffer.getvalue())
    
    # Add security headers
    response['X-Content-Type-Options'] = 'nosniff'
    response['X-Frame-Options'] = 'DENY'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    
    return response

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def model_storage_stats(request, model_id):
    """Get storage statistics for a model"""
    user = request.user
    
    try:
        model = ModelFile.objects.get(id=model_id, is_active=True)
    except ModelFile.DoesNotExist:
        return Response({'error': 'Model not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Check access
    allowed_models = user.get_allowed_models()
    if model.name not in allowed_models:
        return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
    
    # Get storage statistics
    stats = secure_storage.get_storage_stats(model.name)
    
    if not stats.get('exists'):
        return Response({
            'model_name': model.name,
            'encrypted': False,
            'available': False,
            'message': 'Model not available in secure storage'
        })
    
    # Get block information
    blocks = secure_storage.list_model_blocks(model.name)
    
    return Response({
        'model_name': model.name,
        'encrypted': True,
        'available': True,
        'total_encrypted_size': stats.get('total_size', 0),
        'block_count': len(blocks),
        'storage_path': stats.get('storage_path'),
        'blocks': [
            {
                'block_id': block['block_id'],
                'encrypted_size': block.get('file_size', 0),
                'original_size': block.get('original_size', 0),
                'stored_at': block.get('stored_at')
            }
            for block in blocks
        ],
        'security_features': {
            'encryption': 'AES-256-GCM',
            'integrity_verification': True,
            'access_control': True,
            'secure_deletion': True
        }
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_model_integrity(request, model_id):
    """Verify integrity of encrypted model blocks"""
    user = request.user
    
    try:
        model = ModelFile.objects.get(id=model_id, is_active=True)
    except ModelFile.DoesNotExist:
        return Response({'error': 'Model not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Check access
    allowed_models = user.get_allowed_models()
    if model.name not in allowed_models:
        return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
    
    # Verify model integrity
    blocks = secure_storage.list_model_blocks(model.name)
    verification_results = []
    
    for block_info in blocks:
        block_id = block_info['block_id']
        
        # Try to retrieve and verify block
        block_data = secure_storage.retrieve_model_block(
            model.name, block_id, verify_integrity=True
        )
        
        verification_results.append({
            'block_id': block_id,
            'verified': block_data is not None,
            'size': len(block_data) if block_data else 0,
            'stored_at': block_info.get('stored_at')
        })
    
    # Check metadata integrity
    metadata = secure_storage.retrieve_model_metadata(model.name)
    metadata_verified = metadata is not None
    
    # Calculate overall status
    verified_blocks = sum(1 for result in verification_results if result['verified'])
    total_blocks = len(verification_results)
    
    return Response({
        'model_name': model.name,
        'overall_status': 'verified' if verified_blocks == total_blocks and metadata_verified else 'failed',
        'verified_blocks': verified_blocks,
        'total_blocks': total_blocks,
        'metadata_verified': metadata_verified,
        'block_results': verification_results,
        'verification_timestamp': timezone.now().isoformat()
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_model_access(request, model_id):
    """Check if user has access to a specific model"""
    user = request.user
    
    try:
        model = ModelFile.objects.get(id=model_id, is_active=True)
    except ModelFile.DoesNotExist:
        return Response({'error': 'Model not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Import access controller
    from .access_control import access_controller
    
    # Check access
    access_result = access_controller.check_model_access(user, model.name)
    
    # Add model information to response
    access_result['model_info'] = {
        'id': str(model.id),
        'name': model.name,
        'display_name': model.display_name,
        'version': model.version,
        'block_count': model.block_count
    }
    
    return Response(access_result)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_access_summary(request):
    """Get comprehensive access summary for current user"""
    user = request.user
    
    # Import access controller
    from .access_control import access_controller
    
    # Get access summary
    summary = access_controller.get_user_access_summary(user)
    
    return Response(summary)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_usage_analytics(request):
    """Get usage analytics for current user"""
    user = request.user
    days = int(request.GET.get('days', 30))
    
    # Import usage analytics
    from .access_control import usage_analytics
    
    # Get usage statistics
    stats = usage_analytics.get_user_usage_stats(user, days)
    
    return Response(stats)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def model_usage_analytics(request, model_id):
    """Get usage analytics for a specific model (admin only)"""
    user = request.user
    
    # Check if user is admin/staff
    if not (user.is_staff or user.is_superuser):
        return Response({
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        model = ModelFile.objects.get(id=model_id, is_active=True)
    except ModelFile.DoesNotExist:
        return Response({'error': 'Model not found'}, status=status.HTTP_404_NOT_FOUND)
    
    days = int(request.GET.get('days', 30))
    
    # Import usage analytics
    from .access_control import usage_analytics
    
    # Get model usage statistics
    stats = usage_analytics.get_model_usage_stats(model.name, days)
    
    return Response(stats)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_usage_overview(request):
    """Get system-wide usage overview (admin only)"""
    user = request.user
    
    # Check if user is admin/staff
    if not (user.is_staff or user.is_superuser):
        return Response({
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    days = int(request.GET.get('days', 30))
    
    # Import usage analytics
    from .access_control import usage_analytics
    
    # Get system usage overview
    overview = usage_analytics.get_system_usage_overview(days)
    
    return Response(overview)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def record_download_completion(request, download_token):
    """Record download completion for analytics"""
    user = request.user
    
    try:
        download_record = ModelDownload.objects.get(
            download_token=download_token,
            user=user
        )
    except ModelDownload.DoesNotExist:
        return Response({'error': 'Download record not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Mark download as completed
    download_record.is_completed = True
    download_record.completed_at = timezone.now()
    download_record.save()
    
    # Import access controller for recording
    from .access_control import access_controller
    
    # Record successful download
    success = access_controller.record_download_attempt(
        user=user,
        model_name=download_record.model.name,
        success=True,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )
    
    return Response({
        'success': True,
        'download_completed': True,
        'completed_at': download_record.completed_at.isoformat(),
        'analytics_recorded': success
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def subscription_limits(request):
    """Get current user's subscription limits and usage"""
    user = request.user
    
    # Import access controller
    from .access_control import access_controller
    
    subscription_plan = getattr(user, 'subscription_plan', 'free')
    access_config = access_controller.MODEL_ACCESS_MATRIX.get(
        subscription_plan, 
        access_controller.MODEL_ACCESS_MATRIX['free']
    )
    
    # Calculate current usage
    today_downloads = 0
    concurrent_downloads = 0
    
    for model_name in access_config['allowed_models']:
        today_downloads += access_controller._get_daily_download_count(user, model_name)
    
    concurrent_downloads = access_controller._get_concurrent_download_count(user)
    
    # Calculate remaining limits
    daily_limit = access_config['max_downloads_per_day']
    concurrent_limit = access_config['max_concurrent_downloads']
    
    return Response({
        'subscription_plan': subscription_plan,
        'subscription_expires': getattr(user, 'subscription_expires', None),
        'limits': {
            'daily_downloads': daily_limit,
            'concurrent_downloads': concurrent_limit
        },
        'current_usage': {
            'daily_downloads': today_downloads,
            'concurrent_downloads': concurrent_downloads
        },
        'remaining': {
            'daily_downloads': daily_limit - today_downloads if daily_limit > 0 else -1,
            'concurrent_downloads': concurrent_limit - concurrent_downloads
        },
        'features': access_config['features'],
        'allowed_models': access_config['allowed_models'],
        'reset_time': access_controller._get_next_reset_time().isoformat()
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_bulk_access(request):
    """Validate access to multiple models at once"""
    user = request.user
    model_names = request.data.get('model_names', [])
    
    if not isinstance(model_names, list):
        return Response({
            'error': 'model_names must be a list'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Import access controller
    from .access_control import access_controller
    
    results = {}
    
    for model_name in model_names:
        try:
            # Check if model exists
            model = ModelFile.objects.get(name=model_name, is_active=True)
            
            # Check access
            access_result = access_controller.check_model_access(user, model_name)
            results[model_name] = access_result
            
        except ModelFile.DoesNotExist:
            results[model_name] = {
                'allowed': False,
                'reason': 'model_not_found',
                'message': f'Model {model_name} not found'
            }
    
    # Summary statistics
    total_models = len(model_names)
    allowed_models = sum(1 for result in results.values() if result.get('allowed', False))
    
    return Response({
        'results': results,
        'summary': {
            'total_requested': total_models,
            'allowed': allowed_models,
            'denied': total_models - allowed_models,
            'access_rate': (allowed_models / total_models * 100) if total_models > 0 else 0
        }
    })