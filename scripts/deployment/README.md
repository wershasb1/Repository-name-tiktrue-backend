# TikTrue Platform Deployment System

This directory contains the complete deployment orchestration system for the TikTrue platform, providing automated deployment with error handling and rollback capabilities.

## Files Overview

- **`deploy.py`** - Main deployment orchestration script (Python)
- **`deploy.bat`** - Windows deployment wrapper script
- **`deploy.sh`** - Unix/Linux/macOS deployment wrapper script
- **`deployment_config.json`** - Configuration template for deployment
- **`server_setup.yml`** - Ansible playbook for server setup
- **`README.md`** - This documentation file

## Prerequisites

### System Requirements
- Python 3.11+
- Node.js 18+
- Liara CLI (`npm install -g @liara/cli`)
- Git
- curl (for health checks)

### Account Requirements
- Liara account with hosting plan
- Domain configured (tiktrue.com)
- Backend app created on Liara (tiktrue-backend)
- Frontend app created on Liara (tiktrue-frontend)

## Quick Start

### Windows
```cmd
cd scripts\deployment
deploy.bat
```

### Unix/Linux/macOS
```bash
cd scripts/deployment
chmod +x deploy.sh
./deploy.sh
```

### Direct Python Usage
```bash
cd scripts/deployment
python deploy.py
```

## Configuration

### Default Configuration
The deployment script uses sensible defaults but can be customized using a configuration file:

```bash
python deploy.py --config deployment_config.json
```

### Configuration Options

```json
{
  "hosting": {
    "provider": "liara",
    "backend_app": "tiktrue-backend",
    "frontend_app": "tiktrue-frontend", 
    "domain": "tiktrue.com",
    "api_domain": "api.tiktrue.com"
  },
  "deployment": {
    "backup_enabled": true,
    "rollback_enabled": true,
    "health_check_timeout": 300,
    "retry_attempts": 3
  }
}
```

## Deployment Process

The deployment orchestrator follows these steps:

### 1. Backup Creation
- Creates timestamped backup of configuration files
- Stores backup in `temp/deployment_backups/`
- Enables rollback functionality

### 2. Prerequisites Validation
- Checks for required tools (Liara CLI, Node.js, Python)
- Validates project structure
- Verifies configuration files

### 3. Backend Deployment
- Installs Python dependencies
- Runs Django deployment checks
- Collects static files
- Deploys to Liara platform

### 4. Frontend Deployment
- Installs Node.js dependencies
- Builds React application
- Deploys to Liara platform

### 5. Database Setup
- Runs database migrations
- Collects static files on server
- Verifies database connectivity

### 6. Health Checks
- Tests backend API endpoints
- Verifies frontend accessibility
- Checks SSL certificates
- Validates CORS configuration

### 7. Cleanup
- Removes temporary build files
- Cleans up deployment artifacts

## Command Line Options

### Basic Usage
```bash
# Full deployment
python deploy.py

# Dry run (test without executing)
python deploy.py --dry-run

# Custom configuration
python deploy.py --config my_config.json

# Rollback to previous deployment
python deploy.py --rollback

# Rollback to specific backup
python deploy.py --rollback --backup-id 20250128_143022
```

### Advanced Options
```bash
# Combine options
python deploy.py --dry-run --config production_config.json
```

## Error Handling and Rollback

### Automatic Rollback
The deployment system automatically rolls back on failure if:
- `rollback_enabled` is true in configuration
- A backup was successfully created
- Any deployment step fails

### Manual Rollback
```bash
# List available backups
ls temp/deployment_backups/

# Rollback to specific backup
python deploy.py --rollback --backup-id BACKUP_ID
```

### Rollback Process
1. Stops current deployment
2. Restores configuration files from backup
3. Redeploys previous version to Liara
4. Runs health checks to verify rollback

## Logging and Monitoring

### Log Files
- **Location**: `temp/logs/deployment_TIMESTAMP.log`
- **Format**: Timestamped with log levels
- **Content**: Complete deployment process with errors

### Deployment State
- **Location**: `temp/deployment_backups/DEPLOYMENT_ID/deployment_state.json`
- **Content**: Current deployment status and completed steps
- **Usage**: Rollback and debugging information

### Example Log Output
```
2025-01-28 14:30:22 - INFO - 🚀 Starting TikTrue deployment orchestration - ID: 20250128_143022
2025-01-28 14:30:23 - INFO - 💾 Creating deployment backup...
2025-01-28 14:30:24 - INFO - ✅ Backup created successfully
2025-01-28 14:30:25 - INFO - 🔍 Validating deployment prerequisites...
2025-01-28 14:30:26 - INFO - ✅ All prerequisites validated successfully
```

## Server Setup (Optional)

For custom server deployment, use the Ansible playbook:

### Prerequisites
- Ansible installed
- SSH access to target server
- Ubuntu 22.04 LTS server

### Usage
```bash
# Configure inventory
echo "your-server-ip ansible_user=root" > inventory

# Run server setup
ansible-playbook -i inventory server_setup.yml
```

### Server Setup Includes
- System updates and security hardening
- Python 3.11 and Node.js 18 installation
- Nginx reverse proxy configuration
- SSL certificate setup (Certbot)
- Firewall configuration (UFW)
- Process management (systemd services)
- Backup and monitoring scripts

## Troubleshooting

### Common Issues

#### Liara CLI Not Found
```bash
npm install -g @liara/cli
liara login
```

#### Python Dependencies Missing
```bash
cd backend
pip install -r requirements.txt
```

#### Node.js Dependencies Missing
```bash
cd frontend
npm install
```

#### Permission Errors
```bash
# Unix/Linux/macOS
chmod +x scripts/deployment/deploy.sh

# Windows - Run as Administrator
```

#### Deployment Timeout
- Increase timeout in configuration
- Check network connectivity
- Verify Liara service status

### Debug Mode
Enable verbose logging by modifying the script:
```python
logging.basicConfig(level=logging.DEBUG)
```

### Health Check Failures
1. Check service logs: `liara logs --app APP_NAME`
2. Verify environment variables
3. Test endpoints manually with curl
4. Check database connectivity

## Security Considerations

### Sensitive Data
- Never commit API keys or secrets
- Use environment variables for sensitive configuration
- Rotate credentials regularly

### Backup Security
- Backups contain configuration files
- Store backups securely
- Clean up old backups regularly

### Network Security
- Use HTTPS for all communications
- Verify SSL certificates
- Configure proper CORS settings

## Maintenance

### Regular Tasks
- Update dependencies monthly
- Review deployment logs weekly
- Test rollback procedures quarterly
- Clean up old backups monthly

### Backup Cleanup
```bash
# Remove backups older than 30 days
find temp/deployment_backups -type d -mtime +30 -exec rm -rf {} +
```

### Log Rotation
Logs are automatically rotated, but you can manually clean:
```bash
# Remove logs older than 7 days
find temp/logs -name "*.log" -mtime +7 -delete
```

## Support and Contributing

### Getting Help
1. Check this README for common solutions
2. Review deployment logs for specific errors
3. Test with dry-run mode first
4. Verify prerequisites are met

### Contributing
1. Test changes with dry-run mode
2. Update documentation for new features
3. Follow existing code style
4. Add error handling for new functionality

## License

This deployment system is part of the TikTrue platform and follows the same licensing terms.