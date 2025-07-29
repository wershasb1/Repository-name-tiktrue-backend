#!/usr/bin/env python3

"""
Hybrid Profiler - Best of Both Worlds
====================================
Combines optimization from static_profiler.py with sequential testing capability
--------
python scripts\static_profiler.py --network-config network_config.json
# اجرا با تنظیمات سفارشی
python scripts/static_profiler.py --network-config network_config.json --warmup-runs 5 --benchmark-runs 20
---------
"""

import argparse
import json
import time
import numpy as np
import onnxruntime as ort
from pathlib import Path
from typing import Dict, List, Optional

class HybridProfiler:
    def __init__(self, network_config_path: Path, debug: bool = False):
        self.network_config_path = network_config_path
        self.debug = debug
        
        # Fix project root calculation
        if Path.cwd().name == 'scripts':
            self.project_root = Path.cwd().parent  # Go up one level from scripts/
        else:
            self.project_root = Path.cwd()  # Already in project root
            
        if self.debug:
            print(f"Project root: {self.project_root}")
        
        # Load configuration
        config_path = self.project_root / network_config_path
        with open(config_path, 'r') as f:
            self.network_config = json.load(f)
            
        # Load metadata  
        metadata_path = self.project_root / Path(self.network_config['paths']['metadata_file'])
        with open(metadata_path, 'r') as f:
            self.metadata = json.load(f)
    
    def create_optimized_models(self):
        """Create optimized ONNX models (from static_profiler.py logic)"""
        print("🔧 Creating optimized models...")
        
        blocks = self._get_blocks_to_profile()
        providers_to_test = [
            ['CPUExecutionProvider'],
            ['DmlExecutionProvider', 'CPUExecutionProvider']
        ]
        
        optimized_dir = self.project_root / "optimized_models"
        optimized_dir.mkdir(parents=True, exist_ok=True)
        
        for block_id in blocks:
            print(f"📦 Optimizing {block_id}...")
            
            # Get model path
            model_path = self._get_block_model_path(block_id)
            
            for providers in providers_to_test:
                provider_key = providers[0].replace('ExecutionProvider', '')
                
                # Create session options
                so = ort.SessionOptions()
                so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
                so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_EXTENDED
                
                # Set optimized model path
                optimized_path = optimized_dir / f"{block_id}_{provider_key}.onnx"
                so.optimized_model_filepath = str(optimized_path)
                
                try:
                    # Create session to trigger optimization
                    session = ort.InferenceSession(str(model_path), so, providers=providers)
                    print(f"  ✅ {provider_key}: {optimized_path}")
                except Exception as e:
                    print(f"  ❌ {provider_key}: {e}")
        
        print("🎉 Optimization completed!")
    
    def sequential_profile(self, batch_size=1, seq_len=10, providers=['CPUExecutionProvider', 'DmlExecutionProvider']):
        """Sequential profiling (from sequential_profiler.py logic)"""
        print("📊 Starting sequential profiling...")
        
        # Initial inputs for block_1
        current_inputs = self._create_initial_inputs(batch_size, seq_len)
        results = {
            "metadata": {
                "profiling_timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
                "onnxruntime_version": ort.__version__,
                "warmup_runs_per_session": 3,
                "benchmark_runs_per_session": 10,
                "providers_tested": providers,
                "debug_mode": self.debug
            },
            "profiles": {}
        }
        
        blocks = self._get_blocks_to_profile()  # All 33 blocks, not just 5
        
        for block_num, block_id in enumerate(blocks, 1):
            print(f"\n{'='*50}")
            print(f"📦 BLOCK {block_num}: {block_id}")
            print(f"{'='*50}")
            
            block_results = {}
            outputs = None
            
            for provider in providers:
                provider_key = provider.replace('ExecutionProvider', '')  # CPU/Dml format
                print(f"\n🔄 Testing {provider_key}...")
                
                # Load session
                session, error = self._load_block_session(block_id, provider)
                if error:
                    print(f"❌ Failed to load: {error}")
                    block_results[provider_key] = {
                        "status": "failed",
                        "error": error
                    }
                    continue
                
                # Check inputs
                input_names = [inp.name for inp in session.get_inputs()]
                print(f"📥 Expected: {input_names}")
                print(f"📥 Available: {list(current_inputs.keys())}")
                
                # Handle missing inputs
                filtered_inputs = self._prepare_inputs(current_inputs, input_names, batch_size, seq_len)
                
                # Profile this block
                result, block_outputs = self._profile_block(session, filtered_inputs, block_id, provider_key)
                
                if result:
                    block_results[provider_key] = result
                    if outputs is None:
                        outputs = block_outputs
                        output_names = [out.name for out in session.get_outputs()]
                else:
                    block_results[provider_key] = {
                        "status": "failed",
                        "error": "Profiling failed"
                    }
            
            # Save results for this block
            results["profiles"][block_id] = block_results
            
            # Prepare for next block
            if outputs and block_num < len(blocks):
                try:
                    current_inputs = self._prepare_next_inputs(outputs, output_names, blocks[block_num], batch_size, seq_len)
                except Exception as e:
                    print(f"⚠️ Failed to prepare inputs for next block: {e}")
                    # Create fallback inputs
                    current_inputs = self._create_fallback_inputs(batch_size, seq_len)
            
        return results
    
    def _get_blocks_to_profile(self) -> List[str]:
        """Get blocks list from config"""
        return self.network_config.get('model_chain_order', [])
    
    def _get_block_model_path(self, block_id: str) -> Path:
        """Get path to block ONNX file with pattern matching"""
        onnx_dir = Path(self.network_config['paths']['onnx_blocks_dir'])
        base_path = self.project_root / onnx_dir
        
        # الگوهای مختلف نام‌گذاری فایل‌ها
        possible_patterns = [
            f"{block_id}.onnx",  # نام ساده
            f"{block_id}_skeleton.optimized.onnx",  # فایل بهینه‌سازی شده
            f"{block_id}_skeleton_with_zeros.onnx",  # فایل با zeros
            f"{block_id}_optimized.onnx",  # نام بهینه‌سازی شده
        ]
        
        # جستجو برای فایل‌ها
        for pattern in possible_patterns:
            candidate_path = base_path / pattern
            if candidate_path.exists() and candidate_path.is_file():
                if self.debug:
                    print(f"Found model for {block_id}: {pattern}")
                return candidate_path
        
        # اگر هیچ فایل پیدا نشد
        available_files = list(base_path.glob("*.onnx")) if base_path.exists() else []
        available_names = [f.name for f in available_files]
        raise FileNotFoundError(
            f"No model found for {block_id}. "
            f"Searched patterns: {possible_patterns}. "
            f"Available files: {available_names[:10]}{'...' if len(available_names) > 10 else ''}"
        )
    
    def _create_initial_inputs(self, batch_size=1, seq_len=10):
        """Create initial inputs for block_1"""
        return {
            'attention_mask': np.ones([batch_size, seq_len], dtype=np.int64),
            'input_ids': np.random.randint(1, 1000, [batch_size, seq_len], dtype=np.int64),
            'position_ids': np.tile(np.arange(seq_len, dtype=np.int64), (batch_size, 1)),
            'past_key_values.0.key': np.zeros([batch_size, 8, 0, 128], dtype=np.float16),
            'past_key_values.0.value': np.zeros([batch_size, 8, 0, 128], dtype=np.float16)
        }
    
    def _load_block_session(self, block_id: str, provider: str):
        """Load ONNX session for block"""
        try:
            model_path = self._get_block_model_path(block_id)
            session = ort.InferenceSession(str(model_path), providers=[provider])
            return session, None
        except Exception as e:
            return None, str(e)
    
    def _prepare_inputs(self, current_inputs: Dict, needed_inputs: List[str], batch_size: int, seq_len: int):
        """Prepare inputs for current block"""
        filtered = {}
        
        for needed in needed_inputs:
            if needed in current_inputs:
                filtered[needed] = current_inputs[needed]
            elif 'past_key_values' in needed:
                filtered[needed] = np.zeros([batch_size, 8, 0, 128], dtype=np.float16)
            elif 'ScatterND' in needed:
                filtered[needed] = np.random.rand(batch_size, 1, seq_len, seq_len).astype(np.float16) * 0.1
            elif 'Unsqueeze' in needed:
                filtered[needed] = np.random.randn(batch_size, 1, seq_len, 128).astype(np.float16) * 0.1
            else:
                print(f"⚠️ Unknown input: {needed}")
        
        return filtered
    
    def _profile_block(self, session, inputs, block_id, provider_key, iterations=10):
        """Profile single block"""
        try:
            # Warmup
            for _ in range(3):
                session.run(None, inputs)
            
            # Timing
            times = []
            for _ in range(iterations):
                start = time.perf_counter()
                outputs = session.run(None, inputs)
                end = time.perf_counter()
                times.append((end - start) * 1000)
            
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            std_time = np.std(times) if len(times) > 1 else 0.0
            
            print(f"  ✅ {provider_key}: {avg_time:.1f}ms (min: {min_time:.1f}, max: {max_time:.1f})")
            
            return {
                'status': 'success',
                'mean_ms': round(avg_time, 4),
                'std_ms': round(std_time, 4),
                'min_ms': round(min_time, 4),
                'max_ms': round(max_time, 4),
                'num_runs': len(times)
            }, outputs
            
        except Exception as e:
            print(f"  ❌ {provider_key}: {e}")
            return None, None
    
    def _prepare_next_inputs(self, outputs, output_names, next_block_id, batch_size, seq_len):
        """Prepare inputs for next block"""
        # This is simplified - you'd need the full mapping logic from sequential_profiler
        next_inputs = {}
        output_dict = {name: output for name, output in zip(output_names, outputs)}
        
        # Basic mapping - extend as needed
        for name, data in output_dict.items():
            next_inputs[name] = data
        
        return next_inputs
    
    def print_summary(self, results):
        """Print profiling summary"""
        print(f"\n{'='*60}")
        print(f"📊 PROFILING SUMMARY")
        print(f"{'='*60}")
        
        profiles = results.get("profiles", {})
        
        for block_name, providers in profiles.items():
            print(f"\n🔹 {block_name.upper()}:")
            for provider, metrics in providers.items():
                if metrics and metrics.get('status') == 'success':
                    print(f"   {provider:20}: {metrics['mean_ms']:6.1f}ms")
                else:
                    error = metrics.get('error', 'Unknown error') if metrics else 'No data'
                    print(f"   {provider:20}: ❌ FAILED - {error}")
        
        # Summary stats
        total_blocks = len(profiles)
        successful_runs = sum(1 for block_data in profiles.values() 
                            for provider_data in block_data.values() 
                            if provider_data and provider_data.get('status') == 'success')
        total_runs = sum(len(block_data) for block_data in profiles.values())
        
        print(f"\n📊 TOTAL: {successful_runs}/{total_runs} successful runs across {total_blocks} blocks")

    def _create_fallback_inputs(self, batch_size=1, seq_len=10):
        """Create fallback inputs when mapping fails"""
        return {
            'attention_mask': np.ones([batch_size, seq_len], dtype=np.int64),
            'input_ids': np.random.randint(1, 1000, [batch_size, seq_len], dtype=np.int64),
            'position_ids': np.tile(np.arange(seq_len, dtype=np.int64), (batch_size, 1)),
        }
    
    def save_results(self, results, filename="performance_profile.json"):
        """Save results to JSON file"""
        try:
            output_path = self.project_root / filename
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Results saved to: {output_path}")
        except Exception as e:
            print(f"❌ Failed to save results: {e}")

def main():
    parser = argparse.ArgumentParser(description="Hybrid ONNX Profiler")
    parser.add_argument('--network-config', type=Path, default='network_config.json')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--optimize-only', action='store_true', help='Only create optimized models')
    parser.add_argument('--profile-only', action='store_true', help='Only run sequential profiling')
    
    args = parser.parse_args()
    
    profiler = HybridProfiler(args.network_config, args.debug)
    
    if not args.profile_only:
        profiler.create_optimized_models()
    
    if not args.optimize_only:
        results = profiler.sequential_profile()
        profiler.save_results(results)
        profiler.print_summary(results)

if __name__ == "__main__":
    main()