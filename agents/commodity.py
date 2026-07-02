"""Commodity Forecaster.

Forecasts commodity prices with Prophet + technical indicators and a Tavily-search
tool-using Azure OpenAI agent. The client is passed in by the router.
"""

import base64
import json
import os
import pandas as pd
import pandas_ta as ta  # noqa: F401 - registers the DataFrame `.ta` accessor (used as df.ta.rsi/macd/bbands)
import plotly.graph_objects as go
import streamlit as st

from datetime import datetime, timedelta, timezone
from jinja2 import Template
from openai import AzureOpenAI
from prophet import Prophet
from prophet.plot import plot_components_plotly
from tavily import TavilyClient
from utils.net import http_post, http_get


def commodity_forecasting_agent(client: "AzureOpenAI"):
    """
    An advanced AI agent that uses Tools (Tavily Search) to autonomously find
    and analyze news for commodity price forecasting.
    """
    # --- Page Configuration ---
    st.set_page_config(layout="wide")
    st.markdown("### 🌾 Commodity Price Forecasting Agent")
    st.markdown("An agent that uses search tools to analyze market-moving news and forecast prices.")

    # --- AGENT CONFIG (Fetched from secrets) ---
    try:
        FMP_API_KEY = os.environ.get("FMP_API_KEY")
        TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
        if not TAVILY_API_KEY:
            st.error("TAVILY_API_KEY not found. Please add it to your environment variables.")
            st.stop()
        tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
    except Exception as e:
        st.error(f"Configuration or Connection error: {e}. Please check secrets.")
        st.stop()

    # --- HELPER FUNCTIONS ---
    @st.cache_data(ttl=86400)
    def get_fmp_commodities(_api_key):
        """Fetches the list of available commodities from FMP."""
        try:
            url = f"https://financialmodelingprep.com/api/v3/symbol/available-commodities?apikey={_api_key}"
            response = http_get(url)
            response.raise_for_status()
            data = response.json()
            st.session_state['commodity_name_map'] = {item['symbol']: item['name'] for item in data}
            return {item['symbol']: f"{item['name']} ({item['symbol']})" for item in data}
        except Exception as e:
            st.error(f"Failed to fetch commodity list: {e}")
            return {}

    @st.cache_data(ttl=3600)
    def fetch_data(ticker, years, _api_key):
        """Fetches historical data from the FMP API for a specified period."""
        st.info(f"Fetching {years} years of '{ticker}' data from FMP API...")
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=int(years * 365.25))
            url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{ticker}?from={start_date.strftime('%Y-%m-%d')}&to={end_date.strftime('%Y-%m-%d')}&apikey={_api_key}"
            response = http_get(url)
            response.raise_for_status()
            data = response.json().get('historical', [])
            if not data:
                st.error(f"No historical data found for {ticker}.")
                return None
            df = pd.DataFrame(data)[['date', 'close']].rename(columns={'date': 'Date', 'close': 'Close'})
            df['Date'] = pd.to_datetime(df['Date'])
            return df.sort_values(by='Date').reset_index(drop=True)
        except Exception as e:
            st.error(f"Failed to fetch historical data: {e}")
            return None

    @st.cache_data(ttl=3600)
    def run_forecast(_df, periods):
        """Generates a forecast using Prophet."""
        if _df is None or len(_df) < 2: return None, None
        try:
            df_prophet = _df[['Date', 'Close']].rename(columns={'Date': 'ds', 'Close': 'y'})
            m = Prophet(daily_seasonality=True, yearly_seasonality=True, weekly_seasonality=True)
            m.fit(df_prophet)
            future = m.make_future_dataframe(periods=periods)
            forecast = m.predict(future)
            return m, forecast
        except Exception as e:
            st.error(f"Failed to generate forecast: {e}")
            return None, None

    @st.cache_data(ttl=3600)
    def calculate_technicals(_df):
        """Calculates technical indicators for the latest data point."""
        if _df is None or len(_df) < 20: return {}
        df_copy = _df.copy()
        df_copy.columns = [str(col).lower() for col in df_copy.columns]
        try: df_copy.ta.rsi(close='close', append=True)
        except Exception: pass
        try: df_copy.ta.macd(close='close', append=True)
        except Exception: pass
        try: df_copy.ta.bbands(close='close', append=True)
        except Exception: pass
        available_cols = ['RSI_14', 'MACD_12_26_9', 'MACDs_12_26_9', 'BBL_20_2.0', 'BBM_20_2.0', 'BBU_20_2.0']
        cols_to_extract = [col for col in available_cols if col in df_copy.columns]
        if not cols_to_extract: return {}
        latest_technicals = df_copy.iloc[-1][cols_to_extract].to_dict()
        return {k: v for k, v in latest_technicals.items() if pd.notna(v)}
        
    def analyze_with_llm(prompt, _client, is_json=False):
        """Generic function to call the LLM for analysis without tools."""
        try:
            kwargs = {"response_format": {"type": "json_object"}} if is_json else {}
            response = _client.chat.completions.create(
                model=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME"),
                messages=[{"role": "system", "content": "You are a world-class financial analyst providing clear, concise, and insightful analysis."},
                          {"role": "user", "content": prompt}],
                temperature=0.1,
                **kwargs
            )
            content = response.choices[0].message.content
            if is_json:
                return json.loads(content)
            return content
        except Exception as e:
            st.error(f"Error in LLM analysis: {e}")
            return f"Error during analysis: {e}" if not is_json else {"error": f"API Error: {e}"}

    def run_news_analysis_agent(commodity_name, _tavily_client, _azure_client):
        """Orchestrates the tool-using agent to find and analyze news."""
        st.info(f"🤖 Deploying agent to find and analyze news for {commodity_name}...")
        
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "tavily_search",
                    "description": "Get real-time news and market information about a commodity.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string", "description": "A detailed search query for news, e.g., 'latest news on Aluminum supply, LME inventories, and Chinese production'."}},
                        "required": ["query"],
                    },
                },
            }
        ]
        
        prompt = f"""
        Analyze the current fundamental news for '{commodity_name}'.
        Your goal is to provide a structured analysis broken down into key market-moving categories.
        Perform a web search to gather the latest information.

        Break down your analysis into the following four pillars. For each pillar, provide a 2-3 sentence summary:
        1. Demand Analysis: What is the current state of demand? Mention key industries and consumer trends.
        2. Supply Analysis: What is the current state of supply? Mention production levels, inventory data, and any disruptions.
        3. Macro & Geopolitical Analysis: What are the key macroeconomic or geopolitical factors impacting the price? (e.g., interest rates, USD strength, trade disputes, conflicts).
        4. Company Announcements & Projects: Are there any significant announcements from major producers, or new projects that could impact the market?

        After analyzing each pillar, provide an overall summary and a final outlook.

        Return your entire analysis as a single JSON object with the following keys:
        "demand_analysis", "supply_analysis", "macro_geopolitical_analysis", "company_announcements", "overall_summary", "overall_outlook".
        The outlook must be one of the following strings: "Bullish", "Bearish", "Neutral".
        """
        messages = [{"role": "user", "content": prompt}]
        
        try:
            response = _azure_client.chat.completions.create(
                model=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME"),
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
            response_message = response.choices[0].message
            messages.append(response_message)

            if response_message.tool_calls:
                st.info("Agent decided to use the search tool...")
                tool_call = response_message.tool_calls[0]
                function_name = tool_call.function.name
                if function_name == "tavily_search":
                    function_args = json.loads(tool_call.function.arguments)
                    query = function_args.get("query")
                    st.info(f"Agent is searching for: '{query}'")
                    search_results = _tavily_client.search(query=query, search_depth="advanced")
                    
                    tool_response_parts = [
                        f"- {res.get('title', 'No Title')}: {res.get('content', 'No content available.')}" 
                        for res in search_results.get('results', [])
                    ]
                    tool_response = "\n".join(tool_response_parts)
                    
                    messages.append({"tool_call_id": tool_call.id, "role": "tool", "name": function_name, "content": tool_response})

                    st.info("Agent is analyzing the search results...")
                    final_response = _azure_client.chat.completions.create(
                        model=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME"),
                        messages=messages,
                        response_format={"type": "json_object"}
                    )
                    content = final_response.choices[0].message.content
                    return json.loads(content)
            
            # Fallback if the model answers directly without using a tool
            content = response_message.content
            if content:
                # Attempt to parse what might be a direct JSON answer
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return {"error": "Agent returned a non-JSON response without using tools."}
            else:
                return {"error": "Agent failed to produce an analysis or use a tool."}

        except Exception as e:
            st.error(f"An error occurred during agent execution: {e}")
            return {"error": f"Could not complete news analysis: {e}"}
    
    def generate_html_report(data):
        """Generates a full HTML report including the detailed news analysis."""
        template_str = """
        <!DOCTYPE html><html><head><title>Commodity Forecast Report</title><style>body{font-family:'Poppins',sans-serif;margin:20px;background-color:#f9fafb;color:#1f2937}.container{max-width:1000px;margin:auto;background-color:#fff;padding:30px;border-radius:8px;box-shadow:0 4px 6px rgba(0,0,0,.05)}h1,h2,h3,h4{color:#00416A}h1{font-size:2em;border-bottom:2px solid #e0e0e0;padding-bottom:10px}h2{font-size:1.5em;margin-top:30px}h3{font-size:1.2em;margin-top:20px;border-bottom:1px solid #eee;padding-bottom:5px}h4{font-size:1em;margin-top:15px;}.metric-grid{display:flex;gap:20px;margin:20px 0}.metric{flex:1;text-align:center;background-color:#f8f9fa;padding:15px;border-radius:8px;border:1px solid #e0e0e0}.metric .label{font-size:.9em;color:#6c757d}.metric .value{font-size:1.8em;font-weight:600;color:#00416A}.section{margin-top:25px}.section p,.section li{line-height:1.6}ul{list-style-type:none;padding-left:0}li::before{content:"•";color:#00416A;font-weight:700;display:inline-block;width:1em;margin-left:-1em}img.forecast-chart{width:100%;border:1px solid #e0e0e0;border-radius:8px;margin-top:15px;}</style></head><body><div class="container"><h1>Commodity Forecast for {{ticker}}</h1><p>Report generated on: {{date}}</p><div class="metric-grid"><div class="metric"><div class="label">Current Price</div><div class="value">${{"%.2f"|format(current_price)}}</div></div><div class="metric"><div class="label">Forecasted Price ({{forecast_horizon_str}})</div><div class="value">${{"%.2f"|format(forecasted_price)}}</div></div><div class="metric"><div class="label">Projected Change</div><div class="value">{{"%.2f"|format(upside)}}%</div></div></div><div class="section"><h2>Final Recommendation</h2><p><b>{{recommendation.get('outlook', 'N/A')}}</b></p><p>{{recommendation.get('rationale', 'No rationale provided.')}}</p></div><div class="section"><h2>Time-Series Forecast Analysis</h2><p>{{forecast_summary}}</p><img src="data:image/png;base64,{{ chart_base_64 }}" alt="Forecast Chart" class="forecast-chart"></div><div class="section"><h2>Fundamental News Analysis</h2><h4>Overall Outlook: {{sentiment.get('overall_outlook', 'N/A')}}</h4><p><i>{{sentiment.get('overall_summary', 'No summary available.')}}</i></p><h3>Demand Analysis</h3><p>{{sentiment.get('demand_analysis', 'No data available.')}}</p><h3>Supply Analysis</h3><p>{{sentiment.get('supply_analysis', 'No data available.')}}</p><h3>Macro & Geopolitical Analysis</h3><p>{{sentiment.get('macro_geopolitical_analysis', 'No data available.')}}</p><h3>Company Announcements & Projects</h3><p>{{sentiment.get('company_announcements', 'No data available.')}}</p></div><div class="section"><h2>Technical Analysis</h2><p>{{technical_summary}}</p><ul>{% if technicals %}{% for key, value in technicals.items() %}<li><b>{{key}}:</b> {{"%.2f"|format(value)}}</li>{% endfor %}{% else %}<li>No technical data available.</li>{% endif %}</ul></div></div></body></html>
        """
        template = Template(template_str)
        return template.render(data)
        
    # --- UI & WORKFLOW ---
    st.subheader("1. Define Commodity & Forecast Period")
    commodity_options = get_fmp_commodities(FMP_API_KEY)
    
    if commodity_options:
        if 'current_commodity' not in st.session_state:
            st.session_state.current_commodity = ""

        c1, c2, c3 = st.columns(3)
        commodity_ticker = c1.selectbox("Select Commodity", options=list(commodity_options.keys()), format_func=lambda x: commodity_options[x], key="commodity_select")
        forecast_options = { "3 Months": 90, "6 Months": 180, "1 Year": 365, "2 Years": 730, "3 Years": 1095, "5 Years": 1825 }
        forecast_horizon_str = c2.selectbox("Select Forecast Horizon", options=list(forecast_options.keys()), index=2)
        forecast_horizon_days = forecast_options[forecast_horizon_str]
        history_years = c3.selectbox("Historical Data Period (Years)", [1, 2, 5, 10], index=2)

        if st.session_state.current_commodity != commodity_ticker:
            st.cache_data.clear()
            st.session_state.current_commodity = commodity_ticker
            st.info(f"Switched to {commodity_ticker}. Cache cleared for fresh analysis.")

        if st.button("🚀 Run Forecast & Analysis", type="primary", use_container_width=True):
            df = fetch_data(commodity_ticker, history_years, FMP_API_KEY)
            
            if df is not None and not df.empty:
                with st.spinner("Agent is running... This may take a moment. 🕵️"):
                    # 1. RUN CORE ANALYSIS (Quant & Technical)
                    model, forecast = run_forecast(df, forecast_horizon_days)
                    technicals = calculate_technicals(df)
                    commodity_name = st.session_state.get('commodity_name_map', {}).get(commodity_ticker, commodity_ticker)
                    base_commodity_name = ' '.join(commodity_name.split(' ')[:-1]) if 'future' in commodity_name.lower() else commodity_name
                    
                    # 2. RUN NEWS ANALYSIS AGENT (Fundamental)
                    sentiment_analysis = run_news_analysis_agent(base_commodity_name, tavily_client, client)
                    
                    # 3. RUN SYNTHESIS & FINAL RECOMMENDATION
                    current_price = df['Close'].iloc[-1]
                    forecasted_price, upside = current_price, 0.0
                    forecast_summary, trend_analysis = "Forecast could not be generated.", "Trend data not available."

                    if forecast is not None:
                        forecasted_price = forecast['yhat'].iloc[-1]
                        upside = ((forecasted_price / current_price) - 1) * 100 if current_price > 0 else 0
                        forecast_summary = f"The model forecasts a price of ${forecasted_price:.2f} in {forecast_horizon_str}."
                        trend_slope = (forecast['trend'].iloc[-1] - forecast['trend'].iloc[-forecast_horizon_days]) / forecast_horizon_days
                        if trend_slope > 0.01: trend_analysis = "a notable upward trend."
                        elif trend_slope > 0: trend_analysis = "a slight upward trend."
                        elif trend_slope < -0.01: trend_analysis = "a notable downward trend."
                        else: trend_analysis = "a slight downward trend."
                    
                    prompt_technicals = f"""Analyze these technical indicators for {commodity_name}: {str(technicals)}. Provide a one-sentence summary of the short-term outlook."""
                    technical_summary = analyze_with_llm(prompt_technicals, client) if technicals else "Not enough data for technical analysis."
                    
                    prompt_final = f"""As a commodity analyst, synthesize these three pillars of analysis for '{commodity_name}' to provide a final investment outlook (e.g., 'Bullish', 'Cautiously Bullish', 'Neutral', 'Bearish') and a 3-sentence rationale. Return a JSON object with keys "outlook" and "rationale".

                    1. **Quantitative Forecast**: The price is projected to be ${forecasted_price:.2f} in {forecast_horizon_str}. The model identifies {trend_analysis}
                    2. **Technical Picture**: Short-term indicators suggest: "{technical_summary}".
                    3. **Fundamental News Analysis**: The agent's real-time search concluded a '{sentiment_analysis.get('overall_outlook', 'N/A')}' outlook, summarized as: "{sentiment_analysis.get('overall_summary', 'Not available.')}".
                    """
                    final_recommendation = analyze_with_llm(prompt_final, client, is_json=True)

                    # 4. VISUALIZE RESULTS
                    st.markdown("---")
                    st.subheader(f"📈 Analysis for {commodity_name} ({commodity_ticker})")
                    kpi1, kpi2, kpi3 = st.columns(3)
                    kpi1.metric("Current Price", f"${current_price:.2f}")
                    kpi2.metric(f"Forecast ({forecast_horizon_str})", f"${forecasted_price:.2f}")
                    kpi3.metric("Projected Change", f"{upside:.2f}%")
                    st.markdown("#### Final Recommendation")
                    rec = final_recommendation
                    if 'error' not in rec:
                        st.markdown(f"**Outlook: {rec.get('outlook', 'N/A')}**")
                        st.markdown(rec.get('rationale', 'No rationale provided.'))
                    else: st.error(rec.get('error'))
                    
                    tab1, tab2, tab3, tab4 = st.tabs(["Forecast Chart", "Forecast Components", "Technical Details", "Fundamental News Analysis"])

                    with tab1:
                        if forecast is not None:
                            fig = go.Figure()
                            fig.add_trace(go.Scatter(x=df['Date'], y=df['Close'], mode='lines', line_color='#1f77b4', name='Historical Price'))
                            fig.add_trace(go.Scatter(x=forecast['ds'], y=forecast['yhat'], mode='lines', line_color='#ff7f0e', name='Forecasted Price'))
                            fig.add_trace(go.Scatter(x=forecast['ds'], y=forecast['yhat_lower'], fill=None, mode='lines', line_color='rgba(255, 127, 14, 0.3)', name='Lower Confidence Bound'))
                            fig.add_trace(go.Scatter(x=forecast['ds'], y=forecast['yhat_upper'], fill='tonexty', mode='lines', line_color='rgba(255, 127, 14, 0.3)', name='Upper Confidence Bound'))
                            fig.update_layout(title_text=f'{commodity_name} Price Forecast', xaxis_title='Date', yaxis_title='Price (USD)', showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                            st.plotly_chart(fig, use_container_width=True)
                            img_bytes = fig.to_image(format="png", width=900, height=500, scale=2)
                            chart_base_64 = base64.b64encode(img_bytes).decode()
                        else: chart_base_64 = ""

                    with tab2:
                        st.write("This chart substantiates the forecast by showing the underlying patterns the model detected.")
                        if model and forecast is not None:
                            fig_comp = plot_components_plotly(model, forecast)
                            st.plotly_chart(fig_comp, use_container_width=True)

                    with tab3:
                        st.write(technical_summary)
                        if technicals: st.json({k: f"{v:.2f}" for k, v in technicals.items()})

                    with tab4:
                        if 'error' not in sentiment_analysis:
                            st.markdown(f"**Overall Outlook: {sentiment_analysis.get('overall_outlook', 'Not Available')}**")
                            st.markdown(f"_{sentiment_analysis.get('overall_summary', 'No summary available.')}_")
                            
                            st.markdown("---")
                            
                            st.markdown("##### Demand Analysis")
                            st.write(sentiment_analysis.get('demand_analysis', 'N/A'))
                            
                            st.markdown("##### Supply Analysis")
                            st.write(sentiment_analysis.get('supply_analysis', 'N/A'))
                            
                            st.markdown("##### Macro & Geopolitical Analysis")
                            st.write(sentiment_analysis.get('macro_geopolitical_analysis', 'N/A'))

                            st.markdown("##### Company Announcements & Projects")
                            st.write(sentiment_analysis.get('company_announcements', 'N/A'))
                        else:
                            st.error(sentiment_analysis.get('error'))
                    
                    report_data = {
                        "ticker": commodity_name, 
                        "technicals": technicals, 
                        "technical_summary": technical_summary,
                        "sentiment": sentiment_analysis, 
                        "forecast_summary": f"{forecast_summary}. The model identified {trend_analysis}",
                        "recommendation": final_recommendation, 
                        "current_price": current_price,
                        "forecasted_price": forecasted_price, 
                        "upside": upside,
                        "forecast_horizon_str": forecast_horizon_str, 
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "chart_base_64": chart_base_64
                    }
                    html_report = generate_html_report(report_data)
                    st.download_button(label="📥 Download Full HTML Report", data=html_report,
                                       file_name=f"Forecast_{commodity_ticker}_{datetime.now().strftime('%Y%m%d')}.html", mime="text/html",
                                       use_container_width=True)
