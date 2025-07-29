# Network Configuration Documentation

This file (`network_config.json`) defines the core network configuration for the TikTrue Distributed LLM Platform.

## Structure

### deployment_mode
Environment setting: "development", "staging", or "production"
- development: Used for local development with debug features enabled
- staging: Pre-production environment for testing
- production: Live environment with optimized settings

### paths
File system paths for various components:
- `models_dir`: Directory containing model files and blocks
- `logs_dir`: Directory for log files
- `sessions_dir`: Directory for user session data
- `data_dir`: Directory for application data files
- `config_dir`: Directory for configuration files
- `temp_dir`: Directory for temporary files

### network
Network configuration settings:
- `network_id`: Unique identifier for the network
- `network_name`: Human-readable name for the network
- `admin_node_id`: Identifier for the admin node
- `max_clients`: Maximum number of allowed client connections
- `allowed_models`: List of models available on this network
- `encryption_enabled`: Whether to enable encryption for communications
- `discovery_port`: Port for network discovery service
- `communication_port`: Port for node communications

### security
Security settings:
- `encryption_key_rotation_days`: Days between encryption key rotations
- `max_login_attempts`: Maximum allowed login attempts before lockout
- `session_timeout_minutes`: Minutes until inactive sessions expire
- `hardware_fingerprint_enabled`: Whether to enable hardware fingerprinting
- `audit_logging_enabled`: Whether to enable detailed audit logging

### version
Configuration file version for tracking changes

### created_at
Timestamp when the configuration was created