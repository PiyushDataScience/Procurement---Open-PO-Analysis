import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import base64

# Constants
CONVERSION_RATES = {
    'USD': 0.93,
    'GBP': 1.2,
    'INR': 0.011,
    'JPY': 0.0061
}

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
    return price  # Return original price if currency not found instead of None

def process_data(open_po_df, workbench_df):
    """Process the input dataframes according to business logic"""
    try:
        # Filter Open PO for LINE_TYPE = Inventory
        open_po_df = open_po_df[open_po_df['LINE_TYPE'] == 'Inventory']
        
        # Clean up column names before merge
        open_po_df.columns = open_po_df.columns.str.strip()
        workbench_df.columns = workbench_df.columns.str.strip()
        
        # Rename UNIT_PRICE columns before merge to avoid confusion
        open_po_df = open_po_df.rename(columns={'UNIT_PRICE': 'UNIT_PRICE_OPO'})
        workbench_df = workbench_df.rename(columns={'UNIT_PRICE': 'UNIT_PRICE_WB'})
        
        # Merge dataframes
        merged_df = pd.merge(
            workbench_df,
            open_po_df,
            left_on=['PART_NUMBER', 'VENDOR_NUM'],
            right_on=['ITEM', 'VENDOR_NUM'],
            how='inner'
        )
        
        # Drop redundant column
        merged_df = merged_df.drop('ITEM', axis=1)
        
        # Rename columns
        merged_df = merged_df.rename(columns={
            'DANDB': 'VENDOR_DUNS',
            'CURRENCY_CODE': 'CURRENCY_CODE_WB',
            'CURRNECY': 'CURRENCY_CODE_OPO'  # Fixed typo in CURRENCY
        })
        
        # Add IG/OG classification
        merged_df['IG/OG'] = merged_df['VENDOR_NAME'].apply(
            lambda x: 'IG' if 'SCHNEIDER' in str(x).upper() or 'WUXI' in str(x).upper() else 'OG'
        )
        
        # Add PO Year
        merged_df['PO Year'] = pd.to_datetime(merged_df['PO_SHIPMENT_CREATION_DATE']).dt.year
        
        # Convert prices to EUR
        merged_df['UNIT_PRICE_WB_EUR'] = merged_df.apply(
            lambda row: convert_to_euro(row['UNIT_PRICE_WB'], row['CURRENCY_CODE_WB']), axis=1
        )
        merged_df['UNIT_PRICE_OPO_EUR'] = merged_df.apply(
            lambda row: convert_to_euro(row['UNIT_PRICE_OPO'], row['CURRENCY_CODE_OPO']), axis=1
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
    if df is None or df.empty:
        return None
        
    total_impact = df['Impact in Euros'].sum()
    total_po_value = df['Open PO Value'].sum()
    distinct_parts_count = df['PART_NUMBER'].nunique() 
    unique_vendors = df['VENDOR_NAME'].nunique()
    
    # Group by analyses
    impact_by_vendor = df.groupby('VENDOR_NAME')['Impact in Euros'].sum().sort_values(ascending=False).head(5)
    impact_by_category = df.groupby('STARS Category Code')['Impact in Euros'].sum().sort_values(ascending=False).head(5)
    
    return {
        'total_impact': total_impact,
        'total_po_value': total_po_value,
        'total_Unique_parts': distinct_parts_count,
        'unique_vendors': unique_vendors,
        'impact_by_vendor': impact_by_vendor,
        'impact_by_category': impact_by_category
    }

def create_visualizations(df):
    """Create visualizations using Plotly"""
    if df is None or df.empty:
        return None
        
    # Impact by Category
    category_fig = px.bar(
        df.groupby('STARS Category Code')['Impact in Euros'].sum().sort_values(ascending=False).head(10).reset_index(),
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
    if df is None or df.empty:
        return ""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download {filename}</a>'
    return href

def main():
    st.set_page_config(
        page_title="Open PO Analysis Tool",
        page_icon="📊",
        layout="wide"
    )
    
    load_css()

    st.title("Open PO Analysis")
    st.markdown("""
    This tool analyzes Open PO data against Workbench data to identify price variations and potential savings opportunities.
    Please upload both required files to begin the analysis.
    """)

    # File uploaders
    col1, col2 = st.columns(2)
    with col1:
        open_po_file = st.file_uploader("Upload Open PO Report", type=['xlsx'])
    with col2:
        workbench_file = st.file_uploader("Upload Workbench Report", type=['xlsx'])

    if open_po_file is not None and workbench_file is not None:
        try:
            # Read files
            open_po_df = pd.read_excel(
                open_po_file,
                usecols=['ORDER_TYPE', 'LINE_TYPE', 'ITEM', 'VENDOR_NUM', 'PO_NUM', 'RELEASE_NUM', 
                        'LINE_NUM', 'SHIPMENT_NUM', 'AUTHORIZATION_STATUS', 'PO_SHIPMENT_CREATION_DATE',
                        'QTY_ELIGIBLE_TO_SHIP', 'UNIT_PRICE', 'CURRNECY']
            )
            
            workbench_df = pd.read_excel(
                workbench_file,
                usecols=['PART_NUMBER', 'DESCRIPTION', 'VENDOR_NUM', 'VENDOR_NAME', 'DANDB',
                        'STARS Category Code', 'ASL_MPN', 'UNIT_PRICE', 'CURRENCY_CODE']
            )

            st.success("Files uploaded successfully!")

            # Process data
            processed_df = process_data(open_po_df, workbench_df)
            
            if processed_df is not None and not processed_df.empty:
                # Generate insights
                insights = generate_insights(processed_df)
                
                if insights:
                    # Display metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Price Impact (EUR)", f"{insights['total_impact']:,.2f}")
                    with col2:
                        st.metric("Total Open PO Value (EUR)", f"{insights['total_po_value']:,.2f}")
                    with col3:
                        st.metric("Number of Parts", insights['total_Unique_parts'])
                    with col4:
                        st.metric("Number of Vendors", insights['unique_vendors'])

                    # Create tabs
                    tab1, tab2, tab3 = st.tabs(["Visualizations", "Data Table", "Top Impact Analysis"])

                    with tab1:
                        figures = create_visualizations(processed_df)
                        if figures:
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
                            st.subheader("Top Vendors by Price Impact")
                            st.table(pd.DataFrame({
                                'Vendor': insights['impact_by_vendor'].index,
                                'Impact (EUR)': insights['impact_by_vendor'].values.round(2)
                            }))
                        
                        with col2:
                            st.subheader("Top Categories by Price Impact")
                            st.table(pd.DataFrame({
                                'Category': insights['impact_by_category'].index,
                                'Impact (EUR)': insights['impact_by_category'].values.round(2)
                            }))

            else:
                st.warning("No data matches the analysis criteria.")

        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.info("Please ensure your files have the required columns and format.")

if __name__ == "__main__":
    main()
