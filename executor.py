import os
import json
import subprocess
import sys
import re
from datetime import datetime

import logger
from config import OWNER_NAME, SCRIPTS_DIR, SCRIPTS_TEMP
from memory import safe_generate

INDEX_FILE  = os.path.join(SCRIPTS_DIR, "index.json")
MAX_RETRIES = 10

YELLOW = "\033[33m"
GREEN  = "\033[92m"
RESET  = "\033[0m"

os.makedirs(SCRIPTS_DIR, exist_ok=True)

CODE_SYSTEM_PROMPT = """Sen bir Windows 11 Python otomasyon uzmanisın.

TEMEL KURALLAR:
1. Sadece calisir Python kodu yaz — markdown, aciklama, yorum YOK.
2. Tum importlari kodun basina ekle.
3. Kod bittiginde print() ile kisa onay mesaji ver.
4. Harici kutüphane kullanacaksan kodun EN BASINA su formatla belirt:
   # REQUIRES: kutuphane_adi, diger_kutuphane
5. Mumkun olan en kisa ve en guvenilir yolu sec.

YONTEM ONCELIK SIRASI:
1. Windows yerlesik araclar: subprocess + PowerShell/cmd, os, winreg
2. Standart kutuphaneler: webbrowser, pathlib, shutil, ctypes
3. Windows COM nesneleri: win32com.client
4. Hafif kutuphaneler: requests, pyperclip
5. PyAutoGUI: SADECE baska hicbir yol yoksa

GOREV BAZLI YONTEMLER:
- Spotify/muzik ac → subprocess ile exe veya webbrowser ile spotify: URI
- Uygulama ac → subprocess.Popen() veya os.startfile()
- Dosya islemleri → pathlib, shutil, os
- Web'de bir sey ac → webbrowser.open()
- Ekran goruntusu → pyautogui.screenshot() veya PIL
- Bildirim → win10toast veya plyer
- E-posta → win32com.client ile Outlook veya smtplib
- Sistem bilgisi → psutil, platform, os

HATA ONLEME:
- time.sleep() kullan ama makul tut (max 3 sn)
- try/except ekle kritik islemlere
- Dosya yollarini os.path.expanduser() ile genislet
- Windows yollarinda raw string veya double backslash kullan"""

MODULE_TO_PACKAGE = {
    "PIL": "Pillow", "cv2": "opencv-python", "sklearn": "scikit-learn",
    "bs4": "beautifulsoup4", "pywhatkit": "pywhatkit", "pyautogui": "pyautogui",
    "pyperclip": "pyperclip", "win32com": "pywin32", "win32api": "pywin32",
    "win32gui": "pywin32", "pynput": "pynput", "psutil": "psutil",
    "requests": "requests", "playsound": "playsound", "plyer": "plyer",
    "win10toast": "win10toast", "pyttsx3": "pyttsx3",
    "pandas": "pandas", "numpy": "numpy",
}

def extract_required_packages(code: str) -> list:
    for line in code.split("\n")[:10]:
        if line.strip().startswith("# REQUIRES:"):
            raw = line.split(":", 1)[1].strip()
            return [p.strip() for p in raw.split(",") if p.strip()]
    return []

def extract_package_from_error(error: str) -> str | None:
    patterns = [
        r"No module named '([^']+)'",
        r"ModuleNotFoundError: No module named '([^']+)'",
        r"cannot import name .+ from '([^']+)'",
    ]
    for pattern in patterns:
        match = re.search(pattern, error)
        if match:
            module = match.group(1).split(".")[0]
            return MODULE_TO_PACKAGE.get(module, module)
    return None

def install_package(package: str) -> bool:
    logger.info("PIP", f"Yukleniyor: {package}")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package, "--quiet"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            logger.success("PIP", f"{package} yuklendi")
            return True
        logger.error("PIP", f"{package} yuklenemedi", extra=result.stderr[:200])
        return False
    except subprocess.TimeoutExpired:
        logger.error("PIP", f"{package} zaman asimi")
        return False
    except Exception as e:
        logger.error("PIP", f"{package} hata", e)
        return False

def install_required_packages(code: str) -> bool:
    packages = extract_required_packages(code)
    if not packages:
        return True
    for pkg in packages:
        if not install_package(pkg):
            return False
    return True

def load_index() -> dict:
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_index(index: dict):
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=4)

def task_key(task: str) -> str:
    clean = "".join(c if c.isalnum() or c == " " else "" for c in task.lower())
    return "_".join(clean.strip().split()[:5])

def find_similar_script(task: str) -> str | None:
    index = load_index()
    if not index:
        return None
    key = task_key(task)
    if key in index:
        path = index[key]["file"]
        if os.path.exists(path):
            logger.info("Script", f"Kayitli: {path}")
            return path
    saved_tasks = [{"key": k, "description": v["description"]} for k, v in index.items()]
    if not saved_tasks:
        return None
    prompt = (
        f"Yeni gorev: '{task}'\n\n"
        f"Kayitli gorevler:\n{json.dumps(saved_tasks, ensure_ascii=False, indent=2)}\n\n"
        "TAMAMEN ayni isi yapan bir gorev var mi? Varsa 'key' degerini yaz, yoksa NO_MATCH yaz."
    )
    answer = safe_generate(prompt).strip()
    if answer and answer != "NO_MATCH" and answer in index:
        path = index[answer]["file"]
        if os.path.exists(path):
            logger.info("Script", f"Benzer: {path}")
            return path
    return None

def save_script(task: str, code: str) -> str:
    key      = task_key(task)
    filename = f"{key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
    filepath = os.path.join(SCRIPTS_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(code)
    index      = load_index()
    index[key] = {"description": task, "file": filepath,
                  "created": datetime.now().strftime("%Y-%m-%d %H:%M"), "success": True}
    save_index(index)
    logger.success("Script", f"Kaydedildi: {filepath}")
    return filepath

def generate_code(task: str, previous_code: str = "", error: str = "") -> str:
    if previous_code and error:
        prompt = (
            f"Bu Python kodu hata verdi. Duzelt:\n\n"
            f"GOREV: {task}\n\n"
            f"KOD:\n{previous_code}\n\n"
            f"HATA:\n{error}\n\n"
            "Onemli: Harici kutuphane gerekiyorsa kodun basina # REQUIRES: paket_adi ekle.\n"
            "Sadece duzeltilmis kodu yaz."
        )
    else:
        prompt = (
            f"Windows 11'de su gorevi yapan Python kodu yaz:\n{task}\n\n"
            "Onemli: Harici kutuphane gerekiyorsa kodun basina # REQUIRES: paket_adi ekle.\n"
            "Sadece kodu yaz."
        )
    code = safe_generate(prompt, system_instruction=CODE_SYSTEM_PROMPT)
    if not code:
        return ""
    if "```python" in code:
        code = code.split("```python")[1].split("```")[0].strip()
    elif "```" in code:
        code = code.split("```")[1].split("```")[0].strip()
    return code

def cloud_validate(task: str, code: str) -> tuple:
    prompt = (
        f"Python kodu Windows 11'de su gorevi yapacak: {task}\n\n"
        f"KOD:\n{code}\n\n"
        "Kontrol et:\n"
        "1. Sistem dosyalarina zarar verir mi?\n"
        "2. Veri kaybi?\n"
        "3. Gorevi dogru ve verimli yapiyor mu?\n"
        "4. Syntax veya runtime hatasi var mi?\n\n"
        "GUVENLI ve DOGRU ise sadece yaz: ONAYLANDI\n"
        "Sorun varsa duzeltilmis kodu yaz."
    )
    result = safe_generate(prompt)
    if not result or result.strip() == "ONAYLANDI":
        return True, code
    if "```python" in result:
        result = result.split("```python")[1].split("```")[0].strip()
    elif "```" in result:
        result = result.split("```")[1].split("```")[0].strip()
    return False, result

def run_code(code: str) -> tuple:
    temp_file = os.path.join(SCRIPTS_DIR, SCRIPTS_TEMP)
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        result = subprocess.run(
            [sys.executable, temp_file],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return True, result.stdout.strip() or "Basariyla calisti."
        return False, result.stderr.strip() or "Bilinmeyen hata."
    except subprocess.TimeoutExpired:
        return False, "Zaman asimi: 30 saniyede tamamlanamadi."
    except Exception as e:
        return False, str(e)
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

def run_saved_script(script_path: str) -> tuple:
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return True, result.stdout.strip() or "Basariyla calisti."
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "Zaman asimi."
    except Exception as e:
        return False, str(e)

def _user_confirm(code: str, summary: str) -> bool:
    print(f"\n{'═'*60}")
    print(f"{YELLOW}OZET: {summary}{RESET}")
    print(f"{'─'*60}")
    print(code)
    print(f"{'═'*60}")
    answer = input(f"{YELLOW}Kodu calistirayayim mi? (e/h): {RESET}").strip().lower()
    return answer in ("e", "evet", "y", "yes", "")

def execute_task(task: str) -> tuple:
    logger.info("Executor", f"Gorev: {task}")

    saved = find_similar_script(task)
    if saved:
        logger.info("Executor", "Kayitli script bulundu")
        with open(saved, "r", encoding="utf-8") as f:
            saved_code = f.read()
        summary = safe_generate(
            f"Bu Python kodunun ne yaptigini 1-2 cumleyle Turkce ozetle:\n{saved_code[:500]}"
        ) or "Daha once kaydedilmis script."
        if _user_confirm(saved_code, summary):
            ok, out = run_saved_script(saved)
            if ok:
                logger.success("Executor", "Basarili")
                return True, "Gorev tamamlandi."
            logger.warn("Executor", "Kayitli script hata verdi")
        else:
            return False, "Iptal edildi."

    current_code  = ""
    last_error    = ""
    installed     = set()
    user_approved = False

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info("Executor", f"Deneme {attempt}/{MAX_RETRIES}")
        current_code = generate_code(task, current_code, last_error)
        if not current_code:
            logger.error("Executor", "Kod uretilemedi")
            continue

        required = extract_required_packages(current_code)
        for pkg in required:
            if pkg not in installed:
                install_package(pkg)
                installed.add(pkg)

        for review in range(5):
            approved, current_code = cloud_validate(task, current_code)
            if approved:
                break

        if not user_approved:
            summary = safe_generate(
                f"Bu Python kodunun ne yaptigini 1-2 cumleyle Turkce ozetle:\n{current_code[:500]}"
            ) or "Gorev icin hazirlanan kod."
            if not _user_confirm(current_code, summary):
                return False, "Iptal edildi."
            user_approved = True

        success, output = run_code(current_code)
        if success:
            logger.success("Executor", f"Basarili deneme {attempt}")
            logger.log_raw("Executor", "Cikti", output)
            save_script(task, current_code)
            return True, "Gorev tamamlandi."

        last_error = output
        logger.error("Executor", f"Hata deneme {attempt}", extra=last_error[:300])

        missing_pkg = extract_package_from_error(last_error)
        if missing_pkg and missing_pkg not in installed:
            if install_package(missing_pkg):
                installed.add(missing_pkg)
                success, output = run_code(current_code)
                if success:
                    print(f"{GREEN}[Paket yuklendikten sonra basarili!]{RESET}")
                    save_script(task, current_code)
                    return True, "Gorev tamamlandi."
                last_error = output

    logger.error("Executor", f"{MAX_RETRIES} denemede basarisiz")
    failed = os.path.join(SCRIPTS_DIR, f"FAILED_{task_key(task)}.py")
    with open(failed, "w", encoding="utf-8") as f:
        f.write(f"# BASARISIZ: {task}\n# Hata: {last_error}\n\n{current_code}")
    return False, f"Bu gorevi {MAX_RETRIES} denemede tamamlayamadim, {OWNER_NAME}."
