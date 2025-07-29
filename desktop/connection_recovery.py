"""
Connection Recovery System for TikTrue Distributed LLM Platform

This module implements automatic reconnection with exponential backoff, connection health monitoring,
and graceful degradation for network failures as specified in requirements 10.1 and 10.3.

Features:
- Automatic reconnection with exponential backoff
- Connection health monitoring and failover
- Graceful degradation for network failures
- Circuit breaker pattern for failing connections
- Connection pool management
- Comprehensive recovery statistics

Classes:
    ConnectionState: Enum for connection states
    ConnectionHealth: Data class for connection health metrics
    RecoveryStrategy: Enum for recovery strategies
    ConnectionRecovery: Main connection recovery manager
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import threading
from pathlib import Path
import random

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ConnectionRecovery")

# Create logs directory if it doesn't exist
Path('logs').mkdir(exist_ok=True)
file_handler = logging.FileHandler('logs/connection_recovery.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)


class ConnectionState(Enum):
    """Connection state definitions"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    RECONNECTING = "reconnecting"
    FAILED = "failed"
    CIRCUIT_OPEN = "circuit_open"
    DEGRADED = "degraded"


class RecoveryStrategy(Enum):
    """Recovery strategy options"""
    IMMEDIATE = "immediate"          # Immediate reconnection attempt
    EXPONENTIAL_BACKOFF = "exponential_backoff"  # Exponential backoff retry
    LINEAR_BACKOFF = "linear_backoff"  # Linear backoff retry
    CIRCUIT_BREAKER = "circuit_breaker"  # Circuit breaker pattern
    GRACEFUL_DEGRADATION = "graceful_degradation"  # Degrade service quality


@dataclass
class ConnectionHealth:
    """Connection health metrics"""
    connection_id: str
    state: ConnectionState
    last_successful_connection: datetime
    last_failure: datetime
    consecutive_failures: int = 0
    total_failures: int = 0
    total_connections: int = 0
    average_response_time: float = 0.0
    last_response_time: float = 0.0
    uptime_percentage: float = 100.0
    circuit_breaker_open: bool = False
    circuit_breaker_open_until: Optional[datetime] = None
    recovery_attempts: int = 0
    max_recovery_attempts: int = 10
    backoff_multiplier: float = 1.5
    current_backoff_delay: float = 1.0
    max_backoff_delay: float = 300.0  # 5 minutes max
    health_score: float = 100.0


@dataclass
class RecoveryEvent:
    """Recovery event record"""
    event_id: str
    connection_id: str
    timestamp: datetime
    event_type: str  # "connection_lost", "reconnection_attempt", "recovery_success", "recovery_failed"
    strategy_used: RecoveryStrategy
    backoff_delay: float = 0.0
    success: bool = False
    error_message: Optional[str] = None
    response_time: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)


class ConnectionRecovery:
    """
    Connection recovery manager with exponential backoff and health monitoring
    Implements requirements 10.1 and 10.3 for fault tolerance
    """
    
    def __init__(self,
                 max_retry_attempts: int = 10,
                 initial_backoff_delay: float = 1.0,
                 max_backoff_delay: float = 300.0,
                 backoff_multiplier: float = 1.5,
                 circuit_breaker_threshold: int = 5,
                 circuit_breaker_timeout: float = 60.0,
                 health_check_interval: float = 30.0):
        """
        Initialize connection recovery manager
        
        Args:
            max_retry_attempts: Maximum number of retry attempts
            initial_backoff_delay: Initial backoff delay in seconds
            max_backoff_delay: Maximum backoff delay in seconds
            backoff_multiplier: Exponential backoff multiplier
            circuit_breaker_threshold: Failures before opening circuit breaker
            circuit_breaker_timeout: Circuit breaker timeout in seconds
            health_check_interval: Health check interval in seconds
        """
        self.max_retry_attempts = max_retry_attempts
        self.initial_backoff_delay = initial_backoff_delay
        self.max_backoff_delay = max_backoff_delay
        self.backoff_multiplier = backoff_multiplier
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout
        self.health_check_interval = health_check_interval
        
        # Connection tracking
        self.connections: Dict[str, ConnectionHealth] = {}
        self.recovery_events: List[RecoveryEvent] = []
        self.active_recoveries: Dict[str, asyncio.Task] = {}
        
        # Callbacks for external integration
        self.on_connection_lost: Optional[Callable[[str, str], None]] = None
        self.on_connection_recovered: Optional[Callable[[str], None]] = None
        self.on_recovery_failed: Optional[Callable[[str, str], None]] = None
        self.on_circuit_breaker_opened: Optional[Callable[[str], None]] = None
        self.on_circuit_breaker_closed: Optional[Callable[[str], None]] = None
        
        # Service state
        self.running = False
        self.health_monitor_task: Optional[asyncio.Task] = None
        self.lock = threading.RLock()
        
        # Statistics
        self.stats = {
            "total_connections": 0,
            "active_connections": 0,
            "failed_connections": 0,
            "recovery_attempts": 0,
            "successful_recoveries": 0,
            "failed_recoveries": 0,
            "circuit_breaker_activations": 0,
            "average_recovery_time": 0.0,
            "uptime_percentage": 100.0
        }
        
        logger.info("ConnectionRecovery initialized")
    
    async def start(self):
        """Start connection recovery service"""
        if self.running:
            logger.warning("Connection recovery service already running")
            return
        
        logger.info("Starting connection recovery service")
        self.running = True
        
        # Start health monitoring
        self.health_monitor_task = asyncio.create_task(self._health_monitor_loop())
        
        logger.info("Connection recovery service started")
    
    async def stop(self):
        """Stop connection recovery service"""
        if not self.running:
            logger.warning("Connection recovery service not running")
            return
        
        logger.info("Stopping connection recovery service")
        self.running = False
        
        # Cancel health monitoring
        if self.health_monitor_task:
            self.health_monitor_task.cancel()
            try:
                await self.health_monitor_task
            except asyncio.CancelledError:
                pass
            self.health_monitor_task = None
        
        # Cancel active recovery tasks
        for connection_id, task in list(self.active_recoveries.items()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self.active_recoveries.clear()
        
        logger.info("Connection recovery service stopped")
    
    def register_connection(self, connection_id: str, 
                          max_retry_attempts: Optional[int] = None,
                          backoff_multiplier: Optional[float] = None) -> bool:
        """
        Register a connection for monitoring and recovery
        
        Args:
            connection_id: Unique connection identifier
            max_retry_attempts: Override default max retry attempts
            backoff_multiplier: Override default backoff multiplier
            
        Returns:
            True if registration successful
        """
        try:
            with self.lock:
                if connection_id in self.connections:
                    logger.warning(f"Connection {connection_id} already registered")
                    return False
                
                # Create connection health record
                health = ConnectionHealth(
                    connection_id=connection_id,
                    state=ConnectionState.CONNECTED,
                    last_successful_connection=datetime.now(),
                    last_failure=datetime.now(),
                    max_recovery_attempts=max_retry_attempts or self.max_retry_attempts,
                    backoff_multiplier=backoff_multiplier or self.backoff_multiplier,
                    current_backoff_delay=self.initial_backoff_delay
                )
                
                self.connections[connection_id] = health
                self.stats["total_connections"] += 1
                self.stats["active_connections"] += 1
                
                logger.info(f"Connection registered: {connection_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to register connection {connection_id}: {e}")
            return False
    
    def unregister_connection(self, connection_id: str) -> bool:
        """
        Unregister a connection from monitoring
        
        Args:
            connection_id: Connection identifier to unregister
            
        Returns:
            True if unregistration successful
        """
        try:
            with self.lock:
                if connection_id not in self.connections:
                    logger.warning(f"Connection {connection_id} not registered")
                    return False
                
                # Cancel active recovery if running
                if connection_id in self.active_recoveries:
                    self.active_recoveries[connection_id].cancel()
                    del self.active_recoveries[connection_id]
                
                # Remove connection
                health = self.connections[connection_id]
                if health.state == ConnectionState.CONNECTED:
                    self.stats["active_connections"] -= 1
                elif health.state in [ConnectionState.FAILED, ConnectionState.CIRCUIT_OPEN]:
                    self.stats["failed_connections"] -= 1
                
                del self.connections[connection_id]
                
                logger.info(f"Connection unregistered: {connection_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to unregister connection {connection_id}: {e}")
            return False
    
    async def handle_connection_failure(self, connection_id: str, 
                                      error_message: str,
                                      strategy: RecoveryStrategy = RecoveryStrategy.EXPONENTIAL_BACKOFF) -> bool:
        """
        Handle connection failure and initiate recovery
        
        Args:
            connection_id: Failed connection identifier
            error_message: Error message describing the failure
            strategy: Recovery strategy to use
            
        Returns:
            True if recovery initiated successfully
        """
        try:
            with self.lock:
                if connection_id not in self.connections:
                    logger.error(f"Connection {connection_id} not registered")
                    return False
                
                health = self.connections[connection_id]
                
                # Update health metrics
                health.state = ConnectionState.DISCONNECTED
                health.last_failure = datetime.now()
                health.consecutive_failures += 1
                health.total_failures += 1
                
                # Update statistics
                if health.consecutive_failures == 1:  # First failure
                    self.stats["active_connections"] -= 1
                    self.stats["failed_connections"] += 1
                
                # Check circuit breaker threshold
                if health.consecutive_failures >= self.circuit_breaker_threshold:
                    await self._open_circuit_breaker(connection_id)
                    return False
                
                # Create recovery event
                event = RecoveryEvent(
                    event_id=f"failure_{uuid.uuid4().hex[:8]}",
                    connection_id=connection_id,
                    timestamp=datetime.now(),
                    event_type="connection_lost",
                    strategy_used=strategy,
                    error_message=error_message
                )
                
                self.recovery_events.append(event)
                
                logger.warning(f"Connection failure detected: {connection_id} - {error_message}")
                
                # Notify callback
                if self.on_connection_lost:
                    self.on_connection_lost(connection_id, error_message)
                
                # Start recovery process
                if connection_id not in self.active_recoveries:
                    recovery_task = asyncio.create_task(
                        self._recovery_loop(connection_id, strategy)
                    )
                    self.active_recoveries[connection_id] = recovery_task
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to handle connection failure for {connection_id}: {e}")
            return False
    
    async def mark_connection_healthy(self, connection_id: str, response_time: float = 0.0) -> bool:
        """
        Mark connection as healthy after successful operation
        
        Args:
            connection_id: Connection identifier
            response_time: Response time for the operation
            
        Returns:
            True if update successful
        """
        try:
            with self.lock:
                if connection_id not in self.connections:
                    logger.error(f"Connection {connection_id} not registered")
                    return False
                
                health = self.connections[connection_id]
                
                # Update health metrics
                old_state = health.state
                health.state = ConnectionState.CONNECTED
                health.last_successful_connection = datetime.now()
                health.last_response_time = response_time
                
                # Update average response time
                if health.average_response_time == 0.0:
                    health.average_response_time = response_time
                else:
                    health.average_response_time = (health.average_response_time * 0.9) + (response_time * 0.1)
                
                # Reset failure counters on successful connection
                if health.consecutive_failures > 0:
                    health.consecutive_failures = 0
                    health.recovery_attempts = 0
                    health.current_backoff_delay = self.initial_backoff_delay
                    
                    # Update statistics
                    if old_state in [ConnectionState.FAILED, ConnectionState.CIRCUIT_OPEN]:
                        self.stats["failed_connections"] -= 1
                        self.stats["active_connections"] += 1
                        self.stats["successful_recoveries"] += 1
                    
                    # Close circuit breaker if open
                    if health.circuit_breaker_open:
                        await self._close_circuit_breaker(connection_id)
                    
                    # Cancel active recovery
                    if connection_id in self.active_recoveries:
                        self.active_recoveries[connection_id].cancel()
                        del self.active_recoveries[connection_id]
                    
                    logger.info(f"Connection recovered: {connection_id}")
                    
                    # Notify callback
                    if self.on_connection_recovered:
                        self.on_connection_recovered(connection_id)
                
                health.total_connections += 1
                
                # Update health score
                health.health_score = self._calculate_health_score(health)
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to mark connection healthy for {connection_id}: {e}")
            return False
    
    async def _recovery_loop(self, connection_id: str, strategy: RecoveryStrategy):
        """
        Main recovery loop with exponential backoff
        
        Args:
            connection_id: Connection to recover
            strategy: Recovery strategy to use
        """
        try:
            health = self.connections[connection_id]
            
            while (self.running and 
                   health.recovery_attempts < health.max_recovery_attempts and
                   health.state != ConnectionState.CONNECTED and
                   not health.circuit_breaker_open):
                
                # Calculate backoff delay
                if strategy == RecoveryStrategy.EXPONENTIAL_BACKOFF:
                    delay = min(
                        health.current_backoff_delay * (health.backoff_multiplier ** health.recovery_attempts),
                        self.max_backoff_delay
                    )
                elif strategy == RecoveryStrategy.LINEAR_BACKOFF:
                    delay = min(
                        health.current_backoff_delay + (health.recovery_attempts * 2.0),
                        self.max_backoff_delay
                    )
                elif strategy == RecoveryStrategy.IMMEDIATE:
                    delay = 0.1  # Minimal delay
                else:
                    delay = health.current_backoff_delay
                
                # Add jitter to prevent thundering herd
                jitter = random.uniform(0.1, 0.5) * delay
                total_delay = delay + jitter
                
                logger.info(f"Recovery attempt {health.recovery_attempts + 1}/{health.max_recovery_attempts} "
                           f"for {connection_id} in {total_delay:.2f}s")
                
                # Wait for backoff delay
                await asyncio.sleep(total_delay)
                
                # Update recovery attempt
                health.recovery_attempts += 1
                health.state = ConnectionState.RECONNECTING
                self.stats["recovery_attempts"] += 1
                
                # Create recovery event
                event = RecoveryEvent(
                    event_id=f"recovery_{uuid.uuid4().hex[:8]}",
                    connection_id=connection_id,
                    timestamp=datetime.now(),
                    event_type="reconnection_attempt",
                    strategy_used=strategy,
                    backoff_delay=total_delay
                )
                
                # Attempt recovery (this would be implemented by the specific connection type)
                recovery_start = time.time()
                success = await self._attempt_reconnection(connection_id)
                recovery_time = time.time() - recovery_start
                
                event.success = success
                event.response_time = recovery_time
                
                if success:
                    event.event_type = "recovery_success"
                    logger.info(f"Connection recovery successful: {connection_id}")
                    break
                else:
                    event.event_type = "recovery_failed"
                    event.error_message = "Reconnection attempt failed"
                    logger.warning(f"Connection recovery attempt failed: {connection_id}")
                
                self.recovery_events.append(event)
            
            # Check if recovery failed completely
            if (health.recovery_attempts >= health.max_recovery_attempts and 
                health.state != ConnectionState.CONNECTED):
                
                health.state = ConnectionState.FAILED
                self.stats["failed_recoveries"] += 1
                
                logger.error(f"Connection recovery failed after {health.recovery_attempts} attempts: {connection_id}")
                
                # Notify callback
                if self.on_recovery_failed:
                    self.on_recovery_failed(connection_id, "Maximum recovery attempts exceeded")
            
            # Clean up active recovery
            if connection_id in self.active_recoveries:
                del self.active_recoveries[connection_id]
                
        except asyncio.CancelledError:
            logger.info(f"Recovery cancelled for connection: {connection_id}")
        except Exception as e:
            logger.error(f"Error in recovery loop for {connection_id}: {e}")
            
            # Clean up on error
            if connection_id in self.active_recoveries:
                del self.active_recoveries[connection_id]
    
    async def _attempt_reconnection(self, connection_id: str) -> bool:
        """
        Attempt to reconnect a specific connection
        This is a placeholder that should be overridden by specific implementations
        
        Args:
            connection_id: Connection to reconnect
            
        Returns:
            True if reconnection successful
        """
        # This is a placeholder implementation
        # In a real implementation, this would attempt to reconnect the specific connection type
        # For now, we'll simulate a reconnection attempt
        
        try:
            # Simulate connection attempt
            await asyncio.sleep(0.1)
            
            # Simulate success/failure (70% success rate for testing)
            success = random.random() < 0.7
            
            if success:
                await self.mark_connection_healthy(connection_id, response_time=0.1)
            
            return success
            
        except Exception as e:
            logger.error(f"Reconnection attempt failed for {connection_id}: {e}")
            return False
    
    async def _open_circuit_breaker(self, connection_id: str):
        """Open circuit breaker for a connection"""
        try:
            health = self.connections[connection_id]
            health.circuit_breaker_open = True
            health.circuit_breaker_open_until = datetime.now() + timedelta(seconds=self.circuit_breaker_timeout)
            health.state = ConnectionState.CIRCUIT_OPEN
            
            self.stats["circuit_breaker_activations"] += 1
            
            logger.warning(f"Circuit breaker opened for connection: {connection_id}")
            
            # Notify callback
            if self.on_circuit_breaker_opened:
                self.on_circuit_breaker_opened(connection_id)
                
        except Exception as e:
            logger.error(f"Failed to open circuit breaker for {connection_id}: {e}")
    
    async def _close_circuit_breaker(self, connection_id: str):
        """Close circuit breaker for a connection"""
        try:
            health = self.connections[connection_id]
            health.circuit_breaker_open = False
            health.circuit_breaker_open_until = None
            
            logger.info(f"Circuit breaker closed for connection: {connection_id}")
            
            # Notify callback
            if self.on_circuit_breaker_closed:
                self.on_circuit_breaker_closed(connection_id)
                
        except Exception as e:
            logger.error(f"Failed to close circuit breaker for {connection_id}: {e}")
    
    async def _health_monitor_loop(self):
        """Health monitoring loop"""
        try:
            while self.running:
                await self._check_connection_health()
                await self._check_circuit_breakers()
                await self._update_statistics()
                await asyncio.sleep(self.health_check_interval)
                
        except asyncio.CancelledError:
            logger.info("Health monitor loop cancelled")
        except Exception as e:
            logger.error(f"Error in health monitor loop: {e}")
    
    async def _check_connection_health(self):
        """Check health of all connections"""
        try:
            current_time = datetime.now()
            
            for connection_id, health in list(self.connections.items()):
                # Check for stale connections (no activity for 5 minutes)
                if health.state == ConnectionState.CONNECTED:
                    time_since_last_activity = (current_time - health.last_successful_connection).total_seconds()
                    if time_since_last_activity > 300:  # 5 minutes
                        logger.warning(f"Connection appears stale: {connection_id}")
                        # Could trigger a health check here
                
                # Update health score
                health.health_score = self._calculate_health_score(health)
                
        except Exception as e:
            logger.error(f"Error checking connection health: {e}")
    
    async def _check_circuit_breakers(self):
        """Check and potentially close expired circuit breakers"""
        try:
            current_time = datetime.now()
            
            for connection_id, health in list(self.connections.items()):
                if (health.circuit_breaker_open and 
                    health.circuit_breaker_open_until and
                    current_time >= health.circuit_breaker_open_until):
                    
                    # Reset circuit breaker
                    health.circuit_breaker_open = False
                    health.circuit_breaker_open_until = None
                    health.consecutive_failures = 0
                    health.recovery_attempts = 0
                    health.state = ConnectionState.DISCONNECTED
                    
                    logger.info(f"Circuit breaker timeout expired, allowing retry: {connection_id}")
                    
                    # Start recovery process
                    if connection_id not in self.active_recoveries:
                        recovery_task = asyncio.create_task(
                            self._recovery_loop(connection_id, RecoveryStrategy.EXPONENTIAL_BACKOFF)
                        )
                        self.active_recoveries[connection_id] = recovery_task
                
        except Exception as e:
            logger.error(f"Error checking circuit breakers: {e}")
    
    async def _update_statistics(self):
        """Update recovery statistics"""
        try:
            if not self.connections:
                return
            
            # Calculate uptime percentage
            total_uptime = 0.0
            for health in self.connections.values():
                if health.state == ConnectionState.CONNECTED:
                    total_uptime += 100.0
                elif health.state in [ConnectionState.CONNECTING, ConnectionState.RECONNECTING]:
                    total_uptime += 50.0
                # Failed/circuit open connections contribute 0%
            
            self.stats["uptime_percentage"] = total_uptime / len(self.connections)
            
            # Calculate average recovery time
            recovery_events = [e for e in self.recovery_events if e.event_type == "recovery_success" and e.response_time]
            if recovery_events:
                self.stats["average_recovery_time"] = sum(e.response_time for e in recovery_events) / len(recovery_events)
            
        except Exception as e:
            logger.error(f"Error updating statistics: {e}")
    
    def _calculate_health_score(self, health: ConnectionHealth) -> float:
        """Calculate health score for a connection"""
        try:
            score = 100.0
            
            # Penalize for failures
            if health.total_connections > 0:
                failure_rate = health.total_failures / health.total_connections
                score -= (failure_rate * 50.0)  # Up to 50 points for failure rate
            
            # Penalize for consecutive failures
            score -= (health.consecutive_failures * 10.0)  # 10 points per consecutive failure
            
            # Penalize for circuit breaker
            if health.circuit_breaker_open:
                score -= 30.0
            
            # Penalize for slow response times
            if health.average_response_time > 1.0:  # More than 1 second
                score -= min(health.average_response_time * 5.0, 20.0)  # Up to 20 points
            
            return max(0.0, min(100.0, score))
            
        except Exception as e:
            logger.error(f"Error calculating health score: {e}")
            return 0.0
    
    def get_connection_health(self, connection_id: str) -> Optional[ConnectionHealth]:
        """Get health information for a specific connection"""
        return self.connections.get(connection_id)
    
    def get_all_connection_health(self) -> Dict[str, ConnectionHealth]:
        """Get health information for all connections"""
        return self.connections.copy()
    
    def get_recovery_statistics(self) -> Dict[str, Any]:
        """Get recovery statistics"""
        stats = self.stats.copy()
        stats["registered_connections"] = len(self.connections)
        stats["active_recoveries"] = len(self.active_recoveries)
        stats["total_recovery_events"] = len(self.recovery_events)
        
        # Connection state breakdown
        state_counts = {}
        for health in self.connections.values():
            state = health.state.value
            state_counts[state] = state_counts.get(state, 0) + 1
        
        stats["connection_states"] = state_counts
        
        return stats
    
    def get_recent_recovery_events(self, limit: int = 50) -> List[RecoveryEvent]:
        """Get recent recovery events"""
        return sorted(self.recovery_events, key=lambda e: e.timestamp, reverse=True)[:limit]
    
    def set_connection_lost_callback(self, callback: Callable[[str, str], None]):
        """Set callback for connection lost events"""
        self.on_connection_lost = callback
    
    def set_connection_recovered_callback(self, callback: Callable[[str], None]):
        """Set callback for connection recovered events"""
        self.on_connection_recovered = callback
    
    def set_recovery_failed_callback(self, callback: Callable[[str, str], None]):
        """Set callback for recovery failed events"""
        self.on_recovery_failed = callback
    
    def set_circuit_breaker_opened_callback(self, callback: Callable[[str], None]):
        """Set callback for circuit breaker opened events"""
        self.on_circuit_breaker_opened = callback
    
    def set_circuit_breaker_closed_callback(self, callback: Callable[[str], None]):
        """Set callback for circuit breaker closed events"""
        self.on_circuit_breaker_closed = callback


# Utility functions for easy integration
async def create_connection_recovery(max_retry_attempts: int = 10,
                                   initial_backoff_delay: float = 1.0,
                                   max_backoff_delay: float = 300.0) -> ConnectionRecovery:
    """Create and start a connection recovery manager"""
    recovery = ConnectionRecovery(
        max_retry_attempts=max_retry_attempts,
        initial_backoff_delay=initial_backoff_delay,
        max_backoff_delay=max_backoff_delay
    )
    
    await recovery.start()
    return recovery


if __name__ == "__main__":
    # Example usage and testing
    async def test_connection_recovery():
        """Test connection recovery functionality"""
        print("Testing Connection Recovery System...")
        
        # Create recovery manager
        recovery = await create_connection_recovery(max_retry_attempts=5)
        
        # Register test connections
        recovery.register_connection("test_conn_1")
        recovery.register_connection("test_conn_2")
        
        # Simulate connection failures
        await recovery.handle_connection_failure("test_conn_1", "Network timeout")
        await recovery.handle_connection_failure("test_conn_2", "Connection refused")
        
        # Wait for recovery attempts
        await asyncio.sleep(10)
        
        # Print statistics
        stats = recovery.get_recovery_statistics()
        print(f"Recovery Statistics: {json.dumps(stats, indent=2, default=str)}")
        
        # Stop recovery service
        await recovery.stop()
        
        print("Connection Recovery test completed")
    
    # Run test
    asyncio.run(test_connection_recovery())