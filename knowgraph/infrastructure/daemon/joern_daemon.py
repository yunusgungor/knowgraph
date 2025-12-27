"""Joern daemon mode for persistent process (optional advanced feature).

Keeps Joern process running to avoid startup overhead on repeated queries.
"""

import logging
import subprocess
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class JoernDaemon:
    """Manage Joern as a persistent daemon process."""
    
    def __init__(self, joern_path: Path):
        """Initialize Joern daemon manager.
        
        Args:
            joern_path: Path to joern-cli directory
        """
        self.joern_path = joern_path
        self.process: Optional[subprocess.Popen] = None
        self.is_running = False
    
    def start(self) -> bool:
        """Start Joern daemon process.
        
        Returns:
            True if started successfully
        """
        if self.is_running:
            logger.warning("Joern daemon already running")
            return True
        
        try:
            # Note: This is a simplified implementation
            # Full daemon mode would require Joern server setup
            logger.info("Starting Joern daemon...")
            
            # For now, just mark as conceptually started
            # Real implementation would start actual Joern server
            self.is_running = True
            
            logger.info("Joern daemon started (conceptual)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Joern daemon: {e}")
            return False
    
    def stop(self) -> bool:
        """Stop Joern daemon process.
        
        Returns:
            True if stopped successfully
        """
        if not self.is_running:
            logger.warning("Joern daemon not running")
            return True
        
        try:
            logger.info("Stopping Joern daemon...")
            
            if self.process:
                self.process.terminate()
                self.process.wait(timeout=10)
            
            self.is_running = False
            self.process = None
            
            logger.info("Joern daemon stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop Joern daemon: {e}")
            return False
    
    def restart(self) -> bool:
        """Restart Joern daemon.
        
        Returns:
            True if restarted successfully
        """
        self.stop()
        time.sleep(1)
        return self.start()
    
    def is_healthy(self) -> bool:
        """Check if daemon is healthy.
        
        Returns:
            True if daemon is running and responsive
        """
        if not self.is_running:
            return False
        
        # In real implementation, would ping Joern server
        return True
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        return False


# Note: This is a conceptual implementation
# Full Joern daemon mode would require:
# 1. Joern server mode (if available)
# 2. HTTP/gRPC API for queries
# 3. Connection pooling
# 4. Health monitoring
# 5. Automatic restart on failure
#
# Current Joern CLI doesn't have built-in daemon mode,
# so this would need custom server wrapper or use of
# Joern's programmatic API if available.
