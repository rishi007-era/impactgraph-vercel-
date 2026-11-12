"""Access rules: what an adversary gains by compromising a component, and when an edge condition holds.

A graph connection alone never implies traversal. An edge may be attempted only when ALL of its
access conditions are satisfied by (a) environment flags, (b) properties of the source component, or
(c) capabilities the adversary has already gained earlier in the attack. All values are assumptions.
"""
from __future__ import annotations

from ..infrastructure.enums import NodeType as NT

# capabilities gained by compromising a component of a given type
CAPS_BY_TYPE = {
    NT.REMOTE_ACCOUNT: {"valid_credentials"},
    NT.VPN_GATEWAY: {"network_reachability"},
    NT.REMOTE_PORTAL: {"valid_credentials"},
    NT.EXTERNAL_PROVIDER: {"valid_credentials"},
    NT.IDENTITY_SERVICE: {"valid_credentials", "domain_trust", "admin_privilege"},
    NT.ADMIN_WORKSTATION: {"valid_credentials", "admin_privilege"},
    NT.APPLICATION_SERVER: {"valid_credentials"},
    NT.DATABASE: {"valid_credentials"},
    NT.FILE_SERVER: {"valid_credentials"},
    NT.BACKUP_SYSTEM: {"valid_credentials"},
    NT.BOUNDARY_GATEWAY: {"valid_credentials"},
    NT.SCADA_SERVER: {"valid_credentials", "controller_write_access"},
    NT.HMI: {"valid_credentials", "controller_write_access"},
    NT.ENGINEERING_WORKSTATION: {"valid_credentials", "engineering_privilege", "controller_write_access"},
    NT.PLC: {"controller_write_access"},
    NT.RTU: {"controller_write_access"},
}

ENVIRONMENTAL = {"network_reachability", "boundary_rule_permits", "maintenance_session_active",
                 "mfa_absent_or_bypassed"}
DEFAULT_ENV = {"boundary_rule_permits": True, "maintenance_session_active": False, "mfa_bypass": False}


def caps_for(node) -> set:
    return set(CAPS_BY_TYPE.get(node.node_type, set()))


def condition_status(cond, src_node, env, cap_time):
    """Return (satisfied, ready_time, reason). cap_time maps capability -> earliest time held."""
    if cond == "network_reachability":
        return True, 0.0, "link present and not isolated"
    if cond == "boundary_rule_permits":
        ok = env.get("boundary_rule_permits", True)
        return ok, 0.0, "firewall rule permits the crossing" if ok else "boundary rule blocks the crossing"
    if cond == "maintenance_session_active":
        ok = env.get("maintenance_session_active", False)
        return ok, 0.0, "a vendor maintenance session is active" if ok else "no active maintenance session"
    if cond == "mfa_absent_or_bypassed":
        ok = (src_node.security_controls.get("mfa", True) is False) or env.get("mfa_bypass", False)
        return ok, 0.0, "account has no multi-factor authentication" if ok else "multi-factor authentication blocks use"
    if cond in cap_time:
        return True, cap_time[cond], f"capability '{cond}' already gained"
    return False, 0.0, f"capability '{cond}' not yet gained"
