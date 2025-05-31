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
# NOTE: Ensure you have a `.streamlit/config.toml` at your repo root with:
#
# [server]
# fileWatcherType = "none"
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
defaults = {
    "last_url": "",
    "proxies": "",
    "submitted": False,
    "video_id": "",
    "langs": {},
    "used_proxy_for_langs": None,
    "selected_lang": "",
    "transcript": "",
    "used_proxy_for_transcript": None,
    "transcript_fetched": False,
    "summary": "",
    "summary_generated": False,
    "quiz": "",
    "quiz_generated": False,
    "mod_instructions": "",
    "updated_quiz": "",
    "updated_pending": False,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ------------------------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------------------------
def get_video_id(url: str) -> str:
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    if "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    return url.strip()

def parse_proxies(proxy_input: str) -> list[str]:
    return [u.strip() for u in proxy_input.split(",") if u.strip()]

def list_languages_yt_dlp(video_id: str) -> dict:
    """
    Use yt_dlp to extract available subtitle language codes (manual + auto).
    Returns a dict {language_code: "manual"/"auto"}.
    """
    try:
        ydl_opts = {"skip_download": True, "quiet": True, "no_warnings": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            manual = {}
            subs = info.get("subtitles") or {}
            for code in subs.keys():
                manual[code] = "manual"
            auto = {}
            ac = info.get("automatic_captions") or {}
            for code in ac.keys():
                if code not in manual:
                    auto[code] = "auto"
            langs = {**manual, **auto}
            return langs
    except Exception:
        return {}

def try_list_transcripts_api(video_id: str, proxies: dict | None) -> dict:
    """
    Try to list via youtube_transcript_api. Returns a dict of language_code -> type,
    or {} if it fails.
    """
    try:
        ts_list = YouTubeTranscriptApi.list_transcripts(video_id, proxies=proxies)
        return {t.language_code: ("auto" if t.is_generated else "manual") for t in ts_list}
    except Exception:
        return {}

def list_transcript_languages(video_id: str, proxy_list: list[str]) -> tuple[dict, dict | None]:
    """
    1) Attempt to list via yt_dlp.
    2) If that fails (langs empty), try youtube_transcript_api (no proxy → proxies).
    Returns (langs_dict, used_proxy_dict_or_None).
    """
    st.info("Attempting to list languages via yt_dlp...")
    langs = list_languages_yt_dlp(video_id)
    if langs:
        st.success(f"✓ Languages found via yt_dlp: {', '.join(langs.keys())}")
        return langs, None

    st.info("Falling back to youtube_transcript_api without proxy...")
    langs = try_list_transcripts_api(video_id, None)
    if langs:
        st.success("✓ Languages found via API without proxy")
        return langs, None

    for p in proxy_list:
        proxy_cfg = {"http": p, "https": p}
        st.info(f"Trying proxy {p} for list_transcripts API...")
        langs = try_list_transcripts_api(video_id, proxy_cfg)
        if langs:
            st.success(f"✓ Languages found via API proxy {p}")
            return langs, proxy_cfg

    st.error("✗ Unable to list transcript languages (yt_dlp + API all failed)")
    return {}, None

def fetch_transcript_yt_dlp(video_id: str, lang: str) -> str:
    """
    Use yt_dlp to download .vtt/.srt for the given language.
    Returns joined text or "".
    """
    try:
        ydl_opts = {
            "skip_download": True,
            "writesubtitles": True,
            "subtitleslangs": [lang],
            "subtitlesformat": "vtt",
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            subs = info.get("requested_subtitles") or info.get("automatic_captions") or {}
            if lang in subs:
                vtt_url = subs[lang]["url"]
                r = requests.get(vtt_url, timeout=10)
                vtt_text = r.text
                lines = []
                for row in vtt_text.splitlines():
                    if row.startswith("WEBVTT") or re.match(r"^\d\d:\d\d:\d\d\.\d\d\d -->", row):
                        continue
                    lines.append(row)
                return "\n".join(lines).strip()
    except Exception:
        pass
    return ""

def try_fetch_transcript_api(video_id: str, lang: str, proxies: dict | None) -> str:
    """
    Try youtube_transcript_api.get_transcript(...). Return raw text or "" if fails.
    """
    try:
        entries = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang], proxies=proxies)
        return "\n".join(e.get("text", "") for e in entries)
    except Exception:
        return ""

def fetch_transcript_with_fallback(video_id: str, lang: str, proxy_list: list[str]) -> tuple[str, dict | None]:
    """
    1) Attempt to fetch via yt_dlp.
    2) If that fails (empty), attempt youtube_transcript_api (no proxy → proxies).
    Returns (transcript_text, used_proxy_dict_or_None).
    """
    st.info("Attempting to fetch transcript via yt_dlp...")
    text = fetch_transcript_yt_dlp(video_id, lang)
    if text:
        st.success("✓ Fetched transcript via yt_dlp")
        return text, None

    st.info("Falling back to youtube_transcript_api without proxy...")
    text = try_fetch_transcript_api(video_id, lang, None)
    if text:
        st.success("✓ Fetched transcript via API without proxy")
        return text, None

    for p in proxy_list:
        proxy_cfg = {"http": p, "https": p}
        st.info(f"Trying proxy {p} for get_transcript API...")
        text = try_fetch_transcript_api(video_id, lang, proxy_cfg)
        if text:
            st.success(f"✓ Fetched transcript via API proxy {p}")
            return text, proxy_cfg

    st.error("✗ Unable to fetch transcript (yt_dlp + API all failed)")
    return "", None

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

def modify_quiz(existing_quiz: str, instructions: str, lang: str) -> str:
    prompt = (
        f"Modify this quiz in {lang} as follows: {instructions}\n\n"
        f"Current quiz:\n{existing_quiz}"
    )
    try:
        resp = client.chat.completions.create(
            model="Meta-Llama-4-Maverick-17B-128E-Instruct-FP8",
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content
    except Exception as e:
        st.error(f"Quiz modification error: {e}")
        st.text(traceback.format_exc())
        return ""

# ------------------------------------------------------------------------------
# Streamlit UI
# ------------------------------------------------------------------------------
st.set_page_config(page_title="YouTube Quiz Generator", layout="wide")
st.title("YouTube Quiz Generator 📚")

# --- Input Form for Mobile-friendly UI ---
with st.form(key="input_form", clear_on_submit=False):
    url_input = st.text_input("YouTube video URL:", value=st.session_state.last_url)
    proxy_input = st.text_input(
        "Optional: HTTP(S) proxy URLs (comma-separated):",
        value=st.session_state.proxies,
    )
    submit_button = st.form_submit_button(label="Load Video & Proxies")

if submit_button:
    st.session_state.last_url = url_input.strip()
    st.session_state.proxies = proxy_input.strip()
    st.session_state.submitted = True
    # Reset downstream state
    st.session_state.video_id = get_video_id(st.session_state.last_url)
    st.session_state.langs = {}
    st.session_state.used_proxy_for_langs = None
    st.session_state.selected_lang = ""
    st.session_state.transcript = ""
    st.session_state.used_proxy_for_transcript = None
    st.session_state.transcript_fetched = False
    st.session_state.summary = ""
    st.session_state.summary_generated = False
    st.session_state.quiz = ""
    st.session_state.quiz_generated = False
    st.session_state.mod_instructions = ""
    st.session_state.updated_quiz = ""
    st.session_state.updated_pending = False

# Only proceed if form was submitted
if st.session_state.submitted and st.session_state.last_url:
    vid = st.session_state.video_id
    proxy_list = parse_proxies(st.session_state.proxies)

    # 1) List available languages (yt_dlp → API no proxy → API with proxy)
    if not st.session_state.langs:
        langs, used_proxy = list_transcript_languages(vid, proxy_list)
        st.session_state.langs = langs
        st.session_state.used_proxy_for_langs = used_proxy

    if not st.session_state.langs:
        st.error("No transcripts available—yt_dlp & API all failed, or IP blocked.")
    else:
        # Let user pick caption language
        st.session_state.selected_lang = st.selectbox(
            "Transcript language:", list(st.session_state.langs.keys()), index=0
        )

        # 2) Show Transcript button
        if not st.session_state.transcript_fetched:
            if st.button("Show Transcript"):
                text, used_proxy_trans = fetch_transcript_with_fallback(
                    st.session_state.video_id,
                    st.session_state.selected_lang,
                    proxy_list,
                )
                st.session_state.transcript = text
                st.session_state.used_proxy_for_transcript = used_proxy_trans
                if not text:
                    st.error("Failed to fetch transcript—yt_dlp & API all failed.")
                else:
                    st.session_state.transcript_fetched = True

        # 3) Display transcript once fetched
        if st.session_state.transcript_fetched and st.session_state.transcript:
            st.subheader("🔹 Transcript")
            st.text_area(
                "Transcript text:",
                value=st.session_state.transcript,
                height=200,
                disabled=True
            )

            # 4) Generate summary button
            if not st.session_state.summary_generated:
                if st.button("Generate Summary"):
                    with st.spinner("Summarizing transcript…"):
                        st.session_state.summary = summarize_transcript(
                            st.session_state.transcript, st.session_state.selected_lang
                        )
                        st.session_state.summary_generated = True

        # 5) Display summary if generated
        if st.session_state.summary_generated and st.session_state.summary:
            st.subheader("🔹 Summary")
            st.write(st.session_state.summary)

            # 6) Quiz specification & generation
            grade = st.text_input("Student's grade level:", value="10")
            num_q = st.number_input("Number of questions:", min_value=1, max_value=20, value=5)
            if not st.session_state.quiz_generated:
                if st.button("Generate Quiz"):
                    with st.spinner("Creating quiz…"):
                        st.session_state.quiz = generate_quiz(
                            st.session_state.summary,
                            st.session_state.selected_lang,
                            grade,
                            int(num_q),
                        )
                        st.session_state.quiz_generated = True

        # 7) Display quiz if generated
        if st.session_state.quiz_generated and st.session_state.quiz:
            st.subheader("🔹 Quiz")
            st.write(st.session_state.quiz)

            # 8) Modification instructions UI
            st.markdown("**Modify the quiz (optional):**")
            _ = st.text_area(
                "Enter modification instructions:",
                value=st.session_state.mod_instructions,
                key="mod_instructions",
                height=120
            )

            # 9) Apply modifications button
            if st.button("Apply Modifications"):
                instructions = st.session_state.mod_instructions
                if instructions.strip():
                    with st.spinner("Applying modifications…"):
                        modified = modify_quiz(
                            st.session_state.quiz,
                            instructions,
                            st.session_state.selected_lang
                        )
                        if modified:
                            st.session_state.updated_quiz = modified
                            st.session_state.updated_pending = True
                            st.success("Modifications ready. Click 'Show Updated Quiz' to view.")
                else:
                    st.warning("Please enter instructions to modify the quiz.")

            # 10) Show Updated Quiz button
            if st.session_state.updated_pending:
                if st.button("Show Updated Quiz"):
                    st.session_state.quiz = st.session_state.updated_quiz
                    st.session_state.updated_pending = False
                    st.success("Displaying updated quiz below.")
                    st.subheader("🔹 Quiz (Updated)")
                    st.write(st.session_state.quiz)
