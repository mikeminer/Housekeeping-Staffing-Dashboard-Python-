"""
Housekeeping Staffing Dashboard (Tkinter) - SINGLE FILE

Aggiornamenti richiesti:
- Colonna ore/minuti nascosta dalla tabella e dal PDF.
- Parametri e impostazioni spostati in una tab chiamata "Tarature".
- Generazione PDF con timestamp data/ora e nome del receptionist.

Dipendenza per PDF:
    pip install reportlab

How to use:
1) Run: python housekeeping_dashboard_UI_PLUS_PDF.py
2) Vai in "Tarature" e imposta hotel, receptionist e parametri
3) Vai in "Report", clicca "Carica XML"
4) Clicca "Calcola"
5) Clicca "Genera PDF"
"""

from __future__ import annotations

import json
import math
import os
import tkinter as tk
from dataclasses import dataclass, asdict, fields
from datetime import datetime
from tkinter import ttk, filedialog, messagebox
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET

CONFIG_FILENAME = "config.json"


# ---------------- SETTINGS ----------------
@dataclass
class Settings:
    hotel_name: str = "My Hotel"
    receptionist_name: str = ""
    minutes_stayover: int = 20
    minutes_departure: int = 40
    minutes_arrival: int = 10
    shift_minutes: int = 420
    efficiency_percent: int = 85

    def clamp(self):
        self.hotel_name = (self.hotel_name or "My Hotel").strip()
        self.receptionist_name = (self.receptionist_name or "").strip()
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
            data = json.load(f)

        # Compatibile anche con vecchi config.json senza receptionist_name
        allowed = {field.name for field in fields(Settings)}
        clean = {k: v for k, v in data.items() if k in allowed}
        return Settings(**clean).clamp()
    except Exception:
        # Silent fallback: non blocca l'app se config.json e' danneggiato
        return Settings()


def save_settings(settings: Settings):
    p = config_path()
    with open(p, "w", encoding="utf-8") as f:
        json.dump(asdict(settings.clamp()), f, indent=2, ensure_ascii=False)


# ---------------- XML / CALCOLO ----------------
def parse_int(v, d=0):
    try:
        if v is None:
            return d
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
            "rooms_morning": rooms_morning,
            "arrivals": arrivals,
            "departures": departures,
            "stayover": stayover,
            "date_obj": parse_date(date),
        })

    return sorted(rows, key=lambda r: r["date_obj"])


def compute(row, s: Settings):
    """
    Restituisce:
    - workload_minutes: minuti lavoro totali, usati internamente
    - staff: numero cameriere necessarie, visibile nel report

    La colonna workload/ore/minuti viene tenuta nascosta nella UI e nel PDF.
    """
    workload = (
        row["stayover"] * s.minutes_stayover +
        row["departures"] * s.minutes_departure +
        row["arrivals"] * s.minutes_arrival
    )
    effective_minutes = s.shift_minutes * (s.efficiency_percent / 100)

    staff = math.ceil(workload / effective_minutes) if workload > 0 and effective_minutes > 0 else 0
    staff = max(staff, 1) if workload > 0 else 0

    return int(workload), int(staff)


# ---------------- INFO TEXTS ----------------
INFO_TEXT = {
    "stayover": (
        "Minuti Stayover\n"
        "Camera occupata che resta in house.\n\n"
        "Pulizia leggera:\n"
        "- rifacimento letto\n"
        "- bagno rapido\n"
        "- riordino\n"
        "- cambio asciugamani, se previsto\n\n"
        "Valore tipico:\n"
        "- 15-25 minuti\n"
        "- Hotel 4 stelle ben organizzato: 20 min"
    ),
    "departure": (
        "Minuti Departure / Checkout\n"
        "Camera in partenza.\n\n"
        "Pulizia completa:\n"
        "- bagno profondo\n"
        "- cambio completo biancheria\n"
        "- controllo minibar\n"
        "- aspirazione / pavimenti\n"
        "- controlli finali\n\n"
        "Valore tipico:\n"
        "- 35-50 minuti\n"
        "- 4 stelle standard: 40 min\n"
        "- Suite/camere grandi: 50-60 min"
    ),
    "arrival": (
        "Minuti Arrival\n"
        "Extra legato all'arrivo.\n\n"
        "Non e' una pulizia completa, ma include:\n"
        "- rifiniture\n"
        "- controlli qualita'\n"
        "- richieste speciali\n"
        "- preparazione VIP\n\n"
        "Valore tipico:\n"
        "- 5-15 minuti\n"
        "- Default: 10 min\n\n"
        "Se non fate extra sugli arrivi, puoi mettere 0."
    ),
    "shift": (
        "Minuti turno reali\n"
        "Tempo reale lavorabile da una cameriera.\n\n"
        "Non e' l'orario teorico, ma quello effettivo.\n"
        "Esempio:\n"
        "- Turno 8 ore = 480 min\n"
        "- pause/briefing/spostamenti/imprevisti = -60 min\n"
        "- minuti reali = 420\n\n"
        "Valore realistico:\n"
        "- 420 minuti, cioe' 7 ore reali\n"
        "- Hotel molto tirati: 390-400"
    ),
    "eff": (
        "Efficienza percentuale\n\n"
        "Serve a stimare quanto del tempo teorico diventa lavoro utile.\n\n"
        "Esempi:\n"
        "- 100% = giornata perfetta teorica\n"
        "- 90% = hotel ben organizzato\n"
        "- 80-85% = realta' molto comune\n"
        "- 70% = caos / staff nuovo / camere lontane\n\n"
        "Nel calcolo:\n"
        "tempo_effettivo = minuti_turno x efficienza / 100\n\n"
        "Esempio:\n"
        "420 x 85% = 357 min reali"
    ),
}


# ---------------- APP ----------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Housekeeping Dashboard")
        self.geometry("1050x640")
        self.minsize(950, 560)

        self.settings = load_settings()

        self.var_hotel = tk.StringVar(value=self.settings.hotel_name)
        self.var_receptionist = tk.StringVar(value=self.settings.receptionist_name)
        self.var_stay = tk.IntVar(value=self.settings.minutes_stayover)
        self.var_dep = tk.IntVar(value=self.settings.minutes_departure)
        self.var_arr = tk.IntVar(value=self.settings.minutes_arrival)
        self.var_shift = tk.IntVar(value=self.settings.shift_minutes)
        self.var_eff = tk.IntVar(value=self.settings.efficiency_percent)

        self.xml_path = None
        self.rows = []  # lista di tuple: (row_dict, workload_minutes, staff)

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.build_ui()

    # ---------- UI ----------
    def build_ui(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.tab_report = ttk.Frame(self.notebook, padding=10)
        self.tab_tarature = ttk.Frame(self.notebook, padding=10)

        self.notebook.add(self.tab_report, text="Report")
        self.notebook.add(self.tab_tarature, text="Tarature")

        self.build_report_tab(self.tab_report)
        self.build_tarature_tab(self.tab_tarature)

    def build_report_tab(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill=tk.X)

        ttk.Button(top, text="Carica XML", command=self.load_xml).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(top, text="Calcola", command=self.calculate).pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="Genera PDF", command=self.generate_pdf).pack(side=tk.LEFT, padx=6)

        self.lbl_xml = ttk.Label(top, text="Nessun file selezionato", foreground="gray")
        self.lbl_xml.pack(side=tk.LEFT, padx=12)

        self.lbl_summary = ttk.Label(parent, text="", foreground="gray")
        self.lbl_summary.pack(fill=tk.X, pady=(10, 6))

        right = ttk.LabelFrame(parent, text="Risultati", padding=10)
        right.pack(fill=tk.BOTH, expand=True)

        # Colonna ore/minuti nascosta: workload resta calcolato internamente ma non viene mostrato.
        cols = ("date", "day", "arr", "dep", "stay", "staff")
        self.tree = ttk.Treeview(right, columns=cols, show="headings", height=18)

        yscroll = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)

        heads = {
            "date": "Data",
            "day": "Giorno",
            "arr": "Arrivi",
            "dep": "Partenze",
            "stay": "Stayover",
            "staff": "Cameriere",
        }

        widths = {
            "date": 90,
            "day": 130,
            "arr": 75,
            "dep": 85,
            "stay": 85,
            "staff": 95,
        }

        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, anchor=tk.CENTER, width=widths[c], stretch=True)

    def build_tarature_tab(self, parent):
        header = ttk.Label(
            parent,
            text="Tarature calcolo cameriere",
            font=("Segoe UI", 14, "bold"),
        )
        header.pack(anchor=tk.W, pady=(0, 10))

        general = ttk.LabelFrame(parent, text="Dati report", padding=10)
        general.pack(fill=tk.X, pady=(0, 12))

        row1 = ttk.Frame(general)
        row1.pack(fill=tk.X, pady=4)
        ttk.Label(row1, text="Hotel:", width=20).pack(side=tk.LEFT)
        ttk.Entry(row1, textvariable=self.var_hotel, width=40).pack(side=tk.LEFT, padx=6)

        row2 = ttk.Frame(general)
        row2.pack(fill=tk.X, pady=4)
        ttk.Label(row2, text="Receptionist:", width=20).pack(side=tk.LEFT)
        ttk.Entry(row2, textvariable=self.var_receptionist, width=40).pack(side=tk.LEFT, padx=6)
        ttk.Label(row2, text="Questo nome verra' stampato nel PDF.", foreground="gray").pack(side=tk.LEFT, padx=8)

        params = ttk.LabelFrame(parent, text="Parametri di calcolo", padding=10)
        params.pack(fill=tk.X)

        self.param_row(params, "Stayover (min)", self.var_stay, "stayover", 0, 1000)
        self.param_row(params, "Departure (min)", self.var_dep, "departure", 0, 1000)
        self.param_row(params, "Arrival (min)", self.var_arr, "arrival", 0, 1000)
        self.param_row(params, "Turno reali (min)", self.var_shift, "shift", 60, 1000)
        self.param_row(params, "Efficienza (%)", self.var_eff, "eff", 10, 150)

        buttons = ttk.Frame(parent)
        buttons.pack(fill=tk.X, pady=12)
        ttk.Button(buttons, text="Salva impostazioni", command=self.save).pack(side=tk.LEFT)

        note = ttk.Label(
            parent,
            text=(
                "Formula: Stayover = Rooms Morning - Departures. "
                "Workload = Stayover x min stayover + Departures x min departure + Arrivals x min arrival. "
                "Cameriere = CEIL(Workload / (Turno x Efficienza%)). "
                "La colonna workload/ore resta nascosta."
            ),
            wraplength=850,
            foreground="gray",
        )
        note.pack(anchor=tk.W, pady=(8, 0))

    def param_row(self, parent, label, var, info_key, from_, to_):
        f = ttk.Frame(parent)
        f.pack(fill=tk.X, pady=5)

        ttk.Label(f, text=label, width=22).pack(side=tk.LEFT)
        ttk.Spinbox(f, from_=from_, to=to_, textvariable=var, width=8).pack(side=tk.LEFT, padx=6)
        ttk.Button(
            f,
            text="(i)",
            width=4,
            command=lambda k=info_key: self.show_info(k),
        ).pack(side=tk.LEFT, padx=4)

    def show_info(self, key):
        txt = INFO_TEXT.get(key, "Nessuna descrizione disponibile.")
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

    # ---------- SETTINGS ----------
    def current_settings(self):
        return Settings(
            hotel_name=self.var_hotel.get(),
            receptionist_name=self.var_receptionist.get(),
            minutes_stayover=parse_int(self.var_stay.get(), 20),
            minutes_departure=parse_int(self.var_dep.get(), 40),
            minutes_arrival=parse_int(self.var_arr.get(), 10),
            shift_minutes=parse_int(self.var_shift.get(), 420),
            efficiency_percent=parse_int(self.var_eff.get(), 85),
        ).clamp()

    def save(self):
        try:
            self.settings = self.current_settings()
            save_settings(self.settings)
            messagebox.showinfo("Salvato", f"Impostazioni salvate in {CONFIG_FILENAME}.")
        except Exception as e:
            messagebox.showerror("Errore", str(e))

    # ---------- REPORT ----------
    def load_xml(self):
        path = filedialog.askopenfilename(
            title="Seleziona file XML",
            filetypes=[("XML", "*.xml *.XML"), ("Tutti i file", "*.*")],
        )
        if not path:
            return
        self.xml_path = path
        self.lbl_xml.config(text=os.path.basename(path), foreground="black")
        self.rows = []
        self.clear_tree()
        self.lbl_summary.config(text="XML caricato. Clicca Calcola per aggiornare i risultati.")

    def clear_tree(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

    def calculate(self):
        if not self.xml_path:
            messagebox.showwarning("Attenzione", "Carica prima un file XML.")
            return

        try:
            self.settings = self.current_settings()
            base = extract_rows(self.xml_path)
        except Exception as e:
            messagebox.showerror("Errore lettura XML", str(e))
            return

        self.clear_tree()
        self.rows = []

        total_arrivals = 0
        total_departures = 0
        total_stayover = 0
        total_staff = 0

        for r in base:
            workload, staff = compute(r, self.settings)
            self.rows.append((r, workload, staff))

            total_arrivals += r["arrivals"]
            total_departures += r["departures"]
            total_stayover += r["stayover"]
            total_staff += staff

            self.tree.insert("", tk.END, values=(
                r["date"],
                r["day"],
                r["arrivals"],
                r["departures"],
                r["stayover"],
                staff,
            ))

        self.lbl_summary.config(
            text=(
                f"Righe: {len(self.rows)} | "
                f"Arrivi totali: {total_arrivals} | "
                f"Partenze totali: {total_departures} | "
                f"Stayover totali: {total_stayover} | "
                f"Cameriere totali: {total_staff}"
            )
        )

    def generate_pdf(self):
        if not self.rows:
            messagebox.showwarning("Attenzione", "Calcola prima i risultati, poi genera il PDF.")
            return

        self.settings = self.current_settings()
        receptionist = self.settings.receptionist_name.strip()
        if not receptionist:
            messagebox.showwarning(
                "Receptionist mancante",
                "Inserisci il nome del receptionist nella tab Tarature prima di generare il PDF.",
            )
            self.notebook.select(self.tab_tarature)
            return

        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import cm
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        except ImportError:
            messagebox.showerror(
                "Modulo mancante",
                "Per generare il PDF installa ReportLab:\n\npip install reportlab",
            )
            return

        now = datetime.now()
        timestamp = now.strftime("%d/%m/%Y %H:%M:%S")
        default_name = f"housekeeping_cameriere_{now.strftime('%Y%m%d_%H%M')}.pdf"

        pdf_path = filedialog.asksaveasfilename(
            title="Salva PDF",
            defaultextension=".pdf",
            initialfile=default_name,
            filetypes=[("PDF", "*.pdf")],
        )
        if not pdf_path:
            return

        try:
            page_size = landscape(A4)
            doc = SimpleDocTemplate(
                pdf_path,
                pagesize=page_size,
                leftMargin=1.0 * cm,
                rightMargin=1.0 * cm,
                topMargin=1.0 * cm,
                bottomMargin=1.0 * cm,
            )

            styles = getSampleStyleSheet()
            story = []

            story.append(Paragraph("Housekeeping - Numero Cameriere Necessarie", styles["Title"]))
            story.append(Spacer(1, 8))

            meta_data = [
                ["Hotel", escape(self.settings.hotel_name)],
                ["Generato da", escape(receptionist)],
                ["Data e ora generazione", timestamp],
                ["File XML", escape(os.path.basename(self.xml_path or ""))],
                [
                    "Tarature",
                    (
                        f"Stayover {self.settings.minutes_stayover} min | "
                        f"Departure {self.settings.minutes_departure} min | "
                        f"Arrival {self.settings.minutes_arrival} min | "
                        f"Turno {self.settings.shift_minutes} min | "
                        f"Efficienza {self.settings.efficiency_percent}%"
                    ),
                ],
            ]
            meta = Table(meta_data, colWidths=[5 * cm, 22 * cm])
            meta.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eeeeee")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(meta)
            story.append(Spacer(1, 12))

            # Tabella senza colonna ore/minuti/workload.
            table_data = [["Data", "Giorno", "Arrivi", "Partenze", "Stayover", "Cameriere"]]

            total_arrivals = 0
            total_departures = 0
            total_stayover = 0
            total_staff = 0

            for r, _workload, staff in self.rows:
                total_arrivals += r["arrivals"]
                total_departures += r["departures"]
                total_stayover += r["stayover"]
                total_staff += staff

                table_data.append([
                    r["date"],
                    r["day"],
                    r["arrivals"],
                    r["departures"],
                    r["stayover"],
                    staff,
                ])

            table_data.append([
                "Totale",
                "",
                total_arrivals,
                total_departures,
                total_stayover,
                total_staff,
            ])

            result_table = Table(
                table_data,
                colWidths=[3.0 * cm, 5.0 * cm, 3.0 * cm, 3.2 * cm, 3.2 * cm, 3.4 * cm],
                repeatRows=1,
            )
            result_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
                ("TOPPADDING", (0, 0), (-1, 0), 7),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#eeeeee")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ]))
            story.append(result_table)
            story.append(Spacer(1, 12))

            formula = (
                "Formula usata: Stayover = max(0, Rooms Morning - Partenze). "
                "Cameriere = CEIL((Stayover x min stayover + Partenze x min departure + Arrivi x min arrival) "
                "/ (Turno minuti x Efficienza / 100)). "
                "La colonna dei minuti/ore di lavoro e' calcolata internamente ma nascosta nel report."
            )
            story.append(Paragraph(escape(formula), styles["BodyText"]))

            def add_footer(canvas, _doc):
                canvas.saveState()
                canvas.setFont("Helvetica", 8)
                width, _height = page_size
                canvas.drawRightString(width - 1.0 * cm, 0.55 * cm, f"Pagina {_doc.page}")
                canvas.drawString(1.0 * cm, 0.55 * cm, f"Generato: {timestamp} - Receptionist: {receptionist}")
                canvas.restoreState()

            doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)

            messagebox.showinfo("PDF creato", f"PDF generato correttamente:\n{pdf_path}")

        except Exception as e:
            messagebox.showerror("Errore PDF", str(e))

    def on_close(self):
        # Auto-save senza popup
        try:
            self.settings = self.current_settings()
            save_settings(self.settings)
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
