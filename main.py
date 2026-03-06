import asyncio
import json
import os
import re
import time
import speech_recognition as sr
import pygame
import edge_tts
from datetime import datetime

from config import (
    AI_NAME, OWNER_NAME, OWNER_FULL_NAME,
    SYSTEM_PROMPT, TTS_VOICE, TEMP_AUDIO_FILE,
    TTS_RATE, TTS_PITCH, TTS_VOLUME,
    TTS_PAUSE_AFTER_SENTENCE, TTS_PAUSE_AFTER_COMMA,
    MEMORY_FILE, PROFILE_FILE, WEATHER_CITY,
    STT_LANGUAGE, STT_PAUSE_THRESHOLD, STT_PHRASE_LIMIT, STT_NOISE_DURATION,
    SHUTDOWN_KEYWORDS, RESPOND_KEYWORDS, RESPOND_SHORT_SENTENCE,
    FEATURES
)
from memory import (
    load_history, save_history, clean_history,
    get_profile_summary, update_profile_from_conversation,
    safe_generate, chat_generate, rotate_key,
    load_profile, save_profile, EMPTY_PROFILE, get_weather
)
import logger
from executor import execute_task

if FEATURES.get("projects", False):
    from project_manager import (
        get_active_project, project_think,
        apply_project_task, run_project,
        interactive_project_select
    )
else:
    def get_active_project(): return None

BLUE   = "\033[94m"
GREEN  = "\033[92m"
YELLOW = "\033[33m"
CYAN   = "\033[96m"
RED    = "\033[31m"
RESET  = "\033[0m"

pygame.mixer.init()


def _add_pauses(text: str) -> str:
    text = re.sub(r'([.!?])\s+', lambda m: m.group(1) + f'<break time="{TTS_PAUSE_AFTER_SENTENCE}ms"/> ', text)
    text = re.sub(r',\s+', f', <break time="{TTS_PAUSE_AFTER_COMMA}ms"/> ', text)
    return text

async def _tts_save(text: str):
    communicate = edge_tts.Communicate(text, voice=TTS_VOICE, rate=TTS_RATE, pitch=TTS_PITCH, volume=TTS_VOLUME)
    await communicate.save(TEMP_AUDIO_FILE)

def speak(text: str):
    if not FEATURES.get("voice_output", True):
        return
    try:
        asyncio.run(_tts_save(text))
        pygame.mixer.music.load(TEMP_AUDIO_FILE)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        time.sleep(0.15)
        os.remove(TEMP_AUDIO_FILE)
    except Exception as e:
        logger.error("TTS", "Seslendirme hatasi", e)


def listen() -> str | None:
    if not FEATURES.get("voice_input", True):
        try:
            text = input(f"{CYAN}{OWNER_NAME}: {RESET}").strip()
            return text if text else None
        except (EOFError, KeyboardInterrupt):
            return None

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = STT_PAUSE_THRESHOLD
    with sr.Microphone() as source:
        print(f"\n{YELLOW}[{AI_NAME} Dinliyor...]{RESET}")
        recognizer.adjust_for_ambient_noise(source, duration=STT_NOISE_DURATION)
        try:
            audio = recognizer.listen(source, timeout=None, phrase_time_limit=STT_PHRASE_LIMIT)
            print(f"{YELLOW}[Isleniyor...]{RESET}")
            text = recognizer.recognize_google(audio, language=STT_LANGUAGE)
            print(f"{GREEN}{OWNER_NAME}: {text}{RESET}")
            return text
        except sr.UnknownValueError:
            return None
        except Exception as e:
            logger.error("STT", "Dinleme hatasi", e)
            return None


def should_respond(user_input: str) -> bool:
    text = user_input.lower().strip()
    for keyword in RESPOND_KEYWORDS:
        if keyword in text:
            return True
    if len(text.split()) <= RESPOND_SHORT_SENTENCE:
        return True
    prompt = (
        f"Kullanici sunu soyledi: '{user_input}'\n\n"
        "Sen bir kisisel asistansin, arka planda surekli dinliyorsun. "
        "Bu cumle sana mi yonelik yoksa kullanici kendi kendine mi konusuyor?\n"
        "EVET: Sana soru/gorev yoneltilmis.\n"
        "HAYIR: Kendi kendine ya da baskasiyla konusuyor.\n"
        "Sadece EVET ya da HAYIR yaz."
    )
    try:
        return "EVET" in safe_generate(prompt).upper()
    except Exception:
        return True


def _load_mentioned_characters(user_input: str) -> str:
    if not FEATURES.get("character_query", True):
        return ""
    characters_dir = "characters"
    if not os.path.exists(characters_dir):
        return ""
    files = [f for f in os.listdir(characters_dir) if f.endswith(".json")]
    if not files:
        return ""
    text_lower = user_input.lower()
    found = []
    for filename in files:
        name_parts = filename.replace(".json", "").replace("_", " ").lower().split()
        if any(part in text_lower for part in name_parts if len(part) > 2):
            path = os.path.join(characters_dir, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                block  = f"--- {data.get('name', filename)} ---\n"
                block += f"Iliski: {data.get('relation', '')}\n"
                if data.get("character"):
                    block += f"Karakter: {data['character']}\n"
                if data.get("communication_style"):
                    block += f"Iletisim tarzi: {data['communication_style']}\n"
                if data.get("warnings"):
                    block += f"Dikkat: {data['warnings']}\n"
                if data.get("advice"):
                    block += f"Tavsiyeler: {data['advice']}\n"
                if data.get("important_notes"):
                    block += f"Notlar: {' | '.join(str(n) for n in data['important_notes'][-5:])}\n"
                found.append(block)
                print(f"{YELLOW}[Karakter yuklendi: {data.get('name', filename)}]{RESET}")
            except Exception as e:
                logger.error("Karakter", f"Yukleme hatasi: {filename}", e)
    return "\n\n".join(found)


def think(user_input: str) -> tuple:
    history     = clean_history(load_history())
    profile_ctx = get_profile_summary()
    full_system = SYSTEM_PROMPT + f"\n\nSahibin hakkinda guncel bilgiler:\n{profile_ctx}"

    character_ctx = _load_mentioned_characters(user_input)
    if character_ctx:
        full_system += f"\n\nBahsedilen kisiler hakkinda kayitli bilgiler:\n{character_ctx}"

    try:
        raw_text = chat_generate(history, user_input, system_instruction=full_system)
        if not raw_text:
            logger.warn("Gemini", "Bos yanit")
            return "Bir sorun olustu, tekrar dener misin?", None, None

        history.append({"role": "user",  "parts": [{"text": user_input}]})
        history.append({"role": "model", "parts": [{"text": raw_text}]})
        save_history(history)

        if FEATURES.get("memory_update", True):
            update_profile_from_conversation(user_input, raw_text)

        if raw_text.startswith("TASK:"):
            lines = raw_text.split("\n")
            task  = lines[0].replace("TASK:", "").strip()
            resp  = next((l.replace("RESPONSE:", "").strip() for l in lines[1:] if l.startswith("RESPONSE:")), "")
            return resp, "TASK", task

        if raw_text.startswith("PROJECT_MODE"):
            lines = raw_text.split("\n")
            resp  = next((l.replace("RESPONSE:", "").strip() for l in lines[1:] if l.startswith("RESPONSE:")), "")
            return resp, "PROJECT_MODE", None

        return raw_text, None, None

    except Exception as e:
        err = str(e).lower()
        if "quota" in err or "429" in err or "exhausted" in err:
            rotate_key()
            return "Kota doldu, anahtari degistirdim. Tekrar dener misin?", None, None
        logger.error("Think", "Dusunme hatasi", e)
        return "Bir hata olustu.", None, None


def startup_briefing() -> str:
    if not FEATURES.get("daily_briefing", True):
        now  = datetime.now()
        hour = now.hour
        if 5 <= hour < 12:
            g = "Gunaydin"
        elif 12 <= hour < 18:
            g = "Iyi oglenler"
        elif 18 <= hour < 22:
            g = "Iyi aksamlar"
        else:
            g = "Iyi geceler"
        return f"{g} {OWNER_NAME}. Sistemler cevrimici."

    now     = datetime.now()
    hour    = now.hour
    today   = now.strftime("%A, %d %B %Y")
    profile = load_profile()

    if 5 <= hour < 12:
        greeting_time = "Gunaydin"
    elif 12 <= hour < 18:
        greeting_time = "Iyi oglenler"
    elif 18 <= hour < 22:
        greeting_time = "Iyi aksamlar"
    else:
        greeting_time = "Iyi geceler"

    weather = get_weather(WEATHER_CITY)

    from datetime import timedelta
    today_str    = now.strftime("%Y-%m-%d")
    tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    upcoming_exams = []
    for e in profile.get("exams", []):
        if isinstance(e, dict) and not e.get("passed"):
            edate = e.get("date", "")
            if today_str in edate or tomorrow_str in edate or edate in today_str:
                upcoming_exams.append(f"{e.get('course','')} ({edate})")

    pending_tasks = [
        t.get("title", "") for t in profile.get("tasks", [])
        if isinstance(t, dict) and not t.get("done") and t.get("title")
    ]
    important = profile.get("important_notes", [])[-3:]

    briefing_data = (
        f"Tarih: {today}\nSaat: {now.strftime('%H:%M')}\n"
        f"Selamlama: {greeting_time}\n"
        f"Hava: {weather if weather else 'bilgi alinamadi'}\n"
        f"Yaklasan sinavlar: {', '.join(upcoming_exams) if upcoming_exams else 'yok'}\n"
        f"Bekleyen gorevler ({len(pending_tasks)} adet): {', '.join(pending_tasks[:5]) if pending_tasks else 'yok'}\n"
        f"Onemli notlar: {' | '.join(str(n) for n in important) if important else 'yok'}"
    )
    prompt = (
        f"Sabah brifing yapiyorsun. Veriler:\n{briefing_data}\n\n"
        f"Sahibine {greeting_time} de, hava durumunu soyle, varsa sinav ve gorevleri "
        f"dogal bir sekilde hatirlat. 3-5 cumle, insan gibi konus, liste yapma. Turkce."
    )
    try:
        response = safe_generate(prompt, system_instruction=SYSTEM_PROMPT)
        return response if response else f"{greeting_time} {OWNER_NAME}. Sistemler cevrimici."
    except Exception as e:
        logger.error("Brifing", "Hata", e)
        return f"{greeting_time} {OWNER_NAME}."


if __name__ == "__main__":
    if not os.path.exists(MEMORY_FILE):
        save_history([])
    if not os.path.exists(PROFILE_FILE):
        with open(PROFILE_FILE, "w", encoding="utf-8") as f:
            json.dump(EMPTY_PROFILE, f, ensure_ascii=False, indent=4)

    print(f"{YELLOW}[{AI_NAME} baslatiliyor...]{RESET}")

    opening = startup_briefing()
    print(f"{BLUE}{AI_NAME}: {opening}{RESET}")
    speak(opening)

    while True:
        if get_active_project():
            try:
                user_input = input(f"{CYAN}Sen: {RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                user_input = "kapat"
            if not user_input:
                continue
        else:
            user_input = listen()
            if not user_input:
                continue

        if any(keyword in user_input.lower() for keyword in SHUTDOWN_KEYWORDS):
            farewell = f"Iyi aksamlar {OWNER_NAME}. Tum sistemleri uyku moduna aliyorum."
            print(f"{BLUE}{AI_NAME}: {farewell}{RESET}")
            speak(farewell)
            pygame.mixer.quit()
            break

        if not get_active_project() and not should_respond(user_input):
            print(f"{YELLOW}[{AI_NAME} dinledi, mudahale gerekmedi]{RESET}")
            continue

        if FEATURES.get("projects", False) and get_active_project():
            proj_response, proj_cmd, proj_data = project_think(user_input)
            if proj_response:
                print(f"{BLUE}{AI_NAME}: {proj_response}{RESET}")
            if proj_cmd == "TASK" and proj_data:
                ok, result = apply_project_task(proj_data)
                print(f"{BLUE}{AI_NAME}: {'Tamamlandi.' if ok else f'Sorun cikti: {result[:100]}'}{RESET}")
            elif proj_cmd == "RUN":
                ok, result = run_project()
                print(f"{BLUE}{AI_NAME}: {'Proje calisiyor.' if ok else f'Hata: {result[:100]}'}{RESET}")
            continue

        ai_text, mode, payload = think(user_input)

        if ai_text:
            print(f"{BLUE}{AI_NAME}: {ai_text}{RESET}")
            speak(ai_text)

        if mode == "TASK" and payload:
            if not FEATURES.get("executor", True):
                msg = "Executor ozelligi devre disi."
                print(f"{BLUE}{AI_NAME}: {msg}{RESET}")
                speak(msg)
            else:
                logger.info("Executor", f"Gorev: {payload}")
                success, result_msg = execute_task(payload)
                if not success:
                    print(f"{BLUE}{AI_NAME}: {result_msg}{RESET}")
                    speak(result_msg)

        elif mode == "PROJECT_MODE":
            if not FEATURES.get("projects", False):
                msg = "Proje ozelligi henuz tamamlanmadi."
                print(f"{BLUE}{AI_NAME}: {msg}{RESET}")
                speak(msg)
            else:
                ok, msg = interactive_project_select()
                print(f"{BLUE}{AI_NAME}: {msg}{RESET}")
                speak(msg)
