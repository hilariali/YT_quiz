import streamlit as st
import re
import subprocess
from pytube import YouTube
from pytube.exceptions import RegexMatchError, VideoUnavailable
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from urllib.error import HTTPError, URLError
import textwrap
import openai

# ------------------------------------------------------------------------------
# NOTE: Make sure you have a `.streamlit/config.toml` at your repo root with:
#
#   [server]
#   fileWatcherType = "none"
#
# to disable the inotify limit error in hosted environments.
# ------------------------------------------------------------------------------

# Initialize OpenAI client (adjust base_url if you're using a custom endpoint)
client = openai.OpenAI(
    api_key=st.secrets["OPENAI_API_KEY"],
    base_url=st.secrets.get("OPENAI_BASE_URL")
)

# Constants
CHUNK_SIZE = 100000   # characters per transcript chunk
MAX_TITLE_LENGTH = 50 # max filename length if you enable downloading

# ------------------------------------------------------------------------------
# Session state defaults
# ------------------------------------------------------------------------------
if "last_url" not in st.session_state:
    st.session_state.last_url = ""
if "proxies" not in st.session_state:
    st.session_state.proxies = ""
if "transcript" not in st.session_state:
    st.session_state.transcript = ""
if "summary" not in st.session_state:
    st.session_state.summary = ""
if "quiz" not in st.session_state:
    st.session_state.quiz = ""

# ------------------------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------------------------
def make_proxy_dict(proxy_input: str):
    """Build a proxies dict for youtube-transcript-api from comma-sep input."""
    urls = [u.strip() for u in proxy_input.split(",") if u.strip()]
    if not urls:
        return None
    # use the first proxy for both http and https
    return {"http": urls[0], "https": urls[0]}

def get_video_id(url: str) -> str:
    """Extract the YouTube video ID from a URL or ID."""
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    if "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    return url

def list_transcript_languages(video_id: str, proxies=None) -> dict:
    """Return available caption languages, handling errors gracefully."""
    try:
        ts_list = YouTubeTranscriptApi.list_transcripts(video_id, proxies=proxies)
    except (TranscriptsDisabled, NoTranscriptFound, HTTPError, URLError):
        return {}
    return {t.language_code: ("auto" if t.is_generated else "manual") for t in ts_list}

def fetch_transcript(video_id: str, lang: str, proxies=None) -> str:
    """Fetch the raw transcript text for a given language using optional proxies."""
    try:
        entries = YouTubeTranscriptApi.get_transcript(
            video_id, languages=[lang], proxies=proxies
        )
    except Exception:
        return ""
    return "\n".join(e.get("text", "") for e in entries)

def summarize_chunk(text: str, lang: str) -> str:
    """Summarize a chunk of transcript via your Meta-Llama model."""
    prompt = f"Please summarize the following transcript chunk in {lang}:\n\n{text}"
    resp = client.chat.completions.create(
        model="Meta-Llama-4-Maverick-17B-128E-Instruct-FP8",
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content

def summarize_transcript(transcript: str, lang: str) -> str:
    """Chunk large transcripts and combine summaries."""
    if len(transcript) <= CHUNK_SIZE:
        return summarize_chunk(transcript, lang)
    parts = []
    for i in range(0, len(transcript), CHUNK_SIZE):
        parts.append(summarize_chunk(transcript[i : i + CHUNK_SIZE], lang))
    return summarize_chunk("\n".join(parts), lang)

def generate_quiz(summary: str, lang: str, grade: str, num_questions: int) -> str:
    """Generate a multiple-choice quiz from a summary."""
    prompt = (
        f"Create a {num_questions}-question multiple-choice quiz in {lang} "
        f"for grade {grade} students based on this summary:\n\n{summary}"
    )
    resp = client.chat.completions.create(
        model="Meta-Llama-4-Maverick-17B-128E-Instruct-FP8",
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content

# ------------------------------------------------------------------------------
# Streamlit UI
# ------------------------------------------------------------------------------
st.set_page_config(page_title="YouTube Quiz Generator")
st.title("YouTube Quiz Generator 📚")

# 1) Input: YouTube URL
url = st.text_input("YouTube video URL:", value=st.session_state.last_url)
if url != st.session_state.last_url:
    # reset state when URL changes
    st.session_state.last_url = url
    st.session_state.transcript = ""
    st.session_state.summary = ""
    st.session_state.quiz = ""

# 2) Optional: proxy list
proxy_input = st.text_input(
    "Optional: HTTP(S) proxy URLs (comma-separated):",
    value=st.session_state.proxies,
)
st.session_state.proxies = proxy_input
proxy_dict = make_proxy_dict(proxy_input)

if url:
    vid = get_video_id(url)
    langs = list_transcript_languages(vid, proxies=proxy_dict)
    if not langs:
        st.error("No transcripts found — your IP may be blocked. Try a proxy above.")
    else:
        # select language
        lang = st.selectbox("Transcript language:", list(langs.keys()))

        # Generate summary
        if st.button("Generate Summary"):
            with st.spinner("Fetching transcript…"):
                st.session_state.transcript = fetch_transcript(vid, lang, proxies=proxy_dict)
            if not st.session_state.transcript:
                st.error("Failed to fetch transcript. Try another proxy or URL.")
            else:
                with st.spinner("Summarizing…"):
                    st.session_state.summary = summarize_transcript(st.session_state.transcript, lang)

        # Show summary
        if st.session_state.summary:
            st.subheader("Summary")
            st.write(st.session_state.summary)

            # Quiz parameters
            grade = st.text_input("Student's grade level:", value="10")
            num_q = st.number_input("Number of questions:", min_value=1, max_value=20, value=5)

            # Generate quiz
            if st.button("Generate Quiz"):
                with st.spinner("Creating quiz…"):
                    st.session_state.quiz = generate_quiz(st.session_state.summary, lang, grade, int(num_q))

        # Show quiz
        if st.session_state.quiz:
            st.subheader("Quiz")
            st.write(st.session_state.quiz)
