#!/usr/bin/env python3
"""
Troubleshooting and Diagnostic Tools for TikTrue Distributed LLM Platform
Provides comprehensive diagnostic capabilities for system troubleshooting and issue resolution

This module implements diagnostic tools for:
- System health checks
- Network connectivity diagnostics
- License validation diagnostics
- Model availability checks
- Performance diagnostics
- Security validation checks

Requirements addressed:
- 14.5: Troubleshooting and diagnostic tools
"""

import asyncio
import json
import logging
import time
import sys
import psutil
import socket
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TroubleshootingTools")


class DiagnosticSeverity(Enum):
    """Diagnostic result severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class DiagnosticResult:
    """Diagnostic check result"""
    check_name: str
    status: bool
    severity: DiagnosticSeverity
    message: str
    details: Dict[str, Any]
    timestamp: str
    recommendations: List[str]


class TroubleshootingDiagnosticTools:
    """
    Comprehensive troubleshooting and diagnostic tools
    
    Provides automated diagnostic capabilities for:
    - System health and resource checks
    - Network connectivity and discovery
    - License validation and security
    - Model availability and integrity
    - Performance analysis and optimization
    """
    
    def __init__(self):
        """Initialize diagnostic tools"""
        self.diagnostic_results = []
        self.system_info = {}
        
        # Diagnostic thresholds
        self.thresholds = {
            'cpu_warning': 70,
            'cpu_critical': 90,
            'memory_warning': 80,
            'memory_critical': 95,
            'disk_warning': 85,
            'disk_critical': 95,
            'network_timeout': 5.0,
            'response_time_warning': 1.0,
            'response_time_critical': 3.0
        }
    
    async def run_comprehensive_diagnostics(self) -> Dict[str, Any]:
        """
        Run comprehensive system diagnostics
        
        Returns:
            Dict containing all diagnostic results and recommendations
        """
        logger.info("🔍 Starting Comprehensive System Diagnostics")
        logger.info("=" * 60)
        
        start_time = time.time()
        
        try:
            # System Health Diagnostics
            await self._diagnose_system_health()
            
            # Network Connectivity Diagnostics
            await self._diagnose_network_connectivity()
            
            # License and Security Diagnostics
            await self._diagnose_license_security()
            
            # Model Availability Diagnostics
            await self._diagnose_model_availability()
            
            # Performance Diagnostics
            await self._diagnose_performance()
            
            # Configuration Diagnostics
            await self._diagnose_configuration()
            
            # Service Status Diagnostics
            await self._diagnose_service_status()
            
            end_time = time.time()
            diagnostic_duration = end_time - start_time
            
            return self._generate_diagnostic_report(diagnostic_duration)
            
        except Exception as e:
            logger.error(f"❌ Comprehensive diagnostics failed: {e}", exc_info=True)
            return self._generate_error_report(str(e))
    
    async def _diagnose_system_health(self):
        """Diagnose system health and resources"""
        logger.info("\n🏥 System Health Diagnostics")
        logger.info("-" * 40)
        
        try:
            # CPU Usage Check
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            if cpu_percent >= self.thresholds['cpu_critical']:
                severity = DiagnosticSeverity.CRITICAL
                recommendations = [
                    "Stop non-essential processes",
                    "Check for CPU-intensive applications",
                    "Consider upgrading hardware"
                ]
            elif cpu_percent >= self.thresholds['cpu_warning']:
                severity = DiagnosticSeverity.WARNING
                recommendations = [
                    "Monitor CPU usage trends",
                    "Optimize running processes"
                ]
            else:
                severity = DiagnosticSeverity.INFO
                recommendations = []
            
            self._add_diagnostic_result(
                "CPU Usage Check",
                cpu_percent < self.thresholds['cpu_critical'],
                severity,
                f"CPU usage: {cpu_percent}% ({cpu_count} cores)",
                {"cpu_percent": cpu_percent, "cpu_count": cpu_count},
                recommendations
            )
            
            # Memory Usage Check
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available_gb = memory.available / (1024**3)
            
            if memory_percent >= self.thresholds['memory_critical']:
                severity = DiagnosticSeverity.CRITICAL
                recommendations = [
                    "Free up memory immediately",
                    "Close unnecessary applications",
                    "Restart system if necessary"
                ]
            elif memory_percent >= self.thresholds['memory_warning']:
                severity = DiagnosticSeverity.WARNING
                recommendations = [
                    "Monitor memory usage",
                    "Close non-essential applications"
                ]
            else:
                severity = DiagnosticSeverity.INFO
                recommendations = []
            
            self._add_diagnostic_result(
                "Memory Usage Check",
                memory_percent < self.thresholds['memory_critical'],
                severity,
                f"Memory usage: {memory_percent}% (Available: {memory_available_gb:.1f}GB)",
                {
                    "memory_percent": memory_percent,
                    "memory_total_gb": memory.total / (1024**3),
                    "memory_available_gb": memory_available_gb
                },
                recommendations
            )
            
            # Disk Usage Check
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            disk_free_gb = disk.free / (1024**3)
            
            if disk_percent >= self.thresholds['disk_critical']:
                severity = DiagnosticSeverity.CRITICAL
                recommendations = [
                    "Free up disk space immediately",
                    "Delete temporary files",
                    "Move large files to external storage"
                ]
            elif disk_percent >= self.thresholds['disk_warning']:
                severity = DiagnosticSeverity.WARNING
                recommendations = [
                    "Clean up unnecessary files",
                    "Monitor disk usage trends"
                ]
            else:
                severity = DiagnosticSeverity.INFO
                recommendations = []
            
            self._add_diagnostic_result(
                "Disk Usage Check",
                disk_percent < self.thresholds['disk_critical'],
                severity,
                f"Disk usage: {disk_percent:.1f}% (Free: {disk_free_gb:.1f}GB)",
                {
                    "disk_percent": disk_percent,
                    "disk_total_gb": disk.total / (1024**3),
                    "disk_free_gb": disk_free_gb
                },
                recommendations
            )
            
            # Process Check
            process_count = len(psutil.pids())
            tiktrue_processes = []
            
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    if 'tiktrue' in proc.info['name'].lower() or 'python' in proc.info['name'].lower():
                        tiktrue_processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            self._add_diagnostic_result(
                "Process Status Check",
                True,
                DiagnosticSeverity.INFO,
                f"Total processes: {process_count}, TikTrue-related: {len(tiktrue_processes)}",
                {
                    "total_processes": process_count,
                    "tiktrue_processes": tiktrue_processes
                },
                []
            )
            
            logger.info("✅ System health diagnostics completed")
            
        except Exception as e:
            self._add_diagnostic_result(
                "System Health Check",
                False,
                DiagnosticSeverity.ERROR,
                f"System health check failed: {str(e)}",
                {"error": str(e)},
                ["Check system permissions", "Verify psutil installation"]
            )
    
    async def _diagnose_network_connectivity(self):
        """Diagnose network connectivity and discovery"""
        logger.info("\n🌐 Network Connectivity Diagnostics")
        logger.info("-" * 40)
        
        try:
            # Internet Connectivity Check
            internet_hosts = [
                ("8.8.8.8", 53),  # Google DNS
                ("1.1.1.1", 53),  # Cloudflare DNS
                ("api.tiktrue.com", 443)  # TikTrue API (if available)
            ]
            
            internet_connectivity = []
            for host, port in internet_hosts:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(self.thresholds['network_timeout'])
                    result = sock.connect_ex((host, port))
                    sock.close()
                    
                    is_connected = result == 0
                    internet_connectivity.append({
                        "host": host,
                        "port": port,
                        "connected": is_connected
                    })
                    
                except Exception as e:
                    internet_connectivity.append({
                        "host": host,
                        "port": port,
                        "connected": False,
                        "error": str(e)
                    })
            
            connected_hosts = sum(1 for conn in internet_connectivity if conn["connected"])
            
            self._add_diagnostic_result(
                "Internet Connectivity Check",
                connected_hosts > 0,
                DiagnosticSeverity.WARNING if connected_hosts == 0 else DiagnosticSeverity.INFO,
                f"Connected to {connected_hosts}/{len(internet_hosts)} test hosts",
                {"connectivity_results": internet_connectivity},
                ["Check internet connection", "Verify firewall settings"] if connected_hosts == 0 else []
            )
            
            # Local Network Interface Check
            network_interfaces = psutil.net_if_addrs()
            active_interfaces = []
            
            for interface_name, addresses in network_interfaces.items():
                for addr in addresses:
                    if addr.family == socket.AF_INET and not addr.address.startswith('127.'):
                        active_interfaces.append({
                            "interface": interface_name,
                            "ip_address": addr.address,
                            "netmask": addr.netmask
                        })
            
            self._add_diagnostic_result(
                "Network Interface Check",
                len(active_interfaces) > 0,
                DiagnosticSeverity.WARNING if len(active_interfaces) == 0 else DiagnosticSeverity.INFO,
                f"Found {len(active_interfaces)} active network interfaces",
                {"active_interfaces": active_interfaces},
                ["Check network adapter configuration"] if len(active_interfaces) == 0 else []
            )
            
            # Port Availability Check
            tiktrue_ports = [8700, 8701, 8702, 8900, 8901, 8902]
            port_status = []
            
            for port in tiktrue_ports:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1.0)
                    result = sock.connect_ex(('localhost', port))
                    sock.close()
                    
                    port_status.append({
                        "port": port,
                        "in_use": result == 0,
                        "available": result != 0
                    })
                    
                except Exception as e:
                    port_status.append({
                        "port": port,
                        "in_use": False,
                        "available": True,
                        "error": str(e)
                    })
            
            self._add_diagnostic_result(
                "Port Availability Check",
                True,
                DiagnosticSeverity.INFO,
                f"Checked {len(tiktrue_ports)} TikTrue ports",
                {"port_status": port_status},
                []
            )
            
            # Network Discovery Test
            try:
                # Test UDP broadcast capability
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.settimeout(2.0)
                
                # Try to send a test broadcast
                test_message = b"TikTrue Discovery Test"
                sock.sendto(test_message, ('<broadcast>', 8900))
                sock.close()
                
                self._add_diagnostic_result(
                    "Network Discovery Test",
                    True,
                    DiagnosticSeverity.INFO,
                    "UDP broadcast capability verified",
                    {"broadcast_test": "success"},
                    []
                )
                
            except Exception as e:
                self._add_diagnostic_result(
                    "Network Discovery Test",
                    False,
                    DiagnosticSeverity.WARNING,
                    f"UDP broadcast test failed: {str(e)}",
                    {"broadcast_test": "failed", "error": str(e)},
                    ["Check firewall UDP settings", "Verify network permissions"]
                )
            
            logger.info("✅ Network connectivity diagnostics completed")
            
        except Exception as e:
            self._add_diagnostic_result(
                "Network Connectivity Check",
                False,
                DiagnosticSeverity.ERROR,
                f"Network diagnostics failed: {str(e)}",
                {"error": str(e)},
                ["Check network configuration", "Verify system permissions"]
            )
    
    async def _diagnose_license_security(self):
        """Diagnose license validation and security components"""
        logger.info("\n🔒 License and Security Diagnostics")
        logger.info("-" * 40)
        
        try:
            # License Module Availability
            try:
                from license_storage import LicenseStorage
                from security.license_validator import LicenseValidator
                license_modules_available = True
            except ImportError as e:
                license_modules_available = False
                license_import_error = str(e)
            
            self._add_diagnostic_result(
                "License Module Availability",
                license_modules_available,
                DiagnosticSeverity.ERROR if not license_modules_available else DiagnosticSeverity.INFO,
                "License modules available" if license_modules_available else f"License modules missing: {license_import_error}",
                {"modules_available": license_modules_available},
                ["Install required license modules", "Check Python path"] if not license_modules_available else []
            )
            
            # Hardware Fingerprinting Check
            try:
                from security.hardware_fingerprint import HardwareFingerprint
                
                hw_fingerprint = HardwareFingerprint()
                fingerprint = hw_fingerprint.generate_fingerprint()
                
                # Validate fingerprint format and consistency
                fingerprint_valid = len(fingerprint) > 10 and fingerprint.isalnum()
                
                # Test consistency
                fingerprint2 = hw_fingerprint.generate_fingerprint()
                fingerprint_consistent = fingerprint == fingerprint2
                
                self._add_diagnostic_result(
                    "Hardware Fingerprinting Check",
                    fingerprint_valid and fingerprint_consistent,
                    DiagnosticSeverity.WARNING if not fingerprint_consistent else DiagnosticSeverity.INFO,
                    f"Hardware fingerprint: {'Valid' if fingerprint_valid else 'Invalid'}, {'Consistent' if fingerprint_consistent else 'Inconsistent'}",
                    {
                        "fingerprint_length": len(fingerprint),
                        "fingerprint_valid": fingerprint_valid,
                        "fingerprint_consistent": fingerprint_consistent
                    },
                    ["Check hardware stability", "Verify fingerprinting algorithm"] if not fingerprint_consistent else []
                )
                
            except ImportError:
                self._add_diagnostic_result(
                    "Hardware Fingerprinting Check",
                    False,
                    DiagnosticSeverity.ERROR,
                    "Hardware fingerprinting module not available",
                    {"module_available": False},
                    ["Install hardware fingerprinting module"]
                )
            
            # Encryption Capability Check
            try:
                from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
                from cryptography.hazmat.backends import default_backend
                import os
                
                # Test AES-256-GCM encryption
                key = os.urandom(32)  # 256-bit key
                iv = os.urandom(12)   # 96-bit IV for GCM
                
                cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
                encryptor = cipher.encryptor()
                
                test_data = b"TikTrue encryption test data"
                ciphertext = encryptor.update(test_data) + encryptor.finalize()
                
                # Test decryption
                decryptor = Cipher(algorithms.AES(key), modes.GCM(iv, encryptor.tag), backend=default_backend()).decryptor()
                decrypted_data = decryptor.update(ciphertext) + decryptor.finalize()
                
                encryption_working = decrypted_data == test_data
                
                self._add_diagnostic_result(
                    "Encryption Capability Check",
                    encryption_working,
                    DiagnosticSeverity.CRITICAL if not encryption_working else DiagnosticSeverity.INFO,
                    "AES-256-GCM encryption working" if encryption_working else "Encryption test failed",
                    {"encryption_test": "success" if encryption_working else "failed"},
                    ["Check cryptography library installation"] if not encryption_working else []
                )
                
            except ImportError:
                self._add_diagnostic_result(
                    "Encryption Capability Check",
                    False,
                    DiagnosticSeverity.CRITICAL,
                    "Cryptography library not available",
                    {"cryptography_available": False},
                    ["Install cryptography library: pip install cryptography"]
                )
            
            # Certificate and Key File Check
            cert_dirs = [Path("certs"), Path("temp")]
            certificate_files = []
            
            for cert_dir in cert_dirs:
                if cert_dir.exists():
                    cert_files = list(cert_dir.glob("*.pem")) + list(cert_dir.glob("*.key"))
                    certificate_files.extend(cert_files)
            
            self._add_diagnostic_result(
                "Certificate Files Check",
                len(certificate_files) > 0,
                DiagnosticSeverity.WARNING if len(certificate_files) == 0 else DiagnosticSeverity.INFO,
                f"Found {len(certificate_files)} certificate/key files",
                {"certificate_count": len(certificate_files), "certificate_files": [str(f) for f in certificate_files]},
                ["Generate required certificates", "Check certificate directory"] if len(certificate_files) == 0 else []
            )
            
            logger.info("✅ License and security diagnostics completed")
            
        except Exception as e:
            self._add_diagnostic_result(
                "License and Security Check",
                False,
                DiagnosticSeverity.ERROR,
                f"License/security diagnostics failed: {str(e)}",
                {"error": str(e)},
                ["Check security module installation"]
            )
    
    async def _diagnose_model_availability(self):
        """Diagnose model availability and integrity"""
        logger.info("\n🤖 Model Availability Diagnostics")
        logger.info("-" * 40)
        
        try:
            # Model Directory Check
            model_dirs = [Path("assets/models"), Path("models")]
            available_models = []
            
            for model_dir in model_dirs:
                if model_dir.exists():
                    for model_path in model_dir.iterdir():
                        if model_path.is_dir():
                            # Check for model blocks
                            blocks_dir = model_path / "blocks"
                            metadata_file = model_path / "metadata.json"
                            
                            block_files = list(blocks_dir.glob("*.onnx")) if blocks_dir.exists() else []
                            has_metadata = metadata_file.exists()
                            
                            available_models.append({
                                "model_name": model_path.name,
                                "model_path": str(model_path),
                                "block_count": len(block_files),
                                "has_metadata": has_metadata,
                                "total_size_mb": sum(f.stat().st_size for f in block_files) / (1024*1024) if block_files else 0
                            })
            
            self._add_diagnostic_result(
                "Model Availability Check",
                len(available_models) > 0,
                DiagnosticSeverity.WARNING if len(available_models) == 0 else DiagnosticSeverity.INFO,
                f"Found {len(available_models)} available models",
                {"available_models": available_models},
                ["Download required models", "Check model directory structure"] if len(available_models) == 0 else []
            )
            
            # Model Integrity Check
            for model in available_models:
                model_path = Path(model["model_path"])
                blocks_dir = model_path / "blocks"
                
                if blocks_dir.exists():
                    block_files = list(blocks_dir.glob("*.onnx"))
                    
                    # Check for missing blocks
                    expected_blocks = set(f"block_{i}.onnx" for i in range(1, model["block_count"] + 1))
                    actual_blocks = set(f.name for f in block_files)
                    missing_blocks = expected_blocks - actual_blocks
                    
                    integrity_ok = len(missing_blocks) == 0
                    
                    self._add_diagnostic_result(
                        f"Model Integrity Check - {model['model_name']}",
                        integrity_ok,
                        DiagnosticSeverity.WARNING if not integrity_ok else DiagnosticSeverity.INFO,
                        f"Model integrity: {'OK' if integrity_ok else f'{len(missing_blocks)} missing blocks'}",
                        {
                            "model_name": model["model_name"],
                            "expected_blocks": len(expected_blocks),
                            "actual_blocks": len(actual_blocks),
                            "missing_blocks": list(missing_blocks)
                        },
                        [f"Re-download missing blocks for {model['model_name']}"] if not integrity_ok else []
                    )
            
            # ONNX Runtime Check
            try:
                import onnxruntime as ort
                
                # Check available providers
                available_providers = ort.get_available_providers()
                has_gpu_support = any('CUDA' in provider or 'DirectML' in provider for provider in available_providers)
                
                self._add_diagnostic_result(
                    "ONNX Runtime Check",
                    True,
                    DiagnosticSeverity.INFO,
                    f"ONNX Runtime available with {len(available_providers)} providers (GPU: {'Yes' if has_gpu_support else 'No'})",
                    {
                        "onnx_runtime_available": True,
                        "available_providers": available_providers,
                        "gpu_support": has_gpu_support
                    },
                    []
                )
                
            except ImportError:
                self._add_diagnostic_result(
                    "ONNX Runtime Check",
                    False,
                    DiagnosticSeverity.CRITICAL,
                    "ONNX Runtime not available",
                    {"onnx_runtime_available": False},
                    ["Install ONNX Runtime: pip install onnxruntime or onnxruntime-directml"]
                )
            
            logger.info("✅ Model availability diagnostics completed")
            
        except Exception as e:
            self._add_diagnostic_result(
                "Model Availability Check",
                False,
                DiagnosticSeverity.ERROR,
                f"Model diagnostics failed: {str(e)}",
                {"error": str(e)},
                ["Check model directory permissions"]
            )
    
    async def _diagnose_performance(self):
        """Diagnose system performance characteristics"""
        logger.info("\n⚡ Performance Diagnostics")
        logger.info("-" * 40)
        
        try:
            # CPU Performance Test
            start_time = time.time()
            
            # Simple CPU benchmark
            result = 0
            for i in range(1000000):
                result += i * i
            
            cpu_test_time = time.time() - start_time
            
            cpu_performance_ok = cpu_test_time < 1.0  # Should complete in under 1 second
            
            self._add_diagnostic_result(
                "CPU Performance Test",
                cpu_performance_ok,
                DiagnosticSeverity.WARNING if not cpu_performance_ok else DiagnosticSeverity.INFO,
                f"CPU benchmark completed in {cpu_test_time:.3f} seconds",
                {"cpu_test_time": cpu_test_time, "performance_ok": cpu_performance_ok},
                ["Check CPU load", "Close resource-intensive applications"] if not cpu_performance_ok else []
            )
            
            # Memory Performance Test
            start_time = time.time()
            
            # Memory allocation test
            test_data = []
            for i in range(100):
                test_data.append(bytearray(1024 * 1024))  # 1MB chunks
            
            memory_test_time = time.time() - start_time
            del test_data  # Clean up
            
            memory_performance_ok = memory_test_time < 2.0
            
            self._add_diagnostic_result(
                "Memory Performance Test",
                memory_performance_ok,
                DiagnosticSeverity.WARNING if not memory_performance_ok else DiagnosticSeverity.INFO,
                f"Memory allocation test completed in {memory_test_time:.3f} seconds",
                {"memory_test_time": memory_test_time, "performance_ok": memory_performance_ok},
                ["Check available memory", "Close memory-intensive applications"] if not memory_performance_ok else []
            )
            
            # Disk I/O Performance Test
            start_time = time.time()
            
            # Write/read test
            test_file = Path("performance_test.tmp")
            test_data = b"Performance test data" * 1000
            
            try:
                with open(test_file, 'wb') as f:
                    f.write(test_data)
                
                with open(test_file, 'rb') as f:
                    read_data = f.read()
                
                test_file.unlink()  # Delete test file
                
                disk_test_time = time.time() - start_time
                disk_performance_ok = disk_test_time < 1.0 and read_data == test_data
                
                self._add_diagnostic_result(
                    "Disk I/O Performance Test",
                    disk_performance_ok,
                    DiagnosticSeverity.WARNING if not disk_performance_ok else DiagnosticSeverity.INFO,
                    f"Disk I/O test completed in {disk_test_time:.3f} seconds",
                    {"disk_test_time": disk_test_time, "performance_ok": disk_performance_ok},
                    ["Check disk health", "Free up disk space"] if not disk_performance_ok else []
                )
                
            except Exception as e:
                self._add_diagnostic_result(
                    "Disk I/O Performance Test",
                    False,
                    DiagnosticSeverity.ERROR,
                    f"Disk I/O test failed: {str(e)}",
                    {"error": str(e)},
                    ["Check disk permissions", "Verify disk health"]
                )
            
            # Network Performance Test
            start_time = time.time()
            
            # Local network latency test
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                sock.connect(('localhost', 80))  # Try to connect to localhost
                sock.close()
                
                network_test_time = time.time() - start_time
                network_performance_ok = network_test_time < self.thresholds['response_time_warning']
                
            except Exception:
                # If localhost:80 fails, just measure socket creation time
                network_test_time = time.time() - start_time
                network_performance_ok = network_test_time < 0.1
            
            self._add_diagnostic_result(
                "Network Performance Test",
                network_performance_ok,
                DiagnosticSeverity.WARNING if not network_performance_ok else DiagnosticSeverity.INFO,
                f"Network latency test: {network_test_time:.3f} seconds",
                {"network_test_time": network_test_time, "performance_ok": network_performance_ok},
                ["Check network configuration", "Verify network drivers"] if not network_performance_ok else []
            )
            
            logger.info("✅ Performance diagnostics completed")
            
        except Exception as e:
            self._add_diagnostic_result(
                "Performance Diagnostics",
                False,
                DiagnosticSeverity.ERROR,
                f"Performance diagnostics failed: {str(e)}",
                {"error": str(e)},
                ["Check system resources"]
            )
    
    async def _diagnose_configuration(self):
        """Diagnose configuration files and settings"""
        logger.info("\n⚙️ Configuration Diagnostics")
        logger.info("-" * 40)
        
        try:
            # Configuration File Check
            config_files = [
                "network_config.json",
                "config/network_config.json",
                "config/portable_config.json",
                "config/performance_profile.json"
            ]
            
            found_configs = []
            for config_file in config_files:
                config_path = Path(config_file)
                if config_path.exists():
                    try:
                        with open(config_path, 'r') as f:
                            config_data = json.load(f)
                        
                        found_configs.append({
                            "file": config_file,
                            "valid_json": True,
                            "size_bytes": config_path.stat().st_size,
                            "keys": list(config_data.keys()) if isinstance(config_data, dict) else []
                        })
                        
                    except json.JSONDecodeError as e:
                        found_configs.append({
                            "file": config_file,
                            "valid_json": False,
                            "error": str(e)
                        })
            
            self._add_diagnostic_result(
                "Configuration Files Check",
                len(found_configs) > 0,
                DiagnosticSeverity.WARNING if len(found_configs) == 0 else DiagnosticSeverity.INFO,
                f"Found {len(found_configs)} configuration files",
                {"configuration_files": found_configs},
                ["Create required configuration files"] if len(found_configs) == 0 else []
            )
            
            # Python Path and Module Check
            python_path = sys.path
            required_modules = [
                "asyncio", "json", "logging", "pathlib", "datetime",
                "psutil", "socket", "subprocess"
            ]
            
            missing_modules = []
            for module in required_modules:
                try:
                    __import__(module)
                except ImportError:
                    missing_modules.append(module)
            
            self._add_diagnostic_result(
                "Python Environment Check",
                len(missing_modules) == 0,
                DiagnosticSeverity.ERROR if len(missing_modules) > 0 else DiagnosticSeverity.INFO,
                f"Python environment: {len(missing_modules)} missing modules",
                {
                    "python_version": sys.version,
                    "python_path_count": len(python_path),
                    "missing_modules": missing_modules
                },
                [f"Install missing modules: {', '.join(missing_modules)}"] if missing_modules else []
            )
            
            logger.info("✅ Configuration diagnostics completed")
            
        except Exception as e:
            self._add_diagnostic_result(
                "Configuration Diagnostics",
                False,
                DiagnosticSeverity.ERROR,
                f"Configuration diagnostics failed: {str(e)}",
                {"error": str(e)},
                ["Check file permissions"]
            )
    
    async def _diagnose_service_status(self):
        """Diagnose TikTrue service status"""
        logger.info("\n🔧 Service Status Diagnostics")
        logger.info("-" * 40)
        
        try:
            # Check for running TikTrue processes
            tiktrue_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'status', 'cpu_percent', 'memory_percent']):
                try:
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    if ('tiktrue' in proc.info['name'].lower() or 
                        'tiktrue' in cmdline.lower() or
                        any('tiktrue' in arg.lower() for arg in proc.info['cmdline'] if arg)):
                        
                        tiktrue_processes.append({
                            "pid": proc.info['pid'],
                            "name": proc.info['name'],
                            "status": proc.info['status'],
                            "cpu_percent": proc.info['cpu_percent'],
                            "memory_percent": proc.info['memory_percent']
                        })
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            self._add_diagnostic_result(
                "TikTrue Process Status",
                True,  # Always pass, just informational
                DiagnosticSeverity.INFO,
                f"Found {len(tiktrue_processes)} TikTrue-related processes",
                {"tiktrue_processes": tiktrue_processes},
                []
            )
            
            # Check log files
            log_dirs = [Path("logs"), Path(".")]
            log_files = []
            
            for log_dir in log_dirs:
                if log_dir.exists():
                    log_files.extend(list(log_dir.glob("*.log")))
            
            recent_logs = []
            for log_file in log_files:
                try:
                    stat = log_file.stat()
                    age_hours = (time.time() - stat.st_mtime) / 3600
                    
                    if age_hours < 24:  # Logs from last 24 hours
                        recent_logs.append({
                            "file": str(log_file),
                            "size_mb": stat.st_size / (1024*1024),
                            "age_hours": age_hours
                        })
                except Exception:
                    continue
            
            self._add_diagnostic_result(
                "Log Files Check",
                True,  # Always pass, just informational
                DiagnosticSeverity.INFO,
                f"Found {len(recent_logs)} recent log files",
                {"recent_log_files": recent_logs},
                []
            )
            
            # Check Windows Service (if applicable)
            if sys.platform == "win32":
                try:
                    result = subprocess.run(
                        ['sc', 'query', 'TikTrueService'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    service_exists = result.returncode == 0
                    service_status = "Unknown"
                    
                    if service_exists:
                        if "RUNNING" in result.stdout:
                            service_status = "Running"
                        elif "STOPPED" in result.stdout:
                            service_status = "Stopped"
                    
                    self._add_diagnostic_result(
                        "Windows Service Check",
                        True,  # Always pass, just informational
                        DiagnosticSeverity.INFO,
                        f"TikTrue Windows Service: {'Exists' if service_exists else 'Not installed'} ({service_status})",
                        {
                            "service_exists": service_exists,
                            "service_status": service_status
                        },
                        []
                    )
                    
                except Exception as e:
                    self._add_diagnostic_result(
                        "Windows Service Check",
                        False,
                        DiagnosticSeverity.WARNING,
                        f"Could not check Windows service: {str(e)}",
                        {"error": str(e)},
                        ["Check Windows service permissions"]
                    )
            
            logger.info("✅ Service status diagnostics completed")
            
        except Exception as e:
            self._add_diagnostic_result(
                "Service Status Diagnostics",
                False,
                DiagnosticSeverity.ERROR,
                f"Service diagnostics failed: {str(e)}",
                {"error": str(e)},
                ["Check system permissions"]
            )
    
    def _add_diagnostic_result(self, check_name: str, status: bool, severity: DiagnosticSeverity, 
                              message: str, details: Dict[str, Any], recommendations: List[str]):
        """Add diagnostic result to results list"""
        result = DiagnosticResult(
            check_name=check_name,
            status=status,
            severity=severity,
            message=message,
            details=details,
            timestamp=datetime.now().isoformat(),
            recommendations=recommendations
        )
        
        self.diagnostic_results.append(result)
        
        # Log result
        status_icon = "✅" if status else "❌"
        severity_icon = {
            DiagnosticSeverity.INFO: "ℹ️",
            DiagnosticSeverity.WARNING: "⚠️",
            DiagnosticSeverity.ERROR: "❌",
            DiagnosticSeverity.CRITICAL: "🚨"
        }.get(severity, "❓")
        
        logger.info(f"{status_icon} {severity_icon} {check_name}: {message}")
        
        if recommendations:
            for rec in recommendations:
                logger.info(f"   💡 {rec}")
    
    def _generate_diagnostic_report(self, diagnostic_duration: float) -> Dict[str, Any]:
        """Generate comprehensive diagnostic report"""
        
        # Count results by severity
        severity_counts = {
            DiagnosticSeverity.INFO: 0,
            DiagnosticSeverity.WARNING: 0,
            DiagnosticSeverity.ERROR: 0,
            DiagnosticSeverity.CRITICAL: 0
        }
        
        passed_checks = 0
        failed_checks = 0
        all_recommendations = []
        
        for result in self.diagnostic_results:
            severity_counts[result.severity] += 1
            
            if result.status:
                passed_checks += 1
            else:
                failed_checks += 1
            
            all_recommendations.extend(result.recommendations)
        
        # Determine overall system health
        if severity_counts[DiagnosticSeverity.CRITICAL] > 0:
            overall_health = "CRITICAL"
        elif severity_counts[DiagnosticSeverity.ERROR] > 0:
            overall_health = "ERROR"
        elif severity_counts[DiagnosticSeverity.WARNING] > 0:
            overall_health = "WARNING"
        else:
            overall_health = "HEALTHY"
        
        return {
            'diagnostic_type': 'comprehensive_system_diagnostics',
            'timestamp': datetime.now().isoformat(),
            'duration_seconds': round(diagnostic_duration, 2),
            'overall_health': overall_health,
            'summary': {
                'total_checks': len(self.diagnostic_results),
                'passed_checks': passed_checks,
                'failed_checks': failed_checks,
                'success_rate_percent': round((passed_checks / len(self.diagnostic_results) * 100), 1) if self.diagnostic_results else 0
            },
            'severity_breakdown': {
                'info': severity_counts[DiagnosticSeverity.INFO],
                'warning': severity_counts[DiagnosticSeverity.WARNING],
                'error': severity_counts[DiagnosticSeverity.ERROR],
                'critical': severity_counts[DiagnosticSeverity.CRITICAL]
            },
            'diagnostic_results': [
                {
                    'check_name': result.check_name,
                    'status': result.status,
                    'severity': result.severity.value,
                    'message': result.message,
                    'details': result.details,
                    'timestamp': result.timestamp,
                    'recommendations': result.recommendations
                }
                for result in self.diagnostic_results
            ],
            'all_recommendations': list(set(all_recommendations)),  # Remove duplicates
            'system_info': {
                'platform': sys.platform,
                'python_version': sys.version,
                'diagnostic_tool_version': '1.0.0'
            }
        }
    
    def _generate_error_report(self, error_message: str) -> Dict[str, Any]:
        """Generate error report when diagnostics fail"""
        return {
            'diagnostic_type': 'comprehensive_system_diagnostics',
            'timestamp': datetime.now().isoformat(),
            'overall_health': 'DIAGNOSTIC_FAILED',
            'error': error_message,
            'partial_results': [
                {
                    'check_name': result.check_name,
                    'status': result.status,
                    'severity': result.severity.value,
                    'message': result.message,
                    'timestamp': result.timestamp
                }
                for result in self.diagnostic_results
            ]
        }
    
    def save_diagnostic_report(self, report: Dict[str, Any], output_file: Optional[str] = None):
        """Save diagnostic report to file"""
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"tiktrue_diagnostic_report_{timestamp}.json"
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info(f"📄 Diagnostic report saved to: {output_file}")
        except Exception as e:
            logger.error(f"Failed to save diagnostic report: {e}")


async def main():
    """Main function for running troubleshooting diagnostics"""
    print("🔍 TikTrue Distributed LLM Platform - Troubleshooting Diagnostics")
    print("=" * 70)
    print()
    
    # Create and run diagnostics
    diagnostics = TroubleshootingDiagnosticTools()
    report = await diagnostics.run_comprehensive_diagnostics()
    
    # Save report
    diagnostics.save_diagnostic_report(report)
    
    # Print summary
    print("\n" + "=" * 70)
    print("📊 DIAGNOSTIC SUMMARY")
    print("=" * 70)
    
    if 'summary' in report:
        summary = report['summary']
        print(f"Overall Health: {report['overall_health']}")
        print(f"Total Checks: {summary['total_checks']}")
        print(f"Passed: {summary['passed_checks']}")
        print(f"Failed: {summary['failed_checks']}")
        print(f"Success Rate: {summary['success_rate_percent']}%")
        print(f"Duration: {report.get('duration_seconds', 0):.1f} seconds")
        
        # Print severity breakdown
        if 'severity_breakdown' in report:
            severity = report['severity_breakdown']
            print(f"\nSeverity Breakdown:")
            print(f"  ℹ️  Info: {severity['info']}")
            print(f"  ⚠️  Warning: {severity['warning']}")
            print(f"  ❌ Error: {severity['error']}")
            print(f"  🚨 Critical: {severity['critical']}")
    else:
        print(f"Diagnostic Status: FAILED")
        print(f"Error: {report.get('error', 'Unknown error')}")
    
    # Print recommendations
    if 'all_recommendations' in report and report['all_recommendations']:
        print(f"\n💡 RECOMMENDATIONS:")
        for i, recommendation in enumerate(report['all_recommendations'][:10], 1):
            print(f"  {i}. {recommendation}")
        
        if len(report['all_recommendations']) > 10:
            print(f"  ... and {len(report['all_recommendations']) - 10} more recommendations")
    
    print("\n🎯 Diagnostics completed! Check the detailed report file for full results.")
    
    return 0 if report.get('overall_health') in ['HEALTHY', 'WARNING'] else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)