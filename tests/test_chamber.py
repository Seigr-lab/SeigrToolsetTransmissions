"""
Tests for STT chamber (STC-encrypted storage).
"""

import pytest
import tempfile
import os
from pathlib import Path
from seigr_toolset_transmissions.chamber import Chamber
from seigr_toolset_transmissions.crypto import STCWrapper
from seigr_toolset_transmissions.utils.exceptions import STTChamberError


class TestChamber:
    """Test STC-encrypted chamber storage."""
    
    @pytest.fixture
    def temp_chamber_dir(self):
        """Create temporary directory for chamber."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def node_id(self):
        """Node ID for chamber."""
        return b'\x01' * 32
    
    @pytest.fixture
    def stc_wrapper(self):
        """STC wrapper for encryption."""
        return STCWrapper(b"chamber_seed_32_bytes_minimum!!")
    
    @pytest.fixture
    def chamber(self, temp_chamber_dir, node_id, stc_wrapper):
        """Create chamber instance."""
        return Chamber(
            chamber_path=temp_chamber_dir,
            node_id=node_id,
            stc_wrapper=stc_wrapper,
        )
    
    def test_create_chamber(self, temp_chamber_dir, node_id, stc_wrapper):
        """Test creating a chamber."""
        chamber = Chamber(
            chamber_path=temp_chamber_dir,
            node_id=node_id,
            stc_wrapper=stc_wrapper,
        )
        
        assert chamber.chamber_path == temp_chamber_dir
        assert chamber.node_id == node_id
        assert temp_chamber_dir.exists()
    
    def test_store_data(self, chamber):
        """Test storing data in chamber."""
        key = "test_key"
        data = {"message": "test data", "value": 42}
        
        chamber.store(key, data)
        
        # Verify file exists in node-specific storage_path
        file_path = chamber.storage_path / f"{key}.stt"
        assert file_path.exists()
    
    def test_retrieve_data(self, chamber):
        """Test retrieving data from chamber."""
        key = "retrieve_test"
        original_data = {"content": "sensitive", "number": 123}
        
        # Store and retrieve
        chamber.store(key, original_data)
        retrieved_data = chamber.retrieve(key)
        
        assert retrieved_data == original_data
    
    def test_store_retrieve_roundtrip(self, chamber):
        """Test complete store/retrieve roundtrip."""
        key = "roundtrip"
        data = {
            "nested": {
                "values": [1, 2, 3],
                "text": "hello",
            },
            "flag": True,
        }
        
        chamber.store(key, data)
        result = chamber.retrieve(key)
        
        assert result == data
    
    def test_retrieve_nonexistent_key(self, chamber):
        """Test retrieving non-existent key."""
        with pytest.raises(STTChamberError):
            chamber.retrieve("does_not_exist")
    
    def test_delete_data(self, chamber):
        """Test deleting data from chamber."""
        key = "delete_test"
        data = {"temp": "data"}
        
        # Store and delete
        chamber.store(key, data)
        assert chamber.exists(key)
        
        chamber.delete(key)
        assert not chamber.exists(key)
    
    def test_list_keys(self, chamber):
        """Test listing all keys in chamber."""
        keys = ["key1", "key2", "key3"]
        
        for key in keys:
            chamber.store(key, {"data": key})
        
        stored_keys = chamber.list_keys()
        
        assert set(stored_keys) == set(keys)
    
    def test_exists(self, chamber):
        """Test checking if key exists."""
        key = "exists_test"
        
        assert not chamber.exists(key)
        
        chamber.store(key, {"data": "value"})
        
        assert chamber.exists(key)
    
    def test_encrypted_storage(self, temp_chamber_dir, node_id, stc_wrapper):
        """Test that stored data is encrypted."""
        chamber = Chamber(
            chamber_path=temp_chamber_dir,
            node_id=node_id,
            stc_wrapper=stc_wrapper,
        )
        
        key = "encrypted"
        plaintext_data = {"secret": "password123"}
        
        chamber.store(key, plaintext_data)
        
        # Read raw file content from node-specific storage path
        file_path = chamber.storage_path / f"{key}.stt"
        with open(file_path, 'rb') as f:
            raw_content = f.read()
        
        # Ensure plaintext is not in raw content
        assert b"password123" not in raw_content
        
        # Verify we can still decrypt
        retrieved = chamber.retrieve(key)
        assert retrieved == plaintext_data
    
    def test_native_serialization(self, chamber):
        """Test that chamber uses native STT serialization."""
        key = "serialization_test"
        data = {"type": "test", "count": 99}
        
        chamber.store(key, data)
        
        # Read raw file from node-specific storage path
        file_path = chamber.storage_path / f"{key}.stt"
        with open(file_path, 'rb') as f:
            raw_content = f.read()
        
        # Should NOT be JSON
        assert not raw_content.startswith(b'{')
        # Should NOT be msgpack
        assert not raw_content.startswith(b'\x80')
        
        # But should still decode correctly
        retrieved = chamber.retrieve(key)
        assert retrieved == data
    
    def test_update_data(self, chamber):
        """Test updating existing data."""
        key = "update_test"
        
        # Store initial data
        chamber.store(key, {"version": 1})
        
        # Update
        chamber.store(key, {"version": 2})
        
        # Verify update
        result = chamber.retrieve(key)
        assert result == {"version": 2}
    
    def test_store_binary_data(self, chamber):
        """Test storing binary data."""
        key = "binary_test"
        binary_data = b'\x00\x01\x02\xff\xfe\xfd'
        
        chamber.store(key, {"binary": binary_data})
        result = chamber.retrieve(key)
        
        assert result["binary"] == binary_data
    
    def test_store_large_data(self, chamber):
        """Test storing large data."""
        key = "large_test"
        large_data = {"content": "x" * 100000}  # 100KB string
        
        chamber.store(key, large_data)
        result = chamber.retrieve(key)
        
        assert result == large_data
    
    def test_multiple_chambers_same_directory(self, temp_chamber_dir, stc_wrapper):
        """Test multiple chambers with different node IDs."""
        node_id_1 = b'\x01' * 32
        node_id_2 = b'\x02' * 32
        
        chamber1 = Chamber(temp_chamber_dir, node_id_1, stc_wrapper)
        chamber2 = Chamber(temp_chamber_dir, node_id_2, stc_wrapper)
        
        # Store in different namespaces
        chamber1.store("shared_key", {"owner": "chamber1"})
        chamber2.store("shared_key", {"owner": "chamber2"})
        
        # Each should retrieve its own data
        assert chamber1.retrieve("shared_key") == {"owner": "chamber1"}
        assert chamber2.retrieve("shared_key") == {"owner": "chamber2"}
    
    def test_clear_chamber(self, chamber):
        """Test clearing all data from chamber."""
        keys = ["clear1", "clear2", "clear3"]
        
        for key in keys:
            chamber.store(key, {"data": key})
        
        chamber.clear()
        
        assert len(chamber.list_keys()) == 0
    
    def test_get_metadata(self, chamber):
        """Test getting file metadata."""
        key = "meta_test"
        chamber.store(key, {"data": "value"})
        
        # Get metadata for specific key
        metadata = chamber.get_metadata(key)
        
        assert 'key' in metadata
        assert 'size' in metadata
        assert metadata['key'] == key
    
    def test_different_stc_wrappers(self, temp_chamber_dir, node_id):
        """Test that different STC wrappers can't decrypt each other's data."""
        # Create chamber with first wrapper
        wrapper1 = STCWrapper(b"wrapper_one_32_bytes_minimum!!")
        chamber1 = Chamber(temp_chamber_dir, node_id, wrapper1)
        
        key = "encrypted_data"
        data = {"secret": "message"}
        
        chamber1.store(key, data)
        
        # Try to read with different wrapper
        wrapper2 = STCWrapper(b"wrapper_two_32_bytes_minimum!!")
        chamber2 = Chamber(temp_chamber_dir, node_id, wrapper2)
        
        # Should fail to decrypt
        with pytest.raises(STTChamberError):
            chamber2.retrieve(key)
    
    def test_chamber_delete_nonexistent(self, temp_chamber_dir, stc_wrapper, node_id):
        """Test deleting non-existent key raises error."""
        chamber = Chamber(temp_chamber_dir, node_id, stc_wrapper)
        
        with pytest.raises(STTChamberError, match="not found"):
            chamber.delete("nonexistent")
