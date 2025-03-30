import streamlit as st
from PyPDF2 import PdfReader
import pandas as pd
import io
import re

def extract_data_from_pdf(file):
    reader = PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"

    entries = []
    matches = re.finditer(r"(\d{5})\s+(\d+)\s+(.+?)\n", text)
    
    for match in matches:
        code = match.group(1)
        qty = match.group(2)
        label = match.group(3)
        
        desc_pattern = re.compile(re.escape(label) + r"\n(.*?)(?=\n\d{5}|\Z)", re.DOTALL)
        desc_match = desc_pattern.search(text)
        description = desc_match.group(1).strip().replace("\n", " ") if desc_match else ""

        entries.append({
            "Code": code,
            "Label": label,
            "Item Long Description": description,
            "Qty": qty,
            "UOM": "NOS",
            "Item Code": code
        })

    return pd.DataFrame(entries)

def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='RFQ_Data')
    processed_data = output.getvalue()
    return processed_data

# Streamlit UI
st.title("📄 RFQ PDF to Excel Converter")

uploaded_file = st.file_uploader("Upload your RFQ PDF", type="pdf")

if uploaded_file:
    df = extract_data_from_pdf(uploaded_file)
    st.success("✅ Data Extracted Successfully!")

    st.dataframe(df)

    excel_data = convert_df_to_excel(df)
    st.download_button(
        label="📥 Download Excel",
        data=excel_data,
        file_name="rfq_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
