from youtube_transcript_api import YouTubeTranscriptApi
import logging

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def test_transcript_fetch(video_id: str):
    try:
        # Try to list all available transcripts
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        print("\nAvailable transcripts:")
        for transcript in transcript_list:
            print(f"Language: {transcript.language} ({transcript.language_code})")
        
        # Try to get any available transcript
        transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
        if transcript:
            print("\nFetching English transcript...")
            transcript_data = transcript.fetch()
            print("First few lines of transcript:")
            for entry in transcript_data[:3]:
                print(f"[{entry['start']:.1f}s] {entry['text']}")
            return True
    except Exception as e:
        print(f"\nError: {str(e)}")
        return False

if __name__ == "__main__":
    # Test with a known video ID
    test_video_id = "dQw4w9WgXcQ"  # This is a popular video that should have captions
    print(f"Testing with video ID: {test_video_id}")
    test_transcript_fetch(test_video_id) 