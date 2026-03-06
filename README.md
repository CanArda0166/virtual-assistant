# NOVA — Kişisel Yapay Zeka Asistan

NOVA, Gemini API üzerine inşa edilmiş, Türkçe konuşan bir kişisel masaüstü asistanıdır. Sesli komutları anlayarak bilgisayarda görev çalıştırır, konuşmalardan hafıza oluşturur ve günlük yaşam bilgilerini takip eder.

---
> [!WARNING]
> Bu proje tamamen tek bir kişi (Can Arda Ceylan) tarafından kişisel kullanım için yapılmıştır. Lisans gereği dosyaların kopyalanması ve direkt kullanılması hak ihlali sayılır. Kodların paylaşım amacı diğer geliştiricilere ilham olmaktır. Lütfen geliştirici ile iletişime geçerek izin almadan dosyaları farklı platformlarda kullanıma ve paylaşıma sunmayınız.
---
## Özellikler

### Sesli Asistan
Mikrofon üzerinden sizi dinler, komutlarınızı Google Speech Recognition ile metne çevirir. Her cümle için konuşmanın size mi yoksa başka birine mi yönelik olduğunu otomatik algılar. Yanıtları Edge TTS ile seslendirir.

### Gemini AI Entegrasyonu
Birden fazla API anahtarı ve model destekler. Kota dolduğunda otomatik olarak sıradaki modele, oradan da sıradaki anahtara geçer. Desteklenen modeller: `gemini-2.0-flash`, `gemini-2.0-flash-lite`, `gemini-1.5-flash`, `gemini-1.5-flash-8b`, `gemini-1.5-pro`.

### Görev Yürütücü (Executor)
"Spotify'ı aç", "ekran görüntüsü al", "şu dosyayı oluştur" gibi tek seferlik bilgisayar görevlerini Python kodu yazarak çalıştırır. Kod Gemini tarafından üretilir, güvenlik kontrolünden geçirilir ve kullanıcı onayı alındıktan sonra çalıştırılır. Başarılı scriptler kaydedilir, benzer isteklerde tekrar kullanılır. Gerekli pip paketleri otomatik kurulur.

### Hafıza ve Profil Sistemi
Konuşmalardan otomatik olarak bilgi çıkarır: sınavlar, dersler, görevler, alışkanlıklar, hedefler, önemli kişiler. Günlük brifingde bu bilgileri kullanarak kişiselleştirilmiş bir özet sunar.

### Günlük Brifing
Her açılışta saate göre selamlama, hava durumu (wttr.in), yaklaşan sınavlar ve bekleyen görevlerin kısa özetini sesli olarak sunar.

### Karakter/Kişi Dosyaları
`characters/` klasörüne JSON formatında kişi dosyaları eklenebilir. Konuşmada o kişinin adı geçtiğinde dosya otomatik yüklenir ve bağlam olarak kullanılır.

### Metin Analizi
WhatsApp sohbet geçmişi, notlar ve CV gibi uzun metinleri analiz etmek için ayrı bir araç (`run_analyze.py`) bulunur. Parçalara bölerek işler, benzer cümleleri filtreler.

### Özellik Anahtarları
`config.py` içindeki `FEATURES` sözlüğünden her özellik tek satırla açılıp kapatılabilir.

---

## Durum: Tamamlanmamış Özellikler

> **⚠️ Proje Geliştirme Modu (`projects`) şu an devre dışıdır.**
>
> Kullanıcının verdiği konseptten çok dosyalı, birbirine entegre Python projeleri üretmeyi hedefleyen bu sistem henüz tamamlanmamıştır. `config.py` içinde `"projects": False` olarak işaretlenmiştir. Geliştirme devam etmektedir.

---

## Kurulum

### Gereksinimler

- Python 3.11+
- Windows 10/11 (STT ve TTS Windows'a özgüdür)
- Mikrofon

### Adımlar

```bash
git clone https://github.com/CanArda0166/virtual-assistant
cd nova
pip install -r requirements.txt
```

`config.py` dosyasını açın ve şu alanları doldurun:

```python
OWNER_NAME      = "Adınız"
OWNER_FULL_NAME = "Adınız Soyadınız"
GEMINI_API_KEYS = ["YOUR_GEMINI_API_KEY_1"]
WEATHER_CITY    = "Istanbul"
```

Gemini API anahtarı almak için: [https://aistudio.google.com](https://aistudio.google.com)

### Çalıştırma

```bash
python main.py
```

---

## Gerekli Paketler

```
google-generativeai
edge-tts
SpeechRecognition
pyaudio
pygame
```

Metin analizi için ek paket:
```
thefuzz
python-Levenshtein
```

---

## Dosya Yapısı

```
nova/
├── main.py              # Ana döngü, ses giriş/çıkış, düşünme motoru
├── config.py            # Tüm ayarlar ve özellik anahtarları
├── memory.py            # Gemini API, sohbet geçmişi, profil yönetimi
├── executor.py          # Bilgisayar görevi üretme ve çalıştırma
├── analyze.py           # Metin analiz motoru
├── logger.py            # Merkezi loglama
├── run_analyze.py       # Metin analizi komut satırı arayüzü
├── run_projects.py      # Proje görüntüleyici (geliştirme aşamasında)
├── project_manager.py   # Proje motoru (geliştirme aşamasında)
├── profile.json         # Kullanıcı profili (otomatik güncellenir)
├── memory.json          # Sohbet geçmişi
├── characters/          # Kişi/karakter JSON dosyaları
├── scripts/             # Kaydedilmiş executor scriptleri
└── logs/                # Günlük hata logları
```

---

## Özellik Anahtarları Referansı

| Anahtar | Varsayılan | Açıklama |
|---|---|---|
| `voice_input` | `True` | Mikrofon girişi. `False`: klavye modu |
| `voice_output` | `True` | TTS sesli çıkış. `False`: sadece terminal |
| `executor` | `True` | Bilgisayar görevi çalıştırma |
| `projects` | `False` | Çok dosyalı proje geliştirme (**tamamlanmadı**) |
| `analyze` | `True` | Metin analizi (run_analyze.py) |
| `memory_update` | `True` | Konuşmadan otomatik profil güncelleme |
| `daily_briefing` | `True` | Açılışta günlük özet |
| `character_query` | `True` | Kişi dosyası sorgulama |

---

## Lisans

MIT
