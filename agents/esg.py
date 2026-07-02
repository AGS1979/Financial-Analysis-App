"""ESG Analyzer.

Extracts and benchmarks ESG metrics from sustainability reports (Azure OpenAI),
with a comparison dashboard and report.
"""

import os
import streamlit as st

from llm import llm
from utils.logging import log_audit_event, log_user_history, get_user_history


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
        Stage 2: Get KPIs and takeaways for each pillar separately using specialized prompts.
        """
        if not text.strip():
            return {"error": "No text provided for analysis."}
            
        try:
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
                summary_and_scores = json.loads(llm.chat([{"role": "user", "content": prompt_stage1}], provider="azure", model=deployment_name, response_format={"type": "json_object"}, temperature=0.1))
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
                    # Default prompt for Environmental and Social pillars
                    prompt_stage2_base = f"""
                    You are an ESG analyst focused on the '{pillar.title()}' pillar. From the provided ESG report text, perform the following tasks:
                    1.  Identify the 4-5 most relevant and quantifiable Key Performance Indicators (KPIs). For each KPI, provide its icon, title, value, unit, a brief context, and a rating ('Positive', 'Neutral', 'Negative').
                    2.  Provide one or two key takeaways summarizing the company's performance.
                    3.  Extract a list of detailed insights, where each insight is an object with "subcategory" and "detail".

                    Return a single, valid JSON object with three keys: "kpis" (a list of objects), "takeaways" (a list of strings), and "insights" (a list of objects).
                    """

                    # Specialized, more restrictive prompt for the Governance pillar
                    prompt_stage2_governance = """
                    You are a specialist Governance analyst. From the provided ESG report text, perform the following tasks focusing strictly on Governance topics.
                    
                    **Instructions for Governance KPIs:**
                    - Identify the 4-5 most quantifiable Key Performance Indicators (KPIs) related EXCLUSIVELY to corporate governance.
                    - Focus ONLY on topics like: **anti-corruption training, business ethics, data protection (e.g., having a DPO), board of directors composition, supplier audits, lobbying, and shareholder rights.**
                    - **CRITICAL:** DO NOT include any KPIs related to environmental topics such as packaging, waste, food waste, water usage, CO2 emissions, or sustainable agriculture. These are NOT governance KPIs.

                    For each KPI, provide its icon, title, value, unit, a brief context, and a rating ('Positive', 'Neutral', 'Negative').
                    
                    **Other Tasks:**
                    1.  Provide one or two key takeaways summarizing the company's governance performance.
                    2.  Extract a list of detailed insights related to governance, where each insight is an object with "subcategory" and "detail".

                    Return a single, valid JSON object with three keys: "kpis", "takeaways", and "insights".
                    """

                    # Select the appropriate prompt based on the pillar
                    if pillar == "governance":
                        prompt_stage2 = prompt_stage2_governance + f"\n\nDOCUMENT TEXT:\n---\n{text[:80000]}\n---"
                    else:
                        prompt_stage2 = prompt_stage2_base + f"\n\nDOCUMENT TEXT:\n---\n{text[:80000]}\n---"
                    
                    pillar_data = json.loads(llm.chat([{"role": "user", "content": prompt_stage2}], provider="azure", model=deployment_name, response_format={"type": "json_object"}, temperature=0.1))
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
                # --- ADD AUDIT LOG CALL ---
                log_audit_event(
                    action_type="ESG_DASHBOARD_GEN",
                    status="STARTED",
                    target_id=company_dash,
                    details={"file": file_dash.name}
                )
                # ---
                text = extract_text_from_pdf_esg(file_dash)
                if text:
                    esg_data = analyze_esg_in_stages(text)
                    if "error" in esg_data: 
                        # --- ADD AUDIT LOG CALL ---
                        log_audit_event(
                            action_type="ESG_DASHBOARD_GEN",
                            status="FAILURE",
                            target_id=company_dash,
                            details={"error": esg_data['error']}
                        )
                        # ---
                        st.error(f"Analysis failed: {esg_data['error']}")
                    else:
                        st.success("Dashboard generated successfully!")
                        # --- ADD AUDIT LOG CALL ---
                        log_audit_event(action_type="ESG_DASHBOARD_GEN", status="SUCCESS", target_id=company_dash)
                        # ---
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
                # --- ADD AUDIT LOG CALL ---
                log_audit_event(
                    action_type="ESG_REPORT_GEN",
                    status="STARTED",
                    target_id=company_classic,
                    details={"file": file_classic.name}
                )
                # ---
                text = extract_text_from_pdf_esg(file_classic)
                if text:
                    esg_data = analyze_esg_in_stages(text) # Use the same robust function
                    if "error" in esg_data: 
                        # --- ADD AUDIT LOG CALL ---
                        log_audit_event(
                            action_type="ESG_REPORT_GEN",
                            status="FAILURE",
                            target_id=company_classic,
                            details={"error": esg_data['error']}
                        )
                        # ---
                        st.error(f"Analysis failed: {esg_data['error']}")
                    else:
                        st.success("Analysis complete!")
                        # --- ADD AUDIT LOG CALL ---
                        log_audit_event(action_type="ESG_REPORT_GEN", status="SUCCESS", target_id=company_classic)
                        # ---
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
                # --- ADD AUDIT LOG CALL ---
                log_audit_event(
                    action_type="ESG_COMPARE_REPORTS",
                    status="STARTED",
                    target_id="Multiple Files",
                    details={"files": [f.name for f in uploaded_html_files]}
                )
                # ---
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
                    # --- ADD AUDIT LOG CALL ---
                    log_audit_event(action_type="ESG_COMPARE_REPORTS", status="SUCCESS", target_id="Multiple Files")
                    # ---
                    st.download_button("📥 Download Comparison Report", compare_content, compare_filename, "text/html", use_container_width=True)
                    st.markdown("### Comparison Preview:")
                    st.components.v1.html(compare_content.decode(), height=800, scrolling=True)
