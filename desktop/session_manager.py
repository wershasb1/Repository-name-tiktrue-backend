"""
Session Management System
Manages chat sessions, saving/loading conversations, and license-based restrictions
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import uuid
import shutil

from security.license_validator import LicenseInfo, SubscriptionTier, LicenseStatus

logger = logging.getLogger("SessionManager")


class Session:
    """Represents a chat session"""
    
    def __init__(self, session_id: str = None, name: str = None):
        self.session_id = session_id or f"session_{uuid.uuid4().hex[:8]}"
        self.name = name or f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        self.messages: List[Dict[str, Any]] = []
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.metadata: Dict[str, Any] = {}
    
    def add_message(self, message: Dict[str, Any]) -> None:
        """Add a message to the session"""
        self.messages.append(message)
        self.updated_at = datetime.now()
    
    def clear_messages(self) -> None:
        """Clear all messages in the session"""
        self.messages = []
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary"""
        return {
            "session_id": self.session_id,
            "name": self.name,
            "messages": self.messages,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Session':
        """Create session from dictionary"""
        session = cls(session_id=data["session_id"], name=data["name"])
        session.messages = data["messages"]
        session.created_at = datetime.fromisoformat(data["created_at"])
        session.updated_at = datetime.fromisoformat(data["updated_at"])
        session.metadata = data.get("metadata", {})
        return session


class SessionManager:
    """Manages chat sessions with license-based restrictions"""
    
    # Session limits by subscription tier
    SESSION_LIMITS = {
        SubscriptionTier.FREE: 3,
        SubscriptionTier.PRO: 50,
        SubscriptionTier.ENT: -1  # Unlimited
    }
    
    # Message limits by subscription tier
    MESSAGE_LIMITS = {
        SubscriptionTier.FREE: 50,
        SubscriptionTier.PRO: 500,
        SubscriptionTier.ENT: -1  # Unlimited
    }
    
    def __init__(self, sessions_dir: str = "sessions"):
        """Initialize session manager"""
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        
        self.active_session: Optional[Session] = None
        self.sessions: Dict[str, Session] = {}
        
        # Load existing sessions
        self.load_sessions()
    
    def load_sessions(self) -> None:
        """Load all saved sessions"""
        try:
            self.sessions = {}
            
            for file_path in self.sessions_dir.glob("*.json"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        session = Session.from_dict(data)
                        self.sessions[session.session_id] = session
                except Exception as e:
                    logger.error(f"Failed to load session {file_path}: {e}")
            
            logger.info(f"Loaded {len(self.sessions)} sessions")
            
        except Exception as e:
            logger.error(f"Failed to load sessions: {e}")
    
    def create_session(self, name: str = None) -> Session:
        """Create a new session"""
        session = Session(name=name)
        self.sessions[session.session_id] = session
        self.active_session = session
        self.save_session(session)
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID"""
        return self.sessions.get(session_id)
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        try:
            if session_id in self.sessions:
                # Remove from memory
                session = self.sessions.pop(session_id)
                
                # Remove file
                file_path = self.sessions_dir / f"{session_id}.json"
                if file_path.exists():
                    file_path.unlink()
                
                # Reset active session if needed
                if self.active_session and self.active_session.session_id == session_id:
                    self.active_session = None
                
                logger.info(f"Deleted session {session_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    def save_session(self, session: Session) -> bool:
        """Save a session to disk"""
        try:
            file_path = self.sessions_dir / f"{session.session_id}.json"
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Saved session {session.session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save session {session.session_id}: {e}")
            return False
    
    def rename_session(self, session_id: str, new_name: str) -> bool:
        """Rename a session"""
        try:
            session = self.get_session(session_id)
            if session:
                session.name = new_name
                session.updated_at = datetime.now()
                self.save_session(session)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to rename session {session_id}: {e}")
            return False
    
    def get_all_sessions(self) -> List[Session]:
        """Get all sessions sorted by updated_at (newest first)"""
        return sorted(
            self.sessions.values(),
            key=lambda s: s.updated_at,
            reverse=True
        )
    
    def set_active_session(self, session_id: str) -> bool:
        """Set the active session"""
        session = self.get_session(session_id)
        if session:
            self.active_session = session
            return True
        return False
    
    def get_active_session(self) -> Optional[Session]:
        """Get the active session"""
        return self.active_session
    
    def add_message_to_active_session(self, message: Dict[str, Any]) -> bool:
        """Add a message to the active session"""
        if self.active_session:
            self.active_session.add_message(message)
            self.save_session(self.active_session)
            return True
        return False
    
    def clear_active_session(self) -> bool:
        """Clear messages in the active session"""
        if self.active_session:
            self.active_session.clear_messages()
            self.save_session(self.active_session)
            return True
        return False
    
    def export_session(self, session_id: str, export_path: str) -> bool:
        """Export a session to a file"""
        try:
            session = self.get_session(session_id)
            if not session:
                return False
            
            # Ensure directory exists
            export_dir = os.path.dirname(export_path)
            if export_dir:
                os.makedirs(export_dir, exist_ok=True)
            
            # Export as JSON
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
            
            logger.info(f"Exported session {session_id} to {export_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export session {session_id}: {e}")
            return False
    
    def import_session(self, import_path: str) -> Optional[Session]:
        """Import a session from a file"""
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Create new session ID to avoid conflicts
            original_id = data["session_id"]
            data["session_id"] = f"session_{uuid.uuid4().hex[:8]}"
            
            session = Session.from_dict(data)
            self.sessions[session.session_id] = session
            self.save_session(session)
            
            logger.info(f"Imported session {original_id} as {session.session_id}")
            return session
            
        except Exception as e:
            logger.error(f"Failed to import session from {import_path}: {e}")
            return None
    
    def backup_sessions(self, backup_path: str) -> bool:
        """Backup all sessions to a directory"""
        try:
            backup_dir = Path(backup_path)
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy all session files
            for file_path in self.sessions_dir.glob("*.json"):
                shutil.copy2(file_path, backup_dir / file_path.name)
            
            logger.info(f"Backed up {len(self.sessions)} sessions to {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to backup sessions: {e}")
            return False
    
    def restore_sessions(self, restore_path: str) -> int:
        """Restore sessions from a backup directory"""
        try:
            restore_dir = Path(restore_path)
            if not restore_dir.exists() or not restore_dir.is_dir():
                logger.error(f"Restore directory {restore_path} does not exist")
                return 0
            
            # Clear existing sessions
            for file_path in self.sessions_dir.glob("*.json"):
                file_path.unlink()
            
            # Copy backup files
            count = 0
            for file_path in restore_dir.glob("*.json"):
                shutil.copy2(file_path, self.sessions_dir / file_path.name)
                count += 1
            
            # Reload sessions
            self.load_sessions()
            
            logger.info(f"Restored {count} sessions from {restore_path}")
            return count
            
        except Exception as e:
            logger.error(f"Failed to restore sessions: {e}")
            return 0
    
    def check_session_limits(self, license_info: LicenseInfo) -> Tuple[bool, int, int]:
        """Check if session limits are reached"""
        if not license_info or license_info.status != LicenseStatus.VALID:
            return False, 0, self.SESSION_LIMITS[SubscriptionTier.FREE]
        
        # Get limits for the subscription tier
        session_limit = self.SESSION_LIMITS.get(
            license_info.plan, 
            self.SESSION_LIMITS[SubscriptionTier.FREE]
        )
        
        # Check if unlimited
        if session_limit < 0:
            return True, len(self.sessions), float('inf')
        
        # Check if limit reached
        return len(self.sessions) < session_limit, len(self.sessions), session_limit
    
    def check_message_limits(self, session: Session, license_info: LicenseInfo) -> Tuple[bool, int, int]:
        """Check if message limits are reached for a session"""
        if not license_info or license_info.status != LicenseStatus.VALID:
            return False, 0, self.MESSAGE_LIMITS[SubscriptionTier.FREE]
        
        # Get limits for the subscription tier
        message_limit = self.MESSAGE_LIMITS.get(
            license_info.plan, 
            self.MESSAGE_LIMITS[SubscriptionTier.FREE]
        )
        
        # Check if unlimited
        if message_limit < 0:
            return True, len(session.messages), float('inf')
        
        # Check if limit reached
        return len(session.messages) < message_limit, len(session.messages), message_limit
    
    def cleanup_old_sessions(self, max_age_days: int = 30, keep_min: int = 5) -> int:
        """Clean up old sessions"""
        try:
            if len(self.sessions) <= keep_min:
                return 0
            
            # Sort sessions by updated_at (oldest first)
            sorted_sessions = sorted(
                self.sessions.values(),
                key=lambda s: s.updated_at
            )
            
            # Keep at least keep_min sessions
            if len(sorted_sessions) <= keep_min:
                return 0
            
            # Calculate cutoff date
            cutoff_date = datetime.now() - timedelta(days=max_age_days)
            
            # Delete old sessions
            deleted_count = 0
            for session in sorted_sessions[:-keep_min]:  # Keep the newest keep_min sessions
                if session.updated_at < cutoff_date:
                    if self.delete_session(session.session_id):
                        deleted_count += 1
            
            logger.info(f"Cleaned up {deleted_count} old sessions")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old sessions: {e}")
            return 0


# Utility functions
def get_session_manager(sessions_dir: str = "sessions") -> SessionManager:
    """Get a session manager instance"""
    return SessionManager(sessions_dir)


def format_timestamp(timestamp: datetime) -> str:
    """Format timestamp for display"""
    now = datetime.now()
    delta = now - timestamp
    
    if delta.days == 0:
        if delta.seconds < 60:
            return "just now"
        elif delta.seconds < 3600:
            minutes = delta.seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            hours = delta.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif delta.days == 1:
        return "yesterday"
    elif delta.days < 7:
        return f"{delta.days} days ago"
    else:
        return timestamp.strftime("%Y-%m-%d")


if __name__ == "__main__":
    # Test the session manager
    logging.basicConfig(level=logging.INFO)
    
    # Create a temporary directory for testing
    import tempfile
    import shutil
    
    temp_dir = tempfile.mkdtemp()
    try:
        # Create session manager
        manager = SessionManager(temp_dir)
        
        # Create some test sessions
        session1 = manager.create_session("Test Session 1")
        session1.add_message({"role": "user", "content": "Hello"})
        session1.add_message({"role": "assistant", "content": "Hi there!"})
        manager.save_session(session1)
        
        session2 = manager.create_session("Test Session 2")
        session2.add_message({"role": "user", "content": "How are you?"})
        session2.add_message({"role": "assistant", "content": "I'm doing well, thanks!"})
        manager.save_session(session2)
        
        # List sessions
        print(f"\nSessions ({len(manager.get_all_sessions())}):\n" + "-" * 40)
        for session in manager.get_all_sessions():
            print(f"{session.name} ({session.session_id}) - {format_timestamp(session.updated_at)}")
            print(f"  Messages: {len(session.messages)}")
        
        # Test export/import
        export_path = os.path.join(temp_dir, "export.json")
        manager.export_session(session1.session_id, export_path)
        imported_session = manager.import_session(export_path)
        
        if imported_session:
            print(f"\nImported session: {imported_session.name} ({imported_session.session_id})")
        
        # Test backup/restore
        backup_dir = os.path.join(temp_dir, "backup")
        manager.backup_sessions(backup_dir)
        print(f"\nBacked up sessions to {backup_dir}")
        
        # Test session limits
        from security.license_validator import LicenseInfo
        
        free_license = LicenseInfo(
            license_key="TEST-FREE-1M-123",
            tier=SubscriptionTier.FREE,
            is_valid=True,
            expires_at=datetime.now() + timedelta(days=30),
            max_clients=3,
            features=["basic_chat"],
            models=["llama-7b"]
        )
        
        can_add, current, limit = manager.check_session_limits(free_license)
        print(f"\nFree tier: Can add more sessions? {can_add} ({current}/{limit})")
        
    finally:
        # Clean up
        shutil.rmtree(temp_dir)