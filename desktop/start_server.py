#!/usr/bin/env python3
"""
Startup script for Distributed Inference System
اسکریپت راه‌اندازی سیستم inference توزیعی
"""

import sys
import argparse
import asyncio
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

def setup_logging(level: str = "INFO", log_file: str = None):
    """تنظیم logging"""
    handlers = [logging.StreamHandler()]
    
    if log_file:
        log_path = project_root / "logs" / log_file
        log_path.parent.mkdir(exist_ok=True)
        handlers.append(logging.FileHandler(log_path))
    
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )

def main():
    """تابع اصلی"""
    parser = argparse.ArgumentParser(
        description="Start Distributed Inference Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python start_server.py
  python start_server.py --node-id physical_node_1 --config network_config.json
  python start_server.py --log-level DEBUG --max-warm-homf 10
  python start_server.py --model mistral_7b_int4
        """
    )
    
    parser.add_argument("--node-id", 
                       default="physical_node_1", 
                       help="Node ID for this server instance")
    
    parser.add_argument("--config", 
                       default="network_config.json", 
                       help="Network configuration file")
    
    parser.add_argument("--log-level", 
                       default="INFO", 
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Logging level")
    
    parser.add_argument("--log-file", 
                       help="Log file name (saved in logs/ directory)")
    
    parser.add_argument("--max-warm-homf", 
                       type=int, 
                       default=5, 
                       help="Maximum warm HOMF sessions")
    
    parser.add_argument("--initial-kv-pages", 
                       type=int, 
                       default=16, 
                       help="Initial KV cache pages")
    
    parser.add_argument("--kv-page-tokens", 
                       type=int, 
                       default=16, 
                       help="Tokens per KV cache page")
    
    parser.add_argument("--validate-first", 
                       action="store_true", 
                       help="Run system validation before starting")
    
    parser.add_argument("--model", 
                       help="Model ID to use (e.g., llama3_1_8b_fp16, mistral_7b_int4)")
    
    parser.add_argument("--list-models", 
                       action="store_true", 
                       help="List available models and exit")
    
    parser.add_argument("--profile-system", 
                       action="store_true", 
                       help="Profile system performance and create performance_profile.json")
    
    args = parser.parse_args()
    
    # نمایش مدل‌های موجود و خروج
    if args.list_models:
        try:
            from model_selector import ModelSelector
            selector = ModelSelector()
            selector.list_models()
        except Exception as e:
            print(f"❌ Error listing models: {e}")
        sys.exit(0)
    
    # اجرای system profiling و خروج
    if args.profile_system:
        print("📊 Starting system performance profiling...")
        try:
            from workers.static_profiler import HybridProfiler
            
            # تعیین config file
            config_path = project_root / args.config
            if not config_path.exists():
                print(f"❌ Configuration file not found: {config_path}")
                sys.exit(1)
            
            # ایجاد profiler
            profiler = HybridProfiler(args.config, debug=True)
            
            print("🔧 Creating optimized models...")
            profiler.create_optimized_models()
            
            print("📈 Running performance profiling...")
            results = profiler.sequential_profile()
            
            print("💾 Saving results...")
            profiler.save_results(results, "performance_profile.json")
            
            print("📊 Printing summary...")
            profiler.print_summary(results)
            
            print("✅ System profiling completed!")
            print("📄 Results saved to: performance_profile.json")
            
        except Exception as e:
            print(f"❌ Error during profiling: {e}")
            import traceback
            traceback.print_exc()
        sys.exit(0)
    
    # تنظیم logging
    setup_logging(args.log_level, args.log_file)
    
    print("🚀 Distributed LLM Inference System")
    print("=" * 50)
    print(f"📁 Project root: {project_root}")
    print(f"🏷️  Node ID: {args.node_id}")
    print(f"⚙️  Config: {args.config}")
    print(f"📊 Log level: {args.log_level}")
    if args.model:
        print(f"🧠 Model: {args.model}")
    print("=" * 50)
    
    # اعتبارسنجی اولیه در صورت درخواست
    if args.validate_first:
        print("🔍 Running system validation...")
        try:
            from utils.setup_validator import SystemValidator
            validator = SystemValidator(project_root)
            if not validator.run_full_validation(fix_issues=True):
                print("❌ System validation failed. Please fix issues before starting.")
                sys.exit(1)
            print("✅ System validation passed!")
        except Exception as e:
            print(f"⚠️  Validation error: {e}")
            print("Continuing without validation...")
    
    # بررسی وجود فایل config
    config_path = project_root / args.config
    if not config_path.exists():
        print(f"❌ Configuration file not found: {config_path}")
        
        # جستجو برای فایل‌های config موجود
        possible_configs = [
            "network_config.json",
            "network_config_llama_single_node.json",
            "network_config_mistral_single_node.json"
        ]
        
        found_configs = [c for c in possible_configs if (project_root / c).exists()]
        
        if found_configs:
            print(f"💡 Available config files: {', '.join(found_configs)}")
            print(f"Use: python start_server.py --config {found_configs[0]}")
        else:
            print("💡 No configuration files found. Please create one or run setup_validator.py")
        
        sys.exit(1)
    
    try:
        # Import و اجرای سرور
        print("📦 Loading modules...")
        from core.model_node import main_server
        
        print("🔧 Initializing configuration...")
        from core.config_manager import initialize_config
        
        # اگر مدل مشخص شده، از آن استفاده کن
        if args.model:
            print(f"🎯 Using specified model: {args.model}")
            config_manager = initialize_config(str(config_path), model_id=args.model)
        else:
            config_manager = initialize_config(str(config_path))
        
        print("✅ Configuration loaded successfully")
        print(f"🧠 Selected model: {config_manager.selected_model['name']} ({config_manager.selected_model['id']})")
        print(f"📦 Model blocks: {len(config_manager.network_config.get('model_chain_order', []))}")
        print(f"🔤 Tokenizer: {'✅' if config_manager.selected_model['stats']['has_tokenizer'] else '❌'}")
        
        # اجرای سرور
        print("🚀 Starting server...")
        asyncio.run(main_server(
            node_id_arg=args.node_id,
            network_config_file_path_arg=config_path,
            initial_kv_pages_arg=args.initial_kv_pages,
            kv_page_tokens_arg=args.kv_page_tokens,
            max_warm_sessions_homf_arg=args.max_warm_homf
        ))
        
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        logging.error(f"Server error: {e}", exc_info=True)
        print(f"❌ Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()