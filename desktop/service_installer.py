"""
Enhanced Windows Service Installation and Configuration Scripts
Provides comprehensive service management with dependency handling and validation

Requirements addressed:
- 13.2: Provide options to register application as Windows service
- 13.3: Configure automatic startup when installed as Windows service
"""

import os
import sys
import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import shutil

# Windows service imports
try:
    import win32service
    import win32serviceutil
    import win32api
    import win32con
    import winerror
    import pywintypes
    WINDOWS_SERVICE_AVAILABLE = True
except ImportError:
    WINDOWS_SERVICE_AVAILABLE = False

from windows_service import TikTrueLLMService, ServiceManager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ServiceInstaller")

# Create logs directory if it doesn't exist
Path('logs').mkdir(exist_ok=True)
file_handler = logging.FileHandler('logs/service_installer.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)


class ServiceInstallationError(Exception):
    """Custom exception for service installation errors"""
    pass


class ServiceDependencyManager:
    """Manages service dependencies and prerequisites"""
    
    def __init__(self):
        self.required_modules = [
            'win32service',
            'win32serviceutil', 
            'win32api',
            'win32con',
            'pywintypes'
        ]
        self.required_files = [
            'windows_service.py',
            'core/service_runner.py',
            'core/config_manager.py'
        ]
        self.python_requirements = [
            'pywin32>=306',
            'psutil>=5.9.6',
            'aiohttp>=3.9.1',
            'websockets>=11.0.3'
        ]
    
    def check_python_version(self) -> Tuple[bool, str]:
        """Check if Python version is compatible"""
        try:
            version = sys.version_info
            if version.major == 3 and version.minor >= 8:
                return True, f"Python {version.major}.{version.minor}.{version.micro}"
            else:
                return False, f"Python {version.major}.{version.minor}.{version.micro} (requires 3.8+)"
        except Exception as e:
            return False, f"Error checking Python version: {e}"
    
    def check_windows_modules(self) -> Tuple[bool, List[str]]:
        """Check if required Windows modules are available"""
        missing_modules = []
        
        for module in self.required_modules:
            try:
                __import__(module)
            except ImportError:
                missing_modules.append(module)
        
        return len(missing_modules) == 0, missing_modules
    
    def check_required_files(self) -> Tuple[bool, List[str]]:
        """Check if required files exist"""
        missing_files = []
        
        for file_path in self.required_files:
            if not Path(file_path).exists():
                missing_files.append(file_path)
        
        return len(missing_files) == 0, missing_files
    
    def install_python_requirements(self) -> bool:
        """Install required Python packages"""
        try:
            logger.info("Installing Python requirements...")
            
            for requirement in self.python_requirements:
                logger.info(f"Installing {requirement}...")
                result = subprocess.run([
                    sys.executable, '-m', 'pip', 'install', requirement
                ], capture_output=True, text=True, timeout=300)
                
                if result.returncode != 0:
                    logger.error(f"Failed to install {requirement}: {result.stderr}")
                    return False
                else:
                    logger.info(f"Successfully installed {requirement}")
            
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("Timeout installing Python requirements")
            return False
        except Exception as e:
            logger.error(f"Error installing Python requirements: {e}")
            return False
    
    def validate_dependencies(self) -> Dict[str, Any]:
        """Validate all dependencies"""
        validation_result = {
            "python_version": {"valid": False, "details": ""},
            "windows_modules": {"valid": False, "missing": []},
            "required_files": {"valid": False, "missing": []},
            "overall_valid": False
        }
        
        # Check Python version
        python_valid, python_details = self.check_python_version()
        validation_result["python_version"]["valid"] = python_valid
        validation_result["python_version"]["details"] = python_details
        
        # Check Windows modules
        modules_valid, missing_modules = self.check_windows_modules()
        validation_result["windows_modules"]["valid"] = modules_valid
        validation_result["windows_modules"]["missing"] = missing_modules
        
        # Check required files
        files_valid, missing_files = self.check_required_files()
        validation_result["required_files"]["valid"] = files_valid
        validation_result["required_files"]["missing"] = missing_files
        
        # Overall validation
        validation_result["overall_valid"] = (
            python_valid and modules_valid and files_valid
        )
        
        return validation_result


class ServiceConfigurationManager:
    """Manages service configuration and settings"""
    
    def __init__(self):
        self.config_file = "service_config.json"
        self.default_config = {
            "service_name": "TikTrueLLMService",
            "display_name": "TikTrue Distributed LLM Platform Service",
            "description": "Distributed Large Language Model inference platform with license management",
            "auto_start": True,
            "restart_on_failure": True,
            "restart_delay_seconds": 30,
            "max_restart_attempts": 5,
            "failure_actions": [
                {"action": "restart", "delay_ms": 30000},
                {"action": "restart", "delay_ms": 60000},
                {"action": "restart", "delay_ms": 120000},
                {"action": "none", "delay_ms": 0}
            ],
            "main_script": "core/service_runner.py",
            "python_executable": sys.executable,
            "working_directory": os.getcwd(),
            "environment_variables": {
                "PYTHONPATH": os.getcwd(),
                "TIKTRUE_SERVICE_MODE": "1"
            },
            "log_level": "INFO",
            "log_rotation": True,
            "max_log_size_mb": 10,
            "max_log_files": 5,
            "dependencies": [
                "Tcpip",
                "Dnscache"
            ],
            "privileges": {
                "run_as_system": True,
                "interact_with_desktop": False
            }
        }
    
    def load_config(self) -> Dict[str, Any]:
        """Load service configuration"""
        try:
            if Path(self.config_file).exists():
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                logger.info(f"Loaded service configuration from {self.config_file}")
                return config
            else:
                logger.info("Using default service configuration")
                return self.default_config.copy()
        except Exception as e:
            logger.error(f"Failed to load service configuration: {e}")
            return self.default_config.copy()
    
    def save_config(self, config: Dict[str, Any]) -> bool:
        """Save service configuration"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"Saved service configuration to {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save service configuration: {e}")
            return False
    
    def update_config(self, updates: Dict[str, Any]) -> bool:
        """Update service configuration with new values"""
        try:
            config = self.load_config()
            config.update(updates)
            return self.save_config(config)
        except Exception as e:
            logger.error(f"Failed to update service configuration: {e}")
            return False
    
    def validate_config(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate service configuration"""
        errors = []
        
        # Check required fields
        required_fields = [
            "service_name", "display_name", "description",
            "main_script", "python_executable", "working_directory"
        ]
        
        for field in required_fields:
            if field not in config or not config[field]:
                errors.append(f"Missing required field: {field}")
        
        # Check file paths
        if "main_script" in config:
            script_path = Path(config["working_directory"]) / config["main_script"]
            if not script_path.exists():
                errors.append(f"Main script not found: {script_path}")
        
        if "python_executable" in config:
            if not Path(config["python_executable"]).exists():
                errors.append(f"Python executable not found: {config['python_executable']}")
        
        # Check numeric values
        numeric_fields = {
            "restart_delay_seconds": (1, 3600),
            "max_restart_attempts": (1, 100),
            "max_log_size_mb": (1, 1000),
            "max_log_files": (1, 50)
        }
        
        for field, (min_val, max_val) in numeric_fields.items():
            if field in config:
                try:
                    value = int(config[field])
                    if not (min_val <= value <= max_val):
                        errors.append(f"{field} must be between {min_val} and {max_val}")
                except (ValueError, TypeError):
                    errors.append(f"{field} must be a valid integer")
        
        return len(errors) == 0, errors


class EnhancedServiceInstaller:
    """Enhanced service installer with comprehensive management"""
    
    def __init__(self):
        self.dependency_manager = ServiceDependencyManager()
        self.config_manager = ServiceConfigurationManager()
        self.service_name = "TikTrueLLMService"
        
    def pre_installation_check(self) -> Tuple[bool, Dict[str, Any]]:
        """Perform pre-installation validation"""
        logger.info("Performing pre-installation checks...")
        
        # Check if running as administrator
        try:
            is_admin = os.getuid() == 0
        except AttributeError:
            # Windows
            try:
                is_admin = win32api.GetUserName() in win32api.GetUserName()
                # Better check for Windows admin
                import ctypes
                is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
            except:
                is_admin = False
        
        # Validate dependencies
        dependency_result = self.dependency_manager.validate_dependencies()
        
        # Check if service already exists
        service_exists = self._check_service_exists()
        
        # Validate configuration
        config = self.config_manager.load_config()
        config_valid, config_errors = self.config_manager.validate_config(config)
        
        result = {
            "is_admin": is_admin,
            "dependencies": dependency_result,
            "service_exists": service_exists,
            "config_valid": config_valid,
            "config_errors": config_errors,
            "ready_for_installation": (
                is_admin and 
                dependency_result["overall_valid"] and 
                config_valid
            )
        }
        
        return result["ready_for_installation"], result
    
    def _check_service_exists(self) -> bool:
        """Check if service already exists"""
        if not WINDOWS_SERVICE_AVAILABLE:
            return False
        
        try:
            scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ENUMERATE_SERVICE)
            try:
                service = win32service.OpenService(scm, self.service_name, win32service.SERVICE_QUERY_STATUS)
                win32service.CloseServiceHandle(service)
                return True
            except pywintypes.error as e:
                if e.winerror == winerror.ERROR_SERVICE_DOES_NOT_EXIST:
                    return False
                raise
            finally:
                win32service.CloseServiceHandle(scm)
        except Exception as e:
            logger.error(f"Error checking service existence: {e}")
            return False
    
    def install_service(self, config_updates: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """Install the Windows service with enhanced configuration"""
        try:
            logger.info("Starting service installation...")
            
            # Update configuration if provided
            if config_updates:
                if not self.config_manager.update_config(config_updates):
                    return False, "Failed to update service configuration"
            
            # Load final configuration
            config = self.config_manager.load_config()
            
            # Perform pre-installation checks
            ready, check_result = self.pre_installation_check()
            if not ready:
                error_msg = "Pre-installation checks failed:\n"
                if not check_result["is_admin"]:
                    error_msg += "- Must run as administrator\n"
                if not check_result["dependencies"]["overall_valid"]:
                    error_msg += f"- Missing dependencies: {check_result['dependencies']}\n"
                if not check_result["config_valid"]:
                    error_msg += f"- Configuration errors: {check_result['config_errors']}\n"
                return False, error_msg
            
            # Remove existing service if it exists
            if check_result["service_exists"]:
                logger.info("Removing existing service...")
                self.uninstall_service()
                time.sleep(2)  # Wait for cleanup
            
            # Install the service
            logger.info("Installing Windows service...")
            
            if not WINDOWS_SERVICE_AVAILABLE:
                return False, "Windows service modules not available"
            
            # Use the existing ServiceManager to install
            success = ServiceManager.install_service()
            if not success:
                return False, "Service installation failed"
            
            # Configure service properties
            self._configure_service_properties(config)
            
            # Set up service recovery options
            self._configure_service_recovery(config)
            
            # Create service management scripts
            self._create_management_scripts()
            
            logger.info("Service installation completed successfully")
            return True, "Service installed successfully"
            
        except Exception as e:
            error_msg = f"Service installation failed: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def _configure_service_properties(self, config: Dict[str, Any]):
        """Configure service properties"""
        try:
            if not WINDOWS_SERVICE_AVAILABLE:
                return
            
            scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ALL_ACCESS)
            try:
                service = win32service.OpenService(
                    scm, 
                    config["service_name"], 
                    win32service.SERVICE_ALL_ACCESS
                )
                try:
                    # Configure service startup type
                    startup_type = win32service.SERVICE_AUTO_START if config.get("auto_start", True) else win32service.SERVICE_DEMAND_START
                    
                    win32service.ChangeServiceConfig(
                        service,
                        win32service.SERVICE_NO_CHANGE,  # service type
                        startup_type,  # start type
                        win32service.SERVICE_NO_CHANGE,  # error control
                        None,  # binary path
                        None,  # load order group
                        0,     # tag id
                        config.get("dependencies", []),  # dependencies
                        None,  # service start name
                        None,  # password
                        config.get("display_name", "TikTrue LLM Service")  # display name
                    )
                    
                    # Set service description
                    description = config.get("description", "")
                    if description:
                        win32service.ChangeServiceConfig2(
                            service,
                            win32service.SERVICE_CONFIG_DESCRIPTION,
                            description
                        )
                    
                    logger.info("Service properties configured successfully")
                    
                finally:
                    win32service.CloseServiceHandle(service)
            finally:
                win32service.CloseServiceHandle(scm)
                
        except Exception as e:
            logger.error(f"Failed to configure service properties: {e}")
    
    def _configure_service_recovery(self, config: Dict[str, Any]):
        """Configure service recovery options"""
        try:
            if not WINDOWS_SERVICE_AVAILABLE or not config.get("restart_on_failure", True):
                return
            
            scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ALL_ACCESS)
            try:
                service = win32service.OpenService(
                    scm, 
                    config["service_name"], 
                    win32service.SERVICE_ALL_ACCESS
                )
                try:
                    # Configure failure actions
                    failure_actions = []
                    for action_config in config.get("failure_actions", []):
                        action_type = {
                            "none": win32service.SC_ACTION_NONE,
                            "restart": win32service.SC_ACTION_RESTART,
                            "reboot": win32service.SC_ACTION_REBOOT,
                            "run_command": win32service.SC_ACTION_RUN_COMMAND
                        }.get(action_config.get("action", "none"), win32service.SC_ACTION_NONE)
                        
                        failure_actions.append((action_type, action_config.get("delay_ms", 0)))
                    
                    # Set failure actions
                    win32service.ChangeServiceConfig2(
                        service,
                        win32service.SERVICE_CONFIG_FAILURE_ACTIONS,
                        {
                            'ResetPeriod': 86400,  # Reset failure count after 24 hours
                            'RebootMsg': '',
                            'Command': '',
                            'Actions': failure_actions
                        }
                    )
                    
                    logger.info("Service recovery options configured successfully")
                    
                finally:
                    win32service.CloseServiceHandle(service)
            finally:
                win32service.CloseServiceHandle(scm)
                
        except Exception as e:
            logger.error(f"Failed to configure service recovery: {e}")
    
    def _create_management_scripts(self):
        """Create service management scripts"""
        try:
            scripts_dir = Path("scripts")
            scripts_dir.mkdir(exist_ok=True)
            
            # Create batch scripts for easy service management
            scripts = {
                "install_service.bat": [
                    "@echo off",
                    "echo Installing TikTrue LLM Service...",
                    f'"{sys.executable}" service_installer.py --install',
                    "pause"
                ],
                "uninstall_service.bat": [
                    "@echo off",
                    "echo Uninstalling TikTrue LLM Service...",
                    f'"{sys.executable}" service_installer.py --uninstall',
                    "pause"
                ],
                "start_service.bat": [
                    "@echo off",
                    "echo Starting TikTrue LLM Service...",
                    f'"{sys.executable}" windows_service.py start',
                    "pause"
                ],
                "stop_service.bat": [
                    "@echo off",
                    "echo Stopping TikTrue LLM Service...",
                    f'"{sys.executable}" windows_service.py stop',
                    "pause"
                ],
                "service_status.bat": [
                    "@echo off",
                    "echo TikTrue LLM Service Status:",
                    f'"{sys.executable}" windows_service.py status',
                    "pause"
                ]
            }
            
            for script_name, commands in scripts.items():
                script_path = scripts_dir / script_name
                with open(script_path, 'w') as f:
                    f.write('\n'.join(commands))
                logger.info(f"Created management script: {script_path}")
            
            # Create PowerShell script for advanced management
            powershell_script = scripts_dir / "manage_service.ps1"
            with open(powershell_script, 'w') as f:
                f.write('''# TikTrue LLM Service Management Script
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("install", "uninstall", "start", "stop", "restart", "status")]
    [string]$Action
)

$ServiceName = "TikTrueLLMService"
$PythonExe = "''' + sys.executable.replace('\\', '\\\\') + '''"

switch ($Action) {
    "install" {
        Write-Host "Installing TikTrue LLM Service..."
        & $PythonExe "service_installer.py" --install
    }
    "uninstall" {
        Write-Host "Uninstalling TikTrue LLM Service..."
        & $PythonExe "service_installer.py" --uninstall
    }
    "start" {
        Write-Host "Starting TikTrue LLM Service..."
        Start-Service -Name $ServiceName
    }
    "stop" {
        Write-Host "Stopping TikTrue LLM Service..."
        Stop-Service -Name $ServiceName
    }
    "restart" {
        Write-Host "Restarting TikTrue LLM Service..."
        Restart-Service -Name $ServiceName
    }
    "status" {
        Write-Host "TikTrue LLM Service Status:"
        Get-Service -Name $ServiceName | Format-Table -AutoSize
    }
}
''')
            
            logger.info("Service management scripts created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create management scripts: {e}")
    
    def uninstall_service(self) -> Tuple[bool, str]:
        """Uninstall the Windows service"""
        try:
            logger.info("Uninstalling Windows service...")
            
            # Use the existing ServiceManager to uninstall
            success = ServiceManager.uninstall_service()
            
            if success:
                logger.info("Service uninstalled successfully")
                return True, "Service uninstalled successfully"
            else:
                return False, "Service uninstallation failed"
                
        except Exception as e:
            error_msg = f"Service uninstallation failed: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_installation_status(self) -> Dict[str, Any]:
        """Get current installation status"""
        try:
            service_exists = self._check_service_exists()
            
            status = {
                "service_installed": service_exists,
                "service_status": "unknown",
                "configuration_valid": False,
                "dependencies_met": False,
                "last_check": datetime.now().isoformat()
            }
            
            if service_exists:
                # Get service status
                service_status = ServiceManager.get_service_status()
                status["service_status"] = service_status.get("status", "unknown")
            
            # Check configuration
            config = self.config_manager.load_config()
            config_valid, _ = self.config_manager.validate_config(config)
            status["configuration_valid"] = config_valid
            
            # Check dependencies
            dependency_result = self.dependency_manager.validate_dependencies()
            status["dependencies_met"] = dependency_result["overall_valid"]
            status["dependency_details"] = dependency_result
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting installation status: {e}")
            return {
                "error": str(e),
                "last_check": datetime.now().isoformat()
            }


def main():
    """Main entry point for service installer"""
    import argparse
    
    parser = argparse.ArgumentParser(description="TikTrue LLM Service Installer")
    parser.add_argument("--install", action="store_true", help="Install the service")
    parser.add_argument("--uninstall", action="store_true", help="Uninstall the service")
    parser.add_argument("--status", action="store_true", help="Show installation status")
    parser.add_argument("--check-deps", action="store_true", help="Check dependencies")
    parser.add_argument("--install-deps", action="store_true", help="Install dependencies")
    parser.add_argument("--config-file", help="Custom configuration file")
    parser.add_argument("--auto-start", type=bool, default=True, help="Enable automatic startup")
    
    args = parser.parse_args()
    
    installer = EnhancedServiceInstaller()
    
    if args.check_deps:
        print("Checking dependencies...")
        result = installer.dependency_manager.validate_dependencies()
        print(json.dumps(result, indent=2))
        return
    
    if args.install_deps:
        print("Installing dependencies...")
        success = installer.dependency_manager.install_python_requirements()
        print("Dependencies installed successfully" if success else "Failed to install dependencies")
        return
    
    if args.status:
        print("Getting installation status...")
        status = installer.get_installation_status()
        print(json.dumps(status, indent=2))
        return
    
    if args.install:
        print("Installing TikTrue LLM Service...")
        
        config_updates = {}
        if args.auto_start is not None:
            config_updates["auto_start"] = args.auto_start
        
        success, message = installer.install_service(config_updates)
        print(message)
        sys.exit(0 if success else 1)
    
    elif args.uninstall:
        print("Uninstalling TikTrue LLM Service...")
        success, message = installer.uninstall_service()
        print(message)
        sys.exit(0 if success else 1)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()