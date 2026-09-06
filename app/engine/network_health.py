"""
Simulated Network Health Engine.

Provides deterministic synthetic rail telemetry across scenarios, supporting:
- Deterministic simulation seeds
- Temporal health degradation and recovery timelines
- Explicit simulation labeling and disclaimers (NEVER claims live bank telemetry)
"""

import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Any

from app.models.enums import NetworkScenario
from app.models.schemas import RailHealthTelemetry

RAIL_METADATA = {
    "UPI_SBI": {"name": "SBI UPI Rail", "category": "UPI"},
    "UPI_HDFC": {"name": "HDFC UPI Rail", "category": "UPI"},
    "UPI_ICICI": {"name": "ICICI UPI Rail", "category": "UPI"},
    "UPI_AXIS": {"name": "Axis UPI Rail", "category": "UPI"},
    "CARD_VISA": {"name": "Visa Card Rail", "category": "CARD"},
    "CARD_MASTERCARD": {"name": "Mastercard Rail", "category": "CARD"},
    "NETBANKING_SBI": {"name": "SBI Netbanking Rail", "category": "NETBANKING"},
}

# Base health score templates per scenario (Deterministic Scenario Presets)
SCENARIO_PRESETS: Dict[NetworkScenario, Dict[str, Dict[str, float]]] = {
    NetworkScenario.NORMAL: {
        "UPI_SBI": {"health": 95.0, "latency_ms": 220.0, "timeout_rate": 0.012, "success_rate": 0.988},
        "UPI_HDFC": {"health": 98.0, "latency_ms": 180.0, "timeout_rate": 0.006, "success_rate": 0.994},
        "UPI_ICICI": {"health": 96.0, "latency_ms": 195.0, "timeout_rate": 0.009, "success_rate": 0.991},
        "UPI_AXIS": {"health": 94.0, "latency_ms": 230.0, "timeout_rate": 0.015, "success_rate": 0.985},
        "CARD_VISA": {"health": 97.0, "latency_ms": 310.0, "timeout_rate": 0.008, "success_rate": 0.992},
        "CARD_MASTERCARD": {"health": 96.5, "latency_ms": 325.0, "timeout_rate": 0.010, "success_rate": 0.990},
        "NETBANKING_SBI": {"health": 93.0, "latency_ms": 450.0, "timeout_rate": 0.018, "success_rate": 0.982},
    },
    NetworkScenario.SBI_DEGRADED: {
        # SBI is degraded as a demo scenario (43.0), ICICI at 91.0, HDFC at 97.0
        "UPI_SBI": {"health": 43.0, "latency_ms": 1850.0, "timeout_rate": 0.185, "success_rate": 0.815},
        "UPI_HDFC": {"health": 97.0, "latency_ms": 185.0, "timeout_rate": 0.007, "success_rate": 0.993},
        "UPI_ICICI": {"health": 91.0, "latency_ms": 280.0, "timeout_rate": 0.024, "success_rate": 0.976},
        "UPI_AXIS": {"health": 88.0, "latency_ms": 340.0, "timeout_rate": 0.031, "success_rate": 0.969},
        "CARD_VISA": {"health": 96.0, "latency_ms": 315.0, "timeout_rate": 0.009, "success_rate": 0.991},
        "CARD_MASTERCARD": {"health": 95.5, "latency_ms": 330.0, "timeout_rate": 0.011, "success_rate": 0.989},
        "NETBANKING_SBI": {"health": 48.0, "latency_ms": 1600.0, "timeout_rate": 0.160, "success_rate": 0.840},
    },
    NetworkScenario.ICICI_DEGRADED: {
        "UPI_SBI": {"health": 94.0, "latency_ms": 230.0, "timeout_rate": 0.014, "success_rate": 0.986},
        "UPI_HDFC": {"health": 97.0, "latency_ms": 190.0, "timeout_rate": 0.008, "success_rate": 0.992},
        "UPI_ICICI": {"health": 45.0, "latency_ms": 1650.0, "timeout_rate": 0.170, "success_rate": 0.830},
        "UPI_AXIS": {"health": 92.0, "latency_ms": 260.0, "timeout_rate": 0.020, "success_rate": 0.980},
        "CARD_VISA": {"health": 96.5, "latency_ms": 310.0, "timeout_rate": 0.009, "success_rate": 0.991},
        "CARD_MASTERCARD": {"health": 96.0, "latency_ms": 320.0, "timeout_rate": 0.010, "success_rate": 0.990},
        "NETBANKING_SBI": {"health": 92.0, "latency_ms": 470.0, "timeout_rate": 0.021, "success_rate": 0.979},
    },
    NetworkScenario.MULTI_RAIL_DEGRADATION: {
        "UPI_SBI": {"health": 38.0, "latency_ms": 2100.0, "timeout_rate": 0.220, "success_rate": 0.780},
        "UPI_HDFC": {"health": 92.0, "latency_ms": 270.0, "timeout_rate": 0.022, "success_rate": 0.978},
        "UPI_ICICI": {"health": 74.0, "latency_ms": 650.0, "timeout_rate": 0.075, "success_rate": 0.925},
        "UPI_AXIS": {"health": 45.0, "latency_ms": 1700.0, "timeout_rate": 0.175, "success_rate": 0.825},
        "CARD_VISA": {"health": 89.0, "latency_ms": 410.0, "timeout_rate": 0.028, "success_rate": 0.972},
        "CARD_MASTERCARD": {"health": 88.0, "latency_ms": 430.0, "timeout_rate": 0.030, "success_rate": 0.970},
        "NETBANKING_SBI": {"health": 35.0, "latency_ms": 2400.0, "timeout_rate": 0.250, "success_rate": 0.750},
    },
    NetworkScenario.UPI_OUTAGE: {
        "UPI_SBI": {"health": 22.0, "latency_ms": 3800.0, "timeout_rate": 0.450, "success_rate": 0.550},
        "UPI_HDFC": {"health": 40.0, "latency_ms": 1950.0, "timeout_rate": 0.210, "success_rate": 0.790},
        "UPI_ICICI": {"health": 31.0, "latency_ms": 2800.0, "timeout_rate": 0.320, "success_rate": 0.680},
        "UPI_AXIS": {"health": 25.0, "latency_ms": 3400.0, "timeout_rate": 0.390, "success_rate": 0.610},
        "CARD_VISA": {"health": 96.0, "latency_ms": 310.0, "timeout_rate": 0.009, "success_rate": 0.991},
        "CARD_MASTERCARD": {"health": 95.0, "latency_ms": 325.0, "timeout_rate": 0.011, "success_rate": 0.989},
        "NETBANKING_SBI": {"health": 78.0, "latency_ms": 680.0, "timeout_rate": 0.065, "success_rate": 0.935},
    },
    NetworkScenario.CARD_DEGRADATION: {
        "UPI_SBI": {"health": 94.0, "latency_ms": 230.0, "timeout_rate": 0.014, "success_rate": 0.986},
        "UPI_HDFC": {"health": 97.0, "latency_ms": 190.0, "timeout_rate": 0.008, "success_rate": 0.992},
        "UPI_ICICI": {"health": 95.0, "latency_ms": 210.0, "timeout_rate": 0.011, "success_rate": 0.989},
        "UPI_AXIS": {"health": 93.0, "latency_ms": 250.0, "timeout_rate": 0.017, "success_rate": 0.983},
        "CARD_VISA": {"health": 48.0, "latency_ms": 2100.0, "timeout_rate": 0.190, "success_rate": 0.810},
        "CARD_MASTERCARD": {"health": 52.0, "latency_ms": 1850.0, "timeout_rate": 0.165, "success_rate": 0.835},
        "NETBANKING_SBI": {"health": 91.0, "latency_ms": 490.0, "timeout_rate": 0.024, "success_rate": 0.976},
    },
    NetworkScenario.RECOVERY: {
        "UPI_SBI": {"health": 82.0, "latency_ms": 480.0, "timeout_rate": 0.045, "success_rate": 0.955},
        "UPI_HDFC": {"health": 97.5, "latency_ms": 180.0, "timeout_rate": 0.007, "success_rate": 0.993},
        "UPI_ICICI": {"health": 94.0, "latency_ms": 220.0, "timeout_rate": 0.015, "success_rate": 0.985},
        "UPI_AXIS": {"health": 91.0, "latency_ms": 270.0, "timeout_rate": 0.022, "success_rate": 0.978},
        "CARD_VISA": {"health": 96.5, "latency_ms": 310.0, "timeout_rate": 0.009, "success_rate": 0.991},
        "CARD_MASTERCARD": {"health": 96.0, "latency_ms": 320.0, "timeout_rate": 0.010, "success_rate": 0.990},
        "NETBANKING_SBI": {"health": 88.0, "latency_ms": 520.0, "timeout_rate": 0.032, "success_rate": 0.968},
    },
}

class SimulatedNetworkHealthEngine:
    """
    Deterministic Simulator for Payment Rail Telemetry.
    All scores represent simulation scenario outputs, never live production telemetry.
    """

    @staticmethod
    def _deterministic_jitter(key: str, seed: int, max_range: float = 2.0) -> float:
        """Derives a deterministic jitter in [-max_range, max_range] based on key and seed."""
        raw = hashlib.md5(f"{key}_{seed}".encode()).hexdigest()
        normalized = int(raw[:6], 16) / 0xFFFFFF  # 0.0 to 1.0
        return (normalized * 2.0 - 1.0) * max_range

    @classmethod
    def get_rail_health(
        cls,
        rail_id: str,
        scenario: NetworkScenario = NetworkScenario.SBI_DEGRADED,
        seed: int = 42,
        time_offset_minutes: int = 0,
    ) -> RailHealthTelemetry:
        """Returns deterministic telemetry for a single rail."""
        scenario_data = SCENARIO_PRESETS.get(scenario, SCENARIO_PRESETS[NetworkScenario.NORMAL])
        base = scenario_data.get(rail_id, {"health": 90.0, "latency_ms": 300.0, "timeout_rate": 0.02, "success_rate": 0.98})

        # Apply deterministic seed jitter
        jitter = cls._deterministic_jitter(f"{scenario.value}_{rail_id}_{time_offset_minutes}", seed, max_range=1.8)
        health = round(max(5.0, min(100.0, base["health"] + jitter)), 1)
        latency = round(max(50.0, base["latency_ms"] + jitter * 15.0), 1)
        timeout = round(max(0.001, min(0.99, base["timeout_rate"] - (jitter * 0.002))), 3)
        success = round(max(0.01, min(0.999, 1.0 - timeout)), 3)

        if health >= 80.0:
            status = "OPERATIONAL"
        elif health >= 40.0:
            status = "DEGRADED"
        else:
            status = "OUTAGE"

        rail_name = RAIL_METADATA.get(rail_id, {}).get("name", rail_id)
        now_iso = datetime.now(timezone.utc).isoformat()

        return RailHealthTelemetry(
            rail_id=rail_id,
            rail_name=rail_name,
            health_score=health,
            status=status,
            latency_ms=latency,
            timeout_rate=timeout,
            success_rate=success,
            scenario=scenario,
            timestamp=now_iso,
            simulation_disclaimer="SIMULATED NETWORK HEALTH: Generated by deterministic scenario simulation; not live bank telemetry.",
        )

    @classmethod
    def get_all_rail_health(
        cls,
        scenario: NetworkScenario = NetworkScenario.SBI_DEGRADED,
        seed: int = 42,
        time_offset_minutes: int = 0,
    ) -> Dict[str, RailHealthTelemetry]:
        """Returns deterministic telemetry for all known rails."""
        return {
            rail_id: cls.get_rail_health(rail_id, scenario=scenario, seed=seed, time_offset_minutes=time_offset_minutes)
            for rail_id in RAIL_METADATA.keys()
        }

    @classmethod
    def get_temporal_timeline(
        cls,
        rail_id: str = "UPI_SBI",
        scenario: NetworkScenario = NetworkScenario.SBI_DEGRADED,
        seed: int = 42,
    ) -> List[Dict[str, Any]]:
        """
        Generates a 7-step temporal health timeline demonstrating degradation and recovery.
        E.g.: 10:00 -> 94, 10:05 -> 91, 10:10 -> 78, 10:15 -> 43, 10:20 -> 39, 10:25 -> 67, 10:30 -> 89
        """
        temporal_trajectory = [
            {"time_label": "10:00", "offset_min": -30, "factor": 1.00},
            {"time_label": "10:05", "offset_min": -25, "factor": 0.96},
            {"time_label": "10:10", "offset_min": -20, "factor": 0.82},
            {"time_label": "10:15", "offset_min": -15, "factor": 0.45},
            {"time_label": "10:20", "offset_min": -10, "factor": 0.41},
            {"time_label": "10:25", "offset_min": -5,  "factor": 0.71},
            {"time_label": "10:30", "offset_min": 0,   "factor": 0.94},
        ]

        scenario_data = SCENARIO_PRESETS.get(scenario, SCENARIO_PRESETS[NetworkScenario.NORMAL])
        base_health = scenario_data.get(rail_id, {"health": 90.0})["health"]

        timeline = []
        for step in temporal_trajectory:
            jitter = cls._deterministic_jitter(f"temp_{step['time_label']}_{rail_id}", seed, max_range=2.0)
            if scenario == NetworkScenario.NORMAL:
                step_health = round(max(85.0, min(100.0, 95.0 + jitter)), 1)
            else:
                target = base_health * step["factor"] if step["factor"] < 0.9 else (95.0 * step["factor"])
                step_health = round(max(10.0, min(100.0, target + jitter)), 1)

            timeline.append({
                "time_label": step["time_label"],
                "offset_minutes": step["offset_min"],
                "health_score": step_health,
                "status": "OPERATIONAL" if step_health >= 80.0 else ("DEGRADED" if step_health >= 50.0 else "OUTAGE"),
            })

        return timeline
