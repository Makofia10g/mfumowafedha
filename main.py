"""
Mfumo wa Mapato na Matumizi (Toleo lenye Akaunti za Watumiaji)
----------------------------------------------------------------
Toleo hili linaongeza usajili (signup) na kuingia (login), ili kila
mtumiaji aone miamala yake mwenyewe pekee.

Jinsi ya kuendesha: sawa na kabla - uvicorn main:app --reload
DATABASE_URL lazima iwepo (kwenye Render tayari ipo).
"""

import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path

import bcrypt
import psycopg2
import psycopg2.extras
from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Mipangilio ya msingi
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent
DATABASE_URL = os.environ.get("DATABASE_URL")
JINA_LA_COOKIE = "kikao"          # jina la cookie inayohifadhi session token
SIKU_ZA_KIKAO = 30                # kikao (session) kinadumu siku ngapi

app = FastAPI(title="Mfumo wa Mapato na Matumizi")


def pata_muunganisho():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL haijawekwa.")
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def anzisha_hifadhidata():
    muunganisho = pata_muunganisho()
    cursor = muunganisho.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS watumiaji (
            id SERIAL PRIMARY KEY,
            jina TEXT NOT NULL,
            barua_pepe TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            tarehe_ya_usajili TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS vikao (
            token TEXT PRIMARY KEY,
            mtumiaji_id INTEGER NOT NULL REFERENCES watumiaji(id) ON DELETE CASCADE,
            inaisha TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS miamala (
            id SERIAL PRIMARY KEY,
            mtumiaji_id INTEGER REFERENCES watumiaji(id) ON DELETE CASCADE,
            aina TEXT NOT NULL CHECK(aina IN ('mapato', 'matumizi')),
            kiasi REAL NOT NULL,
            maelezo TEXT,
            tarehe TEXT NOT NULL
        )
        """
    )
    # Kama jedwali la miamala lilikuwepo tayari bila mtumiaji_id, liongeze
    cursor.execute(
        "ALTER TABLE miamala ADD COLUMN IF NOT EXISTS mtumiaji_id INTEGER REFERENCES watumiaji(id) ON DELETE CASCADE"
    )

    muunganisho.commit()
    cursor.close()
    muunganisho.close()


@app.on_event("startup")
def wakati_wa_kuanza():
    anzisha_hifadhidata()


# ---------------------------------------------------------------------------
# Zana za usalama (password + session)
# ---------------------------------------------------------------------------

def sitiri_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def linganisha_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def tengeneza_kikao(mtumiaji_id: int) -> str:
    """Inatengeneza session token mpya na kuihifadhi kwenye jedwali la 'vikao'."""
    token = secrets.token_hex(32)
    inaisha = (datetime.now() + timedelta(days=SIKU_ZA_KIKAO)).isoformat(timespec="seconds")

    muunganisho = pata_muunganisho()
    cursor = muunganisho.cursor()
    cursor.execute(
        "INSERT INTO vikao (token, mtumiaji_id, inaisha) VALUES (%s, %s, %s)",
        (token, mtumiaji_id, inaisha),
    )
    muunganisho.commit()
    cursor.close()
    muunganisho.close()
    return token


def mtumiaji_wa_sasa(kikao: str | None):
    """Inaangalia cookie ya 'kikao', inarudisha mtumiaji husika au None."""
    if not kikao:
        return None

    muunganisho = pata_muunganisho()
    cursor = muunganisho.cursor()
    cursor.execute(
        """
        SELECT watumiaji.id, watumiaji.jina, watumiaji.barua_pepe
        FROM vikao
        JOIN watumiaji ON watumiaji.id = vikao.mtumiaji_id
        WHERE vikao.token = %s AND vikao.inaisha > %s
        """,
        (kikao, datetime.now().isoformat(timespec="seconds")),
    )
    mtumiaji = cursor.fetchone()
    cursor.close()
    muunganisho.close()
    return dict(mtumiaji) if mtumiaji else None


def hakikisha_amelogin(kikao: str | None = Cookie(default=None, alias=JINA_LA_COOKIE)):
    """Dependency ya FastAPI - inazuia njia (endpoint) isipofikiwa bila kuingia."""
    mtumiaji = mtumiaji_wa_sasa(kikao)
    if not mtumiaji:
        raise HTTPException(status_code=401, detail="Tafadhali ingia kwanza (login)")
    return mtumiaji


# ---------------------------------------------------------------------------
# Miundo ya data
# ---------------------------------------------------------------------------

class UsajiliMpya(BaseModel):
    jina: str
    barua_pepe: str
    password: str


class TaarifaZaKuingia(BaseModel):
    barua_pepe: str
    password: str


class MuamalaMpya(BaseModel):
    aina: str
    kiasi: float
    maelezo: str = ""


class Muamala(MuamalaMpya):
    id: int
    tarehe: str


# ---------------------------------------------------------------------------
# Njia za usajili / kuingia / kutoka
# ---------------------------------------------------------------------------

@app.post("/usajili")
def usajili(data: UsajiliMpya, response: Response):
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password lazima iwe na herufi/namba 6 au zaidi")

    muunganisho = pata_muunganisho()
    cursor = muunganisho.cursor()

    cursor.execute("SELECT id FROM watumiaji WHERE barua_pepe = %s", (data.barua_pepe,))
    kama_ipo = cursor.fetchone()
    if kama_ipo:
        cursor.close()
        muunganisho.close()
        raise HTTPException(status_code=400, detail="Barua pepe hii tayari imesajiliwa")

    password_hash = sitiri_password(data.password)
    tarehe = datetime.now().isoformat(timespec="seconds")
    cursor.execute(
        "INSERT INTO watumiaji (jina, barua_pepe, password_hash, tarehe_ya_usajili) "
        "VALUES (%s, %s, %s, %s) RETURNING id",
        (data.jina, data.barua_pepe, password_hash, tarehe),
    )
    mtumiaji_id = cursor.fetchone()["id"]
    muunganisho.commit()
    cursor.close()
    muunganisho.close()

    token = tengeneza_kikao(mtumiaji_id)
    response.set_cookie(JINA_LA_COOKIE, token, httponly=True, max_age=60 * 60 * 24 * SIKU_ZA_KIKAO)
    return {"ujumbe": "Usajili umefanikiwa", "jina": data.jina}


@app.post("/ingia")
def ingia(data: TaarifaZaKuingia, response: Response):
    muunganisho = pata_muunganisho()
    cursor = muunganisho.cursor()
    cursor.execute("SELECT * FROM watumiaji WHERE barua_pepe = %s", (data.barua_pepe,))
    mtumiaji = cursor.fetchone()
    cursor.close()
    muunganisho.close()

    if not mtumiaji or not linganisha_password(data.password, mtumiaji["password_hash"]):
        raise HTTPException(status_code=401, detail="Barua pepe au password si sahihi")

    token = tengeneza_kikao(mtumiaji["id"])
    response.set_cookie(JINA_LA_COOKIE, token, httponly=True, max_age=60 * 60 * 24 * SIKU_ZA_KIKAO)
    return {"ujumbe": "Umeingia", "jina": mtumiaji["jina"]}


@app.post("/toka")
def toka(response: Response, kikao: str | None = Cookie(default=None, alias=JINA_LA_COOKIE)):
    if kikao:
        muunganisho = pata_muunganisho()
        cursor = muunganisho.cursor()
        cursor.execute("DELETE FROM vikao WHERE token = %s", (kikao,))
        muunganisho.commit()
        cursor.close()
        muunganisho.close()
    response.delete_cookie(JINA_LA_COOKIE)
    return {"ujumbe": "Umetoka"}


@app.get("/mtumiaji/sasa")
def taarifa_za_mtumiaji(kikao: str | None = Cookie(default=None, alias=JINA_LA_COOKIE)):
    mtumiaji = mtumiaji_wa_sasa(kikao)
    if not mtumiaji:
        return {"amelogin": False}
    return {"amelogin": True, "jina": mtumiaji["jina"], "barua_pepe": mtumiaji["barua_pepe"]}


# ---------------------------------------------------------------------------
# Njia za miamala - sasa zinahitaji kuwa umeingia (login)
# ---------------------------------------------------------------------------

@app.post("/miamala", response_model=Muamala)
def ongeza_muamala(muamala: MuamalaMpya, mtumiaji: dict = Depends(hakikisha_amelogin)):
    if muamala.aina not in ("mapato", "matumizi"):
        raise HTTPException(status_code=400, detail="Aina lazima iwe 'mapato' au 'matumizi'")
    if muamala.kiasi <= 0:
        raise HTTPException(status_code=400, detail="Kiasi lazima kiwe zaidi ya sifuri")

    tarehe_ya_sasa = datetime.now().isoformat(timespec="seconds")
    muunganisho = pata_muunganisho()
    cursor = muunganisho.cursor()
    cursor.execute(
        "INSERT INTO miamala (mtumiaji_id, aina, kiasi, maelezo, tarehe) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (mtumiaji["id"], muamala.aina, muamala.kiasi, muamala.maelezo, tarehe_ya_sasa),
    )
    muamala_id = cursor.fetchone()["id"]
    muunganisho.commit()
    cursor.close()
    muunganisho.close()

    return Muamala(id=muamala_id, tarehe=tarehe_ya_sasa, **muamala.dict())


@app.get("/miamala", response_model=list[Muamala])
def orodha_ya_miamala(kipindi: str = "yote", mtumiaji: dict = Depends(hakikisha_amelogin)):
    muunganisho = pata_muunganisho()
    cursor = muunganisho.cursor()
    tarehe_ya_mwanzo = _tarehe_ya_mwanzo_kwa_kipindi(kipindi)

    if tarehe_ya_mwanzo:
        cursor.execute(
            "SELECT * FROM miamala WHERE mtumiaji_id = %s AND tarehe >= %s ORDER BY tarehe DESC",
            (mtumiaji["id"], tarehe_ya_mwanzo.isoformat(timespec="seconds")),
        )
    else:
        cursor.execute(
            "SELECT * FROM miamala WHERE mtumiaji_id = %s ORDER BY tarehe DESC",
            (mtumiaji["id"],),
        )

    safu = cursor.fetchall()
    cursor.close()
    muunganisho.close()
    return [dict(row) for row in safu]


@app.delete("/miamala/{muamala_id}")
def futa_muamala(muamala_id: int, mtumiaji: dict = Depends(hakikisha_amelogin)):
    muunganisho = pata_muunganisho()
    cursor = muunganisho.cursor()
    cursor.execute(
        "DELETE FROM miamala WHERE id = %s AND mtumiaji_id = %s",
        (muamala_id, mtumiaji["id"]),
    )
    idadi_iliyofutwa = cursor.rowcount
    muunganisho.commit()
    cursor.close()
    muunganisho.close()

    if idadi_iliyofutwa == 0:
        raise HTTPException(status_code=404, detail="Muamala haujapatikana")
    return {"ujumbe": "Muamala umefutwa"}


@app.get("/muhtasari")
def muhtasari(kipindi: str = "leo", mtumiaji: dict = Depends(hakikisha_amelogin)):
    muunganisho = pata_muunganisho()
    cursor = muunganisho.cursor()
    tarehe_ya_mwanzo = _tarehe_ya_mwanzo_kwa_kipindi(kipindi)

    hoja_msingi = "SELECT aina, SUM(kiasi) as jumla FROM miamala WHERE mtumiaji_id = %s"
    vigezo = [mtumiaji["id"]]
    if tarehe_ya_mwanzo:
        hoja_msingi += " AND tarehe >= %s"
        vigezo.append(tarehe_ya_mwanzo.isoformat(timespec="seconds"))
    hoja_msingi += " GROUP BY aina"

    cursor.execute(hoja_msingi, tuple(vigezo))
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
    sasa = datetime.now()
    if kipindi == "leo":
        return sasa.replace(hour=0, minute=0, second=0, microsecond=0)
    if kipindi == "wiki":
        return sasa - timedelta(days=7)
    if kipindi == "mwezi":
        return sasa - timedelta(days=30)
    return None


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/")
def ukurasa_wa_mwanzo():
    return FileResponse(BASE_DIR / "static" / "index.html")
