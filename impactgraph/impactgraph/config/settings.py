"""Central, documented configuration. Every weight here is an ASSUMPTION, not a calibrated value."""

SEED = 42
DB_PATH = "impactgraph.db"

# --- Risk model (see risk/risk_scoring.py for the formula)
RISK_LIKELIHOOD_WEIGHTS = {"simulation": 0.45, "evidence": 0.35, "exposure": 0.20}   # sum = 1
RISK_CONSEQUENCE_WEIGHTS = {"importance": 0.60, "downstream": 0.40}                    # sum = 1

# --- Residual operational impact (used by blast-radius, containment objective)
IMPACT_WEIGHTS = {"throughput": 0.40, "service": 0.20, "hazard": 0.25, "exposure": 0.15}  # sum = 1

# --- Containment objective  J(S) = E[impact | S] + LAMBDA * sum(cost(S)) / COST_REF
LAMBDA = 0.05
COST_REF = 10.0
MIN_CONTINUITY = 0.60        # isolation set must leave >= 60% of attack-free throughput
MAX_ISOLATIONS = 6
SEARCH_TRIALS = 300

# --- Monte Carlo
DEFAULT_TRIALS = 500
HOLDOUT_TRIALS = 2000

# --- Detection
ALERT_QUANTILE = 0.995       # calibrated anomaly score needed to count as suspicious
ALERT_PERSISTENCE = 2        # consecutive steps above threshold before an alert fires
EPISODE_STEPS = 240
ATTACK_ONSET_STEP = 60
STEPS_PER_HOP = 12
