#!/usr/bin/env python3
"""
TikTrue Platform - Nginx Configuration Setup Script

This script sets up and configures Nginx for the TikTrue platform with:
- Reverse proxy configuration for Django backend
- Static file serving optimization
- Security headers and SSL preparation
- Rate limiting and performance optimization

Requirements: 3.4 - Domain configuration and SSL setup
"""

import os
import sys
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

class NginxConfigurator:
    """Nginx configuration manager for TikTrue platform"""
    
    def __init__(self, domain: str = "tiktrue.com", dry_run: bool = False):
        self.domain = domain
        self.api_domain = f"api.{domain}"
        self.dry_run = dry_run
        self.project_root = Path(__file__).parent.parent.parent
        self.nginx_conf_path = Path("/etc/nginx")
        self.sites_available = self.nginx_conf_path / "sites-available"
        self.sites_enabled = self.nginx_conf_path / "sites-enabled"
        
        # Setup logging
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging for nginx configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(self.project_root / "temp" / "logs" / "nginx_setup.log", encoding='utf-8')
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def execute_command(self, command: str, check: bool = True) -> Tuple[bool, str, str]:
        """Execute shell command with error handling"""
        if self.dry_run:
            self.logger.info(f"🔍 DRY RUN: Would execute: {command}")
            return True, "DRY RUN - Command not executed", ""
            
        self.logger.info(f"⚡ Executing: {command}")
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                self.logger.info(f"✅ Command succeeded: {command}")
                return True, result.stdout, result.stderr
            else:
                self.logger.error(f"❌ Command failed: {command}")
                self.logger.error(f"Error output: {result.stderr}")
                if check:
                    raise subprocess.CalledProcessError(result.returncode, command, result.stderr)
                return False, result.stdout, result.stderr
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"⏰ Command timed out: {command}")
            if check:
                raise
            return False, "", "Command timed out"
        except Exception as e:
            self.logger.error(f"💥 Command execution error: {e}")
            if check:
                raise
            return False, "", str(e)
            
    def check_nginx_installed(self) -> bool:
        """Check if Nginx is installed"""
        self.logger.info("🔍 Checking if Nginx is installed...")
        
        success, stdout, stderr = self.execute_command("nginx -v", check=False)
        if success:
            version = stderr.strip() if stderr else stdout.strip()
            self.logger.info(f"✅ Nginx is installed: {version}")
            return True
        else:
            self.logger.error("❌ Nginx is not installed")
            return False
            
    def install_nginx(self) -> bool:
        """Install Nginx if not already installed"""
        if self.check_nginx_installed():
            return True
            
        self.logger.info("📦 Installing Nginx...")
        
        try:
            # Update package list
            self.execute_command("apt update")
            
            # Install Nginx
            self.execute_command("apt install -y nginx")
            
            # Enable Nginx service
            self.execute_command("systemctl enable nginx")
            
            self.logger.info("✅ Nginx installed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Nginx installation failed: {e}")
            return False
            
    def backup_existing_config(self) -> bool:
        """Backup existing Nginx configuration"""
        self.logger.info("💾 Backing up existing Nginx configuration...")
        
        try:
            backup_dir = self.project_root / "temp" / "nginx_backup"
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Backup main nginx.conf
            if (self.nginx_conf_path / "nginx.conf").exists():
                shutil.copy2(
                    self.nginx_conf_path / "nginx.conf",
                    backup_dir / "nginx.conf.backup"
                )
                self.logger.info("📄 Backed up nginx.conf")
                
            # Backup sites-available
            if self.sites_available.exists():
                sites_backup = backup_dir / "sites-available"
                if sites_backup.exists():
                    shutil.rmtree(sites_backup)
                shutil.copytree(self.sites_available, sites_backup)
                self.logger.info("📁 Backed up sites-available directory")
                
            # Backup sites-enabled
            if self.sites_enabled.exists():
                enabled_backup = backup_dir / "sites-enabled"
                if enabled_backup.exists():
                    shutil.rmtree(enabled_backup)
                shutil.copytree(self.sites_enabled, enabled_backup)
                self.logger.info("📁 Backed up sites-enabled directory")
                
            self.logger.info(f"✅ Backup completed: {backup_dir}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Backup failed: {e}")
            return False
            
    def create_nginx_directories(self) -> bool:
        """Create necessary Nginx directories"""
        self.logger.info("📁 Creating Nginx directories...")
        
        try:
            directories = [
                "/var/log/nginx",
                "/var/www/certbot",
                "/opt/tiktrue/backend/staticfiles",
                "/opt/tiktrue/backend/media",
                "/opt/tiktrue/frontend/build/static"
            ]
            
            for directory in directories:
                dir_path = Path(directory)
                if not self.dry_run:
                    dir_path.mkdir(parents=True, exist_ok=True)
                    # Set appropriate permissions
                    if "tiktrue" in directory:
                        self.execute_command(f"chown -R tiktrue:tiktrue {directory}", check=False)
                    else:
                        self.execute_command(f"chown -R www-data:www-data {directory}", check=False)
                        
                self.logger.info(f"📁 Created directory: {directory}")
                
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Directory creation failed: {e}")
            return False
            
    def install_tiktrue_config(self) -> bool:
        """Install TikTrue Nginx configuration"""
        self.logger.info("⚙️ Installing TikTrue Nginx configuration...")
        
        try:
            # Copy our configuration file
            source_config = self.project_root / "scripts" / "deployment" / "nginx_tiktrue.conf"
            target_config = self.sites_available / "tiktrue"
            
            if not source_config.exists():
                self.logger.error(f"❌ Source configuration not found: {source_config}")
                return False
                
            if not self.dry_run:
                shutil.copy2(source_config, target_config)
                
                # Update domain names in configuration
                with open(target_config, 'r') as f:
                    config_content = f.read()
                    
                # Replace placeholder domains with actual domains
                config_content = config_content.replace("tiktrue.com", self.domain)
                config_content = config_content.replace("api.tiktrue.com", self.api_domain)
                
                with open(target_config, 'w') as f:
                    f.write(config_content)
                    
                # Set proper permissions
                self.execute_command(f"chown root:root {target_config}")
                self.execute_command(f"chmod 644 {target_config}")
                
            self.logger.info(f"📄 Installed configuration: {target_config}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Configuration installation failed: {e}")
            return False
            
    def enable_tiktrue_site(self) -> bool:
        """Enable TikTrue site in Nginx"""
        self.logger.info("🔗 Enabling TikTrue site...")
        
        try:
            source_link = self.sites_available / "tiktrue"
            target_link = self.sites_enabled / "tiktrue"
            
            # Remove existing link if it exists
            if target_link.exists() and not self.dry_run:
                target_link.unlink()
                
            # Create symbolic link
            if not self.dry_run:
                target_link.symlink_to(source_link)
                
            self.logger.info(f"🔗 Site enabled: {target_link} -> {source_link}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Site enabling failed: {e}")
            return False
            
    def disable_default_site(self) -> bool:
        """Disable default Nginx site"""
        self.logger.info("🚫 Disabling default Nginx site...")
        
        try:
            default_site = self.sites_enabled / "default"
            
            if default_site.exists() and not self.dry_run:
                default_site.unlink()
                self.logger.info("🚫 Default site disabled")
            else:
                self.logger.info("ℹ️ Default site already disabled or doesn't exist")
                
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Default site disabling failed: {e}")
            return False
            
    def test_nginx_config(self) -> bool:
        """Test Nginx configuration"""
        self.logger.info("🧪 Testing Nginx configuration...")
        
        try:
            success, stdout, stderr = self.execute_command("nginx -t")
            
            if success:
                self.logger.info("✅ Nginx configuration test passed")
                return True
            else:
                self.logger.error("❌ Nginx configuration test failed")
                self.logger.error(f"Error details: {stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Configuration test failed: {e}")
            return False
            
    def reload_nginx(self) -> bool:
        """Reload Nginx configuration"""
        self.logger.info("🔄 Reloading Nginx...")
        
        try:
            # First test the configuration
            if not self.test_nginx_config():
                return False
                
            # Reload Nginx
            self.execute_command("systemctl reload nginx")
            
            # Check if Nginx is running
            success, stdout, stderr = self.execute_command("systemctl is-active nginx", check=False)
            
            if success and "active" in stdout:
                self.logger.info("✅ Nginx reloaded successfully")
                return True
            else:
                self.logger.error("❌ Nginx is not active after reload")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Nginx reload failed: {e}")
            return False
            
    def setup_log_rotation(self) -> bool:
        """Setup log rotation for TikTrue logs"""
        self.logger.info("📋 Setting up log rotation...")
        
        try:
            logrotate_config = """
/var/log/nginx/tiktrue_*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 www-data adm
    sharedscripts
    prerotate
        if [ -d /etc/logrotate.d/httpd-prerotate ]; then \\
            run-parts /etc/logrotate.d/httpd-prerotate; \\
        fi
    endscript
    postrotate
        invoke-rc.d nginx rotate >/dev/null 2>&1
    endscript
}
"""
            
            logrotate_file = Path("/etc/logrotate.d/tiktrue-nginx")
            
            if not self.dry_run:
                with open(logrotate_file, 'w') as f:
                    f.write(logrotate_config.strip())
                    
                self.execute_command(f"chmod 644 {logrotate_file}")
                
            self.logger.info("📋 Log rotation configured")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Log rotation setup failed: {e}")
            return False
            
    def create_health_check_script(self) -> bool:
        """Create Nginx health check script"""
        self.logger.info("🏥 Creating health check script...")
        
        try:
            health_script = f"""#!/bin/bash
# TikTrue Nginx Health Check Script

echo "=== TikTrue Nginx Health Check ==="
echo "Date: $(date)"
echo

# Check Nginx status
echo "=== Nginx Status ==="
systemctl is-active nginx
systemctl status nginx --no-pager -l

echo
echo "=== Nginx Configuration Test ==="
nginx -t

echo
echo "=== Port Status ==="
netstat -tlnp | grep -E ':80|:443'

echo
echo "=== SSL Certificate Status ==="
if [ -f "/etc/letsencrypt/live/{self.domain}/fullchain.pem" ]; then
    openssl x509 -in /etc/letsencrypt/live/{self.domain}/fullchain.pem -text -noout | grep -E "Subject:|Not After"
else
    echo "SSL certificate not found"
fi

echo
echo "=== Log File Status ==="
ls -la /var/log/nginx/tiktrue_*.log 2>/dev/null || echo "No TikTrue log files found"

echo
echo "=== Recent Errors ==="
tail -n 10 /var/log/nginx/tiktrue_error.log 2>/dev/null || echo "No error log found"
"""
            
            script_path = Path("/opt/tiktrue/nginx_health_check.sh")
            
            if not self.dry_run:
                script_path.parent.mkdir(parents=True, exist_ok=True)
                with open(script_path, 'w') as f:
                    f.write(health_script)
                    
                self.execute_command(f"chmod +x {script_path}")
                self.execute_command(f"chown tiktrue:tiktrue {script_path}")
                
            self.logger.info(f"🏥 Health check script created: {script_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Health check script creation failed: {e}")
            return False
            
    def run_setup(self) -> bool:
        """Run complete Nginx setup"""
        self.logger.info("🚀 Starting TikTrue Nginx configuration setup...")
        
        try:
            # Step 1: Install Nginx if needed
            if not self.install_nginx():
                return False
                
            # Step 2: Backup existing configuration
            if not self.backup_existing_config():
                self.logger.warning("⚠️ Backup failed, continuing anyway...")
                
            # Step 3: Create necessary directories
            if not self.create_nginx_directories():
                return False
                
            # Step 4: Install TikTrue configuration
            if not self.install_tiktrue_config():
                return False
                
            # Step 5: Disable default site
            if not self.disable_default_site():
                return False
                
            # Step 6: Enable TikTrue site
            if not self.enable_tiktrue_site():
                return False
                
            # Step 7: Test configuration
            if not self.test_nginx_config():
                return False
                
            # Step 8: Setup log rotation
            if not self.setup_log_rotation():
                self.logger.warning("⚠️ Log rotation setup failed, continuing...")
                
            # Step 9: Create health check script
            if not self.create_health_check_script():
                self.logger.warning("⚠️ Health check script creation failed, continuing...")
                
            # Step 10: Reload Nginx
            if not self.reload_nginx():
                return False
                
            self.logger.info("🎉 TikTrue Nginx configuration completed successfully!")
            self.logger.info(f"🌐 Frontend will be available at: https://{self.domain}")
            self.logger.info(f"🔧 Backend API will be available at: https://{self.api_domain}")
            self.logger.info("⚠️ Note: SSL certificates need to be configured separately")
            
            return True
            
        except Exception as e:
            self.logger.error(f"💥 Nginx setup failed: {e}")
            return False

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="TikTrue Nginx Configuration Setup")
    parser.add_argument("--domain", default="tiktrue.com", help="Primary domain name")
    parser.add_argument("--dry-run", action="store_true", help="Perform dry run without making changes")
    
    args = parser.parse_args()
    
    configurator = NginxConfigurator(domain=args.domain, dry_run=args.dry_run)
    
    if configurator.run_setup():
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()