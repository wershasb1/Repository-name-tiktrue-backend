"""
Model Access Control System
Handles license-based access control and usage analytics for model downloads
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q, Count, Sum
from django.contrib.auth import get_user_model
import logging

from .models import ModelFile, ModelAccess, ModelDownload
from licenses.models import License

logger = logging.getLogger(__name__)

User = get_user_model()

class ModelAccessController:
    """
    Controls access to models based on user license levels and subscription plans
    """
    
    # Define model access levels based on subscription plans
    MODEL_ACCESS_MATRIX = {
        'free': {
            'allowed_models': ['llama3_1_8b_fp16'],  # Basic model only
            'max_downloads_per_day': 5,
            'max_concurrent_downloads': 1,
            'features': ['basic_inference']
        },
        'pro': {
            'allowed_models': ['llama3_1_8b_fp16', 'mistral_7b_int4'],
            'max_downloads_per_day': 50,
            'max_concurrent_downloads': 3,
            'features': ['basic_inference', 'advanced_inference', 'custom_models']
        },
        'enterprise': {
            'allowed_models': ['llama3_1_8b_fp16', 'mistral_7b_int4'],  # All models
            'max_downloads_per_day': -1,  # Unlimited
            'max_concurrent_downloads': 10,
            'features': ['basic_inference', 'advanced_inference', 'custom_models', 'priority_support']
        }
    }
    
    def __init__(self):
        self.analytics = ModelUsageAnalytics()
    
    def check_model_access(self, user, model_name: str) -> Dict:
        """
        Check if user has access to a specific model
        
        Args:
            user: User object
            model_name: Name of the model to check
            
        Returns:
            Dict with access information
        """
        try:
            # Get user's subscription plan
            subscription_plan = getattr(user, 'subscription_plan', 'free')
            
            # Check if subscription is active
            if hasattr(user, 'subscription_expires'):
                if user.subscription_expires and user.subscription_expires < timezone.now():
                    return {
                        'allowed': False,
                        'reason': 'subscription_expired',
                        'message': 'Your subscription has expired. Please renew to continue.',
                        'expires_at': user.subscription_expires.isoformat()
                    }
            
            # First check user's allowed_models field (if exists)
            if hasattr(user, 'get_allowed_models'):
                user_allowed_models = user.get_allowed_models()
                if user_allowed_models and model_name not in user_allowed_models:
                    return {
                        'allowed': False,
                        'reason': 'model_not_allowed_for_user',
                        'message': f'Model {model_name} is not allowed for your account.',
                        'allowed_models': user_allowed_models
                    }
            
            # Get access matrix for user's plan
            access_config = self.MODEL_ACCESS_MATRIX.get(subscription_plan, self.MODEL_ACCESS_MATRIX['free'])
            
            # Check if model is allowed for this plan
            if model_name not in access_config['allowed_models']:
                return {
                    'allowed': False,
                    'reason': 'model_not_in_plan',
                    'message': f'Model {model_name} is not available in your {subscription_plan} plan.',
                    'current_plan': subscription_plan,
                    'required_plans': self._get_plans_for_model(model_name),
                    'upgrade_required': True
                }
            
            # Check daily download limits
            daily_limit = access_config['max_downloads_per_day']
            if daily_limit > 0:
                today_downloads = self._get_daily_download_count(user, model_name)
                if today_downloads >= daily_limit:
                    return {
                        'allowed': False,
                        'reason': 'daily_limit_exceeded',
                        'message': f'Daily download limit ({daily_limit}) exceeded for {model_name}.',
                        'daily_limit': daily_limit,
                        'current_count': today_downloads,
                        'reset_time': self._get_next_reset_time().isoformat()
                    }
            
            # Check concurrent download limits
            concurrent_limit = access_config['max_concurrent_downloads']
            current_concurrent = self._get_concurrent_download_count(user)
            if current_concurrent >= concurrent_limit:
                return {
                    'allowed': False,
                    'reason': 'concurrent_limit_exceeded',
                    'message': f'Maximum concurrent downloads ({concurrent_limit}) reached.',
                    'concurrent_limit': concurrent_limit,
                    'current_count': current_concurrent
                }
            
            # Check license validity (if applicable)
            license_check = self._check_license_validity(user, model_name)
            if not license_check['valid']:
                return {
                    'allowed': False,
                    'reason': 'license_invalid',
                    'message': license_check['message'],
                    'license_status': license_check
                }
            
            # All checks passed
            return {
                'allowed': True,
                'reason': 'access_granted',
                'subscription_plan': subscription_plan,
                'features': access_config['features'],
                'limits': {
                    'daily_downloads': daily_limit,
                    'concurrent_downloads': concurrent_limit,
                    'remaining_daily': daily_limit - today_downloads if daily_limit > 0 else -1,
                    'current_concurrent': current_concurrent
                }
            }
            
        except Exception as e:
            logger.error(f"Error checking model access for user {user.id}: {e}")
            return {
                'allowed': False,
                'reason': 'system_error',
                'message': 'Unable to verify access permissions. Please try again.',
                'error': str(e)
            }
    
    def _get_plans_for_model(self, model_name: str) -> List[str]:
        """Get list of plans that include access to a specific model"""
        plans = []
        for plan, config in self.MODEL_ACCESS_MATRIX.items():
            if model_name in config['allowed_models']:
                plans.append(plan)
        return plans
    
    def _get_daily_download_count(self, user, model_name: str) -> int:
        """Get number of downloads for user today"""
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)
        
        try:
            model = ModelFile.objects.get(name=model_name)
            count = ModelDownload.objects.filter(
                user=user,
                model=model,
                started_at__gte=today,
                started_at__lt=tomorrow
            ).count()
            return count
        except ModelFile.DoesNotExist:
            return 0
    
    def _get_concurrent_download_count(self, user) -> int:
        """Get number of active concurrent downloads for user"""
        # Consider downloads active if started within last hour and not completed
        cutoff_time = timezone.now() - timedelta(hours=1)
        
        count = ModelDownload.objects.filter(
            user=user,
            started_at__gte=cutoff_time,
            is_completed=False
        ).count()
        
        return count
    
    def _get_next_reset_time(self) -> datetime:
        """Get next daily limit reset time (midnight)"""
        now = timezone.now()
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        return tomorrow
    
    def _check_license_validity(self, user, model_name: str) -> Dict:
        """Check if user has valid license for model"""
        try:
            # Get user's active license
            license_obj = License.objects.filter(
                user=user,
                is_active=True,
                expires_at__gt=timezone.now()
            ).first()
            
            if not license_obj:
                # For MVP/testing: Allow access without license if user has valid subscription
                if hasattr(user, 'subscription_plan') and user.subscription_plan in ['free', 'pro', 'enterprise']:
                    return {
                        'valid': True,
                        'message': 'Access granted via subscription plan',
                        'license_required': False
                    }
                
                return {
                    'valid': False,
                    'message': 'No active license found',
                    'license_required': True
                }
            
            # Check if license allows this model
            allowed_models = getattr(license_obj, 'allowed_models', [])
            if isinstance(allowed_models, str):
                import json
                try:
                    allowed_models = json.loads(allowed_models)
                except:
                    allowed_models = []
            
            if allowed_models and model_name not in allowed_models:
                return {
                    'valid': False,
                    'message': f'License does not include access to {model_name}',
                    'allowed_models': allowed_models
                }
            
            return {
                'valid': True,
                'license_key': license_obj.license_key,
                'expires_at': license_obj.expires_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking license validity: {e}")
            # For MVP/testing: Allow access on license check error if user has valid subscription
            if hasattr(user, 'subscription_plan') and user.subscription_plan in ['free', 'pro', 'enterprise']:
                return {
                    'valid': True,
                    'message': 'Access granted via subscription plan (license check failed)',
                    'license_required': False,
                    'error': str(e)
                }
            
            return {
                'valid': False,
                'message': 'Unable to verify license',
                'error': str(e)
            }
    
    def record_download_attempt(self, user, model_name: str, success: bool, 
                               ip_address: str, user_agent: str = '') -> bool:
        """Record a download attempt for analytics"""
        try:
            model = ModelFile.objects.get(name=model_name)
            
            # Update or create model access record
            model_access, created = ModelAccess.objects.get_or_create(
                user=user,
                model=model,
                defaults={'access_granted': True}
            )
            
            if success:
                model_access.download_count += 1
                model_access.last_download = timezone.now()
                model_access.save()
            
            return True
            
        except Exception as e:
            logger.error(f"Error recording download attempt: {e}")
            return False
    
    def get_user_access_summary(self, user) -> Dict:
        """Get comprehensive access summary for user"""
        subscription_plan = getattr(user, 'subscription_plan', 'free')
        access_config = self.MODEL_ACCESS_MATRIX.get(subscription_plan, self.MODEL_ACCESS_MATRIX['free'])
        
        # Get access status for each model
        model_access = {}
        for model_name in access_config['allowed_models']:
            access_check = self.check_model_access(user, model_name)
            model_access[model_name] = access_check
        
        # Get usage statistics
        usage_stats = self.analytics.get_user_usage_stats(user)
        
        return {
            'user_id': user.id,
            'subscription_plan': subscription_plan,
            'subscription_expires': getattr(user, 'subscription_expires', None),
            'features': access_config['features'],
            'limits': {
                'daily_downloads': access_config['max_downloads_per_day'],
                'concurrent_downloads': access_config['max_concurrent_downloads']
            },
            'model_access': model_access,
            'usage_statistics': usage_stats
        }


class ModelUsageAnalytics:
    """
    Tracks and analyzes model usage patterns and statistics
    """
    
    def get_user_usage_stats(self, user, days: int = 30) -> Dict:
        """Get usage statistics for a user"""
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Get download statistics
            downloads = ModelDownload.objects.filter(
                user=user,
                started_at__gte=cutoff_date
            )
            
            # Get model access records
            model_accesses = ModelAccess.objects.filter(user=user)
            
            # Calculate statistics
            total_downloads = downloads.count()
            completed_downloads = downloads.filter(is_completed=True).count()
            unique_models = downloads.values('model').distinct().count()
            
            # Downloads by model
            downloads_by_model = {}
            for access in model_accesses:
                downloads_by_model[access.model.name] = {
                    'total_downloads': access.download_count,
                    'last_download': access.last_download.isoformat() if access.last_download else None
                }
            
            # Daily download pattern
            daily_downloads = downloads.extra(
                select={'day': 'date(started_at)'}
            ).values('day').annotate(count=Count('id')).order_by('day')
            
            return {
                'period_days': days,
                'total_downloads': total_downloads,
                'completed_downloads': completed_downloads,
                'success_rate': (completed_downloads / total_downloads * 100) if total_downloads > 0 else 0,
                'unique_models_accessed': unique_models,
                'downloads_by_model': downloads_by_model,
                'daily_pattern': list(daily_downloads),
                'last_activity': downloads.order_by('-started_at').first().started_at.isoformat() if downloads.exists() else None
            }
            
        except Exception as e:
            logger.error(f"Error getting user usage stats: {e}")
            return {
                'error': str(e),
                'period_days': days
            }
    
    def get_model_usage_stats(self, model_name: str, days: int = 30) -> Dict:
        """Get usage statistics for a specific model"""
        try:
            model = ModelFile.objects.get(name=model_name)
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Get download statistics
            downloads = ModelDownload.objects.filter(
                model=model,
                started_at__gte=cutoff_date
            )
            
            # Get access records
            accesses = ModelAccess.objects.filter(model=model)
            
            # Calculate statistics
            total_downloads = downloads.count()
            unique_users = downloads.values('user').distinct().count()
            completed_downloads = downloads.filter(is_completed=True).count()
            
            # Downloads by subscription plan
            downloads_by_plan = downloads.values(
                'user__subscription_plan'
            ).annotate(count=Count('id')).order_by('-count')
            
            # Top users
            top_users = accesses.order_by('-download_count')[:10]
            
            return {
                'model_name': model_name,
                'period_days': days,
                'total_downloads': total_downloads,
                'unique_users': unique_users,
                'completed_downloads': completed_downloads,
                'success_rate': (completed_downloads / total_downloads * 100) if total_downloads > 0 else 0,
                'downloads_by_plan': list(downloads_by_plan),
                'top_users': [
                    {
                        'user_id': access.user.id,
                        'email': access.user.email,
                        'download_count': access.download_count,
                        'last_download': access.last_download.isoformat() if access.last_download else None
                    }
                    for access in top_users
                ],
                'average_downloads_per_user': total_downloads / unique_users if unique_users > 0 else 0
            }
            
        except ModelFile.DoesNotExist:
            return {'error': f'Model {model_name} not found'}
        except Exception as e:
            logger.error(f"Error getting model usage stats: {e}")
            return {'error': str(e)}
    
    def get_system_usage_overview(self, days: int = 30) -> Dict:
        """Get system-wide usage overview"""
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Overall statistics
            total_downloads = ModelDownload.objects.filter(
                started_at__gte=cutoff_date
            ).count()
            
            total_users = User.objects.filter(
                modeldownload__started_at__gte=cutoff_date
            ).distinct().count()
            
            # Downloads by model
            model_stats = ModelDownload.objects.filter(
                started_at__gte=cutoff_date
            ).values(
                'model__name', 'model__display_name'
            ).annotate(
                download_count=Count('id'),
                unique_users=Count('user', distinct=True)
            ).order_by('-download_count')
            
            # Downloads by subscription plan
            plan_stats = ModelDownload.objects.filter(
                started_at__gte=cutoff_date
            ).values(
                'user__subscription_plan'
            ).annotate(count=Count('id')).order_by('-count')
            
            # Success rate
            completed_downloads = ModelDownload.objects.filter(
                started_at__gte=cutoff_date,
                is_completed=True
            ).count()
            
            return {
                'period_days': days,
                'total_downloads': total_downloads,
                'active_users': total_users,
                'success_rate': (completed_downloads / total_downloads * 100) if total_downloads > 0 else 0,
                'model_statistics': list(model_stats),
                'plan_statistics': list(plan_stats),
                'average_downloads_per_user': total_downloads / total_users if total_users > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting system usage overview: {e}")
            return {'error': str(e)}


# Global instances
access_controller = ModelAccessController()
usage_analytics = ModelUsageAnalytics()