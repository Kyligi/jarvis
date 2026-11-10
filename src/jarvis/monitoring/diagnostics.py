
import psutil

from jarvis.monitoring.intelligence import (
    read_sensors,
)


def get_top_processes(limit=5):
    """Mesure les processus les plus gourmands en CPU."""

    processes = []

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            proc.cpu_percent(interval=None)
            processes.append(proc)
        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess,
        ):
            continue

    # Échantillon de courte durée
    import time
    time.sleep(0.3)

    results = []

    for proc in processes:
        try:
            cpu = proc.cpu_percent(interval=None)
            ram = proc.memory_info().rss / (1024 ** 2)

            results.append({
                "name": proc.name(),
                "pid": proc.pid,
                "cpu": cpu,
                "ram": ram,
            })

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess,
        ):
            continue

    results.sort(
        key=lambda item: item["cpu"],
        reverse=True,
    )

    return results[:limit]


def explain_slowdown() -> str:
    """Analyse les performances et suggère des pistes."""

    cpu = psutil.cpu_percent(interval=0.3)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    battery = psutil.sensors_battery()
    sensors = read_sensors()

    lines = [
        "J.A.R.V.I.S. — DIAGNOSTIC AVANCÉ",
        "",
        "RESSOURCES",
        f"CPU : {cpu:.1f} %",
        f"RAM : {ram.percent:.1f} %",
        f"Disque système occupé : {disk.percent:.1f} %",
        "",
    ]

    problems = []
    recommendations = []

    # CPU
    if cpu >= 90:
        problems.append(
            "CPU : utilisation très élevée."
        )
        recommendations.append(
            "Examiner les processus fortement consommateurs."
        )
    elif cpu >= 75:
        problems.append(
            "CPU : utilisation relativement élevée."
        )

    # RAM
    if ram.percent >= 90:
        problems.append(
            "RAM : mémoire presque saturée."
        )
        recommendations.append(
            "Vérifier les applications utilisant beaucoup de RAM."
        )

    # Stockage
    if disk.percent >= 95:
        problems.append(
            "Disque : espace libre très faible."
        )
        recommendations.append(
            "Libérer de l'espace après vérification des fichiers."
        )

    # Batterie
    if battery is not None:
        if not battery.power_plugged and battery.percent <= 15:
            problems.append(
                f"Batterie faible : {battery.percent:.0f} %."
            )

    lines.append("ANALYSE")

    if problems:
        lines.extend(f"• {p}" for p in problems)
    else:
        lines.append(
            "Aucune saturation majeure détectée "
            "pendant cet échantillon."
        )

    # Capteurs AMD
    lines.extend(["", "TEMPÉRATURES"])

    if sensors:
        for name, temperature in sensors.items():
            lines.append(
                f"{name} : {temperature:.1f} °C"
            )
    else:
        lines.append("Capteurs indisponibles.")

    # Processus
    lines.extend(["", "PROCESSUS LES PLUS ACTIFS"])

    processes = get_top_processes(5)

    if processes:
        for proc in processes:
            lines.append(
                f"{proc['name']} (PID {proc['pid']}) "
                f"— CPU {proc['cpu']:.1f} % "
                f"— RAM {proc['ram']:.0f} Mo"
            )
    else:
        lines.append("Aucun processus accessible.")

    # Recommandations
    lines.extend(["", "RECOMMANDATIONS"])

    if recommendations:
        lines.extend(
            f"• {recommendation}"
            for recommendation in recommendations
        )
    else:
        lines.append(
            "Aucune action particulière recommandée."
        )

    lines.extend([
        "",
        "Remarque : ce diagnostic est ponctuel. "
        "Il ne permet pas, à lui seul, de confirmer "
        "la cause d'un ralentissement ou d'une surchauffe.",
    ])

    return "\n".join(lines)
