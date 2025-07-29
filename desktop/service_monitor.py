"""
Service Monitoring and Health Check System
Provides comprehensive monitoring, health checks, and alerting for TikTrue LLM Platform services
"""

import asyncio
import json
import logging
import time
import psutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ServiceMonitor")

# Create logs directory if it doesn't exist
Path('logs').mkdir(exist_ok=True)
file_handler = logging.FileHandler('logs/service_monitor.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)


class HealthStatus(Enum):
    """Health status enumeration"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Health check result data structure"""
    name: str
    status: HealthStatus
    message: str
    timestamp: datetime
    metrics: Dict[str, Any]
    duration_ms: float


@dataclass
class ServiceMetrics:
    """Service metrics data structure"""
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    disk_usage_percent: float
    network_connections: int
    uptime_seconds: float
    timestamp: datetime


class HealthChecker:
    """Individual health check implementation"""
    
    def __init__(self, name: str, check_function: Callable, interval_seconds: int = 60):
        self.name = name
        self.check_function = check_function
        self.interval_seconds = interval_seconds
        self.last_result: Optional[HealthCheckResult] = None
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
    
    def start(self):
        """Start the health check"""
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self._run_checks, daemon=True)
            self.thread.start()
            logger.info(f"Started health check: {self.name}")
    
    def stop(self):
        """Stop the health check"""
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        logger.info(f"Stopped health check: {self.name}")
    
    def _run_checks(self):
        """Run health checks in a loop"""
        while self.is_running:
            try:
                start_time = time.time()
                result = self.check_function()
                duration_ms = (time.time() - start_time) * 1000
                
                # Create health check result
                self.last_result = HealthCheckResult(
                    name=self.name,
                    status=result.get("status", HealthStatus.UNKNOWN),
                    message=result.get("message", ""),
                    timestamp=datetime.now(),
                    metrics=result.get("metrics", {}),
                    duration_ms=duration_ms
                )
                
                logger.debug(f"Health check {self.name}: {self.last_result.status.value}")
                
            except Exception as e:
                logger.error(f"Health check {self.name} failed: {e}")
                self.last_result = HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.CRITICAL,
                    message=f"Health check failed: {e}",
                    timestamp=datetime.now(),
                    metrics={},
                    duration_ms=0
                )
            
            # Wait for next check
            time.sleep(self.interval_seconds)


class ServiceMonitor:
    """Main service monitoring system"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._get_default_config()
        self.health_checkers: Dict[str, HealthChecker] = {}
        self.is_running = False
        self.metrics_history: List[ServiceMetrics] = []
        self.max_history_size = self.config.get("max_history_size", 1000)
        
        # Initialize built-in health checks
        self._initialize_health_checks()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default monitoring configuration"""
        return {
            "monitoring_interval": 30,
            "health_check_interval": 60,
            "max_history_size": 1000,
            "alert_thresholds": {
                "cpu_percent": 80.0,
                "memory_percent": 85.0,
                "disk_usage_percent": 90.0
            },
            "enabled_checks": [
                "system_resources",
                "disk_space",
                "network_connectivity",
                "service_process"
            ]
        }
    
    def _initialize_health_checks(self):
        """Initialize built-in health checks"""
        enabled_checks = self.config.get("enabled_checks", [])
        
        if "system_resources" in enabled_checks:
            self.add_health_check("system_resources", self._check_system_resources)
        
        if "disk_space" in enabled_checks:
            self.add_health_check("disk_space", self._check_disk_space)
        
        if "network_connectivity" in enabled_checks:
            self.add_health_check("network_connectivity", self._check_network_connectivity)
        
        if "service_process" in enabled_checks:
            self.add_health_check("service_process", self._check_service_process)
    
    def add_health_check(self, name: str, check_function: Callable, interval_seconds: Optional[int] = None):
        """Add a custom health check"""
        interval = interval_seconds or self.config.get("health_check_interval", 60)
        
        health_checker = HealthChecker(name, check_function, interval)
        self.health_checkers[name] = health_checker
        
        if self.is_running:
            health_checker.start()
        
        logger.info(f"Added health check: {name}")
    
    def remove_health_check(self, name: str):
        """Remove a health check"""
        if name in self.health_checkers:
            self.health_checkers[name].stop()
            del self.health_checkers[name]
            logger.info(f"Removed health check: {name}")
    
    def start_monitoring(self):
        """Start the monitoring system"""
        if not self.is_running:
            self.is_running = True
            
            # Start all health checkers
            for checker in self.health_checkers.values():
                checker.start()
            
            # Start metrics collection
            self.metrics_thread = threading.Thread(target=self._collect_metrics, daemon=True)
            self.metrics_thread.start()
            
            logger.info("Service monitoring started")
    
    def stop_monitoring(self):
        """Stop the monitoring system"""
        if self.is_running:
            self.is_running = False
            
            # Stop all health checkers
            for checker in self.health_checkers.values():
                checker.stop()
            
            # Wait for metrics thread to finish
            if hasattr(self, 'metrics_thread') and self.metrics_thread.is_alive():
                self.metrics_thread.join(timeout=5)
            
            logger.info("Service monitoring stopped")
    
    def _collect_metrics(self):
        """Collect system metrics"""
        while self.is_running:
            try:
                # Get current process
                current_process = psutil.Process()
                
                # Collect metrics
                metrics = ServiceMetrics(
                    cpu_percent=current_process.cpu_percent(),
                    memory_mb=current_process.memory_info().rss / 1024 / 1024,
                    memory_percent=current_process.memory_percent(),
                    disk_usage_percent=psutil.disk_usage('/').percent,
                    network_connections=len(current_process.connections()),
                    uptime_seconds=time.time() - current_process.create_time(),
                    timestamp=datetime.now()
                )
                
                # Add to history
                self.metrics_history.append(metrics)
                
                # Trim history if needed
                if len(self.metrics_history) > self.max_history_size:
                    self.metrics_history = self.metrics_history[-self.max_history_size:]
                
                logger.debug(f"Collected metrics: CPU {metrics.cpu_percent}%, Memory {metrics.memory_mb:.1f}MB")
                
            except Exception as e:
                logger.error(f"Failed to collect metrics: {e}")
            
            # Wait for next collection
            time.sleep(self.config.get("monitoring_interval", 30))
    
    def _check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            thresholds = self.config.get("alert_thresholds", {})
            cpu_threshold = thresholds.get("cpu_percent", 80.0)
            memory_threshold = thresholds.get("memory_percent", 85.0)
            
            status = HealthStatus.HEALTHY
            messages = []
            
            if cpu_percent > cpu_threshold:
                status = HealthStatus.WARNING if cpu_percent < cpu_threshold + 10 else HealthStatus.CRITICAL
                messages.append(f"High CPU usage: {cpu_percent:.1f}%")
            
            if memory.percent > memory_threshold:
                status = HealthStatus.WARNING if memory.percent < memory_threshold + 5 else HealthStatus.CRITICAL
                messages.append(f"High memory usage: {memory.percent:.1f}%")
            
            message = "; ".join(messages) if messages else "System resources normal"
            
            return {
                "status": status,
                "message": message,
                "metrics": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_available_gb": memory.available / 1024 / 1024 / 1024
                }
            }
            
        except Exception as e:
            return {
                "status": HealthStatus.CRITICAL,
                "message": f"Failed to check system resources: {e}",
                "metrics": {}
            }
    
    def _check_disk_space(self) -> Dict[str, Any]:
        """Check disk space usage"""
        try:
            disk_usage = psutil.disk_usage('/')
            usage_percent = (disk_usage.used / disk_usage.total) * 100
            
            threshold = self.config.get("alert_thresholds", {}).get("disk_usage_percent", 90.0)
            
            if usage_percent > threshold:
                status = HealthStatus.CRITICAL
                message = f"Low disk space: {usage_percent:.1f}% used"
            elif usage_percent > threshold - 10:
                status = HealthStatus.WARNING
                message = f"Disk space getting low: {usage_percent:.1f}% used"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk space normal: {usage_percent:.1f}% used"
            
            return {
                "status": status,
                "message": message,
                "metrics": {
                    "disk_usage_percent": usage_percent,
                    "free_space_gb": disk_usage.free / 1024 / 1024 / 1024,
                    "total_space_gb": disk_usage.total / 1024 / 1024 / 1024
                }
            }
            
        except Exception as e:
            return {
                "status": HealthStatus.CRITICAL,
                "message": f"Failed to check disk space: {e}",
                "metrics": {}
            }
    
    def _check_network_connectivity(self) -> Dict[str, Any]:
        """Check network connectivity"""
        try:
            # Check if we have network interfaces up
            network_stats = psutil.net_if_stats()
            active_interfaces = [name for name, stats in network_stats.items() if stats.isup]
            
            if not active_interfaces:
                return {
                    "status": HealthStatus.CRITICAL,
                    "message": "No active network interfaces",
                    "metrics": {"active_interfaces": 0}
                }
            
            # Check network connections
            connections = psutil.net_connections()
            established_connections = [conn for conn in connections if conn.status == 'ESTABLISHED']
            
            return {
                "status": HealthStatus.HEALTHY,
                "message": f"Network connectivity normal ({len(active_interfaces)} interfaces, {len(established_connections)} connections)",
                "metrics": {
                    "active_interfaces": len(active_interfaces),
                    "established_connections": len(established_connections),
                    "total_connections": len(connections)
                }
            }
            
        except Exception as e:
            return {
                "status": HealthStatus.CRITICAL,
                "message": f"Failed to check network connectivity: {e}",
                "metrics": {}
            }
    
    def _check_service_process(self) -> Dict[str, Any]:
        """Check service process health"""
        try:
            current_process = psutil.Process()
            
            # Check if process is running normally
            if current_process.status() == psutil.STATUS_RUNNING:
                status = HealthStatus.HEALTHY
                message = f"Service process running normally (PID: {current_process.pid})"
            else:
                status = HealthStatus.WARNING
                message = f"Service process status: {current_process.status()}"
            
            # Get process metrics
            memory_info = current_process.memory_info()
            
            return {
                "status": status,
                "message": message,
                "metrics": {
                    "pid": current_process.pid,
                    "status": current_process.status(),
                    "cpu_percent": current_process.cpu_percent(),
                    "memory_rss_mb": memory_info.rss / 1024 / 1024,
                    "memory_vms_mb": memory_info.vms / 1024 / 1024,
                    "num_threads": current_process.num_threads(),
                    "create_time": current_process.create_time()
                }
            }
            
        except Exception as e:
            return {
                "status": HealthStatus.CRITICAL,
                "message": f"Failed to check service process: {e}",
                "metrics": {}
            }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status"""
        try:
            overall_status = HealthStatus.HEALTHY
            health_results = {}
            
            # Collect all health check results
            for name, checker in self.health_checkers.items():
                if checker.last_result:
                    health_results[name] = asdict(checker.last_result)
                    
                    # Determine overall status (worst case)
                    if checker.last_result.status == HealthStatus.CRITICAL:
                        overall_status = HealthStatus.CRITICAL
                    elif checker.last_result.status == HealthStatus.WARNING and overall_status != HealthStatus.CRITICAL:
                        overall_status = HealthStatus.WARNING
                else:
                    health_results[name] = {
                        "name": name,
                        "status": HealthStatus.UNKNOWN.value,
                        "message": "No results yet",
                        "timestamp": datetime.now().isoformat(),
                        "metrics": {},
                        "duration_ms": 0
                    }
            
            # Get latest metrics
            latest_metrics = None
            if self.metrics_history:
                latest_metrics = asdict(self.metrics_history[-1])
                # Convert datetime to string for JSON serialization
                latest_metrics["timestamp"] = latest_metrics["timestamp"].isoformat()
            
            return {
                "overall_status": overall_status.value,
                "health_checks": health_results,
                "latest_metrics": latest_metrics,
                "monitoring_active": self.is_running,
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get health status: {e}")
            return {
                "overall_status": HealthStatus.CRITICAL.value,
                "error": str(e),
                "last_updated": datetime.now().isoformat()
            }
    
    def get_metrics_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get metrics history for specified hours"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            filtered_metrics = [
                asdict(metrics) for metrics in self.metrics_history
                if metrics.timestamp >= cutoff_time
            ]
            
            # Convert datetime to string for JSON serialization
            for metrics in filtered_metrics:
                metrics["timestamp"] = metrics["timestamp"].isoformat()
            
            return filtered_metrics
            
        except Exception as e:
            logger.error(f"Failed to get metrics history: {e}")
            return []
    
    def export_health_report(self, filepath: Optional[str] = None) -> str:
        """Export comprehensive health report"""
        try:
            report = {
                "report_timestamp": datetime.now().isoformat(),
                "service_info": {
                    "monitoring_active": self.is_running,
                    "config": self.config,
                    "health_checkers": list(self.health_checkers.keys())
                },
                "current_status": self.get_health_status(),
                "metrics_summary": {
                    "total_metrics_collected": len(self.metrics_history),
                    "metrics_history_hours": 24
                },
                "recent_metrics": self.get_metrics_history(hours=1)  # Last hour
            }
            
            # Generate filename if not provided
            if not filepath:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filepath = f"logs/health_report_{timestamp}.json"
            
            # Ensure directory exists
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            
            # Write report
            with open(filepath, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            logger.info(f"Health report exported to: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Failed to export health report: {e}")
            raise


# Global service monitor instance
_service_monitor: Optional[ServiceMonitor] = None


def get_service_monitor(config: Optional[Dict[str, Any]] = None) -> ServiceMonitor:
    """Get or create global service monitor instance"""
    global _service_monitor
    
    if _service_monitor is None:
        _service_monitor = ServiceMonitor(config)
    
    return _service_monitor


def start_monitoring(config: Optional[Dict[str, Any]] = None):
    """Start service monitoring"""
    monitor = get_service_monitor(config)
    monitor.start_monitoring()


def stop_monitoring():
    """Stop service monitoring"""
    global _service_monitor
    
    if _service_monitor:
        _service_monitor.stop_monitoring()


def get_health_status() -> Dict[str, Any]:
    """Get current health status"""
    monitor = get_service_monitor()
    return monitor.get_health_status()


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "start":
            print("Starting service monitoring...")
            start_monitoring()
            
            try:
                # Keep running
                while True:
                    time.sleep(10)
                    status = get_health_status()
                    print(f"Overall status: {status['overall_status']}")
            except KeyboardInterrupt:
                print("Stopping monitoring...")
                stop_monitoring()
        
        elif command == "status":
            monitor = get_service_monitor()
            status = monitor.get_health_status()
            print(json.dumps(status, indent=2))
        
        elif command == "report":
            monitor = get_service_monitor()
            filepath = monitor.export_health_report()
            print(f"Health report exported to: {filepath}")
        
        else:
            print("Usage: python service_monitor.py [start|status|report]")
    else:
        print("Usage: python service_monitor.py [start|status|report]")