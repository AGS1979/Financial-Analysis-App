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
import hashlib # For legacy SHA-256 password verification (migration only)
import hmac     # For constant-time legacy hash comparison
import bcrypt   # For password hashing
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
from datetime import datetime, timedelta, timezone
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
import config
from config import require_env, DEEPSEEK_API_URL
from utils.net import http_post, http_get
from utils.branding import get_base64_logo_image, load_logo
from utils.logging import log_audit_event, log_user_history, get_user_history
from auth.session import validate_session
from auth.ui import authentication_ui, whitelist_manager_ui
from agents.investment_memo import investment_memo_app
from agents.portfolio import portfolio_agent_app
from agents.dcf import dcf_agent_app
from agents.special_situations import special_situations_app
from agents.esg import esg_analyzer_app
from agents.pe import pe_agent_app_azure
from agents.credit import agent_credit_app_azure
from agents.sentinel import agent_sentinel_app
from agents.ideagen import investment_pipeline_agent
from agents.real_time_sentinel import real_time_sentinel_app
from agents.commodity import commodity_forecasting_agent
from agents.risk_correlator import portfolio_risk_correlator_app
from agents.model_integrity import model_integrity_agent_app
from agents.tariff import tariff_impact_tracker_app


# --- Must be the first st.* command ---
st.set_page_config(
    page_title="ARANC'AI'",
    page_icon="📈",  # Adds a browser tab icon
    layout="wide"
)

# ==============================================================================
# APP BOOTSTRAP — stylesheet, config validation, and shared clients.
# Auth/config/util logic now lives in the auth/ and utils/ packages and config.py.
# ==============================================================================

def _inject_css():
    """Load the app stylesheet from static/styles.css once."""
    css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "styles.css")
    with open(css_path, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


_inject_css()

# Validate the env vars required to boot, then build the shared clients (config.py).
config.validate_core_config()
openai_client = config.get_azure_client()
conn = config.get_conn()

# Re-export core secrets as module globals for the agent functions defined below.
DEEPSEEK_API_KEY = config.DEEPSEEK_API_KEY
FMP_API_KEY = config.FMP_API_KEY
OPENAI_API_KEY = config.OPENAI_API_KEY

# --- Page header ---
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

LOGO_OBJECT = load_logo()



# ==============================================================================
# HISTORY PAGE + ROUTER
# ==============================================================================

def show_history_page():
    """
    Renders a full page for the user's recent activity, using the app's CSS.
    """
    st.markdown("### 📜 Your Recent Activity")
    st.markdown("Here is a log of your most recent actions on the platform.")
    st.markdown("---")

    # Fetch a larger number of items since it's a full page
    history_items = get_user_history(limit=25) 

    if not history_items:
        st.info("You have no recent activity.")
    else:
        html_items = []
        for item in history_items:
            # Format the timestamp
            timestamp = pd.to_datetime(item['created_at']).strftime('%b %d, %Y at %I:%M %p')
            
            tags_html = ""
            
            # Action Tag
            if item.get('action_type'):
                safe_action = html.escape(item["action_type"])
                tags_html += f'<div class="history-tag" title="{safe_action}"><span class="history-tag-label">Action:</span> {safe_action}</div>'
            
            # Target Tag
            if item.get('target_id'):
                safe_target = html.escape(item["target_id"])
                tags_html += f'<div class="history-tag" title="{safe_target}"><span class="history-tag-label">Target:</span> {safe_target}</div>'
            
            # Parameters Tags
            if item.get('details'):
                clean_details = {k: v for k, v in item['details'].items() if v is not None}
                for key, value in clean_details.items():
                    clean_key = html.escape(key.replace('_', ' ').title())
                    value_str = html.escape(str(value))
                    tags_html += f'<div class="history-tag" title="{value_str}"><span class="history-tag-label">{clean_key}:</span> {value_str}</div>'

            # Assemble the full HTML for this one card
            safe_summary = html.escape(item['summary'])
            html_items.append(f"""
            <div class="history-item">
                <div class="history-summary">{safe_summary}</div>
                <div class="history-timestamp">Performed on {timestamp}</div>
                <div class="history-tags">
                    {tags_html}
                </div>
            </div>
            """)
        
        # Join all cards into a single HTML string
        full_history_html = "\n".join(html_items)
        
        # Render the HTML directly to the page. The page will scroll naturally.
        st.markdown(full_history_html, unsafe_allow_html=True)

# ==============================================================================
# 16. MAIN APP ROUTER (CORRECTED AND COMPLETE)
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
    elif app_mode == "Portfolio Risk Correlator":
        portfolio_risk_correlator_app(client=openai_client)
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
    elif app_mode == "Commodity Forecaster":
        commodity_forecasting_agent(client=openai_client)
    elif app_mode == "History":
        show_history_page()
    else: # This is the "🏠 Welcome" page
        st.markdown('<p class="welcome-subtitle">A unified platform for advanced financial analysis.</p>', unsafe_allow_html=True)
        st.info("👈 **Select an agent from the sidebar to begin.**")
        
        # --- The history section has been removed ---
        
        st.subheader("Available Agents")

        # Define all possible agent cards in a master list
        ALL_AGENT_DETAILS = [
            {"name": "History", "title": "📜 History", "description": "View a full log of your recent activity and generated analyses."},
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
            {"name": "Commodity Forecaster", "title": "🌾 Commodity Forecaster", "description": "Forecast commodity prices using time-series data, technical indicators, and news sentiment analysis."},
            {"name": "Real-Time Sentinel", "title": "🚨 Real-Time Sentinel", "description": "Provides a real-time warning system for compliance issues and tail risks."},
            {"name": "Portfolio Risk Correlator", "title": "🧬 Portfolio Risk Correlator", "description": "Upload documents for multiple companies to identify and visualize hidden, correlated risks across your portfolio."}
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
            </head>            <body>
                <div class="agent-grid">
                    {''.join(card_html_list)}
                </div>
            </body>
        </html>
        """
        
        num_rows = (len(visible_agent_details) + 2) // 3
        height_px = num_rows * 220
        
        components.html(full_html, height=height_px)

if __name__ == "__main__":
    main()