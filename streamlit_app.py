import streamlit as st
# Note: fileWatcherType must be set via config.toml or CLI, not in code

import re
import subprocess
from pytube import YouTube
from pytube.exceptions import RegexMatchError, VideoUnavailable
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from urllib.error import HTTPError, URLError
import textwrap
import openai

# Initialize OpenAI client using your existing setup
client = openai.OpenAI(
    api_key=st.secrets["OPENAI_API_KEY"],
    base_url=st.secrets["OPENAI_BASE_URL"]
)

# Constants
CHUNK_SIZE = 100000  # Characters per transcript chunk
MAX_TITLE_LENGTH = 50  # Max filename length

# Utility functions
def sanitize_title(title: str, max_length: int = MAX_TITLE_LENGTH) -> str:
    safe = re.sub(r'[\\/*?:"<>|]', '', title)
    return re.sub(r"\s+", ' ', safe).strip()[:max_length].rstrip()

def get_video_id(url: str) -> str:
    if 'v=' in url:
        return url.split('v=')[1].split('&')[0]
    if 'youtu.be/' in url:
        return url.split('youtu.be/')[1].split('?')[0]
    return url

def list_transcript_languages(video_id: str) -> dict:
    try:
        transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
    except (TranscriptsDisabled, NoTranscriptFound):
        return {}
    return {t.language_code: ('auto' if t.is_generated else 'manual') for t in transcripts}

def fetch_transcript(video_id: str, lang: str) -> str:
    """
    Fetch transcript text safely, returning empty on any failure.
    """
    try:
        entries = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
    except Exception:
        return ''
    if not entries:
        return ''
    try:
        return '\n'.join(item.get('text', '') for item in entries)
    except Exception:
        return ''

# Summarization and quiz generation using Meta-Llama
def summarize_chunk(text: str, lang: str) -> str:
    prompt = f"Please summarize the following transcript chunk in {lang}:\n\n{text}"
    try:
        resp = client.chat.completions.create(
            model="Meta-Llama-4-Maverick-17B-128E-Instruct-FP8",
            messages=[{'role':'user','content': prompt}],
        )
        return resp.choices[0].message.content
    except Exception as e:
        st.error(f"Summarization error: {e}")
        return ''

def summarize_transcript(transcript: str, lang: str) -> str:
    if len(transcript) <= CHUNK_SIZE:
        return summarize_chunk(transcript, lang)
    parts = []
    for i in range(0, len(transcript), CHUNK_SIZE):
        chunk = transcript[i:i+CHUNK_SIZE]
        parts.append(summarize_chunk(chunk, lang))
    combined = '\n'.join(parts)
    return summarize_chunk(combined, lang)

def generate_quiz(summary: str, lang: str, grade: str, num_questions: int) -> str:
    prompt = (
        f"Create a {num_questions}-question multiple-choice quiz in {lang} "
        f"for grade {grade} students based on this summary:\n{summary}"
    )
    try:
        resp = client.chat.completions.create(
            model="Meta-Llama-4-Maverick-17B-128E-Instruct-FP8",
            messages=[{'role':'user','content': prompt}],
        )
        return resp.choices[0].message.content
    except Exception as e:
        st.error(f"Quiz generation error: {e}")
        return ''

# Streamlit UI
st.set_page_config(page_title="YouTube Quiz Generator")
st.title("YouTube Quiz Generator 📚")

url = st.text_input("YouTube video URL:")
if url:
    video_id = get_video_id(url)
    langs = list_transcript_languages(video_id)
    if not langs:
        st.error("No transcripts available for this video.")
    else:
        lang = st.selectbox("Transcript language:", list(langs.keys()))
        if st.button("Generate Summary & Quiz"):
            with st.spinner("Fetching transcript..."):
                transcript = fetch_transcript(video_id, lang)
            if not transcript:
                st.error("Failed to fetch transcript in this language.")
            else:
                with st.spinner("Summarizing transcript..."):
                    summary = summarize_transcript(transcript, lang)
                if summary:
                    st.subheader("Summary")
                    st.write(summary)

                    grade = st.text_input("Student's grade level:", value="10")
                    num_q = st.number_input("Number of multiple-choice questions:", min_value=1, max_value=20, value=5)
                    if st.button("Generate Quiz"):
                        with st.spinner("Generating quiz..."):
                            quiz = generate_quiz(summary, lang, grade, int(num_q))
                        if quiz:
                            st.subheader("Quiz")
                            st.write(quiz)
