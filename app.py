import streamlit as st
from dataclasses import dataclass, field
from typing import Dict, Any, List
import time

@dataclass
class BorrowerApplication:
  company_id: str
  loan_requested: float
  reported_credits: float
  verified_credits: float
  registry_source: str
  project_type: str
  meta: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Decision:
  status: str #approved, approved with penalty, rejected#
  reason: str
  interest_rate_apr: float
  required_credits: float
  greenwashing_score: float
  audit_ref: str

DEFAULT_REQUIRED_CREDITS_PER_1K = 10.0
GREENWASH_GAP_TOLERANCE = 0.10
REGISTRY_QUALITY_WEIGHTS = {
    "Gold Standard": 0.95,
    "Verra": 0.90,
    "Other": 0.80
}

PROJECT_RISK_WEIGHTS = {
    "Reforestation": 0.90,
    "Renewable": 0.95,
    "Cookstove": 0.85,
    "Other": 0.80
}
BASE_RATE = 0.06
PENALTY_RATE_STEP = 0.03


class BiologyValidator:
  def score(self, app: BorrowerApplication) -> float:
    score = 1.0
    if app.project_type.lower() == "reforestation":
      score *= 0.95
    if app.meta.get("has_recent_remote_sensing", False):
      score *= 1.00
    else:
      score *= 0.90
    if app.meta.get("soil_tests_ok", True) is False:
      score *= 0.80
    return max(0.0, min(1.0, score))

class GreenLoanContract:
  def __init__(self,
               required_credits: float = DEFAULT_REQUIRED_CREDITS_PER_1K,
               gap_tolerance: float = GREENWASH_GAP_TOLERANCE):
    self.required_credits_per_1k = required_credits
    self.gap_tolerance = gap_tolerance
    self.audit_log: List[Dict[str, Any]] = []
    self.bio = BiologyValidator()

  def required_credits(self, loan_requested: float) -> float:
    return (loan_requested / 1000) * self.required_credits_per_1k

  def greenwash_signals(self, app: BorrowerApplication) -> float:
    if app.verified_credits > 0:
        gap = max(0.0, (app.reported_credits - app.verified_credits) / app.verified_credits)
    else:
        gap = 1.0
    reg_q = REGISTRY_QUALITY_WEIGHTS.get(app.registry_source, REGISTRY_QUALITY_WEIGHTS["Other"])
    proj_r = PROJECT_RISK_WEIGHTS.get(app.project_type, PROJECT_RISK_WEIGHTS["Other"])
    bio_q = self.bio.score(app)
    return {"gap": gap, "registry_quality": reg_q, "project_quality": proj_r, "biology_confidence": bio_q}


  def greenwashing_score(self, signals: Dict[str, Any]) -> float:
    gap_component = min(1.0, signals["gap"] / self.gap_tolerance)
    quality_component = 1.0 - 0.5 * (signals["registry_quality"] + signals["project_quality"])
    bio_component = 1.0 - signals["biology_confidence"]
    raw = 0.5 * gap_component + 0.3 * quality_component + 0.2 * bio_component
    return round(100.0 * max(0.0, min(1.0, raw)), 2)

  def price(self, base_rate: float, score: float) -> float:
      if score < 25:  return base_rate
      if score < 50:  return base_rate + PENALTY_RATE_STEP
      if score < 75:  return base_rate + 2 * PENALTY_RATE_STEP
      return base_rate + 3 * PENALTY_RATE_STEP

  def _log(self, app: BorrowerApplication, signals: Dict[str, Any], decision: str) -> str:
      ref = f"evt_{int(time.time()*1000)}_{app.company_id}"
      self.audit_log.append({
            "ref": ref,
            "company_id": app.company_id,
            "decision": decision,
            "signals": signals,
            "timestamp": int(time.time()),
            "hash_like": hex(abs(hash((app.company_id, decision))) % (1<<64))
        })
      return ref

  def evaluate(self, app: BorrowerApplication) -> Decision:
      req = self.required_credits(app.loan_requested)
      signals = self.greenwash_signals(app)
      score = self.greenwashing_score(signals)

      has_sufficient_verified = app.verified_credits >= req
      mismatch_ok = signals["gap"] <= self.gap_tolerance

      if has_sufficient_verified and mismatch_ok and score < 50:
            rate = self.price(BASE_RATE, score)
            ref = self._log(app, signals, "APPROVED")
            return Decision("APPROVED", "Credits sufficient and clean signals", rate, req, score, ref)

      if has_sufficient_verified and score < 75:
            rate = self.price(BASE_RATE, score)
            ref = self._log(app, signals, "APPROVED_WITH_PENALTY")
            return Decision("APPROVED_WITH_PENALTY", "Credits sufficient with moderate greenwashing risk", rate, req, score, ref)

      ref = self._log(app, signals, "REJECTED")
      return Decision("REJECTED", "Insufficient verified credits or high greenwashing risk", 0.0, req, score, ref)










def run_cli():
    contract = GreenLoanContract()
    print("ESG Green Loan Evaluator")
    company = input("Company name: ").strip()
    loan = float(input("Loan requested in euros: ").strip())
    reported = float(input("Reported carbon credits: ").strip())
    verified = float(input("Verified carbon credits: ").strip())
    registry = input("Registry Gold Standard or Verra or Other: ").strip() or "Other"
    project = input("Project type Reforestation or Renewable or Cookstove or Other: ").strip() or "Other"


    rs = input("Recent remote sensing evidence y or n: ").strip().lower() == "y"
    soil = input("Soil tests ok y or n: ").strip().lower() != "n"


    app = BorrowerApplication(
      company_id=company,
      loan_requested=loan,
      reported_credits=reported,
      verified_credits=verified,
      registry_source=registry,
      project_type=project,
      meta={"has_recent_remote_sensing": rs, "soil_tests_ok": soil}
    )
    d = contract.evaluate(app)
    print("\nResult")
    print(f"Decision: {d.status}")
    print(f"Reason: {d.reason}")
    print(f"Required credits: {d.required_credits:.2f}")
    print(f"APR: {d.interest_rate_apr:.2%}")
    print(f"Greenwashing score: {d.greenwashing_score}")
    print(f"Audit ref: {d.audit_ref}")

import streamlit as st

st.set_page_config(page_title="ESG Green Loan Evaluator", layout = "wide")
if "contract" not in st.session_state:
    st.session_state.contract = GreenLoanContract()
if "runs" not in st.session_state:
    st.session_state.runs = []
st.title("ESG Green Loan Evaluator")
st.caption("Interactive prototype. Enter inputs and get an instant decision.")

with st.sidebar: 
  st.header("Quick presets") 
  if st.button("Load example: Maersk"):
    st.session_state.prefill = dict(
      company="Maersk", loan=1000.0, reported=3000.0, verified=3500.0,
      registry="Other", project="Other", remote=False, soil_ok=True
    )
  if st.button("Load example: Reforestation high risk"):
    st.session_state.prefill = dict(
        company = "Demo Forest Ltd", loan=250000.0, reported=500.0, verified=200.0,
        registry="Other", project="Reforestation", remote=False, soil_ok=False
    )

pf=st.session_state.get("prefill", {})
company = pf.get("company", "DemCo")
loan = pf.get("loan", 1000.0)
reported = pf.get("reported", 1000.0)
verified = pf.get("verified", 800.0)
registry = pf.get ("registry", "Other") 
project = pf.get("project", "Other")
remote = pf.get("remote", False)
soil_ok = pf.get("soil_ok", True)

with st.form("loan_form", clear_on_submit = False) :
    st.subheader("Applicant inputs")
    c1, c2 = st.columns(2) 
    with c1: 
        company = st.text_input("Company name", value=company)
        loan = st.number_input("Loan requested (€)", min_value=0.0, step=1000.0, value=loan)
        registry = st.selectbox("Registry", ["Gold Standard", "Verra", "Other"], index=["Gold Standard","Verra","Other"].index(registry))
        project = st.selectbox("Project type", ["Reforestation", "Renewable", "Cookstove", "Other"], index=["Reforestation","Renewable","Cookstove","Other"].index(project))
    with c2: 
        reported = st.number_input("Reported carbon credits", min_value=0.0, value=reported)
        verified = st.number_input("Verified carbon credits", min_value=0.0, value=verified)
        remote = st.checkbox("Recent remote sensing evidence", value=remote)
        soil_ok = st.checkbox("Soil tests OK", value=soil_ok)

    submitted = st.form_submit_button("Evaluate")

if submitted: 
    app_obj = BorrowerApplication(
        company_id = company, 
        loan_requested=loan, 
        reported_credits=reported,
        verified_credits=verified,
        registry_source=registry,
        project_type=project,
        meta={"has_recent_remote_sensing": remote, "soil_tests_ok": soil_ok}
    )
    d = st.session_state.contract.evaluate(app_obj)

    st.success("Decision ready")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Decision", d.status)
    col2.metric("APR", f"{d.interest_rate_apr*100:.2f}%")
    col3.metric("Required credits", f"{d.required_credits:.2f}")
    col4.metric("Greenwashing score", f"{d.greenwashing_score:.2f}")

    st.write(f"**Reason:** {d.reason}")
    with st.expander("Signals used in scoring"):
        st.json(st.session_state.contract.greenwash_signals(app_obj))

    st.session_state.runs.append({
        "company": company,
        "loan_eur": loan,
        "reported": reported,
        "verified": verified,
        "registry": registry,
        "project": project,
        "remote": remote,
        "soil_ok": soil_ok,
        "decision": d.status,
        "apr": d.interest_rate_apr,
        "required_credits": d.required_credits,
        "greenwashing_score": d.greenwashing_score,
        "audit_ref": d.audit_ref,
    })
runs = st.session_state.get("runs",[])
if st.session_state.runs:
    st.subheader("Your evaluations")
    st.dataframe(runs, use_container_width=True)

    import json, io
    buf = io.StringIO()
    json.dump(runs, buf, indent=2)

    st.download_button(
      "Download results as JSON", 
      data=buf.getvalue(), 
      file_name="evaluations.json", 
      mime="application/json"
    )

    if st.button("Clear history"):
        st.session_state.runs = []
        st.rerun()
      


