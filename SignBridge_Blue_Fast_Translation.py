"""SignBridge Studio - premium blue UI and improved long-utterance transcription (single-file app).
Pages:  Sign → Text  |  Speech → Sign  |  Sign Library
Gumagamit ng hand_tracker.py at sign_core.py mo."""
import gc, json, math, os, queue, re, subprocess, sys, threading, time, tkinter as tk
from collections import deque
from tkinter import filedialog, messagebox, simpledialog, ttk
import cv2
from PIL import Image, ImageDraw, ImageFont, ImageTk
from hand_tracker import CameraEngine, HandDetector, load_image_rgb
from sign_core import SentenceBuilder, SignClassifier, SignLibrary, safe_label
try:
    import pyttsx3
except ImportError:
    pyttsx3 = None
try:
    import speech_recognition as sr
except ImportError:
    sr = None
try:
    from gtts import gTTS          # online Filipino voice (pip install gTTS)
except ImportError:
    gTTS = None

LIB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "library")
IMG_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
TAGALOG = set("ako ikaw ka siya kami tayo kayo sila ang ng mga sa na po opo oo hindi salamat kumusta kamusta magandang umaga hapon "
              "gabi mahal kita ito iyon ano bakit paano saan sino kailan pwede puwede gusto walang mayroon para kung pero din rin lang "
              "naman mo ko niya namin natin ninyo nila ngayon bukas kahapon tulong pagod masaya malungkot galit gutom uhaw kain inom tubig "
              "paalam pasensya patawad sige halika tara bahay kaibigan pamilya nanay tatay kuya ate lola lolo".split())
# Hiwalay na proseso para sa boses: laging bago ang engine kaya hindi na tumatahimik ang susunod na salita
TTS_HELPER = r"""
import sys, json, gc
import pyttsx3
for line in sys.stdin:
    try:
        d = json.loads(line)
        e = pyttsx3.init(); e.setProperty("rate", d.get("rate", 175)); e.setProperty("volume", d.get("vol", 0.9))
        for v in e.getProperty("voices"):
            if any(k in (v.id + " " + v.name).lower() for k in d.get("want", [])):
                e.setProperty("voice", v.id); break
        e.say(d["text"]); e.runAndWait(); del e; gc.collect()
    except Exception as exc:
        print("ERR", exc, flush=True)
    print("DONE", flush=True)
"""

THEMES = {
    # Calm, premium blue palette inspired by the supplied UI reference.
    "dark": dict(bg="#07111F", card="#0E1B2D", card2="#142640", fg="#EAF3FF", mute="#91A8C7",
                 accent="#39BDF8", good="#52D6C7", bad="#FF7185", line="#233A59", accent2="#8B9CFF"),
    "light": dict(bg="#EFF5FC", card="#FFFFFF", card2="#E4EEF9", fg="#14253D", mute="#5E7492",
                  accent="#168FE0", good="#168E91", bad="#D94C67", line="#D0DDED", accent2="#665DE8"),
}

TXT = {
    "en": dict(
        sign="Sign → Text", speech="Speech → Sign", lib="Sign Library", start="▶  Start Camera", stop="■  Stop Camera",
        cam="Cam #", whole="Whole-word only", mood="Mood", reset="⟲ Reset", speakall="🔊 Speak all",
        ph="Your translated words appear here…", det="DETECTED", rd="READING", face="Face", left="Left Hand",
        right="Right Hand", up="up", mid="middle", down="down", near="near face", happy="Happy", neutral="Neutral", sad="Sad", calib="◎ Calibrate", calibok="Mood calibrated - this is now your neutral face.", noface="No face found.",
        conf="Confidence", hold="Hold (s)", camoff="Camera is off.\nPress ▶ Start Camera.", heard="SPEECH → TEXT",
        signs="SIGN OUTPUT", send="Speak", listen="● Listening… speak now", nolisten="Microphone not available",
        replay="↻ Replay", mute="Mute", auto="Auto-speak", ready="Ready.", nolib="No signs yet - open Sign Library to add photos.",
        novoice="No Filipino voice found - run: pip install gTTS for Filipino audio.", say="Say something, or type below…",
        signs_t="SIGNS", photos_of="PHOTOS OF", pick="Select a sign on the left to see its photos.",
        upl="🖼  Upload photos", imp="📁  Import folder", cap1="📸  Capture 1", burst="📸  Burst ×15",
        name="Sign name", ren="Rename", delsign="🗑 Delete sign", delp="✕ Delete", test="✅ Test accuracy",
        trained="signs", photos="photos", needname="Type a sign name first (or select one in the list).",
        needcam="Start the camera first.", captured="Captured", nohand="No hand visible - show your hand.",
        asktitle="Sign name", ask="What is the name/meaning of this sign?\n(e.g. A, Hello, Thank you)", scan="Scanning photo",
        added="Added", skipped="Skipped (no hand found)", busy="Please wait, still working.", cdel="Delete sign “%s” and all its photos?",
        cdelp="Delete this photo? This cannot be undone.", report="Accuracy report", confus="Often confused",
        tip="Tip: add 10-20 varied photos per sign for better accuracy.", fewph="needs at least 2 photos",
        libcam="LIVE CAMERA - capture signs here", voice_on="🔊 Voice on", muted="🔇 Muted", addsign="＋ Add sign", nosign="no sign yet", tts_t="TEXT → SPEECH", speaking="🔊 Speaking", tts_ready="● Voice ready",
        askgtts="Install the Filipino voice now?\n(needs internet, takes about 10 seconds)", gttsok="Filipino voice installed! Tagalog words will now be spoken in Filipino.", gttsfail="Install failed. Check your internet, then try again."),
    "fil": dict(
        sign="Sign → Teksto", speech="Boses → Sign", lib="Sign Library", start="▶  Buksan ang Camera", stop="■  Isara ang Camera",
        cam="Cam #", whole="Buong salita lang", mood="Mood", reset="⟲ I-reset", speakall="🔊 Basahin lahat",
        ph="Lalabas dito ang mga salita…", det="NAKILALA", rd="BINABASA", face="Mukha", left="Kaliwang Kamay",
        right="Kanang Kamay", up="itaas", mid="gitna", down="ibaba", near="malapit sa mukha", happy="Masaya", neutral="Neutral", sad="Malungkot", calib="◎ I-calibrate", calibok="Na-calibrate ang mood - ito na ang neutral na mukha mo.", noface="Walang mukhang nakita.",
        conf="Confidence", hold="Hold (s)", camoff="Naka-off ang camera.\nI-click ang ▶ Buksan ang Camera.", heard="BOSES → TEKSTO",
        signs="SIGN NA LABAS", send="Basahin", listen="● Nakikinig… magsalita na", nolisten="Walang mikropono",
        replay="↻ Ulitin", mute="I-mute", auto="Auto-basa", ready="Handa na.", nolib="Wala pang sign - buksan ang Sign Library para mag-upload.",
        novoice="Walang Filipino voice - i-install ang gTTS (pip install gTTS) para sa Filipino na audio.", say="Magsalita, o mag-type sa ibaba…",
        signs_t="MGA SIGN", photos_of="MGA LARAWAN NG", pick="Pumili ng sign sa kaliwa para makita ang mga larawan nito.",
        upl="🖼  Mag-upload ng larawan", imp="📁  Import folder", cap1="📸  Capture 1", burst="📸  Burst ×15",
        name="Pangalan ng sign", ren="Palitan ng pangalan", delsign="🗑 Burahin ang sign", delp="✕ Burahin", test="✅ Test accuracy",
        trained="sign", photos="larawan", needname="Maglagay muna ng pangalan ng sign (o pumili sa listahan).",
        needcam="I-start muna ang camera.", captured="Na-capture", nohand="Walang kamay - ipakita sa camera.",
        asktitle="Pangalan ng sign", ask="Ano ang pangalan/kahulugan ng sign na ito?\n(hal. A, Hello, Salamat)", scan="Sinusuri ang larawan",
        added="Naidagdag", skipped="Nilaktawan (walang kamay)", busy="Sandali lang, may ginagawa pa.", cdel="Burahin ang sign “%s” at lahat ng larawan nito?",
        cdelp="Burahin ang larawang ito? Hindi na ito maibabalik.", report="Accuracy report", confus="Madalas malito",
        tip="Tip: magdagdag ng 10-20 iba't ibang larawan bawat sign para mas accurate.", fewph="kailangan ng hindi bababa sa 2 larawan",
        libcam="LIVE CAMERA - dito mag-capture ng sign", voice_on="🔊 May boses", muted="🔇 Naka-mute", addsign="＋ Magdagdag", nosign="wala pang sign", tts_t="TEKSTO → BOSES", speaking="🔊 Nagsasalita", tts_ready="● Handa ang boses",
        askgtts="I-install ang Filipino voice ngayon?\n(kailangan ng internet, mga 10 segundo lang)", gttsok="Na-install na ang Filipino voice! Magsasalita na sa Filipino ang mga salitang Tagalog.", gttsfail="Hindi na-install. Tingnan ang internet at subukan ulit."),
}


def load_font(px, bold=True):
    for n in (("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf") if bold else ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf")):
        try:
            return ImageFont.truetype(n, px)
        except OSError:
            pass
    return ImageFont.load_default()


class App:
    def __init__(self, root):
        self.root = root
        root.title("SignBridge Studio · Sign Language Translator")
        root.geometry("1440x900"); root.minsize(1080, 700)
        root.bind("<F11>", lambda e: root.attributes("-fullscreen", not bool(root.attributes("-fullscreen"))))
        root.bind("<Escape>", lambda e: root.attributes("-fullscreen", False))
        self.lc, self.theme, self.page = "en", "dark", "sign"
        self.library = SignLibrary(LIB_DIR); self.clf = SignClassifier(); self.engine = CameraEngine()
        self.builder = SentenceBuilder(hold=0.45)
        self.busy = False; self._fonts = {}; self._ph = {}; self._thumbs = []; self._tp = []
        self.status = tk.StringVar(value="")
        self.cam_index = tk.IntVar(value=0); self.min_conf = tk.DoubleVar(value=0.7); self.holdv = tk.DoubleVar(value=0.45)
        self.vol = tk.DoubleVar(value=0.9); self.muted = tk.BooleanVar(value=False)
        self.whole = tk.BooleanVar(value=False); self.mood_on = tk.BooleanVar(value=True); self.autospeak = tk.BooleanVar(value=True)
        self.cap_name = tk.StringVar()
        self.vol_val, self.mute_val, self.speaking, self.warned = 0.9, False, False, False
        self.words, self.ended, self.last_hand, self.flash, self.stop_listen = [], False, time.monotonic(), 0.0, None
        self.face, self.fmiss, self.fcount, self.last_frame = None, 0, 0, None
        self.mood, self.smiles, self.hist, self.last_text = "", deque(maxlen=5), [], ""
        self._anim = 0.0; self.base, self.mshape, self.mvotes, self.mood_src, self.mood_on_val, self.mmiss = (0.0, 0.38), None, deque(maxlen=6), None, True, 0
        self.helper = None; self.tts_warned = False; self.installing = False; self.fps = 0.0; self._tl = 0.0
        self.fd = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        self.sd = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_smile.xml")
        self.tq = queue.Queue(); self._recognition_lock = threading.Lock(); self._audio_queue = queue.Queue(); self._speech_session = 0; threading.Thread(target=self.tts_worker, daemon=True).start(); threading.Thread(target=self.recognition_worker, daemon=True).start()
        threading.Thread(target=self.mood_worker, daemon=True).start()
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self.build_ui(); self.retrain(); self.poll()
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    T = property(lambda self: THEMES[self.theme])
    t = property(lambda self: TXT[self.lc])

    def F(self, px, bold=True):
        k = (max(int(px), 8), bold)
        if k not in self._fonts:
            self._fonts[k] = load_font(*k)
        return self._fonts[k]

    def ui(self, fn):
        self.root.after(0, fn)

    def set_status(self, text):
        self.ui(lambda: self.status.set(text))

    # ------------------------------------------------------------------ building blocks
    def btn(self, parent, text, cmd, bg, fg="white", **kw):
        # Allow individual buttons to override padding without passing duplicate
        # keyword arguments to tkinter.Button (which raises TypeError).
        padx = kw.pop("padx", 14)
        pady = kw.pop("pady", 8)
        button = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg, relief="flat", bd=0, padx=padx, pady=pady, cursor="hand2",
                           font=("Segoe UI", 10, "bold"), activebackground=bg, activeforeground=fg, **kw)
        # Gentle hover feedback makes controls feel responsive without changing the layout.
        base_bg = bg
        def hover_on(_event):
            try:
                button.configure(highlightthickness=1, highlightbackground=self.T["accent"], relief="flat")
                if bg not in (self.T["good"], self.T["bad"], self.T["accent"]):
                    button.configure(bg=self.T["line"])
            except tk.TclError:
                pass
        def hover_off(_event):
            try:
                button.configure(highlightthickness=0, bg=base_bg)
            except tk.TclError:
                pass
        button.bind("<Enter>", hover_on)
        button.bind("<Leave>", hover_off)
        return button

    def seg(self, parent, items, cur, cmd):
        f = tk.Frame(parent, bg=self.T["card"]); f.btns = {}
        for val, txt in items:
            f.btns[val] = tk.Button(f, text=txt, command=lambda v=val: cmd(v), relief="flat", bd=0, padx=15, pady=11,
                                    cursor="hand2", font=("Segoe UI", 9, "bold"), highlightthickness=0)
            f.btns[val].pack(side="left", padx=2)
        self.paint(f, cur); return f

    def paint(self, f, cur):
        for v, b in f.btns.items():
            on = v == cur
            b.config(bg=self.T["accent"] if on else self.T["bg"], fg="#07130F" if on else self.T["mute"],
                     activebackground=self.T["accent"] if on else self.T["card2"], activeforeground="#07130F" if on else self.T["fg"])

    def card(self, parent, title, expand=False, **pk):
        T = self.T
        f = tk.Frame(parent, bg=T["card"], highlightthickness=1, highlightbackground=T.get("line", T["card2"])); f.pack(fill="both" if expand else "x", expand=expand, **pk)
        if title:
            tk.Label(f, text=title, font=("Segoe UI", 9, "bold"), fg=T["accent"], bg=T["card"]).pack(anchor="w", padx=16, pady=(12, 3))
        inner = tk.Frame(f, bg=T["card"]); inner.pack(fill="both", expand=True, padx=14, pady=(2, 12)); return inner

    def check(self, parent, text, var):
        T = self.T
        return tk.Checkbutton(parent, text=text, variable=var, font=("Segoe UI", 10, "bold"), fg=T["fg"], bg=T["card"],
                              selectcolor=T["card2"], activebackground=T["card"], activeforeground=T["fg"])

    def slider(self, parent, text, var, lo, hi):
        T = self.T; r = tk.Frame(parent, bg=T["card"])
        tk.Label(r, text=text, fg=T["mute"], bg=T["card"], font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        ttk.Scale(r, from_=lo, to=hi, variable=var, length=110, command=lambda _=None: self.apply_settings()).pack(side="left")
        return r

    def video_box(self, parent):
        box = tk.Frame(parent, bg="#07111F"); box.pack_propagate(False)
        lab = tk.Label(box, bg="#07111F", fg="#91A8C7", font=("Segoe UI", 12), text=self.t["camoff"]); lab.pack(fill="both", expand=True)
        return box, lab

    # ------------------------------------------------------------------ UI
    def build_ui(self):
        T, t = self.T, self.t
        for w in self.root.winfo_children():
            w.destroy()
        self.root.configure(bg=T["bg"])
        s = self.style
        s.configure("Horizontal.TScale", background=T["card"], troughcolor=T["card2"], bordercolor=T["card"])
        s.configure("TSpinbox", fieldbackground=T["card2"], foreground=T["fg"], arrowcolor=T["mute"])
        s.configure("TEntry", fieldbackground=T["card2"], foreground=T["fg"], insertcolor=T["fg"], bordercolor=T["line"])
        s.configure("Horizontal.TScrollbar", background=T["card2"], troughcolor=T["card"])
        s.configure("Vertical.TScrollbar", background=T["card2"], troughcolor=T["card"])

        # Compact product header: restrained typography, clear hierarchy, no decorative emoji clutter.
        top = tk.Frame(self.root, bg=T["bg"])
        top.pack(fill="x", padx=24, pady=(18, 12))
        brand = tk.Frame(top, bg=T["bg"])
        brand.pack(side="left", padx=(0, 28))
        mark = tk.Canvas(brand, width=38, height=38, bg=T["bg"], highlightthickness=0)
        mark.pack(side="left", padx=(0, 10))
        mark.create_rectangle(2, 2, 36, 36, outline=T["accent"], width=2)
        mark.create_line(10, 25, 10, 13, fill=T["accent"], width=3)
        mark.create_line(10, 13, 19, 22, fill=T["accent"], width=3)
        mark.create_line(19, 22, 28, 11, fill=T["accent"], width=3)
        mark.create_line(28, 11, 28, 25, fill=T["accent"], width=3)
        brandtext = tk.Frame(brand, bg=T["bg"]); brandtext.pack(side="left")
        tk.Label(brandtext, text="SIGNBRIDGE", font=("Segoe UI", 17, "bold"), fg=T["fg"], bg=T["bg"]).pack(anchor="w")
        tk.Label(brandtext, text="SIGN LANGUAGE  /  ACCESSIBILITY TOOLS", font=("Segoe UI", 8, "bold"), fg=T["mute"], bg=T["bg"]).pack(anchor="w", pady=(1, 0))

        self.nav = self.seg(top, [("sign", "SIGN  /  TEXT"), ("speech", "SPEECH  /  SIGN"), ("lib", "SIGN LIBRARY")], self.page, self.show_page)
        self.nav.pack(side="left", pady=2)
        tools = tk.Frame(top, bg=T["bg"]); tools.pack(side="right")
        self.btn(tools, "FIL" if self.lc == "en" else "ENG", self.toggle_lang, T["card2"], T["fg"], padx=12, pady=9).pack(side="right", padx=(8, 0))
        self.btn(tools, "LIGHT" if self.theme == "dark" else "DARK", self.toggle_theme, T["card2"], T["fg"], padx=12, pady=9).pack(side="right", padx=(8, 0))
        ttk.Scale(tools, from_=0, to=1, variable=self.vol, length=76, command=lambda _=None: self.apply_settings()).pack(side="right", padx=(4, 7))
        self.mute_btn = self.btn(tools, "", self.toggle_mute, T["card2"], T["fg"], padx=12, pady=9); self.mute_btn.pack(side="right")
        self.sync_mute()

        self.accent_line(); self._phs = {}
        self.content = tk.Frame(self.root, bg=T["bg"])
        self.content.pack(fill="both", expand=True, padx=24, pady=(2, 10))
        self.pages = {k: tk.Frame(self.content, bg=T["bg"]) for k in ("sign", "speech", "lib")}
        self.build_sign(self.pages["sign"])
        self.build_speech(self.pages["speech"])
        self.build_lib(self.pages["lib"])
        self.borderize(self.content)

        footer = tk.Frame(self.root, bg=T["bg"])
        footer.pack(fill="x", padx=25, pady=(0, 9))
        tk.Label(footer, text="●", font=("Segoe UI", 9), fg=T["good"], bg=T["bg"]).pack(side="left")
        tk.Label(footer, textvariable=self.status, font=("Segoe UI", 9), fg=T["mute"], bg=T["bg"], anchor="w").pack(side="left", padx=(6, 0))
        tk.Label(footer, text="SIGNBRIDGE STUDIO  ·  LOCAL SESSION", font=("Segoe UI", 8, "bold"), fg=T["mute"], bg=T["bg"]).pack(side="right")
        self.status.set(t["ready"]); self.render_sentence(); self.show_page(self.page); self._sync_cam_buttons(); self.sync_mute()

    def build_sign(self, pg):
        T, t = self.T, self.t
        box = tk.Frame(pg, bg=T["card"]); box.pack(fill="both", expand=True)
        self.vbox, self.video = self.video_box(box); self.vbox.pack(fill="both", expand=True, padx=8, pady=8)
        bub = tk.Frame(box, bg=T["card2"]); bub.pack(fill="x", padx=14, pady=(0, 8))
        tk.Frame(bub, bg=T["accent"], width=6).pack(side="left", fill="y")
        self.sentence = tk.Label(bub, font=("Segoe UI", 26, "bold"), bg=T["card2"], anchor="w", justify="left", wraplength=900)
        self.sentence.pack(side="left", fill="x", expand=True, padx=16, pady=10)
        self.sign_tts = tk.Label(bub, text=t["tts_ready"], font=("Segoe UI", 10, "bold"), bg=T["card2"], fg=T["mute"]); self.sign_tts.pack(side="right", padx=14)
        box.bind("<Configure>", lambda e: self.sentence.config(wraplength=max(e.width - 240, 200)))
        ctl = tk.Frame(box, bg=T["card"]); ctl.pack(fill="x", padx=14, pady=(0, 12))
        self.cam_btn = self.btn(ctl, "", self.toggle_camera, T["good"]); self.cam_btn.pack(side="left")
        tk.Label(ctl, text=t["cam"], fg=T["mute"], bg=T["card"]).pack(side="left", padx=(10, 3))
        ttk.Spinbox(ctl, from_=0, to=5, width=3, textvariable=self.cam_index).pack(side="left")
        self.check(ctl, t["whole"], self.whole).pack(side="left", padx=(14, 0))
        self.check(ctl, t["mood"], self.mood_on).pack(side="left", padx=(6, 0))
        self.btn(ctl, t["calib"], self.calibrate_mood, T["card2"], T["fg"]).pack(side="left", padx=4)
        self.slider(ctl, t["conf"], self.min_conf, 0.4, 0.95).pack(side="left", padx=8)
        self.slider(ctl, t["hold"], self.holdv, 0.25, 1.5).pack(side="left", padx=8)
        self.btn(ctl, t["reset"], self.reset_sentence, T["bad"]).pack(side="right")
        self.btn(ctl, t["speakall"], lambda: self.speak(" ".join(self.words)), T["accent"], "#06121F").pack(side="right", padx=8)

    def build_speech(self, pg):
        T, t = self.T, self.t
        # Balanced 58/42 layout: transcript gets room, sign results remain visible.
        pg.columnconfigure(0, weight=8, uniform="speechcols")
        pg.columnconfigure(1, weight=5, uniform="speechcols")
        pg.rowconfigure(0, weight=1)
        left = tk.Frame(pg, bg=T["bg"]); left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.rowconfigure(0, weight=1); left.rowconfigure(1, weight=0); left.columnconfigure(0, weight=1)

        c1 = tk.Frame(left, bg=T["card"], highlightthickness=1, highlightbackground=T["card2"])
        c1.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        self.step(c1, 1, "LIVE TRANSCRIPTION")
        hd = tk.Frame(c1, bg=T["card"]); hd.pack(fill="x", padx=18, pady=(6, 2))
        self.orb = tk.Canvas(hd, width=76, height=76, bg=T["card"], highlightthickness=0); self.orb.pack(side="left")
        mid = tk.Frame(hd, bg=T["card"]); mid.pack(side="left", fill="x", expand=True, padx=12)
        microw = tk.Frame(mid, bg=T["card"]); microw.pack(fill="x")
        self.mic_lbl = tk.Label(microw, text="", font=("Segoe UI", 11, "bold"), fg=T["good"], bg=T["card"], anchor="w")
        self.mic_lbl.pack(side="left", fill="x", expand=True)
        self.mic_fix_btn = self.btn(microw, "Install Mic Support", self.install_mic_support, T["card2"], T["fg"])
        self.mic_fix_btn.pack(side="right", padx=(8, 0))
        self.wave = tk.Canvas(mid, height=48, bg=T["card"], highlightthickness=0); self.wave.pack(fill="x", pady=(4, 0))
        tk.Label(c1, text="TRANSCRIPT  /  PHRASE RESULTS", font=("Segoe UI", 9, "bold"),
                 fg=T["mute"], bg=T["card"], anchor="w").pack(fill="x", padx=22, pady=(5, 3))
        bub = tk.Frame(c1, bg=T["card2"], highlightthickness=1, highlightbackground=T["accent"])
        bub.pack(fill="both", expand=True, padx=18, pady=(3, 8))
        tk.Frame(bub, bg=T["accent"], width=5).pack(side="left", fill="y")
        self.heard = tk.Label(bub, text=t["say"], font=("Segoe UI", 25, "bold"), fg=T["mute"], bg=T["card2"],
                              justify="left", anchor="nw", wraplength=720)
        self.heard.pack(fill="both", expand=True, padx=18, pady=16)
        bub.bind("<Configure>", lambda e: self.heard.config(wraplength=max(e.width - 55, 220)))
        self.histl = tk.Label(c1, text="", font=("Segoe UI", 10), fg=T["mute"], bg=T["card"], justify="left", anchor="w", wraplength=700)
        self.histl.pack(fill="x", padx=22, pady=(0, 10))

        c2 = tk.Frame(left, bg=T["card"], highlightthickness=1, highlightbackground=T["card2"])
        c2.grid(row=1, column=0, sticky="ew")
        row = self.step(c2, 2, "TEXT TO SPEECH")
        self.tts_lbl = tk.Label(row, text=t["tts_ready"], font=("Segoe UI", 10, "bold"), fg=T["mute"], bg=T["card"]); self.tts_lbl.pack(side="right")
        bar = tk.Frame(c2, bg=T["card"]); bar.pack(fill="x", padx=18, pady=(6, 8))
        self.entry = ttk.Entry(bar, font=("Segoe UI", 13)); self.entry.pack(side="left", fill="x", expand=True, ipady=7)
        self.entry.bind("<Return>", lambda e: self.send_typed())
        self.btn(bar, "🔊  " + t["send"], self.send_typed, T["accent"], "#06121F").pack(side="left", padx=(8, 0))
        bar2 = tk.Frame(c2, bg=T["card"]); bar2.pack(fill="x", padx=18, pady=(0, 12))
        self.sp_mute = self.btn(bar2, "", self.toggle_mute, T["card2"], T["fg"]); self.sp_mute.pack(side="left")
        self.check(bar2, t["auto"], self.autospeak).pack(side="left", padx=12)
        ttk.Scale(bar2, from_=0, to=1, variable=self.vol, length=100, command=lambda _=None: self.apply_settings()).pack(side="left", padx=6)
        self.btn(bar2, t["reset"], self.reset_speech, T["bad"]).pack(side="right")

        right = tk.Frame(pg, bg=T["card"], highlightthickness=1, highlightbackground=T["card2"])
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        self.step(right, 3, "SIGN OUTPUT")
        tk.Label(right, text="MATCHED SIGN LIBRARY RESULTS", font=("Segoe UI", 9, "bold"),
                 fg=T["mute"], bg=T["card"], anchor="w", justify="left", wraplength=360).pack(fill="x", padx=16, pady=(2, 6))
        self.holder = tk.Frame(right, bg=T["card"]); self.holder.pack(fill="both", expand=True, padx=12, pady=8)
        self.holder.columnconfigure(0, weight=1, uniform="signtiles"); self.holder.columnconfigure(1, weight=1, uniform="signtiles")

    def build_lib(self, pg):
        T, t = self.T, self.t
        pg.columnconfigure(1, weight=1); pg.rowconfigure(0, weight=1)
        lf = tk.Frame(pg, bg=T["card"], width=250); lf.grid(row=0, column=0, sticky="ns", padx=(0, 10)); lf.pack_propagate(False)
        tk.Label(lf, text=t["signs_t"], font=("Segoe UI", 9, "bold"), fg=T["mute"], bg=T["card"]).pack(anchor="w", padx=14, pady=(12, 4))
        row = tk.Frame(lf, bg=T["card"]); row.pack(fill="both", expand=True, padx=8)
        self.lb = tk.Listbox(row, font=("Segoe UI", 12), bg=T["card2"], fg=T["fg"], bd=0, highlightthickness=0, activestyle="none",
                             selectbackground=T["accent"], selectforeground="#06121F", exportselection=False)
        sb = ttk.Scrollbar(row, command=self.lb.yview); self.lb.config(yscrollcommand=sb.set)
        self.lb.pack(side="left", fill="both", expand=True); sb.pack(side="left", fill="y")
        self.lb.bind("<<ListboxSelect>>", lambda e: self.show_photos())
        self.btn(lf, t["ren"], self.rename_sign, T["card2"], T["fg"]).pack(fill="x", padx=10, pady=(8, 4))
        self.btn(lf, t["delsign"], self.delete_sign, T["bad"]).pack(fill="x", padx=10, pady=(0, 10))
        right = tk.Frame(pg, bg=T["bg"]); right.grid(row=0, column=1, sticky="nsew")
        phc = tk.Frame(right, bg=T["card"]); phc.pack(side="bottom", fill="x", pady=(10, 0))
        self.ph_title = tk.Label(phc, text="", font=("Segoe UI", 9, "bold"), fg=T["mute"], bg=T["card"]); self.ph_title.pack(anchor="w", padx=14, pady=(10, 0))
        cv = tk.Canvas(phc, bg=T["card"], height=185, highlightthickness=0)
        hs = ttk.Scrollbar(phc, orient="horizontal", command=cv.xview); cv.configure(xscrollcommand=hs.set)
        cv.pack(fill="x", padx=8); hs.pack(fill="x", padx=8, pady=(0, 8))
        self.strip = tk.Frame(cv, bg=T["card"]); cv.create_window((0, 0), window=self.strip, anchor="nw")
        self.strip.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        camrow = tk.Frame(right, bg=T["bg"]); camrow.pack(fill="both", expand=True)
        cc = tk.Frame(camrow, bg=T["card"]); cc.pack(side="left", fill="both", expand=True)
        tk.Label(cc, text=t["libcam"], font=("Segoe UI", 9, "bold"), fg=T["mute"], bg=T["card"]).pack(anchor="w", padx=14, pady=(10, 2))
        self.vbox2, self.video2 = self.video_box(cc); self.vbox2.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        ct = tk.Frame(camrow, bg=T["card"], width=290); ct.pack(side="left", fill="y", padx=(10, 0)); ct.pack_propagate(False)
        p = tk.Frame(ct, bg=T["card"]); p.pack(fill="both", expand=True, padx=14, pady=12)
        self.cam_btn2 = self.btn(p, "", self.toggle_camera, T["good"]); self.cam_btn2.pack(fill="x")
        r = tk.Frame(p, bg=T["card"]); r.pack(fill="x", pady=6)
        tk.Label(r, text=t["cam"], fg=T["mute"], bg=T["card"]).pack(side="left"); ttk.Spinbox(r, from_=0, to=5, width=3, textvariable=self.cam_index).pack(side="left", padx=6)
        tk.Label(p, text=t["name"].upper(), font=("Segoe UI", 9, "bold"), fg=T["mute"], bg=T["card"]).pack(anchor="w", pady=(8, 2))
        ttk.Entry(p, textvariable=self.cap_name, font=("Segoe UI", 12)).pack(fill="x", ipady=4)
        self.btn(p, t["cap1"], lambda: self.capture(1), T["accent"], "#06121F").pack(fill="x", pady=(8, 4))
        self.btn(p, t["burst"], lambda: self.capture(15), "#5B6EAE").pack(fill="x", pady=4)
        self.btn(p, t["upl"], self.add_photos, T["card2"], T["fg"]).pack(fill="x", pady=(14, 4))
        self.btn(p, t["imp"], self.import_folder, T["card2"], T["fg"]).pack(fill="x", pady=4)
        self.btn(p, t["test"], self.test_accuracy, T["good"]).pack(fill="x", pady=(14, 4))
        self.train_info = tk.Label(p, text="", fg=T["fg"], bg=T["card"], font=("Segoe UI", 10, "bold"), wraplength=250, justify="left"); self.train_info.pack(anchor="w", pady=(10, 0))
        self.cap_info = tk.Label(p, text=t["tip"], fg=T["mute"], bg=T["card"], wraplength=250, justify="left"); self.cap_info.pack(anchor="w", pady=4)
        self.refresh_library_view()

    def show_page(self, name):
        prev, self.page = self.page, name; self.paint(self.nav, name)
        for p in self.pages.values():
            p.pack_forget()
        self.pages[name].pack(fill="both", expand=True)
        if name == "speech":
            self.listen_start()
        elif self.stop_listen:
            self.listen_stop()
        if name == "lib":
            self.refresh_library_view()

    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"; self.build_ui()

    def toggle_lang(self):
        self.lc = "fil" if self.lc == "en" else "en"; self.warned = False; self.listen_stop(); self.build_ui()

    def toggle_mute(self):
        self.muted.set(not self.muted.get()); self.apply_settings(); self.sync_mute()

    def sync_mute(self):
        m = self.muted.get()
        for b, txt in ((getattr(self, "mute_btn", None), "🔇" if m else "🔊"),
                       (getattr(self, "sp_mute", None), self.t["muted"] if m else self.t["voice_on"])):
            try:
                if b is not None:
                    b.config(text=txt)
            except tk.TclError:
                pass

    def apply_settings(self):
        self.engine.min_conf = float(self.min_conf.get()); self.builder.hold = float(self.holdv.get())
        self.vol_val, self.mute_val = float(self.vol.get()), bool(self.muted.get()); self.sync_mute()

    # ------------------------------------------------------------------ camera + sign -> text -> speech
    def toggle_camera(self):
        if self.engine.running:
            self.engine.stop(); self.builder.reset()
        else:
            self.engine.classifier = self.clf; self.apply_settings(); self.engine.start(int(self.cam_index.get()))
        self._sync_cam_buttons()

    def _sync_cam_buttons(self):
        on = self.engine.running
        for b in (getattr(self, "cam_btn", None), getattr(self, "cam_btn2", None)):
            try:
                b.config(text=self.t["stop"] if on else self.t["start"], bg=self.T["bad"] if on else self.T["good"],
                         activebackground=self.T["bad"] if on else self.T["good"])
            except (tk.TclError, AttributeError):
                pass

    def on_word(self, word):
        if self.ended:
            self.words, self.ended = [], False
        self.words.append(word.capitalize() if not self.words else word.lower())
        self.flash = time.monotonic() + 1.0; self.beep(); self.render_sentence(); self.speak(word)

    def render_sentence(self):
        self.sentence.config(text=" ".join(self.words) or self.t["ph"], fg=self.T["fg"] if self.words else self.T["mute"])

    def reset_sentence(self):
        self.words, self.ended = [], False; self.builder.reset(); self.render_sentence()

    def beep(self):
        if self.mute_val:
            return
        def b():
            try:
                import winsound; winsound.Beep(1200, 60)
            except Exception:
                pass
        threading.Thread(target=b, daemon=True).start()

    def speak(self, text):
        text = (text or "").strip()
        if text and not self.mute_val:
            self.tq.put(text)

    def tts_worker(self):
        try:
            import pythoncom; pythoncom.CoInitialize()
        except Exception:
            pass
        while True:
            parts = [self.tq.get()]
            while not self.tq.empty():
                parts.append(self.tq.get_nowait())
            if self.mute_val:
                continue
            self.speaking = True; joined = " ".join(parts)
            self.ui(lambda: self.tts_state("speaking", "Filipino" if self.is_tagalog(joined) else "English"))
            try:
                self.say(joined)
                self.ui(lambda: self.tts_state("ready"))
            except Exception as exc:
                self.tts_fail(str(exc))
            gc.collect(); time.sleep(0.15); self.speaking = False

    def is_tagalog(self, text):
        if self.lc == "fil":
            return True
        ws = re.findall(r"[a-zñ']+", text.lower()); hits = sum(w in TAGALOG for w in ws)
        return hits >= 1 and hits * 3 >= len(ws)

    def say(self, text):
        tl = self.is_tagalog(text)
        if tl and gTTS is not None and os.name == "nt":          # Filipino audio (online)
            try:
                self.say_gtts(text, "tl"); return
            except Exception as exc:
                self.set_status(f"Filipino voice failed (check internet): {exc}")
        elif tl and gTTS is None and not self.warned:
            self.warned = True; self.set_status(self.t["novoice"]); self.ui(self.offer_gtts)
        self.say_local(text, tl)

    def say_local(self, text, tl):
        msg = json.dumps(dict(text=text, rate=175, vol=self.vol_val, want=["fil", "tagalog"] if tl else ["en-us", "english", "zira", "david"]))
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        for _ in range(2):
            try:
                if self.helper is None or self.helper.poll() is not None:
                    self.helper = subprocess.Popen([sys.executable, "-c", TTS_HELPER], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                                   stderr=subprocess.STDOUT, text=True, encoding="utf-8", bufsize=1, creationflags=flags)
                self.helper.stdin.write(msg + "\n"); self.helper.stdin.flush(); last = ""
                while True:
                    line = self.helper.stdout.readline()
                    if not line:
                        raise RuntimeError(last or "TTS helper stopped")
                    if line.startswith("DONE"):
                        break
                    last = line.strip()
                if last.startswith("ERR"):
                    self.tts_fail(last)
                return
            except Exception:
                self.helper = None
        self.say_powershell(text)                                # huling paraan: built-in na boses ng Windows

    def say_powershell(self, text):
        ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
              f"$s.Volume = {int(self.vol_val * 100)}; $s.Speak([Console]::In.ReadToEnd())")
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], input=text, text=True, encoding="utf-8", timeout=90,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=True)

    def tts_fail(self, msg):
        self.set_status(f"TTS error: {msg}"); self.ui(lambda: self.tts_state("error", msg))
        if not self.tts_warned:
            self.tts_warned = True
            self.ui(lambda: messagebox.showwarning("Voice", f"Hindi makapagsalita / Voice error:\n{msg}"))

    def say_gtts(self, text, lang):
        import ctypes, tempfile
        fd, path = tempfile.mkstemp(suffix=".mp3"); os.close(fd)
        try:
            gTTS(text=text, lang=lang).save(path)
            mci = ctypes.windll.winmm.mciSendStringW; al = f"sb{int(time.time() * 1000)}"
            mci(f'open "{path}" type mpegvideo alias {al}', None, 0, None)
            mci(f"setaudio {al} volume to {int(self.vol_val * 1000)}", None, 0, None)
            mci(f"play {al} wait", None, 0, None); mci(f"close {al}", None, 0, None)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    # ------------------------------------------------------------------ speech -> text -> speech + sign
    def install_mic_support(self):
        """Install microphone dependencies into the exact Python running this app."""
        if getattr(self, "_mic_installing", False):
            return
        self._mic_installing = True
        self.mic_fix_btn.config(state="disabled", text="Installing…")
        self.heard.config(
            text="Installing microphone support… Please wait. The app may need to restart afterward.",
            fg=self.T["mute"]
        )
        self.set_status("Installing SpeechRecognition and PyAudio…")

        def worker():
            try:
                cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "SpeechRecognition", "PyAudio"]
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=300,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
                if result.returncode == 0:
                    def success():
                        self.heard.config(
                            text="Microphone support installed. Please close and reopen SignBridge, then open Speech → Sign.",
                            fg=self.T["fg"]
                        )
                        self.status.set("Microphone support installed · restart the app to activate it.")
                        messagebox.showinfo(
                            "Microphone support installed",
                            "SpeechRecognition and PyAudio were installed successfully.\n\n"
                            "Close and reopen SignBridge, then open Speech → Sign."
                        )
                    self.ui(success)
                else:
                    details = (result.stderr or result.stdout or "No details returned.")[-1800:]
                    def failed():
                        self.heard.config(
                            text="Microphone support could not be installed automatically. See the message for the fix.",
                            fg=self.T["bad"]
                        )
                        self.status.set("Microphone setup failed.")
                        messagebox.showerror(
                            "Microphone setup failed",
                            "Could not install PyAudio automatically.\n\n"
                            "Try running this in Command Prompt using the same Python installation:\n\n"
                            f'"{sys.executable}" -m pip install --upgrade SpeechRecognition PyAudio\n\n'
                            "Details:\n" + details
                        )
                    self.ui(failed)
            except Exception as exc:
                self.ui(lambda err=str(exc): messagebox.showerror(
                    "Microphone setup failed",
                    f"Automatic installation failed: {err}\n\n"
                    f'Run: "{sys.executable}" -m pip install --upgrade SpeechRecognition PyAudio'
                ))
            finally:
                self._mic_installing = False
                self.ui(lambda: self.mic_fix_btn.config(state="normal", text="Install Mic Support"))

        threading.Thread(target=worker, daemon=True).start()

    def listen_start(self):
        """Listen continuously with lower pause latency; queue and merge phrase chunks."""
        self._speech_session += 1
        if sr is None:
            self.heard.config(
                text="Speech recognition is not installed. Click “Install Mic Support”, then restart SignBridge.",
                fg=self.T["bad"]
            )
            return
        self.listen_stop()
        code = "fil-PH" if self.lc == "fil" else "en-US"

        def work():
            try:
                rec = sr.Recognizer()
                # Avoid cutting off short trailing words; still finalize after a natural pause.
                # Let natural pauses occur without splitting the sentence too aggressively.
                # The recognizer still emits chunks periodically so very long speech can continue.
                rec.pause_threshold = 0.65
                rec.non_speaking_duration = 0.30
                rec.phrase_threshold = 0.20
                rec.dynamic_energy_threshold = True
                mic = sr.Microphone()
                with mic as src:
                    rec.adjust_for_ambient_noise(src, duration=0.35)
                # Longer limit prevents phrases like "ang ganda ganda ni Lea" being clipped.
                stopper = rec.listen_in_background(
                    mic, lambda r, a: self.on_audio(r, a, code), phrase_time_limit=18
                )
                self.stop_listen = stopper
                self.ui(lambda: self.set_status("Listening · Filipino" if code == "fil-PH" else "Listening · English"))
            except Exception as exc:
                err = str(exc)
                is_audio_dep = any(k in err.lower() for k in ("pyaudio", "no default input device", "microphone"))
                def show_mic_error():
                    if is_audio_dep:
                        self.heard.config(
                            text="Microphone support is missing or unavailable. Click “Install Mic Support”, then restart SignBridge.",
                            fg=self.T["bad"]
                        )
                        self.status.set(f"Microphone setup needed: {err}")
                    else:
                        self.heard.config(text=f"{self.t['nolisten']}: {err}", fg=self.T["bad"])
                        self.status.set("Microphone error.")
                self.ui(show_mic_error)
        threading.Thread(target=work, daemon=True).start()

    def listen_stop(self):
        self._speech_session += 1
        stopper, self.stop_listen = self.stop_listen, None
        if stopper:
            try:
                stopper(wait_for_stop=False)
            except Exception:
                pass
        try:
            self.mic_lbl.config(text="")
        except (tk.TclError, AttributeError):
            pass

    def on_audio(self, rec, audio, code):
        """Queue every captured phrase; never discard a phrase just because another is transcribing."""
        if self.speaking:
            return
        try:
            self._audio_queue.put_nowait((rec, audio, code, self._speech_session, time.monotonic()))
        except Exception:
            self.set_status("Speech queue is busy; please continue speaking naturally.")

    @staticmethod
    def _join_transcripts(previous, new_text):
        """Join adjacent recognition chunks without duplicating their overlapping words."""
        a = " ".join((previous or "").split()).strip()
        b = " ".join((new_text or "").split()).strip()
        if not a:
            return b
        if not b:
            return a
        aw, bw = a.split(), b.split()
        # Some recognizers repeat the end of the previous chunk at the start of the next.
        max_overlap = min(len(aw), len(bw), 8)
        overlap = 0
        for n in range(max_overlap, 0, -1):
            if " ".join(aw[-n:]).casefold() == " ".join(bw[:n]).casefold():
                overlap = n
                break
        return " ".join(aw + bw[overlap:])

    def recognition_worker(self):
        """Recognize queued audio in order and merge nearby chunks by capture time.

        Uses one recognition request per chunk to reduce network latency. The Google
        recognition endpoint still requires internet access and response time varies.
        """
        pending = ""
        pending_capture_at = 0.0
        pending_finished_at = 0.0
        pending_session = -1
        merge_gap = 4.5
        finalize_after = 0.9

        while True:
            try:
                item = self._audio_queue.get(timeout=0.55)
            except queue.Empty:
                if pending and time.monotonic() - pending_finished_at >= finalize_after:
                    final_text, session = pending, pending_session
                    pending = ""
                    pending_capture_at = pending_finished_at = 0.0
                    if session == self._speech_session:
                        self.ui(lambda value=final_text: self.show_speech(value, self.autospeak.get()))
                continue

            try:
                # Timestamp was added by on_audio. Keep compatibility with any queued
                # four-field item left over during a hot reload.
                if len(item) == 5:
                    rec, audio, code, session, captured_at = item
                else:
                    rec, audio, code, session = item
                    captured_at = time.monotonic()

                if session != self._speech_session or self.speaking:
                    continue

                # One network recognition request per phrase is much faster than
                # requesting every alternative and then retrying multiple languages.
                # Keep the selected UI language as the primary recognition language.
                try:
                    text = rec.recognize_google(audio, language=code)
                except sr.UnknownValueError:
                    text = ""
                except Exception as exc:
                    text = ""
                    self.set_status(f"Speech recognition issue: {exc}")

                if text:
                    clean = " ".join(text.split()).strip()
                    same_session = session == pending_session
                    close_in_real_time = (captured_at - pending_capture_at) <= merge_gap
                    if pending and same_session and close_in_real_time:
                        pending = self._join_transcripts(pending, clean)
                    else:
                        if pending and pending_session == self._speech_session:
                            final_text = pending
                            self.ui(lambda value=final_text: self.show_speech(value, self.autospeak.get()))
                        pending = clean
                    pending_capture_at = captured_at
                    pending_finished_at = time.monotonic()
                    pending_session = session
                    self.set_status("Recognizing speech…")

            finally:
                self._audio_queue.task_done()

    def send_typed(self):
        text = self.entry.get().strip()
        if text:
            self.show_speech(text, True)

    def show_speech(self, text, speak):
        if self.last_text:
            self.hist = ([self.last_text] + self.hist)[:3]
        self.last_text = text; self.heard.config(text=text, fg=self.T["fg"]); self.histl.config(text="\n".join(self.hist))
        self.entry.delete(0, "end"); self.entry.insert(0, text)        # lumilipat agad sa Text → Speech
        self.beep()
        if speak:
            self.speak(text)
        self._tp = []; T = self.T
        for w in self.holder.winfo_children():
            w.destroy()
        toks = [w.strip(".,!?;:") for w in text.split()]; toks = [w for w in toks if w]; i = g = 0
        while i < len(toks) and g < 40:
            found = None
            for n in (3, 2, 1):                                  # hal. "I LOVE YOU" bilang isang sign
                ph = " ".join(toks[i:i + n])
                if len(ph) > 1 and self.library.first_image(ph):
                    found = (ph, n); break
            word, p, adv = (found[0], self.library.first_image(found[0]), found[1]) if found else (toks[i], None, 1)
            i += adv; self.tile(word, p, g); g += 1

    def tile(self, word, p, idx):
        T, t = self.T, self.t
        c = tk.Frame(self.holder, bg=T["card2"], highlightthickness=2, highlightbackground=T["accent"] if p else T["card2"])
        c.grid(row=idx // 2, column=idx % 2, padx=7, pady=7, sticky="nsew")
        if p and os.path.exists(p):
            im = Image.open(p); im.thumbnail((150, 150)); ph = ImageTk.PhotoImage(im); self._tp.append(ph)
            tk.Label(c, image=ph, bg=T["card2"]).pack(padx=8, pady=(8, 4))
            tk.Label(c, text=word, font=("Segoe UI", 12, "bold"), fg=T["fg"], bg=T["card2"]).pack(padx=8, pady=(0, 8))
        else:
            tk.Label(c, text=word if len(word) < 11 else word[:10] + "…", font=("Segoe UI", 17, "bold"), fg=T["fg"], bg=T["card2"],
                     width=9, height=2).pack(padx=8, pady=(8, 0))
            tk.Label(c, text=t["nosign"], font=("Segoe UI", 9), fg=T["mute"], bg=T["card2"]).pack()
            self.btn(c, t["addsign"], lambda w=word: self.goto_add(w), T["accent"], "#06121F").pack(fill="x", padx=8, pady=(6, 8))

    def goto_add(self, word):
        self.show_page("lib"); self.lb.selection_clear(0, "end"); self.show_photos(); self.cap_name.set(word)

    def reset_speech(self):
        self.hist, self.last_text = [], ""
        while not self.tq.empty():
            self.tq.get_nowait()
        self.heard.config(text=self.t["say"], fg=self.T["mute"]); self.histl.config(text="")
        for w in self.holder.winfo_children():
            w.destroy()

    # ------------------------------------------------------------------ Sign Library
    def selected_label(self):
        sel = self.lb.curselection()
        return self.lib_labels[sel[0]] if sel else None

    def refresh_library_view(self):
        keep = self.selected_label() if hasattr(self, "lib_labels") else None
        self.lib_labels = self.library.labels(); self.lb.delete(0, "end")
        for i, lab in enumerate(self.lib_labels):
            self.lb.insert("end", f"  {lab}    ·  {self.library.count(lab)}")
            if lab == keep:
                self.lb.selection_set(i); self.lb.see(i)
        self.show_photos()

    def show_photos(self):
        for w in self.strip.winfo_children():
            w.destroy()
        self._thumbs = []; lab = self.selected_label(); T, t = self.T, self.t
        if not lab:
            self.ph_title.config(text=t["photos_of"]); tk.Label(self.strip, text=t["pick"], fg=T["mute"], bg=T["card"]).pack(padx=20, pady=70); return
        self.cap_name.set(lab); self.ph_title.config(text=f"{t['photos_of']} “{lab}”  ·  {self.library.count(lab)}")
        for s in self.library.samples_of(lab):
            p = self.library.image_path(s)
            if not os.path.exists(p):
                continue
            im = Image.open(p); im.thumbnail((120, 120)); ph = ImageTk.PhotoImage(im); self._thumbs.append(ph)
            c = tk.Frame(self.strip, bg=T["card2"]); c.pack(side="left", padx=6, pady=6)
            tk.Label(c, image=ph, bg=T["card2"]).pack(padx=5, pady=(5, 3))
            self.btn(c, t["delp"], lambda s=s: self.delete_photo(s), T["bad"]).pack(fill="x", padx=5, pady=(0, 5))

    def delete_photo(self, s):
        if not messagebox.askyesno(self.t["delp"], self.t["cdelp"]):
            return
        try:
            self.library.samples.remove(s); os.remove(self.library.image_path(s))
        except (ValueError, OSError):
            pass
        self.library.save(); self.refresh_library_view(); self.retrain()

    def delete_sign(self):
        lab = self.selected_label()
        if lab and messagebox.askyesno(self.t["delsign"], self.t["cdel"] % lab):
            self.library.delete_label(lab); self.refresh_library_view(); self.retrain()

    def rename_sign(self):
        lab = self.selected_label()
        if lab:
            new = self.ask_label(lab)
            if new and new != lab:
                self.library.rename_label(lab, new); self.refresh_library_view(); self.retrain()

    def ask_label(self, initial=""):
        n = simpledialog.askstring(self.t["asktitle"], self.t["ask"], initialvalue=initial, parent=self.root)
        return safe_label(n) if n else None

    def add_photos(self):
        if self.busy:
            messagebox.showinfo("…", self.t["busy"]); return
        label = self.ask_label(self.selected_label() or "")
        if not label:
            return
        files = filedialog.askopenfilenames(title=label, filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.webp")])
        if files:
            self.start_import([(label, f) for f in files])

    def import_folder(self):
        if self.busy:
            messagebox.showinfo("…", self.t["busy"]); return
        folder = filedialog.askdirectory()
        if not folder:
            return
        items = []
        for name in sorted(os.listdir(folder)):
            full = os.path.join(folder, name)
            if os.path.isdir(full):
                items += [(safe_label(name), os.path.join(full, f)) for f in sorted(os.listdir(full)) if f.lower().endswith(IMG_EXT)]
            elif name.lower().endswith(IMG_EXT):
                lab = safe_label(os.path.splitext(name)[0].rstrip("0123456789").rstrip(" _-"))
                if lab:
                    items.append((lab, full))
        if items:
            self.start_import(items)

    def start_import(self, items):
        self.busy = True; threading.Thread(target=self.import_worker, args=(items,), daemon=True).start()

    def import_worker(self, items):
        added, skipped = 0, []
        try:
            det = HandDetector(static_image_mode=True, max_hands=2)
        except Exception as exc:
            self.busy = False; self.ui(lambda: messagebox.showerror("MediaPipe", str(exc))); return
        try:
            for i, (label, path) in enumerate(items, 1):
                self.set_status(f"{self.t['scan']} {i}/{len(items)}…")
                try:
                    hands, _ = det.detect(load_image_rgb(path))
                    if not hands:
                        skipped.append(os.path.basename(path)); continue
                    self.library.add(label, hands, source_image_path=path); added += 1
                except Exception:
                    skipped.append(os.path.basename(path))
        finally:
            det.close(); self.library.save(); self.busy = False
        def done():
            self.refresh_library_view(); self.retrain()
            msg = f"{self.t['added']}: {added}"
            if skipped:
                msg += f"\n{self.t['skipped']}: {len(skipped)}\n" + ", ".join(skipped[:8])
            messagebox.showinfo("OK", msg)
        self.ui(done)

    def capture(self, n):
        name = safe_label(self.cap_name.get()) or self.selected_label()
        if not name:
            messagebox.showinfo("…", self.t["needname"]); return
        if not self.engine.running:
            messagebox.showinfo("…", self.t["needcam"]); return
        self.cap_name.set(name); self._cl, self._ok, self._cn = n, 0, name; self.cap_step()

    def cap_step(self):
        if self._cl <= 0:
            self.library.save(); self.refresh_library_view(); self.retrain()
            self.cap_info.config(text=f"{self.t['captured']}: {self._ok} → {self._cn}"); return
        st = self.engine.state()
        if st["hands"] and st["raw"] is not None:
            ok, buf = cv2.imencode(".jpg", st["raw"], [cv2.IMWRITE_JPEG_QUALITY, 90])
            if ok:
                self.library.add(self._cn, st["hands"], image_bytes_jpg=buf.tobytes()); self._ok += 1
        else:
            self.cap_info.config(text=self.t["nohand"])
        self._cl -= 1; self.root.after(180 if self._cl else 10, self.cap_step)

    def retrain(self):
        def work():
            clf = SignClassifier().fit(self.library); self.clf = clf; self.engine.classifier = clf
            txt = f"{len(clf.labels)} {self.t['trained']} · {len(self.library.samples)} {self.t['photos']}" if clf.ready else self.t["nolib"]
            def show():
                try:
                    self.train_info.config(text=txt)
                except tk.TclError:
                    pass
            self.ui(show)
        threading.Thread(target=work, daemon=True).start()

    def test_accuracy(self):
        if not self.clf.ready:
            messagebox.showinfo(self.t["report"], self.t["nolib"]); return
        per, conf = self.clf.evaluate(self.library, self.min_conf.get()); lines, ok_all, tot = [], 0, 0
        for lab in self.library.labels():
            c, n = per.get(lab, [0, 0])
            if n == 0:
                lines.append(f"{lab:<14} - {self.t['fewph']}")
            else:
                lines.append(f"{lab:<14} {c}/{n}  ({100 * c / n:.0f}%)"); ok_all += c; tot += n
        head = f"Overall: {ok_all}/{tot} = {100 * ok_all / tot:.0f}%\n\n" if tot else ""
        body = "\n".join(lines)
        if conf:
            body += f"\n\n{self.t['confus']}:\n" + "\n".join(f"  {a} → {b}: {n}×" for (a, b), n in conf.most_common(8))
        win = tk.Toplevel(self.root); win.title(self.t["report"]); win.geometry("460x520"); win.configure(bg=self.T["card"])
        txt = tk.Text(win, font=("Consolas", 11), wrap="word", bg=self.T["card"], fg=self.T["fg"], bd=0, padx=12, pady=12)
        txt.pack(fill="both", expand=True); txt.insert("1.0", head + body); txt.config(state="disabled")

    # ------------------------------------------------------------------ vision helpers
    def find_face(self, frame):
        g = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY), (0, 0), fx=0.4, fy=0.4)
        fs = self.fd.detectMultiScale(g, 1.2, 5, minSize=(28, 28))
        if len(fs):
            x, y, w, h = max(fs, key=lambda f: f[2] * f[3]); self.face, self.fmiss = (x / .4, y / .4, w / .4, h / .4), 0
        else:
            self.fmiss += 1
            if self.fmiss > 6:
                self.face, self.mood = None, ""

    def find_mood(self, frame):
        """Simpleng mood: ngiti = Happy, kung hindi = Neutral (hindi kayang basahin ang lungkot nang walang trained emotion model)."""
        if not self.face:
            return
        x, y, w, h = [int(v) for v in self.face]
        roi = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)[y + h // 2: y + h, x: x + w]
        if roi.size == 0:
            return
        self.smiles.append(1 if len(self.sd.detectMultiScale(roi, 1.7, 22, minSize=(25, 25))) else 0)
        self.mood = "happy" if sum(self.smiles) >= 2 else "neutral"

    def mood_worker(self):
        """Mood gamit ang MediaPipe FaceMesh (hugis ng bibig) sa hiwalay na thread para hindi bumagal ang camera."""
        fm = None
        try:
            import mediapipe as mp
            fm = mp.solutions.face_mesh.FaceMesh(static_image_mode=False, max_num_faces=1, refine_landmarks=False,
                                                 min_detection_confidence=0.5, min_tracking_confidence=0.5)
        except Exception:
            fm = None                                     # fallback: simpleng smile cascade ng OpenCV
        last = None
        while True:
            time.sleep(0.06)
            fr = self.mood_src
            if fr is None or fr is last or not self.mood_on_val:
                continue
            last = fr
            try:
                if fm is None:
                    self.find_mood(fr); continue
                small = cv2.resize(fr, (320, max(int(320 * fr.shape[0] / fr.shape[1]), 2)))
                res = fm.process(small)
                if res.multi_face_landmarks:
                    self.mmiss = 0; self.set_mood(res.multi_face_landmarks[0].landmark)
                else:
                    self.mmiss += 1
                    if self.mmiss > 10:
                        self.mood, self.mshape = "", None
            except Exception:
                pass

    def set_mood(self, lm):
        P = lambda i: (lm[i].x, lm[i].y)
        dist = lambda a, b: math.hypot(P(a)[0] - P(b)[0], P(a)[1] - P(b)[1])
        mw = dist(61, 291) or 1e-6; width = mw / (dist(234, 454) or 1e-6)             # lapad ng bibig / lapad ng mukha
        lift = ((P(13)[1] + P(14)[1]) / 2 - (P(61)[1] + P(291)[1]) / 2) / mw          # taas ng sulok ng bibig
        self.mshape = (lift, width)
        dl, dw = lift - self.base[0], width - self.base[1]
        m = "happy" if (dw > 0.05 or dl > 0.05 or (dw > 0.03 and dl > 0.03)) else "sad" if (dl < -0.05 and dw < 0.015) else "neutral"
        self.mvotes.append(m); self.mood = max(set(self.mvotes), key=list(self.mvotes).count)

    def calibrate_mood(self):
        if self.mshape:
            self.base = self.mshape; self.mvotes.clear(); self.status.set(self.t["calibok"])
        else:
            self.status.set(self.t["noface"])

    def hand_info(self, hands, fw, fh):
        m = max(fw, fh); pts = [(a[:, 0].mean() * m, a[:, 1].mean() * m) for a in hands]; out = []
        order = sorted(range(len(pts)), key=lambda i: pts[i][0]); t = self.t
        for rank, i in enumerate(order):
            cx, cy = pts[i]
            side = (("left", "right")[rank]) if len(pts) == 2 else ("right" if cx > fw / 2 else "left")   # salamin: kanan = kanang kamay
            v = "up" if cy < fh * .38 else "down" if cy > fh * .68 else "mid"; near = ""
            if self.face:
                x, y, bw, bh = self.face
                if x - bw * .6 < cx < x + bw * 1.6 and y - bh * .6 < cy < y + bh * 1.6:
                    near = " · " + t["near"]
            out.append(f"{t[side]} · {t[v]}{near}")
        return out

    # ------------------------------------------------------------------ render (HUD)
    def dashed(self, d, box, col, w, dash=9):
        x0, y0, x1, y1 = [int(v) for v in box]
        for x in range(x0, x1, dash * 2):
            d.line((x, y0, min(x + dash, x1), y0), fill=col, width=w); d.line((x, y1, min(x + dash, x1), y1), fill=col, width=w)
        for y in range(y0, y1, dash * 2):
            d.line((x0, y, x0, min(y + dash, y1)), fill=col, width=w); d.line((x1, y, x1, min(y + dash, y1)), fill=col, width=w)

    def chip(self, d, x, y, text, col, s):
        f = self.F(14 * s, False); tw = d.textlength(text, font=f); pw, ph = tw + 38 * s, 28 * s
        d.rounded_rectangle((x - pw, y, x, y + ph), ph / 2, fill=(8, 14, 30, 165))
        d.ellipse((x - pw + 11 * s, y + ph / 2 - 4 * s, x - pw + 19 * s, y + ph / 2 + 4 * s), fill=col)
        d.text((x - pw + 27 * s, y + 5 * s), text, font=f, fill=(255, 255, 255, 240))
        return ph + 6 * s

    def render(self, frame, W, H, hands, label, conf, full):
        T, t, now = self.T, self.t, time.monotonic()
        fh, fw = frame.shape[:2]; sc = min(W / fw, H / fh); w, h = max(int(fw * sc), 4), max(int(fh * sc), 4)
        im = Image.fromarray(frame).resize((w, h), Image.BILINEAR); d = ImageDraw.Draw(im, "RGBA")
        s = max(0.8, min(h / 640, 1.15)); acc = tuple(int(T["accent"][i:i + 2], 16) for i in (1, 3, 5))
        on, off = (52, 211, 153, 255), (140, 155, 180, 255); WH = (255, 255, 255, 255)
        if self.face:
            x, y, bw, bh = self.face; k = w / fw
            self.dashed(d, (x * k, y * k, (x + bw) * k, (y + bh) * k), (255, 255, 255, 230), max(int(2 * s), 1))
        if now < self.flash:
            a = int(230 * (self.flash - now))
            for k in range(6):
                d.rectangle((k, k, w - 1 - k, h - 1 - k), outline=acc + (max(a - k * 38, 0),))
        if full:
            d.rounded_rectangle((14 * s, 14 * s, 262 * s, 112 * s), 16 * s, fill=(8, 14, 30, 150))
            d.text((28 * s, 22 * s), t["det"], font=self.F(11 * s), fill=acc + (255,))
            txt = label or ("…" if hands else "—")
            d.text((28 * s, 38 * s), txt, font=self.F((36 if len(txt) < 8 else 26 if len(txt) < 13 else 19) * s), fill=WH)
            d.rounded_rectangle((28 * s, 98 * s, 248 * s, 103 * s), 3 * s, fill=(140, 160, 200, 90))
            if label:
                d.rounded_rectangle((28 * s, 98 * s, (28 + 220 * min(conf, 1)) * s, 103 * s), 3 * s, fill=acc + (255,))
                d.text((196 * s, 22 * s), f"{conf * 100:.0f}%", font=self.F(14 * s), fill=WH)
            d.rounded_rectangle((14 * s, 120 * s, 262 * s, 160 * s), 14 * s, fill=(8, 14, 30, 130))
            d.text((28 * s, 125 * s), t["rd"], font=self.F(9 * s), fill=acc + (255,))
            d.text((28 * s, 136 * s), (" ".join(self.words)[-24:] or "—"), font=self.F(15 * s), fill=WH)
            if self.builder.progress > 0:
                d.rounded_rectangle((14 * s, h - 14 * s, 14 * s + (w - 28 * s) * self.builder.progress, h - 8 * s), 3 * s, fill=acc + (235,))
        elif label:
            d.rounded_rectangle((14 * s, 14 * s, 190 * s, 62 * s), 14 * s, fill=(8, 14, 30, 150))
            d.text((28 * s, 20 * s), f"{label}  {conf * 100:.0f}%", font=self.F(24 * s), fill=WH)
        y = 14 * s
        for txt in self.hand_info(hands, fw, fh):
            y += self.chip(d, w - 14 * s, y, txt, on, s)
        self.chip(d, w - 14 * s, h - 46 * s, f"LIVE · {self.fps:.0f} FPS", on, s)
        ftxt = t["face"] + ((" · " + t[self.mood]) if self.mood and self.mood_on.get() else "")
        self.chip(d, w - 14 * s, y, ftxt, on if (self.face or self.mood) else off, s)
        return ImageTk.PhotoImage(im)

    def poll(self):
        try:
            now = time.monotonic(); st = self.engine.state() if self.engine.running else None
            tgt = {"sign": (self.vbox, self.video), "lib": (self.vbox2, self.video2)}.get(self.page)
            if st and st["frame"] is not None:
                frame, label, conf = st["frame"], st["label"], st["conf"]
                if self.whole.get() and label and len(label) == 1:
                    label = None
                if st["hands"]:
                    self.last_hand = now
                new = frame is not self.last_frame
                if new:
                    self.last_frame = frame; self.fcount += 1
                    dt = now - self._tl; self._tl = now
                    if 0 < dt < 1:
                        self.fps = 0.9 * self.fps + 0.1 / dt if self.fps else 1 / dt
                    if self.fcount % 4 == 0:
                        self.find_face(frame)
                    self.mood_on_val = self.mood_on.get(); self.mood_src = frame
                if self.page == "sign":
                    committed = self.builder.update(label, now)
                    if committed:
                        self.on_word(committed)
                if tgt and (new or now < self.flash):
                    W, H = tgt[0].winfo_width(), tgt[0].winfo_height()
                    if W > 50 and H > 50:
                        self._ph[self.page] = self.render(frame, W, H, st["hands"], label, conf, self.page == "sign"); self._phs.clear()
                        tgt[1].config(image=self._ph[self.page], text="")
                if not self.clf.ready:
                    self.status.set(self.t["nolib"])
            elif not self.engine.running:
                for key, box, lab in (("a", self.vbox, self.video), ("b", self.vbox2, self.video2)):
                    W, H = box.winfo_width(), box.winfo_height()
                    sig = (W, H, self.theme, self.lc)
                    if W > 50 and H > 50 and self._phs.get(key) != sig:
                        self._phs[key] = sig; self._ph["idle" + key] = self.idle(W, H); lab.config(image=self._ph["idle" + key], text="")
                self._sync_cam_buttons()
            if self.words and not self.ended and self.engine.running and now - self.last_hand >= 2.5:
                self.words[-1] += "."; self.ended = True; self.render_sentence()        # auto-punctuation
            if self.page == "speech" and now - self._anim > 0.06:
                self._anim = now; self.anim_speech(now)
            if self.engine.error:
                err, self.engine.error = self.engine.error, None
                self._sync_cam_buttons(); messagebox.showerror("Camera", err)
        except Exception as exc:
            self.status.set(f"UI warning: {exc}")
        self.root.after(12, self.poll)

    def offer_gtts(self):
        if messagebox.askyesno("Filipino voice 🇵🇭", self.t["askgtts"]):
            self.install_gtts()

    def install_gtts(self):
        """Awtomatikong i-install ang gTTS (Filipino voice) - hindi na kailangan ng command."""
        if self.installing:
            return
        self.installing = True; self.set_status("⏳ Installing Filipino voice (gTTS)… " + ("please wait" if self.lc == "en" else "sandali lang"))
        def work():
            global gTTS
            try:
                r = subprocess.run([sys.executable, "-m", "pip", "install", "gTTS"], capture_output=True, text=True, timeout=300,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                if r.returncode == 0:
                    import importlib; importlib.invalidate_caches()
                    from gtts import gTTS as g
                    gTTS = g; self.set_status("✅ " + self.t["gttsok"])
                else:
                    self.set_status("⚠ " + self.t["gttsfail"] + " " + r.stderr.strip()[-80:])
            except Exception as exc:
                self.set_status("⚠ " + self.t["gttsfail"] + f" ({exc})")
            finally:
                self.installing = False
        threading.Thread(target=work, daemon=True).start()

    def tts_state(self, kind, msg=""):
        T, t = self.T, self.t
        txt, col = {"speaking": (f"{t['speaking']} · {msg}", T["accent"]), "ready": (t["tts_ready"], T["mute"]),
                    "error": ("⚠ " + msg[:70], T["bad"])}[kind]
        for w in (getattr(self, "tts_lbl", None), getattr(self, "sign_tts", None)):
            try:
                if w is not None:
                    w.config(text=txt, fg=col)
            except tk.TclError:
                pass

    def step(self, parent, n, title):
        T = self.T; r = tk.Frame(parent, bg=T["card"]); r.pack(fill="x", padx=20, pady=(14, 2))
        tk.Label(r, text=f"0{n}", font=("Consolas", 9, "bold"), fg=T["accent"], bg=T["card2"], padx=8, pady=5).pack(side="left")
        tk.Label(r, text="  " + title, font=("Segoe UI", 10, "bold"), fg=T["fg"], bg=T["card"]).pack(side="left", padx=(5, 0))
        return r

    def accent_line(self):
        T = self.T; cv = tk.Canvas(self.root, height=2, bg=T["bg"], highlightthickness=0); cv.pack(fill="x", padx=18, pady=(0, 10))
        a = tuple(int(T["accent"][i:i + 2], 16) for i in (1, 3, 5)); b_hex = T.get("accent2", T["accent"]); b = tuple(int(b_hex[i:i + 2], 16) for i in (1, 3, 5))
        def draw(e):
            w = max(e.width, 2); m = Image.linear_gradient("L").rotate(90).resize((w, 3))
            cv.img = ImageTk.PhotoImage(Image.composite(Image.new("RGB", (w, 3), b), Image.new("RGB", (w, 3), a), m))
            cv.delete("all"); cv.create_image(0, 0, anchor="nw", image=cv.img)
        cv.bind("<Configure>", draw)

    def borderize(self, w):
        T = self.T
        for c in w.winfo_children():
            if isinstance(c, tk.Frame) and str(c.cget("bg")).lower() == T["card"].lower() and str(w.cget("bg")).lower() == T["bg"].lower():
                c.config(highlightthickness=1, highlightbackground=T["card2"])
            self.borderize(c)

    def idle(self, W, H):
        T, t = self.T, self.t; dark = self.theme == "dark"
        c1, c2 = ((5, 9, 18), (20, 34, 66)) if dark else ((230, 238, 252), (200, 218, 248))
        acc = tuple(int(T["accent"][i:i + 2], 16) for i in (1, 3, 5))
        im = Image.composite(Image.new("RGB", (W, H), c2), Image.new("RGB", (W, H), c1), Image.linear_gradient("L").resize((W, H)))
        d = ImageDraw.Draw(im, "RGBA"); cx, cy = W // 2, H // 2 - 30
        for k, r in enumerate((150, 112, 78)):
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=acc + (80 - k * 18,), width=2)
        d.ellipse((cx - 38, cy - 38, cx + 38, cy + 38), fill=acc + (255,))
        d.polygon([(cx - 11, cy - 18), (cx - 11, cy + 18), (cx + 20, cy)], fill=(6, 18, 31, 255))
        tc = (255, 255, 255, 255) if dark else (16, 33, 63, 255); mc = (143, 163, 196, 255) if dark else (90, 107, 136, 255)
        f1, f2 = self.F(28), self.F(16, False); y = cy + 150
        for txt, f, col in (("SignBridge", f1, tc),) + tuple((ln, f2, mc) for ln in t["camoff"].split("\n")):
            d.text((W / 2 - d.textlength(txt, font=f) / 2, y), txt, font=f, fill=col); y += 38 if f is f1 else 26
        return ImageTk.PhotoImage(im)

    def anim_speech(self, now):
        T = self.T; lis, spk = bool(self.stop_listen), self.speaking
        col = T["accent"] if spk else T["good"] if lis else T["mute"]; on = lis or spk
        pulse = (math.sin(now * 5) + 1) / 2 if on else 0
        o = self.orb; o.delete("all")
        for r in (40, 33):
            rr = r - 4 + pulse * 5; o.create_oval(42 - rr, 42 - rr, 42 + rr, 42 + rr, outline=col, width=2)
        o.create_oval(16, 16, 68, 68, fill=col, outline="")
        o.create_text(42, 42, text="🔊" if spk else "🎙", font=("Segoe UI Emoji", 20), fill="#06121F")
        self.mic_lbl.config(text=self.t["listen"] if lis and not spk else "", fg=col)
        w = self.wave; w.delete("all")
        for i in range(max(w.winfo_width() // 12, 8)):
            h = 3 + (24 * abs(math.sin(now * 5 + i * .55)) * (.55 + .45 * math.sin(now * 1.7 + i * .2)) if on else 0)
            w.create_rectangle(i * 12 + 3, 30 - h, i * 12 + 9, 30 + h, fill=col, outline="")

    def on_close(self):
        try:
            if self.helper:
                self.helper.kill()
        except Exception:
            pass
        try:
            self.listen_stop(); self.engine.stop()
        finally:
            self.root.destroy()


if __name__ == "__main__":
    try:
        import ctypes; ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    r = tk.Tk(); App(r); r.mainloop()
