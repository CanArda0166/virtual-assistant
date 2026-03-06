import sys
import os
import math
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analyze import merge_into_profile
from analyze import analyze_whatsapp, analyze_note, analyze_cv, analyze_general
from analyze import analyze
from memory import load_profile, safe_generate

YELLOW = "\033[33m"
GREEN  = "\033[32m"
RED    = "\033[31m"
CYAN   = "\033[96m"
RESET  = "\033[0m"

CHUNK_SIZE = 10000

def progress_bar(current: int, total: int, width: int = 40) -> str:
    pct    = current / total if total > 0 else 1
    filled = int(width * pct)
    bar    = "█" * filled + "░" * (width - filled)
    return f"{CYAN}[{bar}] {int(pct*100)}% ({current}/{total} parça){RESET}"

def get_text_from_file() -> tuple[str, str]:
    print(f"\n{YELLOW}Dosya yolunu gir:{RESET}")
    path = input("> ").strip().strip('"')

    if not os.path.exists(path):
        print(f"{RED}Dosya bulunamadı: {path}{RESET}")
        sys.exit(1)

    ext = os.path.splitext(path)[1].lower()
    if ext not in [".txt", ".md", ".csv", ".json", ".log"]:
        print(f"{RED}Desteklenmeyen tür: {ext} — Desteklenenler: .txt .md .csv .json .log{RESET}")
        sys.exit(1)

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(), os.path.basename(path)
    except Exception as e:
        print(f"{RED}Okuma hatası: {e}{RESET}")
        sys.exit(1)

def get_text_from_paste() -> str:
    print(f"\n{YELLOW}Metni yapıştır (bitirmek için boş satırda CTRL+Z + Enter):{RESET}")
    print("-" * 50)
    lines = []
    try:
        while True:
            lines.append(input())
    except EOFError:
        pass
    return "\n".join(lines)

def split_into_chunks(text: str) -> list[str]:
    
    lines   = text.split("\n")
    chunks  = []
    current = ""
    for line in lines:
        if len(current) + len(line) + 1 > CHUNK_SIZE and current:
            chunks.append(current.strip())
            current = line + "\n"
        else:
            current += line + "\n"
    if current.strip():
        chunks.append(current.strip())
    return chunks

def analyze_chunked(text: str, instruction: str, content_type: str) -> str:
    
    chunks  = split_into_chunks(text)
    total   = len(chunks)
    profile = load_profile()

    print(f"\n{YELLOW}Tür: {content_type} | {total} parça{RESET}\n")

    analyzers = {
        "whatsapp": analyze_whatsapp,
        "note":     analyze_note,
        "cv":       analyze_cv,
        "general":  analyze_general,
    }
    analyzer    = analyzers.get(content_type, analyze_general)
    all_updates = {}

    for i, chunk in enumerate(chunks, 1):
        print(f"\r{progress_bar(i, total)}", end="", flush=True)

        try:
            updates = analyzer(chunk, instruction, profile)
            if not updates:
                continue

            for key, value in updates.items():
                if isinstance(value, list):
                    existing = all_updates.get(key, [])
                    for item in value:
                        if not any(str(e) == str(item) for e in existing):
                            existing.append(item)
                    all_updates[key] = existing
                elif isinstance(value, dict):
                    all_updates[key] = {**all_updates.get(key, {}), **value}
                else:
                    all_updates[key] = value

            merge_into_profile(updates)
            profile = load_profile()

        except Exception as e:
            print(f"\n{RED}[Parça {i} hatası]: {e}{RESET}")
            continue

    print()

    if not all_updates:
        return "Analiz tamamlandı, eklenecek yeni bilgi bulunamadı."

    summary = safe_generate(
        f"Şu analiz yapıldı ve profil güncellendi:\n"
        f"{json.dumps(all_updates, ensure_ascii=False, indent=2)}\n\n"
        "2-3 cümleyle ne buldun, kaç kişi/bilgi ekledin diye Türkçe özet ver."
    )
    return summary or f"{total} parça işlendi, profil güncellendi."

print("=" * 50)
print("NOVA — Manuel Analiz Modu")
print("=" * 50)

print(f"\n{YELLOW}Talimatını gir:{RESET}")
instruction = input("> ").strip()
if not instruction:
    print(f"{RED}Talimat boş.{RESET}")
    sys.exit(1)

print(f"\n{YELLOW}İçerik türü:{RESET}")
print("  1 — whatsapp  (sohbet geçmişi)")
print("  2 — note      (not, ders özeti, metin)")
print("  3 — cv        (özgeçmiş, profil belgesi)")
print("  4 — general   (genel metin)")
type_choice = input("> ").strip()
type_map = {"1": "whatsapp", "2": "note", "3": "cv", "4": "general",
            "whatsapp": "whatsapp", "note": "note", "cv": "cv", "general": "general"}
content_type = type_map.get(type_choice, "general")
print(f"{CYAN}Seçilen tür: {content_type}{RESET}")

print(f"\n{YELLOW}Kaynak seç:{RESET}")
print("  1 — Dosyadan oku")
print("  2 — Yapıştır")
choice = input("> ").strip()

if choice == "1":
    text, filename = get_text_from_file()
    print(f"\n{GREEN}'{filename}' okundu — {len(text):,} karakter{RESET}")
else:
    text = get_text_from_paste()

if not text.strip():
    print(f"{RED}Metin boş.{RESET}")
    sys.exit(1)

char_count = len(text)
print(f"\n{YELLOW}{char_count:,} karakter.{RESET}")

if char_count > CHUNK_SIZE:
    est = math.ceil(char_count / CHUNK_SIZE)
    print(f"{YELLOW}~{est} parçaya bölünerek analiz edilecek.{RESET}")
    result = analyze_chunked(text, instruction, content_type)
else:
    print(f"{YELLOW}Analiz başlatılıyor...{RESET}")
    from analyze import analyze_whatsapp, analyze_note, analyze_cv, analyze_general, merge_into_profile
    from memory import load_profile as lp, safe_generate
    import json
    profile   = lp()
    analyzers = {"whatsapp": analyze_whatsapp, "note": analyze_note,
                 "cv": analyze_cv, "general": analyze_general}
    updates   = analyzers.get(content_type, analyze_general)(text, instruction, profile)
    if updates:
        merge_into_profile(updates)
        result = safe_generate(
            f"Analiz yapıldı:\n{json.dumps(updates, ensure_ascii=False, indent=2)}\n\n"
            "2-3 cümleyle ne buldun, ne ekledin diye Türkçe özet ver."
        ) or "Analiz tamamlandı."
    else:
        result = "Eklenecek yeni bilgi bulunamadı."

print(f"\n{'=' * 50}")
print(f"{GREEN}NOVA: {result}{RESET}")
print("=" * 50)
