'''
# استفاده عادی
python chatbot_interface.py --tokenizer-path ./llama3_1_tokenizer

# با تنظیمات سفارشی
python chatbot_interface.py --tokenizer-path ./llama3_1_tokenizer --first-node-port 8701 --max-new-tokens 3 --bot-name "AI Assistant"

'''

import asyncio
import json
import numpy as np
import argparse
import logging
import sys
from pathlib import Path
import time
import websockets
from typing import Dict, Any, Optional, List
import colorama

try:
    from transformers import AutoTokenizer
except ImportError:
    logging.error("transformers not found. Install with: pip install transformers")
    sys.exit(1)

# Initialize colorama for colored terminal output
colorama.init(autoreset=True)

# --- Path Setup ---
# Use ConfigManager for proper path management
try:
    from core.config_manager import get_config_manager
    config_manager = get_config_manager()
except ImportError:
    # Fallback for standalone usage
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# --- Serialization Fallback ---
# Using the proven serialization logic from your original client.
try:
    from utils.serialization_utils import tensor_to_json_serializable, json_serializable_to_tensor
except ImportError:
    logging.warning("serialization_utils.py not found. Using local fallback for tensor serialization.")
    import base64
    
    def tensor_to_json_serializable(tensor: np.ndarray) -> dict:
        """تبدیل tensor به فرمت JSON قابل ارسال"""
        return {
            "_tensor_": True,
            "dtype": str(tensor.dtype),
            "shape": list(tensor.shape),
            "data_b64": base64.b64encode(tensor.tobytes()).decode("utf-8")
        }
    
    def json_serializable_to_tensor(data: dict) -> np.ndarray:
        """تبدیل JSON به tensor"""
        if not isinstance(data, dict) or not data.get("_tensor_"):
            return data
        dt, sh, b = np.dtype(data["dtype"]), tuple(data["shape"]), base64.b64decode(data["data_b64"])
        return np.frombuffer(b, dtype=dt).reshape(sh)

# --- Main Chatbot Class ---

class ChatbotInterface:
    """رابط چت‌بات برای ارتباط با سرور inference توزیعی"""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.tokenizer = self._load_tokenizer()
        self.chat_history: List[Dict[str, str]] = []
        self.server_uri = f"ws://{args.first_node_host}:{args.first_node_port}"
        
        # تنظیمات اضافی
        self.max_retries = 3
        self.retry_delay = 1.0
        
    
        
        print(f"{colorama.Fore.CYAN}🤖 Chatbot initialized successfully!{colorama.Style.RESET_ALL}")
        print(f"{colorama.Fore.YELLOW}📡 Server: {self.server_uri}{colorama.Style.RESET_ALL}")

    def _load_tokenizer(self):
        """بارگذاری tokenizer"""
        print(f"{colorama.Style.BRIGHT}📥 Loading tokenizer from {self.args.tokenizer_path}...{colorama.Style.RESET_ALL}")
        try:
            tokenizer = AutoTokenizer.from_pretrained(self.args.tokenizer_path)
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            print(f"{colorama.Fore.GREEN}{colorama.Style.BRIGHT}✅ Tokenizer loaded successfully.{colorama.Style.RESET_ALL}")
            return tokenizer
        except Exception as e:
            print(f"{colorama.Fore.RED}{colorama.Style.BRIGHT}❌ Fatal: Could not load tokenizer. Error: {e}{colorama.Style.RESET_ALL}")
            sys.exit(1)

    def _format_prompt_with_history(self, user_prompt: str) -> str:
        """آماده‌سازی prompt با تاریخچه مکالمه"""
        if not self.chat_history:
            return f"user: {user_prompt}\nassistant:"
        
        history_str = ""
        for turn in self.chat_history:
            history_str += f"user: {turn['user']}\nassistant: {turn['assistant']}\n"
        
        return history_str + f"user: {user_prompt}\nassistant:"

    def _create_position_ids(self, input_ids: np.ndarray, past_length: int = 0) -> np.ndarray:
        """ایجاد position_ids برای مدل"""
        seq_length = input_ids.shape[1]
        position_ids = np.arange(past_length, past_length + seq_length, dtype=np.int64)
        return position_ids.reshape(1, seq_length)

    
    async def _send_request_with_retry(self, payload: dict) -> Optional[dict]:
        """ارسال درخواست با قابلیت تلاش مجدد"""
        for attempt in range(self.max_retries):
            try:
                async with websockets.connect(
                    self.server_uri, 
                    max_size=None, 
                    ping_interval=180,
                    ping_timeout=600,
                    close_timeout=1200
                ) as websocket:
                    # ارسال درخواست
                    await websocket.send(json.dumps(payload))
                    
                    # دریافت پاسخ
                    response_data = await asyncio.wait_for(websocket.recv(), timeout=1200.0)
                    response = json.loads(response_data)
                    
                    # تبدیل tensor های موجود در پاسخ
                    if response.get("status") == "success":
                        # تبدیل tensors در output_tensors
                        if "output_tensors" in response:
                            for name, tensor in response["output_tensors"].items():
                                response["output_tensors"][name] = json_serializable_to_tensor(tensor)
                        
                        # تبدیل tensors در outputs (جایی که logits نهایی قرار داره)
                        if "outputs" in response:
                            for name, tensor in response["outputs"].items():
                                if isinstance(tensor, dict) and tensor.get("_tensor_"):
                                    response["outputs"][name] = json_serializable_to_tensor(tensor)
                    
                    return response
                    
            except asyncio.TimeoutError:
                print(f"\n{colorama.Fore.RED}⏰ Timeout waiting for response from server (attempt {attempt + 1}/{self.max_retries}){colorama.Style.RESET_ALL}")
                
            except websockets.exceptions.ConnectionClosed as e:
                print(f"\n{colorama.Fore.RED}🔌 Connection closed (attempt {attempt + 1}/{self.max_retries}). Is the server running? Details: {e}{colorama.Style.RESET_ALL}")
                
            except Exception as e:
                print(f"\n{colorama.Fore.RED}❌ Communication error (attempt {attempt + 1}/{self.max_retries}): {e}{colorama.Style.RESET_ALL}")
            
            # تأخیر قبل از تلاش مجدد
            if attempt < self.max_retries - 1:
                print(f"{colorama.Fore.YELLOW}🔄 Retrying in {self.retry_delay} seconds...{colorama.Style.RESET_ALL}")
                await asyncio.sleep(self.retry_delay)
        
        print(f"{colorama.Fore.RED}💥 All retry attempts failed!{colorama.Style.RESET_ALL}")
        return None

    async def _handle_generation_loop(self, user_prompt: str):
        """حلقه اصلی تولید توکن به توکن با KV cache کامل"""
        
        # آماده‌سازی prompt کامل
        full_prompt = self._format_prompt_with_history(user_prompt)
        
        # توکن‌سازی
        inputs = self.tokenizer(
            full_prompt, 
            return_tensors="np", 
            padding=False, 
            truncation=True, 
            max_length=128
        )
        input_ids = inputs["input_ids"]
        
        # اطلاعات session
        session_id = f"chat_{int(time.time())}"
        generated_tokens = []
        
        print(f"{colorama.Fore.BLUE}{colorama.Style.BRIGHT}{self.args.bot_name}: {colorama.Style.RESET_ALL}", end="", flush=True)

        last_decoded_text = ""
        generation_start_time = time.time()

        # حلقه تولید
        for step in range(self.args.max_new_tokens):
            try:
                # آماده‌سازی ورودی‌ها بر اساس step
                if step == 0:
                    # اولین step: تمام prompt را ارسال می‌کنیم
                    current_input_ids = input_ids
                    current_attention_mask = np.ones_like(input_ids, dtype=np.int64)
                    current_position_ids = self._create_position_ids(input_ids)
                    
                    
                else:
                    # step های بعدی: فقط آخرین توکن تولید شده
                    last_token = generated_tokens[-1]
                    current_input_ids = np.array([[last_token]], dtype=np.int64)
                    
                    # attention_mask برای کل دنباله
                    if step == 0:
                        current_attention_mask = np.ones_like(input_ids, dtype=np.int64)
                    else:
                        # برای توکن‌های بعدی فقط یک توکن
                        current_attention_mask = np.ones((1, 1), dtype=np.int64)
                    
                    # position_ids برای توکن جدید
                    current_position = input_ids.shape[1] + len(generated_tokens) - 1
                    current_position_ids = np.array([[current_position]], dtype=np.int64)
                    
                  
                # ساخت payload با KV cache
                input_tensors = {
                "input_ids": tensor_to_json_serializable(current_input_ids),
                "attention_mask": tensor_to_json_serializable(current_attention_mask),
                "position_ids": tensor_to_json_serializable(current_position_ids)
                }               
             

                payload = {
                    "session_id": session_id,
                    "step": step,
                    "target_block_id": self.args.initial_target_block,
                    "input_tensors": input_tensors
                }

                # نمایش پیش‌نمایش payload برای debug
                if step == 0:
                    print(f"\n{colorama.Fore.YELLOW}🔧 Debug - First step payload keys: {list(input_tensors.keys())}{colorama.Style.RESET_ALL}")

                # ارسال درخواست
                response = await self._send_request_with_retry(payload)
                
                if not response or response.get("status") != "success":
                    error_msg = response.get('message', 'No response') if response else 'No response'
                    print(f"\n{colorama.Fore.RED}💥 Generation failed at step {step}: {error_msg}{colorama.Style.RESET_ALL}")
                    
                    # Debug: نمایش کل response
                    if response:
                        print(f"{colorama.Fore.YELLOW}🔧 Full response keys: {list(response.keys())}{colorama.Style.RESET_ALL}")
                        if 'outputs' in response:
                            print(f"{colorama.Fore.YELLOW}🔧 Response outputs: {response['outputs']}{colorama.Style.RESET_ALL}")
                        if 'output_tensors' in response:
                            print(f"{colorama.Fore.YELLOW}🔧 Response output_tensors: {list(response['output_tensors'].keys())}{colorama.Style.RESET_ALL}")
                        if 'successful_blocks' in response:
                            print(f"{colorama.Fore.YELLOW}🔧 Successful blocks: {response['successful_blocks']}{colorama.Style.RESET_ALL}")
                        if 'failed_blocks' in response:
                            print(f"{colorama.Fore.YELLOW}🔧 Failed blocks: {response['failed_blocks']}{colorama.Style.RESET_ALL}")
                    break
                
                # اگر pipeline موفق بوده ولی فقط block_1 اجرا شده
                successful_blocks = response.get('successful_blocks', [])
                if len(successful_blocks) == 1 and successful_blocks[0] == 'block_1':
                    print(f"\n{colorama.Fore.RED}🚨 PIPELINE INCOMPLETE: Only block_1 executed!{colorama.Style.RESET_ALL}")
                    print(f"  This means the pipeline stopped after the first block.")
                    print(f"  Check the server logs for errors in block_2 input preparation.")
                    print(f"  Common causes:")
                    print(f"    - Missing required inputs for block_2")
                    print(f"    - Incorrect tensor shapes from block_1")
                    print(f"    - Input mapping errors between blocks")
                    
                    # نمایش failed_blocks اگر وجود داره
                    failed_blocks = response.get('failed_blocks', [])
                    if failed_blocks:
                        print(f"  Failed blocks: {failed_blocks}")
                    
                    # نمایش execution_times برای تحلیل بیشتر
                    exec_times = response.get('execution_times', {})
                    if exec_times:
                        print(f"  Execution times: {exec_times}")
                    
                    break

                # استخراج logits - اول از outputs بعد از output_tensors
                outputs = response.get("outputs", {})
                logits = None
                
                # Debug: نمایش کل response structure (فقط در صورت خطا)
                if response.get("status") != "success" or len(response.get('successful_blocks', [])) != 33:
                    print(f"\n{colorama.Fore.CYAN}🔧 Response structure:{colorama.Style.RESET_ALL}")
                    print(f"  Status: {response.get('status')}")
                    print(f"  Keys: {list(response.keys())}")
                    print(f"  Successful blocks: {response.get('successful_blocks', [])}")
                    print(f"  Total successful blocks: {len(response.get('successful_blocks', []))}")
                
                # بررسی propagating_tensors (که احتمالاً logits توش هست)
                if 'propagating_tensors' in response:
                    prop_tensors = response['propagating_tensors']
                    print(f"  Propagating tensors keys: {list(prop_tensors.keys()) if isinstance(prop_tensors, dict) else type(prop_tensors)}")
                    
                    # جستجو برای logits در propagating_tensors
                    if isinstance(prop_tensors, dict):
                        for key, value in prop_tensors.items():
                            if 'logits' in key.lower() or (hasattr(value, 'shape') and len(value.shape) == 3 and value.shape[-1] > 30000):
                                print(f"  🎯 Potential logits found in propagating_tensors['{key}']: shape={getattr(value, 'shape', 'unknown')}")
                
                # ❗ چک کردن اینکه آیا block_33 اجرا شده یا نه
                successful_blocks = response.get('successful_blocks', [])
                if 'block_33' not in successful_blocks:
                    print(f"\n{colorama.Fore.RED}🚨 CRITICAL: Block 33 (logits generator) was NOT executed!{colorama.Style.RESET_ALL}")
                    print(f"  Only {len(successful_blocks)} blocks executed: {successful_blocks}")
                    print(f"  Expected: 33 blocks including block_33")
                    
                    # نمایش execution times برای دیدن آخرین بلاک اجرا شده
                    if 'execution_times' in response:
                        exec_times = response['execution_times']
                        last_block = max(exec_times.keys()) if exec_times else 'none'
                        print(f"  Last executed block: {last_block}")
                        print(f"  Total blocks in pipeline: {len(exec_times)}")
                
                if 'outputs' in response:
                    print(f"  Outputs type: {type(response['outputs'])}")
                    print(f"  Outputs content: {response['outputs']}")
                if 'output_tensors' in response:
                    print(f"  Output tensors keys: {list(response['output_tensors'].keys())}")
                
                # جستجوی جامع برای logits
                outputs = response.get("outputs", {})
                logits = None
                
                # روش 1: مستقیم از outputs
                if isinstance(outputs, dict) and "logits" in outputs:
                    logits = outputs["logits"]
                    print(f"\n{colorama.Fore.GREEN}✅ Found logits in 'outputs': {logits.shape}{colorama.Style.RESET_ALL}")
                
                # روش 2: از output_tensors
                elif "output_tensors" in response and "logits" in response["output_tensors"]:
                    logits = response["output_tensors"]["logits"]
                    print(f"\n{colorama.Fore.GREEN}✅ Found logits in 'output_tensors': {logits.shape}{colorama.Style.RESET_ALL}")
                
                # روش 3: از propagating_tensors
                elif "propagating_tensors" in response:
                    prop_tensors = response["propagating_tensors"]
                    if isinstance(prop_tensors, dict):
                        # جستجوی مستقیم
                        if "logits" in prop_tensors:
                            logits = prop_tensors["logits"]
                            # تبدیل tensor اگر لازم باشه
                            if isinstance(logits, dict) and logits.get("_tensor_"):
                                logits = json_serializable_to_tensor(logits)
                            print(f"\n{colorama.Fore.GREEN}✅ Found logits in 'propagating_tensors': {logits.shape}{colorama.Style.RESET_ALL}")
                        
                        # جستجوی هوشمند برای tensor با shape مناسب
                        else:
                            for key, value in prop_tensors.items():
                                # تبدیل tensor اگر لازم باشه
                                if isinstance(value, dict) and value.get("_tensor_"):
                                    value = json_serializable_to_tensor(value)
                                
                                if hasattr(value, 'shape') and len(value.shape) == 3 and value.shape[-1] > 30000:
                                    logits = value
                                    print(f"\n{colorama.Fore.GREEN}✅ Found logits in 'propagating_tensors[{key}]': {value.shape}{colorama.Style.RESET_ALL}")
                                    break
                
                # روش 4: جستجوی در همه جا
                else:
                    all_sources = {
                        **outputs,
                        **response.get("output_tensors", {}),
                        **response.get("propagating_tensors", {})
                    }
                    print(f"\n{colorama.Fore.YELLOW}🔧 Searching in all sources: {list(all_sources.keys())}{colorama.Style.RESET_ALL}")
                    
                    for key, value in all_sources.items():
                        # تبدیل tensor اگر لازم باشه
                        if isinstance(value, dict) and value.get("_tensor_"):
                            value = json_serializable_to_tensor(value)
                        
                        if hasattr(value, 'shape') and len(value.shape) == 3 and value.shape[-1] > 30000:
                            logits = value
                            print(f"\n{colorama.Fore.GREEN}✅ Found logits in '{key}': {value.shape}{colorama.Style.RESET_ALL}")
                            break
                
                if logits is None:
                    print(f"\n{colorama.Fore.RED}❌ Error: 'logits' not found in server response.{colorama.Style.RESET_ALL}")
                    break
                
                # انتخاب توکن بعدی (استراتژی greedy)
                next_token_id = np.argmax(logits[0, -1, :]).item()
                
                # بررسی پایان دنباله
                if next_token_id == self.tokenizer.eos_token_id:
                    print(f"\n{colorama.Fore.GREEN}🏁 Generation completed (EOS token reached){colorama.Style.RESET_ALL}")
                    break
                
                # اضافه کردن توکن جدید
                generated_tokens.append(next_token_id)
                
                # نمایش تدریجی متن
                current_full_text = self.tokenizer.decode(generated_tokens, skip_special_tokens=False)
                newly_decoded_text = current_full_text[len(last_decoded_text):]
                
                print(newly_decoded_text, end="", flush=True)
                last_decoded_text = current_full_text
                
            except Exception as e:
                print(f"\n{colorama.Fore.RED}💥 Error at step {step}: {e}{colorama.Style.RESET_ALL}")
                import traceback
                traceback.print_exc()
                break

        print()  # خط جدید
        
        # آمار تولید
        generation_time = time.time() - generation_start_time
        tokens_per_second = len(generated_tokens) / generation_time if generation_time > 0 else 0
        
        print(f"{colorama.Fore.CYAN}📊 Generated {len(generated_tokens)} tokens in {generation_time:.2f}s ({tokens_per_second:.1f} tokens/s){colorama.Style.RESET_ALL}")
        
        # ذخیره در تاریخچه
        if generated_tokens:
            full_response_text = self.tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()
            self.chat_history.append({"user": user_prompt, "assistant": full_response_text})

    def _show_help(self):
        """نمایش راهنما"""
        print(f"\n{colorama.Style.BRIGHT}📚 Available Commands:{colorama.Style.RESET_ALL}")
        print(f"{colorama.Fore.GREEN}  clear{colorama.Style.RESET_ALL}     - Clear conversation history")
        print(f"{colorama.Fore.GREEN}  history{colorama.Style.RESET_ALL}   - Show conversation history")
        print(f"{colorama.Fore.GREEN}  stats{colorama.Style.RESET_ALL}     - Show session statistics")
        print(f"{colorama.Fore.GREEN}  help{colorama.Style.RESET_ALL}      - Show this help")
        print(f"{colorama.Fore.GREEN}  exit/quit{colorama.Style.RESET_ALL} - End session")
        print()

    def _show_history(self):
        """نمایش تاریخچه مکالمه"""
        if not self.chat_history:
            print(f"{colorama.Fore.YELLOW}📝 No conversation history yet.{colorama.Style.RESET_ALL}")
            return
        
        print(f"\n{colorama.Style.BRIGHT}📚 Conversation History:{colorama.Style.RESET_ALL}")
        print("=" * 60)
        
        for i, turn in enumerate(self.chat_history, 1):
            print(f"{colorama.Fore.GREEN}[{i}] You:{colorama.Style.RESET_ALL} {turn['user']}")
            print(f"{colorama.Fore.BLUE}[{i}] {self.args.bot_name}:{colorama.Style.RESET_ALL} {turn['assistant']}")
            print("-" * 40)
        print()

    def _show_stats(self):
        """نمایش آمار session"""
        total_turns = len(self.chat_history)
        total_user_tokens = sum(len(self.tokenizer.encode(turn['user'])) for turn in self.chat_history)
        total_bot_tokens = sum(len(self.tokenizer.encode(turn['assistant'])) for turn in self.chat_history)
        
        print(f"\n{colorama.Style.BRIGHT}📊 Session Statistics:{colorama.Style.RESET_ALL}")
        print(f"  💬 Total turns: {total_turns}")
        print(f"  👤 User tokens: {total_user_tokens}")
        print(f"  🤖 Bot tokens: {total_bot_tokens}")
        print(f"  📡 Server: {self.server_uri}")
        print(f"  🎯 Max tokens per generation: {self.args.max_new_tokens}")
        print(f"  🧠 Model layers: {self.num_layers}")
        print()

    async def run(self):
        """حلقه اصلی تعامل با کاربر"""
        print("\n" + "=" * 60)
        print(f"{colorama.Style.BRIGHT}      🚀 Advanced Interactive Chat Client{colorama.Style.RESET_ALL}")
        print("=" * 60)
        print(f" {colorama.Fore.CYAN}💡 Type 'help' for available commands{colorama.Style.RESET_ALL}")
        print("=" * 60 + "\n")

        while True:
            try:
                prompt = input(f"{colorama.Fore.GREEN}{colorama.Style.BRIGHT}You: {colorama.Style.RESET_ALL}")
                
                if not prompt.strip():
                    continue
                    
                prompt_lower = prompt.lower().strip()
                
                # دستورات خاص
                if prompt_lower in ["exit", "quit"]:
                    break
                elif prompt_lower == "clear":
                    self.chat_history = []
                    print(f"\n{colorama.Fore.YELLOW}🧹 Conversation history cleared!{colorama.Style.RESET_ALL}\n")
                    continue
                elif prompt_lower == "history":
                    self._show_history()
                    continue
                elif prompt_lower == "stats":
                    self._show_stats()
                    continue
                elif prompt_lower == "help":
                    self._show_help()
                    continue
                
                # تولید پاسخ
                await self._handle_generation_loop(prompt)
                print()  # فاصله بین مکالمات

            except (EOFError, KeyboardInterrupt):
                print(f"\n{colorama.Fore.YELLOW}👋 Interrupted by user{colorama.Style.RESET_ALL}")
                break
            except Exception as e:
                print(f"\n{colorama.Fore.RED}💥 Unexpected error: {e}{colorama.Style.RESET_ALL}")
                continue
        
        print(f"\n{colorama.Style.BRIGHT}👋 Thank you for using the chatbot! Goodbye!{colorama.Style.RESET_ALL}")


def main():
    """تابع اصلی برنامه"""
    parser = argparse.ArgumentParser(
        description="🤖 Advanced Chatbot Interface for Distributed Inference",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python chatbot_interface.py --tokenizer-path ./llama3_1_tokenizer
  python chatbot_interface.py --tokenizer-path ./models/tokenizer --max-new-tokens 50
  python chatbot_interface.py --first-node-host 192.168.1.100 --first-node-port 8701
        """
    )
    
    parser.add_argument("--first-node-host", 
                       default="localhost", 
                       help="Hostname of the first inference node")
    
    parser.add_argument("--first-node-port", 
                       type=int, 
                       default=8702, 
                       help="Port of the first inference node")
    
    parser.add_argument("--initial-target-block", 
                       default="block_1", 
                       help="Initial target block ID for pipeline")
    
    parser.add_argument("--tokenizer-path", 
                       help="Path to the tokenizer directory (auto-detected if not provided)")
    
    parser.add_argument("--model", 
                       help="Model ID to use (e.g., llama3_1_8b_fp16, mistral_7b_int4)")
    
    parser.add_argument("--max-new-tokens", 
                       type=int, 
                       default=100, 
                       help="Maximum number of tokens to generate per response")
    
    parser.add_argument("--bot-name", 
                       default="AI Assistant", 
                       help="Display name for the chatbot")
    
    parser.add_argument("--list-models", 
                       action="store_true", 
                       help="List available models and exit")
    
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
    
    # تنظیم tokenizer path خودکار
    if not args.tokenizer_path:
        try:
            from core.config_manager import ConfigManager
            
            # اگر مدل مشخص شده، از آن استفاده کن
            if args.model:
                config_manager = ConfigManager(model_id=args.model)
            else:
                config_manager = ConfigManager()
            
            tokenizer_path = config_manager.get_tokenizer_path()
            if tokenizer_path:
                args.tokenizer_path = str(tokenizer_path)
                print(f"{colorama.Fore.GREEN}✅ Auto-detected tokenizer: {args.tokenizer_path}{colorama.Style.RESET_ALL}")
            else:
                print(f"{colorama.Fore.RED}❌ No tokenizer found. Please specify --tokenizer-path{colorama.Style.RESET_ALL}")
                sys.exit(1)
                
        except Exception as e:
            print(f"{colorama.Fore.RED}❌ Error auto-detecting tokenizer: {e}{colorama.Style.RESET_ALL}")
            if not args.tokenizer_path:
                print("Please specify --tokenizer-path manually")
                sys.exit(1)
    
    # نمایش تنظیمات
    print(f"{colorama.Style.BRIGHT}🔧 Configuration:{colorama.Style.RESET_ALL}")
    print(f"  📍 Server: {args.first_node_host}:{args.first_node_port}")
    print(f"  🎭 Tokenizer: {args.tokenizer_path}")
    print(f"  🎯 Max tokens: {args.max_new_tokens}")
    print(f"  🤖 Bot name: {args.bot_name}")
    if args.model:
        print(f"  🧠 Model: {args.model}")
    
    try:
        interface = ChatbotInterface(args)
        asyncio.run(interface.run())
    except KeyboardInterrupt:
        print(f"\n{colorama.Fore.YELLOW}👋 Goodbye!{colorama.Style.RESET_ALL}")
    except Exception as e:
        print(f"{colorama.Fore.RED}💥 Fatal error: {e}{colorama.Style.RESET_ALL}")
        sys.exit(1)


if __name__ == "__main__":
    main()