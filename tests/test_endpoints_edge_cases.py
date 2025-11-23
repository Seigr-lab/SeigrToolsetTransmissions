"""
Edge case tests for EndpointManager - error paths and edge cases.
Targets uncovered lines: 76, 99, 123, 127, 154-163, 188, 196-204, 230, 242-243, 286-289
"""

import pytest
import asyncio
from seigr_toolset_transmissions.endpoints.manager import EndpointManager
from seigr_toolset_transmissions.utils.exceptions import STTEndpointError


class TestEndpointManagerEdgeCases:
    """Test error paths and edge cases in EndpointManager."""
    
    @pytest.fixture
    def manager(self):
        """Create endpoint manager instance."""
        return EndpointManager()
    
    @pytest.mark.asyncio
    async def test_add_duplicate_endpoint_fails(self, manager):
        """Test adding duplicate endpoint raises error (line 76)."""
        endpoint_id = b'test_endpoint_id_123_456_789'
        address = ('192.168.1.1', 8080)
        
        # Add first time - should succeed
        await manager.add_endpoint(endpoint_id, address)
        
        # Add duplicate - should fail
        with pytest.raises(STTEndpointError, match="Endpoint already exists"):
            await manager.add_endpoint(endpoint_id, address)
    
    @pytest.mark.asyncio
    async def test_remove_nonexistent_endpoint_fails(self, manager):
        """Test removing non-existent endpoint raises error (line 99)."""
        fake_endpoint_id = b'nonexistent_endpoint_xyz_123'
        
        with pytest.raises(STTEndpointError, match="Endpoint not found"):
            await manager.remove_endpoint(fake_endpoint_id)
    
    @pytest.mark.asyncio
    async def test_send_to_nonexistent_endpoint_fails(self, manager):
        """Test sending to non-existent endpoint raises error (line 123)."""
        fake_endpoint_id = b'nonexistent_endpoint_xyz_123'
        data = b"test_message"
        
        with pytest.raises(STTEndpointError, match="Endpoint not found"):
            await manager.send_to(fake_endpoint_id, data)
    
    @pytest.mark.asyncio
    async def test_send_with_empty_data(self, manager):
        """Test sending empty data (line 127)."""
        endpoint_id = b'test_endpoint_id_123_456_789'
        address = ('192.168.1.1', 8080)
        
        await manager.add_endpoint(endpoint_id, address)
        
        # Should handle empty data gracefully
        await manager.send_to(endpoint_id, b"")
        
        info = manager.get_endpoint_info(endpoint_id)
        assert info['bytes_sent'] == 0
    
    @pytest.mark.asyncio
    async def test_receive_from_nonexistent_endpoint_fails(self, manager):
        """Test receiving from non-existent endpoint raises error (line 154-163)."""
        fake_endpoint_id = b'nonexistent_endpoint_xyz_123'
        
        with pytest.raises(STTEndpointError, match="Endpoint not found"):
            await manager.receive_from(fake_endpoint_id)
    
    @pytest.mark.asyncio
    async def test_receive_timeout(self, manager):
        """Test receive timeout when no data available (line 154-163)."""
        endpoint_id = b'test_endpoint_id_123_456_789'
        address = ('192.168.1.1', 8080)
        
        await manager.add_endpoint(endpoint_id, address)
        
        # Receive with short timeout - should timeout
        with pytest.raises(STTEndpointError, match="timeout"):
            await manager.receive_from(endpoint_id, timeout=0.1)
    
    @pytest.mark.asyncio
    async def test_get_info_nonexistent_endpoint_returns_none(self, manager):
        """Test getting info for non-existent endpoint returns None (line 286-289)."""
        fake_endpoint_id = b'nonexistent_endpoint_xyz_123'
        
        info = manager.get_endpoint_info(fake_endpoint_id)
        assert info is None
    
    
    @pytest.mark.asyncio
    async def test_send_to_many_with_no_endpoints(self, manager):
        """Test send_to_many with empty list (line 154-163)."""
        data = b"broadcast_message"
        
        # Should handle empty endpoint list gracefully
        results = await manager.send_to_many([], data)
        
        # No error expected, empty results
        assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_send_to_many_partial_failure(self, manager):
        """Test send_to_many with some non-existent endpoints (line 154-163)."""
        endpoint1 = b'endpoint_1_test_123456789012'
        fake_endpoint = b'fake_endpoint_xyz_123_456_78'
        
        await manager.add_endpoint(endpoint1, ('192.168.1.1', 8080))
        
        data = b"test_message"
        
        # Send to mix of valid and invalid endpoints
        results = await manager.send_to_many([endpoint1, fake_endpoint], data)
        
        # endpoint1 should succeed, fake should fail
        assert results[endpoint1] == True
        assert results[fake_endpoint] == False
    
    
    @pytest.mark.asyncio
    async def test_endpoint_lifecycle(self, manager):
        """Test complete endpoint lifecycle - add, use, remove."""
        endpoint_id = b'test_endpoint_id_123_456_789'
        address = ('192.168.1.1', 8080)
        metadata = {'protocol': 'websocket', 'version': '1.0'}
        
        # Add with metadata
        await manager.add_endpoint(endpoint_id, address, metadata=metadata)
        
        # Verify it exists
        endpoints = manager.get_endpoints()
        assert endpoint_id in endpoints
        
        # Get info
        info = manager.get_endpoint_info(endpoint_id)
        assert info['bytes_sent'] == 0
        assert info['bytes_received'] == 0
        assert info['address'] == address
        assert info['metadata'] == metadata
        
        # Send data
        await manager.send_to(endpoint_id, b"test_data")
        info = manager.get_endpoint_info(endpoint_id)
        assert info['bytes_sent'] == 9
        
        # Remove
        await manager.remove_endpoint(endpoint_id)
        
        # Verify removed
        endpoints = manager.get_endpoints()
        assert endpoint_id not in endpoints
    
    @pytest.mark.asyncio
    async def test_concurrent_endpoint_operations(self, manager):
        """Test concurrent operations on different endpoints."""
        endpoints = [
            (b'endpoint_1_test_123456789012', ('192.168.1.1', 8080)),
            (b'endpoint_2_test_123456789012', ('192.168.1.2', 8080)),
            (b'endpoint_3_test_123456789012', ('192.168.1.3', 8080)),
        ]
        
        # Add all concurrently
        await asyncio.gather(*[
            manager.add_endpoint(ep_id, addr)
            for ep_id, addr in endpoints
        ])
        
        # Send to all concurrently
        await asyncio.gather(*[
            manager.send_to(ep_id, b"concurrent_test")
            for ep_id, addr in endpoints
        ])
        
        # Verify all have stats
        for ep_id, addr in endpoints:
            info = manager.get_endpoint_info(ep_id)
            assert info['bytes_sent'] == 15
        
        # Remove all concurrently
        await asyncio.gather(*[
            manager.remove_endpoint(ep_id)
            for ep_id, addr in endpoints
        ])
        
        # Verify all removed
        remaining = manager.get_endpoints()
        assert len(remaining) == 0
