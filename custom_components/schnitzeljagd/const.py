"""Konstanten der Schnitzeljagd-Integration."""

DOMAIN = "schnitzeljagd"

CONF_FILE = "hunt_file"
CONF_INSTALL_EXAMPLE = "install_example"

DEFAULT_FILE = "schnitzeljagd/funkel_luna.yaml"
EXAMPLE_FILE = "funkel_luna.yaml"

PLATFORMS = ["sensor", "binary_sensor", "select", "button", "switch"]

EVENT_TASK_COMPLETED = f"{DOMAIN}_task_completed"
EVENT_STATION_CHANGED = f"{DOMAIN}_station_changed"

SIGNAL_UPDATE = f"{DOMAIN}_update_{{}}"

SERVICE_PREPARE = "prepare"
SERVICE_STOP = "stop"
SERVICE_RESET = "reset"
SERVICE_SET_STATION = "set_station"
SERVICE_START_STATION = "start_station"
SERVICE_COMPLETE_TASK = "complete_task"
SERVICE_RELEASE_TREASURE = "release_treasure"
SERVICE_RELOAD = "reload_hunt"

ATTR_ENTRY = "config_entry"
ATTR_STATION = "station"
ATTR_TASK = "task"
