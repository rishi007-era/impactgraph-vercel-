"""Scenario definitions for Phase 1.

Three scenarios (all SIMULATIONS inside the project's own model):
  S1  Mode A  Colonial-inspired IT-side ransomware with uncertainty about OT exposure
  S2  Mode B  Hypothetical IT-to-OT propagation toward a pump controller
  S3  Physical sabotage / failure of remote field assets (plus a tampered field RTU)

Mode A represents the documented IT-side incident. The probability that the intruder also holds
an OT foothold is NOT a historical fact: it models the operators' uncertainty and is an assumption.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..infrastructure.enums import Zone


@dataclass(frozen=True)
class PhysicalEntry:
    node_id: str
    probability: float          # chance the physical intrusion/sabotage succeeds in a trial (assumed)
    release: bool = False       # failure releases product (rupture) -> hazard exposure


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    mode: str                                   # "A" historical, "B" hypothetical cyber, "P" physical
    description: str
    entry_nodes: tuple = ()                     # ((node_id, frozenset(initial capabilities)), ...)
    physical_entries: tuple = ()
    allowed_zones: Optional[frozenset] = None   # attacker spread restriction (None = unrestricted)
    ransomware_zones: frozenset = frozenset()
    ransomware_prob: float = 0.9
    ot_foothold_prob: float = 0.0
    foothold_node: str = "OT01"
    env: dict = field(default_factory=dict)     # environment flags used by access conditions
    attempts: int = 3                           # attempts per edge within the horizon
    response_delay: float = 3.0                 # hops before a decided isolation takes effect
    alert_seed_node: str = ""                   # component that raised the first alert
    focus_targets: tuple = ()                   # nodes for attack-path analysis
    assumptions: tuple = ()


SCENARIOS = {
    "S1": Scenario(
        id="S1",
        name="IT ransomware with OT-exposure uncertainty (Colonial-inspired, Mode A)",
        mode="A",
        description=("A legacy remote account is compromised and ransomware spreads through vendor access and "
                     "enterprise IT. Operators cannot tell whether the intruder also holds a foothold inside OT "
                     "(modelled as an assumed probability), which is the decision problem behind a precautionary shutdown."),
        entry_nodes=(("V02", frozenset({"valid_credentials"})),),
        allowed_zones=frozenset({Zone.VENDOR, Zone.IT}),
        ransomware_zones=frozenset({Zone.IT}),
        ransomware_prob=0.9,
        ot_foothold_prob=0.15,
        foothold_node="OT01",
        attempts=3,
        response_delay=3.0,
        alert_seed_node="V02",
        focus_targets=("OT01", "OT02", "PH01"),
        assumptions=("Historical facts: IT-side ransomware; operations shut down as a precaution; OT not shown compromised.",
                     "Assumed: 15% chance an OT foothold already exists (uncertainty model, not a historical claim).",
                     "Assumed: ransomware impact probability 0.9 per reached IT host; 3 attempts per link."),
    ),
    "S2": Scenario(
        id="S2",
        name="Hypothetical IT-to-OT propagation toward a pump controller (Mode B)",
        mode="B",
        description=("Hypothetical: the same remote-account compromise, but the adversary pursues the control "
                     "network through the IT/OT gateway, a SCADA server and a PLC to cause unsafe pump actuation. "
                     "This is a simulation, not a claim about what happened in 2021."),
        entry_nodes=(("V02", frozenset({"valid_credentials"})),),
        allowed_zones=None,
        attempts=3,
        response_delay=3.0,
        alert_seed_node="V02",
        focus_targets=("PH01", "PH03", "PH04"),
        assumptions=("All traversal probabilities are assumed, not calibrated.",
                     "A control edge into a physical asset models the chance that a compromised controller causes unsafe actuation.",
                     "Isolation decided after the first alert takes effect after a response delay of 3 hops."),
    ),
    "S3": Scenario(
        id="S3",
        name="Physical sabotage of remote field assets (Mode P)",
        mode="P",
        description=("Hypothetical on-site sabotage at remote right-of-way assets: segments may rupture, the block "
                     "valve may be forced closed, and a field RTU cabinet may be tampered with, giving the intruder "
                     "control of downstream actuators."),
        entry_nodes=(),
        physical_entries=(PhysicalEntry("PH02", 0.35, True), PhysicalEntry("PH03", 0.50, False),
                          PhysicalEntry("PH05", 0.35, True), PhysicalEntry("OT06", 0.45, False)),
        attempts=3,
        response_delay=0.0,
        alert_seed_node="PH05",
        focus_targets=("PH03", "PH04", "PH06"),
        assumptions=("Sabotage success probabilities are assumed values loosely scaled to each site's physical-access exposure.",
                     "A ruptured segment keeps releasing product while upstream flow can still reach it (hazard exposure).",
                     "Physical isolation means closing a block valve; it reduces hazard but does not restore throughput."),
    ),
}
