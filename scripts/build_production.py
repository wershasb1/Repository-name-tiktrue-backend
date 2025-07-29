#!/usr/bin/env python3
"""
TikTrue Platform - Production Build System

This script creates production-ready executables with:
- PyInstaller packaging for cross-platform executables
- PyArmor obfuscation for code protection
- Automated build process with error handling
- Version management and build validation

Requirements: 4.1 - Production build system setup
"""

import os
import sys
import json
import shutil
import logging
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

class ProductionBuilder:
    """Production build system for TikTrue desktop application"""
    
    def __init__(self, version: str = "1.0.0", enable_obfuscation: bool = True, dry_run: bool = False):
        self.version = version
        self.enable_obfuscation = enable_obfuscation
        self.dry_run = dry_run
        self.project_root = Path(__file__).parent.parent
        self.desktop_root = self.project_root / "desktop"
        self.build_dir = self.project_root / "build"
        self.dist_dir = self.project_root / "dist"
        self.temp_dir = None
        
        # Build configuration
        self.build_config = {
            "app_name": "TikTrue",
            "app_description": "TikTrue Distributed LLM Platform",
            "company": "TikTrue Technologies",
            "copyright": f"Copyright (c) {datetime.now().year} TikTrue Technologies",
            "main_script": "main_app.py",
            "service_script": "windows_service.py",
            "icon_file": "assets/icon.ico",
            "version": version,
            "build_date": datetime.now().isoformat()
        }
        
        # Setup logging
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging for build process"""
        log_dir = self.project_root / "temp" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(log_dir / "production_build.log", encoding='utf-8')
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def execute_command(self, command: str, cwd: Optional[Path] = None, check: bool = True) -> Tuple[bool, str, str]:
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
                cwd=cwd,
                timeout=1800  # 30 minutes timeout
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
            
    def check_dependencies(self) -> bool:
        """Check if required build dependencies are installed"""
        self.logger.info("🔍 Checking build dependencies...")
        
        dependencies = {
            "pyinstaller": "PyInstaller",
            "pyarmor": "PyArmor" if self.enable_obfuscation else None
        }
        
        missing_deps = []
        
        for cmd, name in dependencies.items():
            if name is None:
                continue
                
            success, stdout, stderr = self.execute_command(f"{cmd} --version", check=False)
            if success:
                version = stdout.strip() if stdout else stderr.strip()
                self.logger.info(f"✅ {name} is installed: {version}")
            else:
                self.logger.error(f"❌ {name} is not installed")
                missing_deps.append(name)
                
        if missing_deps:
            self.logger.error(f"❌ Missing dependencies: {', '.join(missing_deps)}")
            self.logger.info("💡 Install missing dependencies with:")
            for dep in missing_deps:
                if dep == "PyInstaller":
                    self.logger.info("   pip install pyinstaller")
                elif dep == "PyArmor":
                    self.logger.info("   pip install pyarmor")
            return False
            
        return True
        
    def prepare_build_environment(self) -> bool:
        """Prepare build environment and directories"""
        self.logger.info("📁 Preparing build environment...")
        
        try:
            # Create build directories
            self.build_dir.mkdir(exist_ok=True)
            self.dist_dir.mkdir(exist_ok=True)
            
            # Create temporary directory for obfuscation
            if self.enable_obfuscation:
                self.temp_dir = Path(tempfile.mkdtemp(prefix="tiktrue_build_"))
                self.logger.info(f"📁 Created temporary directory: {self.temp_dir}")
                
            # Clean previous builds
            if not self.dry_run:
                for item in self.build_dir.iterdir():
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                        
                for item in self.dist_dir.iterdir():
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                        
            self.logger.info("✅ Build environment prepared")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to prepare build environment: {e}")
            return False
            
    def create_version_info(self) -> bool:
        """Create version info file for Windows executable"""
        self.logger.info("📋 Creating version info file...")
        
        try:
            version_info = f"""# UTF-8
#
# For more details about fixed file info 'ffi' see:
# http://msdn.microsoft.com/en-us/library/ms646997.aspx
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({self.version.replace('.', ',')},0),
    prodvers=({self.version.replace('.', ',')},0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'040904B0',
          [StringStruct(u'CompanyName', u'{self.build_config["company"]}'),
           StringStruct(u'FileDescription', u'{self.build_config["app_description"]}'),
           StringStruct(u'FileVersion', u'{self.version}'),
           StringStruct(u'InternalName', u'{self.build_config["app_name"]}'),
           StringStruct(u'LegalCopyright', u'{self.build_config["copyright"]}'),
           StringStruct(u'OriginalFilename', u'{self.build_config["app_name"]}.exe'),
           StringStruct(u'ProductName', u'{self.build_config["app_name"]}'),
           StringStruct(u'ProductVersion', u'{self.version}')])
      ]), 
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
            
            version_file = self.build_dir / "version_info.txt"
            if not self.dry_run:
                with open(version_file, 'w', encoding='utf-8') as f:
                    f.write(version_info)
                    
            self.logger.info(f"📋 Version info created: {version_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to create version info: {e}")
            return False
            
    def obfuscate_code(self) -> bool:
        """Obfuscate Python code using PyArmor"""
        if not self.enable_obfuscation:
            self.logger.info("⏭️ Code obfuscation disabled, skipping...")
            return True
            
        self.logger.info("🔒 Starting code obfuscation with PyArmor...")
        
        try:
            # Create obfuscated directory
            obfuscated_dir = self.temp_dir / "obfuscated"
            obfuscated_dir.mkdir(exist_ok=True)
            
            # Copy source files to temporary directory
            source_files = [
                "main_app.py",
                "windows_service.py",
                "core",
                "interfaces",
                "models",
                "network",
                "security",
                "workers"
            ]
            
            temp_source_dir = self.temp_dir / "source"
            temp_source_dir.mkdir(exist_ok=True)
            
            for item in source_files:
                source_path = self.desktop_root / item
                if source_path.exists():
                    if source_path.is_file():
                        shutil.copy2(source_path, temp_source_dir / item)
                    else:
                        shutil.copytree(source_path, temp_source_dir / item, dirs_exist_ok=True)
                        
            # Initialize PyArmor project
            success, stdout, stderr = self.execute_command(
                f"pyarmor gen --output {obfuscated_dir} --recursive {temp_source_dir}/*.py"
            )
            
            if not success:
                self.logger.error("❌ PyArmor obfuscation failed")
                return False
                
            self.logger.info("✅ Code obfuscation completed")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Code obfuscation failed: {e}")
            return False
            
    def create_pyinstaller_spec(self) -> Path:
        """Create PyInstaller spec file for production build"""
        self.logger.info("📄 Creating PyInstaller spec file...")
        
        # Determine source directory (obfuscated or original)
        if self.enable_obfuscation and self.temp_dir:
            source_dir = self.temp_dir / "obfuscated"
            main_script = source_dir / "main_app.py"
        else:
            source_dir = self.desktop_root
            main_script = source_dir / "main_app.py"
            
        # Icon path
        icon_path = self.project_root / "assets" / "icon.ico"
        if not icon_path.exists():
            icon_path = None
            
        # Version info path
        version_info_path = self.build_dir / "version_info.txt"
        
        spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
# TikTrue Production Build Specification
# Generated on {datetime.now().isoformat()}

import sys
from pathlib import Path

# Build configuration
block_cipher = None
app_name = '{self.build_config["app_name"]}'
version = '{self.version}'

# Data files to include
datas = [
    ('{self.project_root / "config"}', 'config'),
    ('{self.project_root / "assets"}', 'assets'),
]

# Hidden imports for PyQt6 and other dependencies
hiddenimports = [
    'PyQt6.QtCore',
    'PyQt6.QtGui', 
    'PyQt6.QtWidgets',
    'PyQt6.sip',
    'asyncio',
    'websockets',
    'aiohttp',
    'aiofiles',
    'cryptography',
    'psutil',
    'wmi',
    'numpy',
    'onnxruntime',
    'transformers',
    'sentencepiece',
    'json',
    'sqlite3',
    'threading',
    'multiprocessing',
    'queue',
    'logging',
    'pathlib',
    'datetime',
    'hashlib',
    'base64',
    'uuid',
    'platform',
    'socket',
    'ssl',
    'urllib',
    'requests'
]

# Analysis
a = Analysis(
    ['{main_script}'],
    pathex=['{source_dir}'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'pandas',
        'jupyter',
        'notebook',
        'IPython',
        'tkinter'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    optimize=2,
)

# Remove duplicate binaries
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Main executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI application
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='{version_info_path}' if Path('{version_info_path}').exists() else None,
    icon='{icon_path}' if {icon_path is not None} else None,
)

# Windows Service executable (if needed)
service_exe = EXE(
    PYZ(Analysis(
        ['{source_dir / "windows_service.py"}'],
        pathex=['{source_dir}'],
        binaries=[],
        datas=datas,
        hiddenimports=hiddenimports,
        hookspath=[],
        hooksconfig={{}},
        runtime_hooks=[],
        excludes=[
            'matplotlib',
            'scipy', 
            'pandas',
            'jupyter',
            'notebook',
            'IPython',
            'tkinter'
        ],
        win_no_prefer_redirects=False,
        win_private_assemblies=False,
        cipher=block_cipher,
        noarchive=False,
        optimize=2,
    ).pure),
    Analysis(
        ['{source_dir / "windows_service.py"}'],
        pathex=['{source_dir}'],
        binaries=[],
        datas=datas,
        hiddenimports=hiddenimports,
        hookspath=[],
        hooksconfig={{}},
        runtime_hooks=[],
        excludes=[
            'matplotlib',
            'scipy',
            'pandas', 
            'jupyter',
            'notebook',
            'IPython',
            'tkinter'
        ],
        win_no_prefer_redirects=False,
        win_private_assemblies=False,
        cipher=block_cipher,
        noarchive=False,
        optimize=2,
    ).scripts,
    Analysis(
        ['{source_dir / "windows_service.py"}'],
        pathex=['{source_dir}'],
        binaries=[],
        datas=datas,
        hiddenimports=hiddenimports,
        hookspath=[],
        hooksconfig={{}},
        runtime_hooks=[],
        excludes=[
            'matplotlib',
            'scipy',
            'pandas',
            'jupyter', 
            'notebook',
            'IPython',
            'tkinter'
        ],
        win_no_prefer_redirects=False,
        win_private_assemblies=False,
        cipher=block_cipher,
        noarchive=False,
        optimize=2,
    ).binaries,
    Analysis(
        ['{source_dir / "windows_service.py"}'],
        pathex=['{source_dir}'],
        binaries=[],
        datas=datas,
        hiddenimports=hiddenimports,
        hookspath=[],
        hooksconfig={{}},
        runtime_hooks=[],
        excludes=[
            'matplotlib',
            'scipy',
            'pandas',
            'jupyter',
            'notebook', 
            'IPython',
            'tkinter'
        ],
        win_no_prefer_redirects=False,
        win_private_assemblies=False,
        cipher=block_cipher,
        noarchive=False,
        optimize=2,
    ).zipfiles,
    Analysis(
        ['{source_dir / "windows_service.py"}'],
        pathex=['{source_dir}'],
        binaries=[],
        datas=datas,
        hiddenimports=hiddenimports,
        hookspath=[],
        hooksconfig={{}},
        runtime_hooks=[],
        excludes=[
            'matplotlib',
            'scipy',
            'pandas',
            'jupyter',
            'notebook',
            'IPython',
            'tkinter'
        ],
        win_no_prefer_redirects=False,
        win_private_assemblies=False,
        cipher=block_cipher,
        noarchive=False,
        optimize=2,
    ).datas,
    [],
    name=f'{{app_name}}_Service',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Service runs in console mode
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='{version_info_path}' if Path('{version_info_path}').exists() else None,
    icon='{icon_path}' if {icon_path is not None} else None,
)
"""
        
        spec_file = self.build_dir / f"{self.build_config['app_name']}_Production.spec"
        
        if not self.dry_run:
            with open(spec_file, 'w', encoding='utf-8') as f:
                f.write(spec_content)
                
        self.logger.info(f"📄 PyInstaller spec created: {spec_file}")
        return spec_file
        
    def build_executable(self, spec_file: Path) -> bool:
        """Build executable using PyInstaller"""
        self.logger.info("🔨 Building executable with PyInstaller...")
        
        try:
            # Build command
            build_cmd = f"pyinstaller --clean --noconfirm --distpath {self.dist_dir} --workpath {self.build_dir} {spec_file}"
            
            success, stdout, stderr = self.execute_command(build_cmd, cwd=self.project_root)
            
            if not success:
                self.logger.error("❌ PyInstaller build failed")
                return False
                
            # Check if executables were created
            main_exe = self.dist_dir / f"{self.build_config['app_name']}.exe"
            service_exe = self.dist_dir / f"{self.build_config['app_name']}_Service.exe"
            
            if not self.dry_run:
                if not main_exe.exists():
                    self.logger.error(f"❌ Main executable not found: {main_exe}")
                    return False
                    
                if not service_exe.exists():
                    self.logger.warning(f"⚠️ Service executable not found: {service_exe}")
                    
            self.logger.info("✅ Executable build completed")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Executable build failed: {e}")
            return False
            
    def validate_build(self) -> bool:
        """Validate the built executable"""
        self.logger.info("🧪 Validating build...")
        
        try:
            main_exe = self.dist_dir / f"{self.build_config['app_name']}.exe"
            
            if self.dry_run:
                self.logger.info("🔍 DRY RUN: Would validate executable")
                return True
                
            if not main_exe.exists():
                self.logger.error(f"❌ Executable not found: {main_exe}")
                return False
                
            # Check file size (should be reasonable)
            file_size = main_exe.stat().st_size
            size_mb = file_size / (1024 * 1024)
            
            if size_mb < 10:
                self.logger.warning(f"⚠️ Executable seems too small: {size_mb:.1f}MB")
            elif size_mb > 500:
                self.logger.warning(f"⚠️ Executable seems too large: {size_mb:.1f}MB")
            else:
                self.logger.info(f"✅ Executable size looks good: {size_mb:.1f}MB")
                
            # Try to run executable with --version flag (if supported)
            success, stdout, stderr = self.execute_command(
                f'"{main_exe}" --help',
                check=False
            )
            
            if success:
                self.logger.info("✅ Executable runs successfully")
            else:
                self.logger.warning("⚠️ Could not test executable execution")
                
            self.logger.info("✅ Build validation completed")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Build validation failed: {e}")
            return False
            
    def create_build_info(self) -> bool:
        """Create build information file"""
        self.logger.info("📋 Creating build information...")
        
        try:
            build_info = {
                "app_name": self.build_config["app_name"],
                "version": self.version,
                "build_date": self.build_config["build_date"],
                "obfuscation_enabled": self.enable_obfuscation,
                "python_version": sys.version,
                "platform": sys.platform,
                "build_machine": os.environ.get("COMPUTERNAME", "unknown"),
                "files": []
            }
            
            # Add file information
            if not self.dry_run:
                for exe_file in self.dist_dir.glob("*.exe"):
                    file_info = {
                        "name": exe_file.name,
                        "size": exe_file.stat().st_size,
                        "size_mb": round(exe_file.stat().st_size / (1024 * 1024), 2)
                    }
                    build_info["files"].append(file_info)
                    
            build_info_file = self.dist_dir / "build_info.json"
            
            if not self.dry_run:
                with open(build_info_file, 'w', encoding='utf-8') as f:
                    json.dump(build_info, f, indent=2, ensure_ascii=False)
                    
            self.logger.info(f"📋 Build info created: {build_info_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to create build info: {e}")
            return False
            
    def cleanup(self) -> bool:
        """Clean up temporary files"""
        self.logger.info("🧹 Cleaning up temporary files...")
        
        try:
            if self.temp_dir and self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                self.logger.info(f"🧹 Removed temporary directory: {self.temp_dir}")
                
            self.logger.info("✅ Cleanup completed")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Cleanup failed: {e}")
            return False
            
    def run_build(self) -> bool:
        """Run complete production build process"""
        self.logger.info("🚀 Starting TikTrue production build...")
        
        try:
            # Step 1: Check dependencies
            if not self.check_dependencies():
                return False
                
            # Step 2: Prepare build environment
            if not self.prepare_build_environment():
                return False
                
            # Step 3: Create version info
            if not self.create_version_info():
                return False
                
            # Step 4: Obfuscate code (if enabled)
            if not self.obfuscate_code():
                return False
                
            # Step 5: Create PyInstaller spec
            spec_file = self.create_pyinstaller_spec()
            
            # Step 6: Build executable
            if not self.build_executable(spec_file):
                return False
                
            # Step 7: Validate build
            if not self.validate_build():
                return False
                
            # Step 8: Create build info
            if not self.create_build_info():
                return False
                
            # Step 9: Cleanup
            if not self.cleanup():
                self.logger.warning("⚠️ Cleanup failed, but build was successful")
                
            self.logger.info("🎉 TikTrue production build completed successfully!")
            self.logger.info(f"📦 Executables available in: {self.dist_dir}")
            
            if not self.dry_run:
                # List created files
                for exe_file in self.dist_dir.glob("*.exe"):
                    size_mb = exe_file.stat().st_size / (1024 * 1024)
                    self.logger.info(f"   📄 {exe_file.name} ({size_mb:.1f}MB)")
                    
            return True
            
        except Exception as e:
            self.logger.error(f"💥 Production build failed: {e}")
            return False

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="TikTrue Production Build System")
    parser.add_argument("--version", default="1.0.0", help="Application version")
    parser.add_argument("--no-obfuscation", action="store_true", help="Disable PyArmor obfuscation")
    parser.add_argument("--dry-run", action="store_true", help="Perform dry run without making changes")
    
    args = parser.parse_args()
    
    builder = ProductionBuilder(
        version=args.version,
        enable_obfuscation=not args.no_obfuscation,
        dry_run=args.dry_run
    )
    
    if builder.run_build():
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()