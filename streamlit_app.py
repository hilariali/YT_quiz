import streamlit as st
import re
import openai
import traceback
import requests
import yt_dlp
import os
import glob
import string

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

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
    # Download-specific state
    "download_url": "",
    "download_video_id": "",
    "download_formats": [],
    "download_submitted": False,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ------------------------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------------------------
def get_video_id(url: str) -> str:
    """
    Extract YouTube video ID from URL or return input if already an ID.
    """
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    if "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    return url.strip()


def parse_proxies(proxy_input: str) -> list[str]:
    """
    Convert comma-separated proxy URLs into a list.
    """
    return [u.strip() for u in proxy_input.split(",") if u.strip()]


def list_languages_yt_dlp(video_id: str) -> dict:
    """
    Use yt_dlp to extract available subtitle language codes (manual + auto).
    Returns a dict {language_code: "manual"/"auto"}.
    """
    try:
        ydl_opts = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)

            langs: dict[str, str] = {}

            # 1) Manual subtitles (info["subtitles"])
            subs = info.get("subtitles") or {}
            for code in subs.keys():
                langs[code] = "manual"

            # 2) Automatic captions (info["automatic_captions"])
            auto = info.get("automatic_captions") or {}
            for code in auto.keys():
                if code not in langs:
                    langs[code] = "auto"

            return langs
    except Exception:
        return {}


def try_list_transcripts_api(video_id: str, proxies: dict | None) -> dict:
    """
    Try to list via youtube_transcript_api. Returns a dict {lang: "auto"/"manual"} or {} if it fails.
    """
    try:
        ts_list = YouTubeTranscriptApi.list_transcripts(video_id, proxies=proxies)
        return {t.language_code: ("auto" if t.is_generated else "manual") for t in ts_list}
    except (TranscriptsDisabled, NoTranscriptFound, Exception):
        return {}


def list_transcript_languages(video_id: str, proxy_list: list[str]) -> tuple[dict, dict | None]:
    """
    1) Attempt to list via yt_dlp first.
    2) If empty, fall back to YouTubeTranscriptApi (no proxy → each proxy).
    Returns (langs_dict, used_proxy_dict_or_None).
    """
    st.info("Attempting to list languages via yt_dlp…")
    langs = list_languages_yt_dlp(video_id)
    if langs:
        st.success(f"✓ Languages found via yt_dlp: {', '.join(langs.keys())}")
        return langs, None

    st.info("Falling back to youtube_transcript_api (no proxy)…")
    langs = try_list_transcripts_api(video_id, None)
    if langs:
        st.success("✓ Languages found via API without proxy")
        return langs, None

    for p in proxy_list:
        proxy_cfg = {"http": p, "https": p}
        st.info(f"Trying proxy {p} for youtube_transcript_api…")
        langs = try_list_transcripts_api(video_id, proxy_cfg)
        if langs:
            st.success(f"✓ Languages found via API proxy {p}")
            return langs, proxy_cfg

    st.error("✗ Unable to list transcript languages (yt_dlp + API all failed)")
    return {}, None


def fetch_transcript_yt_dlp(video_id: str, lang: str) -> str:
    """
    Use yt_dlp to download .vtt/.srt for the given language.
    Returns joined text or '' if nothing found.
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

            # 1) Check manual subtitles
            subs = info.get("subtitles") or {}
            if lang in subs:
                vtt_url = subs[lang][0].get("url")
            else:
                # 2) Check automatic captions
                auto = info.get("automatic_captions") or {}
                if lang in auto:
                    vtt_url = auto[lang][0].get("url")
                else:
                    return ""

            # Download the VTT file and strip timing cues
            r = requests.get(vtt_url, timeout=10)
            vtt_text = r.text
            lines = []
            for row in vtt_text.splitlines():
                if row.startswith("WEBVTT") or re.match(r"^\d\d:\d\d:\d\d\.\d\d\d -->", row):
                    continue
                lines.append(row)
            return "\n".join(lines).strip()
    except Exception:
        return ""


def try_fetch_transcript_api(video_id: str, lang: str, proxies: dict | None) -> str:
    """
    Try YouTubeTranscriptApi.get_transcript(...). Return raw text or '' if it fails.
    """
    try:
        entries = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang], proxies=proxies)
        return "\n".join(e.get("text", "") for e in entries)
    except (TranscriptsDisabled, NoTranscriptFound, Exception):
        return ""


def fetch_transcript_with_fallback(video_id: str, lang: str, proxy_list: list[str]) -> tuple[str, dict | None]:
    """
    1) Attempt to fetch via yt_dlp.
    2) If empty, fall back to YouTubeTranscriptApi (no proxy → each proxy).
    Returns (transcript_text, used_proxy_dict_or_None).
    """
    st.info("Attempting to fetch transcript via yt_dlp…")
    text = fetch_transcript_yt_dlp(video_id, lang)
    if text:
        st.success("✓ Fetched transcript via yt_dlp")
        return text, None

    st.info("Falling back to youtube_transcript_api (no proxy)…")
    text = try_fetch_transcript_api(video_id, lang, None)
    if text:
        st.success("✓ Fetched transcript via API without proxy")
        return text, None

    for p in proxy_list:
        proxy_cfg = {"http": p, "https": p}
        st.info(f"Trying proxy {p} for get_transcript API…")
        text = try_fetch_transcript_api(video_id, lang, proxy_cfg)
        if text:
            st.success(f"✓ Fetched transcript via API proxy {p}")
            return text, proxy_cfg

    st.error("✗ Unable to fetch transcript (yt_dlp + API all failed)")
    return "", None


def summarize_chunk(text: str, lang: str) -> str:
    """
    Send a single chunk to OpenAI to summarize.
    """
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
    """
    Break transcript into chunks and summarize iteratively.
    """
    if len(transcript) <= CHUNK_SIZE:
        return summarize_chunk(transcript, lang)
    parts = []
    for i in range(0, len(transcript), CHUNK_SIZE):
        parts.append(summarize_chunk(transcript[i : i + CHUNK_SIZE], lang))
    return summarize_chunk("\n".join(parts), lang)


def generate_quiz(summary: str, lang: str, grade: str, num_questions: int) -> str:
    """
    Ask the model to create a multiple-choice quiz based on the summary.
    """
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
    """
    Ask the model to modify the existing quiz as per user instructions.
    """
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
# Video Download Functions
# ------------------------------------------------------------------------------
def get_video_formats(video_id: str) -> list[dict]:
    """
    Get available video formats for download using yt_dlp.
    Returns a list of format dictionaries.
    """
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 30,
            # Enhanced options to help with 403 errors when getting formats
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "extractor_args": {
                "youtube": {
                    "skip": ["hls", "dash"]
                }
            },
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            
            if not info:
                st.error("❌ Could not retrieve video information.")
                return []
            
            formats = []
            seen_formats = set()
            
            # Check if video is too long or has restrictions
            duration = info.get("duration", 0)
            if duration and duration > 7200:  # More than 2 hours
                st.warning(f"⚠️ Video is very long ({duration//60} minutes). Consider downloading smaller segments.")
            
            availability = info.get("availability")
            if availability and availability != "public":
                st.warning(f"⚠️ Video availability: {availability}. Download may fail.")
            
            for fmt in info.get("formats", []):
                if fmt.get("vcodec") != "none" and fmt.get("acodec") != "none":  # Video with audio
                    height = fmt.get("height")
                    ext = fmt.get("ext", "mp4")
                    filesize = fmt.get("filesize")
                    format_note = fmt.get("format_note", "")
                    tbr = fmt.get("tbr", 0)  # Total bitrate
                    
                    if height is not None and height not in seen_formats:
                        seen_formats.add(height)
                        size_mb = f" (~{filesize // (1024*1024)} MB)" if filesize else ""
                        if not filesize and tbr and duration:
                            # Estimate file size if not provided
                            estimated_size_mb = (tbr * duration) / (8 * 1024)  # Convert kbps to MB
                            size_mb = f" (~{int(estimated_size_mb)} MB est.)"
                        
                        formats.append({
                            "format_id": fmt.get("format_id"),
                            "height": height,
                            "ext": ext,
                            "description": f"{height}p {format_note} (.{ext}){size_mb}",
                            "filesize": filesize,
                            "tbr": tbr
                        })
            
            # Sort by quality (height) descending - handle None values
            formats.sort(key=lambda x: x["height"] if x["height"] is not None else 0, reverse=True)
            
            # Add audio-only option
            audio_formats = [fmt for fmt in info.get("formats", []) if fmt.get("vcodec") == "none" and fmt.get("acodec") != "none"]
            if audio_formats:
                # Filter out formats with None abr values before finding the best one
                valid_audio_formats = [fmt for fmt in audio_formats if fmt.get("abr") is not None and isinstance(fmt.get("abr"), (int, float))]
                if valid_audio_formats:
                    # Use safe comparison for abr values
                    def safe_get_abr(fmt):
                        abr = fmt.get("abr", 0)
                        return abr if abr is not None and isinstance(abr, (int, float)) else 0
                    
                    best_audio = max(valid_audio_formats, key=safe_get_abr)
                else:
                    # Fallback to first audio format if no valid abr values
                    best_audio = audio_formats[0]
                filesize = best_audio.get("filesize")
                size_mb = f" (~{filesize // (1024*1024)} MB)" if filesize else ""
                formats.append({
                    "format_id": best_audio.get("format_id"),
                    "height": 0,  # Use 0 for audio
                    "ext": best_audio.get("ext", "m4a"),
                    "description": f"Audio Only (.{best_audio.get('ext', 'm4a')}){size_mb}",
                    "filesize": filesize,
                    "tbr": best_audio.get("abr", 0)
                })
            
            if not formats:
                st.error("❌ No suitable formats found for this video.")
            
            return formats
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "403" in error_msg or "Forbidden" in error_msg:
            st.error("❌ Error fetching video formats: HTTP Error 403: Forbidden")
            st.error("🔒 This video may be:")
            st.error("• Age-restricted or region-blocked")
            st.error("• Private or requires authentication")
            st.error("• Temporarily unavailable")
            st.error("💡 Please try a different video or check if this video is publicly accessible.")
        else:
            st.error(f"❌ Error fetching video formats: {error_msg}")
        return []
    except Exception as e:
        st.error(f"❌ Unexpected error getting video formats: {str(e)}")
        return []


def download_video(video_id: str, format_id: str, output_path: str = "/tmp") -> str:
    """
    Download video using yt_dlp with specified format.
    Returns the path to the downloaded file or empty string if failed.
    """
    try:
        # Ensure output directory exists
        os.makedirs(output_path, exist_ok=True)
        
        # Clean filename
        ydl_opts_info = {
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 30,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            title = info.get("title", video_id)
            duration = info.get("duration", 0)
            filesize_approx = info.get("filesize_approx", 0)
            
            # Validate video duration and size
            if duration and duration > 3600:  # More than 1 hour
                st.warning(f"⚠️ Video is {duration//60} minutes long. Download may take a while.")
            
            if filesize_approx and filesize_approx > 500 * 1024 * 1024:  # More than 500MB
                st.warning(f"⚠️ Video is approximately {filesize_approx//(1024*1024)} MB. Download may take a while.")
            
            # Clean title for filename - more robust sanitization
            valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
            clean_title = ''.join(c for c in title if c in valid_chars).strip()
            clean_title = clean_title[:50]  # Limit length
            if not clean_title:  # Fallback if title becomes empty
                clean_title = f"video_{video_id[:8]}"
        
        # Use a more specific output template with safe characters
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', clean_title)
        output_template = os.path.join(output_path, f"{safe_title}_%(height)sp.%(ext)s")
        
        ydl_opts = {
            "format": format_id,
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 30,
            "retries": 3,
            # Enhanced options to help with 403 errors
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "extractor_args": {
                "youtube": {
                    "skip": ["hls", "dash"]  # Skip potentially restricted formats
                }
            },
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
            except yt_dlp.utils.DownloadError as e:
                # If we get a 403 error, try with a more basic configuration
                if "403" in str(e) or "Forbidden" in str(e):
                    st.warning("⚠️ Initial download failed with 403 error. Trying alternative configuration...")
                    
                    # Retry with more basic options that may bypass restrictions
                    fallback_opts = {
                        "format": "best[height<=720]",  # Try lower quality
                        "outtmpl": output_template,
                        "quiet": True,
                        "no_warnings": True,
                        "socket_timeout": 60,  # Longer timeout
                        "retries": 5,  # More retries
                        "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                        "extractor_args": {
                            "youtube": {
                                "skip": ["hls", "dash"],
                                "player_skip": ["js"]  # Skip JavaScript player
                            }
                        },
                    }
                    
                    with yt_dlp.YoutubeDL(fallback_opts) as ydl_fallback:
                        ydl_fallback.download([f"https://www.youtube.com/watch?v={video_id}"])
                        st.info("✅ Download succeeded with alternative configuration")
                else:
                    raise  # Re-raise if not a 403 error
            
            # Find the downloaded file using safer pattern matching
            pattern = os.path.join(output_path, f"{safe_title}_*.*")
            files = glob.glob(pattern)
            if files:
                # Return the most recently created file if multiple matches
                # Use safe file time comparison that handles None values
                def safe_getctime(filepath):
                    try:
                        ctime = os.path.getctime(filepath)
                        return ctime if ctime is not None else 0
                    except (OSError, AttributeError):
                        return 0
                
                return max(files, key=safe_getctime)
                
        return ""
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "403" in error_msg or "Forbidden" in error_msg:
            st.error("❌ Download error: HTTP Error 403: Forbidden")
            st.error("🔒 This video may be:")
            st.error("• Age-restricted or region-blocked")
            st.error("• Private or requires authentication")  
            st.error("• Temporarily unavailable")
            st.error("💡 Try:")
            st.error("• Selecting a different video format/quality")
            st.error("• Checking if the video is publicly accessible")
            st.error("• Trying again later")
        else:
            st.error(f"Download error: {error_msg}")
        return ""
    except PermissionError:
        st.error("❌ Permission denied. Unable to write to download directory.")
        return ""
    except OSError as e:
        st.error(f"❌ Disk error: {str(e)}")
        return ""
    except Exception as e:
        st.error(f"❌ Unexpected error during download: {str(e)}")
        return ""


# ------------------------------------------------------------------------------
# Page Functions
# ------------------------------------------------------------------------------
def quiz_generator_page():
    """The original quiz generator functionality"""
    st.title("YouTube Quiz Generator 📚")
    st.title("(current beta version only support YouTube video contains caption)")

    # --- Input Form for Mobile-friendly UI ---
    with st.form(key="input_form", clear_on_submit=False):
        url_input = st.text_input(
            "YouTube video URL:", value=st.session_state.last_url
        )
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

        # 1) List available languages (yt_dlp → API without proxy → API with proxy)
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
                num_q = st.number_input(
                    "Number of questions:", min_value=1, max_value=20, value=5
                )
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


def video_download_page():
    """YouTube Video Download functionality"""
    st.title("YouTube Video Downloader 📥")
    st.write("Download YouTube videos in various qualities and formats.")
    
    # URL input form
    with st.form(key="download_form", clear_on_submit=False):
        url_input = st.text_input(
            "YouTube video URL:", 
            value=st.session_state.download_url,
            placeholder="https://www.youtube.com/watch?v=..."
        )
        submit_button = st.form_submit_button(label="Get Video Formats")
    
    if submit_button and url_input.strip():
        st.session_state.download_url = url_input.strip()
        st.session_state.download_video_id = get_video_id(st.session_state.download_url)
        st.session_state.download_submitted = True
        
        # Fetch available formats
        with st.spinner("Fetching available video formats..."):
            st.session_state.download_formats = get_video_formats(st.session_state.download_video_id)
    
    # Display formats and download options
    if st.session_state.download_submitted and st.session_state.download_formats:
        st.subheader("🔹 Available Formats")
        
        # Create format options for selectbox
        format_options = []
        format_mapping = {}
        
        for fmt in st.session_state.download_formats:
            option_text = fmt["description"]
            format_options.append(option_text)
            format_mapping[option_text] = fmt["format_id"]
        
        # Format selection
        selected_format = st.selectbox(
            "Choose format to download:",
            format_options,
            index=0
        )
        
        # Download button
        if st.button("Download Video", type="primary"):
            selected_format_id = format_mapping[selected_format]
            
            with st.spinner("Downloading video... This may take a few minutes."):
                download_path = download_video(
                    st.session_state.download_video_id, 
                    selected_format_id
                )
                
                if download_path:
                    st.success("✅ Download completed!")
                    
                    # Get file info safely
                    try:
                        file_size = os.path.getsize(download_path)
                        filename = os.path.basename(download_path)
                        
                        # Check file size before loading into memory
                        if file_size > 100 * 1024 * 1024:  # 100MB threshold
                            st.warning(f"⚠️ File is large ({file_size//(1024*1024)} MB). Download may be slow.")
                        
                        # For very large files, suggest alternative download methods
                        if file_size > 500 * 1024 * 1024:  # 500MB threshold
                            st.error("❌ File too large for browser download. Consider using yt-dlp directly on your machine.")
                        else:
                            # Stream the file for download instead of loading all at once
                            def read_file_chunks(file_path, chunk_size=1024*1024):  # 1MB chunks
                                with open(file_path, "rb") as f:
                                    while True:
                                        chunk = f.read(chunk_size)
                                        if not chunk:
                                            break
                                        yield chunk
                            
                            # For smaller files, use direct read for simplicity
                            if file_size <= 50 * 1024 * 1024:  # 50MB or less
                                with open(download_path, "rb") as file:
                                    file_data = file.read()
                                    
                                st.download_button(
                                    label=f"📁 Download {filename}",
                                    data=file_data,
                                    file_name=filename,
                                    mime="video/mp4"
                                )
                            else:
                                # For larger files, create a generator-based download
                                st.info("💡 Large file detected. Download will be processed in chunks.")
                                
                                # Create a temporary link or suggest alternative method
                                st.markdown(f"""
                                **File ready for download:** `{filename}`
                                
                                **File size:** {file_size//(1024*1024)} MB
                                
                                For files this large, we recommend downloading directly using:
                                ```
                                yt-dlp "{st.session_state.download_url}" -f {selected_format_id}
                                ```
                                """)
                        
                    except OSError as e:
                        st.error(f"❌ Error accessing downloaded file: {e}")
                    
                    # Clean up the temporary file after a delay
                    try:
                        os.remove(download_path)
                        st.info("🗑️ Temporary file cleaned up.")
                    except OSError:
                        st.warning("⚠️ Could not clean up temporary file. You may need to remove it manually.")
                        
                else:
                    st.error("❌ Download failed. Please try again or choose a different format.")
    
    elif st.session_state.download_submitted and not st.session_state.download_formats:
        st.error("❌ Unable to fetch video formats. Please check the URL and try again.")
    
    # Add some helpful information
    with st.expander("ℹ️ Download Information"):
        st.markdown("""
        **Supported formats:**
        - Various video qualities (1080p, 720p, 480p, etc.)
        - Audio-only downloads
        - Different file formats (MP4, WebM, etc.)
        
        **Notes:**
        - Download time depends on video length and your internet connection
        - Larger files (higher quality) take longer to download
        - Files are temporarily stored and automatically cleaned up
        - Make sure you have permission to download the content
        """)


# ------------------------------------------------------------------------------
# Main App
# ------------------------------------------------------------------------------
st.set_page_config(page_title="YouTube Tools", layout="wide")

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Choose a tool:",
    ["Quiz Generator", "Video Downloader"]
)

# Page routing
if page == "Quiz Generator":
    quiz_generator_page()
elif page == "Video Downloader":
    video_download_page()