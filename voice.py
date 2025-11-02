# --- Patch for Streamlit Cloud (Python 3.13 missing pyaudioop) ---
import sys, types
if sys.version_info >= (3, 13):
    sys.modules['pyaudioop'] = types.ModuleType('pyaudioop')

import streamlit as st
import pdfplumber
from gtts import gTTS
from pydub import AudioSegment
from pydub.playback import play
import tempfile
import time
import os

# Optional: ElevenLabs (for AI-quality voices)
try:
    from elevenlabs import generate, play as play_eleven, set_api_key
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False

# ---------- Streamlit UI ----------
st.set_page_config(page_title="AI Interview Simulator", layout="wide", initial_sidebar_state="collapsed")

# UI styling
st.markdown("""
<style>
h1, h2, h3, h4, h5 {font-size:18px !important;}
.stMarkdown {font-size:16px !important;}
</style>
""", unsafe_allow_html=True)

st.title("🎤 AI Interview Practice Simulator")
st.write("""
Upload your interview Q&A PDF and practice like a real interview.  
The AI will **read each question aloud**, wait for your response, and then read the **model answer**,  
with adjustable speed and thinking time.
""")

uploaded_file = st.file_uploader("📄 Upload your Interview PDF", type=["pdf"])
use_ai_voice = st.toggle("🎧 Use AI Voice (ElevenLabs)", value=False)

# Detect if running on Streamlit Cloud
IS_CLOUD = "STREAMLIT_SERVER_RUNNING" in os.environ

if uploaded_file:
    # Extract text from PDF
    with pdfplumber.open(uploaded_file) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    # Validate PDF content
    if not text.strip():
        st.error("⚠️ No readable text found. Try a text-based PDF (not scanned images).")
        st.stop()

    # Extract Q&A pairs
    qa_pairs = []
    q, a = "", ""
    for line in text.split("\n"):
        if line.strip().startswith("Q:"):
            if q and a:
                qa_pairs.append((q.strip(), a.strip()))
                q, a = "", ""
            q = line.replace("Q:", "").strip()
        elif line.strip().startswith("A:"):
            a += line.replace("A:", "").strip() + " "
        elif a:
            a += line.strip() + " "
    if q and a:
        qa_pairs.append((q.strip(), a.strip()))

    if qa_pairs:
        st.success(f"✅ Extracted {len(qa_pairs)} Q&A pairs successfully!")

        pause_duration = st.slider("🕒 Thinking Time (seconds)", 5, 20, 10)
        speech_speed = st.slider("🎚️ Reading Speed (1.0 = normal, >1.0 faster)", 0.8, 1.5, 1.0, 0.1)
        num_questions = st.slider("📋 Number of Questions", 3, min(15, len(qa_pairs)), 5)

        # ---------- Voice Functions ----------

        def speak(text, speed=1.0):
            """Local speech playback using gTTS + Pydub (disabled on Cloud)."""
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                tts = gTTS(text)
                tts.save(fp.name)
                audio = AudioSegment.from_mp3(fp.name)
                adjusted = audio.speedup(playback_speed=speed)
                if not IS_CLOUD:
                    try:
                        play(adjusted)
                    except Exception as e:
                        st.warning(f"⚠️ Playback skipped: {e}")
                os.remove(fp.name)

        def speak_ai(text, speed=1.0):
            """AI voice via ElevenLabs (optional)."""
            if not ELEVENLABS_AVAILABLE:
                st.warning("⚠️ ElevenLabs not installed or configured.")
                return
            try:
                set_api_key(st.secrets.get("ELEVENLABS_API_KEY", ""))
                audio = generate(
                    text=text,
                    voice="Rachel",
                    model="eleven_multilingual_v2",
                    stream=True,
                    voice_settings={"stability": 0.5, "speaking_rate": speed}
                )
                if not IS_CLOUD:
                    play_eleven(audio)
                else:
                    st.info("🔇 AI voice generated but not played in cloud.")
            except Exception as e:
                st.warning(f"ElevenLabs error: {e}")

        # ---------- Simulation ----------
        if st.button("▶️ Start Interview Simulation"):
            progress = st.progress(0)
            for i, (q, a) in enumerate(qa_pairs[:num_questions]):
                st.markdown(f"### ❓ Question {i+1}:")
                st.write(q)

                # Read question
                if use_ai_voice and ELEVENLABS_AVAILABLE:
                    speak_ai(f"Question {i+1}. {q}", speed=speech_speed)
                else:
                    speak(f"Question {i+1}. {q}", speed=speech_speed)

                # Wait for user response
                with st.empty():
                    for sec in range(pause_duration, 0, -1):
                        st.info(f"⏳ Waiting {sec} seconds for your response...")
                        time.sleep(1)
                    st.empty()

                # Read answer
                st.markdown(f"**✅ Answer:** {a}")
                if use_ai_voice and ELEVENLABS_AVAILABLE:
                    speak_ai(f"Answer. {a}", speed=speech_speed)
                else:
                    speak(f"Answer. {a}", speed=speech_speed)

                # Progress update
                progress.progress(int(((i+1)/num_questions) * 100))
                st.markdown("---")

            st.success("🎉 Interview Simulation Completed! Great job!")
    else:
        st.error("❌ No Q&A pairs found. Make sure your PDF uses 'Q:' and 'A:' labels.")
else:
    st.info("👆 Upload your PDF to begin the simulation.")
