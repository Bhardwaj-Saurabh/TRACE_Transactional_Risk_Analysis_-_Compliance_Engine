"""
Metrics Aggregator - Performance and Cost Tracking

This module aggregates performance metrics and cost data from audit logs
to provide comprehensive system efficiency analysis.
"""

import json
import statistics
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


class MetricsAggregator:
    """Aggregates and analyzes system performance and cost metrics from audit logs."""

    def __init__(self, audit_log_path: str):
        """Initialize metrics aggregator with audit log path.

        Args:
            audit_log_path: Path to the audit log file (JSONL format)
        """
        self.audit_log_path = Path(audit_log_path)
        self.entries: List[Dict[str, Any]] = []

    def load_audit_logs(self) -> int:
        """Load all entries from the audit log file.

        Returns:
            Number of entries loaded
        """
        self.entries = []

        if not self.audit_log_path.exists():
            return 0

        with open(self.audit_log_path, 'r') as f:
            for line in f:
                if line.strip():
                    try:
                        entry = json.loads(line)
                        self.entries.append(entry)
                    except json.JSONDecodeError:
                        continue  # Skip malformed lines

        return len(self.entries)

    def aggregate_metrics(self) -> Dict[str, Any]:
        """Aggregate all metrics from audit logs.

        Returns:
            Dictionary containing comprehensive metrics rollup
        """
        if not self.entries:
            return self._empty_metrics()

        # Separate by agent type
        risk_analyst_entries = [e for e in self.entries if e.get('agent_type') == 'RiskAnalyst' and e.get('success')]
        compliance_entries = [e for e in self.entries if e.get('agent_type') == 'ComplianceOfficer' and e.get('success')]

        metrics = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'audit_log_path': str(self.audit_log_path),
                'total_entries': len(self.entries),
                'successful_entries': len([e for e in self.entries if e.get('success')])
            },
            'overall': self._compute_overall_metrics(self.entries),
            'by_agent': {
                'RiskAnalyst': self._compute_agent_metrics(risk_analyst_entries),
                'ComplianceOfficer': self._compute_agent_metrics(compliance_entries)
            },
            'cost_breakdown': self._compute_cost_breakdown(self.entries),
            'performance_comparison': self._compute_performance_comparison(
                risk_analyst_entries, compliance_entries
            )
        }

        return metrics

    def _compute_overall_metrics(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute overall system metrics.

        Args:
            entries: List of audit log entries

        Returns:
            Dictionary of overall metrics
        """
        successful_entries = [e for e in entries if e.get('success')]

        if not successful_entries:
            return self._empty_agent_metrics()

        # Extract metrics
        exec_times = [e.get('execution_time_ms', 0) for e in successful_entries]
        costs = [e.get('cost_usd', 0) for e in successful_entries if e.get('cost_usd') is not None]

        # Token metrics
        prompt_tokens = [e.get('token_usage', {}).get('prompt_tokens', 0)
                        for e in successful_entries if e.get('token_usage')]
        completion_tokens = [e.get('token_usage', {}).get('completion_tokens', 0)
                            for e in successful_entries if e.get('token_usage')]
        total_tokens = [e.get('token_usage', {}).get('total_tokens', 0)
                       for e in successful_entries if e.get('token_usage')]

        return {
            'total_operations': len(successful_entries),
            'execution_time_ms': {
                'mean': statistics.mean(exec_times) if exec_times else 0,
                'median': statistics.median(exec_times) if exec_times else 0,
                'p95': self._percentile(exec_times, 95) if exec_times else 0,
                'min': min(exec_times) if exec_times else 0,
                'max': max(exec_times) if exec_times else 0
            },
            'token_usage': {
                'total_prompt_tokens': sum(prompt_tokens),
                'total_completion_tokens': sum(completion_tokens),
                'total_tokens': sum(total_tokens),
                'mean_prompt_tokens': statistics.mean(prompt_tokens) if prompt_tokens else 0,
                'mean_completion_tokens': statistics.mean(completion_tokens) if completion_tokens else 0,
                'mean_total_tokens': statistics.mean(total_tokens) if total_tokens else 0
            },
            'cost_usd': {
                'total': sum(costs),
                'mean': statistics.mean(costs) if costs else 0,
                'median': statistics.median(costs) if costs else 0,
                'min': min(costs) if costs else 0,
                'max': max(costs) if costs else 0
            }
        }

    def _compute_agent_metrics(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute metrics for a specific agent type.

        Args:
            entries: List of audit log entries for one agent type

        Returns:
            Dictionary of agent-specific metrics
        """
        if not entries:
            return self._empty_agent_metrics()

        # Extract metrics
        exec_times = [e.get('execution_time_ms', 0) for e in entries]
        costs = [e.get('cost_usd', 0) for e in entries if e.get('cost_usd') is not None]

        # Token metrics
        prompt_tokens = [e.get('token_usage', {}).get('prompt_tokens', 0)
                        for e in entries if e.get('token_usage')]
        completion_tokens = [e.get('token_usage', {}).get('completion_tokens', 0)
                            for e in entries if e.get('token_usage')]
        total_tokens = [e.get('token_usage', {}).get('total_tokens', 0)
                       for e in entries if e.get('token_usage')]

        return {
            'operations': len(entries),
            'execution_time_ms': {
                'mean': round(statistics.mean(exec_times), 2) if exec_times else 0,
                'median': round(statistics.median(exec_times), 2) if exec_times else 0,
                'p95': round(self._percentile(exec_times, 95), 2) if exec_times else 0,
                'min': round(min(exec_times), 2) if exec_times else 0,
                'max': round(max(exec_times), 2) if exec_times else 0
            },
            'token_usage': {
                'total_prompt_tokens': sum(prompt_tokens),
                'total_completion_tokens': sum(completion_tokens),
                'total_tokens': sum(total_tokens),
                'mean_prompt_tokens': round(statistics.mean(prompt_tokens), 1) if prompt_tokens else 0,
                'mean_completion_tokens': round(statistics.mean(completion_tokens), 1) if completion_tokens else 0,
                'mean_total_tokens': round(statistics.mean(total_tokens), 1) if total_tokens else 0
            },
            'cost_usd': {
                'total': round(sum(costs), 6),
                'mean': round(statistics.mean(costs), 6) if costs else 0,
                'median': round(statistics.median(costs), 6) if costs else 0,
                'per_operation': round(sum(costs) / len(entries), 6) if entries else 0
            }
        }

    def _compute_cost_breakdown(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute detailed cost breakdown.

        Args:
            entries: List of audit log entries

        Returns:
            Dictionary of cost breakdown by agent and model
        """
        risk_analyst_costs = [e.get('cost_usd', 0) for e in entries
                             if e.get('agent_type') == 'RiskAnalyst' and e.get('cost_usd') is not None]
        compliance_costs = [e.get('cost_usd', 0) for e in entries
                           if e.get('agent_type') == 'ComplianceOfficer' and e.get('cost_usd') is not None]

        total_risk_cost = sum(risk_analyst_costs)
        total_compliance_cost = sum(compliance_costs)
        total_cost = total_risk_cost + total_compliance_cost

        return {
            'total_cost_usd': round(total_cost, 6),
            'risk_analyst_cost_usd': round(total_risk_cost, 6),
            'compliance_officer_cost_usd': round(total_compliance_cost, 6),
            'risk_analyst_percentage': round((total_risk_cost / total_cost * 100), 2) if total_cost > 0 else 0,
            'compliance_officer_percentage': round((total_compliance_cost / total_cost * 100), 2) if total_cost > 0 else 0,
            'cost_per_sar': round(total_cost / len(risk_analyst_costs), 6) if risk_analyst_costs else 0
        }

    def _compute_performance_comparison(self, risk_entries: List[Dict],
                                       compliance_entries: List[Dict]) -> Dict[str, Any]:
        """Compare performance between agent stages.

        Args:
            risk_entries: RiskAnalyst entries
            compliance_entries: ComplianceOfficer entries

        Returns:
            Performance comparison metrics
        """
        risk_time = statistics.mean([e.get('execution_time_ms', 0) for e in risk_entries]) if risk_entries else 0
        compliance_time = statistics.mean([e.get('execution_time_ms', 0) for e in compliance_entries]) if compliance_entries else 0

        total_time = risk_time + compliance_time

        risk_cost = sum([e.get('cost_usd', 0) for e in risk_entries if e.get('cost_usd') is not None])
        compliance_cost = sum([e.get('cost_usd', 0) for e in compliance_entries if e.get('cost_usd') is not None])

        return {
            'total_pipeline_time_ms': round(total_time, 2),
            'risk_analysis_time_ms': round(risk_time, 2),
            'compliance_time_ms': round(compliance_time, 2),
            'risk_analysis_percentage': round((risk_time / total_time * 100), 2) if total_time > 0 else 0,
            'compliance_percentage': round((compliance_time / total_time * 100), 2) if total_time > 0 else 0,
            'stage_1_vs_stage_2_cost_delta_usd': round(risk_cost - compliance_cost, 6),
            'stage_1_cost_usd': round(risk_cost, 6),
            'stage_2_cost_usd': round(compliance_cost, 6)
        }

    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile value.

        Args:
            data: List of numeric values
            percentile: Percentile to calculate (0-100)

        Returns:
            Percentile value
        """
        if not data:
            return 0.0

        sorted_data = sorted(data)
        index = (len(sorted_data) - 1) * percentile / 100

        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower = sorted_data[int(index)]
            upper = sorted_data[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))

    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics structure.

        Returns:
            Empty metrics dictionary
        """
        return {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'audit_log_path': str(self.audit_log_path),
                'total_entries': 0,
                'successful_entries': 0
            },
            'overall': self._empty_agent_metrics(),
            'by_agent': {
                'RiskAnalyst': self._empty_agent_metrics(),
                'ComplianceOfficer': self._empty_agent_metrics()
            },
            'cost_breakdown': {
                'total_cost_usd': 0,
                'risk_analyst_cost_usd': 0,
                'compliance_officer_cost_usd': 0,
                'risk_analyst_percentage': 0,
                'compliance_officer_percentage': 0,
                'cost_per_sar': 0
            },
            'performance_comparison': {
                'total_pipeline_time_ms': 0,
                'risk_analysis_time_ms': 0,
                'compliance_time_ms': 0,
                'risk_analysis_percentage': 0,
                'compliance_percentage': 0,
                'stage_1_vs_stage_2_cost_delta_usd': 0,
                'stage_1_cost_usd': 0,
                'stage_2_cost_usd': 0
            }
        }

    def _empty_agent_metrics(self) -> Dict[str, Any]:
        """Return empty agent metrics structure.

        Returns:
            Empty agent metrics dictionary
        """
        return {
            'operations': 0,
            'execution_time_ms': {
                'mean': 0,
                'median': 0,
                'p95': 0,
                'min': 0,
                'max': 0
            },
            'token_usage': {
                'total_prompt_tokens': 0,
                'total_completion_tokens': 0,
                'total_tokens': 0,
                'mean_prompt_tokens': 0,
                'mean_completion_tokens': 0,
                'mean_total_tokens': 0
            },
            'cost_usd': {
                'total': 0,
                'mean': 0,
                'median': 0,
                'per_operation': 0
            }
        }

    def save_metrics(self, output_path: str) -> None:
        """Save aggregated metrics to JSON file.

        Args:
            output_path: Path to output JSON file
        """
        metrics = self.aggregate_metrics()

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w') as f:
            json.dump(metrics, f, indent=2)

    def print_summary(self) -> None:
        """Print human-readable metrics summary."""
        metrics = self.aggregate_metrics()

        print("\n" + "=" * 80)
        print("SYSTEM PERFORMANCE & COST METRICS")
        print("=" * 80)

        print(f"\nGenerated: {metrics['metadata']['generated_at']}")
        print(f"Total Operations: {metrics['metadata']['successful_entries']}")

        print("\n" + "-" * 80)
        print("OVERALL METRICS")
        print("-" * 80)
        overall = metrics['overall']
        print(f"Total Cost: ${overall['cost_usd']['total']:.6f}")
        print(f"Mean Execution Time: {overall['execution_time_ms']['mean']:.2f}ms")
        print(f"P95 Execution Time: {overall['execution_time_ms']['p95']:.2f}ms")
        print(f"Total Tokens: {overall['token_usage']['total_tokens']:,}")

        print("\n" + "-" * 80)
        print("BY AGENT TYPE")
        print("-" * 80)

        for agent_type in ['RiskAnalyst', 'ComplianceOfficer']:
            agent_metrics = metrics['by_agent'][agent_type]
            print(f"\n{agent_type}:")
            print(f"  Operations: {agent_metrics['operations']}")
            print(f"  Total Cost: ${agent_metrics['cost_usd']['total']:.6f}")
            print(f"  Mean Cost: ${agent_metrics['cost_usd']['mean']:.6f}")
            print(f"  Mean Tokens: {agent_metrics['token_usage']['mean_total_tokens']:.1f}")
            print(f"  Mean Time: {agent_metrics['execution_time_ms']['mean']:.2f}ms")

        print("\n" + "-" * 80)
        print("COST BREAKDOWN")
        print("-" * 80)
        cost_breakdown = metrics['cost_breakdown']
        print(f"Total System Cost: ${cost_breakdown['total_cost_usd']:.6f}")
        print(f"Cost Per SAR: ${cost_breakdown['cost_per_sar']:.6f}")
        print(f"RiskAnalyst: ${cost_breakdown['risk_analyst_cost_usd']:.6f} ({cost_breakdown['risk_analyst_percentage']:.1f}%)")
        print(f"ComplianceOfficer: ${cost_breakdown['compliance_officer_cost_usd']:.6f} ({cost_breakdown['compliance_officer_percentage']:.1f}%)")

        print("\n" + "=" * 80)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python metrics_aggregator.py <audit_log_path> [output_path]")
        sys.exit(1)

    audit_log = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "outputs/metrics.json"

    aggregator = MetricsAggregator(audit_log)
    entries_loaded = aggregator.load_audit_logs()

    print(f"Loaded {entries_loaded} entries from {audit_log}")

    aggregator.save_metrics(output_path)
    print(f"\nMetrics saved to: {output_path}")

    aggregator.print_summary()
