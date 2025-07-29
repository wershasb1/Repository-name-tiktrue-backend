#!/usr/bin/env python3
"""
Project File Analyzer
تحلیل و بررسی فایل‌های پروژه TikTrue Platform
"""

import os
import ast
import json
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
import hashlib

class FileInfo:
    def __init__(self, path: str):
        self.path = path
        self.name = os.path.basename(path)
        self.size = os.path.getsize(path) if os.path.exists(path) else 0
        self.extension = os.path.splitext(path)[1]
        self.imports: Set[str] = set()
        self.functions: List[str] = []
        self.classes: List[str] = []
        self.has_main = False
        self.has_docstring = False
        self.is_test = path.startswith('test_') or '/test' in path
        self.is_demo = path.startswith('demo_') or '/demo' in path
        self.hash = self._calculate_hash()
        
    def _calculate_hash(self) -> str:
        """محاسبه hash فایل برای تشخیص تکراری‌ها"""
        try:
            with open(self.path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except:
            return ""

class ProjectAnalyzer:
    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path)
        self.files: Dict[str, FileInfo] = {}
        self.dependencies: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_dependencies: Dict[str, Set[str]] = defaultdict(set)
        self.duplicates: List[Tuple[str, str]] = []
        self.orphaned_files: List[str] = []
        self.categories = {
            'core': [],
            'workers': [],
            'interfaces': [],
            'network': [],
            'security': [],
            'models': [],
            'config': [],
            'tests': [],
            'build': [],
            'docs': [],
            'utils': [],
            'unknown': []
        }
        
    def analyze_project(self):
        """تحلیل کامل پروژه"""
        print("🔍 شروع تحلیل پروژه...")
        
        # 1. اسکن فایل‌ها
        self._scan_files()
        
        # 2. تحلیل وابستگی‌ها
        self._analyze_dependencies()
        
        # 3. دسته‌بندی فایل‌ها
        self._categorize_files()
        
        # 4. تشخیص فایل‌های تکراری
        self._find_duplicates()
        
        # 5. تشخیص فایل‌های orphaned
        self._find_orphaned_files()
        
        print("✅ تحلیل پروژه کامل شد")
        
    def _scan_files(self):
        """اسکن تمام فایل‌های پروژه"""
        print("📁 اسکن فایل‌ها...")
        
        # فایل‌های قابل نادیده گرفتن
        ignore_patterns = {
            '__pycache__', '.git', '.venv', 'node_modules', 
            '.pytest_cache', 'dist', 'build', '.vscode',
            'logs', 'sessions', 'temp', 'test_storage'
        }
        
        ignore_extensions = {'.pyc', '.pyo', '.log', '.tmp', '.bak'}
        
        for file_path in self.root_path.rglob('*'):
            if file_path.is_file():
                # چک کردن ignore patterns
                if any(pattern in str(file_path) for pattern in ignore_patterns):
                    continue
                    
                if file_path.suffix in ignore_extensions:
                    continue
                    
                relative_path = str(file_path.relative_to(self.root_path))
                file_info = FileInfo(relative_path)
                
                # تحلیل فایل‌های پایتون
                if file_path.suffix == '.py':
                    self._analyze_python_file(file_info, file_path)
                
                self.files[relative_path] = file_info
                
        print(f"📊 {len(self.files)} فایل پیدا شد")
        
    def _analyze_python_file(self, file_info: FileInfo, file_path: Path):
        """تحلیل فایل پایتون"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # پارس کردن AST
            tree = ast.parse(content)
            
            # بررسی docstring
            if (tree.body and isinstance(tree.body[0], ast.Expr) and 
                isinstance(tree.body[0].value, ast.Constant) and 
                isinstance(tree.body[0].value.value, str)):
                file_info.has_docstring = True
                
            # استخراج imports, functions, classes
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        file_info.imports.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        file_info.imports.add(node.module)
                elif isinstance(node, ast.FunctionDef):
                    file_info.functions.append(node.name)
                    if node.name == 'main':
                        file_info.has_main = True
                elif isinstance(node, ast.ClassDef):
                    file_info.classes.append(node.name)
                    
        except Exception as e:
            print(f"⚠️  خطا در تحلیل {file_path}: {e}")
            
    def _analyze_dependencies(self):
        """تحلیل وابستگی‌ها"""
        print("🔗 تحلیل وابستگی‌ها...")
        
        for file_path, file_info in self.files.items():
            for import_name in file_info.imports:
                # تبدیل import به نام فایل محتمل
                potential_files = [
                    f"{import_name}.py",
                    f"{import_name}/__init__.py",
                    f"{import_name.replace('.', '/')}.py"
                ]
                
                for potential_file in potential_files:
                    if potential_file in self.files:
                        self.dependencies[file_path].add(potential_file)
                        self.reverse_dependencies[potential_file].add(file_path)
                        break
                        
    def _categorize_files(self):
        """دسته‌بندی فایل‌ها بر اساس نام و محتوا"""
        print("📂 دسته‌بندی فایل‌ها...")
        
        # الگوهای دسته‌بندی
        patterns = {
            'core': [
                'model_node.py', 'network_manager.py', 'config_manager.py',
                'protocol_spec.py', 'main_app.py', 'service_runner.py'
            ],
            'workers': [
                'worker_lib.py', 'scheduler_lib.py', 'homf_lib.py',
                'dynamic_profiler.py', 'static_profiler.py',
                'paged_kv_cache_lib.py', 'sequential_gpu_worker_lib.py'
            ],
            'interfaces': [
                'chatbot_interface.py', 'chat_interface.py',
                'enhanced_chat_interface.py', 'session_ui.py',
                'network_dashboard.py', 'first_run_wizard.py'
            ],
            'network': [
                'websocket_server.py', 'unified_websocket_server.py',
                'enhanced_websocket_handler.py', 'network_discovery.py',
                'api_client.py', 'backend_api_client.py'
            ],
            'security': [
                'security.license_validator.py', 'license_storage.py',
                'security.auth_manager.py', 'security.crypto_layer.py',
                'security.hardware_fingerprint.py', 'access_control.py',
                'key_manager.py'
            ],
            'models': [
                'models.model_downloader.py', 'models.model_encryption.py',
                'models.model_verification.py', 'model_selector.py',
                'model_node_license_integration.py'
            ],
            'config': [
                'network_config.json', 'portable_config.json',
                'performance_profile.json'
            ],
            'build': [
                'Build-Installer.ps1', 'build_installer_complete.py',
                'build_installer.bat', 'installer.nsi',
                'validate_installer_build.py'
            ],
            'docs': [
                'README_SETUP.md', 'PRODUCTION_READY.md',
                'Data_Full_Project_V1.md', 'About_MDI_Mainproject.txt',
                'KEY_MANAGEMENT_IMPLEMENTATION_SUMMARY.md',
                'ENHANCED_WEBSOCKET_INTEGRATION.md'
            ],
            'utils': [
                'setup_validator.py', 'serialization_utils.py',
                'custom_logging.py', 'monitoring_system.py'
            ]
        }
        
        # دسته‌بندی بر اساس الگوها
        for file_path in self.files:
            categorized = False
            file_name = os.path.basename(file_path)
            
            # تست فایل‌ها
            if file_name.startswith('test_') or file_name.startswith('demo_'):
                self.categories['tests'].append(file_path)
                categorized = True
            else:
                # سایر دسته‌ها
                for category, file_patterns in patterns.items():
                    if file_name in file_patterns:
                        self.categories[category].append(file_path)
                        categorized = True
                        break
                        
            if not categorized:
                self.categories['unknown'].append(file_path)
                
    def _find_duplicates(self):
        """تشخیص فایل‌های تکراری"""
        print("🔍 جستجوی فایل‌های تکراری...")
        
        hash_to_files = defaultdict(list)
        
        for file_path, file_info in self.files.items():
            if file_info.hash and file_info.size > 0:
                hash_to_files[file_info.hash].append(file_path)
                
        for file_hash, file_list in hash_to_files.items():
            if len(file_list) > 1:
                for i in range(len(file_list)):
                    for j in range(i + 1, len(file_list)):
                        self.duplicates.append((file_list[i], file_list[j]))
                        
    def _find_orphaned_files(self):
        """تشخیص فایل‌های orphaned (استفاده نشده)"""
        print("🔍 جستجوی فایل‌های orphaned...")
        
        # فایل‌هایی که هیچ فایل دیگری به آن‌ها وابسته نیست
        for file_path in self.files:
            if (file_path not in self.reverse_dependencies and 
                not self.files[file_path].has_main and
                not self.files[file_path].is_test and
                not self.files[file_path].is_demo and
                file_path.endswith('.py')):
                self.orphaned_files.append(file_path)
                
    def generate_report(self) -> str:
        """تولید گزارش کامل"""
        report = []
        report.append("=" * 60)
        report.append("📊 گزارش تحلیل پروژه TikTrue Platform")
        report.append("=" * 60)
        
        # آمار کلی
        report.append(f"\n📈 آمار کلی:")
        report.append(f"   • تعداد کل فایل‌ها: {len(self.files)}")
        report.append(f"   • فایل‌های پایتون: {len([f for f in self.files if f.endswith('.py')])}")
        report.append(f"   • فایل‌های JSON: {len([f for f in self.files if f.endswith('.json')])}")
        report.append(f"   • فایل‌های مستندات: {len([f for f in self.files if f.endswith('.md')])}")
        
        # دسته‌بندی
        report.append(f"\n📂 دسته‌بندی فایل‌ها:")
        for category, files in self.categories.items():
            if files:
                report.append(f"   • {category}: {len(files)} فایل")
                for file_path in sorted(files)[:5]:  # نمایش 5 فایل اول
                    report.append(f"     - {file_path}")
                if len(files) > 5:
                    report.append(f"     ... و {len(files) - 5} فایل دیگر")
                    
        # فایل‌های تکراری
        if self.duplicates:
            report.append(f"\n🔄 فایل‌های تکراری ({len(self.duplicates)} جفت):")
            for file1, file2 in self.duplicates[:10]:
                report.append(f"   • {file1} ≈ {file2}")
                
        # فایل‌های orphaned
        if self.orphaned_files:
            report.append(f"\n🏝️  فایل‌های orphaned ({len(self.orphaned_files)} فایل):")
            for file_path in self.orphaned_files[:10]:
                report.append(f"   • {file_path}")
                
        # فایل‌های بدون مستندات
        undocumented = [f for f, info in self.files.items() 
                       if f.endswith('.py') and not info.has_docstring]
        if undocumented:
            report.append(f"\n📝 فایل‌های بدون docstring ({len(undocumented)} فایل):")
            for file_path in undocumented[:10]:
                report.append(f"   • {file_path}")
                
        # پیشنهادات
        report.append(f"\n💡 پیشنهادات:")
        report.append(f"   • ایجاد پوشه‌های مجزا برای هر دسته")
        report.append(f"   • حذف فایل‌های تکراری")
        report.append(f"   • بررسی فایل‌های orphaned")
        report.append(f"   • اضافه کردن docstring به فایل‌های پایتون")
        
        return "\n".join(report)
        
    def save_detailed_report(self, filename: str = "project_analysis_report.json"):
        """ذخیره گزارش تفصیلی در فرمت JSON"""
        detailed_report = {
            "summary": {
                "total_files": len(self.files),
                "python_files": len([f for f in self.files if f.endswith('.py')]),
                "json_files": len([f for f in self.files if f.endswith('.json')]),
                "markdown_files": len([f for f in self.files if f.endswith('.md')])
            },
            "categories": {k: v for k, v in self.categories.items() if v},
            "duplicates": self.duplicates,
            "orphaned_files": self.orphaned_files,
            "undocumented_files": [f for f, info in self.files.items() 
                                 if f.endswith('.py') and not info.has_docstring],
            "dependencies": {k: list(v) for k, v in self.dependencies.items()},
            "file_details": {
                path: {
                    "size": info.size,
                    "extension": info.extension,
                    "imports": list(info.imports),
                    "functions": info.functions,
                    "classes": info.classes,
                    "has_main": info.has_main,
                    "has_docstring": info.has_docstring,
                    "is_test": info.is_test,
                    "is_demo": info.is_demo
                }
                for path, info in self.files.items()
            }
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(detailed_report, f, indent=2, ensure_ascii=False)
            
        print(f"💾 گزارش تفصیلی در {filename} ذخیره شد")

def main():
    """تابع اصلی"""
    print("🚀 شروع تحلیل پروژه TikTrue Platform")
    
    analyzer = ProjectAnalyzer()
    analyzer.analyze_project()
    
    # نمایش گزارش
    report = analyzer.generate_report()
    print(report)
    
    # ذخیره گزارش تفصیلی
    analyzer.save_detailed_report()
    
    print("\n✅ تحلیل کامل شد!")

if __name__ == "__main__":
    main()