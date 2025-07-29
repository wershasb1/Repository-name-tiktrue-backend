# Configuration Files Documentation

This directory contains configuration files for the TikTrue Distributed LLM Platform.

## network_config.json

Main network configuration file that defines deployment settings, file paths, network parameters, and security settings.

### Structure:

- `deployment_mode`: Environment setting ("development", "staging", "production")
- `paths`: File system paths for various components
  - `models_dir`: Directory containing model files and blocks
  - `logs_dir`: Directory for log files
  - `sessions_dir`: Directory for user session data
  - `data_dir`: Directory for application data files
  - `config_dir`: Directory for configuration files
  - `temp_dir`: Directory for temporary files
- `network`: Network configuration settings
  - `network_id`: Unique identifier for the network
  - `network_name`: Human-readable name for the network
  - `admin_node_id`: Identifier for the admin node
  - `max_clients`: Maximum number of allowed client connections
  - `allowed_models`: List of models available on this network
  - `encryption_enabled`: Whether to enable encryption for communications
  - `discovery_port`: Port for network discovery service
  - `communication_port`: Port for node communications
- `security`: Security settings
  - `encryption_key_rotation_days`: Days between encryption key rotations
  - `max_login_attempts`: Maximum allowed login attempts before lockout
  - `session_timeout_minutes`: Minutes until inactive sessions expire
  - `hardware_fingerprint_enabled`: Whether to enable hardware fingerprinting
  - `audit_logging_enabled`: Whether to enable detailed audit logging
- `version`: Configuration file version
- `created_at`: Timestamp when the configuration was created

## performance_profile.json

Performance profiling data for model blocks with different execution providers.

### Structure:

- `metadata`: Information about the profiling process
  - `profiling_timestamp_utc`: When the profiling was performed
  - `onnxruntime_version`: Version of ONNX Runtime used
  - `warmup_runs_per_session`: Number of warmup runs performed
  - `benchmark_runs_per_session`: Number of benchmark runs performed
  - `providers_tested`: List of execution providers tested
  - `debug_mode`: Whether debug mode was enabled during profiling
- `profiles`: Performance data for each model block
  - `block_X`: Data for a specific block (where X is the block number)
    - `CPU`: CPU execution provider performance
      - `status`: Execution status
      - `mean_ms`: Mean execution time in milliseconds
      - `std_ms`: Standard deviation of execution time
      - `min_ms`: Minimum execution time
      - `max_ms`: Maximum execution time
      - `num_runs`: Number of runs performed
    - `Dml`: DirectML execution provider performance (same structure as CPU)

## network_config_llama_single_node.json

Configuration for a single-node deployment with Llama model.

## portable_config.json

Configuration for portable deployment scenarios with self-contained settings.