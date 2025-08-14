# YouTube Quiz Generator

A Streamlit app that takes a YouTube video URL, fetches its transcript, summarizes it via OpenAI, and generates a multiple-choice quiz.

## Features

### Quiz Generator 📚
- Extract transcripts from YouTube videos
- Generate AI-powered summaries 
- Create customizable multiple-choice quizzes
- Support for multiple languages
- Proxy support for restricted regions

### Video Downloader 📥 
- Download YouTube videos in various qualities
- Support for audio-only downloads
- Multiple format options (MP4, WebM, etc.)
- Robust error handling and user feedback
- Safe handling of large files
- Cross-platform compatibility

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

## Recent Improvements (Video Downloader)

The video downloader functionality has been significantly enhanced with:

- **Robust Error Handling**: Comprehensive error catching for network, permission, and disk space issues
- **HTTP 403 Error Mitigation**: Specific handling for age-restricted and region-blocked videos with automatic fallback retry
- **Enhanced yt-dlp Configuration**: User agent spoofing and format skipping to bypass restrictions  
- **Memory Management**: Smart file size handling to prevent memory issues with large videos
- **Cross-Platform Support**: Proper file path sanitization and directory creation
- **Timeout & Retry Logic**: 30-second timeouts and 3-retry attempts for reliability with fallback to extended timeouts
- **User Feedback**: Clear progress indicators and helpful error messages with actionable guidance
- **File Validation**: Size estimation and format validation before download
- **Safe Cleanup**: Proper temporary file management

### Testing

Run the validation tests:
```bash
python test_download_fixes.py
```
