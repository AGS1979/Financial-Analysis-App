"""Agent Credit.

Extracts and synthesizes terms from credit agreements / indentures (Azure Document
Intelligence + Azure OpenAI), with covenant monitoring and Q&A over stored deals.
"""

from config import require_env


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
    _cfg = require_env(
        "AZURE_DI_ENDPOINT", "AZURE_DI_KEY", "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_KEY", "AZURE_OPENAI_DEPLOYMENT_NAME",
    )
    di_endpoint = _cfg["AZURE_DI_ENDPOINT"]
    di_key = _cfg["AZURE_DI_KEY"]
    openai_endpoint = _cfg["AZURE_OPENAI_ENDPOINT"]
    openai_key = _cfg["AZURE_OPENAI_KEY"]
    openai_deployment_name = _cfg["AZURE_OPENAI_DEPLOYMENT_NAME"]
    conn = st.connection("supabase", type=SupabaseConnection)

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
                             return {"error": "Failed to decode JSON from response."}
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
