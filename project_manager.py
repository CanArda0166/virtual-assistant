"""
NOVA — Proje Geliştirme Motoru
===============================
Kullanıcı bir proje tarif eder. NOVA:
  1. Projeyi anlar, gerekirse soru sorar
  2. Tüm dosya mimarisini planlar
  3. Her dosyayı tam ve birbirine entegre yazar
  4. Kullanıcıya gösterir, onay alır
  5. Test eder — hata varsa sessizce okur/düzeltir
  6. README + nasıl çalıştırılır ile teslim eder

Aktif proje modunda normal sohbet tamamen izole çalışır.
"""

import os
import sys
import json
import re
import subprocess
import shutil
from datetime import datetime
from typing import Optional

import logger
from config import PROJECTS_DIR, OWNER_NAME
from memory import safe_generate

YELLOW  = "\033[33m"
GREEN   = "\033[92m"
RED     = "\033[91m"
CYAN    = "\033[96m"
BLUE    = "\033[94m"
RESET   = "\033[0m"
BOLD    = "\033[1m"
GRAY    = "\033[90m"

os.makedirs(PROJECTS_DIR, exist_ok=True)

MAX_FIX_ITERATIONS = 12   # Otomatik düzeltme denemesi

# ═══════════════════════════════════════════════════════════════════
# OTURUM DURUMU
# ═══════════════════════════════════════════════════════════════════

_active_project: Optional[str] = None
_project_session: list = []          # Proje içi sohbet geçmişi

def get_active_project() -> Optional[str]:
    return _active_project

def get_active_branch() -> str:
    return "main"

def set_active_project(name: Optional[str]):
    global _active_project, _project_session
    _active_project = name
    _project_session = []

# ═══════════════════════════════════════════════════════════════════
# PROJE DOSYA YAPISI
# ═══════════════════════════════════════════════════════════════════

def _proj_dir(name: str) -> str:
    return os.path.join(PROJECTS_DIR, name)

def _meta_path(name: str) -> str:
    return os.path.join(_proj_dir(name), ".nova_meta.json")

def _src_dir(name: str) -> str:
    path = os.path.join(_proj_dir(name), "src")
    os.makedirs(path, exist_ok=True)
    return path

def list_projects() -> list:
    if not os.path.exists(PROJECTS_DIR):
        return []
    return [d for d in os.listdir(PROJECTS_DIR)
            if os.path.isdir(os.path.join(PROJECTS_DIR, d))
            and not d.startswith(".")]

def load_meta(name: str) -> dict:
    p = _meta_path(name)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_meta(name: str, data: dict):
    os.makedirs(_proj_dir(name), exist_ok=True)
    data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(_meta_path(name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ═══════════════════════════════════════════════════════════════════
# ADIM 1: PROJE ANLAMA VE PLANLAMA
# ═══════════════════════════════════════════════════════════════════

CLARIFY_PROMPT = """Sen bir yazılım mimarısın. Kullanıcının proje fikrini anlıyorsun.
Projeyi doğru inşa etmek için neyi bilmen gerekiyor?

Eğer fikir yeterliyse:
{"ready": true, "questions": []}

Eğer daha fazla bilgi gerekiyorsa (en fazla 3 soru):
{"ready": false, "questions": ["Soru 1?", "Soru 2?"]}

Şunlar için soru sor:
- Platform/hedef kitle (masaüstü mü, web mi, mobil mi?)
- Veri kaynağı (API kullanacak mı, lokal mi?)
- UI tipi (terminal, GUI, web arayüzü?)
- Kritik özellikler (hangisi olmazsa olmaz?)

Şunlar için soru sorma:
- Kodun nasıl yazılacağı
- Hangi dosyaların oluşturulacağı
- Teknik implementasyon detayları

Sadece JSON döndür."""

ARCHITECT_PROMPT = """Sen bir yazılım mimarısın. Kullanıcının detaylı projesini analiz edip
tam bir dosya planı çıkaracaksın.

Yanıtını SADECE şu JSON formatında ver, başka hiçbir şey yazma:
{
  "description": "projenin 1-2 cümle açıklaması",
  "goal": "bitti diyebileceğimiz durum",
  "stack": "Python, tkinter, requests vb.",
  "entry_point": "main.py",
  "needs_packages": ["paket1", "paket2"],
  "files": [
    {
      "name": "main.py",
      "role": "Ana giriş noktası, uygulamayı başlatır",
      "imports": ["config", "ui", "api"],
      "key_functions": ["main()", "setup()"]
    },
    {
      "name": "config.py",
      "role": "Tüm sabitler ve ayarlar",
      "imports": [],
      "key_functions": []
    }
  ],
  "run_instructions": "python main.py",
  "notes": "varsa önemli notlar"
}

KURALLAR:
- Dosyalar minimal ve amaç odaklı olsun
- Her dosyanın tek bir sorumluluğu olsun
- Fazla dosya oluşturma — gerekli olan kadar
- Sadece JSON, markdown yok, açıklama yok"""


CODEGEN_PROMPT = """Sen bir Python geliştiricisin. Sana bir proje mimarisi ve
yazman gereken dosyanın detayları verilecek.

KURALLAR:
1. SADECE çalışır Python kodu yaz. Markdown yok, açıklama blokları yok.
2. Diğer proje dosyalarını import ederken gerçek dosya adlarını kullan.
3. Harici paket gerekiyorsa: # REQUIRES: paket1, paket2  (ilk satır)
4. Kodun sonunda dosyanın ne yaptığını tek satır comment ile belirt.
5. Fonksiyonlar ve sınıflar docstring içermesin — sadece kod.
6. Windows 11 uyumlu ol.
7. Hata yönetimi ekle (try/except).
8. Dosya tam ve çalışır halde olsun — yarım bırakma."""


def _parse_json(raw: str) -> dict:
    """Gemini JSON yanıtını güvenli parse eder."""
    if not raw:
        return {}
    try:
        raw = raw.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw.strip())
        if isinstance(parsed, list) and parsed:
            parsed = parsed[0]
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def gather_requirements(name: str, description: str) -> str:
    """
    Projeyi anlamak için kullanıcıya soru sorar.
    Tüm cevapları toplar, zenginleştirilmiş açıklama döner.
    """
    # Soru gerekli mi kontrol et
    check = _parse_json(safe_generate(
        f"Proje: {name}\nFikir: {description}",
        system_instruction=CLARIFY_PROMPT
    ))

    if check.get("ready", True) or not check.get("questions"):
        return description  # Yeterli bilgi var, direkt devam

    questions = check["questions"][:3]
    print(f"\n{CYAN}{BOLD}  NOVA soru soruyor:{RESET}")

    answers = []
    for i, q in enumerate(questions, 1):
        print(f"\n  {YELLOW}{i}. {q}{RESET}")
        ans = input(f"  {CYAN}Sen: {RESET}").strip()
        if ans:
            answers.append(f"S: {q}\nC: {ans}")

    if answers:
        return description + "\n\nEk bilgiler:\n" + "\n".join(answers)
    return description


def plan_project(name: str, description: str) -> dict:
    """Zenginleştirilmiş açıklamadan dosya planı çıkarır."""
    raw = safe_generate(
        f"Proje adı: {name}\nDetaylı açıklama: {description}",
        system_instruction=ARCHITECT_PROMPT
    )
    result = _parse_json(raw)
    if not result:
        logger.error("Proje", "Plan oluşturulamadı")
    return result


# ═══════════════════════════════════════════════════════════════════
# ADIM 2: KOD ÜRETME
# ═══════════════════════════════════════════════════════════════════

def generate_file(file_info: dict, all_files: list, project_plan: dict) -> str:
    """Tek bir dosyanın tam kodunu üretir."""

    other_files = [f for f in all_files if f["name"] != file_info["name"]]
    other_desc  = "\n".join(
        f"  - {f['name']}: {f['role']}" for f in other_files
    )

    prompt = f"""Proje: {project_plan.get('description', '')}
Stack: {project_plan.get('stack', '')}

Diğer proje dosyaları (bunlarla entegre çalışacak):
{other_desc}

Şimdi yaz: {file_info['name']}
Rolü: {file_info['role']}
Import edilecekler: {', '.join(file_info.get('imports', [])) or 'yok'}
Ana fonksiyonlar: {', '.join(file_info.get('key_functions', [])) or 'serbest'}

Bu dosyanın tam ve çalışır Python kodunu yaz."""

    code = safe_generate(prompt, system_instruction=CODEGEN_PROMPT)
    if not code:
        return ""

    # Markdown temizle
    code = code.strip()
    if "```python" in code:
        code = code.split("```python")[1].split("```")[0].strip()
    elif "```" in code:
        code = code.split("```")[1].split("```")[0].strip()

    return code


# ═══════════════════════════════════════════════════════════════════
# ADIM 3: ONAY EKRANI
# ═══════════════════════════════════════════════════════════════════

def show_project_summary(name: str, plan: dict, files: dict) -> bool:
    """Tüm dosyaları göster, onay al."""
    print(f"\n{'═'*65}")
    print(f"{BOLD}{CYAN}  PROJE: {name.upper()}{RESET}")
    print(f"{'─'*65}")
    print(f"  {GRAY}Açıklama :{RESET} {plan.get('description','')}")
    print(f"  {GRAY}Stack    :{RESET} {plan.get('stack','')}")
    print(f"  {GRAY}Çalıştır :{RESET} {CYAN}python {plan.get('entry_point','main.py')}{RESET}")

    pkgs = plan.get("needs_packages", [])
    if pkgs:
        print(f"  {GRAY}Paketler :{RESET} {', '.join(pkgs)}")

    print(f"\n  {BOLD}Dosyalar ({len(files)}):{RESET}")
    for fname, code in files.items():
        lines = code.count("\n") + 1
        finfo = next((f for f in plan["files"] if f["name"] == fname), {})
        print(f"\n  {GREEN}▸ {fname}{RESET}  {GRAY}({lines} satır — {finfo.get('role','')}){RESET}")
        # İlk 8 satırı önizle
        preview = "\n".join(code.split("\n")[:8])
        for line in preview.split("\n"):
            print(f"    {GRAY}{line}{RESET}")
        if lines > 8:
            print(f"    {GRAY}... ({lines-8} satır daha){RESET}")

    print(f"\n{'─'*65}")
    ans = input(f"  {YELLOW}Dosyaları kaydet ve test et? (e/h): {RESET}").strip().lower()
    return ans in ("e", "evet", "y", "yes", "")


# ═══════════════════════════════════════════════════════════════════
# ADIM 4: YAZMA, TEST, OTO-DÜZELTME
# ═══════════════════════════════════════════════════════════════════

def _install_pkg(pkg: str) -> bool:
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg, "--quiet"],
            capture_output=True, text=True, timeout=60
        )
        if r.returncode == 0:
            print(f"{GREEN}  [pip] {pkg} kuruldu{RESET}")
            return True
        return False
    except Exception:
        return False


def _extract_pkgs(code: str) -> list:
    for line in code.split("\n")[:3]:
        if line.strip().startswith("# REQUIRES:"):
            return [p.strip() for p in line.split(":", 1)[1].split(",") if p.strip()]
    return []


def _run_project(proj_dir: str, entry: str) -> tuple:
    """Projenin entry point'ini çalıştırır."""
    entry_path = os.path.join(proj_dir, entry)
    if not os.path.exists(entry_path):
        # src/ içinde ara
        src_entry = os.path.join(proj_dir, "src", entry)
        if os.path.exists(src_entry):
            entry_path = src_entry
        else:
            return False, f"Giriş dosyası bulunamadı: {entry}"

    try:
        r = subprocess.run(
            [sys.executable, entry_path],
            capture_output=True, text=True,
            timeout=15,
            cwd=proj_dir
        )
        # GUI uygulamaları timeout ile biter ama çalışmış sayılır
        if r.returncode == 0 or "mainloop" in open(entry_path, encoding="utf-8").read():
            return True, r.stdout.strip() or "Çalıştı."
        return False, r.stderr.strip() or "Bilinmeyen hata."
    except subprocess.TimeoutExpired:
        # Timeout = GUI açıldı demek, başarı sayılır
        return True, "Uygulama başlatıldı (GUI)."
    except Exception as e:
        return False, str(e)


FIX_PROMPT = """Sen bir Python debug uzmanısın.
Hata mesajını, ilgili dosyayı ve diğer dosyaları veriyorum.

ADIMLAR:
1. Hatanın tam nedenini belirle (satır numarası, değişken, import hatası vs.)
2. Sadece o hatayı düzelt — fazladan değiştirme yapma
3. Diğer dosyalarla import uyumunu koru
4. TAM dosya kodunu ver — markdown yok, açıklama yok

Düzeltilmiş Python kodu:"""


def _diagnose_error(error: str, all_contents: dict) -> str:
    """Hatayı analiz edip hangi dosyanın sorumlu olduğunu tespit eder."""
    # Traceback'ten dosya adını çek
    for line in error.split("\n"):
        if "File " in line and ".py" in line:
            m = re.search(r'File ".*?([^/\\]+\.py)"', line)
            if m:
                fname = m.group(1)
                if fname in all_contents:
                    return fname

    # Dosya adı traceback'te yoksa hata tipine bak
    if "ImportError" in error or "ModuleNotFoundError" in error:
        m = re.search(r"from (\w+) import|import (\w+)", error)
        if m:
            mod = (m.group(1) or m.group(2)).strip()
            for fname in all_contents:
                if mod in fname:
                    return fname

    # NameError veya AttributeError — hangi dosyada o isim var?
    m = re.search(r"name '(\w+)'|attribute '(\w+)'", error)
    if m:
        symbol = (m.group(1) or m.group(2))
        for fname, code in all_contents.items():
            if f"def {symbol}" in code or f"class {symbol}" in code:
                return fname

    return None


def _fix_file(error: str, all_file_contents: dict, hint_file: str = None) -> tuple:
    """
    Hatalı dosyayı tespit eder, AI ile düzeltir.
    Returns: (dosya_adı, düzeltilmiş_kod)
    """
    # Hangi dosya hatalı?
    faulty = _diagnose_error(error, all_file_contents)
    if not faulty:
        faulty = hint_file or list(all_file_contents.keys())[0]

    current_code = all_file_contents.get(faulty, "")

    # Diğer dosyaların tam içeriğini ver — entegrasyon için kritik
    context = ""
    for fn, code in all_file_contents.items():
        if fn != faulty:
            context += f"\n===== {fn} =====\n{code}\n"

    prompt = f"""HATA:
{error}

HATAYI IÇEREN DOSYA ({faulty}):
{current_code}

DIĞER PROJE DOSYALARI (import/entegrasyon için):
{context}

{faulty} dosyasını düzelt. Tam Python kodu:"""

    fixed = safe_generate(prompt, system_instruction=FIX_PROMPT)
    if not fixed:
        return faulty, current_code

    fixed = fixed.strip()
    for marker in ["```python", "```"]:
        if marker in fixed:
            fixed = fixed.split(marker)[1].split("```")[0].strip()
            break

    return faulty, fixed


PKG_MAP = {
    "PIL": "Pillow", "cv2": "opencv-python",
    "bs4": "beautifulsoup4", "sklearn": "scikit-learn",
    "dotenv": "python-dotenv", "yaml": "pyyaml",
    "wx": "wxPython", "serial": "pyserial",
    "gi": "PyGObject", "Crypto": "pycryptodome",
}

def _read_all_files(proj_dir: str, file_names: list) -> dict:
    """Projedeki tüm dosyaları okur."""
    contents = {}
    for fname in file_names:
        fpath = os.path.join(proj_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                contents[fname] = f.read()
    return contents


def write_and_test(name: str, plan: dict, files: dict) -> tuple:
    """
    1. Paketleri kur
    2. Dosyaları yaz
    3. Test et → hata varsa akıllıca teşhis et + düzelt
    4. MAX_FIX_ITERATIONS kez dene
    """
    proj_dir = _proj_dir(name)
    os.makedirs(proj_dir, exist_ok=True)

    # Paket kurulumu
    all_pkgs = set(plan.get("needs_packages", []))
    for code in files.values():
        all_pkgs.update(_extract_pkgs(code))
    installed = set()
    for pkg in all_pkgs:
        if _install_pkg(pkg):
            installed.add(pkg)

    # Dosyaları yaz
    print(f"\n{YELLOW}  Dosyalar yazılıyor...{RESET}")
    for fname, code in files.items():
        fpath = os.path.join(proj_dir, fname)
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(code)
        print(f"  {GREEN}✓{RESET} {fname}")

    entry      = plan.get("entry_point", "main.py")
    last_error = ""
    last_fixed = ""   # Sonsuz döngüyü önle — aynı fix tekrarlanmasın

    for attempt in range(1, MAX_FIX_ITERATIONS + 1):
        print(f"\n{YELLOW}  [{attempt}/{MAX_FIX_ITERATIONS}] Test ediliyor...{RESET}", end=" ", flush=True)
        ok, output = _run_project(proj_dir, entry)

        if ok:
            print(f"{GREEN}✓ Çalışıyor!{RESET}")
            return True, output

        print(f"{RED}✗{RESET}")
        print(f"  {RED}Hata:{RESET} {output[:150]}")
        logger.error("Proje", f"Test {attempt}", extra=output[:400])
        last_error = output

        # ── ImportError → önce paketi kur ──────────────────────
        m = re.search(r"No module named \'([^\']+)\'", output)
        if m:
            mod = m.group(1).split(".")[0]
            pkg = PKG_MAP.get(mod, mod)
            if pkg not in installed:
                print(f"  {YELLOW}Paket kuruluyor: {pkg}...{RESET}")
                if _install_pkg(pkg):
                    installed.add(pkg)
                    continue  # Paketi kurup hemen tekrar dene, kod değişmeden

        # ── Mevcut dosyaları oku ───────────────────────────────
        current = _read_all_files(proj_dir, list(files.keys()))

        # ── Teşhis ve düzeltme ────────────────────────────────
        faulty_fname, new_code = _fix_file(output, current)

        # Aynı düzeltme tekrarlanıyorsa farklı dosyayı dene
        fix_sig = f"{faulty_fname}:{hash(new_code)}"
        if fix_sig == last_fixed:
            # Farklı dosyayı düzeltmeyi dene
            other_files = [f for f in current if f != faulty_fname]
            if other_files:
                alt_faulty = other_files[0]
                print(f"  {YELLOW}Alternatif düzeltme: {alt_faulty}...{RESET}")
                alt_faulty, new_code = _fix_file(output, current, hint_file=alt_faulty)
                faulty_fname = alt_faulty
                fix_sig = f"{faulty_fname}:{hash(new_code)}"

        last_fixed = fix_sig
        print(f"  {YELLOW}Düzeltiliyor: {faulty_fname}...{RESET}")

        # Yaz
        fpath = os.path.join(proj_dir, faulty_fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(new_code)
        files[faulty_fname] = new_code

        # Yeni paket gerektiriyor mu?
        for pkg in _extract_pkgs(new_code):
            if pkg not in installed:
                if _install_pkg(pkg):
                    installed.add(pkg)

    return False, f"{MAX_FIX_ITERATIONS} denemede çalışır hale getirilemedi.\nSon hata: {last_error[:300]}"


# ═══════════════════════════════════════════════════════════════════
# ADIM 5: README YAZMA
# ═══════════════════════════════════════════════════════════════════

README_PROMPT = """Bir projenin README.md dosyasını yaz.
Türkçe, kısa ve net. Markdown kullan.
Bölümler: # Proje Adı, ## Ne Yapar, ## Kurulum, ## Kullanım
Fazla açıklama yapma, direkt ve kullanışlı ol."""

def write_readme(name: str, plan: dict, files: dict):
    file_list = "\n".join(f"- `{fn}`: {next((f['role'] for f in plan['files'] if f['name']==fn), '')} "
                          for fn in files)
    prompt = f"""Proje: {name}
Açıklama: {plan.get('description','')}
Stack: {plan.get('stack','')}
Dosyalar:
{file_list}
Çalıştırma: {plan.get('run_instructions', f'python {plan.get("entry_point","main.py")}')}
Notlar: {plan.get('notes','')}"""

    readme = safe_generate(prompt, system_instruction=README_PROMPT)
    if not readme:
        readme = f"# {name}\n\n{plan.get('description','')}\n\n## Kullanım\n```\n{plan.get('run_instructions','python main.py')}\n```\n"

    path = os.path.join(_proj_dir(name), "README.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(readme)


# ═══════════════════════════════════════════════════════════════════
# ANA PROJE OLUŞTURMA FONKSİYONU
# ═══════════════════════════════════════════════════════════════════

def create_project(name: str, description: str) -> tuple:
    """
    Tam proje oluşturma akışı.
    Returns: (başarı, mesaj)
    """
    if os.path.exists(_proj_dir(name)):
        return False, f"'{name}' adında zaten bir proje var."

    print(f"\n{CYAN}{BOLD}  NOVA: '{name}' projesini anlıyorum...{RESET}")

    # 1. Gereksinim toplama — eksik bilgi varsa soru sor
    description = gather_requirements(name, description)

    # 2. Plan oluştur
    print(f"\n{YELLOW}  Mimari planlanıyor...{RESET}")
    plan = plan_project(name, description)
    if not plan:
        return False, "Proje planlanamadı, tekrar dene."

    # 2. Tüm dosyaları üret
    print(f"  {YELLOW}Dosyalar üretiliyor ({len(plan.get('files',[]))} dosya)...{RESET}")
    files = {}
    for file_info in plan.get("files", []):
        fname = file_info["name"]
        print(f"    {GRAY}► {fname}...{RESET}", end="", flush=True)
        code = generate_file(file_info, plan["files"], plan)
        if code:
            files[fname] = code
            print(f" {GREEN}✓{RESET}")
        else:
            print(f" {RED}✗ (atlandı){RESET}")

    if not files:
        return False, "Dosyalar üretilemedi."

    # 3. Kullanıcıya göster ve onay al
    if not show_project_summary(name, plan, files):
        return False, "İptal edildi."

    # 4. Yaz ve test et
    ok, msg = write_and_test(name, plan, files)

    # 5. README yaz
    write_readme(name, plan, files)

    # 6. Meta kaydet
    save_meta(name, {
        "name":        name,
        "description": plan.get("description", description),
        "created_at":  datetime.now().strftime("%Y-%m-%d %H:%M"),
        "stack":       plan.get("stack", ""),
        "entry_point": plan.get("entry_point", "main.py"),
        "run":         plan.get("run_instructions", "python main.py"),
        "files":       list(files.keys()),
        "status":      "ok" if ok else "error"
    })

    # 7. Sonuç
    proj_dir = _proj_dir(name)
    if ok:
        print(f"\n{GREEN}{BOLD}  ✓ Proje hazır!{RESET}")
        print(f"  {GRAY}Konum  :{RESET} {proj_dir}")
        print(f"  {GRAY}Çalıştır:{RESET} {CYAN}cd \"{proj_dir}\" && python {plan.get('entry_point','main.py')}{RESET}\n")
        return True, f"'{name}' projesi tamamlandı. {len(files)} dosya yazıldı."
    else:
        print(f"\n{YELLOW}{BOLD}  ⚠ Proje yazıldı ama test başarısız oldu.{RESET}")
        print(f"  {GRAY}Konum: {proj_dir}{RESET}\n")
        return False, f"Proje yazıldı ama çalışmadı: {msg}"


# ═══════════════════════════════════════════════════════════════════
# PROJE AKTİFLEŞTİRME / DEVRE DIŞI BIRAKMA
# ═══════════════════════════════════════════════════════════════════

def activate_project(name: str) -> tuple:
    projects = list_projects()
    match    = None

    if name in projects:
        match = name
    else:
        nn = name.lower().replace(" ", "_").replace("-", "_")
        for p in projects:
            if nn in p.lower() or p.lower() in nn:
                match = p
                break

    if not match:
        return False, f"'{name}' bulunamadı. Projeler: {', '.join(projects) or 'yok'}"

    set_active_project(match)
    meta  = load_meta(match)
    desc  = meta.get("description", "")
    run   = meta.get("run", f"python {meta.get('entry_point','main.py')}")
    files = meta.get("files", [])
    msg   = f"'{match}' aktif. {len(files)} dosya. Çalıştır: {run}"
    logger.info("Proje", f"Aktif: {match}")
    return True, msg


def deactivate_project() -> str:
    name = _active_project
    if not name:
        return "Aktif proje yok."
    set_active_project(None)
    logger.info("Proje", f"Kapatıldı: {name}")
    return f"'{name}' projesi kapatıldı, eski NOVA'ya dönüldü."


# ═══════════════════════════════════════════════════════════════════
# PROJE MODUNDA KONUŞMA — TAM İZOLASYON
# ═══════════════════════════════════════════════════════════════════

PROJECT_MODE_PROMPT = """Sen NOVA'nın proje modundasın.
YALNIZCA aktif projeyle ilgileniyorsun.
Normal sohbet geçmişi, profil, diğer projeler TAMAMEN YOK.
Projenin vizyonuna ve koduna odaklan.

KOMUTLAR (ilk satırda tam olarak yaz):
TASK: <projeye yeni özellik/değişiklik ekle>
RUN                  → projeyi çalıştır
STATUS               → proje bilgisi göster
CLOSE                → projeyi kapat, eski NOVA'ya dön
EDIT: <dosya_adı>    → dosyayı değiştir

Proje dışı sorulara: "Bunu proje dışında konuşalım." de.
Kısa ve net konuş."""


_DEVAM_KEYS  = {"devam et","devam edelim","ilerle","baslat","basla","haydi","calistir","next","devam"}
_KAPAT_KEYS  = {"kapat","durdur","askiya al","eski nova","geri don","projeyi kapat","cikis","bitir"}
_RUN_KEYS    = {"calistir","ac","run","test et","dene"}
_STATUS_KEYS = {"durum","ne kaldi","status","bilgi","nerede"}


def project_think(user_input: str) -> tuple:
    """
    Proje modunda kullanıcı girdisini işler.
    Returns: (yanıt, komut, veri)
    Komutlar: TASK | RUN | EDIT | CLOSE | STATUS | None
    """
    global _project_session
    name = _active_project
    low  = user_input.strip().lower()

    # ── Kısayollar (Gemini'ye sormadan) ──────────────────────────
    if low in _KAPAT_KEYS or any(k in low for k in _KAPAT_KEYS):
        return deactivate_project(), "CLOSE", None

    if low in _RUN_KEYS or any(k in low for k in _RUN_KEYS):
        return "Çalıştırıyorum...", "RUN", None

    if low in _STATUS_KEYS or any(k in low for k in _STATUS_KEYS):
        meta  = load_meta(name)
        files = meta.get("files", [])
        run   = meta.get("run", "")
        msg   = (f"{name}: {meta.get('description','')}\n"
                 f"Dosyalar: {', '.join(files)}\n"
                 f"Çalıştır: {run}")
        return msg, "STATUS", None

    # ── Gemini'ye sor ────────────────────────────────────────────
    meta    = load_meta(name)
    ctx     = (f"Proje: {name}\n"
               f"Açıklama: {meta.get('description','')}\n"
               f"Dosyalar: {', '.join(meta.get('files',[]))}\n"
               f"Çalıştır: {meta.get('run','')}")

    system   = PROJECT_MODE_PROMPT + f"\n\nAKTİF PROJE:\n{ctx}"
    from memory import chat_generate
    response = chat_generate(_project_session, user_input, system_instruction=system)
    if not response:
        return "Anlayamadım.", None, None

    _project_session.append({"role": "user",  "parts": [{"text": user_input}]})
    _project_session.append({"role": "model", "parts": [{"text": response}]})
    if len(_project_session) > 20:
        _project_session = _project_session[-20:]

    first = response.strip().split("\n")[0].strip()
    rest  = "\n".join(response.strip().split("\n")[1:]).strip()

    if first.startswith("TASK:"):
        data = first[5:].strip()
        return rest or f"Görev alındı: {data}", "TASK", data

    if first.startswith("EDIT:"):
        data = first[5:].strip()
        return rest or f"{data} düzenlenecek.", "EDIT", data

    if first == "CLOSE":
        return deactivate_project(), "CLOSE", None

    if first == "RUN":
        return "Çalıştırıyorum...", "RUN", None

    if first == "STATUS":
        meta  = load_meta(name)
        msg   = f"{name}: {', '.join(meta.get('files',[]))}"
        return msg, "STATUS", None

    return response, None, None


# ═══════════════════════════════════════════════════════════════════
# PROJE MODUNDA GÖREV/DÜZENLEME UYGULAMA
# ═══════════════════════════════════════════════════════════════════

def apply_project_task(task: str) -> tuple:
    """
    Aktif projeye yeni özellik/değişiklik ekler.
    Tüm dosyaları okur → neyi değiştireceğine karar verir →
    değiştirir → test eder → düzeltir.
    """
    name     = _active_project
    proj_dir = _proj_dir(name)
    meta     = load_meta(name)
    files    = meta.get("files", [])

    if not files:
        return False, "Proje dosyaları bulunamadı."

    # Mevcut dosyaları oku
    current = {}
    for fname in files:
        fpath = os.path.join(proj_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                current[fname] = f.read()

    file_overview = "\n".join(
        f"=== {fn} ===\n{code[:300]}..." for fn, code in current.items()
    )

    # Hangi dosyayı nasıl değiştireceğini planla
    plan_prompt = f"""Proje: {meta.get('description','')}
Mevcut dosyalar:
{file_overview}

Görev: {task}

Hangi dosyayı nasıl değiştirmek gerekiyor? JSON olarak:
{{"file": "dosya_adi.py", "change": "ne yapılacak 1 cümle"}}
Sadece JSON."""

    plan_raw = safe_generate(plan_prompt)
    change_plan = {"file": meta.get("entry_point", "main.py"), "change": task}
    try:
        if "```" in plan_raw:
            plan_raw = plan_raw.split("```")[1]
            if plan_raw.startswith("json"):
                plan_raw = plan_raw[4:]
        parsed = json.loads(plan_raw.strip())
        # Liste gelirse ilk elemanı al
        if isinstance(parsed, list) and parsed:
            parsed = parsed[0]
        if isinstance(parsed, dict):
            change_plan = parsed
    except Exception:
        pass

    target_file = change_plan.get("file", files[0] if files else "main.py")
    if target_file not in current:
        target_file = files[0]

    # Dosyayı değiştir
    modify_prompt = f"""Mevcut kod ({target_file}):
{current[target_file]}

Değişiklik: {task}

Tüm dosyayı değişiklikle birlikte yaz. Sadece Python kodu."""

    new_code = safe_generate(modify_prompt, system_instruction=CODEGEN_PROMPT)
    if not new_code:
        return False, "Kod üretilemedi."

    new_code = new_code.strip()
    if "```python" in new_code:
        new_code = new_code.split("```python")[1].split("```")[0].strip()
    elif "```" in new_code:
        new_code = new_code.split("```")[1].split("```")[0].strip()

    # Önce kullanıcıya göster
    print(f"\n{'─'*60}")
    print(f"{CYAN}► {target_file} değişikliği:{RESET}")
    print(new_code[:600] + ("..." if len(new_code) > 600 else ""))
    print(SEP2)
    ans = input(f"{YELLOW}Uygulayayım mı? (e/h): {RESET}").strip().lower()
    if ans not in ("e", "evet", "y", "yes", ""):
        return False, "İptal edildi."

    # Yaz
    fpath = os.path.join(proj_dir, target_file)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(new_code)
    current[target_file] = new_code

    # Test et
    entry = meta.get("entry_point", "main.py")
    for attempt in range(1, MAX_FIX_ITERATIONS + 1):
        ok, output = _run_project(proj_dir, entry)
        if ok:
            print(f"{GREEN}  ✓ Çalışıyor!{RESET}")
            return True, "Değişiklik uygulandı ve test edildi."

        print(f"{YELLOW}  Düzeltiliyor... (deneme {attempt}){RESET}")
        fixed = _fix_file(fpath, output, current)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(fixed)
        current[target_file] = fixed

    return False, "Değişiklik uygulandı ama test başarısız oldu."


def run_project() -> tuple:
    """Aktif projeyi çalıştırır."""
    name     = _active_project
    proj_dir = _proj_dir(name)
    meta     = load_meta(name)
    entry    = meta.get("entry_point", "main.py")
    ok, out  = _run_project(proj_dir, entry)
    return ok, out


# ═══════════════════════════════════════════════════════════════════
# İNTERAKTİF PROJE SEÇİM MENÜSÜ
# ═══════════════════════════════════════════════════════════════════

def interactive_project_select() -> tuple:
    """
    Proje moduna girildiğinde çalışır.
    Mevcut projeleri listeler, seçim veya yeni proje oluşturma sunar.
    Returns: (başarı, mesaj)
    """
    projects = list_projects()

    SEP1 = "═" * 60
    SEP2 = "─" * 60
    print(f"\n{SEP1}")
    print(f"{CYAN}{BOLD}  NOVA — PROJE MODU{RESET}")
    print(SEP2)

    if not projects:
        print(f"  {GRAY}Henuz hic proje yok.{RESET}")
        print(f"  {YELLOW}[1]{RESET} Yeni proje oluştur")
        print(f"  {YELLOW}[0]{RESET} Çıkış")
        print(SEP2)
        choice = input(f"  {CYAN}Seçim: {RESET}").strip()

        if choice == "1":
            return _new_project_flow()
        return False, "Proje modu kapatıldı."

    # Projeleri göster
    print(f"  {GRAY}Mevcut projeler:{RESET}")
    for i, name in enumerate(projects, 1):
        meta  = load_meta(name)
        desc  = meta.get("description", "")[:50]
        stack = meta.get("stack", "")
        status_icon = GREEN + "●" + RESET if meta.get("status") == "ok" else YELLOW + "◐" + RESET
        print(f"  {YELLOW}[{i}]{RESET} {status_icon} {BOLD}{name}{RESET}")
        if desc:
            print(f"       {GRAY}{desc}{RESET}")
        if stack:
            print(f"       {GRAY}Stack: {stack}{RESET}")
        print()

    print(f"  {YELLOW}[N]{RESET} Yeni proje oluştur")
    print(f"  {YELLOW}[0]{RESET} Çıkış")
    print(SEP2)
    choice = input(f"  {CYAN}Seçim (1-{len(projects)} veya N): {RESET}").strip().lower()

    if choice == "0":
        return False, "Proje modu kapatıldı."

    if choice in ("n", "yeni", "new"):
        return _new_project_flow()

    # Numara seçildiyse
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(projects):
            selected = projects[idx]
            ok, msg = activate_project(selected)
            if ok:
                meta  = load_meta(selected)
                files = meta.get("files", [])
                run   = meta.get("run", f"python {meta.get('entry_point','main.py')}")
                print(f"\n  {GREEN}✓ '{selected}' aktif{RESET}")
                print(f"  {GRAY}Dosyalar: {', '.join(files)}{RESET}")
                print(f"  {GRAY}Calistir: {run}{RESET}\n")
            return ok, msg
    except ValueError:
        pass

    # İsim ile arama
    matches = [p for p in projects if choice in p.lower()]
    if matches:
        ok, msg = activate_project(matches[0])
        return ok, msg

    return False, f"'{choice}' geçerli bir seçim değil."


def _new_project_flow() -> tuple:
    """Yeni proje oluşturma sihirbazı."""
    print(f"\n  {CYAN}{BOLD}Yeni Proje{RESET}")
    print(f"  {GRAY}Projenin adını gir (kısa, alt çizgi ile): {RESET}", end="")
    name = input().strip().replace(" ", "_")

    if not name:
        return False, "Proje adı boş olamaz."

    if name in list_projects():
        print(f"  {YELLOW}'{name}' zaten var. Onu açıyorum...{RESET}")
        return activate_project(name)

    print(f"  {GRAY}Ne yapmak istediğini anlat: {RESET}", end="")
    description = input().strip()

    if not description:
        return False, "Açıklama boş olamaz."

    ok, msg = create_project(name, description)
    if ok:
        activate_project(name)
    return ok, msg


# ═══════════════════════════════════════════════════════════════════
# İNTERAKTİF PROJE SEÇİM MENÜSÜ
# ═══════════════════════════════════════════════════════════════════

def interactive_project_select() -> tuple:
    """
    Proje moduna girerken kullanıcıya mevcut projeleri gösterir,
    seçmesini veya yeni proje oluşturmasını ister.
    Returns: (başarı, mesaj)
    """
    projects = list_projects()

    print(f"\n{'═'*55}")
    print(f"{BOLD}{CYAN}  PROJE MODU{RESET}")
    print(f"{'─'*55}")

    if projects:
        print(f"  {GRAY}Mevcut projeler:{RESET}")
        for i, p in enumerate(projects, 1):
            meta  = load_meta(p)
            desc  = meta.get("description", "")[:45]
            files = len(meta.get("files", []))
            print(f"  {CYAN}{i}.{RESET} {BOLD}{p}{RESET}  {GRAY}({files} dosya){RESET}")
            if desc:
                print(f"     {GRAY}{desc}{'...' if len(meta.get('description',''))>45 else ''}{RESET}")
        print()
        print(f"  {CYAN}y.{RESET} Yeni proje oluştur")
        print(f"  {CYAN}q.{RESET} İptal")
    else:
        print(f"  {GRAY}Henüz proje yok.{RESET}")
        print(f"  {CYAN}y.{RESET} Yeni proje oluştur")
        print(f"  {CYAN}q.{RESET} İptal")

    print(f"{'─'*55}")
    choice = input(f"  {YELLOW}Seçim: {RESET}").strip().lower()

    if choice in ("q", "iptal", ""):
        return False, "İptal edildi."

    if choice == "y":
        name = input(f"  {CYAN}Proje adı: {RESET}").strip()
        if not name:
            return False, "Proje adı boş olamaz."
        desc = input(f"  {CYAN}Ne yapmak istiyorsun: {RESET}").strip()
        if not desc:
            return False, "Açıklama boş olamaz."
        ok, msg = create_project(name, desc)
        if ok:
            activate_project(name)
        return ok, msg

    # Numara ile seçim
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(projects):
            return activate_project(projects[idx])
        return False, "Geçersiz numara."

    # İsimle kısmi eşleşme
    match = next((p for p in projects if choice in p.lower()), None)
    if match:
        return activate_project(match)

    return False, f"'{choice}' bulunamadı."
