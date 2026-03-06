import json
import os
import time
from datetime import datetime

from google import genai
from google.genai import types

import logger
from config import (
    GEMINI_API_KEYS, GEMINI_MODELS,
    MEMORY_FILE, PROFILE_FILE,
    OWNER_FULL_NAME, OWNER_UNI,
    HISTORY_LIMIT
)

EMPTY_PROFILE = {
    "personal":        {"name": OWNER_FULL_NAME, "university": OWNER_UNI, "notes": ""},
    "courses":         [],
    "exams":           [],
    "tasks":           [],
    "habits":          {"sleep": "", "study": "", "other": []},
    "relations":       [],
    "goals":           [],
    "important_notes": [],
    "last_updated":    ""
}

_current_key_index   = 0
_current_model_index = 0

def _get_client() -> genai.Client:
    key = GEMINI_API_KEYS[_current_key_index % len(GEMINI_API_KEYS)]
    return genai.Client(api_key=key)

def _get_model() -> str:
    return GEMINI_MODELS[_current_model_index % len(GEMINI_MODELS)]

def rotate_key():
    global _current_key_index, _current_model_index
    _current_key_index   = (_current_key_index + 1) % len(GEMINI_API_KEYS)
    _current_model_index = 0
    logger.info("Key Rotasyon", f"Key {_current_key_index + 1} | model: {_get_model()}")

def rotate_model():
    global _current_model_index
    _current_model_index += 1
    if _current_model_index >= len(GEMINI_MODELS):
        _current_model_index = 0
        rotate_key()
    else:
        logger.info("Model Rotasyon", _get_model())

def _handle_quota_error(e: Exception):
    logger.error("Kota", f"Kota doldu ({_get_model()})", e)
    rotate_model()

def safe_generate(prompt: str, system_instruction: str = "") -> str:
    max_attempts = len(GEMINI_API_KEYS) * len(GEMINI_MODELS) * 2
    for _ in range(max_attempts):
        try:
            client   = _get_client()
            config   = types.GenerateContentConfig(
                system_instruction=system_instruction if system_instruction else None
            )
            response = client.models.generate_content(
                model=_get_model(), contents=prompt, config=config
            )
            if response and response.candidates:
                cand   = response.candidates[0]
                finish = str(getattr(cand, "finish_reason", "")).upper()
                if finish in ("SAFETY", "BLOCKED", "RECITATION"):
                    logger.warn("API", f"Yanit engellendi: {finish}")
                    return ""
                try:
                    text = cand.content.parts[0].text.strip()
                    if not text:
                        logger.warn("API", f"Bos yanit — model: {_get_model()}")
                    return text
                except Exception as ex:
                    logger.error("API", "Yanit parse hatasi", ex)
                    return ""
            logger.warn("API", f"Candidate yok — model: {_get_model()}")
            return ""
        except Exception as e:
            err = str(e).lower()
            if "quota" in err or "429" in err or "resource" in err or "exhausted" in err:
                _handle_quota_error(e)
            elif "503" in err or "unavailable" in err or "high demand" in err:
                logger.warn("API", "Sunucu yogun, 5sn bekleniyor")
                time.sleep(5)
            else:
                logger.error("safe_generate", str(e)[:60], e)
                return ""
    logger.error("API", "Tum key ve modeller tukendi")
    return ""

def chat_generate(history: list, user_input: str, system_instruction: str = "") -> str:
    max_attempts = len(GEMINI_API_KEYS) * len(GEMINI_MODELS) * 2
    for _ in range(max_attempts):
        try:
            client   = _get_client()
            config   = types.GenerateContentConfig(
                system_instruction=system_instruction if system_instruction else None
            )
            contents = []
            for msg in history:
                role = msg["role"]
                text = ""
                for p in msg.get("parts", []):
                    text += p.get("text", "") if isinstance(p, dict) else str(p)
                if text:
                    contents.append({"role": role, "parts": [{"text": text}]})
            contents.append({"role": "user", "parts": [{"text": user_input}]})
            response = client.models.generate_content(
                model=_get_model(), contents=contents, config=config
            )
            if response and response.candidates:
                cand   = response.candidates[0]
                finish = str(getattr(cand, "finish_reason", "")).upper()
                if finish in ("SAFETY", "BLOCKED", "RECITATION"):
                    logger.warn("API", f"Yanit engellendi: {finish}")
                    return ""
                try:
                    text = cand.content.parts[0].text.strip()
                    if not text:
                        logger.warn("API", f"Bos yanit — model: {_get_model()}")
                    return text
                except Exception as ex:
                    logger.error("API", "Yanit parse hatasi", ex)
                    return ""
            logger.warn("API", f"Candidate yok — model: {_get_model()}")
            return ""
        except Exception as e:
            err = str(e).lower()
            if "quota" in err or "429" in err or "resource" in err or "exhausted" in err:
                _handle_quota_error(e)
            elif "503" in err or "unavailable" in err or "high demand" in err:
                logger.warn("API", "Sunucu yogun, 5sn bekleniyor")
                time.sleep(5)
            else:
                logger.error("chat_generate", str(e)[:60], e)
                return ""
    logger.error("API", "Tum key ve modeller tukendi")
    return ""

def load_history() -> list:
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                return data if isinstance(data, list) else []
            except json.JSONDecodeError:
                return []
    return []

def save_history(history: list):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

def clean_history(history: list) -> list:
    clean = []
    for message in history:
        if clean and clean[-1]["role"] == message["role"]:
            continue
        clean.append(message)
    if len(clean) > HISTORY_LIMIT:
        excess = len(clean) - HISTORY_LIMIT
        excess += excess % 2
        clean = clean[excess:]
    return clean

def load_profile() -> dict:
    if os.path.exists(PROFILE_FILE):
        with open(PROFILE_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return dict(EMPTY_PROFILE)
    return dict(EMPTY_PROFILE)

def save_profile(profile: dict):
    profile["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=4)

def get_profile_summary() -> str:
    profile = load_profile()
    lines   = []
    note = profile.get("personal", {}).get("notes", "")
    if note:
        lines.append(f"Kisisel not: {note}")
    exams = [e for e in profile.get("exams", []) if isinstance(e, dict) and not e.get("passed")]
    if exams:
        lines.append("Yaklasan sinavlar: " + ", ".join(
            f"{e.get('course','')} ({e.get('date','')})" for e in exams
        ))
    courses = profile.get("courses", [])
    if courses:
        lines.append(f"Aldigi dersler: {', '.join(str(c) for c in courses)}")
    pending = [
        t.get("title", "") for t in profile.get("tasks", [])
        if isinstance(t, dict) and not t.get("done") and t.get("title")
    ]
    if pending:
        lines.append(f"Bekleyen gorevler: {', '.join(pending)}")
    goals = profile.get("goals", [])
    if goals:
        lines.append(f"Hedefler: {', '.join(str(g) for g in goals)}")
    relations = profile.get("relations", [])
    if relations:
        lines.append("Onemli kisiler: " + ", ".join(
            f"{r.get('name','')} ({r.get('relation', r.get('role',''))})"
            for r in relations if isinstance(r, dict)
        ))
    notes = profile.get("important_notes", [])
    if notes:
        lines.append(f"Onemli notlar: {' | '.join(str(n) for n in notes[-3:])}")
    sleep = profile.get("habits", {}).get("sleep", "")
    if sleep:
        lines.append(f"Uyku aliskanlik: {sleep}")
    return "\n".join(lines) if lines else "Henuz profilde kayitli bilgi yok."

def _merge_profile_updates(profile: dict, updates: dict) -> dict:
    if "relations" in updates:
        existing = {r.get("name", "").lower() for r in profile.get("relations", []) if isinstance(r, dict)}
        for rel in updates["relations"]:
            if not isinstance(rel, dict):
                continue
            name = rel.get("name", "").lower()
            if name and name not in existing:
                profile.setdefault("relations", []).append(rel)
            elif name:
                for i, r in enumerate(profile["relations"]):
                    if isinstance(r, dict) and r.get("name", "").lower() == name:
                        profile["relations"][i].update(rel)
                        break

    if "important_notes" in updates:
        existing = [str(n) for n in profile.get("important_notes", [])]
        for note in updates["important_notes"]:
            note_str = str(note)
            if note_str not in existing:
                profile.setdefault("important_notes", []).append(note_str)
                existing.append(note_str)

    if "exams" in updates:
        existing = {e.get("course", "").lower() for e in profile.get("exams", []) if isinstance(e, dict)}
        for exam in updates["exams"]:
            if isinstance(exam, dict) and exam.get("course", "").lower() not in existing:
                profile.setdefault("exams", []).append(exam)

    if "tasks" in updates:
        existing = {t.get("title", "").lower() for t in profile.get("tasks", []) if isinstance(t, dict)}
        for task in updates["tasks"]:
            if not isinstance(task, dict):
                task = {"title": str(task), "done": False}
            title = task.get("title", "").lower()
            if title not in existing:
                profile.setdefault("tasks", []).append(task)
            else:
                for i, t in enumerate(profile["tasks"]):
                    if isinstance(t, dict) and t.get("title", "").lower() == title:
                        profile["tasks"][i]["done"] = task.get("done", t.get("done", False))
                        break

    if "goals" in updates:
        existing = [str(g) for g in profile.get("goals", [])]
        for goal in updates["goals"]:
            goal_str = str(goal)
            if goal_str not in existing:
                profile.setdefault("goals", []).append(goal_str)
                existing.append(goal_str)

    if "courses" in updates:
        existing = [str(c).lower() for c in profile.get("courses", [])]
        for course in updates["courses"]:
            if str(course).lower() not in existing:
                profile.setdefault("courses", []).append(str(course))

    if "personal" in updates and isinstance(updates["personal"], dict):
        profile.setdefault("personal", {}).update(updates["personal"])

    if "habits" in updates and isinstance(updates["habits"], dict):
        profile.setdefault("habits", {}).update(updates["habits"])

    return profile

def get_weather(city: str = "Istanbul") -> str:
    try:
        import urllib.request
        url      = f"https://wttr.in/{city}?format=3&lang=tr"
        req      = urllib.request.Request(url, headers={"User-Agent": "curl/7.0"})
        response = urllib.request.urlopen(req, timeout=5)
        return response.read().decode("utf-8").strip()
    except Exception:
        return ""

def _check_task_completion(user_input: str) -> bool:
    completion_keywords = [
        "tamamladim", "tamamlandi", "hallettim", "halledildi", "bitti",
        "bittim", "yaptim", "yapildi", "cozdum", "cozuldu", "bitirdim",
        "hazirladim", "hazırlandi", "teslim ettim", "gonderdim"
    ]
    text_lower = user_input.lower()
    if not any(kw in text_lower for kw in completion_keywords):
        return False
    profile = load_profile()
    tasks   = profile.get("tasks", [])
    if not tasks:
        return False
    pending = [t for t in tasks if isinstance(t, dict) and not t.get("done")]
    if not pending:
        return False
    prompt = (
        f"Kullanici sunu soyledi: '{user_input}'\n\n"
        f"Bekleyen gorevler:\n"
        + "\n".join(f"- {t.get('title','')}" for t in pending)
        + "\n\nKullanici hangi gorevi tamamladi? "
        "Gorevin tam basligini yaz. Emin degilsen NO_MATCH yaz."
    )
    result = safe_generate(prompt).strip()
    if not result or result == "NO_MATCH":
        return False
    changed      = False
    result_lower = result.lower()
    for i, task in enumerate(tasks):
        if isinstance(task, dict):
            title = task.get("title", "").lower()
            if title and (title in result_lower or result_lower in title):
                tasks[i]["done"]         = True
                tasks[i]["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                changed = True
                logger.success("Gorev", f"Tamamlandi: {task.get('title','')}")
                break
    if changed:
        profile["tasks"] = tasks
        save_profile(profile)
        return True
    return False

def update_profile_from_conversation(user_input: str, ai_response: str):
    _check_task_completion(user_input)
    current_profile = load_profile()
    prompt = f"""Son konusma:
Kullanici: {user_input}
Asistan: {ai_response}

Mevcut profil:
{json.dumps(current_profile, ensure_ascii=False, indent=2)}

Bu konusmadan kaydedilmesi gereken YENI veya DEGISEN bir bilgi var mi?
Varsa SADECE degisen/eklenen alanlari JSON olarak dondur.
Yoksa sadece su yaz: NO_UPDATE

Kullanilabilecek alanlar:
- exams: [{{"course": "", "date": "", "passed": false}}]
- courses: ["ders adi"]
- tasks: [{{"title": "", "done": false, "deadline": "", "priority": "normal"}}]
- habits: {{"sleep": "", "study": "", "other": []}}
- relations: [{{"name": "", "relation": ""}}]
- goals: ["hedef"]
- important_notes: ["not"]
- personal: {{"notes": ""}}

Sadece JSON veya NO_UPDATE dondur."""

    try:
        raw_text = safe_generate(prompt)
        if not raw_text or raw_text.strip() == "NO_UPDATE":
            return False
        if "```" in raw_text:
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        updates = json.loads(raw_text.strip())
        updated = _merge_profile_updates(current_profile, updates)
        save_profile(updated)
        logger.info("Profil", "Guncellendi")
        return True
    except Exception as e:
        logger.error("Profil", "Guncelleme hatasi", e)
        return False
