#!/usr/bin/env python3
"""
Offline Build Validation Script for RAG Document Assistant v2.0
Validates the integrity and completeness of offline distribution
"""

import os
import sys
import json
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple
import hashlib


class OfflineBuildValidator:
    """Validates offline distribution build"""
    
    def __init__(self, dist_path: str):
        self.dist_path = Path(dist_path)
        self.errors = []
        self.warnings = []
        self.info = []
        
    def log_error(self, message: str):
        """Log error message"""
        self.errors.append(message)
        print(f"❌ ERROR: {message}")
    
    def log_warning(self, message: str):
        """Log warning message"""
        self.warnings.append(message)
        print(f"⚠️  WARNING: {message}")
    
    def log_info(self, message: str):
        """Log info message"""
        self.info.append(message)
        print(f"ℹ️  INFO: {message}")
    
    def validate_archive_exists(self) -> bool:
        """Check if main archive exists"""
        print("\n📦 Checking main archive...")
        
        archive_pattern = "rag-assistant-v*-offline-windows-complete.zip"
        archives = list(self.dist_path.glob(archive_pattern))
        
        if not archives:
            self.log_error(f"Main archive not found in {self.dist_path}")
            return False
        
        if len(archives) > 1:
            self.log_warning(f"Multiple archives found: {[a.name for a in archives]}")
        
        archive_path = archives[0]
        size_mb = archive_path.stat().st_size / 1024 / 1024
        
        if size_mb < 1000:  # Less than 1GB
            self.log_warning(f"Archive size ({size_mb:.1f}MB) seems small for offline distribution")
        elif size_mb > 5000:  # More than 5GB
            self.log_warning(f"Archive size ({size_mb:.1f}MB) seems very large")
        else:
            self.log_info(f"Archive size: {size_mb:.1f}MB - looks reasonable")
        
        return True
    
    def validate_archive_structure(self) -> bool:
        """Validate internal archive structure"""
        print("\n📁 Checking archive structure...")
        
        archive_pattern = "rag-assistant-v*-offline-windows-complete.zip"
        archives = list(self.dist_path.glob(archive_pattern))
        
        if not archives:
            return False
        
        archive_path = archives[0]
        required_dirs = [
            "rag-assistant-offline/wheels/",
            "rag-assistant-offline/models/embedding/",
            "rag-assistant-offline/models/spacy/", 
            "rag-assistant-offline/app/",
            "rag-assistant-offline/tools/qdrant/",
            "rag-assistant-offline/config/",
            "rag-assistant-offline/scripts/",
            "rag-assistant-offline/docs/"
        ]
        
        try:
            with zipfile.ZipFile(archive_path, 'r') as zf:
                file_list = zf.namelist()
                
                for required_dir in required_dirs:
                    found = any(f.startswith(required_dir) for f in file_list)
                    if found:
                        self.log_info(f"Found directory: {required_dir}")
                    else:
                        self.log_error(f"Missing directory: {required_dir}")
                
                # Check for key files
                key_files = [
                    "rag-assistant-offline/manifest.json",
                    "rag-assistant-offline/scripts/install.ps1",
                    "rag-assistant-offline/scripts/install.bat",
                    "rag-assistant-offline/config/.env.offline"
                ]
                
                for key_file in key_files:
                    if key_file in file_list:
                        self.log_info(f"Found key file: {key_file}")
                    else:
                        self.log_error(f"Missing key file: {key_file}")
                
                # Count wheels
                wheel_files = [f for f in file_list if f.endswith('.whl')]
                if len(wheel_files) < 30:
                    self.log_warning(f"Only {len(wheel_files)} wheel files found - may be incomplete")
                else:
                    self.log_info(f"Found {len(wheel_files)} wheel files")
                
                # Check models
                model_files = [f for f in file_list if 'models/' in f and f.endswith(('.bin', '.json', '.tar.gz'))]
                if len(model_files) < 5:
                    self.log_warning(f"Only {len(model_files)} model files found - may be incomplete")
                else:
                    self.log_info(f"Found {len(model_files)} model files")
                
        except zipfile.BadZipFile:
            self.log_error("Archive is corrupted or not a valid ZIP file")
            return False
        except Exception as e:
            self.log_error(f"Error reading archive: {e}")
            return False
        
        return True
    
    def validate_manifest(self) -> bool:
        """Validate manifest file if available"""
        print("\n📋 Checking manifest...")
        
        archive_pattern = "rag-assistant-v*-offline-windows-complete.zip"
        archives = list(self.dist_path.glob(archive_pattern))
        
        if not archives:
            return False
        
        archive_path = archives[0]
        
        try:
            with zipfile.ZipFile(archive_path, 'r') as zf:
                manifest_path = "rag-assistant-offline/manifest.json"
                if manifest_path in zf.namelist():
                    manifest_data = zf.read(manifest_path)
                    manifest = json.loads(manifest_data.decode('utf-8'))
                    
                    # Validate manifest structure
                    required_keys = ['name', 'version', 'total_size_mb', 'components', 'models']
                    for key in required_keys:
                        if key in manifest:
                            self.log_info(f"Manifest has {key}: {manifest[key]}")
                        else:
                            self.log_warning(f"Manifest missing key: {key}")
                    
                    # Check models
                    if 'models' in manifest:
                        models = manifest['models']
                        if 'embedding_model' in models:
                            if models['embedding_model'] == 'intfloat/multilingual-e5-large':
                                self.log_info("Correct embedding model in manifest")
                            else:
                                self.log_warning(f"Unexpected embedding model: {models['embedding_model']}")
                        
                        if 'spacy_model' in models:
                            if models['spacy_model'] == 'ru_core_news_lg':
                                self.log_info("Correct SpaCy model in manifest")
                            else:
                                self.log_warning(f"Unexpected SpaCy model: {models['spacy_model']}")
                
                else:
                    self.log_warning("Manifest file not found in archive")
                    
        except Exception as e:
            self.log_error(f"Error reading manifest: {e}")
            return False
        
        return True
    
    def validate_checksums(self) -> bool:
        """Validate checksums if available"""
        print("\n🔐 Checking checksums...")
        
        archive_pattern = "rag-assistant-v*-offline-windows-complete.zip"
        archives = list(self.dist_path.glob(archive_pattern))
        
        if not archives:
            return False
        
        archive_path = archives[0]
        checksum_path = Path(str(archive_path) + ".sha256")
        
        if checksum_path.exists():
            try:
                # Read stored checksum
                with open(checksum_path, 'r') as f:
                    stored_hash = f.read().strip().split()[0]
                
                # Calculate actual checksum
                sha256_hash = hashlib.sha256()
                with open(archive_path, 'rb') as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        sha256_hash.update(chunk)
                actual_hash = sha256_hash.hexdigest()
                
                if stored_hash.lower() == actual_hash.lower():
                    self.log_info("Archive checksum verification passed")
                else:
                    self.log_error("Archive checksum verification failed")
                    self.log_error(f"Stored:  {stored_hash}")
                    self.log_error(f"Actual:  {actual_hash}")
                    return False
                    
            except Exception as e:
                self.log_error(f"Error verifying checksum: {e}")
                return False
        else:
            self.log_warning("No checksum file found")
        
        return True
    
    def validate_build_log(self) -> bool:
        """Check build log for errors"""
        print("\n📝 Checking build log...")
        
        build_log = self.dist_path / "build.log"
        if build_log.exists():
            try:
                with open(build_log, 'r', encoding='utf-8') as f:
                    log_content = f.read()
                
                # Check for error indicators
                error_indicators = ['ERROR:', 'Failed', 'Exception', 'Error:']
                errors_found = []
                
                for line_num, line in enumerate(log_content.split('\n'), 1):
                    for indicator in error_indicators:
                        if indicator in line:
                            errors_found.append(f"Line {line_num}: {line.strip()}")
                
                if errors_found:
                    self.log_warning(f"Found {len(errors_found)} potential errors in build log:")
                    for error in errors_found[:5]:  # Show first 5 errors
                        self.log_warning(f"  {error}")
                    if len(errors_found) > 5:
                        self.log_warning(f"  ... and {len(errors_found) - 5} more")
                else:
                    self.log_info("No obvious errors found in build log")
                
            except Exception as e:
                self.log_error(f"Error reading build log: {e}")
                return False
        else:
            self.log_warning("Build log not found")
        
        return True
    
    def validate_all(self) -> Tuple[bool, Dict]:
        """Run all validations"""
        print("🔍 RAG Document Assistant v2.0 - Offline Build Validator")
        print("=" * 60)
        
        results = {
            'archive_exists': self.validate_archive_exists(),
            'archive_structure': self.validate_archive_structure(), 
            'manifest': self.validate_manifest(),
            'checksums': self.validate_checksums(),
            'build_log': self.validate_build_log()
        }
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 Validation Summary:")
        print("=" * 60)
        
        all_passed = all(results.values())
        
        if all_passed and not self.errors:
            print("✅ All validations PASSED - Distribution is ready for deployment!")
        elif self.errors:
            print(f"❌ {len(self.errors)} ERRORS found - Distribution needs fixes")
            for error in self.errors:
                print(f"   • {error}")
        else:
            print(f"⚠️  Some validations failed but no critical errors")
        
        if self.warnings:
            print(f"\n⚠️  {len(self.warnings)} warnings:")
            for warning in self.warnings:
                print(f"   • {warning}")
        
        print(f"\nℹ️  Distribution path: {self.dist_path.absolute()}")
        
        return all_passed and not self.errors, results


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate offline distribution build")
    parser.add_argument("--dist-dir", "-d", default="dist", help="Distribution directory")
    
    args = parser.parse_args()
    
    dist_path = Path(args.dist_dir)
    if not dist_path.exists():
        print(f"❌ Distribution directory not found: {dist_path}")
        sys.exit(1)
    
    validator = OfflineBuildValidator(str(dist_path))
    success, results = validator.validate_all()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()