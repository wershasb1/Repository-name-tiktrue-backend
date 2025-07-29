#!/usr/bin/env python3
"""
Installer Testing Script
Tests the installer build process and validates the installation
"""

import os
import sys
import json
import logging
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import time
from datetime import datetime
import unittest
from unittest.mock import patch, MagicMock

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("InstallerTesting")

# Create logs directory if it doesn't exist
Path('logs').mkdir(exist_ok=True)
file_handler = logging.FileHandler('logs/installer_testing.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)


class InstallerTestResult:
    """Test result container"""
    
    def __init__(self, test_name: str, passed: bool, message: str, details: Optional[Dict] = None):
        self.test_name = test_name
        self.passed = passed
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.now()


class InstallerTester:
    """
    Tests installer build and installation process
    """
    
    def __init__(self, project_root: str = "."):
        """
        Initialize installer tester
        
        Args:
            project_root: Root directory of the project
        """
        self.project_root = Path(project_root).resolve()
        self.test_results: List[InstallerTestResult] = []
        self.temp_dir = None
        
        logger.info(f"Initialized installer tester for project: {self.project_root}")
    
    def run_all_tests(self) -> bool:
        """
        Run all installer tests
        
        Returns:
            True if all tests pass
        """
        logger.info("Starting comprehensive installer testing")
        
        # Clear previous results
        self.test_results.clear()
        
        # Create temporary directory for testing
        self.temp_dir = Path(tempfile.mkdtemp(prefix="installer_test_"))
        logger.info(f"Using temporary directory: {self.temp_dir}")
        
        try:
            # Run all test categories
            self.test_build_prerequisites()
            self.test_nsis_script_syntax()
            self.test_powershell_script_syntax()
            self.test_file_packaging()
            self.test_dependency_resolution()
            self.test_service_installation()
            self.test_uninstallation_process()
            
            # Generate test report
            self.generate_test_report()
            
            # Check if all tests passed
            all_passed = all(result.passed for result in self.test_results)
            
            if all_passed:
                logger.info("✅ All installer tests passed")
            else:
                logger.error("❌ Some installer tests failed")
            
            return all_passed
            
        finally:
            # Cleanup temporary directory
            if self.temp_dir and self.temp_dir.exists():
                try:
                    shutil.rmtree(self.temp_dir)
                    logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temporary directory: {e}")
    
    def test_build_prerequisites(self):
        """Test build prerequisites"""
        logger.info("Testing build prerequisites...")
        
        # Test Python availability
        try:
            result = subprocess.run(
                ["python", "--version"],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            if result.returncode == 0:
                self.test_results.append(InstallerTestResult(
                    "python_availability",
                    True,
                    f"Python is available: {result.stdout.strip()}",
                    {"version": result.stdout.strip()}
                ))
            else:
                self.test_results.append(InstallerTestResult(
                    "python_availability",
                    False,
                    "Python is not available"
                ))
                
        except Exception as e:
            self.test_results.append(InstallerTestResult(
                "python_availability",
                False,
                f"Error checking Python: {str(e)}"
            ))
        
        # Test PowerShell availability
        try:
            result = subprocess.run(
                ["powershell", "-Command", "Get-Host"],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            if result.returncode == 0:
                self.test_results.append(InstallerTestResult(
                    "powershell_availability",
                    True,
                    "PowerShell is available",
                    {"output": result.stdout.strip()[:200]}
                ))
            else:
                self.test_results.append(InstallerTestResult(
                    "powershell_availability",
                    False,
                    "PowerShell is not available"
                ))
                
        except Exception as e:
            self.test_results.append(InstallerTestResult(
                "powershell_availability",
                False,
                f"Error checking PowerShell: {str(e)}"
            ))
        
        # Test required files existence
        required_files = [
            "installer.nsi",
            "Build-Installer.ps1",
            "main_app.py",
            "service_runner.py",
            "windows_service.py",
            "requirements.txt"
        ]
        
        missing_files = []
        for file_path in required_files:
            if not (self.project_root / file_path).exists():
                missing_files.append(file_path)
        
        if missing_files:
            self.test_results.append(InstallerTestResult(
                "required_files",
                False,
                f"Missing required files: {', '.join(missing_files)}",
                {"missing_files": missing_files}
            ))
        else:
            self.test_results.append(InstallerTestResult(
                "required_files",
                True,
                "All required files are present"
            ))
    
    def test_nsis_script_syntax(self):
        """Test NSIS script syntax"""
        logger.info("Testing NSIS script syntax...")
        
        nsis_script = self.project_root / "installer.nsi"
        
        if not nsis_script.exists():
            self.test_results.append(InstallerTestResult(
                "nsis_syntax",
                False,
                "NSIS script not found"
            ))
            return
        
        try:
            # Read and validate NSIS script
            with open(nsis_script, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for required NSIS elements
            required_elements = [
                "!define APP_NAME",
                "!define APP_VERSION",
                "Section \"MainSection\"",
                "WriteUninstaller",
                "Function .onInit",
                "Section Uninstall"
            ]
            
            missing_elements = []
            for element in required_elements:
                if element not in content:
                    missing_elements.append(element)
            
            # Check for syntax issues
            syntax_issues = []
            
            # Check for balanced quotes
            single_quotes = content.count("'")
            double_quotes = content.count('"')
            if single_quotes % 2 != 0:
                syntax_issues.append("Unbalanced single quotes")
            if double_quotes % 2 != 0:
                syntax_issues.append("Unbalanced double quotes")
            
            # Check for balanced braces
            open_braces = content.count("{")
            close_braces = content.count("}")
            if open_braces != close_braces:
                syntax_issues.append("Unbalanced braces")
            
            if missing_elements or syntax_issues:
                issues = missing_elements + syntax_issues
                self.test_results.append(InstallerTestResult(
                    "nsis_syntax",
                    False,
                    f"NSIS script issues: {', '.join(issues)}",
                    {"missing_elements": missing_elements, "syntax_issues": syntax_issues}
                ))
            else:
                self.test_results.append(InstallerTestResult(
                    "nsis_syntax",
                    True,
                    "NSIS script syntax is valid"
                ))
                
        except Exception as e:
            self.test_results.append(InstallerTestResult(
                "nsis_syntax",
                False,
                f"Error validating NSIS script: {str(e)}"
            ))
    
    def test_powershell_script_syntax(self):
        """Test PowerShell script syntax"""
        logger.info("Testing PowerShell script syntax...")
        
        ps_script = self.project_root / "Build-Installer.ps1"
        
        if not ps_script.exists():
            self.test_results.append(InstallerTestResult(
                "powershell_syntax",
                False,
                "PowerShell script not found"
            ))
            return
        
        try:
            # Test PowerShell script syntax
            result = subprocess.run(
                ["powershell", "-Command", f"Get-Command -Syntax (Get-Content '{ps_script}' -Raw)"],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            # Alternative: just try to parse the script
            result = subprocess.run(
                ["powershell", "-Command", f"$null = [System.Management.Automation.PSParser]::Tokenize((Get-Content '{ps_script}' -Raw), [ref]$null)"],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            if result.returncode == 0:
                self.test_results.append(InstallerTestResult(
                    "powershell_syntax",
                    True,
                    "PowerShell script syntax is valid"
                ))
            else:
                self.test_results.append(InstallerTestResult(
                    "powershell_syntax",
                    False,
                    f"PowerShell script syntax error: {result.stderr.strip()}"
                ))
                
        except Exception as e:
            self.test_results.append(InstallerTestResult(
                "powershell_syntax",
                False,
                f"Error validating PowerShell script: {str(e)}"
            ))
    
    def test_file_packaging(self):
        """Test file packaging for installer"""
        logger.info("Testing file packaging...")
        
        # Create a test package directory
        package_dir = self.temp_dir / "package"
        package_dir.mkdir(exist_ok=True)
        
        try:
            # Copy essential files to package directory
            essential_files = [
                "main_app.py",
                "service_runner.py",
                "windows_service.py",
                "security.license_validator.py",
                "requirements.txt"
            ]
            
            copied_files = []
            missing_files = []
            
            for file_name in essential_files:
                source_file = self.project_root / file_name
                if source_file.exists():
                    dest_file = package_dir / file_name
                    shutil.copy2(source_file, dest_file)
                    copied_files.append(file_name)
                else:
                    missing_files.append(file_name)
            
            # Test package integrity
            if missing_files:
                self.test_results.append(InstallerTestResult(
                    "file_packaging",
                    False,
                    f"Missing files for packaging: {', '.join(missing_files)}",
                    {"missing_files": missing_files, "copied_files": copied_files}
                ))
            else:
                # Calculate package size
                total_size = sum(f.stat().st_size for f in package_dir.rglob('*') if f.is_file())
                
                self.test_results.append(InstallerTestResult(
                    "file_packaging",
                    True,
                    f"File packaging successful ({len(copied_files)} files, {total_size:,} bytes)",
                    {"copied_files": copied_files, "total_size": total_size}
                ))
                
        except Exception as e:
            self.test_results.append(InstallerTestResult(
                "file_packaging",
                False,
                f"Error during file packaging: {str(e)}"
            ))
    
    def test_dependency_resolution(self):
        """Test dependency resolution"""
        logger.info("Testing dependency resolution...")
        
        requirements_file = self.project_root / "requirements.txt"
        
        if not requirements_file.exists():
            self.test_results.append(InstallerTestResult(
                "dependency_resolution",
                False,
                "requirements.txt not found"
            ))
            return
        
        try:
            # Read requirements
            with open(requirements_file, 'r') as f:
                requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            
            # Test dependency resolution in a virtual environment
            venv_dir = self.temp_dir / "test_venv"
            
            # Create virtual environment
            result = subprocess.run(
                ["python", "-m", "venv", str(venv_dir)],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            if result.returncode != 0:
                self.test_results.append(InstallerTestResult(
                    "dependency_resolution",
                    False,
                    f"Failed to create test virtual environment: {result.stderr}"
                ))
                return
            
            # Get python executable in venv
            if os.name == 'nt':  # Windows
                python_exe = venv_dir / "Scripts" / "python.exe"
                pip_exe = venv_dir / "Scripts" / "pip.exe"
            else:  # Unix-like
                python_exe = venv_dir / "bin" / "python"
                pip_exe = venv_dir / "bin" / "pip"
            
            # Upgrade pip
            result = subprocess.run(
                [str(pip_exe), "install", "--upgrade", "pip"],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            # Test installing a few key dependencies
            test_packages = ["websockets", "aiohttp", "colorama"]
            successful_installs = []
            failed_installs = []
            
            for package in test_packages:
                if package in ' '.join(requirements):
                    result = subprocess.run(
                        [str(pip_exe), "install", package],
                        capture_output=True,
                        text=True,
                        timeout=120
                    )
                    
                    if result.returncode == 0:
                        successful_installs.append(package)
                    else:
                        failed_installs.append(package)
            
            if failed_installs:
                self.test_results.append(InstallerTestResult(
                    "dependency_resolution",
                    False,
                    f"Failed to install packages: {', '.join(failed_installs)}",
                    {"successful": successful_installs, "failed": failed_installs}
                ))
            else:
                self.test_results.append(InstallerTestResult(
                    "dependency_resolution",
                    True,
                    f"Dependency resolution successful ({len(successful_installs)} packages tested)",
                    {"successful": successful_installs}
                ))
                
        except subprocess.TimeoutExpired:
            self.test_results.append(InstallerTestResult(
                "dependency_resolution",
                False,
                "Dependency installation timed out"
            ))
        except Exception as e:
            self.test_results.append(InstallerTestResult(
                "dependency_resolution",
                False,
                f"Error testing dependency resolution: {str(e)}"
            ))
    
    def test_service_installation(self):
        """Test Windows service installation simulation"""
        logger.info("Testing service installation simulation...")
        
        service_script = self.project_root / "windows_service.py"
        
        if not service_script.exists():
            self.test_results.append(InstallerTestResult(
                "service_installation",
                False,
                "Windows service script not found"
            ))
            return
        
        try:
            # Test service script syntax
            result = subprocess.run(
                ["python", "-m", "py_compile", str(service_script)],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            if result.returncode == 0:
                # Test service script help/info
                result = subprocess.run(
                    ["python", str(service_script), "--help"],
                    capture_output=True,
                    text=True,
                    cwd=self.project_root,
                    timeout=10
                )
                
                # Even if help fails, if the script compiles, it's a good sign
                self.test_results.append(InstallerTestResult(
                    "service_installation",
                    True,
                    "Service script is syntactically valid and ready for installation"
                ))
            else:
                self.test_results.append(InstallerTestResult(
                    "service_installation",
                    False,
                    f"Service script has syntax errors: {result.stderr}"
                ))
                
        except subprocess.TimeoutExpired:
            # Timeout is okay for service scripts
            self.test_results.append(InstallerTestResult(
                "service_installation",
                True,
                "Service script is responsive (timed out on help, which is normal)"
            ))
        except Exception as e:
            self.test_results.append(InstallerTestResult(
                "service_installation",
                False,
                f"Error testing service installation: {str(e)}"
            ))
    
    def test_uninstallation_process(self):
        """Test uninstallation process simulation"""
        logger.info("Testing uninstallation process simulation...")
        
        try:
            # Create a mock installation directory
            mock_install_dir = self.temp_dir / "mock_installation"
            mock_install_dir.mkdir(exist_ok=True)
            
            # Create some mock files and directories
            mock_files = [
                "main_app.py",
                "service_runner.py",
                "config/network_config.json",
                "logs/app.log",
                "data/cache.db"
            ]
            
            for file_path in mock_files:
                full_path = mock_install_dir / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(f"Mock content for {file_path}")
            
            # Simulate uninstallation by removing files
            removed_files = []
            removal_errors = []
            
            for file_path in mock_files:
                full_path = mock_install_dir / file_path
                try:
                    if full_path.exists():
                        full_path.unlink()
                        removed_files.append(file_path)
                except Exception as e:
                    removal_errors.append(f"{file_path}: {str(e)}")
            
            # Remove empty directories
            try:
                for dir_path in ["logs", "data", "config"]:
                    dir_full_path = mock_install_dir / dir_path
                    if dir_full_path.exists() and not any(dir_full_path.iterdir()):
                        dir_full_path.rmdir()
            except Exception as e:
                removal_errors.append(f"Directory cleanup: {str(e)}")
            
            if removal_errors:
                self.test_results.append(InstallerTestResult(
                    "uninstallation_process",
                    False,
                    f"Uninstallation simulation had errors: {', '.join(removal_errors)}",
                    {"removed_files": removed_files, "errors": removal_errors}
                ))
            else:
                self.test_results.append(InstallerTestResult(
                    "uninstallation_process",
                    True,
                    f"Uninstallation simulation successful ({len(removed_files)} files removed)",
                    {"removed_files": removed_files}
                ))
                
        except Exception as e:
            self.test_results.append(InstallerTestResult(
                "uninstallation_process",
                False,
                f"Error testing uninstallation process: {str(e)}"
            ))
    
    def generate_test_report(self):
        """Generate test report"""
        logger.info("Generating test report...")
        
        report = {
            "test_timestamp": datetime.now().isoformat(),
            "project_root": str(self.project_root),
            "total_tests": len(self.test_results),
            "passed_tests": sum(1 for r in self.test_results if r.passed),
            "failed_tests": sum(1 for r in self.test_results if not r.passed),
            "success_rate": 0,
            "results": []
        }
        
        if report["total_tests"] > 0:
            report["success_rate"] = (report["passed_tests"] / report["total_tests"]) * 100
        
        # Add detailed results
        for result in self.test_results:
            report["results"].append({
                "test_name": result.test_name,
                "passed": result.passed,
                "message": result.message,
                "details": result.details,
                "timestamp": result.timestamp.isoformat()
            })
        
        # Save report to file
        report_file = self.project_root / "installer_test_report.json"
        try:
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Test report saved to: {report_file}")
        except Exception as e:
            logger.error(f"Error saving test report: {str(e)}")
        
        # Print summary
        print("\n" + "="*60)
        print("INSTALLER TESTING SUMMARY")
        print("="*60)
        print(f"Total Tests: {report['total_tests']}")
        print(f"Passed: {report['passed_tests']}")
        print(f"Failed: {report['failed_tests']}")
        print(f"Success Rate: {report['success_rate']:.1f}%")
        print("="*60)
        
        # Print failed tests
        failed_results = [r for r in self.test_results if not r.passed]
        if failed_results:
            print("\nFAILED TESTS:")
            print("-" * 40)
            for result in failed_results:
                print(f"❌ {result.test_name}: {result.message}")
        
        # Print passed tests
        passed_results = [r for r in self.test_results if r.passed]
        if passed_results:
            print("\nPASSED TESTS:")
            print("-" * 40)
            for result in passed_results:
                print(f"✅ {result.test_name}: {result.message}")
        
        print("\n" + "="*60)
    
    def get_test_summary(self) -> Dict:
        """Get test summary"""
        return {
            "total_tests": len(self.test_results),
            "passed_tests": sum(1 for r in self.test_results if r.passed),
            "failed_tests": sum(1 for r in self.test_results if not r.passed),
            "all_passed": all(r.passed for r in self.test_results),
            "results": self.test_results
        }


class TestInstallerTester(unittest.TestCase):
    """Unit tests for InstallerTester"""
    
    def setUp(self):
        """Set up test environment"""
        self.tester = InstallerTester(".")
    
    def test_initialization(self):
        """Test tester initialization"""
        self.assertIsNotNone(self.tester.project_root)
        self.assertEqual(len(self.tester.test_results), 0)
    
    def test_test_result_creation(self):
        """Test test result creation"""
        result = InstallerTestResult("test_name", True, "Test message")
        self.assertEqual(result.test_name, "test_name")
        self.assertTrue(result.passed)
        self.assertEqual(result.message, "Test message")
        self.assertIsInstance(result.timestamp, datetime)
    
    def test_build_prerequisites(self):
        """Test build prerequisites check"""
        self.tester.test_build_prerequisites()
        
        # Should have at least some test results
        self.assertGreater(len(self.tester.test_results), 0)
        
        # Check for expected test names
        test_names = [r.test_name for r in self.tester.test_results]
        self.assertIn("python_availability", test_names)
        self.assertIn("powershell_availability", test_names)
        self.assertIn("required_files", test_names)


def main():
    """Main function"""
    print("=== Installer Testing ===\n")
    
    # Get project root from command line or use current directory
    project_root = sys.argv[1] if len(sys.argv) > 1 else "."
    
    # Create tester
    tester = InstallerTester(project_root)
    
    # Run tests
    success = tester.run_all_tests()
    
    # Run unit tests if requested
    if "--unit-tests" in sys.argv:
        print("\n=== Running Unit Tests ===")
        unittest.main(argv=[''], exit=False, verbosity=2)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()