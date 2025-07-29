from django.http import JsonResponse
from django.core.management import call_command
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import connection
from django.conf import settings
import io
import sys
import time

@csrf_exempt
@require_http_methods(["POST"])
def setup_database(request):
    """Setup database tables and initial data"""
    try:
        results = {}
        
        # 1. Create migrations for custom apps
        apps_to_migrate = ['accounts', 'licenses', 'models_api']
        
        for app in apps_to_migrate:
            output = io.StringIO()
            try:
                call_command('makemigrations', app, stdout=output, stderr=output)
                results[f'makemigrations_{app}'] = output.getvalue()
            except Exception as e:
                results[f'makemigrations_{app}_error'] = str(e)
        
        # 2. Run migrations
        output = io.StringIO()
        call_command('migrate', stdout=output, stderr=output)
        results['migrate'] = output.getvalue()
        
        # 3. Setup initial data
        output = io.StringIO()
        try:
            call_command('setup_initial_data', stdout=output, stderr=output)
            results['setup_data'] = output.getvalue()
        except Exception as e:
            results['setup_data_error'] = str(e)
        
        return JsonResponse({
            'success': True,
            'message': 'Database setup completed',
            'results': results
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'results': results if 'results' in locals() else {}
        }, status=500)

@require_http_methods(["GET"])
def health_check(request):
    """Comprehensive health check endpoint"""
    start_time = time.time()
    health_status = {
        'status': 'healthy',
        'timestamp': time.time(),
        'checks': {}
    }
    
    # Check database connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        health_status['checks']['database'] = {
            'status': 'healthy',
            'message': 'Database connection successful'
        }
    except Exception as e:
        health_status['status'] = 'unhealthy'
        health_status['checks']['database'] = {
            'status': 'unhealthy',
            'message': f'Database connection failed: {str(e)}'
        }
    
    # Check Django configuration
    try:
        secret_key_set = bool(settings.SECRET_KEY and settings.SECRET_KEY != 'django-insecure-development-key-only')
        health_status['checks']['configuration'] = {
            'status': 'healthy' if secret_key_set else 'warning',
            'debug_mode': settings.DEBUG,
            'secret_key_configured': secret_key_set,
            'allowed_hosts': len(settings.ALLOWED_HOSTS) > 0
        }
        
        if not secret_key_set and not settings.DEBUG:
            health_status['status'] = 'unhealthy'
            
    except Exception as e:
        health_status['status'] = 'unhealthy'
        health_status['checks']['configuration'] = {
            'status': 'unhealthy',
            'message': f'Configuration check failed: {str(e)}'
        }
    
    # Check CORS configuration
    try:
        cors_configured = hasattr(settings, 'CORS_ALLOWED_ORIGINS') and len(settings.CORS_ALLOWED_ORIGINS) > 0
        health_status['checks']['cors'] = {
            'status': 'healthy' if cors_configured else 'warning',
            'origins_configured': cors_configured,
            'credentials_allowed': getattr(settings, 'CORS_ALLOW_CREDENTIALS', False)
        }
    except Exception as e:
        health_status['checks']['cors'] = {
            'status': 'warning',
            'message': f'CORS check failed: {str(e)}'
        }
    
    # Calculate response time
    response_time = (time.time() - start_time) * 1000
    health_status['response_time_ms'] = round(response_time, 2)
    
    # Set HTTP status code based on health
    status_code = 200 if health_status['status'] == 'healthy' else 503
    
    return JsonResponse(health_status, status=status_code)