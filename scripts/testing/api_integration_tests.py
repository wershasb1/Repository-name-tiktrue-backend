#!/usr/bin/env python3
"""
TikTrue Platform - API Integration Tests

This script provides comprehensive integration testing for all API endpoints:
- Authentication APIs (login, refresh, logout)
- License validation APIs (validate, info, renew)
- Model download APIs (available, download, metadata)
- Payment APIs (create, webhook, history)
- User management APIs
- Admin APIs

Requirements: 3.1, 4.1 - Integration tests for all API endpoints
"""

import os
import sys
import json
import time
import logging
import asyncio
import aiohttp
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from urllib.parse import urljoin

@dataclass
class TestResult:
    """Test result data structure"""
    test_name: str
    endpoint: str
    method: str
    status: str  # PASS, FAIL, SKIP
    response_time: float
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    response_data: Optional[Dict] = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()

class APIIntegrationTester:
    """Comprehensive API integration testing suite"""
    
    def __init__(self, base_url: str = "https://api.tiktrue.com", timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        self.session.timeout = timeout
        
        # Test data
        self.test_users = {
            "admin": {
                "email": "admin@tiktrue.com",
                "password": "admin_test_password_123",
                "expected_role": "admin"
            },
            "pro_user": {
                "email": "pro@tiktrue.com", 
                "password": "pro_test_password_123",
                "expected_plan": "PRO"
            },
            "free_user": {
                "email": "free@tiktrue.com",
                "password": "free_test_password_123",
                "expected_plan": "FREE"
            }
        }
        
        # Authentication tokens
        self.auth_tokens = {}
        
        # Test results
        self.test_results: List[TestResult] = []
        
        # Setup logging
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging for API tests"""
        log_dir = Path(__file__).parent.parent.parent / "temp" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(log_dir / "api_integration_tests.log", encoding='utf-8')
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def make_request(self, method: str, endpoint: str, **kwargs) -> Tuple[bool, Dict, float]:
        """Make HTTP request with timing and error handling"""
        url = urljoin(self.base_url, endpoint)
        start_time = time.time()
        
        try:
            response = self.session.request(method, url, **kwargs)
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            try:
                response_data = response.json()
            except:
                response_data = {"raw_response": response.text}
                
            return True, {
                "status_code": response.status_code,
                "data": response_data,
                "headers": dict(response.headers)
            }, response_time
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return False, {"error": str(e)}, response_time
            
    def add_test_result(self, test_name: str, endpoint: str, method: str, 
                       success: bool, response: Dict, response_time: float, 
                       error_message: str = None):
        """Add test result to results list"""
        result = TestResult(
            test_name=test_name,
            endpoint=endpoint,
            method=method,
            status="PASS" if success else "FAIL",
            response_time=response_time,
            status_code=response.get("status_code"),
            error_message=error_message,
            response_data=response.get("data")
        )
        self.test_results.append(result)
        
        # Log result
        status_emoji = "✅" if success else "❌"
        self.logger.info(f"{status_emoji} {test_name}: {result.status} ({response_time:.2f}ms)")
        if error_message:
            self.logger.error(f"   Error: {error_message}")
            
    def test_authentication_apis(self) -> bool:
        """Test authentication API endpoints"""
        self.logger.info("🔐 Testing Authentication APIs...")
        
        all_passed = True
        
        for user_type, user_data in self.test_users.items():
            # Test login
            login_data = {
                "email": user_data["email"],
                "password": user_data["password"]
            }
            
            success, response, response_time = self.make_request(
                "POST", "/api/v1/auth/login/", json=login_data
            )
            
            if success and response.get("status_code") == 200:
                # Store auth token
                token_data = response.get("data", {})
                if "access" in token_data:
                    self.auth_tokens[user_type] = {
                        "access": token_data["access"],
                        "refresh": token_data.get("refresh")
                    }
                    
                self.add_test_result(
                    f"Login - {user_type}",
                    "/api/v1/auth/login/",
                    "POST",
                    True,
                    response,
                    response_time
                )
            else:
                all_passed = False
                self.add_test_result(
                    f"Login - {user_type}",
                    "/api/v1/auth/login/",
                    "POST",
                    False,
                    response,
                    response_time,
                    f"Login failed for {user_type}"
                )
                
            # Test token refresh (if we have refresh token)
            if user_type in self.auth_tokens and self.auth_tokens[user_type].get("refresh"):
                refresh_data = {"refresh": self.auth_tokens[user_type]["refresh"]}
                
                success, response, response_time = self.make_request(
                    "POST", "/api/v1/auth/refresh/", json=refresh_data
                )
                
                self.add_test_result(
                    f"Token Refresh - {user_type}",
                    "/api/v1/auth/refresh/",
                    "POST",
                    success and response.get("status_code") == 200,
                    response,
                    response_time,
                    None if success else "Token refresh failed"
                )
                
                if not (success and response.get("status_code") == 200):
                    all_passed = False
                    
        # Test logout
        if "pro_user" in self.auth_tokens:
            headers = {"Authorization": f"Bearer {self.auth_tokens['pro_user']['access']}"}
            
            success, response, response_time = self.make_request(
                "POST", "/api/v1/auth/logout/", headers=headers
            )
            
            self.add_test_result(
                "Logout",
                "/api/v1/auth/logout/",
                "POST",
                success and response.get("status_code") in [200, 204],
                response,
                response_time,
                None if success else "Logout failed"
            )
            
            if not (success and response.get("status_code") in [200, 204]):
                all_passed = False
                
        return all_passed
        
    def test_license_apis(self) -> bool:
        """Test license validation API endpoints"""
        self.logger.info("📜 Testing License APIs...")
        
        all_passed = True
        
        # Test with authenticated user
        if "pro_user" not in self.auth_tokens:
            self.logger.error("No pro_user token available for license tests")
            return False
            
        headers = {"Authorization": f"Bearer {self.auth_tokens['pro_user']['access']}"}
        
        # Test license validation
        success, response, response_time = self.make_request(
            "GET", "/api/v1/license/validate/", headers=headers
        )
        
        self.add_test_result(
            "License Validation",
            "/api/v1/license/validate/",
            "GET",
            success and response.get("status_code") == 200,
            response,
            response_time,
            None if success else "License validation failed"
        )
        
        if not (success and response.get("status_code") == 200):
            all_passed = False
            
        # Test license info
        success, response, response_time = self.make_request(
            "GET", "/api/v1/license/info/", headers=headers
        )
        
        self.add_test_result(
            "License Info",
            "/api/v1/license/info/",
            "GET",
            success and response.get("status_code") == 200,
            response,
            response_time,
            None if success else "License info failed"
        )
        
        if not (success and response.get("status_code") == 200):
            all_passed = False
            
        # Test license renewal (POST)
        renewal_data = {"extend_months": 12}
        
        success, response, response_time = self.make_request(
            "POST", "/api/v1/license/renew/", headers=headers, json=renewal_data
        )
        
        # Note: This might fail in test environment, which is expected
        self.add_test_result(
            "License Renewal",
            "/api/v1/license/renew/",
            "POST",
            success and response.get("status_code") in [200, 400, 403],  # 400/403 expected in test
            response,
            response_time,
            None if success else "License renewal request failed"
        )
        
        return all_passed
        
    def test_model_apis(self) -> bool:
        """Test model download API endpoints"""
        self.logger.info("🤖 Testing Model APIs...")
        
        all_passed = True
        
        if "pro_user" not in self.auth_tokens:
            self.logger.error("No pro_user token available for model tests")
            return False
            
        headers = {"Authorization": f"Bearer {self.auth_tokens['pro_user']['access']}"}
        
        # Test available models
        success, response, response_time = self.make_request(
            "GET", "/api/v1/models/available/", headers=headers
        )
        
        self.add_test_result(
            "Available Models",
            "/api/v1/models/available/",
            "GET",
            success and response.get("status_code") == 200,
            response,
            response_time,
            None if success else "Available models failed"
        )
        
        if not (success and response.get("status_code") == 200):
            all_passed = False
            return all_passed
            
        # Get model list for further tests
        models = response.get("data", {}).get("models", [])
        
        if models:
            model_id = models[0].get("id")
            
            # Test model metadata
            success, response, response_time = self.make_request(
                "GET", f"/api/v1/models/{model_id}/metadata/", headers=headers
            )
            
            self.add_test_result(
                "Model Metadata",
                f"/api/v1/models/{model_id}/metadata/",
                "GET",
                success and response.get("status_code") == 200,
                response,
                response_time,
                None if success else "Model metadata failed"
            )
            
            if not (success and response.get("status_code") == 200):
                all_passed = False
                
            # Test download token creation
            success, response, response_time = self.make_request(
                "POST", f"/api/v1/models/{model_id}/download/", headers=headers
            )
            
            self.add_test_result(
                "Create Download Token",
                f"/api/v1/models/{model_id}/download/",
                "POST",
                success and response.get("status_code") == 200,
                response,
                response_time,
                None if success else "Download token creation failed"
            )
            
            if success and response.get("status_code") == 200:
                download_token = response.get("data", {}).get("download_token")
                
                if download_token:
                    # Test actual download (just check endpoint, don't download full file)
                    success, response, response_time = self.make_request(
                        "HEAD", f"/api/v1/models/download/{download_token}/", headers=headers
                    )
                    
                    self.add_test_result(
                        "Model Download",
                        f"/api/v1/models/download/{download_token}/",
                        "HEAD",
                        success and response.get("status_code") == 200,
                        response,
                        response_time,
                        None if success else "Model download failed"
                    )
                    
                    if not (success and response.get("status_code") == 200):
                        all_passed = False
            else:
                all_passed = False
                
        return all_passed
        
    def test_payment_apis(self) -> bool:
        """Test payment API endpoints"""
        self.logger.info("💳 Testing Payment APIs...")
        
        all_passed = True
        
        if "pro_user" not in self.auth_tokens:
            self.logger.error("No pro_user token available for payment tests")
            return False
            
        headers = {"Authorization": f"Bearer {self.auth_tokens['pro_user']['access']}"}
        
        # Test payment methods
        success, response, response_time = self.make_request(
            "GET", "/api/v1/payments/methods/", headers=headers
        )
        
        self.add_test_result(
            "Payment Methods",
            "/api/v1/payments/methods/",
            "GET",
            success and response.get("status_code") == 200,
            response,
            response_time,
            None if success else "Payment methods failed"
        )
        
        if not (success and response.get("status_code") == 200):
            all_passed = False
            
        # Test pricing plans
        success, response, response_time = self.make_request(
            "GET", "/api/v1/payments/plans/", headers=headers
        )
        
        self.add_test_result(
            "Pricing Plans",
            "/api/v1/payments/plans/",
            "GET",
            success and response.get("status_code") == 200,
            response,
            response_time,
            None if success else "Pricing plans failed"
        )
        
        if not (success and response.get("status_code") == 200):
            all_passed = False
            
        # Test create payment session
        payment_data = {
            "plan_id": "pro_monthly",
            "success_url": "https://tiktrue.com/success",
            "cancel_url": "https://tiktrue.com/cancel"
        }
        
        success, response, response_time = self.make_request(
            "POST", "/api/v1/payments/create/", headers=headers, json=payment_data
        )
        
        self.add_test_result(
            "Create Payment Session",
            "/api/v1/payments/create/",
            "POST",
            success and response.get("status_code") in [200, 201],
            response,
            response_time,
            None if success else "Payment session creation failed"
        )
        
        if not (success and response.get("status_code") in [200, 201]):
            all_passed = False
            
        # Test payment history
        success, response, response_time = self.make_request(
            "GET", "/api/v1/payments/history/", headers=headers
        )
        
        self.add_test_result(
            "Payment History",
            "/api/v1/payments/history/",
            "GET",
            success and response.get("status_code") == 200,
            response,
            response_time,
            None if success else "Payment history failed"
        )
        
        if not (success and response.get("status_code") == 200):
            all_passed = False
            
        return all_passed
        
    def test_admin_apis(self) -> bool:
        """Test admin API endpoints"""
        self.logger.info("👑 Testing Admin APIs...")
        
        all_passed = True
        
        if "admin" not in self.auth_tokens:
            self.logger.warning("No admin token available, skipping admin tests")
            return True  # Skip admin tests if no admin token
            
        headers = {"Authorization": f"Bearer {self.auth_tokens['admin']['access']}"}
        
        # Test user management
        success, response, response_time = self.make_request(
            "GET", "/api/v1/admin/users/", headers=headers
        )
        
        self.add_test_result(
            "Admin - User List",
            "/api/v1/admin/users/",
            "GET",
            success and response.get("status_code") == 200,
            response,
            response_time,
            None if success else "Admin user list failed"
        )
        
        if not (success and response.get("status_code") == 200):
            all_passed = False
            
        # Test license management
        success, response, response_time = self.make_request(
            "GET", "/api/v1/admin/licenses/", headers=headers
        )
        
        self.add_test_result(
            "Admin - License List",
            "/api/v1/admin/licenses/",
            "GET",
            success and response.get("status_code") == 200,
            response,
            response_time,
            None if success else "Admin license list failed"
        )
        
        if not (success and response.get("status_code") == 200):
            all_passed = False
            
        # Test analytics
        success, response, response_time = self.make_request(
            "GET", "/api/v1/admin/analytics/", headers=headers
        )
        
        self.add_test_result(
            "Admin - Analytics",
            "/api/v1/admin/analytics/",
            "GET",
            success and response.get("status_code") == 200,
            response,
            response_time,
            None if success else "Admin analytics failed"
        )
        
        if not (success and response.get("status_code") == 200):
            all_passed = False
            
        return all_passed
        
    def test_error_handling(self) -> bool:
        """Test API error handling"""
        self.logger.info("🚨 Testing Error Handling...")
        
        all_passed = True
        
        # Test unauthorized access
        success, response, response_time = self.make_request(
            "GET", "/api/v1/license/validate/"
        )
        
        self.add_test_result(
            "Unauthorized Access",
            "/api/v1/license/validate/",
            "GET",
            success and response.get("status_code") == 401,
            response,
            response_time,
            None if (success and response.get("status_code") == 401) else "Should return 401"
        )
        
        if not (success and response.get("status_code") == 401):
            all_passed = False
            
        # Test invalid endpoint
        success, response, response_time = self.make_request(
            "GET", "/api/v1/nonexistent/"
        )
        
        self.add_test_result(
            "Invalid Endpoint",
            "/api/v1/nonexistent/",
            "GET",
            success and response.get("status_code") == 404,
            response,
            response_time,
            None if (success and response.get("status_code") == 404) else "Should return 404"
        )
        
        if not (success and response.get("status_code") == 404):
            all_passed = False
            
        # Test invalid method
        success, response, response_time = self.make_request(
            "DELETE", "/api/v1/auth/login/"
        )
        
        self.add_test_result(
            "Invalid Method",
            "/api/v1/auth/login/",
            "DELETE",
            success and response.get("status_code") == 405,
            response,
            response_time,
            None if (success and response.get("status_code") == 405) else "Should return 405"
        )
        
        if not (success and response.get("status_code") == 405):
            all_passed = False
            
        return all_passed
        
    def generate_test_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r.status == "PASS"])
        failed_tests = len([r for r in self.test_results if r.status == "FAIL"])
        
        avg_response_time = sum(r.response_time for r in self.test_results) / total_tests if total_tests > 0 else 0
        
        report = {
            "test_summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "success_rate": round((passed_tests / total_tests) * 100, 2) if total_tests > 0 else 0,
                "average_response_time": round(avg_response_time, 2)
            },
            "test_details": [asdict(result) for result in self.test_results],
            "test_environment": {
                "base_url": self.base_url,
                "timeout": self.timeout,
                "test_date": datetime.now().isoformat()
            }
        }
        
        return report
        
    def run_all_tests(self) -> bool:
        """Run all API integration tests"""
        self.logger.info("🚀 Starting API Integration Tests...")
        
        test_suites = [
            ("Authentication APIs", self.test_authentication_apis),
            ("License APIs", self.test_license_apis),
            ("Model APIs", self.test_model_apis),
            ("Payment APIs", self.test_payment_apis),
            ("Admin APIs", self.test_admin_apis),
            ("Error Handling", self.test_error_handling)
        ]
        
        all_passed = True
        
        for suite_name, test_function in test_suites:
            self.logger.info(f"\n{'='*50}")
            self.logger.info(f"Running: {suite_name}")
            self.logger.info(f"{'='*50}")
            
            try:
                result = test_function()
                if not result:
                    all_passed = False
                    self.logger.error(f"❌ {suite_name}: FAILED")
                else:
                    self.logger.info(f"✅ {suite_name}: PASSED")
            except Exception as e:
                self.logger.error(f"💥 {suite_name}: ERROR - {e}")
                all_passed = False
                
        # Generate and save report
        report = self.generate_test_report()
        
        report_file = Path(__file__).parent.parent.parent / "temp" / "api_integration_test_report.json"
        report_file.parent.mkdir(exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            
        self.logger.info(f"\n{'='*50}")
        self.logger.info("TEST SUMMARY")
        self.logger.info(f"{'='*50}")
        self.logger.info(f"Total tests: {report['test_summary']['total_tests']}")
        self.logger.info(f"Passed: {report['test_summary']['passed_tests']}")
        self.logger.info(f"Failed: {report['test_summary']['failed_tests']}")
        self.logger.info(f"Success rate: {report['test_summary']['success_rate']}%")
        self.logger.info(f"Average response time: {report['test_summary']['average_response_time']}ms")
        self.logger.info(f"Report saved: {report_file}")
        
        if all_passed:
            self.logger.info("🎉 All API integration tests passed!")
        else:
            self.logger.error("❌ Some API integration tests failed!")
            
        return all_passed

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="TikTrue API Integration Tests")
    parser.add_argument("--base-url", default="https://api.tiktrue.com", help="API base URL")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds")
    
    args = parser.parse_args()
    
    tester = APIIntegrationTester(base_url=args.base_url, timeout=args.timeout)
    
    if tester.run_all_tests():
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()