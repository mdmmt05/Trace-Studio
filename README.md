# 🏁 Trace Studio

> Analisi locale di sessioni di guida da data logger **Trace** (ESP32-S3).

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Plotly](https://img.shields.io/badge/Plotly-5.22%2B-3F4F75?logo=plotly&logoColor=white)](https://plotly.com/)
[![Folium](https://img.shields.io/badge/Folium-0.16%2B-77B829)](https://python-visualization.github.io/folium/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Trace Studio è un'applicazione **Streamlit** completamente locale per l'analisi di sessioni di guida registrate con il data logger Trace su ESP32-S3. Carica un singolo file CSV, ottieni in pochi secondi dashboard di sintesi, grafici temporali sincronizzati, mappa GNSS colorata e metriche di performance come tempi di accelerazione e friction circle.

---

## Sommario

- [Funzionalità](#funzionalità)
- [Architettura del progetto](#architettura-del-progetto)
- [Requisiti](#requisiti)
- [Installazione](#installazione)
- [Avvio](#avvio)
- [Formato CSV atteso](#formato-csv-atteso)
- [Struttura dei dati derivati](#struttura-dei-dati-derivati)
- [Colonne derivate dalla pipeline](#colonne-derivate-dalla-pipeline)
- [Eseguire i test](#eseguire-i-test)
- [Limitazioni note](#limitazioni-note)
- [Roadmap](#roadmap)
- [Contribuire](#contribuire)
- [Licenza](#licenza)

---

## Funzionalità

### Dashboard di sintesi
Metriche chiave a colpo d'occhio: durata sessione, numero campioni, distanza (OBD e GNSS), velocità massima, RPM massimo, accelerazioni di picco, altitudine, marcia stimata. Un pannello warning tecnici segnala automaticamente dati mancanti, gap di campionamento, bassa copertura GNSS e qualità di sincronizzazione.

### Grafici temporali sincronizzati
Selezione multipla dei canali telemetrici (velocità, RPM, throttle, accelerazioni, rollio, beccheggio, pendenza, heading, yaw rate, jerk, curvatura, marcia). Tutti i sottografici condividono l'asse X (`time_s`), con zoom e pan sincronizzati e hover unificato (`x unified`). Un cursore temporale tramite slider mostra una linea verticale sull'istante selezionato e i valori del campione più vicino nel pannello laterale.

### Mappa GNSS raw con percorso colorato
Il tracciato GPS viene visualizzato su OpenStreetMap senza map-matching. Il colore di ogni segmento riflette il valore di un canale telemetrico scelto dall'utente (velocità, RPM, throttle, accelerazioni, pendenza, jerk, curvatura, marcia). Marker inizio/fine con popup, marker cursore sincronizzato con lo slider dei grafici e click sulla mappa per spostare il cursore al punto GNSS più vicino. Downsampling automatico per sessioni con più di 5.000 segmenti.

### Analisi di performance
- **Tempi di accelerazione**: 0–50 km/h, 0–100 km/h, 80–120 km/h (misurazione del passaggio più veloce nell'intera sessione).
- **Frenata**: decelerazione massima istantanea in G, istante e velocità al momento del picco.
- **Accelerazione laterale**: picco assoluto in G.
- **Durate soglia**: tempo trascorso oltre una soglia di RPM, throttle e accelerazione laterale configurabili.
- **Friction circle**: scatter plot accelerazione longitudinale vs laterale, colorato per velocità, con cerchi di riferimento a 0.3 g, 0.6 g e 1.0 g.

### Preview dati e catalogo colonne
Anteprima del DataFrame grezzo e derivato con tipi, unità e descrizioni di ogni colonna.

### Debug sessione
Report di validazione JSON, metriche di sessione, warning tecnici e tipi di colonna.

---

## Architettura del progetto

```
trace_studio/
│
├── app.py                  # Entry point Streamlit, routing tab e orchestrazione
│
├── config.py               # Costanti globali (colori, conversioni, titoli)
├── schema.py               # Definizione colonne attese, unità, descrizioni e validazione CSV
│
├── importer.py             # Caricamento, pulizia e validazione del file CSV
├── processing.py           # Pipeline di normalizzazione e derivazione colonne
├── metrics.py              # Calcolo metriche di sessione (durata, distanza, velocità, ecc.)
├── performance.py          # Metriche prestazionali (tempi 0-100, friction circle, ecc.)
├── warnings.py             # Warning tecnici automatici sulla qualità dei dati
│
├── charts.py               # Grafici Plotly (serie temporali sincronizzate)
├── map_view.py             # Mappa Folium con percorso colorato e marker cursore
├── cursor.py               # Gestione centralizzata del cursore temporale globale
│
├── ui.py                   # Tutti i componenti UI Streamlit (dashboard, tab, ecc.)
├── theme.py                # CSS e styling dark/motorsport, brand sidebar
│
└── __init__.py
```

Il flusso di dati è sempre unidirezionale:

```
CSV  →  importer  →  processing  →  metrics / warnings / performance
                                 →  charts / map_view / ui
```

---

## Requisiti

- **Python 3.11** o superiore
- Connessione Internet attiva per il caricamento dei tile OpenStreetMap nella scheda Mappa

Dipendenze Python (gestite da `requirements.txt`):

| Pacchetto | Versione minima | Utilizzo |
|---|---|---|
| `streamlit` | 1.35 | Framework UI |
| `pandas` | 2.2 | Manipolazione dati |
| `numpy` | 1.26 | Calcoli numerici |
| `plotly` | 5.22 | Grafici temporali interattivi |
| `folium` | 0.16 | Mappa GNSS interattiva |
| `streamlit-folium` | 0.20 | Integrazione Folium in Streamlit |
| `branca` | 0.7 | Colormaps per la mappa |

---

## Installazione

Le istruzioni seguenti si riferiscono a Windows (PowerShell). Su macOS/Linux il processo è analogo con `/` al posto di `\`.

**1. Clona il repository**

```powershell
git clone https://github.com/mdmmt05/trace-studio.git
cd trace-studio
```

**2. Crea un ambiente virtuale**

```powershell
python -m venv .venv
```

**3. Attiva l'ambiente virtuale**

```powershell
# PowerShell
.venv\Scripts\Activate.ps1

# Prompt dei comandi
.venv\Scripts\activate.bat

# macOS / Linux
source .venv/bin/activate
```

**4. Installa le dipendenze**

```powershell
pip install -r requirements.txt
```

---

## Avvio

```powershell
streamlit run app.py
```

L'app si aprirà automaticamente nel browser all'indirizzo `http://localhost:8501`.

Dalla **sidebar** carica un file CSV Trace, poi naviga tra le schede:

| Scheda | Contenuto |
|---|---|
| **Dashboard** | Metriche chiave e warning tecnici |
| **Grafici** | Serie temporali sincronizzate con cursore |
| **Mappa** | Percorso GNSS raw con colore telemetrico |
| **Performance** | Tempi di accelerazione, frenata, friction circle |
| **Dati** | Anteprima del DataFrame normalizzato |
| **Colonne** | Catalogo colonne con unità e tipo |
| **Debug** | Report validazione, metriche raw, tipi colonne |

### Shortcut da tastiera

| Tasto | Azione |
|---|---|
| `Ctrl+R` | Ricarica app/browser |
| Drag sui grafici | Zoom temporale |
| Doppio click sui grafici | Reset zoom Plotly |
| Click sulla mappa | Sposta cursore al punto GNSS più vicino |

---

## Formato CSV atteso

Il file CSV deve contenere esattamente le seguenti colonne (l'ordine non è rilevante; colonne aggiuntive vengono tollerate e conservate).

| Colonna | Tipo | Descrizione |
|---|---|---|
| `timestamp_utc_str` | stringa | Etichetta UTC leggibile (non usata come asse temporale) |
| `lat`, `lon` | float | Coordinate GNSS |
| `alt_m` | float | Altitudine (m) |
| `sat`, `hdop` | float | Qualità segnale GNSS |
| `speed_obd_kmh` | float | Velocità OBD-II (km/h) |
| `acc_lon_G`, `acc_lat_G` | float | Accelerazioni (G) |
| `roll_deg`, `pitch_deg`, `slope_deg`, `slope_confidence` | float | Assetto veicolo |
| `heading_deg`, `yawRate_dps`, `heading_confidence` | float | Direzione e imbardata |
| `rpm`, `load_pct`, `throttle_pct` | float | Dati motore OBD-II |
| `estimated_gear` | int | Marcia stimata |
| `t_mono_us` | int | Timer monotono µs — **asse temporale principale** |
| `utc_epoch_us` | int | Epoch UTC µs (riferimento) |
| `utc_valid`, `sync_quality` | int | Validità e qualità sincronizzazione |
| `imu_t_us`, `gnss_t_us`, `obd_speed_t_us` | int | Timestamp sorgenti dati |
| `imu_age_ms`, `gnss_age_ms`, `obd_speed_age_ms` | int | Età dei dati al momento del log (ms) |

> **Nota importante:** l'asse temporale primario è `t_mono_us`, non `timestamp_utc_str` né `utc_epoch_us`. La pipeline calcola `time_s` come secondi trascorsi dal primo campione valido.

Un file CSV di esempio per test è disponibile in `trace_dummy_log.csv` (1.000 campioni a ~2 Hz, sessione simulata su circuito urbano).

---

## Colonne derivate dalla pipeline

`processing.normalize_trace_data()` aggiunge le seguenti colonne al DataFrame originale senza modificare le colonne raw.

| Colonna derivata | Unità | Descrizione |
|---|---|---|
| `time_s` | s | Secondi trascorsi da inizio sessione |
| `sample_dt_s` | s | Intervallo tra campioni consecutivi |
| `speed_mps` | m/s | Velocità convertita da `speed_obd_kmh` |
| `acc_lon_mps2`, `acc_lat_mps2` | m/s² | Accelerazioni convertite da G |
| `distance_from_speed_m` | m | Distanza cumulativa da integrazione rettangolare OBD |
| `gnss_step_distance_m` | m | Distanza haversine passo-passo GNSS |
| `distance_from_gnss_m` | m | Distanza cumulativa GNSS |
| `distance_m` | m | Distanza canonica (GNSS se plausibile, altrimenti OBD) |
| `distance_km` | km | `distance_m` in chilometri |
| `acc_lon_G_filt`, `acc_lat_G_filt` | G | Accelerazioni filtrate (mediana mobile, finestra 5) |
| `acc_lon_mps2_filt`, `acc_lat_mps2_filt` | m/s² | Accelerazioni filtrate in unità SI |
| `jerk_lon_mps3`, `jerk_lat_mps3` | m/s³ | Jerk longitudinale e laterale da acc filtrata |
| `curvature_1pm` | 1/m | Curvatura da yaw rate (fallback: derivata heading) |
| `abs_curvature_1pm` | 1/m | Curvatura assoluta |
| `curve_radius_m` | m | Raggio di curvatura (NaN oltre 10 km) |
| `valid_position` | bool | Vero se lat/lon sono finiti e non entrambi zero |
| `valid_time` | bool | Vero se `t_mono_us` e `time_s` sono finiti |

---

## Eseguire i test

```powershell
python -m pytest tests/ -v
```

---

## Limitazioni note

- **Nessun map-matching**: il percorso segue le coordinate GNSS raw e può apparire staccato dalla carreggiata reale.
- **Distanza da velocità**: usa integrazione rettangolare semplice (sovrastima in frenata, sottostima in accelerazione).
- **Distanza da GNSS**: formula haversine senza correzione per l'altitudine.
- **Curvatura**: approssimata da yaw rate o derivata dell'heading; non è validata contro la geometria stradale reale.
- **Tempi di accelerazione 0-x**: rilevati solo se la sessione contiene il transiente da fermo (velocità ≤ 3 km/h). Sessioni che iniziano già in moto non producono un valore.
- **Mappa**: richiede connessione Internet per caricare i tile OpenStreetMap.
- **Sessione singola**: non è ancora possibile confrontare due o più sessioni sullo stesso grafico.
- **Nessun salvataggio persistente**: nessun database, nessun export Parquet o PDF.

---

## Roadmap

Le fasi già implementate sono contrassegnate con ✅.

| Fase | Descrizione | Stato |
|---|---|---|
| 1–2 | Caricamento CSV, validazione schema, normalizzazione, metriche base | ✅ |
| 3 | Dashboard di sintesi con warning tecnici | ✅ |
| 4 | Grafici temporali sincronizzati con cursore | ✅ |
| 5 | Mappa GNSS raw con percorso colorato | ✅ |
| 6 | Cursor centralizzato e sincronizzazione grafici/mappa | ✅ |
| 7 | Canali derivati (jerk, curvatura, raggio, acc filtrate) | ✅ |
| 8 | Catalogo colonne e scheda Debug | ✅ |
| 9 | Analisi performance (tempi, friction circle, soglie) | ✅ |
| 10 | Confronto multi-sessione | ⬜ |
| 11 | Export report PDF / Parquet | ⬜ |
| 12 | Map-matching (OSRM / Valhalla) | ⬜ |
| 13 | Database locale sessioni | ⬜ |
| 14 | Annotazioni manuali su grafici e mappa | ⬜ |

---

## Contribuire

Pull request e segnalazioni di bug sono benvenuti. Prima di aprire una PR:

1. Crea un branch a partire da `main`: `git checkout -b feature/nome-feature`.
2. Segui le convenzioni di codice esistenti (type hints, docstring, gestione difensiva dei NaN).
3. Aggiungi o aggiorna i test in `tests/` se la modifica riguarda la pipeline dati.
4. Verifica che `pytest tests/ -v` passi senza errori.
5. Apri la PR descrivendo cosa cambia e perché.

---

## Licenza

Distribuito sotto licenza **MIT**. Vedi [`LICENSE`](LICENSE) per i dettagli.

---

<div align="center">
  Fatto con ❤️ per l'analisi telemetrica su pista e strada.
</div>
