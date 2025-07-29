"""
Unit Tests for Secure Block Transfer System

This module contains comprehensive unit tests for the secure model block transfer system,
covering transfer reliability, security, and error handling scenarios.

Test Categories:
- Basic transfer functionality
- Encryption and security
- Resumable transfers
- Error handling and retry logic
- Integrity validation
- Progress tracking
- Connection recovery

Requirements tested:
- 6.2.1: Encrypt data during transit using AES-256-GCM
- 6.2.2: Perform key exchange using secure protocols
- 6.2.4: Retry with exponential backoff up to 3 attempts
- 6.2.5: Verify block integrity using cryptographic checksums
- 10.2: Support resumable transfer capability
"""

import asyncio
import json
import pytest
import tempfile
import hashlib
import secrets
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Add missing import for aiofiles
try:
    import aiofiles
except ImportError:
    # Mock aiofiles if not available
    class MockAioFiles:
        @staticmethod
        def open(*args, **kwargs):
            return open(*args, **kwargs)
    aiofiles = MockAioFiles()

from network.secure_block_transfer import (
    SecureBlockTransferManager,
    TransferStatus,
    TransferMethod,
    BlockTransferInfo,
    TransferSession,
    transfer_model_blocks
)
from models.model_encryption import EncryptedBlock, EncryptionKey
from security.crypto_layer import CryptoLayer


class TestSecureBlockTransferManager:
    """Test cases for SecureBlockTransferManager"""
    
    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def mock_crypto_layer(self):
        """Create mock crypto layer"""
        crypto_layer = Mock(spec=CryptoLayer)
        crypto_layer.encrypt_message = AsyncMock(return_value=Mock())
        crypto_layer.decrypt_message = AsyncMock(return_value=b"decrypted_data")
        return crypto_layer
    
    @pytest.fixture
    def transfer_manager(self, temp_storage_dir, mock_crypto_layer):
        """Create transfer manager instance"""
        return SecureBlockTransferManager(
            node_id="test_node",
            storage_dir=temp_storage_dir,
            crypto_layer=mock_crypto_layer
        )
    
    @pytest.fixture
    def sample_encrypted_blocks(self):
        """Create sample encrypted blocks for testing"""
        blocks = []
        for i in range(3):
            block_data = f"encrypted_block_data_{i}".encode()
            block = EncryptedBlock(
                block_id=f"block_{i}",
                model_id="test_model",
                block_index=i,
                encrypted_data=block_data,
                nonce=secrets.token_bytes(12),
                tag=secrets.token_bytes(16),
                key_id="test_key",
                original_size=len(block_data),
                encrypted_size=len(block_data),
                checksum=hashlib.sha256(block_data).hexdigest(),
                created_at=datetime.now()
            )
            blocks.append(block)
        return blocks
    
    @pytest.mark.asyncio
    async def test_start_transfer_session(self, transfer_manager, sample_encrypted_blocks):
        """Test starting a new transfer session"""
        # Start transfer session
        session_id = await transfer_manager.start_transfer_session(
            admin_node_id="admin_node",
            client_node_id="client_node",
            model_id="test_model",
            encrypted_blocks=sample_encrypted_blocks
        )
        
        # Verify session creation
        assert session_id is not None
        assert session_id in transfer_manager.active_sessions
        
        session = transfer_manager.active_sessions[session_id]
        assert session.admin_node_id == "admin_node"
        assert session.client_node_id == "client_node"
        assert session.model_id == "test_model"
        assert len(session.blocks) == 3
        assert session.total_blocks == 3
        assert session.status == TransferStatus.PENDING
        assert session.encryption_key is not None
    
    @pytest.mark.asyncio
    async def test_block_transfer_info_properties(self):
        """Test BlockTransferInfo properties"""
        block_info = BlockTransferInfo(
            transfer_id="test_transfer",
            block_id="test_block",
            model_id="test_model",
            block_index=0,
            total_size=1000,
            transferred_size=500
        )
        
        # Test progress calculation
        assert block_info.progress_percentage == 50.0
        assert not block_info.is_complete
        assert block_info.can_retry
        
        # Test completion
        block_info.transferred_size = 1000
        block_info.status = TransferStatus.COMPLETED
        assert block_info.progress_percentage == 100.0
        assert block_info.is_complete
        
        # Test retry logic
        block_info.retry_count = 3
        block_info.status = TransferStatus.FAILED
        assert not block_info.can_retry
    
    @pytest.mark.asyncio
    async def test_transfer_session_properties(self, sample_encrypted_blocks):
        """Test TransferSession properties"""
        session = TransferSession(
            session_id="test_session",
            admin_node_id="admin_node",
            client_node_id="client_node",
            model_id="test_model",
            total_blocks=3,
            total_size=3000,
            transferred_size=1500
        )
        
        # Test progress calculation
        assert session.progress_percentage == 50.0
        assert not session.is_complete
        
        # Test completion
        session.completed_blocks = 3
        session.transferred_size = 3000
        session.status = TransferStatus.COMPLETED
        assert session.progress_percentage == 100.0
        assert session.is_complete
    
    @pytest.mark.asyncio
    async def test_encrypt_for_transfer(self, transfer_manager):
        """Test AES-256-GCM encryption for transfer"""
        # Create test data and encryption key
        test_data = b"test_data_for_encryption"
        encryption_key = EncryptionKey(
            key_id="test_key",
            algorithm="AES-256-GCM",
            key_data=secrets.token_bytes(32),  # 256-bit key
            created_at=datetime.now()
        )
        
        # Encrypt data
        encrypted_data = await transfer_manager._encrypt_for_transfer(test_data, encryption_key)
        
        # Verify encryption
        assert encrypted_data is not None
        assert len(encrypted_data) > len(test_data)  # Should be larger due to nonce and tag
        assert encrypted_data != test_data  # Should be different from original
        
        # Verify structure (nonce + encrypted_data + tag)
        assert len(encrypted_data) >= 12 + len(test_data) + 16  # nonce(12) + data + tag(16)
    
    @pytest.mark.asyncio
    async def test_verify_block_integrity(self, transfer_manager):
        """Test block integrity verification with cryptographic checksums"""
        # Create test block with valid checksum
        block_data = b"test_block_data"
        valid_checksum = hashlib.sha256(block_data).hexdigest()
        
        valid_block = EncryptedBlock(
            block_id="test_block",
            model_id="test_model",
            block_index=0,
            encrypted_data=block_data,
            nonce=secrets.token_bytes(12),
            tag=secrets.token_bytes(16),
            key_id="test_key",
            original_size=len(block_data),
            encrypted_size=len(block_data),
            checksum=valid_checksum,
            created_at=datetime.now()
        )
        
        # Test valid block
        assert transfer_manager._verify_block_integrity(valid_block)
        
        # Create block with invalid checksum
        invalid_block = EncryptedBlock(
            block_id="test_block",
            model_id="test_model",
            block_index=0,
            encrypted_data=block_data,
            nonce=secrets.token_bytes(12),
            tag=secrets.token_bytes(16),
            key_id="test_key",
            original_size=len(block_data),
            encrypted_size=len(block_data),
            checksum="invalid_checksum",
            created_at=datetime.now()
        )
        
        # Test invalid block
        assert not transfer_manager._verify_block_integrity(invalid_block)
    
    @pytest.mark.asyncio
    async def test_transfer_with_retry_logic(self, transfer_manager, sample_encrypted_blocks):
        """Test transfer retry logic with exponential backoff"""
        # Start transfer session
        session_id = await transfer_manager.start_transfer_session(
            admin_node_id="admin_node",
            client_node_id="client_node",
            model_id="test_model",
            encrypted_blocks=sample_encrypted_blocks
        )
        
        session = transfer_manager.active_sessions[session_id]
        block_info = session.blocks[0]
        
        # Mock transfer method to fail initially
        original_method = transfer_manager._transfer_single_block
        call_count = 0
        
        async def mock_transfer_single_block(session, block_info):
            nonlocal call_count
            call_count += 1
            if call_count < 3:  # Fail first 2 attempts
                return False
            return True  # Succeed on 3rd attempt
        
        transfer_manager._transfer_single_block = mock_transfer_single_block
        
        # Test retry logic
        success = await transfer_manager._transfer_block_with_retry(session, block_info)
        
        # Verify retry behavior
        assert success
        assert call_count == 3  # Should have retried 2 times
        assert block_info.retry_count == 2
        
        # Restore original method
        transfer_manager._transfer_single_block = original_method
    
    @pytest.mark.asyncio
    async def test_transfer_max_retries_exceeded(self, transfer_manager, sample_encrypted_blocks):
        """Test transfer failure when max retries exceeded"""
        # Start transfer session
        session_id = await transfer_manager.start_transfer_session(
            admin_node_id="admin_node",
            client_node_id="client_node",
            model_id="test_model",
            encrypted_blocks=sample_encrypted_blocks
        )
        
        session = transfer_manager.active_sessions[session_id]
        block_info = session.blocks[0]
        
        # Mock transfer method to always fail
        async def mock_failing_transfer(session, block_info):
            return False
        
        transfer_manager._transfer_single_block = mock_failing_transfer
        
        # Test max retries
        success = await transfer_manager._transfer_block_with_retry(session, block_info)
        
        # Verify failure after max retries
        assert not success
        assert block_info.retry_count == block_info.max_retries
        assert block_info.status == TransferStatus.FAILED
    
    @pytest.mark.asyncio
    async def test_websocket_transfer(self, transfer_manager):
        """Test WebSocket-based block transfer"""
        # Create mock WebSocket
        mock_websocket = AsyncMock()
        mock_websocket.send = AsyncMock()
        mock_websocket.recv = AsyncMock(return_value=json.dumps({"status": "success"}))
        
        # Create test block info
        block_info = BlockTransferInfo(
            transfer_id="test_transfer",
            block_id="test_block",
            model_id="test_model",
            block_index=0,
            total_size=100
        )
        
        # Test WebSocket transfer
        encrypted_data = b"encrypted_test_data"
        success = await transfer_manager._transfer_via_websocket(
            mock_websocket,
            block_info,
            encrypted_data
        )
        
        # Verify transfer
        assert success
        assert block_info.transferred_size == block_info.total_size
        mock_websocket.send.assert_called_once()
        mock_websocket.recv.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_websocket_transfer_failure(self, transfer_manager):
        """Test WebSocket transfer failure handling"""
        # Create mock WebSocket that returns error
        mock_websocket = AsyncMock()
        mock_websocket.send = AsyncMock()
        mock_websocket.recv = AsyncMock(return_value=json.dumps({
            "status": "error",
            "error": "Transfer failed"
        }))
        
        # Create test block info
        block_info = BlockTransferInfo(
            transfer_id="test_transfer",
            block_id="test_block",
            model_id="test_model",
            block_index=0,
            total_size=100
        )
        
        # Test WebSocket transfer failure
        encrypted_data = b"encrypted_test_data"
        
        with pytest.raises(ValueError, match="Transfer failed"):
            await transfer_manager._transfer_via_websocket(
                mock_websocket,
                block_info,
                encrypted_data
            )
    
    @pytest.mark.asyncio
    async def test_websocket_transfer_timeout(self, transfer_manager):
        """Test WebSocket transfer timeout handling"""
        # Create mock WebSocket that times out
        mock_websocket = AsyncMock()
        mock_websocket.send = AsyncMock()
        mock_websocket.recv = AsyncMock(side_effect=asyncio.TimeoutError())
        
        # Create test block info
        block_info = BlockTransferInfo(
            transfer_id="test_transfer",
            block_id="test_block",
            model_id="test_model",
            block_index=0,
            total_size=100
        )
        
        # Test timeout handling
        encrypted_data = b"encrypted_test_data"
        
        with pytest.raises(ValueError, match="Transfer timeout"):
            await transfer_manager._transfer_via_websocket(
                mock_websocket,
                block_info,
                encrypted_data
            )
    
    @pytest.mark.asyncio
    async def test_resume_transfer(self, transfer_manager, sample_encrypted_blocks):
        """Test resumable transfer capability"""
        # Start transfer session
        session_id = await transfer_manager.start_transfer_session(
            admin_node_id="admin_node",
            client_node_id="client_node",
            model_id="test_model",
            encrypted_blocks=sample_encrypted_blocks
        )
        
        session = transfer_manager.active_sessions[session_id]
        
        # Simulate partial completion
        session.status = TransferStatus.PAUSED
        session.blocks[0].status = TransferStatus.COMPLETED
        session.blocks[1].status = TransferStatus.FAILED
        session.blocks[2].status = TransferStatus.PENDING
        session.completed_blocks = 1
        
        # Mock successful transfer for remaining blocks
        async def mock_successful_transfer(session_id):
            session = transfer_manager.active_sessions[session_id]
            for block in session.blocks:
                if block.status != TransferStatus.COMPLETED:
                    block.status = TransferStatus.COMPLETED
                    session.completed_blocks += 1
            session.status = TransferStatus.COMPLETED
            return True
        
        transfer_manager.transfer_blocks = mock_successful_transfer
        
        # Test resume
        success = await transfer_manager.resume_transfer(session_id)
        
        # Verify resume
        assert success
        assert session.status == TransferStatus.COMPLETED
        assert session.completed_blocks == 3
    
    @pytest.mark.asyncio
    async def test_cancel_transfer(self, transfer_manager, sample_encrypted_blocks):
        """Test transfer cancellation"""
        # Start transfer session
        session_id = await transfer_manager.start_transfer_session(
            admin_node_id="admin_node",
            client_node_id="client_node",
            model_id="test_model",
            encrypted_blocks=sample_encrypted_blocks
        )
        
        session = transfer_manager.active_sessions[session_id]
        session.status = TransferStatus.IN_PROGRESS
        
        # Cancel transfer
        success = await transfer_manager.cancel_transfer(session_id)
        
        # Verify cancellation
        assert success
        assert session.status == TransferStatus.CANCELLED
        
        # Verify all blocks are cancelled
        for block in session.blocks:
            assert block.status == TransferStatus.CANCELLED
    
    @pytest.mark.asyncio
    async def test_get_transfer_progress(self, transfer_manager, sample_encrypted_blocks):
        """Test transfer progress tracking"""
        # Start transfer session
        session_id = await transfer_manager.start_transfer_session(
            admin_node_id="admin_node",
            client_node_id="client_node",
            model_id="test_model",
            encrypted_blocks=sample_encrypted_blocks
        )
        
        session = transfer_manager.active_sessions[session_id]
        session.status = TransferStatus.IN_PROGRESS
        session.completed_blocks = 1
        session.transferred_size = 1000
        session.started_at = datetime.now()
        
        # Get progress
        progress = transfer_manager.get_transfer_progress(session_id)
        
        # Verify progress information
        assert progress is not None
        assert progress['session_id'] == session_id
        assert progress['status'] == TransferStatus.IN_PROGRESS.value
        assert progress['completed_blocks'] == 1
        assert progress['total_blocks'] == 3
        assert progress['transferred_size'] == 1000
        assert 'progress_percentage' in progress
        assert 'estimated_completion' in progress
    
    @pytest.mark.asyncio
    async def test_progress_callbacks(self, transfer_manager):
        """Test progress callback notifications"""
        callback_calls = []
        
        def progress_callback(session_id, progress):
            callback_calls.append((session_id, progress))
        
        # Add callback
        transfer_manager.add_progress_callback(progress_callback)
        
        # Trigger progress notification
        await transfer_manager._notify_progress("test_session", 50.0)
        
        # Verify callback was called
        assert len(callback_calls) == 1
        assert callback_calls[0] == ("test_session", 50.0)
    
    @pytest.mark.asyncio
    async def test_transfer_statistics(self, transfer_manager):
        """Test transfer statistics tracking"""
        # Get initial statistics
        stats = transfer_manager.get_transfer_statistics()
        
        # Verify statistics structure
        assert 'total_sessions' in stats
        assert 'completed_sessions' in stats
        assert 'failed_sessions' in stats
        assert 'total_bytes_transferred' in stats
        assert 'total_blocks_transferred' in stats
        assert 'retry_attempts' in stats
        assert 'integrity_failures' in stats
        
        # Verify initial values
        assert stats['total_sessions'] == 0
        assert stats['completed_sessions'] == 0
        assert stats['failed_sessions'] == 0
    
    @pytest.mark.asyncio
    async def test_concurrent_transfers(self, transfer_manager, sample_encrypted_blocks):
        """Test concurrent block transfers with semaphore control"""
        # Verify max concurrent transfers setting
        assert transfer_manager.MAX_CONCURRENT_TRANSFERS == 3
        
        # Start transfer session with multiple blocks
        session_id = await transfer_manager.start_transfer_session(
            admin_node_id="admin_node",
            client_node_id="client_node",
            model_id="test_model",
            encrypted_blocks=sample_encrypted_blocks
        )
        
        # Mock transfer method to track concurrent calls
        concurrent_calls = 0
        max_concurrent = 0
        
        async def mock_transfer_with_concurrency_tracking(session, block_info):
            nonlocal concurrent_calls, max_concurrent
            concurrent_calls += 1
            max_concurrent = max(max_concurrent, concurrent_calls)
            
            # Simulate transfer time
            await asyncio.sleep(0.1)
            
            concurrent_calls -= 1
            return True
        
        transfer_manager._transfer_single_block = mock_transfer_with_concurrency_tracking
        
        # Mock other required methods
        transfer_manager._load_encrypted_block = AsyncMock(return_value=sample_encrypted_blocks[0])
        transfer_manager._verify_block_integrity = Mock(return_value=True)
        transfer_manager._encrypt_for_transfer = AsyncMock(return_value=b"encrypted_data")
        transfer_manager._transfer_via_direct_connection = AsyncMock(return_value=True)
        
        # Execute transfers
        success = await transfer_manager.transfer_blocks(session_id)
        
        # Verify concurrent execution was controlled
        assert success
        assert max_concurrent <= transfer_manager.MAX_CONCURRENT_TRANSFERS


class TestUtilityFunctions:
    """Test utility functions"""
    
    @pytest.mark.asyncio
    async def test_create_secure_transfer_manager(self):
        """Test transfer manager creation utility"""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = await create_secure_transfer_manager("test_node", temp_dir)
            
            assert manager is not None
            assert manager.node_id == "test_node"
            assert str(manager.storage_dir) == temp_dir
    
    @pytest.mark.asyncio
    async def test_transfer_model_blocks_utility(self):
        """Test model blocks transfer utility function"""
        # Create mock manager
        mock_manager = Mock(spec=SecureBlockTransferManager)
        mock_manager.start_transfer_session = AsyncMock(return_value="test_session")
        mock_manager.transfer_blocks = AsyncMock(return_value=True)
        
        # Create sample blocks
        sample_blocks = [
            Mock(spec=EncryptedBlock, block_id="block_1"),
            Mock(spec=EncryptedBlock, block_id="block_2")
        ]
        
        # Test utility function
        success = await transfer_model_blocks(
            manager=mock_manager,
            admin_node_id="admin_node",
            client_node_id="client_node",
            model_id="test_model",
            encrypted_blocks=sample_blocks
        )
        
        # Verify calls
        assert success
        mock_manager.start_transfer_session.assert_called_once_with(
            admin_node_id="admin_node",
            client_node_id="client_node",
            model_id="test_model",
            encrypted_blocks=sample_blocks,
            websocket_connection=None
        )
        mock_manager.transfer_blocks.assert_called_once_with("test_session")


class TestErrorHandling:
    """Test error handling scenarios"""
    
    @pytest.fixture
    def transfer_manager(self):
        """Create transfer manager for error testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield SecureBlockTransferManager(node_id="test_node", storage_dir=temp_dir)
    
    @pytest.mark.asyncio
    async def test_invalid_session_id(self, transfer_manager):
        """Test handling of invalid session IDs"""
        # Test resume with invalid session
        success = await transfer_manager.resume_transfer("invalid_session")
        assert not success
        
        # Test cancel with invalid session
        success = await transfer_manager.cancel_transfer("invalid_session")
        assert not success
        
        # Test progress with invalid session
        progress = transfer_manager.get_transfer_progress("invalid_session")
        assert progress is None
    
    @pytest.mark.asyncio
    async def test_encryption_failure(self, transfer_manager):
        """Test handling of encryption failures"""
        # Create invalid encryption key
        invalid_key = EncryptionKey(
            key_id="invalid_key",
            algorithm="AES-256-GCM",
            key_data=b"invalid_key_data",  # Invalid key length
            created_at=datetime.now()
        )
        
        # Test encryption failure
        with pytest.raises(Exception):
            await transfer_manager._encrypt_for_transfer(b"test_data", invalid_key)
    
    @pytest.mark.asyncio
    async def test_integrity_validation_failure(self, transfer_manager):
        """Test integrity validation failure handling"""
        # Create block with corrupted data
        corrupted_block = EncryptedBlock(
            block_id="corrupted_block",
            model_id="test_model",
            block_index=0,
            encrypted_data=b"corrupted_data",
            nonce=secrets.token_bytes(12),
            tag=secrets.token_bytes(16),
            key_id="test_key",
            original_size=100,
            encrypted_size=100,
            checksum="wrong_checksum",
            created_at=datetime.now()
        )
        
        # Test integrity validation failure
        assert not transfer_manager._verify_block_integrity(corrupted_block)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])