import streamlit as st
import pandas as pd
import os
import shutil

from utils.pdf_utils import download_pdf, extract_pdf_text
from utils.llm_utils import extract_pdf_details, CACHE_DIR

# Page title
st.title("📑 Interactive PDF Content Extraction & Excel Filling")

# Input OpenAI API key
OpenAI_api_key = st.sidebar.text_input(
    "Enter OpenAI API Key",
    type="password"
)

# Upload Excel file
uploaded_file = st.file_uploader("Upload Excel file containing PDF links", type=['xlsx'])

# Required fields for output
required_fields = [
    "Title", "Summary", "Key Questions and Answers", "Issuing Authority",
    "Centers Involved", "Date of Issuance", "Type of Document", "Public Comment Period",
    "Docket Number", "Guidance Status", "Open for Comment", "Comment Closing Date",
    "Relevance of this Guidance"
]

# Reset session and cache
if st.button("🔄 Reset All Progress and Cache"):
    st.session_state.current_index = 0
    st.session_state.results = []
    try:
        shutil.rmtree(CACHE_DIR)
        os.makedirs(CACHE_DIR, exist_ok=True)
        st.success("✅ Cache and session state cleared.")
    except Exception as e:
        st.warning(f"⚠️ Could not clear cache: {e}")

# Run if file and key are both available
if uploaded_file and OpenAI_api_key:
    df = pd.read_excel(uploaded_file)
    st.write("✅ **Excel Uploaded Successfully! Preview:**", df.head())

    # Prepare directory for storing PDFs
    pdf_dir = "data/pdfs"
    os.makedirs(pdf_dir, exist_ok=True)

    # Init session state
    if "results" not in st.session_state:
        st.session_state.results = []
    if "current_index" not in st.session_state:
        st.session_state.current_index = 0

    total_rows = len(df)

    # Full extraction
    if st.button("🚀 Run Full Extraction"):
        while st.session_state.current_index < total_rows:
            idx = st.session_state.current_index
            row = df.iloc[idx]
            url = row['Source Link']
            sr_no = row['Sr. No.']

            st.write(f"Processing **Sr. No. {sr_no}**")

            pdf_path = f"{pdf_dir}/doc_{sr_no}.pdf"

            # Download PDF
            if not os.path.exists(pdf_path):
                with st.spinner(f"Downloading PDF for Sr. No. {sr_no}..."):
                    try:
                        download_pdf(url, pdf_path)
                        st.success("PDF downloaded successfully.")
                    except Exception as e:
                        st.error(f"Failed to download PDF: {str(e)}")
                        st.session_state.current_index += 1
                        continue

            # Extract and LLM
            with st.spinner("Extracting PDF text..."):
                pdf_text = extract_pdf_text(pdf_path)
                st.success("PDF text extracted.")

            with st.spinner("Extracting structured details via OpenAI..."):
                extracted_data = extract_pdf_details(pdf_text, OpenAI_api_key)
                st.success("Structured details extracted via OpenAI.")

            result_row = {'Sr. No.': sr_no, 'Source Link': url}

            if "raw_response" in extracted_data:
                st.warning("⚠️ Raw LLM response could not be parsed. Check below:")
                st.code(extracted_data["raw_response"])
            elif "error" in extracted_data:
                st.error(f"Error: {extracted_data['error']}")
            else:
                for field in required_fields:
                    result_row[field] = extracted_data.get(field, 'Not Available')
                st.session_state.results.append(result_row)

            st.session_state.current_index += 1

        st.success("🎉 All rows processed!")

    # Show intermediate output
    if st.session_state.results:
        intermediate_df = pd.DataFrame(st.session_state.results)
        st.subheader("🗃️ Intermediate Results")
        st.dataframe(intermediate_df)

        # Download button
        output_path = "data/output_excel.xlsx"
        intermediate_df.to_excel(output_path, index=False)
        with open(output_path, "rb") as f:
            st.download_button("📥 Download Filled Excel (Current Progress)", f, "extracted_guidance.xlsx")
