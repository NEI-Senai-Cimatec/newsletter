# gui/theme/colors.py
"""Visual constants: window sizing, status colors, and font specs.

CustomTkinter's ``dark-blue`` theme renders the base widgets; this module
only centralizes the few values the app sets explicitly.
"""

APP_TITLE = "Newsletter Tool — Processamento de Notícias"
APP_GEOMETRY = "1100x700"
APP_MINSIZE = (900, 600)
APPEARANCE_MODE = "dark"
COLOR_THEME = "dark-blue"

SIDEBAR_WIDTH = 220
STATUS_BAR_HEIGHT = 28

ACTIVE_NAV_COLOR = ("#3B8ED0", "#1F6AA5")

STATUS_OK = "#3FB950"
STATUS_WARNING = "#D29922"
STATUS_ERROR = "#F85149"

LOG_COLORS = {
    "DEBUG": "#8B949E",
    "INFO": "#E6EDF3",
    "WARNING": "#D29922",
    "ERROR": "#F85149",
    "CRITICAL": "#F85149",
}

TITLE_FONT = {"size": 20, "weight": "bold"}
SECTION_FONT = {"size": 14, "weight": "bold"}
NORMAL_FONT = {"size": 13}
SMALL_FONT = {"size": 11}
MONO_FONT = {"family": "Consolas", "size": 12}
