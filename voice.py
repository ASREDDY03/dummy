# --- Patch for Python 3.13 removal of audioop (affects pydub) ---
import sys, types, os, tempfile, time

if sys.version_info >= (3, 13):
    import array

    fake_audioop = types.ModuleType("audioop")

    # Minimal safe stubs used by pydub
    def _mul(fragment, width, factor): return fragment
    def _add(fragment1, fragment2, width): return fragment1
    def _bias(fragment, width, bias): return fragment
    def _avg(fragment, width): return b"\x00" * width
    def _max(fragment, width): return 0
    def _minmax(fragment, width): return (0, 0)
    def _getsample(fragment, width, index): return 0
    def _reverse(fragment, width): return fragment
    def _tostereo(fragment, width, lfactor, rfactor): return fragment

    for fn in ["mul","add","bias","avg","max","minmax","getsample","reverse","tostereo"]:
        setattr(fake_audioop, fn, locals().get(f"_{fn}"))

    sys.modules["audioop"] = fake_audioop

# --- Imports ---
import streamlit as st
import pdfplumber
from gtts import gTTS
from pydub import AudioSegment
from pydub.utils import which
from pydub.playback import play

# --- Ensure ffmpeg/ffprobe on Streamlit Cloud ---
AudioSegment.converter = which("ffmpeg") or "/usr/bin/ffmpeg"
if not which("ffprobe") and not os.path.exists("/usr/bin/ffprobe"):
    import shutil
    shutil.copyfile("/usr/bin/ffmpeg", "/tmp/ffprobe")
    AudioSegment.ffprobe = "/tmp/ffprobe"
else:
    AudioSegment.ffprobe = which("ffprobe") or "/usr/bin/ffprobe"

# --- Optional: ElevenLabs voices ---
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
Upload your interview Q&A PDF and practice like a real interview.  
The AI will **read each question aloud**, wait for your response, and then read the **model answer**,  
with adjustable speed and thinking time.
""")

uploaded_file = st.file_uploader("📄 Upload your Interview PDF", type=["pdf"])
use_ai_voice = st.toggle("🎧 Use AI Voice (ElevenLabs)", value=False)

IS_CLOUD = "STREAMLIT_SERVER_RUNNING" in os.environ

if uploaded_file:
    with pdfplumber.open(uploaded_file) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    if not text.strip():
        st.error("⚠️ No readable text found. Try a text-based PDF (not scanned images).")
        st.stop()

    # ---------- Extract Q&A pairs ----------
    qa_pairs, q, a = [], "", ""
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
            """Speech playback that works both locally and in Streamlit Cloud."""
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                tts = gTTS(text)
                tts.save(fp.name)
                try:
                    audio = AudioSegment.from_file(fp.name, format="mp3")
                    adjusted = audio.speedup(playback_speed=speed)
                    adjusted.export(fp.name, format="mp3")

                    if IS_CLOUD:
                        st.audio(fp.name)
                    else:
                        play(adjusted)
                except Exception as e:
                    st.warning(f"⚠️ Audio skipped: {e}")
                finally:
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
                if IS_CLOUD:
                    import io
                    audio_bytes = b"".join(audio)
                    st.audio(io.BytesIO(audio_bytes), format="audio/mp3")
                else:
                    play_eleven(audio)
            except Exception as e:
                st.warning(f"ElevenLabs error: {e}")

        # ---------- Simulation ----------
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

                progress.progress(int(((i + 1) / num_questions) * 100))
                st.markdown("---")
            st.success("🎉 Interview Simulation Completed! Great job!")
    else:
        st.error("❌ No Q&A pairs found. Make sure your PDF uses 'Q:' and 'A:' labels.")
else:
    st.info("👆 Upload your PDF to begin the simulation.")
