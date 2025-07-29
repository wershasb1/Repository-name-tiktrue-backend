"""
Monitoring System for Distributed LLM Platform
Implements comprehensive event logging, license usage tracking, performance monitoring,
and resource utilization tracking with report generation
"""

import os
import json
import time
import logging
import threading
import psutil
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import statistics
from collections import defaultdict, deque
import asyncio

from security.license_validator import LicenseInfo, SubscriptionTier, LicenseStatus

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MonitoringSystem")

# Create logs directory if it doesn't exist
Path('logs').mkdir(exist_ok=True)
file_handler = logging.FileHandler('logs/monitoring_system.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)


class EventType(Enum):
    """System event types"""
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    WORKER_CONNECTED = "worker_connected"
    WORKER_DISCONNECTED = "worker_disconnected"
    MODEL_LOADED = "model_loaded"
    MODEL_UNLOADED = "model_unloaded"
    INFERENCE_REQUEST = "inference_request"
    INFERENCE_RESPONSE = "inference_response"
    LICENSE_CHECK = "license_check"
    LICENSE_EXPIRED = "license_expired"
    QUOTA_EXCEEDED = "quota_exceeded"
    ERROR_OCCURRED = "error_occurred"
    NETWORK_EVENT = "network_event"
    RESOURCE_ALERT = "resource_alert"


class EventSeverity(Enum):
    """Event severity levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MetricType(Enum):
    """Performance metric types"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class SystemEvent:
    """System event data structure"""
    event_id: str
    event_type: EventType
    severity: EventSeverity
    timestamp: datetime
    component: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    worker_id: Optional[str] = None
    model_id: Optional[str] = None
    license_hash: Optional[str] = None
    duration_ms: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceMetric:
    """Performance metric data structure"""
    metric_name: str
    metric_type: MetricType
    value: Union[int, float]
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)
    unit: str = ""
    description: str = ""


@dataclass
class ResourceUsage:
    """Resource usage data structure"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: int
    memory_available_mb: int
    disk_usage_percent: float
    disk_used_gb: float
    disk_available_gb: float
    network_bytes_sent: int
    network_bytes_recv: int
    active_connections: int
    gpu_usage_percent: Optional[float] = None
    gpu_memory_used_mb: Optional[int] = None


@dataclass
class LicenseUsageRecord:
    """License usage tracking record"""
    timestamp: datetime
    license_hash: str
    user_id: Optional[str]
    operation: str
    resource_type: str
    quota_consumed: int
    quota_remaining: int
    subscription_tier: SubscriptionTier
    feature_used: Optional[str] = None
    duration_ms: Optional[int] = None
    success: bool = True
    error_message: Optional[str] = None


class MonitoringDatabase:
    """SQLite database for monitoring data storage"""
    
    def __init__(self, db_path: str = "monitoring.db"):
        """Initialize monitoring database"""
        self.db_path = db_path
        self.connection = None
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize database tables"""
        try:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.execute("PRAGMA journal_mode=WAL")
            
            # Create tables
            self._create_events_table()
            self._create_metrics_table()
            self._create_resource_usage_table()
            self._create_license_usage_table()
            
            logger.info(f"Monitoring database initialized: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize monitoring database: {e}")
            raise
    
    def _create_events_table(self):
        """Create system events table"""
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS system_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                component TEXT NOT NULL,
                message TEXT NOT NULL,
                details TEXT,
                user_id TEXT,
                session_id TEXT,
                worker_id TEXT,
                model_id TEXT,
                license_hash TEXT,
                duration_ms INTEGER,
                metadata TEXT
            )
        """)
        
        # Create indexes
        self.connection.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON system_events(timestamp)")
        self.connection.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON system_events(event_type)")
        self.connection.execute("CREATE INDEX IF NOT EXISTS idx_events_severity ON system_events(severity)")
        self.connection.commit()
    
    def _create_metrics_table(self):
        """Create performance metrics table"""
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                value REAL NOT NULL,
                timestamp TEXT NOT NULL,
                labels TEXT,
                unit TEXT,
                description TEXT
            )
        """)
        
        # Create indexes
        self.connection.execute("CREATE INDEX IF NOT EXISTS idx_metrics_name ON performance_metrics(metric_name)")
        self.connection.execute("CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON performance_metrics(timestamp)")
        self.connection.commit()
    
    def _create_resource_usage_table(self):
        """Create resource usage table"""
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS resource_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                cpu_percent REAL NOT NULL,
                memory_percent REAL NOT NULL,
                memory_used_mb INTEGER NOT NULL,
                memory_available_mb INTEGER NOT NULL,
                disk_usage_percent REAL NOT NULL,
                disk_used_gb REAL NOT NULL,
                disk_available_gb REAL NOT NULL,
                network_bytes_sent INTEGER NOT NULL,
                network_bytes_recv INTEGER NOT NULL,
                active_connections INTEGER NOT NULL,
                gpu_usage_percent REAL,
                gpu_memory_used_mb INTEGER
            )
        """)
        
        # Create index
        self.connection.execute("CREATE INDEX IF NOT EXISTS idx_resource_timestamp ON resource_usage(timestamp)")
        self.connection.commit()
    
    def _create_license_usage_table(self):
        """Create license usage table"""
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS license_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                license_hash TEXT NOT NULL,
                user_id TEXT,
                operation TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                quota_consumed INTEGER NOT NULL,
                quota_remaining INTEGER NOT NULL,
                subscription_tier TEXT NOT NULL,
                feature_used TEXT,
                duration_ms INTEGER,
                success BOOLEAN NOT NULL,
                error_message TEXT
            )
        """)
        
        # Create indexes
        self.connection.execute("CREATE INDEX IF NOT EXISTS idx_license_timestamp ON license_usage(timestamp)")
        self.connection.execute("CREATE INDEX IF NOT EXISTS idx_license_hash ON license_usage(license_hash)")
        self.connection.commit()
    
    def insert_event(self, event: SystemEvent):
        """Insert system event into database"""
        try:
            self.connection.execute("""
                INSERT INTO system_events (
                    event_id, event_type, severity, timestamp, component, message,
                    details, user_id, session_id, worker_id, model_id, license_hash,
                    duration_ms, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id,
                event.event_type.value,
                event.severity.value,
                event.timestamp.isoformat(),
                event.component,
                event.message,
                json.dumps(event.details),
                event.user_id,
                event.session_id,
                event.worker_id,
                event.model_id,
                event.license_hash,
                event.duration_ms,
                json.dumps(event.metadata)
            ))
            self.connection.commit()
            
        except Exception as e:
            logger.error(f"Failed to insert event: {e}")
    
    def insert_metric(self, metric: PerformanceMetric):
        """Insert performance metric into database"""
        try:
            self.connection.execute("""
                INSERT INTO performance_metrics (
                    metric_name, metric_type, value, timestamp, labels, unit, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                metric.metric_name,
                metric.metric_type.value,
                metric.value,
                metric.timestamp.isoformat(),
                json.dumps(metric.labels),
                metric.unit,
                metric.description
            ))
            self.connection.commit()
            
        except Exception as e:
            logger.error(f"Failed to insert metric: {e}")
    
    def insert_resource_usage(self, usage: ResourceUsage):
        """Insert resource usage into database"""
        try:
            self.connection.execute("""
                INSERT INTO resource_usage (
                    timestamp, cpu_percent, memory_percent, memory_used_mb, memory_available_mb,
                    disk_usage_percent, disk_used_gb, disk_available_gb, network_bytes_sent,
                    network_bytes_recv, active_connections, gpu_usage_percent, gpu_memory_used_mb
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                usage.timestamp.isoformat(),
                usage.cpu_percent,
                usage.memory_percent,
                usage.memory_used_mb,
                usage.memory_available_mb,
                usage.disk_usage_percent,
                usage.disk_used_gb,
                usage.disk_available_gb,
                usage.network_bytes_sent,
                usage.network_bytes_recv,
                usage.active_connections,
                usage.gpu_usage_percent,
                usage.gpu_memory_used_mb
            ))
            self.connection.commit()
            
        except Exception as e:
            logger.error(f"Failed to insert resource usage: {e}")
    
    def insert_license_usage(self, usage: LicenseUsageRecord):
        """Insert license usage record into database"""
        try:
            self.connection.execute("""
                INSERT INTO license_usage (
                    timestamp, license_hash, user_id, operation, resource_type,
                    quota_consumed, quota_remaining, subscription_tier, feature_used,
                    duration_ms, success, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                usage.timestamp.isoformat(),
                usage.license_hash,
                usage.user_id,
                usage.operation,
                usage.resource_type,
                usage.quota_consumed,
                usage.quota_remaining,
                usage.subscription_tier.value,
                usage.feature_used,
                usage.duration_ms,
                usage.success,
                usage.error_message
            ))
            self.connection.commit()
            
        except Exception as e:
            logger.error(f"Failed to insert license usage: {e}")
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            logger.info("Monitoring database connection closed")


class MonitoringSystem:
    """
    Comprehensive monitoring system for distributed LLM platform
    """
    
    def __init__(self, 
                 license_info: Optional[LicenseInfo] = None,
                 db_path: str = "monitoring.db",
                 resource_collection_interval: int = 30,
                 max_memory_events: int = 10000):
        """
        Initialize monitoring system
        
        Args:
            license_info: License information for usage tracking
            db_path: Path to monitoring database
            resource_collection_interval: Resource collection interval in seconds
            max_memory_events: Maximum events to keep in memory
        """
        self.license_info = license_info
        self.resource_collection_interval = resource_collection_interval
        self.max_memory_events = max_memory_events
        
        # Initialize database
        self.db = MonitoringDatabase(db_path)
        
        # In-memory event storage for fast access
        self.recent_events = deque(maxlen=max_memory_events)
        self.recent_metrics = deque(maxlen=max_memory_events)
        
        # Performance counters
        self.counters = defaultdict(int)
        self.gauges = defaultdict(float)
        self.histograms = defaultdict(list)
        self.timers = defaultdict(list)
        
        # Resource monitoring
        self.resource_monitor_active = False
        self.resource_monitor_thread = None
        
        # License usage tracking
        self.license_usage_stats = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "quota_exceeded_count": 0,
            "license_expired_count": 0
        }
        
        # System statistics
        self.system_stats = {
            "start_time": datetime.now(),
            "total_events": 0,
            "total_metrics": 0,
            "total_errors": 0,
            "uptime_seconds": 0
        }
        
        logger.info("Monitoring system initialized")
    
    def log_system_events(self, 
                         event_type: EventType,
                         component: str,
                         message: str,
                         severity: EventSeverity = EventSeverity.INFO,
                         **kwargs) -> str:
        """
        Log system events function as specified in requirements
        
        Args:
            event_type: Type of event
            component: Component that generated the event
            message: Event message
            severity: Event severity level
            **kwargs: Additional event details
            
        Returns:
            Event ID
        """
        try:
            import uuid
            
            # Create event
            event = SystemEvent(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                severity=severity,
                timestamp=datetime.now(),
                component=component,
                message=message,
                details=kwargs.get('details', {}),
                user_id=kwargs.get('user_id'),
                session_id=kwargs.get('session_id'),
                worker_id=kwargs.get('worker_id'),
                model_id=kwargs.get('model_id'),
                license_hash=kwargs.get('license_hash'),
                duration_ms=kwargs.get('duration_ms'),
                metadata=kwargs.get('metadata', {})
            )
            
            # Store in database
            self.db.insert_event(event)
            
            # Store in memory for fast access
            self.recent_events.append(event)
            
            # Update statistics
            self.system_stats["total_events"] += 1
            if severity in [EventSeverity.ERROR, EventSeverity.CRITICAL]:
                self.system_stats["total_errors"] += 1
            
            # Log to file based on severity
            log_message = f"{component}: {message}"
            if severity == EventSeverity.DEBUG:
                logger.debug(log_message)
            elif severity == EventSeverity.INFO:
                logger.info(log_message)
            elif severity == EventSeverity.WARNING:
                logger.warning(log_message)
            elif severity == EventSeverity.ERROR:
                logger.error(log_message)
            elif severity == EventSeverity.CRITICAL:
                logger.critical(log_message)
            
            return event.event_id
            
        except Exception as e:
            logger.error(f"Failed to log system event: {e}")
            return ""
    
    def track_license_usage(self,
                          operation: str,
                          resource_type: str,
                          quota_consumed: int = 1,
                          quota_remaining: int = 0,
                          user_id: Optional[str] = None,
                          feature_used: Optional[str] = None,
                          duration_ms: Optional[int] = None,
                          success: bool = True,
                          error_message: Optional[str] = None):
        """
        Track license usage and analytics
        
        Args:
            operation: Operation performed
            resource_type: Type of resource used
            quota_consumed: Amount of quota consumed
            quota_remaining: Remaining quota
            user_id: User ID
            feature_used: Feature that was used
            duration_ms: Operation duration
            success: Whether operation was successful
            error_message: Error message if failed
        """
        try:
            if not self.license_info:
                return
            
            # Create license usage record
            usage_record = LicenseUsageRecord(
                timestamp=datetime.now(),
                license_hash=self.license_info.checksum,
                user_id=user_id,
                operation=operation,
                resource_type=resource_type,
                quota_consumed=quota_consumed,
                quota_remaining=quota_remaining,
                subscription_tier=self.license_info.plan,
                feature_used=feature_used,
                duration_ms=duration_ms,
                success=success,
                error_message=error_message
            )
            
            # Store in database
            self.db.insert_license_usage(usage_record)
            
            # Update statistics
            self.license_usage_stats["total_operations"] += 1
            if success:
                self.license_usage_stats["successful_operations"] += 1
            else:
                self.license_usage_stats["failed_operations"] += 1
                
                if "quota" in error_message.lower() if error_message else False:
                    self.license_usage_stats["quota_exceeded_count"] += 1
                elif "expired" in error_message.lower() if error_message else False:
                    self.license_usage_stats["license_expired_count"] += 1
            
            # Log license usage event
            self.log_system_events(
                event_type=EventType.LICENSE_CHECK,
                component="license_tracker",
                message=f"License usage: {operation} on {resource_type}",
                severity=EventSeverity.INFO if success else EventSeverity.WARNING,
                details={
                    "operation": operation,
                    "resource_type": resource_type,
                    "quota_consumed": quota_consumed,
                    "quota_remaining": quota_remaining,
                    "success": success
                },
                user_id=user_id,
                license_hash=self.license_info.checksum,
                duration_ms=duration_ms
            )
            
        except Exception as e:
            logger.error(f"Failed to track license usage: {e}")
    
    def record_performance_metric(self,
                                metric_name: str,
                                value: Union[int, float],
                                metric_type: MetricType = MetricType.GAUGE,
                                labels: Optional[Dict[str, str]] = None,
                                unit: str = "",
                                description: str = ""):
        """
        Record performance metric
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            metric_type: Type of metric
            labels: Metric labels
            unit: Unit of measurement
            description: Metric description
        """
        try:
            # Create metric
            metric = PerformanceMetric(
                metric_name=metric_name,
                metric_type=metric_type,
                value=value,
                timestamp=datetime.now(),
                labels=labels or {},
                unit=unit,
                description=description
            )
            
            # Store in database
            self.db.insert_metric(metric)
            
            # Store in memory
            self.recent_metrics.append(metric)
            
            # Update in-memory collections based on type
            if metric_type == MetricType.COUNTER:
                self.counters[metric_name] += value
            elif metric_type == MetricType.GAUGE:
                self.gauges[metric_name] = value
            elif metric_type == MetricType.HISTOGRAM:
                self.histograms[metric_name].append(value)
                # Keep only recent values
                if len(self.histograms[metric_name]) > 1000:
                    self.histograms[metric_name] = self.histograms[metric_name][-1000:]
            elif metric_type == MetricType.TIMER:
                self.timers[metric_name].append(value)
                # Keep only recent values
                if len(self.timers[metric_name]) > 1000:
                    self.timers[metric_name] = self.timers[metric_name][-1000:]
            
            self.system_stats["total_metrics"] += 1
            
        except Exception as e:
            logger.error(f"Failed to record performance metric: {e}")
    
    def collect_resource_usage(self) -> ResourceUsage:
        """
        Collect current resource usage
        
        Returns:
            ResourceUsage object
        """
        try:
            # Get CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Get memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_mb = memory.used // (1024 * 1024)
            memory_available_mb = memory.available // (1024 * 1024)
            
            # Get disk usage
            disk = psutil.disk_usage('/')
            disk_usage_percent = (disk.used / disk.total) * 100
            disk_used_gb = disk.used // (1024 * 1024 * 1024)
            disk_available_gb = disk.free // (1024 * 1024 * 1024)
            
            # Get network usage
            network = psutil.net_io_counters()
            network_bytes_sent = network.bytes_sent
            network_bytes_recv = network.bytes_recv
            
            # Get connection count
            try:
                connections = psutil.net_connections()
                active_connections = len([c for c in connections if c.status == 'ESTABLISHED'])
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                active_connections = 0
            
            # Try to get GPU usage (optional)
            gpu_usage_percent = None
            gpu_memory_used_mb = None
            try:
                import GPUtil
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]  # Use first GPU
                    gpu_usage_percent = gpu.load * 100
                    gpu_memory_used_mb = gpu.memoryUsed
            except ImportError:
                pass  # GPU monitoring not available
            except Exception:
                pass  # GPU monitoring failed
            
            # Create resource usage record
            usage = ResourceUsage(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_used_mb=memory_used_mb,
                memory_available_mb=memory_available_mb,
                disk_usage_percent=disk_usage_percent,
                disk_used_gb=disk_used_gb,
                disk_available_gb=disk_available_gb,
                network_bytes_sent=network_bytes_sent,
                network_bytes_recv=network_bytes_recv,
                active_connections=active_connections,
                gpu_usage_percent=gpu_usage_percent,
                gpu_memory_used_mb=gpu_memory_used_mb
            )
            
            # Store in database
            self.db.insert_resource_usage(usage)
            
            # Record as metrics
            self.record_performance_metric("cpu_usage_percent", cpu_percent, MetricType.GAUGE, unit="%")
            self.record_performance_metric("memory_usage_percent", memory_percent, MetricType.GAUGE, unit="%")
            self.record_performance_metric("disk_usage_percent", disk_usage_percent, MetricType.GAUGE, unit="%")
            self.record_performance_metric("active_connections", active_connections, MetricType.GAUGE)
            
            if gpu_usage_percent is not None:
                self.record_performance_metric("gpu_usage_percent", gpu_usage_percent, MetricType.GAUGE, unit="%")
            
            # Check for resource alerts
            self._check_resource_alerts(usage)
            
            return usage
            
        except Exception as e:
            logger.error(f"Failed to collect resource usage: {e}")
            return None
    
    def _check_resource_alerts(self, usage: ResourceUsage):
        """Check for resource usage alerts"""
        try:
            # CPU alert
            if usage.cpu_percent > 90:
                self.log_system_events(
                    event_type=EventType.RESOURCE_ALERT,
                    component="resource_monitor",
                    message=f"High CPU usage: {usage.cpu_percent:.1f}%",
                    severity=EventSeverity.WARNING,
                    details={"cpu_percent": usage.cpu_percent}
                )
            
            # Memory alert
            if usage.memory_percent > 85:
                self.log_system_events(
                    event_type=EventType.RESOURCE_ALERT,
                    component="resource_monitor",
                    message=f"High memory usage: {usage.memory_percent:.1f}%",
                    severity=EventSeverity.WARNING,
                    details={"memory_percent": usage.memory_percent}
                )
            
            # Disk alert
            if usage.disk_usage_percent > 90:
                self.log_system_events(
                    event_type=EventType.RESOURCE_ALERT,
                    component="resource_monitor",
                    message=f"High disk usage: {usage.disk_usage_percent:.1f}%",
                    severity=EventSeverity.WARNING,
                    details={"disk_usage_percent": usage.disk_usage_percent}
                )
            
            # GPU alert
            if usage.gpu_usage_percent and usage.gpu_usage_percent > 95:
                self.log_system_events(
                    event_type=EventType.RESOURCE_ALERT,
                    component="resource_monitor",
                    message=f"High GPU usage: {usage.gpu_usage_percent:.1f}%",
                    severity=EventSeverity.WARNING,
                    details={"gpu_usage_percent": usage.gpu_usage_percent}
                )
                
        except Exception as e:
            logger.error(f"Failed to check resource alerts: {e}")
    
    def start_resource_monitoring(self):
        """Start continuous resource monitoring"""
        try:
            if self.resource_monitor_active:
                logger.warning("Resource monitoring is already active")
                return
            
            self.resource_monitor_active = True
            self.resource_monitor_thread = threading.Thread(target=self._resource_monitor_loop, daemon=True)
            self.resource_monitor_thread.start()
            
            self.log_system_events(
                event_type=EventType.SYSTEM_START,
                component="resource_monitor",
                message="Resource monitoring started",
                severity=EventSeverity.INFO
            )
            
            logger.info("Resource monitoring started")
            
        except Exception as e:
            logger.error(f"Failed to start resource monitoring: {e}")
    
    def stop_resource_monitoring(self):
        """Stop continuous resource monitoring"""
        try:
            self.resource_monitor_active = False
            
            if self.resource_monitor_thread:
                self.resource_monitor_thread.join(timeout=5)
            
            self.log_system_events(
                event_type=EventType.SYSTEM_STOP,
                component="resource_monitor",
                message="Resource monitoring stopped",
                severity=EventSeverity.INFO
            )
            
            logger.info("Resource monitoring stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop resource monitoring: {e}")
    
    def _resource_monitor_loop(self):
        """Resource monitoring loop"""
        while self.resource_monitor_active:
            try:
                self.collect_resource_usage()
                time.sleep(self.resource_collection_interval)
            except Exception as e:
                logger.error(f"Error in resource monitoring loop: {e}")
                time.sleep(self.resource_collection_interval)
    
    def generate_performance_reports(self, 
                                   start_time: Optional[datetime] = None,
                                   end_time: Optional[datetime] = None,
                                   report_type: str = "summary") -> Dict[str, Any]:
        """
        Generate performance reports function as specified in requirements
        
        Args:
            start_time: Report start time (default: last 24 hours)
            end_time: Report end time (default: now)
            report_type: Type of report (summary, detailed, license_usage)
            
        Returns:
            Performance report dictionary
        """
        try:
            # Set default time range
            if not end_time:
                end_time = datetime.now()
            if not start_time:
                start_time = end_time - timedelta(hours=24)
            
            report = {
                "report_type": report_type,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "generated_at": datetime.now().isoformat(),
                "system_info": self._get_system_info()
            }
            
            if report_type == "summary":
                report.update(self._generate_summary_report(start_time, end_time))
            elif report_type == "detailed":
                report.update(self._generate_detailed_report(start_time, end_time))
            elif report_type == "license_usage":
                report.update(self._generate_license_usage_report(start_time, end_time))
            else:
                report.update(self._generate_summary_report(start_time, end_time))
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate performance report: {e}")
            return {"error": str(e)}
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information"""
        try:
            uptime = (datetime.now() - self.system_stats["start_time"]).total_seconds()
            self.system_stats["uptime_seconds"] = uptime
            
            return {
                "uptime_hours": uptime / 3600,
                "total_events": self.system_stats["total_events"],
                "total_metrics": self.system_stats["total_metrics"],
                "total_errors": self.system_stats["total_errors"],
                "license_tier": self.license_info.plan.value if self.license_info else "none",
                "monitoring_start_time": self.system_stats["start_time"].isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get system info: {e}")
            return {}
    
    def _generate_summary_report(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Generate summary performance report"""
        try:
            # Get recent events summary
            events_by_type = defaultdict(int)
            events_by_severity = defaultdict(int)
            
            for event in self.recent_events:
                if start_time <= event.timestamp <= end_time:
                    events_by_type[event.event_type.value] += 1
                    events_by_severity[event.severity.value] += 1
            
            # Get performance metrics summary
            metrics_summary = {}
            for metric_name, values in self.histograms.items():
                if values:
                    metrics_summary[metric_name] = {
                        "count": len(values),
                        "avg": statistics.mean(values),
                        "min": min(values),
                        "max": max(values),
                        "median": statistics.median(values)
                    }
            
            # Get current resource usage
            current_usage = self.collect_resource_usage()
            
            return {
                "events_summary": {
                    "by_type": dict(events_by_type),
                    "by_severity": dict(events_by_severity),
                    "total_events": sum(events_by_type.values())
                },
                "metrics_summary": metrics_summary,
                "current_resource_usage": asdict(current_usage) if current_usage else {},
                "license_usage_stats": self.license_usage_stats.copy(),
                "counters": dict(self.counters),
                "gauges": dict(self.gauges)
            }
            
        except Exception as e:
            logger.error(f"Failed to generate summary report: {e}")
            return {"error": str(e)}
    
    def _generate_detailed_report(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Generate detailed performance report"""
        try:
            summary = self._generate_summary_report(start_time, end_time)
            
            # Add detailed event information
            detailed_events = []
            for event in self.recent_events:
                if start_time <= event.timestamp <= end_time:
                    detailed_events.append(asdict(event))
            
            # Add detailed metrics
            detailed_metrics = []
            for metric in self.recent_metrics:
                if start_time <= metric.timestamp <= end_time:
                    detailed_metrics.append(asdict(metric))
            
            summary.update({
                "detailed_events": detailed_events[-100:],  # Last 100 events
                "detailed_metrics": detailed_metrics[-100:],  # Last 100 metrics
                "timer_statistics": {
                    name: {
                        "count": len(values),
                        "avg_ms": statistics.mean(values) if values else 0,
                        "min_ms": min(values) if values else 0,
                        "max_ms": max(values) if values else 0,
                        "p95_ms": statistics.quantiles(values, n=20)[18] if len(values) > 20 else 0
                    }
                    for name, values in self.timers.items()
                }
            })
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate detailed report: {e}")
            return {"error": str(e)}
    
    def _generate_license_usage_report(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Generate license usage report"""
        try:
            if not self.license_info:
                return {"error": "No license information available"}
            
            # Query license usage from database
            cursor = self.db.connection.cursor()
            cursor.execute("""
                SELECT operation, resource_type, COUNT(*) as count, 
                       SUM(quota_consumed) as total_quota,
                       AVG(duration_ms) as avg_duration,
                       SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_ops
                FROM license_usage 
                WHERE timestamp BETWEEN ? AND ? AND license_hash = ?
                GROUP BY operation, resource_type
            """, (start_time.isoformat(), end_time.isoformat(), self.license_info.checksum))
            
            usage_by_operation = []
            for row in cursor.fetchall():
                usage_by_operation.append({
                    "operation": row[0],
                    "resource_type": row[1],
                    "count": row[2],
                    "total_quota_consumed": row[3],
                    "avg_duration_ms": row[4] if row[4] else 0,
                    "successful_operations": row[5],
                    "success_rate": (row[5] / row[2] * 100) if row[2] > 0 else 0
                })
            
            return {
                "license_info": {
                    "license_key": self.license_info.license_key,
                    "subscription_tier": self.license_info.plan.value,
                    "expires_at": self.license_info.expires_at.isoformat(),
                    "max_clients": self.license_info.max_clients
                },
                "usage_by_operation": usage_by_operation,
                "total_stats": self.license_usage_stats.copy()
            }
            
        except Exception as e:
            logger.error(f"Failed to generate license usage report: {e}")
            return {"error": str(e)}
    
    def get_recent_events(self, 
                         limit: int = 100,
                         event_type: Optional[EventType] = None,
                         severity: Optional[EventSeverity] = None) -> List[Dict[str, Any]]:
        """Get recent events with optional filtering"""
        try:
            events = []
            for event in reversed(list(self.recent_events)):
                if len(events) >= limit:
                    break
                
                if event_type and event.event_type != event_type:
                    continue
                
                if severity and event.severity != severity:
                    continue
                
                events.append(asdict(event))
            
            return events
            
        except Exception as e:
            logger.error(f"Failed to get recent events: {e}")
            return []
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get current system health status"""
        try:
            current_usage = self.collect_resource_usage()
            
            # Determine health status
            health_status = "healthy"
            health_issues = []
            
            if current_usage:
                if current_usage.cpu_percent > 90:
                    health_status = "warning"
                    health_issues.append(f"High CPU usage: {current_usage.cpu_percent:.1f}%")
                
                if current_usage.memory_percent > 85:
                    health_status = "warning"
                    health_issues.append(f"High memory usage: {current_usage.memory_percent:.1f}%")
                
                if current_usage.disk_usage_percent > 90:
                    health_status = "critical"
                    health_issues.append(f"High disk usage: {current_usage.disk_usage_percent:.1f}%")
            
            # Check recent errors
            recent_errors = len([e for e in self.recent_events 
                               if e.severity in [EventSeverity.ERROR, EventSeverity.CRITICAL] 
                               and e.timestamp > datetime.now() - timedelta(minutes=5)])
            
            if recent_errors > 10:
                health_status = "critical"
                health_issues.append(f"High error rate: {recent_errors} errors in last 5 minutes")
            elif recent_errors > 5:
                health_status = "warning"
                health_issues.append(f"Elevated error rate: {recent_errors} errors in last 5 minutes")
            
            return {
                "status": health_status,
                "timestamp": datetime.now().isoformat(),
                "issues": health_issues,
                "resource_usage": asdict(current_usage) if current_usage else {},
                "uptime_hours": (datetime.now() - self.system_stats["start_time"]).total_seconds() / 3600,
                "total_events": self.system_stats["total_events"],
                "recent_errors": recent_errors
            }
            
        except Exception as e:
            logger.error(f"Failed to get system health: {e}")
            return {"status": "unknown", "error": str(e)}
    
    def shutdown(self):
        """Shutdown monitoring system"""
        try:
            self.stop_resource_monitoring()
            
            self.log_system_events(
                event_type=EventType.SYSTEM_STOP,
                component="monitoring_system",
                message="Monitoring system shutting down",
                severity=EventSeverity.INFO
            )
            
            self.db.close()
            logger.info("Monitoring system shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during monitoring system shutdown: {e}")


def create_monitoring_system(license_info: Optional[LicenseInfo] = None) -> MonitoringSystem:
    """Create and initialize monitoring system"""
    return MonitoringSystem(license_info=license_info)


def main():
    """Main function for testing monitoring system"""
    print("=== Testing Monitoring System ===\n")
    
    # Create test license
    from security.license_validator import LicenseInfo, SubscriptionTier, LicenseStatus
    
    license_info = LicenseInfo(
        license_key="TIKT-PRO-12-MONITOR",
        plan=SubscriptionTier.PRO,
        duration_months=12,
        unique_id="MONITOR",
        expires_at=datetime.now() + timedelta(days=365),
        max_clients=20,
        allowed_models=["llama", "mistral"],
        allowed_features=["monitoring", "analytics"],
        status=LicenseStatus.VALID,
        hardware_signature="monitor_hw",
        created_at=datetime.now(),
        checksum="monitor_checksum"
    )
    
    # Create monitoring system
    monitoring = create_monitoring_system(license_info)
    
    # Test 1: Log system events
    print("1. Testing System Event Logging")
    
    event_id = monitoring.log_system_events(
        event_type=EventType.SYSTEM_START,
        component="test_system",
        message="Test system started successfully",
        severity=EventSeverity.INFO,
        details={"version": "1.0", "mode": "test"}
    )
    print(f"✓ System event logged: {event_id}")
    
    # Test 2: Track license usage
    print("\n2. Testing License Usage Tracking")
    
    monitoring.track_license_usage(
        operation="inference_request",
        resource_type="api_call",
        quota_consumed=1,
        quota_remaining=999,
        user_id="test_user",
        feature_used="llm_inference",
        duration_ms=1500,
        success=True
    )
    print("✓ License usage tracked")
    
    # Test 3: Record performance metrics
    print("\n3. Testing Performance Metrics")
    
    monitoring.record_performance_metric(
        metric_name="inference_latency",
        value=1.25,
        metric_type=MetricType.TIMER,
        labels={"model": "llama-7b", "worker": "worker-001"},
        unit="seconds",
        description="Time taken for inference request"
    )
    print("✓ Performance metric recorded")
    
    # Test 4: Collect resource usage
    print("\n4. Testing Resource Usage Collection")
    
    usage = monitoring.collect_resource_usage()
    if usage:
        print(f"✓ Resource usage collected:")
        print(f"  CPU: {usage.cpu_percent:.1f}%")
        print(f"  Memory: {usage.memory_percent:.1f}%")
        print(f"  Disk: {usage.disk_usage_percent:.1f}%")
    else:
        print("✗ Failed to collect resource usage")
    
    # Test 5: Generate performance report
    print("\n5. Testing Performance Report Generation")
    
    report = monitoring.generate_performance_reports(report_type="summary")
    if "error" not in report:
        print("✓ Performance report generated")
        print(f"  Total events: {report['events_summary']['total_events']}")
        print(f"  License tier: {report['system_info']['license_tier']}")
        print(f"  Uptime: {report['system_info']['uptime_hours']:.2f} hours")
    else:
        print(f"✗ Failed to generate report: {report['error']}")
    
    # Test 6: Get system health
    print("\n6. Testing System Health Check")
    
    health = monitoring.get_system_health()
    print(f"✓ System health: {health['status']}")
    if health['issues']:
        print(f"  Issues: {health['issues']}")
    
    # Test 7: Start and stop resource monitoring
    print("\n7. Testing Resource Monitoring")
    
    monitoring.start_resource_monitoring()
    print("✓ Resource monitoring started")
    
    # Wait a bit to collect some data
    time.sleep(2)
    
    monitoring.stop_resource_monitoring()
    print("✓ Resource monitoring stopped")
    
    # Cleanup
    monitoring.shutdown()
    print("\n✓ Monitoring system shutdown complete")
    
    print("\n=== Monitoring System Tests Completed ===")


if __name__ == "__main__":
    main()