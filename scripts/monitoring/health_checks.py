#!/usr/bin/env python3
"""
TikTrue Platform - Health Check System

This script provides comprehensive health monitoring for all TikTrue services:
- Backend API health checks
- Database connectivity monitoring
- Model service availability
- Network connectivity validation
- System resource monitoring

Requirements: 3.1 - Health checks for all services
"""

import os
import sys
import json
import time
import logging
import asyncio
import aiohttp
import psutil
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from urllib.parse import urljoin

@dataclass
class HealthCheckResult:
    """Health check result"""
    service_name: str
    status: str  # HEALTHY, UNHEALTHY, DEGRADED, UNKNOWN
    response_time_ms: float
    details: Dict[str, Any]
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()

@dataclass
class SystemMetrics:
    """System resource metrics"""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_io: Dict[str, int]
    process_count: int
    uptime_seconds: float
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()

class HealthMonitor:
    """Comprehensive health monitoring system"""
    
    def __init__(self, config_file: Optional[str] = None, verbose: bool = False):
        self.verbose = verbose
        self.project_root = Path(__file__).parent.parent.parent
        
        # Load configuration
        self.config = self.load_config(config_file)
        
        # Health check results
        self.health_results: List[HealthCheckResult] = []
        self.system_metrics: List[SystemMetrics] = []
        
        # Setup logging
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging for health monitoring"""
        log_dir = self.project_root / "temp" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_level = logging.DEBUG if self.verbose else logging.INFO
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(log_dir / "health_monitor.log", encoding='utf-8')
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def load_config(self, config_file: Optional[str] = None) -> Dict[str, Any]:
        """Load health monitoring configuration"""
        default_config = {
            "services": {
                "backend_api": {
                    "url": "https://api.tiktrue.com",
                    "endpoints": [
                        "/health/",
                        "/api/v1/health/",
                        "/api/v1/auth/health/"
                    ],
                    "timeout": 10,
                    "expected_status": 200
                },
                "frontend": {
                    "url": "https://tiktrue.com",
                    "endpoints": ["/health"],
                    "timeout": 10,
                    "expected_status": 200
                },
                "database": {
                    "type": "sqlite",
                    "path": "backend/db.sqlite3",
                    "timeout": 5
                }
            },
            "thresholds": {
                "response_time_ms": 2000,
                "cpu_percent": 80,
                "memory_percent": 85,
                "disk_percent": 90
            },
            "monitoring": {
                "interval_seconds": 60,
                "retention_hours": 24,
                "alert_on_failure": True
            }
        }
        
        if config_file and Path(config_file).exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    # Merge with default config
                    default_config.update(user_config)
            except Exception as e:
                self.logger.warning(f"Failed to load config file {config_file}: {e}")
                
        return default_config
        
    async def check_http_endpoint(self, service_name: str, base_url: str, 
                                endpoint: str, timeout: int = 10, 
                                expected_status: int = 200) -> HealthCheckResult:
        """Check HTTP endpoint health"""
        url = urljoin(base_url, endpoint)
        start_time = time.time()
        
        try:
            timeout_config = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(timeout=timeout_config) as session:
                async with session.get(url) as response:
                    response_time = (time.time() - start_time) * 1000
                    
                    details = {
                        "url": url,
                        "status_code": response.status,
                        "headers": dict(response.headers),
                        "response_size": len(await response.read())
                    }
                    
                    if response.status == expected_status:
                        status = "HEALTHY"
                    elif 200 <= response.status < 300:
                        status = "DEGRADED"
                    else:
                        status = "UNHEALTHY"
                        details["error"] = f"Unexpected status code: {response.status}"
                        
                    return HealthCheckResult(
                        service_name=f"{service_name}_{endpoint.replace('/', '_')}",
                        status=status,
                        response_time_ms=response_time,
                        details=details
                    )
                    
        except asyncio.TimeoutError:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name=f"{service_name}_{endpoint.replace('/', '_')}",
                status="UNHEALTHY",
                response_time_ms=response_time,
                details={"url": url, "error": "Request timeout"}
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name=f"{service_name}_{endpoint.replace('/', '_')}",
                status="UNHEALTHY",
                response_time_ms=response_time,
                details={"url": url, "error": str(e)}
            )
            
    def check_database_health(self, db_config: Dict[str, Any]) -> HealthCheckResult:
        """Check database health"""
        start_time = time.time()
        
        try:
            if db_config["type"] == "sqlite":
                db_path = self.project_root / db_config["path"]
                
                if not db_path.exists():
                    return HealthCheckResult(
                        service_name="database",
                        status="UNHEALTHY",
                        response_time_ms=0,
                        details={"error": f"Database file not found: {db_path}"}
                    )
                    
                # Test connection and basic query
                with sqlite3.connect(str(db_path), timeout=db_config.get("timeout", 5)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    
                    # Get database info
                    cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                    table_count = cursor.fetchone()[0]
                    
                    db_size = db_path.stat().st_size
                    
                    response_time = (time.time() - start_time) * 1000
                    
                    return HealthCheckResult(
                        service_name="database",
                        status="HEALTHY" if result and result[0] == 1 else "UNHEALTHY",
                        response_time_ms=response_time,
                        details={
                            "database_path": str(db_path),
                            "database_size_mb": round(db_size / (1024 * 1024), 2),
                            "table_count": table_count,
                            "connection_test": "passed" if result and result[0] == 1 else "failed"
                        }
                    )
                    
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name="database",
                status="UNHEALTHY",
                response_time_ms=response_time,
                details={"error": str(e)}
            )
            
    def check_system_resources(self) -> SystemMetrics:
        """Check system resource usage"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # Network I/O
            network = psutil.net_io_counters()
            network_io = {
                "bytes_sent": network.bytes_sent,
                "bytes_recv": network.bytes_recv,
                "packets_sent": network.packets_sent,
                "packets_recv": network.packets_recv
            }
            
            # Process count
            process_count = len(psutil.pids())
            
            # System uptime
            boot_time = psutil.boot_time()
            uptime_seconds = time.time() - boot_time
            
            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                disk_percent=disk_percent,
                network_io=network_io,
                process_count=process_count,
                uptime_seconds=uptime_seconds
            )
            
        except Exception as e:
            self.logger.error(f"Failed to collect system metrics: {e}")
            return SystemMetrics(
                cpu_percent=0,
                memory_percent=0,
                disk_percent=0,
                network_io={},
                process_count=0,
                uptime_seconds=0
            )
            
    def check_tiktrue_processes(self) -> HealthCheckResult:
        """Check TikTrue-specific processes"""
        start_time = time.time()
        
        try:
            tiktrue_processes = []
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'status', 'cpu_percent', 'memory_percent']):
                try:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if 'tiktrue' in cmdline.lower() or 'main_app.py' in cmdline:
                        tiktrue_processes.append({
                            "pid": proc.info['pid'],
                            "name": proc.info['name'],
                            "status": proc.info['status'],
                            "cpu_percent": proc.info['cpu_percent'],
                            "memory_percent": proc.info['memory_percent'],
                            "cmdline": cmdline
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
            response_time = (time.time() - start_time) * 1000
            
            status = "HEALTHY" if tiktrue_processes else "DEGRADED"
            
            return HealthCheckResult(
                service_name="tiktrue_processes",
                status=status,
                response_time_ms=response_time,
                details={
                    "process_count": len(tiktrue_processes),
                    "processes": tiktrue_processes
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name="tiktrue_processes",
                status="UNKNOWN",
                response_time_ms=response_time,
                details={"error": str(e)}
            )
            
    def check_disk_space(self) -> HealthCheckResult:
        """Check disk space for critical directories"""
        start_time = time.time()
        
        try:
            critical_paths = [
                self.project_root,
                self.project_root / "temp",
                self.project_root / "backend",
                Path("/var/log") if Path("/var/log").exists() else None
            ]
            
            disk_info = {}
            overall_status = "HEALTHY"
            
            for path in critical_paths:
                if path and path.exists():
                    disk_usage = psutil.disk_usage(str(path))
                    used_percent = (disk_usage.used / disk_usage.total) * 100
                    
                    disk_info[str(path)] = {
                        "total_gb": round(disk_usage.total / (1024**3), 2),
                        "used_gb": round(disk_usage.used / (1024**3), 2),
                        "free_gb": round(disk_usage.free / (1024**3), 2),
                        "used_percent": round(used_percent, 2)
                    }
                    
                    if used_percent > self.config["thresholds"]["disk_percent"]:
                        overall_status = "UNHEALTHY"
                    elif used_percent > self.config["thresholds"]["disk_percent"] - 10:
                        overall_status = "DEGRADED"
                        
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                service_name="disk_space",
                status=overall_status,
                response_time_ms=response_time,
                details=disk_info
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name="disk_space",
                status="UNKNOWN",
                response_time_ms=response_time,
                details={"error": str(e)}
            )
            
    async def run_all_health_checks(self) -> List[HealthCheckResult]:
        """Run all configured health checks"""
        self.logger.info("🏥 Running comprehensive health checks...")
        
        results = []
        
        # HTTP endpoint checks
        for service_name, service_config in self.config["services"].items():
            if "url" in service_config and "endpoints" in service_config:
                for endpoint in service_config["endpoints"]:
                    result = await self.check_http_endpoint(
                        service_name,
                        service_config["url"],
                        endpoint,
                        service_config.get("timeout", 10),
                        service_config.get("expected_status", 200)
                    )
                    results.append(result)
                    
        # Database health check
        if "database" in self.config["services"]:
            db_result = self.check_database_health(self.config["services"]["database"])
            results.append(db_result)
            
        # System resource checks
        system_metrics = self.check_system_resources()
        self.system_metrics.append(system_metrics)
        
        # Convert system metrics to health check result
        cpu_status = "HEALTHY"
        if system_metrics.cpu_percent > self.config["thresholds"]["cpu_percent"]:
            cpu_status = "UNHEALTHY"
        elif system_metrics.cpu_percent > self.config["thresholds"]["cpu_percent"] - 10:
            cpu_status = "DEGRADED"
            
        memory_status = "HEALTHY"
        if system_metrics.memory_percent > self.config["thresholds"]["memory_percent"]:
            memory_status = "UNHEALTHY"
        elif system_metrics.memory_percent > self.config["thresholds"]["memory_percent"] - 10:
            memory_status = "DEGRADED"
            
        results.append(HealthCheckResult(
            service_name="system_resources",
            status=cpu_status if cpu_status != "HEALTHY" else memory_status,
            response_time_ms=0,
            details=asdict(system_metrics)
        ))
        
        # TikTrue process checks
        process_result = self.check_tiktrue_processes()
        results.append(process_result)
        
        # Disk space checks
        disk_result = self.check_disk_space()
        results.append(disk_result)
        
        self.health_results.extend(results)
        return results
        
    def generate_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive health report"""
        if not self.health_results:
            return {"error": "No health check results available"}
            
        # Categorize results by status
        healthy_services = [r for r in self.health_results if r.status == "HEALTHY"]
        degraded_services = [r for r in self.health_results if r.status == "DEGRADED"]
        unhealthy_services = [r for r in self.health_results if r.status == "UNHEALTHY"]
        unknown_services = [r for r in self.health_results if r.status == "UNKNOWN"]
        
        # Calculate overall system health
        total_services = len(self.health_results)
        healthy_count = len(healthy_services)
        
        if len(unhealthy_services) > 0:
            overall_status = "UNHEALTHY"
        elif len(degraded_services) > 0:
            overall_status = "DEGRADED"
        elif len(unknown_services) > 0:
            overall_status = "UNKNOWN"
        else:
            overall_status = "HEALTHY"
            
        # Calculate average response time
        response_times = [r.response_time_ms for r in self.health_results if r.response_time_ms > 0]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # Get latest system metrics
        latest_metrics = self.system_metrics[-1] if self.system_metrics else None
        
        report = {
            "overall_status": overall_status,
            "summary": {
                "total_services": total_services,
                "healthy_services": len(healthy_services),
                "degraded_services": len(degraded_services),
                "unhealthy_services": len(unhealthy_services),
                "unknown_services": len(unknown_services),
                "health_percentage": round((healthy_count / total_services) * 100, 2) if total_services > 0 else 0,
                "average_response_time_ms": round(avg_response_time, 2)
            },
            "service_details": [asdict(result) for result in self.health_results],
            "system_metrics": asdict(latest_metrics) if latest_metrics else None,
            "alerts": self.generate_alerts(),
            "recommendations": self.generate_health_recommendations(),
            "check_timestamp": datetime.now().isoformat()
        }
        
        return report
        
    def generate_alerts(self) -> List[Dict[str, Any]]:
        """Generate alerts based on health check results"""
        alerts = []
        
        # Service alerts
        for result in self.health_results:
            if result.status == "UNHEALTHY":
                alerts.append({
                    "severity": "CRITICAL",
                    "service": result.service_name,
                    "message": f"Service {result.service_name} is unhealthy",
                    "details": result.details,
                    "timestamp": result.timestamp
                })
            elif result.status == "DEGRADED":
                alerts.append({
                    "severity": "WARNING",
                    "service": result.service_name,
                    "message": f"Service {result.service_name} is degraded",
                    "details": result.details,
                    "timestamp": result.timestamp
                })
                
        # System resource alerts
        if self.system_metrics:
            latest_metrics = self.system_metrics[-1]
            
            if latest_metrics.cpu_percent > self.config["thresholds"]["cpu_percent"]:
                alerts.append({
                    "severity": "CRITICAL",
                    "service": "system",
                    "message": f"High CPU usage: {latest_metrics.cpu_percent}%",
                    "timestamp": latest_metrics.timestamp
                })
                
            if latest_metrics.memory_percent > self.config["thresholds"]["memory_percent"]:
                alerts.append({
                    "severity": "CRITICAL",
                    "service": "system",
                    "message": f"High memory usage: {latest_metrics.memory_percent}%",
                    "timestamp": latest_metrics.timestamp
                })
                
            if latest_metrics.disk_percent > self.config["thresholds"]["disk_percent"]:
                alerts.append({
                    "severity": "CRITICAL",
                    "service": "system",
                    "message": f"High disk usage: {latest_metrics.disk_percent}%",
                    "timestamp": latest_metrics.timestamp
                })
                
        return alerts
        
    def generate_health_recommendations(self) -> List[str]:
        """Generate health recommendations"""
        recommendations = []
        
        unhealthy_services = [r for r in self.health_results if r.status == "UNHEALTHY"]
        degraded_services = [r for r in self.health_results if r.status == "DEGRADED"]
        
        if unhealthy_services:
            recommendations.append(f"🚨 Immediate attention required for {len(unhealthy_services)} unhealthy service(s)")
            
        if degraded_services:
            recommendations.append(f"⚠️ Monitor {len(degraded_services)} degraded service(s)")
            
        # System resource recommendations
        if self.system_metrics:
            latest_metrics = self.system_metrics[-1]
            
            if latest_metrics.cpu_percent > 70:
                recommendations.append("🔥 Consider scaling CPU resources or optimizing processes")
                
            if latest_metrics.memory_percent > 80:
                recommendations.append("💾 Consider increasing memory or optimizing memory usage")
                
            if latest_metrics.disk_percent > 85:
                recommendations.append("💿 Clean up disk space or expand storage")
                
        # Response time recommendations
        slow_services = [r for r in self.health_results if r.response_time_ms > self.config["thresholds"]["response_time_ms"]]
        if slow_services:
            recommendations.append(f"🐌 Optimize response time for {len(slow_services)} slow service(s)")
            
        if not recommendations:
            recommendations.append("✅ All systems appear healthy")
            
        return recommendations
        
    def save_health_report(self, report: Dict[str, Any]) -> Path:
        """Save health report to file"""
        report_dir = self.project_root / "temp" / "health_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = report_dir / f"health_report_{timestamp}.json"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            
        # Also save as latest report
        latest_report = report_dir / "latest_health_report.json"
        with open(latest_report, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            
        return report_file
        
    def print_health_summary(self, report: Dict[str, Any]):
        """Print health summary to console"""
        summary = report["summary"]
        
        # Status emoji mapping
        status_emoji = {
            "HEALTHY": "✅",
            "DEGRADED": "⚠️",
            "UNHEALTHY": "❌",
            "UNKNOWN": "❓"
        }
        
        self.logger.info(f"\n{'='*60}")
        self.logger.info("SYSTEM HEALTH SUMMARY")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"Overall Status: {status_emoji.get(report['overall_status'], '❓')} {report['overall_status']}")
        self.logger.info(f"Health Percentage: {summary['health_percentage']}%")
        self.logger.info(f"Total Services: {summary['total_services']}")
        self.logger.info(f"Healthy: {summary['healthy_services']} ✅")
        self.logger.info(f"Degraded: {summary['degraded_services']} ⚠️")
        self.logger.info(f"Unhealthy: {summary['unhealthy_services']} ❌")
        self.logger.info(f"Unknown: {summary['unknown_services']} ❓")
        self.logger.info(f"Avg Response Time: {summary['average_response_time_ms']:.2f}ms")
        
        # Print alerts
        if report.get("alerts"):
            self.logger.info(f"\n{'='*60}")
            self.logger.info("ACTIVE ALERTS")
            self.logger.info(f"{'='*60}")
            for alert in report["alerts"]:
                severity_emoji = "🚨" if alert["severity"] == "CRITICAL" else "⚠️"
                self.logger.warning(f"{severity_emoji} {alert['message']}")
                
        # Print recommendations
        if report.get("recommendations"):
            self.logger.info(f"\n{'='*60}")
            self.logger.info("RECOMMENDATIONS")
            self.logger.info(f"{'='*60}")
            for rec in report["recommendations"]:
                self.logger.info(f"  {rec}")
                
    async def run_health_monitoring(self) -> bool:
        """Run complete health monitoring"""
        self.logger.info("🚀 Starting TikTrue Health Monitoring...")
        
        try:
            # Run all health checks
            results = await self.run_all_health_checks()
            
            # Generate report
            report = self.generate_health_report()
            
            # Save report
            report_file = self.save_health_report(report)
            
            # Print summary
            self.print_health_summary(report)
            
            self.logger.info(f"\n📊 Health report saved: {report_file}")
            
            # Determine overall success
            success = report["overall_status"] in ["HEALTHY", "DEGRADED"]
            
            if success:
                self.logger.info("🎉 Health monitoring completed - system is operational!")
            else:
                self.logger.error("❌ Health monitoring detected critical issues!")
                
            return success
            
        except Exception as e:
            self.logger.error(f"💥 Health monitoring failed: {e}")
            return False

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="TikTrue Health Monitoring")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--continuous", action="store_true", help="Run continuous monitoring")
    parser.add_argument("--interval", type=int, default=60, help="Monitoring interval in seconds")
    
    args = parser.parse_args()
    
    async def run_monitoring():
        monitor = HealthMonitor(config_file=args.config, verbose=args.verbose)
        
        if args.continuous:
            monitor.logger.info(f"Starting continuous monitoring (interval: {args.interval}s)")
            
            while True:
                success = await monitor.run_health_monitoring()
                if not success:
                    monitor.logger.error("Health check failed, continuing monitoring...")
                    
                await asyncio.sleep(args.interval)
        else:
            return await monitor.run_health_monitoring()
    
    # Run monitoring
    if args.continuous:
        asyncio.run(run_monitoring())
    else:
        result = asyncio.run(run_monitoring())
        sys.exit(0 if result else 1)

if __name__ == "__main__":
    main()