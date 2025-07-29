"""
Network Dashboard GUI for TikTrue Distributed LLM Platform

This module provides a comprehensive graphical dashboard for monitoring and managing
multiple networks, resource allocation, client assignments, and system performance.

Features:
- Real-time network status monitoring
- Resource utilization visualization
- Client assignment management
- Performance metrics and analytics
- Network creation and configuration
- System health monitoring

Classes:
    NetworkDashboardWidget: Main dashboard widget
    NetworkListWidget: Network list and management
    ResourceMonitorWidget: Resource monitoring display
    ClientManagementWidget: Client assignment management
    PerformanceChartsWidget: Performance visualization
"""

import sys
import json
import asyncio
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QGridLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
        QTabWidget, QGroupBox, QProgressBar, QTextEdit, QComboBox,
        QSpinBox, QLineEdit, QDialog, QDialogButtonBox, QFormLayout,
        QMessageBox, QSplitter, QFrame, QScrollArea, QTreeWidget,
        QTreeWidgetItem, QHeaderView, QAbstractItemView
    )
    from PyQt6.QtCore import (
        Qt, QTimer, QThread, pyqtSignal, QObject, QSize
    )
    from PyQt6.QtGui import (
        QFont, QColor, QPalette, QPixmap, QIcon, QPainter, QPen
    )
    from PyQt6.QtCharts import (
        QChart, QChartView, QLineSeries, QValueAxis, QDateTimeAxis
    )
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    # Mock classes for when PyQt6 is not available
    class QWidget: pass
    class QMainWindow: pass
    class QVBoxLayout: pass
    class QHBoxLayout: pass
    class QLabel: pass
    class QPushButton: pass
    class QTableWidget: pass
    class QTabWidget: pass
    class QTimer: pass
    class QThread: pass
    class pyqtSignal: 
        def __init__(self, *args): pass
        def emit(self, *args): pass
        def connect(self, func): pass

import logging
from multi_network_service import MultiNetworkService, NetworkDashboard, NetworkPriority
from core.network_manager import NetworkType

logger = logging.getLogger("NetworkDashboard")


class NetworkStatusUpdateThread(QThread):
    """Thread for updating network status"""
    status_updated = pyqtSignal(dict)
    
    def __init__(self, multi_network_service: MultiNetworkService):
        super().__init__()
        self.multi_network_service = multi_network_service
        self.running = False
    
    def run(self):
        """Main thread loop"""
        self.running = True
        while self.running:
            try:
                # Get dashboard data
                dashboard_data = self.multi_network_service.get_service_statistics()
                self.status_updated.emit(dashboard_data)
                
                # Sleep for 2 seconds
                self.msleep(2000)
                
            except Exception as e:
                logger.error(f"Status update thread error: {e}")
                self.msleep(1000)
    
    def stop(self):
        """Stop the thread"""
        self.running = False
        self.quit()
        self.wait()


class CreateNetworkDialog(QDialog):
    """Dialog for creating new networks"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Network")
        self.setModal(True)
        self.resize(400, 300)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup dialog UI"""
        layout = QVBoxLayout(self)
        
        # Form layout
        form_layout = QFormLayout()
        
        # Network name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter network name")
        form_layout.addRow("Network Name:", self.name_edit)
        
        # Model selection
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "llama3_1_8b_fp16",
            "mistral_7b_int4",
            "custom_model"
        ])
        form_layout.addRow("Model:", self.model_combo)
        
        # Network type
        self.type_combo = QComboBox()
        self.type_combo.addItems(["public", "private", "enterprise"])
        form_layout.addRow("Network Type:", self.type_combo)
        
        # Max clients
        self.max_clients_spin = QSpinBox()
        self.max_clients_spin.setRange(1, 100)
        self.max_clients_spin.setValue(10)
        form_layout.addRow("Max Clients:", self.max_clients_spin)
        
        # Priority
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["low", "normal", "high", "critical"])
        self.priority_combo.setCurrentText("normal")
        form_layout.addRow("Priority:", self.priority_combo)
        
        # Description
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.description_edit.setPlaceholderText("Optional description")
        form_layout.addRow("Description:", self.description_edit)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_network_config(self) -> Dict[str, Any]:
        """Get network configuration from dialog"""
        return {
            'network_name': self.name_edit.text().strip(),
            'model_id': self.model_combo.currentText(),
            'network_type': self.type_combo.currentText(),
            'max_clients': self.max_clients_spin.value(),
            'priority': self.priority_combo.currentText(),
            'description': self.description_edit.toPlainText().strip()
        }


class NetworkListWidget(QWidget):
    """Widget for displaying and managing network list"""
    
    def __init__(self, multi_network_service: MultiNetworkService):
        super().__init__()
        self.multi_network_service = multi_network_service
        self.setup_ui()
    
    def setup_ui(self):
        """Setup widget UI"""
        layout = QVBoxLayout(self)
        
        # Header with controls
        header_layout = QHBoxLayout()
        
        title_label = QLabel("Active Networks")
        title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Create network button
        self.create_btn = QPushButton("Create Network")
        self.create_btn.clicked.connect(self.create_network)
        header_layout.addWidget(self.create_btn)
        
        # Refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_networks)
        header_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(header_layout)
        
        # Network table
        self.network_table = QTableWidget()
        self.network_table.setColumnCount(8)
        self.network_table.setHorizontalHeaderLabels([
            "Name", "Model", "Type", "Status", "Clients", "CPU %", "Memory MB", "Actions"
        ])
        
        # Configure table
        header = self.network_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        
        self.network_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.network_table.setAlternatingRowColors(True)
        
        layout.addWidget(self.network_table)
        
        # Load initial data
        self.refresh_networks()
    
    def refresh_networks(self):
        """Refresh network list"""
        try:
            networks = self.multi_network_service.get_network_list()
            
            self.network_table.setRowCount(len(networks))
            
            for row, network in enumerate(networks):
                # Network name
                self.network_table.setItem(row, 0, QTableWidgetItem(network.get('network_name', 'Unknown')))
                
                # Model
                self.network_table.setItem(row, 1, QTableWidgetItem(network.get('model_id', 'Unknown')))
                
                # Type
                self.network_table.setItem(row, 2, QTableWidgetItem(network.get('network_type', 'Unknown')))
                
                # Status
                status_item = QTableWidgetItem(network.get('status', 'Unknown'))
                if network.get('status') == 'active':
                    status_item.setBackground(QColor(144, 238, 144))  # Light green
                else:
                    status_item.setBackground(QColor(255, 182, 193))  # Light red
                self.network_table.setItem(row, 3, status_item)
                
                # Clients
                current_clients = network.get('current_clients', 0)
                max_clients = network.get('max_clients', 0)
                self.network_table.setItem(row, 4, QTableWidgetItem(f"{current_clients}/{max_clients}"))
                
                # Resource allocation
                resource_alloc = network.get('resource_allocation', {})
                cpu_percent = resource_alloc.get('cpu_limit_percent', 0)
                memory_mb = resource_alloc.get('memory_limit_mb', 0)
                
                self.network_table.setItem(row, 5, QTableWidgetItem(f"{cpu_percent:.1f}"))
                self.network_table.setItem(row, 6, QTableWidgetItem(f"{memory_mb:.0f}"))
                
                # Actions
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(2, 2, 2, 2)
                
                # Details button
                details_btn = QPushButton("Details")
                details_btn.clicked.connect(lambda checked, nid=network['network_id']: self.show_network_details(nid))
                actions_layout.addWidget(details_btn)
                
                # Delete button
                delete_btn = QPushButton("Delete")
                delete_btn.clicked.connect(lambda checked, nid=network['network_id']: self.delete_network(nid))
                actions_layout.addWidget(delete_btn)
                
                self.network_table.setCellWidget(row, 7, actions_widget)
            
        except Exception as e:
            logger.error(f"Failed to refresh networks: {e}")
            QMessageBox.critical(self, "Error", f"Failed to refresh networks: {e}")
    
    def create_network(self):
        """Create new network"""
        try:
            dialog = CreateNetworkDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                config = dialog.get_network_config()
                
                if not config['network_name']:
                    QMessageBox.warning(self, "Warning", "Network name is required")
                    return
                
                # Convert string values to appropriate types
                network_type = NetworkType.PUBLIC
                if config['network_type'] == 'private':
                    network_type = NetworkType.PRIVATE
                elif config['network_type'] == 'enterprise':
                    network_type = NetworkType.ENTERPRISE
                
                priority = NetworkPriority.NORMAL
                if config['priority'] == 'low':
                    priority = NetworkPriority.LOW
                elif config['priority'] == 'high':
                    priority = NetworkPriority.HIGH
                elif config['priority'] == 'critical':
                    priority = NetworkPriority.CRITICAL
                
                # Create network asynchronously
                asyncio.create_task(self._create_network_async(
                    config['network_name'],
                    config['model_id'],
                    network_type,
                    config['max_clients'],
                    priority,
                    config['description']
                ))
                
        except Exception as e:
            logger.error(f"Failed to create network: {e}")
            QMessageBox.critical(self, "Error", f"Failed to create network: {e}")
    
    async def _create_network_async(self, network_name: str, model_id: str,
                                   network_type: NetworkType, max_clients: int,
                                   priority: NetworkPriority, description: str):
        """Create network asynchronously"""
        try:
            network_info = await self.multi_network_service.create_network(
                network_name=network_name,
                model_id=model_id,
                network_type=network_type,
                max_clients=max_clients,
                priority=priority,
                description=description
            )
            
            if network_info:
                QMessageBox.information(self, "Success", f"Network '{network_name}' created successfully")
                self.refresh_networks()
            else:
                QMessageBox.warning(self, "Warning", "Failed to create network")
                
        except Exception as e:
            logger.error(f"Failed to create network: {e}")
            QMessageBox.critical(self, "Error", f"Failed to create network: {e}")
    
    def show_network_details(self, network_id: str):
        """Show detailed network information"""
        try:
            details = self.multi_network_service.get_network_details(network_id)
            if not details:
                QMessageBox.warning(self, "Warning", "Network not found")
                return
            
            # Create details dialog
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Network Details - {network_id}")
            dialog.resize(600, 400)
            
            layout = QVBoxLayout(dialog)
            
            # Details text
            details_text = QTextEdit()
            details_text.setReadOnly(True)
            details_text.setPlainText(json.dumps(details, indent=2, default=str))
            layout.addWidget(details_text)
            
            # Close button
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)
            
            dialog.exec()
            
        except Exception as e:
            logger.error(f"Failed to show network details: {e}")
            QMessageBox.critical(self, "Error", f"Failed to show network details: {e}")
    
    def delete_network(self, network_id: str):
        """Delete network"""
        try:
            reply = QMessageBox.question(
                self, "Confirm Delete",
                f"Are you sure you want to delete network {network_id}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                asyncio.create_task(self._delete_network_async(network_id))
                
        except Exception as e:
            logger.error(f"Failed to delete network: {e}")
            QMessageBox.critical(self, "Error", f"Failed to delete network: {e}")
    
    async def _delete_network_async(self, network_id: str):
        """Delete network asynchronously"""
        try:
            success = await self.multi_network_service.delete_network(network_id)
            
            if success:
                QMessageBox.information(self, "Success", f"Network {network_id} deleted successfully")
                self.refresh_networks()
            else:
                QMessageBox.warning(self, "Warning", "Failed to delete network")
                
        except Exception as e:
            logger.error(f"Failed to delete network: {e}")
            QMessageBox.critical(self, "Error", f"Failed to delete network: {e}")


class ResourceMonitorWidget(QWidget):
    """Widget for monitoring system resources"""
    
    def __init__(self, multi_network_service: MultiNetworkService):
        super().__init__()
        self.multi_network_service = multi_network_service
        self.setup_ui()
        
        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_resources)
        self.update_timer.start(5000)  # Update every 5 seconds
    
    def setup_ui(self):
        """Setup widget UI"""
        layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel("System Resources")
        title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title_label)
        
        # Resource grid
        grid_layout = QGridLayout()
        
        # CPU usage
        cpu_group = QGroupBox("CPU Usage")
        cpu_layout = QVBoxLayout(cpu_group)
        
        self.cpu_progress = QProgressBar()
        self.cpu_progress.setRange(0, 100)
        self.cpu_label = QLabel("0%")
        
        cpu_layout.addWidget(self.cpu_progress)
        cpu_layout.addWidget(self.cpu_label)
        
        grid_layout.addWidget(cpu_group, 0, 0)
        
        # Memory usage
        memory_group = QGroupBox("Memory Usage")
        memory_layout = QVBoxLayout(memory_group)
        
        self.memory_progress = QProgressBar()
        self.memory_progress.setRange(0, 100)
        self.memory_label = QLabel("0 GB / 0 GB")
        
        memory_layout.addWidget(self.memory_progress)
        memory_layout.addWidget(self.memory_label)
        
        grid_layout.addWidget(memory_group, 0, 1)
        
        # Network allocation
        network_group = QGroupBox("Network Allocation")
        network_layout = QVBoxLayout(network_group)
        
        self.network_progress = QProgressBar()
        self.network_progress.setRange(0, 100)
        self.network_label = QLabel("0 networks")
        
        network_layout.addWidget(self.network_progress)
        network_layout.addWidget(self.network_label)
        
        grid_layout.addWidget(network_group, 1, 0)
        
        # Client connections
        clients_group = QGroupBox("Client Connections")
        clients_layout = QVBoxLayout(clients_group)
        
        self.clients_progress = QProgressBar()
        self.clients_progress.setRange(0, 100)
        self.clients_label = QLabel("0 clients")
        
        clients_layout.addWidget(self.clients_progress)
        clients_layout.addWidget(self.clients_label)
        
        grid_layout.addWidget(clients_group, 1, 1)
        
        layout.addLayout(grid_layout)
        
        # Resource details table
        self.resource_table = QTableWidget()
        self.resource_table.setColumnCount(4)
        self.resource_table.setHorizontalHeaderLabels([
            "Network", "CPU %", "Memory MB", "Clients"
        ])
        
        header = self.resource_table.horizontalHeader()
        header.setStretchLastSection(True)
        
        layout.addWidget(self.resource_table)
        
        # Initial update
        self.update_resources()
    
    def update_resources(self):
        """Update resource display"""
        try:
            stats = self.multi_network_service.get_service_statistics()
            system_resources = stats.get('system_resources', {}).get('system', {})
            
            # Update CPU
            cpu_usage = system_resources.get('cpu_usage_percent', 0)
            self.cpu_progress.setValue(int(cpu_usage))
            self.cpu_label.setText(f"{cpu_usage:.1f}%")
            
            # Update Memory
            memory_used = system_resources.get('memory_used_gb', 0)
            memory_total = system_resources.get('memory_total_gb', 1)
            memory_percent = (memory_used / memory_total) * 100
            
            self.memory_progress.setValue(int(memory_percent))
            self.memory_label.setText(f"{memory_used:.1f} GB / {memory_total:.1f} GB")
            
            # Update Network allocation
            service_info = stats.get('service', {})
            active_networks = service_info.get('active_networks', 0)
            max_networks = 10  # Assume max 10 networks for display
            
            network_percent = min((active_networks / max_networks) * 100, 100)
            self.network_progress.setValue(int(network_percent))
            self.network_label.setText(f"{active_networks} networks")
            
            # Update Clients
            total_clients = service_info.get('total_clients', 0)
            active_clients = service_info.get('active_clients', 0)
            max_clients = 100  # Assume max 100 clients for display
            
            client_percent = min((total_clients / max_clients) * 100, 100)
            self.clients_progress.setValue(int(client_percent))
            self.clients_label.setText(f"{active_clients}/{total_clients} clients")
            
            # Update resource table
            self.update_resource_table(stats)
            
        except Exception as e:
            logger.error(f"Failed to update resources: {e}")
    
    def update_resource_table(self, stats: Dict[str, Any]):
        """Update resource table with network details"""
        try:
            networks = self.multi_network_service.get_network_list()
            
            self.resource_table.setRowCount(len(networks))
            
            for row, network in enumerate(networks):
                # Network name
                self.resource_table.setItem(row, 0, QTableWidgetItem(network.get('network_name', 'Unknown')))
                
                # Resource allocation
                resource_alloc = network.get('resource_allocation', {})
                cpu_percent = resource_alloc.get('cpu_limit_percent', 0)
                memory_mb = resource_alloc.get('memory_limit_mb', 0)
                
                self.resource_table.setItem(row, 1, QTableWidgetItem(f"{cpu_percent:.1f}"))
                self.resource_table.setItem(row, 2, QTableWidgetItem(f"{memory_mb:.0f}"))
                
                # Clients
                current_clients = network.get('current_clients', 0)
                self.resource_table.setItem(row, 3, QTableWidgetItem(str(current_clients)))
            
        except Exception as e:
            logger.error(f"Failed to update resource table: {e}")


class NetworkDashboardWidget(QMainWindow):
    """Main network dashboard widget"""
    
    def __init__(self, multi_network_service: MultiNetworkService):
        super().__init__()
        self.multi_network_service = multi_network_service
        self.dashboard = NetworkDashboard(multi_network_service)
        
        self.setWindowTitle("TikTrue Network Dashboard")
        self.setGeometry(100, 100, 1200, 800)
        
        self.setup_ui()
        self.setup_status_updates()
    
    def setup_ui(self):
        """Setup main UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Status bar
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("Service Status: Starting...")
        self.status_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        # Service controls
        self.start_btn = QPushButton("Start Service")
        self.start_btn.clicked.connect(self.start_service)
        status_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("Stop Service")
        self.stop_btn.clicked.connect(self.stop_service)
        status_layout.addWidget(self.stop_btn)
        
        layout.addLayout(status_layout)
        
        # Main tabs
        self.tab_widget = QTabWidget()
        
        # Networks tab
        self.network_list_widget = NetworkListWidget(self.multi_network_service)
        self.tab_widget.addTab(self.network_list_widget, "Networks")
        
        # Resources tab
        self.resource_monitor_widget = ResourceMonitorWidget(self.multi_network_service)
        self.tab_widget.addTab(self.resource_monitor_widget, "Resources")
        
        # Logs tab
        self.logs_widget = QTextEdit()
        self.logs_widget.setReadOnly(True)
        self.logs_widget.setFont(QFont("Courier", 9))
        self.tab_widget.addTab(self.logs_widget, "Logs")
        
        layout.addWidget(self.tab_widget)
    
    def setup_status_updates(self):
        """Setup status update thread"""
        self.status_thread = NetworkStatusUpdateThread(self.multi_network_service)
        self.status_thread.status_updated.connect(self.update_status)
        self.status_thread.start()
    
    def update_status(self, stats: Dict[str, Any]):
        """Update status display"""
        try:
            service_info = stats.get('service', {})
            service_running = service_info.get('service_running', False)
            active_networks = service_info.get('active_networks', 0)
            total_clients = service_info.get('total_clients', 0)
            
            if service_running:
                status_text = f"Service Running - {active_networks} networks, {total_clients} clients"
                self.status_label.setStyleSheet("color: green")
            else:
                status_text = "Service Stopped"
                self.status_label.setStyleSheet("color: red")
            
            self.status_label.setText(f"Service Status: {status_text}")
            
        except Exception as e:
            logger.error(f"Failed to update status: {e}")
    
    def start_service(self):
        """Start multi-network service"""
        try:
            asyncio.create_task(self._start_service_async())
        except Exception as e:
            logger.error(f"Failed to start service: {e}")
            QMessageBox.critical(self, "Error", f"Failed to start service: {e}")
    
    async def _start_service_async(self):
        """Start service asynchronously"""
        try:
            success = await self.multi_network_service.start_service()
            if success:
                self.dashboard.start_dashboard()
                self.logs_widget.append(f"[{datetime.now()}] Multi-network service started")
            else:
                QMessageBox.warning(self, "Warning", "Failed to start service")
        except Exception as e:
            logger.error(f"Failed to start service: {e}")
            QMessageBox.critical(self, "Error", f"Failed to start service: {e}")
    
    def stop_service(self):
        """Stop multi-network service"""
        try:
            asyncio.create_task(self._stop_service_async())
        except Exception as e:
            logger.error(f"Failed to stop service: {e}")
            QMessageBox.critical(self, "Error", f"Failed to stop service: {e}")
    
    async def _stop_service_async(self):
        """Stop service asynchronously"""
        try:
            await self.multi_network_service.stop_service()
            self.dashboard.stop_dashboard()
            self.logs_widget.append(f"[{datetime.now()}] Multi-network service stopped")
        except Exception as e:
            logger.error(f"Failed to stop service: {e}")
            QMessageBox.critical(self, "Error", f"Failed to stop service: {e}")
    
    def closeEvent(self, event):
        """Handle window close event"""
        try:
            # Stop status thread
            if hasattr(self, 'status_thread'):
                self.status_thread.stop()
            
            # Stop service
            asyncio.create_task(self.multi_network_service.stop_service())
            
            event.accept()
            
        except Exception as e:
            logger.error(f"Error during close: {e}")
            event.accept()


def main():
    """Main function for testing dashboard"""
    if not PYQT_AVAILABLE:
        print("PyQt6 not available. Dashboard cannot be displayed.")
        return
    
    app = QApplication(sys.argv)
    
    # Create multi-network service
    service = MultiNetworkService()
    
    # Create and show dashboard
    dashboard = NetworkDashboardWidget(service)
    dashboard.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()