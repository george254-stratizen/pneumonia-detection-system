"""Shared Streamlit pieces used by more than one page."""

from pathlib import Path

import streamlit as st

from modules.analysis import ROOT
from modules.report import build_pdf
from modules.results import get_result


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
        st.warning("Low confidence result.")

    def show(col, path, cap):
        if path and (ROOT / path).exists():
            col.image(str(ROOT / path), caption=cap)
        else:
            col.caption(f"{cap}: image file not found")

    if d["prediction"] == "PNEUMONIA":
        c1, c2, c3 = st.columns(3)
        show(c1, d["file_path"], "Original")
        show(c2, d["processed_image_path"], "After CLAHE")
        show(c3, d["heatmap_path"], "Grad-CAM")
        st.caption("The heatmap shows where the model looked. It is not a confirmed lesion "
                   "location and can highlight areas outside the lungs.")
    else:
        c1, c2 = st.columns(2)
        show(c1, d["file_path"], "Original")
        show(c2, d["processed_image_path"], "After CLAHE")
        with st.expander("View model attention map (Grad-CAM)"):
            show(st, d["heatmap_path"], "Grad-CAM")
            st.caption("This shows what influenced the NORMAL prediction. It does not "
                       "indicate disease.")

    st.markdown("#### Diagnosis")
    if d["final_diagnosis"]:
        st.info(f"**{d['final_diagnosis']}** - recorded by {d['diagnosed_by']} on {d['diagnosis_date']}")
    else:
        st.info(f"**{d['prediction']}**")

    pdf = build_pdf(d, user["name"])
    st.download_button("Download PDF report", pdf,
                       file_name=f"report_{d['patient_number']}_{result_id}.pdf",
                       mime="application/pdf")