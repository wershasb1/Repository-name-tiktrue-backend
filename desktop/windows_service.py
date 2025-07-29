"""
Windows Service Wrapper for Distributed LLM Platform
Implements Windows service lifecycle management, configuration, and logging
"""

import os
import sys
import time
import json
import logging
import threading
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# Windows service imports
try:
    import win32serviceutil
    import win32service
    import win32event
    import win32api
    import servicemanager
    WINDOWS_SERVICE_AVAILABLE = True
except ImportError:
    WINDOWS_SERVICE_AVAILABLE = False
    # Create mock classes for non-Windows environments
    class win32serviceutil:
        class ServiceFramework:
            def __init__(self, args): pass
            def SvcStop(self): pass
            def SvcDoRun(self): pass
            def ReportServiceStatus(self, status): pass
        
        @staticmethod
        def HandleCommandLine(service_class): pass
    
    class win32service:
        SERVICE_STOPPED = 1
        SERVICE_START_PENDING = 2
        SERVICE_STOP_PENDING = 3
        SERVICE_RUNNING = 4
        SERVICE_CONTINUE_PENDING = 5
        SERVICE_PAUSE_PENDING = 6
        SERVICE_PAUSED = 7
    
    class win32event:
        @staticmethod
        def CreateEvent(a, b, c, d): return None
        @staticmethod
        def WaitForSingleObject(a, b): return 0
    
    class servicemanager:
        @staticmethod
        def LogMsg(a, b, c): pass

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WindowsService")

# Create logs directory if it doesn't exist
Path('logs').mkdir(exist_ok=True)
file_handler = logging.FileHandler('logs/windows_service.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)


class TikTrueLLMService(win32serviceutil.ServiceFramework):
    """
    Windows Service wrapper for TikTrue Distributed LLM Platform
    """
    
    # Service configuration
    _svc_name_ = "TikTrueLLMService"
    _svc_display_name_ = "TikTrue Distributed LLM Platform Service"
    _svc_description_ = "Distributed Large Language Model inference platform with license management"
    
    def __init__(self, args):
        """Initialize the Windows service"""
        win32serviceutil.ServiceFramework.__init__(self, args)
        
        # Create event for service stop signal
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        
        # Service state
        self.is_running = False
        self.service_thread = None
        
        # Configuration
        self.config_file = "service_config.json"
        self.service_config = self._load_service_config()
        
        # Process management
        self.main_process = None
        self.process_monitor_thread = None
        
        logger.info("TikTrue LLM Service initialized")
    
    def _load_service_config(self) -> Dict[str, Any]:
        """Load service configuration"""
        try:
            if Path(self.config_file).exists():
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                logger.info(f"Loaded service configuration from {self.config_file}")
                return config
            else:
                # Default configuration
                default_config = {
                    "service_name": self._svc_name_,
                    "display_name": self._svc_display_name_,
                    "description": self._svc_description_,
                    "auto_start": True,
                    "restart_on_failure": True,
                    "restart_delay_seconds": 30,
                    "max_restart_attempts": 5,
                    "main_script": "service_runner.py",
                    "python_executable": sys.executable,
                    "working_directory": os.getcwd(),
                    "environment_variables": {},
                    "log_level": "INFO",
                    "log_rotation": True,
                    "max_log_size_mb": 10,
                    "max_log_files": 5
                }
                
                # Save default configuration
                self._save_service_config(default_config)
                return default_config
                
        except Exception as e:
            logger.error(f"Failed to load service configuration: {e}")
            return {}
    
    def _save_service_config(self, config: Dict[str, Any]):
        """Save service configuration"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"Saved service configuration to {self.config_file}")
        except Exception as e:
            logger.error(f"Failed to save service configuration: {e}")
    
    def SvcStop(self):
        """Handle service stop request"""
        try:
            logger.info("Service stop requested")
            
            # Report that we're stopping
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            
            # Set stop event
            win32event.SetEvent(self.hWaitStop)
            
            # Stop the main service
            self.is_running = False
            
            # Terminate main process if running
            if self.main_process and self.main_process.poll() is None:
                logger.info("Terminating main process")
                self.main_process.terminate()
                
                # Wait for graceful shutdown
                try:
                    self.main_process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    logger.warning("Main process did not terminate gracefully, forcing kill")
                    self.main_process.kill()
            
            # Wait for service thread to finish
            if self.service_thread and self.service_thread.is_alive():
                self.service_thread.join(timeout=10)
            
            logger.info("Service stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping service: {e}")
    
    def SvcDoRun(self):
        """Main service execution"""
        try:
            logger.info("Starting TikTrue LLM Service")
            
            # Log service start to Windows Event Log
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, '')
            )
            
            # Report that we're running
            self.ReportServiceStatus(win32service.SERVICE_RUNNING)
            
            # Start the main service logic
            self.is_running = True
            self.service_thread = threading.Thread(target=self._run_service, daemon=True)
            self.service_thread.start()
            
            # Wait for stop signal
            win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
            
        except Exception as e:
            logger.error(f"Error in service main loop: {e}")
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_ERROR_TYPE,
                servicemanager.PYS_SERVICE_STOPPED,
                (self._svc_name_, str(e))
            )
    
    def _run_service(self):
        """Main service logic"""
        restart_attempts = 0
        max_attempts = self.service_config.get("max_restart_attempts", 5)
        restart_delay = self.service_config.get("restart_delay_seconds", 30)
        
        while self.is_running:
            try:
                logger.info("Starting main application process")
                
                # Start the main application
                success = self._start_main_process()
                
                if success:
                    restart_attempts = 0  # Reset counter on successful start
                    
                    # Monitor the process
                    self._monitor_main_process()
                    
                else:
                    restart_attempts += 1
                    logger.error(f"Failed to start main process (attempt {restart_attempts}/{max_attempts})")
                    
                    if restart_attempts >= max_attempts:
                        logger.error("Maximum restart attempts reached, stopping service")
                        self.is_running = False
                        break
                
                # Wait before restart if configured
                if self.is_running and self.service_config.get("restart_on_failure", True):
                    logger.info(f"Waiting {restart_delay} seconds before restart")
                    time.sleep(restart_delay)
                
            except Exception as e:
                logger.error(f"Error in service loop: {e}")
                restart_attempts += 1
                
                if restart_attempts >= max_attempts:
                    logger.error("Maximum restart attempts reached due to errors")
                    self.is_running = False
                    break
                
                time.sleep(restart_delay)
    
    def _start_main_process(self) -> bool:
        """Start the main application process"""
        try:
            # Get configuration
            python_exe = self.service_config.get("python_executable", sys.executable)
            main_script = self.service_config.get("main_script", "service_runner.py")
            working_dir = self.service_config.get("working_directory", os.getcwd())
            env_vars = self.service_config.get("environment_variables", {})
            
            # Check if main script exists
            script_path = Path(working_dir) / main_script
            if not script_path.exists():
                logger.error(f"Main script not found: {script_path}")
                return False
            
            # Prepare environment
            env = os.environ.copy()
            env.update(env_vars)
            
            # Start the process
            cmd = [python_exe, str(script_path)]
            
            self.main_process = subprocess.Popen(
                cmd,
                cwd=working_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW  # Run without console window
            )
            
            logger.info(f"Started main process with PID: {self.main_process.pid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start main process: {e}")
            return False
    
    def _monitor_main_process(self):
        """Monitor the main process"""
        try:
            while self.is_running and self.main_process:
                # Check if process is still running
                return_code = self.main_process.poll()
                
                if return_code is not None:
                    # Process has terminated
                    logger.warning(f"Main process terminated with return code: {return_code}")
                    
                    # Log stdout and stderr
                    try:
                        stdout, stderr = self.main_process.communicate(timeout=5)
                        if stdout:
                            logger.info(f"Process stdout: {stdout.decode('utf-8', errors='ignore')}")
                        if stderr:
                            logger.error(f"Process stderr: {stderr.decode('utf-8', errors='ignore')}")
                    except subprocess.TimeoutExpired:
                        pass
                    
                    break
                
                # Wait a bit before checking again
                time.sleep(5)
                
        except Exception as e:
            logger.error(f"Error monitoring main process: {e}")
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get current service status"""
        try:
            status = {
                "service_name": self._svc_name_,
                "display_name": self._svc_display_name_,
                "is_running": self.is_running,
                "main_process_running": self.main_process and self.main_process.poll() is None,
                "main_process_pid": self.main_process.pid if self.main_process else None,
                "configuration": self.service_config,
                "timestamp": datetime.now().isoformat()
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting service status: {e}")
            return {"error": str(e)}


class ServiceManager:
    """
    Service management utilities
    """
    
    @staticmethod
    def install_service():
        """Install the Windows service"""
        try:
            if not WINDOWS_SERVICE_AVAILABLE:
                logger.error("Windows service modules not available")
                return False
            
            logger.info("Installing TikTrue LLM Service")
            
            # Install the service
            win32serviceutil.InstallService(
                TikTrueLLMService._svc_reg_class_,
                TikTrueLLMService._svc_name_,
                TikTrueLLMService._svc_display_name_,
                description=TikTrueLLMService._svc_description_,
                startType=win32service.SERVICE_AUTO_START
            )
            
            logger.info("Service installed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to install service: {e}")
            return False
    
    @staticmethod
    def uninstall_service():
        """Uninstall the Windows service"""
        try:
            if not WINDOWS_SERVICE_AVAILABLE:
                logger.error("Windows service modules not available")
                return False
            
            logger.info("Uninstalling TikTrue LLM Service")
            
            # Stop the service first
            ServiceManager.stop_service()
            
            # Uninstall the service
            win32serviceutil.RemoveService(TikTrueLLMService._svc_name_)
            
            logger.info("Service uninstalled successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to uninstall service: {e}")
            return False
    
    @staticmethod
    def start_service():
        """Start the Windows service"""
        try:
            if not WINDOWS_SERVICE_AVAILABLE:
                logger.error("Windows service modules not available")
                return False
            
            logger.info("Starting TikTrue LLM Service")
            
            win32serviceutil.StartService(TikTrueLLMService._svc_name_)
            
            logger.info("Service start command sent")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start service: {e}")
            return False
    
    @staticmethod
    def stop_service():
        """Stop the Windows service"""
        try:
            if not WINDOWS_SERVICE_AVAILABLE:
                logger.error("Windows service modules not available")
                return False
            
            logger.info("Stopping TikTrue LLM Service")
            
            win32serviceutil.StopService(TikTrueLLMService._svc_name_)
            
            logger.info("Service stop command sent")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop service: {e}")
            return False
    
    @staticmethod
    def restart_service():
        """Restart the Windows service"""
        try:
            logger.info("Restarting TikTrue LLM Service")
            
            # Stop the service
            if ServiceManager.stop_service():
                # Wait a moment
                time.sleep(5)
                
                # Start the service
                return ServiceManager.start_service()
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to restart service: {e}")
            return False
    
    @staticmethod
    def get_service_status():
        """Get Windows service status"""
        try:
            if not WINDOWS_SERVICE_AVAILABLE:
                return {"status": "unavailable", "reason": "Windows service modules not available"}
            
            # Query service status
            status = win32serviceutil.QueryServiceStatus(TikTrueLLMService._svc_name_)
            
            status_map = {
                win32service.SERVICE_STOPPED: "stopped",
                win32service.SERVICE_START_PENDING: "starting",
                win32service.SERVICE_STOP_PENDING: "stopping",
                win32service.SERVICE_RUNNING: "running",
                win32service.SERVICE_CONTINUE_PENDING: "resuming",
                win32service.SERVICE_PAUSE_PENDING: "pausing",
                win32service.SERVICE_PAUSED: "paused"
            }
            
            return {
                "status": status_map.get(status[1], "unknown"),
                "service_type": status[0],
                "current_state": status[1],
                "controls_accepted": status[2],
                "win32_exit_code": status[3],
                "service_specific_exit_code": status[4],
                "check_point": status[5],
                "wait_hint": status[6]
            }
            
        except Exception as e:
            logger.error(f"Failed to get service status: {e}")
            return {"status": "error", "error": str(e)}


def main():
    """Main entry point for service management"""
    if len(sys.argv) == 1:
        # No arguments - show usage
        print("TikTrue Distributed LLM Platform - Windows Service")
        print("Usage:")
        print("  python windows_service.py install    - Install the service")
        print("  python windows_service.py remove     - Uninstall the service")
        print("  python windows_service.py start      - Start the service")
        print("  python windows_service.py stop       - Stop the service")
        print("  python windows_service.py restart    - Restart the service")
        print("  python windows_service.py status     - Show service status")
        print("  python windows_service.py debug      - Run in debug mode")
        return
    
    command = sys.argv[1].lower()
    
    if command == "install":
        success = ServiceManager.install_service()
        print("Service installed successfully" if success else "Failed to install service")
    
    elif command == "remove" or command == "uninstall":
        success = ServiceManager.uninstall_service()
        print("Service uninstalled successfully" if success else "Failed to uninstall service")
    
    elif command == "start":
        success = ServiceManager.start_service()
        print("Service started successfully" if success else "Failed to start service")
    
    elif command == "stop":
        success = ServiceManager.stop_service()
        print("Service stopped successfully" if success else "Failed to stop service")
    
    elif command == "restart":
        success = ServiceManager.restart_service()
        print("Service restarted successfully" if success else "Failed to restart service")
    
    elif command == "status":
        status = ServiceManager.get_service_status()
        print(f"Service Status: {json.dumps(status, indent=2)}")
    
    elif command == "debug":
        # Run service in debug mode (console)
        print("Running service in debug mode...")
        service = TikTrueLLMService([])
        try:
            service.is_running = True
            service._run_service()
        except KeyboardInterrupt:
            print("Service stopped by user")
            service.is_running = False
    
    else:
        # Let the service framework handle it
        if WINDOWS_SERVICE_AVAILABLE:
            win32serviceutil.HandleCommandLine(TikTrueLLMService)
        else:
            print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()