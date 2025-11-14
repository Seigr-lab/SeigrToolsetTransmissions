"""
Chamber manager for encrypted key material and session state storage.
"""

import os
import secrets
from pathlib import Path
from typing import Optional, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass, asdict

if TYPE_CHECKING:
    from ..crypto.stc_wrapper import STCWrapper

from ..utils.serialization import serialize_stt, deserialize_stt
from ..utils.exceptions import STTChamberError
from ..utils.logging import get_logger
logger = get_logger(__name__)


@dataclass
class ChamberMetadata:
    """Metadata for a chamber."""
    
    node_id: str
    created_at: float
    version: int = 1


class Chamber:
    """
    Encrypted storage for STT node state.
    
    All data stored in the chamber is encrypted via STC.
    Provides isolated environment for key material and session metadata.
    """
    
    def __init__(
        self,
        chamber_path: Path,
        node_id: bytes,
        stc_wrapper: 'STCWrapper',
    ):
        """
        Initialize chamber with STC encryption.
        
        Args:
            chamber_path: Path to chamber directory
            node_id: Node identifier (32 bytes)
            stc_wrapper: STC wrapper for encryption
        """
        if len(node_id) != 32:
            raise STTChamberError("Node ID must be 32 bytes")
        
        self.chamber_path = chamber_path
        self.node_id = node_id
        self.stc = stc_wrapper
        
        # Chamber subdirectories
        self.keys_path = chamber_path / "keys"
        self.sessions_path = chamber_path / "sessions"
        self.metadata_path = chamber_path / "metadata"
        
        self._ensure_chamber_structure()
    
    def _ensure_chamber_structure(self) -> None:
        """Create chamber directory structure."""
        try:
            self.chamber_path.mkdir(parents=True, exist_ok=True)
            self.keys_path.mkdir(exist_ok=True)
            self.sessions_path.mkdir(exist_ok=True)
            self.metadata_path.mkdir(exist_ok=True)
            
            logger.info(f"Chamber initialized at {self.chamber_path}")
            
        except OSError as e:
            raise STTChamberError(f"Failed to create chamber structure: {e}")
    
    def _encrypt_data(self, data: bytes, file_id: str) -> bytes:
        """
        Encrypt data using STC.
        
        Args:
            data: Plaintext data
            file_id: File identifier for associated data
            
        Returns:
            Encrypted data with nonce prepended
        """
        try:
            # Generate unique nonce for this encryption
            nonce = secrets.token_bytes(12)
            
            # Create associated data
            associated_data = {
                'purpose': 'chamber_storage',
                'node_id': self.node_id.hex(),
                'file_id': file_id
            }
            
            # Encrypt with STC
            encrypted = self.stc.stc_context.encrypt(
                data,
                nonce=nonce,
                associated_data=associated_data
            )
            
            # Prepend nonce for storage (nonce || ciphertext)
            return nonce + encrypted
            
        except Exception as e:
            raise STTChamberError(f"Encryption failed: {e}")
    
    def _decrypt_data(self, encrypted_data: bytes, file_id: str) -> bytes:
        """
        Decrypt data using STC.
        
        Args:
            encrypted_data: Encrypted data with prepended nonce
            file_id: File identifier for associated data
            
        Returns:
            Decrypted data
        """
        try:
            # Extract nonce (first 12 bytes)
            if len(encrypted_data) < 12:
                raise STTChamberError("Invalid encrypted data: too short")
            
            nonce = encrypted_data[:12]
            ciphertext = encrypted_data[12:]
            
            # Create associated data (must match encryption)
            associated_data = {
                'purpose': 'chamber_storage',
                'node_id': self.node_id.hex(),
                'file_id': file_id
            }
            
            # Decrypt with STC
            plaintext = self.stc.stc_context.decrypt(
                ciphertext,
                nonce=nonce,
                associated_data=associated_data
            )
            
            return plaintext
            
        except Exception as e:
            raise STTChamberError(f"Decryption failed: {e}")
    
    def store_key(self, key_id: str, key_data: bytes) -> None:
        """
        Store encrypted key material.
        
        Args:
            key_id: Key identifier
            key_data: Key material to store
        """
        try:
            encrypted = self._encrypt_data(key_data, f"key:{key_id}")
            key_file = self.keys_path / f"{key_id}.key"
            
            with open(key_file, 'wb') as f:
                f.write(encrypted)
            
            logger.debug(f"Stored key {key_id}")
            
        except Exception as e:
            raise STTChamberError(f"Failed to store key: {e}")
    
    def retrieve_key(self, key_id: str) -> Optional[bytes]:
        """
        Retrieve and decrypt key material.
        
        Args:
            key_id: Key identifier
            
        Returns:
            Decrypted key data or None if not found
        """
        try:
            key_file = self.keys_path / f"{key_id}.key"
            
            if not key_file.exists():
                return None
            
            with open(key_file, 'rb') as f:
                encrypted = f.read()
            
            key_data = self._decrypt_data(encrypted, f"key:{key_id}")
            
            logger.debug(f"Retrieved key {key_id}")
            
            return key_data
            
        except Exception as e:
            raise STTChamberError(f"Failed to retrieve key: {e}")
    
    def delete_key(self, key_id: str) -> bool:
        """
        Delete key material.
        
        Args:
            key_id: Key identifier
            
        Returns:
            True if deleted, False if not found
        """
        try:
            key_file = self.keys_path / f"{key_id}.key"
            
            if key_file.exists():
                key_file.unlink()
                logger.debug(f"Deleted key {key_id}")
                return True
            
            return False
            
        except Exception as e:
            raise STTChamberError(f"Failed to delete key: {e}")
    
    def store_session(self, session_id: str, session_data: Dict[str, Any]) -> None:
        """
        Store encrypted session metadata.
        
        Args:
            session_id: Session identifier
            session_data: Session metadata dictionary
        """
        try:
            # Serialize to STT binary format
            stt_data = serialize_stt(session_data)
            
            # Encrypt
            encrypted = self._encrypt_data(stt_data, f"session:{session_id}")
            
            session_file = self.sessions_path / f"{session_id}.session"
            
            with open(session_file, 'wb') as f:
                f.write(encrypted)
            
            logger.debug(f"Stored session {session_id}")
            
        except Exception as e:
            raise STTChamberError(f"Failed to store session: {e}")
    
    def retrieve_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve and decrypt session metadata.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session metadata dictionary or None if not found
        """
        try:
            session_file = self.sessions_path / f"{session_id}.session"
            
            if not session_file.exists():
                return None
            
            with open(session_file, 'rb') as f:
                encrypted = f.read()
            
            # Decrypt
            stt_data = self._decrypt_data(encrypted, f"session:{session_id}")
            
            # Deserialize
            session_data = deserialize_stt(stt_data)
            
            logger.debug(f"Retrieved session {session_id}")
            
            return session_data
            
        except Exception as e:
            raise STTChamberError(f"Failed to retrieve session: {e}")
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete session metadata.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if deleted, False if not found
        """
        try:
            session_file = self.sessions_path / f"{session_id}.session"
            
            if session_file.exists():
                session_file.unlink()
                logger.debug(f"Deleted session {session_id}")
                return True
            
            return False
            
        except Exception as e:
            raise STTChamberError(f"Failed to delete session: {e}")
    
    def wipe(self) -> None:
        """
        Securely wipe all chamber data.
        WARNING: This is irreversible!
        """
        try:
            import shutil
            
            if self.chamber_path.exists():
                shutil.rmtree(self.chamber_path)
                logger.warning(f"Chamber at {self.chamber_path} has been wiped")
            
        except Exception as e:
            raise STTChamberError(f"Failed to wipe chamber: {e}")
