"""
Mfumo wa Mapato na Matumizi (Toleo la PostgreSQL)
--------------------------------------------------
Toleo hili linatumia PostgreSQL (hifadhidata ya kudumu) badala ya SQLite,
ili data isipotee programu ikianzishwa upya kwenye Render.

Jinsi ya kuendesha kwa ndani (local):
    pip install -r requirements.txt
    (Weka DATABASE_URL kwenye mazingira yako - angalia README.md)
    uvicorn main:app --reload

Kwenye Render, DATABASE_URL tayari imewekwa kama Environment Variable.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Mipangilio ya msingi
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent
DATABASE_URL = os.environ.get("DATABASE_URL")

app = FastAPI(title="Mfumo wa Mapato na Matumizi")


def pata_muunganisho():
    """Inarudisha muunganisho mpya na hifadhidata ya PostgreSQL."""
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL haijawekwa. Weka kwenye Environment Variables (Render) "
            "au kwenye mazingira yako ya ndani."
        )
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def anzisha_hifadhidata():
    """Inatengeneza jedwali la 'miamala' kama halipo."""
    muunganisho = pata_muunganisho()
    cursor = muunganisho.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS miamala (
            id SERIAL PRIMARY KEY,
            aina TEXT NOT NULL CHECK(aina IN ('mapato', 'matumizi')),
            kiasi REAL NOT NULL,
            maelezo TEXT,
            tarehe TEXT NOT NULL
        )
        """
    )
    muunganisho.commit()
    cursor.close()
    muunganisho.close()


@app.on_event("startup")
def wakati_wa_kuanza():
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
    cursor = muunganisho.cursor()
    cursor.execute(
        "INSERT INTO miamala (aina, kiasi, maelezo, tarehe) VALUES (%s, %s, %s, %s) RETURNING id",
        (muamala.aina, muamala.kiasi, muamala.maelezo, tarehe_ya_sasa),
    )
    muamala_id = cursor.fetchone()["id"]
    muunganisho.commit()
    cursor.close()
    muunganisho.close()

    return Muamala(id=muamala_id, tarehe=tarehe_ya_sasa, **muamala.dict())


@app.get("/miamala", response_model=list[Muamala])
def orodha_ya_miamala(kipindi: str = "yote"):
    """
    Orodhesha miamala. `kipindi` inaweza kuwa: 'leo', 'wiki', 'mwezi', au 'yote'.
    """
    muunganisho = pata_muunganisho()
    cursor = muunganisho.cursor()
    tarehe_ya_mwanzo = _tarehe_ya_mwanzo_kwa_kipindi(kipindi)

    if tarehe_ya_mwanzo:
        cursor.execute(
            "SELECT * FROM miamala WHERE tarehe >= %s ORDER BY tarehe DESC",
            (tarehe_ya_mwanzo.isoformat(timespec="seconds"),),
        )
    else:
        cursor.execute("SELECT * FROM miamala ORDER BY tarehe DESC")

    safu = cursor.fetchall()
    cursor.close()
    muunganisho.close()
    return [dict(row) for row in safu]


@app.delete("/miamala/{muamala_id}")
def futa_muamala(muamala_id: int):
    """Futa muamala mmoja kwa kutumia id yake."""
    muunganisho = pata_muunganisho()
    cursor = muunganisho.cursor()
    cursor.execute("DELETE FROM miamala WHERE id = %s", (muamala_id,))
    idadi_iliyofutwa = cursor.rowcount
    muunganisho.commit()
    cursor.close()
    muunganisho.close()

    if idadi_iliyofutwa == 0:
        raise HTTPException(status_code=404, detail="Muamala haujapatikana")
    return {"ujumbe": "Muamala umefutwa"}


@app.get("/muhtasari")
def muhtasari(kipindi: str = "leo"):
    """
    Inarudisha jumla ya mapato, matumizi, na salio kwa kipindi husika.
    `kipindi`: 'leo', 'wiki', 'mwezi', au 'yote'.
    """
    muunganisho = pata_muunganisho()
    cursor = muunganisho.cursor()
    tarehe_ya_mwanzo = _tarehe_ya_mwanzo_kwa_kipindi(kipindi)

    hoja_msingi = "SELECT aina, SUM(kiasi) as jumla FROM miamala"
    vigezo = ()
    if tarehe_ya_mwanzo:
        hoja_msingi += " WHERE tarehe >= %s"
        vigezo = (tarehe_ya_mwanzo.isoformat(timespec="seconds"),)
    hoja_msingi += " GROUP BY aina"

    cursor.execute(hoja_msingi, vigezo)
    safu = cursor.fetchall()
    cursor.close()
    muunganisho.close()

    matokeo = {"mapato": 0.0, "matumizi": 0.0}
    for row in safu:
        matokeo[row["aina"]] = float(row["jumla"])

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
