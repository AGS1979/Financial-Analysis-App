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

# --- Must be the first st.* command ---
st.set_page_config(
    page_title="Aranca Financial Suite",
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
    font-size: 2.0rem;
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
        <div class="aranca-title">Welcome to the Aranca Financial Suite</div>
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
                        st.session_state['logged_in'] = True
                        st.session_state['username'] = email
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

# --- Whitelist Management UI (for Admins) ---
# --- Whitelist Management UI (for Admins) ---
def whitelist_manager_ui():
    """Renders a UI in the sidebar for admins to manage the email whitelist in Supabase."""
    try:
        admin_password = st.secrets.get("app", {}).get("admin_password")
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
    DEEPSEEK_API_KEY = st.secrets.get("deepseek", {}).get("api_key")
    FMP_API_KEY = st.secrets.get("fmp", {}).get("api_key")
    OPENAI_API_KEY = st.secrets.get("openai", {}).get("api_key")
except (KeyError, FileNotFoundError):
    st.sidebar.error("API keys not found in Streamlit secrets.")
    st.stop()

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
openai_client = OpenAI(api_key=OPENAI_API_KEY)

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

def investment_memo_app():
    """
    Encapsulates the entire IPO Investment Memo Generator with Infographic and Q&A.
    This version is aligned with the advanced standalone module.
    """
    
    # --- CONFIGURATION ---
    DEEPSEEK_API_KEY = st.secrets.get("deepseek", {}).get("api_key")
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
            f"{text[:3000]}"
        )
        messages = [
            {"role": "system", "content": "You are an expert in IPO documents."},
            {"role": "user", "content": prompt}
        ]
        response = requests.post(DEEPSEEK_API_URL, headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}, json={"model": "deepseek-chat", "messages": messages})
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content'].strip()

    def generate_memo_sections(filtered_text, custom_notes=""):
        section_titles = [
            "1. IPO Offer Details", "2. Company Overview", "3. Industry Overview and Outlook",
            "4. Business Model", "5. Financial Highlights",
            "6. Guidance and Outlook on future financial performance",
            "7. Peer Comparison and Competitors", "8. Risks", "9. Investment Highlights"
        ]
        sections = {}
        for title in section_titles:
            prompt = (
                f"You are writing a professional pre-IPO investment memo section titled: {title[3:]}. "
                "Please generate ~500 words of clean, structured, analytical prose suitable for institutional investors. "
                "Do not mention this is a memo. Avoid starting with the section title, and avoid phrases like 'In this section'. "
                "Strictly avoid markdown (no asterisks, hashes, underscores). Use plain text only.\n\n"
            )
            if custom_notes:
                prompt += f"Focus on this angle: {custom_notes.strip()}\n\n"
            prompt += f"Relevant DRHP Text:\n{filtered_text[:16000]}"
            
            messages = [
                {"role": "system", "content": "You are an expert financial analyst."},
                {"role": "user", "content": prompt}
            ]
            response = requests.post(DEEPSEEK_API_URL, headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}, json={"model": "deepseek-chat", "messages": messages})
            response.raise_for_status()
            raw_content = response.json()['choices'][0]['message']['content']
            cleaned = clean_markdown(raw_content)
            # Additional cleaning to remove redundant titles
            cleaned = re.sub(rf"^{re.escape(title[3:])}[\s:—-]*", "", cleaned, flags=re.IGNORECASE | re.MULTILINE)
            sections[title] = cleaned.strip()
        return sections

    def save_sections_to_word(sections_dict, company_name="Company", output_dir="documents"):
        os.makedirs(output_dir, exist_ok=True)
        filename = f"{company_name.replace(' ', '_')}_PreIPO_Memo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
        full_path = os.path.join(output_dir, filename)
        
        doc = Document()
        style = doc.styles['Normal']
        style.font.name = 'Aptos Display'
        style.font.size = Pt(11)

        title_para = doc.add_paragraph()
        title_run = title_para.add_run(f"{company_name} Pre-IPO Investment Memo")
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
        
        # Set margins for better layout
        section = doc.sections[0]
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        
        doc.save(full_path)
        return full_path

    def run_memo_pipeline(pdf_path, custom_focus="", output_dir="documents"):
        text_by_page, _ = extract_text_by_page(pdf_path)
        default_query = (
            "Extract pages with: 'Management’s Discussion and Analysis', 'Financial Highlights', "
            "'Risk Factors', 'Business Overview', 'Industry Overview'."
        )
        pages_to_keep = get_relevant_pages_chunked(text_by_page, default_query)
        if not pages_to_keep:
            raise ValueError("No relevant pages found. The document may be incompatible or lack key sections.")
        
        filtered_text = extract_selected_pages_text(pdf_path, pages_to_keep)
        if not filtered_text.strip():
            raise ValueError("Could not extract text from relevant pages.")
        
        company_name = extract_company_name(filtered_text)
        sections_dict = generate_memo_sections(filtered_text, custom_focus)
        return save_sections_to_word(sections_dict, company_name=company_name, output_dir=output_dir)

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
        # Pattern to capture headers like "## 1. IPO Offer Details" or "### Company Overview"
        header_pattern = re.compile(r"^#+\s*(?:\d+\.\s*)?(.*?)\s*$", re.MULTILINE)
        
        # Split text by headers
        parts = header_pattern.split(summary_text)
        if len(parts) > 1:
            # The first part is usually empty, so we iterate over pairs of (header, content)
            for i in range(1, len(parts), 2):
                header = parts[i].strip()
                content = parts[i+1]
                bullets = re.findall(r'[-\*•]\s+(.*)', content)
                # Bold markdown like **Key Metric:** to <strong>Key Metric:</strong>
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

    class PDFQueryEngine:
        def __init__(self, model_name="all-MiniLM-L6-v2"):
            self.api_key = DEEPSEEK_API_KEY
            self.embedder = SentenceTransformer(model_name)

        def extract_text_from_pdf(self, path):
            reader = PdfReader(path)
            return [(i + 1, page.extract_text().strip()) for i, page in enumerate(reader.pages) if page.extract_text()]

        def answer_query(self, pdf_path, query, top_k=3):
            chunks = self.extract_text_from_pdf(pdf_path)
            if not chunks: raise ValueError("No text could be extracted from the PDF.")
            
            pages, texts = zip(*chunks)
            text_embeddings = np.array(self.embedder.encode(texts, convert_to_numpy=True))
            
            index = faiss.IndexFlatL2(text_embeddings.shape[1])
            index.add(text_embeddings)
            
            query_embedding = self.embedder.encode([query])
            _, I = index.search(query_embedding, k=top_k)
            
            context_chunks = [(pages[i], texts[i]) for i in I[0]]
            
            messages = [{"role": "system", "content": "Answer the user's question based on the context provided from the document pages."}]
            for page_num, text in context_chunks:
                messages.append({"role": "user", "content": f"[Context from Page {page_num}]:\n{text}"})
            messages.append({"role": "user", "content": f"Question: {query}"})
            
            response = requests.post(DEEPSEEK_API_URL, headers={"Authorization": f"Bearer {self.api_key}"}, json={"model": "deepseek-chat", "messages": messages, "temperature": 0.2})
            response.raise_for_status()
            
            answer_md = response.json()["choices"][0]["message"]["content"]
            cited_pages = sorted([pages[i] for i in I[0]])
            return markdown.markdown(answer_md), cited_pages

    # Initialize session state
    if "memo_generated" not in st.session_state:
        st.session_state.memo_generated = False
    if "memo_path" not in st.session_state:
        st.session_state.memo_path = None
    if "pdf_path" not in st.session_state:
        st.session_state.pdf_path = None
    
    # --- Main App Flow ---
    st.markdown("### 📝 Pre-IPO Investment Memo Generator")
    st.markdown("Upload a DRHP or IPO prospectus to automatically generate a detailed investment memo, an infographic, and perform Q&A.")
    st.subheader("📤 1. Upload DRHP or IPO PDF")
    pdf_file = st.file_uploader("Upload your PDF file", type=["pdf"], key="memo_pdf")
    
    if pdf_file:
        # Save uploaded file to a temporary path
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(pdf_file.getbuffer())
            st.session_state.pdf_path = tmp_file.name
            
        custom_focus = st.text_area(
            "Optional: Add custom notes to guide memo generation",
            key="memo_focus",
            help="Example: 'Focus on the competitive landscape in North America and risks related to supply chain.'"
        )

        if st.button("📘 Generate Investment Memo", key="gen_memo"):
            with st.spinner("⏳ Analyzing document and generating memo... This may take a few minutes."):
                try:
                    memo_path = run_memo_pipeline(st.session_state.pdf_path, custom_focus)
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
                        
                        # --- NEW FIX ---
                        # The infographic likely has a fixed width in its CSS. We can force the 
                        # component to render in a wider frame by setting the `width` parameter.
                        # This should allow the content to display as intended.
                        st.components.v1.html(infographic_html, width=950, height=1000, scrolling=True)
                        # --- END FIX ---
                                            
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
        st.subheader("🔍 3. Ask Questions from the PDF")
        query = st.text_input("Type your question (e.g., What are the key risk factors?)", key="memo_query")
        if query:
            with st.spinner("💬 Searching for answers in the document..."):
                try:
                    engine = PDFQueryEngine()
                    answer_html, cited_pages = engine.answer_query(st.session_state.pdf_path, query)
                    st.markdown(answer_html, unsafe_allow_html=True)
                    st.caption(f"📄 Answer generated from information on pages: {', '.join(map(str, cited_pages))}")
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
# 4. SPECIAL SITUATIONS ANALYZER
# (Code from app - SpecialSituations.py)
# ==============================================================================
def special_situations_app():
    """
    Encapsulates the complete Special Situations Analyzer functionality,
    including memo generation, a valuation module, and infographic creation.
    """

    # ========== CONFIG & SETUP ==========
    # This section handles API key loading and global constants.
    try:
        DEEPSEEK_API_KEY = st.secrets["deepseek"]["api_key"]
    except (KeyError, FileNotFoundError):
        st.error("DeepSeek API key not found. Please add it to your Streamlit secrets.")
        st.stop()

    DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

    try:
        FMP_API_KEY = st.secrets["fmp"]["api_key"]
    except (KeyError, FileNotFoundError):
        st.error("FMP API key not found. Please add it to your Streamlit secrets.")
        st.stop()

    # ==========================
    # REPORT & INFOGRAPHIC STRUCTURES
    # ==========================
    REPORT_TEMPLATES = {
        "Spin-Off or Split-Up": """
Transaction Overview
ParentCo and SpinCo details
Rationale (regulatory, strategic unlock, valuation arbitrage)
Distribution terms (ratio, eligibility, tax treatment)
ParentCo Post-Spin Outlook
Strategic focus
Financial profile and valuation
SpinCo Investment Case
Business model, growth drivers
Historical and pro forma financials
Independent valuation (e.g., Sum-of-the-Parts)
Valuation Analysis
Risks and Overhangs
Forced selling, low float, governance concerns
""",
        "Mergers & Acquisitions": """
Deal Summary
Parties involved, consideration (cash/stock), premium
Regulatory/antitrust/board approval status
Target Company Analysis
Valuation vs. offer
Control premium vs. peers
Buyer’s Rationale and Financing
Strategic fit
Synergies and pro forma financials
Deal financing (debt, equity)
Shareholder Vote & Antitrust Risk
Key holders' stance
Timing and likelihood of deal closure
Spread Analysis and Arbitrage Opportunity
Deal spread
IRR scenarios based on timing/riskfv
""",
        "Bankruptcy / Distressed / Restructuring": """
Situation Summary
Cause of distress
Filing date, jurisdiction, DIP terms
Capital Structure Analysis
Pre- and post-reorg structure
Seniority waterfall
Creditor classes and recovery potential
Valuation and Recovery Scenarios
Estimated Enterprise Value
Recovery per instrument (bonds, equity, unsecured)
Reorganization Plan and Exit Timeline
Conversion to equity, rights offering, warrants
Exit multiples
Catalysts and Legal Risks
Judge approval, creditor objections, asset sales
""",
        "Activist Campaign": """
Activist Background
Fund profile, history, prior campaigns
Campaign Details
Demands (board seat, spin, buyback, etc.)
Timeline of engagement
Company's Response and Governance Profile
Management alignment, shareholder defense
Scenario Analysis
Status quo vs. activist success
Proxy fight implications
Valuation Impact
NPV of potential changes (e.g., spin-off value, ROIC uplift)
""",
        "Regulatory or Legal Catalyst": """
Legal/Regulatory Background
Case/issue summary
Historical legal proceedings
Outcome Scenarios
Win, loss, settlement
Timeline
Financial and Strategic Implications
Fines, product approval, license loss
Revenue/EBITDA impact
Market Reaction History (if any)
Past similar cases
""",
        "Asset Sales or Carve-Outs": """
Transaction Overview
Buyer, price, structure
Valuation vs. book and peers
Strategic Impact
Focus shift, deleveraging, margin profile
Use of Proceeds
Debt repayment, dividends, buybacks, capex
Re-rating Potential
EBITDA margin uplift, return metrics
""",
        "Capital Raising or Buyback Catalyst": """
Transaction Mechanics
Size, dilution, instrument type
Capital Structure Post-Deal
Leverage ratios, interest burden
Shareholder Implications
Accretion/dilution
EPS impact
Buyback Analysis (if applicable)
Repurchase pace, valuation support
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
            market_cap = info.get("marketCap", 0) or 0
            total_debt = info.get("totalDebt", 0) or 0
            cash = info.get("cashAndShortTermInvestments", info.get("cash", 0)) or 0
            net_debt = total_debt - cash
            ebitda = info.get("ebitda", 0) or 0
            return float(market_cap), float(net_debt), float(ebitda)
        except Exception:
            return 0.0, 0.0, 0.0

    # --- Text & Document Processors ---
    def clean_markdown(text):
        text = re.sub(r'^[ \t\-]{3,}$', '', text, flags=re.MULTILINE)
        text = re.sub(r'#+\s*', '', text)
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        text = re.sub(r'\*(.*?)\*', r'\1', text)
        text = re.sub(r'`{1,3}(.*?)`{1,3}', r'\1', text)
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'^- ', '• ', text, flags=re.MULTILINE)
        return text.strip()

    def truncate_safely(text, limit=20000):
        return text[:limit]

    def split_into_sections(text: str, template: str) -> Dict[str, str]:
        sections = {}
        titles = [line.split('(')[0].strip() for line in template.strip().split('\n') if line.strip()]
        if not titles:
            return {"Memo": text.strip()}

        pattern = re.compile(r'^(' + '|'.join(map(re.escape, titles)) + r')\s*$', re.MULTILINE | re.IGNORECASE)
        matches = list(pattern.finditer(text))

        if not matches:
             # Fallback for when the AI doesn't use the exact titles as headings
            intro_end = matches[0].start() if matches else len(text)
            first_title_key = titles[0] if titles else "Introduction"
            sections[first_title_key] = text[:intro_end].strip()

        for i, match in enumerate(matches):
            title = match.group(1).strip()
            start_of_content = match.end()
            end_of_content = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start_of_content:end_of_content].strip()
            # Find the canonical title to handle case differences
            canonical_title = next((t for t in titles if t.lower() == title.lower()), title)
            sections[canonical_title] = content
        
        # If still no sections, just return the whole memo under a generic key
        if not sections:
            return {"Investment Memo": text}
            
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
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        
        return doc

    # --- Core Memo Generator ---
    def generate_special_situation_note(
        company_name: str,
        situation_type: str,
        uploaded_files: list,
        valuation_mode: str = None,
        parent_peers: str = "",
        spinco_peers: str = ""
    ):
        # 1) Extract text
        combined_text = ""
        for file in uploaded_files:
            if file.name.endswith(".pdf"):
                combined_text += extract_text_from_pdf(file) + "\n"
            elif file.name.endswith(".docx"):
                combined_text += extract_text_from_docx(file) + "\n"
            else:
                combined_text += f"[Unsupported file: {file.name}]\n"

        # 2) Select template
        structure = REPORT_TEMPLATES.get(situation_type)
        if not structure:
            raise ValueError(f"Unsupported situation type: {situation_type}")

        # 3) Build valuation_section only for spin-offs
        valuation_section = ""
        if situation_type == "Spin-Off or Split-Up" and valuation_mode:
            def process_peers(raw: str):
                names = [n.strip() for n in raw.split(",") if n.strip()]
                tickers = [resolve_company_to_ticker(n) for n in names]
                mults = [get_ev_ebitda_multiple(t, FMP_API_KEY) for t in tickers if t]
                avg = round(sum(mults) / len(mults), 2) if mults else None
                return names, tickers, mults, avg

            if valuation_mode == "Let AI choose peers":
                prompt = (
                    f"List 5 large, publicly-traded companies most comparable to the business segments of {company_name}, "
                    "separated by commas."
                )
                resp = requests.post(
                    DEEPSEEK_API_URL,
                    headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
                    json={"model":"deepseek-chat","messages":[{"role":"user","content":prompt}],"temperature":0}
                )
                resp.raise_for_status()
                body = resp.json().get("choices", [])
                ai_text = body[0].get("message",{}).get("content","") if body else ""
                peer_names = [n.strip() for n in ai_text.split(",") if n.strip()]
                peer_tickers = [resolve_company_to_ticker(n) for n in peer_names if resolve_company_to_ticker(n)]
                raw_mults = [get_ev_ebitda_multiple(t, FMP_API_KEY) for t in peer_tickers]
                peer_mults = [m for m in raw_mults if isinstance(m,(int,float))]
                avg_mult = round(sum(peer_mults)/len(peer_mults),2) if peer_mults else None
                
                ticker = resolve_company_to_ticker(company_name)
                actual_mc, debt, ebitda = fetch_fundamentals_yf(ticker)
                ev_est = (avg_mult or 0) * ebitda
                equity_est = ev_est - debt
                upside_pct = ((equity_est / actual_mc) - 1) * 100 if actual_mc else None

                valuation_section = f"""
# Valuation Analysis (AI-Generated)
**AI-Selected Peers**: {', '.join(peer_names)}
**Peer EV/EBITDA multiples**: {peer_mults}
**Average EV/EBITDA**: {avg_mult or 'N/A'}
**{company_name} TTM EBITDA**: ${ebitda:,.0f}
**Estimated Enterprise Value**: {avg_mult or 0}x * ${ebitda:,.0f} = ${ev_est:,.0f}
**Net Debt**: ${debt:,.0f}
**Implied Equity Value**: ${equity_est:,.0f}
**Actual Market Cap**: ${actual_mc:,.0f}
**Implied Upside**: {f"{upside_pct:.1f}%" if upside_pct is not None else 'N/A'}
"""
            elif valuation_mode == "I'll enter peer company names":
                p_names, _, p_mults, p_avg = process_peers(parent_peers)
                s_names, _, s_mults, s_avg = process_peers(spinco_peers)
                valuation_section = f"""
# Valuation Analysis (User-Provided Peers)
**ParentCo Peers**: {', '.join(p_names)}
EV/EBITDA multiples: {p_mults} (avg {p_avg or 'N/A'})
**SpinCo Peers**: {', '.join(s_names)}
EV/EBITDA multiples: {s_mults} (avg {s_avg or 'N/A'})
"""
        
        # 4) Assemble prompt
        prompt = f"""You are an institutional investment analyst writing a professional memo on a special situation involving {company_name}.
The situation is: **{situation_type}**

Below is the internal company information extracted from various files:
\"\"\"{truncate_safely(combined_text)}\"\"\"
{valuation_section}
Using the structure below, generate a well-written investment memo. Be factual, insightful, and clear.
Structure:
{structure}
"""

        # 5) Call DeepSeek
        response = requests.post(
            DEEPSEEK_API_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            json={"model":"deepseek-chat","messages":[{"role":"user","content":prompt}],"temperature":0.3}
        )
        response.raise_for_status()
        memo_text = clean_markdown(response.json()["choices"][0]["message"]["content"])

        # 6) Build and return .docx
        memo_dict = split_into_sections(memo_text, structure)
        doc = format_memo_docx(memo_dict, company_name, situation_type)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            doc.save(tmp.name)
            return tmp.name

    # --- Infographic Functions ---
    def extract_sections_from_docx_for_infographic(file, situation_type: str) -> Dict[str, str]:
        toc = REPORT_TEMPLATES.get(situation_type)
        if not toc:
            return {}
        
        expected_titles = {t.split('(')[0].strip().lower() for t in toc.strip().splitlines() if t.strip()}
        doc = Document(file)
        sections = {}
        current_heading = None
        current_text = []

        # Find all bolded paragraphs as potential headings
        all_headings = [p.text.strip() for p in doc.paragraphs if p.runs and all(r.bold for r in p.runs if r.text.strip())]

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            
            # Check if the paragraph text is a likely heading
            is_heading = text in all_headings and text.lower() in expected_titles
            
            if is_heading:
                if current_heading and current_text:
                    sections[current_heading] = "\n".join(current_text).strip()
                current_heading = text
                current_text = []
            elif current_heading:
                current_text.append(text)

        if current_heading and current_text:
            sections[current_heading] = "\n".join(current_text).strip()
        
        return sections

    def summarize_section_with_deepseek(section_title, section_text):
        prompt = f"""
You are an institutional research analyst preparing a financial infographic.
Summarize the section titled \"{section_title}\" into 3 to 5 concise bullet points.
Each point should be a single sentence, highlighting key insights clearly and professionally.
Section:
\"\"\"{section_text}\"\"\"
"""
        headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
        payload = {"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    def build_infographic_html(company_name, sections):
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
    <title>{company_name} – Infographic</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', sans-serif; background-color: #f9fafb; color: #1f2937; }}
        .section-icon {{ font-size: 1.4rem; margin-right: 0.6rem; }}
    </style>
</head>
<body class="px-4 py-8 md:px-6 md:py-10 max-w-7xl mx-auto">
    <header class="text-center mb-12">
        <h1 class="text-3xl md:text-4xl font-bold text-gray-800 mb-2">{company_name} – Investment Memo Infographic</h1>
        <p class="text-sm text-gray-500">Generated by AI</p>
    </header>
    <main class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
"""
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
        <div class="shadow-lg rounded-xl p-5 transition-transform hover:scale-[1.02] duration-300 ease-in-out border-l-4 {border_class} {bg_class}">
            <h2 class="text-lg font-semibold text-gray-800 mb-3 flex items-center">
                <span class="section-icon">{icon}</span>{title}
            </h2>
            <ul class="list-disc text-sm text-gray-700 space-y-2 pl-5 leading-relaxed">
{bullet_items}
            </ul>
        </div>
"""
        html += """
    </main>
    <footer class="text-center mt-12">
        <p class="text-xs text-gray-400">This document is for informational purposes only and does not constitute investment advice.</p>
    </footer>
</body>
</html>
"""
        return html


    # ==========================
    # STREAMLIT UI & APP LOGIC
    # ==========================
    st.markdown("### 🔀 Special Situation Memo & Infographic Generator")
    # --- Step 1: Memo Generation ---
    st.header("Step 1: Generate Investment Memo")

    company_name_memo = st.text_input("Enter Company Name", key="company_name_memo")
    situation_type_memo = st.selectbox("Select Situation Type", options=list(REPORT_TEMPLATES.keys()), key="situation_type_memo")
    
    valuation_mode = None
    parent_peers_raw = ""
    spinco_peers_raw = ""

    if situation_type_memo == "Spin-Off or Split-Up":
        st.markdown("##### 🔍 Valuation Module (Optional)")
        valuation_mode = st.radio(
            "Choose a valuation approach:",
            options=["Let AI choose peers", "I'll enter peer company names", "None"],
            key="valuation_mode",
            horizontal=True
        )
        if valuation_mode == "I'll enter peer company names":
            parent_peers_raw = st.text_area("Enter ParentCo Peer Company Names (comma-separated)", key="parent_peers_raw")
            spinco_peers_raw = st.text_area("Enter SpinCo Peer Company Names (comma-separated)", key="spinco_peers_raw")
        elif valuation_mode == "Let AI choose peers":
            st.info("AI will select peers, fetch financials, and generate valuation logic automatically.")

    uploaded_files_memo = st.file_uploader("Upload Public Documents (PDF, DOCX)", accept_multiple_files=True, key="uploaded_files_memo")

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

    # --- Step 2: Infographic Generation ---
    st.header("Step 2: Generate Infographic from Memo")
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

# You would have these imports at the top of your file
# Ensure you have installed the required packages:
# pip install streamlit pymupdf requests beautifulsoup4

def esg_analyzer_app():
    """
    Encapsulates the ESG Analyzer functionality with robust JSON parsing,
    benchmark-driven scoring, categorized insights, and a smarter comparison report.
    """
    st.markdown("### ✨ Advanced ESG Analyzer")
    st.markdown("Generate benchmarked ESG insights from sustainability reports and perform true category-based comparisons.")

    # --- Configuration & Helper Functions ---

    def get_benchmark_rating(score):
        """Converts a numeric score to a benchmark rating and color."""
        try:
            s = float(score)
            if s >= 8.0: return ("Leading", "#27ae60")  # Green
            if s >= 5.0: return ("Average", "#f39c12")  # Orange
            return ("Lagging", "#e74c3c")  # Red
        except (ValueError, TypeError):
            return ("N/A", "#7f8c8d") # Grey

    # --- Core AI Analysis & Parsing (NEW & IMPROVED) ---

    def analyze_esg_with_structured_output(text):
        """Analyzes text using the DeepSeek API with a structured JSON prompt."""
        if not text.strip():
            return json.dumps({"error": "No text provided for analysis."})

        # This new prompt is the key to getting structured, benchmarked data.
        prompt = f"""
        You are an expert ESG analyst. Your task is to analyze the provided ESG report text and return a structured JSON object.

        **JSON Output Specification:**
        - **overall_score**: A single float score from 0.0 to 10.0 representing the overall ESG sentiment and performance.
        - **environmental_score**: A float score from 0.0 to 10.0 for the Environmental pillar.
        - **social_score**: A float score from 0.0 to 10.0 for the Social pillar.
        - **governance_score**: A float score from 0.0 to 10.0 for the Governance pillar.
        - **environmental_insights**: A list of JSON objects. Each object must have two keys: "subcategory" (e.g., "GHG Emissions Reduction", "Water Management") and "detail" (the specific insight). Provide up to 10 insights.
        - **social_insights**: A list of JSON objects with "subcategory" (e.g., "Diversity and Inclusion", "Employee Safety") and "detail". Provide up to 10 insights.
        - **governance_insights**: A list of JSON objects with "subcategory" (e.g., "Board Independence", "Executive Compensation") and "detail". Provide up to 10 insights.
        - **management_remarks**: A list of strings, each being a direct or summarized key remark from management.

        **Example Insight Object:**
        {{
          "subcategory": "GHG Emissions",
          "detail": "The company reported a 15% reduction in Scope 1 and 2 emissions against a 2020 baseline."
        }}

        Do not include any text, explanations, or markdown formatting outside of the main JSON object.

        --- DOCUMENT TEXT ---
        {text[:50000]}
        """
        try:
            DEEPSEEK_API_KEY = st.secrets["deepseek"]["api_key"]
            DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 8000,
                "response_format": {"type": "json_object"} # Force JSON output if the model supports it
            }
            response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=90)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except (KeyError, FileNotFoundError):
            st.error("API Key not found. Please ensure your secrets.toml file is configured.")
            return json.dumps({"error": "API Key not configured."})
        except requests.exceptions.RequestException as e:
            st.error(f"API Request Error: {e}")
            return json.dumps({"error": f"API Request Error: {e}"})

    def parse_structured_esg_data(api_response_text):
        """Parses the JSON string from the API to extract ESG data."""
        default_data = {
            "overall_score": "N/A", "environmental_score": "N/A", "social_score": "N/A", "governance_score": "N/A",
            "environmental_insights": [], "social_insights": [], "governance_insights": [], "management_remarks": []
        }
        try:
            # The response should be a clean JSON string.
            return json.loads(api_response_text)
        except json.JSONDecodeError:
            st.warning("Failed to decode JSON from API response. The AI may have returned malformed data. Attempting to extract JSON block.")
            # Fallback: try to find a JSON block within the response text
            match = re.search(r'```json\s*([\s\S]*?)\s*```', api_response_text)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    st.error("Could not parse the extracted JSON block.")
                    return default_data
            else:
                st.error("No valid JSON found in the API response.")
                return default_data
        except Exception as e:
            st.error(f"An unexpected error occurred during parsing: {e}")
            return default_data

    # --- Individual Report Generation (NEW & IMPROVED HTML) ---

    def generate_html_report_esg(esg_data, company_name):
        """Generates a rich, benchmark-driven HTML report from the parsed ESG data."""
        safe_company_name = re.sub(r'[^\w\-_]', '_', company_name)[:50]
        current_date = datetime.now().strftime("%B %d, %Y")

        def generate_score_summary_html(title, score):
            rating, color = get_benchmark_rating(score)
            return f"""
            <div class="score-card">
                <h4>{title}</h4>
                <div class="score-value">{score}/10</div>
                <div class="benchmark-pill" style="background-color:{color};">{rating}</div>
            </div>
            """
        
        def generate_insight_section(title, icon, insights):
            if not insights: return ""
            # Using html.escape to prevent markdown issues with asterisks
            rows_html = "".join(f"""
            <tr>
                <td>{idx}</td>
                <td>{html.escape(insight.get('subcategory', 'N/A'))}</td>
                <td>{html.escape(insight.get('detail', 'No detail provided.'))}</td>
            </tr>
            """ for idx, insight in enumerate(insights, 1))
            return f"""
                <h2><span class="category-icon">{icon}</span>{title}</h2>
                <table>
                    <thead><tr><th width="5%">#</th><th width="25%">Category</th><th>Insight Detail</th></tr></thead>
                    <tbody>{rows_html}</tbody>
                </table>
            """

        html_content = f"""
        <!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{company_name} ESG Insights Report</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.6; color: #333; background-color: #f9fafb; padding: 20px; margin: 0; }}
            .container {{ max-width: 1000px; margin: auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            header {{ border-bottom: 2px solid #e5e7eb; padding-bottom: 20px; margin-bottom: 30px; text-align: center; }}
            h1 {{ font-size: 2.5em; color: #111827; margin-bottom: 0; }}
            h2 {{ font-size: 1.8em; color: #1f2937; border-bottom: 2px solid #3b82f6; padding-bottom: 10px; margin-top: 40px; }}
            h3.subtitle {{ font-size: 1.1em; color: #6b7280; font-weight: normal; }}
            table {{ width: 100%; border-collapse: collapse; margin: 25px 0; }}
            th, td {{ border: 1px solid #e5e7eb; padding: 12px 15px; text-align: left; vertical-align: top; }}
            th {{ background-color: #f3f4f6; color: #374151; font-weight: 600; }}
            .score-summary {{ display: flex; justify-content: space-around; flex-wrap: wrap; gap: 20px; margin-top: 20px; text-align: center; }}
            .score-card {{ background-color: #f9fafb; border: 1px solid #e5e7eb; padding: 15px; border-radius: 8px; flex: 1; min-width: 150px; }}
            .score-card h4 {{ margin: 0 0 10px 0; color: #4b5563; }}
            .score-value {{ font-size: 2em; font-weight: bold; color: #1f2937; }}
            .benchmark-pill {{ display: inline-block; padding: 4px 12px; border-radius: 9999px; color: white; font-weight: 500; font-size: 0.9em; margin-top: 10px; }}
            .category-icon {{ margin-right: 12px; }}
        </style></head><body><div class="container">
            <header>
                <h1>{company_name}</h1>
                <h3 class="subtitle">ESG Insights Report | Generated on: {current_date}</h3>
            </header>
            
            <h2>📊 Executive Score Summary</h2>
            <div class="score-summary">
                {generate_score_summary_html("Overall ESG Score", esg_data.get('overall_score', 'N/A'))}
                {generate_score_summary_html("Environmental", esg_data.get('environmental_score', 'N/A'))}
                {generate_score_summary_html("Social", esg_data.get('social_score', 'N/A'))}
                {generate_score_summary_html("Governance", esg_data.get('governance_score', 'N/A'))}
            </div>

            {generate_insight_section("Environmental Insights", "🌍", esg_data.get("environmental_insights", []))}
            {generate_insight_section("Social Insights", "🏢", esg_data.get("social_insights", []))}
            {generate_insight_section("Governance Insights", "🏛️", esg_data.get("governance_insights", []))}
            {generate_insight_section("Key Remarks by Management", "🎤", [{"subcategory": "Remark", "detail": r} for r in esg_data.get("management_remarks", [])])}
        </div></body></html>
        """
        return html_content.encode('utf-8'), f"ESG_Insights_{safe_company_name}.html"

    # --- Comparison Tool (NEW & IMPROVED LOGIC) ---

    def extract_data_from_html_for_comparison(soup, filename):
        """Extracts structured ESG data from a single HTML report soup."""
        data = {'company_name': filename.replace('.html', '').replace('ESG_Insights_', '')}
        
        # Extract Scores
        score_cards = soup.find_all('div', class_='score-card')
        for card in score_cards:
            title = card.find('h4').text.lower().replace(' ', '_').replace('esg_', '')
            score = card.find('div', class_='score-value').text.split('/')[0]
            data[title] = score
        
        # Extract Insights
        for pillar, icon in [('environmental', '🌍'), ('social', '🏢'), ('governance', '🏛️')]:
            insights = []
            header = soup.find(lambda tag: tag.name == 'h2' and icon in tag.get_text(strip=True))
            if header:
                table = header.find_next('table')
                if table:
                    rows = table.find_all('tr')[1:]  # Skip header
                    for row in rows:
                        cells = row.find_all('td')
                        if len(cells) == 3:
                            insights.append({
                                'subcategory': cells[1].get_text(strip=True),
                                'detail': cells[2].get_text(strip=True)
                            })
            data[f'{pillar}_insights'] = insights
        return data

    def generate_comparison_html_esg(esg_reports):
        """Generates an HTML comparison report with true category-based matching."""
        if not 1 <= len(esg_reports) <= 5:
            return "<h1>Error: Please provide between 1 and 5 reports.</h1>".encode('utf-8'), "ESG_Comparison.html"
        
        current_date = datetime.now().strftime("%B %d, %Y")
        company_names = [report.get('company_name', 'Unknown') for report in esg_reports]

        def generate_score_comparison_table():
            header = "".join(f"<th>{name}</th>" for name in company_names)
            
            def score_row(title, key_prefix):
                cells = ""
                for report in esg_reports:
                    score = report.get(f'{key_prefix}_score', 'N/A')
                    rating, color = get_benchmark_rating(score)
                    cells += f'<td><div class="score-cell"><span class="score-val">{score}</span><span class="rating-badge" style="background:{color};">{rating}</span></div></td>'
                return f"<tr><td>{title}</td>{cells}</tr>"

            return f"""
            <h2>📊 Overall Score Comparison</h2>
            <table>
                <thead><tr><th>Metric</th>{header}</tr></thead>
                <tbody>
                    {score_row('Overall ESG', 'overall')}
                    {score_row('Environmental', 'environmental')}
                    {score_row('Social', 'social')}
                    {score_row('Governance', 'governance')}
                </tbody>
            </table>
            """

        def generate_insight_comparison_section(title, icon, category_key):
            # 1. Aggregate all unique subcategories across all reports for this pillar
            all_subcategories = set()
            for report in esg_reports:
                for insight in report.get(category_key, []):
                    all_subcategories.add(insight['subcategory'])
            
            if not all_subcategories: return ""

            # 2. Create a lookup map for faster access: {company: {subcategory: detail}}
            insight_map = {name: {i['subcategory']: i['detail'] for i in report.get(category_key, [])}
                           for name, report in zip(company_names, esg_reports)}

            # 3. Build the HTML table
            header = "".join(f"<th>{name}</th>" for name in company_names)
            rows_html = ""
            for subcat in sorted(list(all_subcategories)):
                row = f"<tr><td>{html.escape(subcat)}</td>"
                for name in company_names:
                    detail = insight_map[name].get(subcat, "—")
                    row += f"<td>{html.escape(detail)}</td>"
                row += "</tr>"
                rows_html += row
            
            return f"""
            <h2><span class="category-icon">{icon}</span>{title} Comparison</h2>
            <table>
                <thead><tr><th>Category</th>{header}</tr></thead>
                <tbody>{rows_html}</tbody>
            </table>
            """

        html_content = f"""
        <!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ESG Comparison Report</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.6; color: #333; background-color: #f9fafb; padding: 20px; margin: 0; }}
            .container {{ max-width: 1200px; margin: auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            header {{ border-bottom: 2px solid #e5e7eb; padding-bottom: 20px; margin-bottom: 30px; text-align: center; }}
            h1 {{ font-size: 2.5em; color: #111827; }} h2 {{ font-size: 1.8em; color: #1f2937; border-bottom: 2px solid #3b82f6; padding-bottom: 10px; margin-top: 40px; }}
            h3.subtitle {{ font-size: 1.1em; color: #6b7280; font-weight: normal; }}
            table {{ width: 100%; border-collapse: collapse; margin: 25px 0; }}
            th, td {{ border: 1px solid #e5e7eb; padding: 12px 15px; text-align: left; vertical-align: top; }}
            th {{ background-color: #f3f4f6; color: #374151; font-weight: 600; }}
            td:first-child {{ font-weight: 500; color: #374151; }}
            .score-cell {{ display: flex; flex-direction: column; align-items: flex-start; gap: 5px; }}
            .score-val {{ font-size: 1.2em; font-weight: bold; }}
            .rating-badge {{ display: inline-block; padding: 2px 10px; border-radius: 9999px; color: white; font-weight: 500; font-size: 0.8em; }}
            .category-icon {{ margin-right: 12px; }}
        </style></head><body><div class="container">
            <header><h1>ESG Comparison Report</h1><h3 class="subtitle">Generated on: {current_date}</h3></header>
            {generate_score_comparison_table()}
            {generate_insight_comparison_section("Environmental", "🌍", "environmental_insights")}
            {generate_insight_comparison_section("Social", "🏢", "social_insights")}
            {generate_insight_comparison_section("Governance", "🏛️", "governance_insights")}
        </div></body></html>
        """
        return html_content.encode('utf-8'), "ESG_Comparison_Report.html"

    # --- PDF Text Extraction (kept your original, it's good) ---
    def extract_text_from_pdf_esg(pdf_file):
        try:
            pdf_bytes = pdf_file.getvalue()
            pdf_file.seek(0)
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            return "\n\n".join(page.get_text("text") for page in doc if page.get_text("text").strip())
        except Exception as e:
            st.error(f"Error reading PDF: {e}")
            return ""

    # --- Streamlit UI and Logic ---
    st.subheader("1. Generate New ESG Report")
    company = st.text_input("🏢 Enter Company Name", key="esg_company")
    file = st.file_uploader("📄 Upload ESG Disclosure PDF", type="pdf", key="esg_file")

    if st.button("🚀 Generate & Download Report", key="esg_generate"):
        if not all([company, file]):
            st.error("Please provide a company name and a PDF file.")
        else:
            with st.spinner("Analyzing ESG disclosures... This may take a moment."):
                text = extract_text_from_pdf_esg(file)
                if text:
                    response_text = analyze_esg_with_structured_output(text)
                    esg_data = parse_structured_esg_data(response_text)
                    
                    if "error" in esg_data:
                         st.error(f"Analysis failed: {esg_data['error']}")
                    else:
                        st.success("Analysis complete!")
                        report_content, report_filename = generate_html_report_esg(esg_data, company)
                        st.download_button("📥 Download HTML Report", report_content, report_filename, "text/html", use_container_width=True)
                        st.markdown("### Report Preview:")
                        st.components.v1.html(report_content.decode('utf-8'), height=600, scrolling=True)

    st.markdown("---")
    st.subheader("2. Compare Existing Reports")
    uploaded_html_files = st.file_uploader("📂 Upload 2 to 5 ESG HTML Reports", type="html", accept_multiple_files=True, key="esg_compare_files")

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
# 6. PORTFOLIO AGENT (FINAL CORRECTED VERSION)
# ==============================================================================
def portfolio_agent_app(user_id: str):
    """
    A persistent agent to index and query company documents using Pinecone,
    with added capabilities for pre-defined, structured analysis.
    """
    st.markdown("### 🗂️ Portfolio Agent")
    st.markdown("Upload company-specific documents for indexation.")

    # --- HELPER FUNCTIONS ---
    # These helpers are used by the PortfolioAgent class, so they are defined here in the main function scope.
    def call_deepseek_model(prompt: str) -> str:
        try:
            if not DEEPSEEK_API_KEY:
                st.error("DeepSeek API Key is not configured in secrets.")
                return "Error: API Key not available."
            headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
            payload = {"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0.2, "max_tokens": 8192}
            response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=240)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")
            return f"Error: {e}"

    def parse_markdown_to_structure(markdown_text: str) -> list:
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

    def clean_metric_name(name: str) -> str:
        cleaned_name = name.replace('*', '').strip()
        cleaned_name = re.sub(r'(?<!^)(?=[A-Z])', ' ', cleaned_name)
        return cleaned_name

    def add_spacing_to_run_on_text(text: str) -> str:
        text = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', text)
        text = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', text)
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
        return text

    def markdown_to_word_bytes(structured_data: list, company_name: str) -> bytes:
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
        doc.add_paragraph(f"Quick Note - {company_name}", style=title_style)
        for heading, content in structured_data:
            cleaned_heading = re.sub(r'^#+\s*', '', heading).strip()
            doc.add_paragraph(cleaned_heading, style=heading_style)
            if "Financial Data" in heading:
                metrics, values = [], []
                pairs = [p.strip() for p in content.split(';') if p.strip()]
                for pair in pairs:
                    if ':' in pair:
                        metric, value = pair.split(':', 1)
                        metrics.append(clean_metric_name(metric))
                        values.append(value.strip())
                if metrics:
                    table = doc.add_table(rows=2, cols=len(metrics))
                    table.style = 'Table Grid'
                    for i, metric_text in enumerate(metrics):
                        p_header = table.cell(0, i).paragraphs[0]
                        run_header = p_header.add_run(metric_text)
                        run_header.font.bold = True
                        run_header.font.name = 'Aptos Display'
                        run_header.font.size = Pt(9)
                        p_value = table.cell(1, i).paragraphs[0]
                        run_value = p_value.add_run(values[i])
                        run_value.font.bold = False
                        run_value.font.name = 'Aptos Display'
                        run_value.font.size = Pt(9)
            else:
                content_with_spaces = add_spacing_to_run_on_text(content)
                cleaned_content = re.sub(r'\*(\*?)(.*?)\1\*', r'\2', content_with_spaces)
                for para in cleaned_content.split('\n'):
                    para = para.strip()
                    if not para: continue
                    if para.startswith(('* ', '- ')):
                        doc.add_paragraph(para[2:], style='List Bullet')
                    else:
                        doc.add_paragraph(para, style=body_style)
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()

    def format_analysis_as_html(structured_data: list, title: str, sources: str) -> str:
        html_body = ""
        for i, (heading, content) in enumerate(structured_data):
            cleaned_heading = re.sub(r'^#+\s*(\d+\.\s*)?', '', heading).strip()
            if i == 0 and title.lower() in cleaned_heading.lower():
                continue
            html_body += f"<h3>{cleaned_heading}</h3>"
            if "Financial Data" in heading:
                metrics, values = [], []
                pairs = [p.strip() for p in content.split(';') if p.strip()]
                for pair in pairs:
                    if ':' in pair:
                        metric, value = pair.split(':', 1)
                        metrics.append(clean_metric_name(metric))
                        values.append(value.strip())
                table_html = "<div style='overflow-x:auto;'><table class='custom-table'><thead><tr>"
                for metric in metrics: table_html += f"<th>{metric}</th>"
                table_html += "</tr></thead><tbody><tr>"
                for value in values: table_html += f"<td>{value}</td>"
                table_html += "</tr></tbody></table></div>"
                html_body += table_html
            else:
                cleaned_content = add_spacing_to_run_on_text(content)
                paragraphs = cleaned_content.strip().split('\n')
                for para in paragraphs:
                    p = para.strip()
                    if not p:
                        continue
                    if re.match(r'^\s*([*-]|\d+\.)\s+', p):
                        list_item_text = re.sub(r'^\s*([*-]|\d+\.)\s+', '', p)
                        html_body += f'<p style="padding-left: 1.5em; text-indent: -1.5em;">• {list_item_text}</p>'
                    else:
                        html_body += f"<p>{p}</p>"
        html_style = """
        <style>
            .analysis-container { font-family: 'Poppins', sans-serif; border: 1px solid #e0e0e0; border-radius: 8px; padding: 25px; background-color: #f9f9f9; margin-top: 20px; }
            .analysis-container h2 {font-size: 1.5em; color: #00416A; border-bottom: 2px solid #00416A; padding-bottom: 10px; margin-top: 0;}
            .analysis-container h3 {font-size: 1.2em; color: #00416A; padding-bottom: 5px; margin-top: 25px; border-bottom: 1px solid #e6f1f6;}
            .analysis-container .custom-table { width: 100%; border-collapse: collapse; margin: 15px 0; }
            .analysis-container .custom-table th, .analysis-container .custom-table td { border: 1px solid #ddd; padding: 10px 14px; text-align: center; white-space: nowrap; }
            .analysis-container .custom-table th { background-color: #e6f1f6; font-weight: 600; }
            .analysis-container p { margin-bottom: 1em; line-height: 1.6; }
            .analysis-container .sources { font-size: 0.85em; color: #555; margin-top: 25px; text-align: right; }
        </style>
        """
        return f"""
        {html_style}
        <div class="analysis-container">
            <h2>{title} Analysis</h2>
            {html_body}
            <div class="sources"><strong>Sources:</strong> {sources}</div>
        </div>
        """

    # --- UI & State Management ---
    @st.cache_resource
    def load_agent(user_id):
        """
        Initializes the PortfolioAgent.
        The fix is to define the class directly INSIDE the cached function
        to avoid the "free variable" scope error with st.cache_resource.
        """
        # --- CORE: The PortfolioAgent Class (Defined INSIDE the cached function) ---
        class PortfolioAgent:
            def __init__(self, user_id: str, index_name: str = "portfolio-agent"):
                self.namespace = user_id
                try:
                    pinecone_api_key = st.secrets["pinecone"]["api_key"]
                except (KeyError, FileNotFoundError):
                    st.error("Pinecone API key not found.")
                    raise
                self.pc = Pinecone(api_key=pinecone_api_key)
                if index_name not in self.pc.list_indexes().names():
                    st.error(f"Index '{index_name}' does not exist.")
                    raise
                self.index = self.pc.Index(index_name)
                self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

            def sanitize_filename(self, name: str) -> str:
                return re.sub(r'[<>:"/\\|?*]', '_', name.strip())

            def _extract_text(self, file_content: bytes, filename: str) -> str:
                try:
                    if filename.lower().endswith(".pdf"):
                        with fitz.open(stream=file_content, filetype="pdf") as doc:
                            return "\n".join(page.get_text() for page in doc)
                    elif filename.lower().endswith(".docx"):
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                            tmp.write(file_content)
                            tmp_path = tmp.name
                        doc = Document(tmp_path)
                        os.unlink(tmp_path)
                        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
                    elif filename.lower().endswith(".txt"):
                        return file_content.decode("utf-8")
                except Exception as e:
                    st.warning(f"Could not read {filename}: {e}")
                return ""

            def _chunk_text(self, text: str, max_tokens: int = 250) -> List[str]:
                paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
                chunks, current_chunk = [], ""
                for para in paragraphs:
                    if len(current_chunk.split()) + len(para.split()) <= max_tokens:
                        current_chunk += f" {para}"
                    else:
                        if current_chunk: chunks.append(current_chunk.strip())
                        current_chunk = para
                if current_chunk: chunks.append(current_chunk.strip())
                return chunks

            def add_documents(self, company: str, uploaded_files: list):
                safe_company_name = self.sanitize_filename(company)
                with st.status(f"Processing documents for {safe_company_name}...", expanded=True) as status:
                    vectors_to_upsert = []
                    for file in uploaded_files:
                        status.write(f"Extracting text from {file.name}...")
                        text = self._extract_text(file.getvalue(), file.name)
                        if not text: continue
                        status.write(f"Chunking and embedding text from {file.name}...")
                        chunks = self._chunk_text(text)
                        vectors = self.embedding_model.encode(chunks).tolist()
                        for i, chunk in enumerate(chunks):
                            chunk_id = f"{safe_company_name}-{self.sanitize_filename(file.name)}-{i}"
                            metadata = {"company": safe_company_name, "source_file": file.name, "original_text": chunk}
                            vectors_to_upsert.append({"id": chunk_id, "values": vectors[i], "metadata": metadata})
                    if not vectors_to_upsert:
                        st.warning("No text could be extracted.")
                        return
                    status.update(label=f"Upserting {len(vectors_to_upsert)} vectors to Pinecone...")
                    self.index.upsert(vectors=vectors_to_upsert, batch_size=100, namespace=self.namespace)
                st.success(f"Successfully indexed {len(vectors_to_upsert)} new document chunks for **{company}**.")

            def query(self, query_text: str, companies: List[str], k: int = 7) -> Tuple[str, str]:
                query_vector = self.embedding_model.encode(query_text).tolist()
                query_filter = {"company": {"$in": [self.sanitize_filename(c) for c in companies]}}
                results = self.index.query(vector=query_vector, top_k=k, filter=query_filter, include_metadata=True, namespace=self.namespace)
                if not results.matches: return "I could not find relevant information in the indexed documents to answer your question.", ""
                context_excerpts = [f"Excerpt from '{m.metadata['source_file']}':\n\"{m.metadata['original_text']}\"\n" for m in results.matches]
                source_docs = set(m.metadata['source_file'] for m in results.matches)
                prompt = (f"Answer the user's question based *only* on the following context:\n--- CONTEXT ---\n{''.join(context_excerpts)}\n--- QUESTION ---\n{query_text}\n--- ANSWER ---\n")
                answer = call_deepseek_model(prompt)
                return answer, ", ".join(sorted(list(source_docs)))

            def get_predefined_analysis(self, analysis_type: str, companies: List[str], k: int = 40) -> Tuple[str, str]:
                ANALYSIS_CONFIG = {
                "Quick Company Note": {
                    "search_query": "Comprehensive company profile including business overview, products, services, market position, key financial data like revenue, profit, debt, cash, market cap, industry trends, competitive landscape, investment highlights, strengths, weaknesses, opportunities, threats, risk factors, governance issues, and any legal or regulatory challenges like litigations or claims.",
                    "system_prompt": """You are a top-tier equity research analyst. Your task is to generate a professional and highly detailed 'Quick Company Note' based ONLY on the provided document excerpts. The analysis must be thorough, well-written, and adhere strictly to the formatting instructions below. Crucially, do not use any markdown formatting (like asterisks for italics or bold) within the financial data line or within the bullet points themselves. Ensure metric names have spaces (e.g., 'Net Income' not 'NetIncome').

# 1. Company Overview
(Provide a comprehensive and in-depth summary of the company. This section MUST be at least 500 words long. Cover its history, business model, core products and services, key operational segments, geographic footprint, and overall strategic mission.)

# 2. Financial Data
(Provide the key financial metrics on a single line, separated by semicolons. Format: "Metric1: Value1; Metric2: Value2; ...". If a value is not found, use "Data not available". Example: "Revenue: $64.8B; Net Income: $10.7B; Total Debt: $50.1B")

# 3. Industry Overview
(Provide a comprehensive and in-depth analysis of the industry landscape. This section MUST be at least 500 words long. Discuss market size, key growth drivers, technological trends, competitive dynamics, regulatory environment, and the company's competitive positioning within the industry.)

# 4. Key Investment Highlights
(Provide exactly 10 detailed bullet points. Each bullet point MUST be a complete, well-reasoned sentence that clearly explains a specific strength, competitive advantage, or investment thesis point.)

# 5. Key Risks
(Provide detailed bullet points explaining the most significant risks facing the company. Each bullet point MUST be a complete, well-reasoned sentence covering operational, financial, market, or strategic risks.)

# 6. Red Flags
(Provide detailed bullet points identifying any potential red flags mentioned in the documents. Each bullet point MUST be a complete, well-reasoned sentence. This includes any mention of governance issues, ongoing lawsuits, regulatory probes, or questionable accounting practices.)"""
                },
                # Other analysis types remain unchanged
                "Debt Details": {
                    "search_query": "Detailed information about the company's short-term and long-term debt, credit facilities, loans, bonds, debentures, financing arrangements, and key debt covenants.",
                    "system_prompt": "You are a senior credit analyst. Based on the provided text, extract and synthesize all available information about the company's debt structure. Format the output in Markdown. Use a table for debt instruments and their amounts. Use bullet points for key covenants and maturity profiles."
                },
                "Litigations and Court Cases/Claims": {
                    "search_query": "Details on litigations, legal proceedings, lawsuits, court cases, regulatory investigations, and contingent liabilities.",
                    "system_prompt": "You are a legal analyst. From the context provided, compile a report on all legal and regulatory matters. For each distinct case, create a section with a heading and detail the nature of the claim, its current status, and any mentioned potential financial impact."
                },
                "Investment Story (Positives & Risks)": {
                    "search_query": "Company strengths, competitive advantages, growth drivers, market opportunities, risk factors, challenges, and competitive threats.",
                    "system_prompt": "You are an equity research analyst. Based on the documents, construct a balanced investment story. Create two main sections in Markdown: 'Investment Positives / Strengths' and 'Key Risks & Concerns'. Under each, list 5-7 detailed bullet points with brief explanations."
                },
                "Company Strategy": {
                    "search_query": "Information on corporate strategy, business objectives, future plans, growth initiatives, market expansion, product development, and strategic priorities.",
                    "system_prompt": "You are a strategy consultant. From the provided documents, outline the company's core strategy. Structure your response in Markdown with sections for 'Vision & Mission', 'Key Strategic Pillars', and 'Growth Initiatives'. Use bullet points to detail the specifics under each section."
                }
            }
                config = ANALYSIS_CONFIG.get(analysis_type)
                if not config: return "Invalid analysis type selected.", ""
                query_vector = self.embedding_model.encode(config["search_query"]).tolist()
                query_filter = {"company": {"$in": [self.sanitize_filename(c) for c in companies]}}
                results = self.index.query(vector=query_vector, top_k=k, filter=query_filter, include_metadata=True, namespace=self.namespace)
                if not results.matches: return f"Could not find any documents related to '{analysis_type}'.", ""
                context_excerpts = [f"Excerpt from '{m.metadata['source_file']}':\n\"{m.metadata['original_text']}\"\n" for m in results.matches]
                source_docs = set(m.metadata['source_file'] for m in results.matches)
                prompt = (f"{config['system_prompt']}\n\nBase your analysis *only* on the following context:\n--- DOCUMENT CONTEXT ---\n{''.join(context_excerpts)}\n--- END CONTEXT ---\n\nProvide the analysis for '{', '.join(companies)}'.")
                analysis_content = call_deepseek_model(prompt)
                return analysis_content, ", ".join(sorted(list(source_docs)))

            def get_indexed_companies(self) -> List[str]:
                all_companies = set()
                try:
                    # Query with a dummy vector to fetch metadata from all vectors in the namespace
                    # Increase top_k to a large number to fetch more entries if needed
                    response = self.index.query(vector=[0.0]*384, top_k=1000, include_metadata=True, namespace=self.namespace)
                    for match in response['matches']:
                        if 'company' in match['metadata']:
                            all_companies.add(match['metadata']['company'])
                except Exception as e:
                    st.warning(f"Could not fetch all indexed companies for this user: {e}")
                return sorted(list(all_companies))

            def delete_company_data(self, company_name: str):
                safe_name = self.sanitize_filename(company_name)
                try:
                    self.index.delete(filter={"company": {"$eq": safe_name}}, namespace=self.namespace)
                    st.success(f"Successfully deleted all data for **{company_name}**.")
                except Exception as e:
                    st.error(f"Failed to delete data for {company_name}: {e}")
        # --- End of inner class definition ---

        try:
            return PortfolioAgent(user_id=user_id, index_name="portfolio-agent")
        except Exception as e:
            st.error(f"Failed to initialize Portfolio Agent: {e}")
            return None

    # This is the line that will now work correctly
    agent = load_agent(user_id=user_id)
    if not agent:
        st.stop()

    # --- Streamlit UI for the Portfolio Agent ---
    st.subheader("📁 Index New Company Documents")
    
    # FIXED: This block was incorrectly indented. It has been moved to the correct level.
    with st.form("indexing_form", clear_on_submit=True):
        new_company = st.text_input("Company Name", placeholder="e.g., RTX Corp.")
        new_docs = st.file_uploader("Upload Documents (PDF, DOCX, TXT)", type=["pdf", "docx", "txt"], accept_multiple_files=True)
        if st.form_submit_button("Index Documents", type="primary"):
            if new_company and new_docs:
                agent.add_documents(new_company, new_docs)
                st.cache_resource.clear() # Clear cache to force reload of agent state
                st.rerun()
            else:
                st.warning("Please provide a company name and at least one document.")

    st.markdown("---")
    st.subheader("🔍 Analyze & Manage Companies")

    indexed_companies = agent.get_indexed_companies()
    if not indexed_companies:
        st.info("No companies have been indexed for your account yet.")
    else:
        st.markdown("#### Run Analysis")
        selected_companies = st.multiselect("Select Company/Companies to Analyze", options=indexed_companies, default=indexed_companies[0] if indexed_companies else [])
        
        analysis_options = [
            "Quick Company Note",
            "Investment Story (Positives & Risks)",
            "Debt Details",
            "Litigations and Court Cases/Claims",
            "Company Strategy",
            "Custom Query"
        ]
        analysis_choice = st.selectbox("Select Analysis Type", options=analysis_options)

        user_query = ""
        if analysis_choice == "Custom Query":
            user_query = st.text_area("Ask a question about the selected companies' documents")

        if st.button("🚀 Run Analysis", use_container_width=True):
            if not selected_companies:
                st.warning("Please select at least one company to analyze.")
            else:
                with st.spinner(f"Running '{analysis_choice}' analysis for {', '.join(selected_companies)}... This may take a few minutes for detailed notes."):
                    if analysis_choice == "Custom Query":
                        if not user_query.strip():
                            st.warning("Please enter a question for the custom query.")
                        else:
                            answer, sources = agent.query(user_query, selected_companies)
                            st.markdown(f"### Answer\n{answer}")
                            st.caption(f"Sources: {sources}")
                            structured_answer = [("Custom Query Response", answer)]
                            word_bytes = markdown_to_word_bytes(structured_answer, "Custom Query")
                            st.download_button(
                                label="📥 Download as Word (.docx)",
                                data=word_bytes,
                                file_name="Custom_Query_Analysis.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                            )
                    else:
                        analysis_md, sources = agent.get_predefined_analysis(analysis_choice, selected_companies)
                        if "Error:" in analysis_md or "Could not find" in analysis_md:
                            st.error(analysis_md)
                        else:
                            structured_report = parse_markdown_to_structure(analysis_md)
                            if not structured_report:
                                st.error("Failed to parse the analysis from the AI model. The response might be empty or malformed.")
                            else:
                                company_name_for_doc = selected_companies[0] if len(selected_companies) == 1 else "Multiple Companies"
                                report_html = format_analysis_as_html(structured_report, analysis_choice, sources)
                                st.markdown(report_html, unsafe_allow_html=True)

                                st.markdown("---")
                                d1, d2 = st.columns(2)
                                
                                word_bytes = markdown_to_word_bytes(structured_report, company_name_for_doc)
                                safe_filename = re.sub(r'[\s/]', '_', analysis_choice)

                                d1.download_button(
                                    label="📥 Download as Word (.docx)",
                                    data=word_bytes,
                                    file_name=f"{safe_filename}_{company_name_for_doc}.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                                )
                                d2.download_button(
                                    label="📥 Download as HTML (.html)",
                                    data=report_html.encode("utf-8"),
                                    file_name=f"{safe_filename}_{company_name_for_doc}.html",
                                    mime="text/html"
                                )

        st.markdown("---")
        st.markdown("#### Manage Data")
        
        # CHANGED: Removed st.expander to prevent icon text issue
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
# 8. MAIN APP ROUTER (CORRECTED AND COMPLETE)
# ==============================================================================
def main():
    """
    Main function to run the Streamlit app with authentication and routing.
    """
    # This must be the first command for the page to render correctly
    if not authentication_ui():
        st.stop()  # Stop the app if the user is not logged in

    # --- Sidebar Definition ---
    with st.sidebar:
        st.title("Aranca Financial Suite")
        # Display the user's email, which is stored in 'username' of session_state
        st.write(f"Welcome, **{st.session_state.username}**") 
        st.markdown("---")

        app_mode = st.radio(
            "Choose a tool:",
            [
                "🏠 Welcome",
                "Pre-IPO Investment Memo Generator",
                "DCF Ginny",
                "Special Situations Analyzer",
                "ESG Analyzer",
                "Portfolio Agent",
                "Tariff Impact Tracker"
            ],
            key="app_tool_choice"
        )
        st.markdown("---")

        # --- NEW: Whitelist Manager UI ---
        whitelist_manager_ui()
        st.markdown("---")
        
        if st.button("Logout"):
            # Clear all session state on logout
            for key in st.session_state.keys():
                del st.session_state[key]
            st.rerun()
            
        st.info("App powered by Aranca.")

    st.markdown("---") 

    # --- Router Logic ---
    if app_mode == "Pre-IPO Investment Memo Generator":
        investment_memo_app()
    elif app_mode == "DCF Ginny":
        dcf_agent_app(client=openai_client, FMP_API_KEY=FMP_API_KEY)
    elif app_mode == "Special Situations Analyzer":
        special_situations_app()
    elif app_mode == "ESG Analyzer":
        esg_analyzer_app()
    elif app_mode == "Portfolio Agent":
        # Pass the logged-in user's email as the unique ID for the agent
        portfolio_agent_app(user_id=st.session_state.username) 
    elif app_mode == "Tariff Impact Tracker":
        # The logo_base64 variable is defined globally, so this works
        tariff_impact_tracker_app(DEEPSEEK_API_KEY=DEEPSEEK_API_KEY, FMP_API_KEY=FMP_API_KEY, logo_base64_string=logo_base64)
    else: 
        st.markdown('<p class="welcome-subtitle">A unified platform for advanced financial analysis.</p>', unsafe_allow_html=True)
        st.info("👈 **Select an agent from the sidebar to begin.**")

        st.subheader("Available Agents")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("##### 📝 Pre-IPO Investment Memo")
            st.markdown("Upload a DRHP/IPO PDF to automatically generate a detailed investment memo and perform Q&A.", help="Uses LLMs to parse and structure information from prospectus documents.")
            st.markdown("##### 📊 Special Situations Analyzer")
            st.markdown("Analyze events like M&A, spin-offs, and activist campaigns by uploading relevant documents to generate a summary memo.", help="Ideal for event-driven investment strategies.")
            
        with c2:
            st.markdown("##### 📈 DCF Ginny")
            st.markdown("Generate a document-driven Discounted Cash Flow (DCF) analysis using public data or your own financials.", help="Combines quantitative data with qualitative insights from documents.")
            st.markdown("##### 🌍 ESG Analyzer")
            st.markdown("Extract and compare key ESG metrics from sustainability reports to benchmark corporate performance.", help="Provides a quick overview of Environmental, Social, and Governance factors.")
        
        with c3:
            st.markdown("##### 🗂️ Portfolio Agent") 
            st.markdown("Index company-specific documents (10-Ks, earnings calls) and perform Q&A across your entire portfolio.", help="A persistent knowledge base for your covered companies.")
            st.markdown("##### 📈 Tariff Impact Tracker")
            st.markdown("Analyze earnings calls or filings to extract mentions of tariffs and their financial impact.", help="Quickly gauge a company's exposure and sentiment towards trade duties.")


if __name__ == "__main__":
    main()