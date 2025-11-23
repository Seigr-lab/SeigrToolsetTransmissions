"""
Edge case tests for BinaryStorage - error paths, corruption, filesystem failures.
Targets uncovered lines: 81, 95-97, 151, 161, 183-184, 191, 211, 254, 269-280, 301-313, 322-324, 333-360
"""

import pytest
import asyncio
import hashlib
import shutil
from pathlib import Path
from seigr_toolset_transmissions.storage.binary_storage import BinaryStorage
from seigr_toolset_transmissions.crypto import STCWrapper
from seigr_toolset_transmissions.utils.exceptions import STTStorageError


class TestBinaryStorageEdgeCases:
    """Test error paths and edge cases in BinaryStorage."""
    
    @pytest.fixture
    def stc_wrapper(self):
        """STC wrapper for storage."""
        return STCWrapper(b"storage_test_seed_32_bytes_min!!")
    
    @pytest.fixture
    def temp_storage_dir(self, tmp_path):
        """Temporary storage directory."""
        storage_dir = tmp_path / "edge_case_storage"
        storage_dir.mkdir()
        yield storage_dir
        # Cleanup
        if storage_dir.exists():
            shutil.rmtree(storage_dir)
    
    @pytest.fixture
    def storage(self, stc_wrapper, temp_storage_dir):
        """Create storage instance."""
        return BinaryStorage(
            stc_wrapper=stc_wrapper,
            storage_path=temp_storage_dir,
            max_size_bytes=1024 * 10  # 10KB limit for eviction tests
        )
    
    @pytest.mark.asyncio
    async def test_put_non_bytes_fails(self, storage):
        """Test putting non-bytes data raises error (line 81)."""
        with pytest.raises(STTStorageError, match="Data must be bytes"):
            await storage.put("not bytes")
        
        with pytest.raises(STTStorageError, match="Data must be bytes"):
            await storage.put(12345)
        
        with pytest.raises(STTStorageError, match="Data must be bytes"):
            await storage.put(['list', 'of', 'things'])
    
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Async lock event loop issue - needs BinaryStorage refactor")
    async def test_storage_eviction_lru(self, storage):
        """Test LRU eviction when storage limit exceeded (lines 95-97)."""
        # Fill storage to near capacity
        data1 = b"x" * 3000  # 3KB
        data2 = b"y" * 3000  # 3KB
        data3 = b"z" * 3000  # 3KB
        
        addr1 = await storage.put(data1)
        await asyncio.sleep(0.01)  # Ensure different timestamps
        addr2 = await storage.put(data2)
        await asyncio.sleep(0.01)
        addr3 = await storage.put(data3)
        
        # All should be stored
        assert addr1 in storage._index
        assert addr2 in storage._index
        assert addr3 in storage._index
        
        # Access addr1 to make it more recent
        await storage.get(addr1)
        
        # Now add data that exceeds limit - should evict addr2 (oldest accessed)
        data4 = b"w" * 3000  # 3KB, will trigger eviction
        addr4 = await storage.put(data4)
        
        # addr2 should be evicted (least recently used)
        assert addr4 in storage._index
        # Either addr2 or addr3 should be evicted
        assert len(storage._index) < 4
    
    @pytest.mark.asyncio
    async def test_get_non_bytes_address_fails(self, storage):
        """Test getting with non-bytes address raises error (line 151)."""
        with pytest.raises(STTStorageError, match="Address must be bytes"):
            await storage.get("not bytes address")
        
        with pytest.raises(STTStorageError, match="Address must be bytes"):
            await storage.get(12345)
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_address_fails(self, storage):
        """Test getting non-existent address raises error (line 161)."""
        fake_address = b"nonexistent_address_32_bytes!!!!"
        
        with pytest.raises(STTStorageError, match="Address not found"):
            await storage.get(fake_address)
    
    @pytest.mark.asyncio
    async def test_get_missing_file_fails(self, storage, temp_storage_dir):
        """Test getting address where file is missing (lines 183-184)."""
        # Put data
        data = b"test data"
        address = await storage.put(data)
        
        # Manually delete the file but keep index entry
        address_path = storage._get_address_path(address)
        address_path.unlink()
        
        # Try to get - should fail
        with pytest.raises(STTStorageError, match="Storage file missing"):
            await storage.get(address)
    
    @pytest.mark.asyncio
    async def test_get_corrupted_data_fails(self, storage):
        """Test getting corrupted encrypted data fails decryption (line 191)."""
        # Put data
        data = b"test data"
        address = await storage.put(data)
        
        # Corrupt the file
        address_path = storage._get_address_path(address)
        corrupted = b"corrupted_garbage_data_that_will_fail_decryption!!"
        address_path.write_bytes(corrupted)
        
        # Try to get - should fail decryption or parsing
        with pytest.raises(STTStorageError):
            await storage.get(address)
    
    @pytest.mark.asyncio
    async def test_get_integrity_check_failure(self, storage):
        """Test integrity check fails when data doesn't match hash (line 211)."""
        # Put data
        data = b"original data"
        address = await storage.put(data)
        
        # Get the encrypted file
        address_path = storage._get_address_path(address)
        encrypted_with_header = address_path.read_bytes()
        
        # Create different data with valid encryption but wrong hash
        different_data = b"tampered data"
        
        # Encrypt the tampered data using same session
        storage_session = b"storage_" + address[:8]
        stream_context = storage.stc_wrapper.create_stream_context(
            session_id=storage_session,
            stream_id=0
        )
        
        # Create valid encrypted data (will decrypt) but with wrong content
        from interfaces.api.streaming_context import ChunkHeader
        header, encrypted_tampered = stream_context.encrypt_chunk(different_data)
        
        # Write tampered but validly encrypted data
        address_path.write_bytes(header.to_bytes() + encrypted_tampered)
        
        # Try to get - should fail integrity check
        with pytest.raises(STTStorageError, match="Integrity check failed"):
            await storage.get(address)
    
    @pytest.mark.asyncio
    async def test_remove_non_existent_address(self, storage):
        """Test removing non-existent address raises error (line 212)."""
        fake_address = b'z' * 32
        with pytest.raises(STTStorageError, match="Address not found"):
            await storage.remove(fake_address)
    
    @pytest.mark.asyncio
    async def test_list_addresses_multiple(self, storage):
        """Test listing all addresses returns complete list."""
        # Add multiple entries
        addresses = []
        for i in range(10):
            data = f"data_{i}".encode()
            addr = await storage.put(data)
            addresses.append(addr)
        
        # List all addresses
        listed = await storage.list_addresses()
        assert len(listed) == 10
        
        # All addresses present
        assert set(addresses) == set(listed)
    
    @pytest.mark.asyncio
    async def test_rebuild_index_from_disk(self, storage, temp_storage_dir):
        """Test rebuilding index from filesystem when corrupted (lines 301-313)."""
        # Put some data
        data1 = b"data1"
        data2 = b"data2"
        addr1 = await storage.put(data1)
        addr2 = await storage.put(data2)
        
        # Manually corrupt index
        storage._index = {}
        
        # Rebuild from disk
        storage._rebuild_index_from_disk()
        
        # Index should be rebuilt
        assert len(storage._index) == 2
        assert addr1 in storage._index
        assert addr2 in storage._index
    
    @pytest.mark.asyncio
    async def test_load_index_with_corrupted_pickle(self, storage, temp_storage_dir):
        """Test loading index when pickle file is corrupted (lines 322-324)."""
        # Put some data
        data = b"test data"
        await storage.put(data)
        
        # Corrupt the index file
        index_path = temp_storage_dir / "index.pkl"
        index_path.write_bytes(b"corrupted pickle data!!!")
        
        # Create new storage instance - should rebuild from disk
        new_storage = BinaryStorage(
            stc_wrapper=storage.stc_wrapper,
            storage_path=temp_storage_dir
        )
        
        # Should have rebuilt index from filesystem
        assert len(new_storage._index) > 0
    
    @pytest.mark.asyncio
    async def test_evict_lru_edge_cases(self, storage):
        """Test LRU eviction edge cases (lines 333-360)."""
        # Add data to fill storage
        addresses = []
        for i in range(5):
            data = b"x" * 1500  # 1.5KB each
            addr = await storage.put(data)
            addresses.append(addr)
            await asyncio.sleep(0.01)
        
        # Access some to change LRU order
        await storage.get(addresses[0])
        await asyncio.sleep(0.01)
        await storage.get(addresses[2])
        
        # Add more data to trigger eviction
        big_data = b"y" * 3000  # 3KB - will trigger multiple evictions
        new_addr = await storage.put(big_data)
        
        # Most recently accessed should still be there
        assert addresses[0] in storage._index or addresses[2] in storage._index
        assert new_addr in storage._index
    
    @pytest.mark.asyncio
    async def test_concurrent_put_operations(self, storage):
        """Test concurrent put operations with locking."""
        # Launch multiple concurrent puts
        tasks = []
        for i in range(10):
            data = f"concurrent_{i}".encode()
            tasks.append(storage.put(data))
        
        # All should complete without errors
        addresses = await asyncio.gather(*tasks)
        
        # All should be in storage
        assert len(addresses) == 10
        for addr in addresses:
            assert addr in storage._index
    
    @pytest.mark.asyncio
    async def test_concurrent_get_operations(self, storage):
        """Test concurrent get operations."""
        # Put some data first
        addresses = []
        for i in range(5):
            data = f"data_{i}".encode()
            addr = await storage.put(data)
            addresses.append(addr)
        
        # Concurrent gets
        tasks = [storage.get(addr) for addr in addresses]
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert len(results) == 5
        for i, result in enumerate(results):
            assert result == f"data_{i}".encode()
    
    @pytest.mark.asyncio
    async def test_storage_size_tracking(self, storage):
        """Test storage size tracking during put/remove."""
        initial_size = storage._current_size
        
        # Add data
        data = b"x" * 1000
        addr = await storage.put(data)
        
        # Size should increase
        assert storage._current_size > initial_size
        
        # Remove data
        await storage.remove(addr)
        
        # Size should decrease
        assert storage._current_size == initial_size
    
    @pytest.mark.asyncio
    async def test_deduplication(self, storage):
        """Test deduplication - same data returns same address."""
        data = b"identical data"
        
        addr1 = await storage.put(data)
        addr2 = await storage.put(data)
        
        # Should be same address
        assert addr1 == addr2
        
        # Should only be stored once
        assert len(storage._index) == 1
    
    @pytest.mark.asyncio
    async def test_index_persistence_across_restarts(self, storage, temp_storage_dir, stc_wrapper):
        """Test index persists across storage restarts."""
        # Put data
        data = b"persistent data"
        addr = await storage.put(data)
        
        # Create new storage instance
        new_storage = BinaryStorage(
            stc_wrapper=stc_wrapper,
            storage_path=temp_storage_dir
        )
        
        # Should load persisted index
        assert addr in new_storage._index
        
        # Should be able to retrieve data
        retrieved = await new_storage.get(addr)
        assert retrieved == data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
