"""
Script to fix import issues in model_downloader.py
"""

import re

def fix_imports():
    # Read the file
    with open('models/model_downloader.py', 'r') as f:
        content = f.read()
    
    # Fix the imports
    pattern = r'from security\.license_validator import SubscriptionTier, LicenseInfo'
    replacement = 'from license_models import SubscriptionTier, LicenseInfo'
    
    # Replace all occurrences
    new_content = re.sub(pattern, replacement, content)
    
    # Write the file back
    with open('models/model_downloader.py', 'w') as f:
        f.write(new_content)
    
    print("Fixed imports in models/model_downloader.py")

if __name__ == "__main__":
    fix_imports()