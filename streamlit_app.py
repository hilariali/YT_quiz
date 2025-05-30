import streamlit as st
import re
import subprocess
from pytube import YouTube
from pytube.exceptions import RegexMatchError, VideoUnavailable
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from urllib.error import HTTPError, URLError
import textwrap
import openai
import traceback

# ------------------------------------------------------------------------------
# NOTE: Make sure you have a `.streamlit/config.toml` at your repo root with:
#
#   [server]
#   fileWatcherType = "none"
#
# to disable file-watcher errors in hosted environments.
# ------------------------------------------------------------------------------

# Initialize OpenAI client
client = openai.OpenAI(
    api_key=st.secrets["OPENAI_API_KEY"],
    base_url=st.secrets.get("OPENAI_BASE_URL")  # optional
)

# Constants
CHUNK_SIZE = 100000   # characters per transcript chunk
MAX_TITLE_LENGTH = 50 # max filename length if you enable downloading

# Session state defaults
for key in ["last_url", "proxies", "transcript", "summary", "quiz"]:
    if key not in st.session_state:
        st.session_state[key] = "" if key != "quiz" else ""

# ----------------------------------------------------------------------------
# Utility functions
# ----------------------------------------------------------------------------
def get_video_id(url: str) -> str:
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    if "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    return url


def parse_proxies(proxy_input: str) -> list[str]:
    return [u.strip() for u in proxy_input.split(",") if u.strip()]


def try_list_transcripts(video_id: str, proxies: dict|None) -> dict:
    try:
        return {t.language_code: ('auto' if t.is_generated else 'manual')
                for t in YouTubeTranscriptApi.list_transcripts(video_id, proxies=proxies)}
    except Exception as e:
        st.warning(f"List transcripts failed (proxies={proxies}): {e}")
        return {}


def list_transcript_languages(video_id: str, proxy_list: list[str]) -> tuple[dict, dict|None]:
    # Try without proxy first
    st.info("Fetching available languages without proxy...")
    langs = try_list_transcripts(video_id, None)
    if langs:
        st.success("Fetched transcript languages without proxy")
        return langs, None
    # Try each proxy in turn
    for p in proxy_list:
        proxy_cfg = {"http": p, "https": p}
        st.info(f"Trying proxy {p} for listing transcripts...")
        langs = try_list_transcripts(video_id, proxy_cfg)
        if langs:
            st.success(f"Fetched languages via proxy {p}")
            return langs, proxy_cfg
    # none worked
    return {}, None


def try_fetch_transcript(video_id: str, lang: str, proxies: dict|None) -> str:
    try:
        entries = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang], proxies=proxies)
        return "\n".join(e.get('text','') for e in entries)
    except Exception as e:
        st.warning(f"Fetch transcript failed (proxies={proxies}): {e}")
        return ""


def fetch_transcript_with_fallback(video_id: str, lang: str, proxy_list: list[str]) -> tuple[str, dict|None]:
    st.info("Fetching transcript without proxy...")
    text = try_fetch_transcript(video_id, lang, None)
    if text:
        st.success("Fetched transcript without proxy")
        return text, None
    for p in proxy_list:
        proxy_cfg = {"http": p, "https": p}
        st.info(f"Trying proxy {p} for transcript fetch...")
        text = try_fetch_transcript(video_id, lang, proxy_cfg)
        if text:
            st.success(f"Fetched transcript via proxy {p}")
            return text, proxy_cfg
    return "", None


def summarize_chunk(text: str, lang: str) -> str:
    prompt = f"Please summarize the following transcript chunk in {lang}:\n\n{text}"
    try:
        resp = client.chat.completions.create(
            model="Meta-Llama-4-Maverick-17B-128E-Instruct-FP8",
            messages=[{"role":"user","content":prompt}],
        )
        return resp.choices[0].message.content
    except Exception as e:
        st.error(f"Summarization error: {e}")
        st.text(traceback.format_exc())
        return ""


def summarize_transcript(transcript: str, lang: str) -> str:
    if len(transcript) <= CHUNK_SIZE:
        return summarize_chunk(transcript, lang)
    parts = []
    for i in range(0, len(transcript), CHUNK_SIZE):
        parts.append(summarize_chunk(transcript[i:i+CHUNK_SIZE], lang))
    return summarize_chunk("\n".join(parts), lang)


def generate_quiz(summary: str, lang: str, grade: str, num_questions: int) -> str:
    prompt = (
        f"Create a {num_questions}-question multiple-choice quiz in {lang} "
        f"for grade {grade} students based on this summary:\n{summary}"
    )
    try:
        resp = client.chat.completions.create(
            model="Meta-Llama-4-Maverick-17B-128E-Instruct-FP8",
            messages=[{"role":"user","content":prompt}],
        )
        return resp.choices[0].message.content
    except Exception as e:
        st.error(f"Quiz generation error: {e}")
        st.text(traceback.format_exc())
        return ""

# ----------------------------------------------------------------------------
# Streamlit UI
# ----------------------------------------------------------------------------
st.set_page_config(page_title="YouTube Quiz Generator")
st.title("YouTube Quiz Generator 📚")

# URL input
url = st.text_input("YouTube video URL:", value=st.session_state.last_url)
if url != st.session_state.last_url:
    st.session_state.last_url = url
    st.session_state.transcript = ""
    st.session_state.summary = ""
    st.session_state.quiz = ""

# Proxy input
proxy_input = st.text_input(
    "Optional: HTTP(S) proxy URLs (comma-separated):",
    value=st.session_state.proxies,
)
st.session_state.proxies = proxy_input
proxy_list = parse_proxies(proxy_input)

if url:
    vid = get_video_id(url)
    # List languages with fallback
    langs, used_proxy = list_transcript_languages(vid, proxy_list)
    if not langs:
        st.error("No transcripts available — IP may be blocked. Try adding proxies.")
    else:
        lang = st.selectbox("Transcript language:", list(langs.keys()))

        # Generate summary
        if st.button("Generate Summary"):
            st.session_state.transcript, fetch_proxy = fetch_transcript_with_fallback(vid, lang, proxy_list)
            if not st.session_state.transcript:
                st.error("Failed to fetch transcript — try different proxies.")
            else:
                with st.spinner("Summarizing transcript…"):
                    st.session_state.summary = summarize_transcript(st.session_state.transcript, lang)

        # Display summary
        if st.session_state.summary:
            st.subheader("Summary")
            st.write(st.session_state.summary)
            grade = st.text_input("Student's grade level:", value="10")
            num_q = st.number_input("Number of questions:", min_value=1, max_value=20, value=5)

            # Generate quiz
            if st.button("Generate Quiz"):
                with st.spinner("Creating quiz…"):
                    st.session_state.quiz = generate_quiz(
                        st.session_state.summary, lang, grade, int(num_q)
                    )

        # Display quiz
        if st.session_state.quiz:
            st.subheader("Quiz")
            st.write(st.session_state.quiz)
