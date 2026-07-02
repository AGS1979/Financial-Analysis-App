"""Agent Sentinel.

On-demand portfolio briefing of recent news and SEC filings (FMP + Azure OpenAI).
"""

from config import require_env
from llm import llm
from utils.net import http_post, http_get


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
    _cfg = require_env("FMP_API_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_KEY", "AZURE_OPENAI_DEPLOYMENT_NAME")
    FMP_API_KEY = _cfg["FMP_API_KEY"]
    openai_endpoint = _cfg["AZURE_OPENAI_ENDPOINT"]
    openai_key = _cfg["AZURE_OPENAI_KEY"]
    openai_deployment_name = _cfg["AZURE_OPENAI_DEPLOYMENT_NAME"]

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
            news_response = http_get(news_url).json()
            if news_response and isinstance(news_response, list):
                for item in news_response:
                    if item.get('symbol') in company_data:
                        company_data[item['symbol']]['news'].append(f"- {item.get('title')} (Source: {item.get('site')}, Published: {item.get('publishedDate')})")
            
            for ticker in tickers_list:
                filings_url = f"https://financialmodelingprep.com/api/v3/sec_filings/{ticker}?type=8-K&from={date_from}&to={date_to}&limit=5&apikey={FMP_API_KEY}"
                filings_response = http_get(filings_url).json()
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
            return llm.chat(
                [
                    {"role": "system", "content": "You are a senior investment analyst responsible for portfolio monitoring."},
                    {"role": "user", "content": prompt},
                ],
                provider="azure",
                model=openai_deployment_name,
            )
        except Exception as e:
            return f"## Error\n\n**Error during analysis:** {e}"

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
