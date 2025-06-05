# AI Tools Hub


This Streamlit app opens with a simple landing page displaying a placeholder logo and buttons for each available tool. The main tool is the **YouTube Quiz Generator**, which fetches a video's transcript, summarizes it with OpenAI, and creates a multiple-choice quiz. Every tool page includes a **Back to Home** button so you can easily return to the landing page.



This Streamlit app now starts with a simple landing page that lets you select from multiple tools. The main tool is the **YouTube Quiz Generator** which takes a YouTube video URL, fetches its transcript, summarizes it via OpenAI, and generates a multiple-choice quiz. Each tool page provides a button to return to the home screen.





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
