import anthropic
import os
import json
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

CATEGORIES = [
    "Stock Market",
    "Economics",
    "World News",
    "AI News & Projects",
    "Business & Entrepreneurship",
    "Side Hustles",
    "Trading Strategies",
    "Philosophy & Self Reflection",
    "Science & Technology",
    "Uncategorized"
]

ANALYSIS_PROMPT = """You are Nexus, an AI intelligence analyst. Your job is to analyze social media video transcripts and produce structured intelligence reports.

Available categories: {categories}

Analyze the following transcript and return a JSON object with EXACTLY this structure — no extra text, no markdown, just raw JSON:

{{
  "summary": "2-3 sentence summary of the video",
  "key_points": [
    {{
      "point": "The key claim or point made",
      "context": "Why the creator made this point and how it fits their argument",
      "verdict": "VERIFIED | MOSTLY TRUE | UNVERIFIED | FALSE | OPINION",
      "confidence": 0.95,
      "source_note": "Supporting source or explanation of verdict"
    }}
  ],
  "conclusion": "2-3 sentence conclusion summarizing the overall credibility, main takeaway, and how to use this information",
  "sentiment": "Bullish | Bearish | Neutral | Optimistic | Pessimistic | Cautionary | Informational",
  "sentiment_confidence": "High | Medium | Low",
  "emotional_framing": "Brief description of emotional tone used",
  "bias_detected": "Any bias detected or None",
  "misinformation_score": 0.08,
  "claims_verified": 2,
  "claims_partly_true": 1,
  "claims_opinion": 1,
  "claims_total": 4,
  "categories": ["Primary Category", "Secondary Category if applicable"],
  "primary_category": "Primary Category",
  "topics": ["topic1", "topic2", "topic3", "topic4", "topic5"]
}}

Rules:
- Extract ALL significant claims as key points — typically 3-8 per video
- misinformation_score is between 0.0 (no misinformation) and 1.0 (all misinformation)
- confidence is between 0.0 and 1.0
- categories must come from the available categories list
- topics should be specific keywords useful for search (e.g. "Federal Reserve", "S&P 500", "rate cuts")
- verdict OPINION means the claim is forward-looking or subjective, not necessarily wrong
- Be precise and analytical — this data feeds other AI systems and projects

Transcript to analyze:
{transcript}

Creator: {creator}
Platform: {platform}"""


def analyze_transcript(transcript: str, creator: str = "Unknown", platform: str = "Unknown") -> dict:
    """
    Send transcript to Claude for full analysis.
    Returns structured intelligence report as a dict.
    """
    print(f"🤖 Analyzing transcript with Claude...")

    try:
        prompt = ANALYSIS_PROMPT.format(
            categories=", ".join(CATEGORIES),
            transcript=transcript,
            creator=creator,
            platform=platform
        )
        
        import asyncio
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        raw_response = message.content[0].text.strip()

        # Strip markdown code blocks if present
        if raw_response.startswith("```"):
            raw_response = raw_response.split("```")[1]
            if raw_response.startswith("json"):
                raw_response = raw_response[4:]
        raw_response = raw_response.strip()

        analysis = json.loads(raw_response)

        # Validate required fields exist
        required = ["summary", "key_points", "conclusion", "sentiment",
                    "misinformation_score", "categories", "topics"]
        for field in required:
            if field not in analysis:
                raise ValueError(f"Missing required field: {field}")

        print(f"✅ Analysis complete — {len(analysis.get('key_points', []))} key points extracted")
        print(f"   Categories : {', '.join(analysis.get('categories', []))}")
        print(f"   Sentiment  : {analysis.get('sentiment')}")
        print(f"   Misinfo    : {analysis.get('misinformation_score')}")

        analysis["success"] = True
        return analysis

    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse Claude response as JSON: {e}")
        return {"success": False, "error": f"JSON parse error: {e}"}

    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return {"success": False, "error": str(e)}


def format_discord_report(analysis: dict, meta: dict) -> str:
    """
    Format the analysis into a clean Discord message.
    meta should contain: url, platform, creator, title
    """
    from datetime import datetime

    divider = "━" * 32
    now = datetime.now().strftime("%B %d %Y %I:%M%p")

    key_points_text = ""
    for i, kp in enumerate(analysis.get("key_points", []), 1):
        verdict = kp.get("verdict", "UNKNOWN")
        verdict_emoji = {
            "VERIFIED": "✅",
            "MOSTLY TRUE": "⚠️",
            "UNVERIFIED": "🔍",
            "FALSE": "❌",
            "OPINION": "💭"
        }.get(verdict, "❓")

        confidence = kp.get("confidence", 0)
        confidence_pct = f"{int(confidence * 100)}%"

        key_points_text += (
            f"\n**{i}️⃣ {kp.get('point', '')}**\n"
            f"   💬 {kp.get('context', '')}\n"
            f"   {verdict_emoji} **{verdict}** | Confidence: {confidence_pct}\n"
            f"   📌 {kp.get('source_note', '')}\n"
        )

    categories_str = " | ".join(analysis.get("categories", []))
    topics_str = ", ".join(analysis.get("topics", []))

    misinfo = analysis.get("misinformation_score", 0)
    misinfo_emoji = "🟢" if misinfo < 0.3 else "🟡" if misinfo < 0.6 else "🔴"

    report = (
        f"{divider}\n"
        f"🎯 **NEXUS INTELLIGENCE REPORT**\n"
        f"{divider}\n\n"
        f"📹 **Platform:** {meta.get('platform', 'Unknown')}\n"
        f"👤 **Creator:** {meta.get('creator', 'Unknown')}\n"
        f"🏷️ **Categories:** {categories_str}\n"
        f"📅 **Processed:** {now}\n\n"
        f"{divider}\n"
        f"📋 **SUMMARY**\n"
        f"{divider}\n"
        f"{analysis.get('summary', '')}\n\n"
        f"{divider}\n"
        f"🔑 **KEY POINTS & FACT CHECKS**\n"
        f"{divider}\n"
        f"{key_points_text}\n"
        f"{divider}\n"
        f"🎭 **SENTIMENT ANALYSIS**\n"
        f"{divider}\n"
        f"**Overall Tone:** {analysis.get('sentiment', 'Unknown')}\n"
        f"**Confidence:** {analysis.get('sentiment_confidence', 'Unknown')}\n"
        f"**Emotional Framing:** {analysis.get('emotional_framing', 'Unknown')}\n"
        f"**Bias Detected:** {analysis.get('bias_detected', 'None')}\n\n"
        f"{divider}\n"
        f"🏁 **CONCLUSION**\n"
        f"{divider}\n"
        f"{analysis.get('conclusion', '')}\n\n"
        f"{misinfo_emoji} **Misinformation Risk:** {misinfo} / 1.0\n"
        f"✅ Verified: {analysis.get('claims_verified', 0)} | "
        f"⚠️ Partly True: {analysis.get('claims_partly_true', 0)} | "
        f"💭 Opinion: {analysis.get('claims_opinion', 0)} | "
        f"📊 Total: {analysis.get('claims_total', 0)}\n\n"
        f"🔍 **Topics:** {topics_str}\n"
        f"{divider}"
    )

    return report


# Test analyzer directly
if __name__ == "__main__":
    test_transcript = input("Paste a transcript to test (or press Enter to use a sample): ").strip()

    if not test_transcript:
        test_transcript = """
        Tomorrow is a multitrillion dollar options expiry for E mini S and P futures. 
        Today just gave us plenty of clues for what to expect tomorrow. What stands out 
        is the soft open, the reclaim, and the huge $4.6 billion in positive delta build 
        on the way up. $4.3 billion of that expires tomorrow. This is crazy bullish flow 
        and buyers showed up early enough to improve the floor. The Fed hasn't cut rates 
        since 2024 and CPI dropped to 2.1% last month which supports the bull case.
        """
        print("Using sample transcript...")

    result = analyze_transcript(
        transcript=test_transcript,
        creator="nicholas_crown",
        platform="TikTok"
    )

    if result["success"]:
        print("\n--- FORMATTED DISCORD REPORT ---\n")
        report = format_discord_report(result, {
            "platform": "TikTok",
            "creator": "nicholas_crown",
            "url": "https://tiktok.com/test"
        })
        print(report)
    else:
        print(f"❌ Failed: {result['error']}")
