"""
Authentication Manager for Node Authentication
Implements RSA/ECDSA certificate generation, node identity verification,
and license binding integration for secure node communication
"""

import asyncio
import json
import logging
import time
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import base64
from pathlib import Path

# Cryptographic imports
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ec, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID

from security.license_validator import LicenseValidator
from license_models import LicenseInfo, SubscriptionTier

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AuthManager")

# Create logs directory if it doesn't exist
Path('logs').mkdir(exist_ok=True)
file_handler = logging.FileHandler('logs/security.auth_manager.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)


class AuthenticationMethod(Enum):
    """Authentication method options"""
    RSA_2048 = "rsa_2048"
    RSA_4096 = "rsa_4096"
    ECDSA_P256 = "ecdsa_p256"
    ECDSA_P384 = "ecdsa_p384"


class NodeRole(Enum):
    """Node role definitions"""
    ADMIN = "admin"
    WORKER = "worker"
    BACKUP = "backup"
    CLIENT = "client"


@dataclass
class NodeCertificate:
    """Node certificate information"""
    node_id: str
    certificate: bytes
    private_key: bytes
    public_key: bytes
    issued_at: datetime
    expires_at: datetime
    license_hash: str
    node_role: NodeRole
    auth_method: AuthenticationMethod
    serial_number: int
    is_valid: bool = True

@dataclass
class ChallengeResponse:
    """Challenge-response authentication data"""
    challenge_id: str
    challenge_data: bytes
    expected_response: bytes
    created_at: datetime
    expires_at: datetime
    node_id: str
    attempts: int = 0
    max_attempts: int = 3


@dataclass
class AuthenticationResult:
    """Authentication result information"""
    success: bool
    node_id: str
    node_role: NodeRole
    license_valid: bool
    error_message: Optional[str] = None
    certificate: Optional[NodeCertificate] = None
    session_token: Optional[str] = None


class AuthenticationManager:
    """
    Manages node authentication, certificate generation, and identity verification
    """
    
    def __init__(self, 
                 license_validator: Optional[LicenseValidator] = None,
                 certificate_validity_days: int = 365,
                 challenge_timeout_seconds: int = 300):
        """
        Initialize authentication manager
        
        Args:
            license_validator: License validator instance
            certificate_validity_days: Certificate validity period
            challenge_timeout_seconds: Challenge-response timeout
        """
        self.license_validator = license_validator or LicenseValidator()
        self.certificate_validity_days = certificate_validity_days
        self.challenge_timeout_seconds = challenge_timeout_seconds
        
        # Certificate storage
        self.node_certificates: Dict[str, NodeCertificate] = {}
        self.active_challenges: Dict[str, ChallengeResponse] = {}
        
        # CA certificate and key (would be loaded from secure storage)
        self.ca_private_key = None
        self.ca_certificate = None
        
        # Authentication statistics
        self.auth_stats = {
            "total_authentications": 0,
            "successful_authentications": 0,
            "failed_authentications": 0,
            "certificates_issued": 0,
            "certificates_revoked": 0
        }
        
        # Initialize CA if not exists
        self._initialize_ca()
        
        logger.info("Authentication manager initialized")
    
    def _initialize_ca(self):
        """Initialize Certificate Authority"""
        try:
            # Generate CA private key
            self.ca_private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=4096
            )
            
            # Create CA certificate
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TikTrue"),
                x509.NameAttribute(NameOID.COMMON_NAME, "TikTrue CA"),
            ])
            
            self.ca_certificate = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                issuer
            ).public_key(
                self.ca_private_key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.utcnow()
            ).not_valid_after(
                datetime.utcnow() + timedelta(days=3650)  # 10 years
            ).add_extension(
                x509.BasicConstraints(ca=True, path_length=None),
                critical=True,
            ).add_extension(
                x509.KeyUsage(
                    key_cert_sign=True,
                    crl_sign=True,
                    digital_signature=False,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            ).sign(self.ca_private_key, hashes.SHA256())
            
            logger.info("Certificate Authority initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize CA: {e}")
            raise    

    def generate_node_certificate(self, 
                                node_id: str, 
                                node_role: NodeRole,
                                license_info: Optional[LicenseInfo] = None,
                                auth_method: AuthenticationMethod = AuthenticationMethod.RSA_2048) -> NodeCertificate:
        """
        Generate node certificate function as specified in requirements
        
        Args:
            node_id: Unique node identifier
            node_role: Role of the node (admin, worker, backup, client)
            license_info: License information for binding
            auth_method: Authentication method (RSA/ECDSA)
            
        Returns:
            NodeCertificate with generated certificate and keys
        """
        try:
            logger.info(f"Generating certificate for node: {node_id} (role: {node_role.value})")
            
            # Generate private key based on method
            if auth_method in [AuthenticationMethod.RSA_2048, AuthenticationMethod.RSA_4096]:
                key_size = 2048 if auth_method == AuthenticationMethod.RSA_2048 else 4096
                private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=key_size
                )
            elif auth_method == AuthenticationMethod.ECDSA_P256:
                private_key = ec.generate_private_key(ec.SECP256R1())
            elif auth_method == AuthenticationMethod.ECDSA_P384:
                private_key = ec.generate_private_key(ec.SECP384R1())
            else:
                raise ValueError(f"Unsupported authentication method: {auth_method}")
            
            # Create license hash for binding
            license_hash = ""
            if license_info:
                license_data = f"{license_info.license_key}:{license_info.plan.value}:{license_info.expires_at.isoformat()}"
                license_hash = hashlib.sha256(license_data.encode()).hexdigest()
            
            # Create certificate subject
            subject = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TikTrue"),
                x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, node_role.value.title()),
                x509.NameAttribute(NameOID.COMMON_NAME, node_id),
            ])
            
            # Set certificate validity
            not_valid_before = datetime.utcnow()
            not_valid_after = not_valid_before + timedelta(days=self.certificate_validity_days)
            
            # Build certificate
            cert_builder = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                self.ca_certificate.subject
            ).public_key(
                private_key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                not_valid_before
            ).not_valid_after(
                not_valid_after
            )
            
            # Add extensions
            cert_builder = cert_builder.add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            ).add_extension(
                x509.KeyUsage(
                    key_cert_sign=False,
                    crl_sign=False,
                    digital_signature=True,
                    content_commitment=True,
                    key_encipherment=True,
                    data_encipherment=False,
                    key_agreement=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            ).add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName(node_id),
                ]),
                critical=False,
            )
            
            # Add custom extension for license binding
            if license_hash:
                license_extension = x509.UnrecognizedExtension(
                    oid=x509.ObjectIdentifier("1.3.6.1.4.1.99999.1"),  # Custom OID
                    value=license_hash.encode()
                )
                cert_builder = cert_builder.add_extension(license_extension, critical=False)
            
            # Sign certificate
            certificate = cert_builder.sign(self.ca_private_key, hashes.SHA256())
            
            # Serialize keys and certificate
            private_key_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            public_key_bytes = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            certificate_bytes = certificate.public_bytes(serialization.Encoding.PEM)
            
            # Create node certificate object
            node_cert = NodeCertificate(
                node_id=node_id,
                certificate=certificate_bytes,
                private_key=private_key_bytes,
                public_key=public_key_bytes,
                issued_at=not_valid_before,
                expires_at=not_valid_after,
                license_hash=license_hash,
                node_role=node_role,
                auth_method=auth_method,
                serial_number=certificate.serial_number
            )
            
            # Store certificate
            self.node_certificates[node_id] = node_cert
            self.auth_stats["certificates_issued"] += 1
            
            logger.info(f"Certificate generated successfully for node: {node_id}")
            return node_cert
            
        except Exception as e:
            logger.error(f"Failed to generate certificate for node {node_id}: {e}")
            raise  
  
    def verify_node_identity(self, 
                           node_id: str, 
                           certificate_data: bytes,
                           signature: bytes,
                           challenge_data: Optional[bytes] = None) -> AuthenticationResult:
        """
        Verify node identity function as specified in requirements
        
        Args:
            node_id: Node identifier to verify
            certificate_data: Node's certificate in PEM format
            signature: Digital signature for verification
            challenge_data: Optional challenge data for challenge-response
            
        Returns:
            AuthenticationResult with verification status
        """
        try:
            logger.info(f"Verifying identity for node: {node_id}")
            self.auth_stats["total_authentications"] += 1
            
            # Parse certificate
            try:
                certificate = x509.load_pem_x509_certificate(certificate_data)
            except Exception as e:
                logger.error(f"Invalid certificate format for node {node_id}: {e}")
                self.auth_stats["failed_authentications"] += 1
                return AuthenticationResult(
                    success=False,
                    node_id=node_id,
                    node_role=NodeRole.CLIENT,
                    license_valid=False,
                    error_message="Invalid certificate format"
                )
            
            # Verify certificate is signed by our CA
            try:
                self.ca_certificate.public_key().verify(
                    certificate.signature,
                    certificate.tbs_certificate_bytes,
                    padding.PKCS1v15(),
                    certificate.signature_hash_algorithm
                )
            except Exception as e:
                logger.error(f"Certificate verification failed for node {node_id}: {e}")
                self.auth_stats["failed_authentications"] += 1
                return AuthenticationResult(
                    success=False,
                    node_id=node_id,
                    node_role=NodeRole.CLIENT,
                    license_valid=False,
                    error_message="Certificate not signed by trusted CA"
                )
            
            # Check certificate validity period
            now = datetime.utcnow()
            if now < certificate.not_valid_before or now > certificate.not_valid_after:
                logger.error(f"Certificate expired or not yet valid for node {node_id}")
                self.auth_stats["failed_authentications"] += 1
                return AuthenticationResult(
                    success=False,
                    node_id=node_id,
                    node_role=NodeRole.CLIENT,
                    license_valid=False,
                    error_message="Certificate expired or not yet valid"
                )
            
            # Extract node role from certificate
            node_role = NodeRole.CLIENT
            try:
                for attribute in certificate.subject:
                    if attribute.oid == NameOID.ORGANIZATIONAL_UNIT_NAME:
                        role_value = attribute.value.lower()
                        if role_value in [role.value for role in NodeRole]:
                            node_role = NodeRole(role_value)
                        break
            except Exception as e:
                logger.warning(f"Could not extract role from certificate for node {node_id}: {e}")
            
            # Extract and verify license binding
            license_valid = True
            license_hash = ""
            try:
                for extension in certificate.extensions:
                    if extension.oid.dotted_string == "1.3.6.1.4.1.99999.1":  # Our custom license OID
                        license_hash = extension.value.decode()
                        break
                
                if license_hash:
                    # Verify license is still valid
                    license_valid = self._verify_license_binding(license_hash)
            except Exception as e:
                logger.warning(f"Could not verify license binding for node {node_id}: {e}")
                license_valid = False
            
            # Verify signature if provided
            if signature and challenge_data:
                try:
                    public_key = certificate.public_key()
                    if isinstance(public_key, rsa.RSAPublicKey):
                        public_key.verify(
                            signature,
                            challenge_data,
                            padding.PKCS1v15(),
                            hashes.SHA256()
                        )
                    elif isinstance(public_key, ec.EllipticCurvePublicKey):
                        public_key.verify(
                            signature,
                            challenge_data,
                            ec.ECDSA(hashes.SHA256())
                        )
                    else:
                        raise ValueError("Unsupported public key type")
                except Exception as e:
                    logger.error(f"Signature verification failed for node {node_id}: {e}")
                    self.auth_stats["failed_authentications"] += 1
                    return AuthenticationResult(
                        success=False,
                        node_id=node_id,
                        node_role=node_role,
                        license_valid=license_valid,
                        error_message="Signature verification failed"
                    )
            
            # Generate session token
            session_token = self._generate_session_token(node_id, node_role)
            
            # Create successful result
            self.auth_stats["successful_authentications"] += 1
            logger.info(f"Identity verification successful for node: {node_id}")
            
            return AuthenticationResult(
                success=True,
                node_id=node_id,
                node_role=node_role,
                license_valid=license_valid,
                session_token=session_token
            )
            
        except Exception as e:
            logger.error(f"Error verifying node identity for {node_id}: {e}")
            self.auth_stats["failed_authentications"] += 1
            return AuthenticationResult(
                success=False,
                node_id=node_id,
                node_role=NodeRole.CLIENT,
                license_valid=False,
                error_message=f"Authentication error: {str(e)}"
            )    
 
    def create_authentication_challenge(self, node_id: str) -> Tuple[str, bytes]:
        """
        Create authentication challenge for challenge-response mechanism
        
        Args:
            node_id: Node identifier requesting authentication
            
        Returns:
            Tuple of (challenge_id, challenge_data)
        """
        try:
            # Generate challenge ID and data
            challenge_id = f"challenge_{node_id}_{int(time.time() * 1000)}"
            challenge_data = secrets.token_bytes(32)  # 256-bit challenge
            
            # Create expected response (hash of challenge + node_id)
            expected_response = hashlib.sha256(challenge_data + node_id.encode()).digest()
            
            # Store challenge
            challenge = ChallengeResponse(
                challenge_id=challenge_id,
                challenge_data=challenge_data,
                expected_response=expected_response,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(seconds=self.challenge_timeout_seconds),
                node_id=node_id
            )
            
            self.active_challenges[challenge_id] = challenge
            
            logger.info(f"Authentication challenge created for node: {node_id}")
            return challenge_id, challenge_data
            
        except Exception as e:
            logger.error(f"Failed to create challenge for node {node_id}: {e}")
            raise
    
    def verify_challenge_response(self, 
                                challenge_id: str, 
                                response_signature: bytes,
                                certificate_data: bytes) -> AuthenticationResult:
        """
        Verify challenge-response authentication
        
        Args:
            challenge_id: Challenge identifier
            response_signature: Signed response from node
            certificate_data: Node's certificate
            
        Returns:
            AuthenticationResult with verification status
        """
        try:
            # Get challenge
            if challenge_id not in self.active_challenges:
                return AuthenticationResult(
                    success=False,
                    node_id="unknown",
                    node_role=NodeRole.CLIENT,
                    license_valid=False,
                    error_message="Challenge not found or expired"
                )
            
            challenge = self.active_challenges[challenge_id]
            
            # Check if challenge expired
            if datetime.utcnow() > challenge.expires_at:
                del self.active_challenges[challenge_id]
                return AuthenticationResult(
                    success=False,
                    node_id=challenge.node_id,
                    node_role=NodeRole.CLIENT,
                    license_valid=False,
                    error_message="Challenge expired"
                )
            
            # Check attempt limit
            challenge.attempts += 1
            if challenge.attempts > challenge.max_attempts:
                del self.active_challenges[challenge_id]
                return AuthenticationResult(
                    success=False,
                    node_id=challenge.node_id,
                    node_role=NodeRole.CLIENT,
                    license_valid=False,
                    error_message="Too many authentication attempts"
                )
            
            # Verify identity with challenge data
            result = self.verify_node_identity(
                challenge.node_id,
                certificate_data,
                response_signature,
                challenge.challenge_data
            )
            
            # Clean up challenge on success
            if result.success:
                del self.active_challenges[challenge_id]
            
            return result
            
        except Exception as e:
            logger.error(f"Error verifying challenge response: {e}")
            return AuthenticationResult(
                success=False,
                node_id="unknown",
                node_role=NodeRole.CLIENT,
                license_valid=False,
                error_message=f"Challenge verification error: {str(e)}"
            )
    
    def _verify_license_binding(self, license_hash: str) -> bool:
        """Verify license binding is still valid"""
        try:
            # This would check against current license information
            # For now, return True if hash is present
            return bool(license_hash)
        except Exception as e:
            logger.error(f"License binding verification failed: {e}")
            return False
    
    def _generate_session_token(self, node_id: str, node_role: NodeRole) -> str:
        """Generate session token for authenticated node"""
        try:
            # Create token data
            token_data = {
                "node_id": node_id,
                "role": node_role.value,
                "issued_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat()
            }
            
            # Encode token (in production, this would be properly signed JWT)
            token_json = json.dumps(token_data)
            token_bytes = token_json.encode()
            session_token = base64.b64encode(token_bytes).decode()
            
            return session_token
            
        except Exception as e:
            logger.error(f"Failed to generate session token: {e}")
            return ""
    
    def revoke_certificate(self, node_id: str) -> bool:
        """Revoke a node certificate"""
        try:
            if node_id in self.node_certificates:
                self.node_certificates[node_id].is_valid = False
                self.auth_stats["certificates_revoked"] += 1
                logger.info(f"Certificate revoked for node: {node_id}")
                return True
            else:
                logger.warning(f"Certificate not found for revocation: {node_id}")
                return False
        except Exception as e:
            logger.error(f"Failed to revoke certificate for {node_id}: {e}")
            return False
    
    def get_authentication_stats(self) -> Dict[str, Any]:
        """Get authentication statistics"""
        return {
            **self.auth_stats,
            "active_certificates": len([cert for cert in self.node_certificates.values() if cert.is_valid]),
            "active_challenges": len(self.active_challenges),
            "success_rate": (
                self.auth_stats["successful_authentications"] / 
                max(1, self.auth_stats["total_authentications"])
            ) * 100
        }
    
    def cleanup_expired_challenges(self):
        """Clean up expired challenges"""
        try:
            now = datetime.utcnow()
            expired_challenges = [
                challenge_id for challenge_id, challenge in self.active_challenges.items()
                if now > challenge.expires_at
            ]
            
            for challenge_id in expired_challenges:
                del self.active_challenges[challenge_id]
            
            if expired_challenges:
                logger.info(f"Cleaned up {len(expired_challenges)} expired challenges")
                
        except Exception as e:
            logger.error(f"Error cleaning up expired challenges: {e}")


def main():
    """Main entry point for testing"""
    # Create authentication manager
    auth_manager = AuthenticationManager()
    
    # Generate test certificate
    test_cert = security.auth_manager.generate_node_certificate(
        node_id="test-worker-1",
        node_role=NodeRole.WORKER,
        auth_method=AuthenticationMethod.RSA_2048
    )
    
    print(f"Generated certificate for: {test_cert.node_id}")
    print(f"Role: {test_cert.node_role.value}")
    print(f"Method: {test_cert.auth_method.value}")
    print(f"Valid until: {test_cert.expires_at}")
    
    # Test authentication
    result = security.auth_manager.verify_node_identity(
        node_id="test-worker-1",
        certificate_data=test_cert.certificate,
        signature=b"test_signature"
    )
    
    print(f"Authentication result: {result.success}")
    print(f"Node role: {result.node_role.value}")
    print(f"License valid: {result.license_valid}")
    
    # Show statistics
    stats = security.auth_manager.get_authentication_stats()
    print(f"Authentication stats: {stats}")


if __name__ == "__main__":
    main()