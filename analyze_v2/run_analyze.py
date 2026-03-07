import sys
import os
import json
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analyze import (
    merge_into_profile, detect_people_in_chat,
    analyze_note, analyze_cv, analyze_general,
    list_characters, FIELD_PROMPTS,
    save_character_field, _get_character_dir, _save_field, _parse_json
)
from memory import load_profile, safe_generate

YELLOW = "\033[33m"
GREEN  = "\033[32m"
RED    = "\033[31m"
CYAN   = "\033[96m"
RESET  = "\033[0m"

MAX_CHARS_PER_CALL = 700000

def progress_bar(current: int, total: int, width: int = 40) -> str:
    pct    = current / total if total > 0 else 1
    filled = int(width * pct)
    bar    = "█" * filled + "░" * (width - filled)
    return f"{CYAN}[{bar}] {int(pct*100)}%{RESET}"

def get_text_from_file() -> tuple:
    print(f"\n{YELLOW}Dosya yolunu gir:{RESET}")
    path = input("> ").strip().strip('"')
    if not os.path.exists(path):
        print(f"{RED}Dosya bulunamadi: {path}{RESET}")
        sys.exit(1)
    ext = os.path.splitext(path)[1].lower()
    if ext not in [".txt", ".md", ".csv", ".json", ".log"]:
        print(f"{RED}Desteklenmeyen tur: {ext}{RESET}")
        sys.exit(1)
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(), os.path.basename(path)
    except Exception as e:
        print(f"{RED}Okuma hatasi: {e}{RESET}")
        sys.exit(1)

def get_text_from_paste() -> str:
    print(f"\n{YELLOW}Metni yapistir (bitirmek icin CTRL+Z + Enter):{RESET}")
    print("-" * 50)
    lines = []
    try:
        while True:
            lines.append(input())
    except EOFError:
        pass
    return "\n".join(lines)

def _split_text(text: str, max_chars: int) -> list:
    if len(text) <= max_chars:
        return [text]
    chunks = []
    lines  = text.split("\n")
    current = ""
    for line in lines:
        if len(current) + len(line) + 1 > max_chars and current:
            chunks.append(current.strip())
            current = line + "\n"
        else:
            current += line + "\n"
    if current.strip():
        chunks.append(current.strip())
    return chunks

def _analyze_field_for_person(full_text: str, instruction: str, person: str, field: str) -> list:
    field_prompt = FIELD_PROMPTS[field]
    chunks       = _split_text(full_text, MAX_CHARS_PER_CALL)
    all_items    = []
    seen         = set()

    for ci, chunk in enumerate(chunks):
        chunk_info = f" (parça {ci+1}/{len(chunks)})" if len(chunks) > 1 else ""
        prompt = (
            f"SOHBET METNİ{chunk_info}:\n{chunk}\n\n"
            f"KULLANICI TALİMATI: {instruction}\n\n"
            f"KİŞİ: {person}\n\n"
            f"{field_prompt}\n\n"
            "KURALLAR:\n"
            "- Her madde tek cümle, somut, kanıtlanmış\n"
            "- Yorum değil doğrudan gözlem\n"
            "- Emin olmadığın şeyi yazma\n"
            "- Mümkün olduğunca fazla madde çıkar\n"
            "- Sadece JSON döndür, başka hiçbir şey yazma"
        )
        raw = safe_generate(prompt)

        if not raw:
            print(f"\n  {RED}! {field}{chunk_info}: Gemini bos yanit{RESET}")
            continue

        parsed = _parse_json(raw)
        if not parsed:
            print(f"\n  {RED}! {field}{chunk_info}: JSON parse hatasi — raw: {raw[:80]}{RESET}")
            continue

        if field == "warnings":
            items = parsed.get("warnings", [])
            score = parsed.get("reliability_score", "")
            if score:
                save_character_field(person, "reliability_score", score)
        elif field == "connected_people":
            items = parsed.get("connected_people", [])
        else:
            items = parsed.get(field, [])

        for item in items:
            key = str(item).strip().lower()
            if key not in seen:
                seen.add(key)
                all_items.append(item)

    return all_items

def analyze_whatsapp_optimized(full_text: str, instruction: str) -> str:
    print(f"\n{YELLOW}Kisiler tespit ediliyor...{RESET}")
    people = detect_people_in_chat(full_text)

    if not people:
        print(f"{RED}Sohbette kisi tespit edilemedi.{RESET}")
        return "Kisi tespit edilemedi."

    print(f"{GREEN}Tespit edilen kisiler: {', '.join(people)}{RESET}")

    char_count = len(full_text)
    chunks     = _split_text(full_text, MAX_CHARS_PER_CALL)
    if len(chunks) > 1:
        print(f"{YELLOW}Metin cok buyuk ({char_count:,} karakter), {len(chunks)} parcaya bolundu.{RESET}\n")
    else:
        print(f"{YELLOW}Metin boyutu: {char_count:,} karakter — tek parca.{RESET}\n")

    total_fields = len(FIELD_PROMPTS)
    results      = {}

    for pi, person in enumerate(people, 1):
        print(f"\n{CYAN}[{pi}/{len(people)}] {person}{RESET}")
        total_saved = 0

        for fi, field in enumerate(FIELD_PROMPTS.keys(), 1):
            print(f"  {progress_bar(fi, total_fields)} {field:<30}", end="\r", flush=True)

            items = _analyze_field_for_person(full_text, instruction, person, field)

            if items:
                save_character_field(person, field, items)
                total_saved += len(items)

        char_dir = _get_character_dir(person)
        _save_field(char_dir, "meta", {
            "name":         person,
            "source":       "whatsapp_analysis",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M")
        })

        print(f"\n  {GREEN}✓ {person}: {total_saved} madde kaydedildi{RESET}")
        results[person] = total_saved

    summary_parts = [f"{name}: {count} madde" for name, count in results.items()]
    return f"Analiz tamamlandi. {' | '.join(summary_parts)}"


print("=" * 55)
print("NOVA — Manuel Analiz Modu")
print("=" * 55)

print(f"\n{YELLOW}Talimatini gir:{RESET}")
instruction = input("> ").strip()
if not instruction:
    print(f"{RED}Talimat bos.{RESET}")
    sys.exit(1)

print(f"\n{YELLOW}Icerik turu:{RESET}")
print("  1 — whatsapp  (sohbet gecmisi)")
print("  2 — note      (not, metin)")
print("  3 — cv        (ozgecmis)")
print("  4 — general   (genel metin)")
type_choice  = input("> ").strip()
type_map     = {"1": "whatsapp", "2": "note", "3": "cv", "4": "general",
                "whatsapp": "whatsapp", "note": "note", "cv": "cv", "general": "general"}
content_type = type_map.get(type_choice, "general")
print(f"{CYAN}Secilen tur: {content_type}{RESET}")

print(f"\n{YELLOW}Kaynak sec:{RESET}")
print("  1 — Dosyadan oku")
print("  2 — Yapistir")
choice = input("> ").strip()

if choice == "1":
    text, filename = get_text_from_file()
    print(f"\n{GREEN}'{filename}' okundu — {len(text):,} karakter{RESET}")
else:
    text = get_text_from_paste()

if not text.strip():
    print(f"{RED}Metin bos.{RESET}")
    sys.exit(1)

if content_type == "whatsapp":
    result = analyze_whatsapp_optimized(text, instruction)
else:
    profile   = load_profile()
    analyzers = {"note": analyze_note, "cv": analyze_cv, "general": analyze_general}
    print(f"{YELLOW}Analiz baslatiliyor...{RESET}")
    updates = analyzers[content_type](text, instruction, profile)
    if updates:
        merge_into_profile(updates)
        result = safe_generate(
            f"Analiz yapildi:\n{json.dumps(updates, ensure_ascii=False, indent=2)}\n\n"
            "2-3 cumleyle ne buldun, ne ekledin diye Turkce ozet ver."
        ) or "Analiz tamamlandi."
    else:
        result = "Eklenecek yeni bilgi bulunamadi."

print(f"\n{'=' * 55}")
print(f"{GREEN}NOVA: {result}{RESET}")
print("=" * 55)
