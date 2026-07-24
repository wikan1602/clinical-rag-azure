import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Clinical Knowledge Assistant", page_icon="🩺")
st.title("Clinical Knowledge Assistant")
st.caption("RAG over public WHO clinical guidelines (hypertension, diabetes, cardiovascular risk)")

strategy = st.sidebar.radio("Chunking strategy", ["semantic", "fixed"], index=0)
top_k = st.sidebar.slider("Chunks to retrieve", min_value=1, max_value=10, value=5)

question = st.text_input("Ask a question about the WHO guidelines corpus")

if st.button("Ask") and question:
    with st.spinner("Retrieving context and generating answer..."):
        try:
            response = requests.post(
                f"{API_URL}/query",
                json={"question": question, "strategy": strategy, "top_k": top_k},
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            st.error(f"Request failed: {e}")
        else:
            st.subheader("Answer")
            st.write(data["answer"])

            st.subheader(f"Retrieved chunks ({strategy})")
            for i, chunk in enumerate(data["chunks"], start=1):
                with st.expander(f"[{i}] {chunk['source']} (score: {chunk['score']:.4f})"):
                    st.write(chunk["content"])
