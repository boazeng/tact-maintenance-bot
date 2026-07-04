"""
seed_guy — load the "גיא" bot script into the takt-bots store.

גיא = בוט שירות התפעול של TACT. משוחח עם לקוחות שיש להם מתקני חניה
שהחברה מתחזקת. מיקום בהיררכיה: תחת סמנכ"ל התפעול.

שלב 1: גיא הוא שכפול מדויק של "תסריט דיווח תקלה" (maintenance-troubleshoot).
התסריט נקרא חי מה-DB ומועתק כמו שהוא — כך שכל שינוי עתידי בעורך מתחיל
מאותה נקודה בדיוק. ההבדלים היחידים מהמקור:
    • script_id  — חייב להיות שונה כדי שזה יהיה בוט נפרד
    • name       — שם תצוגה משלו ("גיא") כדי לזהות אותו ברשימה
כל השאר (ברכות, שלבים, פעולות, פריסת העורך) זהה בדיוק למקור.

ערוץ ההפצה (טלגרם, ואז וואטסאפ) מתחבר בשלב נפרד.

הרצה (מתיקיית השורש של takt-bots):
    backend\\.venv\\Scripts\\python.exe seed_guy.py
"""

import sys
import copy

import shared_env  # noqa: F401  — loads the shared .env into os.environ
from database.maintenance import bot_scripts_db

# Windows console defaults to cp1252; force UTF-8 so Hebrew prints don't crash.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

SOURCE_SCRIPT_ID = "maintenance-troubleshoot"   # התסריט שמשכפלים ממנו
GUY_SCRIPT_ID = "guy-parking-service"
GUY_NAME = "גיא — שירות מתקני חניה"


def main():
    source = bot_scripts_db.get_script(SOURCE_SCRIPT_ID, use_cache=False)
    if not source:
        print(f"[seed_guy] שגיאה: לא נמצא תסריט מקור '{SOURCE_SCRIPT_ID}'.")
        sys.exit(1)

    # שכפול מלא, ואז דריסת המזהה והשם בלבד.
    guy = copy.deepcopy(source)
    guy["script_id"] = GUY_SCRIPT_ID
    guy["name"] = GUY_NAME
    # שיהיו חותמות זמן חדשות משלו (save_script ידאג ל-updated_at).
    guy.pop("created_at", None)
    guy.pop("updated_at", None)

    result = bot_scripts_db.save_script(guy)
    print(f"[seed_guy] גיא נטען בהצלחה כשכפול של '{SOURCE_SCRIPT_ID}': {result['script_id']}")
    print(f"[seed_guy] שלבים: {len(guy.get('steps', []))} | "
          f"פעולות סיום: {len(guy.get('done_actions', {}))}")
    print("[seed_guy] פתח את עורך הזרימה כדי לראות ולערוך את התסריט.")


if __name__ == "__main__":
    main()
