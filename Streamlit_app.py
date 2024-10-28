import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import base64

# Keep existing constants and functions unchanged
CONVERSION_RATES = {
    'USD': 0.93,
    'GBP': 1.2,
    'INR': 0.011,
    'JPY': 0.0061
}

def load_css():
    """Load custom CSS styles with Schneider Electric theme"""
    st.markdown("""
        <style>
        /* Main theme colors */
        :root {
            --se-green: #3DCD58;
            --se-dark: #1E1E1E;
            --se-gray: #2D2D2D;
            --se-light-gray: #404040;
        }

        /* Global styles */
        .main {
            background-color: var(--se-dark);
            color: white;
            padding: 2rem;
        }

        /* Header styling */
        .stTitle {
            color: var(--se-green) !important;
            font-weight: 600 !important;
        }

        /* Metric cards */
        .metric-container {
            background-color: var(--se-gray);
            border-radius: 10px;
            padding: 1.5rem;
            border: 1px solid var(--se-light-gray);
            transition: transform 0.2s;
        }
        
        .metric-container:hover {
            transform: translateY(-5px);
            box-shadow: 0 4px 15px rgba(61, 205, 88, 0.1);
        }

        .metric-label {
            color: var(--se-green);
            font-size: 0.9rem;
            font-weight: 500;
            margin-bottom: 0.5rem;
        }

        .metric-value {
            color: white;
            font-size: 1.5rem;
            font-weight: 600;
        }

        /* Tabs styling */
        .stTabs {
            background-color: var(--se-gray);
            border-radius: 10px;
            padding: 1rem;
        }

        .stTab {
            color: white !important;
            background-color: var(--se-dark) !important;
        }

        .stTab[aria-selected="true"] {
            background-color: var(--se-green) !important;
            color: var(--se-dark) !important;
        }

        /* Table styling */
        .dataframe {
            background-color: var(--se-gray);
            border: 1px solid var(--se-light-gray);
        }

        .dataframe th {
            background-color: var(--se-green);
            color: white;
        }

        /* File uploader styling */
        .stFileUploader {
            background-color: var(--se-gray);
            border: 2px dashed var(--se-green);
            border-radius: 10px;
            padding: 1rem;
        }

        /* Button styling */
        .stButton>button {
            background-color: var(--se-green);
            color: white;
            border: none;
            border-radius: 5px;
            padding: 0.5rem 1rem;
            transition: all 0.2s;
        }

        .stButton>button:hover {
            background-color: #2eb347;
            transform: translateY(-2px);
        }

        /* Alert styling */
        .stAlert {
            background-color: var(--se-gray);
            border-left: 4px solid var(--se-green);
            color: white;
            margin: 1rem 0;
        }

        /* Download link styling */
        a {
            color: var(--se-green);
            text-decoration: none;
            padding: 0.5rem 1rem;
            border: 1px solid var(--se-green);
            border-radius: 5px;
            transition: all 0.2s;
        }

        a:hover {
            background-color: var(--se-green);
            color: white;
        }

        /* Plot styling */
        .js-plotly-plot {
            background-color: var(--se-gray);
            border-radius: 10px;
            padding: 1rem;
            margin: 1rem 0;
        }

        /* Custom scrollbar */
        ::-webkit-scrollbar {
            width: 10px;
        }

        ::-webkit-scrollbar-track {
            background: var(--se-dark);
        }

        ::-webkit-scrollbar-thumb {
            background: var(--se-green);
            border-radius: 5px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: #2eb347;
        }
        </style>
    """, unsafe_allow_html=True)

def load_css():
    """Load custom CSS styles"""
    st.markdown("""
        <style>
        .main {
            padding: 2rem;
        }
        .stAlert {
            margin-top: 1rem;
        }
        .metric-card {
            border: 1px solid #e6e6e6;
            padding: 1rem;
            border-radius: 0.5rem;
            margin: 0.5rem 0;
        }
        </style>
    """, unsafe_allow_html=True)

def convert_to_euro(price, currency):
    """Converts a price to Euros based on the provided currency."""
    if currency in CONVERSION_RATES:
        return price * CONVERSION_RATES[currency]
    return None

def process_data(open_po_df, workbench_df):
    """Process the input dataframes according to business logic"""
    try:
        # Filter Open PO for LINE_TYPE = Inventory
        open_po_df = open_po_df[open_po_df['LINE_TYPE'] == 'Inventory']
        
        # Merge dataframes
        merged_df = pd.merge(
            workbench_df,
            open_po_df,
            left_on=['PART_NUMBER', 'VENDOR_NUM'],
            right_on=['ITEM', 'VENDOR_NUM'],
            how='inner'
        )
        
        # Clean up column names
        merged_df.columns = merged_df.columns.str.strip()
        merged_df = merged_df.drop('ITEM', axis=1)
        
        # Rename columns
        merged_df = merged_df.rename(columns={
            'DANDB': 'VENDOR_DUNS',
            'UNIT_PRICE_x': 'Unit_Price_WB',
            'CURRENCY_CODE': 'CURRENCY_CODE_WB',
            'UNIT_PRICE_y': 'UNIT_PRICE_OPO',
            'CURRNECY': 'CURRNECY_OPO'
        })
        
        # Add IG/OG classification
        merged_df['IG/OG'] = merged_df['VENDOR_NAME'].apply(
            lambda x: 'IG' if 'SCHNEIDER' in str(x).upper() or 'WUXI' in str(x).upper() else 'OG'
        )
        
        # Add PO Year
        merged_df['PO Year'] = pd.to_datetime(merged_df['PO_SHIPMENT_CREATION_DATE']).dt.year
        
        # Convert prices to EUR
        merged_df['UNIT_PRICE_WB_EUR'] = merged_df.apply(
            lambda row: convert_to_euro(row['Unit_Price_WB'], row['CURRENCY_CODE_WB']), axis=1
        )
        merged_df['UNIT_PRICE_OPO_EUR'] = merged_df.apply(
            lambda row: convert_to_euro(row['UNIT_PRICE_OPO'], row['CURRNECY_OPO']), axis=1
        )
        
        # Calculate metrics
        merged_df['Price_Delta'] = merged_df['UNIT_PRICE_OPO_EUR'] - merged_df['UNIT_PRICE_WB_EUR']
        merged_df['Impact in Euros'] = merged_df['Price_Delta'] * merged_df['QTY_ELIGIBLE_TO_SHIP']
        merged_df['Open PO Value'] = merged_df['QTY_ELIGIBLE_TO_SHIP'] * merged_df['UNIT_PRICE_OPO_EUR']
        
        # Sort by impact
        merged_df = merged_df.sort_values('Impact in Euros', ascending=False)
        
        return merged_df
    except Exception as e:
        st.error(f"Error processing data: {str(e)}")
        return None

def generate_insights(df):
    """Generate key insights from the processed data"""
    total_impact = df['Impact in Euros'].sum()
    total_po_value = df['Open PO Value'].sum()
    total_parts = len(df)
    unique_vendors = df['VENDOR_NAME'].nunique()
    
    # Group by analyses
    impact_by_vendor = df.groupby('VENDOR_NAME')['Impact in Euros'].sum().sort_values(ascending=False).head(5)
    impact_by_category = df.groupby('STARS Category Code')['Impact in Euros'].sum().sort_values(ascending=False).head(5)
    
    return {
        'total_impact': total_impact,
        'total_po_value': total_po_value,
        'total_parts': total_parts,
        'unique_vendors': unique_vendors,
        'impact_by_vendor': impact_by_vendor,
        'impact_by_category': impact_by_category
    }

def create_visualizations(df):
    """Create visualizations using Plotly"""
    # Impact by Category
    category_fig = px.bar(
        df.groupby('STARS Category Code')['Impact in Euros'].sum().reset_index(),
        x='Impact in Euros',
        y='STARS Category Code',
        title='Price Impact by Category (EUR)',
        orientation='h'
    )
    category_fig.update_layout(height=500)
    
    # Impact by Vendor (Top 10)
    vendor_fig = px.pie(
        df.groupby('VENDOR_NAME')['Impact in Euros'].sum().sort_values(ascending=False).head(10).reset_index(),
        values='Impact in Euros',
        names='VENDOR_NAME',
        title='Top 10 Vendors by Price Impact'
    )
    
    # Impact by IG/OG
    ig_og_fig = px.bar(
        df.groupby('IG/OG')['Impact in Euros'].sum().reset_index(),
        x='IG/OG',
        y='Impact in Euros',
        title='Price Impact by IG/OG Classification',
        color='IG/OG'
    )
    
    # Timeline of PO Creation
    timeline_fig = px.line(
        df.groupby('PO_SHIPMENT_CREATION_DATE')['Impact in Euros'].sum().reset_index(),
        x='PO_SHIPMENT_CREATION_DATE',
        y='Impact in Euros',
        title='Price Impact Timeline'
    )
    
    return [category_fig, vendor_fig, ig_og_fig, timeline_fig]

def get_download_link(df, filename="processed_data.csv"):
    """Generate a download link for the processed data"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download {filename}</a>'
    return href

# [Previous functions: convert_to_euro, process_data, generate_insights, create_visualizations, get_download_link]

def main():
    st.set_page_config(
        page_title="Schneider Electric - Open PO Analysis",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    load_css()

    # Header with Schneider Electric branding
    st.markdown("""
        <div style='text-align: center; padding: 2rem 0;'>
            <h1 style='color: #3DCD58; margin-bottom: 0.5rem;'>Open PO Analysis</h1>
            <p style='color: #ffffff; font-size: 1.2rem;'>Schneider Electric Procurement Analytics</p>
        </div>
    """, unsafe_allow_html=True)

    # Introduction text
    st.markdown("""
        <div style='background-color: #2D2D2D; padding: 1.5rem; border-radius: 10px; margin-bottom: 2rem;'>
            <p style='color: white; margin: 0;'>
                This app analyzes Open PO data against Workbench data to identify price variations and potential savings opportunities.
                Upload both required files below to begin the analysis.
            </p>
        </div>
    """, unsafe_allow_html=True)

    # File uploaders with custom styling
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("<div class='upload-container'>", unsafe_allow_html=True)
        open_po_file = st.file_uploader("📄 Upload Open PO Report", type=['xlsx'])
        st.markdown("</div>", unsafe_allow_html=True)
    
    with col2:
        st.markdown("<div class='upload-container'>", unsafe_allow_html=True)
        workbench_file = st.file_uploader("📊 Upload Workbench Report", type=['xlsx'])
        st.markdown("</div>", unsafe_allow_html=True)

    # Rest of the main function remains the same, just with updated styling
    if open_po_file is not None and workbench_file is not None:
        try:
            # [Previous file processing code remains unchanged]
            open_po_df = pd.read_excel(
                open_po_file,
                usecols=['     ORDER_TYPE', 'LINE_TYPE', 'ITEM', 'VENDOR_NUM', 'PO_NUM', 'RELEASE_NUM', 
                        'LINE_NUM', 'SHIPMENT_NUM', 'AUTHORIZATION_STATUS', 'PO_SHIPMENT_CREATION_DATE',
                        'QTY_ELIGIBLE_TO_SHIP', 'UNIT_PRICE', 'CURRNECY']
            )
            
            workbench_df = pd.read_excel(
                workbench_file,
                usecols=['PART_NUMBER', 'DESCRIPTION', 'VENDOR_NUM', 'VENDOR_NAME', 'DANDB',
                        'STARS Category Code', 'ASL_MPN', 'UNIT_PRICE', 'CURRENCY_CODE']
            )

            st.success("✅ Files uploaded successfully!")

            processed_df = process_data(open_po_df, workbench_df)
            
            if processed_df is not None and not processed_df.empty:
                insights = generate_insights(processed_df)
                
                # Styled metrics
                st.markdown("<div style='display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin: 2rem 0;'>", unsafe_allow_html=True)
                
                metrics = [
                    ("💰 Total Price Impact (EUR)", f"{insights['total_impact']:,.2f}"),
                    ("📊 Total Open PO Value (EUR)", f"{insights['total_po_value']:,.2f}"),
                    ("🔢 Number of Parts", insights['total_parts']),
                    ("🏢 Number of Vendors", insights['unique_vendors'])
                ]
                
                for label, value in metrics:
                    st.markdown(f"""
                        <div class='metric-container'>
                            <div class='metric-label'>{label}</div>
                            <div class='metric-value'>{value}</div>
                        </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("</div>", unsafe_allow_html=True)

                # Create styled tabs
                tab1, tab2, tab3 = st.tabs(["📈 Visualizations", "📋 Data Table", "📊 Top Impact Analysis"])

                with tab1:
                    figures = create_visualizations(processed_df)
                    
                    # Update plot themes to match dark theme
                    for fig in figures:
                        fig.update_layout(
                            template="plotly_dark",
                            plot_bgcolor='rgba(45, 45, 45, 0.8)',
                            paper_bgcolor='rgba(45, 45, 45, 0.8)',
                            font=dict(color='white'),
                        )
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.plotly_chart(figures[0], use_container_width=True)
                        st.plotly_chart(figures[2], use_container_width=True)
                    with col2:
                        st.plotly_chart(figures[1], use_container_width=True)
                        st.plotly_chart(figures[3], use_container_width=True)

                with tab2:
                    st.dataframe(processed_df)
                    st.markdown(get_download_link(processed_df), unsafe_allow_html=True)

                with tab3:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("<h3 style='color: #3DCD58;'>📈 Top Vendors by Price Impact</h3>", unsafe_allow_html=True)
                        st.table(pd.DataFrame({
                            'Vendor': insights['impact_by_vendor'].index,
                            'Impact (EUR)': insights['impact_by_vendor'].values.round(2)
                        }))
                    
                    with col2:
                        st.markdown("<h3 style='color: #3DCD58;'>📊 Top Categories by Price Impact</h3>", unsafe_allow_html=True)
                        st.table(pd.DataFrame({
                            'Category': insights['impact_by_category'].index,
                            'Impact (EUR)': insights['impact_by_category'].values.round(2)
                        }))

            else:
                st.warning("⚠️ No data matches the analysis criteria.")

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.info("ℹ️ Please ensure your files have the required columns and format.")

if __name__ == "__main__":
    main()
