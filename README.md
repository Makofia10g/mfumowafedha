# Mfumo wa Mapato na Matumizi

Programu ndogo ya kufuatilia fedha zako — mapato na matumizi — kwa siku, wiki, na mwezi.
Imejengwa kwa **FastAPI** (backend) na **SQLite** (hifadhidata), ukiendana na msingi
ulioujenga tayari kwenye mradi wako wa wallet/payment API.

## Muundo wa mradi

```
mfumo_wa_fedha/
├── main.py           # Backend - API na mantiki yote
├── static/
│   └── index.html    # Dashibodi unayoiona kwenye kivinjari
└── README.md
```

## Jinsi ya kuendesha (mara ya kwanza)

1. Hakikisha una Python 3.9+ imewekwa kwenye kompyuta yako.
2. Fungua terminal ndani ya folder hii (`mfumo_wa_fedha`) na endesha:

   ```bash
   pip install fastapi uvicorn
   ```

3. Anzisha seva:

   ```bash
   uvicorn main:app --reload
   ```

4. Fungua kivinjari chako uende: **http://127.0.0.1:8000**

Hifadhidata (`fedha.db`) itatengenezwa kiotomatiki mara ya kwanza unapoendesha
programu — hakuna hatua ya ziada inayohitajika.

## Vitufe muhimu unavyoweza kujaribu

- Ongeza muamala wa "mapato" au "matumizi" kupitia fomu.
- Bofya vitufe vya **Leo / Wiki 1 / Mwezi 1 / Yote** kuona muhtasari wa kipindi husika.
- Futa muamala wowote kwa kubofya "Futa" pembeni ya safu husika.

## Wazo la hatua inayofuata (unapokuwa tayari)

- Ongeza uthibitishaji (authentication) endapo utataka watumiaji wengi.
- Hamishia hifadhidata kwenda PostgreSQL ukiitaji kuiweka mtandaoni (deploy).
- Ongeza chati (charts) za mwenendo wa fedha kwa wiki/mwezi kwa kutumia maktaba
  kama Chart.js.

## Kuhusu msimbo

Msimbo mzima umeandikwa kwa majina ya Kiswahili (variable names, comments) ili
kukusaidia kuendelea kujifunza — kila kazi ina maelezo mafupi juu yake yanayoeleza
inafanya nini.
