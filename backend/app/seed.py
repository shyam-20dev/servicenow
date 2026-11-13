"""Synthetic labelled tickets: background noise plus two hidden incident spikes."""
import random
from datetime import datetime, timedelta, timezone

from . import db

# (category, subcategory, group, priority, [short descriptions], [descriptions])
BACKGROUND = [
    ("Network", "Wi-Fi", "Network Support", "Medium",
     ["Wi-Fi keeps dropping", "Cannot connect to office Wi-Fi", "Slow Wi-Fi on {floor} floor"],
     ["My laptop disconnects from the Wi-Fi every few minutes on the {floor} floor.",
      "The office Wi-Fi shows connected but pages will not load in the {floor} meeting room.",
      "Wi-Fi speed is extremely slow near the {floor} floor kitchen area."]),
    ("Network", "LAN", "Network Support", "Medium",
     ["Network port not working", "Desk ethernet has no connection"],
     ["The ethernet port at my desk on the {floor} floor shows no link light.",
      "Wired network at my desk stopped working this morning after I moved seats."]),
    ("Hardware", "Laptop", "Hardware Support", "High",
     ["Laptop will not turn on", "Laptop screen flickering", "Laptop battery drains fast"],
     ["My laptop does not power on even when connected to the charger.",
      "The laptop screen flickers and goes black every few minutes.",
      "Battery drops from 100 to 20 percent within an hour of normal use."]),
    ("Hardware", "Printer", "Hardware Support", "Low",
     ["Printer not printing", "Printer paper jam", "Cannot find printer"],
     ["The {floor} floor printer shows offline and nothing prints.",
      "Constant paper jam in the {floor} floor printer, tray looks fine.",
      "My computer cannot find the shared printer on the {floor} floor."]),
    ("Software", "Install", "Software Support", "Low",
     ["Need {app} installed", "Request to install {app}", "Please install {app}"],
     ["Please install {app} on my laptop, it is needed for my project.",
      "I need {app} for client work, can you install it and give a licence?"]),
    ("Software", "Application crash", "Software Support", "Medium",
     ["{app} keeps crashing", "{app} freezes on startup"],
     ["{app} closes by itself a few seconds after opening, reinstalling did not help.",
      "{app} freezes on the loading screen and I have to force close it."]),
    ("Access", "Password reset", "Service Desk", "Medium",
     ["Password reset needed", "Forgot my password", "Cannot log in to my account"],
     ["I forgot my password and the self-service reset link is not working for me.",
      "My password expired and I cannot sign in to my workstation."]),
    ("Access", "Account locked", "Service Desk", "High",
     ["Account locked out", "Locked out after wrong password"],
     ["My account got locked after a few wrong password attempts, please unlock it.",
      "I am locked out of my account and cannot start my work."]),
    ("Email", "Mailbox", "Service Desk", "Low",
     ["Mailbox is full", "Email attachment will not send", "Calendar invites missing"],
     ["My mailbox is full and I cannot receive new email, please increase the quota.",
      "I cannot send emails with attachments larger than a few MB.",
      "Meeting invites are not showing in my calendar since yesterday."]),
]

# Hidden incident spikes: many near-identical tickets in a short window.
SPIKES = [
    dict(scenario="vpn_gateway_outage", category="Network", group="Network Support", priority="High",
         count=18, minutes=28,
         shorts=["Cannot connect to VPN", "VPN authentication timeout", "VPN keeps failing to connect",
                 "Remote VPN not working"],
         descs=["VPN client says authentication timeout and never connects since this morning.",
                "I cannot reach any internal application, the VPN connection times out at login.",
                "Working from home and the VPN fails with a gateway timeout error, nobody on my team can connect.",
                "VPN connects for a second and then drops, internal sites are unreachable.",
                "The company VPN shows error: gateway not responding. Affecting my work."]),
    dict(scenario="exchange_outage", category="Email", group="Service Desk", priority="High",
         count=9, minutes=40,
         shorts=["Outlook cannot connect to server", "Email not syncing", "Outlook stuck on disconnected"],
         descs=["Outlook shows disconnected and is trying to connect to the Exchange server, no email since morning.",
                "My email is not syncing at all, Outlook says it cannot connect to the mail server.",
                "Outlook has been stuck on 'trying to connect' for an hour, webmail is also slow."]),
]

REQUESTERS = ["Asha Rao", "Vikram Shah", "Meera Iyer", "Rahul Verma", "Priya Nair", "Karthik S", "Neha Gupta", "Arjun Menon"]
FLOORS = ["1st", "2nd", "3rd", "4th", "5th"]
APPS = ["Photoshop", "Visual Studio", "Zoom", "Slack", "AutoCAD", "Python", "Docker", "Excel add-in"]


def _fmt(rng, template):
    return template.format(floor=rng.choice(FLOORS), app=rng.choice(APPS))


def seed(background: int = 280) -> dict:
    rng = random.Random(42)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    rows = []

    for _ in range(background):
        cat, sub, group, prio, shorts, descs = rng.choice(BACKGROUND)
        ts = now - timedelta(minutes=rng.randint(90, 60 * 24 * 3))
        rows.append((_fmt(rng, rng.choice(shorts)), _fmt(rng, rng.choice(descs)),
                     cat, prio, group, "background", ts))

    for sp in SPIKES:
        for _ in range(sp["count"]):
            ts = now - timedelta(minutes=rng.randint(1, sp["minutes"]))
            rows.append((rng.choice(sp["shorts"]), rng.choice(sp["descs"]),
                         sp["category"], sp["priority"], sp["group"], sp["scenario"], ts))

    def status_for(age_minutes: int) -> str:     # older tickets are more likely to be finished
        roll = rng.random()
        if age_minutes < 120:
            return "open" if roll < 0.8 else "in_progress"
        return "resolved" if roll < 0.55 else "closed" if roll < 0.7 else "in_progress" if roll < 0.85 else "open"

    with db.conn() as c:
        c.execute("DELETE FROM problems")
        c.execute("DELETE FROM tickets WHERE is_synthetic=1")
        c.executemany(
            """INSERT INTO tickets (short_description, description, label_category, label_priority,
               label_group, scenario, is_synthetic, created_at, requester, status) VALUES (?,?,?,?,?,?,1,?,?,?)""",
            [(s, d, cat, pr, g, sc, ts.strftime("%Y-%m-%d %H:%M:%S"), rng.choice(REQUESTERS),
              status_for(int((now - ts).total_seconds() // 60))) for s, d, cat, pr, g, sc, ts in rows],
        )
    return {"tickets": len(rows), "spikes": [{"scenario": s["scenario"], "count": s["count"]} for s in SPIKES]}
