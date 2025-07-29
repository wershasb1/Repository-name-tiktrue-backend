#!/usr/bin/env python3
"""
Setup Validator for Distributed Inference System
اسکریپت تنظیم و اعتبارسنجی سیستم inference توزیعی
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import colorama
from colorama import Fore, Style

# Initialize colorama
colorama.init(autoreset=True)

def setup_logging(level: str = "INFO"):
    """تنظیم logging"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('setup_validation.log')
        ]
    )

class SystemValidator:
    """اعتبارسنجی و تنظیم سیستم"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.issues: List[str] = []
        self.warnings: List[str] = []
        self.fixes_applied: List[str] = []
        
        print(f"{Style.BRIGHT}🔍 System Validator initialized{Style.RESET_ALL}")
        print(f"📁 Project root: {self.project_root}")
    
    def validate_python_environment(self) -> bool:
        """بررسی محیط Python"""
        print(f"\n{Style.BRIGHT}🐍 Validating Python Environment{Style.RESET_ALL}")
        
        # بررسی نسخه Python
        if sys.version_info < (3, 8):
            self.issues.append(f"Python 3.8+ required, found {sys.version}")
            return False
        
        print(f"✅ Python version: {sys.version.split()[0]}")
        
        # بررسی کتابخانه‌های ضروری
        required_packages = [
            'numpy', 'websockets', 'onnxruntime', 'transformers', 
            'psutil', 'colorama', 'pathlib'
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package)
                print(f"✅ {package}")
            except ImportError:
                missing_packages.append(package)
                print(f"❌ {package} - Missing")
        
        if missing_packages:
            self.issues.append(f"Missing packages: {', '.join(missing_packages)}")
            print(f"\n{Fore.YELLOW}💡 Install missing packages with:{Style.RESET_ALL}")
            print(f"pip install {' '.join(missing_packages)}")
            return False
        
        return True
    
    def validate_project_structure(self) -> bool:
        """بررسی ساختار پروژه"""
        print(f"\n{Style.BRIGHT}📁 Validating Project Structure{Style.RESET_ALL}")
        
        # فایل‌های ضروری
        required_files = [
            'core/model_node.py',
            'core/config_manager.py',
            'workers/worker_lib.py',
            'workers/scheduler_lib.py',
            'workers/homf_lib.py',
            'utils/serialization_utils.py',
            'custom_logging.py',
            'workers/paged_kv_cache_lib.py',
            'workers/sequential_gpu_worker_lib.py',
            'interfaces/chatbot_interface.py',
            'requirements.txt'
        ]
        
        missing_files = []
        for file in required_files:
            file_path = self.project_root / file
            if file_path.exists():
                print(f"✅ {file}")
            else:
                missing_files.append(file)
                print(f"❌ {file} - Missing")
        
        if missing_files:
            self.issues.append(f"Missing core files: {', '.join(missing_files)}")
            return False
        
        # بررسی دایرکتوری‌های مهم
        important_dirs = ['assets', 'logs', 'sessions']
        for dir_name in important_dirs:
            dir_path = self.project_root / dir_name
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                self.fixes_applied.append(f"Created directory: {dir_name}")
                print(f"🔧 Created: {dir_name}/")
            else:
                print(f"✅ {dir_name}/")
        
        return True
    
    def validate_configuration_files(self) -> bool:
        """بررسی فایل‌های تنظیمات"""
        print(f"\n{Style.BRIGHT}⚙️ Validating Configuration Files{Style.RESET_ALL}")
        
        # جستجو برای فایل‌های config
        config_files = [
            'config/network_config.json',
            'config/network_config_llama_single_node.json',
            'config/network_config_mistral_single_node.json'
        ]
        
        found_configs = []
        for config_file in config_files:
            config_path = self.project_root / config_file
            if config_path.exists():
                found_configs.append(config_file)
                print(f"✅ {config_file}")
                
                # اعتبارسنجی JSON
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                    
                    # بررسی کلیدهای ضروری
                    required_keys = ['model_chain_order', 'nodes', 'paths']
                    for key in required_keys:
                        if key not in config_data:
                            self.issues.append(f"Missing key '{key}' in {config_file}")
                        else:
                            print(f"  ✅ {key}")
                    
                except json.JSONDecodeError as e:
                    self.issues.append(f"Invalid JSON in {config_file}: {e}")
                    print(f"  ❌ Invalid JSON: {e}")
            else:
                print(f"⚠️  {config_file} - Not found")
        
        if not found_configs:
            self.issues.append("No network configuration files found")
            return False
        
        return True
    
    def validate_model_files(self) -> bool:
        """بررسی فایل‌های مدل"""
        print(f"\n{Style.BRIGHT}🧠 Validating Model Files{Style.RESET_ALL}")
        
        # بررسی ConfigManager
        try:
            from core.config_manager import ConfigManager
            config_manager = ConfigManager()
            
            # بررسی metadata
            metadata_path = Path(config_manager.network_config["paths"]["metadata_file"])
            if metadata_path.exists():
                print(f"✅ Metadata file: {metadata_path}")
                
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                # بررسی کلیدهای ضروری در metadata
                required_metadata_keys = ['block_io_details', 'num_key_value_heads', 'head_dim']
                for key in required_metadata_keys:
                    if key in metadata:
                        print(f"  ✅ {key}")
                    else:
                        self.issues.append(f"Missing key '{key}' in metadata")
                        print(f"  ❌ {key}")
            else:
                self.issues.append(f"Metadata file not found: {metadata_path}")
                print(f"❌ Metadata file: {metadata_path}")
            
            # بررسی دایرکتوری مدل‌ها
            onnx_dir = Path(config_manager.network_config["paths"]["onnx_blocks_dir"])
            if onnx_dir.exists():
                print(f"✅ ONNX models directory: {onnx_dir}")
                
                # شمارش فایل‌های .onnx
                onnx_files = list(onnx_dir.glob("*.onnx"))
                print(f"  📊 Found {len(onnx_files)} ONNX files")
                
                if len(onnx_files) < 33:
                    self.warnings.append(f"Expected 33 ONNX files, found {len(onnx_files)}")
                
                # بررسی چند فایل اول
                for i in range(1, min(4, len(onnx_files) + 1)):
                    block_file = onnx_dir / f"block_{i}.onnx"
                    if block_file.exists():
                        print(f"  ✅ block_{i}.onnx")
                    else:
                        print(f"  ⚠️  block_{i}.onnx - Not found")
            else:
                self.issues.append(f"ONNX models directory not found: {onnx_dir}")
                print(f"❌ ONNX models directory: {onnx_dir}")
            
            # بررسی tokenizer
            tokenizer_path = config_manager.get_tokenizer_path()
            if tokenizer_path and tokenizer_path.exists():
                print(f"✅ Tokenizer: {tokenizer_path}")
            else:
                self.warnings.append("Tokenizer not found in expected locations")
                print(f"⚠️  Tokenizer not found")
            
        except Exception as e:
            self.issues.append(f"Error validating model files: {e}")
            print(f"❌ Error: {e}")
            return False
        
        return True
    
    def validate_imports(self) -> bool:
        """بررسی import های پروژه"""
        print(f"\n{Style.BRIGHT}📦 Validating Project Imports{Style.RESET_ALL}")
        
        # لیست ماژول‌های پروژه
        project_modules = [
            'core.config_manager',
            'workers.worker_lib', 
            'workers.scheduler_lib',
            'workers.homf_lib',
            'utils.serialization_utils',
            'custom_logging',
            'workers.paged_kv_cache_lib',
            'workers.sequential_gpu_worker_lib'
        ]
        
        # اضافه کردن project root به path
        if str(self.project_root) not in sys.path:
            sys.path.insert(0, str(self.project_root))
        
        import_issues = []
        for module in project_modules:
            try:
                __import__(module)
                print(f"✅ {module}")
            except ImportError as e:
                import_issues.append(f"{module}: {e}")
                print(f"❌ {module}: {e}")
        
        if import_issues:
            self.issues.extend(import_issues)
            return False
        
        return True
    
    def create_portable_package(self) -> bool:
        """ایجاد بسته قابل حمل"""
        print(f"\n{Style.BRIGHT}📦 Creating Portable Package{Style.RESET_ALL}")
        
        try:
            from core.config_manager import ConfigManager
            config_manager = ConfigManager()
            
            # ایجاد portable config
            portable_config_path = config_manager.create_portable_config("portable_config.json")
            print(f"✅ Created: {portable_config_path}")
            
            # ایجاد اسکریپت راه‌اندازی
            startup_script = self.project_root / "start_server.py"
            startup_content = '''#!/usr/bin/env python3
"""
Startup script for Distributed Inference System
اسکریپت راه‌اندازی سیستم inference توزیعی
"""

import sys
import argparse
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

def main():
    parser = argparse.ArgumentParser(description="Start Distributed Inference Server")
    parser.add_argument("--node-id", default="physical_node_1", help="Node ID")
    parser.add_argument("--config", default="network_config.json", help="Network config file")
    parser.add_argument("--log-level", default="INFO", help="Log level")
    parser.add_argument("--max-warm-homf", type=int, default=5, help="Max warm HOMF sessions")
    
    args = parser.parse_args()
    
    # Import and run
    from core.model_node import main_server
    import asyncio
    
    config_path = project_root / args.config
    
    asyncio.run(main_server(
        node_id_arg=args.node_id,
        network_config_file_path_arg=config_path,
        initial_kv_pages_arg=16,
        kv_page_tokens_arg=16,
        max_warm_sessions_homf_arg=args.max_warm_homf
    ))

if __name__ == "__main__":
    main()
'''
            
            with open(startup_script, 'w', encoding='utf-8') as f:
                f.write(startup_content)
            
            print(f"✅ Created: {startup_script}")
            
            # ایجاد README
            readme_path = self.project_root / "README_SETUP.md"
            readme_content = f'''# Distributed LLM Inference System

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Validate Setup
```bash
python utils/setup_validator.py --validate-all
```

### 3. Start Server
```bash
python start_server.py --node-id physical_node_1 --config network_config.json
```

### 4. Start Chatbot Client
```bash
python chatbot_interface.py --tokenizer-path assets/models/llama3_1_8b_fp16/blocks/tokenizer
```

## Project Structure
- `core/model_node.py` - Main inference server
- `core/config_manager.py` - Configuration management
- `workers/worker_lib.py` - CPU/GPU workers
- `interfaces/chatbot_interface.py` - Chat client
- `assets/models/` - Model files
- `logs/` - Log files
- `sessions/` - Session data

## Configuration
- Network config: `config/network_config.json`
- Model metadata: `assets/models/llama3_1_8b_fp16/metadata.json`
- Portable config: `portable_config.json`

## Troubleshooting
1. Run validator: `python utils/setup_validator.py --validate-all --fix`
2. Check logs in `logs/` directory
3. Verify model files in `assets/models/`

Generated by setup_validator.py on {Path.cwd()}
'''
            
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(readme_content)
            
            print(f"✅ Created: {readme_path}")
            
            return True
            
        except Exception as e:
            self.issues.append(f"Error creating portable package: {e}")
            print(f"❌ Error: {e}")
            return False
    
    def fix_common_issues(self) -> bool:
        """اصلاح مشکلات رایج"""
        print(f"\n{Style.BRIGHT}🔧 Fixing Common Issues{Style.RESET_ALL}")
        
        fixes_applied = 0
        
        # ایجاد دایرکتوری‌های مفقود
        required_dirs = ['logs', 'sessions', 'assets', 'assets/models']
        for dir_name in required_dirs:
            dir_path = self.project_root / dir_name
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                print(f"🔧 Created directory: {dir_name}")
                fixes_applied += 1
        
        # اصلاح مجوزهای فایل‌ها (در Linux/Mac)
        if sys.platform != 'win32':
            script_files = ['start_server.py', 'utils/setup_validator.py']
            for script in script_files:
                script_path = self.project_root / script
                if script_path.exists():
                    os.chmod(script_path, 0o755)
                    print(f"🔧 Made executable: {script}")
                    fixes_applied += 1
        
        print(f"✅ Applied {fixes_applied} fixes")
        return fixes_applied > 0
    
    def generate_report(self) -> Dict[str, Any]:
        """تولید گزارش نهایی"""
        return {
            "project_root": str(self.project_root),
            "validation_status": "PASSED" if not self.issues else "FAILED",
            "issues": self.issues,
            "warnings": self.warnings,
            "fixes_applied": self.fixes_applied,
            "summary": {
                "total_issues": len(self.issues),
                "total_warnings": len(self.warnings),
                "fixes_applied": len(self.fixes_applied)
            }
        }
    
    def run_full_validation(self, fix_issues: bool = False) -> bool:
        """اجرای اعتبارسنجی کامل"""
        print(f"{Style.BRIGHT}🚀 Starting Full System Validation{Style.RESET_ALL}")
        print("=" * 60)
        
        validation_steps = [
            ("Python Environment", self.validate_python_environment),
            ("Project Structure", self.validate_project_structure),
            ("Configuration Files", self.validate_configuration_files),
            ("Model Files", self.validate_model_files),
            ("Project Imports", self.validate_imports),
            ("Portable Package", self.create_portable_package)
        ]
        
        passed_steps = 0
        total_steps = len(validation_steps)
        
        for step_name, step_func in validation_steps:
            print(f"\n{Style.BRIGHT}📋 {step_name}{Style.RESET_ALL}")
            try:
                if step_func():
                    passed_steps += 1
                    print(f"✅ {step_name} - PASSED")
                else:
                    print(f"❌ {step_name} - FAILED")
            except Exception as e:
                print(f"💥 {step_name} - ERROR: {e}")
                self.issues.append(f"{step_name}: {e}")
        
        # اصلاح مشکلات در صورت درخواست
        if fix_issues:
            self.fix_common_issues()
        
        # نمایش گزارش نهایی
        print(f"\n{Style.BRIGHT}📊 Validation Summary{Style.RESET_ALL}")
        print("=" * 60)
        print(f"✅ Passed: {passed_steps}/{total_steps}")
        print(f"❌ Issues: {len(self.issues)}")
        print(f"⚠️  Warnings: {len(self.warnings)}")
        print(f"🔧 Fixes Applied: {len(self.fixes_applied)}")
        
        if self.issues:
            print(f"\n{Fore.RED}❌ Issues Found:{Style.RESET_ALL}")
            for i, issue in enumerate(self.issues, 1):
                print(f"  {i}. {issue}")
        
        if self.warnings:
            print(f"\n{Fore.YELLOW}⚠️  Warnings:{Style.RESET_ALL}")
            for i, warning in enumerate(self.warnings, 1):
                print(f"  {i}. {warning}")
        
        if self.fixes_applied:
            print(f"\n{Fore.GREEN}🔧 Fixes Applied:{Style.RESET_ALL}")
            for i, fix in enumerate(self.fixes_applied, 1):
                print(f"  {i}. {fix}")
        
        # ذخیره گزارش
        report = self.generate_report()
        report_path = self.project_root / "validation_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Full report saved to: {report_path}")
        
        success = len(self.issues) == 0
        if success:
            print(f"\n{Fore.GREEN}{Style.BRIGHT}🎉 System validation completed successfully!{Style.RESET_ALL}")
            print(f"{Fore.GREEN}✅ Your system is ready to run!{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.RED}{Style.BRIGHT}❌ System validation failed!{Style.RESET_ALL}")
            print(f"{Fore.RED}Please fix the issues above before running the system.{Style.RESET_ALL}")
        
        return success


def main():
    """تابع اصلی"""
    parser = argparse.ArgumentParser(
        description="Setup Validator for Distributed Inference System",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("--project-root", type=Path, help="Project root directory")
    parser.add_argument("--validate-all", action="store_true", help="Run full validation")
    parser.add_argument("--fix", action="store_true", help="Attempt to fix common issues")
    parser.add_argument("--log-level", default="INFO", help="Log level")
    
    args = parser.parse_args()
    
    # تنظیم logging
    setup_logging(args.log_level)
    
    # ایجاد validator
    validator = SystemValidator(args.project_root)
    
    if args.validate_all:
        success = validator.run_full_validation(fix_issues=args.fix)
        sys.exit(0 if success else 1)
    else:
        print("Use --validate-all to run full system validation")
        print("Use --fix to attempt automatic fixes")


if __name__ == "__main__":
    main()