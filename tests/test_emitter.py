"""
Comprehensive tests for events/emitter.py
Tests all event registration, emission, and management functionality.
"""

import pytest
import asyncio
from seigr_toolset_transmissions.events.emitter import EventEmitter, STTEvents
from seigr_toolset_transmissions.utils.exceptions import STTEventError


@pytest.fixture
def emitter():
    """Create fresh EventEmitter for each test."""
    return EventEmitter()


class TestEventRegistration:
    """Test event handler registration."""
    
    @pytest.mark.asyncio
    async def test_on_decorator_registers_handler(self, emitter):
        """Test @emitter.on() decorator registers async handler."""
        @emitter.on('test_event')
        async def handler(data):
            return data
        
        handlers = emitter.get_handlers('test_event')
        assert len(handlers) == 1
        assert handlers[0] == handler
    
    @pytest.mark.asyncio
    async def test_on_decorator_rejects_sync_handler(self, emitter):
        """Test @emitter.on() rejects non-async handler."""
        with pytest.raises(STTEventError, match="Event handler must be async"):
            @emitter.on('test_event')
            def sync_handler(data):  # Not async!
                return data
    
    @pytest.mark.asyncio
    async def test_register_method_adds_handler(self, emitter):
        """Test programmatic handler registration."""
        async def handler(data):
            return data
        
        emitter.register('test_event', handler)
        
        handlers = emitter.get_handlers('test_event')
        assert len(handlers) == 1
        assert handlers[0] == handler
    
    @pytest.mark.asyncio
    async def test_register_rejects_sync_handler(self, emitter):
        """Test register() rejects non-async handler."""
        def sync_handler(data):
            return data
        
        with pytest.raises(STTEventError, match="Event handler must be async"):
            emitter.register('test_event', sync_handler)
    
    @pytest.mark.asyncio
    async def test_multiple_handlers_same_event(self, emitter):
        """Test multiple handlers can be registered for same event."""
        @emitter.on('test_event')
        async def handler1(data):
            return 1
        
        @emitter.on('test_event')
        async def handler2(data):
            return 2
        
        handlers = emitter.get_handlers('test_event')
        assert len(handlers) == 2
        assert handler1 in handlers
        assert handler2 in handlers


class TestEventEmission:
    """Test event emission and handler execution."""
    
    @pytest.mark.asyncio
    async def test_emit_calls_registered_handler(self, emitter):
        """Test emit() calls registered handler."""
        called = []
        
        @emitter.on('test_event')
        async def handler(data):
            called.append(data)
            return data
        
        results = await emitter.emit('test_event', 'test_data')
        
        assert called == ['test_data']
        assert results == ['test_data']
    
    @pytest.mark.asyncio
    async def test_emit_with_no_handlers(self, emitter):
        """Test emit() with no registered handlers returns empty list."""
        results = await emitter.emit('nonexistent_event', 'data')
        assert results == []
    
    @pytest.mark.asyncio
    async def test_emit_calls_all_handlers(self, emitter):
        """Test emit() calls all registered handlers."""
        results_collected = []
        
        @emitter.on('test_event')
        async def handler1(data):
            results_collected.append('h1')
            return 1
        
        @emitter.on('test_event')
        async def handler2(data):
            results_collected.append('h2')
            return 2
        
        @emitter.on('test_event')
        async def handler3(data):
            results_collected.append('h3')
            return 3
        
        results = await emitter.emit('test_event', 'data')
        
        # All handlers should be called
        assert len(results_collected) == 3
        assert set(results_collected) == {'h1', 'h2', 'h3'}
        
        # All results returned
        assert len(results) == 3
        assert set(results) == {1, 2, 3}
    
    @pytest.mark.asyncio
    async def test_emit_with_args_and_kwargs(self, emitter):
        """Test emit() passes args and kwargs to handlers."""
        received = []
        
        @emitter.on('test_event')
        async def handler(arg1, arg2, key1=None, key2=None):
            received.append((arg1, arg2, key1, key2))
            return 'ok'
        
        await emitter.emit('test_event', 'a', 'b', key1='k1', key2='k2')
        
        assert received == [('a', 'b', 'k1', 'k2')]
    
    @pytest.mark.asyncio
    async def test_emit_handler_exception_returns_exception(self, emitter):
        """Test emit() returns exceptions from handlers."""
        @emitter.on('test_event')
        async def failing_handler(data):
            raise ValueError("Handler failed")
        
        @emitter.on('test_event')
        async def working_handler(data):
            return 'success'
        
        results = await emitter.emit('test_event', 'data')
        
        # Both results returned, one is exception
        assert len(results) == 2
        assert 'success' in results
        assert any(isinstance(r, ValueError) for r in results)
    
    @pytest.mark.asyncio
    async def test_emit_concurrent_execution(self, emitter):
        """Test emit() executes handlers concurrently."""
        execution_order = []
        
        @emitter.on('test_event')
        async def slow_handler():
            execution_order.append('slow_start')
            await asyncio.sleep(0.05)
            execution_order.append('slow_end')
            return 'slow'
        
        @emitter.on('test_event')
        async def fast_handler():
            execution_order.append('fast_start')
            await asyncio.sleep(0.01)
            execution_order.append('fast_end')
            return 'fast'
        
        results = await emitter.emit('test_event')
        
        # Both should have completed
        assert set(results) == {'slow', 'fast'}
        
        # Fast handler should finish before slow handler
        assert execution_order.index('fast_end') < execution_order.index('slow_end')


class TestHandlerManagement:
    """Test handler management operations."""
    
    @pytest.mark.asyncio
    async def test_unregister_removes_handler(self, emitter):
        """Test unregister() removes specific handler."""
        @emitter.on('test_event')
        async def handler1(data):
            return 1
        
        @emitter.on('test_event')
        async def handler2(data):
            return 2
        
        # Verify both registered
        assert len(emitter.get_handlers('test_event')) == 2
        
        # Unregister one
        emitter.unregister('test_event', handler1)
        
        handlers = emitter.get_handlers('test_event')
        assert len(handlers) == 1
        assert handlers[0] == handler2
    
    @pytest.mark.asyncio
    async def test_unregister_nonexistent_event(self, emitter):
        """Test unregister() with nonexistent event does nothing."""
        async def handler(data):
            return data
        
        # Should not raise exception
        emitter.unregister('nonexistent_event', handler)
    
    @pytest.mark.asyncio
    async def test_unregister_nonexistent_handler(self, emitter):
        """Test unregister() with handler not in list does nothing."""
        @emitter.on('test_event')
        async def registered_handler(data):
            return 1
        
        async def unregistered_handler(data):
            return 2
        
        # Should not raise exception
        emitter.unregister('test_event', unregistered_handler)
        
        # Registered handler still there
        assert len(emitter.get_handlers('test_event')) == 1
    
    @pytest.mark.asyncio
    async def test_get_handlers_returns_copy(self, emitter):
        """Test get_handlers() returns handlers for event."""
        @emitter.on('test_event')
        async def handler(data):
            return data
        
        handlers = emitter.get_handlers('test_event')
        assert len(handlers) == 1
        assert handlers[0] == handler
    
    @pytest.mark.asyncio
    async def test_get_handlers_nonexistent_event(self, emitter):
        """Test get_handlers() for nonexistent event returns empty list."""
        handlers = emitter.get_handlers('nonexistent_event')
        assert handlers == []
    
    @pytest.mark.asyncio
    async def test_get_events_returns_event_names(self, emitter):
        """Test get_events() returns all registered event names."""
        @emitter.on('event1')
        async def handler1(data):
            return 1
        
        @emitter.on('event2')
        async def handler2(data):
            return 2
        
        @emitter.on('event3')
        async def handler3(data):
            return 3
        
        events = emitter.get_events()
        assert len(events) == 3
        assert set(events) == {'event1', 'event2', 'event3'}
    
    @pytest.mark.asyncio
    async def test_get_events_empty_emitter(self, emitter):
        """Test get_events() on empty emitter returns empty list."""
        events = emitter.get_events()
        assert events == []
    
    @pytest.mark.asyncio
    async def test_clear_handlers_specific_event(self, emitter):
        """Test clear_handlers() clears specific event."""
        @emitter.on('event1')
        async def handler1(data):
            return 1
        
        @emitter.on('event2')
        async def handler2(data):
            return 2
        
        # Clear only event1
        emitter.clear_handlers('event1')
        
        assert len(emitter.get_handlers('event1')) == 0
        assert len(emitter.get_handlers('event2')) == 1
    
    @pytest.mark.asyncio
    async def test_clear_handlers_nonexistent_event(self, emitter):
        """Test clear_handlers() on nonexistent event does nothing."""
        @emitter.on('event1')
        async def handler1(data):
            return 1
        
        # Should not raise exception
        emitter.clear_handlers('nonexistent_event')
        
        # event1 still has handler
        assert len(emitter.get_handlers('event1')) == 1
    
    @pytest.mark.asyncio
    async def test_clear_handlers_all_events(self, emitter):
        """Test clear_handlers(None) clears all events."""
        @emitter.on('event1')
        async def handler1(data):
            return 1
        
        @emitter.on('event2')
        async def handler2(data):
            return 2
        
        @emitter.on('event3')
        async def handler3(data):
            return 3
        
        # Clear all
        emitter.clear_handlers()
        
        assert len(emitter.get_events()) == 0
        assert len(emitter.get_handlers('event1')) == 0
        assert len(emitter.get_handlers('event2')) == 0
        assert len(emitter.get_handlers('event3')) == 0


class TestSTTEvents:
    """Test STTEvents constants."""
    
    def test_standard_event_constants_exist(self):
        """Test all standard event constants are defined."""
        assert STTEvents.BYTES_RECEIVED == 'bytes_received'
        assert STTEvents.BYTES_SENT == 'bytes_sent'
        assert STTEvents.ENDPOINT_CONNECTED == 'endpoint_connected'
        assert STTEvents.ENDPOINT_DISCONNECTED == 'endpoint_disconnected'
        assert STTEvents.STREAM_OPENED == 'stream_opened'
        assert STTEvents.STREAM_CLOSED == 'stream_closed'
        assert STTEvents.SEGMENT_RECEIVED == 'segment_received'
        assert STTEvents.BYTES_STORED == 'bytes_stored'
        assert STTEvents.BYTES_RETRIEVED == 'bytes_retrieved'
        assert STTEvents.ERROR == 'error'


class TestRealWorldUsage:
    """Test real-world usage patterns."""
    
    @pytest.mark.asyncio
    async def test_bytes_received_workflow(self, emitter):
        """Test realistic bytes_received event workflow."""
        received_data = []
        
        @emitter.on(STTEvents.BYTES_RECEIVED)
        async def process_bytes(data, endpoint_id):
            received_data.append((data, endpoint_id))
            return len(data)
        
        # Emit bytes received event
        results = await emitter.emit(STTEvents.BYTES_RECEIVED, b'test_data', b'endpoint_123')
        
        assert received_data == [(b'test_data', b'endpoint_123')]
        assert results == [9]  # Length of 'test_data'
    
    @pytest.mark.asyncio
    async def test_multiple_event_types(self, emitter):
        """Test multiple different event types."""
        events_fired = []
        
        @emitter.on(STTEvents.ENDPOINT_CONNECTED)
        async def on_connect(endpoint_id):
            events_fired.append(('connected', endpoint_id))
        
        @emitter.on(STTEvents.BYTES_SENT)
        async def on_sent(data, endpoint_id):
            events_fired.append(('sent', len(data)))
        
        @emitter.on(STTEvents.ENDPOINT_DISCONNECTED)
        async def on_disconnect(endpoint_id):
            events_fired.append(('disconnected', endpoint_id))
        
        # Fire events in sequence
        await emitter.emit(STTEvents.ENDPOINT_CONNECTED, b'peer1')
        await emitter.emit(STTEvents.BYTES_SENT, b'data', b'peer1')
        await emitter.emit(STTEvents.ENDPOINT_DISCONNECTED, b'peer1')
        
        assert len(events_fired) == 3
        assert events_fired[0] == ('connected', b'peer1')
        assert events_fired[1] == ('sent', 4)
        assert events_fired[2] == ('disconnected', b'peer1')
