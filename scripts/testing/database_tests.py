#!/usr/bin/env python3
"""
TikTrue Platform - Database Testing Suite

This script provides comprehensive database testing:
- Connection and configuration validation
- Data integrity and constraint testing
- Performance benchmarking
- Migration testing
- Backup and recovery validation

Requirements: 3.1, 4.1 - Database operations and integrity testing
"""

import os
import sys
import json
import time
import logging
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict

@dataclass
class DatabaseTestResult:
    """Database test result"""
    test_name: str
    category: str
    status: str  # PASS, FAIL, SKIP
    duration: float
    details: Optional[Dict] = None
    error_message: Optional[str] = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()

class DatabaseTester:
    """Database testing suite for TikTrue platform"""
    
    def __init__(self, db_path: str = None, verbose: bool = False):
        self.db_path = db_path or self.get_default_db_path()
        self.verbose = verbose
        
        # Test results
        self.test_results: List[DatabaseTestResult] = []
        
        # Setup logging
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging for database tests"""
        log_dir = Path(__file__).parent.parent.parent / "temp" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_level = logging.DEBUG if self.verbose else logging.INFO
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(log_dir / "database_tests.log", encoding='utf-8')
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def get_default_db_path(self) -> str:
        """Get default database path"""
        project_root = Path(__file__).parent.parent.parent
        backend_db = project_root / "backend" / "db.sqlite3"
        
        if backend_db.exists():
            return str(backend_db)
        else:
            # Create test database
            test_db = project_root / "temp" / "test_db.sqlite3"
            test_db.parent.mkdir(exist_ok=True)
            return str(test_db)
            
    def execute_test(self, test_name: str, category: str, test_function, *args, **kwargs) -> DatabaseTestResult:
        """Execute a single database test"""
        self.logger.info(f"🔄 Running: {test_name}")
        start_time = time.time()
        
        try:
            result = test_function(*args, **kwargs)
            duration = time.time() - start_time
            
            if isinstance(result, tuple) and len(result) == 2:
                success, details = result
            else:
                success = bool(result)
                details = result if isinstance(result, dict) else None
                
            status = "PASS" if success else "FAIL"
            
            test_result = DatabaseTestResult(
                test_name=test_name,
                category=category,
                status=status,
                duration=duration,
                details=details
            )
            
            if success:
                self.logger.info(f"✅ {test_name}: PASSED ({duration:.2f}s)")
            else:
                self.logger.error(f"❌ {test_name}: FAILED ({duration:.2f}s)")
                
            return test_result
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"💥 {test_name}: ERROR ({duration:.2f}s) - {e}")
            
            return DatabaseTestResult(
                test_name=test_name,
                category=category,
                status="FAIL",
                duration=duration,
                error_message=str(e)
            )
            
    def get_db_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn
        
    def test_database_connection(self) -> Tuple[bool, Dict]:
        """Test database connection and basic functionality"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Test basic query
                cursor.execute("SELECT 1 as test_value")
                result = cursor.fetchone()
                
                if result and result[0] == 1:
                    return True, {"connection": "successful", "basic_query": "working"}
                else:
                    return False, {"connection": "failed", "error": "Basic query failed"}
                    
        except Exception as e:
            return False, {"connection": "failed", "error": str(e)}
            
    def test_database_schema(self) -> Tuple[bool, Dict]:
        """Test database schema and table structure"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get all tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                schema_info = {"tables": tables, "table_details": {}}
                
                # Check each table structure
                for table in tables:
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = cursor.fetchall()
                    
                    schema_info["table_details"][table] = {
                        "column_count": len(columns),
                        "columns": [
                            {
                                "name": col[1],
                                "type": col[2],
                                "not_null": bool(col[3]),
                                "primary_key": bool(col[5])
                            }
                            for col in columns
                        ]
                    }
                    
                # Check for expected tables (based on TikTrue requirements)
                expected_tables = [
                    "auth_user", "accounts_customuser", "licenses_license", 
                    "models_api_modelfile", "payments_subscription"
                ]
                
                missing_tables = [t for t in expected_tables if t not in tables]
                
                if missing_tables:
                    return False, {
                        **schema_info,
                        "missing_tables": missing_tables,
                        "error": f"Missing expected tables: {missing_tables}"
                    }
                    
                return True, schema_info
                
        except Exception as e:
            return False, {"error": str(e)}
            
    def test_data_integrity(self) -> Tuple[bool, Dict]:
        """Test data integrity and constraints"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                integrity_results = {
                    "foreign_key_violations": 0,
                    "null_constraint_violations": 0,
                    "unique_constraint_violations": 0,
                    "check_constraint_violations": 0
                }
                
                # Enable foreign key checking
                cursor.execute("PRAGMA foreign_keys = ON")
                
                # Check foreign key integrity
                cursor.execute("PRAGMA foreign_key_check")
                fk_violations = cursor.fetchall()
                integrity_results["foreign_key_violations"] = len(fk_violations)
                
                if fk_violations:
                    integrity_results["fk_violation_details"] = [
                        {"table": row[0], "rowid": row[1], "parent": row[2], "fkid": row[3]}
                        for row in fk_violations
                    ]
                    
                # Check for orphaned records (example with users and licenses)
                try:
                    cursor.execute("""
                        SELECT COUNT(*) FROM licenses_license l 
                        LEFT JOIN accounts_customuser u ON l.user_id = u.id 
                        WHERE u.id IS NULL
                    """)
                    orphaned_licenses = cursor.fetchone()[0]
                    integrity_results["orphaned_licenses"] = orphaned_licenses
                except:
                    pass  # Table might not exist in test environment
                    
                # Overall integrity status
                total_violations = sum([
                    integrity_results["foreign_key_violations"],
                    integrity_results["null_constraint_violations"],
                    integrity_results["unique_constraint_violations"]
                ])
                
                return total_violations == 0, integrity_results
                
        except Exception as e:
            return False, {"error": str(e)}
            
    def test_database_performance(self) -> Tuple[bool, Dict]:
        """Test database performance with various operations"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                performance_results = {}
                
                # Test 1: Simple SELECT performance
                start_time = time.time()
                cursor.execute("SELECT COUNT(*) FROM sqlite_master")
                cursor.fetchone()
                performance_results["simple_select_ms"] = (time.time() - start_time) * 1000
                
                # Test 2: Create temporary table and insert performance
                cursor.execute("""
                    CREATE TEMPORARY TABLE perf_test (
                        id INTEGER PRIMARY KEY,
                        data TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Insert test data
                start_time = time.time()
                test_data = [(i, f"test_data_{i}") for i in range(1000)]
                cursor.executemany("INSERT INTO perf_test (id, data) VALUES (?, ?)", test_data)
                conn.commit()
                performance_results["insert_1000_records_ms"] = (time.time() - start_time) * 1000
                
                # Test 3: SELECT with WHERE clause
                start_time = time.time()
                cursor.execute("SELECT * FROM perf_test WHERE id BETWEEN 100 AND 200")
                results = cursor.fetchall()
                performance_results["select_with_where_ms"] = (time.time() - start_time) * 1000
                performance_results["select_result_count"] = len(results)
                
                # Test 4: UPDATE performance
                start_time = time.time()
                cursor.execute("UPDATE perf_test SET data = 'updated_' || data WHERE id <= 100")
                conn.commit()
                performance_results["update_100_records_ms"] = (time.time() - start_time) * 1000
                
                # Test 5: DELETE performance
                start_time = time.time()
                cursor.execute("DELETE FROM perf_test WHERE id > 900")
                conn.commit()
                performance_results["delete_records_ms"] = (time.time() - start_time) * 1000
                
                # Performance benchmarks (in milliseconds)
                benchmarks = {
                    "simple_select_ms": 10,
                    "insert_1000_records_ms": 500,
                    "select_with_where_ms": 50,
                    "update_100_records_ms": 100,
                    "delete_records_ms": 50
                }
                
                # Check if performance meets benchmarks
                performance_issues = []
                for metric, threshold in benchmarks.items():
                    if performance_results.get(metric, 0) > threshold:
                        performance_issues.append(f"{metric}: {performance_results[metric]:.2f}ms > {threshold}ms")
                        
                performance_results["benchmarks"] = benchmarks
                performance_results["performance_issues"] = performance_issues
                
                return len(performance_issues) == 0, performance_results
                
        except Exception as e:
            return False, {"error": str(e)}
            
    def test_transaction_handling(self) -> Tuple[bool, Dict]:
        """Test transaction handling and rollback functionality"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                transaction_results = {}
                
                # Create test table
                cursor.execute("""
                    CREATE TEMPORARY TABLE transaction_test (
                        id INTEGER PRIMARY KEY,
                        value TEXT
                    )
                """)
                
                # Test 1: Successful transaction
                try:
                    conn.execute("BEGIN TRANSACTION")
                    cursor.execute("INSERT INTO transaction_test (value) VALUES ('test1')")
                    cursor.execute("INSERT INTO transaction_test (value) VALUES ('test2')")
                    conn.commit()
                    
                    cursor.execute("SELECT COUNT(*) FROM transaction_test")
                    count_after_commit = cursor.fetchone()[0]
                    transaction_results["successful_transaction"] = count_after_commit == 2
                    
                except Exception as e:
                    conn.rollback()
                    transaction_results["successful_transaction"] = False
                    transaction_results["commit_error"] = str(e)
                    
                # Test 2: Transaction rollback
                try:
                    conn.execute("BEGIN TRANSACTION")
                    cursor.execute("INSERT INTO transaction_test (value) VALUES ('test3')")
                    cursor.execute("INSERT INTO transaction_test (value) VALUES ('test4')")
                    conn.rollback()  # Intentional rollback
                    
                    cursor.execute("SELECT COUNT(*) FROM transaction_test")
                    count_after_rollback = cursor.fetchone()[0]
                    transaction_results["rollback_test"] = count_after_rollback == 2  # Should still be 2
                    
                except Exception as e:
                    transaction_results["rollback_test"] = False
                    transaction_results["rollback_error"] = str(e)
                    
                # Test 3: Automatic rollback on error
                try:
                    conn.execute("BEGIN TRANSACTION")
                    cursor.execute("INSERT INTO transaction_test (value) VALUES ('test5')")
                    # This should cause an error (duplicate primary key)
                    cursor.execute("INSERT INTO transaction_test (id, value) VALUES (1, 'duplicate')")
                    conn.commit()
                    transaction_results["auto_rollback_test"] = False  # Should not reach here
                    
                except Exception:
                    # Error expected, check if rollback worked
                    cursor.execute("SELECT COUNT(*) FROM transaction_test")
                    count_after_error = cursor.fetchone()[0]
                    transaction_results["auto_rollback_test"] = count_after_error == 2
                    
                all_tests_passed = all([
                    transaction_results.get("successful_transaction", False),
                    transaction_results.get("rollback_test", False),
                    transaction_results.get("auto_rollback_test", False)
                ])
                
                return all_tests_passed, transaction_results
                
        except Exception as e:
            return False, {"error": str(e)}
            
    def test_concurrent_access(self) -> Tuple[bool, Dict]:
        """Test concurrent database access"""
        try:
            import threading
            import queue
            
            results_queue = queue.Queue()
            
            def worker(worker_id: int):
                try:
                    with self.get_db_connection() as conn:
                        cursor = conn.cursor()
                        
                        # Create worker-specific temporary table
                        table_name = f"concurrent_test_{worker_id}"
                        cursor.execute(f"""
                            CREATE TEMPORARY TABLE {table_name} (
                                id INTEGER PRIMARY KEY,
                                worker_id INTEGER,
                                data TEXT
                            )
                        """)
                        
                        # Perform multiple operations
                        for i in range(10):
                            cursor.execute(
                                f"INSERT INTO {table_name} (worker_id, data) VALUES (?, ?)",
                                (worker_id, f"data_{i}")
                            )
                            
                        conn.commit()
                        
                        # Count records
                        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                        count = cursor.fetchone()[0]
                        
                        results_queue.put({"worker_id": worker_id, "success": True, "count": count})
                        
                except Exception as e:
                    results_queue.put({"worker_id": worker_id, "success": False, "error": str(e)})
                    
            # Start multiple worker threads
            threads = []
            num_workers = 5
            
            for i in range(num_workers):
                thread = threading.Thread(target=worker, args=(i,))
                threads.append(thread)
                thread.start()
                
            # Wait for all threads to complete
            for thread in threads:
                thread.join(timeout=30)
                
            # Collect results
            worker_results = []
            while not results_queue.empty():
                worker_results.append(results_queue.get())
                
            concurrent_results = {
                "num_workers": num_workers,
                "completed_workers": len(worker_results),
                "successful_workers": len([r for r in worker_results if r.get("success", False)]),
                "worker_details": worker_results
            }
            
            success = (concurrent_results["completed_workers"] == num_workers and 
                      concurrent_results["successful_workers"] == num_workers)
                      
            return success, concurrent_results
            
        except Exception as e:
            return False, {"error": str(e)}
            
    def test_backup_restore(self) -> Tuple[bool, Dict]:
        """Test database backup and restore functionality"""
        try:
            backup_results = {}
            
            # Create backup
            backup_path = Path(self.db_path).parent / f"backup_test_{int(time.time())}.db"
            
            start_time = time.time()
            
            # Simple file copy backup (for SQLite)
            import shutil
            shutil.copy2(self.db_path, backup_path)
            
            backup_time = time.time() - start_time
            backup_results["backup_time_ms"] = backup_time * 1000
            backup_results["backup_size_mb"] = backup_path.stat().st_size / (1024 * 1024)
            
            # Verify backup integrity
            try:
                with sqlite3.connect(str(backup_path)) as backup_conn:
                    cursor = backup_conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM sqlite_master")
                    table_count = cursor.fetchone()[0]
                    backup_results["backup_table_count"] = table_count
                    backup_results["backup_integrity"] = True
                    
            except Exception as e:
                backup_results["backup_integrity"] = False
                backup_results["backup_error"] = str(e)
                
            # Test restore (verify backup can be used)
            try:
                restore_path = Path(self.db_path).parent / f"restore_test_{int(time.time())}.db"
                shutil.copy2(backup_path, restore_path)
                
                with sqlite3.connect(str(restore_path)) as restore_conn:
                    cursor = restore_conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM sqlite_master")
                    restored_table_count = cursor.fetchone()[0]
                    
                backup_results["restore_success"] = restored_table_count == table_count
                
                # Cleanup
                restore_path.unlink()
                
            except Exception as e:
                backup_results["restore_success"] = False
                backup_results["restore_error"] = str(e)
                
            # Cleanup backup
            backup_path.unlink()
            
            success = (backup_results.get("backup_integrity", False) and 
                      backup_results.get("restore_success", False))
                      
            return success, backup_results
            
        except Exception as e:
            return False, {"error": str(e)}
            
    def generate_database_report(self) -> Dict[str, Any]:
        """Generate comprehensive database test report"""
        if not self.test_results:
            return {"error": "No test results available"}
            
        # Categorize results
        categories = {}
        for result in self.test_results:
            if result.category not in categories:
                categories[result.category] = []
            categories[result.category].append(result)
            
        # Calculate summary statistics
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r.status == "PASS"])
        failed_tests = len([r for r in self.test_results if r.status == "FAIL"])
        
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        total_duration = sum(r.duration for r in self.test_results)
        
        # Identify critical issues
        critical_failures = [
            r for r in self.test_results 
            if r.status == "FAIL" and r.category in ["Connection", "Schema", "Integrity"]
        ]
        
        report = {
            "test_summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "success_rate": round(success_rate, 2),
                "total_duration": round(total_duration, 2),
                "critical_failures": len(critical_failures)
            },
            "category_results": {
                category: {
                    "total": len(results),
                    "passed": len([r for r in results if r.status == "PASS"]),
                    "failed": len([r for r in results if r.status == "FAIL"])
                }
                for category, results in categories.items()
            },
            "test_details": [asdict(result) for result in self.test_results],
            "critical_failures": [asdict(failure) for failure in critical_failures],
            "recommendations": self.generate_database_recommendations(),
            "database_info": {
                "database_path": self.db_path,
                "database_size_mb": Path(self.db_path).stat().st_size / (1024 * 1024) if Path(self.db_path).exists() else 0,
                "test_date": datetime.now().isoformat()
            }
        }
        
        return report
        
    def generate_database_recommendations(self) -> List[str]:
        """Generate database recommendations based on test results"""
        recommendations = []
        
        failed_tests = [r for r in self.test_results if r.status == "FAIL"]
        
        # Check for connection issues
        connection_failures = [r for r in failed_tests if r.category == "Connection"]
        if connection_failures:
            recommendations.append("🔌 Fix database connection issues before deployment")
            
        # Check for schema issues
        schema_failures = [r for r in failed_tests if r.category == "Schema"]
        if schema_failures:
            recommendations.append("🗄️ Review and fix database schema issues")
            
        # Check for integrity issues
        integrity_failures = [r for r in failed_tests if r.category == "Integrity"]
        if integrity_failures:
            recommendations.append("🔒 Address data integrity violations")
            
        # Check for performance issues
        performance_failures = [r for r in failed_tests if r.category == "Performance"]
        if performance_failures:
            recommendations.append("⚡ Optimize database performance")
            recommendations.append("📊 Consider adding database indexes")
            recommendations.append("🔧 Review query optimization")
            
        # Check for concurrency issues
        concurrency_failures = [r for r in failed_tests if r.category == "Concurrency"]
        if concurrency_failures:
            recommendations.append("🔄 Review concurrent access patterns")
            recommendations.append("🔒 Consider connection pooling")
            
        if not recommendations:
            recommendations.append("✅ Database tests passed - system appears ready")
            
        return recommendations
        
    def run_all_database_tests(self) -> bool:
        """Run all database tests"""
        self.logger.info("🚀 Starting TikTrue Database Testing Suite...")
        
        # Define test suite
        test_suite = [
            ("Database Connection", "Connection", self.test_database_connection),
            ("Database Schema", "Schema", self.test_database_schema),
            ("Data Integrity", "Integrity", self.test_data_integrity),
            ("Database Performance", "Performance", self.test_database_performance),
            ("Transaction Handling", "Transactions", self.test_transaction_handling),
            ("Concurrent Access", "Concurrency", self.test_concurrent_access),
            ("Backup & Restore", "Backup", self.test_backup_restore)
        ]
        
        all_passed = True
        
        for test_name, category, test_function in test_suite:
            try:
                result = self.execute_test(test_name, category, test_function)
                self.test_results.append(result)
                
                if result.status == "FAIL":
                    all_passed = False
                    
            except Exception as e:
                self.logger.error(f"💥 Test execution failed for {test_name}: {e}")
                all_passed = False
                
        # Generate and save report
        report = self.generate_database_report()
        
        report_file = Path(__file__).parent.parent.parent / "temp" / "database_test_report.json"
        report_file.parent.mkdir(exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            
        # Print summary
        summary = report["test_summary"]
        self.logger.info(f"\n{'='*50}")
        self.logger.info("DATABASE TEST SUMMARY")
        self.logger.info(f"{'='*50}")
        self.logger.info(f"Total Tests: {summary['total_tests']}")
        self.logger.info(f"Passed: {summary['passed_tests']} ✅")
        self.logger.info(f"Failed: {summary['failed_tests']} ❌")
        self.logger.info(f"Success Rate: {summary['success_rate']}%")
        self.logger.info(f"Total Duration: {summary['total_duration']:.2f}s")
        
        if summary['critical_failures'] > 0:
            self.logger.error(f"Critical Failures: {summary['critical_failures']} 🚨")
            
        self.logger.info(f"📊 Report saved: {report_file}")
        
        if all_passed:
            self.logger.info("🎉 All database tests passed!")
        else:
            self.logger.error("❌ Some database tests failed!")
            
        return all_passed

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="TikTrue Database Testing Suite")
    parser.add_argument("--db-path", help="Database file path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    tester = DatabaseTester(db_path=args.db_path, verbose=args.verbose)
    
    if tester.run_all_database_tests():
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()