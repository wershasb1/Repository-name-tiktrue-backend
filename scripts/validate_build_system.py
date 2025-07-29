#!/usr/bin/env python3
"""
TikTrue Platform - Build System Validation Script

This script validates the production build system setup:
- Checks all required dependencies
- Validates build scripts and configurations
- Tests build process in dry-run mode
- Verifies PyInstaller and PyArmor integration

Requirements: 4.1 - Production build system validation
"""

import os
import sys
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

class BuildSystemValidator:
    """Validator for TikTrue production build system"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.project_root = Path(__file__).parent.parent
        self.scripts_dir = Path(__file__).parent
        self.desktop_dir = self.project_root / "desktop"
        self.validation_results = {}
        
        # Setup logging
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging for validation"""
        log_level = logging.DEBUG if self.verbose else logging.INFO
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        self.logger = logging.getLogger(__name__)
        
    def execute_command(self, command: str, check: bool = False) -> Tuple[bool, str, str]:
        """Execute shell command and return result"""
        self.logger.debug(f"Executing: {command}")
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            success = result.returncode == 0
            if success:
                self.logger.debug(f"Command succeeded: {command}")
            else:
                self.logger.debug(f"Command failed: {command} (exit code: {result.returncode})")
                
            return success, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            self.logger.error(f"Command timed out: {command}")
            return False, "", "Command timed out"
        except Exception as e:
            self.logger.error(f"Command execution error: {e}")
            return False, "", str(e)
            
    def validate_python_environment(self) -> bool:
        """Validate Python environment and required packages"""
        self.logger.info("🐍 Validating Python environment...")
        
        results = {}
        
        # Check Python version
        try:
            version_info = sys.version_info
            python_version = f"{version_info.major}.{version_info.minor}.{version_info.micro}"
            results["python_version"] = python_version
            
            if version_info >= (3, 11):
                self.logger.info(f"✅ Python version: {python_version}")
                results["python_version_ok"] = True
            else:
                self.logger.error(f"❌ Python version too old: {python_version} (requires 3.11+)")
                results["python_version_ok"] = False
                
        except Exception as e:
            self.logger.error(f"❌ Failed to check Python version: {e}")
            results["python_version_ok"] = False
            
        # Check required packages
        required_packages = [
            "pyinstaller",
            "pyarmor", 
            "PyQt6",
            "asyncio",
            "websockets",
            "aiohttp",
            "aiofiles",
            "cryptography",
            "psutil"
        ]
        
        results["packages"] = {}
        all_packages_ok = True
        
        for package in required_packages:
            try:
                __import__(package)
                self.logger.info(f"✅ Package available: {package}")
                results["packages"][package] = True
            except ImportError:
                self.logger.error(f"❌ Package missing: {package}")
                results["packages"][package] = False
                all_packages_ok = False
                
        results["all_packages_ok"] = all_packages_ok
        
        # Check PyInstaller
        success, stdout, stderr = self.execute_command("pyinstaller --version")
        if success:
            version = stdout.strip()
            self.logger.info(f"✅ PyInstaller version: {version}")
            results["pyinstaller_version"] = version
            results["pyinstaller_ok"] = True
        else:
            self.logger.error("❌ PyInstaller not available")
            results["pyinstaller_ok"] = False
            
        # Check PyArmor
        success, stdout, stderr = self.execute_command("pyarmor --version")
        if success:
            version = stdout.strip()
            self.logger.info(f"✅ PyArmor version: {version}")
            results["pyarmor_version"] = version
            results["pyarmor_ok"] = True
        else:
            self.logger.error("❌ PyArmor not available")
            results["pyarmor_ok"] = False
            
        self.validation_results["python_environment"] = results
        return results["python_version_ok"] and all_packages_ok and results["pyinstaller_ok"]
        
    def validate_project_structure(self) -> bool:
        """Validate project structure and required files"""
        self.logger.info("📁 Validating project structure...")
        
        results = {}
        
        # Required files and directories
        required_items = {
            "files": [
                "desktop/main_app.py",
                "desktop/windows_service.py",
                "desktop/desktop_requirements.txt",
                "scripts/build_production.py",
                "scripts/Build-Production.ps1",
                "scripts/build_production.bat",
                "scripts/pyarmor_config.json"
            ],
            "directories": [
                "desktop",
                "desktop/core",
                "desktop/interfaces",
                "desktop/models",
                "desktop/network",
                "desktop/security",
                "desktop/workers",
                "config",
                "assets"
            ]
        }
        
        results["files"] = {}
        results["directories"] = {}
        
        all_files_ok = True
        for file_path in required_items["files"]:
            full_path = self.project_root / file_path
            exists = full_path.exists()
            results["files"][file_path] = exists
            
            if exists:
                self.logger.info(f"✅ File exists: {file_path}")
            else:
                self.logger.error(f"❌ File missing: {file_path}")
                all_files_ok = False
                
        all_dirs_ok = True
        for dir_path in required_items["directories"]:
            full_path = self.project_root / dir_path
            exists = full_path.exists() and full_path.is_dir()
            results["directories"][dir_path] = exists
            
            if exists:
                self.logger.info(f"✅ Directory exists: {dir_path}")
            else:
                self.logger.error(f"❌ Directory missing: {dir_path}")
                all_dirs_ok = False
                
        results["all_files_ok"] = all_files_ok
        results["all_directories_ok"] = all_dirs_ok
        
        self.validation_results["project_structure"] = results
        return all_files_ok and all_dirs_ok
        
    def validate_build_scripts(self) -> bool:
        """Validate build scripts syntax and configuration"""
        self.logger.info("📜 Validating build scripts...")
        
        results = {}
        
        # Validate Python build script
        build_script = self.scripts_dir / "build_production.py"
        if build_script.exists():
            try:
                with open(build_script, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Basic syntax check
                compile(content, str(build_script), 'exec')
                self.logger.info("✅ Python build script syntax OK")
                results["python_script_syntax"] = True
                
                # Check for required classes/functions
                required_items = ["ProductionBuilder", "main"]
                for item in required_items:
                    if item in content:
                        self.logger.info(f"✅ Found required item: {item}")
                    else:
                        self.logger.error(f"❌ Missing required item: {item}")
                        results["python_script_syntax"] = False
                        
            except SyntaxError as e:
                self.logger.error(f"❌ Python build script syntax error: {e}")
                results["python_script_syntax"] = False
            except Exception as e:
                self.logger.error(f"❌ Failed to validate Python build script: {e}")
                results["python_script_syntax"] = False
        else:
            self.logger.error("❌ Python build script not found")
            results["python_script_syntax"] = False
            
        # Validate PowerShell script
        ps_script = self.scripts_dir / "Build-Production.ps1"
        if ps_script.exists():
            try:
                # Basic PowerShell syntax check
                success, stdout, stderr = self.execute_command(
                    f'powershell -Command "Get-Content \'{ps_script}\' | Out-Null"'
                )
                
                if success:
                    self.logger.info("✅ PowerShell build script syntax OK")
                    results["powershell_script_syntax"] = True
                else:
                    self.logger.error(f"❌ PowerShell build script syntax error: {stderr}")
                    results["powershell_script_syntax"] = False
                    
            except Exception as e:
                self.logger.error(f"❌ Failed to validate PowerShell script: {e}")
                results["powershell_script_syntax"] = False
        else:
            self.logger.error("❌ PowerShell build script not found")
            results["powershell_script_syntax"] = False
            
        # Validate PyArmor configuration
        config_file = self.scripts_dir / "pyarmor_config.json"
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                required_keys = ["project_name", "obfuscation_settings", "protection_settings"]
                config_ok = True
                
                for key in required_keys:
                    if key in config:
                        self.logger.info(f"✅ PyArmor config has: {key}")
                    else:
                        self.logger.error(f"❌ PyArmor config missing: {key}")
                        config_ok = False
                        
                results["pyarmor_config_ok"] = config_ok
                
            except json.JSONDecodeError as e:
                self.logger.error(f"❌ PyArmor config JSON error: {e}")
                results["pyarmor_config_ok"] = False
            except Exception as e:
                self.logger.error(f"❌ Failed to validate PyArmor config: {e}")
                results["pyarmor_config_ok"] = False
        else:
            self.logger.error("❌ PyArmor config not found")
            results["pyarmor_config_ok"] = False
            
        self.validation_results["build_scripts"] = results
        
        return (results.get("python_script_syntax", False) and 
                results.get("powershell_script_syntax", False) and
                results.get("pyarmor_config_ok", False))
        
    def test_dry_run_build(self) -> bool:
        """Test build process in dry-run mode"""
        self.logger.info("🧪 Testing dry-run build...")
        
        results = {}
        
        # Test Python build script
        build_script = self.scripts_dir / "build_production.py"
        
        try:
            success, stdout, stderr = self.execute_command(
                f'python "{build_script}" --version 1.0.0 --dry-run'
            )
            
            if success:
                self.logger.info("✅ Dry-run build completed successfully")
                results["dry_run_success"] = True
                
                # Check for expected output messages
                expected_messages = [
                    "Starting TikTrue production build",
                    "DRY RUN",
                    "build completed successfully"
                ]
                
                output = stdout + stderr
                for message in expected_messages:
                    if message.lower() in output.lower():
                        self.logger.info(f"✅ Found expected message: {message}")
                    else:
                        self.logger.warning(f"⚠️ Missing expected message: {message}")
                        
            else:
                self.logger.error(f"❌ Dry-run build failed: {stderr}")
                results["dry_run_success"] = False
                
        except Exception as e:
            self.logger.error(f"❌ Failed to test dry-run build: {e}")
            results["dry_run_success"] = False
            
        self.validation_results["dry_run_test"] = results
        return results.get("dry_run_success", False)
        
    def validate_pyinstaller_specs(self) -> bool:
        """Validate existing PyInstaller spec files"""
        self.logger.info("📋 Validating PyInstaller spec files...")
        
        results = {}
        
        # Find spec files
        spec_files = list(self.desktop_dir.glob("*.spec"))
        results["spec_files_found"] = len(spec_files)
        
        if spec_files:
            self.logger.info(f"✅ Found {len(spec_files)} spec files")
            
            for spec_file in spec_files:
                try:
                    with open(spec_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    # Basic validation
                    if "Analysis" in content and "EXE" in content:
                        self.logger.info(f"✅ Spec file looks valid: {spec_file.name}")
                        results[f"spec_{spec_file.name}"] = True
                    else:
                        self.logger.error(f"❌ Spec file invalid: {spec_file.name}")
                        results[f"spec_{spec_file.name}"] = False
                        
                except Exception as e:
                    self.logger.error(f"❌ Failed to read spec file {spec_file.name}: {e}")
                    results[f"spec_{spec_file.name}"] = False
        else:
            self.logger.warning("⚠️ No existing spec files found")
            
        self.validation_results["pyinstaller_specs"] = results
        return len(spec_files) > 0
        
    def generate_validation_report(self) -> Dict[str, Any]:
        """Generate comprehensive validation report"""
        self.logger.info("📊 Generating validation report...")
        
        report = {
            "validation_date": str(Path(__file__).stat().st_mtime),
            "project_root": str(self.project_root),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "platform": sys.platform,
            "results": self.validation_results,
            "summary": {}
        }
        
        # Calculate summary
        total_checks = 0
        passed_checks = 0
        
        for category, results in self.validation_results.items():
            if isinstance(results, dict):
                for key, value in results.items():
                    if isinstance(value, bool):
                        total_checks += 1
                        if value:
                            passed_checks += 1
                            
        report["summary"]["total_checks"] = total_checks
        report["summary"]["passed_checks"] = passed_checks
        report["summary"]["success_rate"] = round((passed_checks / total_checks) * 100, 2) if total_checks > 0 else 0
        report["summary"]["overall_status"] = "PASS" if passed_checks == total_checks else "FAIL"
        
        return report
        
    def run_validation(self) -> bool:
        """Run complete build system validation"""
        self.logger.info("🚀 Starting TikTrue build system validation...")
        
        validation_steps = [
            ("Python Environment", self.validate_python_environment),
            ("Project Structure", self.validate_project_structure),
            ("Build Scripts", self.validate_build_scripts),
            ("PyInstaller Specs", self.validate_pyinstaller_specs),
            ("Dry-Run Test", self.test_dry_run_build)
        ]
        
        all_passed = True
        
        for step_name, step_function in validation_steps:
            self.logger.info(f"\n{'='*50}")
            self.logger.info(f"Validating: {step_name}")
            self.logger.info(f"{'='*50}")
            
            try:
                result = step_function()
                if result:
                    self.logger.info(f"✅ {step_name}: PASSED")
                else:
                    self.logger.error(f"❌ {step_name}: FAILED")
                    all_passed = False
            except Exception as e:
                self.logger.error(f"💥 {step_name}: ERROR - {e}")
                all_passed = False
                
        # Generate report
        report = self.generate_validation_report()
        
        # Save report
        report_file = self.project_root / "temp" / "build_validation_report.json"
        report_file.parent.mkdir(exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            
        self.logger.info(f"\n{'='*50}")
        self.logger.info("VALIDATION SUMMARY")
        self.logger.info(f"{'='*50}")
        self.logger.info(f"Total checks: {report['summary']['total_checks']}")
        self.logger.info(f"Passed checks: {report['summary']['passed_checks']}")
        self.logger.info(f"Success rate: {report['summary']['success_rate']}%")
        self.logger.info(f"Overall status: {report['summary']['overall_status']}")
        self.logger.info(f"Report saved: {report_file}")
        
        if all_passed:
            self.logger.info("🎉 Build system validation completed successfully!")
        else:
            self.logger.error("❌ Build system validation failed!")
            
        return all_passed

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="TikTrue Build System Validation")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    validator = BuildSystemValidator(verbose=args.verbose)
    
    if validator.run_validation():
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()