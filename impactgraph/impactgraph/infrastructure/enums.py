"""Controlled vocabularies used across the ImpactGraph infrastructure model."""
from enum import Enum


class Zone(str, Enum):
    VENDOR = "vendor"
    IT = "it"
    OT = "ot"
    PHYSICAL = "physical"


class ComponentCategory(str, Enum):
    ACCESS = "access"                  # external access paths and identities
    IT_SERVICE = "it_service"          # enterprise servers and services
    IT_ENDPOINT = "it_endpoint"        # administrator / user endpoints
    OT_BOUNDARY = "ot_boundary"        # IT/OT boundary (DMZ) systems
    OT_SUPERVISORY = "ot_supervisory"  # SCADA, HMI, engineering systems
    OT_CONTROLLER = "ot_controller"    # PLCs and RTUs
    PROCESS_ASSET = "process_asset"    # physical pipeline assets


class NodeType(str, Enum):
    VPN_GATEWAY = "vpn_gateway"
    REMOTE_ACCOUNT = "remote_account"
    REMOTE_PORTAL = "remote_portal"
    EXTERNAL_PROVIDER = "external_provider"
    IDENTITY_SERVICE = "identity_service"
    APPLICATION_SERVER = "application_server"
    DATABASE = "database"
    FILE_SERVER = "file_server"
    BACKUP_SYSTEM = "backup_system"
    ADMIN_WORKSTATION = "admin_workstation"
    BOUNDARY_GATEWAY = "boundary_gateway"
    SCADA_SERVER = "scada_server"
    HMI = "hmi"
    ENGINEERING_WORKSTATION = "engineering_workstation"
    PLC = "plc"
    RTU = "rtu"
    PUMP_STATION = "pump_station"
    PIPELINE_SEGMENT = "pipeline_segment"
    BLOCK_VALVE = "block_valve"
    STORAGE_TANK = "storage_tank"
    TERMINAL = "terminal"
    DELIVERY_POINT = "delivery_point"


class Condition(str, Enum):
    NORMAL = "normal"
    DEGRADED = "degraded"
    COMPROMISED = "compromised"
    FAILED = "failed"
    ISOLATED = "isolated"


class Criticality(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EdgeType(str, Enum):
    NETWORK = "network"                    # network communication path
    AUTH = "auth"                          # authentication / access relationship
    CONTROL = "control"                    # control communication or actuation
    PHYSICAL_FLOW = "physical_flow"        # product flow between physical assets
    OPERATIONAL_DEP = "operational_dep"    # target needs source to operate
    SERVICE_DEP = "service_dep"            # target needs source's service


class IsolationKind(str, Enum):
    LOGICAL = "logical"    # firewall rule, account disable, link disconnect
    PHYSICAL = "physical"  # valve closure / physical separation


# --- Semantic groupings (kept explicit so relationship types are never confused) ---
# Edge direction convention:
#   NETWORK / AUTH / CONTROL : source -> target is the direction an adversary
#                              holding the source can move or act.
#   SERVICE_DEP / OPERATIONAL_DEP : source -> target means "failure of the source
#                              can degrade the target" (target depends on source).
#   PHYSICAL_FLOW : source -> target is the direction product flows.
ATTACK_TRAVERSABLE = frozenset({EdgeType.NETWORK, EdgeType.AUTH, EdgeType.CONTROL})
DEPENDENCY_TYPES = frozenset({EdgeType.SERVICE_DEP, EdgeType.OPERATIONAL_DEP})
