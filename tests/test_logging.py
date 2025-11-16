"""
Tests for logging utility.
"""

import pytest
import logging
from seigr_toolset_transmissions.utils.logging import STTLogger


class TestSTTLogger:
    """Test STT logger."""
    
    def test_logger_warning_level(self):
        """Test logging at warning level."""
        logger = STTLogger("test_logger", level=logging.WARNING)
        
        # Should not raise
        logger.warning("Test warning message")
        logger.error("Test error message")
        logger.critical("Test critical message")
    
    def test_logger_set_level(self):
        """Test setting logger level."""
        logger = STTLogger("test_set_level", level=logging.INFO)
        
        # Change level
        logger.set_level(logging.ERROR)
        
        # Should not raise
        logger.error("Error message after level change")
    
    def test_logger_sanitize(self):
        """Test message sanitization."""
        logger = STTLogger("test_sanitize")
        
        # Currently returns message as-is
        sanitized = logger._sanitize("test message")
        assert sanitized == "test message"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
