import psutil


def system_status() -> str:
    ram = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.15)
    battery = psutil.sensors_battery()
    battery_text = f"{battery.percent:.0f}%" if battery else "non disponible"
    return f"CPU : {cpu:.0f}% | RAM : {ram.percent:.0f}% | Batterie : {battery_text}"
