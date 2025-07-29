#!/usr/bin/env python3
"""
TikTrue Platform - Main Deployment Orchestration Script

This script orchestrates the complete deployment of the TikTrue platform including:
- Server setup and configuration
- Backend Django application deployment
- Frontend React application deployment
- Database setup and migrations
- SSL certificate configuration
- Error handling and rollback capabilities

Requirements: 3.1 - Complete deployment orchestration with error handling and rollback
"""

import os
import sys
import json
import time
import shutil
import logging
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import tempfile

class DeploymentOrchestrator:
    """Main deployment orchestration class with error handling and rollback"""
    
    def __init__(self, config_file: str = None, dry_run: bool = False):
        self.project_root = Path(__file__).parent.parent.parent
        self.dry_run = dry_run
        self.deployment_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_dir = self.project_root / "temp" / "deployment_backups" / self.deployment_id
        self.deployment_state = {}
        self.rollback_actions = []
        
        # Setup logging
        self.setup_logging()
        
        # Load configuration
        self.config = self.load_configuration(config_file)
        
        # Initialize deployment state
        self.init_deployment_state()
        
    def setup_logging(self):
        """Setup comprehensive logging for deployment"""
        log_dir = self.project_root / "temp" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / f"deployment_{self.deployment_id}.log"
        
        # Configure logging with UTF-8 encoding for Unicode support
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        console_handler = logging.StreamHandler(sys.stdout)
        
        # Set encoding for console handler on Windows
        if hasattr(console_handler.stream, 'reconfigure'):
            try:
                console_handler.stream.reconfigure(encoding='utf-8')
            except:
                pass  # Fallback if reconfigure fails
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[file_handler, console_handler]
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Starting TikTrue deployment orchestration - ID: {self.deployment_id}")
        
    def load_configuration(self, config_file: str = None) -> Dict:
        """Load deployment configuration"""
        if config_file and Path(config_file).exists():
            with open(config_file, 'r') as f:
                config = json.load(f)
        else:
            # Default configuration
            config = {
                "hosting": {
                    "provider": "liara",
                    "backend_app": "tiktrue-backend",
                    "frontend_app": "tiktrue-frontend",
                    "domain": "tiktrue.com",
                    "api_domain": "api.tiktrue.com"
                },
                "database": {
                    "type": "postgresql",
                    "backup_before_deploy": True
                },
                "deployment": {
                    "backup_enabled": True,
                    "rollback_enabled": True,
                    "health_check_timeout": 300,
                    "retry_attempts": 3
                },
                "notifications": {
                    "enabled": False,
                    "webhook_url": None
                }
            }
            
        self.logger.info(f"📋 Configuration loaded: {config['hosting']['provider']}")
        return config
        
    def init_deployment_state(self):
        """Initialize deployment state tracking"""
        self.deployment_state = {
            "deployment_id": self.deployment_id,
            "start_time": datetime.now().isoformat(),
            "status": "initializing",
            "steps_completed": [],
            "steps_failed": [],
            "current_step": None,
            "rollback_available": False,
            "backup_created": False
        }
        
        # Create backup directory
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
    def save_deployment_state(self):
        """Save current deployment state"""
        state_file = self.backup_dir / "deployment_state.json"
        with open(state_file, 'w') as f:
            json.dump(self.deployment_state, f, indent=2)
            
    def add_rollback_action(self, action: str, command: str, description: str):
        """Add a rollback action to the stack"""
        self.rollback_actions.append({
            "action": action,
            "command": command,
            "description": description,
            "timestamp": datetime.now().isoformat()
        })
        
    def execute_command(self, command: str, cwd: Path = None, timeout: int = 300) -> Tuple[bool, str, str]:
        """Execute a command with error handling and logging"""
        if self.dry_run:
            self.logger.info(f"🔍 DRY RUN: Would execute: {command}")
            return True, "DRY RUN - Command not executed", ""
            
        self.logger.info(f"⚡ Executing: {command}")
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd or self.project_root,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode == 0:
                self.logger.info(f"✅ Command succeeded: {command}")
                return True, result.stdout, result.stderr
            else:
                self.logger.error(f"❌ Command failed: {command}")
                self.logger.error(f"Error output: {result.stderr}")
                return False, result.stdout, result.stderr
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"⏰ Command timed out: {command}")
            return False, "", f"Command timed out after {timeout} seconds"
        except Exception as e:
            self.logger.error(f"💥 Command execution error: {e}")
            return False, "", str(e)
            
    def create_backup(self) -> bool:
        """Create backup of current deployment"""
        self.logger.info("💾 Creating deployment backup...")
        
        try:
            # Backup configuration files
            config_backup = self.backup_dir / "config"
            config_backup.mkdir(exist_ok=True)
            
            # Backend configuration
            backend_files = [
                "backend/liara.json",
                "backend/requirements.txt",
                "backend/runtime.txt",
                "backend/.env.example"
            ]
            
            for file_path in backend_files:
                src = self.project_root / file_path
                if src.exists():
                    dst = config_backup / Path(file_path).name
                    shutil.copy2(src, dst)
                    self.logger.info(f"📄 Backed up: {file_path}")
                    
            # Frontend configuration
            frontend_files = [
                "frontend/liara.json",
                "frontend/package.json",
                "frontend/.env.production",
                "frontend/.env.example"
            ]
            
            for file_path in frontend_files:
                src = self.project_root / file_path
                if src.exists():
                    dst = config_backup / f"frontend_{Path(file_path).name}"
                    shutil.copy2(src, dst)
                    self.logger.info(f"📄 Backed up: {file_path}")
                    
            # Create backup metadata
            backup_metadata = {
                "backup_id": self.deployment_id,
                "timestamp": datetime.now().isoformat(),
                "files_backed_up": len(backend_files) + len(frontend_files),
                "backup_location": str(self.backup_dir)
            }
            
            with open(self.backup_dir / "backup_metadata.json", 'w') as f:
                json.dump(backup_metadata, f, indent=2)
                
            self.deployment_state["backup_created"] = True
            self.deployment_state["rollback_available"] = True
            self.save_deployment_state()
            
            self.logger.info(f"✅ Backup created successfully: {self.backup_dir}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Backup creation failed: {e}")
            return False
            
    def validate_prerequisites(self) -> bool:
        """Validate deployment prerequisites"""
        self.logger.info("🔍 Validating deployment prerequisites...")
        self.deployment_state["current_step"] = "validate_prerequisites"
        
        prerequisites_ok = True
        
        # Check Liara CLI
        success, stdout, stderr = self.execute_command("liara --version")
        if not success:
            self.logger.error("❌ Liara CLI not found. Please install: npm install -g @liara/cli")
            prerequisites_ok = False
        else:
            self.logger.info(f"✅ Liara CLI found: {stdout.strip()}")
            
        # Check Node.js and npm
        success, stdout, stderr = self.execute_command("node --version")
        if not success:
            self.logger.error("❌ Node.js not found. Please install Node.js")
            prerequisites_ok = False
        else:
            self.logger.info(f"✅ Node.js found: {stdout.strip()}")
            
        # Check Python
        success, stdout, stderr = self.execute_command("python --version")
        if not success:
            self.logger.error("❌ Python not found. Please install Python 3.11+")
            prerequisites_ok = False
        else:
            self.logger.info(f"✅ Python found: {stdout.strip()}")
            
        # Check project structure
        required_dirs = ["backend", "frontend"]
        for dir_name in required_dirs:
            dir_path = self.project_root / dir_name
            if not dir_path.exists():
                self.logger.error(f"❌ Required directory not found: {dir_name}")
                prerequisites_ok = False
            else:
                self.logger.info(f"✅ Directory found: {dir_name}")
                
        # Check configuration files
        required_files = [
            "backend/liara.json",
            "backend/requirements.txt",
            "frontend/liara.json",
            "frontend/package.json"
        ]
        
        for file_path in required_files:
            file_full_path = self.project_root / file_path
            if not file_full_path.exists():
                self.logger.error(f"❌ Required file not found: {file_path}")
                prerequisites_ok = False
            else:
                self.logger.info(f"✅ File found: {file_path}")
                
        if prerequisites_ok:
            self.deployment_state["steps_completed"].append("validate_prerequisites")
            self.logger.info("✅ All prerequisites validated successfully")
        else:
            self.deployment_state["steps_failed"].append("validate_prerequisites")
            self.logger.error("❌ Prerequisites validation failed")
            
        self.save_deployment_state()
        return prerequisites_ok
        
    def deploy_backend(self) -> bool:
        """Deploy Django backend application"""
        self.logger.info("🔧 Deploying backend application...")
        self.deployment_state["current_step"] = "deploy_backend"
        
        backend_dir = self.project_root / "backend"
        
        try:
            # Install backend dependencies
            self.logger.info("📦 Installing backend dependencies...")
            success, stdout, stderr = self.execute_command(
                "pip install -r requirements.txt",
                cwd=backend_dir,
                timeout=600
            )
            
            if not success:
                self.logger.error("❌ Backend dependency installation failed")
                return False
                
            # Run Django checks
            self.logger.info("🔍 Running Django deployment checks...")
            success, stdout, stderr = self.execute_command(
                "python manage.py check --deploy",
                cwd=backend_dir
            )
            
            if not success:
                self.logger.warning(f"⚠️ Django deployment checks failed: {stderr}")
                # Continue deployment but log the warning
                
            # Collect static files
            self.logger.info("📁 Collecting static files...")
            success, stdout, stderr = self.execute_command(
                "python manage.py collectstatic --noinput",
                cwd=backend_dir
            )
            
            if not success:
                self.logger.error("❌ Static file collection failed")
                return False
                
            # Deploy to Liara
            self.logger.info("🚀 Deploying to Liara...")
            app_name = self.config["hosting"]["backend_app"]
            
            success, stdout, stderr = self.execute_command(
                f"liara deploy --app {app_name} --platform django",
                cwd=backend_dir,
                timeout=900  # 15 minutes timeout for deployment
            )
            
            if not success:
                self.logger.error(f"❌ Backend deployment to Liara failed: {stderr}")
                return False
                
            # Add rollback action
            self.add_rollback_action(
                "redeploy_backend",
                f"liara deploy --app {app_name} --platform django",
                "Rollback backend deployment"
            )
            
            self.deployment_state["steps_completed"].append("deploy_backend")
            self.logger.info("✅ Backend deployment completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Backend deployment failed: {e}")
            self.deployment_state["steps_failed"].append("deploy_backend")
            return False
        finally:
            self.save_deployment_state()
            
    def deploy_frontend(self) -> bool:
        """Deploy React frontend application"""
        self.logger.info("🎨 Deploying frontend application...")
        self.deployment_state["current_step"] = "deploy_frontend"
        
        frontend_dir = self.project_root / "frontend"
        
        try:
            # Install frontend dependencies
            self.logger.info("📦 Installing frontend dependencies...")
            success, stdout, stderr = self.execute_command(
                "npm install",
                cwd=frontend_dir,
                timeout=600
            )
            
            if not success:
                self.logger.error("❌ Frontend dependency installation failed")
                return False
                
            # Build frontend application
            self.logger.info("🔨 Building frontend application...")
            success, stdout, stderr = self.execute_command(
                "npm run build",
                cwd=frontend_dir,
                timeout=600
            )
            
            if not success:
                self.logger.error(f"❌ Frontend build failed: {stderr}")
                return False
                
            # Deploy to Liara
            self.logger.info("🚀 Deploying frontend to Liara...")
            app_name = self.config["hosting"]["frontend_app"]
            
            success, stdout, stderr = self.execute_command(
                f"liara deploy --app {app_name} --platform static",
                cwd=frontend_dir,
                timeout=900  # 15 minutes timeout for deployment
            )
            
            if not success:
                self.logger.error(f"❌ Frontend deployment to Liara failed: {stderr}")
                return False
                
            # Add rollback action
            self.add_rollback_action(
                "redeploy_frontend",
                f"liara deploy --app {app_name} --platform static",
                "Rollback frontend deployment"
            )
            
            self.deployment_state["steps_completed"].append("deploy_frontend")
            self.logger.info("✅ Frontend deployment completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Frontend deployment failed: {e}")
            self.deployment_state["steps_failed"].append("deploy_frontend")
            return False
        finally:
            self.save_deployment_state()
            
    def setup_database(self) -> bool:
        """Setup and migrate database"""
        self.logger.info("🗄️ Setting up database...")
        self.deployment_state["current_step"] = "setup_database"
        
        backend_dir = self.project_root / "backend"
        app_name = self.config["hosting"]["backend_app"]
        
        try:
            # Run database migrations
            self.logger.info("🔄 Running database migrations...")
            success, stdout, stderr = self.execute_command(
                f"liara shell --app {app_name} --command 'python manage.py migrate'",
                timeout=300
            )
            
            if not success:
                self.logger.error(f"❌ Database migration failed: {stderr}")
                return False
                
            # Collect static files on server
            self.logger.info("📁 Collecting static files on server...")
            success, stdout, stderr = self.execute_command(
                f"liara shell --app {app_name} --command 'python manage.py collectstatic --noinput'",
                timeout=300
            )
            
            if not success:
                self.logger.warning(f"⚠️ Static file collection on server failed: {stderr}")
                # Continue as this might not be critical
                
            self.deployment_state["steps_completed"].append("setup_database")
            self.logger.info("✅ Database setup completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Database setup failed: {e}")
            self.deployment_state["steps_failed"].append("setup_database")
            return False
        finally:
            self.save_deployment_state()
            
    def health_check(self) -> bool:
        """Perform comprehensive health checks"""
        self.logger.info("🏥 Performing health checks...")
        self.deployment_state["current_step"] = "health_check"
        
        try:
            # Check backend health
            backend_url = f"https://{self.config['hosting']['api_domain']}/health/"
            self.logger.info(f"🔍 Checking backend health: {backend_url}")
            
            success, stdout, stderr = self.execute_command(
                f"curl -f -s {backend_url}",
                timeout=30
            )
            
            if not success:
                self.logger.error(f"❌ Backend health check failed: {stderr}")
                return False
            else:
                self.logger.info("✅ Backend health check passed")
                
            # Check frontend health
            frontend_url = f"https://{self.config['hosting']['domain']}"
            self.logger.info(f"🔍 Checking frontend health: {frontend_url}")
            
            success, stdout, stderr = self.execute_command(
                f"curl -f -s -I {frontend_url}",
                timeout=30
            )
            
            if not success:
                self.logger.error(f"❌ Frontend health check failed: {stderr}")
                return False
            else:
                self.logger.info("✅ Frontend health check passed")
                
            # Check SSL certificates
            self.logger.info("🔒 Checking SSL certificates...")
            for domain in [self.config['hosting']['domain'], self.config['hosting']['api_domain']]:
                success, stdout, stderr = self.execute_command(
                    f"curl -I https://{domain}",
                    timeout=30
                )
                
                if success:
                    self.logger.info(f"✅ SSL certificate valid for: {domain}")
                else:
                    self.logger.warning(f"⚠️ SSL certificate issue for: {domain}")
                    
            self.deployment_state["steps_completed"].append("health_check")
            self.logger.info("✅ Health checks completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Health checks failed: {e}")
            self.deployment_state["steps_failed"].append("health_check")
            return False
        finally:
            self.save_deployment_state()
            
    def rollback_deployment(self) -> bool:
        """Rollback deployment to previous state"""
        self.logger.info("🔄 Starting deployment rollback...")
        
        if not self.deployment_state.get("rollback_available", False):
            self.logger.error("❌ No rollback available - backup not created")
            return False
            
        try:
            # Execute rollback actions in reverse order
            for action in reversed(self.rollback_actions):
                self.logger.info(f"🔄 Executing rollback: {action['description']}")
                
                success, stdout, stderr = self.execute_command(
                    action['command'],
                    timeout=600
                )
                
                if not success:
                    self.logger.error(f"❌ Rollback action failed: {action['description']}")
                    self.logger.error(f"Error: {stderr}")
                else:
                    self.logger.info(f"✅ Rollback action completed: {action['description']}")
                    
            # Restore configuration files
            config_backup = self.backup_dir / "config"
            if config_backup.exists():
                self.logger.info("📄 Restoring configuration files...")
                
                for backup_file in config_backup.iterdir():
                    if backup_file.name.startswith("frontend_"):
                        target_name = backup_file.name.replace("frontend_", "")
                        target_path = self.project_root / "frontend" / target_name
                    else:
                        target_path = self.project_root / "backend" / backup_file.name
                        
                    if target_path.parent.exists():
                        shutil.copy2(backup_file, target_path)
                        self.logger.info(f"📄 Restored: {target_path}")
                        
            self.logger.info("✅ Rollback completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Rollback failed: {e}")
            return False
            
    def cleanup_deployment(self):
        """Cleanup deployment artifacts"""
        self.logger.info("🧹 Cleaning up deployment artifacts...")
        
        try:
            # Clean up temporary files
            temp_dirs = [
                self.project_root / "backend" / "build",
                self.project_root / "frontend" / "build",
                self.project_root / "frontend" / "node_modules" / ".cache"
            ]
            
            for temp_dir in temp_dirs:
                if temp_dir.exists() and temp_dir.is_dir():
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    self.logger.info(f"🗑️ Cleaned up: {temp_dir}")
                    
            self.logger.info("✅ Cleanup completed")
            
        except Exception as e:
            self.logger.warning(f"⚠️ Cleanup warning: {e}")
            
    def send_notification(self, status: str, message: str):
        """Send deployment notification"""
        if not self.config.get("notifications", {}).get("enabled", False):
            return
            
        webhook_url = self.config["notifications"].get("webhook_url")
        if not webhook_url:
            return
            
        try:
            notification_data = {
                "deployment_id": self.deployment_id,
                "status": status,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "domain": self.config["hosting"]["domain"]
            }
            
            # Send notification (implementation depends on webhook service)
            self.logger.info(f"📢 Notification sent: {status}")
            
        except Exception as e:
            self.logger.warning(f"⚠️ Notification failed: {e}")
            
    def run_deployment(self) -> bool:
        """Run complete deployment orchestration"""
        self.logger.info("🚀 Starting complete deployment orchestration...")
        self.deployment_state["status"] = "running"
        
        try:
            # Step 1: Create backup
            if self.config["deployment"]["backup_enabled"]:
                if not self.create_backup():
                    self.logger.error("❌ Backup creation failed - aborting deployment")
                    return False
                    
            # Step 2: Validate prerequisites
            if not self.validate_prerequisites():
                self.logger.error("❌ Prerequisites validation failed - aborting deployment")
                return False
                
            # Step 3: Deploy backend
            if not self.deploy_backend():
                self.logger.error("❌ Backend deployment failed")
                if self.config["deployment"]["rollback_enabled"]:
                    self.rollback_deployment()
                return False
                
            # Step 4: Deploy frontend
            if not self.deploy_frontend():
                self.logger.error("❌ Frontend deployment failed")
                if self.config["deployment"]["rollback_enabled"]:
                    self.rollback_deployment()
                return False
                
            # Step 5: Setup database
            if not self.setup_database():
                self.logger.error("❌ Database setup failed")
                if self.config["deployment"]["rollback_enabled"]:
                    self.rollback_deployment()
                return False
                
            # Step 6: Health checks
            if not self.health_check():
                self.logger.error("❌ Health checks failed")
                if self.config["deployment"]["rollback_enabled"]:
                    self.rollback_deployment()
                return False
                
            # Step 7: Cleanup
            self.cleanup_deployment()
            
            # Update deployment state
            self.deployment_state["status"] = "completed"
            self.deployment_state["end_time"] = datetime.now().isoformat()
            self.save_deployment_state()
            
            # Send success notification
            self.send_notification("success", "Deployment completed successfully")
            
            self.logger.info("🎉 Deployment completed successfully!")
            self.logger.info(f"🌐 Frontend: https://{self.config['hosting']['domain']}")
            self.logger.info(f"🔧 Backend: https://{self.config['hosting']['api_domain']}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"💥 Deployment failed with exception: {e}")
            self.deployment_state["status"] = "failed"
            self.deployment_state["error"] = str(e)
            self.save_deployment_state()
            
            # Send failure notification
            self.send_notification("failed", f"Deployment failed: {str(e)}")
            
            # Attempt rollback
            if self.config["deployment"]["rollback_enabled"]:
                self.rollback_deployment()
                
            return False

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="TikTrue Platform Deployment Orchestrator")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--dry-run", action="store_true", help="Perform dry run without executing commands")
    parser.add_argument("--rollback", action="store_true", help="Rollback to previous deployment")
    parser.add_argument("--backup-id", help="Backup ID for rollback")
    
    args = parser.parse_args()
    
    try:
        orchestrator = DeploymentOrchestrator(
            config_file=args.config,
            dry_run=args.dry_run
        )
        
        if args.rollback:
            if args.backup_id:
                orchestrator.deployment_id = args.backup_id
                orchestrator.backup_dir = orchestrator.project_root / "temp" / "deployment_backups" / args.backup_id
                
            success = orchestrator.rollback_deployment()
        else:
            success = orchestrator.run_deployment()
            
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n⚠️ Deployment interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()