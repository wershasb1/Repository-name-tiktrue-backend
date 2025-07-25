from django.http import JsonResponse
from django.core.management import call_command
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import io
import sys

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
    """Simple health check endpoint"""
    return JsonResponse({
        'status': 'healthy',
        'message': 'TikTrue Backend is running'
    })