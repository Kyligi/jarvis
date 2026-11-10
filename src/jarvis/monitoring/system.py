
import time
from datetime import timedelta
from pathlib import Path

import psutil


def format_bytes(value: float) -> str:
    return f"{value / (1024 ** 3):.1f} Go"


def system_status() -> str:
    cpu = psutil.cpu_percent(interval=0.3)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage(str(Path.home()))
    battery = psutil.sensors_battery()

    uptime = timedelta(
        seconds=int(time.time() - psutil.boot_time())
    )

    lines = [
        "J.A.R.V.I.S. — ÉTAT SYSTÈME",
        "",
        f"CPU : {cpu:.1f} %",
        f"RAM : {format_bytes(ram.used)} / "
        f"{format_bytes(ram.total)} ({ram.percent:.1f} %)",
        f"Disque : {format_bytes(disk.used)} / "
        f"{format_bytes(disk.total)} ({disk.percent:.1f} %)",
        f"Uptime : {uptime}",
    ]

    if battery is not None:
        state = (
            "En charge" if battery.power_plugged
            else "Sur batterie"
        )
        lines.append(
            f"Batterie : {battery.percent:.0f} % — {state}"
        )

    return "\n".join(lines)


def battery_status() -> str:
    battery = psutil.sensors_battery()

    if battery is None:
        return "Aucune batterie détectée."

    if battery.power_plugged:
        return (
            f"Batterie : {battery.percent:.0f} %. "
            "Alimentation branchée."
        )

    if battery.secsleft in (
        psutil.POWER_TIME_UNKNOWN,
        psutil.POWER_TIME_UNLIMITED,
    ):
        remaining = "Autonomie estimée indisponible"
    else:
        remaining = (
            "Autonomie estimée : "
            + str(timedelta(seconds=int(battery.secsleft)))
        )

    return (
        f"Batterie : {battery.percent:.0f} %. "
        f"{remaining}."
    )


def top_processes(limit: int = 5) -> str:
    # Échantillon initial pour obtenir les valeurs CPU
    processes = []

    for proc in psutil.process_iter(
        ["pid", "name", "memory_info"]
    ):
        try:
            proc.cpu_percent(None)
            processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    time.sleep(0.3)

    results = []

    for proc in processes:
        try:
            cpu = proc.cpu_percent(None)
            mem = proc.memory_info().rss / (1024 ** 2)

            results.append((
                cpu,
                proc.pid,
                proc.name(),
                mem,
            ))
        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess,
        ):
            continue

    results.sort(reverse=True)

    lines = ["TOP PROCESSUS — CPU", ""]

    for cpu, pid, name, mem in results[:limit]:
        lines.append(
            f"{name} (PID {pid}) — "
            f"CPU {cpu:.1f} % | RAM {mem:.0f} Mo"
        )

    return "\n".join(lines)


def diagnose() -> str:
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage(str(Path.home()))
    battery = psutil.sensors_battery()

    issues = []

    if cpu >= 90:
        issues.append(
            f"CPU fortement sollicité : {cpu:.0f} %"
        )

    if ram.percent >= 90:
        issues.append(
            f"Mémoire presque saturée : {ram.percent:.0f} %"
        )

    if disk.percent >= 90:
        issues.append(
            f"Espace disque faible : {disk.percent:.0f} % utilisé"
        )

    if battery and not battery.power_plugged:
        if battery.percent <= 15:
            issues.append(
                f"Batterie faible : {battery.percent:.0f} %"
            )

    if not issues:
        return (
            "DIAGNOSTIC JARVIS\n\n"
            "Aucune saturation détectée sur les ressources "
            "surveillées. Ce contrôle ponctuel ne garantit "
            "pas l'absence d'autres problèmes."
        )

    return (
        "DIAGNOSTIC JARVIS\n\n"
        + "\n".join(f"• {issue}" for issue in issues)
    )
