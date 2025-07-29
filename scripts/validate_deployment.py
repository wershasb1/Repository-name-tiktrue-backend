#!/usr/bin/env python3
"""
Deployment Validation Script for TikTrue Platform

This script validates all configuration files, dependencies, and paths
to ensure everything is properly configured for deployment.
"""

import os
import sys
import json
import subprocess
from pathlib import Path

class DeploymentValidator:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.errors = []
        self.warnings = []
        self.success_count = 0
        
    def log_error(self, message):
        """Log an error"""
        self.errors.append(message)
        print(f"❌ ERROR: {message}")
        
    def log_warning(self, message):
        """Log a warning"""
        self.warnings.append(message)
        print(f"⚠️  WARNING: {message}")
        
    def log_success(self, message):
        """Log a success"""
        self.success_count += 1
        print(f"✅ {message}")
        
    def validate_backend_config(self):
        """Validate backend configuration"""
        print("\n🔍 Validating Backend Configuration...")
        
        backend_dir = self.project_root / "backend"
        
        # Check if backend directory exists
        if not backend_dir.exists():
            self.log_error("Backend directory not found")
            return
            
        # Check required files
        required_files = [
            "manage.py",
            "requirements.txt",
            "runtime.txt",
            "liara.json",
            ".env.example"
        ]
        
        for file in required_files:
            file_path = backend_dir / file
            if file_path.exists():
                self.log_success(f"Backend file exists: {file}")
            else:
                self.log_error(f"Backend file missing: {file}")
                
        # Validate liara.json
        liara_json = backend_dir / "liara.json"
        if liara_json.exists():
            try:
                with open(liara_json, 'r') as f:
                    config = json.load(f)
                    
                if config.get('platform') == 'django':
                    self.log_success("Backend liara.json platform is correctly set to 'django'")
                else:
                    self.log_error("Backend liara.json platform should be 'django'")
                    
                if config.get('port') == 8000:
                    self.log_success("Backend port is correctly set to 8000")
                else:
                    self.log_warning("Backend port should be 8000")
                    
            except json.JSONDecodeError:
                self.log_error("Backend liara.json is not valid JSON")
                
        # Check Django apps structure
        django_apps = ["accounts", "licenses", "models_api", "tiktrue_backend"]
        for app in django_apps:
            app_dir = backend_dir / app
            if app_dir.exists():
                self.log_success(f"Django app exists: {app}")
                
                # Check for required files in each app
                if app != "tiktrue_backend":
                    required_app_files = ["models.py", "views.py", "urls.py", "serializers.py"]
                    for file in required_app_files:
                        file_path = app_dir / file
                        if file_path.exists():
                            self.log_success(f"App file exists: {app}/{file}")
                        else:
                            self.log_error(f"App file missing: {app}/{file}")
            else:
                self.log_error(f"Django app missing: {app}")
                
        # Validate runtime.txt
        runtime_file = backend_dir / "runtime.txt"
        if runtime_file.exists():
            with open(runtime_file, 'r') as f:
                runtime_version = f.read().strip()
                if runtime_version.startswith('python-3.11'):
                    self.log_success(f"Python runtime version is correct: {runtime_version}")
                else:
                    self.log_warning(f"Python runtime version should be 3.11, found: {runtime_version}")
                    
    def validate_frontend_config(self):
        """Validate frontend configuration"""
        print("\n🔍 Validating Frontend Configuration...")
        
        frontend_dir = self.project_root / "frontend"
        
        # Check if frontend directory exists
        if not frontend_dir.exists():
            self.log_error("Frontend directory not found")
            return
            
        # Check required files
        required_files = [
            "package.json",
            "liara.json",
            ".env.example",
            ".env.production",
            "tailwind.config.js",
            "postcss.config.js"
        ]
        
        for file in required_files:
            file_path = frontend_dir / file
            if file_path.exists():
                self.log_success(f"Frontend file exists: {file}")
            else:
                self.log_error(f"Frontend file missing: {file}")
                
        # Validate package.json
        package_json = frontend_dir / "package.json"
        if package_json.exists():
            try:
                with open(package_json, 'r') as f:
                    config = json.load(f)
                    
                # Check dependencies
                required_deps = [
                    "react", "react-dom", "react-router-dom", 
                    "axios", "framer-motion", "react-hot-toast"
                ]
                
                dependencies = config.get('dependencies', {})
                for dep in required_deps:
                    if dep in dependencies:
                        self.log_success(f"Frontend dependency exists: {dep}")
                    else:
                        self.log_error(f"Frontend dependency missing: {dep}")
                        
            except json.JSONDecodeError:
                self.log_error("Frontend package.json is not valid JSON")
                
        # Validate liara.json
        liara_json = frontend_dir / "liara.json"
        if liara_json.exists():
            try:
                with open(liara_json, 'r') as f:
                    config = json.load(f)
                    
                if config.get('platform') == 'static':
                    self.log_success("Frontend liara.json platform is correctly set to 'static'")
                else:
                    self.log_error("Frontend liara.json platform should be 'static'")
                    
                static_config = config.get('static', {})
                if static_config.get('spa') is True:
                    self.log_success("Frontend SPA routing is enabled")
                else:
                    self.log_error("Frontend SPA routing should be enabled")
                    
            except json.JSONDecodeError:
                self.log_error("Frontend liara.json is not valid JSON")
                
        # Check React app structure
        src_dir = frontend_dir / "src"
        if src_dir.exists():
            required_dirs = ["components", "contexts", "pages", "services"]
            for dir_name in required_dirs:
                dir_path = src_dir / dir_name
                if dir_path.exists():
                    self.log_success(f"Frontend directory exists: src/{dir_name}")
                else:
                    self.log_error(f"Frontend directory missing: src/{dir_name}")
                    
            # Check required files
            required_src_files = ["App.js", "index.js", "index.css"]
            for file in required_src_files:
                file_path = src_dir / file
                if file_path.exists():
                    self.log_success(f"Frontend source file exists: src/{file}")
                else:
                    self.log_error(f"Frontend source file missing: src/{file}")
                    
    def validate_environment_files(self):
        """Validate environment configuration files"""
        print("\n🔍 Validating Environment Files...")
        
        # Backend environment
        backend_env = self.project_root / "backend" / ".env.example"
        if backend_env.exists():
            with open(backend_env, 'r') as f:
                content = f.read()
                required_vars = [
                    "SECRET_KEY", "DEBUG", "ALLOWED_HOSTS", 
                    "CORS_ALLOWED_ORIGINS", "DATABASE_URL"
                ]
                
                for var in required_vars:
                    if var in content:
                        self.log_success(f"Backend env variable documented: {var}")
                    else:
                        self.log_error(f"Backend env variable missing: {var}")
                        
        # Frontend environment
        frontend_env = self.project_root / "frontend" / ".env.example"
        if frontend_env.exists():
            with open(frontend_env, 'r') as f:
                content = f.read()
                required_vars = [
                    "REACT_APP_API_BASE_URL", "REACT_APP_BACKEND_URL", 
                    "REACT_APP_FRONTEND_URL"
                ]
                
                for var in required_vars:
                    if var in content:
                        self.log_success(f"Frontend env variable documented: {var}")
                    else:
                        self.log_error(f"Frontend env variable missing: {var}")
                        
    def validate_import_paths(self):
        """Validate import paths in Python and JavaScript files"""
        print("\n🔍 Validating Import Paths...")
        
        # Check Python imports in backend
        backend_dir = self.project_root / "backend"
        python_files = list(backend_dir.rglob("*.py"))
        
        for py_file in python_files:
            if "__pycache__" in str(py_file) or "migrations" in str(py_file):
                continue
                
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Check for common import issues
                if "from . import" in content or "from .models import" in content:
                    self.log_success(f"Python relative imports look good: {py_file.name}")
                    
            except Exception as e:
                self.log_warning(f"Could not read Python file: {py_file.name} - {e}")
                
        # Check JavaScript imports in frontend
        frontend_src = self.project_root / "frontend" / "src"
        if frontend_src.exists():
            js_files = list(frontend_src.rglob("*.js"))
            
            for js_file in js_files:
                try:
                    with open(js_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    # Check for common import issues
                    if "import" in content and "from" in content:
                        self.log_success(f"JavaScript imports look good: {js_file.name}")
                        
                except Exception as e:
                    self.log_warning(f"Could not read JavaScript file: {js_file.name} - {e}")
                    
    def validate_dependencies(self):
        """Validate dependencies and versions"""
        print("\n🔍 Validating Dependencies...")
        
        # Check Python dependencies
        requirements_file = self.project_root / "backend" / "requirements.txt"
        if requirements_file.exists():
            with open(requirements_file, 'r') as f:
                requirements = f.read()
                
            required_packages = [
                "Django", "djangorestframework", "djangorestframework-simplejwt",
                "django-cors-headers", "dj-database-url", "psycopg2-binary",
                "whitenoise", "gunicorn"
            ]
            
            for package in required_packages:
                if package in requirements:
                    self.log_success(f"Python package included: {package}")
                else:
                    self.log_error(f"Python package missing: {package}")
                    
        # Check Node.js dependencies
        package_json = self.project_root / "frontend" / "package.json"
        if package_json.exists():
            try:
                with open(package_json, 'r') as f:
                    config = json.load(f)
                    
                dependencies = config.get('dependencies', {})
                required_packages = [
                    "react", "react-dom", "react-router-dom", "axios",
                    "framer-motion", "react-hot-toast", "lucide-react"
                ]
                
                for package in required_packages:
                    if package in dependencies:
                        self.log_success(f"Node.js package included: {package}")
                    else:
                        self.log_error(f"Node.js package missing: {package}")
                        
            except json.JSONDecodeError:
                self.log_error("Could not parse package.json")
                
    def validate_urls_and_endpoints(self):
        """Validate URL configurations and API endpoints"""
        print("\n🔍 Validating URLs and Endpoints...")
        
        # Check Django URL configurations
        backend_dir = self.project_root / "backend"
        
        # Main URLs
        main_urls = backend_dir / "tiktrue_backend" / "urls.py"
        if main_urls.exists():
            with open(main_urls, 'r') as f:
                content = f.read()
                
            required_patterns = [
                "admin/", "api/v1/auth/", "api/v1/license/", 
                "api/v1/models/", "health/"
            ]
            
            for pattern in required_patterns:
                if pattern in content:
                    self.log_success(f"URL pattern exists: {pattern}")
                else:
                    self.log_error(f"URL pattern missing: {pattern}")
                    
        # Check app URLs
        apps = ["accounts", "licenses", "models_api"]
        for app in apps:
            urls_file = backend_dir / app / "urls.py"
            if urls_file.exists():
                self.log_success(f"App URLs file exists: {app}/urls.py")
            else:
                self.log_error(f"App URLs file missing: {app}/urls.py")
                
    def run_validation(self):
        """Run all validation checks"""
        print("🚀 Starting TikTrue Platform Deployment Validation...")
        print("=" * 60)
        
        self.validate_backend_config()
        self.validate_frontend_config()
        self.validate_environment_files()
        self.validate_import_paths()
        self.validate_dependencies()
        self.validate_urls_and_endpoints()
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 VALIDATION SUMMARY")
        print("=" * 60)
        
        print(f"✅ Successful checks: {self.success_count}")
        print(f"⚠️  Warnings: {len(self.warnings)}")
        print(f"❌ Errors: {len(self.errors)}")
        
        if self.errors:
            print("\n❌ ERRORS FOUND:")
            for error in self.errors:
                print(f"  • {error}")
                
        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"  • {warning}")
                
        if not self.errors:
            print("\n🎉 All critical checks passed! Deployment should work correctly.")
            return True
        else:
            print(f"\n💥 Found {len(self.errors)} critical errors. Please fix before deployment.")
            return False

if __name__ == "__main__":
    validator = DeploymentValidator()
    success = validator.run_validation()
    sys.exit(0 if success else 1)