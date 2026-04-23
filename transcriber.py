import assemblyai as aai
import os
from dotenv import load_dotenv

load_dotenv()

# Set AssemblyAI API key
aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")


def transcribe_audio(filepath: str) -> dict:
    """
    Transcribe an audio file using AssemblyAI.
    Returns a dict with transcript text and metadata.
    """
    print(f"🎙️  Starting transcription: {filepath}")

    try:
        config = aai.TranscriptionConfig(
            speech_model=aai.SpeechModel.best,
            punctuate=True,
            format_text=True,
        )

        transcriber = aai.Transcriber(config=config)
        transcript = transcriber.transcribe(filepath)

        if transcript.status == aai.TranscriptStatus.error:
            print(f"❌ Transcription error: {transcript.error}")
            return {
                "success": False,
                "error": transcript.error
            }

        text = transcript.text
        word_count = len(text.split()) if text else 0
        duration = transcript.audio_duration or 0

        print(f"✅ Transcription complete — {word_count} words, {round(duration, 1)}s audio")

        return {
            "success": True,
            "transcript": text,
            "word_count": word_count,
            "duration_seconds": round(duration, 1),
            "transcript_id": transcript.id
        }

    except Exception as e:
        print(f"❌ Transcription failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# Test transcriber directly
if __name__ == "__main__":
    import sys

    # Allow passing filepath as argument or prompt for it
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
    else:
        test_file = input("Enter path to audio file (e.g. downloads\\file.mp3): ").strip()

    if not os.path.exists(test_file):
        print(f"❌ File not found: {test_file}")
    else:
        result = transcribe_audio(test_file)

        if result["success"]:
            print("\n✅ Transcription successful:")
            print(f"   Words    : {result['word_count']}")
            print(f"   Duration : {result['duration_seconds']}s")
            print(f"\n📋 Transcript preview (first 500 chars):")
            print(result["transcript"][:500] + "...")
        else:
            print(f"\n❌ Failed: {result['error']}")
