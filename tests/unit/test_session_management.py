"""
Test Session Management System
Tests for session_manager.py and session_ui.py modules
"""

import unittest
import tempfile
import shutil
import os
import json
from datetime import datetime, timedelta
from pathlib import Path

# Import modules to test
from session_manager import SessionManager, Session, format_timestamp
from security.license_validator import LicenseInfo, SubscriptionTier, LicenseStatus


class TestSession(unittest.TestCase):
    """Test Session class"""
    
    def test_session_creation(self):
        """Test session creation"""
        session = Session()
        
        # Check default values
        self.assertIsNotNone(session.session_id)
        self.assertIsNotNone(session.name)
        self.assertEqual(len(session.messages), 0)
        self.assertIsInstance(session.created_at, datetime)
        self.assertIsInstance(session.updated_at, datetime)
        self.assertIsInstance(session.metadata, dict)
    
    def test_session_with_custom_values(self):
        """Test session creation with custom values"""
        session_id = "test_session_123"
        name = "Test Session"
        
        session = Session(session_id=session_id, name=name)
        
        self.assertEqual(session.session_id, session_id)
        self.assertEqual(session.name, name)
    
    def test_add_message(self):
        """Test adding messages to session"""
        session = Session()
        
        message1 = {"role": "user", "content": "Hello"}
        message2 = {"role": "assistant", "content": "Hi there!"}
        
        session.add_message(message1)
        session.add_message(message2)
        
        self.assertEqual(len(session.messages), 2)
        self.assertEqual(session.messages[0], message1)
        self.assertEqual(session.messages[1], message2)
    
    def test_clear_messages(self):
        """Test clearing messages"""
        session = Session()
        
        session.add_message({"role": "user", "content": "Hello"})
        session.add_message({"role": "assistant", "content": "Hi!"})
        
        self.assertEqual(len(session.messages), 2)
        
        session.clear_messages()
        
        self.assertEqual(len(session.messages), 0)
    
    def test_to_dict_and_from_dict(self):
        """Test session serialization"""
        original_session = Session("test_id", "Test Session")
        original_session.add_message({"role": "user", "content": "Hello"})
        original_session.metadata = {"test": "value"}
        
        # Convert to dict
        session_dict = original_session.to_dict()
        
        # Check dict structure
        self.assertIn("session_id", session_dict)
        self.assertIn("name", session_dict)
        self.assertIn("messages", session_dict)
        self.assertIn("created_at", session_dict)
        self.assertIn("updated_at", session_dict)
        self.assertIn("metadata", session_dict)
        
        # Convert back to session
        restored_session = Session.from_dict(session_dict)
        
        # Check values
        self.assertEqual(restored_session.session_id, original_session.session_id)
        self.assertEqual(restored_session.name, original_session.name)
        self.assertEqual(restored_session.messages, original_session.messages)
        self.assertEqual(restored_session.metadata, original_session.metadata)


class TestSessionManager(unittest.TestCase):
    """Test SessionManager class"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.session_manager = SessionManager(self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir)
    
    def test_create_session(self):
        """Test session creation"""
        session = self.session_manager.create_session("Test Session")
        
        self.assertIsNotNone(session)
        self.assertEqual(session.name, "Test Session")
        self.assertIn(session.session_id, self.session_manager.sessions)
        self.assertEqual(self.session_manager.active_session, session)
    
    def test_get_session(self):
        """Test getting session by ID"""
        session = self.session_manager.create_session("Test Session")
        
        retrieved_session = self.session_manager.get_session(session.session_id)
        
        self.assertEqual(retrieved_session, session)
        
        # Test non-existent session
        non_existent = self.session_manager.get_session("non_existent_id")
        self.assertIsNone(non_existent)
    
    def test_delete_session(self):
        """Test session deletion"""
        session = self.session_manager.create_session("Test Session")
        session_id = session.session_id
        
        # Verify session exists
        self.assertIn(session_id, self.session_manager.sessions)
        
        # Delete session
        result = self.session_manager.delete_session(session_id)
        
        self.assertTrue(result)
        self.assertNotIn(session_id, self.session_manager.sessions)
        self.assertIsNone(self.session_manager.active_session)
    
    def test_save_and_load_session(self):
        """Test session persistence"""
        # Create session
        session = self.session_manager.create_session("Test Session")
        session.add_message({"role": "user", "content": "Hello"})
        
        # Save session
        result = self.session_manager.save_session(session)
        self.assertTrue(result)
        
        # Check file exists
        file_path = Path(self.temp_dir) / f"{session.session_id}.json"
        self.assertTrue(file_path.exists())
        
        # Create new session manager and load sessions
        new_manager = SessionManager(self.temp_dir)
        
        # Check session was loaded
        self.assertIn(session.session_id, new_manager.sessions)
        loaded_session = new_manager.get_session(session.session_id)
        
        self.assertEqual(loaded_session.name, session.name)
        self.assertEqual(loaded_session.messages, session.messages)
    
    def test_rename_session(self):
        """Test session renaming"""
        session = self.session_manager.create_session("Original Name")
        session_id = session.session_id
        
        result = self.session_manager.rename_session(session_id, "New Name")
        
        self.assertTrue(result)
        self.assertEqual(session.name, "New Name")
    
    def test_set_active_session(self):
        """Test setting active session"""
        session1 = self.session_manager.create_session("Session 1")
        session2 = self.session_manager.create_session("Session 2")
        
        # Active session should be session2 (last created)
        self.assertEqual(self.session_manager.active_session, session2)
        
        # Set session1 as active
        result = self.session_manager.set_active_session(session1.session_id)
        
        self.assertTrue(result)
        self.assertEqual(self.session_manager.active_session, session1)
    
    def test_add_message_to_active_session(self):
        """Test adding message to active session"""
        session = self.session_manager.create_session("Test Session")
        message = {"role": "user", "content": "Hello"}
        
        result = self.session_manager.add_message_to_active_session(message)
        
        self.assertTrue(result)
        self.assertEqual(len(session.messages), 1)
        self.assertEqual(session.messages[0], message)
    
    def test_export_and_import_session(self):
        """Test session export and import"""
        # Create session
        session = self.session_manager.create_session("Export Test")
        session.add_message({"role": "user", "content": "Test message"})
        
        # Export session
        export_path = os.path.join(self.temp_dir, "export.json")
        result = self.session_manager.export_session(session.session_id, export_path)
        
        self.assertTrue(result)
        self.assertTrue(os.path.exists(export_path))
        
        # Import session
        imported_session = self.session_manager.import_session(export_path)
        
        self.assertIsNotNone(imported_session)
        self.assertEqual(imported_session.name, session.name)
        self.assertEqual(imported_session.messages, session.messages)
        self.assertNotEqual(imported_session.session_id, session.session_id)  # Should have new ID
    
    def test_backup_and_restore_sessions(self):
        """Test session backup and restore"""
        # Create multiple sessions
        session1 = self.session_manager.create_session("Session 1")
        session1.add_message({"role": "user", "content": "Message 1"})
        
        session2 = self.session_manager.create_session("Session 2")
        session2.add_message({"role": "user", "content": "Message 2"})
        
        # Backup sessions
        backup_dir = os.path.join(self.temp_dir, "backup")
        result = self.session_manager.backup_sessions(backup_dir)
        
        self.assertTrue(result)
        self.assertTrue(os.path.exists(backup_dir))
        
        # Check backup files exist
        backup_files = list(Path(backup_dir).glob("*.json"))
        self.assertEqual(len(backup_files), 2)
        
        # Create new session manager and restore
        new_temp_dir = tempfile.mkdtemp()
        try:
            new_manager = SessionManager(new_temp_dir)
            
            count = new_manager.restore_sessions(backup_dir)
            
            self.assertEqual(count, 2)
            self.assertEqual(len(new_manager.sessions), 2)
            
        finally:
            shutil.rmtree(new_temp_dir)
    
    def test_session_limits(self):
        """Test session limits based on license"""
        # Test FREE tier
        free_license = LicenseInfo(
            license_key="TIKT-FREE-1M-123",
            plan=SubscriptionTier.FREE,
            duration_months=1,
            unique_id="123",
            expires_at=datetime.now() + timedelta(days=30),
            max_clients=3,
            allowed_models=["llama-7b"],
            allowed_features=["basic_chat"],
            status=LicenseStatus.VALID,
            hardware_signature="test_signature",
            created_at=datetime.now(),
            checksum="test_checksum"
        )
        
        can_add, current, limit = self.session_manager.check_session_limits(free_license)
        self.assertTrue(can_add)
        self.assertEqual(current, 0)
        self.assertEqual(limit, 3)
        
        # Create sessions up to limit
        for i in range(3):
            self.session_manager.create_session(f"Session {i+1}")
        
        can_add, current, limit = self.session_manager.check_session_limits(free_license)
        self.assertFalse(can_add)
        self.assertEqual(current, 3)
        self.assertEqual(limit, 3)
        
        # Test PRO tier
        pro_license = LicenseInfo(
            license_key="TIKT-PRO-1M-123",
            plan=SubscriptionTier.PRO,
            duration_months=1,
            unique_id="123",
            expires_at=datetime.now() + timedelta(days=30),
            max_clients=20,
            allowed_models=["llama-7b", "llama-13b"],
            allowed_features=["advanced_chat", "session_management"],
            status=LicenseStatus.VALID,
            hardware_signature="test_signature",
            created_at=datetime.now(),
            checksum="test_checksum"
        )
        
        can_add, current, limit = self.session_manager.check_session_limits(pro_license)
        self.assertTrue(can_add)
        self.assertEqual(current, 3)
        self.assertEqual(limit, 50)
    
    def test_message_limits(self):
        """Test message limits based on license"""
        session = self.session_manager.create_session("Test Session")
        
        free_license = LicenseInfo(
            license_key="TIKT-FREE-1M-123",
            plan=SubscriptionTier.FREE,
            duration_months=1,
            unique_id="123",
            expires_at=datetime.now() + timedelta(days=30),
            max_clients=3,
            allowed_models=["llama-7b"],
            allowed_features=["basic_chat"],
            status=LicenseStatus.VALID,
            hardware_signature="test_signature",
            created_at=datetime.now(),
            checksum="test_checksum"
        )
        
        can_add, current, limit = self.session_manager.check_message_limits(session, free_license)
        self.assertTrue(can_add)
        self.assertEqual(current, 0)
        self.assertEqual(limit, 50)
        
        # Add messages up to limit
        for i in range(50):
            session.add_message({"role": "user", "content": f"Message {i+1}"})
        
        can_add, current, limit = self.session_manager.check_message_limits(session, free_license)
        self.assertFalse(can_add)
        self.assertEqual(current, 50)
        self.assertEqual(limit, 50)
    
    def test_cleanup_old_sessions(self):
        """Test cleanup of old sessions"""
        # Create sessions with different ages
        old_session = self.session_manager.create_session("Old Session")
        old_session.updated_at = datetime.now() - timedelta(days=35)
        self.session_manager.save_session(old_session)
        
        recent_session = self.session_manager.create_session("Recent Session")
        recent_session.updated_at = datetime.now() - timedelta(days=5)
        self.session_manager.save_session(recent_session)
        
        # Cleanup sessions older than 30 days, keep at least 1
        deleted_count = self.session_manager.cleanup_old_sessions(max_age_days=30, keep_min=1)
        
        self.assertEqual(deleted_count, 1)
        self.assertNotIn(old_session.session_id, self.session_manager.sessions)
        self.assertIn(recent_session.session_id, self.session_manager.sessions)


class TestFormatTimestamp(unittest.TestCase):
    """Test timestamp formatting function"""
    
    def test_format_timestamp(self):
        """Test timestamp formatting"""
        now = datetime.now()
        
        # Test "just now"
        recent = now - timedelta(seconds=30)
        self.assertEqual(format_timestamp(recent), "just now")
        
        # Test minutes ago
        minutes_ago = now - timedelta(minutes=5)
        self.assertEqual(format_timestamp(minutes_ago), "5 minutes ago")
        
        # Test hours ago
        hours_ago = now - timedelta(hours=2)
        self.assertEqual(format_timestamp(hours_ago), "2 hours ago")
        
        # Test yesterday
        yesterday = now - timedelta(days=1)
        self.assertEqual(format_timestamp(yesterday), "yesterday")
        
        # Test days ago
        days_ago = now - timedelta(days=3)
        self.assertEqual(format_timestamp(days_ago), "3 days ago")
        
        # Test weeks ago (should show date)
        weeks_ago = now - timedelta(days=10)
        expected = weeks_ago.strftime("%Y-%m-%d")
        self.assertEqual(format_timestamp(weeks_ago), expected)


if __name__ == "__main__":
    # Set up logging
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Run tests
    unittest.main(verbosity=2)