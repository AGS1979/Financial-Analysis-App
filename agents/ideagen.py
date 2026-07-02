"""Agent IdeaGen.

Turns an investment theme into validated tickers and deep-dive dossiers
(EODHD + FMP + Azure OpenAI).
"""

from config import require_env
from utils.net import http_post, http_get


def investment_pipeline_agent():
    """
    A robust, multi-stage, AI-powered investment research pipeline.
    It uses an intelligent "Validate-then-Filter" workflow for superior relevance.
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
    import os

    # --- (Previous helper code remains the same) ---

    COUNTRY_EQUIVALENCE = {
        "China": ["China", "Hong Kong"]
    }

    COUNTRY_CURRENCY_MAP = {
        "USA": "USD", "India": "INR", "Germany": "EUR", "France": "EUR",
        "Italy": "EUR", "Spain": "EUR", "UK": "GBP", "China": "CNY",
        "Hong Kong": "HKD", "Taiwan": "TWD", "South Africa": "ZAR",
        "Brazil": "BRL", "Chile": "CLP", "Mexico": "MXN"
    }

    st.markdown("### 💡 Agent IdeaGen")
    st.markdown("Define a theme. The agent will brainstorm ideas, find the correct tickers, validate them, and perform a deep-dive analysis.")

    _cfg = require_env(
        "EODHD_API_KEY", "FMP_API_KEY", "AZURE_OPENAI_KEY",
        "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT_NAME",
    )
    eodhd_api_key = _cfg["EODHD_API_KEY"]
    fmp_api_key = _cfg["FMP_API_KEY"]
    client = AzureOpenAI(
        api_key=_cfg["AZURE_OPENAI_KEY"],
        api_version="2024-02-01",
        azure_endpoint=_cfg["AZURE_OPENAI_ENDPOINT"],
    )
    llm_deployment_name = _cfg["AZURE_OPENAI_DEPLOYMENT_NAME"]

    # --- (Functions get_theme_sectors, get_company_ideas, get_exchange_rate, validate_ticker, filter_companies_by_theme_relevance remain the same) ---
    def get_theme_sectors(theme: str, client: AzureOpenAI, llm_deployment_name: str) -> list:
        st.info(f"**(LIVE) Step 1A: Agent is identifying guideline sectors for '{theme}'...")
        prompt = f"""
        You are a highly accurate market analyst specializing in GICS sectors. For the investment theme "{theme}", identify up to 5 GICS sectors that are most directly relevant. These will be used as guidelines.
        Return a JSON object with a single key "sectors" containing a list of strings.
        Example: {{"sectors": ["Information Technology", "Industrials"]}}
        """
        try:
            response = client.chat.completions.create(model=llm_deployment_name, messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"}, temperature=0.0)
            sectors = json.loads(response.choices[0].message.content).get('sectors', [])
            st.success(f"Identified guideline sectors: **{', '.join(sectors)}**")
            return sectors
        except Exception: return None

    def get_company_ideas(theme: str, sectors: list, country: str, client: AzureOpenAI, llm_deployment_name: str) -> list:
        st.info(f"**(LIVE) Step 1B: Agent is generating a broad list of potential companies for '{theme}'...**")
        prompt = f"""
        As a financial analyst, generate a comprehensive list of up to 30 public companies relevant to the theme "{theme}".
        The focus is on companies primarily operating in or serving the **{country}** market.
        **CRITICAL INSTRUCTIONS for Ticker Formatting:**
        1.  You MUST provide the ticker symbol followed by the correct EODHD/FMP exchange code (e.g., .MI for Borsa Italiana).
        2.  **Examples for Italy:** Enel is 'ENEL.MI', Intesa Sanpaolo is 'ISP.MI'.
        3.  **General Examples:** Apple is 'AAPL.US', Volkswagen is 'VOW3.F', Tencent is '0700.HK'. Chinese stocks listed on Shanghai Stock Exchange end with '.SS' and those on Shenzen Stock Exchange end with '.SZ'
        Return ONLY a single comma-separated string of the correct ticker symbols, sorted alphabetically.
        """
        try:
            response = client.chat.completions.create(model=llm_deployment_name, messages=[{"role": "user", "content": prompt}], temperature=0.0)
            content = response.choices[0].message.content
            cleaned_content = re.sub(r'```.*?\n|```', '', content).strip()
            tickers = sorted(list(set([t.strip() for t in cleaned_content.split(',') if t.strip()])))
            st.info(f"Agent suggested {len(tickers)} unique tickers for screening.")
            return tickers
        except Exception:
            return []

    def get_exchange_rate(from_currency: str, to_currency: str, api_key: str, cache: dict) -> float:
        """ Fetches the latest available closing exchange rate between two currencies directly. """
        if from_currency == to_currency: return 1.0
        cache_key = f"{from_currency}-{to_currency}"
        if cache_key in cache: return cache[cache_key]
        ticker = f"{from_currency}{to_currency}.FOREX"
        url = f"https://eodhistoricaldata.com/api/eod/{ticker}?api_token={api_key}&fmt=json&order=d&limit=1"
        try:
            response = http_get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            if not data or not isinstance(data, list): return 1.0
            rate = float(data[0].get('close', 1.0))
            if rate == 0: return 1.0
            cache[cache_key] = rate
            return rate
        except Exception: return 1.0

    def validate_ticker(ticker_full: str, filters: dict, eodhd_api_key: str, fmp_api_key: str, cache: dict) -> (str, dict):
        try:
            url = f"https://eodhistoricaldata.com/api/fundamentals/{ticker_full}?api_token={eodhd_api_key}"
            response = http_get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                market_cap = data.get('Highlights', {}).get('MarketCapitalization')
                div_yield = data.get('Highlights', {}).get('DividendYield', 0.0) or 0.0
                currency = data.get('General', {}).get('CurrencyCode')
                company_name = data.get('General', {}).get('Name')
                sector = data.get('General', {}).get('Sector', 'N/A')
                code_parts = ticker_full.split('.')
                code = code_parts[0]
                exchange = code_parts[1] if len(code_parts) > 1 else ''
                if all([market_cap, currency, company_name]):
                    rate_local_to_usd = get_exchange_rate(currency, "USD", eodhd_api_key, cache)
                    market_cap_usd = float(market_cap) * rate_local_to_usd
                    mkt_cap_filter_usd = filters["market_cap_min"] * 1e6
                    if market_cap_usd < mkt_cap_filter_usd: return "FAIL_MCAP", {}
                    if div_yield < (filters["dividend_yield_min"] / 100): return "FAIL_DIVIDEND", {}
                    return "PASS", {"code": code, "name": company_name, "exchange": exchange, "sector": sector, "market_capitalization_local": market_cap, "dividend_yield": div_yield}
        except Exception: pass
        try:
            profile_url = f"https://financialmodelingprep.com/api/v3/profile/{ticker_full}?apikey={fmp_api_key}"
            profile_res = http_get(profile_url, timeout=10)
            if profile_res.status_code != 200 or not profile_res.json(): raise ValueError("FMP Profile failed.")
            profile_data = profile_res.json()[0]
            market_cap, currency, company_name = profile_data.get('mktCap'), profile_data.get('currency'), profile_data.get('companyName')
            ratios_url = f"https://financialmodelingprep.com/api/v3/ratios/{ticker_full}?apikey={fmp_api_key}"
            ratios_res = http_get(ratios_url, timeout=10)
            if ratios_res.status_code != 200 or not ratios_res.json(): raise ValueError("FMP Ratios failed.")
            ratios_data = ratios_res.json()[0]
            div_yield = ratios_data.get('dividendYield', 0.0) or 0.0
            code_parts = ticker_full.split('.')
            code = code_parts[0]
            exchange = code_parts[1] if len(code_parts) > 1 else ''
            if all([market_cap, currency, company_name]):
                rate_local_to_usd = get_exchange_rate(currency, "USD", eodhd_api_key, cache)
                market_cap_usd = float(market_cap) * rate_local_to_usd
                mkt_cap_filter_usd = filters["market_cap_min"] * 1e6
                if market_cap_usd < mkt_cap_filter_usd: return "FAIL_MCAP", {}
                if div_yield < (filters["dividend_yield_min"] / 100): return "FAIL_DIVIDEND", {}
                return "PASS", {"code": code, "name": company_name, "exchange": exchange, "sector": "N/A", "market_capitalization_local": market_cap, "dividend_yield": div_yield}
        except Exception: pass
        return "FAIL_ALL", {}

    def filter_companies_by_theme_relevance(companies_df: pd.DataFrame, theme: str, country: str, client: AzureOpenAI, llm_deployment_name: str, eodhd_api_key: str, fmp_api_key: str) -> list:
        st.info(f"**(LIVE) Agent is filtering {len(companies_df)} companies for thematic relevance...**")
        detailed_company_data = []
        for i, company in companies_df.iterrows():
            ticker_code = f"{company['code']}.{company['exchange']}"
            description = None
            try:
                url_eod = f"https://eodhistoricaldata.com/api/fundamentals/{ticker_code}?api_token={eodhd_api_key}"
                response_eod = http_get(url_eod, timeout=10)
                if response_eod.status_code == 200: description = response_eod.json().get('General', {}).get('Description', None)
            except Exception: pass
            if not description:
                try:
                    url_fmp = f"https://financialmodelingprep.com/api/v3/profile/{ticker_code}?apikey={fmp_api_key}"
                    response_fmp = http_get(url_fmp, timeout=10)
                    if response_fmp.status_code == 200 and response_fmp.json(): description = response_fmp.json()[0].get('description', 'No description.')
                except Exception: continue
            if description: detailed_company_data.append({"ticker": company['code'], "name": company['name'], "sector": company['sector'], "description": description[:700]})
        if not detailed_company_data: return []
        prompt = f"""
        You are a discerning expert portfolio manager. Your task is to analyze a list of companies for their direct relevance to the investment theme: "{theme}".
        Review the following JSON list of companies from **{country}**.
        **Company List:**
        ```json
        {json.dumps(detailed_company_data, indent=2)}
        ```
        **Task & Instructions:**
        1.  **Analyze Relevancy:** Carefully read each company's business description to determine its direct connection to the theme: "{theme}".
        2.  **Filter Strictly:** Select ONLY the companies whose core business is clearly and directly aligned with the theme.
        3.  **Final Output:** Return a JSON object with a single key "relevant_tickers", containing a list of ticker symbols.
        """
        try:
            response = client.chat.completions.create(model=llm_deployment_name, messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"}, temperature=0.0)
            relevant_tickers = json.loads(response.choices[0].message.content).get("relevant_tickers", [])
            st.success(f"Agent identified {len(relevant_tickers)} companies as highly relevant.")
            return relevant_tickers
        except Exception as e:
            st.error(f"Error during relevance filtering: {e}")
            return []

    def aggregate_qualitative_data_eodhd(ticker_code: str, api_key: str) -> str:
        base_url = "https://eodhistoricaldata.com/api/news"; ticker_only = ticker_code.split('.')[0]; params = {"api_token": api_key, "t": ticker_only, "limit": 50}
        try:
            response = http_get(base_url, params=params, timeout=15); response.raise_for_status(); news_data = response.json()
            if news_data and isinstance(news_data, list): return "\n".join([f"- {item['title']} ({item['date']})" for item in news_data])
            return "No recent news found."
        except Exception: return "Could not fetch recent news."
        
    # --- START OF IMPROVEMENT 1: NEW FUNCTION TO ENRICH DATA ---
    def enrich_final_companies_with_financials(df: pd.DataFrame, api_key: str) -> pd.DataFrame:
        """Enriches the final list of companies with detailed financial metrics from EODHD."""
        
        all_metrics = []
        for index, row in df.iterrows():
            ticker_code = f"{row['code']}.{row['exchange']}"
            url = f"https://eodhistoricaldata.com/api/fundamentals/{ticker_code}?api_token={api_key}"
            metrics = {}
            try:
                res = http_get(url, timeout=10)
                res.raise_for_status()
                data = res.json()
                
                highlights = data.get('Highlights', {})
                valuation = data.get('Valuation', {})
                technicals = data.get('Technicals', {})
                
                metrics['pe_ratio'] = highlights.get('PERatio')
                metrics['ps_ratio'] = highlights.get('PSRatio')
                metrics['operating_margin'] = highlights.get('OperatingMarginTTM')
                metrics['net_margin'] = highlights.get('ProfitMargin')
                metrics['revenue_growth_yoy'] = technicals.get('QuarterlyRevenueGrowthYOY')
                
            except Exception as e:
                # Silently fail, leaving metrics as None if data is unavailable
                pass
            all_metrics.append(metrics)
        
        metrics_df = pd.DataFrame(all_metrics, index=df.index)
        return pd.concat([df, metrics_df], axis=1)
    # --- END OF IMPROVEMENT 1 ---

    # --- START OF IMPROVEMENT 2: ENHANCED AI QUALITATIVE ANALYSIS ---
    def run_ai_qualitative_analysis(company_name: str, text_corpus: str, theme: str, client: AzureOpenAI, llm_deployment_name: str) -> dict:
        prompt = f"""
        As a senior equity research analyst, provide a comprehensive analysis of '{company_name}' for the investment theme '{theme}'.
        Use the provided text corpus which includes the company description and recent news headlines.

        **TEXT CORPUS:**
        ---
        {text_corpus[:25000]}
        ---

        Generate a JSON object with the following structure:
        {{
            "theme_analysis": "Provide a concise paragraph explaining how this company aligns with the investment theme. Be specific.",
            "swot_analysis": {{
                "strengths": ["List 2-3 key business strengths."],
                "weaknesses": ["List 1-2 significant weaknesses or challenges."],
                "opportunities": ["List 2-3 potential growth opportunities."],
                "threats": ["List 2-3 major external threats or risks."]
            }},
            "bull_case": "In a paragraph, summarize the primary investment thesis (the bull case). Why would an investor be optimistic?",
            "bear_case": "In a paragraph, summarize the primary counter-arguments (the bear case). What are the main risks that could lead to underperformance?",
            "recent_catalysts": "Based on the news, briefly summarize any recent events (e.g., earnings, partnerships, product launches) that could act as near-term catalysts or headwinds."
        }}
        """
        try:
            response = client.chat.completions.create(
                model=llm_deployment_name,
                messages=[{"role": "system", "content": "You are an equity analyst that only outputs structured JSON."}, {"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            st.error(f"Error in Analysis for {company_name}: {e}")
            return {}
    # --- END OF IMPROVEMENT 2 ---

    # --- START OF IMPROVEMENT 3: COMPREHENSIVE DOSSIER SYNTHESIS ---
    def synthesize_dossier(quant_data: pd.Series, qual_analysis: dict, theme: str, local_currency: str) -> dict:
        
        def format_metric(value, format_type='number'):
            if value is None or not isinstance(value, (int, float)):
                return "N/A"
            if format_type == 'percent':
                return f"{value:.2%}"
            if format_type == 'ratio':
                return f"{value:,.2f}x"
            return f"{value:,.2f}"

        quant_md = f"""
| Metric                      | Value                          |
|-----------------------------|--------------------------------|
| Market Cap ({local_currency}) | {quant_data.get('market_capitalization_local', 0) / 1e9:,.1f}B |
| Dividend Yield              | {format_metric(quant_data.get('dividend_yield'), 'percent')} |
| P/E Ratio (TTM)             | {format_metric(quant_data.get('pe_ratio'), 'ratio')} |
| P/S Ratio (TTM)             | {format_metric(quant_data.get('ps_ratio'), 'ratio')} |
| Operating Margin (TTM)      | {format_metric(quant_data.get('operating_margin'), 'percent')} |
| Net Profit Margin (TTM)     | {format_metric(quant_data.get('net_margin'), 'percent')} |
| Revenue Growth (YoY)        | {format_metric(quant_data.get('revenue_growth_yoy'), 'percent')} |
"""
        def format_swot(swot_data):
            if not swot_data or not isinstance(swot_data, dict): return "No SWOT analysis available."
            s = "\n".join([f"- {item}" for item in swot_data.get("strengths", [])])
            w = "\n".join([f"- {item}" for item in swot_data.get("weaknesses", [])])
            o = "\n".join([f"- {item}" for item in swot_data.get("opportunities", [])])
            t = "\n".join([f"- {item}" for item in swot_data.get("threats", [])])
            return f"**Strengths:**\n{s}\n\n**Weaknesses:**\n{w}\n\n**Opportunities:**\n{o}\n\n**Threats:**\n{t}"
        
        return {
            "dossier_title": f"{quant_data.get('name', 'N/A')} ({quant_data.get('code', 'N/A')}.{quant_data.get('exchange', '')})",
            "Quantitative Snapshot": quant_md,
            "Thematic Alignment": qual_analysis.get('theme_analysis', "No analysis available."),
            "SWOT Analysis": format_swot(qual_analysis.get('swot_analysis')),
            "Investment Thesis (Bull vs. Bear)": f"**The Bull Case:**\n{qual_analysis.get('bull_case', 'Not available.')}\n\n**The Bear Case:**\n{qual_analysis.get('bear_case', 'Not available.')}",
            "Recent Catalysts & Developments": qual_analysis.get('recent_catalysts', "No recent catalysts identified.")
        }
    # --- END OF IMPROVEMENT 3 ---

    def generate_final_html_report(dossier_list: list, theme: str) -> str:
        safe_theme = html.escape(theme or "...")
        styles = """<style>body{font-family:sans-serif;margin:20px;background-color:#f9fafb;color:#1f2937}.container{max-width:1200px;margin:auto}.report-header h1{font-size:2.2em;color:#111827;border-bottom:2px solid #d1d5db;padding-bottom:10px}.dossier{background-color:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:30px;margin-bottom:30px;box-shadow:0 4px 6px rgba(0,0,0,0.05)}.dossier h2{font-size:1.4em;border-bottom:1px solid #e5e7eb;padding-bottom:8px;margin-top:25px}.dossier table{width:auto;border-collapse:collapse;margin-top:15px}.dossier th,td{padding:10px 12px;border:1px solid #d1d5db;text-align:left}</style>"""
        html_body = f"<div class='report-header'><h1>Investment Idea Report</h1><h2>Theme: {safe_theme}</h2></div>"
        
        # --- DYNAMIC SECTION GENERATION FOR RICHER CONTENT ---
        for d in dossier_list:
            html_body += f"<div class='dossier'><h1>{html.escape(d.get('dossier_title', ''))}</h1>"
            sections = ["Quantitative Snapshot", "Thematic Alignment", "SWOT Analysis", "Investment Thesis (Bull vs. Bear)", "Recent Catalysts & Developments"]
            for s in sections:
                if s in d and d[s]:
                    html_body += f"<h2>{html.escape(s)}</h2>" + markdown.markdown(str(d[s]), extensions=['tables'])
            html_body += "</div>"
        return f"<!DOCTYPE html><html><head><title>IdeaGen Report</title>{styles}</head><body><div class='container'>{html_body}</div></body></html>"

    # --- (risk_and_sizing_agent remains the same, as its input dossier is now richer) ---
    def risk_and_sizing_agent(dossier: dict, client: AzureOpenAI, llm_deployment_name: str) -> dict:
        # This agent now receives a much more detailed dossier, which will improve its recommendation.
        prompt_dossier = {
            "dossier_title": dossier.get("dossier_title"),
            "Thematic Alignment": dossier.get("Thematic Alignment", "")[:1000],
            "SWOT Analysis": dossier.get("SWOT Analysis", "")[:1000],
            "Investment Thesis (Bull vs. Bear)": dossier.get("Investment Thesis (Bull vs. Bear)", "")[:1000]
        }
        prompt = f"""Analyze the investment dossier. Based on the analysis of thematic alignment, SWOT, and the bull/bear cases, recommend a position size as a percentage of a portfolio (e.g., from 1% to 10%). Return a JSON object with two keys: "position_size_recommendation" (a string like "3.5%") and "rationale" (a brief explanation for your recommendation). DOSSIER: ```json\n{json.dumps(prompt_dossier, indent=2)}\n```"""
        try:
            response = client.chat.completions.create(model=llm_deployment_name, messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"}, temperature=0.0)
            return json.loads(response.choices[0].message.content)
        except Exception as e: return {"error": f"Risk analysis failed: {e}"}

    # --- UI AND ORCHESTRATION ---
    st.subheader("Step 1: Define Your Investment Theme")
    qualitative_theme = st.text_area("**Describe the Qualitative Theme**", "Companies benefiting from the rise of Artificial Intelligence", height=75)
    st.subheader("Step 2: Define Validation Criteria")
    country_options = ["Brazil", "Chile", "China", "France", "Germany", "Hong Kong", "India", "Italy", "Mexico", "South Africa", "Spain", "Taiwan", "UK", "USA"]
    selected_country_code = st.selectbox("Target Country", options=country_options, index=country_options.index("USA"))
    col1, col2 = st.columns(2)
    with col1: mkt_cap_min = st.slider("Min Market Cap (Million USD)", 100.0, 500000.0, 1000.0, 100.0)
    with col2: dividend_yield_min = st.slider("Min Dividend Yield (%)", 0.0, 10.0, 0.0, 0.1)

    st.subheader("Step 3: Generate and Analyze Ideas")
    if st.button("🚀 Generate, Validate, and Analyze", type="primary"):
        if not qualitative_theme: st.warning("Please describe your theme."); return
        
        # --- (Orchestration logic updated to include new enrichment step) ---
        with st.spinner("Stage 1 & 2: Generating and validating initial ideas..."):
            theme_sectors = get_theme_sectors(qualitative_theme, client, llm_deployment_name)
            if not theme_sectors: st.error("Could not identify guideline sectors."); return
            company_tickers = get_company_ideas(qualitative_theme, theme_sectors, selected_country_code, client, llm_deployment_name)
            if not company_tickers: st.error("Agent returned no initial company ideas."); return
            user_filters = {"market_cap_min": mkt_cap_min, "dividend_yield_min": dividend_yield_min}
            exchange_rate_cache = {}
            quant_validated_companies = []
            progress = st.progress(0, text=f"Screening {len(company_tickers)} tickers...")
            for i, ticker in enumerate(company_tickers):
                status, result = validate_ticker(ticker, user_filters, eodhd_api_key, fmp_api_key, exchange_rate_cache)
                if status == 'PASS': quant_validated_companies.append(result)
                progress.progress((i + 1) / len(company_tickers), text=f"Screening {ticker}...")
            progress.empty()

        if not quant_validated_companies: st.warning("No companies passed initial quantitative filters."); return
        quant_df = pd.DataFrame(quant_validated_companies)
        st.info(f"Passed {len(quant_df)} companies through quantitative filters. Now running relevance check.")
        
        relevant_tickers = filter_companies_by_theme_relevance(quant_df, qualitative_theme, selected_country_code, client, llm_deployment_name, eodhd_api_key, fmp_api_key)
        if not relevant_tickers: st.warning("Agent filter found no highly relevant companies."); return
        
        # --- UPDATED ORCHESTRATION ---
        initial_final_df = quant_df[quant_df['code'].isin(relevant_tickers)].reset_index(drop=True)
        st.success(f"Final list: {len(initial_final_df)} highly relevant companies. Enriching data and performing deep-dive analysis...")
        
        # Call the new enrichment function
        final_df = enrich_final_companies_with_financials(initial_final_df, eodhd_api_key)
        
        all_dossiers = []
        with st.spinner(f"Performing deep-dive analysis on {len(final_df)} companies..."):
            local_currency = COUNTRY_CURRENCY_MAP.get(selected_country_code, "USD")
            for i, company_row in final_df.iterrows():
                company_name = company_row['name']
                ticker_code = f"{company_row['code']}.{company_row['exchange']}"
                
                # The text corpus now includes description and news
                description_url = f"https://eodhistoricaldata.com/api/fundamentals/{ticker_code}?api_token={eodhd_api_key}"
                description_text = "No description available."
                try:
                    desc_res = http_get(description_url, timeout=10)
                    if desc_res.status_code == 200: description_text = desc_res.json().get('General', {}).get('Description', 'No description available.')
                except: pass
                
                news_text = aggregate_qualitative_data_eodhd(ticker_code, eodhd_api_key)
                qualitative_corpus = f"Company Description:\n{description_text}\n\n---\n\nRecent News:\n{news_text}"
                
                qual_analysis = run_ai_qualitative_analysis(company_name, qualitative_corpus, qualitative_theme, client, llm_deployment_name)
                dossier = synthesize_dossier(company_row, qual_analysis, qualitative_theme, local_currency)
                
                # Optional: The risk/sizing agent can still be used for a final recommendation layer
                # risk_analysis = risk_and_sizing_agent(dossier, client, llm_deployment_name)
                # dossier['sizing_recommendation'] = risk_analysis 
                
                all_dossiers.append(dossier)

        if all_dossiers:
            st.success("✅ Analysis complete! Your report is ready for download.")
            final_html_report = generate_final_html_report(all_dossiers, qualitative_theme)
            safe_filename = re.sub(r'(?u)[^-\w.]', '', qualitative_theme[:40].strip().replace(' ', '_'))
            st.download_button(label="📥 Download Full HTML Report", data=final_html_report, file_name=f"IdeaGen_Report_{safe_filename}.html", mime="text/html")
        else:
            st.error("Could not generate a report for any of the validated companies.")
