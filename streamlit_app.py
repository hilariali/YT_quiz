import streamlit as st
import openai
import re
from pytube import YouTube
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

# Utility functions
def sanitize_title(title: str, max_length: int = 50) -> str:
    safe = re.sub(r'[\\/*?:"<>|]', '', title)
    safe = re.sub(r"\s+", ' ', safe).strip()
    return safe[:max_length].rstrip()

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
    try:
        entries = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
    except (TranscriptsDisabled, NoTranscriptFound):
        return ''
    return ' '.join(e['text'] for e in entries)

# Summarization and quiz generation
CHUNK_SIZE = 100000

def summarize_transcript(transcript: str, lang: str) -> str:
    def summarize_chunk(text: str) -> str:
        prompt = f"Summarize the following transcript chunk in {lang}:\n\n{text}"
        resp = openai.ChatCompletion.create(
            model='gpt-4',
            messages=[{'role':'user','content': prompt}]
        )
        return resp.choices[0].message.content

    if len(transcript) <= CHUNK_SIZE:
        return summarize_chunk(transcript)
    parts = []
    for i in range(0, len(transcript), CHUNK_SIZE):
        parts.append(summarize_chunk(transcript[i:i+CHUNK_SIZE]))
    return summarize_chunk(' '.join(parts))

def generate_quiz(summary: str, lang: str, grade: str, num_questions: int) -> str:
    prompt = (
        f"Create a {num_questions}-question multiple-choice quiz in {lang} "
        f"for grade {grade} based on the following summary:\n\n{summary}"
    )
    resp = openai.ChatCompletion.create(
        model='gpt-4',
        messages=[{'role':'user','content': prompt}]
    )
    return resp.choices[0].message.content

# Streamlit Interface
st.set_page_config(page_title="YouTube Quiz Generator")
st.title("YouTube Quiz Generator")
openai.api_key = st.secrets["OPENAI_API_KEY"]

url = st.text_input("Enter YouTube video URL:")
if url:
    video_id = get_video_id(url)
    langs = list_transcript_languages(video_id)
    if langs:
        lang = st.selectbox("Transcript Language:", list(langs.keys()))
        if st.button("Generate Summary"):
            with st.spinner("Fetching transcript and summarizing..."):
                transcript = fetch_transcript(video_id, lang)
                if not transcript:
                    st.error("No transcript available in that language.")
                else:
                    summary = summarize_transcript(transcript, lang)
                    st.subheader("Summary")
                    st.write(summary)

                    grade = st.text_input("Student grade level:", "10")
                    num_q = st.slider("Number of questions:", 1, 20, 5)
                    if st.button("Generate Quiz"):
                        with st.spinner("Generating quiz..."):
                            quiz = generate_quiz(summary, lang, grade, num_q)
                            st.subheader("Quiz")
                            st.write(quiz)
