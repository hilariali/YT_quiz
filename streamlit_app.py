import streamlit as st
import re
import openai
from pytube import YouTube
from pytube.exceptions import RegexMatchError, VideoUnavailable
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from urllib.error import HTTPError, URLError

# Initialize OpenAI client
client = openai.OpenAI(
    api_key=st.secrets["OPENAI_API_KEY"],
    base_url=st.secrets.get("OPENAI_BASE_URL")  # optional
)

CHUNK_SIZE = 100000
MAX_TITLE_LENGTH = 50

# Session-state defaults
if 'summary' not in st.session_state:
    st.session_state.summary = None
if 'transcript' not in st.session_state:
    st.session_state.transcript = None
if 'quiz' not in st.session_state:
    st.session_state.quiz = None
if 'last_url' not in st.session_state:
    st.session_state.last_url = None

def sanitize_title(title):
    safe = re.sub(r'[\\/*?:"<>|]', '', title)
    return re.sub(r"\s+", " ", safe).strip()[:MAX_TITLE_LENGTH]

def get_video_id(url):
    if 'v=' in url:
        return url.split('v=')[1].split('&')[0]
    if 'youtu.be/' in url:
        return url.split('youtu.be/')[1].split('?')[0]
    return url

def list_transcript_languages(vid):
    try:
        ts = YouTubeTranscriptApi.list_transcripts(vid)
    except (TranscriptsDisabled, NoTranscriptFound):
        return {}
    return {t.language_code: ('auto' if t.is_generated else 'manual') for t in ts}

def fetch_transcript(video_id, lang):
    try:
        entries = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
    except Exception:
        return ""
    return "\n".join(e.get('text','') for e in entries)

def summarize_chunk(text, lang):
    resp = client.chat.completions.create(
        model="Meta-Llama-4-Maverick-17B-128E-Instruct-FP8",
        messages=[{'role':'user','content':f"Please summarize the following transcript chunk in {lang}:\n\n{text}"}]
    )
    return resp.choices[0].message.content

def summarize_transcript(transcript, lang):
    if len(transcript) <= CHUNK_SIZE:
        return summarize_chunk(transcript, lang)
    parts = [summarize_chunk(transcript[i:i+CHUNK_SIZE], lang)
             for i in range(0, len(transcript), CHUNK_SIZE)]
    return summarize_chunk("\n".join(parts), lang)

def generate_quiz(summary, lang, grade, num_q):
    resp = client.chat.completions.create(
        model="Meta-Llama-4-Maverick-17B-128E-Instruct-FP8",
        messages=[{'role':'user','content':(
            f"Create a {num_q}-question multiple-choice quiz in {lang} for grade {grade} "
            f"students based on this summary:\n{summary}"
        )}]
    )
    return resp.choices[0].message.content

st.set_page_config(page_title="YouTube Quiz Generator")
st.title("YouTube Quiz Generator 🚀")

url = st.text_input("YouTube video URL:", value=st.session_state.last_url or "")
if url != st.session_state.last_url:
    # clear previous state on URL change
    st.session_state.last_url = url
    st.session_state.summary = None
    st.session_state.transcript = None
    st.session_state.quiz = None

if url:
    vid = get_video_id(url)
    langs = list_transcript_languages(vid)
    if not langs:
        st.error("No transcripts available for this video.")
    else:
        lang = st.selectbox("Transcript language:", list(langs.keys()))
        if st.button("Generate Summary"):
            with st.spinner("Fetching and summarizing…"):
                st.session_state.transcript = fetch_transcript(vid, lang)
                if not st.session_state.transcript:
                    st.error("Could not fetch transcript.")
                else:
                    st.session_state.summary = summarize_transcript(st.session_state.transcript, lang)

        if st.session_state.summary:
            st.subheader("Summary")
            st.write(st.session_state.summary)

            grade = st.text_input("Grade level:", "10")
            num_q = st.number_input("Number of questions:", 1, 20, 5)
            if st.button("Generate Quiz"):
                with st.spinner("Creating quiz…"):
                    st.session_state.quiz = generate_quiz(
                        st.session_state.summary, lang, grade, int(num_q)
                    )

        if st.session_state.quiz:
            st.subheader("Quiz")
            st.write(st.session_state.quiz)
