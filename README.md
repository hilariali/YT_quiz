# YouTube Quiz Generator

A Streamlit app that takes a YouTube video URL, fetches its transcript, summarizes it via OpenAI, and generates a multiple-choice quiz.

## Setup

1. **Clone the repo**
   ```bash
   git clone <your-repo-url>
   cd <repo-folder>
   ```
2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure your OpenAI key**
   - Create a file named `.streamlit/secrets.toml` with:
     ```toml
     ["OPENAI_API_KEY"]
     value = "YOUR_OPENAI_API_KEY"
     ```
4. **Run locally**
   ```bash
   streamlit run streamlit_app.py
   ```
