"""DCF Ginny.

Document-driven discounted-cash-flow valuation: pulls financials (FMP), builds
base/bull/bear forecasts, and writes an analyst memo via Azure OpenAI. The client
and FMP key are passed in by the router.
"""

import json
import pandas as pd
import requests
import streamlit as st

from PyPDF2 import PdfReader
from openai import OpenAI
from llm import llm
from utils.logging import log_audit_event, log_user_history, get_user_history
from utils.net import http_post, http_get


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
            try: return http_get(url).json()
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
            return llm.chat([{"role": "user", "content": prompt}], provider="azure", model="gpt-4o-mini", temperature=0).strip().upper().split()[0].strip('".:,')
        except Exception as e:
            st.error(f"Could not retrieve ticker: {e}"); return None

    @st.cache_data(ttl=900, show_spinner=False)
    def get_current_price(ticker):
        url = f"https://financialmodelingprep.com/api/v3/quote-short/{ticker}?apikey={FMP_API_KEY}"
        try:
            r = http_get(url).json()
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
            items = http_get(url).json()
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
            result = json.loads(llm.chat([{"role": "user", "content": prompt}], provider="azure", model="gpt-4o", response_format={"type": "json_object"}, temperature=0.2))
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
            return json.loads(llm.chat([{"role": "user", "content": prompt}], provider="azure", model="gpt-4o", response_format={"type": "json_object"}, temperature=0.0))
        except Exception as e:
            st.error(f"Error generating scenarios: {e}"); return None

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
        c1.text_input("Stock Ticker (e.g., 'AAPL', 'BA.L')", key="dcf_ticker_input", help="Provide the exact ticker. This will override the Agent search.")
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

            # --- ADD AUDIT LOG CALL ---
            log_audit_event(
                action_type="RUN_DCF_ANALYSIS", 
                status="STARTED",
                target_id=st.session_state.dcf_company,
                details={
                    "wacc": st.session_state.dcf_wacc,
                    "data_source": st.session_state.dcf_data_source
                }
            )
            # ---

            # --- START: NEW HISTORY LOG CALL ---
            log_user_history(
                action_type="DCF Analysis",
                target_id=st.session_state.dcf_company,
                summary=f"Ran DCF Analysis for {st.session_state.dcf_company}",
                details={
                    "wacc": st.session_state.dcf_wacc,
                    "data_source": st.session_state.dcf_data_source,
                    "primary_doc": st.session_state.get("dcf_primary_doc").name if st.session_state.get("dcf_primary_doc") else None
                }
            )
            # --- END: NEW HISTORY LOG CALL ---

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
                # --- ADD AUDIT LOG CALL ---
                log_audit_event(action_type="RUN_DCF_ANALYSIS", status="FAILURE", target_id=st.session_state.dcf_company_name, details={"error": "Could not determine ticker"})
                # ---
                st.session_state.dcf_step = "initial"
                st.rerun()

            price = get_current_price(ticker)
            if st.session_state.dcf_data_source == "Upload Financials (CSV/Excel)":
                uploaded_file = st.session_state.get("dcf_upload")
                if not uploaded_file:
                    st.error("❌ Please upload a financials file.")
                    # --- ADD AUDIT LOG CALL ---
                    log_audit_event(action_type="RUN_DCF_ANALYSIS", status="FAILURE", target_id=st.session_state.dcf_company_name, details={"error": "User did not upload financials file"})
                    # ---
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
                    # --- ADD AUDIT LOG CALL ---
                    log_audit_event(action_type="DCF_STEP_ASSUMPTIONS", status="SUCCESS", target_id=st.session_state.dcf_company_name)
                    # ---
                    st.session_state.dcf_assumptions = assumptions
                    st.session_state.dcf_step = "review"
                    st.rerun()
                else:
                    st.error("❌ Could not generate assumptions.")
                    # --- ADD AUDIT LOG CALL ---
                    log_audit_event(action_type="DCF_STEP_ASSUMPTIONS", status="FAILURE", target_id=st.session_state.dcf_company_name, details={"error": "Could not generate assumptions"})
                    # ---
                    st.session_state.dcf_step = "initial"
                    st.rerun()
            else:
                st.error(f"❌ Could not fetch complete financial data for {ticker}.")
                # --- ADD AUDIT LOG CALL ---
                log_audit_event(action_type="DCF_STEP_DATA_FETCH", status="FAILURE", target_id=st.session_state.dcf_company_name, details={"error": f"Could not fetch FMP/financial data for {ticker}"})
                # ---
                st.session_state.dcf_step = "initial"
                st.rerun()

    # --- Block 3: Reviewing assumptions ---
    if st.session_state.dcf_step == "review":
        st.subheader("🔬 Review AI-Generated Assumptions")
        st.markdown("The Agent has generated forecasts based on its analysis. Review them below and revise if necessary.")
        
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
        try: # <<< NEW: Added try/except block for safety
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
                    
                    # --- ADD AUDIT LOG CALL (SUCCESS) ---
                    log_audit_event(
                        action_type="RUN_DCF_ANALYSIS", 
                        status="SUCCESS",
                        target_id=st.session_state.dcf_company_name,
                        details={"valuation_method": st.session_state.dcf_valuation_method}
                    )
                    # ---
        except Exception as e:
            # --- ADD AUDIT LOG CALL (FAILURE) ---
            log_audit_event(
                action_type="RUN_DCF_ANALYSIS", 
                status="FAILURE",
                target_id=st.session_state.dcf_company_name,
                details={"error_step": "processing_final", "error_message": str(e)}
            )
            # ---
            st.error(f"An error occurred during final calculation: {e}")
            st.session_state.dcf_step = "initial" # Reset on failure

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
            # --- ADD AUDIT LOG CALL ---
            log_audit_event(
                action_type="DCF_RESET_ANALYSIS", 
                status="SUCCESS",
                target_id=st.session_state.get('dcf_company_name', 'N/A')
            )
            # ---
            keys_to_delete = [key for key in st.session_state.keys() if key.startswith('dcf_')]
            for key in keys_to_delete:
                del st.session_state[key]
            st.session_state.dcf_step = "initial"
            st.rerun()
