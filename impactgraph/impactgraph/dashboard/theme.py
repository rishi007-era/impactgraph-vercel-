"""Visual identity: dark security-operations look. Colours encode meaning, never decoration."""
from __future__ import annotations

import streamlit as st

BG, PANEL, PANEL2, BORDER = "#0B1220", "#111A2E", "#16213A", "#243251"
TEXT, MUTED, ACCENT = "#E6EDF7", "#8FA3BF", "#22D3EE"
GOOD, WARN, BAD, MAGENTA = "#34D399", "#FBBF24", "#EF4444", "#E879F9"

ZONE_COLOR = {"vendor": "#A78BFA", "it": "#38BDF8", "ot": "#F59E0B", "physical": "#34D399"}
ZONE_LABEL = {"vendor": "ZONE 1  -  VENDOR / EXTERNAL ACCESS", "it": "ZONE 2  -  ENTERPRISE IT",
              "ot": "ZONE 3  -  OPERATIONAL TECHNOLOGY", "physical": "ZONE 4  -  PHYSICAL PIPELINE INFRASTRUCTURE"}
COND_COLOR = {"normal": "#1B2740", "degraded": "#FBBF24", "compromised": "#F97316", "failed": "#EF4444", "isolated": "#94A3B8"}
EDGE_COLOR = {"network": "#38BDF8", "auth": "#A78BFA", "control": "#F59E0B", "physical_flow": "#2DD4BF",
              "operational_dep": "#7C8DA8", "service_dep": "#7C8DA8"}
EDGE_LABEL = {"network": "Network", "auth": "Authentication", "control": "Control / actuation",
              "physical_flow": "Physical product flow", "operational_dep": "Operational dependency", "service_dep": "Service dependency"}
FONT = "Inter, Segoe UI, Roboto, sans-serif"


def inject_css():
    st.markdown(f"""
<style>
html, body, [class*="css"] {{ font-family: {FONT}; }}
.block-container {{ padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1500px; }}
section[data-testid="stSidebar"] {{ background: linear-gradient(180deg,#0E1730 0%,#0B1220 100%); border-right: 1px solid {BORDER}; }}
h1,h2,h3 {{ letter-spacing: -0.01em; }}
.ig-hero {{ background: radial-gradient(1200px 300px at 0% 0%, rgba(34,211,238,.18), transparent 60%),
            linear-gradient(135deg,#111A2E 0%,#0E1730 100%); border:1px solid {BORDER}; border-radius:18px; padding:22px 28px; margin-bottom:16px; }}
.ig-hero h1 {{ margin:0; font-size:1.9rem; font-weight:800; }}
.ig-hero p {{ margin:6px 0 10px 0; color:{MUTED}; font-size:.98rem; }}
.ig-badge {{ display:inline-block; padding:3px 10px; border-radius:999px; font-size:.72rem; font-weight:700; letter-spacing:.04em;
            margin-right:6px; border:1px solid; }}
.ig-kpi {{ background:{PANEL}; border:1px solid {BORDER}; border-radius:14px; padding:14px 16px; height:100%; position:relative; overflow:hidden; }}
.ig-kpi:before {{ content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:var(--c); }}
.ig-kpi .l {{ color:{MUTED}; font-size:.72rem; text-transform:uppercase; letter-spacing:.08em; font-weight:600; }}
.ig-kpi .v {{ font-size:1.75rem; font-weight:800; line-height:1.15; margin-top:2px; }}
.ig-kpi .s {{ color:{MUTED}; font-size:.78rem; margin-top:2px; }}
.ig-card {{ background:{PANEL}; border:1px solid {BORDER}; border-radius:14px; padding:14px 18px; margin-bottom:12px; }}
.ig-card h4 {{ margin:0 0 6px 0; font-size:.95rem; }}
.ig-note {{ background:rgba(251,191,36,.08); border:1px solid rgba(251,191,36,.35); color:#FCE7A8; border-radius:10px; padding:8px 12px; font-size:.82rem; }}
.ig-advice {{ background:rgba(232,121,249,.08); border:1px solid rgba(232,121,249,.4); color:#F5D0FE; border-radius:10px; padding:8px 12px; font-size:.82rem; }}
.ig-step {{ background:{PANEL2}; border-left:3px solid {MAGENTA}; border-radius:8px; padding:8px 12px; margin:6px 0; font-size:.88rem; }}
.ig-legend span {{ display:inline-block; margin-right:14px; font-size:.78rem; color:{MUTED}; }}
.ig-dot {{ display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:5px; vertical-align:middle; border:2px solid; }}
.stTabs [data-baseweb="tab"] {{ font-weight:600; }}
div[data-testid="stMetric"] {{ background:{PANEL}; border:1px solid {BORDER}; border-radius:12px; padding:10px 14px; }}
</style>""", unsafe_allow_html=True)


def badge(text, color=ACCENT):
    return f'<span class="ig-badge" style="color:{color};border-color:{color};background:{color}1A">{text}</span>'


def hero(title, subtitle, badges=()):
    st.markdown(f'<div class="ig-hero"><h1>{title}</h1><p>{subtitle}</p>{"".join(badges)}</div>', unsafe_allow_html=True)


def kpi(label, value, sub="", color=ACCENT):
    return f'<div class="ig-kpi" style="--c:{color}"><div class="l">{label}</div><div class="v">{value}</div><div class="s">{sub}</div></div>'


def kpi_row(items):
    cols = st.columns(len(items))
    for c, it in zip(cols, items):
        c.markdown(kpi(*it), unsafe_allow_html=True)


def note(text):
    st.markdown(f'<div class="ig-note">{text}</div>', unsafe_allow_html=True)


def advisory(text):
    st.markdown(f'<div class="ig-advice">{text}</div>', unsafe_allow_html=True)


def style_fig(fig, height=420, legend=True):
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(17,26,46,0.0)",
                      font=dict(family=FONT, color=TEXT, size=12), height=height, margin=dict(l=10, r=10, t=40, b=10),
                      showlegend=legend, legend=dict(bgcolor="rgba(0,0,0,0)"))
    fig.update_xaxes(gridcolor="rgba(143,163,191,0.12)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(143,163,191,0.12)", zeroline=False)
    return fig


def zone_legend():
    items = "".join(f'<span><i class="ig-dot" style="border-color:{c}"></i>{z.upper()}</span>' for z, c in ZONE_COLOR.items())
    items += "".join(f'<span><i class="ig-dot" style="background:{COND_COLOR[k]};border-color:{COND_COLOR[k]}"></i>{k}</span>'
                     for k in ("compromised", "failed", "degraded"))
    st.markdown(f'<div class="ig-legend">{items}</div>', unsafe_allow_html=True)
