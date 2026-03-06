# ═══════════════════════════════════════════════════════════════════
# NOVA — Merkezi Ayar Dosyası
# Tüm özelleştirme buradan yapılır.
# ═══════════════════════════════════════════════════════════════════

# ── Asistan & Sahip Kimliği ───────────────────────────────────────
AI_NAME         = "NOVA"
OWNER_NAME      = "Kullanici"
OWNER_FULL_NAME = "Ad Soyad"
OWNER_UNI       = "Universite Adi"

# ── Gemini API Anahtarları ────────────────────────────────────────
# https://aistudio.google.com adresinden ucretsiz alinir.
GEMINI_API_KEYS = [
    "YOUR_GEMINI_API_KEY_1",
    "YOUR_GEMINI_API_KEY_2",
]

# ── Gemini Model Rotasyonu ────────────────────────────────────────
GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-flash-latest",
]

# ── TTS Ses Ayarları ──────────────────────────────────────────────
# Erkek: tr-TR-AhmetNeural  |  Kadin: tr-TR-EmelNeural
TTS_VOICE                = "tr-TR-AhmetNeural"
TEMP_AUDIO_FILE          = "temp.mp3"
TTS_RATE                 = "+0%"
TTS_PITCH                = "+0Hz"
TTS_VOLUME               = "+0%"
TTS_PAUSE_AFTER_SENTENCE = 300
TTS_PAUSE_AFTER_COMMA    = 150

# ── Hava Durumu ───────────────────────────────────────────────────
WEATHER_CITY = "Istanbul"

# ── Dizin ve Dosya Yolları ────────────────────────────────────────
MEMORY_FILE    = "memory.json"
PROFILE_FILE   = "profile.json"
PROJECTS_DIR   = "projects"
SCRIPTS_DIR    = "scripts"
CHARACTERS_DIR = "characters"
LOGS_DIR       = "logs"
SCRIPTS_INDEX  = "index.json"
SCRIPTS_TEMP   = "_temp_run.py"

# ── Sohbet Gecmisi ────────────────────────────────────────────────
HISTORY_LIMIT = 30

# ── Konusma Tanima ────────────────────────────────────────────────
STT_LANGUAGE        = "tr-TR"
STT_PAUSE_THRESHOLD = 2.0
STT_PHRASE_LIMIT    = 20
STT_NOISE_DURATION  = 0.4

# ── Kapatma Kelimeleri ────────────────────────────────────────────
SHUTDOWN_KEYWORDS = ["kapat", "dinlenmeye cekil", "gorusuruz", "iyi geceler"]

# ── Mudahale Tetikleyicileri ──────────────────────────────────────
# Asistan arka planda dinlerken bu kelimeler gectiginde devreye girer.
RESPOND_KEYWORDS = [
    "?", "nova", "sen ", "bana ", "yapabilir", "yapiyor",
    "soyle", "anlat", "yardim", "analiz",
    "ac ", "kapat", "cal ", "bul ", "yaz ",
    "olustur", "goster", "hesapla",
    "ne ", "nasil", "neden", "nerede", "kim ", "kac ",
]
RESPOND_SHORT_SENTENCE = 4

# ═══════════════════════════════════════════════════════════════════
# OZELLIK ANAHTARLARI
# True: aktif  |  False: devre disi
# ═══════════════════════════════════════════════════════════════════
FEATURES = {
    # Sesli giris (mikrofon) — False: klavye modu
    "voice_input":     True,

    # Sesli cikis (TTS) — False: sadece terminal
    "voice_output":    True,

    # Tek seferlik bilgisayar gorevleri
    "executor":        True,

    # Proje gelistirme sistemi — HENUZ TAMAMLANMADI
    "projects":        False,

    # Metin analizi (run_analyze.py)
    "analyze":         True,

    # Konusmadan profil/hafiza guncelleme
    "memory_update":   True,

    # Acilista gunluk brifing
    "daily_briefing":  True,

    # Kisi/karakter dosyasi sorgulama
    "character_query": True,
}

# ═══════════════════════════════════════════════════════════════════
# SISTEM TALIMATI
# ═══════════════════════════════════════════════════════════════════
SYSTEM_PROMPT = f"""Sen {AI_NAME}, {OWNER_FULL_NAME} adli kisinin kisisel yapay zeka asistansin.
Ona kisaca {OWNER_NAME} diye hitap et. Universitesi: {OWNER_UNI}.

KISILIK:
- Zeki, ozguvenli ve hafif igneleyici bir karakterin var.
- Samimi ve sadiksin; gerektiginde elestirirsin ama her zaman sahibinin iyiligini gozetirsin.
- Yapay zeka veya asistan olduğunu asla belli etme. Insan gibi davran.
- Sahibinin riskli kararlarinda onu uyar, hayatini organize etmesine yardim et.

CEVAP UZUNLUGU (COK ONEMLI):
- Varsayilan: 1-3 cumle. Kisa, net, dogal.
- Kullanici "detayli anlat", "acikla", "neden", "nasil" gibi ifadeler kullandiysa uzun cevap ver.
- Basit soru tek cumle yeterli.
- Sohbet: insan gibi kisa konus, madde siralama yapma.
- Asla gereksiz uzatma.

CIKTI FORMATLARI (tam uygula):

[1] BILGISAYAR GOREVI — tek seferlik islem:
TASK: <gorevi Turkce acikla>
RESPONSE: <1 cumle>

[2] PROJE MODU — proje baslatmak veya devam etmek:
PROJECT_MODE
RESPONSE: <1 cumle>

KURAL: Bilgi sorusu / sohbet → format yok, normal cevap ver.
"Proje", "yap", "gelistir", "kodla", "insa et" icerenleri PROJECT_MODE olarak isle.
Projelerden kullanici sormadikca bahsetme.

KISI VE NOT SORULARI:
Sana kayitli bilgi verildiginde:
- Sorulan soruya odaklan
- Kayitli olmayan bir seyi asla uydurma
- Analiz YAPMA, sadece kayitlari ozetle

NOT ANALIZI:
Kullanici metin analiz ettirmek isterse "Bunun icin run_analyze.py kullan" de.

PROFIL FARKINDALIK:
Kullanici bir sey yasadigini, hissettıgini, planladigini soyluyor ise hafizana kaydet.

Sohbet, soru veya bilgi talebi ise sadece normal Turkce cevap ver."""
