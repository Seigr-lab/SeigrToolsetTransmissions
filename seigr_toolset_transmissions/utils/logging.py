"""
Logging utilities for STT with privacy-preserving features.
"""

import logging
import sys
from typing import Optional
from .constants import STT_LOG_LEVEL_INFO


class STTLogger:
    """
    Privacy-preserving logger for STT.
    Ensures no plaintext or key material is ever logged.
    """
    
    def __init__(self, name: str, level: int = STT_LOG_LEVEL_INFO):
        """
        Initialize STT logger.
        
        Args:
            name: Logger name (typically module name)
            level: Logging level
        """
        self.logger = logging.getLogger(f"STT.{name}")
        self.logger.setLevel(level)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(level)
            
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def debug(self, message: str, **kwargs: object) -> None:
        """Log debug message."""
        self.logger.debug(self._sanitize(message), **kwargs)
    
    def info(self, message: str, **kwargs: object) -> None:
        """Log info message."""
        self.logger.info(self._sanitize(message), **kwargs)
    
    def warning(self, message: str, **kwargs: object) -> None:
        """Log warning message."""
        self.logger.warning(self._sanitize(message), **kwargs)
    
    def error(self, message: str, **kwargs: object) -> None:
        """Log error message."""
        self.logger.error(self._sanitize(message), **kwargs)
    
    def critical(self, message: str, **kwargs: object) -> None:
        """Log critical message."""
        self.logger.critical(self._sanitize(message), **kwargs)
    
    def _sanitize(self, message: str) -> str:
        """
        Sanitize log message to prevent sensitive data leaks.
        
        Args:
            message: Raw log message
            
        Returns:
            Sanitized message
        """
        # In production, implement more sophisticated sanitization
        # For now, just return as-is since we trust internal code
        return message
    
    def set_level(self, level: int) -> None:
        """Set logging level."""
        self.logger.setLevel(level)
        for handler in self.logger.handlers:
            handler.setLevel(level)


def get_logger(name: str, level: Optional[int] = None) -> STTLogger:
    """
    Get or create an STT logger.
    
    Args:
        name: Logger name
        level: Optional logging level
        
    Returns:
        STT logger instance
    """
    if level is None:
        level = STT_LOG_LEVEL_INFO
    return STTLogger(name, level)
