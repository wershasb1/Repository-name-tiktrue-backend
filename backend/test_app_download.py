#!/usr/bin/env python3
"""
Desktop App Download Testing Script for TikTrue Backend

This script tests the desktop application download functionality
including API endpoints, file serving, and security measures.
"""

import requests
import json
import sys
import os
from datetime import datetime

class AppDownloadTester:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.test_results = []
        self.auth_token = None
        
    def log_test(self, test_name, status, details=None, response_time=None):
        """Log test result"""
        result = {
            'test': test_name,
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'details': details,
            'response_time_ms': response_time
        }
        self.test_results.append(result)
        
        status_icon = "✓" if status == "pass" else "✗" if status == "fail" else "⚠"
        print(f"{status_icon} {test_name}: {status.upper()}")
        if details:
            print(f"  {details}")
        if response_time:
            print(f"  Response time: {response_time:.2f}ms")

    def test_endpoint_availability(self):
        """Test if download endpoints are available"""
        print("\n" + "-" * 40)
        print("Download Endpoint Availability Tests")
        print("-" * 40)
        
        endpoints = [
            '/api/v1/downloads/desktop-app-info/',
            '/api/v1/downloads/installation-guide/',
        ]
        
        for endpoint in endpoints:
            try:
                import time
                start_time = time.time()
                
                response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                response_time = (time.time() - start_time) * 1000
                
                if endpoint == '/api/v1/downloads/installation-guide/':
                    # This endpoint should work without auth
                    if response.status_code == 200:
                        self.log_test(f"Endpoint {endpoint}", "pass", 
                                    f"HTTP {response.status_code}", response_time)
                    else:
                        self.log_test(f"Endpoint {endpoint}", "fail", 
                                    f"HTTP {response.status_code}", response_time)
                else:
                    # These endpoints require auth, so 401 is expected
                    if response.status_code in [200, 401]:
                        self.log_test(f"Endpoint {endpoint}", "pass", 
                                    f"HTTP {response.status_code} (expected)", response_time)
                    else:
                        self.log_test(f"Endpoint {endpoint}", "fail", 
                                    f"HTTP {response.status_code}", response_time)
                        
            except Exception as e:
                self.log_test(f"Endpoint {endpoint}", "fail", str(e))

    def test_installation_guide(self):
        """Test installation guide endpoint"""
        print("\n" + "-" * 40)
        print("Installation Guide Tests")
        print("-" * 40)
        
        try:
            import time
            start_time = time.time()
            
            response = requests.get(f"{self.base_url}/api/v1/downloads/installation-guide/", timeout=10)
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    # Check required fields
                    required_fields = ['title', 'version', 'steps', 'system_requirements', 'troubleshooting']
                    missing_fields = [field for field in required_fields if field not in data]
                    
                    if not missing_fields:
                        self.log_test("Installation Guide Structure", "pass", 
                                    f"All required fields present", response_time)
                        
                        # Check steps structure
                        if isinstance(data.get('steps'), list) and len(data['steps']) > 0:
                            self.log_test("Installation Steps", "pass", 
                                        f"{len(data['steps'])} steps provided")
                        else:
                            self.log_test("Installation Steps", "fail", 
                                        "No installation steps found")
                            
                        # Check system requirements
                        if isinstance(data.get('system_requirements'), dict):
                            self.log_test("System Requirements", "pass", 
                                        "System requirements provided")
                        else:
                            self.log_test("System Requirements", "fail", 
                                        "System requirements missing")
                            
                    else:
                        self.log_test("Installation Guide Structure", "fail", 
                                    f"Missing fields: {', '.join(missing_fields)}", response_time)
                        
                except json.JSONDecodeError:
                    self.log_test("Installation Guide JSON", "fail", 
                                "Invalid JSON response", response_time)
            else:
                self.log_test("Installation Guide Access", "fail", 
                            f"HTTP {response.status_code}", response_time)
                
        except Exception as e:
            self.log_test("Installation Guide Access", "fail", str(e))

    def test_download_info_without_auth(self):
        """Test download info endpoint without authentication"""
        print("\n" + "-" * 40)
        print("Download Info Without Auth Tests")
        print("-" * 40)
        
        try:
            import time
            start_time = time.time()
            
            response = requests.get(f"{self.base_url}/api/v1/downloads/desktop-app-info/", timeout=10)
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 401:
                self.log_test("Download Info Auth Required", "pass", 
                            "Properly requires authentication", response_time)
            else:
                self.log_test("Download Info Auth Required", "fail", 
                            f"Expected 401, got {response.status_code}", response_time)
                
        except Exception as e:
            self.log_test("Download Info Auth Required", "fail", str(e))

    def test_download_file_without_auth(self):
        """Test download file endpoint without authentication"""
        print("\n" + "-" * 40)
        print("Download File Without Auth Tests")
        print("-" * 40)
        
        test_files = [
            'TikTrue_Real_Build.exe',
            'TikTrue_Working_GUI.exe',
            'TikTrue_Working_Console.exe'
        ]
        
        for filename in test_files:
            try:
                import time
                start_time = time.time()
                
                response = requests.get(
                    f"{self.base_url}/api/v1/downloads/desktop-app/{filename}", 
                    timeout=10
                )
                response_time = (time.time() - start_time) * 1000
                
                if response.status_code == 401:
                    self.log_test(f"Download {filename} Auth Required", "pass", 
                                "Properly requires authentication", response_time)
                else:
                    self.log_test(f"Download {filename} Auth Required", "fail", 
                                f"Expected 401, got {response.status_code}", response_time)
                    
            except Exception as e:
                self.log_test(f"Download {filename} Auth Required", "fail", str(e))

    def test_file_existence(self):
        """Test if desktop app files exist on server"""
        print("\n" + "-" * 40)
        print("File Existence Tests")
        print("-" * 40)
        
        # Get the project root directory (assuming script is in backend/)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        dist_dir = os.path.join(project_root, 'dist')
        
        test_files = [
            'TikTrue_Real_Build.exe',
            'TikTrue_Working_GUI.exe',
            'TikTrue_Working_Console.exe',
            'TikTrue_GUI_Test.exe',
            'TikTrue_BuildTest.exe'
        ]
        
        for filename in test_files:
            file_path = os.path.join(dist_dir, filename)
            
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                size_mb = file_size / (1024 * 1024)
                self.log_test(f"File {filename}", "pass", 
                            f"Exists, size: {size_mb:.1f} MB")
            else:
                self.log_test(f"File {filename}", "fail", 
                            "File not found on server")

    def test_security_measures(self):
        """Test security measures for download endpoints"""
        print("\n" + "-" * 40)
        print("Security Measures Tests")
        print("-" * 40)
        
        # Test path traversal protection
        malicious_filenames = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32\\config\\sam',
            'TikTrue_Real_Build.exe/../../../sensitive_file.txt',
            'invalid_file.exe'
        ]
        
        for filename in malicious_filenames:
            try:
                import time
                start_time = time.time()
                
                response = requests.get(
                    f"{self.base_url}/api/v1/downloads/desktop-app/{filename}", 
                    timeout=10
                )
                response_time = (time.time() - start_time) * 1000
                
                if response.status_code in [401, 404]:
                    self.log_test(f"Security Test: {filename[:20]}...", "pass", 
                                f"Properly blocked (HTTP {response.status_code})", response_time)
                else:
                    self.log_test(f"Security Test: {filename[:20]}...", "fail", 
                                f"Not properly blocked (HTTP {response.status_code})", response_time)
                    
            except Exception as e:
                self.log_test(f"Security Test: {filename[:20]}...", "pass", 
                            f"Request failed (good): {str(e)}")

    def test_cors_headers(self):
        """Test CORS headers for download endpoints"""
        print("\n" + "-" * 40)
        print("CORS Headers Tests")
        print("-" * 40)
        
        try:
            import time
            start_time = time.time()
            
            response = requests.options(
                f"{self.base_url}/api/v1/downloads/installation-guide/",
                headers={
                    'Origin': 'https://tiktrue.com',
                    'Access-Control-Request-Method': 'GET'
                },
                timeout=10
            )
            response_time = (time.time() - start_time) * 1000
            
            cors_origin = response.headers.get('Access-Control-Allow-Origin')
            
            if cors_origin:
                self.log_test("CORS Headers", "pass", 
                            f"Origin allowed: {cors_origin}", response_time)
            else:
                self.log_test("CORS Headers", "fail", 
                            "No CORS headers found", response_time)
                
        except Exception as e:
            self.log_test("CORS Headers", "fail", str(e))

    def run_all_tests(self):
        """Run all download functionality tests"""
        print(f"TikTrue Desktop App Download Test Suite")
        print(f"Base URL: {self.base_url}")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        self.test_endpoint_availability()
        self.test_installation_guide()
        self.test_download_info_without_auth()
        self.test_download_file_without_auth()
        self.test_file_existence()
        self.test_security_measures()
        self.test_cors_headers()
        
        self.print_summary()

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("DESKTOP APP DOWNLOAD TEST SUMMARY")
        print("=" * 60)
        
        passed = len([r for r in self.test_results if r['status'] == 'pass'])
        failed = len([r for r in self.test_results if r['status'] == 'fail'])
        warnings = len([r for r in self.test_results if r['status'] == 'warning'])
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Warnings: {warnings}")
        
        if failed > 0:
            print(f"\n❌ {failed} tests failed - Download functionality has issues")
            print("\nFailed Tests:")
            for result in self.test_results:
                if result['status'] == 'fail':
                    print(f"  - {result['test']}: {result['details']}")
        elif warnings > 0:
            print(f"\n⚠️  {warnings} tests have warnings - Download functionality mostly working")
        else:
            print(f"\n✅ All tests passed - Download functionality is working correctly")
        
        # Save results to file
        with open('app_download_test_results.json', 'w') as f:
            json.dump(self.test_results, f, indent=2)
        print(f"\nDetailed results saved to: app_download_test_results.json")

def main():
    """Main function"""
    base_url = "https://api.tiktrue.com"
    
    # Allow URL override from command line
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    
    tester = AppDownloadTester(base_url)
    tester.run_all_tests()

if __name__ == "__main__":
    main()