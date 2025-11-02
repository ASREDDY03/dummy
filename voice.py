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
st.markdown("""
<style>
h1, h2, h3, h4, h5 {font-size:18px !important;}
.stMarkdown {font-size:16px !important;}
</style>
""", unsafe_allow_html=True)

st.title("🎤 AI Interview Practice Simulator")
st.write("""
Upload your interview PDF and practice like a real interview.  
The AI will **read each question aloud**, wait for your answer, and then read the **model answer** — all with adjustable speed and timing.
""")

uploaded_file = st.file_uploader("📄 Upload your Interview PDF", type=["pdf"])
use_ai_voice = st.toggle("🎧 Use AI Voice (ElevenLabs)", value=False)

if uploaded_file:
    with pdfplumber.open(uploaded_file) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

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

        # Voice function (gTTS + Pydub)
        def speak(text, speed=1.0):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                tts = gTTS(text)
                tts.save(fp.name)
                audio = AudioSegment.from_mp3(fp.name)
                adjusted = audio.speedup(playback_speed=speed)
                play(adjusted)
                os.remove(fp.name)

        # ElevenLabs function (if enabled)
        def speak_ai(text, speed=1.0):
            from elevenlabs import generate, play, set_api_key
            set_api_key(st.secrets.get("ELEVENLABS_API_KEY", ""))  # Add key to secrets.toml if deployed
            audio = generate(
                text=text,
                voice="Rachel",
                model="eleven_multilingual_v2",
                stream=True,
                voice_settings={"stability": 0.5, "speaking_rate": speed}
            )
            play(audio)

        if st.button("▶️ Start Interview Simulation"):
            progress = st.progress(0)
            for i, (q, a) in enumerate(qa_pairs[:num_questions]):
                st.markdown(f"### ❓ Question {i+1}:")
                st.write(q)
                if use_ai_voice and ELEVENLABS_AVAILABLE:
                    speak_ai(f"Question {i+1}. {q}", speed=speech_speed)
                else:
                    speak(f"Question {i+1}. {q}", speed=speech_speed)

                with st.empty():
                    for sec in range(pause_duration, 0, -1):
                        st.info(f"⏳ Waiting {sec} seconds for your response...")
                        time.sleep(1)
                    st.empty()

                st.markdown(f"**✅ Answer:** {a}")
                if use_ai_voice and ELEVENLABS_AVAILABLE:
                    speak_ai(f"Answer. {a}", speed=speech_speed)
                else:
                    speak(f"Answer. {a}", speed=speech_speed)

                progress.progress(int(((i+1)/num_questions)*100))
                st.markdown("---")

            st.success("🎉 Interview Simulation Completed! Great work!")
    else:
        st.error("❌ No Q&A pairs found — make sure your PDF uses 'Q:' and 'A:' labels.")
else:
    st.info("👆 Upload your PDF to begin the simulation.")
