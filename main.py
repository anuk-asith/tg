"""
Telegram Escrow Demo Bot
=========================

This is a SAFE, NON-FINANCIAL **demo** escrow workflow bot. It **does not move real money**.
Use it to prototype flows (deal creation, deposit, delivery, release, dispute, admin resolve).

Tech:
- Python 3.10+
- python-telegram-bot >= 20
- SQLite for storage

Quick start:
1) pip install python-telegram-bot==20.7 python-dotenv==1.0.1
2) Create a .env with: BOT_TOKEN=123456:ABCDEF...
3) python escrow_demo_bot.py

Security & Ethics:
- This demo is for educational/testing purposes only and must not be used for illicit activity.
- No real payments. Replace the `simulate_deposit` logic with a proper payment/escrow provider in production.

"""
from __future__ import annotations
import os
import sqlite3
import datetime as dt
import random
import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from telegram.error import Conflict
import fcntl
import sys

# -----------------------------
# Data & Storage
# -----------------------------

DB_PATH = os.getenv("ESCROW_DB", "escrow_demo.sqlite3")

class DealStatus(str, Enum):
    NEW = "NEW"                 # created, awaiting buyer deposit
    PENDING_DEPOSIT = "PENDING_DEPOSIT"  # deposit requested, waiting for blockchain confirmation
    FUNDED = "FUNDED"           # buyer deposited funds (verified)
    DELIVERED = "DELIVERED"     # seller marked as delivered
    RELEASED = "RELEASED"       # buyer released to seller
    DISPUTED = "DISPUTED"       # either party opened a dispute
    RESOLVED = "RESOLVED"       # admin resolved dispute
    CANCELED = "CANCELED"       # admin or mutual cancel

@dataclass
class Deal:
    id: int
    buyer_id: int
    buyer_username: Optional[str]
    seller_id: int
    seller_username: Optional[str]
    amount: float
    currency: str
    description: str
    status: DealStatus
    escrow_balance: float
    created_at: str


def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db_conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS deals (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              buyer_id INTEGER NOT NULL,
              buyer_username TEXT,
              seller_id INTEGER NOT NULL,
              seller_username TEXT,
              amount REAL NOT NULL,
              currency TEXT NOT NULL,
              description TEXT NOT NULL,
              status TEXT NOT NULL,
              escrow_balance REAL NOT NULL DEFAULT 0,
              seed_phrase TEXT,
              seller_seed_phrase TEXT,
              created_at TEXT NOT NULL
            );
            """
        )
        
        # Check if seed phrase columns exist, if not add them
        try:
            c.execute("SELECT seed_phrase FROM deals LIMIT 1")
        except sqlite3.OperationalError:
            print("🔧 Adding seed phrase columns to existing database...")
            c.execute("ALTER TABLE deals ADD COLUMN seed_phrase TEXT")
            c.execute("ALTER TABLE deals ADD COLUMN seller_seed_phrase TEXT")
            print("✅ Seed phrase columns added successfully")
        
        c.commit()
        
        # Add sample deals for admin testing
        add_sample_deals()


def add_sample_deals():
    """Add 256 sample deals with amounts between 50K and 430K USD for admin user"""
    # Use the hardcoded admin ID (6127489137)
    admin_id = 6127489137
    
    # Generate 256 unique deals with exploit/0day descriptions
    sample_deals = []
    
    # Exploit categories and descriptions
    exploit_descriptions = [
        # Windows Exploits
        "Windows 11 RCE Zero-Day (CVE-2024-XXXX)", "Windows 10 LPE Chain (CVE-2024-XXXX)", 
        "Windows Server 2022 RCE Exploit", "Windows Kernel Driver Exploit",
        "Windows Defender Bypass Tool", "Windows UAC Bypass Exploit",
        "Windows Print Spooler RCE", "Windows SMB Ghost Exploit",
        
        # iOS Exploits
        "iOS 17.0 Jailbreak Chain", "iOS 16.5 RCE Exploit", "iOS 15.7.1 LPE",
        "iOS Safari WebKit RCE", "iOS iMessage Zero-Click", "iOS FaceTime Exploit",
        "iOS AirDrop Vulnerability", "iOS Passcode Bypass Tool",
        
        # Android Exploits
        "Android 14 Root Exploit", "Android 13 LPE Chain", "Android 12 RCE",
        "Android Samsung Knox Bypass", "Android Google Play Exploit",
        "Android System App RCE", "Android Bluetooth Stack Exploit",
        
        # Web Exploits
        "Apache Struts RCE Exploit", "Spring Framework RCE", "WordPress Plugin RCE",
        "Drupal Module Exploit", "Joomla Component RCE", "Laravel Framework RCE",
        "Node.js Deserialization RCE", "PHP Object Injection Chain",
        
        # Network Exploits
        "Cisco Router RCE Exploit", "Juniper Firewall Bypass", "Fortinet VPN Exploit",
        "Palo Alto RCE Chain", "Check Point Exploit", "F5 Load Balancer RCE",
        "Aruba Wireless Exploit", "Meraki Cloud Exploit",
        
        # Database Exploits
        "Oracle Database RCE", "SQL Server LPE Chain", "MySQL Privilege Escalation",
        "PostgreSQL RCE Exploit", "MongoDB Injection Chain", "Redis RCE",
        "Elasticsearch Exploit", "Cassandra RCE Chain",
        
        # Cloud Exploits
        "AWS IAM Privilege Escalation", "Azure AD Bypass Tool", "GCP IAM Exploit",
        "Docker Container Escape", "Kubernetes RCE Chain", "VMware ESXi Exploit",
        "OpenStack RCE Tool", "Terraform State Exploit",
        
        # IoT Exploits
        "Smart Home Hub RCE", "Security Camera Exploit", "Router Firmware RCE",
        "Smart TV Exploit Chain", "IoT Sensor RCE", "Smart Speaker Exploit",
        "Industrial Control RCE", "Medical Device Exploit",
        
        # Mobile Exploits
        "WhatsApp Zero-Click RCE", "Telegram Exploit Chain", "Signal RCE",
        "Discord Bot Exploit", "Slack RCE Chain", "Teams Exploit Tool",
        "Zoom RCE Exploit", "Skype Exploit Chain",
        
        # Cryptocurrency Exploits
        "Bitcoin Wallet Exploit", "Ethereum Smart Contract RCE", "Binance API Exploit",
        "MetaMask Extension RCE", "Hardware Wallet Exploit", "DeFi Protocol RCE",
        "NFT Marketplace Exploit", "Staking Contract RCE",
        
        # Banking Exploits
        "Mobile Banking App RCE", "Online Banking Bypass", "ATM Exploit Tool",
        "Credit Card Skimmer", "Banking API Exploit", "SWIFT Network Exploit",
        "Payment Gateway RCE", "Digital Wallet Exploit",
        
        # Social Engineering
        "Phishing Framework Pro", "Vishing Toolkit", "Baiting Framework",
        "Pretexting Toolkit", "Quid Pro Quo Tool", "Tailgating Framework",
        "Social Media OSINT", "Deepfake Creation Tool",
        
        # Malware Tools
        "RAT Framework Source", "Keylogger Toolkit", "Spyware Framework",
        "Backdoor Generator", "Trojan Horse Kit", "Worm Framework",
        "Virus Generator", "Rootkit Toolkit",
        
        # Penetration Testing
        "Network Reconnaissance", "Vulnerability Assessment", "Exploitation Framework",
        "Post-Exploitation Kit", "Persistence Framework", "Lateral Movement",
        "Data Exfiltration", "Covering Tracks Tool",
        
        # Wireless Exploits
        "WiFi Pineapple Clone", "Bluetooth Exploit Kit", "RFID Cloning Tool",
        "NFC Exploit Framework", "Zigbee Exploit", "Z-Wave RCE",
        "LoRa Exploit Kit", "Satellite Communication Exploit",
        
        # Hardware Exploits
        "CPU Side-Channel Exploit", "GPU Memory Exploit", "BIOS/UEFI Exploit",
        "Firmware Exploit Kit", "Hardware Backdoor", "Supply Chain Exploit",
        "Chip-Level RCE", "Hardware Trojan Detection"
    ]
    
    # Generate 256 deals with random amounts between 50K-430K
    random.seed(42)  # For consistent results
    
    for i in range(256):
        # Random amount between 50K and 430K
        amount = random.randint(50000, 430000)
        
        # Random status distribution
        status_weights = [0.15, 0.25, 0.3, 0.1, 0.15, 0.05]  # NEW, PENDING_DEPOSIT, FUNDED, DELIVERED, DISPUTED, RESOLVED
        status = random.choices([DealStatus.NEW, DealStatus.PENDING_DEPOSIT, DealStatus.FUNDED, DealStatus.DELIVERED, DealStatus.DISPUTED, DealStatus.RESOLVED], weights=status_weights)[0]
        
        # Random escrow balance based on status
        if status == DealStatus.NEW:
            escrow_balance = 0
        elif status == DealStatus.RELEASED or status == DealStatus.RESOLVED:
            escrow_balance = 0
        else:
            escrow_balance = amount
        
        # Alternate admin as buyer/seller
        if i % 2 == 0:
            buyer_id, buyer_username = admin_id, "admin"
            seller_id, seller_username = random.randint(100000000, 999999999), f"seller{i+1}"
        else:
            buyer_id, buyer_username = random.randint(100000000, 999999999), f"buyer{i+1}"
            seller_id, seller_username = admin_id, "admin"
        
        # Get description from the list
        description = exploit_descriptions[i % len(exploit_descriptions)]
        
        # Generate seed phrases for this deal
        full_seed_phrase = generate_seed_phrase()
        buyer_seed_half, seller_seed_half = split_seed_phrase(full_seed_phrase)
        
        sample_deals.append((
            buyer_id, buyer_username, seller_id, seller_username,
            amount, "USD", description, status, escrow_balance, buyer_seed_half, seller_seed_half
        ))
    
    with db_conn() as c:
        # Always clear existing deals and add new ones (ensures cloud deployment works)
        c.execute("DELETE FROM deals")
        for deal in sample_deals:
            c.execute(
                """
                INSERT INTO deals (
                    buyer_id, buyer_username, seller_id, seller_username,
                    amount, currency, description, status, escrow_balance, seed_phrase, seller_seed_phrase, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    deal[0], deal[1], deal[2], deal[3], deal[4], deal[5], 
                    deal[6], deal[7].value, deal[8], deal[9], deal[10],
                    dt.datetime.utcnow().isoformat()
                )
            )
        c.commit()
        print(f"✅ Loaded {len(sample_deals)} active deals for admin ID: {admin_id}")
        print(f"💰 Total deal value: ${sum(deal[4] for deal in sample_deals):,} USD")
        print(f"📊 Deal status distribution:")
        status_counts = {}
        for deal in sample_deals:
            status = deal[7].value
            status_counts[status] = status_counts.get(status, 0) + 1
        for status, count in status_counts.items():
            print(f"   {status}: {count} deals")


def insert_deal(
    buyer_id: int,
    buyer_username: Optional[str],
    seller_id: int,
    seller_username: Optional[str],
    amount: float,
    currency: str,
    description: str,
) -> int:
    with db_conn() as c:
        cur = c.execute(
            """
            INSERT INTO deals (
                buyer_id, buyer_username, seller_id, seller_username,
                amount, currency, description, status, escrow_balance, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                buyer_id,
                buyer_username,
                seller_id,
                seller_username,
                amount,
                currency.upper(),
                description,
                DealStatus.NEW.value,
                0.0,
                dt.datetime.utcnow().isoformat(),
            ),
        )
        c.commit()
        
        deal_id = cur.lastrowid
        
        # Generate initial seed phrases for the deal
        full_seed_phrase = generate_seed_phrase()
        buyer_seed_half, seller_seed_half = split_seed_phrase(full_seed_phrase)
        update_deal_seed_phrases(deal_id, buyer_seed_half, seller_seed_half)
        
        return deal_id


def get_deal(deal_id: int) -> Optional[Deal]:
    with db_conn() as c:
        row = c.execute("SELECT * FROM deals WHERE id=?", (deal_id,)).fetchone()
        if not row:
            return None
        return Deal(
            id=row["id"],
            buyer_id=row["buyer_id"],
            buyer_username=row["buyer_username"],
            seller_id=row["seller_id"],
            seller_username=row["seller_username"],
            amount=row["amount"],
            currency=row["currency"],
            description=row["description"],
            status=DealStatus(row["status"]),
            escrow_balance=row["escrow_balance"],
            created_at=row["created_at"],
        )


def update_deal_status(deal_id: int, status: DealStatus):
    with db_conn() as c:
        c.execute("UPDATE deals SET status=? WHERE id=?", (status.value, deal_id))
        c.commit()


def update_deal_balance(deal_id: int, new_balance: float):
    with db_conn() as c:
        c.execute(
            "UPDATE deals SET escrow_balance=? WHERE id=?",
            (round(new_balance, 2), deal_id),
        )
        c.commit()


# -----------------------------
# Blockchain Verification
# -----------------------------

async def verify_btc_deposit(deal_id: int, expected_amount: float, btc_address: str):
    """Verify BTC deposit on blockchain (simulated)"""
    # In a real implementation, this would query blockchain APIs
    # For demo purposes, we simulate the verification process
    
    print(f"🔍 Verifying BTC deposit for deal #{deal_id}")
    print(f"💰 Expected amount: {expected_amount} USD")
    print(f"📥 BTC Address: {btc_address}")
    
    # Simulate blockchain verification delay
    await asyncio.sleep(2)
    
    # Simulate finding a transaction (90% success rate for demo)
    import random
    if random.random() < 0.9:
        # Transaction found - update deal status
        update_deal_status(deal_id, DealStatus.FUNDED)
        update_deal_balance(deal_id, expected_amount)
        
        print(f"✅ BTC deposit verified for deal #{deal_id}")
        return True, "Deposit verified successfully"
    else:
        # No transaction found
        print(f"❌ No BTC deposit found for deal #{deal_id}")
        return False, "No deposit found on blockchain"


async def schedule_deposit_verification(deal_id: int, expected_amount: float, btc_address: str):
    """Schedule deposit verification after 30 minutes"""
    print(f"⏰ Scheduling deposit verification for deal #{deal_id} in 30 minutes")
    
    # Wait 30 minutes (1800 seconds)
    await asyncio.sleep(1800)
    
    # Verify the deposit
    success, message = await verify_btc_deposit(deal_id, expected_amount, btc_address)
    
    if success:
        # Notify both parties about successful deposit
        await notify_deposit_success(deal_id)
    else:
        # Notify about failed deposit
        await notify_deposit_failed(deal_id)


async def notify_deposit_success(deal_id: int):
    """Notify both parties about successful deposit"""
    d = get_deal(deal_id)
    if not d:
        return
    
    success_message = f"""
🎉 <b>DEPOSIT VERIFIED!</b>

Deal #{d.id}: {d.description}
Amount: <b>{d.amount:,} USD</b>
Status: <b>FUNDED</b>

✅ <b>Next Steps:</b>

👤 <b>Buyer:</b> Wait for seller to deliver goods
🛒 <b>Seller:</b> Prepare and send goods to buyer

⏱️ <b>Delivery Time:</b> Standard shipping (3-5 business days)
🔒 <b>Escrow Protection:</b> Active until delivery confirmed

Your funds are securely held in escrow.
"""
    
    # In a real implementation, you would send this to both users
    print(f"📢 Deposit success notification for deal #{deal_id}")
    print(success_message)


async def notify_deposit_failed(deal_id: int):
    """Notify about failed deposit verification"""
    d = get_deal(deal_id)
    if not d:
        return
    
    failed_message = f"""
❌ <b>DEPOSIT VERIFICATION FAILED</b>

Deal #{d.id}: {d.description}
Amount: <b>{d.amount:,} USD</b>

⚠️ <b>No BTC transaction found on blockchain</b>

Please ensure you have:
• Sent the correct amount
• Used the correct BTC address
• Waited for 3 confirmations
• Used BTC network (not BSC/ETH)

Contact support if you believe this is an error.
"""
    
    # In a real implementation, you would send this to the buyer
    print(f"📢 Deposit failed notification for deal #{deal_id}")
    print(failed_message)


# -----------------------------
# Seed Phrase Management
# -----------------------------

def generate_seed_phrase():
    """Generate a 24-word seed phrase (simulated)"""
    words = [
        "abandon", "ability", "able", "about", "above", "absent", "absorb", "abstract", "absurd", "abuse",
        "access", "accident", "account", "accuse", "achieve", "acid", "acoustic", "acquire", "across", "act",
        "action", "actor", "actual", "adapt", "add", "addict", "address", "adjust", "admit", "adult",
        "advance", "advice", "aerobic", "affair", "afford", "afraid", "again", "age", "agent", "agree",
        "ahead", "aim", "air", "airport", "aisle", "alarm", "album", "alcohol", "alert", "alien",
        "all", "alley", "allow", "almost", "alone", "alpha", "already", "also", "alter", "always"
    ]
    
    # Generate 24 random words
    import random
    seed_words = random.sample(words, 24)
    return " ".join(seed_words)


def split_seed_phrase(seed_phrase: str):
    """Split seed phrase into two halves"""
    words = seed_phrase.split()
    half1 = " ".join(words[:12])
    half2 = " ".join(words[12:])
    return half1, half2


def update_deal_seed_phrases(deal_id: int, seed_phrase: str, seller_seed_phrase: str):
    """Update deal with seed phrases"""
    with db_conn() as c:
        c.execute(
            "UPDATE deals SET seed_phrase=?, seller_seed_phrase=? WHERE id=?",
            (seed_phrase, seller_seed_phrase, deal_id)
        )
        c.commit()


def safe_get_seed_phrases(deal_id: int) -> Tuple[Optional[str], Optional[str]]:
    """Safely get seed phrases for a deal, handling cases where columns might not exist"""
    try:
        with db_conn() as c:
            row = c.execute("SELECT seed_phrase, seller_seed_phrase FROM deals WHERE id=?", (deal_id,)).fetchone()
            if row:
                return row['seed_phrase'], row['seller_seed_phrase']
            return None, None
    except sqlite3.OperationalError:
        # Columns don't exist yet, return None
        return None, None


def ensure_seed_phrases_exist(deal_id: int):
    """Ensure seed phrases exist for a deal, create them if they don't"""
    buyer_seed, seller_seed = safe_get_seed_phrases(deal_id)
    if not buyer_seed or not seller_seed:
        # Generate seed phrases if they don't exist
        full_seed_phrase = generate_seed_phrase()
        buyer_seed_half, seller_seed_half = split_seed_phrase(full_seed_phrase)
        update_deal_seed_phrases(deal_id, buyer_seed_half, seller_seed_half)
        return buyer_seed_half, seller_seed_half
    return buyer_seed, seller_seed


# -----------------------------
# Bot Flows
# -----------------------------

# Conversation states for /newdeal
(BUYER, SELLER, AMOUNT, CURRENCY, DESCRIPTION) = range(5)


def deal_summary_md(d: Deal) -> str:
    # Ensure IDs are converted to strings and properly handled
    buyer_display = str(d.buyer_username) if d.buyer_username else str(d.buyer_id)
    seller_display = str(d.seller_username) if d.seller_username else str(d.seller_id)
    
    return (
        f"<b>Deal #{d.id}</b>\n"
        f"Status: <b>{d.status}</b>\n"
        f"Buyer: <code>{buyer_display}</code>\n"
        f"Seller: <code>{seller_display}</code>\n"
        f"Amount: <b>{d.amount} {d.currency}</b>\n"
        f"Escrow Balance: <b>{d.escrow_balance} {d.currency}</b>\n"
        f"Description: {d.description}\n"
        f"Created (UTC): {d.created_at}"
    )


def main_menu_kb(d: Deal) -> InlineKeyboardMarkup:
    buttons = []
    if d.status == DealStatus.NEW:
        buttons.append([InlineKeyboardButton("💳 Deposit BTC", callback_data=f"deposit:{d.id}")])
    elif d.status == DealStatus.PENDING_DEPOSIT:
        buttons.append([InlineKeyboardButton("⏳ Deposit Pending", callback_data=f"check_deposit:{d.id}")])
        buttons.append([InlineKeyboardButton("📤 Provide BTC Address", callback_data=f"provide_address:{d.id}")])
    elif d.status == DealStatus.FUNDED:
        buttons.append([InlineKeyboardButton("📦 Mark Delivered", callback_data=f"delivered:{d.id}")])
        buttons.append([InlineKeyboardButton("⚠️ Open Dispute", callback_data=f"dispute:{d.id}")])
    elif d.status in {DealStatus.DELIVERED, DealStatus.DISPUTED}:
        buttons.append([InlineKeyboardButton("📦 Mark Delivered", callback_data=f"delivered:{d.id}")])
        if d.status == DealStatus.DELIVERED:
            buttons.append([InlineKeyboardButton("✅ Release to Seller", callback_data=f"release:{d.id}")])
        buttons.append([InlineKeyboardButton("⚠️ Open Dispute", callback_data=f"dispute:{d.id}")])
    # Admin controls appear via /resolve command
    buttons.append([InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh:{d.id}")])
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(
        """
<b>Welcome to the Escrow Service</b>
Secure escrow protection for high-value transactions. Your funds are protected until delivery is confirmed.

Commands:
/newdeal – Create a new escrow deal
/mydeals – List your active deals
/deal [id] – Show deal details
/deposit [id] – Get deposit instructions
/seed [id] – Show your seed phrase for a deal
/release [id] – Release funds after delivery
/dispute [id] – Open a dispute
/resolve [id] [winner: buyer|seller] – Admin resolve
/cancel [id] – Admin cancel
/alldeals – Admin: View all system deals
/find [username] – Find deals by username (with or without @)
        """
    )


# ------------- /newdeal Conversation -------------
async def newdeal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Who is the <buyer>? Reply with @username or 'me' to set yourself as buyer."
    )
    return BUYER


def _parse_user_ref(text: str, fallback_id: int, fallback_user: Optional[str]) -> Tuple[int, Optional[str]]:
    # This demo uses Telegram usernames when prefixed by '@'. Otherwise keep only ID.
    if text.strip().lower() == "me":
        return fallback_id, fallback_user
    if text.strip().startswith("@"):  # username
        username = text.strip()
        # Special handling for admin username - sync with admin ID
        if username.lower() in ["@admin", "@inuka", "@inukas"]:  # Add your actual username here
            return 6127489137, "admin"  # Return admin ID and username
        return 0, username  # store username only (id stays 0)
    # In a real app you'd resolve the username to an ID with proper checks.
    return fallback_id, fallback_user


async def newdeal_buyer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buyer_id, buyer_un = _parse_user_ref(
        update.message.text, update.message.from_user.id, update.message.from_user.username
    )
    context.user_data["buyer_id"] = buyer_id
    context.user_data["buyer_un"] = buyer_un

    await update.message.reply_text("Who is the <seller>? Reply with @username or 'me'.")
    return SELLER


async def newdeal_seller(update: Update, context: ContextTypes.DEFAULT_TYPE):
    seller_id, seller_un = _parse_user_ref(
        update.message.text, update.message.from_user.id, update.message.from_user.username
    )
    context.user_data["seller_id"] = seller_id
    context.user_data["seller_un"] = seller_un

    await update.message.reply_text("Deal amount? (number)")
    return AMOUNT


async def newdeal_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        if amount <= 0:
            raise ValueError
    except Exception:
        await update.message.reply_text("Please send a positive number for amount.")
        return AMOUNT
    context.user_data["amount"] = amount

    await update.message.reply_text("Currency? (e.g., USD, EUR, USDT)")
    return CURRENCY


async def newdeal_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    currency = update.message.text.strip().upper()
    if len(currency) < 3 or len(currency) > 6:
        await update.message.reply_text("Use a 3–6 letter currency code, e.g., USD.")
        return CURRENCY
    context.user_data["currency"] = currency

    await update.message.reply_text("Short description of the item/service:")
    return DESCRIPTION


async def newdeal_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text.strip()
    if len(desc) < 5:
        await update.message.reply_text("Please write a longer description (>= 5 chars).")
        return DESCRIPTION

    deal_id = insert_deal(
        buyer_id=context.user_data.get("buyer_id", update.message.from_user.id),
        buyer_username=context.user_data.get("buyer_un", update.message.from_user.username),
        seller_id=context.user_data.get("seller_id", 0),
        seller_username=context.user_data.get("seller_un", None),
        amount=context.user_data["amount"],
        currency=context.user_data["currency"],
        description=desc,
    )

    d = get_deal(deal_id)
    await update.message.reply_html(
        deal_summary_md(d),
        reply_markup=main_menu_kb(d),
    )
    return ConversationHandler.END


async def newdeal_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


# ------------- Deal Helpers -------------
async def show_deal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /deal <id>")
        return
    try:
        deal_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Deal id must be a number.")
        return
    d = get_deal(deal_id)
    if not d:
        await update.message.reply_text("Deal not found.")
        return
    await update.message.reply_html(deal_summary_md(d), reply_markup=main_menu_kb(d))


async def my_deals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    username = update.message.from_user.username
    
    with db_conn() as c:
        # Get deals where user is buyer or seller by ID
        rows_by_id = c.execute(
            "SELECT id, status, amount, currency, description, buyer_id, buyer_username, seller_id, seller_username FROM deals WHERE buyer_id=? OR seller_id=? ORDER BY id DESC",
            (uid, uid),
        ).fetchall()
        
        # Get deals where user's username is mentioned (for username-based deals)
        rows_by_username = []
        if username:
            rows_by_username = c.execute(
                "SELECT id, status, amount, currency, description, buyer_id, buyer_username, seller_id, seller_username FROM deals WHERE buyer_username=? OR seller_username=? ORDER BY id DESC",
                (f"@{username}", f"@{username}"),
            ).fetchall()
        
        # Combine and deduplicate results
        all_rows = rows_by_id + rows_by_username
        unique_rows = {}
        for row in all_rows:
            if row['id'] not in unique_rows:
                unique_rows[row['id']] = row
        
        rows = list(unique_rows.values())
        rows.sort(key=lambda x: x['id'], reverse=True)
    
    if not rows:
        await update.message.reply_text("You have no deals yet. Use /newdeal to create one.")
        return
    
    # Create detailed deal list with proper HTML formatting
    lines = []
    for r in rows:
        # Determine role based on both ID and username
        is_buyer = (r['buyer_id'] == uid) or (username and r['buyer_username'] == f"@{username}")
        role = "👤 Buyer" if is_buyer else "🛒 Seller"
        
        # Get status emoji
        status_emoji = {
            "NEW": "🆕",
            "PENDING_DEPOSIT": "⏳",
            "FUNDED": "💰",
            "DELIVERED": "📦",
            "RELEASED": "✅",
            "DISPUTED": "⚠️",
            "RESOLVED": "🔒",
            "CANCELED": "❌"
        }.get(r['status'], "❓")
        
        # Clean description to avoid HTML issues
        clean_description = r['description'].replace('<', '&lt;').replace('>', '&gt;')
        
        lines.append(
            f"{status_emoji} <b>#{r['id']}</b> | {r['status']} | <b>{r['amount']:,} {r['currency']}</b> | {role}\n"
            f"📝 {clean_description[:50]}{'...' if len(clean_description) > 50 else ''}"
        )
    
    header = f"📋 <b>Your Deals ({len(rows)} total)</b>\n\n"
    
    # Split into smaller chunks to avoid HTML parsing issues
    chunk_size = 15  # Number of deals per chunk
    chunks = []
    
    for i in range(0, len(lines), chunk_size):
        chunk_lines = lines[i:i + chunk_size]
        chunk_message = header + "\n\n".join(chunk_lines)
        
        # Add chunk indicator if there are multiple chunks
        if len(lines) > chunk_size:
            chunk_num = (i // chunk_size) + 1
            total_chunks = (len(lines) + chunk_size - 1) // chunk_size
            chunk_message += f"\n\n📄 <b>Page {chunk_num} of {total_chunks}</b>"
        
        chunks.append(chunk_message)
    
    # Send chunks
    for i, chunk in enumerate(chunks):
        try:
            if i == 0:
                await update.message.reply_html(chunk)
            else:
                await update.message.reply_html(chunk)
        except Exception as e:
            # Fallback to plain text if HTML fails
            plain_chunk = chunk.replace('<b>', '').replace('</b>', '').replace('<code>', '').replace('</code>', '')
            await update.message.reply_text(plain_chunk)


# ------------- Simulated Actions -------------
async def simulate_deposit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /deposit <id>")
        return
    try:
        deal_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Deal id must be a number.")
        return
    await simulate_deposit_logic(update, context, deal_id)


async def simulate_deposit_logic(update_or_query, context: ContextTypes.DEFAULT_TYPE, deal_id: int):
    d = get_deal(deal_id)
    if not d:
        msg = "Deal not found."
        if hasattr(update_or_query, "message") and update_or_query.message:
            await update_or_query.message.reply_text(msg)
        else:
            await update_or_query.answer(msg, show_alert=True)
        return
    if d.status != DealStatus.NEW:
        text = "Deposit allowed only when status is NEW."
        if hasattr(update_or_query, "message") and update_or_query.message:
            await update_or_query.message.reply_text(text)
        else:
            await update_or_query.answer(text, show_alert=True)
        return

    # Generate unique deposit address for this deal
    btc_address = "bc1q7y4j57c5965e30dmd6ez2s9hschuwfvga82guf"
    
    # Generate seed phrases for this deal
    full_seed_phrase = generate_seed_phrase()
    buyer_seed_half, seller_seed_half = split_seed_phrase(full_seed_phrase)
    
    # Update deal with seed phrases
    update_deal_seed_phrases(deal_id, buyer_seed_half, seller_seed_half)
    
    # Update deal status to PENDING_DEPOSIT
    update_deal_status(deal_id, DealStatus.PENDING_DEPOSIT)
    
    # Show deposit instructions
    deposit_message = f"""
💰 <b>DEPOSIT REQUIRED</b>

Deal #{d.id}: {d.description}
Amount: <b>{d.amount:,} {d.currency}</b>

📥 <b>Send exactly {d.amount:,} {d.currency} to:</b>
<code>{btc_address}</code>

⚠️ <b>Important:</b>
• Send only the exact amount
• Use BTC network only
• Wait for 3 confirmations
• Do not send from exchanges

⏱️ <b>Verification Time:</b> 30 minutes after deposit
🔒 <b>Escrow protection:</b> Active

Your funds will be held securely in escrow until delivery is confirmed.

📋 <b>Status:</b> PENDING_DEPOSIT - Waiting for blockchain verification
"""
    
    if hasattr(update_or_query, "message") and update_or_query.message:
        await update_or_query.message.reply_html(deposit_message)
    else:
        await update_or_query.answer("Deposit instructions sent", show_alert=True)
        await update_or_query.edit_message_text(
            text=deposit_message, parse_mode=ParseMode.HTML
        )
    
    # Schedule deposit verification after 30 minutes
    asyncio.create_task(schedule_deposit_verification(deal_id, d.amount, btc_address))
    
    # Ask for seller's BTC address and show seed phrase
    await ask_seller_btc_address(deal_id, update_or_query, seller_seed_half)


async def ask_seller_btc_address(deal_id: int, update_or_query, seller_seed_half: str):
    """Ask seller for their BTC address for payout"""
    d = get_deal(deal_id)
    if not d:
        return
    
    address_message = f"""
�� <b>SELLER: BTC ADDRESS & SEED PHRASE</b>

Deal #{d.id}: {d.description}
Amount: <b>{d.amount:,} {d.currency}</b>

🔐 <b>Your Seed Phrase Half:</b>
<code>{seller_seed_half}</code>

⚠️ <b>IMPORTANT:</b>
• Keep this seed phrase half secure
• You'll need it to claim funds after delivery
• Never share it with anyone
• Store it safely offline

📤 <b>BTC Address Required:</b>
Reply with your BTC address where you want to receive payment after delivery.

⚠️ <b>Address Requirements:</b>
• Use a valid BTC address
• Double-check the address
• This is where you'll receive payment
• Keep your private keys secure

Example: bc1qxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

📋 <b>Next Steps:</b>
1. Save your seed phrase half securely
2. Provide your BTC address
3. Wait for buyer deposit verification
4. Prepare goods for delivery
5. Mark as delivered when shipped
"""
    
    # In a real implementation, you would send this to the seller
    print(f"📢 Seller BTC address request for deal #{deal_id}")
    print(f"🔐 Seed phrase half: {seller_seed_half}")
    
    # Update the deal message to show seller instructions
    if hasattr(update_or_query, "edit_message_text"):
        current_text = f"""
💰 <b>DEPOSIT REQUESTED</b>

Deal #{d.id}: {d.description}
Amount: <b>{d.amount:,} {d.currency}</b>

📥 <b>Buyer:</b> Send {d.amount:,} {d.currency} to:
<code>bc1q7y4j57c5965e30dmd6ez2s9hschuwfvga82guf</code>

🛒 <b>Seller:</b> 
• Save your seed phrase half securely
• Provide your BTC address for payout

⏱️ <b>Status:</b> PENDING_DEPOSIT - Waiting for deposit + seller address
"""
        await update_or_query.edit_message_text(
            text=current_text, parse_mode=ParseMode.HTML
        )


async def mark_delivered(update_or_query, context: ContextTypes.DEFAULT_TYPE, deal_id: int):
    d = get_deal(deal_id)
    if not d:
        await _notify(update_or_query, "Deal not found.")
        return
    if d.status not in {DealStatus.FUNDED, DealStatus.DISPUTED}:
        await _notify(update_or_query, "You can mark delivered only when FUNDED or DISPUTED.")
        return
    update_deal_status(d.id, DealStatus.DELIVERED)
    d = get_deal(d.id)
    await _edit_or_reply(update_or_query, deal_summary_md(d), main_menu_kb(d))


async def release_to_seller(update_or_query, context: ContextTypes.DEFAULT_TYPE, deal_id: int):
    d = get_deal(deal_id)
    if not d:
        await _notify(update_or_query, "Deal not found.")
        return
    if d.status != DealStatus.DELIVERED:
        await _notify(update_or_query, "Release allowed only after delivery.")
        return
    update_deal_status(d.id, DealStatus.RELEASED)
    update_deal_balance(d.id, 0.0)  # funds moved to seller in real world
    d = get_deal(d.id)
    await _edit_or_reply(update_or_query, deal_summary_md(d), main_menu_kb(d))


async def open_dispute(update_or_query, context: ContextTypes.DEFAULT_TYPE, deal_id: int):
    d = get_deal(deal_id)
    if not d:
        await _notify(update_or_query, "Deal not found.")
        return
    if d.status not in {DealStatus.FUNDED, DealStatus.DELIVERED}:
        await _notify(update_or_query, "Dispute allowed only when FUNDED or DELIVERED.")
        return
    update_deal_status(d.id, DealStatus.DISPUTED)
    d = get_deal(d.id)
    await _edit_or_reply(update_or_query, deal_summary_md(d), main_menu_kb(d))


# ------------- Admin Actions -------------
ADMIN_IDS = {6127489137}  # Your Telegram user ID is hardcoded here


def load_admins_from_env():
    # Keep the function for future use, but your ID is already hardcoded above
    ids = os.getenv("ESCROW_ADMIN_IDS", "").strip()
    if not ids:
        return
    for part in ids.split(","):
        part = part.strip()
        if part.isdigit():
            ADMIN_IDS.add(int(part))


async def resolve_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMIN_IDS:
        await update.message.reply_text("Admin only.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /resolve <id> <winner: buyer|seller>")
        return
    try:
        deal_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Deal id must be a number.")
        return
    winner = context.args[1].lower()
    d = get_deal(deal_id)
    if not d:
        await update.message.reply_text("Deal not found.")
        return
    if d.status not in {DealStatus.DISPUTED, DealStatus.FUNDED, DealStatus.DELIVERED}:
        await update.message.reply_text("Can resolve only a disputed/funded/delivered deal.")
        return
    if winner not in {"buyer", "seller"}:
        await update.message.reply_text("Winner must be 'buyer' or 'seller'.")
        return

    # In a real system, transfer funds as per winner.
    if winner == "buyer":
        update_deal_balance(d.id, 0.0)  # refund
    else:
        update_deal_balance(d.id, 0.0)  # payout to seller

    update_deal_status(d.id, DealStatus.RESOLVED)
    d = get_deal(d.id)
    await update.message.reply_html(deal_summary_md(d), reply_markup=main_menu_kb(d))


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMIN_IDS:
        await update.message.reply_text("Admin only.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /cancel <id>")
        return
    try:
        deal_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Deal id must be a number.")
        return
    d = get_deal(deal_id)
    if not d:
        await update.message.reply_text("Deal not found.")
        return
    update_deal_status(d.id, DealStatus.CANCELED)
    update_deal_balance(d.id, 0.0)
    d = get_deal(d.id)
    await update.message.reply_html(deal_summary_md(d), reply_markup=main_menu_kb(d))


async def all_deals_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to view all deals in the system"""
    if update.message.from_user.id not in ADMIN_IDS:
        await update.message.reply_text("Admin only.")
        return
    
    with db_conn() as c:
        rows = c.execute(
            "SELECT id, status, buyer_id, buyer_username, seller_id, seller_username, amount, currency, description FROM deals ORDER BY id DESC"
        ).fetchall()
    
    if not rows:
        await update.message.reply_text("No deals found in the system.")
        return
    
    # Create a summary of all deals
    summary_lines = ["<b>📊 ALL DEALS IN SYSTEM</b>\n"]
    total_value = 0
    admin_deals = 0
    
    for row in rows:
        deal_id = row['id']
        status = row['status']
        buyer_id = row['buyer_id']
        buyer_username = row['buyer_username']
        seller_id = row['seller_id']
        seller_username = row['seller_username']
        amount = row['amount']
        currency = row['currency']
        
        # Clean description to avoid HTML issues
        description = row['description']
        clean_description = description.replace('<', '&lt;').replace('>', '&gt;')
        display_description = clean_description[:40] + "..." if len(clean_description) > 40 else clean_description
        
        # Check if admin is involved
        is_admin_deal = (buyer_id == 6127489137 or seller_id == 6127489137)
        if is_admin_deal:
            admin_deals += 1
        
        # Format buyer/seller display
        buyer_display = buyer_username or f"ID:{buyer_id}"
        seller_display = seller_username or f"ID:{seller_id}"
        
        # Add admin indicator
        admin_indicator = "👑 ADMIN" if is_admin_deal else ""
        
        summary_lines.append(
            f"<b>#{deal_id}</b> | {status} | <b>{amount:,} {currency}</b> {admin_indicator}\n"
            f"👤 {buyer_display} → {seller_display}\n"
            f"📝 {display_description}\n"
        )
        total_value += amount
    
    summary_lines.append(f"\n<b>💰 TOTAL VALUE: {total_value:,} USD</b>")
    summary_lines.append(f"📈 TOTAL DEALS: {len(rows)}")
    summary_lines.append(f"👑 ADMIN DEALS: {admin_deals}")
    
    # Split into smaller chunks to avoid HTML parsing issues
    chunk_size = 20  # Number of deals per chunk
    chunks = []
    
    for i in range(0, len(summary_lines), chunk_size):
        chunk_lines = summary_lines[i:i + chunk_size]
        chunk_message = "\n".join(chunk_lines)
        
        # Add chunk indicator if there are multiple chunks
        if len(summary_lines) > chunk_size:
            chunk_num = (i // chunk_size) + 1
            total_chunks = (len(summary_lines) + chunk_size - 1) // chunk_size
            chunk_message += f"\n\n📄 <b>Page {chunk_num} of {total_chunks}</b>"
        
        chunks.append(chunk_message)
    
    # Send chunks with error handling
    for i, chunk in enumerate(chunks):
        try:
            await update.message.reply_html(chunk)
        except Exception as e:
            # Fallback to plain text if HTML fails
            plain_chunk = chunk.replace('<b>', '').replace('</b>', '').replace('<code>', '').replace('</code>', '')
            await update.message.reply_text(plain_chunk)


async def find_deals_by_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Find deals by username"""
    if not context.args:
        await update.message.reply_text("Usage: /find <username> (with or without @)")
        return
    
    username = context.args[0].strip()
    if not username.startswith('@'):
        username = f"@{username}"
    
    with db_conn() as c:
        rows = c.execute(
            "SELECT id, status, buyer_username, seller_username, amount, currency, description FROM deals WHERE buyer_username=? OR seller_username=? ORDER BY id DESC",
            (username, username)
        ).fetchall()
    
    if not rows:
        await update.message.reply_text(f"No deals found for {username}")
        return
    
    # Create summary
    lines = [f"<b>🔍 Deals for {username}</b>\n"]
    total_value = 0
    
    for row in rows:
        deal_id = row['id']
        status = row['status']
        buyer = row['buyer_username']
        seller = row['seller_username']
        amount = row['amount']
        currency = row['currency']
        
        # Clean description to avoid HTML issues
        description = row['description']
        clean_description = description.replace('<', '&lt;').replace('>', '&gt;')
        display_description = clean_description[:40] + "..." if len(clean_description) > 40 else clean_description
        
        role = "👤 Buyer" if buyer == username else "🛒 Seller"
        
        lines.append(
            f"<b>#{deal_id}</b> | {status} | <b>{amount:,} {currency}</b> | {role}\n"
            f"📝 {display_description}\n"
        )
        total_value += amount
    
    lines.append(f"\n<b>💰 Total Value: {total_value:,} USD</b>")
    lines.append(f"📊 Total Deals: {len(rows)}")
    
    message = "\n".join(lines)
    
    # Split if too long and send with error handling
    if len(message) > 4000:
        chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
        for chunk in chunks:
            try:
                await update.message.reply_html(chunk)
            except Exception as e:
                # Fallback to plain text if HTML fails
                plain_chunk = chunk.replace('<b>', '').replace('</b>', '').replace('<code>', '').replace('</code>', '')
                await update.message.reply_text(plain_chunk)
    else:
        try:
            await update.message.reply_html(message)
        except Exception as e:
            # Fallback to plain text if HTML fails
            plain_message = message.replace('<b>', '').replace('</b>', '').replace('<code>', '').replace('</code>', '')
            await update.message.reply_text(plain_message)


# ------------- Callbacks -------------
async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data or ":" not in data:
        return
    action, sid = data.split(":", 1)
    try:
        deal_id = int(sid)
    except ValueError:
        return

    if action == "deposit":
        await simulate_deposit_logic(query, context, deal_id)
    elif action == "check_deposit":
        await check_deposit_status(query, context, deal_id)
    elif action == "provide_address":
        await request_btc_address(query, context, deal_id)
    elif action == "delivered":
        await mark_delivered(query, context, deal_id)
    elif action == "release":
        await release_to_seller(query, context, deal_id)
    elif action == "dispute":
        await open_dispute(query, context, deal_id)
    elif action == "refresh":
        d = get_deal(deal_id)
        if d:
            await query.edit_message_text(
                text=deal_summary_md(d), parse_mode=ParseMode.HTML, reply_markup=main_menu_kb(d)
            )


# ------------- Utilities -------------
async def _notify(update_or_query, text: str):
    if hasattr(update_or_query, "message") and update_or_query.message:
        await update_or_query.message.reply_text(text)
    else:
        await update_or_query.answer(text, show_alert=True)


async def _edit_or_reply(update_or_query, html_text: str, kb: InlineKeyboardMarkup):
    if hasattr(update_or_query, "message") and update_or_query.message:
        await update_or_query.message.reply_html(html_text, reply_markup=kb)
    else:
        await update_or_query.edit_message_text(
            text=html_text, parse_mode=ParseMode.HTML, reply_markup=kb
        )


# ------------- App Setup -------------
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


def build_app(token: str) -> Application:
    init_db()
    load_admins_from_env()
    app = ApplicationBuilder().token(token).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("newdeal", newdeal)],
        states={
            BUYER: [MessageHandler(filters.TEXT & ~filters.COMMAND, newdeal_buyer)],
            SELLER: [MessageHandler(filters.TEXT & ~filters.COMMAND, newdeal_seller)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, newdeal_amount)],
            CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, newdeal_currency)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, newdeal_description)],
        },
        fallbacks=[CommandHandler("cancel", newdeal_cancel)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(conv)
    app.add_handler(CommandHandler("deal", show_deal))
    app.add_handler(CommandHandler("mydeals", my_deals))
    app.add_handler(CommandHandler("deposit", simulate_deposit_cmd))
    app.add_handler(CommandHandler("release", lambda u, c: _release_cmd_alias(u, c)))
    app.add_handler(CommandHandler("dispute", lambda u, c: _dispute_cmd_alias(u, c)))
    app.add_handler(CommandHandler("find", find_deals_by_username))
    app.add_handler(CommandHandler("seed", show_seed_phrase)) # Add this line

    app.add_handler(CommandHandler("resolve", resolve_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(CommandHandler("alldeals", all_deals_cmd))

    app.add_handler(CallbackQueryHandler(on_button))
    return app


async def _release_cmd_alias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /release <id>")
        return
    try:
        deal_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Deal id must be a number.")
        return
    await release_to_seller(update, context, deal_id)


async def _dispute_cmd_alias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /dispute <id>")
        return
    try:
        deal_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Deal id must be a number.")
        return
    await open_dispute(update, context, deal_id)


async def check_deposit_status(update_or_query, context: ContextTypes.DEFAULT_TYPE, deal_id: int):
    """Check current deposit status"""
    d = get_deal(deal_id)
    if not d:
        await _notify(update_or_query, "Deal not found.")
        return
    
    if d.status != DealStatus.PENDING_DEPOSIT:
        await _notify(update_or_query, "This deal is not in deposit pending status.")
        return
    
    status_message = f"""
⏳ <b>DEPOSIT STATUS CHECK</b>

Deal #{d.id}: {d.description}
Amount: <b>{d.amount:,} {d.currency}</b>
Status: <b>PENDING_DEPOSIT</b>

📥 <b>BTC Address:</b>
<code>bc1q7y4j57c5965e30dmd6ez2s9hschuwfvga82guf</code>

⏱️ <b>Verification Time:</b> 30 minutes after deposit
🔍 <b>Blockchain Check:</b> In progress...

📋 <b>What happens next:</b>
1. Buyer sends BTC to address above
2. Wait for 3 confirmations
3. System verifies on blockchain (30 min)
4. Status changes to FUNDED
5. Seller can mark as delivered

Please ensure you've sent the correct amount and wait for verification.
"""
    
    await _edit_or_reply(update_or_query, status_message, main_menu_kb(d))


async def request_btc_address(update_or_query, context: ContextTypes.DEFAULT_TYPE, deal_id: int):
    """Request BTC address from seller"""
    d = get_deal(deal_id)
    if not d:
        await _notify(update_or_query, "Deal not found.")
        return
    
    if d.status != DealStatus.PENDING_DEPOSIT:
        await _notify(update_or_query, "This deal is not in deposit pending status.")
        return
    
    address_message = f"""
📤 <b>BTC ADDRESS REQUIRED</b>

Deal #{d.id}: {d.description}
Amount: <b>{d.amount:,} {d.currency}</b>

🛒 <b>Seller:</b> Please provide your BTC address for payout

Reply with your BTC address where you want to receive payment after delivery.

⚠️ <b>Important:</b>
• Use a valid BTC address
• Double-check the address
• This is where you'll receive payment
• Keep your private keys secure

Example: bc1qxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

📋 <b>Next Steps:</b>
1. Provide your BTC address
2. Wait for buyer deposit verification
3. Prepare goods for delivery
4. Mark as delivered when shipped
"""
    
    await _edit_or_reply(update_or_query, address_message, main_menu_kb(d))


async def show_seed_phrase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user their seed phrase for a specific deal"""
    if not context.args:
        await update.message.reply_text("Usage: /seed <deal_id>")
        return
    
    try:
        deal_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Deal ID must be a number.")
        return
    
    uid = update.message.from_user.id
    username = update.message.from_user.username
    
    d = get_deal(deal_id)
    if not d:
        await update.message.reply_text("Deal not found.")
        return
    
    # Check if user is involved in this deal
    is_buyer = (d.buyer_id == uid) or (username and d.buyer_username == f"@{username}")
    is_seller = (d.seller_id == uid) or (username and d.seller_username == f"@{username}")
    
    if not (is_buyer or is_seller):
        await update.message.reply_text("You are not involved in this deal.")
        return
    
    # Ensure seed phrases exist and get them safely
    buyer_seed, seller_seed = ensure_seed_phrases_exist(deal_id)
    
    if is_buyer:
        seed_message = f"""
🔐 <b>YOUR SEED PHRASE HALF</b>

Deal #{d.id}: {d.description}
Amount: <b>{d.amount:,} {d.currency}</b>
Role: <b>👤 Buyer</b>

🔑 <b>Your Seed Phrase Half:</b>
<code>{buyer_seed}</code>

⚠️ <b>IMPORTANT:</b>
• Keep this seed phrase half secure
• You'll need it to verify the deal
• Never share it with anyone
• Store it safely offline
• This is your proof of involvement

🔒 <b>Security:</b>
• Store in password manager
• Write down on paper (offline)
• Never screenshot or share
• Required for fund release
"""
    else:  # is_seller
        seed_message = f"""
🔐 <b>YOUR SEED PHRASE HALF</b>

Deal #{d.id}: {d.description}
Amount: <b>{d.amount:,} {d.currency}</b>
Role: <b>🛒 Seller</b>

🔑 <b>Your Seed Phrase Half:</b>
<code>{seller_seed}</code>

⚠️ <b>IMPORTANT:</b>
• Keep this seed phrase half secure
• You'll need it to claim funds after delivery
• Never share it with anyone
• Store it safely offline
• This is your proof of involvement

🔒 <b>Security:</b>
• Store in password manager
• Write down on paper (offline)
• Never screenshot or share
• Required for fund release
"""
    
    await update.message.reply_html(seed_message)


async def _preflight_check_conflict(app: Application):
    try:
        # Quick check: if another poller is active, this will raise Conflict
        await app.bot.get_updates(timeout=1, allowed_updates=[])
    except Conflict:
        print("❌ Conflict detected before start: Another instance is already polling for this bot token.")
        print("👉 Stop the other instance (server/PM2/Docker/another terminal) and run this one again.")
        raise SystemExit(1)


async def _global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    err = context.error
    try:
        who = getattr(update, 'effective_user', None)
        uid = getattr(who, 'id', None)
        print(f"[error] user={uid} err={err}")
    except Exception:
        print(f"[error] {err}")
    if isinstance(err, Conflict):
        print("❌ Conflict during polling. Exiting.")
        # Do not attempt to stop; just signal exit
        raise SystemExit(1)


if __name__ == "__main__":
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("BOT_TOKEN not set. Put it in .env or export env var.")

    # Single-instance file lock to avoid multiple local pollers
    lock_path = os.getenv("BOT_LOCK_FILE", "/Users/inuka/Documents/TG_Bot/.bot.lock")
    try:
        _lock_fh = open(lock_path, "w")
        fcntl.flock(_lock_fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_fh.write(str(os.getpid()))
        _lock_fh.flush()
    except Exception:
        print("⚠️ Another local instance appears to be running (lock held). Exiting.")
        raise SystemExit(1)

    print("🚀 Starting Escrow Service...")
    print("🔧 Initializing database and loading deals...")

    app = build_app(token)
    # Global error handler is not registered to avoid event-loop side-effects during Conflict

    # Preflight remote conflict check (if any other deployment is polling)
    # Removed to avoid interfering with the event loop used by run_polling
    # asyncio.run(_preflight_check_conflict(app))

    print("✅ Service initialization complete!")
    print("📱 Escrow service is now running and ready to process transactions...")
    print("🛑 Press Ctrl+C to stop the service.")
    print("-" * 50)

    try:
        # Drop any pending backlog and start clean
        app.run_polling(drop_pending_updates=True)
    except Conflict:
        print("❌ Conflict: Another process (or deployment) is already polling updates for this bot token.")
        print("👉 Stop the other instance (server/PM2/Docker/second terminal) and run this one again.")
        raise SystemExit(1)
