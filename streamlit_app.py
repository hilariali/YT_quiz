import streamlit as st
import re
import openai
import traceback
import requests
import yt_dlp

from pytube import YouTube
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
)
from urllib.error import HTTPError, URLError

# ------------------------------------------------------------------------------
# NOTE: Make sure you have a `.streamlit/config.toml` in your repo root with:
#
# [server]
# fileWatcherType = "none"
#
# to disable file‐watcher errors on Streamlit Cloud.
# ------------------------------------------------------------------------------

# Initialize OpenAI client (adjust base_url if you use a custom endpoint)
client = openai.OpenAI(
    api_key=st.secrets["OPENAI_API_KEY"],
    base_url=st.secrets.get("OPENAI_BASE_URL")  # optional
)

# Constants
CHUNK_SIZE = 100000   # characters per transcript chunk

# ------------------------------------------------------------------------------
# Session state defaults
# ------------------------------------------------------------------------------
for key in ["last_url", "proxies", "transcript", "summary", "quiz"]:
    if key not in st.session_state:
        st.session_state[key] = ""

# ------------------------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------------------------
def get_video_id(url: str) -> str:
    """Extract the YouTube video ID from a URL or ID string."""
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    if "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    return url.strip()


def parse_proxies(proxy_input: str) -> list[str]:
    """
    Convert a comma-separated string into a list of proxy URLs:
    e.g. "http://1.2.3.4:8080, http://5.6.7.8:3128"
    → ["http://1.2.3.4:8080", "http://5.6.7.8:3128"]
    """
    return [u.strip() for u in proxy_input.split(",") if u.strip()]


def try_list_transcripts(video_id: str, proxies: dict | None) -> dict:
    """
    Try YouTubeTranscriptApi.list_transcripts(...).
    Returns a dict of {language_code: "manual"/"auto"} on success,
    or {} if it fails.
    """
    try:
        ts_list = YouTubeTranscriptApi.list_transcripts(video_id, proxies=proxies)
        return {t.language_code: ("auto" if t.is_generated else "manual") for t in ts_list}
    except Exception as e:
        st.warning(f"  • list_transcripts failed (proxies={proxies}): {e}")
        return {}


def list_transcript_languages(video_id: str, proxy_list: list[str]) -> tuple[dict, dict | None]:
    """
    1) Try listing without any proxy.
    2) If that fails, try each proxy in proxy_list one by one.
    Returns (langs_dict, used_proxy_dict) or ({}, None) if none succeeded.
    """
    st.info("Attempting to list transcript languages without proxy…")
    langs = try_list_transcripts(video_id, None)
    if langs:
        st.success("✓ Languages found without proxy")
        return langs, None

    # Try each proxy
    for p in proxy_list:
        proxy_cfg = {"http": p, "https": p}
        st.info(f"Trying proxy {p} for list_transcripts…")
        langs = try_list_transcripts(video_id, proxy_cfg)
        if langs:
            st.success(f"✓ Languages found via proxy {p}")
            return langs, proxy_cfg

    st.error("✗ Unable to list transcript languages (all proxies failed)")
    return {}, None


def try_fetch_transcript(video_id: str, lang: str, proxies: dict | None) -> str:
    """
    Try YouTubeTranscriptApi.get_transcript(...). Return raw text or "" if fails.
    """
    try:
        entries = YouTubeTranscriptApi.get_transcript(
            video_id, languages=[lang], proxies=proxies
        )
        return "\n".join(e.get("text", "") for e in entries)
    except Exception as e:
        st.warning(f"  • get_transcript failed (proxies={proxies}): {e}")
        return ""


def fetch_transcript_with_fallback(
    video_id: str, lang: str, proxy_list: list[str]
) -> tuple[str, dict | None]:
    """
    1) Try get_transcript(...) with no proxy.
    2) Then iterate through proxy_list.
    3) If still fails, fall back to yt_dlp to scrape subtitles.
    Returns (transcript_text, used_proxy_dict_or_None).
    """
    # Attempt #1: no proxy
    st.info("Fetching transcript with no proxy…")
    text = try_fetch_transcript(video_id, lang, None)
    if text:
        st.success("✓ Fetched transcript without proxy")
        return text, None

    # Attempt #2: try each proxy
    for p in proxy_list:
        cfg = {"http": p, "https": p}
        st.info(f"Trying proxy {p} for transcript fetch…")
        text = try_fetch_transcript(video_id, lang, cfg)
        if text:
            st.success(f"✓ Fetched transcript via proxy {p}")
            return text, cfg

    # Attempt #3: yt_dlp fallback
    st.info("Falling back to yt_dlp to scrape subtitles…")
    try:
        ydl_opts = {
            "skip_download": True,
            "writesubtitles": True,
            "subtitleslangs": [lang],  # try this language code
            "subtitlesformat": "vtt",  # get VTT if available
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            # The info dict may contain 'requested_subtitles' or 'automatic_captions'
            subs = info.get("requested_subtitles") or info.get("automatic_captions") or {}
            if lang in subs:
                vtt_url = subs[lang]["url"]
                # Download the VTT file and strip timing cues
                r = requests.get(vtt_url, timeout=10)
                vtt_text = r.text
                lines = []
                for row in vtt_text.splitlines():
                    # skip WEBVTT header and timing lines (e.g. "00:00:01.000 --> 00:00:03.000")
                    if row.startswith("WEBVTT") or re.match(r"^\d\d:\d\d:\d\d\.\d\d\d -->", row):
                        continue
                    lines.append(row)
                transcript_text = "\n".join(lines).strip()
                if transcript_text:
                    st.success("✓ Fetched transcript via yt_dlp")
                    return transcript_text, None
                else:
                    st.warning("yt_dlp found subtitles but they were empty.")
            else:
                st.warning("yt_dlp fallback did not find a subtitle track for this language.")
    except Exception as e:
        st.warning(f"yt_dlp fallback error: {e}")

    # All methods failed
    return "", None


# ------------------------------------------------------------------------------
# Summarization & Quiz helpers
# ------------------------------------------------------------------------------
def summarize_chunk(text: str, lang: str) -> str:
    prompt = f"Please summarize the following transcript chunk in {lang}:\n\n{text}"
    try:
        resp = client.chat.completions.create(
            model="Meta-Llama-4-Maverick-17B-128E-Instruct-FP8",
            messages=[{"role": "user", "content": prompt}],
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
        parts.append(summarize_chunk(transcript[i : i + CHUNK_SIZE], lang))
    return summarize_chunk("\n".join(parts), lang)


def generate_quiz(summary: str, lang: str, grade: str, num_questions: int) -> str:
    prompt = (
        f"Create a {num_questions}-question multiple-choice quiz in {lang} "
        f"for grade {grade} students based on this summary:\n\n{summary}"
    )
    try:
        resp = client.chat.completions.create(
            model="Meta-Llama-4-Maverick-17B-128E-Instruct-FP8",
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content
    except Exception as e:
        st.error(f"Quiz generation error: {e}")
        st.text(traceback.format_exc())
        return ""


# ------------------------------------------------------------------------------
# Streamlit UI
# ------------------------------------------------------------------------------
st.set_page_config(page_title="YouTube Quiz Generator")
st.title("YouTube Quiz Generator 📚")

# 1) Input: YouTube URL
url = st.text_input("YouTube video URL:", value=st.session_state.last_url or "")
if url != st.session_state.last_url:
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
proxy_list = parse_proxies(proxy_input)

if url:
    vid = get_video_id(url)

    # 3) List available languages (no proxy → each proxy)
    langs, used_proxy = list_transcript_languages(vid, proxy_list)
    if not langs:
        st.error("No transcripts available—your IP may be blocked. Try different proxies.")
    else:
        # Let user pick caption language
        lang = st.selectbox("Transcript language:", list(langs.keys()))

        # 4) Generate summary (with fallback chain #1 → #2)
        if st.button("Generate Summary"):
            text, transcript_proxy = fetch_transcript_with_fallback(vid, lang, proxy_list)
            st.session_state.transcript = text
            if not text:
                st.error("Failed to fetch transcript—try different proxies or URL.")
            else:
                with st.spinner("Summarizing transcript…"):
                    st.session_state.summary = summarize_transcript(text, lang)

        # 5) Display summary if available
        if st.session_state.summary:
            st.subheader("Summary")
            st.write(st.session_state.summary)

            # 6) Quiz parameters
            grade = st.text_input("Student's grade level:", value="10")
            num_q = st.number_input("Number of questions:", min_value=1, max_value=20, value=5)

            # 7) Generate quiz
            if st.button("Generate Quiz"):
                with st.spinner("Creating quiz…"):
                    st.session_state.quiz = generate_quiz(
                        st.session_state.summary, lang, grade, int(num_q)
                    )

        # 8) Display quiz if available
        if st.session_state.quiz:
            st.subheader("Quiz")
            st.write(st.session_state.quiz)
