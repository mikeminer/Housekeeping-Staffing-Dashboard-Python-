"""
Housekeeping Staffing Dashboard (Tkinter) - SINGLE FILE (UI IMPROVED)

Updates:
- Narrower table columns (more compact layout)
- Info popup for EACH parameter (Stayover, Departure, Arrival, Turno, Efficienza)
- Settings persist in config.json (auto-save on exit + manual save button)

How to use:
1) Run: python housekeeping_dashboard_UI_PLUS.py
2) Click "Carica XML", pick your XML
3) Set parameters (use the (i) buttons for explanations)
4) Click "Calcola"
"""

from __future__ import annotations

import json
import math
import os
import tkinter as tk
from dataclasses import dataclass, asdict
from datetime import datetime
from tkinter import ttk, filedialog, messagebox
import xml.etree.ElementTree as ET

CONFIG_FILENAME = "config.json"


# ---------------- SETTINGS ----------------
@dataclass
class Settings:
    hotel_name: str = "My Hotel"
    minutes_stayover: int = 20
    minutes_departure: int = 40
    minutes_arrival: int = 10
    shift_minutes: int = 420
    efficiency_percent: int = 85

    def clamp(self):
        self.hotel_name = (self.hotel_name or "My Hotel").strip()
        self.minutes_stayover = max(0, int(self.minutes_stayover))
        self.minutes_departure = max(0, int(self.minutes_departure))
        self.minutes_arrival = max(0, int(self.minutes_arrival))
        self.shift_minutes = max(60, int(self.shift_minutes))
        self.efficiency_percent = max(10, min(150, int(self.efficiency_percent)))
        return self


def config_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILENAME)


def load_settings():
    p = config_path()
    if not os.path.exists(p):
        return Settings()
    try:
        with open(p, "r", encoding="utf-8") as f:
            return Settings(**json.load(f)).clamp()
    except Exception:
        # Silent fallback (no popup on startup)
        return Settings()


def save_settings(settings: Settings):
    p = config_path()
    with open(p, "w", encoding="utf-8") as f:
        json.dump(asdict(settings.clamp()), f, indent=2, ensure_ascii=False)


# ---------------- XML ----------------
def parse_int(v, d=0):
    try:
        return int(str(v).strip())
    except Exception:
        return d


def parse_date(s):
    return datetime.strptime(s.strip(), "%d/%m/%y")


def extract_rows(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    rows = []
    for n in root.findall(".//G_CONSIDERED_DATE"):
        date = n.findtext("C_DATE")
        if not date:
            continue

        rooms_morning = parse_int(n.findtext("ROOMS_MORNING"))
        departures = parse_int(n.findtext("DEPARTURE_ROOM"))
        arrivals = parse_int(n.findtext("ARRIVAL_ROOM"))

        stayover = max(0, rooms_morning - departures)

        rows.append({
            "date": date.strip(),
            "day": (n.findtext("DAY_DESCRIPTION", "") or "").strip(),
            "arrivals": arrivals,
            "departures": departures,
            "stayover": stayover,
            "date_obj": parse_date(date)
        })

    return sorted(rows, key=lambda r: r["date_obj"])


def compute(row, s: Settings):
    workload = (
        row["stayover"] * s.minutes_stayover +
        row["departures"] * s.minutes_departure +
        row["arrivals"] * s.minutes_arrival
    )
    eff_minutes = s.shift_minutes * (s.efficiency_percent / 100)
    staff = math.ceil(workload / eff_minutes) if workload > 0 else 0
    staff = max(staff, 1) if workload > 0 else 0
    return int(workload), int(staff)


# ---------------- INFO TEXTS ----------------
INFO_TEXT = {
    "stayover": (
        "1️⃣ Minuti Stayover\n"
        "👉 Camera occupata che resta in house\n\n"
        "Pulizia leggera:\n"
        "• rifacimento letto\n"
        "• bagno rapido\n"
        "• riordino\n"
        "• cambio asciugamani (a volte)\n\n"
        "📌 Valore tipico:\n"
        "• 15–25 minuti\n"
        "• Hotel 4★ ben organizzato: 20 min (ottimo default)"
    ),
    "departure": (
        "2️⃣ Minuti Departure (Checkout)\n"
        "👉 Camera in partenza\n\n"
        "Pulizia completa:\n"
        "• bagno profondo\n"
        "• cambio completo biancheria\n"
        "• controllo minibar\n"
        "• aspirazione / pavimenti\n"
        "• controlli finali\n\n"
        "📌 Valore tipico:\n"
        "• 35–50 minuti\n"
        "• 4★ standard: 40 min\n"
        "• Suite/camere grandi: 50–60 min"
    ),
    "arrival": (
        "3️⃣ Minuti Arrival\n"
        "👉 Extra legato all’arrivo\n\n"
        "Non è una pulizia completa, ma:\n"
        "• rifiniture\n"
        "• controlli qualità\n"
        "• richieste speciali\n"
        "• preparazione VIP\n\n"
        "📌 Valore tipico:\n"
        "• 5–15 minuti\n"
        "• Default sensato: 10 min\n\n"
        "👉 Se non fate extra sugli arrivi: puoi mettere 0."
    ),
    "shift": (
        "4️⃣ Minuti Turno\n"
        "👉 Tempo reale lavorabile da una cameriera\n\n"
        "NON è l’orario teorico (8 ore), ma quello effettivo:\n"
        "Esempio:\n"
        "• Turno 8 ore = 480 min\n"
        "• Pause/briefing/spostamenti/imprevisti → −60 min\n\n"
        "📌 Valore realistico:\n"
        "• 420 minuti (7 ore reali)\n"
        "• Hotel molto tirati: 390–400\n\n"
        "Questo valore è strategico: cambia subito le cameriere necessarie."
    ),
    "eff": (
        "⚙️ Cos’è l’Efficienza (%)\n\n"
        "Serve a stimare quanto del tempo teorico diventa lavoro utile:\n\n"
        "Esempi:\n"
        "• 100% → giornata perfetta (teorico)\n"
        "• 90% → hotel ben organizzato\n"
        "• 80–85% → realtà molto comune\n"
        "• 70% → caos / staff nuovo / camere lontane\n\n"
        "Nel calcolo:\n"
        "tempo_effettivo = minuti_turno × (efficienza / 100)\n\n"
        "Esempio:\n"
        "• 420 × 80% = 336 min reali\n"
        "• 420 × 90% = 378 min reali\n\n"
        "👉 Cambia direttamente il numero di cameriere consigliate."
    ),
}


# ---------------- APP ----------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Housekeeping Dashboard")
        self.geometry("1020x620")
        self.minsize(920, 540)

        self.settings = load_settings()

        self.var_hotel = tk.StringVar(value=self.settings.hotel_name)
        self.var_stay = tk.IntVar(value=self.settings.minutes_stayover)
        self.var_dep = tk.IntVar(value=self.settings.minutes_departure)
        self.var_arr = tk.IntVar(value=self.settings.minutes_arrival)
        self.var_shift = tk.IntVar(value=self.settings.shift_minutes)
        self.var_eff = tk.IntVar(value=self.settings.efficiency_percent)

        self.xml_path = None
        self.rows = []

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.build_ui()

    def build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Hotel:", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        ttk.Entry(top, textvariable=self.var_hotel, width=28).pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="Salva impostazioni", command=self.save).pack(side=tk.LEFT)

        body = ttk.Frame(self, padding=10)
        body.pack(fill=tk.BOTH, expand=True)

        left = ttk.LabelFrame(body, text="Parametri", padding=10)
        left.pack(side=tk.LEFT, fill=tk.Y)

        self.param_row(left, "Stayover (min)", self.var_stay, "stayover")
        self.param_row(left, "Departure (min)", self.var_dep, "departure")
        self.param_row(left, "Arrival (min)", self.var_arr, "arrival")
        self.param_row(left, "Turno reali (min)", self.var_shift, "shift")
        self.param_row(left, "Efficienza (%)", self.var_eff, "eff")

        ttk.Separator(left, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        ttk.Button(left, text="Carica XML", command=self.load_xml).pack(fill=tk.X, pady=4)
        ttk.Button(left, text="Calcola", command=self.calculate).pack(fill=tk.X, pady=4)

        self.lbl_xml = ttk.Label(left, text="Nessun file selezionato", wraplength=240, foreground="gray")
        self.lbl_xml.pack(fill=tk.X, pady=(8, 0))

        right = ttk.LabelFrame(body, text="Risultati (colonne compatte)", padding=10)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

        cols = ("date", "day", "arr", "dep", "stay", "work", "staff")
        self.tree = ttk.Treeview(right, columns=cols, show="headings", height=18)
        self.tree.pack(fill=tk.BOTH, expand=True)

        heads = {
            "date": "Data",
            "day": "Giorno",
            "arr": "Arr",
            "dep": "Dep",
            "stay": "Stay",
            "work": "Min",
            "staff": "HK",
        }

        # Narrower widths
        widths = {
            "date": 78,
            "day": 110,
            "arr": 48,
            "dep": 48,
            "stay": 55,
            "work": 60,
            "staff": 55,
        }

        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, anchor=tk.CENTER, width=widths[c], stretch=False)

        # Optional: allow horizontal scroll if window is tight
        xscroll = ttk.Scrollbar(right, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(xscrollcommand=xscroll.set)
        xscroll.pack(fill=tk.X)

    def param_row(self, parent, label, var, info_key):
        f = ttk.Frame(parent)
        f.pack(fill=tk.X, pady=4)

        ttk.Label(f, text=label).pack(side=tk.LEFT)

        ttk.Spinbox(f, from_=0, to=1000, textvariable=var, width=6).pack(side=tk.RIGHT)

        ttk.Button(
            f,
            text="(i)",
            width=4,
            command=lambda k=info_key: self.show_info(k)
        ).pack(side=tk.RIGHT, padx=(6, 6))

    def show_info(self, key):
        txt = INFO_TEXT.get(key, "Nessuna descrizione disponibile.")
        # Use a Toplevel popup for rich multi-line text
        win = tk.Toplevel(self)
        win.title("Info parametro")
        win.geometry("520x420")
        win.transient(self)
        win.grab_set()

        frm = ttk.Frame(win, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        t = tk.Text(frm, wrap="word", height=18)
        t.pack(fill=tk.BOTH, expand=True)
        t.insert("1.0", txt)
        t.config(state="disabled")

        btns = ttk.Frame(frm)
        btns.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btns, text="Chiudi", command=win.destroy).pack(side=tk.RIGHT)

    def current_settings(self):
        return Settings(
            hotel_name=self.var_hotel.get(),
            minutes_stayover=int(self.var_stay.get()),
            minutes_departure=int(self.var_dep.get()),
            minutes_arrival=int(self.var_arr.get()),
            shift_minutes=int(self.var_shift.get()),
            efficiency_percent=int(self.var_eff.get()),
        ).clamp()

    def save(self):
        try:
            self.settings = self.current_settings()
            save_settings(self.settings)
            messagebox.showinfo("Salvato", f"Impostazioni salvate in {CONFIG_FILENAME}.")
        except Exception as e:
            messagebox.showerror("Errore", str(e))

    def load_xml(self):
        path = filedialog.askopenfilename(
            title="Seleziona file XML",
            filetypes=[("XML", "*.xml *.XML"), ("Tutti i file", "*.*")]
        )
        if not path:
            return
        self.xml_path = path
        self.lbl_xml.config(text=os.path.basename(path), foreground="black")

    def calculate(self):
        if not self.xml_path:
            messagebox.showwarning("Attenzione", "Carica prima un file XML.")
            return

        self.settings = self.current_settings()
        base = extract_rows(self.xml_path)

        for i in self.tree.get_children():
            self.tree.delete(i)

        self.rows = []
        for r in base:
            w, staff = compute(r, self.settings)
            self.rows.append((r, w, staff))
            self.tree.insert("", tk.END, values=(
                r["date"],
                r["day"],
                r["arrivals"],
                r["departures"],
                r["stayover"],
                w,
                staff
            ))

    def on_close(self):
        # Auto-save without popup
        try:
            self.settings = self.current_settings()
            save_settings(self.settings)
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
