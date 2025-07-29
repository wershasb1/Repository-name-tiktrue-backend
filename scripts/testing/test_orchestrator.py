#!/usr/bin/env python3
"""
TikTrue Platform - Test Orchestrator

This script orchestrates all automated tests for the TikTrue platform:
- API integration tests for all endpoints
- End-to-end user journey tests
- Performance and load testing
- Security validation tests
- Test reporting and analytics

Requirements: 3.1, 4.1 - Automated testing orchestration
"""

import os
import sys
import json
import time
import logging
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

@dataclass
class TestSuite:
    """Test suite configuration"""
    name: str
    script_path: str
    description: str
    timeout: int = 300  # 5 minutes default
    required: bool = True
    parallel: bool = False
    dependencies: List[str] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []

@dataclass
class TestResult:
    """Test execution result"""
    suite_name: str
    status: str  # PASS, FAIL, SKIP, ERROR
    duration: float
    exit_code: int
    stdout: str
    stderr: str
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()

class TestOrchestrator:
    """Orchestrates all automated tests for TikTrue platform"""
    
    def __init__(self, config_file: Optional[str] = None, parallel: bool = False, 
                 timeout: int = 1800, verbose: bool = False):
        self.parallel = parallel
        self.timeout = timeout
        self.verbose = verbose
        self.project_root = Path(__file__).parent.parent.parent
        self.scripts_dir = Path(__file__).parent
        
        # Test configuration
        self.test_suites = self.load_test_configuration(config_file)
        
        # Test results
        self.test_results: List[TestResult] = []
        self.start_time = None
        self.end_time = None
        
        # Setup logging
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging for test orchestrator"""
        log_dir = self.project_root / "temp" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_level = logging.DEBUG if self.verbose else logging.INFO
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(log_dir / "test_orchestrator.log", encoding='utf-8')
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def load_test_configuration(self, config_file: Optional[str] = None) -> List[TestSuite]:
        """Load test suite configuration"""
        if config_file and Path(config_file).exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                suites = []
                for suite_config in config.get("test_suites", []):
                    suites.append(TestSuite(**suite_config))
                    
                return suites
            except Exception as e:
                self.logger.warning(f"Failed to load config file {config_file}: {e}")
                
        # Default test suite configuration
        return [
            TestSuite(
                name="API Integration Tests",
                script_path="api_integration_tests.py",
                description="Test all API endpoints for functionality and error handling",
                timeout=600,
                required=True,
                parallel=False
            ),
            TestSuite(
                name="E2E User Journey Tests",
                script_path="e2e_user_journey_tests.py", 
                description="Test complete user journeys from registration to model usage",
                timeout=900,
                required=True,
                parallel=False,
                dependencies=["API Integration Tests"]
            ),
            TestSuite(
                name="Security Validation Tests",
                script_path="validate_security_performance.py",
                description="Validate security measures and performance benchmarks",
                timeout=300,
                required=False,
                parallel=True
            ),
            TestSuite(
                name="Load Testing",
                script_path="load_tests.py",
                description="Test system performance under load",
                timeout=1200,
                required=False,
                parallel=True
            ),
            TestSuite(
                name="Database Tests",
                script_path="database_tests.py",
                description="Test database operations and integrity",
                timeout=300,
                required=True,
                parallel=True
            )
        ]
        
    def check_dependencies(self, suite: TestSuite) -> bool:
        """Check if test suite dependencies are satisfied"""
        if not suite.dependencies:
            return True
            
        for dep_name in suite.dependencies:
            # Find dependency result
            dep_result = next((r for r in self.test_results if r.suite_name == dep_name), None)
            
            if not dep_result:
                self.logger.warning(f"Dependency {dep_name} not found for {suite.name}")
                return False
                
            if dep_result.status != "PASS":
                self.logger.warning(f"Dependency {dep_name} failed for {suite.name}")
                return False
                
        return True
        
    def execute_test_suite(self, suite: TestSuite) -> TestResult:
        """Execute a single test suite"""
        self.logger.info(f"🚀 Starting test suite: {suite.name}")
        
        # Check dependencies
        if not self.check_dependencies(suite):
            self.logger.warning(f"⏭️ Skipping {suite.name} due to unmet dependencies")
            return TestResult(
                suite_name=suite.name,
                status="SKIP",
                duration=0,
                exit_code=-1,
                stdout="",
                stderr="Dependencies not met"
            )
            
        script_path = self.scripts_dir / suite.script_path
        
        if not script_path.exists():
            self.logger.error(f"❌ Test script not found: {script_path}")
            return TestResult(
                suite_name=suite.name,
                status="ERROR",
                duration=0,
                exit_code=-1,
                stdout="",
                stderr=f"Test script not found: {script_path}"
            )
            
        start_time = time.time()
        
        try:
            # Execute test script
            self.logger.info(f"⚡ Executing: python {script_path}")
            
            process = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=suite.timeout,
                cwd=self.project_root
            )
            
            duration = time.time() - start_time
            
            # Determine status based on exit code
            if process.returncode == 0:
                status = "PASS"
                self.logger.info(f"✅ {suite.name}: PASSED ({duration:.2f}s)")
            else:
                status = "FAIL"
                self.logger.error(f"❌ {suite.name}: FAILED ({duration:.2f}s)")
                
            return TestResult(
                suite_name=suite.name,
                status=status,
                duration=duration,
                exit_code=process.returncode,
                stdout=process.stdout,
                stderr=process.stderr
            )
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            self.logger.error(f"⏰ {suite.name}: TIMEOUT ({duration:.2f}s)")
            
            return TestResult(
                suite_name=suite.name,
                status="ERROR",
                duration=duration,
                exit_code=-1,
                stdout="",
                stderr=f"Test timed out after {suite.timeout} seconds"
            )
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"💥 {suite.name}: ERROR ({duration:.2f}s) - {e}")
            
            return TestResult(
                suite_name=suite.name,
                status="ERROR",
                duration=duration,
                exit_code=-1,
                stdout="",
                stderr=str(e)
            )
            
    def run_tests_sequential(self) -> bool:
        """Run all test suites sequentially"""
        self.logger.info("🔄 Running tests sequentially...")
        
        all_passed = True
        
        for suite in self.test_suites:
            result = self.execute_test_suite(suite)
            self.test_results.append(result)
            
            if result.status in ["FAIL", "ERROR"] and suite.required:
                all_passed = False
                self.logger.error(f"❌ Required test suite failed: {suite.name}")
                
                # Stop execution if critical test fails
                if suite.required:
                    self.logger.error("🛑 Stopping execution due to critical test failure")
                    break
                    
        return all_passed
        
    def run_tests_parallel(self) -> bool:
        """Run test suites in parallel where possible"""
        self.logger.info("⚡ Running tests in parallel...")
        
        # Separate parallel and sequential tests
        parallel_suites = [s for s in self.test_suites if s.parallel]
        sequential_suites = [s for s in self.test_suites if not s.parallel]
        
        all_passed = True
        
        # Run sequential tests first
        for suite in sequential_suites:
            result = self.execute_test_suite(suite)
            self.test_results.append(result)
            
            if result.status in ["FAIL", "ERROR"] and suite.required:
                all_passed = False
                
        # Run parallel tests
        if parallel_suites:
            with ThreadPoolExecutor(max_workers=min(len(parallel_suites), 4)) as executor:
                future_to_suite = {
                    executor.submit(self.execute_test_suite, suite): suite 
                    for suite in parallel_suites
                }
                
                for future in as_completed(future_to_suite):
                    suite = future_to_suite[future]
                    try:
                        result = future.result()
                        self.test_results.append(result)
                        
                        if result.status in ["FAIL", "ERROR"] and suite.required:
                            all_passed = False
                            
                    except Exception as e:
                        self.logger.error(f"💥 Parallel test execution failed for {suite.name}: {e}")
                        all_passed = False
                        
        return all_passed
        
    def generate_test_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r.status == "PASS"])
        failed_tests = len([r for r in self.test_results if r.status == "FAIL"])
        error_tests = len([r for r in self.test_results if r.status == "ERROR"])
        skipped_tests = len([r for r in self.test_results if r.status == "SKIP"])
        
        total_duration = sum(r.duration for r in self.test_results)
        avg_duration = total_duration / total_tests if total_tests > 0 else 0
        
        # Calculate success rate
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        # Identify critical failures
        critical_failures = [
            r for r in self.test_results 
            if r.status in ["FAIL", "ERROR"] and 
            any(s.required for s in self.test_suites if s.name == r.suite_name)
        ]
        
        report = {
            "test_summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "error_tests": error_tests,
                "skipped_tests": skipped_tests,
                "success_rate": round(success_rate, 2),
                "total_duration": round(total_duration, 2),
                "average_duration": round(avg_duration, 2),
                "critical_failures": len(critical_failures)
            },
            "test_details": [asdict(result) for result in self.test_results],
            "critical_failures": [asdict(failure) for failure in critical_failures],
            "test_environment": {
                "python_version": sys.version,
                "platform": sys.platform,
                "project_root": str(self.project_root),
                "parallel_execution": self.parallel,
                "timeout": self.timeout,
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None
            },
            "recommendations": self.generate_recommendations()
        }
        
        return report
        
    def generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        failed_tests = [r for r in self.test_results if r.status == "FAIL"]
        error_tests = [r for r in self.test_results if r.status == "ERROR"]
        slow_tests = [r for r in self.test_results if r.duration > 300]  # > 5 minutes
        
        if failed_tests:
            recommendations.append(f"🔧 Fix {len(failed_tests)} failing test(s) before deployment")
            
        if error_tests:
            recommendations.append(f"🚨 Investigate {len(error_tests)} test execution error(s)")
            
        if slow_tests:
            recommendations.append(f"⚡ Optimize {len(slow_tests)} slow-running test(s)")
            
        # Check success rate
        success_rate = len([r for r in self.test_results if r.status == "PASS"]) / len(self.test_results) * 100
        
        if success_rate < 80:
            recommendations.append("❌ Success rate below 80% - system not ready for production")
        elif success_rate < 95:
            recommendations.append("⚠️ Success rate below 95% - consider additional testing")
        else:
            recommendations.append("✅ High success rate - system appears ready for deployment")
            
        return recommendations
        
    def save_test_report(self, report: Dict[str, Any]) -> Path:
        """Save test report to file"""
        report_dir = self.project_root / "temp" / "test_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = report_dir / f"test_report_{timestamp}.json"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            
        # Also save as latest report
        latest_report = report_dir / "latest_test_report.json"
        with open(latest_report, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            
        return report_file
        
    def print_test_summary(self, report: Dict[str, Any]):
        """Print test summary to console"""
        summary = report["test_summary"]
        
        self.logger.info(f"\n{'='*60}")
        self.logger.info("TEST EXECUTION SUMMARY")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"Total Tests: {summary['total_tests']}")
        self.logger.info(f"Passed: {summary['passed_tests']} ✅")
        self.logger.info(f"Failed: {summary['failed_tests']} ❌")
        self.logger.info(f"Errors: {summary['error_tests']} 💥")
        self.logger.info(f"Skipped: {summary['skipped_tests']} ⏭️")
        self.logger.info(f"Success Rate: {summary['success_rate']}%")
        self.logger.info(f"Total Duration: {summary['total_duration']:.2f}s")
        self.logger.info(f"Average Duration: {summary['average_duration']:.2f}s")
        
        if summary['critical_failures'] > 0:
            self.logger.error(f"Critical Failures: {summary['critical_failures']} 🚨")
            
        # Print recommendations
        if report.get("recommendations"):
            self.logger.info(f"\n{'='*60}")
            self.logger.info("RECOMMENDATIONS")
            self.logger.info(f"{'='*60}")
            for rec in report["recommendations"]:
                self.logger.info(f"  {rec}")
                
        # Print failed tests details
        failed_results = [r for r in self.test_results if r.status in ["FAIL", "ERROR"]]
        if failed_results:
            self.logger.info(f"\n{'='*60}")
            self.logger.info("FAILED TESTS DETAILS")
            self.logger.info(f"{'='*60}")
            for result in failed_results:
                self.logger.error(f"❌ {result.suite_name}")
                if result.stderr:
                    self.logger.error(f"   Error: {result.stderr[:200]}...")
                    
    def run_all_tests(self) -> bool:
        """Run all configured tests"""
        self.logger.info("🚀 Starting TikTrue Test Orchestrator...")
        self.start_time = datetime.now()
        
        try:
            # Run tests based on parallel setting
            if self.parallel:
                all_passed = self.run_tests_parallel()
            else:
                all_passed = self.run_tests_sequential()
                
            self.end_time = datetime.now()
            
            # Generate and save report
            report = self.generate_test_report()
            report_file = self.save_test_report(report)
            
            # Print summary
            self.print_test_summary(report)
            
            self.logger.info(f"\n📊 Test report saved: {report_file}")
            
            if all_passed:
                self.logger.info("🎉 All tests completed successfully!")
            else:
                self.logger.error("❌ Some tests failed!")
                
            return all_passed
            
        except Exception as e:
            self.logger.error(f"💥 Test orchestration failed: {e}")
            return False

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="TikTrue Test Orchestrator")
    parser.add_argument("--config", help="Test configuration file")
    parser.add_argument("--parallel", action="store_true", help="Run tests in parallel where possible")
    parser.add_argument("--timeout", type=int, default=1800, help="Global timeout in seconds")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--suite", help="Run specific test suite only")
    
    args = parser.parse_args()
    
    orchestrator = TestOrchestrator(
        config_file=args.config,
        parallel=args.parallel,
        timeout=args.timeout,
        verbose=args.verbose
    )
    
    # Filter to specific suite if requested
    if args.suite:
        orchestrator.test_suites = [
            suite for suite in orchestrator.test_suites 
            if suite.name.lower() == args.suite.lower()
        ]
        
        if not orchestrator.test_suites:
            print(f"❌ Test suite '{args.suite}' not found")
            sys.exit(1)
    
    if orchestrator.run_all_tests():
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()