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

FIELD_PROMPTS = {

    "character": (
        "Kişinin KİŞİLİK ve KARAKTER özelliklerini analiz et.\n"
        "Her madde somut, tek cümle, doğrudan gözlem olmalı. Yorum değil, veri.\n\n"
        "Şunları dahil et:\n"
        "- Genel kişilik yapısı (içe/dışa dönük, duygusal/rasyonel, nevrotik/sakin)\n"
        "- Baskın karakter özellikleri (sohbetten kanıtlanmış)\n"
        "- Güçlü yönleri (somut örneklerle)\n"
        "- Zayıf yönleri ve kör noktaları\n"
        "- Ego ve özgüven düzeyi\n"
        "- Kibir veya alçakgönüllülük belirtileri\n"
        "- Empati kapasitesi\n"
        "- Mizah anlayışı ve espri tarzı\n"
        "- Mizacı (sinirli mi, sakin mi, değişken mi)\n"
        "- Sabır seviyesi\n"
        "- Sorumluluk alma tutumu\n"
        "- Başkasını suçlama eğilimi\n"
        "- Manipülatif davranışlar (varsa örneklerle)\n"
        "- Narsistik özellikler (varsa)\n"
        "- Savunmacılık düzeyi\n"
        "- Dürüstlük ve şeffaflık\n"
        "- Tutarsızlıklar (söylediği ile yaptığı arasındaki farklar)\n"
        "- Baskı altındaki davranışı\n"
        "- Başarı ve başarısızlık karşısındaki tutumu\n"
        "- Rekabetçilik düzeyi\n"
        "- Çekememezlik veya kıskançlık belirtileri\n"
        "- Övgüye verilen tepki\n"
        "- Eleştiriye verilen tepki\n"
        "- Karar verme şekli (aceleci mi, düşünceli mi)\n"
        "- Risk alma eğilimi\n"
        "- Özeleştiri kapasitesi\n"
        "- Şükran ve minnet duygusu\n"
        "- Bencillik veya cömertlik belirtileri\n"
        "- Merak ve öğrenme isteği\n"
        "- Açık fikirlilik\n"
        "- Ön yargıları ve kalıp düşünceleri\n"
        "- Sohbetten karakterini en iyi gösteren 5-10 direkt alıntı\n\n"
        "JSON: {\"character\": [\"madde 1\", \"madde 2\", ...]}"
    ),

    "communication_style": (
        "Kişinin İLETİŞİM TARZI ve YAZIŞMA DAVRANIŞLARINI analiz et.\n\n"
        "Şunları dahil et:\n"
        "- Mesaj uzunluğu tercihi (kısa/uzun, neden)\n"
        "- Emoji kullanım şekli ve anlamları\n"
        "- Noktalama işareti kullanımı (sıklık, tarz)\n"
        "- Yazım hataları ve dil kalitesi\n"
        "- Kelime dağarcığı zenginliği\n"
        "- Argo ve küfür kullanımı\n"
        "- Resmi/gayri resmi dil tercihi\n"
        "- Soru sorma şekli ve sıklığı\n"
        "- Cevap verme şekli (direkt mi, dolaylı mı)\n"
        "- Konuyu değiştirme kalıpları\n"
        "- Konuşmayı bitirme şekli\n"
        "- Sessizlik kalıpları (ne zaman, ne kadar cevap vermez)\n"
        "- Mesajları okundu bırakma davranışı\n"
        "- Tepki hızı (hızlı/yavaş, tutarlı mı)\n"
        "- Gece/gündüz mesajlaşma zamanları\n"
        "- Konuşmayı başlatma sıklığı (kim başlatıyor genellikle)\n"
        "- Çatışma anında iletişim değişimi\n"
        "- Üzgünken yazışma tarzı\n"
        "- Mutluyken yazışma tarzı\n"
        "- Sinirli/stresli anlaşma tarzı\n"
        "- Özür dileme şekli (diyor mu, nasıl)\n"
        "- Teşekkür etme şekli\n"
        "- İltifat alma ve verme şekli\n"
        "- Yardım isteme şekli\n"
        "- Hayır deme şekli\n"
        "- Haber verme vs sormadan paylaşma dengesi\n"
        "- Fotoğraf/medya paylaşım alışkanlığı\n"
        "- Sesli mesaj kullanımı\n"
        "- Tekrarlayan kalıp cümleler veya ifadeler\n"
        "- Hangi konularda aktif, hangilerinde pasif\n"
        "- Pasif agresif davranış belirtileri\n\n"
        "JSON: {\"communication_style\": [\"madde 1\", \"madde 2\", ...]}"
    ),

    "personal_info": (
        "Kişinin KİŞİSEL BİLGİLERİNİ ve HAYAT HİKAYESİNİ çıkar.\n"
        "Sadece sohbette geçen veya güçlü şekilde ima edilen bilgileri yaz.\n\n"
        "Şunları dahil et:\n"
        "- Yaş veya doğum tarihi (direkt veya çıkarım)\n"
        "- Yaşadığı şehir ve semt\n"
        "- Büyüdüğü yer\n"
        "- Eğitim durumu ve okulu\n"
        "- Bölümü veya alanı\n"
        "- Mevcut mesleği\n"
        "- Çalıştığı yer veya sektör\n"
        "- İş hayatındaki pozisyonu\n"
        "- Ekonomik durumu (zengin/orta/dar, ipuçlarından)\n"
        "- Para harcama alışkanlıkları\n"
        "- Araba veya ulaşım bilgisi\n"
        "- Ev durumu (kira/sahibi, kiminle yaşıyor)\n"
        "- Aile yapısı (ebeveynler, kardeşler, çocuklar)\n"
        "- Aile ile ilişki kalitesi\n"
        "- Medeni durumu\n"
        "- Romantik geçmişi (bahsettiyse)\n"
        "- Sağlık durumu\n"
        "- Geçirilmiş hastalıklar veya operasyonlar\n"
        "- Fiziksel özellikler (bahsettiyse)\n"
        "- Dini veya manevi inançları\n"
        "- Siyasi görüşü\n"
        "- Milliyetçilik veya etnik kimlik\n"
        "- Dil bilgisi\n"
        "- Seyahat geçmişi ve planları\n"
        "- Sosyal medya hesapları (bahsettiyse)\n"
        "- Çocukluktan bahsettiği önemli anılar\n"
        "- Geçmişte yaşadığı zor dönemler\n"
        "- Hayatını etkileyen önemli olaylar\n\n"
        "JSON: {\"personal_info\": [\"madde 1\", \"madde 2\", ...]}"
    ),

    "values_and_priorities": (
        "Kişinin DEĞERLER, ÖNCELİKLER ve DÜNYA GÖRÜŞÜNÜ analiz et.\n\n"
        "Şunları dahil et:\n"
        "- Hayatta en çok neye değer verdiği\n"
        "- Para ve maddi değerler hakkındaki tutumu\n"
        "- Başarı tanımı\n"
        "- Kariyer önceliği\n"
        "- Aile önceliği\n"
        "- Arkadaşlık ve sadakat anlayışı\n"
        "- Sevgi ve ilişki hakkındaki inançları\n"
        "- Özgürlük ve bağımsızlık tutumu\n"
        "- Güvenlik ihtiyacı\n"
        "- Statü ve prestij önemseme düzeyi\n"
        "- Maddi gösteriş eğilimi\n"
        "- Dini değerleri ve uygulaması\n"
        "- Siyasi değerleri\n"
        "- Adalet anlayışı\n"
        "- Çevre ve doğa duyarlılığı\n"
        "- Hayvanlara tutumu\n"
        "- Zaman yönetimi anlayışı\n"
        "- Sabah/gece insanı olması\n"
        "- Eğlence ve dinlenmeye verdiği önem\n"
        "- Spor ve sağlık önceliği\n"
        "- Entelektüel merak ve bilgi arayışı\n"
        "- Sanata ve kültüre ilgisi\n"
        "- Teknoloji ve yeniliğe açıklığı\n"
        "- Geleneksel mi, modern mi\n"
        "- Otorite ve kurallara tutumu\n"
        "- Risk ve güvenlik dengesi\n"
        "- Kısa vadeli zevk vs uzun vadeli hedef dengesi\n\n"
        "JSON: {\"values_and_priorities\": [\"madde 1\", \"madde 2\", ...]}"
    ),

    "relationship_dynamics": (
        "Kullanıcıyla ARASINDAKİ İLİŞKİ DİNAMİKLERİNİ ve GENEL İLİŞKİ KALIPLARINI analiz et.\n\n"
        "Şunları dahil et:\n"
        "- İlişkinin doğası ve nasıl başladığı\n"
        "- Güç dengesi (kim daha dominant)\n"
        "- Kim daha çok çaba harcıyor\n"
        "- Kim daha çok ihtiyaç duyuyor\n"
        "- Güven seviyesi\n"
        "- Samimiyet derinliği\n"
        "- Ortak ilgi alanları\n"
        "- Çatışma kalıpları ve nedenleri\n"
        "- Çatışma çözme şekli\n"
        "- İlişkide tekrarlayan sorunlar\n"
        "- Kullanıcıya karşı tutumu (samimi mi, çıkarcı mı, ilgisiz mi)\n"
        "- Sınır koyma ve sınırlara saygı\n"
        "- Bağımlılık veya bağımsızlık eğilimi\n"
        "- Kıskançlık veya sahiplenme\n"
        "- Kullanıcıyı manipüle etme girişimleri (varsa)\n"
        "- Destek verme ve alma şekli\n"
        "- Empati gösterme kalıpları\n"
        "- İlişkinin zirve noktaları\n"
        "- İlişkinin kriz noktaları\n"
        "- Romantik ilişkilerdeki genel kalıpları (geçmişten)\n"
        "- Arkadaşlık ilişkilerindeki kalıpları\n"
        "- İş ilişkilerindeki tutumu\n"
        "- Aile ilişkilerindeki kalıpları\n"
        "- İnsanlara genel güven düzeyi\n"
        "- Yabancılara tutumu\n"
        "- Otorite figürlerine tutumu\n\n"
        "JSON: {\"relationship_dynamics\": [\"madde 1\", \"madde 2\", ...]}"
    ),

    "social_life": (
        "Kişinin SOSYAL HAYATINI ve SOSYAL ÇEVRESINI analiz et.\n\n"
        "Şunları dahil et:\n"
        "- Sosyal çevresinin genişliği\n"
        "- Yakın arkadaş sayısı tahmini\n"
        "- Arkadaş çevresiyle ilişki kalitesi\n"
        "- Sohbette ismi geçen arkadaşlar ve özellikleri\n"
        "- Arkadaşlarıyla ne tür aktiviteler yapıyor\n"
        "- Sosyal etkinliklere katılım sıklığı\n"
        "- Parti ve eğlencelere tutumu\n"
        "- Alkol ve madde kullanımı (bahsettiyse)\n"
        "- Gece hayatı\n"
        "- Gittiği mekanlar ve yerler\n"
        "- Yeme içme alışkanlıkları dışarıda\n"
        "- Seyahat alışkanlıkları\n"
        "- Sosyal medya paylaşım şekli\n"
        "- Online vs gerçek hayat sosyal dengesi\n"
        "- Popülerlik ve sosyal statüsü\n"
        "- Liderlik mi, takipçilik mi\n"
        "- Gruplar içindeki rolü\n"
        "- Sosyal onay ihtiyacı\n"
        "- Yalnız kalmaya tutumu\n"
        "- İnsanlardan enerji mi alıyor, enerji mi veriyor\n"
        "- Topluluk önünde konuşma rahat mı\n"
        "- Yeni insanlarla tanışmaya açıklık\n"
        "- Komşuluk veya mahalle ilişkileri\n\n"
        "JSON: {\"social_life\": [\"madde 1\", \"madde 2\", ...]}"
    ),

    "daily_life": (
        "Kişinin GÜNLÜK HAYAT RUTINLERINI ve ALIŞKANLIKLARINI analiz et.\n\n"
        "Şunları dahil et:\n"
        "- Uyku düzeni (uyuma/uyanma saatleri, uyku kalitesi)\n"
        "- Sabah rutini\n"
        "- Akşam rutini\n"
        "- Yemek alışkanlıkları (ne yer, ne içer, ne kadar önem veriyor)\n"
        "- Yemek pişirme alışkanlığı\n"
        "- Kahve/çay/enerji içeceği bağımlılığı\n"
        "- Sigara kullanımı\n"
        "- Alkol tüketimi (sıklık ve miktar)\n"
        "- Spor ve fiziksel aktivite alışkanlığı\n"
        "- Spor türü ve sıklığı\n"
        "- Sağlık ve beslenmeye verdiği önem\n"
        "- Kişisel bakım alışkanlıkları\n"
        "- Giyim tarzı (bahsettiyse)\n"
        "- Ev düzeni ve temizlik alışkanlığı\n"
        "- Alışveriş alışkanlıkları\n"
        "- Para harcama kalıpları\n"
        "- Dijital cihaz kullanım alışkanlıkları\n"
        "- Sosyal medya ne kadar zaman harcıyor\n"
        "- TV/dizi/film izleme alışkanlıkları\n"
        "- Müzik zevki ve dinleme alışkanlığı\n"
        "- Kitap okuma alışkanlığı\n"
        "- Oyun oynama alışkanlığı\n"
        "- Hobileri ve ilgi alanları\n"
        "- Yaratıcı aktiviteler\n"
        "- Doğa aktiviteleri\n"
        "- Hafta sonu nasıl geçiriyor\n"
        "- Tatil ve tatil alışkanlıkları\n"
        "- İş/okul-özel hayat dengesi\n"
        "- Verimlilik ve üretkenlik kalıpları\n"
        "- Erteleme ve tembellik kalıpları\n"
        "- Stres azaltma yöntemleri\n\n"
        "JSON: {\"daily_life\": [\"madde 1\", \"madde 2\", ...]}"
    ),

    "emotional_patterns": (
        "Kişinin DUYGUSAL DÜNYASINI ve PSİKOLOJİK KALIPLARINI analiz et.\n\n"
        "Şunları dahil et:\n"
        "- Genel duygusal tonu ve ruh hali\n"
        "- Duygusal istikrar düzeyi\n"
        "- Duygu ifade etme şekli\n"
        "- Hangi duygular bastırılıyor\n"
        "- Öfke: tetikleyicileri, ifade şekli, süresi\n"
        "- Üzüntü: nasıl başa çıkıyor\n"
        "- Kaygı ve endişe kalıpları\n"
        "- Korku ve fobiler (bahsettiyse)\n"
        "- Mutluluk tetikleyicileri\n"
        "- Coşku ve heyecan kalıpları\n"
        "- Hayal kırıklığıyla başa çıkma\n"
        "- Yalnızlık hissi ile başa çıkma\n"
        "- Reddedilme korkusu veya deneyimi\n"
        "- Terk edilme korkusu\n"
        "- Bağlanma stili (güvenli/kaçıngan/kaygılı)\n"
        "- Geçmiş travmalar veya acılar (bahsettiyse)\n"
        "- Kayıp deneyimleri\n"
        "- Çocukluk yaraları (ima ediliyorsa)\n"
        "- Depresyon veya anksiyete belirtileri\n"
        "- Özsaygı düzeyi\n"
        "- Kimlik ve kendilik algısı\n"
        "- Gelecek kaygısı\n"
        "- Ölüm veya anlam hakkındaki düşünceleri (bahsettiyse)\n"
        "- Duygusal olgunluk seviyesi\n"
        "- Duygusal zeka belirtileri\n"
        "- Empati kapasitesi (duygusal)\n"
        "- İyimserlik/kötümserlik dengesi\n"
        "- Şikayet etme ve sızlanma sıklığı\n"
        "- Minnet ve takdir kapasitesi\n"
        "- Af etme kapasitesi\n"
        "- Kin tutma eğilimi\n\n"
        "JSON: {\"emotional_patterns\": [\"madde 1\", \"madde 2\", ...]}"
    ),

    "warnings": (
        "Kişiyle ilgili UYARILAR, RİSKLER ve TAVSİYELER.\n\n"
        "Şunları dahil et:\n"
        "- Güvenilirlik değerlendirmesi (somut örneklerle)\n"
        "- Sözünü tutma sicili\n"
        "- Yalan söyleme veya çarpıtma belirtileri\n"
        "- Manipülasyon teknikleri (kullanıyorsa: gaslighting, love bombing, silent treatment, vb.)\n"
        "- Toksik davranış kalıpları\n"
        "- Sömürücü eğilimler\n"
        "- Şiddet eğilimi (sözel veya fiziksel belirtiler)\n"
        "- Bağımlılık veya bağımlılık yapan davranışlar\n"
        "- Mali risk faktörleri\n"
        "- Tehlike sinyalleri (red flags)\n"
        "- Çift yüzlülük belirtileri\n"
        "- Arkadan iş çevirme belirtileri\n"
        "- Dedikodu ve gıybet alışkanlığı\n"
        "- Bu kişiyle ilişkide dikkat edilmesi gerekenler\n"
        "- Hangi konularda asla güvenilmez\n"
        "- Hangi konularda güvenilir\n"
        "- Bu kişiyle nasıl iletişim kurulmalı\n"
        "- Bu kişiyle nasıl iletişim kurulmamalı\n"
        "- Çatışma anında ne yapılmalı\n"
        "- Kırmızı çizgileri neler\n"
        "- Neleri sevdiği (onunla iyi geçinmek için)\n"
        "- Neleri sevmediği (kaçınılması gerekenler)\n"
        "- Güven inşa etme yöntemleri\n"
        "- Genel ilişki tavsiyesi\n"
        "- Güvenilirlik skoru: X/10 ve gerekçesi\n\n"
        "JSON: {\"warnings\": [\"madde 1\", \"madde 2\", ...], \"reliability_score\": \"X/10 — açıklama\"}"
    ),

    "connected_people": (
        "Sohbette BAHSEDİLEN veya İMA EDİLEN TÜM KİŞİLERİ listele.\n\n"
        "Her kişi için şunları çıkar:\n"
        "- Adı (tam veya kısmi)\n"
        "- Bu kişiyle ilişkisi\n"
        "- Hakkında söylenenler (olumlu/olumsuz)\n"
        "- Bu kişinin karakterine dair ipuçları\n"
        "- Sohbette geçme bağlamı\n\n"
        "JSON formatı:\n"
        "{\"connected_people\": ["
        "{\"name\": \"isim\", \"relation\": \"ilişki\", \"notes\": \"bilgiler\", \"sentiment\": \"olumlu/olumsuz/nötr\"}"
        "]}"
    ),
}

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
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    logger.warn("JSON", "Bozuk, Gemini ile duzeltiliyor")
    try:
        fixed = safe_generate(f"Bozuk JSON'i duzelt, sadece gecerli JSON dondur:\n\n{raw[:3000]}")
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
    return re.sub(r'[^\w\s-]', '', name.strip()).replace(" ", "_")

def _find_existing_character_dir(name: str) -> str | None:
    if not os.path.exists(CHARACTERS_DIR):
        return None
    name_clean = name.lower().strip().replace("_", " ")
    name_parts = [p for p in name_clean.split() if len(p) > 1]
    if not name_parts:
        return None
    best_match = None
    best_score = 0
    for entry in os.listdir(CHARACTERS_DIR):
        entry_path = os.path.join(CHARACTERS_DIR, entry)
        if not os.path.isdir(entry_path):
            continue
        file_clean = entry.replace("_", " ").lower()
        file_parts = [p for p in file_clean.split() if len(p) > 1]
        if file_clean == name_clean:
            return entry
        name_set = set(name_parts)
        file_set = set(file_parts)
        common   = name_set & file_set
        if common:
            score = len(common) / max(len(name_set), len(file_set))
            if (score >= 0.4 or any(len(w) >= 3 for w in common)) and score > best_score:
                best_score = score
                best_match = entry
    return best_match

def _get_character_dir(name: str) -> str:
    existing = _find_existing_character_dir(name)
    if existing:
        return os.path.join(CHARACTERS_DIR, existing)
    dirname = _safe_filename(name)
    path = os.path.join(CHARACTERS_DIR, dirname)
    os.makedirs(path, exist_ok=True)
    return path

def _load_field(char_dir: str, field: str) -> list | dict | str:
    path = os.path.join(char_dir, f"{field}.json")
    if not os.path.exists(path):
        return [] if field != "meta" else {}
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return [] if field != "meta" else {}

def _save_field(char_dir: str, field: str, data):
    path = os.path.join(char_dir, f"{field}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def _merge_list(existing: list, new_items: list) -> list:
    if not new_items:
        return existing
    existing_lower = {str(s).strip().lower() for s in existing}

    def _too_similar(item: str) -> bool:
        words = set(item.lower().split())
        if len(words) < 3:
            return item.lower() in existing_lower
        for ex in existing_lower:
            ex_words = set(ex.split())
            if not ex_words:
                continue
            common = words & ex_words
            if len(common) / max(len(words), len(ex_words)) >= 0.55:
                return True
        return False

    result = list(existing)
    for item in new_items:
        item_str = str(item).strip()
        if item_str and len(item_str) > 5 and not _too_similar(item_str):
            result.append(item_str)
            existing_lower.add(item_str.lower())
    return result

def load_character(name: str) -> dict:
    char_dir = _get_character_dir(name)
    result   = {}
    meta     = _load_field(char_dir, "meta")
    result.update(meta)
    for field in FIELD_PROMPTS.keys():
        data = _load_field(char_dir, field)
        if data:
            result[field] = data
    connected = _load_field(char_dir, "connected_people")
    if connected:
        result["connected_people"] = connected
    return result

def save_character_field(name: str, field: str, new_data):
    char_dir = _get_character_dir(name)
    if field == "meta":
        existing = _load_field(char_dir, "meta")
        if isinstance(existing, dict) and isinstance(new_data, dict):
            existing.update(new_data)
            new_data = existing
        _save_field(char_dir, "meta", new_data)
        return
    if field == "reliability_score":
        _save_field(char_dir, "reliability_score", new_data)
        return
    if field == "connected_people":
        existing = _load_field(char_dir, "connected_people")
        if not isinstance(existing, list):
            existing = []
        if isinstance(new_data, list):
            existing_names = {
                (p.get("name","") if isinstance(p, dict) else str(p)).lower()
                for p in existing
            }
            for item in new_data:
                item_name = (item.get("name","") if isinstance(item, dict) else str(item)).lower()
                if item_name not in existing_names:
                    existing.append(item)
                    existing_names.add(item_name)
        _save_field(char_dir, "connected_people", existing)
        return
    existing = _load_field(char_dir, field)
    if not isinstance(existing, list):
        existing = []
    if isinstance(new_data, list):
        merged = _merge_list(existing, new_data)
        _save_field(char_dir, field, merged)
        logger.success("Karakter", f"{name} / {field}: {len(merged) - len(existing)} yeni madde eklendi")

def list_characters() -> list:
    if not os.path.exists(CHARACTERS_DIR):
        return []
    return [
        entry.replace("_", " ")
        for entry in os.listdir(CHARACTERS_DIR)
        if os.path.isdir(os.path.join(CHARACTERS_DIR, entry))
    ]

def analyze_whatsapp_full(full_text: str, instruction: str, person_name: str) -> int:
    logger.info("Analiz", f"{person_name} icin tam analiz basliyor ({len(FIELD_PROMPTS)} alan)")
    saved_count = 0

    for field, field_prompt in FIELD_PROMPTS.items():
        print(f"  {CYAN}→ {field}{RESET}", flush=True)
        prompt = (
            f"SOHBET METNİ (tamamı):\n{full_text}\n\n"
            f"KULLANICI TALİMATI: {instruction}\n\n"
            f"KİŞİ: {person_name}\n\n"
            f"{field_prompt}\n\n"
            "KURALLAR:\n"
            "- Her madde tek cümle, somut, kanıtlanmış\n"
            "- Yorum değil doğrudan gözlem\n"
            "- Emin olmadığın şeyi yazma\n"
            "- Mümkün olduğunca fazla madde çıkar, detaydan ödün verme\n"
            "- Sadece JSON döndür, başka hiçbir şey yazma"
        )
        raw    = safe_generate(prompt)
        parsed = _parse_json(raw)
        if not parsed:
            logger.warn("Analiz", f"{field} bos geldi")
            continue

        if field == "warnings":
            items = parsed.get("warnings", [])
            score = parsed.get("reliability_score", "")
            save_character_field(person_name, "warnings", items)
            if score:
                save_character_field(person_name, "reliability_score", score)
        elif field == "connected_people":
            items = parsed.get("connected_people", [])
            save_character_field(person_name, "connected_people", items)
        else:
            items = parsed.get(field, [])
            save_character_field(person_name, field, items)

        saved_count += len(items) if isinstance(items, list) else 1

    char_dir = _get_character_dir(person_name)
    _save_field(char_dir, "meta", {
        "name": person_name,
        "source": "whatsapp_analysis",
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M")
    })
    logger.success("Analiz", f"{person_name} tamamlandi — {saved_count} madde")
    return saved_count

def detect_people_in_chat(full_text: str) -> list:
    prompt = (
        f"Bu WhatsApp sohbetinde kimler var?\n\n"
        f"METİN:\n{full_text[:5000]}\n\n"
        "Sohbetteki kişilerin adlarını veya numaralarını listele.\n"
        "Sadece JSON: {\"people\": [\"İsim1\", \"İsim2\", ...]}"
    )
    raw    = safe_generate(prompt)
    parsed = _parse_json(raw)
    return parsed.get("people", [])

def analyze_whatsapp(text: str, instruction: str, profile: dict) -> dict:
    people = detect_people_in_chat(text)
    if not people:
        logger.warn("Analiz", "Sohbette kisi tespit edilemedi")
        return {}
    logger.info("Analiz", f"Tespit edilen kisiler: {', '.join(people)}")
    relations = []
    for person in people:
        count = analyze_whatsapp_full(text, instruction, person)
        relations.append({"name": person, "relation": "whatsapp_contact"})
        print(f"  {GREEN}✓ {person}: {count} madde{RESET}")
    return {"relations": relations}

def analyze_whatsapp_incremental(chunk: str, instruction: str, accumulated: dict) -> dict:
    existing_summary = ""
    for person_name, fields in accumulated.items():
        total = sum(len(v) for v in fields.values() if isinstance(v, list))
        existing_summary += f"- {person_name}: {total} madde mevcut\n"
    if not existing_summary:
        existing_summary = "Henuz hic bilgi yok."
    prompt = (
        f"KULLANICI TALİMATI: {instruction}\n\n"
        f"MEVCUT KAYITLAR (bunlari tekrar yazma):\n{existing_summary}\n\n"
        f"YENİ PARÇA:\n{chunk}\n\n"
        "Bu parcada mevcut kayitlarda OLMAYAN yeni bilgiler var mi?\n"
        "Varsa: her kisi icin sadece yeni maddeleri JSON listesi olarak dondur.\n"
        "Yoksa: bos JSON dondur {}\n\n"
        "Format: {\"KisiAdi\": {\"character\": [...], \"communication_style\": [...], ...}}"
    )
    raw    = safe_generate(prompt)
    parsed = _parse_json(raw)
    if not parsed:
        return {}
    for person_name, fields in parsed.items():
        if not isinstance(fields, dict):
            continue
        for field, items in fields.items():
            if isinstance(items, list) and items:
                save_character_field(person_name, field, items)
    return parsed

def analyze_note(text: str, instruction: str, profile: dict) -> dict:
    prompt = (
        f"Asagidaki metni analiz et.\n\n"
        f"KULLANICI TALİMATI: {instruction}\n\n"
        f"METİN:\n{text}\n\n"
        "1. Ana konuyu tespit et\n"
        "2. En onemli 3-5 noktayi cikar\n"
        "3. Varsa sinav/gorev/tarih bilgilerini tespit et\n\n"
        "JSON: {\"important_notes\": [\"not1\"], "
        "\"exams\": [{\"course\": \"ders\", \"date\": \"tarih\", \"passed\": false}], "
        "\"tasks\": [{\"title\": \"gorev\", \"done\": false}]}"
    )
    return _parse_json(safe_generate(prompt))

def analyze_cv(text: str, instruction: str, profile: dict) -> dict:
    prompt = (
        f"Asagidaki CV veya belgeyi analiz et.\n\n"
        f"KULLANICI TALİMATI: {instruction}\n\n"
        f"METİN:\n{text}\n\n"
        "JSON: {\"personal\": {\"notes\": \"ozet\"}, \"goals\": [\"hedef\"], \"important_notes\": [\"bilgi\"]}"
    )
    return _parse_json(safe_generate(prompt))

def analyze_general(text: str, instruction: str, profile: dict) -> dict:
    prompt = (
        f"Asagidaki metni kullanicinin talimatina gore analiz et.\n"
        f"Analizler olabildigince detayli olmali.\n\n"
        f"KULLANICI TALİMATI: {instruction}\n\n"
        f"MEVCUT PROFİL:\n{json.dumps(profile, ensure_ascii=False, indent=2)}\n\n"
        f"METİN:\n{text}\n\n"
        "Sadece degisecek/eklenecek alanlari JSON olarak dondur.\n"
        "Kullanilabilecek alanlar: relations, important_notes, exams, tasks, goals, personal, courses, habits"
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
    chars     = list_characters()
    chars_str = ", ".join(chars) if chars else "yok"
    summary   = safe_generate(
        f"Su analizi yaptin:\n{json.dumps(updates, ensure_ascii=False, indent=2)}\n\n"
        f"Kayitli karakter klasorleri: {chars_str}\n\n"
        "2-3 cumleyle ne buldun, hangi kisilerin dosyasi olusturuldu diye Turkce ozet ver."
    )
    return summary or f"Analiz tamamlandi. Karakter klasorleri: {chars_str}"
