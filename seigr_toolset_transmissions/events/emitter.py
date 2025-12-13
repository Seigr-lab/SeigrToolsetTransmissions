"""
Agnostic event system - User-defined event semantics.

Provides event hooks with NO assumptions about meaning.
User defines all event semantics.
"""

import asyncio
from typing import Callable, Dict, List, Any, Optional

from ..utils.exceptions import STTEventError


class EventEmitter:
    """
    Event system for binary transport.
    
    NO assumptions about:
    - Event semantics (user defines)
    - Event data structure (user decides)
    - Event handling logic (user implements)
    
    Provides:
    - Event registration (@stt.on(event_name))
    - Async event dispatch
    - Multiple handlers per event
    """
    
    def __init__(self):
        """Initialize event emitter."""
        # Event handlers (event_name -> list of async callables)
        self._handlers: Dict[str, List[Callable]] = {}
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
    
    def on(self, event_name: str) -> Callable:
        """
        Decorator to register event handler.
        
        Args:
            event_name: Event to listen for (user defines)
        
        Returns:
            Decorator function
        
        Example:
            @stt.on('bytes_received')
            async def handle_bytes(bytes: bytes, endpoint_id: bytes):
                # User interprets bytes
                user_process(bytes)
            
            @stt.on('endpoint_connected')
            async def handle_connection(endpoint_id: bytes):
                # User decides what connection means
                user_handle_peer(endpoint_id)
            
            @stt.on('custom_event')  # User can define any events
            async def handle_custom(data: dict):
                # User defines structure and meaning
                pass
        """
        def decorator(handler: Callable) -> Callable:
            # Verify handler is async
            if not asyncio.iscoroutinefunction(handler):
                raise STTEventError(f"Event handler must be async: {handler.__name__}")
            
            # Register handler
            if event_name not in self._handlers:
                self._handlers[event_name] = []
            
            self._handlers[event_name].append(handler)
            
            return handler
        
        return decorator
    
    def register(self, event_name: str, handler: Callable) -> None:
        """
        Register event handler programmatically.
        
        Args:
            event_name: Event to listen for
            handler: Async callable to handle event
        
        Example:
            async def my_handler(data):
                pass
            
            emitter.register('my_event', my_handler)
        """
        if not asyncio.iscoroutinefunction(handler):
            raise STTEventError(f"Event handler must be async: {handler.__name__}")
        
        if event_name not in self._handlers:
            self._handlers[event_name] = []
        
        self._handlers[event_name].append(handler)
    
    def unregister(self, event_name: str, handler: Callable) -> None:
        """
        Unregister event handler.
        
        Args:
            event_name: Event name
            handler: Handler to remove
        """
        if event_name in self._handlers:
            if handler in self._handlers[event_name]:
                self._handlers[event_name].remove(handler)
    
    async def emit(self, event_name: str, *args, **kwargs) -> List[Any]:
        """
        Emit event to all registered handlers.
        
        Args:
            event_name: Event to emit
            *args: Positional arguments for handlers
            **kwargs: Keyword arguments for handlers
        
        Returns:
            List of handler return values
        
        Example:
            # Emit bytes_received event
            await emitter.emit('bytes_received', b"data", endpoint_id)
            
            # Emit custom event
            await emitter.emit('my_event', custom_data={'foo': 'bar'})
        """
        if event_name not in self._handlers:
            return []  # No handlers registered
        
        results = []
        
        # Call all handlers concurrently
        tasks = []
        for handler in self._handlers[event_name]:
            task = asyncio.create_task(handler(*args, **kwargs))
            tasks.append(task)
        
        # Wait for all handlers to complete
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return results
    
    def get_handlers(self, event_name: str) -> List[Callable]:
        """
        Get all handlers for event.
        
        Args:
            event_name: Event to query
        
        Returns:
            List of registered handlers
        """
        return self._handlers.get(event_name, [])
    
    def get_events(self) -> List[str]:
        """
        Get all registered event names.
        
        Returns:
            List of event names
        """
        return list(self._handlers.keys())
    
    def clear_handlers(self, event_name: Optional[str] = None) -> None:
        """
        Clear event handlers.
        
        Args:
            event_name: Specific event to clear, or None to clear all
        """
        if event_name is not None:
            if event_name in self._handlers:
                self._handlers[event_name].clear()
        else:
            self._handlers.clear()


# Built-in event names (user can define more)
class STTEvents:
    """Standard STT event names (user can define additional events)."""
    
    # Binary transport events
    BYTES_RECEIVED = 'bytes_received'  # (bytes, endpoint_id)
    BYTES_SENT = 'bytes_sent'  # (bytes, endpoint_id)
    
    # Endpoint events
    ENDPOINT_CONNECTED = 'endpoint_connected'  # (endpoint_id)
    ENDPOINT_DISCONNECTED = 'endpoint_disconnected'  # (endpoint_id)
    
    # Stream events
    STREAM_OPENED = 'stream_opened'  # (stream_id, mode)
    STREAM_CLOSED = 'stream_closed'  # (stream_id)
    SEGMENT_RECEIVED = 'segment_received'  # (segment, stream_id, sequence)
    
    # Storage events
    BYTES_STORED = 'bytes_stored'  # (address)
    BYTES_RETRIEVED = 'bytes_retrieved'  # (address)
    
    # Error events
    ERROR = 'error'  # (exception, context)
    
    # User can define custom events by not using these constants
