import math 
import time
import uuid
import pandas as pd
import streamlit as st

st.set_page_config(
  page_title="ESG Green Loan Evaluator", 
  page_icon = "🍀",
  layout="wide"
)

st.markdown("""
<style>
body {
  background-color: #c2d8c1;
  color: #365e30;
}
[data-testid="stAppViewContainer"] {
  background: linear-gradient(to right, #c2d8c1, #ffffff);
}
[data-testid="stSidebar"] {
  background-color: #a6daa6;
}
</style>
""", unsafe_allow_html=True)

/* Remove default padding for a tighter layout */
.block-container {padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1200px}

/* Headings */
h1, h2, h3 {letter-spacing: 0.2px}

/* KPI cards */
.card {
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06);
  background: white;
}
.card.good {border-color: rgba(16,185,129,0.35)}
.card.bad {border-color: rgba(239,68,68,0.35)}
.card.neutral {border-color: rgba(59,130,246,0.35)}

/* Pills */
.pill {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.85rem;
  background: rgba(0,0,0,0.06);
}
.pill.ok {background: rgba(16,185,129,0.12)}
.pill.warn {background: rgba(245,158,11,0.14)}
.pill.err {background: rgba(239,68,68,0.14)}

/* Result banner */
.result-ok {background: linear-gradient(90deg, rgba(16,185,129,0.12), transparent); border-left: 6px solid #10b981; padding: 14px 16px; border-radius: 10px;}
.result-bad {background: linear-gradient(90deg, rgba(239,68,68,0.12), transparent); border-left: 6px solid #ef4444; padding: 14px 16px; border-radius: 10px;}
.result-warn {background: linear-gradient(90deg, rgba(245,158,11,0.12), transparent); border-left: 6px solid #f59e0b; padding: 14px 16px; border-radius: 10px;}

/* Small text */
.small {font-size: 0.82rem; color: #666}
</style>
""", unsafe_allow_html=True)


REGISTRY_WEIGHTS = {
    "Gold Standard": 1.00,
    "Verra": 0.95,
    "Other": 0.80,
    "None": 0.60,
}

PROJECT_WEIGHTS = {
    "Reforestation": 1.00,
    "Renewable": 0.90,
    "Cookstove": 0.85,
    "Other": 0.80,
    "None": 0.70,
}

def required_credits_eur(loan_eur: float, rule_per_1000: float = 10.0) -> float:
    return round((loan_eur / 1000.0) * rule_per_1000, 2)

def greenwashing_score(verified, reported, registry, project, remote, soil):
    if verified < 0: verified = 0
    base = 5.0

    gap = max(reported - verified, 0)
    if reported > 0:
        gap_ratio = gap / max(reported, 1e-6)
    else:
        gap_ratio = 0.0
    base += 2.0 * max(0, 1 - min(gap_ratio, 1))

    base += 1.2 * REGISTRY_WEIGHTS.get(registry, 0.8)
    base += 1.0 * PROJECT_WEIGHTS.get(project, 0.8)

    if remote: base += 0.5
    if soil: base += 0.3

    return round(max(0.0, min(10.0, base - 2.5)), 1)

def apr_from_score(base_apr=6.0, score=7.0, registry="Other", remote=False, soil=False):
    apr = base_apr
    if registry in ["Gold Standard", "Verra"]:
        apr -= 0.25
    if remote:
        apr -= 0.10
    if soil:
        apr -= 0.10
    if score >= 8.5:
        apr -= 0.25
    if score < 5.0:
        apr += 0.50
    return round(max(0.0, apr), 2)

def decision_text(verified, needed):
    if verified >= needed:
        return "APPROVED", "Credits sufficient and clean signals"
    short = round(needed - verified, 2)
    return "REJECTED", f"Insufficient verified credits. Shortfall {short}"

def new_audit_ref(company):
    return f"evt_{int(time.time()*1000)}_{company.replace(' ', '')}"


st.title("🌱 ESG Green Loan Evaluator")
st.caption("Professional demo that screens borrowers using verified environmental data and transparent rules")

with st.sidebar:
    st.subheader("Demo presets")
    preset = st.selectbox("Load example", ["None", "Maersk 2022 style", "Tech company example"])
    if preset == "Maersk 2022 style":
        default_company = "Maersk"
        default_loan = 1000
        default_reported = 3000
        default_verified = 3500
        default_registry = "Other"
        default_project = "Other"
        default_remote = False
        default_soil = True
    elif preset == "Tech company example":
        default_company = "Microsoft"
        default_loan = 250000
        default_reported = 1400000
        default_verified = 1200000
        default_registry = "Gold Standard"
        default_project = "Reforestation"
        default_remote = True
        default_soil = False
    else:
        default_company = ""
        default_loan = 0
        default_reported = 0
        default_verified = 0
        default_registry = "Other"
        default_project = "Other"
        default_remote = False
        default_soil = False

st.write("")
st.markdown("### Borrower input")

with st.form("loan_form"):
    c1, c2, c3 = st.columns([2,1,1])
    with c1:
        company = st.text_input("Company name", value=default_company, placeholder="Enter legal entity name")
    with c2:
        loan_eur = st.number_input("Loan requested in euros", min_value=0.0, value=float(default_loan), step=100.0)
    with c3:
        project = st.selectbox("Project type", ["Reforestation", "Renewable", "Cookstove", "Other", "None"], index=["Reforestation","Renewable","Cookstove","Other","None"].index(default_project))

    c4, c5, c6 = st.columns(3)
    with c4:
        reported = st.number_input("Reported carbon credits", min_value=0.0, value=float(default_reported), step=100.0)
    with c5:
        verified = st.number_input("Verified carbon credits", min_value=0.0, value=float(default_verified), step=100.0)
    with c6:
        registry = st.selectbox("Registry", ["Gold Standard", "Verra", "Other", "None"], index=["Gold Standard","Verra","Other","None"].index(default_registry))

    c7, c8 = st.columns(2)
    with c7:
        remote = st.toggle("Recent remote sensing evidence", value=default_remote, help="Satellite monitoring or similar")
    with c8:
        soil = st.toggle("Soil tests ok", value=default_soil, help="Field measurements validated")

    submitted = st.form_submit_button("Evaluate", use_container_width=True)

if submitted:
    needed = required_credits_eur(loan_eur, rule_per_1000=10.0)
    score = greenwashing_score(verified, reported, registry, project, remote, soil)
    apr = apr_from_score(6.0, score, registry, remote, soil)
    decision, reason = decision_text(verified, needed)
    audit = new_audit_ref(company or "Unknown")

    css_class = "result-ok" if decision == "APPROVED" else "result-bad"
    st.markdown(f"""<div class="{css_class}">
    <strong>Decision</strong> {decision} • <span class="small">{reason}</span>
    </div>""", unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""<div class="card neutral"><div class="small">Required credits</div>
        <h3>{needed}</h3></div>""", unsafe_allow_html=True)
    with k2:
        badge = "pill ok" if verified >= needed else "pill err"
        st.markdown(f"""<div class="card neutral"><div class="small">Verified credits</div>
        <h3>{verified}</h3><span class="{badge}">{'meets policy' if verified>=needed else 'shortfall'}</span></div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div class="card neutral"><div class="small">Greenwashing score</div>
        <h3>{score} / 10</h3></div>""", unsafe_allow_html=True)
    with k4:
        st.markdown(f"""<div class="card {'good' if decision=='APPROVED' else 'bad'}"><div class="small">APR</div>
        <h3>{apr}%</h3></div>""", unsafe_allow_html=True)

    data = {
        "Company name": [company],
        "Loan requested (€)": [loan_eur],
        "Reported credits": [reported],
        "Verified credits": [verified],
        "Registry": [registry],
        "Project type": [project],
        "Remote sensing evidence": ["Yes" if remote else "No"],
        "Soil tests ok": ["Yes" if soil else "No"],
        "Decision": [decision],
        "Reason": [reason],
        "Required credits": [needed],
        "APR": [f"{apr}%"],
        "Greenwashing score": [score],
        "Audit ref": [audit],
    }
    df = pd.DataFrame(data)
    st.write("")
    st.markdown("#### Evaluation snapshot")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.write("")
    st.markdown("#### Auto generated audit note")
    md = f"""**Company:** {company or 'N/A'}

**Loan requested (€):** {loan_eur:,.2f}
**Claimed credits:** {reported:,.0f}
**Verified credits:** {verified:,.0f}
**Registry:** {registry}
**Project type:** {project}
**Remote sensing:** {"Yes" if remote else "No"}
**Soil tests:** {"Yes" if soil else "No"}
**Decision:** {decision}
**Reason:** {reason}
**Required credits:** {needed:,.2f}
**APR:** {apr}%
**Greenwashing score:** {score} out of 10
**Audit ref:** `{audit}`"""
    st.code(md, language="markdown")

    st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"), file_name=f"evaluator_{audit}.csv")
    st.download_button("Download audit note", md.encode("utf-8"), file_name=f"audit_{audit}.md")
with st.expander("How this works"):
    st.markdown("""
**One minute script**
This evaluator compares what a company reports to what is verified in public registries.
It calculates the credits needed for the loan size.
It checks verification quality and evidence signals.
It outputs decision, APR, and a greenwashing score.
An audit note is generated for transparency.

**Policy defaults**
Requirement equals 10 credits per 1,000 EUR of loan.
Registry quality adjusts score and APR.
Remote sensing and soil tests give small positive adjustments.
""")

st.write("")
st.markdown('<span class="small">Prototype for academic demonstration. Not investment advice.</span>', unsafe_allow_html=True)



