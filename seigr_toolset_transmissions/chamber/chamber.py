"""
Chamber - STC-encrypted persistent storage for STT.
"""

from pathlib import Path
from typing import Any, List, Dict
from dataclasses import dataclass

from ..crypto.stc_wrapper import STCWrapper
from ..utils.serialization import serialize_stt, deserialize_stt
from ..utils.exceptions import STTChamberError


@dataclass
class ChamberMetadata:
    """Metadata for chamber storage."""
    key: str
    size: int
    created_at: float
    updated_at: float


class Chamber:
    """
    STC-encrypted persistent storage.
    
    Provides encrypted key-value storage using STC for data protection.
    Data is stored as encrypted files in the chamber directory.
    """
    
    def __init__(self, chamber_path: Path, node_id: bytes, stc_wrapper: STCWrapper):
        """
        Initialize chamber.
        
        Args:
            chamber_path: Directory path for chamber storage
            node_id: Node identifier for this chamber
            stc_wrapper: STC wrapper for encryption
        """
        self.chamber_path = Path(chamber_path)
        self.node_id = node_id
        self.stc_wrapper = stc_wrapper
        
        # Create node-specific subdirectory for isolation
        node_dir = node_id.hex()[:16]  # First 16 hex chars of node_id
        self.storage_path = self.chamber_path / node_dir
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Metadata
        self.metadata: Dict = {}
    
    def store(self, key: str, data: Any) -> None:
        """
        Store data in chamber with encryption.
        
        Args:
            key: Storage key
            data: Data to store (will be serialized)
        """
        # Serialize data
        serialized = serialize_stt(data)
        
        # Encrypt data
        associated_data = {
            'key': key,
            'node_id': self.node_id.hex(),
            'purpose': 'chamber_storage'
        }
        
        encrypted, metadata = self.stc_wrapper.encrypt_frame(
            payload=serialized,
            associated_data=associated_data
        )
        
        # Prepare storage structure
        storage_data = {
            'encrypted': encrypted,
            'metadata': metadata,
            'key': key,
            'associated_data': associated_data
        }
        
        # Write to file
        file_path = self.storage_path / f"{key}.stt"
        with open(file_path, 'wb') as f:
            f.write(serialize_stt(storage_data))
    
    def retrieve(self, key: str) -> Any:
        """
        Retrieve and decrypt data from chamber.
        
        Args:
            key: Storage key
            
        Returns:
            Decrypted and deserialized data
            
        Raises:
            STTChamberError: If key doesn't exist or decryption fails
        """
        file_path = self.storage_path / f"{key}.stt"
        
        if not file_path.exists():
            raise STTChamberError(f"Key '{key}' not found in chamber")
        
        try:
            # Read storage file
            with open(file_path, 'rb') as f:
                storage_data = deserialize_stt(f.read())
            
            # Decrypt data
            decrypted = self.stc_wrapper.decrypt_frame(
                encrypted=storage_data['encrypted'],
                metadata=storage_data['metadata'],
                associated_data=storage_data['associated_data']
            )
            
            # Deserialize data
            return deserialize_stt(decrypted)
            
        except Exception as e:
            raise STTChamberError(f"Failed to retrieve '{key}': {e}") from e
    
    def delete(self, key: str) -> None:
        """
        Delete data from chamber.
        
        Args:
            key: Storage key
        """
        file_path = self.storage_path / f"{key}.stt"
        
        if file_path.exists():
            file_path.unlink()
        else:
            raise STTChamberError(f"Key '{key}' not found in chamber")
    
    def exists(self, key: str) -> bool:
        """
        Check if key exists in chamber.
        
        Args:
            key: Storage key
            
        Returns:
            True if key exists
        """
        file_path = self.storage_path / f"{key}.stt"
        return file_path.exists()
    
    def list_keys(self) -> List[str]:
        """
        List all keys in chamber.
        
        Returns:
            List of storage keys
        """
        keys = []
        for file_path in self.storage_path.glob("*.stt"):
            keys.append(file_path.stem)
        return sorted(keys)
    
    def clear(self) -> None:
        """Clear all data from chamber."""
        for file_path in self.storage_path.glob("*.stt"):
            file_path.unlink()
    
    def update(self, key: str, data: Any) -> None:
        """
        Update existing data (same as store).
        
        Args:
            key: Storage key
            data: New data to store
        """
        self.store(key, data)
    
    def get_metadata(self, key: str) -> Dict:
        """
        Get metadata for stored key.
        
        Args:
            key: Storage key
            
        Returns:
            Metadata dictionary
        """
        file_path = self.storage_path / f"{key}.stt"
        
        if not file_path.exists():
            raise STTChamberError(f"Key '{key}' not found in chamber")
        
        with open(file_path, 'rb') as f:
            storage_data = deserialize_stt(f.read())
        
        return {
            'key': storage_data.get('key'),
            'size': len(storage_data.get('encrypted', b'')),
            'associated_data': storage_data.get('associated_data'),
        }
