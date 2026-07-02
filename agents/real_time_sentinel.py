"""Real-Time Sentinel.

Compliance / tail-risk warning view (Azure OpenAI; currently backed largely by
simulated data). The client is passed in by the router.
"""

import os

from openai import AzureOpenAI
from llm import llm
from utils.net import http_post, http_get


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
                news_data = http_get(news_url).json()
                if news_data and isinstance(news_data, list):
                    for item in news_data:
                        # Use LLM to check for MNPI proxy
                        prompt = f"Does the following news headline for {ticker} contain any information that could be considered material non-public information (MNPI) for a public company? Answer 'Yes' or 'No' and provide a brief reason.\n\nHeadline: {item['title']}"
                        mnpi_reply = llm.chat([{"role": "user", "content": prompt}], provider="azure")
                        if "yes" in mnpi_reply.lower():
                            compliance_findings[ticker]["news_mnpi"].append(f"**{item['title']}** - Potential MNPI: {mnpi_reply}")

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
