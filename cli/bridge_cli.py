"""
CLI tool for running the WebSocket bridge.
"""

import asyncio
import argparse
import signal
import sys

from seigr_toolset_transmissions import WebSocketBridge
from seigr_toolset_transmissions.utils.logging import get_logger
from seigr_toolset_transmissions.utils.constants import (
    STT_DEFAULT_WS_PORT,
    STT_DEFAULT_TCP_PORT,
)


logger = get_logger(__name__)


class BridgeCLI:
    """Command-line interface for WebSocket bridge."""
    
    def __init__(self):
        self.bridge: WebSocketBridge | None = None
        self.shutdown_event = asyncio.Event()
    
    def signal_handler(self, signum: int, frame: object) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        self.shutdown_event.set()
    
    async def run_bridge(
        self,
        ws_host: str,
        ws_port: int,
        backend_host: str,
        backend_port: int,
    ) -> None:
        """
        Run WebSocket bridge.
        
        Args:
            ws_host: WebSocket host to bind
            ws_port: WebSocket port
            backend_host: STT backend host
            backend_port: STT backend port
        """
        try:
            # Create and start bridge
            self.bridge = WebSocketBridge(
                ws_host=ws_host,
                ws_port=ws_port,
                backend_host=backend_host,
                backend_port=backend_port,
            )
            
            await self.bridge.start()
            
            logger.info(f"Bridge running. Press Ctrl+C to stop.")
            logger.info(f"WebSocket: ws://{ws_host}:{ws_port}")
            logger.info(f"Backend: {backend_host}:{backend_port}")
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
        except ImportError as e:
            logger.error(
                "WebSocket bridge requires 'websockets' package. "
                "Install with: pip install seigr-toolset-transmissions[websocket]"
            )
            raise
        
        except Exception as e:
            logger.error(f"Bridge error: {e}")
            raise
        
        finally:
            if self.bridge:
                logger.info("Stopping bridge...")
                await self.bridge.stop()
                logger.info("Bridge stopped")


def main() -> None:
    """Main entry point for bridge CLI."""
    parser = argparse.ArgumentParser(
        description="Run an STT WebSocket bridge for browser compatibility"
    )
    
    parser.add_argument(
        '--ws-host',
        type=str,
        default='0.0.0.0',
        help='WebSocket host to bind (default: 0.0.0.0)'
    )
    
    parser.add_argument(
        '--ws-port',
        type=int,
        default=STT_DEFAULT_WS_PORT,
        help=f'WebSocket port (default: {STT_DEFAULT_WS_PORT})'
    )
    
    parser.add_argument(
        '--backend-host',
        type=str,
        default='127.0.0.1',
        help='STT backend host (default: 127.0.0.1)'
    )
    
    parser.add_argument(
        '--backend-port',
        type=int,
        default=STT_DEFAULT_TCP_PORT,
        help=f'STT backend port (default: {STT_DEFAULT_TCP_PORT})'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Set up logging level
    if args.verbose:
        from seigr_toolset_transmissions.utils.constants import STT_LOG_LEVEL_DEBUG
        logger.set_level(STT_LOG_LEVEL_DEBUG)
    
    # Create CLI instance
    cli = BridgeCLI()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, cli.signal_handler)
    signal.signal(signal.SIGTERM, cli.signal_handler)
    
    # Run bridge
    try:
        asyncio.run(
            cli.run_bridge(
                args.ws_host,
                args.ws_port,
                args.backend_host,
                args.backend_port,
            )
        )
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
