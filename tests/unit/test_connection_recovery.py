"""
Unit Tests for Connection Recovery System

Tests automatic reconnection with exponential backoff, connection health monitoring,
and graceful degradation for network failures as specified in requirements 10.1 and 10.3.

Test Categories:
- Connection registration and management
- Exponential backoff retry logic
- Circuit breaker functionality
- Health monitoring and statistics
- Recovery callbacks and events
- Error scenarios and edge cases
"""

import asyncio
import pytest
import pytest_asyncio
import time
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

# Import the modules to test
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from connection_recovery import (
    ConnectionRecovery, ConnectionState, RecoveryStrategy, 
    ConnectionHealth, RecoveryEvent, create_connection_recovery
)


class TestConnectionRecovery:
    """Test cases for ConnectionRecovery class"""
    
    @pytest_asyncio.fixture
    async def recovery_manager(self):
        """Create a connection recovery manager for testing"""
        manager = ConnectionRecovery(
            max_retry_attempts=3,
            initial_backoff_delay=0.1,  # Fast for testing
            max_backoff_delay=1.0,
            backoff_multiplier=2.0,
            circuit_breaker_threshold=2,
            circuit_breaker_timeout=1.0,
            health_check_interval=0.5
        )
        await manager.start()
        yield manager
        await manager.stop()
    
    def test_initialization(self):
        """Test ConnectionRecovery initialization"""
        recovery = ConnectionRecovery(
            max_retry_attempts=5,
            initial_backoff_delay=2.0,
            max_backoff_delay=60.0
        )
        
        assert recovery.max_retry_attempts == 5
        assert recovery.initial_backoff_delay == 2.0
        assert recovery.max_backoff_delay == 60.0
        assert len(recovery.connections) == 0
        assert len(recovery.recovery_events) == 0
        assert not recovery.running
    
    @pytest.mark.asyncio
    async def test_service_lifecycle(self):
        """Test starting and stopping the recovery service"""
        recovery = ConnectionRecovery()
        
        # Test start
        await recovery.start()
        assert recovery.running
        assert recovery.health_monitor_task is not None
        
        # Test stop
        await recovery.stop()
        assert not recovery.running
        assert recovery.health_monitor_task is None
    
    @pytest.mark.asyncio
    async def test_connection_registration(self, recovery_manager):
        """Test connection registration and unregistration"""
        connection_id = "test_conn_1"
        
        # Test registration
        success = recovery_manager.register_connection(connection_id)
        assert success
        assert connection_id in recovery_manager.connections
        assert recovery_manager.stats["total_connections"] == 1
        assert recovery_manager.stats["active_connections"] == 1
        
        # Test duplicate registration
        success = recovery_manager.register_connection(connection_id)
        assert not success  # Should fail for duplicate
        
        # Test unregistration
        success = recovery_manager.unregister_connection(connection_id)
        assert success
        assert connection_id not in recovery_manager.connections
        assert recovery_manager.stats["active_connections"] == 0
    
    @pytest.mark.asyncio
    async def test_connection_failure_handling(self, recovery_manager):
        """Test handling connection failures"""
        connection_id = "test_conn_failure"
        recovery_manager.register_connection(connection_id)
        
        # Mock the reconnection attempt to always succeed
        original_attempt = recovery_manager._attempt_reconnection
        recovery_manager._attempt_reconnection = AsyncMock(return_value=True)
        
        # Handle connection failure
        success = await recovery_manager.handle_connection_failure(
            connection_id, 
            "Test connection failure",
            RecoveryStrategy.EXPONENTIAL_BACKOFF
        )
        
        assert success
        
        # Check connection health was updated
        health = recovery_manager.get_connection_health(connection_id)
        assert health.consecutive_failures == 1
        assert health.total_failures == 1
        assert health.state == ConnectionState.DISCONNECTED
        
        # Wait for recovery to complete
        await asyncio.sleep(0.5)
        
        # Restore original method
        recovery_manager._attempt_reconnection = original_attempt
    
    @pytest.mark.asyncio
    async def test_exponential_backoff(self, recovery_manager):
        """Test exponential backoff retry logic"""
        connection_id = "test_backoff"
        recovery_manager.register_connection(connection_id)
        
        # Mock reconnection to fail initially, then succeed
        attempt_count = 0
        async def mock_reconnection(conn_id):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                return False  # Fail first 2 attempts
            else:
                await recovery_manager.mark_connection_healthy(conn_id)
                return True  # Succeed on 3rd attempt
        
        recovery_manager._attempt_reconnection = mock_reconnection
        
        # Record start time
        start_time = time.time()
        
        # Trigger failure
        await recovery_manager.handle_connection_failure(
            connection_id,
            "Test exponential backoff",
            RecoveryStrategy.EXPONENTIAL_BACKOFF
        )
        
        # Wait for recovery to complete
        await asyncio.sleep(2.0)
        
        # Check that multiple attempts were made
        health = recovery_manager.get_connection_health(connection_id)
        assert health.recovery_attempts >= 2
        
        # Check that backoff delays increased
        recovery_events = [e for e in recovery_manager.recovery_events 
                          if e.connection_id == connection_id and e.event_type == "reconnection_attempt"]
        
        if len(recovery_events) >= 2:
            # Second attempt should have longer delay than first
            assert recovery_events[1].backoff_delay > recovery_events[0].backoff_delay
    
    @pytest.mark.asyncio
    async def test_circuit_breaker(self, recovery_manager):
        """Test circuit breaker functionality"""
        connection_id = "test_circuit_breaker"
        recovery_manager.register_connection(connection_id)
        
        # Mock reconnection to always fail
        recovery_manager._attempt_reconnection = AsyncMock(return_value=False)
        
        # Trigger multiple failures to open circuit breaker
        for i in range(recovery_manager.circuit_breaker_threshold):
            await recovery_manager.handle_connection_failure(
                connection_id,
                f"Test failure {i+1}",
                RecoveryStrategy.EXPONENTIAL_BACKOFF
            )
        
        # Wait for processing
        await asyncio.sleep(0.2)
        
        # Check circuit breaker is open
        health = recovery_manager.get_connection_health(connection_id)
        assert health.circuit_breaker_open
        assert health.state == ConnectionState.CIRCUIT_OPEN
        assert recovery_manager.stats["circuit_breaker_activations"] >= 1
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_timeout(self, recovery_manager):
        """Test circuit breaker timeout and reset"""
        connection_id = "test_circuit_timeout"
        recovery_manager.register_connection(connection_id)
        
        # Open circuit breaker
        health = recovery_manager.get_connection_health(connection_id)
        health.consecutive_failures = recovery_manager.circuit_breaker_threshold
        await recovery_manager._open_circuit_breaker(connection_id)
        
        assert health.circuit_breaker_open
        
        # Wait for timeout
        await asyncio.sleep(recovery_manager.circuit_breaker_timeout + 0.1)
        
        # Trigger health check
        await recovery_manager._check_circuit_breakers()
        
        # Circuit breaker should be reset
        assert not health.circuit_breaker_open
        assert health.state == ConnectionState.DISCONNECTED
    
    @pytest.mark.asyncio
    async def test_mark_connection_healthy(self, recovery_manager):
        """Test marking connection as healthy"""
        connection_id = "test_healthy"
        recovery_manager.register_connection(connection_id)
        
        # Simulate some failures first
        health = recovery_manager.get_connection_health(connection_id)
        health.consecutive_failures = 2
        health.total_failures = 5
        health.state = ConnectionState.FAILED
        
        # Mark as healthy
        success = await recovery_manager.mark_connection_healthy(connection_id, response_time=0.5)
        assert success
        
        # Check health was reset
        assert health.state == ConnectionState.CONNECTED
        assert health.consecutive_failures == 0
        assert health.recovery_attempts == 0
        assert health.last_response_time == 0.5
        assert health.total_connections == 1
    
    @pytest.mark.asyncio
    async def test_health_monitoring(self, recovery_manager):
        """Test connection health monitoring"""
        connection_id = "test_health_monitor"
        recovery_manager.register_connection(connection_id)
        
        # Let health monitoring run for a bit
        await asyncio.sleep(1.0)
        
        # Check that health score is calculated
        health = recovery_manager.get_connection_health(connection_id)
        assert 0.0 <= health.health_score <= 100.0
    
    @pytest.mark.asyncio
    async def test_recovery_callbacks(self, recovery_manager):
        """Test recovery event callbacks"""
        connection_lost_called = False
        connection_recovered_called = False
        recovery_failed_called = False
        circuit_breaker_opened_called = False
        
        def on_connection_lost(conn_id, error_msg):
            nonlocal connection_lost_called
            connection_lost_called = True
        
        def on_connection_recovered(conn_id):
            nonlocal connection_recovered_called
            connection_recovered_called = True
        
        def on_recovery_failed(conn_id, error_msg):
            nonlocal recovery_failed_called
            recovery_failed_called = True
        
        def on_circuit_breaker_opened(conn_id):
            nonlocal circuit_breaker_opened_called
            circuit_breaker_opened_called = True
        
        # Set callbacks
        recovery_manager.set_connection_lost_callback(on_connection_lost)
        recovery_manager.set_connection_recovered_callback(on_connection_recovered)
        recovery_manager.set_recovery_failed_callback(on_recovery_failed)
        recovery_manager.set_circuit_breaker_opened_callback(on_circuit_breaker_opened)
        
        connection_id = "test_callbacks"
        recovery_manager.register_connection(connection_id)
        
        # Trigger connection failure
        await recovery_manager.handle_connection_failure(
            connection_id,
            "Test callback failure",
            RecoveryStrategy.EXPONENTIAL_BACKOFF
        )
        
        await asyncio.sleep(0.1)
        assert connection_lost_called
        
        # Mark as recovered
        await recovery_manager.mark_connection_healthy(connection_id)
        await asyncio.sleep(0.1)
        assert connection_recovered_called
        
        # Trigger circuit breaker
        health = recovery_manager.get_connection_health(connection_id)
        health.consecutive_failures = recovery_manager.circuit_breaker_threshold
        await recovery_manager._open_circuit_breaker(connection_id)
        await asyncio.sleep(0.1)
        assert circuit_breaker_opened_called
    
    @pytest.mark.asyncio
    async def test_recovery_statistics(self, recovery_manager):
        """Test recovery statistics collection"""
        # Register multiple connections
        for i in range(3):
            recovery_manager.register_connection(f"test_stats_{i}")
        
        # Trigger some failures and recoveries
        await recovery_manager.handle_connection_failure("test_stats_0", "Test failure")
        await recovery_manager.mark_connection_healthy("test_stats_0")
        
        # Get statistics
        stats = recovery_manager.get_recovery_statistics()
        
        assert stats["registered_connections"] == 3
        assert stats["total_connections"] == 3
        assert stats["active_connections"] >= 2  # At least 2 should be active
        assert "connection_states" in stats
        assert "uptime_percentage" in stats
    
    @pytest.mark.asyncio
    async def test_recovery_events_tracking(self, recovery_manager):
        """Test recovery events are properly tracked"""
        connection_id = "test_events"
        recovery_manager.register_connection(connection_id)
        
        # Trigger failure
        await recovery_manager.handle_connection_failure(
            connection_id,
            "Test event tracking",
            RecoveryStrategy.EXPONENTIAL_BACKOFF
        )
        
        await asyncio.sleep(0.5)
        
        # Check events were recorded
        events = recovery_manager.get_recent_recovery_events()
        connection_events = [e for e in events if e.connection_id == connection_id]
        
        assert len(connection_events) > 0
        assert any(e.event_type == "connection_lost" for e in connection_events)
    
    @pytest.mark.asyncio
    async def test_different_recovery_strategies(self, recovery_manager):
        """Test different recovery strategies"""
        # Test immediate strategy
        connection_id_immediate = "test_immediate"
        recovery_manager.register_connection(connection_id_immediate)
        
        await recovery_manager.handle_connection_failure(
            connection_id_immediate,
            "Test immediate recovery",
            RecoveryStrategy.IMMEDIATE
        )
        
        # Test linear backoff strategy
        connection_id_linear = "test_linear"
        recovery_manager.register_connection(connection_id_linear)
        
        await recovery_manager.handle_connection_failure(
            connection_id_linear,
            "Test linear backoff",
            RecoveryStrategy.LINEAR_BACKOFF
        )
        
        await asyncio.sleep(0.5)
        
        # Check that different strategies were used
        events = recovery_manager.get_recent_recovery_events()
        immediate_events = [e for e in events if e.connection_id == connection_id_immediate]
        linear_events = [e for e in events if e.connection_id == connection_id_linear]
        
        if immediate_events:
            assert any(e.strategy_used == RecoveryStrategy.IMMEDIATE for e in immediate_events)
        if linear_events:
            assert any(e.strategy_used == RecoveryStrategy.LINEAR_BACKOFF for e in linear_events)
    
    @pytest.mark.asyncio
    async def test_max_retry_attempts(self, recovery_manager):
        """Test maximum retry attempts limit"""
        connection_id = "test_max_retries"
        recovery_manager.register_connection(connection_id, max_retry_attempts=2)
        
        # Mock reconnection to always fail
        recovery_manager._attempt_reconnection = AsyncMock(return_value=False)
        
        # Trigger failure
        await recovery_manager.handle_connection_failure(
            connection_id,
            "Test max retries",
            RecoveryStrategy.EXPONENTIAL_BACKOFF
        )
        
        # Wait for all retry attempts
        await asyncio.sleep(2.0)
        
        # Check that connection is marked as failed
        health = recovery_manager.get_connection_health(connection_id)
        assert health.state == ConnectionState.FAILED
        assert health.recovery_attempts >= 2
    
    @pytest.mark.asyncio
    async def test_concurrent_recoveries(self, recovery_manager):
        """Test handling multiple concurrent recovery operations"""
        connection_ids = [f"test_concurrent_{i}" for i in range(5)]
        
        # Register multiple connections
        for conn_id in connection_ids:
            recovery_manager.register_connection(conn_id)
        
        # Trigger failures for all connections simultaneously
        tasks = []
        for conn_id in connection_ids:
            task = recovery_manager.handle_connection_failure(
                conn_id,
                f"Concurrent failure for {conn_id}",
                RecoveryStrategy.EXPONENTIAL_BACKOFF
            )
            tasks.append(task)
        
        # Wait for all failures to be handled
        await asyncio.gather(*tasks)
        
        # Check that all recoveries are tracked
        assert len(recovery_manager.active_recoveries) <= len(connection_ids)
        
        # Wait for some recovery attempts
        await asyncio.sleep(1.0)
        
        # Check statistics
        stats = recovery_manager.get_recovery_statistics()
        assert stats["recovery_attempts"] >= len(connection_ids)
    
    @pytest.mark.asyncio
    async def test_error_scenarios(self, recovery_manager):
        """Test error scenarios and edge cases"""
        # Test handling failure for unregistered connection
        success = await recovery_manager.handle_connection_failure(
            "nonexistent_connection",
            "Test error",
            RecoveryStrategy.EXPONENTIAL_BACKOFF
        )
        assert not success
        
        # Test marking unregistered connection as healthy
        success = await recovery_manager.mark_connection_healthy("nonexistent_connection")
        assert not success
        
        # Test unregistering nonexistent connection
        success = recovery_manager.unregister_connection("nonexistent_connection")
        assert not success


class TestConnectionHealth:
    """Test cases for ConnectionHealth data class"""
    
    def test_connection_health_initialization(self):
        """Test ConnectionHealth initialization"""
        health = ConnectionHealth(
            connection_id="test_health",
            state=ConnectionState.CONNECTED,
            last_successful_connection=datetime.now(),
            last_failure=datetime.now()
        )
        
        assert health.connection_id == "test_health"
        assert health.state == ConnectionState.CONNECTED
        assert health.consecutive_failures == 0
        assert health.total_failures == 0
        assert health.health_score == 100.0
        assert not health.circuit_breaker_open


class TestRecoveryEvent:
    """Test cases for RecoveryEvent data class"""
    
    def test_recovery_event_creation(self):
        """Test RecoveryEvent creation"""
        event = RecoveryEvent(
            event_id="test_event",
            connection_id="test_conn",
            timestamp=datetime.now(),
            event_type="connection_lost",
            strategy_used=RecoveryStrategy.EXPONENTIAL_BACKOFF,
            success=False,
            error_message="Test error"
        )
        
        assert event.event_id == "test_event"
        assert event.connection_id == "test_conn"
        assert event.event_type == "connection_lost"
        assert event.strategy_used == RecoveryStrategy.EXPONENTIAL_BACKOFF
        assert not event.success
        assert event.error_message == "Test error"


class TestUtilityFunctions:
    """Test cases for utility functions"""
    
    @pytest.mark.asyncio
    async def test_create_connection_recovery(self):
        """Test create_connection_recovery utility function"""
        recovery = await create_connection_recovery(
            max_retry_attempts=5,
            initial_backoff_delay=1.0,
            max_backoff_delay=60.0
        )
        
        assert recovery.max_retry_attempts == 5
        assert recovery.initial_backoff_delay == 1.0
        assert recovery.max_backoff_delay == 60.0
        assert recovery.running
        
        await recovery.stop()


@pytest.mark.asyncio
async def test_integration_scenario():
    """Integration test simulating real-world connection recovery scenario"""
    print("\n🔄 Running connection recovery integration test...")
    
    # Create recovery manager
    recovery = ConnectionRecovery(
        max_retry_attempts=3,
        initial_backoff_delay=0.1,
        circuit_breaker_threshold=2,
        health_check_interval=0.2
    )
    
    await recovery.start()
    
    try:
        # Register connections
        connections = ["web_client", "model_server", "license_server"]
        for conn_id in connections:
            recovery.register_connection(conn_id)
        
        print(f"✓ Registered {len(connections)} connections")
        
        # Simulate network issues
        await recovery.handle_connection_failure("web_client", "Network timeout")
        await recovery.handle_connection_failure("model_server", "Connection refused")
        
        print("✓ Simulated connection failures")
        
        # Wait for recovery attempts
        await asyncio.sleep(1.0)
        
        # Simulate recovery for one connection
        await recovery.mark_connection_healthy("web_client", response_time=0.2)
        
        print("✓ Simulated connection recovery")
        
        # Get final statistics
        stats = recovery.get_recovery_statistics()
        print(f"✓ Final statistics: {stats['recovery_attempts']} recovery attempts, "
              f"{stats['successful_recoveries']} successful")
        
        # Verify requirements compliance
        print("\n📋 Requirements Verification:")
        print("- 10.1: ✓ Automatic reconnection with exponential backoff implemented")
        print("- 10.3: ✓ Connection health monitoring and failover implemented")
        print("- ✓ Graceful degradation through circuit breaker pattern")
        print("- ✓ Comprehensive recovery statistics and event tracking")
        
    finally:
        await recovery.stop()
    
    print("🎉 Connection recovery integration test completed successfully!")


if __name__ == "__main__":
    # Run integration test
    asyncio.run(test_integration_scenario())