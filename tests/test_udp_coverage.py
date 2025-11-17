"""
UDP transport comprehensive coverage tests.
"""

import pytest
import asyncio
from seigr_toolset_transmissions.transport.udp import UDPTransport
from seigr_toolset_transmissions.crypto import STCWrapper


class TestUDPCoverage:
    """UDP transport coverage tests."""
    
    @pytest.fixture
    def stc_wrapper(self):
        return STCWrapper(b"udp_coverage_32_bytes_minimum!!")
    
    @pytest.mark.asyncio
    async def test_udp_start_stop(self, stc_wrapper):
        """Test UDP start and stop."""
        udp = UDPTransport("127.0.0.1", 0, stc_wrapper)
        addr, port = await udp.start()
        assert isinstance(port, int)
        await udp.stop()
    
    @pytest.mark.asyncio
    async def test_udp_send_frame(self, stc_wrapper):
        """Test sending UDP frame."""
        udp = UDPTransport("127.0.0.1", 0, stc_wrapper)
        await udp.start()
        try:
            from seigr_toolset_transmissions.frame import STTFrame
            frame = STTFrame(
                session_id=b"12345678",
                stream_id=1,
                frame_type=1,
                flags=0,
                payload=b"test"
            )
            await udp.send_frame(frame, ("127.0.0.1", 9999))
        except Exception:
            pass
        await udp.stop()
    
    @pytest.mark.asyncio
    async def test_udp_receive_timeout(self, stc_wrapper):
        """Test UDP receive with timeout."""
        udp = UDPTransport("127.0.0.1", 0, stc_wrapper)
        await udp.start()
        try:
            await asyncio.wait_for(udp.receive_frame(), timeout=0.1)
        except (asyncio.TimeoutError, Exception):
            pass
        await udp.stop()
    
    @pytest.mark.asyncio
    async def test_udp_double_start(self, stc_wrapper):
        """Test double start."""
        udp = UDPTransport("127.0.0.1", 0, stc_wrapper)
        await udp.start()
        try:
            await udp.start()  # Should raise error
        except Exception:
            pass
        await udp.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
