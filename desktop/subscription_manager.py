"""
Subscription Manager
Manages subscription tiers, features, and UI display for different plans
"""

import logging
from typing import Dict, List, Any, Optional
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta

from security.license_validator import SubscriptionTier, LicenseInfo

logger = logging.getLogger("SubscriptionManager")


@dataclass
class FeatureInfo:
    """Information about a feature"""
    name: str
    description: str
    icon: str
    category: str
    premium: bool = False


@dataclass
class TierInfo:
    """Information about a subscription tier"""
    tier: SubscriptionTier
    name: str
    description: str
    max_clients: int
    features: List[str]
    models: List[str]
    price_monthly: Optional[float] = None
    price_yearly: Optional[float] = None
    color: str = "#007bff"
    popular: bool = False


class SubscriptionManager:
    """Manages subscription information and features"""
    
    # Feature definitions
    FEATURES = {
        "basic_chat": FeatureInfo(
            name="Basic Chat",
            description="Simple chat interface with AI models",
            icon="💬",
            category="Chat"
        ),
        "advanced_chat": FeatureInfo(
            name="Advanced Chat",
            description="Enhanced chat with streaming responses and formatting",
            icon="🚀",
            category="Chat",
            premium=True
        ),
        "session_management": FeatureInfo(
            name="Session Management",
            description="Save and restore conversation sessions",
            icon="💾",
            category="Chat",
            premium=True
        ),
        "multi_network": FeatureInfo(
            name="Multi-Network Support",
            description="Connect to multiple distributed networks simultaneously",
            icon="🌐",
            category="Network",
            premium=True
        ),
        "network_creation": FeatureInfo(
            name="Network Creation",
            description="Create and manage your own distributed networks",
            icon="🏗️",
            category="Network"
        ),
        "basic_models": FeatureInfo(
            name="Basic Models",
            description="Access to standard AI models (7B parameters)",
            icon="🤖",
            category="Models"
        ),
        "premium_models": FeatureInfo(
            name="Premium Models",
            description="Access to advanced AI models (13B+ parameters)",
            icon="🧠",
            category="Models",
            premium=True
        ),
        "enterprise_models": FeatureInfo(
            name="Enterprise Models",
            description="Access to enterprise-grade models and custom deployments",
            icon="🏢",
            category="Models",
            premium=True
        ),
        "analytics": FeatureInfo(
            name="Analytics & Monitoring",
            description="Detailed usage analytics and performance monitoring",
            icon="📊",
            category="Management",
            premium=True
        ),
        "priority_support": FeatureInfo(
            name="Priority Support",
            description="Priority customer support and technical assistance",
            icon="🎧",
            category="Support",
            premium=True
        ),
        "api_access": FeatureInfo(
            name="API Access",
            description="Programmatic access via REST API",
            icon="🔌",
            category="Integration",
            premium=True
        ),
        "custom_integrations": FeatureInfo(
            name="Custom Integrations",
            description="Custom integrations and enterprise features",
            icon="⚙️",
            category="Integration",
            premium=True
        )
    }
    
    # Tier definitions
    TIERS = {
        SubscriptionTier.FREE: TierInfo(
            tier=SubscriptionTier.FREE,
            name="Free",
            description="Perfect for trying out TikTrue",
            max_clients=3,
            features=[
                "basic_chat",
                "network_creation",
                "basic_models"
            ],
            models=["llama-7b-chat", "mistral-7b"],
            color="#6c757d"
        ),
        SubscriptionTier.PRO: TierInfo(
            tier=SubscriptionTier.PRO,
            name="Professional",
            description="Ideal for professionals and small teams",
            max_clients=20,
            features=[
                "basic_chat",
                "advanced_chat",
                "session_management",
                "multi_network",
                "network_creation",
                "basic_models",
                "premium_models",
                "analytics"
            ],
            models=[
                "llama-7b-chat", "llama-13b-instruct", 
                "mistral-7b", "gpt-4-turbo"
            ],
            price_monthly=29.99,
            price_yearly=299.99,
            color="#007bff",
            popular=True
        ),
        SubscriptionTier.ENTERPRISE: TierInfo(
            tier=SubscriptionTier.ENTERPRISE,
            name="Enterprise",
            description="For large organizations and enterprises",
            max_clients=-1,  # Unlimited
            features=[
                "basic_chat",
                "advanced_chat", 
                "session_management",
                "multi_network",
                "network_creation",
                "basic_models",
                "premium_models",
                "enterprise_models",
                "analytics",
                "priority_support",
                "api_access",
                "custom_integrations"
            ],
            models=[
                "llama-7b-chat", "llama-13b-instruct", "llama-70b-code",
                "mistral-7b", "gpt-4-turbo", "claude-3-opus"
            ],
            price_monthly=99.99,
            price_yearly=999.99,
            color="#28a745"
        )
    }
    
    def __init__(self):
        """Initialize subscription manager"""
        logger.info("SubscriptionManager initialized")
    
    def get_tier_info(self, tier: SubscriptionTier) -> TierInfo:
        """Get information about a subscription tier"""
        return self.TIERS.get(tier, self.TIERS[SubscriptionTier.FREE])
    
    def get_feature_info(self, feature_id: str) -> Optional[FeatureInfo]:
        """Get information about a feature"""
        return self.FEATURES.get(feature_id)
    
    def get_tier_features(self, tier: SubscriptionTier) -> List[FeatureInfo]:
        """Get list of features for a tier"""
        tier_info = self.get_tier_info(tier)
        features = []
        
        for feature_id in tier_info.features:
            feature_info = self.get_feature_info(feature_id)
            if feature_info:
                features.append(feature_info)
        
        return features
    
    def is_feature_available(self, feature_id: str, tier: SubscriptionTier) -> bool:
        """Check if a feature is available for a tier"""
        tier_info = self.get_tier_info(tier)
        return feature_id in tier_info.features
    
    def is_model_available(self, model_id: str, tier: SubscriptionTier) -> bool:
        """Check if a model is available for a tier"""
        tier_info = self.get_tier_info(tier)
        return model_id in tier_info.models
    
    def get_upgrade_suggestions(self, current_tier: SubscriptionTier, 
                             requested_feature: str) -> List[SubscriptionTier]:
        """Get tier upgrade suggestions for accessing a feature"""
        suggestions = []
        
        for tier in [SubscriptionTier.PRO, SubscriptionTier.ENTERPRISE]:
            if tier.value > current_tier.value:  # Higher tier
                if self.is_feature_available(requested_feature, tier):
                    suggestions.append(tier)
        
        return suggestions
    
    def get_tier_comparison(self) -> Dict[str, Any]:
        """Get comparison data for all tiers"""
        comparison = {
            "tiers": [],
            "features": []
        }
        
        # Add tier information
        for tier in [SubscriptionTier.FREE, SubscriptionTier.PRO, SubscriptionTier.ENTERPRISE]:
            tier_info = self.get_tier_info(tier)
            comparison["tiers"].append({
                "tier": tier.value,
                "name": tier_info.name,
                "description": tier_info.description,
                "max_clients": "Unlimited" if tier_info.max_clients == -1 else tier_info.max_clients,
                "price_monthly": tier_info.price_monthly,
                "price_yearly": tier_info.price_yearly,
                "color": tier_info.color,
                "popular": tier_info.popular
            })
        
        # Add feature comparison
        all_features = set()
        for tier_info in self.TIERS.values():
            all_features.update(tier_info.features)
        
        for feature_id in sorted(all_features):
            feature_info = self.get_feature_info(feature_id)
            if feature_info:
                feature_comparison = {
                    "id": feature_id,
                    "name": feature_info.name,
                    "description": feature_info.description,
                    "icon": feature_info.icon,
                    "category": feature_info.category,
                    "premium": feature_info.premium,
                    "availability": {}
                }
                
                # Check availability for each tier
                for tier in [SubscriptionTier.FREE, SubscriptionTier.PRO, SubscriptionTier.ENTERPRISE]:
                    feature_comparison["availability"][tier.value] = self.is_feature_available(feature_id, tier)
                
                comparison["features"].append(feature_comparison)
        
        return comparison
    
    def get_license_status_display(self, license_info: LicenseInfo) -> Dict[str, Any]:
        """Get display information for license status"""
        if not license_info or not license_info.is_valid:
            return {
                "status": "invalid",
                "message": "Invalid or missing license",
                "color": "#dc3545",
                "icon": "❌"
            }
        
        tier_info = self.get_tier_info(license_info.tier)
        days_remaining = (license_info.expires_at - datetime.now()).days
        
        if days_remaining < 0:
            status = "expired"
            message = f"License expired {abs(days_remaining)} days ago"
            color = "#dc3545"
            icon = "⏰"
        elif days_remaining <= 7:
            status = "expiring"
            message = f"License expires in {days_remaining} days"
            color = "#ffc107"
            icon = "⚠️"
        elif days_remaining <= 30:
            status = "active_warning"
            message = f"License expires in {days_remaining} days"
            color = "#fd7e14"
            icon = "📅"
        else:
            status = "active"
            message = f"Active {tier_info.name} license"
            color = tier_info.color
            icon = "✅"
        
        return {
            "status": status,
            "message": message,
            "color": color,
            "icon": icon,
            "tier": tier_info.name,
            "days_remaining": days_remaining,
            "max_clients": tier_info.max_clients,
            "expires_at": license_info.expires_at.strftime("%Y-%m-%d")
        }
    
    def get_feature_categories(self) -> Dict[str, List[FeatureInfo]]:
        """Get features grouped by category"""
        categories = {}
        
        for feature_info in self.FEATURES.values():
            category = feature_info.category
            if category not in categories:
                categories[category] = []
            categories[category].append(feature_info)
        
        return categories
    
    def calculate_savings(self, tier: SubscriptionTier) -> Optional[Dict[str, float]]:
        """Calculate yearly savings for a tier"""
        tier_info = self.get_tier_info(tier)
        
        if not tier_info.price_monthly or not tier_info.price_yearly:
            return None
        
        monthly_total = tier_info.price_monthly * 12
        yearly_price = tier_info.price_yearly
        savings = monthly_total - yearly_price
        savings_percentage = (savings / monthly_total) * 100
        
        return {
            "monthly_total": monthly_total,
            "yearly_price": yearly_price,
            "savings_amount": savings,
            "savings_percentage": savings_percentage
        }


# Utility functions
def get_subscription_manager() -> SubscriptionManager:
    """Get subscription manager instance"""
    return SubscriptionManager()


def format_price(price: Optional[float]) -> str:
    """Format price for display"""
    if price is None:
        return "Free"
    return f"${price:.2f}"


def format_client_limit(limit: int) -> str:
    """Format client limit for display"""
    if limit == -1:
        return "Unlimited"
    return str(limit)


if __name__ == "__main__":
    # Test the subscription manager
    manager = SubscriptionManager()
    
    print("=== Subscription Tiers ===")
    for tier in [SubscriptionTier.FREE, SubscriptionTier.PRO, SubscriptionTier.ENTERPRISE]:
        tier_info = manager.get_tier_info(tier)
        print(f"\n{tier_info.name} ({tier.value}):")
        print(f"  Max Clients: {format_client_limit(tier_info.max_clients)}")
        print(f"  Monthly Price: {format_price(tier_info.price_monthly)}")
        print(f"  Features: {len(tier_info.features)}")
        
        features = manager.get_tier_features(tier)
        for feature in features:
            premium_mark = " 🌟" if feature.premium else ""
            print(f"    {feature.icon} {feature.name}{premium_mark}")
    
    print("\n=== Feature Categories ===")
    categories = manager.get_feature_categories()
    for category, features in categories.items():
        print(f"\n{category}:")
        for feature in features:
            premium_mark = " (Premium)" if feature.premium else ""
            print(f"  {feature.icon} {feature.name}{premium_mark}")
    
    print("\n=== Tier Comparison ===")
    comparison = manager.get_tier_comparison()
    print(f"Total tiers: {len(comparison['tiers'])}")
    print(f"Total features: {len(comparison['features'])}")