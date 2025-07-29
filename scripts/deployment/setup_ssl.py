#!/usr/bin/env python3
"""
TikTrue Platform - SSL Certificate Setup Script

This script sets up SSL certificates using Let's Encrypt for the TikTrue platform:
- Automatic certificate generation for domain and API subdomain
- Automatic renewal setup with cron jobs
- Nginx configuration update for HTTPS
- Certificate validation and monitoring

Requirements: 3.4 - Domain configuration and SSL setup
"""

import os
import sys
import json
import time
import logging
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

class SSLCertificateManager:
    """SSL Certificate manager for TikTrue platform using Let's Encrypt"""
    
    def __init__(self, domain: str = "tiktrue.com", email: str = None, dry_run: bool = False):
        self.domain = domain
        self.api_domain = f"api.{domain}"
        self.email = email or f"admin@{domain}"
        self.dry_run = dry_run
        self.project_root = Path(__file__).parent.parent.parent
        self.certbot_path = "/usr/bin/certbot"
        self.letsencrypt_dir = Path("/etc/letsencrypt")
        self.webroot_path = Path("/var/www/certbot")
        
        # Setup logging
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging for SSL certificate management"""
        log_dir = self.project_root / "temp" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(log_dir / "ssl_setup.log", encoding='utf-8')
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
            
    def check_certbot_installed(self) -> bool:
        """Check if Certbot is installed"""
        self.logger.info("🔍 Checking if Certbot is installed...")
        
        success, stdout, stderr = self.execute_command("certbot --version", check=False)
        if success:
            version = stdout.strip() if stdout else stderr.strip()
            self.logger.info(f"✅ Certbot is installed: {version}")
            return True
        else:
            self.logger.error("❌ Certbot is not installed")
            return False
            
    def install_certbot(self) -> bool:
        """Install Certbot if not already installed"""
        if self.check_certbot_installed():
            return True
            
        self.logger.info("📦 Installing Certbot...")
        
        try:
            # Update package list
            self.execute_command("apt update")
            
            # Install snapd if not installed
            self.execute_command("apt install -y snapd")
            
            # Install certbot via snap
            self.execute_command("snap install --classic certbot")
            
            # Create symlink
            self.execute_command("ln -sf /snap/bin/certbot /usr/bin/certbot")
            
            self.logger.info("✅ Certbot installed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Certbot installation failed: {e}")
            return False
            
    def setup_webroot_directory(self) -> bool:
        """Setup webroot directory for Let's Encrypt challenges"""
        self.logger.info("📁 Setting up webroot directory...")
        
        try:
            if not self.dry_run:
                self.webroot_path.mkdir(parents=True, exist_ok=True)
                self.execute_command(f"chown -R www-data:www-data {self.webroot_path}")
                self.execute_command(f"chmod -R 755 {self.webroot_path}")
                
            self.logger.info(f"📁 Webroot directory ready: {self.webroot_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Webroot setup failed: {e}")
            return False
            
    def check_domain_accessibility(self) -> bool:
        """Check if domains are accessible via HTTP"""
        self.logger.info("🌐 Checking domain accessibility...")
        
        domains = [self.domain, self.api_domain]
        
        for domain in domains:
            try:
                # Test HTTP accessibility
                success, stdout, stderr = self.execute_command(
                    f"curl -I -s -o /dev/null -w '%{{http_code}}' http://{domain}/.well-known/acme-challenge/test",
                    check=False
                )
                
                if success and "200" in stdout:
                    self.logger.info(f"✅ Domain accessible: {domain}")
                else:
                    self.logger.warning(f"⚠️ Domain may not be properly configured: {domain}")
                    
            except Exception as e:
                self.logger.warning(f"⚠️ Could not test domain {domain}: {e}")
                
        return True
        
    def obtain_certificates(self) -> bool:
        """Obtain SSL certificates from Let's Encrypt"""
        self.logger.info("🔐 Obtaining SSL certificates from Let's Encrypt...")
        
        try:
            # Prepare certbot command
            domains = f"-d {self.domain} -d www.{self.domain} -d {self.api_domain}"
            
            certbot_command = f"""certbot certonly \\
                --webroot \\
                --webroot-path={self.webroot_path} \\
                {domains} \\
                --email {self.email} \\
                --agree-tos \\
                --non-interactive \\
                --expand \\
                --keep-until-expiring"""
                
            if self.dry_run:
                certbot_command += " --dry-run"
                
            success, stdout, stderr = self.execute_command(certbot_command)
            
            if success:
                self.logger.info("✅ SSL certificates obtained successfully")
                return True
            else:
                self.logger.error("❌ Failed to obtain SSL certificates")
                self.logger.error(f"Certbot output: {stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Certificate obtaining failed: {e}")
            return False
            
    def verify_certificates(self) -> bool:
        """Verify that certificates were created successfully"""
        self.logger.info("🔍 Verifying SSL certificates...")
        
        try:
            cert_path = self.letsencrypt_dir / "live" / self.domain
            
            required_files = [
                "fullchain.pem",
                "privkey.pem",
                "cert.pem",
                "chain.pem"
            ]
            
            for file_name in required_files:
                file_path = cert_path / file_name
                
                if not self.dry_run and not file_path.exists():
                    self.logger.error(f"❌ Certificate file missing: {file_path}")
                    return False
                    
                self.logger.info(f"✅ Certificate file found: {file_name}")
                
            # Check certificate validity
            if not self.dry_run:
                cert_file = cert_path / "cert.pem"
                success, stdout, stderr = self.execute_command(
                    f"openssl x509 -in {cert_file} -text -noout | grep -E 'Subject:|Not After'"
                )
                
                if success:
                    self.logger.info(f"📋 Certificate details:\n{stdout}")
                    
            self.logger.info("✅ SSL certificates verified successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Certificate verification failed: {e}")
            return False
            
    def setup_auto_renewal(self) -> bool:
        """Setup automatic certificate renewal"""
        self.logger.info("🔄 Setting up automatic certificate renewal...")
        
        try:
            # Create renewal script
            renewal_script = f"""#!/bin/bash
# TikTrue SSL Certificate Renewal Script
# This script is run by cron to automatically renew SSL certificates

LOG_FILE="/var/log/tiktrue_ssl_renewal.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$DATE] Starting SSL certificate renewal check..." >> $LOG_FILE

# Attempt renewal
/usr/bin/certbot renew --quiet --webroot --webroot-path={self.webroot_path} >> $LOG_FILE 2>&1

RENEWAL_EXIT_CODE=$?

if [ $RENEWAL_EXIT_CODE -eq 0 ]; then
    echo "[$DATE] Certificate renewal check completed successfully" >> $LOG_FILE
    
    # Test nginx configuration
    /usr/sbin/nginx -t >> $LOG_FILE 2>&1
    
    if [ $? -eq 0 ]; then
        # Reload nginx if configuration is valid
        /bin/systemctl reload nginx >> $LOG_FILE 2>&1
        echo "[$DATE] Nginx reloaded successfully" >> $LOG_FILE
    else
        echo "[$DATE] ERROR: Nginx configuration test failed" >> $LOG_FILE
    fi
else
    echo "[$DATE] ERROR: Certificate renewal failed with exit code $RENEWAL_EXIT_CODE" >> $LOG_FILE
fi

echo "[$DATE] SSL renewal process completed" >> $LOG_FILE
echo "" >> $LOG_FILE
"""
            
            script_path = Path("/opt/tiktrue/ssl_renewal.sh")
            
            if not self.dry_run:
                script_path.parent.mkdir(parents=True, exist_ok=True)
                with open(script_path, 'w') as f:
                    f.write(renewal_script)
                    
                self.execute_command(f"chmod +x {script_path}")
                self.execute_command(f"chown root:root {script_path}")
                
            # Setup cron job for automatic renewal (twice daily)
            cron_entry = f"0 */12 * * * root {script_path} >/dev/null 2>&1"
            cron_file = Path("/etc/cron.d/tiktrue-ssl-renewal")
            
            if not self.dry_run:
                with open(cron_file, 'w') as f:
                    f.write(cron_entry + "\n")
                    
                self.execute_command(f"chmod 644 {cron_file}")
                
            self.logger.info(f"🔄 Auto-renewal configured: {script_path}")
            self.logger.info("⏰ Renewal will run twice daily via cron")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Auto-renewal setup failed: {e}")
            return False
            
    def test_renewal(self) -> bool:
        """Test certificate renewal process"""
        self.logger.info("🧪 Testing certificate renewal...")
        
        try:
            success, stdout, stderr = self.execute_command(
                f"certbot renew --dry-run --webroot --webroot-path={self.webroot_path}"
            )
            
            if success:
                self.logger.info("✅ Certificate renewal test passed")
                return True
            else:
                self.logger.error("❌ Certificate renewal test failed")
                self.logger.error(f"Error details: {stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Renewal test failed: {e}")
            return False
            
    def create_ssl_monitoring_script(self) -> bool:
        """Create SSL certificate monitoring script"""
        self.logger.info("📊 Creating SSL monitoring script...")
        
        try:
            monitoring_script = f"""#!/bin/bash
# TikTrue SSL Certificate Monitoring Script

echo "=== TikTrue SSL Certificate Status ==="
echo "Date: $(date)"
echo

CERT_PATH="/etc/letsencrypt/live/{self.domain}"

if [ -f "$CERT_PATH/fullchain.pem" ]; then
    echo "=== Certificate Information ==="
    openssl x509 -in "$CERT_PATH/fullchain.pem" -text -noout | grep -E "Subject:|Issuer:|Not Before:|Not After:"
    
    echo
    echo "=== Certificate Expiry Check ==="
    EXPIRY_DATE=$(openssl x509 -in "$CERT_PATH/fullchain.pem" -noout -enddate | cut -d= -f2)
    EXPIRY_TIMESTAMP=$(date -d "$EXPIRY_DATE" +%s)
    CURRENT_TIMESTAMP=$(date +%s)
    DAYS_UNTIL_EXPIRY=$(( ($EXPIRY_TIMESTAMP - $CURRENT_TIMESTAMP) / 86400 ))
    
    echo "Certificate expires: $EXPIRY_DATE"
    echo "Days until expiry: $DAYS_UNTIL_EXPIRY"
    
    if [ $DAYS_UNTIL_EXPIRY -lt 30 ]; then
        echo "⚠️  WARNING: Certificate expires in less than 30 days!"
    elif [ $DAYS_UNTIL_EXPIRY -lt 7 ]; then
        echo "🚨 CRITICAL: Certificate expires in less than 7 days!"
    else
        echo "✅ Certificate expiry is OK"
    fi
    
    echo
    echo "=== SSL Configuration Test ==="
    echo "Testing HTTPS connectivity..."
    
    for domain in "{self.domain}" "{self.api_domain}"; do
        echo "Testing $domain..."
        curl -I -s -m 10 "https://$domain" | head -1
    done
    
    echo
    echo "=== Certificate Chain Validation ==="
    openssl verify -CAfile "$CERT_PATH/chain.pem" "$CERT_PATH/cert.pem"
    
else
    echo "❌ SSL certificate not found at $CERT_PATH"
fi

echo
echo "=== Certbot Status ==="
certbot certificates

echo
echo "=== Recent Renewal Logs ==="
if [ -f "/var/log/tiktrue_ssl_renewal.log" ]; then
    tail -n 20 /var/log/tiktrue_ssl_renewal.log
else
    echo "No renewal log found"
fi
"""
            
            script_path = Path("/opt/tiktrue/ssl_monitor.sh")
            
            if not self.dry_run:
                script_path.parent.mkdir(parents=True, exist_ok=True)
                with open(script_path, 'w') as f:
                    f.write(monitoring_script)
                    
                self.execute_command(f"chmod +x {script_path}")
                self.execute_command(f"chown tiktrue:tiktrue {script_path}")
                
            self.logger.info(f"📊 SSL monitoring script created: {script_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ SSL monitoring script creation failed: {e}")
            return False
            
    def update_nginx_ssl_config(self) -> bool:
        """Update Nginx configuration to use SSL certificates"""
        self.logger.info("🔧 Updating Nginx SSL configuration...")
        
        try:
            # The nginx configuration already includes SSL settings
            # We just need to test and reload nginx
            
            # Test nginx configuration
            success, stdout, stderr = self.execute_command("nginx -t")
            
            if not success:
                self.logger.error("❌ Nginx configuration test failed")
                self.logger.error(f"Error details: {stderr}")
                return False
                
            # Reload nginx to apply SSL configuration
            self.execute_command("systemctl reload nginx")
            
            # Verify nginx is running
            success, stdout, stderr = self.execute_command("systemctl is-active nginx", check=False)
            
            if success and "active" in stdout:
                self.logger.info("✅ Nginx reloaded with SSL configuration")
                return True
            else:
                self.logger.error("❌ Nginx is not active after reload")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Nginx SSL configuration update failed: {e}")
            return False
            
    def run_ssl_setup(self) -> bool:
        """Run complete SSL certificate setup"""
        self.logger.info("🚀 Starting TikTrue SSL certificate setup...")
        
        try:
            # Step 1: Install Certbot if needed
            if not self.install_certbot():
                return False
                
            # Step 2: Setup webroot directory
            if not self.setup_webroot_directory():
                return False
                
            # Step 3: Check domain accessibility
            if not self.check_domain_accessibility():
                self.logger.warning("⚠️ Domain accessibility check had issues, continuing anyway...")
                
            # Step 4: Obtain SSL certificates
            if not self.obtain_certificates():
                return False
                
            # Step 5: Verify certificates
            if not self.verify_certificates():
                return False
                
            # Step 6: Setup automatic renewal
            if not self.setup_auto_renewal():
                self.logger.warning("⚠️ Auto-renewal setup failed, continuing...")
                
            # Step 7: Test renewal process
            if not self.test_renewal():
                self.logger.warning("⚠️ Renewal test failed, continuing...")
                
            # Step 8: Create monitoring script
            if not self.create_ssl_monitoring_script():
                self.logger.warning("⚠️ Monitoring script creation failed, continuing...")
                
            # Step 9: Update Nginx configuration
            if not self.update_nginx_ssl_config():
                return False
                
            self.logger.info("🎉 TikTrue SSL certificate setup completed successfully!")
            self.logger.info(f"🔐 HTTPS is now available at: https://{self.domain}")
            self.logger.info(f"🔐 API HTTPS is now available at: https://{self.api_domain}")
            self.logger.info("🔄 Automatic renewal is configured")
            self.logger.info("📊 Run /opt/tiktrue/ssl_monitor.sh to check certificate status")
            
            return True
            
        except Exception as e:
            self.logger.error(f"💥 SSL setup failed: {e}")
            return False

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="TikTrue SSL Certificate Setup")
    parser.add_argument("--domain", default="tiktrue.com", help="Primary domain name")
    parser.add_argument("--email", help="Email address for Let's Encrypt registration")
    parser.add_argument("--dry-run", action="store_true", help="Perform dry run without making changes")
    
    args = parser.parse_args()
    
    ssl_manager = SSLCertificateManager(
        domain=args.domain,
        email=args.email,
        dry_run=args.dry_run
    )
    
    if ssl_manager.run_ssl_setup():
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()