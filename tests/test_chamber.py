"""
Tests for chamber encrypted storage.
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from seigr_toolset_transmissions.chamber import Chamber
from seigr_toolset_transmissions.utils.exceptions import STTChamberError


class TestChamber:
    """Test chamber encrypted storage."""
    
    @pytest.fixture
    def temp_chamber_path(self):
        """Create temporary chamber directory."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        # Cleanup
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
    
    def test_chamber_creation(self, temp_chamber_path):
        """Test creating a chamber."""
        node_id = b'\x01' * 32
        
        chamber = Chamber(
            chamber_path=temp_chamber_path,
            node_id=node_id,
        )
        
        assert chamber.chamber_path == temp_chamber_path
        assert chamber.node_id == node_id
        assert chamber.keys_path.exists()
        assert chamber.sessions_path.exists()
    
    def test_store_and_retrieve_key(self, temp_chamber_path):
        """Test storing and retrieving key material."""
        node_id = b'\x02' * 32
        chamber = Chamber(temp_chamber_path, node_id)
        
        key_id = "test_key"
        key_data = b'\xaa' * 32
        
        # Store key
        chamber.store_key(key_id, key_data)
        
        # Retrieve key
        retrieved = chamber.retrieve_key(key_id)
        
        assert retrieved == key_data
    
    def test_delete_key(self, temp_chamber_path):
        """Test deleting key material."""
        node_id = b'\x03' * 32
        chamber = Chamber(temp_chamber_path, node_id)
        
        key_id = "deletable_key"
        key_data = b'\xbb' * 32
        
        # Store and delete
        chamber.store_key(key_id, key_data)
        result = chamber.delete_key(key_id)
        
        assert result is True
        assert chamber.retrieve_key(key_id) is None
    
    def test_store_and_retrieve_session(self, temp_chamber_path):
        """Test storing and retrieving session metadata."""
        node_id = b'\x04' * 32
        chamber = Chamber(temp_chamber_path, node_id)
        
        session_id = "session_123"
        session_data = {
            'peer_id': 'abc123',
            'created_at': 1234567890,
            'capabilities': 0xFF,
        }
        
        # Store session
        chamber.store_session(session_id, session_data)
        
        # Retrieve session
        retrieved = chamber.retrieve_session(session_id)
        
        assert retrieved == session_data
    
    def test_delete_session(self, temp_chamber_path):
        """Test deleting session metadata."""
        node_id = b'\x05' * 32
        chamber = Chamber(temp_chamber_path, node_id)
        
        session_id = "deletable_session"
        session_data = {'test': 'data'}
        
        # Store and delete
        chamber.store_session(session_id, session_data)
        result = chamber.delete_session(session_id)
        
        assert result is True
        assert chamber.retrieve_session(session_id) is None
    
    def test_retrieve_nonexistent_key(self, temp_chamber_path):
        """Test retrieving non-existent key returns None."""
        node_id = b'\x06' * 32
        chamber = Chamber(temp_chamber_path, node_id)
        
        result = chamber.retrieve_key("nonexistent")
        
        assert result is None
    
    def test_chamber_wipe(self, temp_chamber_path):
        """Test wiping chamber data."""
        node_id = b'\x07' * 32
        chamber = Chamber(temp_chamber_path, node_id)
        
        # Store some data
        chamber.store_key("key1", b'data')
        
        # Wipe chamber
        chamber.wipe()
        
        # Chamber should be gone
        assert not temp_chamber_path.exists()
