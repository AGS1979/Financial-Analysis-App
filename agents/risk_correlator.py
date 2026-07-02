"""Portfolio Risk Correlator.

Extracts risks across multiple companies' documents and clusters correlated risks
(SentenceTransformer + hdbscan; DeepSeek for extraction and cluster naming).
"""

from openai import AzureOpenAI
from utils.net import http_post, http_get


def portfolio_risk_correlator_app(client: "AzureOpenAI"): # The 'client' parameter is no longer used but kept for consistency
    """
    An agent to identify and visualize correlated risks across a portfolio of companies
    by clustering risk factors extracted from uploaded documents.
    """
    import hdbscan
    import numpy as np
    from sentence_transformers import SentenceTransformer
    import streamlit as st
    import fitz  # PyMuPDF
    import json
    import os
    import requests # Added for DeepSeek API calls
    from collections import defaultdict
    from sklearn.cluster import AgglomerativeClustering

    st.markdown("### 🧬 Portfolio Risk Correlator")
    st.markdown(
        "Upload annual reports or presentations for your portfolio companies to uncover hidden, correlated risks."
    )

    # --- AGENT CONFIG (ADAPTED FOR DEEPSEEK) ---
    try:
        DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
        if not DEEPSEEK_API_KEY:
            st.error("DeepSeek API key not found. Please add it to your Streamlit secrets.")
            st.stop()
    except Exception as e:
        st.error(f"Configuration error: {e}")
        st.stop()
        
    DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

    # --- AGENT-SPECIFIC HELPER FUNCTIONS ---

    @st.cache_data(show_spinner=False)
    def extract_text_from_pdf_bytes(file_bytes: bytes, filename: str) -> str:
        """Extracts text from a PDF file provided as bytes."""
        try:
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                return "\n".join(page.get_text() for page in doc)
        except Exception as e:
            st.warning(f"Could not read {filename}: {e}")
            return ""

    @st.cache_data(show_spinner=False)
    def extract_and_score_risks_with_llm(_full_text: str) -> list[dict]:
        """
        Uses DeepSeek to pre-process a document, extract risk-related sentences,
        and score them in a single call.
        """
        if not _full_text or len(_full_text) < 200:
            return []

        chunk_size = 80000
        chunks = [_full_text[i:i + chunk_size] for i in range(0, len(_full_text), chunk_size)]
        all_risks_data = []

        for chunk in chunks:
            prompt = f"""
            From the following text from a corporate document, extract all sentences or short paragraphs (under 100 words) that explicitly describe a **specific business, financial, operational, competitive, or regulatory risk, threat, or uncertainty.**

            For each risk identified, assess its potential severity and likelihood.
            - **Severity**: The potential impact on the company's financials or operations. Choose one: [Low, Medium, High, Critical].
            - **Likelihood**: The probability of the risk occurring in the next 1-2 years. Choose one: [Unlikely, Possible, Likely].

            **Crucially, you MUST IGNORE generic, non-specific, or boilerplate legal disclaimers.**

            Return the results as a JSON object with a single key "risks", which is a list of objects. Each object must have three keys: "sentence", "severity", and "likelihood".
            If no specific risks are found, return an empty list.

            TEXT:
            ---
            {chunk}
            ---
            """
            try:
                headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
                payload = {
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.0,
                }
                response = http_post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=120)
                response.raise_for_status()
                risks = json.loads(response.json()['choices'][0]['message']['content']).get("risks", [])
                all_risks_data.extend(risks)
            except Exception as e:
                st.warning(f"An LLM error occurred during risk extraction: {e}")
                continue

        return all_risks_data
        
    def deduplicate_and_group_risks(all_risk_data: list[dict], model: "SentenceTransformer"):
        """
        Groups semantically similar risks together to avoid boilerplate redundancy.
        This function was missing and has been added.
        """
        if not all_risk_data:
            return {}

        sentences = [item['sentence'] for item in all_risk_data if 'sentence' in item]
        if not sentences:
             return {} # Return early if no sentences to process
             
        embeddings = model.encode(sentences)

        # Use Agglomerative Clustering for deduplication
        clustering = AgglomerativeClustering(n_clusters=None, distance_threshold=0.1).fit(embeddings)
        
        grouped_risks = defaultdict(lambda: {'companies': set(), 'sentences': []})
        representative_sentence_map = {}

        for i, label in enumerate(clustering.labels_):
            risk_item = all_risk_data[i]
            grouped_risks[label]['companies'].add(risk_item['company'])
            grouped_risks[label]['sentences'].append(risk_item)
            
            # Use the first sentence in a cluster as its representative
            if label not in representative_sentence_map:
                representative_sentence_map[label] = risk_item['sentence']
        
        final_deduplicated_risks = {}
        for label, data in grouped_risks.items():
            # Only consider risks that are common to more than one company
            if len(data['companies']) > 1:
                rep_sentence = representative_sentence_map[label]
                final_deduplicated_risks[rep_sentence] = data
                
        return final_deduplicated_risks

    @st.cache_data(show_spinner=False)
    def get_cluster_name_with_llm(risk_sentences: list) -> str:
        """Uses DeepSeek to generate a human-readable name for a cluster of risk sentences."""
        context = "\n".join([f"- {s}" for s in risk_sentences[:20]])
        prompt = f"""
        The following is a list of risk statements extracted from various company reports. They have been algorithmically clustered together because they are semantically similar.

        Your task is to provide a single, concise, human-readable name for this cluster of risks. The name should be 3-6 words long.

        RISK STATEMENTS:
        ---
        {context}
        ---

        Example Names: "Geopolitical Tensions in Eastern Europe", "Global Semiconductor Shortage", "Changing Consumer Privacy Regulations".

        Cluster Name:
        """
        try:
            headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
            }
            response = http_post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content'].strip().replace('"', '')
        except Exception:
            return "Unnamed Risk Cluster"

    # --- HTML Dashboard Generation (No changes needed here) ---
    def generate_risk_dashboard_html(clusters: dict) -> str:
        # ... [This function remains exactly the same as in your provided code] ...
        # Define colors for severity levels
        severity_colors = {
            "Critical": "#D32F2F", # Red
            "High": "#F57C00",     # Orange
            "Medium": "#FBC02D",   # Yellow
            "Low": "#388E3C",      # Green
        }
        
        styles = f"""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap');
            .risk-dashboard {{ font-family: 'Poppins', sans-serif; }}
            .dashboard-header {{ font-size: 2em; font-weight: 600; color: #00416A; border-bottom: 2px solid #00416A; padding-bottom: 10px; margin-bottom: 25px; }}
            .cluster-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 25px; }}
            .cluster-card {{ background-color: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); border-left: 5px solid #ccc; }}
            .cluster-title {{ font-size: 1.2em; font-weight: 600; color: #1e1e1e; margin-bottom: 15px; }}
            .cluster-size {{ font-size: 0.9em; color: #6c757d; float: right; }}
            .company-list {{ list-style-type: none; padding-left: 0; }}
            .company-list li {{ background-color: #e6f1f6; color: #00416A; padding: 8px 12px; border-radius: 20px; margin-bottom: 8px; font-size: 0.9em; display: inline-block; margin-right: 8px; }}
            .cluster-card.severity-Critical {{ border-left-color: {severity_colors['Critical']}; }}
            .cluster-card.severity-High {{ border-left-color: {severity_colors['High']}; }}
            .cluster-card.severity-Medium {{ border-left-color: {severity_colors['Medium']}; }}
            .cluster-card.severity-Low {{ border-left-color: {severity_colors['Low']}; }}
        </style>
        """
        
        cards_html = ""
        severity_order = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
        sorted_clusters = sorted(clusters.items(), 
                                 key=lambda item: (
                                     severity_order.get(item[1].get('highest_severity', 'Low'), 0), 
                                     len(item[1]['companies'])
                                 ), 
                                 reverse=True)

        for name, data in sorted_clusters:
            highest_severity = data.get('highest_severity', 'Medium')
            company_pills = "".join(f"<li>{company}</li>" for company in sorted(list(data['companies'])))
            cards_html += f"""
            <div class="cluster-card severity-{highest_severity}">
                <div class="cluster-title">
                    <span class="cluster-size">{len(data['companies'])} Companies</span>
                    {name}
                </div>
                <ul class="company-list">{company_pills}</ul>
            </div>
            """

        return f"""
        <!DOCTYPE html><html><head><title>Portfolio Risk Dashboard</title>{styles}</head>
        <body><div class="risk-dashboard">
            <div class="dashboard-header">Top Correlated Risk Clusters</div>
            <div class="cluster-grid">{cards_html}</div>
        </div></body></html>
        """

    # --- UI & WORKFLOW ---
    if 'prc_portfolio' not in st.session_state:
        st.session_state.prc_portfolio = {}

    st.subheader("1. Define Your Portfolio & Upload Documents")

    new_company = st.text_input("Add a new company to the portfolio")
    if st.button("Add Company") and new_company:
        if new_company not in st.session_state.prc_portfolio:
            st.session_state.prc_portfolio[new_company] = None
        st.rerun()

    if not st.session_state.prc_portfolio:
        st.info("Start by adding a company to your portfolio.")
    else:
        st.write("---")
        for company in list(st.session_state.prc_portfolio.keys()):
            cols_up, cols_del = st.columns([4, 1])
            with cols_up:
                files = st.file_uploader(
                    f"Upload documents for **{company}**",
                    type=["pdf"],
                    accept_multiple_files=True,
                    key=f"uploader_{company}"
                )
                if files:
                    st.session_state.prc_portfolio[company] = files
            with cols_del:
                st.write("") # Spacer
                st.write("") # Spacer
                if st.button(f"Remove {company}", key=f"del_{company}"):
                    del st.session_state.prc_portfolio[company]
                    st.rerun()

    st.write("---")
    st.subheader("2. Run Correlated Risk Analysis")

    if st.button("🚀 Analyze Portfolio Risks", type="primary", use_container_width=True):
        portfolio_with_docs = {c: f for c, f in st.session_state.prc_portfolio.items() if f}
        if len(portfolio_with_docs) < 2:
            st.warning("Please upload documents for at least two companies to run a correlation analysis.")
        else:
            all_risk_data = []
            with st.spinner("Stage 1/4: Extracting and scoring risks from documents..."):
                for company, files in portfolio_with_docs.items():
                    st.write(f"Processing documents for **{company}**...")
                    for file in files:
                        file_bytes = file.getvalue()
                        full_text = extract_text_from_pdf_bytes(file_bytes, file.name)
                        
                        # UPDATED: Call the DeepSeek function
                        scored_risks = extract_and_score_risks_with_llm(full_text)
                        
                        for risk_info in scored_risks:
                            all_risk_data.append({
                                "company": company,
                                "sentence": risk_info.get("sentence"),
                                "severity": risk_info.get("severity", "Medium"),
                                "likelihood": risk_info.get("likelihood", "Possible")
                            })
            if not all_risk_data:
                st.error("Could not extract any risk statements from the uploaded documents.")
                st.stop()
            st.success(f"Extracted and scored {len(all_risk_data)} total risk statements.")
            
            with st.spinner("Stage 2/4: Deduplicating and grouping semantically similar risks..."):
                model = SentenceTransformer("all-MiniLM-L6-v2")
                # This helper function was missing; it's now defined above.
                deduplicated_risks = deduplicate_and_group_risks(all_risk_data, model)
                if not deduplicated_risks:
                    st.warning("No correlated risks (affecting more than one company) were found after deduplication.")
                    st.stop()
                st.success(f"Found {len(deduplicated_risks)} unique correlated risk themes.")

            with st.spinner("Stage 3/4: Clustering themes and interpreting with AI..."):
                representative_sentences = list(deduplicated_risks.keys())
                embeddings = model.encode(representative_sentences)
                clusterer = hdbscan.HDBSCAN(min_cluster_size=2, min_samples=1, metric='euclidean')
                cluster_labels = clusterer.fit_predict(embeddings)
                
                final_clusters = {}
                severity_order = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
                for i, label in enumerate(cluster_labels):
                    if label != -1: # Ignore outliers
                        if label not in final_clusters:
                            sentences_for_naming = [s for j, l in enumerate(cluster_labels) if l == label for s in [list(deduplicated_risks.keys())[j]]]
                            # UPDATED: Call the DeepSeek function
                            cluster_name = get_cluster_name_with_llm(sentences_for_naming)
                            final_clusters[cluster_name] = {'companies': set(), 'sentences': [], 'highest_severity': 'Low'}

                        rep_sentence = representative_sentences[i]
                        theme_data = deduplicated_risks[rep_sentence]
                        final_clusters[cluster_name]['companies'].update(theme_data['companies'])
                        final_clusters[cluster_name]['sentences'].extend(theme_data['sentences'])
                        
                        for risk_item in theme_data['sentences']:
                            current_highest_sev = final_clusters[cluster_name]['highest_severity']
                            item_sev = risk_item['severity']
                            if severity_order.get(item_sev, 0) > severity_order.get(current_highest_sev, 0):
                                final_clusters[cluster_name]['highest_severity'] = item_sev

            with st.spinner("Stage 4/4: Generating final dashboard..."):
                if not final_clusters:
                    st.warning("No significant correlated risks were found.")
                    st.session_state.prc_dashboard = "<div>No correlated risks found.</div>"
                else:
                    st.session_state.prc_dashboard = generate_risk_dashboard_html(final_clusters)
                st.success("Analysis complete!")

    if 'prc_dashboard' in st.session_state:
        st.markdown("---")
        st.subheader("Risk Correlation Dashboard")
        st.components.v1.html(st.session_state.prc_dashboard, height=800, scrolling=True)
        st.download_button(
            label="📥 Download Dashboard as HTML",
            data=st.session_state.prc_dashboard,
            file_name="portfolio_risk_dashboard.html",
            mime="text/html",
            use_container_width=True
        )
