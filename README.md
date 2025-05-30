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
3. **Configure Streamlit settings**
   - Create `.streamlit/config.toml` with:
     ```toml
     [server]
     fileWatcherType = "none"
     ```
4. **Set OpenAI secrets**
   - In Streamlit Cloud secrets, add:
     - `OPENAI_API_KEY`
     - `OPENAI_BASE_URL`
5. **Deploy or run locally**
   ```bash
   streamlit run streamlit_app.py
   ```
