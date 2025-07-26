# TikTrue Platform Project Structure

## Introduction

This document provides a comprehensive overview of the TikTrue Distributed LLM Platform project structure. It explains the purpose of each directory, key files, and how they interact to form the complete system. This guide is intended to help developers navigate the codebase efficiently and understand the organization of the project.

## Directory Structure Overview

```
TikTrue_Platform/
├── core/                    # Core system components
├── workers/                 # Worker and scheduler components
├── interfaces/              # User interface components
├── network/                 # Network and communication components
├── security/                # Security and authentication components
├── models/                  # Model management components
├── config/                  # Configuration files
├── tests/                   # Test files (unit, integration, demo)
├── build/                   # Build and installer components
├── docs/                    # Documentation files
├── utils/                   # Utility components
├── assets/                  # Model and verification assets
│   ├── models/              # Model files
│   ├── encryption/          # Encryption keys and certificates
│   └── verification/        # Model verification data
├── logs/                    # Log files
├── sessions/                # User session data
├── data/                    # Application data files
├── temp/                    # Temporary files
└── static/                  # Static web assets
```

## Core Components (`core/`)

The heart of the TikTrue Platform, containing the main system functionality.

### Key Files:
- `model_node.py` - Main inference server
- `network_manager.py` - Network management
- `config_manager.py` - Configuration management
- `protocol_spec.py` - Communication protocol specifications
- `main_app.py` - Main application entry point
- `service_runner.py` - Windows service runner

## Worker Components (`workers/`)

Handles processing, scheduling, and performance optimization.

### Key Files:
- `worker_lib.py` - CPU and GPU worker implementations
- `scheduler_lib.py` - Task scheduling and distribution
- `homf_lib.py` - Model caching and fast loading
- `dynamic_profiler.py` - Dynamic system profiling
- `static_profiler.py` - Static profiling
- `paged_kv_cache_lib.py` - KV cache management
- `sequential_gpu_worker_lib.py` - Sequential GPU workers

## Interface Components (`interfaces/`)

User interfaces and interaction components.

### Key Files:
- `chatbot_interface.py` - Main chat interface
- `chat_interface.py` - Chat components
- `enhanced_chat_interface.py` - Enhanced chat interface
- `session_ui.py` - User session management
- `network_dashboard.py` - Network dashboard
- `first_run_wizard.py` - First-run setup wizard

## Network Components (`network/`)

Network communication and WebSocket handling.

### Key Files:
- `websocket_server.py` - Basic WebSocket server
- `unified_websocket_server.py` - Unified WebSocket server
- `enhanced_websocket_handler.py` - Enhanced WebSocket handler
- `network_discovery.py` - Local network discovery
- `api_client.py` - API client
- `backend_api_client.py` - Backend API client

## Security Components (`security/`)

Security, authentication, and license management.

### Key Files:
- `license_validator.py` - License validation
- `auth_manager.py` - Authentication management
- `crypto_layer.py` - Cryptography layer
- `hardware_fingerprint.py` - Hardware fingerprinting
- `access_control.py` - Access control
- `key_manager.py` - Key management

## Model Management Components (`models/`)

Model lifecycle management from download to usage.

### Key Files:
- `model_downloader.py` - Model downloading
- `model_encryption.py` - Model encryption
- `model_verification.py` - Model verification
- `model_selector.py` - Model selection
- `model_node_license_integration.py` - License and model integration

## Configuration (`config/`)

Configuration files for the platform.

### Key Files:
- `network_config.json` - Main network configuration
- `portable_config.json` - Portable deployment settings
- `performance_profile.json` - Performance profiling data
- `network_config_llama_single_node.json` - Single-node Llama configuration

## Testing (`tests/`)

Test files for ensuring system quality and functionality.

### Structure:
- `unit/` - Unit tests
- `integration/` - Integration tests
- `demo/` - Demonstration files

### Key File Patterns:
- `test_*.py` - Unit tests
- `demo_*.py` - Demonstration files
- `integration_test_suite.py` - Integration test suite

## Build System (`build/`)

Build and installer components.

### Key Files:
- `Build-Installer.ps1` - PowerShell build script
- `build_installer_complete.py` - Python build orchestrator
- `installer.nsi` - NSIS installer script
- `validate_installer_build.py` - Build validation

## Documentation (`docs/`)

Project documentation and guides.

### Key Files:
- `README_SETUP.md` - Setup guide
- `PRODUCTION_READY.md` - Production readiness guide
- `architecture.md` - Architecture documentation
- `PROJECT_STRUCTURE.md` - This document
- `KEY_MANAGEMENT_IMPLEMENTATION_SUMMARY.md` - Key management implementation
- `ENHANCED_WEBSOCKET_INTEGRATION.md` - WebSocket integration documentation

## Utilities (`utils/`)

Helper tools and utilities used throughout the project.

### Key Files:
- `setup_validator.py` - Setup validation
- `serialization_utils.py` - Serialization utilities
- `custom_logging.py` - Custom logging system
- `monitoring_system.py` - Monitoring system

## Assets (`assets/`)

Model files, encryption keys, and verification data.

### Structure:
- `models/` - Model files
  - `llama3_1_8b_fp16/` - Llama 3 1.8B model (FP16)
    - `blocks/` - Model blocks
    - `metadata.json` - Model metadata
  - `mistral_7b_int4/` - Mistral 7B model (INT4)
- `encryption/` - Encryption keys and certificates
- `verification/` - Model verification data

## Data Storage

Various data storage directories.

- `logs/` - Log files
- `sessions/` - User session data
- `data/` - Application data files
- `temp/` - Temporary files
- `static/` - Static web assets

## Root-Level Files

Important files in the project root.

- `start_server.py` - Server startup script
- `requirements.txt` - Python dependencies
- `windows_service.py` - Windows service implementation
- `resource_optimizer.py` - Resource optimization
- `monitoring_system.py` - System monitoring
- `session_manager.py` - Session management
- `subscription_manager.py` - Subscription management
- `update_imports.py` - Import updater
- `update_model_imports.py` - Model import updater

## Navigation Map for Developers

### Getting Started
1. Start with `docs/README_SETUP.md` for setup instructions
2. Examine `core/main_app.py` for the main application entry point
3. Review `config/network_config.json` for configuration settings

### Feature Development Workflow
1. Understand the feature requirements
2. Identify the relevant components (core, workers, interfaces, etc.)
3. Review existing implementations in those directories
4. Add new functionality following the established patterns
5. Add appropriate tests in the `tests/` directory
6. Update documentation in the `docs/` directory

### Common Development Tasks

#### Adding a New Model
1. Update `models/model_downloader.py`
2. Configure in `config/network_config.json`
3. Test with `tests/demo/demo_*.py`

#### Modifying Network Communication
1. Update relevant files in `network/`
2. Ensure compatibility with `core/protocol_spec.py`
3. Test with `tests/integration/` tests

#### Security Updates
1. Modify relevant files in `security/`
2. Update `crypto_layer.py` for encryption changes
3. Test thoroughly with security-focused tests

#### UI Enhancements
1. Modify relevant files in `interfaces/`
2. Test user experience flow
3. Update documentation if the interface changes significantly

## File Organization Principles

1. **Modularity**: Related functionality is grouped together
2. **Separation of Concerns**: Different aspects of the system are in different directories
3. **Discoverability**: File names clearly indicate their purpose
4. **Documentation**: Each directory contains a README.md explaining its purpose
5. **Testing**: Tests are organized to match the structure of the code they test

## Dependency Flow

```
User Interface (interfaces/) → Core System (core/) → Workers (workers/)
                            ↓                     ↓
                      Network (network/) → Security (security/)
                                         ↓
                                  Models (models/)
```

All components rely on:
- Configuration (config/)
- Utilities (utils/)

## Conclusion

This document provides a comprehensive overview of the TikTrue Platform project structure. By understanding this organization, developers can navigate the codebase efficiently and contribute effectively to the project. For more detailed information about specific components, refer to the README.md files in each directory and the other documentation files in the `docs/` directory.