# ImpactGraph infrastructure graph: schema and assumptions (Milestone 1)

## Status of every number
All importance, exposure, vulnerability, physical-access exposure, traversal probability,
dependency strength, isolation cost, telemetry range and flow capacity in `topology.py` and
`telemetry_spec.py` is an **assumed model value**. None is calibrated to a real system.
Flow capacities are model units (m3/h), not Colonial Pipeline throughput.

## Historical vs hypothetical
- Mode A (historical reconstruction): IT-side compromise, uncertainty about OT exposure, precautionary shutdown.
  Edge IT02 -> PH08 (billing needed to complete deliveries) is a *reconstructed assumption*.
- Mode B (hypothetical): any path that reaches OT or physical assets (e.g. V03 -> OT01, IT01 -> OT01) is a simulated
  weakness, not a claim about what happened in 2021.

## Relationship types and direction
| Type | Direction means | Used by |
|---|---|---|
| network | adversary at source can reach target | attack-path model |
| auth | adversary holding source access can authenticate to target | attack-path model |
| control | source can command target (OT -> OT/physical) | attack-path model, actuation effects |
| physical_flow | product flows source -> target | throughput / resilience |
| operational_dep | failure of source can degrade target | failure propagation |
| service_dep | failure of source's service can degrade target | failure propagation |

Attack traversal and failure transfer use different edge sets (`attack_graph()` vs `dependency_graph()`);
physical flow is never an attack route.

## Boundary rules enforced by the validator
- Vendor -> OT and IT -> OT connections must end at the DMZ boundary gateway.
- OT -> IT connections must start at the DMZ boundary gateway.
- Physical assets never initiate cyber links; only OT `control` edges may enter them.
- Network and auth edges never touch physical assets.
- Physical flow joins physical assets only and must be acyclic.
- A dependency cannot be marked isolatable; isolate the underlying link.
- Logical isolation of a link into a safety-critical component raises a SAFETY_REVIEW warning.

## Threat entry points carried by the model
- Cyber entry: `exposure`, `vulnerability`, `security_controls` on nodes; `traversal_probability` and
  `access_conditions` on edges.
- Physical sabotage entry: `physical_access_exposure` on nodes (field sites such as the block valve station and RTU score highest).
