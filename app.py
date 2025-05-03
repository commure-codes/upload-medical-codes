# app.py
import streamlit as st
import requests
import pandas as pd
import os
from dotenv import load_dotenv
import io
import secrets # Make sure secrets is imported

# --- Configuration ---
load_dotenv() # Load backend credentials if needed locally, though ideally set in deployment env

# Get backend URL from environment variable or use default
BACKEND_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")
UPLOAD_ENDPOINT = f"{BACKEND_URL}/upload/"

# --- Basic Authentication for Streamlit ---
# WARNING: This is very basic protection for Streamlit.
def check_password():
    """Returns `True` if the user has entered the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        # Check if both username and password fields have been populated in session state
        if "username" in st.session_state and "password" in st.session_state:
            frontend_user = os.getenv("FRONTEND_USERNAME", "streamlit_user")
            frontend_pass = os.getenv("FRONTEND_PASSWORD", "streamlit_pass")

            # Perform the comparison
            if secrets.compare_digest(st.session_state["username"], frontend_user) and \
               secrets.compare_digest(st.session_state["password"], frontend_pass):
                st.session_state["password_correct"] = True
                st.session_state["login_attempted"] = True # Mark successful login
                # Clear password from memory after validation for security
                del st.session_state["password"]
                # Optionally clear username too, or keep it if needed later
                # del st.session_state["username"]
            else:
                st.session_state["password_correct"] = False
                st.session_state["login_attempted"] = True # Mark failed login attempt
        else:
            # Handle cases where callback runs before both fields are set (less likely with on_change, but safer)
            st.session_state["password_correct"] = False
            # Don't mark login_attempted here, as the user hasn't necessarily submitted yet

    # Initialize session state variables if they don't exist
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if "login_attempted" not in st.session_state:
        st.session_state["login_attempted"] = False # Track if a login was tried

    # Show login form if not authenticated
    if not st.session_state["password_correct"]:
        st.text_input("Username", key="username")
        # Use on_change for the password input to trigger the check upon entry/submission
        st.text_input(
            "Password",
            type="password",
            key="password",
            on_change=password_entered # Callback triggers when password input changes (usually on Enter or focus loss)
        )

        # Only show the error message *after* a login attempt has been made and failed
        if st.session_state["login_attempted"] and not st.session_state["password_correct"]:
            st.error("😕 User not known or password incorrect")
        return False # Not authenticated
    else:
        return True # Authenticated

# --- Streamlit App UI ---

st.set_page_config(page_title="Medical Code Uploader", layout="centered")
st.title("⚕️ Autonomous Medical Coding - Data Uploader")

# --- Authentication Gate ---
# Load frontend credentials from .env (or environment variables)
if not check_password():
    st.stop() # Do not render the rest of the app if not authenticated

# Only runs if check_password() returns True
st.success("Authentication successful!")

st.markdown("""
Upload your ICD or CPT code Excel files here.
The system will process the descriptions, generate embeddings,
and store them for later use.
""")

# --- User Inputs ---
code_type = st.selectbox(
    "Select Code Type:",
    ("ICD", "CPT"),
    help="Choose whether you are uploading ICD or CPT codes."
)

uploaded_file = st.file_uploader(
    f"Choose {code_type} Excel file (.xlsx, .xls)",
    type=['xlsx', 'xls'],
    help="Select the Excel file containing the codes (col A) and descriptions (col B)."
)

# --- Upload Button and Logic ---
if st.button(f"Upload and Process {code_type} Codes"):
    if uploaded_file is not None:
        backend_user = os.getenv("BACKEND_USERNAME")
        backend_pass = os.getenv("BACKEND_PASSWORD")

        if not backend_user or not backend_pass:
            st.error("Backend credentials are not configured in the frontend environment.")
        else:
            files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            payload = {'code_type': code_type}
            auth = (backend_user, backend_pass)

            st.info(f"Uploading {uploaded_file.name} ({code_type}) to the backend...")
            try:
                response = requests.post(
                    UPLOAD_ENDPOINT,
                    files=files,
                    data=payload,
                    auth=auth,
                    timeout=300
                )
                if response.status_code == 200:
                    st.success(f"✅ Success! Backend response: {response.json().get('message', 'OK')}")
                elif response.status_code == 401:
                     st.error("Authentication failed when contacting backend. Check backend credentials.")
                else:
                    try:
                        detail = response.json().get("detail", response.text)
                    except requests.exceptions.JSONDecodeError:
                        detail = response.text
                    st.error(f"❌ Error {response.status_code}: Failed to process file. Backend response: {detail}")
            except requests.exceptions.RequestException as e:
                st.error(f"🚨 Network Error: Could not connect to the backend at {BACKEND_URL}. Is it running? Error: {e}")
            except Exception as e:
                 st.error(f"An unexpected error occurred: {e}")
    else:
        st.warning("Please choose a file to upload first.")

# --- Optional: Display Sample Data ---
st.markdown("---")
st.subheader("Expected Excel Format")
st.markdown("The uploader expects an Excel file where:")
st.markdown("- **Column A:** Contains the codes (e.g., 'A000', '99213').")
st.markdown("- **Column B:** Contains the corresponding descriptions.")
st.markdown("*(Headers in the first row are optional but recommended)*")

sample_data = {
    'Code': ['A000', 'A0100', '99213'],
    'Description': ['Cholera due to Vibrio cholerae 01, biovar cholerae', 'Typhoid fever, unspecified','Office or other outpatient visit for the evaluation and management...']
}
st.dataframe(pd.DataFrame(sample_data))
