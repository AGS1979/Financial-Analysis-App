import pandas as pd
import streamlit as st

def format_report_as_html(st_session_state):
    """Formats the final DCF results from session state into an HTML report."""
    company_name = st_session_state.get('dcf_company_name', 'N/A')
    ticker = st_session_state.get('dcf_ticker', 'N/A')
    analyst_memo = st_session_state.get('dcf_memo', 'Memo not available.')
    financials_df = st_session_state.get('dcf_financials', pd.DataFrame())
    dcf_results = st_session_state.get('dcf_results_data', {})
    current_price = st_session_state.get('dcf_price', 0)
    
    if not dcf_results:
        return "<h3>Error: Could not generate DCF analysis data.</h3>"

    def get_currency_symbol(t):
        if t.endswith(".L"): return "£"
        if t.endswith((".PA", ".DE", ".AS")): return "€"
        return "$"
    
    currency_symbol = get_currency_symbol(ticker)

    def num_fmt(n, pct=False, money=True):
        if pd.isna(n) or n is None: return "N/A"
        if pct: return f"{n:.2%}"
        pfx = currency_symbol if money else ""
        s = "-" if n < 0 else ""; n = abs(n)
        if n >= 1e9: return f"{s}{pfx}{n/1e9:.2f}B"
        if n >= 1e6: return f"{s}{pfx}{n/1e6:.1f}M"
        return f"{s}{pfx}{n:,.2f}"

    html = f'<div class="report-container"><h1>DCF Valuation Report for {company_name} ({ticker})</h1>'
    html += "<h2>⚖️ Valuation Summary</h2><div class='summary-cards'>"
    valuations = dcf_results.get('valuations', {})
    rationales = {k: v.get('key_driver', '') for k, v in dcf_results.get('scenario_assumptions', {}).items()}
    
    for name in ["Base", "Bull", "Bear"]:
        if name in valuations:
            val = valuations[name]
            upside = (val['Per-Share Value'] / current_price - 1) if current_price else 0
            cls, upside_cls = name.lower(), "bull-text" if upside >= 0 else "bear-text"
            html += f'<div class="card {cls}"><div class="card-title">{name} Case</div>'
            html += f'<div class="card-value">{num_fmt(val["Per-Share Value"])}</div>'
            html += f'<div class="card-upside {upside_cls}">{num_fmt(upside, pct=True, money=False)} Upside</div>'
            html += f'<div class="justification" style="margin-top:15px;"><strong>Rationale:</strong> {rationales.get(name, "")}</div></div>'
    html += '</div>'
    
    html += '<div class="memo-title">Analyst Memo</div>'
    memo_paragraphs = [f"<p>{p.strip()}</p>" for p in analyst_memo.strip().split('\n') if p.strip()]
    html += f'<div class="memo-container">{"".join(memo_paragraphs)}</div>'
    
    html += "<h2>📈 Financial Summary (Historical)</h2>"
    df_fin = financials_df.head(3).copy()
    html += df_fin.to_html(classes='report-table', index=False, formatters={col: lambda x: num_fmt(x) for col in df_fin.columns if df_fin[col].dtype in ['int64', 'float64'] and col != 'Year'})
    
    html += "<h2>📊 Free Cash Flow Forecasts</h2>"
    for name, df in dcf_results.get('forecasts', {}).items():
        html += f"<h3>{name} Case Forecast</h3>"
        display_df = df.transpose()
        html += display_df.to_html(classes='report-table', formatters={col: lambda x: num_fmt(x) for col in display_df.columns})

    html += "</div>"
    return html