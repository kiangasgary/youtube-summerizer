# YouTube Summarizer Telegram Bot - PRD

## Technical Specifications

### Core Functionality
1. **Input**: Accept YouTube URLs via Telegram messages
2. **Processing**:
   - Extract video ID from URL
   - Fetch English transcripts using YouTube Transcript API
   - Generate concise summary using GPT-3.5-turbo (OpenAI)
3. **Output**: Return formatted summary to user within Telegram chat

### Technical Stack
- **Language**: Python 3.13+
- **Libraries**:
  - `python-telegram-bot` (v20+) for Telegram interface
  - `youtube-transcript-api` for transcript fetching
  - `openai` (v1.0+) for summarization
  - `python-dotenv` for configuration

### Key Components

#### 1. URL Handler
```python
def extract_video_id(url: str) -> str:
    """Extracts YouTube video ID from various URL formats:
    - Regular: https://www.youtube.com/watch?v=VIDEO_ID
    - Short: https://youtu.be/VIDEO_ID
    - Embedded: https://www.youtube.com/embed/VIDEO_ID
    Returns None for invalid URLs"""


    2. Transcript Fetcher

def get_transcript(video_id: str) -> str:
    """Fetches English transcript using YouTubeTranscriptApi
    Raises:
    - TranscriptsDisabled: If captions unavailable
    - Exception: For other API failures"""

3. Transcript Fetcher

    def generate_summary(transcript: str) -> str:
    """Uses google gemeni 2.5 with prompt:
    'Summarize this YouTube transcript in 5 concise bullet points focusing on key insights.
    Maintain original meaning and technical accuracy.'
    Returns formatted markdown string"""

    Error Handling Requirements
Invalid URL: Respond with "Please send a valid YouTube URL"

No Transcript: "This video has no available English captions"

API Failures: "Summary service unavailable. Please try later"


Example User Flow
User sends /start → Bot responds with usage instructions

User sends YouTube URL → Bot processes within 15-30 seconds

Bot replies with formatted summary:


🎥 Video Summary:

• Key point 1
• Key point 2
• ...

🔒 9. Security & Rate Limits
Ensure API keys (Cursor, Telegram) are securely stored.

Implement request limits per user to avoid abuse.

Add retry logic and graceful failure messages.

📌 10. Stretch Goals (Post-MVP)
Multiple summary modes (short, detailed, key bullet points)

Support for multi-language transcripts

Auto-detect video chapters and summarize per section

Summary sharing (copy to clipboard, export as PDF/text)
