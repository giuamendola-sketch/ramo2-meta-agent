import os
import sys
import httpx
import anthropic
import smtplib
import schedule
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Forza output immediato
sys.stdout.reconfigure(line_buffering=True)

# Config
META_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
REPORT_EMAIL = os.environ.get("REPORT_EMAIL", "giu.amendola@gmail.com")
BASE_URL = "https://graph.facebook.com/v23.0"
ACCOUNT_ID = "act_3868212556760579"

print(f"Avvio agente Ramo2...", flush=True)
print(f"META_TOKEN presente: {bool(META_TOKEN)}", flush=True)
print(f"ANTHROPIC_KEY presente: {bool(ANTHROPIC_KEY)}", flush=True)
print(f"GMAIL_USER: {GMAIL_USER}", flush=True)
print(f"RUN_NOW: {os.environ.get('RUN_NOW', 'false')}", flush=True)

client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

def meta_get(endpoint: str, params: dict = {}):
    params["access_token"] = META_TOKEN
    r = httpx.get(f"{BASE_URL}/{endpoint}", params=params, timeout=30)
    return r.json()

def collect_data():
    print("Raccolta dati campagne...", flush=True)
    campaigns = meta_get(f"{ACCOUNT_ID}/campaigns", {
        "fields": "id,name,status,objective,daily_budget,lifetime_budget"
    })
    account_insights = meta_get(f"{ACCOUNT_ID}/insights", {
        "fields": "impressions,clicks,spend,reach,ctr,cpc,cpp,frequency,actions,action_values",
        "date_preset": "last_3d"
    })
    account_insights_7d = meta_get(f"{ACCOUNT_ID}/insights", {
        "fields": "impressions,clicks,spend,reach,ctr,cpc,cpp,frequency,actions,action_values",
        "date_preset": "last_7d"
    })
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
                "fields": "id,name,status,daily_budget,optimization_goal"
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
    print(f"Raccolte {len(campaign_details)} campagne attive.", flush=True)
    return {
        "account_insights_3d": account_insights.get("data", []),
        "account_insights_7d": account_insights_7d.get("data", []),
        "campaigns": campaign_details,
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }

def analyze_with_claude(data: dict) -> str:
    print("Analisi con Claude...", flush=True)
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

3. ANALISI ADSET
   - Adset migliori e peggiori
   - Segnali di saturazione del pubblico

4. INDICATORI AGGIUNTIVI
   - Efficienza della spesa
   - Anomalie o pattern interessanti

5. RACCOMANDAZIONI
   A) AZIONI IMMEDIATE (richiedono approvazione):
      - Modifiche budget con motivazione
      - Campagne da pausare con motivazione
   B) AZIONI A MEDIO TERMINE:
      - Strategie per migliorare conversioni
      - Test A/B da considerare

Sii diretto, pratico e specifico. Usa numeri reali dai dati."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    print("Analisi completata.", flush=True)
    return message.content[0].text

def send_email(report: str):
    print("Invio email...", flush=True)
    day = datetime.now().strftime("%A %d %B %Y")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🎯 Report Meta Ads Ramo2 — {day}"
    msg["From"] = GMAIL_USER
    msg["To"] = REPORT_EMAIL
    html_report = report.replace("\n", "<br>")
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #1a1a2e;">🎯 Report Meta Ads Ramo2</h2>
        <p style="color: #666;">Generato il {day}</p>
        <hr>
        <div style="line-height: 1.8;">{html_report}</div>
        <hr>
        <p style="color: #999; font-size: 12px;">Report generato automaticamente dall'agente Ramo2 Media Buyer</p>
    </body>
    </html>"""
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, REPORT_EMAIL, msg.as_string())
    print(f"Email inviata a {REPORT_EMAIL}", flush=True)

def run_agent():
    print(f"\n{'='*50}", flush=True)
    print(f"Avvio analisi: {datetime.now().strftime('%Y-%m-%d %H:%M')}", flush=True)
    print(f"{'='*50}", flush=True)
    try:
        data = collect_data()
        report = analyze_with_claude(data)
        send_email(report)
        print("Agente completato con successo.", flush=True)
    except Exception as e:
        print(f"Errore agente: {e}", flush=True)
        import traceback
        traceback.print_exc()

schedule.every().monday.at("08:00").do(run_agent)
schedule.every().wednesday.at("08:00").do(run_agent)
schedule.every().friday.at("08:00").do(run_agent)

if __name__ == "__main__":
    print("Scheduler avviato. Prossime esecuzioni: Lun/Mer/Ven alle 08:00", flush=True)
    if os.environ.get("RUN_NOW", "false").lower() == "true":
        run_agent()
    while True:
        schedule.run_pending()
        time.sleep(60)
