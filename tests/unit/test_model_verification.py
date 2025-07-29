"""
Tests for model verification and security checks
Tests checksum verification, source validation, and hardware compatibility checks
"""

import unittest
import tempfile
import shutil
import json
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from datetime import datetime

from models.model_verification import (
    ModelVerifier,
    VerificationStatus,
    VerificationType,
    VerificationResult,
    ModelVerificationSummary,
    verify_model_file,
    is_model_verified,
    create_model_verifier
)

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class TestModelVerification(unittest.TestCase):
    """Test model verification functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.verification_dir = Path(self.temp_dir) / "verification"
        self.verification_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test model file
        self.model_dir = Path(self.temp_dir) / "models"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        self.test_model_path = self.model_dir / "test_model.bin"
        with open(self.test_model_path, 'wb') as f:
            f.write(b"This is a test model file for verification testing.")
        
        # Calculate actual checksum
        import hashlib
        sha256 = hashlib.sha256()
        with open(self.test_model_path, 'rb') as f:
            sha256.update(f.read())
        self.test_model_checksum = sha256.hexdigest()
    
    def tearDown(self):
        """Clean up after tests"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_verifier_initialization(self):
        """Test model verifier initialization"""
        verifier = ModelVerifier(str(self.verification_dir))
        
        # Verify initialization
        self.assertEqual(verifier.verification_dir, self.verification_dir)
        self.assertEqual(len(verifier.verification_cache), 0)
        self.assertTrue(self.verification_dir.exists())
    
    def test_checksum_verification_success(self):
        """Test successful checksum verification"""
        verifier = ModelVerifier(str(self.verification_dir))
        
        # Verify with correct checksum
        result = verifier.verify_checksum(str(self.test_model_path), self.test_model_checksum)
        
        # Verify result
        self.assertEqual(result.verification_type, VerificationType.CHECKSUM)
        self.assertEqual(result.status, VerificationStatus.VERIFIED)
        self.assertIn("algorithm", result.details)
        self.assertIn("expected", result.details)
        self.assertIn("calculated", result.details)
        self.assertEqual(result.details["expected"], self.test_model_checksum)
    
    def test_checksum_verification_failure(self):
        """Test failed checksum verification"""
        verifier = ModelVerifier(str(self.verification_dir))
        
        # Verify with incorrect checksum
        result = verifier.verify_checksum(str(self.test_model_path), "invalid_checksum")
        
        # Verify result
        self.assertEqual(result.verification_type, VerificationType.CHECKSUM)
        self.assertEqual(result.status, VerificationStatus.FAILED)
        self.assertEqual(result.error_message, "Checksum mismatch")
        self.assertNotEqual(result.details["expected"], result.details["calculated"])
    
    def test_source_verification_trusted(self):
        """Test trusted source verification"""
        verifier = ModelVerifier(str(self.verification_dir))
        
        # Test trusted sources
        trusted_urls = [
            "https://huggingface.co/models/llama-7b",
            "https://cdn-lfs.huggingface.co/llama-7b.bin",
            "https://api.openai.com/v1/models",
            "https://models.tiktrue.com/llama-7b.bin"
        ]
        
        for url in trusted_urls:
            result = verifier.verify_source(url)
            self.assertEqual(result.status, VerificationStatus.VERIFIED)
            self.assertEqual(result.verification_type, VerificationType.SOURCE)
            self.assertIn("trusted_source", result.details)
    
    def test_source_verification_untrusted(self):
        """Test untrusted source verification"""
        verifier = ModelVerifier(str(self.verification_dir))
        
        # Test untrusted sources
        untrusted_urls = [
            "https://example.com/models/llama-7b.bin",
            "https://malicious-site.com/fake-model.bin",
            "http://insecure-protocol.com/model.bin"
        ]
        
        for url in untrusted_urls:
            result = verifier.verify_source(url)
            self.assertEqual(result.status, VerificationStatus.FAILED)
            self.assertEqual(result.verification_type, VerificationType.SOURCE)
            self.assertEqual(result.error_message, "Untrusted source domain")
    
    @patch('models.model_verification.ModelVerifier._get_system_hardware_info')
    def test_hardware_compatibility_check_pass(self, mock_get_hardware):
        """Test hardware compatibility check passing"""
        # Mock hardware info with sufficient resources
        mock_get_hardware.return_value = {
            "platform": "Windows",
            "processor": "Intel Core i9",
            "ram_gb": 64.0,
            "vram_gb": 32.0,
            "gpu_info": {
                "detected": True,
                "vendor": "NVIDIA",
                "name": "RTX 4090",
                "vram_gb": 32.0
            }
        }
        
        verifier = ModelVerifier(str(self.verification_dir))
        
        # Test with different model types
        models = ["llama-7b", "llama-13b", "gpt-4"]
        
        for model_id in models:
            result = verifier.verify_hardware_compatibility(model_id)
            self.assertEqual(result.status, VerificationStatus.VERIFIED)
            self.assertEqual(result.verification_type, VerificationType.HARDWARE)
            self.assertIn("requirements", result.details)
            self.assertIn("system", result.details)
    
    @patch('models.model_verification.ModelVerifier._get_system_hardware_info')
    def test_hardware_compatibility_check_fail(self, mock_get_hardware):
        """Test hardware compatibility check failing"""
        # Mock hardware info with insufficient resources
        mock_get_hardware.return_value = {
            "platform": "Windows",
            "processor": "Intel Core i3",
            "ram_gb": 4.0,
            "vram_gb": 2.0,
            "gpu_info": {
                "detected": True,
                "vendor": "NVIDIA",
                "name": "GTX 1050",
                "vram_gb": 2.0
            }
        }
        
        verifier = ModelVerifier(str(self.verification_dir))
        
        # Test with large model
        result = verifier.verify_hardware_compatibility("llama-70b")
        self.assertEqual(result.status, VerificationStatus.FAILED)
        self.assertEqual(result.verification_type, VerificationType.HARDWARE)
        self.assertEqual(result.error_message, "Insufficient hardware resources")
    
    def test_malware_scan_safe_file(self):
        """Test malware scan with safe file"""
        verifier = ModelVerifier(str(self.verification_dir))
        
        # Create test files with safe extensions
        safe_extensions = [".bin", ".pt", ".pth", ".ckpt", ".safetensors", ".gguf"]
        
        for ext in safe_extensions:
            test_file = self.model_dir / f"safe_model{ext}"
            with open(test_file, 'wb') as f:
                f.write(b"Safe model content")
            
            result = verifier.scan_for_malware(str(test_file))
            self.assertEqual(result.status, VerificationStatus.VERIFIED)
            self.assertEqual(result.verification_type, VerificationType.MALWARE)
    
    def test_malware_scan_suspicious_file(self):
        """Test malware scan with suspicious file"""
        verifier = ModelVerifier(str(self.verification_dir))
        
        # Create executable file
        exe_file = self.model_dir / "suspicious.exe"
        with open(exe_file, 'wb') as f:
            # Write MZ header (Windows executable)
            f.write(b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xFF\xFF")
            f.write(b"Suspicious content")
        
        result = verifier.scan_for_malware(str(exe_file))
        self.assertEqual(result.status, VerificationStatus.FAILED)
        self.assertEqual(result.verification_type, VerificationType.MALWARE)
        self.assertIn("suspicious", result.error_message.lower())
    
    def test_full_model_verification_success(self):
        """Test full model verification success"""
        verifier = ModelVerifier(str(self.verification_dir))
        
        # Mock hardware check to always succeed
        with patch.object(verifier, 'verify_hardware_compatibility', 
                         return_value=VerificationResult(
                             verification_type=VerificationType.HARDWARE,
                             status=VerificationStatus.VERIFIED
                         )):
            
            # Verify model with correct checksum and trusted source
            summary = verifier.verify_model(
                model_id="test_model",
                model_path=str(self.test_model_path),
                expected_checksum=self.test_model_checksum,
                source_url="https://huggingface.co/models/test_model.bin"
            )
            
            # Verify summary
            self.assertEqual(summary.model_id, "test_model")
            self.assertEqual(summary.overall_status, VerificationStatus.VERIFIED)
            self.assertIsNotNone(summary.verified_at)
            self.assertGreaterEqual(len(summary.results), 3)  # At least checksum, source, and hardware
            
            # Verify individual results
            self.assertEqual(summary.results[VerificationType.CHECKSUM].status, VerificationStatus.VERIFIED)
            self.assertEqual(summary.results[VerificationType.SOURCE].status, VerificationStatus.VERIFIED)
            self.assertEqual(summary.results[VerificationType.HARDWARE].status, VerificationStatus.VERIFIED)
    
    def test_full_model_verification_failure(self):
        """Test full model verification failure"""
        verifier = ModelVerifier(str(self.verification_dir))
        
        # Verify model with incorrect checksum
        summary = verifier.verify_model(
            model_id="test_model",
            model_path=str(self.test_model_path),
            expected_checksum="invalid_checksum",
            source_url="https://example.com/test_model.bin"  # Untrusted source
        )
        
        # Verify summary
        self.assertEqual(summary.model_id, "test_model")
        self.assertEqual(summary.overall_status, VerificationStatus.FAILED)
        self.assertIsNone(summary.verified_at)
        
        # Verify individual results
        self.assertEqual(summary.results[VerificationType.CHECKSUM].status, VerificationStatus.FAILED)
        self.assertEqual(summary.results[VerificationType.SOURCE].status, VerificationStatus.FAILED)


    def test_utility_functions(self):
        """Test utility functions"""
        # Test create_model_verifier
        verifier = create_model_verifier(str(self.verification_dir))
        self.assertIsInstance(verifier, ModelVerifier)
        self.assertEqual(verifier.verification_dir, self.verification_dir)
        
        # Test verify_model_file utility
        with patch.object(ModelVerifier, 'verify_model') as mock_verify:
            mock_summary = ModelVerificationSummary(
                model_id="test_model",
                model_path=str(self.test_model_path),
                overall_status=VerificationStatus.VERIFIED
            )
            mock_verify.return_value = mock_summary
            
            result = verify_model_file("test_model", str(self.test_model_path), self.test_model_checksum)
            self.assertEqual(result.overall_status, VerificationStatus.VERIFIED)
            mock_verify.assert_called_once()
        
        # Test is_model_verified utility
        with patch.object(ModelVerifier, 'get_verification_status') as mock_get_status:
            # Test verified model
            mock_summary = ModelVerificationSummary(
                model_id="verified_model",
                model_path=str(self.test_model_path),
                overall_status=VerificationStatus.VERIFIED
            )
            mock_get_status.return_value = mock_summary
            
            self.assertTrue(is_model_verified("verified_model"))
            
            # Test unverified model
            mock_summary.overall_status = VerificationStatus.FAILED
            mock_get_status.return_value = mock_summary
            
            self.assertFalse(is_model_verified("failed_model"))
            
            # Test non-existent model
            mock_get_status.return_value = None
            
            self.assertFalse(is_model_verified("non_existent_model"))
    
    def test_hash_algorithm_detection(self):
        """Test hash algorithm detection"""
        verifier = ModelVerifier(str(self.verification_dir))
        
        # Test different hash lengths
        test_cases = [
            ("a" * 32, "md5"),
            ("b" * 40, "sha1"),
            ("c" * 64, "sha256"),
            ("d" * 128, "sha512"),
            ("e" * 16, "sha256")  # Unknown length defaults to sha256
        ]
        
        for checksum, expected_algo in test_cases:
            algo = verifier._determine_hash_algorithm(checksum)
            self.assertEqual(algo, expected_algo)
    
    def test_model_hardware_requirements(self):
        """Test model hardware requirements mapping"""
        verifier = ModelVerifier(str(self.verification_dir))
        
        # Test known models
        test_cases = [
            ("llama-7b-chat", "llama-7b"),
            ("llama-13b-instruct", "llama-13b"),
            ("llama-70b-code", "llama-70b"),
            ("gpt-4-turbo", "gpt-4"),
            ("unknown-model", "default")
        ]
        
        for model_id, expected_family in test_cases:
            requirements = verifier._get_model_hardware_requirements(model_id)
            
            if expected_family == "default":
                expected_reqs = verifier.HARDWARE_REQUIREMENTS["default"]
            else:
                expected_reqs = verifier.HARDWARE_REQUIREMENTS[expected_family]
            
            self.assertEqual(requirements, expected_reqs)
    
    def test_verification_cache(self):
        """Test verification result caching"""
        verifier = ModelVerifier(str(self.verification_dir))
        
        # Create test summary
        summary = ModelVerificationSummary(
            model_id="cache_test",
            model_path=str(self.test_model_path),
            overall_status=VerificationStatus.VERIFIED
        )
        
        # Add to cache
        verifier.verification_cache["cache_test"] = summary
        
        # Test cache retrieval
        cached_summary = verifier.get_verification_status("cache_test")
        self.assertEqual(cached_summary.model_id, "cache_test")
        self.assertEqual(cached_summary.overall_status, VerificationStatus.VERIFIED)
        
        # Test cache clearing
        verifier.clear_verification_cache()
        self.assertEqual(len(verifier.verification_cache), 0)
    
    def test_error_handling(self):
        """Test error handling in verification"""
        verifier = ModelVerifier(str(self.verification_dir))
        
        # Test with non-existent file
        result = verifier.verify_checksum("/non/existent/file.bin", "test_checksum")
        self.assertEqual(result.status, VerificationStatus.FAILED)
        self.assertIn("not found", result.error_message.lower())
        
        # Test malware scan with non-existent file
        result = verifier.scan_for_malware("/non/existent/file.bin")
        self.assertEqual(result.status, VerificationStatus.FAILED)
        self.assertIn("not found", result.error_message.lower())
        
        # Test full verification with non-existent file
        summary = verifier.verify_model(
            model_id="error_test",
            model_path="/non/existent/file.bin",
            expected_checksum="test_checksum"
        )
        self.assertEqual(summary.overall_status, VerificationStatus.FAILED)


class TestVerificationDataClasses(unittest.TestCase):
    """Test verification data classes"""
    
    def test_verification_result_serialization(self):
        """Test VerificationResult serialization"""
        result = VerificationResult(
            verification_type=VerificationType.CHECKSUM,
            status=VerificationStatus.VERIFIED,
            details={"test": "data"},
            error_message="test error"
        )
        
        # Test to_dict
        data = result.to_dict()
        
        self.assertEqual(data["verification_type"], "checksum")
        self.assertEqual(data["status"], "verified")
        self.assertEqual(data["details"], {"test": "data"})
        self.assertEqual(data["error_message"], "test error")
        self.assertIn("timestamp", data)
    
    def test_model_verification_summary_serialization(self):
        """Test ModelVerificationSummary serialization"""
        summary = ModelVerificationSummary(
            model_id="test_model",
            model_path="/path/to/model.bin",
            overall_status=VerificationStatus.VERIFIED,
            verified_at=datetime.now(),
            verified_by="test_host"
        )
        
        # Add verification result
        result = VerificationResult(
            verification_type=VerificationType.CHECKSUM,
            status=VerificationStatus.VERIFIED
        )
        summary.results[VerificationType.CHECKSUM] = result
        
        # Test to_dict
        data = summary.to_dict()
        
        self.assertEqual(data["model_id"], "test_model")
        self.assertEqual(data["model_path"], "/path/to/model.bin")
        self.assertEqual(data["overall_status"], "verified")
        self.assertEqual(data["verified_by"], "test_host")
        self.assertIn("verified_at", data)
        self.assertIn("results", data)
        self.assertIn("checksum", data["results"])


class TestModelVerificationIntegration(unittest.TestCase):
    """Integration tests for model verification"""
    
    def setUp(self):
        """Set up integration test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.verification_dir = Path(self.temp_dir) / "verification"
        self.model_dir = Path(self.temp_dir) / "models"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        # Create multiple test model files
        self.test_models = {}
        
        for i, model_name in enumerate(["llama-7b", "gpt-4", "mistral-7b"]):
            model_path = self.model_dir / f"{model_name}.bin"
            content = f"Test model content for {model_name} - {i * 100}".encode()
            
            with open(model_path, 'wb') as f:
                f.write(content)
            
            # Calculate checksum
            import hashlib
            sha256 = hashlib.sha256()
            sha256.update(content)
            checksum = sha256.hexdigest()
            
            self.test_models[model_name] = {
                "path": model_path,
                "checksum": checksum,
                "content": content
            }
    
    def tearDown(self):
        """Clean up integration test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('models.model_verification.ModelVerifier._get_system_hardware_info')
    def test_multiple_model_verification(self, mock_get_hardware):
        """Test verification of multiple models"""
        # Mock sufficient hardware
        mock_get_hardware.return_value = {
            "platform": "Windows",
            "processor": "Intel Core i9",
            "ram_gb": 64.0,
            "vram_gb": 24.0,
            "gpu_info": {"detected": True, "vendor": "NVIDIA", "name": "RTX 4090", "vram_gb": 24.0}
        }
        
        verifier = ModelVerifier(str(self.verification_dir))
        
        # Verify all test models
        verification_results = {}
        
        for model_name, model_info in self.test_models.items():
            summary = verifier.verify_model(
                model_id=model_name,
                model_path=str(model_info["path"]),
                expected_checksum=model_info["checksum"],
                source_url=f"https://huggingface.co/models/{model_name}.bin"
            )
            
            verification_results[model_name] = summary
            
            # Verify each model passed verification
            self.assertEqual(summary.overall_status, VerificationStatus.VERIFIED)
            self.assertIn(VerificationType.CHECKSUM, summary.results)
            self.assertIn(VerificationType.SOURCE, summary.results)
            self.assertIn(VerificationType.HARDWARE, summary.results)
            self.assertIn(VerificationType.MALWARE, summary.results)
        
        # Verify cache contains all models
        self.assertEqual(len(verifier.verification_cache), len(self.test_models))
        
        # Verify persistence
        for model_name in self.test_models.keys():
            loaded_summary = verifier.get_verification_status(model_name)
            self.assertIsNotNone(loaded_summary)
            self.assertEqual(loaded_summary.overall_status, VerificationStatus.VERIFIED)
    
    def test_verification_workflow_with_failures(self):
        """Test verification workflow with various failure scenarios"""
        verifier = ModelVerifier(str(self.verification_dir))
        
        # Test with wrong checksum
        model_info = self.test_models["llama-7b"]
        summary = verifier.verify_model(
            model_id="llama-7b-wrong-checksum",
            model_path=str(model_info["path"]),
            expected_checksum="wrong_checksum",
            source_url="https://huggingface.co/models/llama-7b.bin"
        )
        
        self.assertEqual(summary.overall_status, VerificationStatus.FAILED)
        self.assertEqual(summary.results[VerificationType.CHECKSUM].status, VerificationStatus.FAILED)
        
        # Test with untrusted source
        summary = verifier.verify_model(
            model_id="llama-7b-untrusted",
            model_path=str(model_info["path"]),
            expected_checksum=model_info["checksum"],
            source_url="https://malicious-site.com/fake-model.bin"
        )
        
        self.assertEqual(summary.overall_status, VerificationStatus.FAILED)
        self.assertEqual(summary.results[VerificationType.SOURCE].status, VerificationStatus.FAILED)


if __name__ == '__main__':
    # Configure logging for tests
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run tests
    unittest.main(verbosity=2)