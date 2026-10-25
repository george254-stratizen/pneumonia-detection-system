"""Shared Streamlit pieces used by more than one page."""

from pathlib import Path

import streamlit as st

from modules.analysis import ROOT
from modules.report import build_pdf
from modules.results import FINAL_OPTIONS, get_result, save_diagnosis


def render_result_detail(result_id, user):
    d = get_result(result_id)
    if d is None:
        st.error("Result not found.")
        return

    st.subheader(f"{d['patient_number']} - {d['first_name']} {d['last_name']}")
    st.caption(f"Analysed {d['date']} (Nairobi time)  |  {d['file_name']}")

    if d["prediction"] == "PNEUMONIA":
        st.error(f"### AI prediction: PNEUMONIA ({d['confidence']:.1%} confidence)")
    else:
        st.success(f"### AI prediction: NORMAL ({d['confidence']:.1%} confidence)")
    if d["confidence"] < 0.70:
        st.warning("Low confidence. Review this image carefully and consider a repeat X-ray "
                   "or specialist opinion.")

    c1, c2, c3 = st.columns(3)
    for col, path, cap in [(c1, d["file_path"], "Original"),
                           (c2, d["processed_image_path"], "After CLAHE"),
                           (c3, d["heatmap_path"], "Grad-CAM")]:
        if path and (ROOT / path).exists():
            col.image(str(ROOT / path), caption=cap)
        else:
            col.caption(f"{cap}: image file not found")
    st.caption("The heatmap shows where the model looked. It is not a confirmed lesion location "
               "and can highlight areas outside the lungs.")

    st.markdown("#### Clinician diagnosis")
    if d["final_diagnosis"]:
        tag = "agrees with the AI" if d["agreed"] else "differs from the AI"
        st.info(f"**{d['final_diagnosis']}** ({tag}) - recorded by {d['diagnosed_by']} "
                f"on {d['diagnosis_date']}")

    default = d["final_diagnosis"] or d["prediction"]
    with st.form(f"diagnosis_{result_id}"):
        final = st.radio("Final diagnosis", FINAL_OPTIONS, index=FINAL_OPTIONS.index(default),
                         horizontal=True)
        notes = st.text_area("Clinical notes", value=d["diagnosis_notes"] or "")
        if st.form_submit_button("Save diagnosis", type="primary"):
            try:
                agreed = save_diagnosis(result_id, user["user_id"], final, notes)
                st.toast("Diagnosis saved (agrees with AI)." if agreed else "Diagnosis saved (overrides AI).")
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    pdf = build_pdf(d, user["name"])
    st.download_button("Download PDF report", pdf,
                       file_name=f"report_{d['patient_number']}_{result_id}.pdf",
                       mime="application/pdf")