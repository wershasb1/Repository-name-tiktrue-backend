#!/usr/bin/env python3
"""
Model Selector for Distributed Inference System
انتخابگر مدل برای سیستم inference توزیعی
"""

import sys
import argparse
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import colorama
from colorama import Fore, Style

# Initialize colorama
colorama.init(autoreset=True)

def setup_project_path():
    """تنظیم مسیر پروژه"""
    project_root = Path(__file__).resolve().parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

class ModelSelector:
    """انتخابگر مدل"""
    
    def __init__(self):
        setup_project_path()
        
        try:
            from core.config_manager import ConfigManager
            self.config_manager = ConfigManager()
        except Exception as e:
            print(f"{Fore.RED}❌ Error initializing ConfigManager: {e}{Style.RESET_ALL}")
            sys.exit(1)
    
    def list_models(self) -> None:
        """نمایش لیست مدل‌های موجود"""
        models = self.config_manager.list_available_models()
        
        if not models:
            print(f"{Fore.YELLOW}⚠️  No models found in the system{Style.RESET_ALL}")
            return
        
        print(f"\n{Style.BRIGHT}🧠 Available Models:{Style.RESET_ALL}")
        print("=" * 80)
        
        current_model_id = self.config_manager.selected_model["id"]
        
        for i, model in enumerate(models, 1):
            status = f"{Fore.GREEN}[ACTIVE]{Style.RESET_ALL}" if model["id"] == current_model_id else ""
            
            print(f"{Style.BRIGHT}{i}. {model['name']} {status}{Style.RESET_ALL}")
            print(f"   ID: {model['id']}")
            print(f"   Type: {model['type']}")
            print(f"   Description: {model['description']}")
            print(f"   Blocks: {model['total_blocks']}")
            print(f"   Tokenizer: {'✅' if model['has_tokenizer'] else '❌'}")
            print("-" * 60)
    
    def show_model_details(self, model_id: str) -> None:
        """نمایش جزئیات یک مدل"""
        try:
            model_info = self.config_manager.get_model_info(model_id)
        except ValueError as e:
            print(f"{Fore.RED}❌ {e}{Style.RESET_ALL}")
            return
        
        print(f"\n{Style.BRIGHT}📋 Model Details: {model_info['name']}{Style.RESET_ALL}")
        print("=" * 60)
        
        # اطلاعات کلی
        print(f"🏷️  ID: {model_info['id']}")
        print(f"📝 Name: {model_info['name']}")
        print(f"🔧 Type: {model_info['type']}")
        print(f"📖 Description: {model_info['description']}")
        print(f"🔢 Version: {model_info['version']}")
        
        # آمار
        stats = model_info['stats']
        print(f"\n{Style.BRIGHT}📊 Statistics:{Style.RESET_ALL}")
        print(f"   Total blocks: {stats['total_blocks']}")
        print(f"   Expected blocks: {stats['expected_blocks']}")
        if 'total_files' in stats:
            print(f"   ONNX files: {stats['total_files']}")
        print(f"   Has tokenizer: {'✅' if stats['has_tokenizer'] else '❌'}")
        
        # مسیرها
        paths = model_info['paths']
        print(f"\n{Style.BRIGHT}📁 Paths:{Style.RESET_ALL}")
        print(f"   Model directory: {paths['model_dir']}")
        print(f"   Blocks directory: {paths['blocks_dir']}")
        print(f"   Metadata file: {paths['metadata_file']}")
        if paths['tokenizer_dir']:
            print(f"   Tokenizer directory: {paths['tokenizer_dir']}")
        
        # بررسی وضعیت فایل‌ها
        print(f"\n{Style.BRIGHT}🔍 File Status:{Style.RESET_ALL}")
        
        # بررسی metadata
        metadata_path = Path(paths['metadata_file'])
        print(f"   Metadata: {'✅' if metadata_path.exists() else '❌'}")
        
        # بررسی blocks
        blocks_dir = Path(paths['blocks_dir'])
        if blocks_dir.exists():
            onnx_files = list(blocks_dir.glob("*.onnx"))
            print(f"   ONNX blocks: {len(onnx_files)} files found")
            
            # نمایش چند فایل اول
            if onnx_files:
                print(f"   Sample blocks:")
                for onnx_file in sorted(onnx_files)[:5]:
                    print(f"     - {onnx_file.name}")
                if len(onnx_files) > 5:
                    print(f"     ... and {len(onnx_files) - 5} more")
        else:
            print(f"   ONNX blocks: ❌ Directory not found")
        
        # بررسی tokenizer
        if paths['tokenizer_dir']:
            tokenizer_path = Path(paths['tokenizer_dir'])
            print(f"   Tokenizer: {'✅' if tokenizer_path.exists() else '❌'}")
    
    def select_model(self, model_id: str) -> bool:
        """انتخاب مدل"""
        try:
            success = self.config_manager.switch_model(model_id)
            if success:
                print(f"{Fore.GREEN}✅ Successfully switched to model: {model_id}{Style.RESET_ALL}")
                
                # نمایش اطلاعات مدل جدید
                model_info = self.config_manager.get_model_info(model_id)
                print(f"   Name: {model_info['name']}")
                print(f"   Type: {model_info['type']}")
                print(f"   Blocks: {model_info['stats']['total_blocks']}")
                
                return True
            else:
                print(f"{Fore.RED}❌ Failed to switch to model: {model_id}{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error switching model: {e}{Style.RESET_ALL}")
            return False
    
    def interactive_selection(self) -> None:
        """انتخاب تعاملی مدل"""
        models = self.config_manager.list_available_models()
        
        if not models:
            print(f"{Fore.YELLOW}⚠️  No models found in the system{Style.RESET_ALL}")
            return
        
        print(f"\n{Style.BRIGHT}🎯 Interactive Model Selection{Style.RESET_ALL}")
        print("=" * 50)
        
        current_model_id = self.config_manager.selected_model["id"]
        
        # نمایش مدل‌های موجود
        for i, model in enumerate(models, 1):
            status = f" {Fore.GREEN}[CURRENT]{Style.RESET_ALL}" if model["id"] == current_model_id else ""
            print(f"{i}. {model['name']}{status}")
            print(f"   ID: {model['id']} | Type: {model['type']} | Blocks: {model['total_blocks']}")
        
        print(f"\n{len(models) + 1}. Show detailed info for a model")
        print(f"{len(models) + 2}. Exit")
        
        while True:
            try:
                choice = input(f"\n{Fore.CYAN}Select option (1-{len(models) + 2}): {Style.RESET_ALL}")
                
                if not choice.strip():
                    continue
                
                choice_num = int(choice)
                
                if 1 <= choice_num <= len(models):
                    # انتخاب مدل
                    selected_model = models[choice_num - 1]
                    
                    if selected_model["id"] == current_model_id:
                        print(f"{Fore.YELLOW}ℹ️  Model '{selected_model['name']}' is already selected{Style.RESET_ALL}")
                        continue
                    
                    confirm = input(f"Switch to '{selected_model['name']}'? (y/N): ")
                    if confirm.lower() in ['y', 'yes']:
                        if self.select_model(selected_model["id"]):
                            break
                    
                elif choice_num == len(models) + 1:
                    # نمایش جزئیات
                    model_id = input("Enter model ID for details: ").strip()
                    if model_id:
                        self.show_model_details(model_id)
                
                elif choice_num == len(models) + 2:
                    # خروج
                    print(f"{Fore.YELLOW}👋 Goodbye!{Style.RESET_ALL}")
                    break
                
                else:
                    print(f"{Fore.RED}❌ Invalid choice. Please select 1-{len(models) + 2}{Style.RESET_ALL}")
                    
            except ValueError:
                print(f"{Fore.RED}❌ Please enter a valid number{Style.RESET_ALL}")
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}👋 Interrupted by user{Style.RESET_ALL}")
                break
    
    def validate_model(self, model_id: str) -> bool:
        """اعتبارسنجی یک مدل"""
        try:
            model_info = self.config_manager.get_model_info(model_id)
        except ValueError as e:
            print(f"{Fore.RED}❌ {e}{Style.RESET_ALL}")
            return False
        
        print(f"\n{Style.BRIGHT}🔍 Validating Model: {model_info['name']}{Style.RESET_ALL}")
        print("=" * 50)
        
        issues = []
        warnings = []
        
        # بررسی metadata
        metadata_path = Path(model_info['paths']['metadata_file'])
        if metadata_path.exists():
            print(f"✅ Metadata file exists")
            
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                required_keys = ['block_io_details', 'num_key_value_heads', 'head_dim']
                for key in required_keys:
                    if key in metadata:
                        print(f"  ✅ {key}")
                    else:
                        issues.append(f"Missing key '{key}' in metadata")
                        print(f"  ❌ {key}")
                        
            except Exception as e:
                issues.append(f"Error reading metadata: {e}")
                print(f"  ❌ Error reading metadata: {e}")
        else:
            issues.append("Metadata file not found")
            print(f"❌ Metadata file not found")
        
        # بررسی blocks
        blocks_dir = Path(model_info['paths']['blocks_dir'])
        if blocks_dir.exists():
            print(f"✅ Blocks directory exists")
            
            onnx_files = list(blocks_dir.glob("*.onnx"))
            expected_blocks = model_info['stats']['expected_blocks']
            
            print(f"  📊 Found {len(onnx_files)} ONNX files (expected: {expected_blocks})")
            
            if len(onnx_files) < expected_blocks:
                warnings.append(f"Missing ONNX files: found {len(onnx_files)}, expected {expected_blocks}")
            
            # بررسی چند فایل اول با الگوهای مختلف
            for i in range(1, min(4, expected_blocks + 1)):
                block_id = f"block_{i}"
                
                # الگوهای مختلف نام‌گذاری
                possible_patterns = [
                    f"{block_id}.onnx",
                    f"{block_id}_skeleton.optimized.onnx",
                    f"{block_id}_skeleton_with_zeros.onnx",
                    f"{block_id}_optimized.onnx"
                ]
                
                found = False
                for pattern in possible_patterns:
                    block_file = blocks_dir / pattern
                    if block_file.exists():
                        print(f"  ✅ {block_id} (found as {pattern})")
                        found = True
                        break
                
                if not found:
                    issues.append(f"Missing {block_id} (searched: {possible_patterns})")
                    print(f"  ❌ {block_id}")
        else:
            issues.append("Blocks directory not found")
            print(f"❌ Blocks directory not found")
        
        # بررسی tokenizer
        tokenizer_dir = model_info['paths']['tokenizer_dir']
        if tokenizer_dir and Path(tokenizer_dir).exists():
            print(f"✅ Tokenizer directory exists")
        else:
            warnings.append("Tokenizer directory not found")
            print(f"⚠️  Tokenizer directory not found")
        
        # خلاصه
        print(f"\n{Style.BRIGHT}📊 Validation Summary:{Style.RESET_ALL}")
        print(f"✅ Passed checks: {3 - len(issues)}/3")
        print(f"❌ Issues: {len(issues)}")
        print(f"⚠️  Warnings: {len(warnings)}")
        
        if issues:
            print(f"\n{Fore.RED}❌ Issues found:{Style.RESET_ALL}")
            for issue in issues:
                print(f"  - {issue}")
        
        if warnings:
            print(f"\n{Fore.YELLOW}⚠️  Warnings:{Style.RESET_ALL}")
            for warning in warnings:
                print(f"  - {warning}")
        
        if not issues:
            print(f"\n{Fore.GREEN}✅ Model validation passed!{Style.RESET_ALL}")
            return True
        else:
            print(f"\n{Fore.RED}❌ Model validation failed!{Style.RESET_ALL}")
            return False


def main():
    """تابع اصلی"""
    parser = argparse.ArgumentParser(
        description="Model Selector for Distributed Inference System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python model_selector.py --list                    # List available models
  python model_selector.py --select llama3_1_8b_fp16 # Select a specific model
  python model_selector.py --details mistral_7b_int4 # Show model details
  python model_selector.py --interactive             # Interactive selection
  python model_selector.py --validate llama3_1_8b_fp16 # Validate a model
        """
    )
    
    parser.add_argument("--list", action="store_true", help="List available models")
    parser.add_argument("--select", help="Select a specific model by ID")
    parser.add_argument("--details", help="Show detailed info for a model")
    parser.add_argument("--interactive", action="store_true", help="Interactive model selection")
    parser.add_argument("--validate", help="Validate a specific model")
    parser.add_argument("--current", action="store_true", help="Show current selected model")
    
    args = parser.parse_args()
    
    # اگر هیچ آرگومان داده نشده، حالت تعاملی را اجرا کن
    if not any(vars(args).values()):
        args.interactive = True
    
    try:
        selector = ModelSelector()
        
        if args.list:
            selector.list_models()
        
        elif args.select:
            selector.select_model(args.select)
        
        elif args.details:
            selector.show_model_details(args.details)
        
        elif args.validate:
            selector.validate_model(args.validate)
        
        elif args.current:
            current_model = selector.config_manager.selected_model
            print(f"\n{Style.BRIGHT}🎯 Current Selected Model:{Style.RESET_ALL}")
            print(f"   ID: {current_model['id']}")
            print(f"   Name: {current_model['name']}")
            print(f"   Type: {current_model['type']}")
            print(f"   Blocks: {current_model['stats']['total_blocks']}")
        
        elif args.interactive:
            selector.interactive_selection()
        
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}👋 Interrupted by user{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}💥 Error: {e}{Style.RESET_ALL}")
        sys.exit(1)


if __name__ == "__main__":
    main()