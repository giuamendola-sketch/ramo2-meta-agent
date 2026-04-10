import os
import httpx
import anthropic
import smtplib
import schedule
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Config
META_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
REPORT_EMAIL = os.environ.get("REPORT_EMAIL", "giu.amendola@gmail.com")
BASE_URL = "https://graph.facebook.com/v23.0"
ACCOUNT_ID = "act_3868212556760579"

client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

def meta_get(endpoint: str, params: dict = {}):
    params["access_token"] = META_TOKEN
    r = httpx.get(f"{BASE_URL}/{endpoint}", params=params, timeout=30)
    return r.json()

def collect_data():
    """Raccoglie tutti i dati delle campagne Meta."""
    print("Raccolta dati campagne...")
    
    # Campagne
    campaigns = meta_get(f"{ACCOUNT_ID}/campaigns", {
        "fields": "id,name,status,objective,daily_budget,lifetime_budget"
    })
    
    # Account insights ultimi 3 giorni
    account_insights = meta_get(f"{ACCOUNT_ID}/insights", {
        "fields": "impressions,clicks,spend,reach,ctr,cpc,cpp,frequency,actions,action_values",
        "date_preset": "last_3d"
    })
    
    # Account insights ultimi 7 giorni
    account_insights_7d = meta_get(f"{ACCOUNT_ID}/insights", {
        "fields": "impressions,clicks,spend,reach,ctr,cpc,cpp,frequency,actions,action_values",
        "date_preset": "last_7d"
    })

    # Per ogni campagna attiva, prendi insights e adset
    campaign_details = []
    for camp in campaigns.get("data", []):
        if camp.get("status") == "ACTIVE":
            insights = meta_get(f"{camp['id']}/insights", {
                "fields": "impressions,clicks,spend,reach,ctr,cpc,cpp,frequency,actions,action_values,cost_per_action_type",
                "date_preset": "last_3d"
            })
            insights_7d = meta_get(f"{camp['id']}/insights", {
                "fields": "impressions,clicks,spend,reach,ctr,cpc,frequency",
                "date_preset": "last_7d"
            })
            adsets = meta_get(f"{camp['id']}/adsets", {
                "fields": "id,name,status,daily_budget,optimization_goal,targeting"
            })
            adset_details = []
            for adset in adsets.get("data", []):
                if adset.get("status") == "ACTIVE":
                    adset_insights = meta_get(f"{adset['id']}/insights", {
                        "fields": "impressions,clicks,spend,reach,ctr,cpc,frequency,actions",
                        "date_preset": "last_3d"
                    })
                    adset_details.append({
                        "adset": adset,
                        "insights_3d": adset_insights.get("data", [])
                    })
            campaign_details.append({
                "campaign": camp,
                "insights_3d": insights.get("data", []),
                "insights_7d": insights_7d.get("data", []),
                "adsets": adset_details
            })
    
    return {
        "account_insights_3d": account_insights.get("data", []),
        "account_insights_7d": account_insights_7d.get("data", []),
        "campaigns": campaign_details,
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }

def analyze_with_claude(data: dict) -> str:
    """Invia i dati a Claude per l'analisi."""
    print("Analisi con Claude...")
    
    prompt = f"""Sei un esperto media buyer specializzato in Meta Ads per un'azienda italiana di arredamento chiamata Ramo2.

Analizza questi dati delle campagne Meta Ads di Ramo2 e produci un report completo in italiano.

DATI RACCOLTI IL: {data['collected_at']}

ACCOUNT INSIGHTS (ultimi 3 giorni):
{data['account_insights_3d']}

ACCOUNT INSIGHTS (ultimi 7 giorni):
{data['account_insights_7d']}

DETTAGLIO CAMPAGNE ATTIVE:
{data['campaigns']}

SOGLIE DI RIFERIMENTO PER RAMO2:
- CPC buono: < €0,20 | CPC ottimo: < €0,12
- CTR buono: > 2,5% | CTR ottimo: > 3%
- Budget massimo account: €30/giorno totale
- Obiettivo primario: massimizzare CTR e abbassare CPC
- Obiettivo secondario: aumentare conversioni (acquisti) nel tempo

Il report deve includere:

1. PANORAMICA ACCOUNT
   - Spesa totale periodo, reach, impressioni, frequenza media
   - Confronto 3 giorni vs 7 giorni (trend)

2. ANALISI CAMPAGNE
   Per ogni campagna attiva:
   - Performance vs soglie Ramo2
   - Valutazione: 🟢 Ottima / 🟡 Buona / 🟠 Da migliorare / 🔴 Critica
   - Osservazioni specifiche

3. ANALISI ADSET
   - Adset migliori e peggiori
   - Eventuali segnali di saturazione del pubblico (frequenza alta)
   - Distribuzione budget tra adset

4. INDICATORI AGGIUNTIVI
   - Efficienza della spesa
   - Qualità del traffico generato
   - Qualsiasi anomalia o pattern interessante

5. RACCOMANDAZIONI
   Divise in:
   A) AZIONI IMMEDIATE (richiedono approvazione):
      - Modifiche budget specifiche con motivazione
      - Campagne da mettere in pausa con motivazione
      - Nuove campagne o adset da creare
   
   B) AZIONI A MEDIO TERMINE:
      - Strategie per migliorare le conversioni
      - Suggerimenti su targeting e creatività
      - Test A/B da considerare

Sii diretto, pratico e specifico. Usa numeri reali dai dati. Non essere generico.
"""
    
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return message.content[0].text

def send_email(report: str, data: dict):
    """Invia il report via email."""
    print("Invio email...")
    
    day = datetime.now().strftime("%A %d %B %Y")
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🎯 Report Meta Ads Ramo2 — {day}"
    msg["From"] = GMAIL_USER
    msg["To"] = REPORT_EMAIL
    
    # Converti il report in HTML semplice
    html_report = report.replace("\n", "<br>").replace("🟢", "<span style='color:green'>🟢</span>").replace("🔴", "<span style='color:red'>🔴</span>")
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #1a1a2e;">🎯 Report Meta Ads Ramo2</h2>
        <p style="color: #666;">Generato il {day}</p>
        <hr>
        <div style="line-height: 1.8;">
            {html_report}
        </div>
        <hr>
        <p style="color: #999; font-size: 12px;">Report generato automaticamente dall'agente Ramo2 Media Buyer</p>
    </body>
    </html>
    """
    
    part = MIMEText(html, "html")
    msg.attach(part)
    
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, REPORT_EMAIL, msg.as_string())
    
    print(f"Email inviata a {REPORT_EMAIL}")

def run_agent():
    """Esegue l'analisi completa."""
    print(f"\n{'='*50}")
    print(f"Avvio agente: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")
    
    try:
        data = collect_data()
        report = analyze_with_claude(data)
        send_email(report, data)
        print("Agente completato con successo.")
    except Exception as e:
        print(f"Errore agente: {e}")

# Scheduling: lunedì, mercoledì, venerdì alle 08:00
schedule.every().monday.at("08:00").do(run_agent)
schedule.every().wednesday.at("08:00").do(run_agent)
schedule.every().friday.at("08:00").do(run_agent)

if __name__ == "__main__":
    print("Agente Ramo2 Meta Buyer avviato.")
    print("Prossime esecuzioni: Lunedì, Mercoledì, Venerdì alle 08:00")
    
    # Esegui subito al primo avvio per test
    if os.environ.get("RUN_NOW", "false").lower() == "true":
        run_agent()
    
    while True:
        schedule.run_pending()
        time.sleep(60)
