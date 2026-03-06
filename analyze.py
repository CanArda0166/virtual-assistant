import json
import os
import re
from datetime import datetime
import logger
from config import CHARACTERS_DIR
from memory import safe_generate, load_profile, save_profile, _merge_profile_updates

YELLOW = "\033[33m"
GREEN  = "\033[32m"
RED    = "\033[31m"
CYAN   = "\033[96m"
RESET  = "\033[0m"

os.makedirs(CHARACTERS_DIR, exist_ok=True)

_JSON_KEYS_RULE = (
    "\nZORUNLU: Tüm JSON anahtarları İngilizce olmalı. "
    "Kullan: personal, courses, exams, tasks, habits, relations, goals, important_notes. "
    "Türkçe anahtar KULLANMA.\n"
)

def _parse_json(raw: str) -> dict:
    if not raw:
        return {}

    if "```" in raw:
        parts = raw.split("```")
        raw   = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]

    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    try:
        start = raw.index("{")
        end   = raw.rindex("}") + 1
        return json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        pass

    try:
        import re
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    logger.warn("JSON", "Bozuk, Gemini ile duzeltiliyor")
    try:
        fix_prompt = (
            f"Aşağıdaki bozuk JSON'ı düzelt ve sadece geçerli JSON döndür:\n\n{raw[:3000]}"
        )
        fixed = safe_generate(fix_prompt)
        if fixed:
            if "```" in fixed:
                fixed = fixed.split("```")[1]
                if fixed.startswith("json"):
                    fixed = fixed[4:]
            return json.loads(fixed.strip())
    except Exception as e:
        logger.error("JSON", "Gemini duzeltme basarisiz", e)

    logger.error("JSON", "Parse tamamen basarisiz")
    return {}

def _safe_filename(name: str) -> str:
    
    clean = re.sub(r'[^\w\s-]', '', name.strip())
    return clean.replace(" ", "_")

def _find_existing_character_file(name: str) -> str | None:
    
    if not os.path.exists(CHARACTERS_DIR):
        return None

    name_clean      = name.lower().strip().replace("_", " ")
    name_parts      = [p for p in name_clean.split() if len(p) > 1]

    if not name_parts:
        return None

    best_match = None
    best_score = 0

    for filename in os.listdir(CHARACTERS_DIR):
        if not filename.endswith(".json"):
            continue

        file_key   = filename.replace(".json", "")
        file_clean = file_key.replace("_", " ").lower()
        file_parts = [p for p in file_clean.split() if len(p) > 1]

        if file_clean == name_clean:
            return file_key

        if name_clean.startswith("+") and name_clean.replace(" ", "") in file_clean.replace(" ", ""):
            return file_key

        name_set = set(name_parts)
        file_set = set(file_parts)
        common   = name_set & file_set
        if common:
            score = len(common) / max(len(name_set), len(file_set))
            single_match = any(len(w) >= 3 for w in common)
            if (score >= 0.4 or single_match) and score > best_score:
                best_score = score
                best_match = file_key

        if all(p in file_parts for p in name_parts) or all(p in name_parts for p in file_parts):
            if len(common) > best_score:
                best_score = len(common)
                best_match = file_key

    return best_match

def load_character(name: str) -> dict:
    
    existing_key = _find_existing_character_file(name)
    if existing_key:
        path = os.path.join(CHARACTERS_DIR, f"{existing_key}.json")
    else:
        path = os.path.join(CHARACTERS_DIR, f"{_safe_filename(name)}.json")

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_character(name: str, data: dict):
    
    existing_key = _find_existing_character_file(name)
    if existing_key:
        filename = f"{existing_key}.json"
        logger.info("Karakter", f"Birlestirildi: {filename}")
    else:
        filename = f"{_safe_filename(name)}.json"

    path     = os.path.join(CHARACTERS_DIR, filename)
    existing = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                existing = json.load(f)
            except json.JSONDecodeError:
                existing = {}

    for key, value in data.items():
        if key in ("last_updated", "source"):
            continue

        if isinstance(value, str) and value:
            existing_val = existing.get(key, "")
            if not existing_val:
                existing[key] = value
            else:
                existing_sentences = set(s.strip() for s in existing_val.replace("\n", ".").split(".") if s.strip())
                new_sentences      = [s.strip() for s in value.replace("\n", ".").split(".") if s.strip()]
                added = []
                for s in new_sentences:
                    if s not in existing_sentences and len(s) > 10:
                        added.append(s)
                        existing_sentences.add(s)
                if added:
                    existing[key] = existing_val.rstrip() + "\n" + ". ".join(added)

        elif isinstance(value, list) and value:
            old_list = existing.get(key, [])

            if key == "connected_people":
                def _norm(n):
                    return str(n).lower().strip().replace("_", " ")

                existing_names = {
                    _norm(p.get("name", "")) if isinstance(p, dict) else _norm(p)
                    for p in old_list
                }
                for item in value:
                    item_name = _norm(item.get("name", "")) if isinstance(item, dict) else _norm(item)
                    if not item_name:
                        continue
                    item_parts = set(item_name.split())
                    matched = False
                    for ex_name in existing_names:
                        ex_parts = set(ex_name.split())
                        common   = item_parts & ex_parts
                        if common and any(len(w) >= 3 for w in common):
                            matched = True
                            for i, p in enumerate(old_list):
                                p_name = _norm(p.get("name", "")) if isinstance(p, dict) else _norm(p)
                                p_parts = set(p_name.split())
                                if item_parts & p_parts:
                                    if isinstance(item, dict) and isinstance(old_list[i], dict):
                                        old_list[i] = {**old_list[i], **item}
                                    break
                            break
                    if not matched:
                        old_list.append(item)
                        existing_names.add(item_name)
            else:
                existing_strs = {str(o).lower().strip() for o in old_list}
                for item in value:
                    item_str = str(item).lower().strip()
                    if item_str not in existing_strs and len(item_str) > 3:
                        old_list.append(item)
                        existing_strs.add(item_str)

            existing[key] = old_list

        elif isinstance(value, dict) and value:
            existing[key] = {**existing.get(key, {}), **value}

    list_fields = ["character", "communication_style", "personal_info",
                   "values_and_priorities", "relationship_dynamics",
                   "social_life", "daily_life", "emotional_patterns",
                   "warnings", "communication_tips", "advice"]
    for field in list_fields:
        if field not in data:
            continue
        new_val = data[field]
        if isinstance(new_val, str) and new_val:
            import re as _re
            sentences = _re.split(r'(?<=[.!?])\s+', new_val)
            new_val = [s.strip() for s in sentences if s.strip()]
        if isinstance(new_val, list):
            old_list = existing.get(field, [])
            old_set  = {str(s).strip().lower() for s in old_list}

            def _is_too_similar(new_s: str, existing_set: set) -> bool:
                
                new_words = set(new_s.lower().split())
                if len(new_words) < 3:
                    return new_s.lower() in existing_set
                for ex in existing_set:
                    ex_words = set(ex.split())
                    if not ex_words:
                        continue
                    common = new_words & ex_words
                    similarity = len(common) / max(len(new_words), len(ex_words))
                    if similarity >= 0.5:
                        return True
                return False

            for item in new_val:
                item_str = str(item).strip()
                if item_str and not _is_too_similar(item_str, old_set):
                    old_list.append(item_str)
                    old_set.add(item_str.lower())
            existing[field] = old_list

    existing["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=4)

    logger.success("Karakter", f"Kaydedildi: {path}")

def list_characters() -> list[str]:
    
    if not os.path.exists(CHARACTERS_DIR):
        return []
    return [
        f.replace(".json", "").replace("_", " ")
        for f in os.listdir(CHARACTERS_DIR)
        if f.endswith(".json")
    ]

def resolve_connected_people():
    
    if not os.path.exists(CHARACTERS_DIR):
        return

    files = [f for f in os.listdir(CHARACTERS_DIR) if f.endswith(".json")]
    updated = 0

    for filename in files:
        path = os.path.join(CHARACTERS_DIR, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        connected = data.get("connected_people", [])
        if not connected:
            continue

        changed = False
        for i, person in enumerate(connected):
            if not isinstance(person, dict):
                continue
            raw_name = person.get("name", "")
            if not raw_name:
                continue
            normalized = raw_name.strip().replace("_", " ")
            match = _find_existing_character_file(normalized)
            if match:
                real_name = match.replace("_", " ")
                connected[i]["name"]      = real_name
                connected[i]["file_link"] = match + ".json"
                changed = True
            elif normalized != raw_name:
                connected[i]["name"] = normalized
                changed = True

        if changed:
            data["connected_people"] = connected
            data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            updated += 1

    if updated:
        logger.success("Karakter", f"{updated} dosyada baglantilar guncellendi")

def analyze_whatsapp(text: str, instruction: str, profile: dict) -> dict:
    
    prompt = (
        f"Aşağıdaki WhatsApp sohbet geçmişini SON DERECE detaylı analiz et.\n\n"
        f"KULLANICININ TALİMATI: {instruction}\n\n"
        f"SOHBET METNİ:\n{text}\n\n"
        "━━━ İSİMLENDİRME KURALI (ZORUNLU) ━━━\n"
        "- Kişinin adı kayıtlıysa: tam adını yaz (örn: Mehmet_Ali_Şimşek)\n"
        "- Kayıtlı değilse: sadece telefon numarasını yaz (örn: +90_555_123_4567)\n"
        "- Asla lakap, unvan, yapay isim kullanma\n\n"
        "━━━ GÖREV ━━━\n"
        "Sohbetteki her kişi için aşağıdaki TÜM kategorileri doldur.\n"
        "Her kategori için somut örnekler ve sohbetten doğrudan alıntılar kullan.\n"
        "Kesinlikle yüzeysel geçme — ne kadar detay o kadar iyi.\n"
        "Her kişi için character alanı EN AZ 50 CÜMLE olmalı.\n"
        "Her cümleyi ayrı satıra yaz, tek uzun paragraf yapma.\n\n"
        "━━━ KATEGORİLER ━━━\n\n"
        "1. KİŞİLİK VE KARAKTER\n"
        "   - Genel kişilik yapısı (içe/dışa dönük, duygusal/rasyonel, introvert/extrovert)\n"
        "   - Baskın karakter özellikleri (somut sohbet örnekleriyle kanıtla)\n"
        "   - Güçlü yönleri\n"
        "   - Zayıf yönleri ve kör noktaları\n"
        "   - Mizah anlayışı ve espri tarzı\n"
        "   - Empati seviyesi\n"
        "   - Ego ve özgüven düzeyi\n"
        "   - Manipülatif eğilimler varsa belirt\n\n"
        "2. İLETİŞİM TARZI\n"
        "   - Yazma şekli (uzun/kısa mesajlar, emoji kullanımı, noktalama)\n"
        "   - Dil tercihleri ve kelime seçimleri\n"
        "   - Tepki hızı ve kalıpları\n"
        "   - Çatışma anlarındaki tutumu\n"
        "   - Hangi konularda aktif, hangilerinde pasif\n"
        "   - Soru sorma ve cevap verme şekli\n"
        "   - Sessizlik kalıpları (ne zaman cevap vermez)\n\n"
        "3. KİŞİSEL BİLGİLER\n"
        "   - Doğum tarihi veya yaşı (sohbetten çıkarılabiliyorsa)\n"
        "   - Yaşadığı şehir/semt\n"
        "   - Eğitim durumu\n"
        "   - Meslek veya iş hayatı\n"
        "   - Ekonomik durumu (ipuçlarından çıkar)\n"
        "   - Aile durumu (kardeş, ebeveyn bahsi geçtiyse)\n"
        "   - Sağlık durumu (bahsettiyse)\n\n"
        "4. DEĞERLER VE PRİORİTELER\n"
        "   - Hayatta neye değer verdiği\n"
        "   - Para hakkındaki tutumu\n"
        "   - Zaman yönetimi\n"
        "   - Aile ve arkadaşlık öncelikleri\n"
        "   - Kariyer ve başarı anlayışı\n"
        "   - Siyasi veya dini görüşleri (bahsettiyse)\n"
        "   - Ahlaki değerleri\n\n"
        "5. İLİŞKİ DİNAMİKLERİ\n"
        "   - Kullanıcıyla ilişkinin doğası ve tarihi\n"
        "   - Güç dengesi (kim daha dominant)\n"
        "   - Güven seviyesi\n"
        "   - Ortak ilgi alanları\n"
        "   - Gerilim veya çatışma noktaları\n"
        "   - İlişkide tekrarlayan kalıplar\n"
        "   - Kullanıcıya karşı tutumu (samimi mi, çıkarcı mı, vb.)\n\n"
        "6. SOSYAL HAYAT VE ÇEVRE\n"
        "   - Arkadaş çevresi (sohbette bahsedilen isimler)\n"
        "   - Sosyal aktiviteleri\n"
        "   - Sosyal medya kullanımı (bahsettiyse)\n"
        "   - Gittiği mekanlar, yaptığı aktiviteler\n\n"
        "7. GÜNLÜK HAYAT VE ALIŞKANLIKLAR\n"
        "   - Uyku düzeni\n"
        "   - Yeme içme alışkanlıkları\n"
        "   - Spor veya fiziksel aktivite\n"
        "   - Hobiler ve ilgi alanları\n"
        "   - Rutinleri\n"
        "   - Bağımlılık veya kötü alışkanlıklar (bahsettiyse)\n\n"
        "8. DUYGUSAL DURUM VE KALIPLAR\n"
        "   - Genel ruh hali\n"
        "   - Stres kaynakları\n"
        "   - Mutlu olduğu şeyler\n"
        "   - Tekrarlayan şikayetler ve endişeler\n"
        "   - Travma veya zorlu dönemler (bahsettiyse)\n"
        "   - Duygusal olgunluk seviyesi\n\n"
        "9. BAĞLANTILI KİŞİLER\n"
        "   - Sohbette bahsedilen diğer kişiler\n"
        "   - Bu kişilerle ilişkisi\n"
        "   - Hakkında konuştuğu kişiler (olumlu/olumsuz)\n"
        "   - Ortak tanıdıklar\n\n"
        "10. KULLANICIYA ÖZEL NOTLAR\n"
        "    - Bu kişiyle ilişkide dikkat edilmesi gerekenler\n"
        "    - Risk faktörleri ve tehlike işaretleri\n"
        "    - Güvenilirlik değerlendirmesi\n"
        "    - Bu kişiyle nasıl iletişim kurulmalı\n"
        "    - Genel tavsiyeler\n\n"
        "Yanıtını TAM OLARAK şu JSON formatında ver, başka hiçbir şey yazma:\n"
        '{\n'
        '  "people": [\n'
        '    {\n'
        '      "name": "Tam_Isim_Soyisim veya +90_555_123_4567",\n'
        '      "relation": "ilişki türü",\n'
        '      "character": ["Cümle 1.", "Cümle 2.", "...En az 50 cümle, her cümle ayrı liste elemanı"],\n'
        '      "communication_style": ["iletişim tarzı cümle 1", "cümle 2", "..."],\n'
        '      "personal_info": ["kişisel bilgi 1", "bilgi 2", "..."],\n'
        '      "values_and_priorities": ["değer 1", "öncelik 2", "..."],\n'
        '      "relationship_dynamics": ["dinamik 1", "dinamik 2", "..."],\n'
        '      "social_life": ["sosyal hayat detayı 1", "detay 2", "..."],\n'
        '      "daily_life": ["günlük hayat detayı 1", "detay 2", "..."],\n'
        '      "emotional_patterns": ["duygusal pattern 1", "pattern 2", "..."],\n'
        '      "connected_people": [{"name": "bağlantılı kişi adı", "relation": "bu kişiyle ilişkisi", "context": "bağlam"}],\n'
        '      "warnings": ["uyarı 1", "uyarı 2", "..."],\n'
        '      "reliability_score": "8/10 — kısa açıklama",\n'
        '      "communication_tips": ["ipucu 1", "ipucu 2", "..."],\n'
        '      "advice": ["tavsiye 1", "tavsiye 2", "..."],\n'
        '      "important_notes": ["önemli notlar"],\n'
        '      "quotes": ["sohbetten karakterini en iyi yansıtan alıntılar"]\n'
        '    }\n'
        '  ],\n'
        '  "general_notes": ["sohbetten çıkan genel önemli gözlemler"],\n'
        '  "group_dynamics": "grup varsa grup dinamikleri",\n'
        '  "red_flags": ["dikkat çeken tehlike işaretleri"]\n'
        '}'
    )

    raw     = safe_generate(prompt)
    parsed  = _parse_json(raw)
    people  = parsed.get("people", [])

    if not people:
        return {}

    saved_names = []
    for person in people:
        name = person.get("name", "").strip()
        if not name:
            continue

        character_data = {
            "name":                name,
            "relation":            person.get("relation", ""),
            "character":           person.get("character", ""),
            "communication_style": person.get("communication_style", ""),
            "personal_info":       person.get("personal_info", ""),
            "values_and_priorities":person.get("values_and_priorities", ""),
            "relationship_dynamics":person.get("relationship_dynamics", ""),
            "social_life":         person.get("social_life", ""),
            "daily_life":          person.get("daily_life", ""),
            "emotional_patterns":  person.get("emotional_patterns", ""),
            "connected_people":    person.get("connected_people", []),
            "warnings":            person.get("warnings", ""),
            "reliability_score":   person.get("reliability_score", ""),
            "communication_tips":  person.get("communication_tips", ""),
            "advice":              person.get("advice", ""),
            "important_notes":     person.get("important_notes", []),
            "quotes":              person.get("quotes", []),
            "source":              "whatsapp_analysis",
        }
        save_character(name, character_data)
        saved_names.append(name)

    relations_for_profile = [
        {"name": p.get("name", ""), "relation": p.get("relation", "")}
        for p in people if p.get("name")
    ]

    general_notes = parsed.get("general_notes", [])

    return {
        "relations":      relations_for_profile,
        "important_notes": general_notes
    }

def analyze_note(text: str, instruction: str, profile: dict) -> dict:
    prompt = (
        f"Aşağıdaki metni analiz et.\n\n"
        f"KULLANICININ TALİMATI: {instruction}\n\n"
        f"METİN:\n{text}\n\n"
        "1. Ana konuyu tespit et\n"
        "2. En önemli 3-5 noktayı çıkar\n"
        "3. Varsa sınav/görev/tarih bilgilerini tespit et\n\n"
        f"{_JSON_KEYS_RULE}"
        "Yanıtını TAM OLARAK şu JSON formatında ver:\n"
        '{"important_notes": ["not1"], '
        '"exams": [{"course": "ders", "date": "tarih", "passed": false}], '
        '"tasks": [{"title": "görev", "done": false}]}'
    )
    return _parse_json(safe_generate(prompt))

def analyze_cv(text: str, instruction: str, profile: dict) -> dict:
    prompt = (
        f"Aşağıdaki CV veya belgeyi analiz et.\n\n"
        f"KULLANICININ TALİMATI: {instruction}\n\n"
        f"METİN:\n{text}\n\n"
        f"{_JSON_KEYS_RULE}"
        "Yanıtını TAM OLARAK şu JSON formatında ver:\n"
        '{"personal": {"notes": "özet"}, "goals": ["hedef"], "important_notes": ["bilgi"]}'
    )
    return _parse_json(safe_generate(prompt))

def analyze_general(text: str, instruction: str, profile: dict) -> dict:
    prompt = (
        f"Aşağıdaki metni kullanıcının talimatına göre analiz et.\n"
        f"Analizler olabildiğince detaylı olmalı — hiçbir bilgiyi atla.\n\n"
        f"KULLANICININ TALİMATI: {instruction}\n\n"
        f"MEVCUT PROFİL:\n{json.dumps(profile, ensure_ascii=False, indent=2)}\n\n"
        f"METİN:\n{text}\n\n"
        f"{_JSON_KEYS_RULE}"
        "Sadece değişecek/eklenecek alanları JSON olarak döndür. "
        "Kullanılabilecek alanlar: relations, important_notes, exams, tasks, goals, personal, courses, habits"
    )
    return _parse_json(safe_generate(prompt))

def merge_into_profile(updates: dict) -> bool:
    if not updates:
        return False
    profile = load_profile()
    updated = _merge_profile_updates(profile, updates)
    save_profile(updated)
    return True

def analyze(text: str, instruction: str, content_type: str = "general") -> str:
    logger.info("Analiz", f"Baslatiliyor — tur: {content_type}")

    profile   = load_profile()
    analyzers = {
        "whatsapp": analyze_whatsapp,
        "note":     analyze_note,
        "cv":       analyze_cv,
        "general":  analyze_general,
    }
    updates = analyzers.get(content_type, analyze_general)(text, instruction, profile)

    if not updates:
        return "Metni analiz edemedim, tekrar dener misin?"

    merge_into_profile(updates)
    logger.success("Analiz", "Profil guncellendi")

    resolve_connected_people()

    chars = list_characters()
    chars_str = ", ".join(chars) if chars else "yok"

    summary = safe_generate(
        f"Şu analizi yaptın:\n{json.dumps(updates, ensure_ascii=False, indent=2)}\n\n"
        f"Kayıtlı karakter dosyaları: {chars_str}\n\n"
        "2-3 cümleyle ne buldun, hangi kişilerin dosyası oluşturuldu diye Türkçe özet ver."
    )
    return summary or f"Analiz tamamlandı. Karakter dosyaları: {chars_str}"
