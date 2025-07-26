# TikTrue Distributed LLM Platform - User Setup Guide

## Table of Contents
1. [Overview](#overview)
2. [System Requirements](#system-requirements)
3. [Installation Guide](#installation-guide)
4. [Admin Mode Setup](#admin-mode-setup)
5. [Client Mode Setup](#client-mode-setup)
6. [Troubleshooting](#troubleshooting)
7. [Advanced Configuration](#advanced-configuration)
8. [FAQ](#faq)

## Overview

The TikTrue Distributed LLM Platform enables you to run Large Language Models in a distributed manner. The system supports two modes:

- **Admin Mode**: Host and manage local LLM networks, download models, and control client access
- **Client Mode**: Connect to admin networks and use distributed models offline

## System Requirements

### Minimum Requirements
- **Operating System**: Windows 10/11 (64-bit)
- **RAM**: 8 GB (16 GB recommended)
- **Storage**: 50 GB free space (more for models)
- **Network**: Local network connectivity
- **Python**: 3.11 or higher (automatically installed)

### Recommended Requirements
- **RAM**: 32 GB or more
- **Storage**: 500 GB SSD
- **GPU**: NVIDIA GPU with 8GB+ VRAM (for better performance)
- **Network**: Gigabit Ethernet

## Installation Guide

### Step 1: Download the Installer

1. Visit the TikTrue website and log into your account
2. Navigate to the Downloads section
3. Download the latest TikTrue Platform installer
4. Verify the installer integrity (checksum provided on website)

### Step 2: Run the Installation

1. **Right-click** the installer and select "Run as administrator"
2. Follow the installation wizard:
   - Accept the license agreement
   - Choose installation directory (default recommended)
   - Select components to install
   - Choose whether to install as Windows service
3. Wait for installation to complete
4. Click "Finish" to complete installation

### Step 3: First Launch

1. Launch TikTrue from the desktop shortcut or Start menu
2. The application will prompt you to select a mode:
   - Choose **Admin Mode** if you want to host models
   - Choose **Client Mode** if you want to connect to existing networks
3. Your selection will be saved for future launches

## Admin Mode Setup

### Initial Setup

1. **Login with Website Credentials**
   ```
   - Enter your TikTrue account email and password
   - The system will validate your license online
   - Your hardware will be bound to your license
   ```

2. **License Validation**
   ```
   - System automatically validates your subscription plan
   - Downloads allowed models based on your plan
   - Configures client limits and expiry dates
   ```

3. **Model Download**
   ```
   - Models are automatically downloaded based on your plan
   - Models are encrypted and stored securely
   - Download progress is shown in the interface
   ```

### Creating Networks

1. **Network Creation**
   - Click "Create Network" in the admin interface
   - Enter network name and description
   - Select which model to use for this network
   - Configure maximum number of clients
   - Enable/disable encryption (recommended: enabled)

2. **Network Management**
   - View active networks in the dashboard
   - Monitor connected clients
   - Approve/reject connection requests
   - View resource usage and statistics

### Client Management

1. **Approval System**
   - Client connection requests appear in the "Pending Requests" section
   - Review client information before approval
   - Approve or reject requests with optional notes
   - Monitor active client connections

2. **Resource Allocation**
   - Set resource limits per client
   - Monitor CPU/GPU usage
   - Balance load across multiple clients
   - Configure priority levels

## Client Mode Setup

### Network Discovery

1. **Automatic Discovery**
   ```
   - Launch TikTrue in Client Mode
   - The system automatically scans for available networks
   - Available admin networks are listed in the interface
   ```

2. **Manual Connection**
   ```
   - If automatic discovery fails, use manual connection
   - Enter admin node IP address and port
   - Click "Connect" to send connection request
   ```

### Connection Process

1. **Send Connection Request**
   - Select desired network from the list
   - Click "Request Connection"
   - Provide any required information
   - Wait for admin approval

2. **Model Transfer**
   - Once approved, model blocks are transferred automatically
   - Transfer progress is shown in the interface
   - Models are encrypted during transfer
   - System validates model integrity

### Using Models

1. **Chat Interface**
   - Access the chat interface once models are loaded
   - Type your questions or prompts
   - Receive responses from the distributed model
   - Save conversation history

2. **Offline Operation**
   - Once models are transferred, no internet connection is required
   - All inference happens locally
   - Models remain encrypted and secure

## Troubleshooting

### Common Issues

#### Installation Problems

**Issue**: "Installation failed with error code 1603"
```
Solution:
1. Run installer as administrator
2. Temporarily disable antivirus software
3. Ensure sufficient disk space
4. Check Windows Event Log for details
```

**Issue**: "Python installation failed"
```
Solution:
1. Download Python 3.11+ manually from python.org
2. Install Python with "Add to PATH" option
3. Restart the TikTrue installer
```

#### Admin Mode Issues

**Issue**: "Login failed - invalid credentials"
```
Solution:
1. Verify your TikTrue account credentials
2. Check internet connection
3. Try password reset if necessary
4. Contact support if issue persists
```

**Issue**: "Model download failed"
```
Solution:
1. Check internet connection stability
2. Verify sufficient disk space
3. Temporarily disable firewall/antivirus
4. Restart the download process
```

**Issue**: "Network creation failed"
```
Solution:
1. Check if required ports are available (8700-8702)
2. Verify firewall settings allow TikTrue
3. Ensure no other applications are using the ports
4. Try different port numbers in settings
```

#### Client Mode Issues

**Issue**: "No networks found"
```
Solution:
1. Ensure you're on the same local network as admin
2. Check firewall settings on both admin and client
3. Verify admin node is running and has created networks
4. Try manual connection with admin IP address
```

**Issue**: "Connection request rejected"
```
Solution:
1. Contact the admin to approve your request
2. Verify you're using correct network credentials
3. Check if network has reached client limit
4. Ensure your license tier is compatible
```

**Issue**: "Model transfer failed"
```
Solution:
1. Check network stability between admin and client
2. Verify sufficient disk space on client
3. Restart both admin and client applications
4. Check firewall settings for data transfer ports
```

### Diagnostic Tools

#### Built-in Diagnostics

Run the diagnostic tool to check system health:

```bash
# From TikTrue installation directory
python tests/demo/troubleshooting_diagnostic_tools.py
```

The diagnostic tool checks:
- System resources (CPU, memory, disk)
- Network connectivity
- License validation
- Model availability
- Service status

#### Log Files

Check log files for detailed error information:

```
Location: TikTrue Installation Directory/logs/
Files:
- main.log - General application logs
- network.log - Network-related logs
- license.log - License validation logs
- security.log - Security and encryption logs
```

#### Performance Monitoring

Monitor system performance:

```bash
# Run performance tests
python tests/integration/test_performance_load.py
```

## Advanced Configuration

### Configuration Files

#### Network Configuration
```json
// config/network_config.json
{
  "discovery_port": 8900,
  "admin_api_port": 8701,
  "client_api_port": 8702,
  "max_clients_per_network": 10,
  "encryption_enabled": true,
  "discovery_timeout": 30,
  "transfer_timeout": 300
}
```

#### Performance Configuration
```json
// config/performance_profile.json
{
  "cpu_workers": 4,
  "gpu_workers": 1,
  "memory_limit_gb": 16,
  "model_cache_size": 2,
  "inference_batch_size": 1,
  "enable_gpu_acceleration": true
}
```

### Windows Service Configuration

#### Install as Service
```cmd
# Run as administrator
sc create TikTrueService binPath="C:\Program Files\TikTrue\service_runner.exe"
sc config TikTrueService start=auto
sc start TikTrueService
```

#### Service Management
```cmd
# Check service status
sc query TikTrueService

# Stop service
sc stop TikTrueService

# Start service
sc start TikTrueService

# Remove service
sc delete TikTrueService
```

### Firewall Configuration

#### Windows Firewall Rules

Allow TikTrue through Windows Firewall:

1. Open Windows Defender Firewall
2. Click "Allow an app or feature through Windows Defender Firewall"
3. Click "Change Settings" then "Allow another app..."
4. Browse to TikTrue installation directory
5. Add both `main_app.exe` and `service_runner.exe`
6. Enable for both Private and Public networks

#### Port Configuration

Ensure these ports are open:

```
Inbound Rules:
- Port 8700: Admin WebSocket API
- Port 8701: Admin HTTP API  
- Port 8702: Client API
- Port 8900: Network Discovery (UDP)

Outbound Rules:
- Port 443: HTTPS (for license validation)
- Port 80: HTTP (for model downloads)
```

### Security Configuration

#### Certificate Management

Generate new certificates if needed:

```bash
# Generate admin certificate
openssl req -x509 -newkey rsa:4096 -keyout admin_key.pem -out admin_cert.pem -days 365

# Generate client certificate
openssl req -x509 -newkey rsa:4096 -keyout client_key.pem -out client_cert.pem -days 365
```

#### License Security

Protect your license:

1. Never share license keys
2. Report suspicious activity immediately
3. Regularly check license usage in admin panel
4. Use hardware binding for additional security

## FAQ

### General Questions

**Q: Can I run both Admin and Client mode on the same machine?**
A: No, you must choose one mode per installation. Install TikTrue twice in different directories if you need both modes.

**Q: How many clients can connect to one admin?**
A: This depends on your license plan and hardware resources. Pro plans typically support 10-50 clients.

**Q: Do I need internet connection after initial setup?**
A: No, TikTrue works completely offline after initial license validation and model download.

### Technical Questions

**Q: Which models are supported?**
A: TikTrue supports ONNX-format models including Llama, Mistral, and other popular LLMs. Available models depend on your subscription plan.

**Q: Can I use my own models?**
A: Enterprise plans support custom model uploads. Contact support for custom model integration.

**Q: What happens if my license expires?**
A: Model access is immediately disabled. Renew your license online to restore functionality.

### Troubleshooting Questions

**Q: Why is model inference slow?**
A: Check system resources, enable GPU acceleration if available, and ensure sufficient RAM. Consider upgrading hardware for better performance.

**Q: Why can't clients find my admin network?**
A: Verify firewall settings, ensure both devices are on the same network, and check that network discovery is enabled.

**Q: How do I backup my configuration?**
A: Copy the entire TikTrue installation directory, especially the `config/` and `certs/` folders.

## Support

### Getting Help

1. **Documentation**: Check this guide and other documentation files
2. **Diagnostic Tools**: Run built-in diagnostics to identify issues
3. **Log Files**: Check log files for error details
4. **Community Forum**: Visit the TikTrue community forum
5. **Support Ticket**: Create a support ticket for technical issues

### Contact Information

- **Website**: https://www.tiktrue.com
- **Support Email**: support@tiktrue.com
- **Community Forum**: https://forum.tiktrue.com
- **Documentation**: https://docs.tiktrue.com

### Reporting Issues

When reporting issues, please include:

1. TikTrue version number
2. Operating system and version
3. Hardware specifications
4. Error messages and log files
5. Steps to reproduce the issue
6. Diagnostic report output

---

**Last Updated**: December 2024  
**Version**: 1.0.0  
**Document**: USER_SETUP_GUIDE.md