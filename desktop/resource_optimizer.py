"""
Resource Optimizer for Distributed LLM Platform
Implements workload pattern analysis, dynamic load balancing, and license-aware optimization
"""

import json
import logging
import time
import statistics
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from collections import defaultdict, deque
import threading

from security.license_validator import LicenseInfo, SubscriptionTier, LicenseStatus
from monitoring_system import MonitoringSystem, ResourceUsage, PerformanceMetric

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ResourceOptimizer")

# Create logs directory if it doesn't exist
Path('logs').mkdir(exist_ok=True)
file_handler = logging.FileHandler('logs/resource_optimizer.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)


class OptimizationStrategy(Enum):
    """Resource optimization strategies"""
    BALANCED = "balanced"
    PERFORMANCE = "performance"
    COST_EFFICIENT = "cost_efficient"
    LICENSE_AWARE = "license_aware"


class WorkloadPattern(Enum):
    """Workload pattern types"""
    STEADY = "steady"
    BURSTY = "bursty"
    PERIODIC = "periodic"
    RANDOM = "random"
    DECLINING = "declining"
    GROWING = "growing"


@dataclass
class WorkerNode:
    """Worker node information"""
    node_id: str
    capacity: int
    current_load: float
    available_memory_mb: int
    cpu_cores: int
    gpu_available: bool = False
    models_loaded: List[str] = field(default_factory=list)
    last_heartbeat: datetime = field(default_factory=datetime.now)
    license_tier: SubscriptionTier = SubscriptionTier.FREE
    performance_score: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkloadAnalysis:
    """Workload pattern analysis results"""
    pattern_type: WorkloadPattern
    confidence: float
    peak_hours: List[int]
    average_load: float
    peak_load: float
    load_variance: float
    trend_direction: str  # "increasing", "decreasing", "stable"
    recommendations: List[str]
    analysis_period: timedelta
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class OptimizationRecommendation:
    """Resource optimization recommendation"""
    recommendation_id: str
    strategy: OptimizationStrategy
    action: str
    target_resources: List[str]
    expected_improvement: float
    implementation_cost: float
    priority: int  # 1-10, higher is more important
    license_requirements: List[str]
    description: str
    estimated_savings: Dict[str, float]
    timestamp: datetime = field(default_factory=datetime.now)


class ResourceOptimizer:
    """
    Resource optimization system for distributed LLM platform
    """
    
    def __init__(self, 
                 license_info: Optional[LicenseInfo] = None,
                 monitoring_system: Optional[MonitoringSystem] = None,
                 optimization_interval: int = 300):  # 5 minutes
        """
        Initialize resource optimizer
        
        Args:
            license_info: License information for optimization decisions
            monitoring_system: Monitoring system for data collection
            optimization_interval: Optimization check interval in seconds
        """
        self.license_info = license_info
        self.monitoring_system = monitoring_system
        self.optimization_interval = optimization_interval
        
        # Worker nodes registry
        self.worker_nodes: Dict[str, WorkerNode] = {}
        
        # Workload history for pattern analysis
        self.workload_history = deque(maxlen=1000)  # Keep last 1000 data points
        self.resource_history = deque(maxlen=1000)
        
        # Optimization state
        self.optimization_active = False
        self.optimization_thread = None
        self.last_optimization = datetime.now()
        
        # Analysis results
        self.current_workload_analysis: Optional[WorkloadAnalysis] = None
        self.optimization_recommendations: List[OptimizationRecommendation] = []
        
        # Statistics
        self.optimization_stats = {
            "total_optimizations": 0,
            "successful_optimizations": 0,
            "recommendations_generated": 0,
            "load_balancing_actions": 0,
            "resource_savings": 0.0
        }
        
        logger.info("Resource optimizer initialized")
    
    def analyze_workload_patterns(self, 
                                 analysis_period: timedelta = timedelta(hours=24)) -> WorkloadAnalysis:
        """
        Analyze workload patterns function as specified in requirements
        
        Args:
            analysis_period: Time period for analysis
            
        Returns:
            WorkloadAnalysis object with pattern analysis results
        """
        try:
            logger.info(f"Analyzing workload patterns for period: {analysis_period}")
            
            # Collect workload data from monitoring system
            if self.monitoring_system:
                self._collect_workload_data()
            
            # Analyze patterns if we have sufficient data
            if len(self.workload_history) < 10:
                logger.warning("Insufficient data for workload analysis")
                return WorkloadAnalysis(
                    pattern_type=WorkloadPattern.RANDOM,
                    confidence=0.0,
                    peak_hours=[],
                    average_load=0.0,
                    peak_load=0.0,
                    load_variance=0.0,
                    trend_direction="unknown",
                    recommendations=["Collect more data for accurate analysis"],
                    analysis_period=analysis_period
                )
            
            # Extract load values and timestamps
            loads = [entry['load'] for entry in self.workload_history]
            timestamps = [entry['timestamp'] for entry in self.workload_history]
            
            # Calculate basic statistics
            average_load = statistics.mean(loads)
            peak_load = max(loads)
            load_variance = statistics.variance(loads) if len(loads) > 1 else 0.0
            
            # Detect pattern type
            pattern_type, confidence = self._detect_pattern_type(loads, timestamps)
            
            # Find peak hours
            peak_hours = self._find_peak_hours(loads, timestamps)
            
            # Determine trend direction
            trend_direction = self._analyze_trend(loads)
            
            # Generate recommendations
            recommendations = self._generate_workload_recommendations(
                pattern_type, average_load, peak_load, load_variance
            )
            
            # Create analysis result
            analysis = WorkloadAnalysis(
                pattern_type=pattern_type,
                confidence=confidence,
                peak_hours=peak_hours,
                average_load=average_load,
                peak_load=peak_load,
                load_variance=load_variance,
                trend_direction=trend_direction,
                recommendations=recommendations,
                analysis_period=analysis_period
            )
            
            self.current_workload_analysis = analysis
            
            logger.info(f"Workload analysis completed: {pattern_type.value} pattern with {confidence:.2f} confidence")
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze workload patterns: {e}")
            return WorkloadAnalysis(
                pattern_type=WorkloadPattern.RANDOM,
                confidence=0.0,
                peak_hours=[],
                average_load=0.0,
                peak_load=0.0,
                load_variance=0.0,
                trend_direction="unknown",
                recommendations=[f"Analysis failed: {str(e)}"],
                analysis_period=analysis_period
            )
    
    def dynamic_load_balancing(self, 
                             strategy: OptimizationStrategy = OptimizationStrategy.LICENSE_AWARE) -> bool:
        """
        Dynamic load balancing function as specified in requirements
        
        Args:
            strategy: Load balancing strategy to use
            
        Returns:
            True if load balancing was successful, False otherwise
        """
        try:
            logger.info(f"Performing dynamic load balancing with strategy: {strategy.value}")
            
            # Get current worker states
            active_workers = self._get_active_workers()
            if len(active_workers) < 2:
                logger.warning("Insufficient workers for load balancing")
                return False
            
            # Calculate load distribution
            load_distribution = self._calculate_load_distribution(active_workers)
            
            # Check if rebalancing is needed
            if not self._needs_rebalancing(load_distribution):
                logger.info("Load is already well balanced")
                return True
            
            # Generate load balancing plan
            balancing_plan = self._generate_balancing_plan(active_workers, strategy)
            
            if not balancing_plan:
                logger.warning("No viable load balancing plan generated")
                return False
            
            # Execute load balancing plan
            success = self._execute_balancing_plan(balancing_plan)
            
            if success:
                self.optimization_stats["load_balancing_actions"] += 1
                logger.info("Dynamic load balancing completed successfully")
            else:
                logger.error("Dynamic load balancing failed")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to perform dynamic load balancing: {e}")
            return False
    
    def generate_optimization_suggestions(self, 
                                        target_tier: Optional[SubscriptionTier] = None) -> List[OptimizationRecommendation]:
        """
        Generate subscription optimization suggestions
        
        Args:
            target_tier: Target subscription tier for optimization
            
        Returns:
            List of optimization recommendations
        """
        try:
            logger.info("Generating optimization suggestions")
            
            recommendations = []
            
            # Analyze current resource usage
            current_usage = self._analyze_current_usage()
            
            # Generate tier-based recommendations
            tier_recommendations = self._generate_tier_recommendations(current_usage, target_tier)
            recommendations.extend(tier_recommendations)
            
            # Generate performance optimization recommendations
            performance_recommendations = self._generate_performance_recommendations(current_usage)
            recommendations.extend(performance_recommendations)
            
            # Generate cost optimization recommendations
            cost_recommendations = self._generate_cost_recommendations(current_usage)
            recommendations.extend(cost_recommendations)
            
            # Sort recommendations by priority
            recommendations.sort(key=lambda r: r.priority, reverse=True)
            
            # Store recommendations
            self.optimization_recommendations = recommendations
            self.optimization_stats["recommendations_generated"] += len(recommendations)
            
            logger.info(f"Generated {len(recommendations)} optimization recommendations")
            return recommendations
            
        except Exception as e:
            logger.error(f"Failed to generate optimization suggestions: {e}")
            return []
    
    def _collect_workload_data(self):
        """Collect workload data from monitoring system"""
        try:
            if not self.monitoring_system:
                return
            
            # Get current resource usage
            current_usage = self.monitoring_system.collect_resource_usage()
            if current_usage:
                workload_entry = {
                    'timestamp': current_usage.timestamp,
                    'load': current_usage.cpu_percent,
                    'memory_usage': current_usage.memory_percent,
                    'active_connections': current_usage.active_connections
                }
                self.workload_history.append(workload_entry)
                self.resource_history.append(current_usage)
            
        except Exception as e:
            logger.error(f"Failed to collect workload data: {e}")
    
    def _detect_pattern_type(self, loads: List[float], timestamps: List[datetime]) -> Tuple[WorkloadPattern, float]:
        """Detect workload pattern type"""
        try:
            if len(loads) < 10:
                return WorkloadPattern.RANDOM, 0.0
            
            # Calculate coefficient of variation
            mean_load = statistics.mean(loads)
            std_load = statistics.stdev(loads) if len(loads) > 1 else 0
            cv = std_load / mean_load if mean_load > 0 else 0
            
            # Analyze trend
            if len(loads) >= 20:
                first_half = loads[:len(loads)//2]
                second_half = loads[len(loads)//2:]
                
                first_avg = statistics.mean(first_half)
                second_avg = statistics.mean(second_half)
                
                growth_rate = (second_avg - first_avg) / first_avg if first_avg > 0 else 0
                
                if growth_rate > 0.2:
                    return WorkloadPattern.GROWING, 0.8
                elif growth_rate < -0.2:
                    return WorkloadPattern.DECLINING, 0.8
            
            # Check for periodicity (simplified)
            if cv < 0.2:
                return WorkloadPattern.STEADY, 0.9
            elif cv > 0.8:
                return WorkloadPattern.BURSTY, 0.7
            else:
                # Check for periodic patterns (simplified)
                return WorkloadPattern.PERIODIC, 0.6
            
        except Exception as e:
            logger.error(f"Error detecting pattern type: {e}")
            return WorkloadPattern.RANDOM, 0.0
    
    def _find_peak_hours(self, loads: List[float], timestamps: List[datetime]) -> List[int]:
        """Find peak usage hours"""
        try:
            if len(loads) != len(timestamps):
                return []
            
            # Group by hour
            hourly_loads = defaultdict(list)
            for load, timestamp in zip(loads, timestamps):
                hour = timestamp.hour
                hourly_loads[hour].append(load)
            
            # Calculate average load per hour
            hourly_averages = {}
            for hour, hour_loads in hourly_loads.items():
                hourly_averages[hour] = statistics.mean(hour_loads)
            
            # Find hours with above-average load
            overall_average = statistics.mean(loads)
            peak_hours = [hour for hour, avg_load in hourly_averages.items() 
                         if avg_load > overall_average * 1.2]
            
            return sorted(peak_hours)
            
        except Exception as e:
            logger.error(f"Error finding peak hours: {e}")
            return []
    
    def _analyze_trend(self, loads: List[float]) -> str:
        """Analyze load trend direction"""
        try:
            if len(loads) < 10:
                return "unknown"
            
            # Simple linear trend analysis
            n = len(loads)
            x = list(range(n))
            
            # Calculate correlation coefficient
            mean_x = statistics.mean(x)
            mean_y = statistics.mean(loads)
            
            numerator = sum((x[i] - mean_x) * (loads[i] - mean_y) for i in range(n))
            denominator_x = sum((x[i] - mean_x) ** 2 for i in range(n))
            denominator_y = sum((loads[i] - mean_y) ** 2 for i in range(n))
            
            if denominator_x == 0 or denominator_y == 0:
                return "stable"
            
            correlation = numerator / (denominator_x * denominator_y) ** 0.5
            
            if correlation > 0.3:
                return "increasing"
            elif correlation < -0.3:
                return "decreasing"
            else:
                return "stable"
                
        except Exception as e:
            logger.error(f"Error analyzing trend: {e}")
            return "unknown"
    
    def _generate_workload_recommendations(self, 
                                         pattern_type: WorkloadPattern,
                                         average_load: float,
                                         peak_load: float,
                                         load_variance: float) -> List[str]:
        """Generate workload-based recommendations"""
        recommendations = []
        
        try:
            if pattern_type == WorkloadPattern.BURSTY:
                recommendations.append("Consider implementing auto-scaling for burst workloads")
                recommendations.append("Add more backup workers for peak demand periods")
            
            elif pattern_type == WorkloadPattern.STEADY:
                recommendations.append("Current steady workload is well-suited for fixed resource allocation")
                if average_load > 80:
                    recommendations.append("Consider adding more workers to reduce sustained high load")
            
            elif pattern_type == WorkloadPattern.PERIODIC:
                recommendations.append("Implement scheduled scaling based on periodic patterns")
                recommendations.append("Pre-warm resources before expected peak periods")
            
            elif pattern_type == WorkloadPattern.GROWING:
                recommendations.append("Plan for capacity expansion due to growing workload trend")
                recommendations.append("Consider upgrading to higher subscription tier")
            
            elif pattern_type == WorkloadPattern.DECLINING:
                recommendations.append("Consider reducing resource allocation due to declining workload")
                recommendations.append("Evaluate potential cost savings from tier downgrade")
            
            # General recommendations based on load levels
            if peak_load > 95:
                recommendations.append("Peak load is very high - add more capacity immediately")
            elif average_load < 20:
                recommendations.append("Average load is low - consider optimizing resource allocation")
            
            if load_variance > 50:
                recommendations.append("High load variance detected - implement dynamic scaling")
            
        except Exception as e:
            logger.error(f"Error generating workload recommendations: {e}")
        
        return recommendations 
    def _get_active_workers(self) -> List[WorkerNode]:
        """Get list of active worker nodes"""
        try:
            active_workers = []
            current_time = datetime.now()
            
            for worker in self.worker_nodes.values():
                # Consider worker active if heartbeat is within last 2 minutes
                if (current_time - worker.last_heartbeat).seconds < 120:
                    active_workers.append(worker)
            
            return active_workers
            
        except Exception as e:
            logger.error(f"Error getting active workers: {e}")
            return []
    
    def _calculate_load_distribution(self, workers: List[WorkerNode]) -> Dict[str, float]:
        """Calculate current load distribution across workers"""
        try:
            distribution = {}
            total_capacity = sum(worker.capacity for worker in workers)
            
            for worker in workers:
                if total_capacity > 0:
                    distribution[worker.node_id] = worker.current_load / worker.capacity
                else:
                    distribution[worker.node_id] = 0.0
            
            return distribution
            
        except Exception as e:
            logger.error(f"Error calculating load distribution: {e}")
            return {}
    
    def _needs_rebalancing(self, load_distribution: Dict[str, float]) -> bool:
        """Check if load rebalancing is needed"""
        try:
            if not load_distribution:
                return False
            
            loads = list(load_distribution.values())
            if len(loads) < 2:
                return False
            
            # Calculate load imbalance
            max_load = max(loads)
            min_load = min(loads)
            
            # Rebalance if difference is more than 30%
            return (max_load - min_load) > 0.3
            
        except Exception as e:
            logger.error(f"Error checking rebalancing need: {e}")
            return False
    
    def _generate_balancing_plan(self, 
                               workers: List[WorkerNode], 
                               strategy: OptimizationStrategy) -> Optional[Dict[str, Any]]:
        """Generate load balancing plan"""
        try:
            if len(workers) < 2:
                return None
            
            # Sort workers by current load
            workers_by_load = sorted(workers, key=lambda w: w.current_load / w.capacity)
            
            overloaded_workers = [w for w in workers if w.current_load / w.capacity > 0.8]
            underloaded_workers = [w for w in workers if w.current_load / w.capacity < 0.5]
            
            if not overloaded_workers or not underloaded_workers:
                return None
            
            plan = {
                "strategy": strategy.value,
                "actions": [],
                "expected_improvement": 0.0
            }
            
            # Generate rebalancing actions based on strategy
            if strategy == OptimizationStrategy.LICENSE_AWARE:
                plan["actions"] = self._generate_license_aware_actions(overloaded_workers, underloaded_workers)
            elif strategy == OptimizationStrategy.PERFORMANCE:
                plan["actions"] = self._generate_performance_actions(overloaded_workers, underloaded_workers)
            elif strategy == OptimizationStrategy.COST_EFFICIENT:
                plan["actions"] = self._generate_cost_efficient_actions(overloaded_workers, underloaded_workers)
            else:  # BALANCED
                plan["actions"] = self._generate_balanced_actions(overloaded_workers, underloaded_workers)
            
            # Calculate expected improvement
            plan["expected_improvement"] = len(plan["actions"]) * 0.1  # Simplified calculation
            
            return plan if plan["actions"] else None
            
        except Exception as e:
            logger.error(f"Error generating balancing plan: {e}")
            return None
    
    def _generate_license_aware_actions(self, 
                                      overloaded: List[WorkerNode], 
                                      underloaded: List[WorkerNode]) -> List[Dict[str, Any]]:
        """Generate license-aware balancing actions"""
        actions = []
        
        try:
            # Prioritize workers with higher license tiers
            overloaded_sorted = sorted(overloaded, key=lambda w: w.license_tier.value, reverse=True)
            underloaded_sorted = sorted(underloaded, key=lambda w: w.license_tier.value, reverse=True)
            
            for overloaded_worker in overloaded_sorted:
                for underloaded_worker in underloaded_sorted:
                    # Only move load between workers with compatible license tiers
                    if underloaded_worker.license_tier.value >= overloaded_worker.license_tier.value:
                        actions.append({
                            "type": "move_load",
                            "from": overloaded_worker.node_id,
                            "to": underloaded_worker.node_id,
                            "amount": min(0.2, overloaded_worker.current_load - 0.7),
                            "reason": "license_tier_compatibility"
                        })
                        break
            
        except Exception as e:
            logger.error(f"Error generating license-aware actions: {e}")
        
        return actions
    
    def _generate_performance_actions(self, 
                                    overloaded: List[WorkerNode], 
                                    underloaded: List[WorkerNode]) -> List[Dict[str, Any]]:
        """Generate performance-focused balancing actions"""
        actions = []
        
        try:
            # Prioritize workers with better performance scores
            underloaded_sorted = sorted(underloaded, key=lambda w: w.performance_score, reverse=True)
            
            for overloaded_worker in overloaded:
                best_target = underloaded_sorted[0] if underloaded_sorted else None
                if best_target:
                    actions.append({
                        "type": "move_load",
                        "from": overloaded_worker.node_id,
                        "to": best_target.node_id,
                        "amount": min(0.3, overloaded_worker.current_load - 0.6),
                        "reason": "performance_optimization"
                    })
            
        except Exception as e:
            logger.error(f"Error generating performance actions: {e}")
        
        return actions
    
    def _generate_cost_efficient_actions(self, 
                                       overloaded: List[WorkerNode], 
                                       underloaded: List[WorkerNode]) -> List[Dict[str, Any]]:
        """Generate cost-efficient balancing actions"""
        actions = []
        
        try:
            # Prefer using existing underloaded workers over adding new ones
            for overloaded_worker in overloaded:
                for underloaded_worker in underloaded:
                    if underloaded_worker.current_load / underloaded_worker.capacity < 0.4:
                        actions.append({
                            "type": "move_load",
                            "from": overloaded_worker.node_id,
                            "to": underloaded_worker.node_id,
                            "amount": min(0.25, overloaded_worker.current_load - 0.7),
                            "reason": "cost_efficiency"
                        })
                        break
            
        except Exception as e:
            logger.error(f"Error generating cost-efficient actions: {e}")
        
        return actions
    
    def _generate_balanced_actions(self, 
                                 overloaded: List[WorkerNode], 
                                 underloaded: List[WorkerNode]) -> List[Dict[str, Any]]:
        """Generate balanced load distribution actions"""
        actions = []
        
        try:
            # Simple round-robin distribution
            for i, overloaded_worker in enumerate(overloaded):
                target_worker = underloaded[i % len(underloaded)]
                actions.append({
                    "type": "move_load",
                    "from": overloaded_worker.node_id,
                    "to": target_worker.node_id,
                    "amount": min(0.2, overloaded_worker.current_load - 0.7),
                    "reason": "load_balancing"
                })
            
        except Exception as e:
            logger.error(f"Error generating balanced actions: {e}")
        
        return actions
    
    def _execute_balancing_plan(self, plan: Dict[str, Any]) -> bool:
        """Execute load balancing plan"""
        try:
            logger.info(f"Executing balancing plan with {len(plan['actions'])} actions")
            
            successful_actions = 0
            
            for action in plan["actions"]:
                try:
                    # In a real implementation, this would send commands to workers
                    # For now, we'll simulate the action
                    logger.info(f"Executing action: {action['type']} from {action['from']} to {action['to']}")
                    
                    # Update worker loads (simulation)
                    if action["from"] in self.worker_nodes and action["to"] in self.worker_nodes:
                        from_worker = self.worker_nodes[action["from"]]
                        to_worker = self.worker_nodes[action["to"]]
                        
                        # Move load
                        load_amount = action["amount"] * from_worker.capacity
                        from_worker.current_load = max(0, from_worker.current_load - load_amount)
                        to_worker.current_load = min(to_worker.capacity, to_worker.current_load + load_amount)
                        
                        successful_actions += 1
                    
                except Exception as e:
                    logger.error(f"Failed to execute action: {e}")
            
            success_rate = successful_actions / len(plan["actions"]) if plan["actions"] else 0
            return success_rate > 0.5
            
        except Exception as e:
            logger.error(f"Error executing balancing plan: {e}")
            return False
    
    def _analyze_current_usage(self) -> Dict[str, Any]:
        """Analyze current resource usage"""
        try:
            usage_analysis = {
                "total_workers": len(self.worker_nodes),
                "active_workers": len(self._get_active_workers()),
                "average_load": 0.0,
                "peak_load": 0.0,
                "resource_utilization": 0.0,
                "license_tier": self.license_info.plan.value if self.license_info else "none"
            }
            
            active_workers = self._get_active_workers()
            if active_workers:
                loads = [w.current_load / w.capacity for w in active_workers]
                usage_analysis["average_load"] = statistics.mean(loads)
                usage_analysis["peak_load"] = max(loads)
                usage_analysis["resource_utilization"] = sum(w.current_load for w in active_workers) / sum(w.capacity for w in active_workers)
            
            return usage_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing current usage: {e}")
            return {}
    
    def _generate_tier_recommendations(self, 
                                     usage_analysis: Dict[str, Any], 
                                     target_tier: Optional[SubscriptionTier]) -> List[OptimizationRecommendation]:
        """Generate tier-based optimization recommendations"""
        recommendations = []
        
        try:
            current_tier = self.license_info.plan if self.license_info else SubscriptionTier.FREE
            
            # Recommend tier upgrade if usage is high
            if usage_analysis.get("average_load", 0) > 0.8:
                if current_tier == SubscriptionTier.FREE:
                    recommendations.append(OptimizationRecommendation(
                        recommendation_id=f"tier_upgrade_{int(time.time())}",
                        strategy=OptimizationStrategy.LICENSE_AWARE,
                        action="upgrade_to_pro",
                        target_resources=["license"],
                        expected_improvement=0.3,
                        implementation_cost=100.0,
                        priority=8,
                        license_requirements=["pro_features"],
                        description="Upgrade to PRO tier for better performance and more workers",
                        estimated_savings={"performance_gain": 30.0, "capacity_increase": 500.0}
                    ))
                elif current_tier == SubscriptionTier.PRO:
                    recommendations.append(OptimizationRecommendation(
                        recommendation_id=f"tier_upgrade_ent_{int(time.time())}",
                        strategy=OptimizationStrategy.LICENSE_AWARE,
                        action="upgrade_to_enterprise",
                        target_resources=["license"],
                        expected_improvement=0.5,
                        implementation_cost=500.0,
                        priority=9,
                        license_requirements=["enterprise_features"],
                        description="Upgrade to Enterprise tier for unlimited capacity",
                        estimated_savings={"performance_gain": 50.0, "unlimited_capacity": 1000.0}
                    ))
            
            # Recommend tier downgrade if usage is consistently low
            elif usage_analysis.get("average_load", 0) < 0.2:
                if current_tier == SubscriptionTier.ENT:
                    recommendations.append(OptimizationRecommendation(
                        recommendation_id=f"tier_downgrade_pro_{int(time.time())}",
                        strategy=OptimizationStrategy.COST_EFFICIENT,
                        action="downgrade_to_pro",
                        target_resources=["license"],
                        expected_improvement=0.0,
                        implementation_cost=-400.0,  # Negative cost = savings
                        priority=6,
                        license_requirements=[],
                        description="Downgrade to PRO tier to reduce costs while maintaining adequate capacity",
                        estimated_savings={"cost_savings": 400.0}
                    ))
                elif current_tier == SubscriptionTier.PRO:
                    recommendations.append(OptimizationRecommendation(
                        recommendation_id=f"tier_downgrade_free_{int(time.time())}",
                        strategy=OptimizationStrategy.COST_EFFICIENT,
                        action="downgrade_to_free",
                        target_resources=["license"],
                        expected_improvement=0.0,
                        implementation_cost=-100.0,
                        priority=5,
                        license_requirements=[],
                        description="Downgrade to FREE tier for cost savings with low usage",
                        estimated_savings={"cost_savings": 100.0}
                    ))
            
        except Exception as e:
            logger.error(f"Error generating tier recommendations: {e}")
        
        return recommendations
    
    def _generate_performance_recommendations(self, usage_analysis: Dict[str, Any]) -> List[OptimizationRecommendation]:
        """Generate performance optimization recommendations"""
        recommendations = []
        
        try:
            # Recommend adding workers if load is high
            if usage_analysis.get("average_load", 0) > 0.85:
                recommendations.append(OptimizationRecommendation(
                    recommendation_id=f"add_workers_{int(time.time())}",
                    strategy=OptimizationStrategy.PERFORMANCE,
                    action="add_worker_nodes",
                    target_resources=["workers"],
                    expected_improvement=0.4,
                    implementation_cost=50.0,
                    priority=7,
                    license_requirements=["worker_scaling"],
                    description="Add more worker nodes to handle high load",
                    estimated_savings={"latency_reduction": 25.0, "throughput_increase": 40.0}
                ))
            
            # Recommend model optimization
            if usage_analysis.get("resource_utilization", 0) > 0.9:
                recommendations.append(OptimizationRecommendation(
                    recommendation_id=f"optimize_models_{int(time.time())}",
                    strategy=OptimizationStrategy.PERFORMANCE,
                    action="optimize_model_loading",
                    target_resources=["models"],
                    expected_improvement=0.2,
                    implementation_cost=20.0,
                    priority=6,
                    license_requirements=[],
                    description="Optimize model loading and caching for better resource utilization",
                    estimated_savings={"memory_savings": 15.0, "load_time_reduction": 20.0}
                ))
            
        except Exception as e:
            logger.error(f"Error generating performance recommendations: {e}")
        
        return recommendations
    
    def _generate_cost_recommendations(self, usage_analysis: Dict[str, Any]) -> List[OptimizationRecommendation]:
        """Generate cost optimization recommendations"""
        recommendations = []
        
        try:
            # Recommend removing idle workers
            if usage_analysis.get("average_load", 0) < 0.3:
                recommendations.append(OptimizationRecommendation(
                    recommendation_id=f"remove_idle_workers_{int(time.time())}",
                    strategy=OptimizationStrategy.COST_EFFICIENT,
                    action="remove_idle_workers",
                    target_resources=["workers"],
                    expected_improvement=0.0,
                    implementation_cost=-30.0,  # Cost savings
                    priority=5,
                    license_requirements=[],
                    description="Remove idle worker nodes to reduce operational costs",
                    estimated_savings={"cost_savings": 30.0}
                ))
            
            # Recommend resource consolidation
            if usage_analysis.get("active_workers", 0) > 5 and usage_analysis.get("average_load", 0) < 0.5:
                recommendations.append(OptimizationRecommendation(
                    recommendation_id=f"consolidate_resources_{int(time.time())}",
                    strategy=OptimizationStrategy.COST_EFFICIENT,
                    action="consolidate_workloads",
                    target_resources=["workers", "resources"],
                    expected_improvement=0.1,
                    implementation_cost=-25.0,
                    priority=4,
                    license_requirements=[],
                    description="Consolidate workloads onto fewer workers to reduce resource costs",
                    estimated_savings={"cost_savings": 25.0, "efficiency_gain": 10.0}
                ))
            
        except Exception as e:
            logger.error(f"Error generating cost recommendations: {e}")
        
        return recommendations
    
    def register_worker(self, worker: WorkerNode):
        """Register a new worker node"""
        try:
            self.worker_nodes[worker.node_id] = worker
            logger.info(f"Registered worker node: {worker.node_id}")
        except Exception as e:
            logger.error(f"Failed to register worker: {e}")
    
    def update_worker_status(self, node_id: str, load: float, memory_mb: int):
        """Update worker status"""
        try:
            if node_id in self.worker_nodes:
                worker = self.worker_nodes[node_id]
                worker.current_load = load
                worker.available_memory_mb = memory_mb
                worker.last_heartbeat = datetime.now()
                logger.debug(f"Updated worker status: {node_id}")
        except Exception as e:
            logger.error(f"Failed to update worker status: {e}")
    
    def start_optimization_monitoring(self):
        """Start continuous optimization monitoring"""
        try:
            if self.optimization_active:
                logger.warning("Optimization monitoring is already active")
                return
            
            self.optimization_active = True
            self.optimization_thread = threading.Thread(target=self._optimization_loop, daemon=True)
            self.optimization_thread.start()
            
            logger.info("Optimization monitoring started")
            
        except Exception as e:
            logger.error(f"Failed to start optimization monitoring: {e}")
    
    def stop_optimization_monitoring(self):
        """Stop optimization monitoring"""
        try:
            self.optimization_active = False
            
            if self.optimization_thread:
                self.optimization_thread.join(timeout=5)
            
            logger.info("Optimization monitoring stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop optimization monitoring: {e}")
    
    def _optimization_loop(self):
        """Main optimization monitoring loop"""
        while self.optimization_active:
            try:
                # Perform workload analysis
                self.analyze_workload_patterns()
                
                # Perform dynamic load balancing if needed
                self.dynamic_load_balancing()
                
                # Generate optimization suggestions
                self.generate_optimization_suggestions()
                
                # Update statistics
                self.optimization_stats["total_optimizations"] += 1
                self.optimization_stats["successful_optimizations"] += 1
                self.last_optimization = datetime.now()
                
                time.sleep(self.optimization_interval)
                
            except Exception as e:
                logger.error(f"Error in optimization loop: {e}")
                time.sleep(self.optimization_interval)
    
    def get_optimization_status(self) -> Dict[str, Any]:
        """Get current optimization status"""
        try:
            return {
                "optimization_active": self.optimization_active,
                "last_optimization": self.last_optimization.isoformat(),
                "worker_count": len(self.worker_nodes),
                "active_worker_count": len(self._get_active_workers()),
                "current_workload_pattern": self.current_workload_analysis.pattern_type.value if self.current_workload_analysis else "unknown",
                "pending_recommendations": len(self.optimization_recommendations),
                "statistics": self.optimization_stats.copy()
            }
        except Exception as e:
            logger.error(f"Failed to get optimization status: {e}")
            return {"error": str(e)}


def create_resource_optimizer(license_info: Optional[LicenseInfo] = None,
                            monitoring_system: Optional[MonitoringSystem] = None) -> ResourceOptimizer:
    """Create and initialize resource optimizer"""
    return ResourceOptimizer(license_info=license_info, monitoring_system=monitoring_system)


def main():
    """Main function for testing resource optimizer"""
    print("=== Testing Resource Optimizer ===\n")
    
    # Create test license
    from security.license_validator import LicenseInfo, SubscriptionTier, LicenseStatus
    
    license_info = LicenseInfo(
        license_key="TIKT-PRO-12-OPTIMIZER",
        plan=SubscriptionTier.PRO,
        duration_months=12,
        unique_id="OPTIMIZER",
        expires_at=datetime.now() + timedelta(days=365),
        max_clients=20,
        allowed_models=["llama", "mistral"],
        allowed_features=["optimization", "load_balancing"],
        status=LicenseStatus.VALID,
        hardware_signature="optimizer_hw",
        created_at=datetime.now(),
        checksum="optimizer_checksum"
    )
    
    # Create resource optimizer
    optimizer = create_resource_optimizer(license_info)
    
    # Test 1: Register worker nodes
    print("1. Testing Worker Registration")
    
    workers = [
        WorkerNode(
            node_id="worker-001",
            capacity=100,
            current_load=85.0,
            available_memory_mb=8192,
            cpu_cores=8,
            license_tier=SubscriptionTier.PRO
        ),
        WorkerNode(
            node_id="worker-002",
            capacity=100,
            current_load=25.0,
            available_memory_mb=16384,
            cpu_cores=16,
            license_tier=SubscriptionTier.PRO
        ),
        WorkerNode(
            node_id="worker-003",
            capacity=100,
            current_load=60.0,
            available_memory_mb=12288,
            cpu_cores=12,
            license_tier=SubscriptionTier.ENT
        )
    ]
    
    for worker in workers:
        optimizer.register_worker(worker)
    
    print(f"✓ Registered {len(workers)} worker nodes")
    
    print()
    
    # Test 2: Workload pattern analysis
    print("2. Testing Workload Pattern Analysis")
    
    # Add some sample workload data
    for i in range(50):
        load_value = 50 + 30 * (i % 10) / 10  # Simulated periodic pattern
        optimizer.workload_history.append({
            'timestamp': datetime.now() - timedelta(minutes=i),
            'load': load_value,
            'memory_usage': load_value * 0.8,
            'active_connections': int(load_value / 10)
        })
    
    analysis = optimizer.analyze_workload_patterns()
    print(f"✓ Workload analysis completed:")
    print(f"  Pattern: {analysis.pattern_type.value}")
    print(f"  Confidence: {analysis.confidence:.2f}")
    print(f"  Average load: {analysis.average_load:.1f}%")
    print(f"  Peak load: {analysis.peak_load:.1f}%")
    print(f"  Recommendations: {len(analysis.recommendations)}")
    
    print()
    
    # Test 3: Dynamic load balancing
    print("3. Testing Dynamic Load Balancing")
    
    success = optimizer.dynamic_load_balancing(OptimizationStrategy.LICENSE_AWARE)
    print(f"✓ Load balancing result: {success}")
    
    # Check updated loads
    for worker_id, worker in optimizer.worker_nodes.items():
        load_percent = (worker.current_load / worker.capacity) * 100
        print(f"  {worker_id}: {load_percent:.1f}% load")
    
    print()
    
    # Test 4: Optimization suggestions
    print("4. Testing Optimization Suggestions")
    
    recommendations = optimizer.generate_optimization_suggestions()
    print(f"✓ Generated {len(recommendations)} optimization recommendations:")
    
    for i, rec in enumerate(recommendations[:3], 1):  # Show top 3
        print(f"  {i}. {rec.action} (Priority: {rec.priority})")
        print(f"     {rec.description}")
        print(f"     Expected improvement: {rec.expected_improvement:.1%}")
    
    print()
    
    # Test 5: Optimization status
    print("5. Testing Optimization Status")
    
    status = optimizer.get_optimization_status()
    print(f"✓ Optimization status:")
    print(f"  Active workers: {status['active_worker_count']}/{status['worker_count']}")
    print(f"  Current pattern: {status['current_workload_pattern']}")
    print(f"  Pending recommendations: {status['pending_recommendations']}")
    print(f"  Total optimizations: {status['statistics']['total_optimizations']}")
    
    print("\n=== Resource Optimizer Tests Completed ===")


if __name__ == "__main__":
    main()