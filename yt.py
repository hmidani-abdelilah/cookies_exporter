#!/usr/bin/env python3
"""
تحميل فيديو من يوتيوب عبر yt-dlp.

المتطلبات المُجهَّزة على النظام:
  - yt-dlp + ffmpeg
  - deno  (لحل تحديات JS ولتوليد PO Token)
  - خادم bgutil-ytdlp-pot-provider  (systemd --user: bgutil-pot.service)

المشكلة التي كان يجب حلها:
  1) ملف cookies.txt القديم كان ناقص كوكي LOGIN_INFO، لذلك يعتبر yt-dlp الجلسة
     غير مسجَّلة، ويظهر خطأ "Sign in to confirm your age".
  2) كوكيز المتصفح القديمة داخل الملف كانت تُطبَق فوق الكوكيز الحديثة،
     فتُبطل الجلسة (cookies are no longer valid).
     الحل: تصدير الكوكيز من المتصفح إلى ملف جديد/فارغ.
  3) الفيديو مقيد بالعمر، لذلك نحتاج PO Token (bgutil) وعميل web_creator.
"""

import os
import subprocess
import sys

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cookies_exporter import export_cookies  # noqa: E402

URL = "https://youtu.be/IOitbk4qqlk?si=4SdcSMoPKRahfYTv"
OUT_DIR = "./downloads"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(BASE_DIR, "cookies.txt")
BROWSER = "chrome"
POT_HTTP_URL = "http://127.0.0.1:4416"


def _find_pot_server_home():
    """مسار خادم bgutil: النسخة الموجودة داخل المشروع أولاً، ثم نسخة المنزل."""
    candidates = [
        os.path.join(BASE_DIR, "bgutil-ytdlp-pot-provider", "server"),
        os.path.expanduser("~/bgutil-ytdlp-pot-provider/server"),
    ]
    for path in candidates:
        if os.path.isfile(os.path.join(path, "build", "main.js")):
            return path
    return candidates[0]


POT_SERVER_HOME = _find_pot_server_home()


def cookies_are_valid(path=COOKIE_FILE):
    """الجلسة المسجَّلة تتطلّب وجود LOGIN_INFO في ملف الكوكيز."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return any("\tLOGIN_INFO\t" in line for line in f)
    except OSError:
        return False


def refresh_cookies(path=COOKIE_FILE):
    """تصدير كوكيز حديثة من المتصفح (يكتب ملفاً جديداً كاملاً، لا دمج)."""
    count, out = export_cookies(browser=BROWSER, output=path,
                                domains=("youtube.com", "google.com"))
    print(f"تم تصدير {count} كوكي إلى {out}")
    return out


def build_options():
    options = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
        "outtmpl": os.path.join(OUT_DIR, "%(title)s [%(id)s].%(ext)s"),
        "noplaylist": True,
        "merge_output_format": "mp4",
        "continuedl": True,
        "retries": 10,
        "fragment_retries": 10,
        "js_runtimes": {"deno": {}},
        # ملاحظة: قيم extractor_args يجب أن تكون قوائم نصوص (List[str])
        # وإلا تعاملها yt-dlp كمحارف مفردة.
        "extractor_args": {
            "youtubepot-bgutilhttp": {"base_url": [POT_HTTP_URL]},
            "youtubepot-bgutilscript": {"server_home": [POT_SERVER_HOME]},
        },
    }
    if cookies_are_valid():
        options["cookiefile"] = COOKIE_FILE
    else:
        options["cookiesfrombrowser"] = (BROWSER,)
    return options


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    # تصدير كوكيز حديثة دائماً (يوتيوب يُدوّر الكوكيز بين الجلسات)
    try:
        refresh_cookies()
    except Exception as exc:
        print(f"تعذّر تصدير الكوكيز ({exc})، سيتم القراءة من المتصفح مباشرة.")
    for attempt in (1, 2):
        try:
            with YoutubeDL(build_options()) as ydl:
                ydl.download([URL])
            return 0
        except DownloadError:
            if attempt == 2 or not cookies_are_valid():
                raise
            print("فشل التنزيل، جارٍ تحديث الكوكيز من المتصفح وإعادة المحاولة ...")
            refresh_cookies()
    return 1


if __name__ == "__main__":
    sys.exit(main())
