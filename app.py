import uuid
from azure.ai.documentintelligence.models import ContentFormat, AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from openai import AzureOpenAI # Use the Azure-specific client
from google.oauth2 import service_account
from google.cloud import aiplatform
from google.cloud import storage
from google.cloud import documentai_v1 as documentai
from google.cloud import dlp_v2
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from st_supabase_connection import SupabaseConnection
import hashlib # For password hashing
import html # Used to escape markdown characters
import io
from docx.enum.style import WD_STYLE_TYPE
from pinecone import Pinecone
import pickle
import streamlit as st
import os
import re
import fitz  # PyMuPDF
import faiss
import json
import requests
import markdown
import numpy as np
from datetime import datetime
from PyPDF2 import PdfReader
from docx import Document
from docx.shared import Pt, Inches
from sentence_transformers import SentenceTransformer
from collections import defaultdict
import tempfile
import base64
from pathlib import Path
import streamlit.components.v1 as components
import pandas as pd
from io import BytesIO
from openai import OpenAI
import pdfplumber
import yfinance as yf
from typing import List, Dict, Tuple
from bs4 import BeautifulSoup
from utils import format_report_as_html
from PIL import Image, ImageDraw, ImageFont # Make sure PIL imports are at the top
from docx.enum.text import WD_ALIGN_PARAGRAPH
from jinja2 import Template
import toml


# --- GLOBAL CLIENT INITIALIZATION ---
# This code runs only once when the app starts
try:
    openai_client = AzureOpenAI(
        api_key=os.environ.get("AZURE_OPENAI_KEY"),
        api_version="2024-02-01",  # Match your API version
        azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
        # The deployed model name is CRITICAL here
        azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
    )
except KeyError as e:
    st.error(f"Configuration error: Missing Azure secret: {e}. Please check your secrets.toml file.")
    st.stop()

# --- Must be the first st.* command ---
st.set_page_config(
    page_title="ARANC'AI'",
    page_icon="📈",  # Adds a browser tab icon
    layout="wide"
)




st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap');

/* 1. Apply Poppins font everywhere */
html, body, * {
    font-family: 'Poppins', sans-serif !important;
}

/* 2. Fine-tune main content spacing */
.block-container {
    padding-top: 1rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}

/* 3. Sidebar tweaks */
[data-testid="stSidebar"] h1 {
    font-size: 1.3rem !important;
    margin-top: 0.5rem !important;
    margin-bottom: 0 !important;
}
[data-testid="stSidebarUserContent"] {
    padding-top: 1rem !important;
}

/* 4. Main page title alignment */
h1.stTitle {
    margin-top: 0.5rem !important;
    font-size: 1.0rem !important;  /* 👈 increase font size here */
    font-weight: 700 !important;
}

/* 5. Logo positioning - fixed */
.aranca-logo {
    position: absolute;
    top: 0.75rem !important;
    right: 2rem !important;
    height: 44px !important;
    display: flex;
    align-items: center;
    z-index: 9999;
}

/* 6. Header and Title styling */
h1, h2, h3, .stTitle, .stHeader {
    font-family: 'Poppins', sans-serif !important;
    font-weight: 600 !important;
    line-height: 1.25;
    color: #1e1e1e;
    margin-top: 1.5rem;
    margin-bottom: 0.5rem;
}

/* 7. Radio button enhancements */
div[data-baseweb="radio"] > label {
    display: block;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 10px 15px;
    margin-bottom: 5px;
    transition: background-color 0.2s ease, border-color 0.2s ease;
}
div[data-baseweb="radio"] > label > div:first-child {
    display: none;
}
div[data-baseweb="radio"] > div[data-checked="true"] > label {
    background-color: #e6f1f6;
    border-color: #00416A;
    font-weight: 600;
}
div[data-baseweb="radio"] > div:not([data-checked="true"]) > label:hover {
    background-color: #f0f2f6;
}

/* 8. Report styling */
.report-container {
    font-family: 'Poppins', sans-serif !important;
    color: #333;
}
.report-container h1, .report-container h2, .report-container h3 {
    color: #00416A;
    border-bottom: 2px solid #00416A;
    padding-bottom: 10px;
    margin-top: 30px;
}
.report-container .summary-cards {
    display: flex;
    flex-wrap: wrap;
    gap: 20px;
    justify-content: space-around;
    margin-top: 20px;
}
.report-container .card {
    background-color: #f9f9f9;
    border-left: 5px solid;
    border-radius: 8px;
    padding: 20px;
    flex-basis: 300px;
    flex-grow: 1;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
.report-container .card.base { border-color: #00416A; }
.report-container .card.bull { border-color: #006400; }
.report-container .card.bear { border-color: #8B0000; }
.report-container .card-title {
    font-size: 1.2em;
    font-weight: bold;
    margin-bottom: 10px;
}
.report-container .card-value {
    font-size: 2.5em;
    font-weight: bold;
    color: #00416A;
}
.report-container .card-upside {
    font-size: 1.2em;
    margin-top: 10px;
}
.report-container .bull-text { color: #006400; }
.report-container .bear-text { color: #8B0000; }
.report-container .justification {
    font-size: 0.9em;
    color: #555;
    font-style: italic;
}
.memo-title {
    font-size: 1.75rem;
    font-weight: 600;
    color: #212529;
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 40px;
    margin-bottom: 15px;
}
.memo-container {
    background-color: #f8f9fa;
    padding: 25px;
    border-radius: 8px;
    line-height: 1.65;
    font-size: 1em;
    color: #343a40;
    margin-bottom: 40px;
}
.report-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 15px;
    margin-bottom: 25px;
    font-size: 0.95em;
    border: none;
}
.report-table th, .report-table td {
    padding: 12px 15px;
    text-align: right;
    border-bottom: 1px solid #e0e0e0;
}
.report-table th {
    background-color: #f9f9f9;
    color: #333;
    font-weight: 600;
    text-align: right;
    border-bottom: 2px solid #00416A;
}
.report-table tr:hover {
    background-color: #f5f5f5;
}

.welcome-subtitle {
    font-size: 1.5rem !important;; /* Adjust this value as needed */
    font-weight: 700;
    color: #4a4a4a;
    margin-top: -0.5rem; /* Optional: Reduces space below main title */
    margin-bottom: 1rem;
}

/* 9. Hide ALL default tooltips within the sidebar */
[data-testid="stSidebar"] div[role="tooltip"] {
    display: none !important;
}

/* Align header and logo inline, cleanly */
h1 {
    display: inline-block;
    vertical-align: middle;
    font-size: 2rem !important;
    margin-top: 1.2rem !important;
    margin-bottom: 0.75rem !important;
}

.block-container {
    padding-top: 4.5rem !important; /* Increased from 1rem to 4rem */
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}
.aranca-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;  /* Aligns everything at the top */
    margin-top: 0rem;
    padding-top: 0.5rem;
}

.aranca-title {
    font-size: 3.0rem !important;
    font-weight: 700;
    color: #1e1e1e;
    margin: 0;
    padding-top: 0.25rem;
    line-height: 1.2;
}

.aranca-logo {
    padding-top: 0rem;
    height: 40px;
}
.aranca-logo img {
    height: 38px;
    object-fit: contain;
}

/* ADD THIS CODE */
[data-testid="stSidebarCollapseButton"] {
    display: none;
}

/* 10. Tariff Tracker Styles */
.report-card {
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-left: 5px solid #00416A;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}
.report-card h3 {
    margin-top: 0;
    color: #00416A;
}
.report-card table {
    width: 100%;
    border-collapse: collapse;
}
.report-card th, .report-card td {
    padding: 10px 15px;
    text-align: left;
    border-bottom: 1px solid #e0e0e0;
    vertical-align: top;
}
.report-card th {
    background-color: #f9f9f9;
}
.report-card ul {
    padding-left: 20px;
    margin-top: 0;
}

</style>
""", unsafe_allow_html=True)

def get_base64_logo_image(path="logo.png"):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

# Define this before using in st.markdown
logo_base64 = get_base64_logo_image("logo.png")


st.markdown(
    f"""
    <div class="aranca-header">
        <div class="aranca-title">Welcome to ARANC'AI'</div>
        <div class="aranca-logo">
            <img src="data:image/png;base64,{logo_base64}" alt="Aranca Logo">
        </div>
    </div>
    """,
    unsafe_allow_html=True
)


# ==============================================================================
# 0. USER AUTHENTICATION (MODIFIED)
# ==============================================================================


# Initialize the Supabase connection
conn = st.connection("supabase", type=SupabaseConnection)

# --- New Database Functions for Whitelist ---
def get_whitelist_db():
    """Fetches whitelisted emails from the Supabase database."""
    rows = conn.client.table("whitelist").select("email").execute()
    return [row['email'] for row in rows.data]

def add_to_whitelist_db(email: str):
    """Adds a new email to the whitelist table."""
    conn.client.table("whitelist").insert([{"email": email}]).execute()

def remove_from_whitelist_db(email: str):
    """Removes an email from the whitelist table."""
    conn.client.table("whitelist").delete().eq("email", email).execute()

# --- New Database Functions for Users ---
def get_users_db():
    """Fetches user data from the Supabase database."""
    rows = conn.client.table("users").select("email, password_hash").execute()
    # Return an empty DataFrame with correct columns if there's no data
    if not rows.data:
        return pd.DataFrame(columns=['email', 'password_hash'])
    return pd.DataFrame(rows.data)

def add_user_db(email: str, hashed_password: str):
    """Adds a new user to the users table."""
    conn.client.table("users").insert([{"email": email, "password_hash": hashed_password}]).execute()

# --- Password Hashing ---
def hash_password(password):
    """Hashes a password using SHA-256."""
    return hashlib.sha256(str.encode(password)).hexdigest()

def verify_password(stored_password_hash, provided_password):
    """Verifies a provided password against a stored hash."""
    return stored_password_hash == hash_password(provided_password)

# --- Authentication UI ---
def authentication_ui():
    """Handles the login and sign-up UI using the Supabase database."""
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    if not st.session_state['logged_in']:
        choice = st.selectbox("Login or Sign Up", ["Login", "Sign Up"])

        if choice == "Login":
            st.subheader("Login")
            email = st.text_input("Email Address")
            password = st.text_input("Password", type="password")
            if st.button("Login"):
                user_db = get_users_db() # UPDATED to use database function
                if not user_db.empty and email in user_db["email"].values:
                    user_data = user_db[user_db["email"] == email].iloc[0]
                    if verify_password(user_data["password_hash"], password):
                        
                        # --- START: MODIFIED SESSION LOGIC ---
                        # 1. Generate a new unique session token.
                        session_token = str(uuid.uuid4())
                        
                        # 2. Store the new token in the database, overwriting any old one.
                        conn.client.table("users").update({"active_session_token": session_token}).eq("email", email).execute()

                        # 3. Store user details and the new token in the session state.
                        st.session_state['logged_in'] = True
                        st.session_state['username'] = email
                        st.session_state['session_token'] = session_token 
                        # --- END: MODIFIED SESSION LOGIC ---
                        
                        st.rerun()
                    else:
                        st.error("Incorrect password.")
                else:
                    st.error("Email address not found.")

        elif choice == "Sign Up":
            st.subheader("Create New Account")
            new_email = st.text_input("Enter your Email Address")
            new_password = st.text_input("Choose a Password", type="password")
            
            if st.button("Sign Up"):
                whitelist = get_whitelist_db() # UPDATED
                is_valid_format = re.match(r"[^@]+@[^@]+\.[^@]+", new_email)
                user_db = get_users_db() # UPDATED

                if not new_email or not new_password:
                    st.error("Email and password cannot be empty.")
                elif not is_valid_format:
                    st.error("Please enter a valid email address format.")
                elif new_email not in whitelist:
                    st.error("This email address is not authorized for registration. Please contact the administrator.")
                elif not user_db.empty and new_email in user_db["email"].values:
                    st.error("This email is already registered. Please go to the Login tab.")
                else:
                    # UPDATED: Replaced pandas logic with a single call to the database function
                    add_user_db(new_email, hash_password(new_password))
                    st.success("Account created successfully! You can now log in.")
                    st.info("Please switch to the Login tab to sign in.")
    
    return st.session_state.get('logged_in', False)


def validate_session():
    """Checks if the current session_token matches the one in the database."""
    if not st.session_state.get('logged_in'):
        return False # Not logged in, no session to validate

    try:
        email = st.session_state['username']
        local_token = st.session_state.get('session_token')

        # Fetch the current token from the database
        result = conn.client.table("users").select("active_session_token").eq("email", email).single().execute()
        
        db_token = result.data.get('active_session_token')

        # If tokens don't match, the session is invalid
        if local_token != db_token:
            return False
        return True

    except Exception as e:
        # If any error occurs (e.g., user deleted), invalidate the session
        st.error(f"Session validation error: {e}")
        return False

# --- Whitelist Management UI (for Admins) ---

def whitelist_manager_ui():
    """Renders a UI in the sidebar for admins to manage the email whitelist in Supabase."""
    try:
        admin_password = os.environ.get("APP_ADMIN_PASSWORD")
    except (KeyError, FileNotFoundError):
        admin_password = None

    if not admin_password:
        return

    # REMOVED: The st.expander to fix the icon text issue.
    # The content is now always visible.
    st.subheader("👑 Admin Panel") # Added a subheader for clarity
    entered_pass = st.text_input("Enter Admin Password", type="password", key="admin_pass")
    
    if entered_pass == admin_password:
        st.info("Access Granted. You can now manage the email whitelist.")
        
        try:
            current_whitelist = get_whitelist_db()
            st.write("Whitelisted Emails:")
            st.dataframe(pd.DataFrame({"Authorized Emails": current_whitelist}), use_container_width=True)

            # Add Email Form
            with st.form("add_email_form", clear_on_submit=True):
                new_email = st.text_input("Add new email to whitelist")
                if st.form_submit_button("Add Email"):
                    if new_email and re.match(r"[^@]+@[^@]+\.[^@]+", new_email):
                        if new_email not in current_whitelist:
                            add_to_whitelist_db(new_email)
                            st.success(f"Added '{new_email}' to the whitelist.")
                            st.rerun()
                        else:
                            st.warning("Email already exists in the whitelist.")
                    else:
                        st.error("Please enter a valid, non-empty email address.")
            
            # Remove Email Form
            if current_whitelist:
                with st.form("remove_email_form"):
                    email_to_remove = st.selectbox("Remove email from whitelist", options=[""] + current_whitelist)
                    if st.form_submit_button("Remove Email"):
                        if email_to_remove:
                            remove_from_whitelist_db(email_to_remove)
                            st.success(f"Removed '{email_to_remove}' from the whitelist.")
                            st.rerun()
                        else:
                            st.warning("Please select an email to remove.")

        except Exception as e:
            st.error(f"An error occurred managing the whitelist: {e}")

    elif entered_pass:
        st.error("Incorrect admin password.")


# ==============================================================================
# 1. SHARED UTILITIES & CONFIG
# ==============================================================================

# --- API Keys & Secrets ---
# It's best practice to manage secrets in one place.
# The app will try to get keys and handle errors gracefully if not found.
try:
    DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
    FMP_API_KEY = os.environ.get("FMP_API_KEY")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
except (KeyError, FileNotFoundError):
    st.sidebar.error("API keys not found in Streamlit secrets.")
    st.stop()

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
#openai_client = OpenAI(api_key=OPENAI_API_KEY)

def load_logo():
    # 1) Find the folder where this file (app.py) lives
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 2) Build the full path to logo.png next to it
    logo_path = os.path.join(script_dir, "logo.png")

    if os.path.isfile(logo_path):
        return Image.open(logo_path)

    # fallback dummy if not found
    img = Image.new('RGB', (200, 50), color=(255,255,255))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
    d.text((10,10), "Aranca", fill=(0,65,106), font=font)
    return img

LOGO_OBJECT = load_logo() # Call the new function



# ==============================================================================
# 2. IPO INVESTMENT MEMO GENERATOR
# (Code from InvMemo.py and pipeline.py)
# ==============================================================================

# Add these imports to the top of your Python file
import streamlit as st
import requests
import re
import fitz  # PyMuPDF
import os
import tempfile
import numpy as np
import faiss
import markdown
from docx import Document
from docx.shared import Pt, Inches
from datetime import datetime
from collections import defaultdict
from jinja2 import Template
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
from pathlib import Path
from bs4 import BeautifulSoup # <-- ADD THIS IMPORT

def investment_memo_app():
    """
    Encapsulates the entire IPO Investment Memo Generator with Infographic and Q&A.
    This version is aligned with the advanced standalone module and supports both PDF and HTML.
    """
    
    # --- CONFIGURATION ---
    DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
    DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
    CHUNK_SIZE = 50

    if not DEEPSEEK_API_KEY:
        st.error("DeepSeek API key not found. Please add it to your Streamlit secrets.")
        return

    # --- HELPER FUNCTIONS (Memo & Pipeline) ---

    def clean_markdown(text):
        text = re.sub(r'#+\s*', '', text)
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        text = re.sub(r'\*(.*?)\*', r'\1', text)
        text = re.sub(r'_+', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'^[-*•]+\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'Section\s\d+[:.]?', '', text, flags=re.IGNORECASE)
        text = re.sub(r'(Next|Previous) section:.*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'This section .*?(focuses on|explores|explains).*?\.', '', text, flags=re.IGNORECASE)
        return text.strip()

    def extract_text_by_page(pdf_path):
        doc = fitz.open(pdf_path)
        return [page.get_text() for page in doc], len(doc)

    # MODIFICATION: New function to handle HTML files
    def extract_text_from_html(html_path):
        """Reads an HTML file and extracts all text content."""
        with open(html_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
        
        for element in soup(["script", "style", "header", "footer", "nav"]):
            element.decompose() # Remove irrelevant tags
            
        text = soup.get_text(separator='\n', strip=True)
        # Consolidate whitespace
        cleaned_text = re.sub(r'\n{3,}', '\n\n', text)
        return cleaned_text

    def get_relevant_pages_chunked(text_by_page, user_query):
        total_pages = len(text_by_page)
        relevant_pages = set()
        for start in range(0, total_pages, CHUNK_SIZE):
            end = min(start + CHUNK_SIZE, total_pages)
            chunk_pages = text_by_page[start:end]
            prompt = (
                "Below are texts from a PDF. Identify only the page numbers (starting from 1) relevant to this query:\n"
                f"Query: {user_query}\n\n"
            )
            for i, text in enumerate(chunk_pages):
                snippet = text[:1000].replace('\n', ' ')
                prompt += f"\nPage {start + i + 1}: {snippet}\n"
            
            messages = [
                {"role": "system", "content": "You are an expert document analyst."},
                {"role": "user", "content": prompt}
            ]
            response = requests.post(DEEPSEEK_API_URL, headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}, json={"model": "deepseek-chat", "messages": messages})
            response.raise_for_status()
            reply = response.json()['choices'][0]['message']['content']
            matches = re.findall(r'\d+', reply)
            for m in matches:
                if 1 <= int(m) <= total_pages:
                    relevant_pages.add(int(m))
        return sorted(relevant_pages)

    def extract_selected_pages_text(original_path, pages_to_keep):
        doc = fitz.open(original_path)
        return "\n".join(doc[p - 1].get_text() for p in pages_to_keep).strip()

    def extract_company_name(text):
        prompt = (
            "Extract only the legal name of the company from the following IPO or DRHP text. "
            "Return only the company name, nothing else.\n\n"
            f"{text[:10000]}"
        )
        messages = [
            {"role": "system", "content": "You are an expert in IPO documents."},
            {"role": "user", "content": prompt}
        ]
        response = requests.post(DEEPSEEK_API_URL, headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}, json={"model": "deepseek-chat", "messages": messages})
        response.raise_for_status()
        
        # --- THE FIX IS HERE ---
        # Get the raw response and clean it by replacing newlines with spaces before returning.
        company_name = response.json()['choices'][0]['message']['content'].strip()
        return company_name.replace('\n', ' ')

    def find_relevant_text_for_section(full_text, section_title, keywords_map):
        """
        Searches the full document text for keywords related to a specific section title
        and returns a relevant chunk of text for the LLM to use as context.
        """
        # Get the specific keywords for the given section title
        keywords = keywords_map.get(section_title, [])
        if not keywords:
            # Fallback to a generic chunk if no keywords are defined for a title
            return full_text[:16000]

        # Create a regex pattern to find any of the keywords, ignoring case
        # This pattern looks for the keyword as a potential heading.
        pattern = re.compile(r'^\s*(' + '|'.join(map(re.escape, keywords)) + r')\s*$', re.IGNORECASE | re.MULTILINE)
        
        match = pattern.search(full_text)
        
        if match:
            # If a keyword is found, extract the text following it
            start_index = match.end()
            # Extract a substantial chunk of text to provide enough context
            context_text = full_text[start_index : start_index + 20000]
            return context_text
        else:
            # If no specific section is found, return the initial part of the document as a fallback.
            # This is not ideal but prevents errors. The key is a good keywords_map.
            st.warning(f"Could not find a specific section for '{section_title}'. Using initial text as fallback.")
            return full_text[:16000]

    def generate_memo_sections(filtered_text, custom_notes=""):
        section_titles = [
            "1. IPO Offer Details", "2. Company Overview", "3. Industry Overview and Outlook",
            "4. Business Model", "5. Financial Highlights",
            "6. Guidance and Outlook on future financial performance",
            "7. Peer Comparison and Competitors", "8. Risks", "9. Investment Highlights"
        ]

        # A map to find the right DRHP sections for each memo title. This is crucial.
        keywords_map = {
            "1. IPO Offer Details": ["Details of the Offer", "The Offer"],
            "2. Company Overview": ["Our Business", "Company Overview", "Summary of Business"],
            "3. Industry Overview and Outlook": ["Industry Overview"],
            "4. Business Model": ["Business Model", "Our Business"],
            "5. Financial Highlights": ["Financial Highlights", "Financial Information", "Restated Consolidated Financial Information", "Summary of Restated Consolidated Financial Information"],
            "6. Guidance and Outlook on future financial performance": ["Management's Discussion and Analysis", "Guidance and Outlook"],
            "7. Peer Comparison and Competitors": ["Peer Comparison", "Competitive Landscape", "Competitors"],
            "8. Risks": ["Risk Factors", "Risks"],
            "9. Investment Highlights": ["Investment Rationale", "Investment Highlights", "Our Competitive Strengths"]
        }
        
        sections = {}
        st.info("Generating memo sections with targeted context analysis...")
        progress_bar = st.progress(0)
        
        for i, title in enumerate(section_titles):
            st.write(f"Finding context for: **{title[3:]}**...")
            
            # --- THIS IS THE CORE FIX ---
            # Find relevant text specifically for THIS section, instead of using the same generic text for all.
            relevant_text = find_relevant_text_for_section(filtered_text, title, keywords_map)
            
            st.write(f"Generating content for: **{title[3:]}**...")
            
            prompt = (
                f"You are a professional financial analyst writing a Pre-IPO memo section titled: '{title[3:]}'.\n"
                "Based STRICTLY on the 'Relevant DRHP Text' provided below, generate approximately 500 words of clean, structured, analytical prose suitable for institutional investors.\n"
                "IMPORTANT RULES:\n"
                "- ONLY use information present in the provided text. Do not invent or hallucinate any data, figures, or facts.\n"
                "- If specific information (e.g., financial numbers, competitor names) is not in the text, state that the information is not available in the provided context.\n"
                "- Do not mention this is a memo. Do not start with the section title (e.g., avoid 'The Business Model is...').\n"
                "- Avoid phrases like 'In this section' or 'The provided text states...'. Write authoritatively.\n"
                "- Use plain, professional text only. Strictly avoid markdown (no asterisks, hashes, underscores).\n\n"
            )
            if custom_notes:
                prompt += f"USER'S CUSTOM FOCUS: {custom_notes.strip()}\n\n"
            
            prompt += f"Relevant DRHP Text:\n{relevant_text}" # We use the specifically found relevant_text
            
            messages = [
                {"role": "system", "content": "You are an expert financial analyst writing an investment memo based *only* on provided text."},
                {"role": "user", "content": prompt}
            ]
            
            try:
                response = requests.post(
                    DEEPSEEK_API_URL, 
                    headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}, 
                    json={"model": "deepseek-chat", "messages": messages, "temperature": 0.2}
                )
                response.raise_for_status()
                raw_content = response.json()['choices'][0]['message']['content']
                
                # Clean the generated content
                cleaned = clean_markdown(raw_content)
                cleaned = re.sub(rf"^{re.escape(title[3:])}[\s:—-]*", "", cleaned, flags=re.IGNORECASE | re.MULTILINE)
                sections[title] = cleaned.strip()
                
            except requests.RequestException as e:
                st.error(f"API call failed for section '{title[3:]}': {e}")
                sections[title] = f"Error generating this section. {e}"

            progress_bar.progress((i + 1) / len(section_titles))
            
        st.success("All memo sections generated.")
        return sections

    def save_sections_to_word(sections_dict, company_name="Company", output_dir="documents"):
        os.makedirs(output_dir, exist_ok=True)
        
        # Sanitize the company name for the filename
        sanitized_company_name = re.sub(r'[\\/*?:"<>|]', "", company_name)
        sanitized_company_name = sanitized_company_name.replace(' ', '_')
        
        # Truncate to a reasonable length to avoid "File name too long" errors
        max_len = 50 
        if len(sanitized_company_name) > max_len:
            sanitized_company_name = sanitized_company_name[:max_len]

        filename = f"{sanitized_company_name}_PreIPO_Memo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
        full_path = os.path.join(output_dir, filename)
        
        doc = Document()
        style = doc.styles['Normal']
        style.font.name = 'Aptos Display'
        style.font.size = Pt(11)

        title_para = doc.add_paragraph()
        title_run = title_para.add_run(f"{company_name} Pre-IPO Memo")
        title_run.font.name = 'Aptos Display'
        title_run.font.size = Pt(20)
        title_run.bold = True
        doc.add_paragraph()

        for title, body in sections_dict.items():
            heading = doc.add_paragraph()
            run = heading.add_run(title)
            run.bold = True
            run.font.name = 'Aptos Display'
            run.font.size = Pt(14)
            for para in body.strip().split('\n\n'):
                if para.strip():
                    doc.add_paragraph(para.strip())
            doc.add_paragraph()
        
        section = doc.sections[0]
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        
        doc.save(full_path)
        return full_path

    # MODIFICATION: The run_memo_pipeline is modified below in the main app flow
    # to handle the logic split between PDF and HTML.

    # --- HELPER FUNCTIONS (Infographic) ---

    def extract_raw_text_from_docx(docx_path):
        doc = Document(docx_path)
        return "\n".join(para.text.strip() for para in doc.paragraphs if para.text.strip())

    def call_deepseek_summary(text, company_name):
        prompt = f"""
        You are an investment analyst. Summarize the key points for each section of the provided pre-IPO memo for {company_name}.
        For each section, provide 3-5 crisp bullet points. Each bullet point must be under 30 words.
        Format your response in markdown, with each section as a header.
        
        Memo Text:
        {text}
        """
        messages = [
            {"role": "system", "content": "You are a financial analyst specializing in concise summaries for infographics."},
            {"role": "user", "content": prompt}
        ]
        response = requests.post(DEEPSEEK_API_URL, headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}, json={"model": "deepseek-chat", "messages": messages, "temperature": 0.3})
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    
    def parse_deepseek_response(summary_text):
        sections = defaultdict(list)
        current_section = None
        header_pattern = re.compile(r"^#+\s*(?:\d+\.\s*)?(.*?)\s*$", re.MULTILINE)
        
        parts = header_pattern.split(summary_text)
        if len(parts) > 1:
            for i in range(1, len(parts), 2):
                header = parts[i].strip()
                content = parts[i+1]
                bullets = re.findall(r'[-\*•]\s+(.*)', content)
                formatted_bullets = [re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', b.strip()) for b in bullets]
                if header and formatted_bullets:
                    sections[header] = formatted_bullets
        return dict(sections)

    def generate_infographic_html(docx_path, company_name, template_path="base_infographic.html"):
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"The template file '{template_path}' was not found.")
        raw_text = extract_raw_text_from_docx(docx_path)
        summary = call_deepseek_summary(raw_text, company_name)
        sections = parse_deepseek_response(summary)
        
        with open(template_path, "r", encoding="utf-8") as f:
            html_template = f.read()
            
        template = Template(html_template)
        return template.render(company_name=company_name, sections=sections)

    # --- HELPER FUNCTIONS (Q&A Engine) ---

    # MODIFICATION: Renamed and updated to handle both PDF and HTML
    class DocumentQueryEngine:
        def __init__(self, model_name="all-MiniLM-L6-v2"):
            self.api_key = DEEPSEEK_API_KEY
            self.embedder = SentenceTransformer(model_name)

        def _extract_chunks_from_pdf(self, path):
            reader = PdfReader(path)
            return [(i + 1, page.extract_text().strip()) for i, page in enumerate(reader.pages) if page.extract_text()]

        def _extract_chunks_from_html(self, path):
            full_text = extract_text_from_html(path)
            # Chunk HTML text by paragraphs (or a fixed character length if needed)
            paragraphs = [p.strip() for p in full_text.split('\n\n') if p.strip()]
            # Return with a chunk index instead of a page number
            return [(i + 1, para) for i, para in enumerate(paragraphs)]

        def answer_query(self, doc_path, query, top_k=3):
            # MODIFICATION: Select the correct chunking method based on file type
            if doc_path.endswith('.pdf'):
                chunks = self._extract_chunks_from_pdf(doc_path)
                source_label = "Page"
            elif doc_path.endswith('.html'):
                chunks = self._extract_chunks_from_html(doc_path)
                source_label = "Section" # Use a more generic label for HTML chunks
            else:
                raise ValueError("Unsupported file type for Q&A.")

            if not chunks: raise ValueError("No text could be extracted from the document.")
            
            source_ids, texts = zip(*chunks)
            text_embeddings = np.array(self.embedder.encode(texts, convert_to_numpy=True))
            
            index = faiss.IndexFlatL2(text_embeddings.shape[1])
            index.add(text_embeddings)
            
            query_embedding = self.embedder.encode([query])
            _, I = index.search(query_embedding, k=top_k)
            
            context_chunks = [(source_ids[i], texts[i]) for i in I[0]]
            
            messages = [{"role": "system", "content": "Answer the user's question based on the context provided from the document."}]
            for source_id, text in context_chunks:
                messages.append({"role": "user", "content": f"[Context from {source_label} {source_id}]:\n{text}"})
            messages.append({"role": "user", "content": f"Question: {query}"})
            
            response = requests.post(DEEPSEEK_API_URL, headers={"Authorization": f"Bearer {self.api_key}"}, json={"model": "deepseek-chat", "messages": messages, "temperature": 0.2})
            response.raise_for_status()
            
            answer_md = response.json()["choices"][0]["message"]["content"]
            cited_sources = sorted([source_ids[i] for i in I[0]])
            return markdown.markdown(answer_md), cited_sources, source_label

    # Initialize session state
    if "memo_generated" not in st.session_state:
        st.session_state.memo_generated = False
    if "memo_path" not in st.session_state:
        st.session_state.memo_path = None
    if "doc_path" not in st.session_state: # MODIFICATION: Renamed for generality
        st.session_state.doc_path = None
    
    # --- Main App Flow ---
    st.markdown("### 📝 Agent Pre-IPO")
    st.markdown("Upload a DRHP or IPO prospectus to automatically generate a detailed investment memo, an infographic, and perform Q&A.")
    st.subheader("📤 1. Upload DRHP or IPO Prospectus")
    
    # MODIFICATION: Allow both PDF and HTML files
    uploaded_file = st.file_uploader(
        "Upload your PDF or HTML file",
        type=["pdf", "html"],
        key="prospectus_uploader"
    )
    
    if uploaded_file:
        # Save uploaded file to a temporary path with the correct extension
        suffix = Path(uploaded_file.name).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(uploaded_file.getbuffer())
            st.session_state.doc_path = tmp_file.name
            
        custom_focus = st.text_area(
            "Optional: Add custom notes to guide memo generation",
            key="memo_focus",
            help="Example: 'Focus on the competitive landscape in North America and risks related to supply chain.'"
        )

        # --- NEW UI for Custom Section Prompts ---
        st.markdown("---")
        st.subheader("Advanced: Customize Section Prompts")
        st.info("You can provide your own generation prompt for each memo section below. Leave a box empty to use the default.")
        
        section_titles = [
            "1. IPO Offer Details", "2. Company Overview", "3. Industry Overview and Outlook",
            "4. Business Model", "5. Financial Highlights",
            "6. Guidance and Outlook on future financial performance",
            "7. Peer Comparison and Competitors", "8. Risks", "9. Investment Highlights"
        ]

        for title in section_titles:
            st.markdown(f"##### Custom Prompt for: {title[3:]}")
            st.text_area(
                label=f"Custom prompt for {title[3:]}",
                placeholder=f"Enter your full custom prompt for the '{title[3:]}' section here...",
                height=150,
                key=f"memo_custom_prompt_{title.replace(' ', '_')}", # Unique key
                label_visibility="collapsed"
            )
        # --- END NEW UI ---

        # In your main app flow, under the "if st.button..."
        if st.button("📘 Generate Investment Memo", key="gen_memo"):
            with st.spinner("⏳ Analyzing document and generating memo... This may take a few minutes."):
                try:
                    full_text = ""
                    if st.session_state.doc_path.endswith(".pdf"):
                        # The extract_text_by_page function returns a list of strings (one per page)
                        text_by_page, _ = extract_text_by_page(st.session_state.doc_path)
                        # Join them all into one single large string
                        full_text = "\n".join(text_by_page)
                    
                    elif st.session_state.doc_path.endswith(".html"):
                        full_text = extract_text_from_html(st.session_state.doc_path)

                    if not full_text.strip():
                        raise ValueError("Could not extract text from the document.")
                    
                    company_name = extract_company_name(full_text)
                    
                    # --- CALL THE NEW, FIXED FUNCTION ---
                    # It now takes the full_text and handles context internally.
                    sections_dict = generate_memo_sections(full_text, custom_focus)
                    
                    memo_path = save_sections_to_word(sections_dict, company_name=company_name)

                    st.session_state.memo_generated = True
                    st.session_state.memo_path = memo_path
                    st.success("✅ Memo generated successfully!")
                    
                except Exception as e:
                    st.error(f"❌ Error generating memo: {e}")
                    st.session_state.memo_generated = False
        
        # --- Post-Generation Options ---
        if st.session_state.memo_generated and st.session_state.memo_path:
            with open(st.session_state.memo_path, "rb") as f:
                st.download_button(
                    "📥 Download Memo (.docx)", f, Path(st.session_state.memo_path).name,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            
            st.markdown("---")
            st.subheader("🎨 2. Generate Infographic")
            if st.button("🖼️ Generate Infographic", key="gen_infographic"):
                with st.spinner("✨ Creating infographic summary..."):
                    try:
                        company_name = Path(st.session_state.memo_path).stem.split('_PreIPO_Memo_')[0].replace('_', ' ')
                        infographic_html = generate_infographic_html(st.session_state.memo_path, company_name)
                        
                        st.components.v1.html(infographic_html, width=1100, height=1000, scrolling=True)
                                        
                        st.download_button(
                            label="📥 Download Infographic (.html)",
                            data=infographic_html,
                            file_name=f"{company_name.replace(' ', '_')}_Infographic.html",
                            mime="text/html"
                        )
                    except Exception as e:
                        st.error(f"❌ Error generating infographic: {e}")

        # --- Q&A Section ---
        st.markdown("---")
        st.subheader("🔍 3. Ask Questions from the Document")
        query = st.text_input("Type your question (e.g., What are the key risk factors?)", key="memo_query")
        if query:
            with st.spinner("💬 Searching for answers in the document..."):
                try:
                    # MODIFICATION: Use the updated engine
                    engine = DocumentQueryEngine()
                    answer_html, cited_sources, source_label = engine.answer_query(st.session_state.doc_path, query)
                    st.markdown(answer_html, unsafe_allow_html=True)
                    st.caption(f"📄 Answer generated from information on {source_label.lower()}s: {', '.join(map(str, cited_sources))}")
                except Exception as e:
                    st.error(f"❌ Query Error: {e}")

# ==============================================================================
# 3. DCF AGENT
# (Code from app - DCFAgent.py and 1_📄_Report.py)
# ==============================================================================
def dcf_agent_app(client: OpenAI, FMP_API_KEY: str):
    """
    A self-contained Streamlit app function for document-driven DCF analysis.
    This is the corrected and unified version, ensuring robust functionality and consistent output.

    Args:
        client (OpenAI): An initialized OpenAI client instance.
        FMP_API_KEY (str): The API key for Financial Modeling Prep.
    """

    # ========== HELPER & CACHED FUNCTIONS (Defined internally) ==========

    def load_uploaded_financials(uploaded_file):
        REQUIRED_COLUMNS = [
            "Year", "Revenue", "EBITDA", "Net Income", "Shares Outstanding",
            "Cash", "Short-term Debt", "Long-term Debt", "CapEx",
            "Change in WC", "D&A"
        ]
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            if not all(col in df.columns for col in REQUIRED_COLUMNS):
                st.error(f"❌ Uploaded file is missing required columns. Please ensure it contains: {', '.join(REQUIRED_COLUMNS)}")
                return pd.DataFrame()
            for col in REQUIRED_COLUMNS:
                if col != 'Year':
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            df = df.dropna(subset=REQUIRED_COLUMNS).sort_values(by="Year", ascending=False).reset_index(drop=True)
            return df[REQUIRED_COLUMNS]
        except Exception as e:
            st.error(f"🚨 Error processing uploaded file: {e}")
            return pd.DataFrame()

    @st.cache_data(ttl=3600, show_spinner=False)
    def get_fmp_data(ticker):
        def fetch(endpoint):
            url = f"https://financialmodelingprep.com/api/v3/{endpoint}/{ticker}?period=annual&limit=5&apikey={FMP_API_KEY}"
            try: return requests.get(url).json()
            except requests.exceptions.RequestException: return []
        income, balance, cashflow = fetch("income-statement"), fetch("balance-sheet-statement"), fetch("cash-flow-statement")
        if not all(isinstance(d, list) and d for d in [income, balance, cashflow]): return pd.DataFrame()
        data = []
        num_years = min(len(income), len(balance), len(cashflow))
        for i in range(num_years):
            data.append({
                "Year": income[i].get("calendarYear"), "Revenue": income[i].get("revenue"),
                "EBITDA": income[i].get("ebitda"), "Net Income": income[i].get("netIncome"),
                "Shares Outstanding": income[i].get("weightedAverageShsOutDil"),
                "Cash": balance[i].get("cashAndCashEquivalents"),
                "Short-term Debt": balance[i].get("shortTermDebt"), "Long-term Debt": balance[i].get("longTermDebt"),
                "CapEx": cashflow[i].get("capitalExpenditure"), "Change in WC": cashflow[i].get("changeInWorkingCapital"),
                "D&A": abs(cashflow[i].get("depreciationAndAmortization", 0))
            })
        return pd.DataFrame(data)

    @st.cache_data(ttl=3600, show_spinner=False)
    def get_fmp_ticker(company_name):
        prompt = f'What is the exact stock ticker for the company "{company_name}"? Return only the raw ticker symbol.'
        try:
            response = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], temperature=0)
            return response.choices[0].message.content.strip().upper().split()[0].strip('".:,')
        except Exception as e:
            st.error(f"Could not retrieve ticker: {e}"); return None

    @st.cache_data(ttl=900, show_spinner=False)
    def get_current_price(ticker):
        url = f"https://financialmodelingprep.com/api/v3/quote-short/{ticker}?apikey={FMP_API_KEY}"
        try:
            r = requests.get(url).json()
            if r and isinstance(r, list):
                price = round(r[0].get("price", 0), 2)
                # Convert pence to pounds for UK stocks
                if ticker.endswith(".L"):
                    return price / 100
                return price
        except Exception as e:
            st.error(f"Could not fetch price for {ticker}: {e}")
        return None

    @st.cache_data(ttl=600, show_spinner=False)
    def get_company_news(ticker, limit=5):
        url = f"https://financialmodelingprep.com/api/v3/stock_news?tickers={ticker}&limit={limit}&apikey={FMP_API_KEY}"
        try:
            items = requests.get(url).json()
            return [f"{i['title']} ({i['site']})" for i in items]
        except Exception: return []

    def extract_text_from_files(primary_file, supporting_files):
        docs = []
        def process_file(file, is_primary=False):
            try:
                if file.name.endswith(".pdf"):
                    reader = PdfReader(file)
                    full_text = "".join(page.extract_text() + "\n" for page in reader.pages if page.extract_text())
                    prefix = "PRIMARY DOCUMENT" if is_primary else "SUPPORTING DOCUMENT"
                    return f"--- START OF {prefix}: {file.name} ---\n{full_text}\n--- END OF {prefix}: {file.name} ---"
            except Exception as e:
                st.warning(f"Could not parse file {file.name}: {e}")
            return None
        if primary_file:
            if text := process_file(primary_file, is_primary=True): docs.append(text)
        for file in supporting_files:
            if text := process_file(file): docs.append(text)
        return "\n\n".join(docs)

    def generate_analyst_memo(documents_text, company_name, financials_df):
        hist = financials_df.sort_values("Year", ascending=False).head(3)
        historical_summary = "Not enough historical data for 3-year trends.\n"
        if len(hist) >= 3:
            rev_cagr_3y = (hist.iloc[0]['Revenue'] / hist.iloc[2]['Revenue'])**(1/3) - 1
            ebitda_margin_3y = (hist['EBITDA'] / hist['Revenue']).mean()
            historical_summary = (
                f"\n\n--- KEY HISTORICAL METRICS ---\n"
                f"- Last Year's Revenue: {hist.iloc[0]['Revenue'] / 1e9:.1f}B\n"
                f"- 3-Year Revenue CAGR: {rev_cagr_3y:.1%}\n"
                f"- 3-Year Average EBITDA Margin: {ebitda_margin_3y:.1%}\n"
            )
        prompt = f"""
        Act as a senior equity research analyst for {company_name}.
        Synthesize all context into a concise "Analyst Memo". Prioritize insights from the PRIMARY DOCUMENT.
        The memo should consist of 3-5 distinct paragraphs, separated by newlines.
        Return a valid JSON object with two keys:
        1. "memo": A string containing your qualitative analyst memo.
        2. "sources": A list of objects, where each object has "document_name" and a list of 2-4 "points_used".
        --- CONTEXT ---\n{documents_text}\n{historical_summary}\n--- END CONTEXT ---
        """
        try:
            response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"}, temperature=0.2)
            result = json.loads(response.choices[0].message.content)
            return result.get("memo", "Could not generate memo."), result.get("sources", [])
        except Exception as e:
            st.error(f"Error generating Analyst Memo: {e}")
            return "Could not generate analyst memo.", []

    def extract_scenario_assumptions(analyst_memo, company_name, historical_summary):
        prompt = f"""
        You are a quantitative analyst. Convert the qualitative Analyst Memo for {company_name} into specific, justifiable financial assumptions for a 5-year DCF model.
        Use the provided Historical Metrics as a critical anchor. For items like CapEx, D&A, and WC, the model will use historical averages as a % of revenue. Your rationale should reflect this methodology.

        Return a valid JSON object with keys "Bull", "Base", "Bear". For each key, the value should be an object containing:
        - "revenue_cagr": A decimal value.
        - "ebitda_margin": A decimal value.
        - "key_driver": A short (1-sentence) qualitative summary of the scenario.
        - "justification": An object with rationale strings for the following keys:
            - "revenue_rationale": Justification for the revenue growth rate.
            - "ebitda_margin_rationale": Justification for the EBITDA margin.
            - "capex_rationale": Rationale for CapEx projection (e.g., "Projected at the 3-year historical average of X% of revenue to support growth.").
            - "wc_rationale": Rationale for Working Capital changes (e.g., "Changes in WC are tied to revenue growth, reflecting the historical average of Y% of revenue.").

        --- HISTORICAL METRICS ---\n{historical_summary}\n--- ANALYST MEMO ---\n{analyst_memo}\n--- END ---
        """
        try:
            response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"}, temperature=0.0)
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            st.error(f"Error generating AI scenarios: {e}"); return None

    def perform_dcf_calculations(financials_df, scenario_assumptions, wacc, terminal_multiples=None):
        if financials_df.empty or not scenario_assumptions: return None
        latest_year_data = financials_df.iloc[0]
        hist_avg = financials_df.head(3).mean(numeric_only=True)
        historical_ratios = {
            'capex_pct': abs(hist_avg['CapEx']) / hist_avg['Revenue'] if hist_avg.get('Revenue') else 0,
            'da_pct': hist_avg['D&A'] / hist_avg['Revenue'] if hist_avg.get('Revenue') else 0,
            'wc_pct': abs(hist_avg['Change in WC']) / hist_avg['Revenue'] if hist_avg.get('Revenue') else 0,
        }
        forecasts, valuations = {}, {}
        wacc_dec = wacc / 100
        latest_calendar_year = int(latest_year_data['Year'])
        terminal_growth_rate = 0.025
        base_case_terminal_fcf_is_negative = False
        for name, params in scenario_assumptions.items():
            df = pd.DataFrame(index=range(latest_calendar_year + 1, latest_calendar_year + 6))
            df.index.name = "Year"
            df['Revenue'] = [latest_year_data['Revenue'] * (1 + params["revenue_cagr"])**i for i in range(1, 6)]
            df['EBITDA'] = df['Revenue'] * params["ebitda_margin"]
            df['D&A'] = df['Revenue'] * historical_ratios['da_pct']
            df['EBIT'] = df['EBITDA'] - df['D&A']
            df['NOPAT'] = df['EBIT'] * (1 - 0.21)
            df['CapEx'] = -(df['Revenue'] * historical_ratios['capex_pct'])
            df['Change in WC'] = -(df['Revenue'] * historical_ratios['wc_pct'])
            df['FCF'] = df['NOPAT'] + df['D&A'] + df['CapEx'] + df['Change in WC']
            forecasts[name] = df
            last_fcf = df.iloc[-1]['FCF']
            if name == "Base" and last_fcf < 0: base_case_terminal_fcf_is_negative = True
            
            # **Corrected Logic**: Checks for multiples dict and the specific key.
            if terminal_multiples and name in terminal_multiples:
                tv = df.iloc[-1]['EBITDA'] * terminal_multiples[name]
            else:
                tv = (last_fcf * (1 + terminal_growth_rate)) / (wacc_dec - terminal_growth_rate) if wacc_dec > terminal_growth_rate else 0
            
            pv_fcf = sum(df.iloc[i]['FCF'] / (1 + wacc_dec)**(i + 1) for i in range(5))
            pv_tv = tv / (1 + wacc_dec)**5
            enterprise_value = pv_fcf + pv_tv
            net_debt = latest_year_data.get('Short-term Debt', 0) + latest_year_data.get('Long-term Debt', 0) - latest_year_data.get('Cash', 0)
            equity_value = enterprise_value - net_debt
            shares_outstanding = latest_year_data.get('Shares Outstanding')
            per_share = equity_value / shares_outstanding if shares_outstanding else 0
            valuations[name] = {'Per-Share Value': per_share}
        return {
            'forecasts': forecasts, 'valuations': valuations,
            'scenario_assumptions': scenario_assumptions,
            'base_case_terminal_fcf_is_negative': base_case_terminal_fcf_is_negative
        }

    def get_currency_symbol(ticker):
        if ticker.endswith(".L"): return "£"
        if ticker.endswith((".PA", ".DE", ".AS")): return "€"
        return "$"

    def format_report_as_html(ss):
        # Use .get() for safe access to session state keys
        company = ss.get('dcf_company_name', 'N/A')
        ticker = ss.get('dcf_ticker', 'N/A')
        memo = ss.get('dcf_memo', 'Memo not available.')
        financials = ss.get('dcf_financials') # Can be None, checked later
        results = ss.get('dcf_results_data') # Can be None, checked later
        price = ss.get('dcf_price', 0)
        method = ss.get('dcf_valuation_method', 'Perpetuity Growth')
        multiples = ss.get('dcf_terminal_multiples', {})

        currency_symbol = get_currency_symbol(ticker)
        
        # Check if critical data is missing
        if not results or financials is None or ticker == 'N/A':
            return "<h3>Error: Could not generate report because critical data is missing. Please start a new analysis.</h3>"

        # Formatting helpers
        def num_fmt(n, pct=False, money=True):
            if pd.isna(n) or n is None: return "N/A"
            if pct: return f"{n:.2%}"
            pfx = currency_symbol if money else ""
            s = "-" if n < 0 else ""; n = abs(n)
            if n >= 1e9: return f"{s}{pfx}{n/1e9:.2f}B"
            if n >= 1e6: return f"{s}{pfx}{n/1e6:.1f}M"
            return f"{s}{pfx}{n:,.2f}"

        def detail_fmt(n):
            if pd.isna(n) or n is None: return "N/A"
            s = "(" if n < 0 else ""; e = ")" if n < 0 else ""
            val = abs(n)
            if val >= 1e9: return f"{s}{currency_symbol}{val/1e9:.2f}B{e}"
            if val >= 1e6: return f"{s}{currency_symbol}{val/1e6:.1f}M{e}"
            if val >= 1e3: return f"{s}{currency_symbol}{val/1e3:,.0f}K{e}"
            return f"{s}{currency_symbol}{val:,.2f}"
        
        # Build HTML
        html = f'<div class="report-container"><h1>DCF Valuation Report for {company} ({ticker})</h1>'
        html += "<h2>⚖️ Valuation Summary</h2><div class='summary-cards'>"
        vals = results['valuations']
        rationales = {k: v['key_driver'] for k, v in results['scenario_assumptions'].items()}
        for name in ["Base", "Bull", "Bear"]:
            if name in vals:
                val = vals[name]
                upside = (val['Per-Share Value'] / price - 1) if price else 0
                cls, upside_cls = name.lower(), "bull-text" if upside >= 0 else "bear-text"
                html += f'<div class="card {cls}"><div class="card-title">{name} Case</div>'
                html += f'<div class="card-value">{num_fmt(val["Per-Share Value"])}</div>'
                html += f'<div class="card-upside {upside_cls}">{num_fmt(upside, pct=True, money=False)} Upside</div>'
                html += f'<div class="justification" style="margin-top:15px;"><strong>Rationale:</strong> {rationales.get(name, "")}</div></div>'
        html += '</div>'
        
        html += '<div class="memo-title">Analyst Memo <span style="font-size: 1.2rem; color: #6c757d;">&#x1F517;</span></div>'
        memo_html = "".join([f"<p>{p.strip()}</p>" for p in memo.strip().split('\n') if p.strip()])
        html += f'<div class="memo-container">{memo_html}</div>'
        
        html += "<h2>📈 Financial Summary (Historical)</h2>"
        df_fin = financials.head(3).copy()
        html += df_fin.to_html(classes='report-table', index=False, formatters={c: lambda x: num_fmt(x) for c in df_fin.columns if df_fin[c].dtype in ['int64', 'float64'] and c != 'Year'})
        
        html += "<h2>📊 Free Cash Flow Forecasts</h2>"
        scenarios = results.get('scenario_assumptions', {})
        for name, df in results['forecasts'].items():
            assumps = scenarios.get(name, {})
            justs = assumps.get('justification', {})
            html += f"<h3>{name} Case Forecast</h3><p><strong>Key Assumptions & Rationale:</strong></p><ul class='assumption-list'>"
            html += f"<li><strong>Revenue Growth:</strong> {justs.get('revenue_rationale', 'N/A')}</li>"
            html += f"<li><strong>EBITDA Margin:</strong> {justs.get('ebitda_margin_rationale', 'N/A')}</li>"
            html += f"<li><strong>Capital Expenditures:</strong> {justs.get('capex_rationale', 'N/A')}</li>"
            html += f"<li><strong>Working Capital:</strong> {justs.get('wc_rationale', 'N/A')}</li>"
            rationale_text = f"Terminal Value is based on an exit multiple of <strong>{multiples.get(name, 'N/A')}x LTM EBITDA</strong>." if method == 'EV/EBITDA Multiple' else f"Terminal Value is calculated using the Perpetuity Growth Method with a rate of <strong>{num_fmt(0.025, pct=True, money=False)}</strong>."
            html += f"<li><strong>Terminal Value:</strong> {rationale_text}</li></ul>"
            
            # **Unified Column Renaming**
            display_df = df[['Revenue', 'EBITDA', 'D&A', 'EBIT', 'NOPAT', 'CapEx', 'Change in WC', 'FCF']].copy()
            display_df.rename(columns={'D&A': 'Less: D&A', 'NOPAT': 'NOPAT (21% Tax)', 'CapEx': 'Less: CapEx Reinvestment', 'Change in WC': 'Less: Change in WC', 'FCF': 'Unlevered Free Cash Flow'}, inplace=True)
            display_df_t = display_df.transpose()
            display_df_t.index.name = "Metric"
            for col in display_df_t.columns: display_df_t[col] = display_df_t[col].apply(detail_fmt)
            html += display_df_t.to_html(classes='report-table', index=True)
        html += "</div>"
        return html


    # ========== STREAMLIT UI LOGIC ==========
    st.markdown("### 📊 DCF Ginny")
    st.markdown("Generate a document-driven DCF analysis by providing a company name and prioritized guidance documents.")

    if 'dcf_step' not in st.session_state:
        st.session_state.dcf_step = "initial"

    # --- Block 1: Initial user inputs ---
    if st.session_state.dcf_step == "initial":
        st.subheader("⚙️ Valuation Inputs")
        st.radio("Financial Data Source", ("Fetch from API", "Upload Financials (CSV/Excel)"), horizontal=True, key="dcf_data_source")
        c1, c2 = st.columns(2)
        c1.text_input("Company Name", "NVIDIA", key="dcf_company", help="Enter the full name of the company.")
        # Corrected key to dcf_ticker_input for consistency
        c1.text_input("Stock Ticker (e.g., 'AAPL', 'BA.L')", key="dcf_ticker_input", help="Provide the exact ticker. This will override the AI search.")
        c2.number_input("WACC (%)", 1.0, 20.0, 12.5, 0.1, key="dcf_wacc", help="Weighted Average Cost of Capital.")
        if st.session_state["dcf_data_source"] == "Upload Financials (CSV/Excel)":
            c2.file_uploader("Upload Financials File", type=["csv", "xlsx"], key="dcf_upload")
            st.info("Required Format: File must contain `Year`, `Revenue`, `EBITDA`, etc.", icon="📋")
        
        st.subheader("📄 Qualitative Guidance Documents (Optional)")
        st.file_uploader("Upload Primary Document", type=["pdf"], key="dcf_primary_doc")
        st.file_uploader("Upload Supporting Documents", type=["pdf"], accept_multiple_files=True, key="dcf_support_docs")
        # --- NEW UI for Custom Prompt ---
        st.markdown("---")
        st.subheader("Advanced: Customize Analyst Memo Prompt")
        st.warning("Your custom prompt must ask the model to return a JSON object with keys 'memo' and 'sources', or the analysis will fail.")
        st.text_area(
            "Enter your custom prompt for Analyst Memo generation:",
            placeholder="Enter your full custom prompt here...",
            height=250,
            key="dcf_custom_prompt"
        )
        # --- END NEW UI ---
        if st.button("🚀 Generate DCF Analysis", use_container_width=True):
            st.session_state.update({
                'dcf_company_name': st.session_state.dcf_company,
                'dcf_wacc_input': st.session_state.dcf_wacc,
                'dcf_step': 'processing_initial'
            })
            st.rerun()

    # --- Block 2: Fetching and processing data ---
    if st.session_state.dcf_step == "processing_initial":
        with st.spinner("Performing initial analysis... 🤖"):
            ticker = st.session_state.dcf_ticker_input.upper() or get_fmp_ticker(st.session_state.dcf_company_name)
            if not ticker:
                st.error("❌ Could not determine ticker. Please provide one.")
                st.session_state.dcf_step = "initial"
                st.rerun()

            price = get_current_price(ticker)
            if st.session_state.dcf_data_source == "Upload Financials (CSV/Excel)":
                uploaded_file = st.session_state.get("dcf_upload")
                if not uploaded_file:
                    st.error("❌ Please upload a financials file.")
                    st.session_state.dcf_step = "initial"
                    st.rerun()
                financials = load_uploaded_financials(uploaded_file)
            else:
                financials = get_fmp_data(ticker)

            if price is not None and not financials.empty:
                st.session_state.update({'dcf_financials': financials, 'dcf_price': price, 'dcf_ticker': ticker})
                docs_text = extract_text_from_files(st.session_state.get("dcf_primary_doc"), st.session_state.get("dcf_support_docs", []))
                news = get_company_news(ticker)
                if news: docs_text += "\n\n--- RECENT NEWS ---\n" + "\n".join(f"- {h}" for h in news)
                
                memo, sources = generate_analyst_memo(docs_text, st.session_state.dcf_company_name, financials)
                st.session_state.update({'dcf_memo': memo, 'dcf_sources': sources})
                
                hist = financials.sort_values("Year", ascending=False).head(3)
                hist_summary = "Not enough data for 3-year trends."
                if len(hist) >= 3:
                    rev_cagr = (hist.iloc[0]['Revenue'] / hist.iloc[2]['Revenue'])**(1/3) - 1
                    margin_avg = (hist['EBITDA'] / hist['Revenue']).mean()
                    hist_summary = f"- 3-Year Rev CAGR: {rev_cagr:.1%}\n- 3-Year Avg EBITDA Margin: {margin_avg:.1%}"
                
                assumptions = extract_scenario_assumptions(memo, st.session_state.dcf_company_name, hist_summary)
                if assumptions:
                    st.session_state.dcf_assumptions = assumptions
                    st.session_state.dcf_step = "review"
                    st.rerun()
                else:
                    st.error("❌ Could not generate AI assumptions.")
                    st.session_state.dcf_step = "initial"
                    st.rerun()
            else:
                st.error(f"❌ Could not fetch complete financial data for {ticker}.")
                st.session_state.dcf_step = "initial"
                st.rerun()

    # --- Block 3: Reviewing assumptions ---
    if st.session_state.dcf_step == "review":
        st.subheader("🔬 Review AI-Generated Assumptions")
        st.markdown("The AI has generated forecasts based on its analysis. Review them below and revise if necessary.")
        
        temp_results = perform_dcf_calculations(st.session_state.dcf_financials, st.session_state.dcf_assumptions, st.session_state.dcf_wacc_input)
        currency_symbol = get_currency_symbol(st.session_state.dcf_ticker)

        def format_preview_df(df, symbol):
            df_display = df.copy()
            for col in df_display.columns:
                if df_display[col].dtype in ['int64', 'float64']: df_display[col] = df_display[col].apply(lambda x: f"{symbol}{x/1e6:,.1f}M")
            return df_display.transpose()

        if temp_results and 'forecasts' in temp_results:
            for case in ["Base", "Bull", "Bear"]:
                with st.expander(f"**{case} Case Forecast**", expanded=(case=="Base")):
                    st.dataframe(format_preview_df(temp_results['forecasts'][case], currency_symbol), use_container_width=True)
        
        with st.form("revision_form"):
            current = st.session_state.dcf_assumptions
            c1, c2, c3 = st.columns(3)
            with c1: st.subheader("Base Case"); base_rev = st.number_input("Revenue CAGR (%)", value=current['Base']['revenue_cagr']*100, key="dcf_rev_base", format="%.2f"); base_ebitda = st.number_input("EBITDA Margin (%)", value=current['Base']['ebitda_margin']*100, key="dcf_margin_base", format="%.2f")
            with c2: st.subheader("Bull Case"); bull_rev = st.number_input("Revenue CAGR (%)", value=current['Bull']['revenue_cagr']*100, key="dcf_rev_bull", format="%.2f"); bull_ebitda = st.number_input("EBITDA Margin (%)", value=current['Bull']['ebitda_margin']*100, key="dcf_margin_bull", format="%.2f")
            with c3: st.subheader("Bear Case"); bear_rev = st.number_input("Revenue CAGR (%)", value=current['Bear']['revenue_cagr']*100, key="dcf_rev_bear", format="%.2f"); bear_ebitda = st.number_input("EBITDA Margin (%)", value=current['Bear']['ebitda_margin']*100, key="dcf_margin_bear", format="%.2f")
            
            if st.form_submit_button("✅ Confirm Assumptions & Generate Full Report", use_container_width=True):
                st.session_state.dcf_assumptions['Base'].update({'revenue_cagr': base_rev/100, 'ebitda_margin': base_ebitda/100})
                st.session_state.dcf_assumptions['Bull'].update({'revenue_cagr': bull_rev/100, 'ebitda_margin': bull_ebitda/100})
                st.session_state.dcf_assumptions['Bear'].update({'revenue_cagr': bear_rev/100, 'ebitda_margin': bear_ebitda/100})
                st.session_state.dcf_step = "processing_final"
                # CRITICAL FIX: No st.rerun() here. The natural rerun from the form submission is sufficient.

    # --- Block 4: Final calculation ---
    if st.session_state.dcf_step == "processing_final":
        with st.spinner("Finalizing valuation..."):
            results = perform_dcf_calculations(
                st.session_state.dcf_financials, 
                st.session_state.dcf_assumptions, 
                st.session_state.dcf_wacc_input, 
                terminal_multiples=st.session_state.get('dcf_terminal_multiples')
            )
            st.session_state.dcf_results_data = results
            
            if results and results.get('base_case_terminal_fcf_is_negative') and 'dcf_terminal_multiples' not in st.session_state:
                st.session_state.dcf_step = "request_multiples"
                st.rerun() # This rerun is correct as it's a conditional branch.
            else:
                st.session_state.dcf_valuation_method = 'EV/EBITDA Multiple' if 'dcf_terminal_multiples' in st.session_state else 'Perpetuity Growth'
                st.session_state.dcf_step = "complete"
                # CRITICAL FIX: No st.rerun() here. Let the script "fall through" to the complete block.

    # --- Block 5: Optional step for providing multiples ---
    if st.session_state.dcf_step == "request_multiples":
        st.warning("⚠️ Action Required: Negative terminal FCF projected. Provide EV/EBITDA multiples.", icon="⚠️")
        with st.form("multiples_form"):
            st.subheader("⚙️ Terminal Value Assumptions")
            m1, m2, m3 = st.columns(3)
            base_m = m1.number_input("Base Case EV/EBITDA", 5.0, 35.0, 15.0, 0.5)
            bull_m = m2.number_input("Bull Case EV/EBITDA", 5.0, 35.0, 18.0, 0.5)
            bear_m = m3.number_input("Bear Case EV/EBITDA", 5.0, 35.0, 12.0, 0.5)
            if st.form_submit_button("🔄 Re-run with EV/EBITDA Multiples", use_container_width=True):
                st.session_state.dcf_terminal_multiples = {"Base": base_m, "Bull": bull_m, "Bear": bear_m}
                st.session_state.dcf_step = "processing_final"
                st.rerun()

    # --- Block 6: Displaying the final report ---
    if st.session_state.dcf_step == "complete":
        st.success("✅ Analysis Complete!")
        st.markdown(format_report_as_html(st.session_state), unsafe_allow_html=True)
        
        if st.button("🔄 Start New Analysis"):
            keys_to_delete = [key for key in st.session_state.keys() if key.startswith('dcf_')]
            for key in keys_to_delete:
                del st.session_state[key]
            st.session_state.dcf_step = "initial"
            st.rerun()
                


# ==============================================================================
# 4. Agent Special Situations
# (Code from app - SpecialSituations.py)
# ==============================================================================
def special_situations_app():
    """
    Encapsulates the complete Agent Special Situations functionality,
    including memo generation, a valuation module, and infographic creation.
    """

    # ========== CONFIG & SETUP ==========
    # This section handles API key loading and global constants.
    try:
        DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
    except (KeyError, FileNotFoundError):
        st.error("DeepSeek API key not found. Please add it to your Streamlit secrets.")
        st.stop()

    DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

    try:
        FMP_API_KEY = os.environ.get("FMP_API_KEY")
    except (KeyError, FileNotFoundError):
        st.error("FMP API key not found. Please add it to your Streamlit secrets.")
        st.stop()

    # ==========================
    # REPORT & INFOGRAPHIC STRUCTURES
    # ==========================
    REPORT_TEMPLATES = {
        "Spin-Off or Split-Up": """
Transaction Overview
ParentCo Post-Spin Outlook
SpinCo Investment Case
Valuation Analysis
Risks and Overhangs
""",
        "Mergers & Acquisitions": """
Deal Summary
Target Company Analysis
Buyer’s Rationale and Financing
Shareholder Vote & Antitrust Risk
Spread Analysis and Arbitrage Opportunity
""",
        "Bankruptcy / Distressed / Restructuring": """
Situation Summary
Capital Structure Analysis
Valuation and Recovery Scenarios
Reorganization Plan and Exit Timeline
Catalysts and Legal Risks
""",
        "Activist Campaign": """
Activist Background
Campaign Details
Company's Response and Governance Profile
Scenario Analysis
Valuation Impact
""",
        "Regulatory or Legal Catalyst": """
Legal/Regulatory Background
Outcome Scenarios
Financial and Strategic Implications
Market Reaction History
""",
        "Asset Sales or Carve-Outs": """
Transaction Overview
Strategic Impact
Use of Proceeds
Re-rating Potential
""",
        "Capital Raising or Buyback Catalyst": """
Transaction Mechanics
Capital Structure Post-Deal
Shareholder Implications
Buyback Analysis
"""
    }

    FALLBACK_META = [
        ("💼", "border-blue-600", "bg-blue-50"),
        ("🏢", "border-sky-600", "bg-sky-50"),
        ("🌐", "border-indigo-600", "bg-indigo-50"),
        ("🧩", "border-purple-600", "bg-purple-50"),
        ("📊", "border-green-600", "bg-green-50"),
        ("📈", "border-emerald-600", "bg-emerald-50"),
        ("👥", "border-yellow-600", "bg-yellow-50"),
        ("⚠️", "border-red-600", "bg-red-50"),
        ("💡", "border-pink-600", "bg-pink-50"),
        ("🧠", "border-gray-600", "bg-gray-50"),
    ]

    # ==========================
    # HELPER FUNCTIONS
    # ==========================

    # --- Text Extractors ---
    def extract_text_from_pdf(file):
        try:
            with pdfplumber.open(file) as pdf:
                return "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
        except Exception as e:
            return f"[ERROR extracting PDF: {e}]"

    def extract_text_from_docx(file):
        try:
            doc = Document(file)
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as e:
            return f"[ERROR extracting DOCX: {e}]"

    # --- Automated Financial Data Extraction for SOTP ---
    @st.cache_data(ttl=3600, show_spinner=False)
    def extract_financials_for_sotp(text: str, company_name: str) -> Dict:
        """Uses an LLM to extract structured financial data for SOTP analysis."""
        prompt = f"""
        Act as a financial analyst. From the documents about {company_name}'s spin-off, extract the key financials for each business segment.
        Identify the future Parent Company (likely the core remaining business, e.g., Tires), the Spin-Off company (e.g., Automotive/AUMOVIO), and any other major divisions mentioned that will be divested.

        Return a single, valid JSON object with the following structure. Use 'null' if a value is not found. All financial values should be in billions.
        {{
          "parent_co": {{
            "name": "Name of Parent Company (e.g., New Continental)",
            "segment_name": "Core Segment (e.g., Tires)",
            "sales": 14.0,
            "ebit": 1.9,
            "ebit_margin": 13.5
          }},
          "spin_co": {{
            "name": "Name of Spin-off (e.g., AUMOVIO)",
            "segment_name": "Spin-off Segment (e.g., Automotive)",
            "sales": 20.8,
            "ebit": 0.4,
            "ebit_margin": 1.9
          }},
          "other_divestitures": [
            {{
              "name": "Name of other segment to be sold (e.g., ContiTech)",
              "sales": 6.8,
              "ebit": 0.45,
              "ebit_margin": 6.7
            }}
          ],
          "currency": "EUR",
          "unit": "billion"
        }}

        CONTEXT:
        {text[:30000]}
        """
        headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
        payload = {"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0, "response_format": {"type": "json_object"}}
        try:
            res = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=90)
            res.raise_for_status()
            response_json = json.loads(res.json()["choices"][0]["message"]["content"])
            if 'parent_co' in response_json and 'spin_co' in response_json:
                return response_json
            return None
        except Exception as e:
            st.warning(f"Could not automatically extract structured financials: {e}")
            return None

    # --- NEWLY ADDED: Automated Multiple Assignment ---
    def get_valuation_multiples(sotp_financials: Dict) -> Dict:
        """Assigns reasonable valuation multiples based on business characteristics."""
        multiples = {}
        
        def get_multiple_for_segment(segment):
            if not segment or segment.get('sales') is None:
                return None
                
            margin = segment.get('ebit_margin')
            
            # Use EBIT multiple if profit is meaningful (e.g., > 100 million or >1% margin)
            if segment.get('ebit') and segment['ebit'] > 0.1:
                # Higher margin, stable businesses get higher multiples
                multiple_range = [7.0, 9.0] if margin and margin < 10.0 else [8.0, 10.0]
                return {"type": "EV/EBIT", "range": multiple_range, "metric": segment.get('ebit')}
            # Fallback to Sales multiple if profit is low, zero, or negative
            else:
                return {"type": "EV/Sales", "range": [0.4, 0.6], "metric": segment.get('sales')}

        if financials := sotp_financials.get('parent_co'):
            multiples['parent_co'] = get_multiple_for_segment(financials)
        if financials := sotp_financials.get('spin_co'):
            multiples['spin_co'] = get_multiple_for_segment(financials)
        
        for i, segment in enumerate(sotp_financials.get('other_divestitures', [])):
             multiples[f'other_divestitures_{i}'] = get_multiple_for_segment(segment)
             
        return multiples

    # --- Financial Data Fetchers ---
    @st.cache_data(ttl=3600, show_spinner=False)
    def resolve_company_to_ticker(company_name: str) -> str:
        prompt = f"What is the stock ticker (FMP-compatible) for the public company '{company_name}'?"
        headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
        payload = {"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0}
        try:
            res = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload)
            res.raise_for_status()
            ticker = res.json()["choices"][0]["message"]["content"].strip()
            return re.sub(r'[^A-Z\.]', '', ticker)
        except:
            return None

    @st.cache_data(ttl=3600, show_spinner=False)
    def get_ev_ebitda_multiple(ticker: str, fmp_key: str) -> float:
        url = f"https://financialmodelingprep.com/api/v3/key-metrics-ttm/{ticker}?apikey={fmp_key}"
        try:
            r = requests.get(url)
            data = r.json()
            if isinstance(data, list) and data:
                return float(data[0].get("enterpriseValueOverEBITDATTM", 0))
        except:
            return 0.0

    @st.cache_data(ttl=3600, show_spinner=False)
    def fetch_fundamentals_yf(ticker: str) -> Tuple[float, float, float]:
        """Returns (market_cap, net_debt, ttm_ebitda) via Yahoo Finance."""
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}
            market_cap, total_debt, cash = info.get("marketCap", 0) or 0, info.get("totalDebt", 0) or 0, info.get("cash", 0) or 0
            net_debt = total_debt - cash
            ebitda = info.get("ebitda", 0) or 0
            return float(market_cap), float(net_debt), float(ebitda)
        except Exception:
            return 0.0, 0.0, 0.0

    # --- Text & Document Processors ---
    def clean_markdown(text):
        text = re.sub(r'^[ \t\-]{3,}$', '', text, flags=re.MULTILINE)
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        text = re.sub(r'\*(.*?)\*', r'\1', text)
        text = re.sub(r'`{1,3}(.*?)`{1,3}', r'\1', text)
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'^- ', '• ', text, flags=re.MULTILINE)
        return text.strip()

    def truncate_safely(text, limit=30000):
        return text[:limit]

    def split_into_sections(raw_text: str, template: str) -> Dict[str, str]:
        sections = {}
        titles = [line.split('(')[0].strip() for line in template.strip().split('\n') if line.strip()]
        if not titles: return {"Investment Memo": raw_text.strip()}
        pattern = re.compile(r"^#+\s*(" + "|".join(map(re.escape, titles)) + r")\s*$", re.MULTILINE | re.IGNORECASE)
        matches = list(pattern.finditer(raw_text))
        if not matches:
            st.warning("Could not find structured headings in the AI's response.")
            return {"Investment Memo": raw_text.strip()}
        for i, match in enumerate(matches):
            title_from_text = match.group(1).strip()
            canonical_title = next((t for t in titles if t.lower() == title_from_text.lower()), title_from_text)
            start_of_content = match.end()
            end_of_content = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
            content = raw_text[start_of_content:end_of_content].strip()
            if content: sections[canonical_title] = content
        return sections

    def format_memo_docx(memo_dict: dict, company_name: str, situation_type: str):
        doc = Document()
        style = doc.styles['Normal']
        style.font.name = 'Aptos Display'
        style.font.size = Pt(11)
        title_para = doc.add_paragraph()
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_run = title_para.add_run(f"{company_name} – {situation_type} Investment Memo")
        title_run.font.name = 'Aptos Display'
        title_run.font.size = Pt(20)
        title_run.bold = True
        doc.add_paragraph()
        for section_title, content in memo_dict.items():
            heading = doc.add_paragraph()
            run = heading.add_run(section_title)
            run.bold = True
            run.font.size = Pt(14)
            heading.paragraph_format.space_after = Pt(6)
            for para in content.strip().split('\n\n'):
                if para.strip():
                    p = doc.add_paragraph(para.strip())
                    p.paragraph_format.space_before = Pt(0)
                    p.paragraph_format.space_after = Pt(6)
                    p.paragraph_format.line_spacing = 1.3
        section = doc.sections[0]
        section.left_margin, section.right_margin, section.top_margin, section.bottom_margin = (Inches(0.75),)*4
        return doc

    # --- Core Memo Generator ---
    def generate_special_situation_note(
        company_name: str,
        situation_type: str,
        uploaded_files: list,
        valuation_mode: str = "Automated SOTP Analysis",
        parent_peers: str = "",
        spinco_peers: str = ""
    ):
        # 1) Extract text from uploaded documents
        combined_text = ""
        for file in uploaded_files:
            if file.name.endswith(".pdf"): combined_text += extract_text_from_pdf(file) + "\n"
            elif file.name.endswith(".docx"): combined_text += extract_text_from_docx(file) + "\n"
            else: combined_text += f"[Unsupported file: {file.name}]\n"

        # 2) Select the appropriate report structure
        structure = REPORT_TEMPLATES.get(situation_type)
        if not structure: raise ValueError(f"Unsupported situation type: {situation_type}")

        # 3) Build valuation section for Spin-Offs
        valuation_section = ""
        if situation_type == "Spin-Off or Split-Up":
            try:
                sotp_data = extract_financials_for_sotp(combined_text, company_name)
                if not sotp_data: raise ValueError("Financial data for SOTP not found in documents.")

                multiples = {}
                if valuation_mode == "Use Manual Peers":
                    st.info("Using manually provided peers for valuation.")
                    def process_peers(raw_peers):
                        names = [n.strip() for n in raw_peers.split(",") if n.strip()]
                        if not names: return None
                        tickers = [resolve_company_to_ticker(n) for n in names]
                        mults = [get_ev_ebitda_multiple(t, FMP_API_KEY) for t in tickers if t]
                        return round(sum(mults) / len(mults), 2) if mults else None
                    
                    parent_multiple = process_peers(parent_peers) or 8.0 # Fallback
                    spinco_multiple = process_peers(spinco_peers) or 8.0 # Fallback
                    
                    multiples['parent_co'] = {"type": "EV/EBIT", "range": [parent_multiple, parent_multiple], "metric": sotp_data.get('parent_co',{}).get('ebit')}
                    multiples['spin_co'] = {"type": "EV/EBIT", "range": [spinco_multiple, spinco_multiple], "metric": sotp_data.get('spin_co',{}).get('ebit')}
                else: # Default to Automated SOTP
                    st.info("Attempting automated SOTP analysis.")
                    multiples = get_valuation_multiples(sotp_data)

                results, total_low, total_high = [], 0, 0
                def calculate_segment_value(segment_key, segment_data):
                    mult_info = multiples.get(segment_key)
                    if not mult_info or not mult_info.get('metric') or mult_info.get('metric') <= 0: return None, 0, 0
                    low_val = mult_info['metric'] * mult_info['range'][0]; high_val = mult_info['metric'] * mult_info['range'][1]
                    results.append({
                        "name": segment_data.get('name', 'N/A'), "metric_val": mult_info['metric'], "multiple_type": mult_info['type'],
                        "multiple_range": f"{mult_info['range'][0]}x - {mult_info['range'][1]}x", "low_val": low_val, "high_val": high_val,
                        "unit": sotp_data.get('unit', 'billion'), "currency": sotp_data.get('currency', '$')})
                    return True, low_val, high_val
                
                _, low, high = calculate_segment_value('parent_co', sotp_data.get('parent_co'))
                total_low += low; total_high += high
                _, low, high = calculate_segment_value('spin_co', sotp_data.get('spin_co'))
                total_low += low; total_high += high
                for i, segment in enumerate(sotp_data.get('other_divestitures', [])):
                     _, low, high = calculate_segment_value(f'other_divestitures_{i}', segment)
                     total_low += low; total_high += high
                
                currency_symbol = '€' if sotp_data.get('currency') == 'EUR' else '$'
                unit_label = sotp_data.get('unit', 'billion')

                valuation_section += "## Valuation Analysis\n"
                valuation_section += f"Based on a Sum-of-the-Parts (SOTP) analysis, the implied total enterprise value is **{currency_symbol}{total_low:.1f} to {currency_symbol}{total_high:.1f} {unit_label}**.\n\n"
                valuation_section += "| Business Segment | Key Metric | Multiple | Implied Value Range |\n|:---|:---|:---|:---|\n"
                for res in results:
                    metric_str = f"{currency_symbol}{res['metric_val']:.1f} {unit_label} {res['multiple_type'].split('/')[1]}"
                    value_str = f"{currency_symbol}{res['low_val']:.1f} - {currency_symbol}{res['high_val']:.1f} {unit_label}"
                    valuation_section += f"| **{res['name']}** | {metric_str} | {res['multiple_range']} {res['multiple_type']} | {value_str} |\n"
                valuation_section += "\n[AI, please use this quantitative SOTP data to write a detailed narrative for the valuation analysis section.]"

            except Exception as e:
                st.warning(f"Automated SOTP analysis failed ({e}). Falling back to qualitative analysis.")
                valuation_section = ("## Valuation Analysis\n"
                                     "[AI, please generate a qualitative discussion on the potential valuation based on the documents.]")

        # 4) Assemble the corrected main prompt
        prompt = f"""You are an institutional investment analyst writing a professional memo on {company_name}'s {situation_type}.
        CONTEXT DOCUMENTS: \"\"\"{truncate_safely(combined_text)}\"\"\"
        VALUATION DATA (If available): {valuation_section}
        CRITICAL INSTRUCTIONS:
        1. Generate a detailed, well-written memo with comprehensive paragraphs for each section.
        2. Write in a narrative style. Each section should have at least 2-3 detailed paragraphs.
        3. You MUST use the exact section titles from the 'STRUCTURE' list below as level 2 markdown headings (e.g., `## Deal Summary`).
        4. If quantitative 'Valuation Analysis' data is provided, you MUST use it as the foundation for that section's narrative.
        5. **ABSOLUTELY NO** conversational introductions or conclusions (e.g., "Of course, here is..."). The response must start directly with the first markdown heading.

        STRUCTURE:
        {structure}"""

        # 5) Call LLM and process response
        response = requests.post(DEEPSEEK_API_URL, headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}, json={"model":"deepseek-chat","messages":[{"role":"user","content":prompt}],"temperature":0.3})
        response.raise_for_status()
        raw_memo_text = response.json()["choices"][0]["message"]["content"]
        memo_dict_raw = split_into_sections(raw_memo_text, structure)
        memo_dict_cleaned = {title: clean_markdown(content) for title, content in memo_dict_raw.items()}
        
        # 6) Generate and save Word document
        doc = format_memo_docx(memo_dict_cleaned, company_name, situation_type)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            doc.save(tmp.name)
            return tmp.name

    # --- Infographic Functions ---
    def extract_sections_from_docx_for_infographic(file, situation_type: str) -> Dict[str, str]:
        toc = REPORT_TEMPLATES.get(situation_type)
        if not toc: return {}
        expected_titles = {t.split('(')[0].strip().lower() for t in toc.strip().splitlines() if t.strip()}
        doc = Document(file)
        sections, current_heading, current_text = {}, None, []
        all_headings = [p.text.strip() for p in doc.paragraphs if p.runs and all(r.bold for r in p.runs if r.text.strip())]
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text: continue
            is_heading = text in all_headings and text.lower() in expected_titles
            if is_heading:
                if current_heading and current_text: sections[current_heading] = "\n".join(current_text).strip()
                current_heading, current_text = text, []
            elif current_heading: current_text.append(text)
        if current_heading and current_text: sections[current_heading] = "\n".join(current_text).strip()
        return sections

    def summarize_section_with_deepseek(section_title, section_text):
        prompt = f"""
You are an institutional research analyst preparing a financial infographic.
Your task is to summarize the provided section text into 3 to 5 concise bullet points.
Each point must be a single sentence, highlighting key insights clearly and professionally.
**CRITICAL INSTRUCTION:** Do NOT include any introductory or concluding phrases. Your response must begin directly with the first bullet point.
Section to Summarize:
\"\"\"{section_text}\"\"\"
"""
        headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
        payload = {"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    def build_infographic_html(company_name, sections):
        html = f"""
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8" /><meta name="viewport" content="width=device-width, initial-scale=1.0"/><title>{company_name} – Infographic</title><script src="https://cdn.tailwindcss.com"></script><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet"><style>body {{ font-family: 'Inter', sans-serif; background-color: #f9fafb; color: #1f2937; }} .section-icon {{ font-size: 1.4rem; margin-right: 0.6rem; }}</style></head><body class="px-4 py-8 md:px-6 md:py-10 max-w-7xl mx-auto"><header class="text-center mb-12"><h1 class="text-3xl md:text-4xl font-bold text-gray-800 mb-2">{company_name} – Investment Memo Infographic</h1><p class="text-sm text-gray-500">Generated by ARANC'AI'</p></header><main class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">"""
        with st.spinner("Summarizing sections for infographic..."):
            for idx, (title, section_text) in enumerate(sections.items()):
                icon, border_class, bg_class = FALLBACK_META[idx % len(FALLBACK_META)]
                try:
                    summary = summarize_section_with_deepseek(title, section_text)
                    cleaned_summary = summary.replace('**', '').replace('###', '').replace('##', '').replace('#', '')
                    lines = [line.lstrip("•*- ").strip() for line in cleaned_summary.split("\n") if line.strip()]
                    bullet_items = "\n".join(f"                    <li>{line}</li>" for line in lines)
                except Exception as e:
                    bullet_items = f"<li>Error generating summary: {e}</li>"
                    st.warning(f"Could not summarize section: '{title}'")
                html += f"""
        <div class="shadow-lg rounded-xl p-5 transition-transform hover:scale-[1.02] duration-300 ease-in-out border-l-4 {border_class} {bg_class}"><h2 class="text-lg font-semibold text-gray-800 mb-3 flex items-center"><span class="section-icon">{icon}</span>{title}</h2><ul class="list-disc text-sm text-gray-700 space-y-2 pl-5 leading-relaxed">{bullet_items}</ul></div>"""
        html += """
    </main><footer class="text-center mt-12"><p class="text-xs text-gray-400">This document is for informational purposes only and does not constitute investment advice.</p></footer></body></html>"""
        return html

    # ==========================
    # STREAMLIT UI & APP LOGIC
    # ==========================
    st.markdown("### 🔀 Agent Special Situations")
    st.subheader("Step 1: Generate Investment Memo")

    company_name_memo = st.text_input("Enter Company Name", key="company_name_memo")
    situation_type_memo = st.selectbox("Select Situation Type", options=list(REPORT_TEMPLATES.keys()), key="situation_type_memo")
    
    valuation_mode = "Automated SOTP Analysis"
    parent_peers_raw = ""
    spinco_peers_raw = ""

    if situation_type_memo == "Spin-Off or Split-Up":
        st.markdown("##### 🔍 Valuation Approach")
        valuation_mode = st.radio(
            "Choose a valuation approach for the SOTP analysis:",
            options=["Automated SOTP Analysis", "Use Manual Peers"],
            key="valuation_mode",
            horizontal=True,
            help="Automated analysis is the default. Choose manual to provide your own peer companies."
        )
        if valuation_mode == "Use Manual Peers":
            parent_peers_raw = st.text_area("Enter ParentCo Peer Company Names (comma-separated)", key="parent_peers_raw")
            spinco_peers_raw = st.text_area("Enter SpinCo Peer Company Names (comma-separated)", key="spinco_peers_raw")

    uploaded_files_memo = st.file_uploader("Upload Public Documents (PDF, DOCX)", accept_multiple_files=True, key="uploaded_files_memo")
    # --- NEW UI for Custom Prompt ---
    st.markdown("---")
    st.subheader("Advanced: Customize Memo Prompt")
    st.info("You can provide a custom prompt template below. The agent may require your prompt to ask for a memo based on a specific structure.")
    st.text_area(
        "Enter your custom prompt template:",
        placeholder="Enter your full custom prompt for the memo generation here...",
        height=250,
        key="situations_custom_prompt"
    )
    # --- END NEW UI ---
    if st.button("Generate Memo", type="primary"):
        if not company_name_memo or not situation_type_memo or not uploaded_files_memo:
            st.warning("Please fill in all fields and upload at least one document.")
        else:
            with st.spinner("Generating memo... This may take a moment."):
                try:
                    memo_path = generate_special_situation_note(
                        company_name=company_name_memo,
                        situation_type=situation_type_memo,
                        uploaded_files=uploaded_files_memo,
                        valuation_mode=valuation_mode,
                        parent_peers=parent_peers_raw,
                        spinco_peers=spinco_peers_raw
                    )
                    st.session_state.memo_path = memo_path
                    st.session_state.company_name = company_name_memo
                    st.session_state.situation_type = situation_type_memo
                    
                    st.success("Memo generated successfully!")
                    with open(memo_path, "rb") as f:
                        st.download_button(
                            label="Download Memo (.docx)",
                            data=f,
                            file_name=f"{company_name_memo}_{situation_type_memo}_Memo.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
                except Exception as e:
                    st.error(f"An error occurred during memo generation: {e}")

    st.markdown("\n\n---\n\n")

    st.subheader("Step 2: Generate Infographic from Memo")
    st.info("After generating the memo, you can either upload it below or, if you just generated it, the app will use it automatically.")
    uploaded_memo_infographic = st.file_uploader("Upload the generated Memo (.docx)", type=["docx"], key="uploaded_memo_infographic")

    if st.button("Generate Infographic", type="primary"):
        memo_file_to_use = uploaded_memo_infographic
        if not memo_file_to_use and 'memo_path' in st.session_state:
            memo_file_to_use = st.session_state.memo_path
        
        company_name_infographic = st.session_state.get('company_name', '')
        situation_type_infographic = st.session_state.get('situation_type')

        if not memo_file_to_use or not company_name_infographic or not situation_type_infographic:
            st.warning("Please generate a memo first in Step 1, or upload a previously generated memo.")
        else:
            with st.spinner("Extracting sections and generating infographic..."):
                try:
                    sections = extract_sections_from_docx_for_infographic(memo_file_to_use, situation_type_infographic)
                    if not sections:
                         st.error("Could not extract any sections from the document. Please ensure the memo was generated correctly with clear headings.")
                    else:
                        st.success(f"Successfully extracted {len(sections)} sections. Building infographic...")
                        html_content = build_infographic_html(company_name_infographic, sections)
                        
                        st.subheader("Infographic Preview")
                        st.components.v1.html(html_content, height=800, scrolling=True)

                        st.download_button(
                            label="Download Infographic (.html)",
                            data=html_content,
                            file_name=f"{company_name_infographic}_Infographic.html",
                            mime="text/html"
                        )
                except Exception as e:
                    st.error(f"An error occurred during infographic generation: {e}")

# ==============================================================================
# 5. ESG ANALYZER
# (Code from app-ESG.py and ESGComp.py)
# ==============================================================================


def esg_analyzer_app():
    """
    Encapsulates the ESG Analyzer with a final, professional, data-rich dashboard.
    This version is updated to be more robust by breaking the analysis into multiple, smaller API calls to prevent timeouts with large documents.
    """
    # --- Imports ---
    import re
    from datetime import datetime
    import html
    import json
    import fitz  # PyMuPDF
    import requests
    from bs4 import BeautifulSoup
    from openai import AzureOpenAI

    st.markdown("### ✨ Advanced ESG Analyzer")
    st.markdown("Generate a professional ESG dashboard or a detailed insight report from sustainability disclosures.")

    # --- Core Helper Functions ---
    def get_benchmark_rating(score):
        try:
            s = float(score)
            if s >= 8.0: return ("Leading", "#27ae60")
            if s >= 5.0: return ("Average", "#f39c12")
            return ("Lagging", "#e74c3c")
        except (ValueError, TypeError):
            return ("N/A", "#7f8c8d")

    def extract_text_from_pdf_esg(pdf_file):
        try:
            pdf_bytes = pdf_file.getvalue()
            pdf_file.seek(0)
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            return "\n\n".join(page.get_text("text") for page in doc if page.get_text("text").strip())
        except Exception as e:
            st.error(f"Error reading PDF: {e}")
            return ""

    # --- START: REVISED, MULTI-STAGE ANALYSIS FUNCTION ---
    def analyze_esg_in_stages(text: str) -> dict:
        """
        Performs ESG analysis in multiple stages to avoid API timeouts.
        Stage 1: Get summary and scores.
        Stage 2: Get KPIs and takeaways for each pillar separately.
        """
        if not text.strip():
            return {"error": "No text provided for analysis."}
            
        try:
            # Initialize client inside the function that uses it
            client = AzureOpenAI(
                api_key=os.environ.get("AZURE_OPENAI_KEY"),
                api_version="2024-02-01",
                azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT")
            )
            deployment_name = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
        except Exception as e:
            st.error(f"Failed to initialize Azure OpenAI client: {e}")
            return {"error": f"Azure client initialization failed: {e}"}

        full_esg_data = {}
        
        # --- Stage 1: Get overall summary and scores ---
        with st.spinner("Analyzing overall posture and generating scores... (Stage 1/4)"):
            try:
                prompt_stage1 = f"""
                You are an expert ESG analyst. Based on the provided ESG report, perform the following two tasks:
                1. Write a concise, 2-3 sentence narrative summary of the company's overall ESG posture.
                2. Provide an estimated score from 0.0 to 10.0 for the overall performance and for each of the E, S, and G pillars.

                Return a single, valid JSON object with the following keys: "executive_summary", "overall_score", "environmental_score", "social_score", "governance_score".

                DOCUMENT TEXT:
                ---
                {text[:80000]}
                ---
                """
                response_stage1 = client.chat.completions.create(
                    model=deployment_name,
                    messages=[{"role": "user", "content": prompt_stage1}],
                    response_format={"type": "json_object"},
                    temperature=0.1
                )
                summary_and_scores = json.loads(response_stage1.choices[0].message.content)
                full_esg_data.update(summary_and_scores)
            except Exception as e:
                st.error(f"Error during Stage 1 (Summary & Scores): {e}")
                return {"error": f"Failed at Stage 1: {e}"}

        # --- Stage 2: Get details for each pillar individually ---
        pillars = ["environmental", "social", "governance"]
        full_esg_data["kpis"] = {}
        full_esg_data["pillar_takeaways"] = {}
        full_esg_data["environmental_insights"] = [] # Initialize for classic report
        full_esg_data["social_insights"] = []
        full_esg_data["governance_insights"] = []


        for i, pillar in enumerate(pillars):
            with st.spinner(f"Extracting KPIs and takeaways for {pillar.title()} pillar... (Stage {i+2}/4)"):
                try:
                    prompt_stage2 = f"""
                    You are an ESG analyst focused on the '{pillar.title()}' pillar. From the provided ESG report text, perform the following tasks:
                    1.  Identify the 4-5 most relevant and quantifiable Key Performance Indicators (KPIs). For each KPI, provide its icon, title, value, unit, a brief context, and a rating ('Positive', 'Neutral', 'Negative').
                    2.  Provide one or two key takeaways summarizing the company's performance.
                    3.  Extract a list of detailed insights, where each insight is an object with "subcategory" and "detail".

                    Return a single, valid JSON object with three keys: "kpis" (a list of objects), "takeaways" (a list of strings), and "insights" (a list of objects).
                    
                    DOCUMENT TEXT:
                    ---
                    {text[:80000]}
                    ---
                    """
                    response_stage2 = client.chat.completions.create(
                        model=deployment_name,
                        messages=[{"role": "user", "content": prompt_stage2}],
                        response_format={"type": "json_object"},
                        temperature=0.1
                    )
                    pillar_data = json.loads(response_stage2.choices[0].message.content)
                    full_esg_data["kpis"][pillar] = pillar_data.get("kpis", [])
                    full_esg_data["pillar_takeaways"][pillar] = pillar_data.get("takeaways", [])
                    full_esg_data[f"{pillar}_insights"] = pillar_data.get("insights", []) # For classic report
                except Exception as e:
                    st.error(f"Error during Stage 2 ({pillar.title()}): {e}")
                    # Continue even if one pillar fails, initializing empty lists
                    full_esg_data["kpis"][pillar] = []
                    full_esg_data["pillar_takeaways"][pillar] = []
                    full_esg_data[f"{pillar}_insights"] = []


        return full_esg_data
    # --- END: REVISED ANALYSIS FUNCTION ---

    # --- Helper functions for generating SVG charts ---
    def _create_gauge_chart_svg(score, size=180):
        if not isinstance(score, (int, float)): return ""
        score = max(0, min(10, score)); percentage = score / 10
        color = get_benchmark_rating(score)[1]
        return f"""<svg width="{size}" height="{size/2}" viewBox="0 0 100 50" class="gauge"><path d="M10 50 A 40 40 0 0 1 90 50" stroke="#e9ecef" stroke-width="10" fill="none" /><path d="M10 50 A 40 40 0 0 1 90 50" stroke="{color}" stroke-width="10" fill="none" stroke-dasharray="{percentage * 125.6}, 125.6" stroke-linecap="round" /><text x="50" y="45" text-anchor="middle" class="gauge-value">{score:.1f}</text></svg>"""

    def _create_donut_chart_svg(value, size=100, color="#00416A", title=""):
        """Creates a donut chart SVG using the reliable stroke-dasharray method."""
        if not isinstance(value, (int, float)): return ""
        value = max(0, min(100, value))
        radius = 15.9155; circumference = 2 * 3.14159 * radius; arc_length = (value / 100) * circumference
        return f"""
        <div class="donut-container">
            <svg width="{size}" height="{size}" viewBox="0 0 36 36" class="donut-chart">
                <circle cx="18" cy="18" r="{radius}" fill="none" stroke="#e9ecef" stroke-width="3" />
                <circle cx="18" cy="18" r="{radius}" fill="none" stroke="{color}" stroke-width="3.2"
                        stroke-dasharray="{arc_length} {circumference}"
                        transform="rotate(-90 18 18)"
                        stroke-linecap="round" />
                <text x="18" y="20.5" text-anchor="middle" class="donut-value">{int(value)}%</text>
            </svg>
            <div class="donut-title">{title}</div>
        </div>
        """

    def _create_water_usage_chart(recycled, fresh, other):
        total = recycled + fresh + other
        if total == 0: return "<p>No water data available.</p>"
        r_pct, f_pct, o_pct = (recycled/total*100), (fresh/total*100), (other/total*100)
        return f"""<div class="sidebar-card"><h3>Water Usage Breakdown</h3><div class="water-bar"><div class="water-segment recycled" style="width: {r_pct}%;" title="Recycled: {recycled}M bbl"></div><div class="water-segment other" style="width: {o_pct}%;" title="Other Sourced: {other}M bbl"></div><div class="water-segment fresh" style="width: {f_pct}%;" title="Fresh: {fresh}M bbl"></div></div><div class="water-legend"><div><span class="dot recycled"></span>Recycled ({r_pct:.0f}%)</div><div><span class="dot other"></span>Other ({o_pct:.0f}%)</div><div><span class="dot fresh"></span>Fresh ({f_pct:.0f}%)</div></div></div>"""

    def generate_esg_dashboard_html(esg_data, company_name):
        safe_company_name = re.sub(r'[^\w\-_]', '_', company_name)[:50]
        current_date = datetime.now().strftime("%B %d, %Y")
        kpis = esg_data.get('kpis', {})
        takeaways = esg_data.get('pillar_takeaways', {})

        def get_rating_color(rating_text):
            return {"Positive": "#27ae60", "Neutral": "#f39c12", "Negative": "#e74c3c"}.get(rating_text, "#6c757d")

        def _create_kpi_card_from_dict(kpi_data):
            if not isinstance(kpi_data, dict): return ""
            icon = kpi_data.get('icon', '💡')
            title = kpi_data.get('title', 'N/A')
            value = kpi_data.get('value', 'None')
            unit = kpi_data.get('unit', '')
            context = kpi_data.get('context', 'No context provided.')
            rating = kpi_data.get('rating', 'Neutral')
            return f"""
            <div class="kpi-card">
                <div class="kpi-header">
                    <span class="kpi-icon">{html.escape(str(icon))}</span>
                    <span class="kpi-title">{html.escape(str(title))}</span>
                    <span class="kpi-rating" style="background-color: {get_rating_color(rating)};">{rating}</span>
                </div>
                <div class="kpi-body">
                    <span class="kpi-value">{html.escape(str(value))}</span>
                    <span class="kpi-unit">{html.escape(str(unit))}</span>
                </div>
                <p class="kpi-context">{html.escape(str(context))}</p>
            </div>
            """

        water_recycled_val = 0; water_fresh_val = 0; water_other_val = 0
        env_kpi_list = kpis.get("environmental", [])
        for kpi in env_kpi_list:
            title_lower = kpi.get('title', '').lower()
            if 'recycled' in title_lower and 'water' in title_lower:
                try: water_recycled_val = float(kpi.get('value', 0))
                except (ValueError, TypeError): pass
            elif 'fresh' in title_lower and 'water' in title_lower:
                try: water_fresh_val = float(kpi.get('value', 0))
                except (ValueError, TypeError): pass

        env_kpi_html = "".join([_create_kpi_card_from_dict(kpi) for kpi in env_kpi_list])
        soc_kpi_html = "".join([_create_kpi_card_from_dict(kpi) for kpi in kpis.get("social", [])])
        gov_kpi_html = "".join([_create_kpi_card_from_dict(kpi) for kpi in kpis.get("governance", [])])
        
        takeaways_html = "<div class='sidebar-card'><h3>Key Pillar Takeaways</h3><ul class='takeaways-list'>"
        takeaway_map = {"environmental": "🌍", "social": "🏢", "governance": "🏛️"}
        for pillar, icon in takeaway_map.items():
            points = takeaways.get(pillar, [])
            if points:
                takeaways_html += f"<li><span class='takeaway-icon'>{icon}</span><div>"
                for point in points:
                    takeaways_html += f"<p>{html.escape(point)}</p>"
                takeaways_html += "</div></li>"
        takeaways_html += "</ul></div>"

        html_content = f"""
        <!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>{company_name} ESG Dashboard</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
            body {{ font-family: 'Poppins', sans-serif; background-color: #f4f7fc; color: #343a40; margin: 0; padding: 20px; }}
            .container {{ max-width: 1400px; margin: auto; background: #ffffff; border-radius: 16px; box-shadow: 0 10px 40px rgba(0,0,0,0.08); padding: 40px; }}
            header h1 {{ font-size: 2.8em; color: #00416A; margin: 0; }}
            header p {{ font-size: 1.2em; color: #6c757d; margin: 5px 0 25px 0; border-bottom: 1px solid #e9ecef; padding-bottom: 25px; }}
            .summary-box {{ background-color: #e6f1f6; padding: 25px; border-radius: 12px; margin-bottom: 35px; font-size: 1.1em; line-height: 1.65; border-left: 5px solid #00416A; }}
            .dashboard-layout {{ display: grid; grid-template-columns: 2.5fr 1fr; gap: 30px; }}
            .main-content {{ display: flex; flex-direction: column; gap: 30px; }}
            .sidebar {{ display: flex; flex-direction: column; gap: 25px; }}
            .sidebar-card {{ background-color: #f8f9fa; border-radius: 12px; padding: 25px; border: 1px solid #e9ecef; }}
            .sidebar-card h3 {{ font-size: 1.4em; color: #00416A; text-align: center; margin: 0 0 15px 0; }}
            .kpi-pillar-section h2 {{ font-size: 1.8em; color: #00416A; margin: 0 0 20px 0; padding-bottom: 10px; border-bottom: 2px solid #00416A; }}
            .kpi-card-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
            .kpi-card {{ background-color: #fff; border: 1px solid #e9ecef; border-radius: 12px; padding: 20px; transition: all 0.2s ease-in-out; display: flex; flex-direction: column; }}
            .kpi-card:hover {{ transform: translateY(-5px); box-shadow: 0 8px 20px rgba(0,0,0,0.08); }}
            .kpi-header {{ display: flex; align-items: center; margin-bottom: 15px; }}
            .kpi-icon {{ font-size: 1.5em; margin-right: 12px; }}
            .kpi-title {{ font-weight: 600; color: #495057; flex-grow: 1; }}
            .kpi-rating {{ font-size: 0.75em; font-weight: 600; color: white; padding: 4px 10px; border-radius: 15px; text-transform: uppercase; }}
            .kpi-body {{ display: flex; align-items: baseline; }}
            .kpi-value {{ font-size: 2.5em; font-weight: 700; color: #00416A; line-height: 1; }}
            .kpi-unit {{ font-size: 1em; color: #6c757d; margin-left: 8px; font-weight: 500; }}
            .kpi-context {{ font-size: 0.9em; color: #6c757d; line-height: 1.5; margin: 10px 0 0 0; flex-grow: 1; }}
            .overall-score-card {{ text-align: center; }}
            .gauge-value {{ font-size: 1.4em; font-weight: 700; fill: #212529; }}
            .rating-badge {{ display: inline-block; padding: 6px 18px; border-radius: 20px; color: #fff; font-weight: 600; font-size: 1em; margin-top: -10px; }}
            .pillar-donuts {{ display: flex; justify-content: space-around; text-align: center; }}
            .donut-value {{ font-size: 0.4em; font-weight: 700; fill: #212529; }}
            .donut-title {{ font-weight: 600; font-size: 0.9em; margin-top: 5px; color: #495057; }}
            .water-bar {{ display: flex; width: 100%; height: 25px; border-radius: 10px; overflow: hidden; margin: 10px 0; }}
            .water-segment.recycled {{ background-color: #2980b9; }}
            .water-segment.other {{ background-color: #bdc3c7; }}
            .water-segment.fresh {{ background-color: #e74c3c; }}
            .water-legend {{ display: flex; justify-content: space-around; font-size: 0.8em; }}
            .water-legend .dot {{ height: 10px; width: 10px; border-radius: 50%; display: inline-block; margin-right: 5px; }}
            .takeaways-list {{ list-style-type: none; padding: 0; margin: 0; }}
            .takeaways-list li {{ display: flex; align-items: flex-start; margin-bottom: 15px; }}
            .takeaway-icon {{ font-size: 1.4em; margin-right: 12px; margin-top: 2px; }}
            .takeaways-list p {{ margin: 0; font-size: 0.9em; line-height: 1.5; color: #495057; }}
        </style></head><body><div class="container">
            <header><h1>{html.escape(company_name)}</h1><p>ESG Performance Dashboard | {current_date}</p></header>
            <p class="summary-box">{html.escape(esg_data.get('executive_summary', 'No summary available.'))}</p>
            <div class="dashboard-layout">
                <div class="main-content">
                    <div class="kpi-pillar-section"><h2>🌍 Environmental</h2><div class="kpi-card-grid">{env_kpi_html}</div></div>
                    <div class="kpi-pillar-section"><h2>🏢 Social</h2><div class="kpi-card-grid">{soc_kpi_html}</div></div>
                    <div class="kpi-pillar-section"><h2>🏛️ Governance</h2><div class="kpi-card-grid">{gov_kpi_html}</div></div>
                </div>
                <div class="sidebar">
                    <div class="sidebar-card overall-score-card">
                        <h3>Overall Score</h3>
                        {_create_gauge_chart_svg(esg_data.get('overall_score'))}
                        <span class="rating-badge" style="background-color:{get_benchmark_rating(esg_data.get('overall_score'))[1]};">{get_benchmark_rating(esg_data.get('overall_score'))[0]}</span>
                    </div>
                    <div class="sidebar-card pillar-donuts">
                        {_create_donut_chart_svg(value=esg_data.get('environmental_score', 0) * 10, color='#27ae60', title='Environmental')}
                        {_create_donut_chart_svg(value=esg_data.get('social_score', 0) * 10, color='#2980b9', title='Social')}
                        {_create_donut_chart_svg(value=esg_data.get('governance_score', 0) * 10, color='#8e44ad', title='Governance')}
                    </div>
                    {_create_water_usage_chart(water_recycled_val, water_fresh_val, water_other_val)}
                    {takeaways_html}
                </div>
            </div>
        </div></body></html>
        """
        return html_content.encode('utf-8'), f"ESG_Dashboard_{safe_company_name}.html"
    
    def generate_html_report_esg(esg_data, company_name):
        safe_company_name = re.sub(r'[^\w\-_]', '_', company_name)[:50]
        current_date = datetime.now().strftime("%B %d, %Y")
        def generate_score_summary_html(title, score):
            rating, color = get_benchmark_rating(score)
            return f"""<div class="score-card"><h4>{title}</h4><div class="score-value">{score}/10</div><div class="benchmark-pill" style="background-color:{color};">{rating}</div></div>"""
        def generate_insight_section(title, icon, insights):
            if not insights: return ""
            rows_html = "".join(f"""<tr><td>{idx}</td><td>{html.escape(str(insight.get('subcategory', 'N/A')))}</td><td>{html.escape(str(insight.get('detail', 'No detail provided.')))}</td></tr>""" for idx, insight in enumerate(insights, 1))
            return f"""<h2><span class="category-icon">{icon}</span>{title}</h2><table><thead><tr><th width="5%">#</th><th width="25%">Category</th><th>Insight Detail</th></tr></thead><tbody>{rows_html}</tbody></table>"""
        html_content = f"""<!DOCTYPE html><html><head><title>{company_name} ESG Insights Report</title><style>body{{font-family:sans-serif;line-height:1.6;}} .container{{max-width:1000px;margin:auto;}} h1,h2{{color:#111827;}} table{{width:100%;border-collapse:collapse;margin:25px 0;}} th,td{{border:1px solid #e5e7eb;padding:12px 15px;}} .score-summary{{display:flex;justify-content:space-around;}} .score-card{{text-align:center;}} .score-value{{font-size:2em;font-weight:bold;}} .benchmark-pill{{display:inline-block;padding:4px 12px;border-radius:9999px;color:white;}}</style></head><body><div class="container"><h1>{company_name} ESG Report</h1><h3>{current_date}</h3><h2>Executive Score Summary</h2><div class="score-summary">{generate_score_summary_html("Overall ESG Score", esg_data.get('overall_score', 'N/A'))}{generate_score_summary_html("Environmental", esg_data.get('environmental_score', 'N/A'))}{generate_score_summary_html("Social", esg_data.get('social_score', 'N/A'))}{generate_score_summary_html("Governance", esg_data.get('governance_score', 'N/A'))}</div>{generate_insight_section("Environmental Insights", "🌍", esg_data.get("environmental_insights", []))}{generate_insight_section("Social Insights", "🏢", esg_data.get("social_insights", []))}{generate_insight_section("Governance Insights", "🏛️", esg_data.get("governance_insights", []))}</div></body></html>"""
        return html_content.encode('utf-8'), f"ESG_Insights_{safe_company_name}.html"

    def extract_data_from_html_for_comparison(soup, filename):
        data = {'company_name': filename.replace('.html', '').replace('ESG_Insights_', '')}
        for card in soup.find_all('div', class_='score-card'):
            title = card.find('h4').text.lower().replace(' ', '_').replace('esg_', ''); score = card.find('div', class_='score-value').text.split('/')[0]
            data[title] = score
        for pillar, icon in [('environmental', '🌍'), ('social', '🏢'), ('governance', '🏛️')]:
            insights = []
            header = soup.find(lambda tag: tag.name == 'h2' and icon in tag.get_text(strip=True))
            if header and (table := header.find_next('table')):
                for row in table.find_all('tr')[1:]:
                    cells = row.find_all('td')
                    if len(cells) == 3: insights.append({'subcategory': cells[1].get_text(strip=True), 'detail': cells[2].get_text(strip=True)})
            data[f'{pillar}_insights'] = insights
        return data

    def generate_comparison_html_esg(esg_reports):
        if not 1 <= len(esg_reports) <= 5: return "<h1>Error: Please provide between 1 and 5 reports.</h1>".encode('utf-8'), "ESG_Comparison.html"
        current_date = datetime.now().strftime("%B %d, %Y"); company_names = [r.get('company_name', 'Unknown') for r in esg_reports]
        def generate_score_comparison_table():
            header = "".join(f"<th>{name}</th>" for name in company_names)
            def score_row(title, key_prefix):
                cells = ""
                for report in esg_reports:
                    score = report.get(f'{key_prefix}_score', 'N/A'); rating, color = get_benchmark_rating(score)
                    cells += f'<td><div class="score-cell"><span class="score-val">{score}</span><span class="rating-badge" style="background:{color};">{rating}</span></div></td>'
                return f"<tr><td>{title}</td>{cells}</tr>"
            return f"<h2>Score Comparison</h2><table><thead><tr><th>Metric</th>{header}</tr></thead><tbody>{score_row('Overall ESG', 'overall')}{score_row('Environmental', 'environmental')}{score_row('Social', 'social')}{score_row('Governance', 'governance')}</tbody></table>"
        def generate_insight_comparison_section(title, icon, category_key):
            all_subcategories = {i['subcategory'] for r in esg_reports for i in r.get(category_key, [])}
            if not all_subcategories: return ""
            insight_map = {name: {i['subcategory']: i['detail'] for i in r.get(category_key, [])} for name, r in zip(company_names, esg_reports)}
            header = "".join(f"<th>{name}</th>" for name in company_names)
            rows_html = "".join(f"<tr><td>{html.escape(subcat)}</td>{''.join(f'<td>{html.escape(insight_map[name].get(subcat, '-'))}</td>' for name in company_names)}</tr>" for subcat in sorted(list(all_subcategories)))
            return f"<h2>{icon}{title} Comparison</h2><table><thead><tr><th>Category</th>{header}</tr></thead><tbody>{rows_html}</tbody></table>"
        html_content = f"""<!DOCTYPE html><html><head><title>ESG Comparison</title><style>body{{font-family:sans-serif;}} .container{{max-width:1200px;margin:auto;}} h1,h2{{color:#111827;}} table{{width:100%;border-collapse:collapse;margin:25px 0;}} th,td{{border:1px solid #e5e7eb;padding:12px 15px;}}</style></head><body><div class="container"><h1>ESG Comparison Report</h1><h3>{current_date}</h3>{generate_score_comparison_table()}{generate_insight_comparison_section("Environmental", "🌍", "environmental_insights")}{generate_insight_comparison_section("Social", "🏢", "social_insights")}{generate_insight_comparison_section("Governance", "🏛️", "governance_insights")}</div></body></html>"""
        return html_content.encode('utf-8'), "ESG_Comparison_Report.html"

    # --- UI with Tabs ---
    tab1, tab2 = st.tabs(["📊 ESG Dashboard", "📝 Classic Report & Comparison"])
    with tab1:
        st.subheader("Generate New ESG Dashboard")
        st.info("Upload a company's sustainability or ESG report to generate a comprehensive dashboard.")
        company_dash = st.text_input("🏢 Enter Company Name", "Vedanta", key="esg_company_dash")
        file_dash = st.file_uploader("📄 Upload ESG Disclosure PDF", type="pdf", key="esg_file_dash")
        st.markdown("---")
        st.subheader("Advanced: Customize Analysis Prompt")
        st.warning("The ESG Dashboard requires a specific JSON output. Your custom prompt must request this structure or the dashboard generation will fail.")
        st.text_area("Enter your custom prompt for ESG analysis:", placeholder="Enter your full custom prompt here...", height=250, key="esg_custom_prompt_dash")
        
        if st.button("🚀 Generate Dashboard", key="esg_generate_dash", type="primary"):
            if not all([company_dash, file_dash]): 
                st.error("Please provide a company name and a PDF file.")
            else:
                text = extract_text_from_pdf_esg(file_dash)
                if text:
                    esg_data = analyze_esg_in_stages(text)
                    if "error" in esg_data: 
                        st.error(f"Analysis failed: {esg_data['error']}")
                    else:
                        st.success("Dashboard generated successfully!")
                        report_content, report_filename = generate_esg_dashboard_html(esg_data, company_dash)
                        st.download_button("📥 Download HTML Dashboard", report_content, report_filename, "text/html", use_container_width=True)
                        st.markdown("### Dashboard Preview:")
                        st.components.v1.html(report_content.decode('utf-8'), height=800, scrolling=True)

    with tab2:
        st.subheader("1. Generate Classic ESG Report")
        company_classic = st.text_input("🏢 Enter Company Name", key="esg_company_classic")
        file_classic = st.file_uploader("📄 Upload ESG Disclosure PDF", type="pdf", key="esg_file_classic")
        st.markdown("---")
        st.subheader("Advanced: Customize Analysis Prompt")
        st.warning("The ESG Report requires a specific JSON output. Your custom prompt must request this structure or the report generation will fail.")
        st.text_area("Enter your custom prompt for ESG analysis:", placeholder="Enter your full custom prompt here...", height=250, key="esg_custom_prompt_classic")
        
        if st.button("🚀 Generate & Download Report", key="esg_generate_classic"):
            if not all([company_classic, file_classic]): 
                st.error("Please provide a company name and a PDF file.")
            else:
                text = extract_text_from_pdf_esg(file_classic)
                if text:
                    esg_data = analyze_esg_in_stages(text) # Use the same robust function
                    if "error" in esg_data: 
                        st.error(f"Analysis failed: {esg_data['error']}")
                    else:
                        st.success("Analysis complete!")
                        report_content, report_filename = generate_html_report_esg(esg_data, company_classic)
                        st.download_button("📥 Download HTML Report", report_content, report_filename, "text/html", use_container_width=True)
                        st.markdown("### Report Preview:")
                        st.components.v1.html(report_content.decode('utf-8'), height=600, scrolling=True)
        
        st.markdown("---")
        st.subheader("2. Compare Existing Classic Reports")
        uploaded_html_files = st.file_uploader("📂 Upload 2 to 5 Classic ESG HTML Reports", type="html", accept_multiple_files=True, key="esg_compare_files")
        if st.button("🔍 Compare & Download", key="esg_compare"):
            if not 2 <= len(uploaded_html_files) <= 5: 
                st.warning("Please upload between 2 and 5 HTML files to compare.")
            else:
                comparison_data = []
                with st.spinner("Parsing reports for comparison..."):
                    for f in uploaded_html_files:
                        try:
                            soup = BeautifulSoup(f.read().decode('utf-8', errors='ignore'), 'html.parser')
                            report_data = extract_data_from_html_for_comparison(soup, f.name)
                            comparison_data.append(report_data)
                        except Exception as e: 
                            st.error(f"Error parsing file {f.name}: {e}")
                if comparison_data:
                    compare_content, compare_filename = generate_comparison_html_esg(comparison_data)
                    st.success("Comparison complete!")
                    st.download_button("📥 Download Comparison Report", compare_content, compare_filename, "text/html", use_container_width=True)
                    st.markdown("### Comparison Preview:")
                    st.components.v1.html(compare_content.decode(), height=800, scrolling=True)


# ==============================================================================
# 6. Agent Portfolio (FINAL CORRECTED VERSION)
# ==============================================================================

def portfolio_agent_app(user_id: str):
    """
    A persistent agent to index and query company documents using Pinecone,
    with added capabilities for pre-defined, structured analysis.
    """
    import xml.etree.ElementTree as ET
    import json # Added for parsing risk assessment
    import html # Added for escaping HTML characters

    st.markdown("### 🗂️ Agent Portfolio")
    st.markdown("Upload company-specific documents for indexation.")

    # --- HELPER FUNCTIONS (Existing) ---
    def truncate_context(excerpts: list, max_chars: int = 120000) -> str:
        full_context = ""
        for excerpt in excerpts:
            if len(full_context) + len(excerpt) > max_chars:
                break
            full_context += excerpt
        return full_context

    def add_spacing_to_run_on_text(text: str) -> str:
        text = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', text)
        text = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', text)
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
        return text

    def call_deepseek_model(prompt: str, is_json: bool = False) -> str:
        try:
            if not DEEPSEEK_API_KEY:
                st.error("DeepSeek API Key is not configured in secrets.")
                return "Error: API Key not available."
            
            headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "deepseek-chat", 
                "messages": [{"role": "user", "content": prompt}], 
                "temperature": 0.1, 
                "max_tokens": 8192
            }
            # Add response_format if JSON is expected
            if is_json:
                payload["response_format"] = {"type": "json_object"}

            response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=240)
            response.raise_for_status()
            
            raw_content = response.json()["choices"][0]["message"]["content"]
            # For non-JSON, clean up spacing. For JSON, return as is.
            return raw_content if is_json else add_spacing_to_run_on_text(raw_content)

        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")
            return f"Error: {e}"


    def format_competitive_analysis_output(raw_text: str) -> str:
        """
        Robustly formats the Competitive Analysis output.
        Tries to parse as XML first, then falls back to heuristic HTML cleanup.
        """
        # --- Fallback Function for Messy HTML-like Text ---
        def fallback_formatter(text: str) -> str:
            # Remove the answer tags
            text = re.sub(r'</?answer>', '', text, flags=re.IGNORECASE)
            # Add headings for key sections
            text = re.sub(r'^\s*<competitive_landscape>\s*', '## Competitive Landscape\n', text, flags=re.IGNORECASE)
            text = re.sub(r'^\s*<opportunity_gaps>\s*', '## Opportunity Gaps\n', text, flags=re.IGNORECASE)
            text = re.sub(r'^\s*<prioritized_actions>\s*', '## Prioritized Actions\n', text, flags=re.IGNORECASE)
            text = re.sub(r'^\s*<sources>\s*', '## Sources\n', text, flags=re.IGNORECASE)
            # Format strong tags and paragraphs
            text = re.sub(r'<p><strong>(.*?)</strong>', r'\n### \1', text, flags=re.DOTALL)
            text = re.sub(r'<strong>(.*?)</strong>', r'**\1**', text, flags=re.DOTALL)
            text = re.sub(r'</?p>', '\n', text)
            # Format lists
            text = re.sub(r'<li>', '\n* ', text)
            # Clean up all remaining tags
            text = re.sub(r'<.*?>', '', text)
            # Normalize whitespace
            text = re.sub(r'\n\s*\n', '\n\n', text).strip()
            return text

        # --- Main Function Logic ---
        match = re.search(r'<answer>(.*)</answer>', raw_text, re.DOTALL)
        if not match:
            return fallback_formatter(raw_text) # Try fallback even if no answer tag
        
        content = match.group(1)
        
        try:
            # Try to parse as clean XML
            root = ET.fromstring(f"<root>{content}</root>") # Wrap in root for safety
            md_parts = []
            
            def get_text(element, path, default=''):
                node = element.find(path)
                return node.text.strip() if node is not None and node.text else default

            landscape = root.find('competitive_landscape')
            if landscape is not None:
                md_parts.append("## Competitive Landscape")
                for child in landscape:
                    if child.tag not in ['competitors', 'adjacent_disruptors']:
                        title = child.tag.replace('_', ' ').title()
                        md_parts.append(f"**{title}:** {child.text.strip() if child.text else ''}\n")
                md_parts.append("\n---\n## Key Competitors")

                if landscape.find('competitors') is not None:
                    md_parts.append("### Direct Competitors")
                    for comp in landscape.find('competitors').findall('competitor'):
                        name = get_text(comp, 'name')
                        pos = get_text(comp, 'positioning')
                        price = get_text(comp, 'pricing')
                        moves = get_text(comp, 'recent_strategic_moves')
                        md_parts.append(f"#### {name}\n**Positioning:** {pos}\n\n**Pricing:** {price}\n\n**Recent Moves:** {moves}\n")
                
                if landscape.find('adjacent_disruptors') is not None:
                    md_parts.append("### Adjacent-Space Disruptors")
                    for dis in landscape.find('adjacent_disruptors').findall('disruptor'):
                        name = get_text(dis, 'name')
                        pos = get_text(dis, 'positioning')
                        price = get_text(dis, 'pricing')
                        moves = get_text(dis, 'recent_strategic_moves')
                        md_parts.append(f"#### {name}\n**Positioning:** {pos}\n\n**Pricing:** {price}\n\n**Recent Moves:** {moves}\n")

            gaps = root.find('opportunity_gaps')
            if gaps is not None:
                md_parts.append("\n---\n## Identified Opportunity Gaps")
                if gaps.find('comparison') is not None:
                    md_parts.append(get_text(gaps, 'comparison') + '\n')
                
                levers = gaps.find('levers') if gaps.find('levers') is not None else gaps
                for i, lever in enumerate(levers, 1):
                    name = get_text(lever, 'name')
                    desc = get_text(lever, 'description')
                    exploit = get_text(lever, 'diageo_exploitation')
                    md_parts.append(f"### {i}. {name}\n{desc}")
                    if exploit: md_parts.append(f"\n**Current Exploitation:** {exploit}\n")

            actions = root.find('prioritized_actions')
            if actions is not None:
                md_parts.append("\n---\n## Prioritized Strategic Actions")
                md_parts.append("| Action | Impact (1-5) | Feasibility (1-5) | Rationale |")
                md_parts.append("| :--- | :---: | :---: | :--- |")
                for action in actions.findall('action'):
                    name = get_text(action, 'name', get_text(action, 'description'))
                    impact = get_text(action, 'impact', get_text(action, 'impact_score'))
                    feasibility = get_text(action, 'feasibility', get_text(action, 'feasibility_score'))
                    rationale = get_text(action, 'rationale')
                    md_parts.append(f"| **{name}** | {impact} | {feasibility} | {rationale} |")

            sources = root.find('sources')
            if sources is not None:
                md_parts.append("\n---\n## Sources")
                for source in sources.findall('source'):
                    md_parts.append(f"* {source.text.strip()}")
            
            return "\n".join(md_parts)
        except ET.ParseError:
            # If XML parsing fails, use the fallback formatter on the original text
            return fallback_formatter(raw_text)

    def parse_markdown_to_structure(markdown_text: str, analysis_type: str) -> list:
        if analysis_type == "Custom Query":
            return [("Custom Query Response", markdown_text)]
            
        structure = []
        heading_pattern = re.compile(r'^#+\s+.*$', re.MULTILINE)
        matches = list(heading_pattern.finditer(markdown_text))
        if not matches:
            if markdown_text.strip():
                structure.append(("Overview", markdown_text.strip()))
            return structure
        for i, match in enumerate(matches):
            heading_text = match.group(0).strip()
            start_of_content = match.end()
            end_of_content = matches[i + 1].start() if (i + 1) < len(matches) else len(markdown_text)
            content_text = markdown_text[start_of_content:end_of_content].strip()
            structure.append((heading_text, content_text))
        return structure

    def markdown_to_word_bytes(structured_data: list, company_name: str, analysis_type: str) -> bytes:
        doc = Document()
        styles = doc.styles
        def define_style(style_name, style_type, font_name, font_size, is_bold=False):
            try:
                style = styles[style_name]
            except KeyError:
                style = styles.add_style(style_name, style_type)
            font = style.font
            font.name = font_name
            font.size = Pt(font_size)
            font.bold = is_bold
            if style_type == WD_STYLE_TYPE.PARAGRAPH:
                style.base_style = styles['Normal']
            return style
        title_style = define_style('DocTitle', WD_STYLE_TYPE.PARAGRAPH, 'Aptos Display', 16, True)
        heading_style = define_style('DocHeading', WD_STYLE_TYPE.PARAGRAPH, 'Aptos Display', 12, True)
        body_style = define_style('DocBody', WD_STYLE_TYPE.PARAGRAPH, 'Aptos Display', 9, False)
        title_style.paragraph_format.space_after = Pt(18)
        heading_style.paragraph_format.space_before = Pt(12)
        heading_style.paragraph_format.space_after = Pt(6)
        body_style.paragraph_format.line_spacing = 1.15
        doc.add_paragraph(f"{analysis_type} - {company_name}", style=title_style)
        for heading, content in structured_data:
            cleaned_heading = re.sub(r'^#+\s*', '', heading).strip()
            doc.add_paragraph(cleaned_heading, style=heading_style)
            is_table = False
            lines = content.strip().split('\n')
            if len(lines) > 1 and '|' in lines[0] and re.match(r'^\s*\|?(:?-+:?\|)+(:?-+:?)?\s*$', lines[1]):
                is_table = True
            if is_table:
                headers = [h.strip() for h in lines[0].strip('|').split('|')]
                table = doc.add_table(rows=1, cols=len(headers))
                table.style = 'Table Grid'
                hdr_cells = table.rows[0].cells
                for i, h in enumerate(headers):
                    hdr_cells[i].text = h
                for row_line in lines[2:]:
                    row_cells = table.add_row().cells
                    cells = [c.strip() for c in row_line.strip('|').split('|')]
                    for i, c in enumerate(cells):
                        if i < len(row_cells):
                            row_cells[i].text = c
            else:
                for para in content.split('\n'):
                    para = para.strip()
                    if not para: continue
                    if para.startswith(('* ', '- ')):
                        doc.add_paragraph(para[2:], style='List Bullet')
                    else:
                        para = para.replace('**', '')
                        doc.add_paragraph(para, style=body_style)
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()

    def format_analysis_as_html(markdown_text: str, title: str, sources: str) -> str:
        content_html = markdown.markdown(markdown_text, extensions=['tables'])
        # Logic to prevent repeating the word "Analysis"
        final_title = title if "analysis" in title.lower() else f"{title} Analysis"
        html_style = """
        <style>
            .analysis-container { font-family: 'Poppins', sans-serif; border: 1px solid #e0e0e0; border-radius: 8px; padding: 25px; background-color: #f9f9f9; margin-top: 20px; }
            .analysis-container h1, .analysis-container h2, .analysis-container h3, .analysis-container h4 { color: #00416A; }
            .analysis-container h2 {font-size: 1.5em; border-bottom: 2px solid #00416A; padding-bottom: 10px; margin-top: 0;}
            .analysis-container h3 {font-size: 1.2em; padding-bottom: 5px; margin-top: 25px; border-bottom: 1px solid #e6f1f6;}
            .analysis-container table { width: 100%; border-collapse: collapse; margin: 15px 0; }
            .analysis-container th, .analysis-container td { border: 1px solid #ddd; padding: 10px 14px; text-align: left; }
            .analysis-container th { background-color: #e6f1f6; font-weight: 600; }
            .analysis-container p { margin-bottom: 1em; line-height: 1.6; }
            .analysis-container ul, .analysis-container ol { padding-left: 1.5em; }
            .analysis-container li { margin-bottom: 0.75em; line-height: 1.6;}
            .analysis-container .sources { font-size: 0.85em; color: #555; margin-top: 25px; text-align: right; }
        </style>
        """
        return f"""
        {html_style}
        <div class="analysis-container">
            <h2>{final_title}</h2>
            {content_html}
            <div class="sources"><strong>Sources:</strong> {sources}</div>
        </div>
        """

    # --- NEW HELPER FUNCTIONS FOR RISK ASSESSMENT ---
    def highlight_text(full_text: str, quote: str) -> str:
        """Finds a quote in a larger text and wraps it in a highlight tag."""
        # Escape special characters for regex and handle variations in whitespace
        safe_quote = re.escape(quote)
        pattern = re.compile(r'\s*'.join(safe_quote.split()), re.IGNORECASE)
        match = pattern.search(full_text)
        
        if match:
            start, end = match.span()
            # Get some context around the match
            context_start = max(0, start - 150)
            context_end = min(len(full_text), end + 150)
            context = full_text[context_start:context_end]
            
            # Highlight the matched phrase within the context
            highlighted_context = (
                html.escape(context[:start - context_start]) +
                f"<mark>{html.escape(context[start - context_start:end - context_start])}</mark>" +
                html.escape(context[end - context_start:])
            )
            return f"...{highlighted_context}..."
        return f"<i>(Could not locate exact quote for highlighting, but it was sourced from this document)</i><br>{html.escape(quote)}"

    def format_risk_assessment_html(risks_data: list, company_name: str, sources_str: str) -> str:
        """Creates a styled HTML report for the risk assessment."""
        styles = """
        <style>
            .risk-assessment-container { font-family: 'Poppins', sans-serif; background-color: #ffffff; padding: 20px; }
            .risk-card { border: 1px solid #e0e0e0; border-left: 5px solid #c0392b; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
            .risk-card-header { background-color: #f9f9f9; padding: 15px 20px; border-bottom: 1px solid #e0e0e0; }
            .risk-card-header h3 { margin: 0; font-size: 1.2em; color: #c0392b; }
            .risk-card-body { padding: 20px; }
            .risk-card-body h4 { font-size: 1.0em; color: #333; margin-top: 0; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px;}
            .risk-card-body p { font-size: 0.95em; line-height: 1.6; color: #555; }
            .risk-source-snapshot { background-color: #fdf5f5; border: 1px dashed #e5b8b4; border-radius: 4px; padding: 15px; margin-top: 15px; font-family: monospace, monospace; font-size: 0.85em; line-height: 1.5; color: #444; }
            .risk-source-snapshot mark { background-color: #f6caca; padding: 2px 4px; border-radius: 3px; }
            .risk-sources-footer { font-size: 0.85em; color: #555; margin-top: 25px; text-align: right; }
        </style>
        """
        cards_html = ""
        for i, risk in enumerate(risks_data, 1):
            # +++ NEW LOGIC for snapshot display +++
            snapshot_content = ""
            if risk.get('snapshot_url'):
                snapshot_content = f'<img src="{risk["snapshot_url"]}" alt="Source Snapshot" style="width:100%; border-radius: 4px;">'
            else:
                snapshot_content = risk.get('highlighted_quote', 'Source text not available.')

            cards_html += f"""
            <div class="risk-card">
                <div class="risk-card-header"><h3>Risk #{i}: {html.escape(risk.get('risk_title', 'Untitled Risk'))}</h3></div>
                <div class="risk-card-body">
                    <h4>Summary</h4>
                    <p>{html.escape(risk.get('risk_summary', 'N/A'))}</p>
                    <h4>Potential Impact</h4>
                    <p>{html.escape(risk.get('potential_impact', 'N/A'))}</p>
                    <h4>Source Snapshot</h4>
                    <div class="risk-source-snapshot">{snapshot_content}</div>
                </div>
            </div>
            """
        
        return f"""
        {styles}
        <div class='risk-assessment-container'>
            <h2>Risk Assessment for {company_name}</h2>
            {cards_html}
            <div class="risk-sources-footer"><strong>Source Documents:</strong> {sources_str}</div>
        </div>
        """

    # --- Add this NEW helper function inside the main portfolio_agent_app function ---

    def create_and_upload_snapshot(supabase_client, namespace: str, company: str, source_file: str, page_number: int, quote: str) -> str:
        """
        Downloads a source PDF, creates a highlighted image of the relevant page,
        and uploads it to Supabase, returning the public URL.
        """
        import uuid

        # --- FIX 1: Add validation for missing or non-numeric page_number ---
        if page_number is None:
            st.warning(f"Snapshot skipped for '{source_file}': Page number was missing from metadata.")
            return None
        
        try:
            # Ensure page_number is an integer for library compatibility
            page_number = int(page_number)
            if page_number <= 0: raise ValueError("Page number must be positive.")
        except (ValueError, TypeError):
            st.warning(f"Snapshot skipped for '{source_file}': Invalid page number format ('{page_number}').")
            return None

        if not source_file.lower().endswith('.pdf'):
            return None

        source_bucket = "source-documents"
        snapshot_bucket = "risk_snapshots"
        safe_company_name = re.sub(r'[<>:"/\\|?*]', '_', company.strip())
        source_path = f"{namespace}/{safe_company_name}/{source_file}"
        
        try:
            file_bytes = supabase_client.storage.from_(source_bucket).download(path=source_path)
            
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                # --- FIX 2: Validate that the page number exists in the document ---
                if page_number > len(doc):
                    st.warning(f"Snapshot generation failed for {source_file}: Requested page {page_number}, but the document only has {len(doc)} pages.")
                    return None
                
                page = doc.load_page(page_number - 1)
                
                text_instances = page.search_for(quote, quads=True)
                if not text_instances:
                    words = quote.split()
                    if len(words) > 5:
                        short_quote = " ".join(words[:5])
                        text_instances = page.search_for(short_quote, quads=True)

                for inst in text_instances:
                    page.add_highlight_annot(inst)

                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                
                snapshot_filename = f"{uuid.uuid4()}.png"
                snapshot_path = f"{namespace}/{safe_company_name}/{snapshot_filename}"
                
                supabase_client.storage.from_(snapshot_bucket).upload(
                    path=snapshot_path,
                    file=img_bytes,
                    file_options={"content-type": "image/png", "upsert": "true"}
                )
                
                return supabase_client.storage.from_(snapshot_bucket).get_public_url(snapshot_path)

        except Exception as e:
            st.warning(f"Snapshot generation failed for {source_file} (Page {page_number}): {e}")
            return None

    # --- THIS IS THE ERRONEOUS BLOCK THAT HAS BEEN REMOVED ---
    
    @st.cache_resource
    def load_agent(user_id):
        import tiktoken
        class PortfolioAgent:
            def __init__(self, user_id: str, index_name: str = "portfolio-agent"):
                self.namespace = user_id
                try:
                    self.pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
                    if index_name not in [idx.name for idx in self.pc.list_indexes()]:
                        st.error(f"Pinecone index '{index_name}' was not found.")
                        raise NameError(f"Index '{index_name}' not found.")
                    self.index = self.pc.Index(index_name)
                    self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
                except KeyError as e:
                    st.error(f"Missing configuration in secrets.toml: `pinecone.{e.args[0]}`")
                    raise
                except Exception as e:
                    st.error(f"Failed to connect to Pinecone: {e}")
                    raise

            def _init_supabase(self):
                from supabase import create_client, Client
                # CORRECTED: Access secrets under the 'connections.supabase' structure
                url = os.environ.get("SUPABASE_URL")
                key = os.environ.get("SUPABASE_KEY")
                if not url or not key:
                    st.error("Supabase URL or Key is not configured in secrets for the agent. Please check [connections.supabase].")
                    return None
                return create_client(url, key)


            def sanitize_filename(self, name: str) -> str:
                return re.sub(r'[<>:"/\\|?*]', '_', name.strip())

            def _extract_text(self, file_content: bytes, filename: str) -> str:
                try:
                    if filename.lower().endswith(".pdf"):
                        with fitz.open(stream=file_content, filetype="pdf") as doc:
                            return "\n".join(page.get_text() for page in doc)
                    elif filename.lower().endswith(".docx"):
                        doc = Document(io.BytesIO(file_content))
                        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
                    elif filename.lower().endswith(".txt"):
                        return file_content.decode("utf-8")
                except Exception as e:
                    st.warning(f"Could not read {filename}: {e}")
                return ""

            def _chunk_text(self, file_content: bytes, filename: str, max_tokens: int = 512, overlap_tokens: int = 50) -> List[dict]:
                """Chunks text page by page and returns a list of dictionaries with text and page number."""
                if not filename.lower().endswith(".pdf"):
                    # For non-PDFs, treat as a single page
                    full_text = self._extract_text(file_content, filename)
                    # This part remains similar to before but for a single block
                    try:
                        enc = tiktoken.get_encoding("cl100k_base")
                    except Exception:
                        enc = tiktoken.get_encoding("gpt2")
                    tokens = enc.encode(full_text)
                    chunks = []
                    start = 0
                    while start < len(tokens):
                        end = start + max_tokens
                        chunk_text = enc.decode(tokens[start:end]).strip()
                        if chunk_text:
                            chunks.append({"text": chunk_text, "page_number": 1})
                        start += (max_tokens - overlap_tokens)
                    return chunks

                # PDF-specific page-by-page chunking
                chunks_with_pages = []
                try:
                    with fitz.open(stream=file_content, filetype="pdf") as doc:
                        try:
                            enc = tiktoken.get_encoding("cl100k_base")
                        except Exception:
                            enc = tiktoken.get_encoding("gpt2")
                        
                        for page_num, page in enumerate(doc, start=1):
                            page_text = page.get_text()
                            if not page_text.strip():
                                continue
                            
                            tokens = enc.encode(page_text)
                            start = 0
                            while start < len(tokens):
                                end = start + max_tokens
                                chunk_text = enc.decode(tokens[start:end]).strip()
                                if chunk_text:
                                    chunks_with_pages.append({"text": chunk_text, "page_number": page_num})
                                start += (max_tokens - overlap_tokens)
                except Exception as e:
                    st.warning(f"Error chunking PDF {filename}: {e}")

                return chunks_with_pages

            def _get_year_from_filename(self, filename: str) -> int:
                matches = re.findall(r'\b(20\d{2})\b', filename)
                return int(max(matches)) if matches else 0

            def add_documents(self, company: str, uploaded_files: list):
                safe_company_name = self.sanitize_filename(company)
                
                # Initialize Supabase client
                supabase_client = self._init_supabase()
                if not supabase_client:
                    return

                with st.status(f"Processing documents for {safe_company_name}...", expanded=True) as status:
                    total_vectors_processed = 0
                    for file in uploaded_files:
                        # 1. Upload original document to Supabase Storage
                        status.write(f"Uploading {file.name} to source document storage...")
                        file_bytes = file.getvalue()
                        supabase_path = f"{self.namespace}/{safe_company_name}/{file.name}"
                        
                        try:
                            # Use upsert=True to overwrite if it already exists
                            supabase_client.storage.from_("source-documents").upload(
                                path=supabase_path,
                                file=file_bytes,
                                file_options={"content-type": file.type, "upsert": "true"}
                            )
                        except Exception as e:
                            st.error(f"Failed to upload {file.name} to Supabase: {e}")
                            continue # Skip this file if upload fails

                        # 2. Clear old entries from Pinecone
                        status.write(f"Clearing old Pinecone entries for {file.name}...")
                        self.index.delete(
                            filter={"company": {"$eq": safe_company_name}, "source_file": {"$eq": file.name}},
                            namespace=self.namespace
                        )

                        # 3. Chunk text page by page
                        file_year = self._get_year_from_filename(file.name)
                        status.write(f"Chunking and embedding {file.name}...")
                        # Pass file_bytes to the new chunking function
                        chunks_with_pages = self._chunk_text(file_bytes, file.name)
                        
                        if not chunks_with_pages:
                            st.write(f"Skipping {file.name}: no text could be extracted or chunked.")
                            continue

                        # 4. Create vectors and upsert to Pinecone with page_number metadata
                        chunk_texts = [item['text'] for item in chunks_with_pages]
                        vectors = self.embedding_model.encode(chunk_texts).tolist()
                        
                        vectors_to_upsert = []
                        for i, item in enumerate(chunks_with_pages):
                            chunk_id = f"{safe_company_name}-{self.sanitize_filename(file.name)}-p{item['page_number']}-{i}"
                            metadata = {
                                "company": safe_company_name, 
                                "source_file": file.name, 
                                "original_text": item['text'], 
                                "year": file_year,
                                "page_number": item['page_number'] # <<< CRITICAL ADDITION
                            }
                            vectors_to_upsert.append({"id": chunk_id, "values": vectors[i], "metadata": metadata})

                        if not vectors_to_upsert:
                            continue

                        status.write(f"Upserting {len(vectors_to_upsert)} chunks to Pinecone...")
                        batch_size = 100
                        for i in range(0, len(vectors_to_upsert), batch_size):
                            self.index.upsert(vectors=vectors_to_upsert[i:i + batch_size], namespace=self.namespace)
                        total_vectors_processed += len(vectors_to_upsert)

                    if total_vectors_processed > 0:
                        st.success(f"Successfully indexed {total_vectors_processed} new document chunks for **{company}**.")
                    else:
                        st.warning("No new content was indexed.")

            def query(self, query_text: str, companies: List[str], k: int = 30) -> Tuple[str, str]:
                """
                Performs a query against the Pinecone index with an enhanced RAG pipeline
                for more accurate and synthesized financial analysis.
                """
                query_vector = self.embedding_model.encode(query_text).tolist()
                query_filter = {"company": {"$in": [self.sanitize_filename(c) for c in companies]}}

                # Increased k to 30 to provide a wider context for deeper synthesis
                results = self.index.query(
                    vector=query_vector,
                    top_k=k,
                    filter=query_filter,
                    include_metadata=True,
                    namespace=self.namespace
                )

                if not results.matches:
                    return "I could not find relevant information in the indexed documents.", ""

                # This sorting logic is correct and critical, it must be maintained.
                results.matches.sort(key=lambda m: m.metadata.get('page_number', 0))
                results.matches.sort(key=lambda m: m.metadata.get('year', 0), reverse=True)
                
                context_excerpts = [
                    f"Excerpt from '{m.metadata['source_file']}' (Year: {m.metadata.get('year', 'N/A')}, Page: {m.metadata.get('page_number', 'N/A')}):\n\"{m.metadata['original_text']}\"\n"
                    for m in results.matches
                ]
                
                source_docs = sorted(list(set(m.metadata['source_file'] for m in results.matches)))
                safe_context = truncate_context(context_excerpts)

                # --- THIS IS THE FINAL PROMPT, ENGINEERED FOR MAXIMUM DEPTH AND CONTEXT ---
                prompt = f"""You are a world-class senior equity research analyst from a top-tier investment bank, known for producing exceptionally detailed and insightful reports. Your task is to provide a comprehensive, multi-faceted answer to the user's question, synthesizing all available information into a robust, professional-grade analysis.

**Core Task & Rules:**
1.  **Direct Answer First:** Begin your response with a direct, one-sentence answer to the user's specific question. This should be the single most current and authoritative fact.
2.  **Construct a Detailed Narrative:** After the direct answer, you must build a detailed, multi-paragraph narrative that provides the deepest possible context. You are REQUIRED to search the context for and include the following types of information, if available:
    * **Specific Quantitative Drivers:** Go beyond generalities. Instead of "AI demand," extract specific drivers like "demand for 3nm and 5nm nodes" or "growth in the HPC platform."
    * **Forward-Looking Guidance:** If the user asks about full-year guidance, you MUST also find and include any specific guidance for the next quarter (e.g., "Q3 2025 revenue is guided to be between $X and $Y billion").
    * **Financial Nuances & Headwinds:** Find and include any commentary on factors affecting the headline numbers, such as "foreign exchange (FX) headwinds," "margin impact from new fabs," or "cost dilution."
    * **Management's Rationale:** Summarize management's qualitative commentary and the reasoning behind their projections.
3.  **The "First is Final" Rule for Specific Metrics:** The context is pre-sorted chronologically (most recent first). For any specific, directly comparable metric (e.g., FY2025 revenue growth %), you **MUST** use the value from the **EARLIEST** excerpt in the context. Ignore all subsequent, older values for that specific metric.
4.  **No Meta-Commentary:** **NEVER** mention "conflicting data" or "older guidance." Present a single, unified analysis based on the most current information.
5.  **Professional Formatting:** Structure your response with a clear summary, followed by detailed bullet points or short paragraphs to elaborate on the different aspects of the analysis (Drivers, Quarterly Outlook, etc.).

--- PRE-SORTED CONTEXT (Most Recent First) ---
{safe_context}
--- QUESTION ---
{query_text}
--- ANSWER ---
"""
                return call_deepseek_model(prompt), ", ".join(source_docs)

            def get_unindexed_analysis(self, analysis_type: str, company: str, context: str) -> str:
                """Generates analysis from provided text without querying Pinecone."""
                ANALYSIS_CONFIG = self._get_analysis_config()
                config = ANALYSIS_CONFIG.get(analysis_type)
                if not config:
                    return "Invalid analysis type selected."
                
                is_json = analysis_type == "Risk Assessment"
                system_prompt = config['system_prompt'].replace('{COMPANY_NAME}', company)
                prompt = f"{system_prompt}\n\nBase your analysis *only* on the following context:\n--- DOCUMENT CONTEXT ---\n{context}\n--- END CONTEXT ---"
                
                return call_deepseek_model(prompt, is_json=is_json)


            def _get_analysis_config(self):
                """Centralized configuration for all analysis types."""
                return {
                    "Quick Company Note": {
                        "search_query": "Comprehensive company profile including business overview, products, services, market position, key financial data like revenue, profit, margins, cash flow, EPS, balance sheet items (debt, cash), industry trends, competitive landscape, investment highlights, strengths, weaknesses, opportunities, threats, risk factors, and any red flags like impairments or governance issues.",
                        "system_prompt": """You are an expert equity research analyst from a top-tier investment bank. Your task is to generate a professional 'Quick Company Note' based ONLY on the provided document excerpts.
CRITICAL INSTRUCTION: The output MUST be in clean markdown format. Ensure there is always a single space between separate words, and between numbers and words. Do not concatenate words together.

Structure your response with the following headings:

# 1. Company Overview
(Provide a comprehensive summary of the company as a narrative text.)

# 2. Financial Performance
(Create a markdown table with the columns: 'Metric', 'Most Recent Fiscal Year', 'Prior Fiscal Year', and 'YoY Growth / Change'. Include key metrics like Revenue, Operating Profit, and Free Cash Flow. **IMPORTANT: If data for a specific year or metric is not available in the context, clearly mark that cell with 'N/A'**. Do not make up data. Present any financial figures you can find, even if the table is incomplete.)

# 3. Key Investment Highlights
(Generate a list of concise bullet points, starting each with `*`. For each bullet, **bold the key takeaway** at the beginning. Example: `* **Dominant Market Position:** The company holds the #1 spot...`)

# 4. Key Risks
(Generate a list of concise bullet points, starting each with `*`. For each bullet, **bold the primary risk factor**. Example: `* **Regulatory Headwinds:** The company faces potential...`)

# 5. Red Flags
(Generate a list of concise bullet points, starting each with `*`. Identify any potential red flags like impairments, governance issues, or high valuation uncertainty. **Bold the core issue** of each point.)

# 6. Analyst Commentary
(Write a short, concluding paragraph that synthesizes the key findings and provides a balanced view on the company's position.)
"""
                    },
                    "Competitive Analysis": {
                        "search_query": "High-level overview of the company, its industry, main products, and business strategy to provide initial context.",
                        "system_prompt": """<instructions> You are a top-tier strategy consultant with deep expertise in competitive analysis, growth loops, pricing, and unit-economics-driven product strategy. If information is unavailable, state that explicitly. </instructions>

<context> <business_name>{{COMPANY}}</business_name> <industry>{{INDUSTRY}}</industry>
<current_focus>{{Brief one-paragraph description of what the company does today, including key revenue streams, pricing model, customer segments, and any known growth tactics in use}}</current_focus>
<known_challenges>{{List or paragraph of the biggest obstacles you're aware of -- e.g., slowing user growth, rising CAC, regulatory pressure}}</known_challenges> </context>

<task> 1. Map the competitive landscape: • Identify 3-5 direct competitors + 1-2 adjacent-space disruptors. • Summarize each competitor's positioning, pricing, and recent strategic moves. 2. Spot opportunity gaps: • Compare COMPANY's current tactics to competitors. • Highlight at least 5 high-impact growth or profitability levers **not** currently exploited by COMPANY. 3. Prioritize: • Score each lever on impact (revenue / margin upside) and Feasibility (time-to-impact, resource need) using a 1-5 scale. • Recommend the top 3 actions with the strongest Impact x Feasibility. </task>

<approach> - Go VERY deep. Research far more than you normally would. Spend the time to go through up to 200 webpages — it's worth it due to the value a successful and accurate response will deliver to COMPANY. - Don't just look at articles, forums, etc. — anything is fair game... COMPANY/competitor websites, analytics platforms, etc. </approach>

<output_format> Return ONLY the following XML: <answer> <competitive_landscape> </competitive_landscape> <opportunity_gaps> </opportunity_gaps> <prioritized_actions> </prioritized_actions> <sources> </sources> </answer> </output_format>"""
                    },
                    "Cap Structure": {
                        "search_query": "Detailed information about the company's capital structure, including short-term and long-term debt instruments, maturity dates, coupon rates, leases, equity, and debt covenants.",
                        "system_prompt": """You are a senior credit analyst.
**CRITICAL INSTRUCTION: The entire output must be plain text. Do NOT use any asterisks (`*`) for formatting. Ensure proper spacing between all words and numbers.**
Based on the provided text, synthesize all information about the company's capital structure. Prioritize information from documents with the most recent year if there are conflicts.
Format the output with clear headings and narrative descriptions. Do NOT use markdown tables.
# Capital Structure Analysis
## Debt Instruments
(For each debt instrument, describe it in a sentence. e.g., "The company has 5.0% senior notes due 2028 with a principal of $500 million.")
## Key Ratios
(Describe any relevant ratios found in the text in a paragraph.)
## Covenants
(Describe any mentioned financial or operational covenants in a paragraph.)"""
                    },
                    "Debt Details": {
    "search_query": "Table of borrowings, bonds, notes, and other debt instruments. Short term borrowings, medium and long term borrowings. Unsecured bank loans, overdrafts, sustainability linked loans. US bonds, EMTN programme bonds. Principal, coupon, maturity date, covenants.",
    "system_prompt": """You are a senior credit analyst specializing in data extraction.
**CRITICAL INSTRUCTION: Your entire output must be in clean markdown format.**
Based on the provided text, your primary task is to find any detailed tables listing debt instruments (bonds, loans, etc.) and replicate them accurately. You must also summarize any surrounding text about covenants and maturity.

Format the output precisely as follows:

# Debt Details Analysis

## Debt Instruments
First, search the context for any tables that list borrowings, bonds, or other debt instruments. Recreate these tables in markdown format exactly as they appear, including all rows and columns you can identify. Pay close attention to columns like 'Instrument', 'Principal Amount', 'Maturity Date', 'Coupon/Rate', or similar.

## Key Covenants
After the table, under this heading, write a plain text paragraph summarizing any text that describes financial or procedural covenants.

## Maturity Profile
Under this heading, write a plain text paragraph summarizing any text that describes the debt maturity profile.
"""
},
                    "Litigations and Court Cases/Claims": {
                        "search_query": "Details on litigations, legal proceedings, lawsuits, court cases, regulatory investigations, and contingent liabilities.",
                        "system_prompt": """You are a legal analyst.
**CRITICAL INSTRUCTION: The entire output must be plain text. Do NOT use any asterisks (`*`) for formatting. Ensure proper spacing between all words and numbers.**
From the context provided, compile a report on all legal and regulatory matters. For each distinct case, write a paragraph detailing the nature of the claim, its status, and any potential financial impact. Prioritize information from documents with the most recent year if there are conflicts."""
                    },
                    # --- REPLACED "Investment Story" WITH "Risk Assessment" ---
                    "Risk Assessment": {
                        "search_query": "All mentions of risk factors, potential risks, challenges, threats, contingent liabilities, legal proceedings, and uncertainties.",
                        "system_prompt": """You are an expert risk analyst. Your task is to analyze the provided document excerpts for {COMPANY_NAME} in chronological order.

**CRITICAL INSTRUCTIONS:**
1.  Identify **4-5 of the most significant COMPANY-SPECIFIC risks**.
2.  You MUST differentiate between company-specific risks (e.g., reliance on a single supplier, a major lawsuit) and generic industry/market risks (e.g., economic downturns, general competition). **Focus exclusively on the company-specific ones.**
3.  For each identified risk, you must extract the **exact verbatim quote** from the source text that best describes it.
4.  Return a single, valid JSON object. The root key should be "risks", and its value should be a list of objects.
5.  Each object in the list must have these four keys:
    - "risk_title": A short, descriptive title for the risk (e.g., "Dependency on Key Personnel").
    - "risk_summary": A concise one-paragraph summary explaining the risk.
    - "potential_impact": A one-paragraph analysis of the potential financial or operational impact on the company.
    - "source_quote": The exact, verbatim quote from the document that describes the risk.

**EXAMPLE JSON OUTPUT STRUCTURE:**
{
  "risks": [
    {
      "risk_title": "Reliance on a Single Product Line",
      "risk_summary": "The company derives over 85% of its total revenue from the 'InnovateX' product, creating significant concentration risk. Any downturn in this product's market could severely affect financial performance.",
      "potential_impact": "A decline in InnovateX sales could lead to a sharp fall in revenue and profitability. It also makes the company vulnerable to new competitors targeting this specific niche. This could impact stock valuation and the ability to fund future R&D.",
      "source_quote": "Our InnovateX product line accounted for approximately 87% and 85% of our net product revenues in fiscal 2024 and 2023, respectively."
    }
  ]
}
"""
                    },
                    "Company Strategy": {
                        "search_query": "Information on corporate strategy, business objectives, future plans, growth initiatives, market expansion, product development, and strategic priorities.",
                        "system_prompt": """You are a strategy consultant.
**CRITICAL INSTRUCTION: The entire output must be plain text. Do NOT use any asterisks (`*`) for formatting. Ensure proper spacing between all words and numbers.**
Outline the company's core strategy. Use paragraphs for sections like 'Vision & Mission', 'Strategic Pillars', and 'Growth Initiatives'. Prioritize information from documents with the most recent year if there are conflicts."""
                    },
                    "Compare Investment Ideas": {
                        "search_query": "Comprehensive comparison of companies including business overview, financial performance (revenue, profit, margins), balance sheet strength (debt, cash, leverage), strategic initiatives, growth drivers, competitive landscape, market position, investment highlights, risk factors, and management outlook.",
                        "system_prompt": """You are a senior buy-side investment analyst tasked with producing a comparative analysis of several investment ideas.
**CRITICAL INSTRUCTION: The entire output must be plain text. Do NOT use any asterisks (`*`) for formatting. Ensure proper spacing between all words and numbers.**
Based ONLY on the provided document excerpts for the selected companies, generate a professional investment comparison memo. The analysis must be objective, data-driven, and written in flowing narrative paragraphs. Avoid using bullet points.

Structure your response with the following headings:
# Executive Summary
# Financial Performance Comparison
# Balance Sheet Health
# Strategic Outlook & Growth Drivers
# Risk Profile Comparison
# Analyst Recommendation
"""
                    },
                    "Management Meeting Prep": {
                        "search_query": "Recent CEO comments, guidance, outlook, transcripts, investor presentations, reports on business fundamentals including volumes, pricing, margins, cash flow, strategy, and confidence in public statements.",
                        "system_prompt": """You are an expert institutional public equity investor. Your task is to prepare a briefing document for a non-deal roadshow lunch with the CEO of {COMPANY_NAME}.

**GOAL:**
Your primary goal is to summarize the attached documents to help prepare for a 1-2 hour meeting. Your analysis must look for signals that indicate if the business and story are getting better, worse, or staying the same. This includes any indications that the core fundamentals of the business – volumes, pricing, margins & cash flow – are getting better or worse. You must identify very subtle clues. Pay special attention to comments from the CEO about guidance, outlook, and his level of confidence in those statements, including any language inflections relative to his last few public statements.

**BACKGROUND:**
The user is a dispassionate fact-finder trying to understand the trajectory of the company's fundamental metrics and whether the company is likely to be a long-term winner.

**KEY TOPICS:**
From the attached documents, pull a list of key topics that should be discussed.

**SOURCES:**
Please use primarily the documents provided and any documents directly from the company. Approach all company statements with an objective and skeptical lens. Be wary of blogs or biased sources. The analysis must be unbiased and fact-driven.

**RETURN FORMAT:**
1.  **Key Topics:** Start with a section outlining the key topics from the documents.
2.  **Key Questions for the CEO:** Provide the 3 key questions that can be asked in the meeting to inform whether the business & story are getting better, worse, or staying the same.
3.  **"Tells" to Listen For:** For each of the 3 questions, provide certain clues or "tells" to listen for in the CEO's response.
4.  **Broader Question List:** Provide a broader list of the most important 12-15 questions to ask.

**WARNINGS:**
Approach this analysis without bias. Remain completely objective and do not become influenced by any of these statements or anything that is biased to be bullish or bearish. The goal is to provide clues towards the future trajectory of the company's stock price, informed by the evolution of fundamentals and the narrative.
"""
                    }
                }

            def get_predefined_analysis(self, analysis_type: str, companies: List[str], k: int = 40) -> Tuple[str, str, object]:
                ANALYSIS_CONFIG = self._get_analysis_config()
                config = ANALYSIS_CONFIG.get(analysis_type)
                if not config: return "Invalid analysis type selected.", "", None
                
                query_vector = self.embedding_model.encode(config["search_query"]).tolist()
                query_filter = {"company": {"$in": [self.sanitize_filename(c) for c in companies]}}
                
                # For Risk Assessment, sort by year
                sort_order = None
                if analysis_type == "Risk Assessment":
                        # This is a conceptual sort; Pinecone doesn't directly support sorting by metadata.
                        # We fetch more results and sort them client-side.
                        k = 60 # Fetch more to get a better chronological view

                results = self.index.query(vector=query_vector, top_k=k, filter=query_filter, include_metadata=True, namespace=self.namespace)

                if not results.matches: return f"Could not find any documents for this analysis.", "", None
                
                # Sort matches by year for chronological analysis in Risk Assessment
                if analysis_type == "Risk Assessment":
                    results.matches.sort(key=lambda m: m.metadata.get('year', 0))

                context_excerpts = [f"Excerpt from '{m.metadata['source_file']} (Year: {m.metadata.get('year', 'N/A')})':\n\"{m.metadata['original_text']}\"\n" for m in results.matches]
                source_docs = sorted(list(set(m.metadata['source_file'] for m in results.matches)))
                safe_context = truncate_context(context_excerpts)

                system_prompt = config['system_prompt']
                company_str = ', '.join(companies)

                if analysis_type == "Competitive Analysis":
                    system_prompt = system_prompt.replace('{{COMPANY}}', company_str)
                    system_prompt = system_prompt.replace('COMPANY', company_str)
                    system_prompt = system_prompt.replace('{{INDUSTRY}}', '(To be determined by your research)')
                    system_prompt = system_prompt.replace(
                        '{{Brief one-paragraph description of what the company does today, including key revenue streams, pricing model, customer segments, and any known growth tactics in use}}',
                        '(To be determined by your research based on the company name provided)'
                    )
                    system_prompt = system_prompt.replace(
                        '{{List or paragraph of the biggest obstacles you\'re aware of -- e.g., slowing user growth, rising CAC, regulatory pressure}}',
                        '(To be determined by your research based on the company name provided)'
                    )
                    prompt = f"{system_prompt}\n\nYou can use the following internal document context as a potential starting point, but your primary instruction is to perform the deep external research as detailed in the prompt above.\n--- DOCUMENT CONTEXT ---\n{safe_context}\n--- END CONTEXT ---\n\nProvide the analysis for '{company_str}'."
                else:
                    system_prompt = system_prompt.replace('{COMPANY_NAME}', company_str)
                    prompt = f"{system_prompt}\n\nBase your analysis *only* on the following context:\n--- DOCUMENT CONTEXT ---\n{safe_context}\n--- END CONTEXT ---\n\nProvide the analysis for '{company_str}'."
                
                # Check if JSON output is expected
                is_json_output = analysis_type == "Risk Assessment"
                response_text = call_deepseek_model(prompt, is_json=is_json_output)
                
                return response_text, ", ".join(source_docs), results.matches


            def get_indexed_companies(self) -> List[str]:
                all_companies = set()
                try:
                    # Query a small number of vectors just to get metadata
                    response = self.index.query(vector=[0.0]*384, top_k=1000, include_metadata=True, namespace=self.namespace)
                    for match in response.matches:
                        company = match.metadata.get("company")
                        if company:
                            all_companies.add(company)
                except Exception as e:
                    st.warning(f"Could not fetch indexed companies: {e}")
                return sorted(list(all_companies))

            def delete_company_data(self, company_name: str):
                safe_name = self.sanitize_filename(company_name)
                try:
                    self.index.delete(filter={"company": {"$eq": safe_name}}, namespace=self.namespace)
                    st.success(f"Successfully deleted all data for **{company_name}**.")
                except Exception as e:
                    st.error(f"Failed to delete data for {company_name}: {e}")
            
        try:
            return PortfolioAgent(user_id=user_id)
        except Exception as e:
            st.error(f"Failed to initialize Agent Portfolio: {e}")
            return None

    # --- Streamlit UI for the Agent Portfolio ---
    agent = load_agent(user_id=user_id)
    if not agent:
        st.stop()

    st.subheader("📁 Index New Company Documents")
    
    with st.form("indexing_form", clear_on_submit=True):
        new_company = st.text_input("Company Name", placeholder="e.g., RTX Corp.")
        new_docs = st.file_uploader("Upload Documents (PDF, DOCX, TXT)", type=["pdf", "docx", "txt"], accept_multiple_files=True)
        if st.form_submit_button("Index Documents", type="primary"):
            if new_company and new_docs:
                agent.add_documents(new_company, new_docs)
                st.cache_resource.clear() # Clear cache to refresh company list
                st.rerun()
            else:
                st.warning("Please provide a company name and at least one document.")

    st.markdown("---")
    st.subheader("🔍 Analyze & Manage Companies")

    indexed_companies = agent.get_indexed_companies()
    if not indexed_companies:
        st.info("No companies have been indexed for your account yet. You can still use 'Management Meeting Prep' by uploading temporary documents.")

    st.markdown("#### Run Analysis")
    
    # --- UPDATED: analysis_options list ---
    analysis_options = [
        "Quick Company Note", "Competitive Analysis", "Management Meeting Prep", 
        "Compare Investment Ideas", "Risk Assessment", # <-- Changed here
        "Cap Structure", "Debt Details", "Litigations and Court Cases/Claims",
        "Company Strategy", "Custom Query"
    ]
    analysis_choice = st.selectbox("Select Analysis Type", options=analysis_options)

    # --- NEW: Special UI for Management Meeting Prep ---
    if analysis_choice == "Management Meeting Prep":
        st.markdown("##### Management Meeting Preparation")
        with st.form("meeting_prep_form"):
            prep_company_name = st.text_input("Company Name for Analysis", help="The name of the company you are meeting with.")
            
            source_choice = st.radio(
                "Select Document Source",
                ("Use Indexed Documents", "Upload Temporary Documents"),
                horizontal=True, key="prep_source"
            )

            indexed_selection = None
            temp_docs = None

            if source_choice == "Use Indexed Documents":
                indexed_selection = st.multiselect("Select Indexed Company", options=indexed_companies)
            else:
                temp_docs = st.file_uploader(
                    "Upload Documents for this analysis only (will not be indexed)",
                    type=["pdf", "docx", "txt"], accept_multiple_files=True
                )

            # --- NEW UI for Custom Prompt ---
            st.markdown("---")
            st.subheader("Advanced: Customize Meeting Prep Prompt")
            st.text_area(
                "Enter your custom prompt for the analysis:",
                placeholder="Enter your full custom prompt for the 'Management Meeting Prep' analysis here...",
                height=250,
                key="meeting_prep_custom_prompt"
            )
            # --- END NEW UI ---

            submitted = st.form_submit_button("🚀 Generate Meeting Prep", use_container_width=True)

            if submitted:
                if not prep_company_name:
                    st.error("Please enter the Company Name for the analysis.")
                elif source_choice == "Use Indexed Documents" and not indexed_selection:
                    st.error("Please select at least one indexed company.")
                elif source_choice == "Upload Temporary Documents" and not temp_docs:
                    st.error("Please upload at least one temporary document.")
                else:
                    with st.spinner(f"Preparing briefing for {prep_company_name}..."):
                        analysis_md, sources, pinecone_matches = "", "", None
                        
                        if source_choice == "Use Indexed Documents":
                            analysis_md, sources, _ = agent.get_predefined_analysis(
                                analysis_choice, companies=indexed_selection
                            )
                        else: # Upload Temporary Documents
                            context_list = []
                            source_names = []
                            for doc in temp_docs:
                                text = agent._extract_text(doc.getvalue(), doc.name)
                                if text:
                                    context_list.append(text)
                                    source_names.append(doc.name)
                            full_context = "\n\n---\n\n".join(context_list)
                            analysis_md = agent.get_unindexed_analysis(
                                analysis_choice, prep_company_name, full_context
                            )
                            sources = ", ".join(source_names)
                        
                        if "Error:" in analysis_md or "Could not find" in analysis_md or not analysis_md.strip():
                            st.error(analysis_md or "Failed to generate a response from the model.")
                        else:
                            structured_report = parse_markdown_to_structure(analysis_md, analysis_choice)
                            report_html = format_analysis_as_html(analysis_md, analysis_choice, sources)
                            word_bytes = markdown_to_word_bytes(structured_report, prep_company_name, analysis_choice)
                            
                            st.session_state['analysis_output'] = {
                                "html": report_html,
                                "word": word_bytes,
                                "company_name": prep_company_name,
                                "analysis_type": analysis_choice
                            }

    # --- Existing UI for other analysis types ---
    else:
        if not indexed_companies:
            st.info("Please index documents for a company to run this analysis type.")
        else:
            selected_companies = st.multiselect("Select Company/Companies to Analyze", options=indexed_companies, default=indexed_companies[0] if indexed_companies else [])
            
            user_query = ""
            if analysis_choice == "Custom Query":
                user_query = st.text_area("Ask a question about the selected companies' documents")

            # --- NEW UI for Custom Prompt ---
            # Show custom prompt UI for all non-custom analyses
            if analysis_choice != "Custom Query":
                st.markdown("---")
                st.subheader("Advanced: Customize Analysis Prompt")
                if analysis_choice == "Risk Assessment":
                    st.warning("Your custom prompt must request a specific JSON output for the report to generate correctly.")
                st.text_area(
                    "Enter your custom prompt for the analysis:",
                    placeholder=f"Enter your full custom prompt for the '{analysis_choice}' analysis here...",
                    height=250,
                    key="portfolio_custom_prompt"
                )
            # --- END NEW UI ---


            if st.button("🚀 Run Analysis", use_container_width=True):
                proceed = False
                if not selected_companies:
                    st.warning("Please select at least one company.")
                elif analysis_choice == "Compare Investment Ideas" and len(selected_companies) < 2:
                    st.warning("Please select at least two companies for comparison.")
                elif analysis_choice == "Custom Query" and not user_query.strip():
                    st.warning("Please enter a question for the custom query.")
                else:
                    proceed = True

                if proceed:
                    with st.spinner(f"Running '{analysis_choice}' analysis for {', '.join(selected_companies)}..."):
                        analysis_md, sources, pinecone_matches = "", "", None
                        if analysis_choice == "Custom Query":
                            analysis_md, sources = agent.query(user_query, selected_companies)
                        else:
                            analysis_md, sources, pinecone_matches = agent.get_predefined_analysis(analysis_choice, selected_companies)
                        
                        company_name_for_doc = selected_companies[0] if len(selected_companies) == 1 else "Multiple Companies"
                        
                        if "Error:" in analysis_md or "Could not find" in analysis_md or not analysis_md.strip():
                            st.error(analysis_md or "Failed to generate a response from the model.")
                        else:
                            report_html = ""
                            word_bytes = b""
                            
                            # --- NEW: Custom workflow for Risk Assessment ---
                            if analysis_choice == "Risk Assessment":
                                try:
                                    from thefuzz import fuzz
                                    supabase_client = agent._init_supabase()
                                    data = json.loads(analysis_md)
                                    risks = data.get("risks", [])
                                    
                                    for risk in risks:
                                        # ... (your existing loop for creating snapshots is correct) ...
                                        quote = risk.get("source_quote", "")
                                        risk['snapshot_url'] = None

                                        if not quote or not pinecone_matches or not supabase_client:
                                            risk['highlighted_quote'] = "Source text not available."
                                            continue

                                        best_match_meta = None
                                        highest_score = 0
                                        
                                        for match in pinecone_matches:
                                            score = fuzz.partial_ratio(quote.lower(), match.metadata['original_text'].lower())
                                            if score > highest_score:
                                                highest_score = score
                                                best_match_meta = match.metadata
                                        
                                        MIN_MATCH_SCORE = 75
                                        if highest_score >= MIN_MATCH_SCORE and best_match_meta:
                                            snapshot_url = create_and_upload_snapshot(
                                                supabase_client=supabase_client,
                                                namespace=user_id,
                                                company=company_name_for_doc,
                                                source_file=best_match_meta.get('source_file'),
                                                page_number=best_match_meta.get('page_number'),
                                                quote=quote
                                            )
                                            risk['snapshot_url'] = snapshot_url
                                        else:
                                            risk['highlighted_quote'] = (
                                                f"<i>(Could not find a high-confidence match for the quote in source documents.)</i><br>"
                                                f"<b>LLM-Generated Quote:</b> {html.escape(quote)}"
                                            )

                                    report_html = format_risk_assessment_html(risks, company_name_for_doc, sources)
                                    
                                    # THIS IS THE CRITICAL FIX: The next 6 lines are added to save the result
                                    # We create a placeholder for the Word doc since the HTML is the primary output.
                                    word_bytes = b"" 
                                    st.session_state['analysis_output'] = {
                                        "html": report_html,
                                        "word": word_bytes,
                                        "company_name": company_name_for_doc,
                                        "analysis_type": analysis_choice
                                    }

                                except json.JSONDecodeError:
                                    st.error("Failed to parse the Risk Assessment response from the AI. The format was not valid JSON.")
                                    st.text_area("Raw AI Response:", analysis_md, height=200)

                            else: # --- Existing workflow for all other types ---
                                if analysis_choice == "Competitive Analysis":
                                    analysis_md = format_competitive_analysis_output(analysis_md)

                                structured_report = parse_markdown_to_structure(analysis_md, analysis_choice)
                                report_html = format_analysis_as_html(analysis_md, analysis_choice, sources)
                                word_bytes = markdown_to_word_bytes(structured_report, company_name_for_doc, analysis_choice)
                            
                                # This block now correctly handles only the 'else' cases
                                if report_html and word_bytes:
                                    st.session_state['analysis_output'] = {
                                        "html": report_html,
                                        "word": word_bytes,
                                        "company_name": company_name_for_doc,
                                        "analysis_type": analysis_choice
                                    }

    # --- MODIFIED: Shared Output Display Area ---
    if 'analysis_output' in st.session_state:
        output = st.session_state.pop('analysis_output') # Get and remove to prevent re-display on rerun
        
        # Display a generic success message for all analysis types.
        st.success("✅ Analysis complete. Your report is ready for download below.")
        
        # This section no longer displays any HTML output in the UI.
        
        d1, d2 = st.columns(2)
        safe_filename = re.sub(r'[\s/]', '_', output["analysis_type"])
        doc_name = output["company_name"]
        d1.download_button(
            label="📥 Download as Word (.docx)",
            data=output["word"],
            file_name=f"{safe_filename}_{doc_name}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True
        )
        d2.download_button(
            label="📥 Download as HTML (.html)",
            data=output["html"].encode("utf-8"),
            file_name=f"{safe_filename}_{doc_name}.html",
            mime="text/html",
            use_container_width=True
        )


    if indexed_companies:
        st.markdown("---")
        st.markdown("#### Manage Data")
        
        company_to_delete = st.selectbox("Select Company to Delete", options=[""] + indexed_companies, key="delete_select")
        if st.button("🗑️ Delete All Data for This Company", type="secondary"):
            if company_to_delete:
                agent.delete_company_data(company_to_delete)
                st.cache_resource.clear()
                st.rerun()
            else:
                st.warning("Please select a company to delete.")



    

# ==============================================================================
# 7. TARIFF IMPACT TRACKER (NEW MODULE)
# ==============================================================================

def tariff_impact_tracker_app(DEEPSEEK_API_KEY: str, FMP_API_KEY: str, logo_base64_string: str):
    """
    Encapsulates the updated Tariff Impact Tracker functionality with revised UI and restored downloads.
    """
    st.markdown("### 📈 Tariff Impact Tracker")
    st.markdown("Analyze earnings call transcripts or public filings to extract and summarize mentions of tariffs and their financial impact.")

    # --- HELPER FUNCTIONS TO PREPARE DATA ---
    def prepare_table_data(all_analyses):
        """Prepares dataframes for display and download to ensure consistency."""
        if not all_analyses:
            return None, None, None

        table1_data, table2_data, table3_data = [], [], []

        for company_key, analysis in all_analyses.items():
            if not analysis or not isinstance(analysis, dict):
                continue

            company_display = f"{analysis.get('company_name', 'N/A')} ({analysis.get('ticker', company_key.upper())})"
            
            table1_data.append({
                "Company": company_display,
                "Management Commentary": analysis.get('management_commentary', 'No discussion'),
                "Vulnerability": analysis.get('vulnerability', 'No discussion'),
                "Profitability Impact": analysis.get('profitability_impact', 'No discussion'),
                "Pricing Implication": analysis.get('pricing_implication', 'No discussion'),
            })
            table2_data.append({
                "Company": company_display,
                "Demand Sensitivity": analysis.get('demand_sensitivity', 'No discussion'),
                "Guidance Implications": analysis.get('guidance_implications', 'No discussion'),
                "Mitigation Strategies": analysis.get('mitigation_strategies', 'No discussion'),
            })
            table3_data.append({
                "Company": company_display,
                "The Known Unknowns": analysis.get('the_known_unknowns', 'No discussion'),
                "Competitive Positioning": analysis.get('competitive_positioning', 'No discussion'),
            })

        df1 = pd.DataFrame(table1_data) if table1_data else pd.DataFrame()
        df2 = pd.DataFrame(table2_data) if table2_data else pd.DataFrame()
        df3 = pd.DataFrame(table3_data) if table3_data else pd.DataFrame()
        
        return df1, df2, df3

    # --- CORE ANALYSIS LOGIC ---
    @st.cache_data(ttl=3600, show_spinner=False)
    def get_transcript_from_fmp(ticker, year, quarter):
        # This function remains unchanged.
        if not FMP_API_KEY:
            st.error("Error: FMP_API_KEY not found.")
            return None, None
        url = f"https://financialmodelingprep.com/api/v3/earning_call_transcript/{ticker}?quarter={quarter}&year={year}&apikey={FMP_API_KEY}"
        company_profile_url = f"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={FMP_API_KEY}"
        try:
            company_name = "N/A"
            profile_response = requests.get(company_profile_url)
            profile_response.raise_for_status()
            profile_data = profile_response.json()
            if profile_data and "companyName" in profile_data[0]:
                company_name = profile_data[0]['companyName']
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            if data and "content" in data[0]:
                return data[0]["content"], company_name
            else:
                st.warning(f"No transcript content found for {ticker} for Q{quarter} {year}.")
                return None, None
        except requests.exceptions.RequestException as e:
            st.error(f"Error fetching data from FMP API for {ticker}: {e}")
            return None, None
        except (IndexError, KeyError):
            st.error(f"Error parsing FMP API response for {ticker}. The data might be empty or in an unexpected format.")
            return None, None

    def extract_text_from_pdf(uploaded_file):
        # This function remains unchanged.
        full_text = ""
        try:
            file_bytes = uploaded_file.getvalue()
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                for page in doc:
                    full_text += page.get_text() + "\n"
        except Exception as e:
            st.error(f"An error occurred while reading '{uploaded_file.name}': {e}")
        return full_text

    @st.cache_data(ttl=3600, show_spinner=False)
    def analyze_text_with_deepseek(_text_content, company_name, ticker):
        # MODIFICATION 3: Enhanced prompt for better data capture.
        if not DEEPSEEK_API_KEY:
            st.error("Error: DEEPSEEK_API_KEY not found.")
            return None
        if not _text_content or not _text_content.strip():
            st.warning("Input text is empty. Cannot perform analysis.")
            return None

        prompt = f"""
        As a specialist financial analyst, your task is to meticulously analyze the following corporate document for {company_name} ({ticker}).
        Your entire focus must be on comments related to **tariffs, trade duties, and import taxes**.

        **CRITICAL RULE:** You must extract all specific quantitative data mentioned, such as dollar amounts ($40 million), basis points (170 bps), or percentages (10% to 50%). If specific numbers are mentioned, include them directly in your summary. Do not generalize if specifics are provided. For qualitative points, summarize them concisely. If a topic is not discussed, you MUST return "No discussion".

        Return a single valid JSON object with the following fields:
        - "company_name": "{company_name}"
        - "ticker": "{ticker}"
        - "management_commentary": "A concise summary of the company's overall stance and key messages regarding tariffs."
        - "vulnerability": "Identify the company's financial/operational exposure. Name the specific tariffs (e.g., Section 232), products, and countries involved."
        - "profitability_impact": "How do tariffs affect costs and margins? **Capture all specific financial impacts** (e.g., '$90 million annually', 'reduce operating margins by 170 basis points')."
        - "pricing_implication": "How is the company changing prices due to tariffs? Mention any selective or broad-based price increases."
        - "demand_sensitivity": "How are tariffs expected to impact demand for the company's products? Is the effect positive or negative?"
        - "guidance_implications": "How have tariffs specifically impacted the company's financial guidance or outlook? Mention any quantified impacts (e.g., 'incorporated a 170 basis point tariff impact into Q3 guidance')."
        - "mitigation_strategies": "List the key strategies the company is using to handle tariffs (e.g., supply chain changes, cost savings, negotiations, vertical integration)."
        - "the_known_unknowns": "What are the potential The Known Unknowns, risks, or policy uncertainties mentioned?"
        - "competitive_positioning": "How do tariffs affect the company's competitive position? Do they see it as an advantage or disadvantage?"

        Document Text:
        ---
        {_text_content[:40000]}
        ---
        """
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
        data = {"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0.1, "response_format": {"type": "json_object"}}
        try:
            response = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=data, timeout=120)
            response.raise_for_status()
            content_str = response.json()['choices'][0]['message']['content']
            return json.loads(content_str)
        except requests.exceptions.RequestException as e:
            st.error(f"Error calling DeepSeek API: {e}")
            return None
        except (json.JSONDecodeError, KeyError) as e:
            st.error(f"Error parsing DeepSeek API JSON response: {e}\nResponse: {content_str}")
            return None

    # --- DISPLAY & DOWNLOAD FUNCTIONS ---
    def display_tariff_tables(df1, df2, df3):
        st.markdown("---")
        st.header("Tariff Impact Analysis")

        # Display Table 1
        st.subheader("Table 1: Overall Impact & Exposure")
        if not df1.empty:
            st.markdown(df1.to_html(escape=False, index=False, justify='left'), unsafe_allow_html=True)
        else:
            st.info("No data available to display.")

        st.markdown("<br>", unsafe_allow_html=True) 

        # Display Table 2
        st.subheader("Table 2: Business & Strategy Impact")
        if not df2.empty:
            st.markdown(df2.to_html(escape=False, index=False, justify='left'), unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)

        # Display Table 3
        st.subheader("Table 3: Future Outlook")
        if not df3.empty:
            st.markdown(df3.to_html(escape=False, index=False, justify='left'), unsafe_allow_html=True)

    def generate_html_report(df1, df2, df3, logo_b64):
        # MODIFICATION 2: New HTML report function for the three-table format.
        styles = """<style>
            body { font-family: 'Poppins', sans-serif; background-color: #f9fafb; padding: 20px; color: #333; }
            h1, h2, h3 { color: #1e1e1e; }
            table { width: 100%; border-collapse: collapse; margin-bottom: 30px; }
            th, td { padding: 12px 15px; text-align: left; border: 1px solid #e0e0e0; vertical-align: top; font-size: 14px; }
            th { background-color: #00416A; color: #ffffff; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            .header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 1rem; border-bottom: 3px solid #00416A; margin-bottom: 2rem; }
            .title { font-size: 2.5rem; font-weight: 700; }
            .logo img { height: 40px; }
            </style>"""
        
        header_html = f"""
            <div class="header">
                <div class="title">Tariff Impact Tracker Report</div>
                <div class="logo"><img src="data:image/png;base64,{logo_b64}" alt="Logo"></div>
            </div>"""

        def df_to_html_bold_company(df):
            df_copy = df.copy()
            df_copy['Company'] = df_copy['Company'].apply(lambda x: f"<b>{x}</b>")
            return df_copy.to_html(escape=False, index=False)

        table1_html = f"<h2>Table 1: Overall Impact & Exposure</h2>" + (df_to_html_bold_company(df1) if not df1.empty else "<p>No data.</p>")
        table2_html = f"<h2>Table 2: Business & Strategy Impact</h2>" + (df_to_html_bold_company(df2) if not df2.empty else "<p>No data.</p>")
        table3_html = f"<h2>Table 3: Future Outlook</h2>" + (df_to_html_bold_company(df3) if not df3.empty else "<p>No data.</p>")
        
        full_html_content = f"<html><head><title>Tariff Impact Report</title>{styles}</head><body>{header_html}{table1_html}{table2_html}{table3_html}</body></html>"
        return full_html_content

    def generate_word_report(df1, df2, df3):
        # MODIFICATION 2: New Word report function for the three-table format.
        doc = Document()
        doc.add_heading('Tariff Impact Report', level=0)
        
        for i, df in enumerate([df1, df2, df3]):
            if df.empty: continue
            
            table_titles = ["Table 1: Overall Impact & Exposure", "Table 2: Business & Strategy Impact", "Table 3: Future Outlook"]
            doc.add_heading(table_titles[i], level=1)
            
            table = doc.add_table(rows=1, cols=len(df.columns))
            table.style = 'Table Grid'
            hdr_cells = table.rows[0].cells
            for j, col_name in enumerate(df.columns):
                hdr_cells[j].text = col_name

            for index, row in df.iterrows():
                row_cells = table.add_row().cells
                for j, cell_value in enumerate(row):
                    row_cells[j].text = str(cell_value)
            doc.add_paragraph() # Add space between tables

        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer

    # --- STREAMLIT UI LAYOUT ---
    st.subheader("Data Source")
    data_source = st.radio(
        "Choose where to get the transcript from:",
        ("Fetch Transcript", "Upload PDF Transcript(s)"),
        horizontal=True,
        label_visibility="collapsed"
    )

    if 'tariff_all_analysis_results' not in st.session_state:
        st.session_state.tariff_all_analysis_results = {}
    # --- NEW UI for Custom Prompt ---
    st.markdown("---")
    st.subheader("Advanced: Customize Analysis Prompt")
    st.warning("The Tariff Tracker requires a specific JSON output. Your custom prompt must request this structure or the analysis will fail.")
    st.text_area(
        "Enter your custom prompt for tariff analysis:",
        placeholder="Enter your full custom prompt here. It must ask for a JSON object with keys like 'management_commentary', 'vulnerability', etc.",
        height=250,
        key="tariff_custom_prompt"
    )
    # --- END NEW UI ---    
    if data_source == "Fetch Transcript":
        tickers_input = st.text_input("Company Ticker(s)", "CROX, STLD, CLF", help="Enter one or more tickers, separated by commas.")
        c2, c3 = st.columns(2)
        with c2: year = st.number_input("Year", min_value=2010, max_value=datetime.now().year + 1, value=2025)
        with c3: quarter = st.selectbox("Quarter", [1, 2, 3, 4], index=1)

        if st.button("Fetch & Analyze Transcripts", type="primary"):
            tickers = [ticker.strip().upper() for ticker in tickers_input.split(',') if ticker.strip()]
            if tickers:
                st.session_state.tariff_all_analysis_results = {}
                # MODIFICATION 1: Simplified loading message.
                with st.spinner("Generating analysis... This may take a moment."):
                    results = {}
                    for ticker in tickers:
                        text_to_analyze, company_name = get_transcript_from_fmp(ticker, year, quarter)
                        if text_to_analyze:
                            results[ticker] = analyze_text_with_deepseek(text_to_analyze, company_name, ticker)
                    st.session_state.tariff_all_analysis_results = results

    elif data_source == "Upload PDF Transcript(s)":
        uploaded_files = st.file_uploader("Upload one or more PDF files", type="pdf", accept_multiple_files=True)

        if st.button("Upload & Analyze PDFs", type="primary"):
            if uploaded_files:
                st.session_state.tariff_all_analysis_results = {}
                # MODIFICATION 1: Simplified loading message.
                with st.spinner("Generating analysis... This may take a moment."):
                    results = {}
                    for uploaded_file in uploaded_files:
                        company_key = os.path.splitext(uploaded_file.name)[0]
                        text_to_analyze = extract_text_from_pdf(uploaded_file)
                        if text_to_analyze:
                            results[company_key] = analyze_text_with_deepseek(text_to_analyze, company_key, "N/A")
                    st.session_state.tariff_all_analysis_results = results
            else:
                st.warning("Please upload at least one PDF file.")

    # --- DISPLAY RESULTS AND DOWNLOADS ---
    if st.session_state.get('tariff_all_analysis_results'):
        all_results = st.session_state.tariff_all_analysis_results
        df1, df2, df3 = prepare_table_data(all_results)
        
        display_tariff_tables(df1, df2, df3)

        # MODIFICATION 2: Re-enabled download buttons with updated functions.
        st.markdown("---")
        st.header("Download Report")
        
        col1, col2 = st.columns(2)
        if not df1.empty or not df2.empty or not df3.empty:
            with col1:
                html_content = generate_html_report(df1, df2, df3, logo_base64_string)
                st.download_button(
                    label="📥 Download as HTML",
                    data=html_content,
                    file_name="tariff_impact_report.html",
                    mime="text/html"
                )
            with col2:
                word_buffer = generate_word_report(df1, df2, df3)
                st.download_button(
                    label="📥 Download as Word",
                    data=word_buffer,
                    file_name="tariff_impact_report.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )



# ==============================================================================
# 8. Agent PE (Azure POWERED)
# ==============================================================================

def pe_agent_app_azure():
    """
    A secure, confidential agent for Private Equity analysis using Azure services.
    This version includes a deal document analyzer, an advanced bulk outreach email generator,
    a Diligence Q&A tool, an Expert Call Summarizer, and a Key Terms Comparison tool.
    """
    # --- Local imports ---
    import io, re, html, os, json, uuid
    import markdown, pdfplumber
    import pandas as pd
    import streamlit as st
    import requests
    from bs4 import BeautifulSoup
    from azure.core.credentials import AzureKeyCredential
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.ai.documentintelligence.models import ContentFormat
    from openai import AzureOpenAI
    from docx import Document
    from docx.shared import Pt

    st.markdown("### 🔒 Agent PE")
    st.markdown(
        "Analyze deal documents, generate outreach emails, and perform diligence with enterprise-grade privacy."
    )

    # --- AGENT CONFIG ---
    try:
        di_endpoint = os.environ.get("AZURE_DI_ENDPOINT")
        di_key = os.environ.get("AZURE_DI_KEY")
        openai_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        openai_key = os.environ.get("AZURE_OPENAI_KEY")
        openai_deployment_name = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
    except KeyError as e:
        st.error(f"Configuration error: Missing Azure secret: {e}. Please check your secrets.toml file.")
        st.stop()

    # --- Initialize AzureOpenAI client ---
    client = AzureOpenAI(
        api_key=openai_key,
        api_version="2024-02-01",
        azure_endpoint=openai_endpoint,
    )

    # --- PROMPTS FOR DOCUMENT ANALYSIS (Fully expanded) ---
    ANALYSIS_PROMPTS = {
        "Investment Thesis": (
            "You are a top-tier private equity analyst. Generate a comprehensive investment thesis based on the provided context. "
            "**CRITICAL RULE: Your entire response must be in clean MARKDOWN format.** "
            "Use markdown headings (`## Subheading`) for sections and bullet points (`* Point`) for lists. Do not create a main title. "
            "Structure your response with the following markdown headings:\n"
            "## Market Opportunity\n## Competitive Moat\n## Value Creation Levers\n## Overall Rationale"
        ),
        "Key Risks & Mitigants": (
            "You are a senior risk officer. **CRITICAL RULE: Your entire response must be in clean MARKDOWN format.** "
            "Use markdown headings (`## Subheading`) for sections and bullet points (`* Point`) for lists. Do not create a main title. "
            "Structure your response with the following markdown headings:\n"
            "## Market & Competitive Risks\n## Operational Risks\n## Financial Risks"
        ),
        "Financial Highlights": (
            "You are a financial diligence expert. **CRITICAL RULE: Your entire response must be in clean MARKDOWN format.** "
            "Use markdown headings (`## Subheading`) for sections and bullet points (`* Point`) for lists. Do not create a main title. "
            "Structure your response with the following markdown headings:\n"
            "## Revenue & Profitability\n## Balance Sheet Health\n## Cash Flow"
        ),
        "Potential Exit Options": (
            "You are a partner on the investment committee. **CRITICAL RULE: Your entire response must be in clean MARKDOWN format.** "
            "Use markdown headings (`## Subheading`) for sections and bullet points (`* Point`) for lists. Do not create a main title. "
            "Structure your response with the following markdown headings:\n"
            "## Strategic Sale\n## Secondary Buyout\n## Initial Public Offering (IPO)"
        ),
    }

    # --- HELPER FUNCTIONS ---

    # Document Analysis helpers
    def parse_pdf_with_azure_di(file_bytes: bytes) -> tuple[str, list]:
        try:
            di_client = DocumentIntelligenceClient(
                endpoint=di_endpoint,
                credential=AzureKeyCredential(di_key),
            )
            stream = io.BytesIO(file_bytes)
            poller = di_client.begin_analyze_document(
                model_id="prebuilt-layout",
                analyze_request=stream,
                content_type="application/pdf",
                pages=None,
                output_content_format=ContentFormat.MARKDOWN,
            )
            result = poller.result()
            return (result.content or ""), []
        except Exception as e:
            st.error(f"Azure AI Document Intelligence error: {e}")
            return None, []

    def fallback_pdf_text(file_bytes: bytes) -> str:
        text = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                text.append(page.extract_text() or "")
        return "\n".join(text).strip()
    
    def parse_text_file(file_bytes: bytes) -> str:
        try:
            return file_bytes.decode('utf-8')
        except Exception as e:
            st.warning(f"Could not read text file: {e}")
            return ""

    def parse_excel_to_markdown(file_bytes: bytes, file_name: str) -> str:
        try:
            xls = pd.ExcelFile(io.BytesIO(file_bytes))
            markdown_texts = []
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                df.dropna(how='all', axis=0, inplace=True)
                df.dropna(how='all', axis=1, inplace=True)
                if not df.empty:
                    markdown_texts.append(f"## Data from Sheet: {sheet_name}\n\n")
                    markdown_texts.append(df.to_markdown(index=False))
            return "\n\n".join(markdown_texts)
        except Exception as e:
            st.warning(f"Could not process Excel file {file_name}: {e}")
            return ""

    def analyze_document_with_azure_openai(_context: str, _prompt: str) -> str:
        try:
            response = client.chat.completions.create(
                model=openai_deployment_name,
                messages=[
                    {"role": "system", "content": "You are an expert financial analyst that responds only with clean, structured markdown as instructed."},
                    {"role": "user", "content": f"CONTEXT DOCUMENT:\n---\n{_context}\n---\nYOUR TASK: {_prompt}"},
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"## Error\n\n**Error during Azure OpenAI analysis:** {e}"

    def parse_markdown_to_html(analysis_results: dict) -> tuple[str, str]:
        styles = """
        <style>
            .analysis-container { font-family: 'Poppins', sans-serif; border: 1px solid #e0e0e0; border-radius: 8px; padding: 25px; background-color: #f9fafb; }
            .analysis-container h2 { font-size: 1.5em; font-weight: 600; color: #00416A; border-bottom: 2px solid #00416A; padding-bottom: 10px; margin-top: 0; margin-bottom: 20px; }
            .analysis-container h3 { font-size: 1.05em; font-weight: 600; color: #00416A; padding-bottom: 5px; margin-top: 25px; border-bottom: 1px solid #e6f1f6;}
            .analysis-container p { margin-bottom: 1em; line-height: 1.6; color: #333; }
            .analysis-container ul { list-style-position: outside; padding-left: 20px; margin-top: 1em; margin-bottom: 1em; }
            .analysis-container li { margin-bottom: 0.75em; line-height: 1.6; }
            .analysis-container table { width: 100%; border-collapse: collapse; margin: 15px 0; }
            .analysis-container th, .analysis-container td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            .analysis-container th { background-color: #f2f2f2; }
        </style>
        """
        full_html_body = ""
        for title, markdown_content in analysis_results.items():
            full_html_body += f"<h2>{html.escape(title)}</h2>"
            html_from_md = markdown.markdown(markdown_content, extensions=['tables'])
            processed_html = re.sub(r"<h2>(.*?)</h2>", r"<h3>\1</h3>", html_from_md)
            full_html_body += processed_html
        content_div = f"<div class='analysis-container'>{full_html_body}</div>"
        return styles, content_div

    # ADVANCED OUTREACH HELPER FUNCTIONS
    def scrape_website_text(url: str) -> str:
        if not (url.startswith('http://') or url.startswith('https://')):
            url = 'http://' + url
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.decompose()
            text = soup.get_text(separator='\n', strip=True)
            return re.sub(r'\n{3,}', '\n\n', text)
        except requests.RequestException as e:
            st.warning(f"Failed to scrape {url}: {e}")
            return ""

    def parse_word_doc(file_bytes: bytes) -> str:
        try:
            doc = Document(io.BytesIO(file_bytes))
            return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        except Exception:
            st.warning("Failed to parse Word document. Please ensure it is a .docx file.")
            return ""

    def analyze_source_for_outreach(company_name: str, source_text: str) -> str:
        prompt = f"""...""" # Omitted for brevity
        try:
            response = client.chat.completions.create(model=openai_deployment_name, messages=[{"role": "user", "content": f"{prompt}\n\nSOURCE TEXT:\n---\n{source_text[:12000]}\n---"}], temperature=0.1)
            return response.choices[0].message.content
        except Exception as e:
            return f"Error during AI analysis: {e}"

    def generate_advanced_outreach_email(company_name: str, recipient_name: str, analysis_points: str, value_prop: str, sender_name: str, sender_title: str, firm_name: str) -> str:
        prompt = f"""...""" # Omitted for brevity
        try:
            response = client.chat.completions.create(model=openai_deployment_name, messages=[{"role": "user", "content": prompt}], temperature=0.5)
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating email: {e}"
            
    def generate_word_document_from_drafts(drafts: list) -> bytes:
        doc = Document()
        doc.add_heading('Bulk Outreach Email Drafts', level=0)
        style = doc.styles['Normal']
        style.font.name = 'Aptos Display'
        style.font.size = Pt(11)
        for i, item in enumerate(drafts):
            company_name = item.get('Company', 'Unknown Company').replace('_', ' ')
            email_draft = item.get('Draft', 'No draft generated.')
            doc.add_heading(company_name, level=2)
            doc.add_paragraph(email_draft)
            if i < len(drafts) - 1:
                doc.add_page_break()
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()

    # --- UI TABS ---
    tab_titles = [
        "Deal Document Analysis", 
        "Diligence Q&A", 
        "Expert Call Summarizer",
        "Key Terms Comparison",
        "Email Outreach Generation"
    ]
    tab1, tab2, tab3, tab4, tab5 = st.tabs(tab_titles)

    # --- TAB 1: DEAL DOCUMENT ANALYSIS ---
    with tab1:
        st.subheader("Analyze Confidential Deal Documents")
        st.info("Upload a CIM, Teaser, or other confidential documents to generate a structured analysis.")
        
        uploaded_files_t1 = st.file_uploader(
            "Upload Teasers, CIMs, or Financials (PDF, XLSX, XLS)", type=["pdf", "xlsx", "xls"],
            accept_multiple_files=True, key="pe_agent_uploader_azure"
        )
        if uploaded_files_t1 and "pe_agent_text" not in st.session_state:
            if st.button("Process Documents", type="primary", key="process_docs_t1"):
                with st.spinner("Processing documents..."):
                    all_texts = []
                    for doc in uploaded_files_t1:
                        file_bytes = doc.getvalue()
                        
                        st.write(f"Processing '{doc.name}'...")
                        file_ext = os.path.splitext(doc.name)[1].lower()
                        doc_content = ""
                        if file_ext == ".pdf":
                            text, _ = parse_pdf_with_azure_di(file_bytes)
                            if not text:
                                text = fallback_pdf_text(file_bytes)
                            doc_content = text
                        elif file_ext in [".xlsx", ".xls"]:
                            doc_content = parse_excel_to_markdown(file_bytes, doc.name)
                        if doc_content:
                            all_texts.append(f"--- START: {doc.name} ---\n{doc_content}\n--- END: {doc.name} ---")
                    if all_texts:
                        st.session_state.pe_agent_text = "\n\n".join(all_texts)
                        st.rerun()
        if "pe_agent_text" in st.session_state:
            st.success("✅ Documents processed and ready for analysis.")
            analysis_choices = st.multiselect("Choose analyses:", options=list(ANALYSIS_PROMPTS.keys()), default=list(ANALYSIS_PROMPTS.keys()))
            if st.button("Generate Analysis", use_container_width=True, key="generate_analysis_t1"):
                full_text = st.session_state.pe_agent_text
                analysis_results = {}
                with st.spinner("Generating insights..."):
                    for choice in analysis_choices:
                        result = analyze_document_with_azure_openai(full_text, ANALYSIS_PROMPTS[choice])
                        analysis_results[choice] = result
                st.session_state.pe_agent_analysis_results = analysis_results
        if "pe_agent_analysis_results" in st.session_state:
            st.markdown("---")
            st.subheader("Generated Analysis")
            styles_html, content_html = parse_markdown_to_html(st.session_state.pe_agent_analysis_results)
            st.markdown(styles_html, unsafe_allow_html=True)
            st.markdown(content_html, unsafe_allow_html=True)


    # --- TAB 2: DILIGENCE Q&A ---
    with tab2:
        st.subheader("Diligence Q&A Agent")
        st.info("Upload a market study, report, or CIM and ask specific questions to get answers directly from the text.")
        
        uploaded_file_t2 = st.file_uploader("Upload Document for Q&A (PDF, DOCX, TXT)", type=['pdf', 'docx', 'txt'], key="qa_uploader")
        
        if uploaded_file_t2:
            file_bytes = uploaded_file_t2.getvalue()
            file_ext = os.path.splitext(uploaded_file_t2.name)[1].lower()
            doc_text = ""
            if file_ext == '.pdf':
                doc_text, _ = parse_pdf_with_azure_di(file_bytes)
                if not doc_text: doc_text = fallback_pdf_text(file_bytes)
            elif file_ext == '.docx':
                doc_text = parse_word_doc(file_bytes)
            elif file_ext == '.txt':
                doc_text = parse_text_file(file_bytes)
            
            st.session_state['qa_doc_text'] = doc_text
            st.success(f"✅ Successfully processed '{uploaded_file_t2.name}'. You can now ask questions.")

        if 'qa_doc_text' in st.session_state:
            user_question = st.text_input("Ask a question about the document:")
            if user_question:
                with st.spinner("Searching for answers in the document..."):
                    prompt = f"""You are a Q&A assistant. Answer the user's question based ONLY on the provided document context. If the answer is not in the text, state that clearly. Provide relevant quotes where possible.

                    DOCUMENT CONTEXT:
                    ---
                    {st.session_state['qa_doc_text']}
                    ---
                    
                    QUESTION: {user_question}
                    """
                    response = client.chat.completions.create(model=openai_deployment_name, messages=[{"role": "user", "content": prompt}])
                    st.markdown(response.choices[0].message.content)

    # --- TAB 3: EXPERT CALL SUMMARIZER ---
    with tab3:
        st.subheader("Expert Call Summarizer")
        st.info("Upload one or more transcripts from expert network calls to generate a structured summary.")
        
        uploaded_files_t3 = st.file_uploader("Upload Transcripts (.txt, .docx)", type=['txt', 'docx'], accept_multiple_files=True, key="expert_call_uploader")
        
        if st.button("Summarize Transcripts", key="summarize_calls", disabled=not uploaded_files_t3):
            all_transcripts = []
            for file in uploaded_files_t3:
                file_bytes = file.getvalue()
                file_ext = os.path.splitext(file.name)[1].lower()
                transcript_text = ""
                if file_ext == '.docx':
                    transcript_text = parse_word_doc(file_bytes)
                elif file_ext == '.txt':
                    transcript_text = parse_text_file(file_bytes)
                
                if transcript_text:
                    all_transcripts.append(f"--- TRANSCRIPT: {file.name} ---\n{transcript_text}\n--- END TRANSCRIPT ---")
            
            if all_transcripts:
                full_context = "\n\n".join(all_transcripts)
                prompt = f"""You are a private equity analyst. Synthesize the provided expert call transcript(s) into a single, structured summary. 

                CONTEXT:
                ---
                {full_context}
                ---

                TASK: Generate a report in MARKDOWN format with the following headings:
                ## Key Takeaways
                (A bulleted list of the most critical insights and conclusions from the calls.)
                ## Red Flags & Concerns
                (A bulleted list of points raised by the expert(s) that require further diligence or present risks.)
                ## Supporting Quotes
                (A bulleted list of the most impactful direct quotes from the expert(s), citing the source transcript name if possible.)
                """
                with st.spinner("Synthesizing expert calls..."):
                    response = client.chat.completions.create(model=openai_deployment_name, messages=[{"role": "user", "content": prompt}])
                    st.session_state['expert_call_summary'] = response.choices[0].message.content

        if 'expert_call_summary' in st.session_state:
            st.markdown(st.session_state['expert_call_summary'])


    # --- TAB 4: KEY TERMS COMPARISON ---
    with tab4:
        st.subheader("Key Terms Comparison Tool")
        st.info("Upload multiple documents (e.g., term sheet, credit agreement) to extract and compare key terms side-by-side.")
        
        uploaded_files_t4 = st.file_uploader("Upload Documents to Compare (.pdf, .docx)", type=['pdf', 'docx'], accept_multiple_files=True, key="comparison_uploader")
        
        terms_to_extract = st.text_area("Enter key terms to extract (one per line)", "Purchase Price\nClosing Conditions\nBreak Fee\nFinancial Covenants")
        
        if st.button("Extract & Compare Terms", key="compare_terms", disabled=(len(uploaded_files_t4) < 2)):
            comparison_data = {}
            terms_list = [term.strip() for term in terms_to_extract.split('\n') if term.strip()]
            
            with st.spinner("Extracting terms from documents..."):
                for file in uploaded_files_t4:
                    file_bytes = file.getvalue()
                    file_ext = os.path.splitext(file.name)[1].lower()
                    doc_text = ""
                    if file_ext == '.pdf':
                        doc_text, _ = parse_pdf_with_azure_di(file_bytes)
                        if not doc_text: doc_text = fallback_pdf_text(file_bytes)
                    elif file_ext == '.docx':
                        doc_text = parse_word_doc(file_bytes)
                    
                    if doc_text:
                        prompt = f"""You are a legal diligence assistant. From the document text provided, extract the exact clause or definition for each of the following key terms. If a term is not found, state "Not Found".

                        DOCUMENT TEXT:
                        ---
                        {doc_text[:20000]}
                        ---

                        KEY TERMS TO EXTRACT:
                        {', '.join(terms_list)}

                        Return your response as a JSON object where keys are the terms and values are the extracted text.
                        """
                        response = client.chat.completions.create(
                            model=openai_deployment_name,
                            messages=[{"role": "user", "content": prompt}],
                            response_format={"type": "json_object"}
                        )
                        try:
                            extracted_terms = json.loads(response.choices[0].message.content)
                            comparison_data[file.name] = extracted_terms
                        except json.JSONDecodeError:
                            st.warning(f"Could not parse JSON for {file.name}")
            
            if comparison_data:
                df_data = []
                for term in terms_list:
                    row = {"Key Term": term}
                    for doc_name, terms in comparison_data.items():
                        row[doc_name] = terms.get(term, "Not Found")
                    df_data.append(row)
                
                st.session_state['comparison_df'] = pd.DataFrame(df_data)

        if 'comparison_df' in st.session_state:
            st.dataframe(st.session_state['comparison_df'], use_container_width=True)


    # --- TAB 5: ADVANCED OUTREACH GENERATION ---
    with tab5:
        st.subheader("Generate Highly Personalized Outreach Emails")
        st.info(
            "💡 **Pro Tip:** Some websites may block automated access. For reliable results, use the 'Upload Document' option.",
            icon="ℹ️"
        )
        st.markdown("""<style>.section-header { font-weight: 600; font-size: 1rem; padding-bottom: 0; margin-bottom: -0.5rem; }</style>""", unsafe_allow_html=True)
        
        if 'pe_outreach_targets' not in st.session_state:
            st.session_state.pe_outreach_targets = []
        if not st.session_state.pe_outreach_targets:
            new_id = str(uuid.uuid4())
            st.session_state.pe_outreach_targets.append({'id': new_id, 'file_uploader_key': f'file_{new_id}'})
        
        num_targets = st.number_input(
            "Number of Target Companies", min_value=1, max_value=20,
            value=len(st.session_state.pe_outreach_targets), step=1, key='num_outreach_targets'
        )

        current_len = len(st.session_state.pe_outreach_targets)
        if current_len < num_targets:
            for _ in range(num_targets - current_len):
                new_id = str(uuid.uuid4())
                st.session_state.pe_outreach_targets.append({'id': new_id, 'file_uploader_key': f'file_{new_id}'})
        elif current_len > num_targets:
            st.session_state.pe_outreach_targets = st.session_state.pe_outreach_targets[:num_targets]

        with st.form("advanced_outreach_form"):
            st.markdown("<p class='section-header'>1. Define Your Firm & Sender Details</p>", unsafe_allow_html=True)
            firm_value_prop = st.text_area("Your Firm's Value Proposition", placeholder="e.g., We are a growth equity firm...", label_visibility="collapsed")
            c1, c2, c3 = st.columns(3)
            sender_name = c1.text_input("Your Name", placeholder="Alex Johnson")
            sender_title = c2.text_input("Your Title", placeholder="Associate")
            firm_name = c3.text_input("Your Firm's Name", placeholder="Growth Equity Partners")

            st.markdown('<p class="section-header">2. Define Target Companies</p>', unsafe_allow_html=True)
            
            for i, target in enumerate(st.session_state.pe_outreach_targets):
                st.markdown(f"---")
                st.markdown(f"**Target Company #{i+1}**")
                cols = st.columns([4, 4, 5])
                target['company_name'] = cols[0].text_input("Company Name", key=f"company_{target['id']}")
                target['recipient_name'] = cols[1].text_input("Recipient Name (Optional)", key=f"recipient_{target['id']}")
                target['source_type'] = cols[2].radio("Customization Source", ["Website URL", "Upload Document"], key=f"source_{target['id']}", horizontal=True)

                if target['source_type'] == "Website URL":
                    target['url'] = st.text_input("Website URL", placeholder="www.examplecorp.com", key=f"url_{target['id']}")
                else:
                    target['file'] = st.file_uploader("Upload PDF or Word Doc", type=['pdf', 'docx'], key=target['file_uploader_key'])
            
            submitted = st.form_submit_button("🚀 Generate Email Drafts", use_container_width=True)

        if submitted:
            if not all([firm_value_prop, sender_name, firm_name]):
                st.warning("Please fill out your firm and sender details.")
            else:
                email_drafts = []
                with st.spinner("Analyzing sources and generating drafts..."):
                    for i, target_data in enumerate(st.session_state.pe_outreach_targets):
                        company = target_data.get('company_name')
                        if not company:
                            st.warning(f"Skipping Target #{i+1} because company name is missing.")
                            continue

                        st.write(f"Processing: **{company}**")
                        source_text = ""
                        uploaded_file_obj = target_data.get('file')

                        if target_data['source_type'] == "Website URL" and target_data.get('url'):
                            source_text = scrape_website_text(target_data['url'])
                        elif target_data['source_type'] == "Upload Document" and uploaded_file_obj:
                            file_bytes = uploaded_file_obj.getvalue()
                            if uploaded_file_obj.name.lower().endswith('.pdf'):
                                source_text, _ = parse_pdf_with_azure_di(file_bytes)
                                if not source_text: source_text = fallback_pdf_text(file_bytes)
                            elif uploaded_file_obj.name.lower().endswith('.docx'):
                                source_text = parse_word_doc(file_bytes)
                        
                        analysis = analyze_source_for_outreach(company, source_text)
                        email = generate_advanced_outreach_email(
                            company, target_data.get('recipient_name'), analysis,
                            firm_value_prop, sender_name, sender_title, firm_name
                        )
                        email_drafts.append({"Company": company, "Draft": email})

                st.session_state.pe_advanced_outreach_results = email_drafts

        if 'pe_advanced_outreach_results' in st.session_state:
            st.success("✅ Email drafts generated successfully!")
            results = st.session_state.pe_advanced_outreach_results
            
            word_bytes = generate_word_document_from_drafts(results)
            st.download_button(
                "📥 Download All Drafts (.docx)", word_bytes, "advanced_outreach_drafts.docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True
            )
            
            st.markdown("---")
            for item in results:
                st.subheader(item['Company'].replace('_', ' '))
                st.code(item['Draft'], language='text')
                st.markdown("---")


# ==============================================================================
# 9. Agent Credit (Azure POWERED) - NEW
# ==============================================================================

def agent_credit_app_azure():
    """
    A secure, confidential agent for Private Credit analysis using Azure services.
    It analyzes credit agreements, monitors portfolio compliance, and compares deals.
    """
    # --- Local imports ---
    import io
    import re
    import os
    import html
    import json
    import markdown
    import pdfplumber
    import pandas as pd
    import streamlit as st
    from azure.core.credentials import AzureKeyCredential
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.ai.documentintelligence.models import ContentFormat
    from openai import AzureOpenAI
    from st_supabase_connection import SupabaseConnection
    import time
    from openai import RateLimitError

    st.markdown("### 🔒 Agent Credit")
    st.markdown(
        "Analyze, compare, and monitor confidential credit investments with enterprise-grade privacy."
    )

    # --- AGENT CONFIG (Fetched from secrets for Azure) ---
    try:
        di_endpoint = os.environ.get("AZURE_DI_ENDPOINT")
        di_key = os.environ.get("AZURE_DI_KEY")
        openai_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        openai_key = os.environ.get("AZURE_OPENAI_KEY")
        openai_deployment_name = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
        conn = st.connection("supabase", type=SupabaseConnection)
    except Exception as e:
        st.error(f"Configuration or Connection error: {e}. Please check your secrets.toml file.")
        st.stop()

    # --- HELPER FUNCTIONS (ALIGNED WITH TEST FUNCTION) ---
    TOPIC_SYNONYMS = {
        "negative_covenants": {
            "headings": [
                "negative covenants", "restrictive covenants", "certain covenants",
                "limitations", "restrictions"
            ],
            "keywords": [
                "limitation on liens", "liens", "lien", "security interest", "encumbrance",
                "mortgage", "pledge", "charge",
                "indebtedness", "debt incurrence", "borrowed money",
                "restricted payments", "dividends", "distributions", "stock buybacks",
                "asset sales", "dispositions", "sale-leaseback", "sale and leaseback",
                "affiliate transactions", "transactions with affiliates",
                "mergers", "consolidations", "amalgamations"
            ]
        },
        "positive_covenants": {
            "headings": [
                "affirmative covenants", "positive covenants", "affirmative undertakings",
                "information and reporting", "reporting covenants"
            ],
            "keywords": ["financial statements", "reporting", "certificate", "compliance certificate"]
        },
        "financial_covenant": {
            "headings": [
                "financial covenant", "maintenance covenant", "leverage ratio",
                "interest coverage", "secured leverage", "first lien leverage", "net leverage"
            ],
            "keywords": ["covenant", "ratio", "not to exceed", "at least", "step-down", "holiday"]
        },
        "repayment_terms": {
            "headings": ["repayment", "amortization", "maturity"],
            "keywords": ["scheduled amortization", "repay", "maturity date", "principal payment"]
        },
        "pricing_interest": {
            "headings": ["interest", "interest rate determination", "applicable margin", "fees"],
            "keywords": [
                "sofr", "libor", "base rate", "benchmark", "margin", "floor",
                "commitment fee", "utilization fee", "pricing grid"
            ]
        },
        "guarantees_security": {
            "headings": ["guarantee", "guaranty", "guarantors", "security", "collateral"],
            "keywords": ["secured", "unsecured", "lien priority", "perfection", "pledge agreement"]
        },
        "key_definitions": {
            "headings": ["definitions", "defined terms", "certain definitions", "interpretation"],
            "keywords": ["means", "shall mean", "as defined"]
        },
        "events_of_default": {
            "headings": ["events of default", "event of default", "defaults"],
            "keywords": ["acceleration", "grace period", "cross default", "payment default"]
        },
        "capital_structure": {
            "headings": ["capitalization", "credit agreement", "description of notes", "description of debt"],
            "keywords": ["term loan", "revolving", "bridge", "senior notes", "issuance", "facility"]
        },
    }

    def _normalize_text(t: str) -> str:
        t = re.sub(r'(\w+)-\n(\w+)', r'\1\2', t)
        t = re.sub(r'[ \t]+\n', '\n', t)
        t = re.sub(r'\n{3,}', '\n\n', t)
        return t

    def build_heading_index(md_text: str):
        lines = md_text.splitlines()
        idx = []
        pos = 0
        for i, line in enumerate(lines):
            line_start = pos
            pos += len(line) + 1
            m = re.match(r'^(#{1,6})\s+(.+)', line.strip())
            if m:
                level = len(m.group(1))
                title = m.group(2).strip().lower()
                idx.append({"level": level, "title": title, "char_start": line_start})
        for i in range(len(idx)):
            start = idx[i]["char_start"]
            end = idx[i+1]["char_start"] if i+1 < len(idx) else len(md_text)
            idx[i]["char_end"] = end
        return idx

    def _match_score(s: str, needles: list[str]) -> int:
        s = s.lower()
        return sum(1 for n in needles if n in s)

    def candidates_by_headings(md_text: str, topic_key: str, topn: int = 3) -> list[str]:
        idx = build_heading_index(md_text)
        syn = TOPIC_SYNONYMS.get(topic_key, {})
        titles = [(h, _match_score(h["title"], syn.get("headings", []))) for h in idx]
        titles = [t for t in titles if t[1] > 0]
        titles.sort(key=lambda x: (-x[1], x[0]["level"]))
        blocks = []
        for h, _score in titles[:topn]:
            blocks.append(md_text[h["char_start"]:h["char_end"]][:20000])
        return blocks

    def candidates_by_keywords(md_text: str, topic_key: str, window_chars: int = 2200, topn: int = 3) -> list[str]:
        syn = TOPIC_SYNONYMS.get(topic_key, {})
        keys = syn.get("keywords", [])
        text_low = md_text.lower()
        hits = []
        for k in keys:
            for m in re.finditer(re.escape(k.lower()), text_low):
                start = max(0, m.start() - window_chars//2)
                end   = min(len(md_text), m.start() + window_chars//2)
                hits.append((start, end))
        hits = sorted(hits)
        merged, last = [], None
        for s, e in hits:
            if not last or s > last[1] + 200:
                merged.append([s, e])
                last = merged[-1]
            else:
                last[1] = max(last[1], e)
        return [md_text[s:e][:20000] for s, e in merged[:topn]]

    def smart_candidates_for(topic_key: str, md_text: str) -> list[str]:
        md_text = _normalize_text(md_text)
        blocks = candidates_by_headings(md_text, topic_key)
        if not blocks:
            blocks = candidates_by_keywords(md_text, topic_key)
        return blocks or [md_text[:20000]]

    JSON_SCHEMAS = {
        "capital_structure": {"instruction": ("From the supplied excerpt(s), extract a structured list of instruments.\nReturn JSON with fields: instruments:[{name, type, currency, principal, rate_or_margin, benchmark, maturity_date, amortization, purpose, arrangers, doc_section, page, raw_quote}]. Numbers as plain strings if unknown. Use 'page' and 'doc_section' if visible from the excerpt.")},
        "repayment_terms": {"instruction": ("Extract repayment schedules for each tranche. Return JSON: schedules:[{instrument_name, amortization_pattern, periodic_percent, frequency, start_date, maturity_date, bullet, doc_section, page, raw_quote}]")},
        "guarantees_security": {"instruction": ("List guarantors, collateral/security, and whether unsecured. Return JSON: security:{unsecured:boolean, collateral_description, guarantors:[...], doc_section, page, raw_quote}")},
        "financial_covenant": {"instruction": ("Extract primary financial covenant. Return JSON: covenant:{name, threshold, comparator, stepdowns:[{effective_from, threshold}], holidays:[{type, duration}], test_frequency, definitions_used:[...], doc_section, page, raw_quote}")},
        "negative_covenants": {"instruction": ("Extract key negative covenants and their primary quantified exceptions/baskets.\nReturn JSON: negatives:[{topic, rule, key_baskets:[{name, limit_text, limit_value, limit_units, basis, greater_of: boolean, components: [{value, units, basis}]}], doc_section, heading, raw_quote}].\nIf uncertain, set fields to null. Do not invent data.")},
        "positive_covenants": {"instruction": ("Extract reporting deadlines and other duties. Return JSON: positives:[{topic, requirement, deadline, doc_section, page, raw_quote}]")},
        "key_definitions": {"instruction": ("Return JSON: definitions:[{term, definition_text, doc_section, page}]. Focus on EBITDA, Total Debt, Net Assets and any covenant-linked definitions.")},
        "events_of_default": {"instruction": ("Extract payment default, cross-default, covenant breach, grace periods. Return JSON: eods:[{topic, trigger, grace_period, threshold, remedies, doc_section, page, raw_quote}]")},
        "pricing_interest": {"instruction": ("Extract interest and fee terms by tranche.\nReturn JSON: pricing:[{instrument_name, benchmark, margin, floor, stepups, commitment_fee, utilization_fee, rate_grid_basis, heading, raw_quote}].\nIf values are in a grid/table, summarize in plain fields; unknown as null.")}
    }

    SYNTHESIS_PROMPTS = {
        "Key Terms Sheet": (
            "You are a top-tier credit analyst. Using the provided context, generate a **markdown table** summarizing the key terms. Populate the table with the most critical information found in the extracted clauses. If a specific piece of information is not found, state 'Not Specified'.\n\n"
            "| Term                  | Details                                                                                             |\n"
            "| :-------------------- | :-------------------------------------------------------------------------------------------------- |\n"
            "| Borrower              | (Identify all borrowing entities listed in the document)                                            |\n"
            "| Facilities            | (List the names and amounts of each facility, e.g., '$500M Revolver', '$1.2B Term Loan B')           |\n"
            "| Maturity              | (List the specific maturity date for each facility, e.g., 'July 27, 2028')                           |\n"
            "| Interest & Fees       | (Summarize the specific interest rate for each facility, e.g., 'Term Benchmark + 3.75% with a 0.50% floor') |\n"
            "| Guarantees            | (Summarize the guarantee structure, e.g., 'Guaranteed by Holdings, the Company, and Subsidiary Guarantors.') |\n"
            "| Security              | (Summarize the collateral, e.g., 'First-priority lien on substantially all assets of Loan Parties')   |\n"
            "| Financial Covenants   | (State the primary financial covenant precisely, e.g., 'First Lien Net Leverage Ratio not to exceed 8.70:1.00') |\n"
        ),
        "Capital Structure Summary": (
            "You are a top-tier credit analyst preparing a detailed memorandum. Using the following **extracted clauses**, generate a comprehensive summary of the company's capital structure. "
            "**CRITICAL RULE: Your entire response must be in clean, narrative MARKDOWN format. Write in full sentences and detailed paragraphs. Do not simply list facts; explain their implications for creditors.**\n\n"
            "## Debt Overview\n(Provide a high-level narrative. Use the 'capital_structure' context to describe the main layers of debt, total facility size, and its purpose, for instance, 'The company entered into a $6,000,000,000 Term Loan Credit Agreement to finance the Allergan Acquisition.')\n\n"
            "## Detailed Debt Instrument Analysis\n(Using the 'capital_structure', 'pricing_interest' and 'repayment_terms' context, create a **markdown table** with the following columns: 'Facility/Tranche', 'Principal Amount', 'Maturity Date', 'Interest Rate / Margin', and 'Key Amortization Terms'. Fill this table for **each** debt instrument identified.)\n\n"
            "## Guarantees & Security\n(Using the 'guarantees_security' context, write a detailed paragraph describing the support package. Specify which entities are guarantors. Detail the security package or, if the debt is explicitly stated as unsecured, state that clearly and explain what that implies for creditors.)"
        ),
        "Covenant Analysis": (
            "You are a senior credit analyst. RULES: "
            "(1) Markdown only; (2) ≥600 words; (3) include at least 3 blockquotes of verbatim language; "
            "(4) when possible, attribute quotes using the 'heading' field from the facts; "
            "(5) be precise and quantitative, avoid generalities.\n\n"
            "## Financial Covenants\n(Analyze the 'financial_covenant' and 'key_definitions' context. First, create a **markdown table** with columns: 'Covenant Name', 'Requirement', and 'Key Step-Downs'. Then, in a detailed paragraph below the table, describe the covenant, its definition (especially 'Consolidated EBITDA'), and any special conditions like an 'acquisition holiday'.)\n\n"
            "## Negative Covenants\n(Analyze the 'negative_covenants' context. For each sub-heading below, write a paragraph explaining the core prohibition and then describe the most significant exceptions and **quantitative baskets** in detail, quoting specific dollar amounts or percentages. For each topic present in facts.negatives, write: core rule, list of key baskets with values and bases, and insert a short blockquote of the operative sentence. If 'greater_of' is true, spell out both components.)\n"
            "### Limitation on Liens\n"
            "### Limitation on Indebtedness\n"
            "### Limitation on Mergers and Asset Sales\n\n"
            "## Positive (Affirmative) Covenants\n(Analyze the 'positive_covenants' context. Write a paragraph summarizing key obligations, focusing especially on the **specific financial reporting deadlines** you can find (e.g., 'within 50 days after the end of each of the first three quarters').)"
        ),
        "Credit Risk Factors": (
            "You are a credit risk officer writing an internal memorandum. **CRITICAL RULE: Your response must be a detailed, text-heavy narrative report in clean MARKDOWN format, based exclusively on the provided extracted clauses. You must reference specific contractual terms.**\n\n"
            "## Key Strengths for Creditors\n(Identify and summarize protective features from the document, such as a strong security package, tight covenants, or mandatory prepayments from asset sales.)\n\n"
            "## Key Risks & Mitigants\n(Analyze the agreement's structure using the 'negative_covenants' and 'events_of_default' context. Comment on potential weaknesses, such as loose covenants, large exception baskets, or long grace periods for default. For each risk, describe any mitigating factors present in the agreement.)"
        ),
    }

    REQUIRED_CONTEXT = {
        "Key Terms Sheet": ["capital_structure", "repayment_terms", "pricing_interest", "guarantees_security", "financial_covenant"],
        "Capital Structure Summary": ["capital_structure", "repayment_terms", "guarantees_security", "pricing_interest"],
        "Covenant Analysis": ["financial_covenant", "negative_covenants", "positive_covenants", "key_definitions", "events_of_default"],
        "Debt Maturity Profile": ["repayment_terms", "capital_structure"],
        "Credit Risk Factors": ["financial_covenant", "negative_covenants", "events_of_default", "capital_structure", "guarantees_security"]
    }

    def parse_markdown_to_html(analysis_results: dict, title: str) -> tuple[str, str]:
        styles = """
        <style>
            .analysis-container { font-family: 'Poppins', sans-serif; border: 1px solid #e0e0e0; border-radius: 8px; padding: 25px; background-color: #f9fafb; margin: 20px; }
            .analysis-container h1 { font-size: 1.8em; font-weight: 700; color: #00416A; margin-top: 0; padding-bottom: 15px; border-bottom: 3px solid #00416A; }
            .analysis-container h2 { font-size: 1.5em; font-weight: 600; color: #00416A; border-bottom: 2px solid #e6f1f6; padding-bottom: 10px; margin-top: 30px; margin-bottom: 20px; }
            .analysis-container h3 { font-size: 1.2em; font-weight: 600; color: #1e1e1e; margin-top: 25px; margin-bottom: 10px; }
            .analysis-container p, .analysis-container li { margin-bottom: 1em; line-height: 1.6; color: #333; }
            .analysis-container table { width: 100%; border-collapse: collapse; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
            .analysis-container th, .analysis-container td { border: 1px solid #ddd; padding: 12px 15px; text-align: left; vertical-align: top; }
            .analysis-container th { background-color: #e6f1f6; font-weight: 600; }
            .analysis-container tr:nth-of-type(even) { background-color: #fdfdfd; }
            .analysis-container code { white-space: pre-wrap !important; }
        </style>
        """
        html_body = f"<h1>{html.escape(title)}</h1>"
        for section_title, md_content in analysis_results.items():
            cleaned_md = re.sub(r'^```(markdown)?\s*|\s*```$', '', md_content.strip(), flags=re.MULTILINE)
            html_body += f"<h2>{html.escape(section_title)}</h2>" + markdown.markdown(cleaned_md, extensions=['tables'])
        content_div = f"<div class='analysis-container'>{html_body}</div>"
        return styles, content_div

    def parse_pdf_with_azure_di(file_bytes: bytes) -> tuple[str, list]:
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                n_pages = len(pdf.pages)
            client = DocumentIntelligenceClient(endpoint=di_endpoint, credential=AzureKeyCredential(di_key))
            md_parts, step = [], 30
            for start in range(1, n_pages + 1, step):
                # We need to pass a fresh BytesIO object for each API call
                stream = io.BytesIO(file_bytes)
                poller = client.begin_analyze_document(
                    "prebuilt-layout", 
                    stream, 
                    content_type="application/pdf", 
                    pages=f"{start}-{min(start + step - 1, n_pages)}", 
                    output_content_format=ContentFormat.MARKDOWN
                )
                md_parts.append(poller.result().content or "")
            return "\n\n".join(md_parts), []
        except Exception as e:
            st.error(f"Azure DI error: {e}")
            return None, []

    def fallback_pdf_text(file_bytes: bytes) -> str:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)

    def parse_excel_to_markdown(file_bytes: bytes, file_name: str) -> str:
        try:
            xls = pd.ExcelFile(io.BytesIO(file_bytes))
            markdown_texts = []
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                df.dropna(how='all', axis=0, inplace=True)
                df.dropna(how='all', axis=1, inplace=True)
                if not df.empty:
                    markdown_texts.append(f"## Data from Sheet: {sheet_name}\n\n")
                    markdown_texts.append(df.to_markdown(index=False))
            return "\n\n".join(markdown_texts)
        except Exception as e:
            st.warning(f"Could not process Excel file {file_name}: {e}")
            return ""

    def build_synthesis_context(extracted_data: dict, required_topics: list) -> str:
        context_parts = []
        for topic in required_topics:
            topic_data_list = extracted_data.get(topic)
            if not topic_data_list or not isinstance(topic_data_list, list):
                continue
            
            topic_data = topic_data_list[0]
            context_parts.append(f"--- Topic: {topic.replace('_', ' ').title()} ---")
            
            summary_parts = []
            if topic == "capital_structure" and 'instruments' in topic_data:
                for item in topic_data.get('instruments', []):
                    summary_parts.append(f"Instrument: {item.get('name')}, Principal: {item.get('currency')} {item.get('principal')}, Maturity: {item.get('maturity_date')}. Raw Quote: '{item.get('raw_quote')}'")
            elif topic == "repayment_terms" and 'schedules' in topic_data:
                for item in topic_data.get('schedules', []):
                    summary_parts.append(f"Repayment for {item.get('instrument_name')}: Maturity at {item.get('maturity_date')}. Raw Quote: '{item.get('raw_quote')}'")
            elif topic == "pricing_interest" and 'pricing' in topic_data:
                for item in topic_data.get('pricing', []):
                    summary_parts.append(f"Pricing for {item.get('instrument_name')}: {item.get('benchmark')} + {item.get('margin')}, Floor: {item.get('floor')}. Raw Quote: '{item.get('raw_quote')}'")
            elif topic == "guarantees_security" and 'security' in topic_data:
                sec = topic_data.get('security', {})
                summary_parts.append(f"Security Details: Collateral is '{sec.get('collateral_description')}', Guarantors: {', '.join(sec.get('guarantors', []))}. Raw Quote: '{sec.get('raw_quote')}'")
            elif topic == "financial_covenant" and 'covenant' in topic_data:
                cov = topic_data.get('covenant', {})
                summary_parts.append(f"Financial Covenant: Name is '{cov.get('name')}', Threshold is '{cov.get('threshold')} {cov.get('comparator')}'. Raw Quote: '{cov.get('raw_quote')}'")
            else:
                summary_parts.append(json.dumps({k: v for k, v in topic_data.items() if v}, indent=2))
            
            context_parts.append("\n".join(summary_parts))

        return "\n".join(context_parts)

    # CORRECTED CACHING AND ANALYSIS FUNCTION
    @st.cache_data(ttl=3600)
    def analyze_with_azure_openai(context_hash: int, prompt_hash: int, as_json: bool = False):
        try:
            context_text = st.session_state.get('context_cache', {}).get(context_hash)
            prompt_text = st.session_state.get('prompt_cache', {}).get(prompt_hash)
            if not context_text or not prompt_text:
                return {"error": "Context or prompt not found in cache"}

            client = AzureOpenAI(api_key=openai_key, api_version="2024-02-01", azure_endpoint=openai_endpoint)
            kwargs = {"response_format": {"type": "json_object"}} if as_json else {}
            
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = client.chat.completions.create(
                        model=openai_deployment_name,
                        temperature=0,
                        top_p=0,
                        extra_body={"seed": 1234}, # For reproducibility
                        messages=[
                            {"role": "system", "content": "You are a precise credit-document extractor. If JSON is requested, return ONLY strict JSON."},
                            {"role": "user", "content": f"CONTEXT EXCERPT:\n---\n{context_text}\n---\nTASK:\n{prompt_text}"}
                        ],
                        **kwargs
                    )
                    
                    txt = response.choices[0].message.content
                    if as_json:
                        try:
                            # Clean up potential markdown code fences around the JSON
                            cleaned_txt = re.sub(r"^```json|```$", "", txt.strip(), flags=re.MULTILINE)
                            return json.loads(cleaned_txt)
                        except json.JSONDecodeError:
                             return {"error": "Failed to decode JSON from AI response."}
                    return txt
                
                except RateLimitError as e:
                    wait_time = e.retry_after if hasattr(e, 'retry_after') and e.retry_after is not None else 15 * (attempt + 1)
                    st.warning(f"Rate limit exceeded. Waiting for {wait_time}s... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                except Exception as e:
                    return {"error": f"An unexpected API error occurred: {str(e)}"} if as_json else f"## Error\n**OpenAI Error:** {e}"
            
            return {"error": "Rate limit still exceeded after multiple retries."} if as_json else "## Error\n**Rate limit still exceeded after multiple retries.**"

        except Exception as e:
            return {"error": str(e)} if as_json else f"## Error\n**General Error:** {e}"
            
    @st.cache_data(ttl=600)
    def get_deal_list():
        try:
            response = conn.client.table("credit_deals").select("id, deal_name").order("created_at", desc=True).execute()
            return response.data
        except Exception as e:
            st.error(f"Could not fetch deal list from Supabase: {e}")
            return []

    def track_covenant_compliance(deal: dict, new_financials_doc: bytes, file_type: str):
        st.subheader(f"Covenant Compliance Check for: {deal['deal_name']}")
        with st.spinner("Analyzing new financials and checking compliance..."):
            stored_terms = deal.get('structured_terms', {})
            financial_covenant_data = stored_terms.get('financial_covenant', [])
            if not financial_covenant_data or 'covenant' not in financial_covenant_data[0]:
                st.warning("No financial covenant was extracted for this deal. Cannot perform compliance check.")
                return
            financial_covenant_clause = financial_covenant_data[0].get('covenant', {})

            new_financials_text = ""
            if file_type == '.pdf':
                new_financials_text, _ = parse_pdf_with_azure_di(new_financials_doc)
            elif file_type in ['.xlsx', '.xls']:
                new_financials_text = parse_excel_to_markdown(new_financials_doc, "financials")
            
            if not new_financials_text:
                st.error("Could not parse the uploaded financial document.")
                return

            # Caching setup for this specific analysis
            context_hash = hash(new_financials_text)
            st.session_state.setdefault('context_cache', {})[context_hash] = new_financials_text
            extraction_prompt = 'From the financial text, extract values for the most recent period. Return JSON with "consolidated_ebitda" and "consolidated_total_debt".'
            prompt_hash = hash(extraction_prompt)
            st.session_state.setdefault('prompt_cache', {})[prompt_hash] = extraction_prompt
            
            extracted_metrics = analyze_with_azure_openai(context_hash, prompt_hash, as_json=True)
            
            ebitda = extracted_metrics.get("consolidated_ebitda")
            debt = extracted_metrics.get("consolidated_total_debt")

            if not ebitda or not debt:
                st.error("Could not automatically extract EBITDA or Total Debt from the new financial document.")
                st.write("Agent Response:", extracted_metrics)
                return

            try:
                current_leverage = float(debt) / float(ebitda)
                covenant_limit = float(financial_covenant_clause.get('threshold', 0))
                covenant_name = financial_covenant_clause.get('name', 'N/A')
                cushion = covenant_limit - current_leverage
                cushion_pct = (cushion / covenant_limit) * 100 if covenant_limit != 0 else 0

                st.subheader(f"Results for {covenant_name}")
                if current_leverage <= covenant_limit:
                    st.success(f"✅ IN COMPLIANCE")
                else:
                    st.error(f"🚨 POTENTIAL BREACH")
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Current Leverage", f"{current_leverage:.2f}x")
                c2.metric("Covenant Limit", f"{covenant_limit:.2f}x")
                c3.metric("Headroom / Cushion", f"{cushion:.2f}x", delta=f"{cushion_pct:.1f}%")

            except (ValueError, TypeError, ZeroDivisionError) as e:
                st.error(f"Calculation Error: Could not convert extracted metrics to numbers. Details: {e}")
                st.write("Extracted Metrics:", {"EBITDA": ebitda, "Debt": debt})

    def spread_financial_statements(financials_doc_bytes: bytes):
        st.subheader("Financial Statement Spreading")
        with st.spinner("Extracting and standardizing financial statements..."):
            markdown_text, _ = parse_pdf_with_azure_di(financials_doc_bytes)
            if not markdown_text:
                st.error("Failed to extract any text from the PDF.")
                return

            context_hash = hash(markdown_text)
            st.session_state.setdefault('context_cache', {})[context_hash] = markdown_text
            spreading_prompt = """
            From the markdown text containing financial statements, identify the Income Statement, Balance Sheet, and Cash Flow Statement.
            For each statement, extract the line items and values for the most recent two periods.
            Return a single JSON object with three keys: "income_statement", "balance_sheet", "cash_flow".
            Each key should hold a list of objects, where each object is a row with "line_item", "period_1_value", and "period_2_value".
            Standardize common line items (e.g., 'Net Sales' -> 'Revenue').
            """
            prompt_hash = hash(spreading_prompt)
            st.session_state.setdefault('prompt_cache', {})[prompt_hash] = spreading_prompt

            spread_data = analyze_with_azure_openai(context_hash, prompt_hash, as_json=True)

            if spread_data and "error" not in spread_data:
                for statement, data in spread_data.items():
                    if data and isinstance(data, list):
                        st.write(f"**{statement.replace('_', ' ').title()}**")
                        df = pd.DataFrame(data)
                        st.dataframe(df, use_container_width=True)
                        csv = df.to_csv(index=False).encode('utf-8')
                        st.download_button(f"Download {statement}.csv", csv, f"{statement}.csv", "text/csv", key=f"download_{statement}")
            else:
                st.error("Failed to spread financial statements.")
                st.write("Agent Response:", spread_data)
    
    # --- UI & WORKFLOW ---
    tab_titles = ["New Deal Analysis", "Portfolio Monitoring", "Deal Comparison", "Financial Spreading", "Diligence Q&A"]
    tab1, tab2, tab3, tab4, tab5 = st.tabs(tab_titles)

    # --- TAB 1: NEW DEAL ANALYSIS (CORRECTED WORKFLOW) ---
    with tab1:
        st.subheader("1. Upload Confidential Documents")
        deal_name_input = st.text_input("Enter a unique name for this deal:", key="deal_name_input")
        uploaded_files = st.file_uploader("Upload Credit Agreements, CIMs, or Financials (PDF, XLSX, XLS)", type=["pdf", "xlsx", "xls"], accept_multiple_files=True, key="agent_credit_uploader_azure_tab1")
        
        analysis_choices_tab1 = st.multiselect(
            "Choose analyses to perform:",
            options=list(SYNTHESIS_PROMPTS.keys()),
            default=list(SYNTHESIS_PROMPTS.keys()),
            key="analysis_choices_tab1"
        )

        if st.button("Process & Analyze Documents", type="primary", key="process_button"):
            if not deal_name_input or not uploaded_files:
                st.warning("Please provide a deal name and upload at least one document.")
            else:
                with st.spinner("Processing documents... This may take a few minutes."):
                    all_texts = []
                    for doc in uploaded_files:
                        file_bytes = doc.getvalue()
                        file_ext = os.path.splitext(doc.name)[1].lower()
                        if file_ext == ".pdf":
                            text, _ = parse_pdf_with_azure_di(file_bytes)
                            if not text: text = fallback_pdf_text(file_bytes)
                            all_texts.append(text)
                        elif file_ext in [".xlsx", ".xls"]:
                            all_texts.append(parse_excel_to_markdown(file_bytes, doc.name))
                    full_text = "\n\n".join(all_texts)
                
                # Initialize caches
                st.session_state.context_cache = {}
                st.session_state.prompt_cache = {}

                with st.spinner("Stage 1/2: Extracting key clauses..."):
                    extracted_context = {}
                    needed_keys = set(k for choice in analysis_choices_tab1 for k in REQUIRED_CONTEXT.get(choice, []))
                    
                    for key in needed_keys:
                        st.write(f"Extracting clauses for: **{key.replace('_', ' ').title()}**")
                        candidate_snips = smart_candidates_for(key, full_text)
                        
                        if not candidate_snips:
                            extracted_context[key] = []
                            continue

                        combined_context = "\n\n---\n\n".join(candidate_snips)
                        safe_combined_context = combined_context[:150000]
                        
                        # Cache context and prompt
                        context_hash = hash(safe_combined_context)
                        st.session_state.context_cache[context_hash] = safe_combined_context
                        prompt_text = JSON_SCHEMAS[key]["instruction"]
                        prompt_hash = hash(prompt_text)
                        st.session_state.prompt_cache[prompt_hash] = prompt_text

                        res = analyze_with_azure_openai(context_hash, prompt_hash, as_json=True)
                        
                        if "error" not in res:
                            extracted_context[key] = [res]
                        else:
                            extracted_context[key] = []
                            st.error(f"Failed to extract '{key}': {res['error']}")
                
                with st.spinner("Stage 2/2: Synthesizing final report..."):
                    analysis_results = {}
                    for choice in analysis_choices_tab1:
                        st.write(f"Synthesizing: **{choice}**")
                        req_keys = REQUIRED_CONTEXT.get(choice, [])
                        
                        synthesis_context_str = build_synthesis_context(extracted_context, req_keys)
                        synthesis_task = SYNTHESIS_PROMPTS[choice]

                        # Cache context and prompt for synthesis
                        context_hash = hash(synthesis_context_str)
                        st.session_state.context_cache[context_hash] = synthesis_context_str
                        prompt_hash = hash(synthesis_task)
                        st.session_state.prompt_cache[prompt_hash] = synthesis_task
                        
                        analysis_results[choice] = analyze_with_azure_openai(context_hash, prompt_hash)
                
                st.session_state.agent_credit_analysis_results = analysis_results
                st.session_state.last_analyzed_deal = deal_name_input
                
                with st.spinner("Saving deal to portfolio database..."):
                    try:
                        conn.client.table("credit_deals").insert({
                            "deal_name": deal_name_input,
                            "structured_terms": extracted_context,
                            "full_text_markdown": full_text
                        }).execute()
                        st.success(f"'{deal_name_input}' has been successfully analyzed and saved.")
                        get_deal_list.clear()
                    except Exception as e:
                        st.error(f"Failed to save deal to Supabase: {e}")
                
                st.rerun()

        if "agent_credit_analysis_results" in st.session_state:
            st.markdown("---")
            styles, content = parse_markdown_to_html(st.session_state.agent_credit_analysis_results, f"Analysis for {st.session_state.get('last_analyzed_deal', 'the Deal')}")
            st.markdown(styles, unsafe_allow_html=True)
            st.markdown(content, unsafe_allow_html=True)
    
    # --- TAB 2: PORTFOLIO MONITORING ---
    with tab2:
        st.subheader("Portfolio Covenant Monitoring")
        deal_list = get_deal_list()
        if not deal_list:
            st.info("No deals have been analyzed yet. Please analyze a new deal in the first tab.")
        else:
            deal_options = {d['id']: d['deal_name'] for d in deal_list}
            selected_deal_id = st.selectbox("Select a Deal to Monitor", options=list(deal_options.keys()), format_func=lambda x: deal_options[x])
            
            uploaded_financials = st.file_uploader("Upload Latest Quarterly Financials (PDF or XLSX)", type=["pdf", "xlsx", "xls"], key="financials_uploader")
            
            if st.button("Run Compliance Check", key="compliance_button", use_container_width=True):
                if selected_deal_id and uploaded_financials:
                    response = conn.client.table("credit_deals").select("deal_name, structured_terms").eq("id", selected_deal_id).single().execute()
                    track_covenant_compliance(response.data, uploaded_financials.getvalue(), os.path.splitext(uploaded_financials.name)[1].lower())
                else:
                    st.warning("Please select a deal and upload a financials document.")
                    
    # --- TAB 3: DEAL COMPARISON ---
    with tab3:
        st.subheader("Side-by-Side Deal Comparison")
        deal_list = get_deal_list()
        if len(deal_list) < 2:
            st.info("You need at least two analyzed deals to make a comparison.")
        else:
            deal_options = {d['id']: d['deal_name'] for d in deal_list}
            col1, col2 = st.columns(2)
            deal_a_id = col1.selectbox("Select Deal A", options=list(deal_options.keys()), format_func=lambda x: deal_options[x], key="deal_a")
            deal_b_id = col2.selectbox("Select Deal B", options=list(deal_options.keys()), format_func=lambda x: deal_options[x], key="deal_b", index=1 if len(deal_options) > 1 else 0)
            
            if st.button("Compare Deals", key="compare_deals", use_container_width=True):
                if deal_a_id == deal_b_id:
                    st.warning("Please select two different deals.")
                else:
                    with st.spinner("Fetching data and generating comparison..."):
                        deal_a_data = conn.client.table("credit_deals").select("deal_name, structured_terms").eq("id", deal_a_id).single().execute().data
                        deal_b_data = conn.client.table("credit_deals").select("deal_name, structured_terms").eq("id", deal_b_id).single().execute().data
                        
                        comparison_context = f"""
                        DEAL A NAME: {deal_a_data['deal_name']}
                        DEAL A TERMS: {json.dumps(deal_a_data['structured_terms'])}

                        DEAL B NAME: {deal_b_data['deal_name']}
                        DEAL B TERMS: {json.dumps(deal_b_data['structured_terms'])}
                        """

                        comparison_prompt = f"""
                        You are a credit analyst. Compare the two sets of structured credit terms provided in the context.
                        Generate a markdown table with three columns: 'Term', '{deal_a_data['deal_name']}', and '{deal_b_data['deal_name']}'.
                        In the table, summarize the key terms for: Pricing & Fees, Maturity, Financial Covenants, and Security Package.
                        After the table, provide a short paragraph highlighting the most significant differences between the two deals.
                        """
                        # Caching setup for comparison
                        context_hash = hash(comparison_context)
                        st.session_state.setdefault('context_cache', {})[context_hash] = comparison_context
                        prompt_hash = hash(comparison_prompt)
                        st.session_state.setdefault('prompt_cache', {})[prompt_hash] = comparison_prompt
                        
                        comparison_md = analyze_with_azure_openai(context_hash, prompt_hash)
                        st.markdown(comparison_md)

    # --- TAB 4: FINANCIAL SPREADING ---
    with tab4:
        st.subheader("Automated Financial Statement Spreading")
        uploaded_fs_pdf = st.file_uploader("Upload Financial Statement PDF", type="pdf", key="fs_spreader")
        if st.button("Spread Financials", key="spread_button", disabled=not uploaded_fs_pdf, use_container_width=True):
            spread_financial_statements(uploaded_fs_pdf.getvalue())

    # --- TAB 5: DILIGENCE Q&A ---
    with tab5:
        st.subheader("Interactive Diligence Q&A")
        deal_list = get_deal_list()
        if not deal_list:
            st.info("No deals have been analyzed yet.")
        else:
            deal_options = {d['id']: d['deal_name'] for d in deal_list}
            qa_deal_id = st.selectbox("Select a Deal for Q&A", options=list(deal_options.keys()), format_func=lambda x: deal_options[x], key="qa_deal_select")
            user_question = st.text_input("Ask a question about the deal documents:")

            if user_question and qa_deal_id:
                with st.spinner("Searching for an answer..."):
                    response = conn.client.table("credit_deals").select("full_text_markdown").eq("id", qa_deal_id).single().execute()
                    context = response.data.get('full_text_markdown', '') if response.data else ''
                    
                    if not context:
                        st.error("Could not retrieve document text for this deal.")
                    else:
                        # Caching setup for Q&A
                        context_hash = hash(context)
                        st.session_state.setdefault('context_cache', {})[context_hash] = context
                        qa_prompt = f"Based ONLY on the provided document context, answer the following question. Quote the relevant text if possible.\n\nQuestion: {user_question}"
                        prompt_hash = hash(qa_prompt)
                        st.session_state.setdefault('prompt_cache', {})[prompt_hash] = qa_prompt
                        
                        answer = analyze_with_azure_openai(context_hash, prompt_hash)
                        st.markdown(answer)



# ==============================================================================
# 10. Model Integrity Agent (Azure POWERED) - NEW
# ==============================================================================

def model_integrity_agent_app():
    """
    A secure agent to analyze and audit Excel financial models for errors and inconsistencies.
    """
    # --- Local imports ---
    import io, re, html, markdown
    import streamlit as st
    import pandas as pd
    from openai import AzureOpenAI
    import openpyxl
    from openpyxl.utils import get_column_letter

    st.markdown("### 🛡️ Model Integrity Agent")
    st.markdown(
        "Audit confidential financial models with enterprise-grade privacy. Upload an Excel model to check for common errors, hard-coded values, and inconsistencies."
    )

    # --- AGENT CONFIG (Fetched from secrets for Azure) ---
    try:
        openai_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        openai_key = os.environ.get("AZURE_OPENAI_KEY")
        openai_deployment_name = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
    except KeyError as e:
        st.error(f"Configuration error: Missing Azure secret: {e}. Please check your secrets.toml file.")
        st.stop()

    # --- LOCAL HELPER FUNCTIONS ---
    def generate_report_html_from_markdown(analysis_results: dict) -> str:
        """
        Converts a dictionary of markdown analysis into a complete, styled HTML string.
        This helper is self-contained within the Model Integrity Agent.
        """
        report_title = "Financial Model Integrity Report"
        styles = """
        <style>
            .analysis-container { font-family: 'Poppins', sans-serif; border: 1px solid #e0e0e0; border-radius: 8px; padding: 25px; background-color: #f9fafb; margin: 20px; }
            .analysis-container h1 { font-size: 1.8em; font-weight: 700; color: #00416A; margin-top: 0; padding-bottom: 15px; border-bottom: 3px solid #00416A; }
            .analysis-container h2 { font-size: 1.5em; font-weight: 600; color: #00416A; border-bottom: 2px solid #e6f1f6; padding-bottom: 10px; margin-top: 30px; margin-bottom: 20px; }
            .analysis-container h3 { font-size: 1.2em; font-weight: 600; color: #1e1e1e; margin-top: 25px; margin-bottom: 10px; }
            .analysis-container p { margin-bottom: 1em; line-height: 1.6; color: #333; }
            .analysis-container ul, .analysis-container ol { list-style-position: outside; padding-left: 20px; margin-top: 1em; margin-bottom: 1em; }
            .analysis-container li { margin-bottom: 0.75em; line-height: 1.6; }
            .analysis-container table { width: 100%; border-collapse: collapse; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
            .analysis-container th, .analysis-container td { border: 1px solid #ddd; padding: 12px 15px; text-align: left; }
            .analysis-container th { background-color: #e6f1f6; font-weight: 600; }
            .analysis-container tr:nth-of-type(even) { background-color: #fdfdfd; }
        </style>
        """
        
        full_html_body = f"<h1>{html.escape(report_title)}</h1>"
        for title, markdown_content in analysis_results.items():
            full_html_body += f"<h2>{html.escape(title)}</h2>"
            html_from_md = markdown.markdown(markdown_content, extensions=['tables'])
            processed_html = re.sub(r"<h2>(.*?)</h2>", r"<h3>\1</h3>", html_from_md)
            full_html_body += processed_html
        
        content_div = f"<div class='analysis-container'>{full_html_body}</div>"
        
        return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>{html.escape(report_title)}</title>
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
        {styles}</head><body>{content_div}</body></html>"""

    def audit_excel_model(file_bytes: bytes) -> dict:
        """
        Parses an Excel workbook and checks for common modeling errors.
        Returns a dictionary of findings.
        """
        findings = {
            "hard_codes": [],
            "error_cells": [],
            "external_links": [],
            "summary": {}
        }
        try:
            workbook = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=False)
            findings["summary"]["sheets"] = workbook.sheetnames
            findings["summary"]["total_sheets"] = len(workbook.sheetnames)

            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                for row in sheet.iter_rows(min_row=2, max_row=sheet.max_row, min_col=2, max_col=sheet.max_column):
                    for cell in row:
                        if cell.value is not None and cell.data_type == 'n' and not str(cell.value).startswith('='):
                            left_cell = sheet.cell(row=cell.row, column=cell.column - 1) if cell.column > 1 else None
                            if left_cell and left_cell.data_type == 'f':
                                findings["hard_codes"].append(
                                    f"Sheet '{sheet_name}', Cell {cell.coordinate}: Contains a hard-coded number ({cell.value}) next to a cell with a formula."
                                )
                        if cell.data_type == 'e':
                             findings["error_cells"].append(
                                f"Sheet '{sheet_name}', Cell {cell.coordinate}: Contains an error value: {cell.value}"
                            )
                if hasattr(sheet, 'external_links'):
                    for link in sheet.external_links:
                        findings["external_links"].append(f"Sheet '{sheet_name}' contains an external link to: {link.Target}")

            return findings
        except Exception as e:
            st.warning(f"Could not fully audit the Excel file. Error: {e}")
            return findings

    def analyze_findings_with_azure_openai(findings: dict) -> str:
        """
        Sends the structured findings to Azure OpenAI for a narrative report.
        """
        prompt = f"""
        You are an expert in financial modeling and auditing from a top-tier investment bank.
        An automated script has analyzed an Excel financial model and found the following potential issues.
        Your task is to synthesize these raw findings into a professional, well-structured audit report in MARKDOWN format.

        **CRITICAL INSTRUCTIONS:**
        1.  Start with a high-level executive summary based on the number and type of findings.
        2.  Group the findings into logical sections: "High-Severity Issues (e.g., Error Cells)", "Medium-Severity Issues (e.g., Hard-Codes in Calculation Blocks)", and "Areas for Review (e.g., External Links)".
        3.  For each finding, explain the potential risk (e.g., "Hard-coded values can lead to incorrect calculations if assumptions change and are a common source of model errors.").
        4.  Conclude with a summary and a clear recommendation for a manual review of the identified areas.
        5.  If a category (like 'error_cells') is empty, state that "No issues of this type were detected."

        **AUTOMATED FINDINGS:**
        ---
        {str(findings)}
        ---
        """
        try:
            client = AzureOpenAI(
                api_key=openai_key, api_version="2024-02-01", azure_endpoint=openai_endpoint
            )
            response = client.chat.completions.create(
                model=openai_deployment_name,
                messages=[
                    {"role": "system", "content": "You are a financial modeling audit expert."},
                    {"role": "user", "content": prompt},
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"## Error\n\n**Error during Azure OpenAI analysis:** {e}"

    # --- UI & WORKFLOW ---
    st.subheader("1. Upload Confidential Financial Model")
    uploaded_file = st.file_uploader(
        "Upload an Excel Model (.xlsx)",
        type=["xlsx"],
        accept_multiple_files=False,
        key="model_integrity_uploader",
    )

    if uploaded_file:
        if st.button("Audit Model", type="primary", use_container_width=True):
            with st.spinner("Auditing model structure and generating report..."):
                file_bytes = uploaded_file.getvalue()
                findings = audit_excel_model(file_bytes)
                analysis_report = analyze_findings_with_azure_openai(findings)
                st.session_state.model_integrity_results = {
                    "Model Audit Report": analysis_report
                }

    if "model_integrity_results" in st.session_state:
        st.success("✅ Model audit complete!")
        st.markdown("---")
        st.subheader("2. Download Report")
        
        full_html_for_download = generate_report_html_from_markdown(
            st.session_state.model_integrity_results
        )
        
        st.download_button(
            label="📥 Download Audit Report as HTML",
            data=full_html_for_download,
            file_name="model_integrity_report.html",
            mime="text/html",
            use_container_width=True
        )



# ==============================================================================
# 11. Agent Sentinel (Proactive Monitoring) - NEW
# ==============================================================================

def agent_sentinel_app():
    """
    An agent to proactively monitor a portfolio of companies for significant events,
    triggered on-demand by the user.
    """
    # --- Local imports ---
    import streamlit as st
    import requests, html, markdown, re
    from openai import AzureOpenAI
    from datetime import datetime, timedelta

    st.markdown("### 📡 Agent Sentinel")
    st.markdown(
        "Run an on-demand check on your portfolio for recent significant events. Enter company tickers to fetch the latest news and SEC filings, summarized by AI."
    )
    st.info("Note: This is an on-demand snapshot, not a continuous background service. Run it anytime to get the latest updates.", icon="ℹ️")

    # --- AGENT CONFIG (Fetched from secrets) ---
    try:
        FMP_API_KEY = os.environ.get("FMP_API_KEY")
        openai_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        openai_key = os.environ.get("AZURE_OPENAI_KEY")
        openai_deployment_name = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
    except KeyError as e:
        st.error(f"Configuration error: Missing a required secret: {e}. Please check your secrets.toml file.")
        st.stop()

    # --- LOCAL HELPER FUNCTIONS ---
    def generate_report_html_from_markdown(analysis_results: dict) -> str:
        """
        Converts a dictionary of markdown analysis into a complete, styled HTML string.
        This helper is self-contained within the Agent Sentinel function.
        """
        report_title = "Portfolio Monitoring Briefing"
        styles = """
        <style>
            .analysis-container { font-family: 'Poppins', sans-serif; border: 1px solid #e0e0e0; border-radius: 8px; padding: 25px; background-color: #f9fafb; margin: 20px; }
            .analysis-container h1 { font-size: 1.8em; font-weight: 700; color: #00416A; margin-top: 0; padding-bottom: 15px; border-bottom: 3px solid #00416A; }
            .analysis-container h2 { font-size: 1.5em; font-weight: 600; color: #00416A; border-bottom: 2px solid #e6f1f6; padding-bottom: 10px; margin-top: 30px; margin-bottom: 20px; }
            .analysis-container h3 { font-size: 1.2em; font-weight: 600; color: #1e1e1e; margin-top: 25px; margin-bottom: 10px; }
            .analysis-container p { margin-bottom: 1em; line-height: 1.6; color: #333; }
            .analysis-container ul, .analysis-container ol { list-style-position: outside; padding-left: 20px; margin-top: 1em; margin-bottom: 1em; }
            .analysis-container li { margin-bottom: 0.75em; line-height: 1.6; }
            .analysis-container table { width: 100%; border-collapse: collapse; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
            .analysis-container th, .analysis-container td { border: 1px solid #ddd; padding: 12px 15px; text-align: left; }
            .analysis-container th { background-color: #e6f1f6; font-weight: 600; }
            .analysis-container tr:nth-of-type(even) { background-color: #fdfdfd; }
        </style>
        """
        
        full_html_body = f"<h1>{html.escape(report_title)}</h1>"
        for title, markdown_content in analysis_results.items():
            full_html_body += f"<h2>{html.escape(title)}</h2>"
            html_from_md = markdown.markdown(markdown_content, extensions=['tables'])
            processed_html = re.sub(r"<h2>(.*?)</h2>", r"<h3>\1</h3>", html_from_md)
            full_html_body += processed_html
        
        content_div = f"<div class='analysis-container'>{full_html_body}</div>"
        
        return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>{html.escape(report_title)}</title>
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
        {styles}</head><body>{content_div}</body></html>"""

    def fetch_fmp_data(tickers_list: list) -> dict:
        """
        Fetches latest news and 8-K filings for a list of tickers from FMP.
        """
        company_data = {ticker: {"news": [], "filings": []} for ticker in tickers_list}
        today = datetime.now()
        ninety_days_ago = today - timedelta(days=90)
        date_to = today.strftime('%Y-%m-%d')
        date_from = ninety_days_ago.strftime('%Y-%m-%d')

        try:
            tickers_str = ",".join(tickers_list)
            news_url = f"https://financialmodelingprep.com/api/v3/stock_news?tickers={tickers_str}&limit=50&apikey={FMP_API_KEY}"
            news_response = requests.get(news_url).json()
            if news_response and isinstance(news_response, list):
                for item in news_response:
                    if item.get('symbol') in company_data:
                        company_data[item['symbol']]['news'].append(f"- {item.get('title')} (Source: {item.get('site')}, Published: {item.get('publishedDate')})")
            
            for ticker in tickers_list:
                filings_url = f"https://financialmodelingprep.com/api/v3/sec_filings/{ticker}?type=8-K&from={date_from}&to={date_to}&limit=5&apikey={FMP_API_KEY}"
                filings_response = requests.get(filings_url).json()
                if filings_response and isinstance(filings_response, list):
                    for item in filings_response:
                        company_data[ticker]['filings'].append(f"- 8-K Filing from {item.get('fillingDate')}: [Link]({item.get('finalLink')})")
            return company_data
        except Exception as e:
            st.error(f"Error fetching data from FMP API: {e}")
            return {}

    def summarize_events_with_azure_openai(data: dict) -> str:
        """
        Sends the collected data to Azure OpenAI for a summary report.
        """
        prompt = f"""
        You are a senior analyst on an investment team. You have been given the latest news and SEC filings for a portfolio of companies.
        Your task is to create a concise "Portfolio Monitoring Briefing" in MARKDOWN format.

        **CRITICAL INSTRUCTIONS:**
        1.  Start with a "Portfolio Executive Summary" that highlights the single most important event or trend across the entire portfolio.
        2.  Then, for each company, create a section with its ticker as the heading (e.g., `## AAPL`).
        3.  Under each company, create two subheadings: "Significant News" and "Recent Filings".
        4.  For each section, write a 2-3 sentence summary of the most significant developments. Do not just list the headlines. Synthesize and explain the potential impact.
        5.  If a company has no new data in a category, state "No significant news found." or "No recent 8-K filings found."

        **RAW DATA FEED:**
        ---
        {str(data)}
        ---
        """
        try:
            client = AzureOpenAI(
                api_key=openai_key, api_version="2024-02-01", azure_endpoint=openai_endpoint
            )
            response = client.chat.completions.create(
                model=openai_deployment_name,
                messages=[
                    {"role": "system", "content": "You are a senior investment analyst responsible for portfolio monitoring."},
                    {"role": "user", "content": prompt},
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"## Error\n\n**Error during Azure OpenAI analysis:** {e}"

    # --- UI & WORKFLOW ---
    st.subheader("1. Define Portfolio")
    tickers_input = st.text_input("Enter Company Tickers (comma-separated)", "AAPL, MSFT, NVDA", help="e.g., GOOGL, AMZN, JPM")

    if st.button("Run Monitoring Check", type="primary", use_container_width=True):
        tickers = [ticker.strip().upper() for ticker in tickers_input.split(',') if ticker.strip()]
        if not tickers:
            st.warning("Please enter at least one ticker.")
        else:
            with st.spinner(f"Fetching latest data for {', '.join(tickers)}..."):
                raw_data = fetch_fmp_data(tickers)
                if not raw_data:
                    st.error("Failed to fetch any data. Please check tickers and API keys.")
                else:
                    summary_report = summarize_events_with_azure_openai(raw_data)
                    st.session_state.sentinel_results = {
                        "Portfolio Monitoring Briefing": summary_report
                    }

    if "sentinel_results" in st.session_state:
        st.success("✅ Monitoring check complete!")
        st.markdown("---")
        st.subheader("2. Download Briefing")

        full_html_for_download = generate_report_html_from_markdown(
            st.session_state.sentinel_results
        )
        
        st.download_button(
            label="📥 Download Briefing as HTML",
            data=full_html_for_download,
            file_name="portfolio_monitoring_briefing.html",
            mime="text/html",
            use_container_width=True
        )



# ==============================================================================
# 12. Agent Sentinel (Proactive Monitoring) - NEW
# ==============================================================================

def investment_pipeline_agent():
    """
    A robust, multi-stage, AI-powered investment research pipeline.
    It uses a "Search-Then-Validate" workflow with robust country matching.
    """
    import json
    import pandas as pd
    import requests
    import markdown
    import html
    import re
    from collections import Counter
    from openai import AzureOpenAI
    import streamlit as st
    

    # --- ADD THIS DICTIONARY ---
    COUNTRY_CURRENCY_MAP = {
        "USA": "USD", "India": "INR", "Germany": "EUR", "France": "EUR", 
        "Italy": "EUR", "Spain": "EUR", "UK": "GBP", "China": "CNY", 
        "Hong Kong": "HKD", "Taiwan": "TWD", "South Africa": "ZAR", 
        "Brazil": "BRL", "Chile": "CLP", "Mexico": "MXN"
    }

    st.markdown("### 💡 Agent IdeaGen")
    st.markdown("Define a theme. The agent will brainstorm ideas, find the correct tickers, validate them, and perform a deep-dive analysis.")
    
    # --- 1. API AND CLIENT SETUP ---
    MAX_COMPANIES_TO_ANALYZE = 50
    try:
        eodhd_api_key = os.environ.get("EODHD_API_KEY")
        client = AzureOpenAI(api_key=os.environ.get("AZURE_OPENAI_KEY"), api_version="2024-02-01", azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"))
        llm_deployment_name = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
    except Exception as e:
        st.error(f"Could not initialize secrets or clients. Error: {e}")
        return
        
    # --- 2. CORE FUNCTIONS (WITH CORRECTED SEARCH LOGIC) ---

    def get_theme_sectors(theme: str, client: AzureOpenAI, llm_deployment_name: str) -> list:
        st.info(f"**(LIVE) Step 1A: AI is identifying relevant sectors for '{theme}'...")
        
        # --- FIX: Make the prompt more specific to constrain the AI's choices ---
        prompt = f"""
        You are a market analyst specializing in GICS sectors. For the investment theme "{theme}", identify the 1-3 GICS sectors that companies who PRIMARILY DEVELOP AND SELL these solutions belong to. 
        
        Do NOT include sectors that only USE the technology. For example, for 'AI in healthcare', the correct sector is 'Information Technology', not 'Health Care'.
        
        Return a JSON list of strings. Example: {{"sectors": ["Information Technology", "Communication Services"]}}
        """
        try:
            response = client.chat.completions.create(model=llm_deployment_name, messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"}, temperature=0.0)
            sectors = json.loads(response.choices[0].message.content).get('sectors', [])
            st.success(f"Identified relevant sectors: **{', '.join(sectors)}**")
            return sectors
        except Exception: return None

    def get_company_ideas(theme: str, sectors: list, country: str, client: AzureOpenAI, llm_deployment_name: str) -> list:
        st.info(f"**(LIVE) Step 1B: AI is brainstorming companies for '{theme}'...**")
        
        # --- FIX: Add the selected country and stronger relevance instructions to the prompt ---
        prompt = f"""
        For the investment theme "{theme}" within the sectors '{', '.join(sectors)}', brainstorm up to 20 public companies primarily listed in **{country}** whose **core business is directly related to this theme.**

        CRITICAL: Do not include companies that are merely consumers or beneficiaries of the theme; focus on the enablers and providers.

        Return ONLY a comma-separated list of their most common ticker symbols on their primary exchange.
        For example, for Germany, use tickers from the XETRA exchange where possible (e.g., SAP.DE, DTE.DE).
        """
        try:
            response = client.chat.completions.create(model=llm_deployment_name, messages=[{"role": "user", "content": prompt}], temperature=0.1)
            tickers = [t.strip() for t in response.choices[0].message.content.split(',') if t.strip()]
            st.info(f"Agent suggested tickers: {tickers}")
            return tickers
        except Exception: return []

    def find_instrument_data(ticker: str, country_code: str, api_key: str) -> dict:
        """Uses the EODHD Search API to find the correct exchange for a ticker."""
        try:
            url = f"https://eodhistoricaldata.com/api/search/{ticker}?api_token={api_key}&fmt=json"
            response = requests.get(url, timeout=10)
            if response.status_code != 200: return None
            
            search_results = response.json()
            for result in search_results:
                # --- FIX 3: The comparison now correctly checks "USA" against the API's "USA". ---
                if result.get('Country') == country_code:
                    return result
            return None
        except Exception:
            return None

    def validate_company_with_reason(instrument: dict, filters: dict, api_key: str, mkt_cap_filter_local: float, theme_sectors: list) -> (str, dict):
        ticker, exchange = instrument['Code'], instrument['Exchange']
        try:
            url = f"https://eodhistoricaldata.com/api/fundamentals/{ticker}.{exchange}?api_token={api_key}"
            response = requests.get(url, timeout=10)
            if response.status_code != 200: return "INCOMPLETE_DATA", {"name": instrument.get('Name')}
            
            data = response.json()
            general = data.get('General', {}); highlights = data.get('Highlights', {})
            name = general.get('Name', ticker)
            
            # --- CHANGE 2: ADD THIS NEW VALIDATION BLOCK ---
            sector = general.get('Sector')
            if sector not in theme_sectors:
                return "FAIL_SECTOR", {"name": name, "value": sector}
            # --- END OF NEW BLOCK ---

            market_cap_local = highlights.get('MarketCapitalization')

            if not all([name, market_cap_local is not None]):
                return "INCOMPLETE_DATA", {"name": name}

            # --- FINAL FIX: Compare local market cap with the pre-calculated local filter ---
            if market_cap_local < mkt_cap_filter_local:
                return "FAIL_MCAP", {"name": name, "value": market_cap_local}
            
            dividend_yield = highlights.get('DividendYield') or 0.0
            if dividend_yield < (filters["dividend_yield_min"] / 100):
                return "FAIL_DIVIDEND", {"name": name, "value": dividend_yield}

            return "PASS", { 
                "code": ticker, 
                "name": name, 
                "exchange": exchange,
                "sector": general.get('Sector', 'N/A'),
                # Return the local market cap for later conversion during reporting
                "market_capitalization_local": market_cap_local, 
                "dividend_yield": dividend_yield 
            }
        except (requests.RequestException, json.JSONDecodeError):
            return "ERROR", {"name": instrument.get('Name')}


    def get_exchange_rate(from_currency: str, to_currency: str, api_key: str, cache: dict) -> float:
        """
        Fetches the exchange rate to convert from_currency to to_currency,
        using a cache to avoid redundant API calls.
        """
        # If currencies are the same, the rate is 1.
        if from_currency == to_currency:
            return 1.0

        # To convert from a currency (e.g., INR) to USD, we need the value of 1 USD in INR.
        # The standard FOREX pair for this is USDINR.
        pair = f"{to_currency.upper()}{from_currency.upper()}"
        
        if pair in cache:
            return cache[pair]
        
        try:
            # This is the correct EODHD endpoint for the latest daily FOREX rate.
            url = f"https://eodhistoricaldata.com/api/eod/{pair}.FOREX?api_token={api_key}&fmt=json&period=d&limit=1"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data and isinstance(data, list):
                    # The 'close' price is the exchange rate. For USDINR, this is ~88.
                    rate = data[0].get('close')
                    if rate and rate > 0:
                        cache[pair] = rate
                        return rate
            
            # If the direct pair fails (e.g., a less common currency), try the inverse.
            inverse_pair = f"{from_currency.upper()}{to_currency.upper()}"
            url = f"https://eodhistoricaldata.com/api/eod/{inverse_pair}.FOREX?api_token={api_key}&fmt=json&period=d&limit=1"
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                data = response.json()
                if data and isinstance(data, list):
                    # For an inverse pair like INRUSD, the rate is ~0.011. We return 1/rate.
                    inverse_rate = data[0].get('close')
                    if inverse_rate and inverse_rate > 0:
                        rate = 1 / inverse_rate
                        cache[pair] = rate # Cache the correct, calculated rate
                        return rate

            return 1.0 # Fallback if both attempts fail
        except Exception:
            return 1.0 # Fallback on any error




    # --- (All other analysis, enrichment, and reporting functions are unchanged) ---
    def enrich_company_data_eodhd(ticker_code: str, api_key: str) -> dict: # ... unchanged
        st.info(f"**(LIVE) Enriching {ticker_code}...**")
        base_url = f"https://eodhistoricaldata.com/api/fundamentals/{ticker_code}"; params = {"api_token": api_key}
        try:
            response = requests.get(base_url, params=params, timeout=15); response.raise_for_status(); data = response.json()
            description = data.get('General', {}).get('Description', 'No description available.')
            news = aggregate_qualitative_data_eodhd(ticker_code, api_key)
            return {"description": description, "qualitative_corpus": f"Company Description:\n{description}\n\n---\n\nRecent News:\n{news}"}
        except Exception: return {"description": "Data enrichment failed.", "qualitative_corpus": "Could not fetch qualitative data."}

    def aggregate_qualitative_data_eodhd(ticker_code: str, api_key: str) -> str: # ... unchanged
        base_url = "https://eodhistoricaldata.com/api/news"; ticker_only = ticker_code.split('.')[0]; params = {"api_token": api_key, "t": ticker_only, "limit": 50}
        try:
            response = requests.get(base_url, params=params, timeout=15); response.raise_for_status(); news_data = response.json()
            if news_data and isinstance(news_data, list): return "\n".join([f"- {item['title']} ({item['date']})" for item in news_data])
            return "No recent news found."
        except Exception: return "Could not fetch recent news."

    def run_ai_qualitative_analysis(company_name: str, text_corpus: str, theme: str, client: AzureOpenAI, llm_deployment_name: str) -> dict: # ... unchanged
        st.info(f"**(LIVE) Running AI Qualitative Analysis for {company_name}...**")
        prompt = f"""Analyze '{company_name}' for the theme '{theme}' using the text below. Return a JSON with keys "theme_analysis", "moat_analysis", "risk_analysis". For "risk_analysis", provide a "top_risks" list of objects, each with "risk" and "description". TEXT: --- {text_corpus[:25000]} ---"""
        try:
            response = client.chat.completions.create(model=llm_deployment_name, messages=[{"role": "system", "content": "You are an equity analyst that only outputs JSON."}, {"role": "user", "content": prompt}], response_format={"type": "json_object"})
            return json.loads(response.choices[0].message.content)
        except Exception as e: st.error(f"Error in AI Analysis: {e}"); return {}

    def synthesize_dossier(quant_data: pd.Series, qual_analysis: dict, theme: str, rate_usd_to_local: float) -> dict:
        st.info(f"**(LIVE) Synthesizing Dossier for {quant_data.get('name', 'N/A')}...")

        # --- FINAL FIX: Convert local market cap to USD for reporting ---
        market_cap_local = quant_data.get('market_capitalization_local', 0)
        # Handle the case where the rate might be 0 to avoid division errors
        market_cap_usd = market_cap_local / rate_usd_to_local if rate_usd_to_local else 0
        

        def format_ai_analysis_to_markdown(data):
            if not isinstance(data, dict): return str(data)
            parts = [v for k, v in data.items() if isinstance(v, str)]; return "\n".join(parts) if parts else "No analysis available."
        def format_risks(data):
            risks = data.get('top_risks', []) if isinstance(data, dict) else [];
            if not risks: return "No specific risks identified."
            return "\n".join(f"* **{r.get('risk', 'N/A')}**: {r.get('description', 'N/A')}" for r in risks)
        quant_md = f"""| Metric | Value |\n|---|---|\n| Market Cap (USD) | ${quant_data.get('market_capitalization', 0) / 1e9:,.1f}B |\n| Dividend Yield | {quant_data.get('dividend_yield', 0):.2%} |"""
        return {
                "dossier_title": f"{quant_data.get('name', 'N/A')} ({quant_data.get('code', 'N/A')}.{quant_data.get('exchange', '')})",
                "Quantitative Snapshot": quant_md,
                "Thematic Alignment & Justification": format_ai_analysis_to_markdown(qual_analysis.get('theme_analysis')),
                "Competitive Moat & Pricing Power": format_ai_analysis_to_markdown(qual_analysis.get('moat_analysis')),
                "Key Risks Identified": format_risks(qual_analysis.get('risk_analysis'))
        }
    def generate_final_html_report(dossier_list: list, theme: str) -> str:
        safe_theme = html.escape(theme or "...")
        styles = """<style>body{font-family:sans-serif;margin:20px;background-color:#f9fafb;color:#1f2937}.container{max-width:1200px;margin:auto}.report-header h1{font-size:2.2em;color:#111827;border-bottom:2px solid #d1d5db;padding-bottom:10px}.dossier{background-color:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:30px;margin-bottom:30px;box-shadow:0 4px 6px rgba(0,0,0,0.05)}.dossier h2{font-size:1.4em;border-bottom:1px solid #e5e7eb;padding-bottom:8px;margin-top:25px}.dossier table{width:100%;border-collapse:collapse;margin-top:15px}.dossier th,td{padding:10px 12px;border:1px solid #d1d5db;text-align:left}</style>"""
        
        html_body = f"<div class='report-header'><h1>Investment Idea Report</h1><h2>Theme: {safe_theme}</h2></div>"
        
        for d in dossier_list:
            html_body += f"<div class='dossier'><h1>{html.escape(d.get('dossier_title', ''))}</h1>"
            
            for s in ["Quantitative Snapshot", "Thematic Alignment & Justification", "Competitive Moat & Pricing Power", "Key Risks Identified"]:
                if s in d:
                    html_body += f"<h2>{html.escape(s)}</h2>" + markdown.markdown(str(d[s]), extensions=['tables'])
            
            # --- FIX: Close the 'dossier' div before the loop moves to the next company ---
            html_body += "</div>"
            
        return f"<!DOCTYPE html><html><head><title>IdeaGen Report</title>{styles}</head><body><div class='container'>{html_body}</div></body></html>"

    def risk_and_sizing_agent(dossier: dict, client: AzureOpenAI, llm_deployment_name: str) -> dict: # ... unchanged
        st.info("**(LIVE) Agent 3/3: Risk & Position Sizing Agent is evaluating risk profile...**")
        prompt = f"""Analyze the dossier. Recommend a position size (1-10%). Return JSON with "position_size_recommendation" and "rationale". DOSSIER: {json.dumps(dossier)[:10000]}"""
        try:
            response = client.chat.completions.create(model=llm_deployment_name, messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"})
            return json.loads(response.choices[0].message.content)
        except Exception as e: return {"error": f"Risk analysis failed: {e}"}

    # --- 4. STREAMLIT UI AND ORCHESTRATION ---
    st.subheader("Step 1: Define Your Investment Theme")
    qualitative_theme = st.text_area("**Describe the Qualitative Theme**", "Companies leading the artificial intelligence revolution in enterprise software.", height=75)
    st.subheader("Step 2: Define Validation Criteria")

    # --- FIX 1: Remove the COUNTRY_MAP. Use a simple list of codes that match the EODHD API output. ---
    country_options = [
    "Brazil", "Chile", "China", "France", "Germany", "Hong Kong", "India",
    "Italy", "Mexico", "South Africa", "Spain", "Taiwan", "UK", "USA"
    ]
    selected_country_code = st.selectbox("Target Country", options=country_options, index=country_options.index("USA"))

    col1, col2 = st.columns(2)
    with col1: mkt_cap_min = st.slider("Min Market Cap (Million USD)", 100.0, 500000.0, 10000.0, 100.0)
    with col2: dividend_yield_min = st.slider("Min Dividend Yield (%)", 0.0, 10.0, 1.2, 0.1)

    st.subheader("Step 3: Generate and Analyze Ideas")
    if st.button("🚀 Generate, Validate, and Analyze", type="primary"):
        if not qualitative_theme: st.warning("Please describe your theme."); return
        with st.spinner("Running full investment pipeline..."):
            theme_sectors = get_theme_sectors(qualitative_theme, client, llm_deployment_name)
            if not theme_sectors: st.error("Could not identify sectors for this theme."); return
            
            company_tickers = get_company_ideas(qualitative_theme, theme_sectors, selected_country_code, client, llm_deployment_name)
            if not company_tickers: st.error("AI brainstorming returned no ideas."); return

            user_filters = {"market_cap_min": mkt_cap_min, "dividend_yield_min": dividend_yield_min}

            # --- NEW LOGIC: PRE-CALCULATE LOCAL CURRENCY FILTER ---
            local_currency = COUNTRY_CURRENCY_MAP.get(selected_country_code, "USD")
            exchange_rate_cache = {}
            # Get the value of 1 USD in the local currency (e.g., 88 for USDINR)
            rate_usd_to_local = get_exchange_rate("USD", local_currency, eodhd_api_key, exchange_rate_cache)
            
            # Convert the USD filter (in millions) to the local currency value
            mkt_cap_filter_local = (user_filters["market_cap_min"] * 1e6) * rate_usd_to_local
            
            validated_companies = []; failure_reasons = []
            progress = st.progress(0, text=f"Finding & Validating Tickers in {local_currency}...")
            
            for i, ticker in enumerate(company_tickers):
                instrument = find_instrument_data(ticker, selected_country_code, eodhd_api_key)
                if not instrument:
                    failure_reasons.append(("NOT_FOUND", {"name": ticker}))
                else:
                    # Pass the pre-calculated local filter to the validation function
                    status, result = validate_company_with_reason(instrument, user_filters, eodhd_api_key, mkt_cap_filter_local, theme_sectors)
                    if status == 'PASS': validated_companies.append(result)
                    else: failure_reasons.append((status, result))
                progress.progress((i + 1) / len(company_tickers))
            progress.empty()

            if failure_reasons:
                st.subheader("Validation Summary")
                failure_counts = Counter(code for code, data in failure_reasons)
                summary_md = "| Rejection Reason | Count |\n|---|---|\n"
                summary_md += f"| Did not meet dividend yield | {failure_counts.get('FAIL_DIVIDEND', 0)} |\n"
                summary_md += f"| Did not meet market cap | {failure_counts.get('FAIL_MCAP', 0)} |\n"
                summary_md += f"| Sector did not match | {failure_counts.get('FAIL_SECTOR', 0)} |\n"
                summary_md += f"| Sector did not match theme | {failure_counts.get('FAIL_SECTOR', 0)} |\n"
                summary_md += f"| Ticker not found or incomplete data | {failure_counts.get('NOT_FOUND', 0) + failure_counts.get('INCOMPLETE_DATA', 0) + failure_counts.get('ERROR', 0)} |\n"
                st.markdown(summary_md)

            if not validated_companies: st.warning("No companies met all your criteria."); return
            
            analysis_df = pd.DataFrame(validated_companies)
            st.success(f"Validated {len(analysis_df)} companies. Performing deep analysis...")
            # Display local market cap in the initial table for clarity
            st.dataframe(analysis_df[['code', 'name', 'exchange', 'market_capitalization_local']], hide_index=True, use_container_width=True)
            
            all_dossiers = []
            for i, company_row in analysis_df.iterrows():
                ticker_code = f"{company_row['code']}.{company_row['exchange']}"
                enrichment_data = enrich_company_data_eodhd(ticker_code, eodhd_api_key)
                if "failed" in enrichment_data.get("description", ""): continue
                
                qual_analysis = run_ai_qualitative_analysis(company_row['name'], enrichment_data['qualitative_corpus'], qualitative_theme, client, llm_deployment_name)
                if not qual_analysis: continue
                
                full_data = company_row.copy()
                full_data.update(pd.Series(enrichment_data))
                
                # Pass the exchange rate to the dossier function for reporting in USD
                dossier = synthesize_dossier(full_data, qual_analysis, qualitative_theme, rate_usd_to_local)
                
                risk_analysis = risk_and_sizing_agent(dossier, client, llm_deployment_name)
                dossier['risk_analysis'] = risk_analysis
                all_dossiers.append(dossier)

            if all_dossiers:
                final_html_report = generate_final_html_report(all_dossiers, qualitative_theme)
                safe_filename = re.sub(r'(?u)[^-\w.]', '', qualitative_theme[:40].strip().replace(' ', '_'))
                st.download_button(label="📥 Download Full HTML Report", data=final_html_report, file_name=f"IdeaGen_Report_{safe_filename}.html", mime="text/html")
            else:
                st.error("Could not generate a report for any of the validated companies.")


# ==============================================================================
# 14. Real-Time Risk & Compliance Sentinel (Workflow)
# ==============================================================================

def real_time_sentinel_app(user_id: str, client: AzureOpenAI):
    """
    A workflow that simulates a real-time risk and compliance monitoring system.
    """
    import json
    import pandas as pd
    import requests
    import markdown
    import html
    import re
    import streamlit as st
    from datetime import datetime, timedelta
    from azure.core.credentials import AzureKeyCredential
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.ai.documentintelligence.models import ContentFormat
    from openai import AzureOpenAI
    from st_supabase_connection import SupabaseConnection

    st.markdown("### 🚨 Real-Time Risk & Compliance Sentinel")
    st.markdown("This workflow simulates an automated sentinel that monitors for compliance issues and tail risks in your portfolio.")

    # --- HELPER FUNCTION: Get primary ticker from company name ---
    def get_primary_ticker_by_name(company_name: str) -> str:
        """
        Translates a company name to its primary listing ticker using a Supabase table.
        """
        import streamlit as st
        from st_supabase_connection import SupabaseConnection

        try:
            # Use st.connection to manage the Supabase connection
            supabase_client = st.connection("supabase", type=SupabaseConnection)

            # Corrected query using the standard Supabase client syntax
            # Change 'tickers' to 'symbol' in the select statement
            response = supabase_client.table("tickers") \
                .select("symbol, exchange") \
                .ilike("name", f"%{company_name}%") \
                .limit(1) \
                .execute()
            
            # The result is in the 'data' attribute of the response
            data = response.data
            
            if data and len(data) > 0:
                ticker_data = data[0]
                # Change 'tickers' to 'symbol' when getting the value
                ticker_code = ticker_data.get('symbol')
                exchange_code = ticker_data.get('exchange')
                
                if ticker_code and exchange_code:
                    return f"{ticker_code}.{exchange_code}"
                
            st.warning(f"No ticker found for '{company_name}' in the Supabase database.")
            return None

        except Exception as e:
            st.error(f"Failed to query Supabase for '{company_name}': {e}")
            return None
            
    # --- AGENT MOCK-UP: Compliance & Audit Agent ---
    def compliance_audit_mock(tickers: list, client: AzureOpenAI) -> dict:
        """
        Simulates checking for new MNPI or regulatory filings using EODHD.
        """
        st.info("Agent 1/2: Compliance & Audit Agent is checking for new MNPI and regulatory risks...")
        eodhd_api_key = os.environ.get("EODHD_API_KEY")
        
        compliance_findings = {}
        for ticker in tickers:
            compliance_findings[ticker] = {"news_mnpi": [], "filings": []}
            
            # Check for recent news using EODHD's global news API
            news_url = f"https://eodhd.com/api/news?s={ticker}&limit=5&api_token={eodhd_api_key}"
            try:
                news_data = requests.get(news_url).json()
                if news_data and isinstance(news_data, list):
                    for item in news_data:
                        # Use LLM to check for MNPI proxy
                        prompt = f"Does the following news headline for {ticker} contain any information that could be considered material non-public information (MNPI) for a public company? Answer 'Yes' or 'No' and provide a brief reason.\n\nHeadline: {item['title']}"
                        response = client.chat.completions.create(
                            model=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME"),
                            messages=[{"role": "user", "content": prompt}]
                        )
                        if "yes" in response.choices[0].message.content.lower():
                            compliance_findings[ticker]["news_mnpi"].append(f"**{item['title']}** - Potential MNPI: {response.choices[0].message.content}")

            except Exception as e:
                st.warning(f"Could not fetch news for {ticker}: {e}")
            
            # Note: EODHD does not have a global "8-K" equivalent. 
            # This is a placeholder for a more sophisticated global filings search.
            if ticker.endswith(".US"):
                # You could add specific logic for US filings here using a dedicated SEC API
                compliance_findings[ticker]["filings"].append("No recent 8-K filings found (using mock data).")
            else:
                compliance_findings[ticker]["filings"].append("Regulatory filings for non-US companies are not available in this mock-up.")

        return compliance_findings

    # --- AGENT MOCK-UP: Tail Risk Agent ---
    def tail_risk_mock(tickers: list) -> dict:
        """
        Simulates a tail risk analysis by looking for subtle risks in public data.
        This mock will perform a deep, targeted query against a mock database.
        """
        st.info("Agent 2/2: Tail Risk Agent is searching for subtle, unpriced risks...")
        
        # This is a proxy for searching large databases. We will use the LLM to find
        # subtle risks based on a deep, pre-defined search of a mock dataset.
        mock_data = {
            "TSLA.US": "A new regulatory filing reveals a potential class-action lawsuit related to autonomous vehicle software, which could result in a significant fine and recall, potentially un-pricing current valuation.",
            "JPM.US": "A new congressional bill proposes a cap on credit card interchange fees, which could significantly impact the bank's non-interest income stream, a key tailwind for the past several quarters.",
            "GOOGL.US": "An analyst report notes that Google's core search advertising business is facing a new and unexpected threat from a start-up leveraging a new generative AI model, potentially eroding market share over the next 12-18 months.",
            "SHEL.L": "The company faces new carbon tax litigation in the EU that could lead to significant financial penalties, which are not currently priced into the stock.",
            "NESN.SW": "A new investigation reveals potential supply chain issues for a key raw material, which could impact production and revenue forecasts in the coming quarter."
        }
        
        tail_risks = {}
        for ticker in tickers:
            if ticker in mock_data:
                tail_risks[ticker] = mock_data[ticker]
            else:
                tail_risks[ticker] = "No specific tail risks identified from recent data."

        return tail_risks

    # --- Main Workflow UI ---
    st.subheader("Step 1: Define Portfolio for Monitoring")
    portfolio_input = st.text_input("Enter Company Names or Tickers (comma-separated)", "Alphabet, TSLA, Nestlé", key="sentinel_input")

    if st.button("🚨 Run Sentinel Check", type="primary"):
        input_list = [item.strip() for item in portfolio_input.split(',') if item.strip()]
        if not input_list:
            st.warning("Please enter at least one company or ticker.")
            return
            
        tickers_list = []
        with st.spinner("Translating company names to primary tickers..."):
            for item in input_list:
                # Check if the input looks like a ticker (e.g., all uppercase with a period)
                if '.' in item.upper() and ' ' not in item:
                    tickers_list.append(item.upper())
                else:
                    # If it's not a clear ticker, try to look it up
                    primary_ticker = get_primary_ticker_by_name(item)
                    if primary_ticker:
                        tickers_list.append(primary_ticker)
                    else:
                        st.warning(f"Could not find a primary ticker for '{item}'. Skipping.")

        if not tickers_list:
            st.error("No valid tickers found to monitor. Please check your inputs.")
            return

        st.success(f"Monitoring the following tickers: {', '.join(tickers_list)}")

        with st.spinner("Running agents... This will take a few moments."):
            # 1. Compliance Check
            compliance_findings = compliance_audit_mock(tickers_list, client)
            
            # 2. Tail Risk Check
            tail_risk_findings = tail_risk_mock(tickers_list)
            
            st.success("Sentinel check complete.")
            
            # --- Final Report Display ---
            st.markdown("---")
            st.subheader("Sentinel Briefing")
            
            report_markdown = "## Portfolio Monitoring Report\n\n"
            report_markdown += "### 1. Compliance & Regulatory Watch\n"
            for ticker, findings in compliance_findings.items():
                report_markdown += f"#### {ticker}\n"
                report_markdown += "**Potential MNPI:**\n"
                if findings['news_mnpi']:
                    report_markdown += "\n".join(findings['news_mnpi']) + "\n"
                else:
                    report_markdown += "No significant news with potential MNPI found.\n"
                
                report_markdown += "**Recent Filings:**\n"
                if findings['filings']:
                    report_markdown += "\n".join(findings['filings']) + "\n"
                else:
                    report_markdown += "No recent 8-K filings found.\n"
            
            report_markdown += "\n### 2. Tail Risk & Market Sentinel\n"
            for ticker, risk in tail_risk_findings.items():
                report_markdown += f"#### {ticker}\n"
                report_markdown += f"**Tail Risk identified:** {risk}\n"
            
            st.markdown(report_markdown)

            # Allow download
            full_html = markdown.markdown(report_markdown, extensions=['tables'])
            st.download_button(
                label="📥 Download Full HTML Briefing",
                data=full_html,
                file_name=f"sentinel_briefing_{datetime.now().strftime('%Y%m%d')}.html",
                mime="text/html",
                use_container_width=True
            )


# ==============================================================================
# 15. MAIN APP ROUTER (CORRECTED AND COMPLETE)
# ==============================================================================

def main():
    """
    Main function to run the Streamlit app with authentication and routing.
    This version includes a corrected height calculation for the agent card component.
    """
    
    if not authentication_ui():
        st.stop()
    
    if not validate_session():
        st.warning("Your session has expired or another session has been started with your credentials.")
        st.info("Please log in again.")
        for key in ['logged_in', 'username', 'session_token']:
            if key in st.session_state:
                del st.session_state[key]
        st.button("Reload")
        st.stop()

    if 'st_supabase_connection' not in st.session_state:
        try:
            supabase_url = os.environ.get("SUPABASE_URL")
            supabase_key = os.environ.get("SUPABASE_KEY")
            st.session_state.st_supabase_connection = SupabaseConnection('supabase', supabase_url=supabase_url, supabase_key=supabase_key)
        except Exception as e:
            st.error(f"Error initializing Supabase connection: {e}")
            st.stop()

    # --- DYNAMIC AGENT VISIBILITY LOGIC ---
    
    # Load the config file
    with open("config.toml", "r") as f:
        config = toml.load(f)

    # Get the permissions from the loaded config
    permissions = config.get("user_permissions", {})
    current_user = st.session_state.get("username")
    visible_agents = permissions.get("__DEFAULT__", ["🏠 Welcome"]) 
    if current_user in permissions:
        visible_agents = permissions[current_user]

    # --- SIDEBAR DEFINITION ---
    with st.sidebar:
        st.title("ARANC'AI'")
        st.write(f"Welcome, **{st.session_state.username}**")
        st.markdown("---")
        app_mode = st.radio(
            "Choose a tool:",
            options=visible_agents,
            key="app_tool_choice"
        )
        st.markdown("---")
        if st.button("Logout"):
            conn.client.table("users").update({"active_session_token": None}).eq("email", st.session_state['username']).execute()
            for key in st.session_state.keys():
                del st.session_state[key]
            st.rerun()
        st.info("App powered by Aranca.")

    st.markdown("---")

    # --- ROUTER LOGIC ---
    if app_mode == "Real-Time Sentinel":
        real_time_sentinel_app(user_id=st.session_state.username, client=openai_client)
    elif app_mode == "Agent IdeaGen": 
        investment_pipeline_agent()
    elif app_mode == "Agent Credit":
        agent_credit_app_azure()
    elif app_mode == "Model Integrity Agent":
        model_integrity_agent_app()
    elif app_mode == "Agent Sentinel":
        agent_sentinel_app()
    elif app_mode == "Agent PE":
        pe_agent_app_azure()
    elif app_mode == "Agent Pre-IPO":
        investment_memo_app()
    elif app_mode == "DCF Ginny":
        dcf_agent_app(client=openai_client, FMP_API_KEY=FMP_API_KEY)
    elif app_mode == "Agent Special Situations":
        special_situations_app()
    elif app_mode == "ESG Analyzer":
        esg_analyzer_app()
    elif app_mode == "Agent Portfolio":
        portfolio_agent_app(user_id=st.session_state.username)
    elif app_mode == "Tariff Impact Tracker":
        tariff_impact_tracker_app(DEEPSEEK_API_KEY=DEEPSEEK_API_KEY, FMP_API_KEY=FMP_API_KEY, logo_base64_string=logo_base64)
    else: # This is the "🏠 Welcome" page
        st.markdown('<p class="welcome-subtitle">A unified platform for advanced financial analysis.</p>', unsafe_allow_html=True)
        st.info("👈 **Select an agent from the sidebar to begin.**")
        st.subheader("Available Agents")

        # Define all possible agent cards in a master list
        ALL_AGENT_DETAILS = [
            {"name": "Agent IdeaGen", "title": "💡 Agent IdeaGen", "description": "Discover new investment ideas by screening the market based on a specific theme or set of custom criteria."},
            {"name": "Agent PE", "title": "🔒 Agent PE", "description": "Analyze confidential IMs and teasers with enterprise-grade secured environment."},
            {"name": "DCF Ginny", "title": "📈 DCF Ginny", "description": "Generate a document-driven Discounted Cash Flow (DCF) analysis using public data or your own financials."},
            {"name": "ESG Analyzer", "title": "🌍 ESG Analyzer", "description": "Extract and compare key ESG metrics from sustainability reports to benchmark corporate performance."},
            {"name": "Agent Pre-IPO", "title": "📝 Agent Pre-IPO", "description": "Upload a DRHP/IPO PDF to automatically generate a detailed investment memo and perform Q&A."},
            {"name": "Agent Credit", "title": "🔒 Agent Credit", "description": "Analyze confidential credit agreements, indentures, and loan documents in a secure environment."},
            {"name": "Agent Portfolio", "title": "🗂️ Agent Portfolio", "description": "Index company-specific documents (10-Ks, earnings calls) and perform Q&A across your entire portfolio."},
            {"name": "Tariff Impact Tracker", "title": "📈 Tariff Impact Tracker", "description": "Analyze earnings calls or filings to extract mentions of tariffs and their financial impact."},
            {"name": "Agent Special Situations", "title": "📊 Agent Special Situations", "description": "Analyze events like M&A, spin-offs, and activist campaigns by uploading relevant documents to generate a summary memo."},
            {"name": "Agent Sentinel", "title": "📡 Agent Sentinel", "description": "Proactively monitor portfolio companies for key news, filings, and events."},
            {"name": "Model Integrity Agent", "title": "🛡️ Model Integrity Agent", "description": "Audit Excel financial models for errors, hard-codes, and inconsistencies."},
            {"name": "Real-Time Sentinel", "title": "🚨 Real-Time Sentinel", "description": "Provides a real-time warning system for compliance issues and tail risks."}
        ]

        # Filter the cards based on the user's permissions
        visible_agent_details = [agent for agent in ALL_AGENT_DETAILS if agent["name"] in visible_agents]

        # Generate the HTML for the visible cards
        card_html_list = []
        for agent in visible_agent_details:
            card_html_list.append(f"""
            <div class="agent-card" title="{agent['description']}">
                <div class="agent-title">{agent['title']}</div>
                <div class="agent-description">{agent['description']}</div>
            </div>
            """)

        # Combine the CSS and the dynamic HTML cards into a single block
        full_html = f"""
        <html>
            <head>
                <style>
                .agent-grid {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 20px;
                }}
                .agent-card {{
                    flex: 1 1 30%;
                    min-width: 300px;
                    display: flex;
                    flex-direction: column;
                    background-color: #f8f9fa;
                    border: 1px solid #e0e0e0;
                    border-radius: 8px;
                    padding: 20px;
                    transition: box-shadow 0.2s ease-in-out;
                    font-family: 'Poppins', sans-serif;
                }}
                .agent-card:hover {{
                    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                }}
                .agent-title {{
                    font-size: 1.1rem;
                    font-weight: 600;
                    color: #1e1e1e;
                    margin-bottom: 10px;
                }}
                .agent-description {{
                    font-size: 0.95rem;
                    color: #4a4a4a;
                    line-height: 1.5;
                }}
                </style>
            </head>
            <body>
                <div class="agent-grid">
                    {''.join(card_html_list)}
                </div>
            </body>
        </html>
        """
        
        # --- THE FIX IS HERE ---
        # We now use a more generous height of 220px per row to ensure
        # all content is visible without being cut off.
        num_rows = (len(visible_agent_details) + 2) // 3
        height_px = num_rows * 220  # Increased from 180 to 220 for more space
        
        components.html(full_html, height=height_px)

if __name__ == "__main__":
    main()