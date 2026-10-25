import streamlit as st

from modules.analysis import analyze_xray
from modules.patients import age_text, get_patient, search_patients
from modules.ui import render_result_detail

user = st.session_state["user"]
st.title("🩻 Upload X-ray & Analyse")
st.caption("AI decision support. The result is a second opinion, not a diagnosis.")


@st.cache_resource(show_spinner="Loading AI model...")
def get_engine():
    from modules.analysis import RealEngine
    return RealEngine()


# ---- 1. choose patient ----
q = st.text_input("Find patient (name, number or phone)")
patients = search_patients(q, limit=50)
if not patients:
    st.info("No matching patient. Register the patient first on the Patients page.")
    st.stop()

labels = {f"{p['patient_number']} - {p['first_name']} {p['last_name']}": p["patient_id"] for p in patients}
patient = get_patient(labels[st.selectbox("Patient", list(labels))])
st.write(f"**Age:** {age_text(patient['date_of_birth'])}  |  **Gender:** {patient['gender']}")

# ---- 2. upload ----
file = st.file_uploader("Chest X-ray (PNG or JPEG, max 10 MB)", type=["png", "jpg", "jpeg"])
if file is not None:
    st.image(file, caption="Uploaded image", width=300)

if st.button("Analyse X-ray", type="primary", disabled=file is None):
    try:
        with st.spinner("Analysing..."):
            st.session_state["last_result"] = analyze_xray(
                patient["patient_id"], user["user_id"], file.getvalue(), file.name, get_engine())
    except ValueError as e:
        st.error(str(e))
    except Exception as e:
        st.error(f"Analysis failed: {e}")

# ---- 3. result ----
r = st.session_state.get("last_result")
if r and r["patient_id"] == patient["patient_id"]:
    st.divider()
    render_result_detail(r["result_id"], user)