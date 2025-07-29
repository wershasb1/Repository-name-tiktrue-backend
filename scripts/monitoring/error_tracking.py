#!/usr/bin/env python3
"""
TikTrue Platform - Error Tracking and Alerting System

This script provides comprehensive error tracking and alerting:
- Log file monitoring and analysis
- Error pattern detection
- Alert generation and notification
- Error trend analysis
- Automated incident reporting

Requirements: 3.1 - Error tracking and alerting system
"""

import os
import sys
import json
import time
import logging
import asyncio
import smtplib
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import re

@dataclass
class ErrorEvent:
    """Error event data structure"""
    timestamp: str
    level: str
    source: str
    message: str
    traceback: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    error_hash: Optional[str] = None
    
    def __post_init__(self):
        if self.error_hash is None:
            # Generate hash based on message and source for deduplication
            hash_input = f"{self.source}:{self.message}"
            self.error_hash = hashlib.md5(hash_input.encode()).hexdigest()

@dataclass
class Alert:
    """Alert data structure"""
    alert_id: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    title: str
    description: str
    source: str
    error_count: int
    first_occurrence: str
    last_occurrence: str
    status: str = "ACTIVE"  # ACTIVE, ACKNOWLEDGED, RESOLVED
    
    def __post_init__(self):
        if not hasattr(self, 'alert_id') or not self.alert_id:
            # Generate alert ID based on title and source
            hash_input = f"{self.source}:{self.title}"
            self.alert_id = hashlib.md5(hash_input.encode()).hexdigest()[:8]

class ErrorTracker:
    """Comprehensive error tracking and alerting system"""
    
    def __init__(self, config_file: Optional[str] = None, verbose: bool = False):
        self.verbose = verbose
        self.project_root = Path(__file__).parent.parent.parent
        
        # Load configuration
        self.config = self.load_config(config_file)
        
        # Error tracking data
        self.error_events: List[ErrorEvent] = []
        self.error_patterns: Dict[str, List[ErrorEvent]] = defaultdict(list)
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        
        # Rate limiting for alerts
        self.alert_cooldowns: Dict[str, datetime] = {}
        
        # Setup logging
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging for error tracking"""
        log_dir = self.project_root / "temp" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_level = logging.DEBUG if self.verbose else logging.INFO
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(log_dir / "error_tracker.log", encoding='utf-8')
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def load_config(self, config_file: Optional[str] = None) -> Dict[str, Any]:
        """Load error tracking configuration"""
        default_config = {
            "log_sources": [
                {
                    "name": "backend_api",
                    "path": "temp/logs/api_integration_tests.log",
                    "pattern": r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - (\w+) - (.+)",
                    "level_index": 2,
                    "message_index": 3
                },
                {
                    "name": "health_monitor",
                    "path": "temp/logs/health_monitor.log",
                    "pattern": r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - (\w+) - (.+)",
                    "level_index": 2,
                    "message_index": 3
                },
                {
                    "name": "test_orchestrator",
                    "path": "temp/logs/test_orchestrator.log",
                    "pattern": r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - (\w+) - (.+)",
                    "level_index": 2,
                    "message_index": 3
                },
                {
                    "name": "production_build",
                    "path": "temp/logs/production_build.log",
                    "pattern": r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - (\w+) - (.+)",
                    "level_index": 2,
                    "message_index": 3
                }
            ],
            "error_patterns": [
                {
                    "name": "connection_error",
                    "pattern": r"connection.*(?:failed|refused|timeout)",
                    "severity": "HIGH",
                    "description": "Connection-related errors"
                },
                {
                    "name": "authentication_error",
                    "pattern": r"auth.*(?:failed|invalid|expired)",
                    "severity": "HIGH",
                    "description": "Authentication failures"
                },
                {
                    "name": "database_error",
                    "pattern": r"database.*(?:error|failed|timeout)",
                    "severity": "CRITICAL",
                    "description": "Database operation failures"
                },
                {
                    "name": "memory_error",
                    "pattern": r"memory.*(?:error|out of|allocation)",
                    "severity": "CRITICAL",
                    "description": "Memory-related errors"
                },
                {
                    "name": "file_error",
                    "pattern": r"file.*(?:not found|permission|access)",
                    "severity": "MEDIUM",
                    "description": "File system errors"
                }
            ],
            "alert_thresholds": {
                "error_rate_per_minute": 10,
                "critical_error_threshold": 1,
                "high_error_threshold": 5,
                "medium_error_threshold": 10
            },
            "alert_cooldown_minutes": 15,
            "notification": {
                "email": {
                    "enabled": False,
                    "smtp_server": "smtp.gmail.com",
                    "smtp_port": 587,
                    "username": "",
                    "password": "",
                    "recipients": []
                },
                "webhook": {
                    "enabled": False,
                    "url": "",
                    "headers": {}
                }
            },
            "retention": {
                "error_events_hours": 72,
                "alert_history_days": 30
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
        
    def parse_log_line(self, line: str, source_config: Dict[str, Any]) -> Optional[ErrorEvent]:
        """Parse a log line and extract error information"""
        try:
            pattern = source_config["pattern"]
            match = re.search(pattern, line, re.IGNORECASE)
            
            if not match:
                return None
                
            groups = match.groups()
            
            # Extract timestamp, level, and message based on configuration
            timestamp = groups[0] if len(groups) > 0 else datetime.now().isoformat()
            level = groups[source_config["level_index"] - 1] if len(groups) >= source_config["level_index"] else "INFO"
            message = groups[source_config["message_index"] - 1] if len(groups) >= source_config["message_index"] else line.strip()
            
            # Only track error-level messages
            if level.upper() not in ["ERROR", "CRITICAL", "FATAL", "WARNING"]:
                return None
                
            return ErrorEvent(
                timestamp=timestamp,
                level=level.upper(),
                source=source_config["name"],
                message=message.strip()
            )
            
        except Exception as e:
            self.logger.debug(f"Failed to parse log line: {e}")
            return None
            
    def scan_log_files(self) -> List[ErrorEvent]:
        """Scan all configured log files for errors"""
        new_errors = []
        
        for source_config in self.config["log_sources"]:
            log_path = self.project_root / source_config["path"]
            
            if not log_path.exists():
                self.logger.debug(f"Log file not found: {log_path}")
                continue
                
            try:
                # Read log file (last 1000 lines to avoid memory issues)
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = deque(f, maxlen=1000)
                    
                for line in lines:
                    error_event = self.parse_log_line(line, source_config)
                    if error_event:
                        new_errors.append(error_event)
                        
            except Exception as e:
                self.logger.error(f"Failed to read log file {log_path}: {e}")
                
        return new_errors
        
    def detect_error_patterns(self, errors: List[ErrorEvent]) -> Dict[str, List[ErrorEvent]]:
        """Detect error patterns in the error events"""
        pattern_matches = defaultdict(list)
        
        for error in errors:
            for pattern_config in self.config["error_patterns"]:
                pattern = pattern_config["pattern"]
                
                if re.search(pattern, error.message, re.IGNORECASE):
                    pattern_matches[pattern_config["name"]].append(error)
                    
        return pattern_matches
        
    def analyze_error_trends(self) -> Dict[str, Any]:
        """Analyze error trends and patterns"""
        if not self.error_events:
            return {"error": "No error events to analyze"}
            
        # Time-based analysis
        now = datetime.now()
        last_hour = now - timedelta(hours=1)
        last_day = now - timedelta(days=1)
        
        recent_errors = [
            e for e in self.error_events 
            if datetime.fromisoformat(e.timestamp.replace('Z', '+00:00').replace('+00:00', '')) > last_hour
        ]
        
        daily_errors = [
            e for e in self.error_events 
            if datetime.fromisoformat(e.timestamp.replace('Z', '+00:00').replace('+00:00', '')) > last_day
        ]
        
        # Error rate calculation
        error_rate_per_hour = len(recent_errors)
        error_rate_per_day = len(daily_errors)
        
        # Error distribution by source
        source_distribution = defaultdict(int)
        for error in self.error_events:
            source_distribution[error.source] += 1
            
        # Error distribution by level
        level_distribution = defaultdict(int)
        for error in self.error_events:
            level_distribution[error.level] += 1
            
        # Most common errors
        error_frequency = defaultdict(int)
        for error in self.error_events:
            error_frequency[error.error_hash] += 1
            
        most_common_errors = sorted(
            error_frequency.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:10]
        
        return {
            "error_rates": {
                "per_hour": error_rate_per_hour,
                "per_day": error_rate_per_day
            },
            "distribution": {
                "by_source": dict(source_distribution),
                "by_level": dict(level_distribution)
            },
            "most_common_errors": [
                {
                    "error_hash": error_hash,
                    "count": count,
                    "sample_message": next(
                        (e.message for e in self.error_events if e.error_hash == error_hash), 
                        "Unknown"
                    )
                }
                for error_hash, count in most_common_errors
            ],
            "total_errors": len(self.error_events),
            "unique_errors": len(error_frequency)
        }
        
    def should_create_alert(self, pattern_name: str, errors: List[ErrorEvent]) -> bool:
        """Determine if an alert should be created based on thresholds"""
        if not errors:
            return False
            
        # Check cooldown
        cooldown_key = f"{pattern_name}_{errors[0].source}"
        if cooldown_key in self.alert_cooldowns:
            cooldown_end = self.alert_cooldowns[cooldown_key] + timedelta(
                minutes=self.config["alert_cooldown_minutes"]
            )
            if datetime.now() < cooldown_end:
                return False
                
        # Find pattern configuration
        pattern_config = next(
            (p for p in self.config["error_patterns"] if p["name"] == pattern_name),
            None
        )
        
        if not pattern_config:
            return False
            
        severity = pattern_config["severity"]
        error_count = len(errors)
        
        # Check thresholds
        thresholds = self.config["alert_thresholds"]
        
        if severity == "CRITICAL" and error_count >= thresholds["critical_error_threshold"]:
            return True
        elif severity == "HIGH" and error_count >= thresholds["high_error_threshold"]:
            return True
        elif severity == "MEDIUM" and error_count >= thresholds["medium_error_threshold"]:
            return True
            
        return False
        
    def create_alert(self, pattern_name: str, errors: List[ErrorEvent]) -> Alert:
        """Create an alert for a detected error pattern"""
        pattern_config = next(
            (p for p in self.config["error_patterns"] if p["name"] == pattern_name),
            {"severity": "MEDIUM", "description": "Unknown error pattern"}
        )
        
        # Sort errors by timestamp
        sorted_errors = sorted(errors, key=lambda e: e.timestamp)
        
        alert = Alert(
            alert_id="",  # Will be generated in __post_init__
            severity=pattern_config["severity"],
            title=f"{pattern_config['description']} - {len(errors)} occurrences",
            description=f"Detected {len(errors)} instances of {pattern_name} errors",
            source=sorted_errors[0].source if sorted_errors else "unknown",
            error_count=len(errors),
            first_occurrence=sorted_errors[0].timestamp if sorted_errors else datetime.now().isoformat(),
            last_occurrence=sorted_errors[-1].timestamp if sorted_errors else datetime.now().isoformat()
        )
        
        # Set cooldown
        cooldown_key = f"{pattern_name}_{alert.source}"
        self.alert_cooldowns[cooldown_key] = datetime.now()
        
        return alert
        
    def send_email_notification(self, alert: Alert) -> bool:
        """Send email notification for alert"""
        email_config = self.config["notification"]["email"]
        
        if not email_config["enabled"] or not email_config["recipients"]:
            return False
            
        try:
            # Create message
            msg = MimeMultipart()
            msg['From'] = email_config["username"]
            msg['To'] = ", ".join(email_config["recipients"])
            msg['Subject'] = f"TikTrue Alert: {alert.severity} - {alert.title}"
            
            # Email body
            body = f"""
TikTrue Platform Alert

Alert ID: {alert.alert_id}
Severity: {alert.severity}
Source: {alert.source}
Title: {alert.title}

Description: {alert.description}

Error Count: {alert.error_count}
First Occurrence: {alert.first_occurrence}
Last Occurrence: {alert.last_occurrence}

Please investigate this issue promptly.

---
TikTrue Monitoring System
{datetime.now().isoformat()}
"""
            
            msg.attach(MimeText(body, 'plain'))
            
            # Send email
            server = smtplib.SMTP(email_config["smtp_server"], email_config["smtp_port"])
            server.starttls()
            server.login(email_config["username"], email_config["password"])
            
            text = msg.as_string()
            server.sendmail(email_config["username"], email_config["recipients"], text)
            server.quit()
            
            self.logger.info(f"Email notification sent for alert {alert.alert_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send email notification: {e}")
            return False
            
    async def send_webhook_notification(self, alert: Alert) -> bool:
        """Send webhook notification for alert"""
        webhook_config = self.config["notification"]["webhook"]
        
        if not webhook_config["enabled"] or not webhook_config["url"]:
            return False
            
        try:
            payload = {
                "alert_id": alert.alert_id,
                "severity": alert.severity,
                "title": alert.title,
                "description": alert.description,
                "source": alert.source,
                "error_count": alert.error_count,
                "first_occurrence": alert.first_occurrence,
                "last_occurrence": alert.last_occurrence,
                "timestamp": datetime.now().isoformat()
            }
            
            headers = {
                "Content-Type": "application/json",
                **webhook_config.get("headers", {})
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_config["url"],
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        self.logger.info(f"Webhook notification sent for alert {alert.alert_id}")
                        return True
                    else:
                        self.logger.error(f"Webhook notification failed: {response.status}")
                        return False
                        
        except Exception as e:
            self.logger.error(f"Failed to send webhook notification: {e}")
            return False
            
    async def process_alerts(self, pattern_matches: Dict[str, List[ErrorEvent]]):
        """Process detected patterns and create alerts"""
        new_alerts = []
        
        for pattern_name, errors in pattern_matches.items():
            if self.should_create_alert(pattern_name, errors):
                alert = self.create_alert(pattern_name, errors)
                
                # Check if alert already exists
                if alert.alert_id not in self.active_alerts:
                    self.active_alerts[alert.alert_id] = alert
                    new_alerts.append(alert)
                    
                    self.logger.warning(f"🚨 New alert created: {alert.title}")
                    
                    # Send notifications
                    if self.config["notification"]["email"]["enabled"]:
                        self.send_email_notification(alert)
                        
                    if self.config["notification"]["webhook"]["enabled"]:
                        await self.send_webhook_notification(alert)
                else:
                    # Update existing alert
                    existing_alert = self.active_alerts[alert.alert_id]
                    existing_alert.error_count += len(errors)
                    existing_alert.last_occurrence = alert.last_occurrence
                    
        return new_alerts
        
    def cleanup_old_data(self):
        """Clean up old error events and alerts"""
        now = datetime.now()
        
        # Clean up old error events
        retention_hours = self.config["retention"]["error_events_hours"]
        cutoff_time = now - timedelta(hours=retention_hours)
        
        self.error_events = [
            e for e in self.error_events
            if datetime.fromisoformat(e.timestamp.replace('Z', '+00:00').replace('+00:00', '')) > cutoff_time
        ]
        
        # Clean up old alert history
        retention_days = self.config["retention"]["alert_history_days"]
        alert_cutoff = now - timedelta(days=retention_days)
        
        self.alert_history = [
            a for a in self.alert_history
            if datetime.fromisoformat(a.first_occurrence.replace('Z', '+00:00').replace('+00:00', '')) > alert_cutoff
        ]
        
    def generate_error_report(self) -> Dict[str, Any]:
        """Generate comprehensive error tracking report"""
        trends = self.analyze_error_trends()
        
        report = {
            "summary": {
                "total_errors": len(self.error_events),
                "active_alerts": len(self.active_alerts),
                "alert_history_count": len(self.alert_history),
                "error_rate_per_hour": trends.get("error_rates", {}).get("per_hour", 0),
                "error_rate_per_day": trends.get("error_rates", {}).get("per_day", 0)
            },
            "trends": trends,
            "active_alerts": [asdict(alert) for alert in self.active_alerts.values()],
            "recent_errors": [
                asdict(error) for error in self.error_events[-50:]  # Last 50 errors
            ],
            "pattern_analysis": {
                pattern_name: len(errors)
                for pattern_name, errors in self.error_patterns.items()
            },
            "recommendations": self.generate_error_recommendations(),
            "report_timestamp": datetime.now().isoformat()
        }
        
        return report
        
    def generate_error_recommendations(self) -> List[str]:
        """Generate recommendations based on error analysis"""
        recommendations = []
        
        if not self.error_events:
            recommendations.append("✅ No errors detected - system appears stable")
            return recommendations
            
        trends = self.analyze_error_trends()
        
        # High error rate recommendations
        if trends["error_rates"]["per_hour"] > self.config["alert_thresholds"]["error_rate_per_minute"]:
            recommendations.append("🚨 High error rate detected - investigate immediately")
            
        # Critical alerts
        critical_alerts = [a for a in self.active_alerts.values() if a.severity == "CRITICAL"]
        if critical_alerts:
            recommendations.append(f"🔥 {len(critical_alerts)} critical alert(s) require immediate attention")
            
        # Pattern-based recommendations
        if "connection_error" in self.error_patterns:
            recommendations.append("🔌 Connection errors detected - check network connectivity")
            
        if "database_error" in self.error_patterns:
            recommendations.append("🗄️ Database errors detected - verify database health")
            
        if "memory_error" in self.error_patterns:
            recommendations.append("💾 Memory errors detected - check system resources")
            
        # Source-based recommendations
        source_dist = trends.get("distribution", {}).get("by_source", {})
        if source_dist:
            top_error_source = max(source_dist.items(), key=lambda x: x[1])
            if top_error_source[1] > 10:
                recommendations.append(f"🎯 Focus on {top_error_source[0]} - highest error count ({top_error_source[1]})")
                
        return recommendations
        
    def save_error_report(self, report: Dict[str, Any]) -> Path:
        """Save error report to file"""
        report_dir = self.project_root / "temp" / "error_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = report_dir / f"error_report_{timestamp}.json"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            
        # Also save as latest report
        latest_report = report_dir / "latest_error_report.json"
        with open(latest_report, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            
        return report_file
        
    async def run_error_tracking(self) -> bool:
        """Run complete error tracking cycle"""
        self.logger.info("🔍 Starting TikTrue Error Tracking...")
        
        try:
            # Scan log files for new errors
            new_errors = self.scan_log_files()
            self.error_events.extend(new_errors)
            
            if new_errors:
                self.logger.info(f"Found {len(new_errors)} new error events")
                
                # Detect error patterns
                pattern_matches = self.detect_error_patterns(new_errors)
                self.error_patterns.update(pattern_matches)
                
                # Process alerts
                new_alerts = await self.process_alerts(pattern_matches)
                
                if new_alerts:
                    self.logger.warning(f"Created {len(new_alerts)} new alerts")
            else:
                self.logger.info("No new errors detected")
                
            # Clean up old data
            self.cleanup_old_data()
            
            # Generate report
            report = self.generate_error_report()
            
            # Save report
            report_file = self.save_error_report(report)
            
            self.logger.info(f"📊 Error report saved: {report_file}")
            
            # Print summary
            summary = report["summary"]
            self.logger.info(f"Error Summary: {summary['total_errors']} total, {summary['active_alerts']} active alerts")
            
            return True
            
        except Exception as e:
            self.logger.error(f"💥 Error tracking failed: {e}")
            return False

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="TikTrue Error Tracking and Alerting")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--continuous", action="store_true", help="Run continuous monitoring")
    parser.add_argument("--interval", type=int, default=300, help="Monitoring interval in seconds")
    
    args = parser.parse_args()
    
    async def run_tracking():
        tracker = ErrorTracker(config_file=args.config, verbose=args.verbose)
        
        if args.continuous:
            tracker.logger.info(f"Starting continuous error tracking (interval: {args.interval}s)")
            
            while True:
                success = await tracker.run_error_tracking()
                if not success:
                    tracker.logger.error("Error tracking cycle failed, continuing...")
                    
                await asyncio.sleep(args.interval)
        else:
            return await tracker.run_error_tracking()
    
    # Run error tracking
    if args.continuous:
        asyncio.run(run_tracking())
    else:
        result = asyncio.run(run_tracking())
        sys.exit(0 if result else 1)

if __name__ == "__main__":
    main()