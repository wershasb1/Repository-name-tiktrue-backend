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
        # Capture command output
        output = io.StringIO()
        
        # Run migrations
        call_command('migrate', stdout=output, stderr=output)
        migrate_output = output.getvalue()
        
        # Setup initial data
        output = io.StringIO()
        call_command('setup_initial_data', stdout=output, stderr=output)
        setup_output = output.getvalue()
        
        return JsonResponse({
            'success': True,
            'message': 'Database setup completed successfully',
            'migrate_output': migrate_output,
            'setup_output': setup_output
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@require_http_methods(["GET"])
def health_check(request):
    """Simple health check endpoint"""
    return JsonResponse({
        'status': 'healthy',
        'message': 'TikTrue Backend is running'
    })