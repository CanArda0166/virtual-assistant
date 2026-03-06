import os
import sys
import json
import math
from datetime import datetime

from project_manager import (
    list_projects, list_branches,
    load_vision, load_progress,
    _health_score, estimated_completion,
    activate_project, execute_project_task,
    create_checkpoint, rollback,
    create_branch, merge_branch,
    prioritize_task, project_think,
    set_active_project, get_active_project
)

RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"

GREEN   = "\033[92m"
BLUE    = "\033[94m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
CYAN    = "\033[96m"
MAGENTA = "\033[95m"
WHITE   = "\033[97m"
GRAY    = "\033[90m"

SYM_DONE    = "●"
SYM_ACTIVE  = "▶"
SYM_FUTURE  = "◇"
SYM_BLOCKER = "✖"
SYM_BAR_ON  = "█"
SYM_BAR_OFF = "░"

W = 68

def _bar(percent: float, width: int = 40) -> str:
    filled = int(width * percent / 100)
    bar    = SYM_BAR_ON * filled + SYM_BAR_OFF * (width - filled)
    if percent >= 75:
        color = GREEN
    elif percent >= 40:
        color = BLUE
    else:
        color = YELLOW
    return f"{color}{bar}{RESET}"

def _line(char: str = "─", color: str = GRAY) -> str:
    return f"{color}{char * W}{RESET}"

def _header(text: str, color: str = CYAN) -> str:
    pad = (W - len(text) - 4) // 2
    return f"{color}{'═' * pad}  {BOLD}{text}{RESET}{color}  {'═' * (W - pad - len(text) - 4)}{RESET}"

def _section(text: str, color: str = WHITE) -> str:
    return f"\n{color}{BOLD}  {text}{RESET}"

def _task_line(title: str, desc: str, sym: str, color: str,
               is_priority: bool = False, completed_at: str = "") -> str:
    prefix = f"  {color}{sym}{RESET} "
    star   = f" {MAGENTA}★{RESET}" if is_priority else ""

    title_str = f"{color}{BOLD}{title}{star}{RESET}"

    date_str = ""
    if completed_at:
        date_str = f" {GRAY}({completed_at}){RESET}"

    lines = [f"{prefix}{title_str}{date_str}"]

    if desc and desc.strip():
        wrapped = _wrap(desc, W - 6)
        for i, wline in enumerate(wrapped):
            lines.append(f"    {GRAY}{'└' if i == len(wrapped)-1 else '│'} {wline}{RESET}")

    return "\n".join(lines)

def _wrap(text: str, width: int) -> list:
    words  = text.split()
    lines  = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= width:
            current = (current + " " + word).strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]

def display_project(name: str, branch: str = "main"):
    vision   = load_vision(name)
    progress = load_progress(name, branch)

    completed      = progress.get("completed", [])
    tasks          = progress.get("tasks", [])
    blockers       = progress.get("blockers", [])
    future         = progress.get("future_features", [])
    priority_order = progress.get("priority_order", [])
    task_meta      = progress.get("task_meta", {})

    total   = len(completed) + len(tasks)
    pct     = round(len(completed) / total * 100) if total > 0 else 0
    health  = _health_score(name, branch)
    est     = estimated_completion(name, branch)
    desc    = vision.get("description", "")
    goal    = vision.get("goal", "")
    stack   = vision.get("stack", "")
    created = vision.get("created_at", "")
    branches_list = list_branches(name)

    print()
    print(_header(f"PROJE: {name.upper()}"))

    print()
    for line in _wrap(desc, W - 4):
        print(f"  {WHITE}{line}{RESET}")
    if goal:
        print(f"  {GRAY}Hedef   : {RESET}{WHITE}{goal}{RESET}")
    if stack:
        print(f"  {GRAY}Stack   : {RESET}{CYAN}{stack}{RESET}")
    if created:
        print(f"  {GRAY}Başlangıç: {RESET}{GRAY}{created}{RESET}")
    if len(branches_list) > 1:
        print(f"  {GRAY}Kollar  : {RESET}{CYAN}{', '.join(branches_list)}{RESET}  (aktif: {branch})")

    print()
    print(_line())
    bar_str = _bar(pct, width=42)
    print(f"  {bar_str}  {BOLD}{WHITE}{pct}%{RESET}")
    print(f"  {GRAY}{'Tamamlanan':12}: {GREEN}{len(completed)}{RESET}  "
          f"{GRAY}{'Bekleyen':10}: {BLUE}{len(tasks)}{RESET}  "
          f"{GRAY}{'Gelecek':8}: {YELLOW}{len(future)}{RESET}  "
          f"{GRAY}Bloker: {RED}{len(blockers)}{RESET}")
    print(f"  {GRAY}Sağlık  : {RESET}", end="")
    for i in range(10):
        if i < health:
            print(f"{GREEN}{SYM_BAR_ON}{RESET}", end="")
        else:
            print(f"{GRAY}{SYM_BAR_OFF}{RESET}", end="")
    print(f"  {BOLD}{health}/10{RESET}")
    print(f"  {GRAY}Tahmini bitiş: {RESET}{MAGENTA}{est}{RESET}")
    print(_line())

    if completed:
        print(_section("TAMAMLANAN ADIMLAR", GREEN))
        for t in completed:
            meta       = task_meta.get(t, {})
            desc_t     = meta.get("desc", "")
            done_at    = meta.get("completed_at", "")
            print(_task_line(t, desc_t, SYM_DONE, GREEN, completed_at=done_at))

    if tasks:
        print(_section("AKTİF / ÖNCELİKLİ ADIMLAR", BLUE))

        ordered = priority_order + [t for t in tasks if t not in priority_order]
        for i, t in enumerate(ordered):
            meta      = task_meta.get(t, {})
            desc_t    = meta.get("desc", "")
            is_prio   = t in priority_order[:3]
            if i == 0:
                print(_task_line(t, desc_t, SYM_ACTIVE, BLUE, is_priority=True))
            else:
                print(_task_line(t, desc_t, "○", BLUE, is_priority=is_prio))

    if blockers:
        print(_section("BLOKERLAR", RED))
        for b in blockers:
            parts  = b.split(":", 1)
            title  = parts[0].strip()
            detail = parts[1].strip() if len(parts) > 1 else ""
            print(_task_line(title, detail, SYM_BLOCKER, RED))

    if future:
        print(_section("GELECEK ÖZELLİKLER", YELLOW))
        for t in future:
            meta   = task_meta.get(t, {})
            desc_t = meta.get("desc", "")
            print(_task_line(t, desc_t, SYM_FUTURE, YELLOW))

    print()
    print(_line("═"))
    print()

def display_all_projects():
    projects = list_projects()
    if not projects:
        print(f"\n{YELLOW}  Henüz proje yok.{RESET}\n")
        return
    print()
    print(_header("TÜM PROJELER", CYAN))
    print()
    for name in projects:
        progress = load_progress(name)
        vision   = load_vision(name)
        done     = len(progress.get("completed", []))
        total    = done + len(progress.get("tasks", []))
        pct      = round(done / total * 100) if total > 0 else 0
        health   = _health_score(name)
        est      = estimated_completion(name)
        desc     = vision.get("description","")[:55]
        bar      = _bar(pct, width=20)
        print(f"  {BOLD}{CYAN}{name:<20}{RESET}  {bar}  {WHITE}{pct:>3}%{RESET}  {GRAY}Sağlık:{health}/10  {est}{RESET}")
        if desc:
            print(f"  {GRAY}{'':20}  {desc}{'...' if len(vision.get('description',''))>55 else ''}{RESET}")
        print()
    print(_line("═"))

def _print_menu(name: str, branch: str):
    print(f"\n{GRAY}  [{name}/{branch}] Komutlar:{RESET}")
    print(f"  {WHITE}devam{GRAY}       → sonraki görevi başlat{RESET}")
    print(f"  {WHITE}görev <ad>{GRAY}  → belirli görevi başlat{RESET}")
    print(f"  {WHITE}öncelik <ad>{GRAY}→ görevi öne al{RESET}")
    print(f"  {WHITE}kontrol{GRAY}     → checkpoint kaydet{RESET}")
    print(f"  {WHITE}geri <N>{GRAY}    → N adım rollback{RESET}")
    print(f"  {WHITE}kol <ad>{GRAY}    → yeni branch aç{RESET}")
    print(f"  {WHITE}birleştir <k>{GRAY}→ kolu main'e merge et{RESET}")
    print(f"  {WHITE}konuş{GRAY}       → NOVA ile proje sohbeti{RESET}")
    print(f"  {WHITE}yenile{GRAY}      → ilerlemeyi göster{RESET}")
    print(f"  {WHITE}çıkış{GRAY}       → menüye dön{RESET}")
    print()

def interactive_project(name: str, branch: str = "main"):
    
    display_project(name, branch)
    _print_menu(name, branch)

    while True:
        try:
            cmd = input(f"{CYAN}  > {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not cmd:
            continue

        low = cmd.lower()

        if low in ("çıkış", "cikis", "q", "geri dön", "geri don"):
            break

        elif low == "yenile":
            display_project(name, branch)
            _print_menu(name, branch)

        elif low == "devam":
            progress = load_progress(name, branch)
            tasks    = progress.get("tasks", [])
            priority = progress.get("priority_order", [])
            ordered  = priority + [t for t in tasks if t not in priority]
            if not ordered:
                print(f"\n{GREEN}  Tüm görevler tamamlandı!{RESET}\n")
            else:
                task = ordered[0]
                set_active_project(name, branch)
                ok, result = execute_project_task(task, name, branch)
                print(f"\n{'  ' + GREEN + 'Tamamlandı' if ok else '  ' + RED + 'Başarısız'}{RESET}: {result[:100]}")
                display_project(name, branch)

        elif low.startswith("görev ") or low.startswith("gorev "):
            task_frag = cmd.split(" ", 1)[1].strip()
            progress  = load_progress(name, branch)
            tasks     = progress.get("tasks", [])
            match     = next((t for t in tasks if task_frag.lower() in t.lower()), None)
            if match:
                set_active_project(name, branch)
                ok, result = execute_project_task(match, name, branch)
                print(f"\n{'  OK' if ok else '  HATA'}: {result[:100]}")
                display_project(name, branch)
            else:
                print(f"\n{RED}  Görev bulunamadı: {task_frag}{RESET}\n")

        elif low.startswith("öncelik ") or low.startswith("oncelik "):
            frag = cmd.split(" ", 1)[1].strip()
            msg  = prioritize_task(name, frag, branch)
            print(f"\n{BLUE}  {msg}{RESET}\n")
            display_project(name, branch)

        elif low == "kontrol":
            label = input(f"  {GRAY}Etiket (boş bırakılabilir): {RESET}").strip()
            path  = create_checkpoint(name, branch, label=label or "manual")
            print(f"\n{GREEN}  Checkpoint kaydedildi.{RESET}\n")

        elif low.startswith("geri "):
            try:
                steps = int(cmd.split()[1])
            except Exception:
                steps = 1
            msg = rollback(name, branch, steps)
            print(f"\n{YELLOW}  {msg}{RESET}\n")
            display_project(name, branch)

        elif low.startswith("kol "):
            new_b = cmd.split(" ", 1)[1].strip()
            msg   = create_branch(name, new_b, branch)
            print(f"\n{CYAN}  {msg}{RESET}\n")

        elif low.startswith("birleştir ") or low.startswith("birlestir "):
            src = cmd.split(" ", 1)[1].strip()
            msg = merge_branch(name, src, branch)
            print(f"\n{CYAN}  {msg}{RESET}\n")
            display_project(name, branch)

        elif low == "konuş" or low == "konus":
            print(f"\n{BLUE}  Proje sohbeti başlatıldı. 'bitti' yazarak çık.{RESET}")
            set_active_project(name, branch)
            while True:
                try:
                    user_in = input(f"\n  {WHITE}Sen: {RESET}").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if user_in.lower() in ("bitti", "çıkış", "cikis"):
                    break
                reply, cmd_type, data = project_think(user_in)
                print(f"\n  {CYAN}NOVA:{RESET} {reply}")
                if cmd_type == "TASK" and data:
                    ok, result = execute_project_task(data, name, branch)
                    print(f"\n  {'✓' if ok else '✗'} {result[:100]}")
                    display_project(name, branch)
                elif cmd_type == "CLOSE":
                    break
            print()

        else:
            print(f"\n{GRAY}  Bilinmeyen komut. Yardım için komut listesine bak.{RESET}\n")

def main_menu():
    while True:
        projects = list_projects()
        print()
        print(_header("NOVA — PROJE YÖNETİMİ", CYAN))
        print()
        if not projects:
            print(f"  {GRAY}Henüz proje yok.{RESET}")
        else:
            display_all_projects()

        print(f"  {WHITE}[1-{len(projects)}]{GRAY} Projeye gir   "
              f"{WHITE}[y]{GRAY} Yeni proje   "
              f"{WHITE}[q]{GRAY} Çıkış{RESET}")
        print()

        try:
            choice = input(f"{CYAN}  > {RESET}").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if choice in ("q", "çıkış", "cikis"):
            break

        elif choice == "y":
            name = input(f"  {GRAY}Proje adı: {RESET}").strip()
            if not name:
                continue
            desc = input(f"  {GRAY}Açıklama: {RESET}").strip()
            from project_manager import create_project
            result = create_project(name, desc)
            if isinstance(result, dict):
                print(f"\n{GREEN}  '{name}' oluşturuldu. {len(result.get('tasks',[]))} adım planlandı.{RESET}")
                interactive_project(name)
            else:
                print(f"\n{RED}  {result}{RESET}")

        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(projects):
                name   = projects[idx]
                branches = list_branches(name)
                branch = "main"
                if len(branches) > 1:
                    print(f"\n  {GRAY}Kollar: {', '.join(branches)}{RESET}")
                    b = input(f"  {GRAY}Kol (boş = main): {RESET}").strip()
                    if b in branches:
                        branch = b
                interactive_project(name, branch)
            else:
                print(f"\n{RED}  Geçersiz numara.{RESET}")

        else:
            match = next((p for p in projects if choice in p.lower()), None)
            if match:
                interactive_project(match)
            else:
                print(f"\n{RED}  Bulunamadı.{RESET}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        name = sys.argv[1]
        branch = sys.argv[2] if len(sys.argv) > 2 else "main"
        if name in list_projects():
            interactive_project(name, branch)
        else:
            print(f"{RED}'{name}' bulunamadı.{RESET}")
            main_menu()
    else:
        main_menu()
