# RAG Chatbot for DSA

## Overview

A simple chatbot using Retrieval-Augmented Generation (RAG) to help students with Data Structures and Algorithms (DSA). It provides explanations and guides users through DSA topics step-by-step.

## Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/elroylian/chatbot.git
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Split Documents into Chunks and store in DB
   - Ensure you have the necessary data in the path "data/books/"
   - Run the cell in initial.ipynb to split the documents into chunks and store it in local DB
   ```
4. Run the app:
   ```bash
   streamlit run app.py
   ```

## Usage

- Ask DSA-related questions to get explanations and guidance.
- The chatbot will prompt for clarifications if needed.

## Technologies

- **Python**
- **Streamlit**
- **RAG (Retrieval-Augmented Generation)**
