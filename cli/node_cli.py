"""
CLI tool for running an STT node.
"""

import asyncio
import argparse
import signal
import sys
from pathlib import Path

from seigr_toolset_transmissions import STTNode
from seigr_toolset_transmissions.utils.logging import get_logger
from seigr_toolset_transmissions.utils.constants import STT_DEFAULT_TCP_PORT


logger = get_logger(__name__)


class NodeCLI:
    """Command-line interface for STT node."""
    
    def __init__(self):
        self.node: STTNode | None = None
        self.shutdown_event = asyncio.Event()
    
    def signal_handler(self, signum: int, frame: object) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        self.shutdown_event.set()
    
    async def run_node(
        self,
        host: str,
        port: int,
        chamber_path: Path | None,
    ) -> None:
        """
        Run STT node.
        
        Args:
            host: Host to bind
            port: Port to listen on
            chamber_path: Optional chamber path
        """
        try:
            # Create and start node
            self.node = STTNode(
                host=host,
                port=port,
                chamber_path=chamber_path,
            )
            
            await self.node.start()
            
            logger.info(f"Node running. Press Ctrl+C to stop.")
            logger.info(f"Node ID: {self.node.node_id.hex()}")
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
        except Exception as e:
            logger.error(f"Node error: {e}")
            raise
        
        finally:
            if self.node:
                logger.info("Stopping node...")
                await self.node.stop()
                logger.info("Node stopped")


def main() -> None:
    """Main entry point for node CLI."""
    parser = argparse.ArgumentParser(
        description="Run an STT (Seigr Toolset Transmissions) node"
    )
    
    parser.add_argument(
        '--host',
        type=str,
        default='127.0.0.1',
        help='Host address to bind (default: 127.0.0.1)'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=STT_DEFAULT_TCP_PORT,
        help=f'Port to listen on (default: {STT_DEFAULT_TCP_PORT})'
    )
    
    parser.add_argument(
        '--chamber',
        type=Path,
        default=None,
        help='Path to chamber storage directory (default: ~/.seigr/chambers/...)'
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
    cli = NodeCLI()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, cli.signal_handler)
    signal.signal(signal.SIGTERM, cli.signal_handler)
    
    # Run node
    try:
        asyncio.run(cli.run_node(args.host, args.port, args.chamber))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
