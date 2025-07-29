#!/usr/bin/env python3
"""
Comprehensive End-to-End Test Suite for TikTrue Distributed LLM Platform
Orchestrates all end-to-end workflow tests with proper error handling and reporting

This module implements comprehensive end-to-end testing for the TikTrue platform,
including admin workflows, client workflows, multi-node simulations, and security validation.
"""

import asyncio
import pytest
import json
import logging
import tempfile
import time
import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from dataclasses import dataclass

# Import system modules
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ComprehensiveE2ETests")

# Import test modules
try:
    from test_end_to_end_workflows import EndToEndWorkflowTests
    WORKFLOW_TESTS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Workflow tests import failed: {e}")
    WORKFLOW_TESTS_AVAILABLE = False

try:
    from test_performance_load import PerformanceLoadTestSuite as PerformanceLoadTests
    PERFORMANCE_TESTS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Performance tests import failed: {e}")
    PERFORMANCE_TESTS_AVAILABLE = False

try:
    from test_backend_api_integration import BackendAPIIntegrationTests
    BACKEND_TESTS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Backend API tests import failed: {e}")
    BACKEND_TESTS_AVAILABLE = False


@dataclass
class TestSuiteResult:
    """Result of comprehensive test suite execution"""
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    execution_time: float
    test_results: Dict[str, Any]
    error_summary: List[str]


class ComprehensiveE2ETestSuite:
    """
    Comprehensive End-to-End Test Suite Orchestrator
    
    This class orchestrates all end-to-end tests for the TikTrue platform:
    - Complete admin workflow integration tests
    - Client connection and model usage tests
    - Multi-node network simulation tests
    - Security boundary validation tests
    - Performance and load testing
    - Backend API integration tests
    
    Requirements addressed:
    - 14.2: End-to-end workflow testing
    - 14.3: Security boundary validation
    - 14.4: Performance testing
    """
    
    def __init__(self):
        """Initialize comprehensive test suite"""
        self.test_results = {}
        self.execution_start_time = None
        self.cleanup_tasks = []
        
        # Test suite configuration
        self.config = {
            'run_workflow_tests': WORKFLOW_TESTS_AVAILABLE,
            'run_performance_tests': PERFORMANCE_TESTS_AVAILABLE,
            'run_backend_tests': BACKEND_TESTS_AVAILABLE,
            'parallel_execution': True,
            'timeout_per_suite': 300,  # 5 minutes per test suite
            'max_retries': 2
        }
        
        # Initialize test suite instances
        self.workflow_tests = EndToEndWorkflowTests() if WORKFLOW_TESTS_AVAILABLE else None
        self.performance_tests = PerformanceLoadTests() if PERFORMANCE_TESTS_AVAILABLE else None
        self.backend_tests = BackendAPIIntegrationTests() if BACKEND_TESTS_AVAILABLE else None
    
    async def run_comprehensive_test_suite(self) -> TestSuiteResult:
        """
        Run comprehensive end-to-end test suite
        
        Returns:
            TestSuiteResult: Complete test execution results
        """
        logger.info("=== Starting Comprehensive End-to-End Test Suite ===")
        self.execution_start_time = time.time()
        
        try:
            # Setup test environment
            await self._setup_comprehensive_environment()
            
            # Run test suites
            if self.config['parallel_execution']:
                await self._run_parallel_test_suites()
            else:
                await self._run_sequential_test_suites()
            
            # Generate comprehensive report
            return self._generate_comprehensive_report()
            
        except Exception as e:
            logger.error(f"Comprehensive test suite failed: {e}", exc_info=True)
            return self._generate_error_report(str(e))
        finally:
            await self._cleanup_comprehensive_environment()
    
    async def _setup_comprehensive_environment(self):
        """Setup comprehensive test environment for all test suites"""
        logger.info("Setting up comprehensive test environment...")
        
        # Create temporary directory for all tests
        self.temp_dir = Path(tempfile.mkdtemp(prefix="tiktrue_comprehensive_e2e_"))
        self.cleanup_tasks.append(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))
        
        # Setup individual test environments
        if self.workflow_tests:
            await self.workflow_tests.setup_test_environment()
        
        # Performance tests don't need special setup
        # Backend tests setup would go here if available
        
        logger.info(f"Comprehensive test environment ready at: {self.temp_dir}")
    
    async def _run_parallel_test_suites(self):
        """Run all test suites in parallel for faster execution"""
        logger.info("Running test suites in parallel...")
        
        # Create tasks for each test suite
        test_tasks = []
        
        if self.config['run_workflow_tests'] and self.workflow_tests:
            task = asyncio.create_task(
                self._run_workflow_tests_with_timeout(),
                name="workflow_tests"
            )
            test_tasks.append(task)
        
        if self.config['run_performance_tests'] and self.performance_tests:
            task = asyncio.create_task(
                self._run_performance_tests_with_timeout(),
                name="performance_tests"
            )
            test_tasks.append(task)
        
        if self.config['run_backend_tests'] and self.backend_tests:
            task = asyncio.create_task(
                self._run_backend_tests_with_timeout(),
                name="backend_tests"
            )
            test_tasks.append(task)
        
        # Wait for all tasks to complete
        if test_tasks:
            results = await asyncio.gather(*test_tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(results):
                task_name = test_tasks[i].get_name()
                if isinstance(result, Exception):
                    logger.error(f"Test suite {task_name} failed: {result}")
                    self.test_results[task_name] = {
                        'success': False,
                        'error': str(result),
                        'results': {}
                    }
                else:
                    self.test_results[task_name] = result
    
    async def _run_sequential_test_suites(self):
        """Run test suites sequentially for better debugging"""
        logger.info("Running test suites sequentially...")
        
        # Run workflow tests
        if self.config['run_workflow_tests'] and self.workflow_tests:
            try:
                result = await self._run_workflow_tests_with_timeout()
                self.test_results['workflow_tests'] = result
            except Exception as e:
                logger.error(f"Workflow tests failed: {e}")
                self.test_results['workflow_tests'] = {
                    'success': False,
                    'error': str(e),
                    'results': {}
                }
        
        # Run performance tests
        if self.config['run_performance_tests'] and self.performance_tests:
            try:
                result = await self._run_performance_tests_with_timeout()
                self.test_results['performance_tests'] = result
            except Exception as e:
                logger.error(f"Performance tests failed: {e}")
                self.test_results['performance_tests'] = {
                    'success': False,
                    'error': str(e),
                    'results': {}
                }
        
        # Run backend tests
        if self.config['run_backend_tests'] and self.backend_tests:
            try:
                result = await self._run_backend_tests_with_timeout()
                self.test_results['backend_tests'] = result
            except Exception as e:
                logger.error(f"Backend tests failed: {e}")
                self.test_results['backend_tests'] = {
                    'success': False,
                    'error': str(e),
                    'results': {}
                }
    
    async def _run_workflow_tests_with_timeout(self) -> Dict[str, Any]:
        """Run workflow tests with timeout protection"""
        try:
            result = await asyncio.wait_for(
                self.workflow_tests.run_all_workflows(),
                timeout=self.config['timeout_per_suite']
            )
            return {
                'success': True,
                'results': result,
                'error': None
            }
        except asyncio.TimeoutError:
            return {
                'success': False,
                'results': {},
                'error': f"Workflow tests timed out after {self.config['timeout_per_suite']} seconds"
            }
        except Exception as e:
            return {
                'success': False,
                'results': {},
                'error': str(e)
            }
    
    async def _run_performance_tests_with_timeout(self) -> Dict[str, Any]:
        """Run performance tests with timeout protection"""
        try:
            result = await asyncio.wait_for(
                self.performance_tests.run_all_performance_tests(),
                timeout=self.config['timeout_per_suite']
            )
            return {
                'success': True,
                'results': result,
                'error': None
            }
        except asyncio.TimeoutError:
            return {
                'success': False,
                'results': {},
                'error': f"Performance tests timed out after {self.config['timeout_per_suite']} seconds"
            }
        except Exception as e:
            return {
                'success': False,
                'results': {},
                'error': str(e)
            }
    
    async def _run_backend_tests_with_timeout(self) -> Dict[str, Any]:
        """Run backend API tests with timeout protection"""
        try:
            result = await asyncio.wait_for(
                self.backend_tests.run_all_backend_tests(),
                timeout=self.config['timeout_per_suite']
            )
            return {
                'success': True,
                'results': result,
                'error': None
            }
        except asyncio.TimeoutError:
            return {
                'success': False,
                'results': {},
                'error': f"Backend tests timed out after {self.config['timeout_per_suite']} seconds"
            }
        except Exception as e:
            return {
                'success': False,
                'results': {},
                'error': str(e)
            }
    
    def _generate_comprehensive_report(self) -> TestSuiteResult:
        """Generate comprehensive test execution report"""
        execution_time = time.time() - self.execution_start_time
        
        # Count test results
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        skipped_tests = 0
        error_summary = []
        
        for suite_name, suite_result in self.test_results.items():
            if suite_result['success']:
                if 'results' in suite_result and suite_result['results']:
                    # Count individual test results
                    results = suite_result['results']
                    if isinstance(results, dict):
                        for test_name, test_result in results.items():
                            total_tests += 1
                            if isinstance(test_result, dict):
                                if test_result.get('success', False):
                                    passed_tests += 1
                                else:
                                    failed_tests += 1
                                    if 'error' in test_result:
                                        error_summary.append(f"{suite_name}.{test_name}: {test_result['error']}")
                            elif test_result:
                                passed_tests += 1
                            else:
                                failed_tests += 1
                    else:
                        # Simple boolean result
                        total_tests += 1
                        if results:
                            passed_tests += 1
                        else:
                            failed_tests += 1
                else:
                    # Suite ran but no detailed results
                    total_tests += 1
                    passed_tests += 1
            else:
                # Suite failed entirely
                total_tests += 1
                failed_tests += 1
                error_summary.append(f"{suite_name}: {suite_result.get('error', 'Unknown error')}")
        
        # Generate summary report
        report = TestSuiteResult(
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            skipped_tests=skipped_tests,
            execution_time=execution_time,
            test_results=self.test_results,
            error_summary=error_summary
        )
        
        # Log summary
        logger.info("=== Comprehensive Test Suite Results ===")
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Passed: {passed_tests}")
        logger.info(f"Failed: {failed_tests}")
        logger.info(f"Skipped: {skipped_tests}")
        logger.info(f"Execution Time: {execution_time:.2f} seconds")
        logger.info(f"Success Rate: {(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "No tests executed")
        
        if error_summary:
            logger.error("Error Summary:")
            for error in error_summary[:10]:  # Show first 10 errors
                logger.error(f"  - {error}")
            if len(error_summary) > 10:
                logger.error(f"  ... and {len(error_summary) - 10} more errors")
        
        return report
    
    def _generate_error_report(self, error_message: str) -> TestSuiteResult:
        """Generate error report when test suite fails to run"""
        execution_time = time.time() - self.execution_start_time if self.execution_start_time else 0
        
        return TestSuiteResult(
            total_tests=1,
            passed_tests=0,
            failed_tests=1,
            skipped_tests=0,
            execution_time=execution_time,
            test_results={'comprehensive_suite': {'success': False, 'error': error_message}},
            error_summary=[f"Comprehensive test suite: {error_message}"]
        )
    
    async def _cleanup_comprehensive_environment(self):
        """Cleanup comprehensive test environment"""
        logger.info("Cleaning up comprehensive test environment...")
        
        # Run cleanup tasks
        for cleanup_task in self.cleanup_tasks:
            try:
                if asyncio.iscoroutinefunction(cleanup_task):
                    await cleanup_task()
                else:
                    cleanup_task()
            except Exception as e:
                logger.warning(f"Cleanup task failed: {e}")
        
        # Cleanup individual test environments
        if self.workflow_tests:
            try:
                await self.workflow_tests._cleanup()
            except Exception as e:
                logger.warning(f"Workflow tests cleanup failed: {e}")
        
        # Performance tests don't need special cleanup
        
        # Backend tests cleanup would go here if available
    
    def save_test_report(self, report: TestSuiteResult, output_file: Optional[str] = None):
        """Save comprehensive test report to file"""
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"comprehensive_e2e_test_report_{timestamp}.json"
        
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_tests': report.total_tests,
                'passed_tests': report.passed_tests,
                'failed_tests': report.failed_tests,
                'skipped_tests': report.skipped_tests,
                'execution_time': report.execution_time,
                'success_rate': (report.passed_tests / report.total_tests * 100) if report.total_tests > 0 else 0
            },
            'detailed_results': report.test_results,
            'error_summary': report.error_summary,
            'configuration': self.config
        }
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Test report saved to: {output_file}")
        except Exception as e:
            logger.error(f"Failed to save test report: {e}")


# Test execution functions for pytest integration
@pytest.mark.asyncio
async def test_comprehensive_e2e_suite():
    """Pytest entry point for comprehensive end-to-end test suite"""
    suite = ComprehensiveE2ETestSuite()
    result = await suite.run_comprehensive_test_suite()
    
    # Save report
    suite.save_test_report(result)
    
    # Assert overall success
    assert result.passed_tests > 0, f"No tests passed. Errors: {result.error_summary}"
    assert result.failed_tests == 0, f"Some tests failed. Errors: {result.error_summary}"


async def main():
    """Main entry point for running comprehensive test suite"""
    suite = ComprehensiveE2ETestSuite()
    result = await suite.run_comprehensive_test_suite()
    
    # Save report
    suite.save_test_report(result)
    
    # Exit with appropriate code
    exit_code = 0 if result.failed_tests == 0 else 1
    return exit_code


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)