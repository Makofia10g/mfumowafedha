"""
Mfumo wa Mapato na Matumizi
----------------------------
Programu hii inakusaidia kufuatilia fedha zako - mapato (pesa inayoingia)
na matumizi (pesa inayotoka) - kwa siku, wiki, na mwezi.

Jinsi ya kuendesha:
    pip install fastapi uvicorn
    uvicorn main:app --reload

Kisha fungua kivinjari: http://127.0.0.1:8000
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Mipangilio ya msingi
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent
DATABASE_PATH = BASE_DIR / "fedha.db"

app = FastAPI(title="Mfumo wa Mapato na Matumizi")


def pata_muunganisho():
    """Inarudisha muunganisho mpya na hifadhidata (database)."""
    muunganisho = sqlite3.connect(DATABASE_PATH)
    muunganisho.row_factory = sqlite3.Row
    return muunganisho


def anzisha_hifadhidata():
    """Inatengeneza jedwali la 'miamala' kama halipo."""
    muunganisho = pata_muunganisho()
    muunganisho.execute(
        """
        CREATE TABLE IF NOT EXISTS miamala (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aina TEXT NOT NULL CHECK(aina IN ('mapato', 'matumizi')),
            kiasi REAL NOT NULL,
            maelezo TEXT,
            tarehe TEXT NOT NULL
        )
        """
    )
    muunganisho.commit()
    muunganisho.close()


anzisha_hifadhidata()


# ---------------------------------------------------------------------------
# Miundo ya data (Pydantic models)
# ---------------------------------------------------------------------------

class MuamalaMpya(BaseModel):
    aina: str          # "mapato" au "matumizi"
    kiasi: float        # kiasi cha fedha (TSh)
    maelezo: str = ""   # maelezo mafupi, mfano: "Mshahara" au "Data ya intaneti"


class Muamala(MuamalaMpya):
    id: int
    tarehe: str


# ---------------------------------------------------------------------------
# Njia za API (endpoints)
# ---------------------------------------------------------------------------

@app.post("/miamala", response_model=Muamala)
def ongeza_muamala(muamala: MuamalaMpya):
    """Ongeza muamala mpya (mapato au matumizi)."""
    if muamala.aina not in ("mapato", "matumizi"):
        raise HTTPException(status_code=400, detail="Aina lazima iwe 'mapato' au 'matumizi'")
    if muamala.kiasi <= 0:
        raise HTTPException(status_code=400, detail="Kiasi lazima kiwe zaidi ya sifuri")

    tarehe_ya_sasa = datetime.now().isoformat(timespec="seconds")
    muunganisho = pata_muunganisho()
    cursor = muunganisho.execute(
        "INSERT INTO miamala (aina, kiasi, maelezo, tarehe) VALUES (?, ?, ?, ?)",
        (muamala.aina, muamala.kiasi, muamala.maelezo, tarehe_ya_sasa),
    )
    muunganisho.commit()
    muamala_id = cursor.lastrowid
    muunganisho.close()

    return Muamala(id=muamala_id, tarehe=tarehe_ya_sasa, **muamala.dict())


@app.get("/miamala", response_model=list[Muamala])
def orodha_ya_miamala(kipindi: str = "yote"):
    """
    Orodhesha miamala. `kipindi` inaweza kuwa: 'leo', 'wiki', 'mwezi', au 'yote'.
    """
    muunganisho = pata_muunganisho()
    tarehe_ya_mwanzo = _tarehe_ya_mwanzo_kwa_kipindi(kipindi)

    if tarehe_ya_mwanzo:
        safu = muunganisho.execute(
            "SELECT * FROM miamala WHERE tarehe >= ? ORDER BY tarehe DESC",
            (tarehe_ya_mwanzo.isoformat(timespec="seconds"),),
        ).fetchall()
    else:
        safu = muunganisho.execute(
            "SELECT * FROM miamala ORDER BY tarehe DESC"
        ).fetchall()

    muunganisho.close()
    return [dict(row) for row in safu]


@app.delete("/miamala/{muamala_id}")
def futa_muamala(muamala_id: int):
    """Futa muamala mmoja kwa kutumia id yake."""
    muunganisho = pata_muunganisho()
    matokeo = muunganisho.execute("DELETE FROM miamala WHERE id = ?", (muamala_id,))
    muunganisho.commit()
    muunganisho.close()

    if matokeo.rowcount == 0:
        raise HTTPException(status_code=404, detail="Muamala haujapatikana")
    return {"ujumbe": "Muamala umefutwa"}


@app.get("/muhtasari")
def muhtasari(kipindi: str = "leo"):
    """
    Inarudisha jumla ya mapato, matumizi, na salio kwa kipindi husika.
    `kipindi`: 'leo', 'wiki', 'mwezi', au 'yote'.
    """
    muunganisho = pata_muunganisho()
    tarehe_ya_mwanzo = _tarehe_ya_mwanzo_kwa_kipindi(kipindi)

    hoja_msingi = "SELECT aina, SUM(kiasi) as jumla FROM miamala"
    vigezo = ()
    if tarehe_ya_mwanzo:
        hoja_msingi += " WHERE tarehe >= ?"
        vigezo = (tarehe_ya_mwanzo.isoformat(timespec="seconds"),)
    hoja_msingi += " GROUP BY aina"

    safu = muunganisho.execute(hoja_msingi, vigezo).fetchall()
    muunganisho.close()

    matokeo = {"mapato": 0.0, "matumizi": 0.0}
    for row in safu:
        matokeo[row["aina"]] = row["jumla"]

    matokeo["salio"] = matokeo["mapato"] - matokeo["matumizi"]
    matokeo["kipindi"] = kipindi
    return matokeo


def _tarehe_ya_mwanzo_kwa_kipindi(kipindi: str):
    """Husaidia kukokotoa tarehe ya mwanzo kulingana na kipindi kilichoombwa."""
    sasa = datetime.now()
    if kipindi == "leo":
        return sasa.replace(hour=0, minute=0, second=0, microsecond=0)
    if kipindi == "wiki":
        return sasa - timedelta(days=7)
    if kipindi == "mwezi":
        return sasa - timedelta(days=30)
    return None  # "yote" - hakuna kichujio


# ---------------------------------------------------------------------------
# Kutoa faili za frontend (HTML/CSS/JS)
# ---------------------------------------------------------------------------

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/")
def ukurasa_wa_mwanzo():
    return FileResponse(BASE_DIR / "static" / "index.html")
