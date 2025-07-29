#!/usr/bin/env python3
"""
TikTrue Platform - Monitoring Dashboard

This script provides a comprehensive monitoring dashboard:
- Real-time system metrics visualization
- Service health status display
- Error tracking and alerting overview
- Performance metrics dashboard
- Log analysis and search

Requirements: 3.1 - Monitoring dashboard for system oversight
"""

import os
import sys
import json
import time
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import webbrowser

class MonitoringDashboard:
    """Web-based monitoring dashboard for TikTrue platform"""
    
    def __init__(self, port: int = 8888, auto_refresh: int = 30):
        self.port = port
        self.auto_refresh = auto_refresh
        self.project_root = Path(__file__).parent.parent.parent
        
        # Data sources
        self.health_data = {}
        self.error_data = {}
        self.performance_data = {}
        self.system_metrics = {}
        
        # Dashboard state
        self.last_update = None
        self.update_lock = threading.Lock()
        
    def load_monitoring_data(self):
        """Load latest monitoring data from reports"""
        with self.update_lock:
            try:
                # Load health check data
                health_report = self.project_root / "temp" / "health_reports" / "latest_health_report.json"
                if health_report.exists():
                    with open(health_report, 'r', encoding='utf-8') as f:
                        self.health_data = json.load(f)
                        
                # Load error tracking data
                error_report = self.project_root / "temp" / "error_reports" / "latest_error_report.json"
                if error_report.exists():
                    with open(error_report, 'r', encoding='utf-8') as f:
                        self.error_data = json.load(f)
                        
                # Load test results
                test_report = self.project_root / "temp" / "test_reports" / "latest_test_report.json"
                if test_report.exists():
                    with open(test_report, 'r', encoding='utf-8') as f:
                        self.performance_data = json.load(f)
                        
                self.last_update = datetime.now()
                
            except Exception as e:
                print(f"Error loading monitoring data: {e}")
                
    def generate_dashboard_html(self) -> str:
        """Generate HTML dashboard"""
        # Load latest data
        self.load_monitoring_data()
        
        # Generate dashboard HTML
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TikTrue Monitoring Dashboard</title>
    <meta http-equiv="refresh" content="{self.auto_refresh}">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
            color: #333;
            line-height: 1.6;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1rem 2rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        .header h1 {{
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }}
        
        .header .subtitle {{
            opacity: 0.9;
            font-size: 1rem;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }}
        
        .dashboard-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 2rem;
            margin-bottom: 2rem;
        }}
        
        .card {{
            background: white;
            border-radius: 10px;
            padding: 1.5rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: transform 0.2s ease;
        }}
        
        .card:hover {{
            transform: translateY(-2px);
        }}
        
        .card-header {{
            display: flex;
            align-items: center;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid #f0f0f0;
        }}
        
        .card-title {{
            font-size: 1.2rem;
            font-weight: 600;
            color: #333;
        }}
        
        .status-indicator {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 0.5rem;
        }}
        
        .status-healthy {{ background-color: #10b981; }}
        .status-degraded {{ background-color: #f59e0b; }}
        .status-unhealthy {{ background-color: #ef4444; }}
        .status-unknown {{ background-color: #6b7280; }}
        
        .metric {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.5rem 0;
            border-bottom: 1px solid #f0f0f0;
        }}
        
        .metric:last-child {{
            border-bottom: none;
        }}
        
        .metric-label {{
            font-weight: 500;
            color: #555;
        }}
        
        .metric-value {{
            font-weight: 600;
            color: #333;
        }}
        
        .metric-value.critical {{
            color: #ef4444;
        }}
        
        .metric-value.warning {{
            color: #f59e0b;
        }}
        
        .metric-value.good {{
            color: #10b981;
        }}
        
        .alert {{
            background: #fef2f2;
            border: 1px solid #fecaca;
            border-radius: 6px;
            padding: 0.75rem;
            margin: 0.5rem 0;
        }}
        
        .alert.critical {{
            background: #fef2f2;
            border-color: #fecaca;
            color: #991b1b;
        }}
        
        .alert.warning {{
            background: #fffbeb;
            border-color: #fed7aa;
            color: #92400e;
        }}
        
        .progress-bar {{
            width: 100%;
            height: 8px;
            background-color: #e5e7eb;
            border-radius: 4px;
            overflow: hidden;
            margin: 0.5rem 0;
        }}
        
        .progress-fill {{
            height: 100%;
            transition: width 0.3s ease;
        }}
        
        .progress-fill.good {{ background-color: #10b981; }}
        .progress-fill.warning {{ background-color: #f59e0b; }}
        .progress-fill.critical {{ background-color: #ef4444; }}
        
        .log-entry {{
            background: #f9fafb;
            border-left: 4px solid #e5e7eb;
            padding: 0.5rem;
            margin: 0.25rem 0;
            font-family: 'Courier New', monospace;
            font-size: 0.85rem;
        }}
        
        .log-entry.error {{
            border-left-color: #ef4444;
            background: #fef2f2;
        }}
        
        .log-entry.warning {{
            border-left-color: #f59e0b;
            background: #fffbeb;
        }}
        
        .timestamp {{
            color: #6b7280;
            font-size: 0.8rem;
            margin-top: 1rem;
            text-align: center;
        }}
        
        .full-width {{
            grid-column: 1 / -1;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }}
        
        th, td {{
            text-align: left;
            padding: 0.5rem;
            border-bottom: 1px solid #e5e7eb;
        }}
        
        th {{
            background-color: #f9fafb;
            font-weight: 600;
        }}
        
        .service-status {{
            display: inline-flex;
            align-items: center;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: 500;
        }}
        
        .service-status.healthy {{
            background-color: #d1fae5;
            color: #065f46;
        }}
        
        .service-status.degraded {{
            background-color: #fef3c7;
            color: #92400e;
        }}
        
        .service-status.unhealthy {{
            background-color: #fee2e2;
            color: #991b1b;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 TikTrue Monitoring Dashboard</h1>
        <div class="subtitle">Real-time system monitoring and health status</div>
    </div>
    
    <div class="container">
        <div class="dashboard-grid">
            {self.generate_system_overview_card()}
            {self.generate_service_health_card()}
            {self.generate_error_tracking_card()}
            {self.generate_performance_metrics_card()}
            {self.generate_alerts_card()}
            {self.generate_recent_activity_card()}
        </div>
        
        <div class="timestamp">
            Last updated: {self.last_update.strftime('%Y-%m-%d %H:%M:%S') if self.last_update else 'Never'}
            | Auto-refresh: {self.auto_refresh}s
        </div>
    </div>
</body>
</html>
"""
        return html
        
    def generate_system_overview_card(self) -> str:
        """Generate system overview card"""
        system_metrics = self.health_data.get("system_metrics", {})
        
        cpu_percent = system_metrics.get("cpu_percent", 0)
        memory_percent = system_metrics.get("memory_percent", 0)
        disk_percent = system_metrics.get("disk_percent", 0)
        
        # Determine status colors
        cpu_class = "critical" if cpu_percent > 80 else "warning" if cpu_percent > 60 else "good"
        memory_class = "critical" if memory_percent > 85 else "warning" if memory_percent > 70 else "good"
        disk_class = "critical" if disk_percent > 90 else "warning" if disk_percent > 75 else "good"
        
        return f"""
        <div class="card">
            <div class="card-header">
                <div class="status-indicator status-healthy"></div>
                <div class="card-title">System Overview</div>
            </div>
            
            <div class="metric">
                <div class="metric-label">CPU Usage</div>
                <div class="metric-value {cpu_class}">{cpu_percent:.1f}%</div>
            </div>
            <div class="progress-bar">
                <div class="progress-fill {cpu_class}" style="width: {cpu_percent}%"></div>
            </div>
            
            <div class="metric">
                <div class="metric-label">Memory Usage</div>
                <div class="metric-value {memory_class}">{memory_percent:.1f}%</div>
            </div>
            <div class="progress-bar">
                <div class="progress-fill {memory_class}" style="width: {memory_percent}%"></div>
            </div>
            
            <div class="metric">
                <div class="metric-label">Disk Usage</div>
                <div class="metric-value {disk_class}">{disk_percent:.1f}%</div>
            </div>
            <div class="progress-bar">
                <div class="progress-fill {disk_class}" style="width: {disk_percent}%"></div>
            </div>
            
            <div class="metric">
                <div class="metric-label">Uptime</div>
                <div class="metric-value">{self.format_uptime(system_metrics.get('uptime_seconds', 0))}</div>
            </div>
        </div>
        """
        
    def generate_service_health_card(self) -> str:
        """Generate service health card"""
        summary = self.health_data.get("summary", {})
        service_details = self.health_data.get("service_details", [])
        
        overall_status = self.health_data.get("overall_status", "UNKNOWN")
        status_class = overall_status.lower()
        
        services_html = ""
        for service in service_details[:10]:  # Show top 10 services
            service_status = service.get("status", "UNKNOWN").lower()
            response_time = service.get("response_time_ms", 0)
            
            services_html += f"""
            <tr>
                <td>{service.get('service_name', 'Unknown')}</td>
                <td><span class="service-status {service_status}">{service.get('status', 'UNKNOWN')}</span></td>
                <td>{response_time:.1f}ms</td>
            </tr>
            """
            
        return f"""
        <div class="card">
            <div class="card-header">
                <div class="status-indicator status-{status_class}"></div>
                <div class="card-title">Service Health</div>
            </div>
            
            <div class="metric">
                <div class="metric-label">Overall Status</div>
                <div class="metric-value">{overall_status}</div>
            </div>
            
            <div class="metric">
                <div class="metric-label">Health Percentage</div>
                <div class="metric-value good">{summary.get('health_percentage', 0):.1f}%</div>
            </div>
            
            <div class="metric">
                <div class="metric-label">Total Services</div>
                <div class="metric-value">{summary.get('total_services', 0)}</div>
            </div>
            
            <div class="metric">
                <div class="metric-label">Avg Response Time</div>
                <div class="metric-value">{summary.get('average_response_time_ms', 0):.1f}ms</div>
            </div>
            
            <table>
                <thead>
                    <tr>
                        <th>Service</th>
                        <th>Status</th>
                        <th>Response Time</th>
                    </tr>
                </thead>
                <tbody>
                    {services_html}
                </tbody>
            </table>
        </div>
        """
        
    def generate_error_tracking_card(self) -> str:
        """Generate error tracking card"""
        summary = self.error_data.get("summary", {})
        active_alerts = self.error_data.get("active_alerts", [])
        
        return f"""
        <div class="card">
            <div class="card-header">
                <div class="status-indicator status-{'unhealthy' if summary.get('active_alerts', 0) > 0 else 'healthy'}"></div>
                <div class="card-title">Error Tracking</div>
            </div>
            
            <div class="metric">
                <div class="metric-label">Total Errors</div>
                <div class="metric-value {'critical' if summary.get('total_errors', 0) > 100 else 'warning' if summary.get('total_errors', 0) > 10 else 'good'}">{summary.get('total_errors', 0)}</div>
            </div>
            
            <div class="metric">
                <div class="metric-label">Active Alerts</div>
                <div class="metric-value {'critical' if summary.get('active_alerts', 0) > 0 else 'good'}">{summary.get('active_alerts', 0)}</div>
            </div>
            
            <div class="metric">
                <div class="metric-label">Error Rate (per hour)</div>
                <div class="metric-value {'critical' if summary.get('error_rate_per_hour', 0) > 50 else 'warning' if summary.get('error_rate_per_hour', 0) > 10 else 'good'}">{summary.get('error_rate_per_hour', 0)}</div>
            </div>
            
            <div class="metric">
                <div class="metric-label">Error Rate (per day)</div>
                <div class="metric-value">{summary.get('error_rate_per_day', 0)}</div>
            </div>
            
            {self.generate_alerts_list(active_alerts[:5])}
        </div>
        """
        
    def generate_performance_metrics_card(self) -> str:
        """Generate performance metrics card"""
        test_summary = self.performance_data.get("test_summary", {})
        
        return f"""
        <div class="card">
            <div class="card-header">
                <div class="status-indicator status-{'healthy' if test_summary.get('success_rate', 0) > 90 else 'warning' if test_summary.get('success_rate', 0) > 70 else 'unhealthy'}"></div>
                <div class="card-title">Performance Metrics</div>
            </div>
            
            <div class="metric">
                <div class="metric-label">Test Success Rate</div>
                <div class="metric-value {'good' if test_summary.get('success_rate', 0) > 90 else 'warning' if test_summary.get('success_rate', 0) > 70 else 'critical'}">{test_summary.get('success_rate', 0):.1f}%</div>
            </div>
            
            <div class="metric">
                <div class="metric-label">Total Tests</div>
                <div class="metric-value">{test_summary.get('total_tests', 0)}</div>
            </div>
            
            <div class="metric">
                <div class="metric-label">Passed Tests</div>
                <div class="metric-value good">{test_summary.get('passed_tests', 0)}</div>
            </div>
            
            <div class="metric">
                <div class="metric-label">Failed Tests</div>
                <div class="metric-value {'critical' if test_summary.get('failed_tests', 0) > 0 else 'good'}">{test_summary.get('failed_tests', 0)}</div>
            </div>
            
            <div class="metric">
                <div class="metric-label">Avg Duration</div>
                <div class="metric-value">{test_summary.get('average_duration', 0):.2f}s</div>
            </div>
        </div>
        """
        
    def generate_alerts_card(self) -> str:
        """Generate alerts card"""
        alerts = self.health_data.get("alerts", [])
        
        alerts_html = ""
        for alert in alerts[:5]:  # Show top 5 alerts
            severity = alert.get("severity", "INFO").lower()
            alert_class = "critical" if severity == "critical" else "warning"
            
            alerts_html += f"""
            <div class="alert {alert_class}">
                <strong>{alert.get('severity', 'INFO')}</strong>: {alert.get('message', 'No message')}
                <br><small>{alert.get('service', 'Unknown service')} - {alert.get('timestamp', 'Unknown time')}</small>
            </div>
            """
            
        if not alerts_html:
            alerts_html = '<div class="metric"><div class="metric-label">No active alerts</div><div class="metric-value good">✅ All systems normal</div></div>'
            
        return f"""
        <div class="card">
            <div class="card-header">
                <div class="status-indicator status-{'unhealthy' if alerts else 'healthy'}"></div>
                <div class="card-title">Active Alerts</div>
            </div>
            
            {alerts_html}
        </div>
        """
        
    def generate_recent_activity_card(self) -> str:
        """Generate recent activity card"""
        recent_errors = self.error_data.get("recent_errors", [])
        
        activity_html = ""
        for error in recent_errors[-10:]:  # Show last 10 errors
            level = error.get("level", "INFO").lower()
            entry_class = "error" if level == "error" else "warning" if level == "warning" else ""
            
            activity_html += f"""
            <div class="log-entry {entry_class}">
                [{error.get('timestamp', 'Unknown')}] {error.get('level', 'INFO')}: {error.get('message', 'No message')[:100]}...
            </div>
            """
            
        if not activity_html:
            activity_html = '<div class="metric"><div class="metric-label">No recent activity</div><div class="metric-value">System is quiet</div></div>'
            
        return f"""
        <div class="card full-width">
            <div class="card-header">
                <div class="status-indicator status-healthy"></div>
                <div class="card-title">Recent Activity</div>
            </div>
            
            {activity_html}
        </div>
        """
        
    def generate_alerts_list(self, alerts: List[Dict]) -> str:
        """Generate alerts list HTML"""
        if not alerts:
            return ""
            
        alerts_html = ""
        for alert in alerts:
            severity = alert.get("severity", "INFO").lower()
            alert_class = "critical" if severity == "critical" else "warning"
            
            alerts_html += f"""
            <div class="alert {alert_class}">
                <strong>{alert.get('severity', 'INFO')}</strong>: {alert.get('title', 'No title')}
                <br><small>Count: {alert.get('error_count', 0)} | Last: {alert.get('last_occurrence', 'Unknown')}</small>
            </div>
            """
            
        return alerts_html
        
    def format_uptime(self, seconds: float) -> str:
        """Format uptime in human-readable format"""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds/60:.0f}m"
        elif seconds < 86400:
            return f"{seconds/3600:.1f}h"
        else:
            return f"{seconds/86400:.1f}d"

class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP request handler for monitoring dashboard"""
    
    def __init__(self, dashboard: MonitoringDashboard, *args, **kwargs):
        self.dashboard = dashboard
        super().__init__(*args, **kwargs)
        
    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == "/" or parsed_path.path == "/dashboard":
            # Serve dashboard HTML
            html = self.dashboard.generate_dashboard_html()
            
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.send_header('Content-length', str(len(html.encode('utf-8'))))
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
            
        elif parsed_path.path == "/api/data":
            # Serve JSON data
            self.dashboard.load_monitoring_data()
            
            data = {
                "health": self.dashboard.health_data,
                "errors": self.dashboard.error_data,
                "performance": self.dashboard.performance_data,
                "timestamp": datetime.now().isoformat()
            }
            
            json_data = json.dumps(data, ensure_ascii=False)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Content-length', str(len(json_data.encode('utf-8'))))
            self.end_headers()
            self.wfile.write(json_data.encode('utf-8'))
            
        else:
            # 404 for other paths
            self.send_response(404)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<h1>404 Not Found</h1>')
            
    def log_message(self, format, *args):
        """Override to reduce log noise"""
        pass

def create_handler(dashboard):
    """Create request handler with dashboard instance"""
    def handler(*args, **kwargs):
        DashboardHandler(dashboard, *args, **kwargs)
    return handler

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="TikTrue Monitoring Dashboard")
    parser.add_argument("--port", type=int, default=8888, help="Dashboard port")
    parser.add_argument("--auto-refresh", type=int, default=30, help="Auto-refresh interval in seconds")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")
    
    args = parser.parse_args()
    
    # Create dashboard
    dashboard = MonitoringDashboard(port=args.port, auto_refresh=args.auto_refresh)
    
    # Create HTTP server
    handler = create_handler(dashboard)
    httpd = HTTPServer(('localhost', args.port), handler)
    
    print(f"🚀 TikTrue Monitoring Dashboard starting on http://localhost:{args.port}")
    print(f"📊 Auto-refresh interval: {args.auto_refresh} seconds")
    print("Press Ctrl+C to stop the server")
    
    # Open browser if requested
    if not args.no_browser:
        try:
            webbrowser.open(f"http://localhost:{args.port}")
        except Exception as e:
            print(f"Could not open browser: {e}")
            
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down dashboard...")
        httpd.shutdown()
        httpd.server_close()

if __name__ == "__main__":
    main()