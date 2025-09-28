# Biggie – Token-Gated Telegram Group Bot

Biggie ("The American Bully – Top Dog Check") is a Telegram bot that enforces **token-gated access** for private groups.  
It verifies user wallet balances and ownership before allowing entry, automatically removes unverified members,  
and re-checks balances on a schedule.

---

## 🚀 Features

- **Interactive Group Setup:** Configure chain, token address, min balance, and verifier wallet.
- **Secure Verification Flow:** Users must verify holdings **and send 1 token** to prove wallet ownership.
- **Automatic Access Control:**  
  - Kicks unverified users who join without passing verification.  
  - Sends them instructions and verification link in DM.  
- **Periodic Re-Verification:** Automatically removes users who drop below balance requirements.
- **Admin Controls:** Whitelist management, approval/rejection, group status view.
- **Owner Debug Tools:** Job queue inspection, manual verification run, job status checks.

---

## 📦 Installation

1. **Clone the repo:**
   ```bash
   git clone https://github.com/arttester1/biggie.git
   cd biggie
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create `.env` file:**
   ```env
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
   MORALIS_API_KEY=your_moralis_api_key_here
   ```

4. **Run the bot:**
   ```bash
   python main.py
   ```

---

## 🛠 Configuration Files

- `config.json` – Stores group setups (token, min balance, verifier address).
- `user_data.json` – Tracks verified users, wallet addresses, and timestamps.
- `verification_links.json` – Maps unique tokens to group IDs.
- `whitelist.json` / `pending_whitelist.json` – Manages approved and pending groups.

---

## 💬 Commands

### For Everyone
| Command | Where | Description |
|--------|-------|-------------|
| `/start` | Group | Show intro message. |
| `/start <token>` | DM | Begin verification flow for specific group. |
| `/help` | Group/DM | Show available commands. |
| `/guide` | Group/DM | Show full user or admin guide. |

### For Group Admins
| Command | Where | Description |
|--------|-------|-------------|
| `/setup` | Group | Configure token requirements for group. |
| `/status` | Group | Show current settings & verification link. |
| `/guide` | Group | Show admin setup instructions. |

### For Bot Owner (Hard-Coded `ADMIN_USER_ID`)
| Command | Where | Description |
|--------|-------|-------------|
| `/setup` | Group | Bypass whitelist and configure instantly. |
| `/admin pending` | Group/DM | View pending whitelist requests. |
| `/admin approve <group_id>` | Group/DM | Approve group. |
| `/admin reject <group_id>` | Group/DM | Reject group. |
| `/admin list` | Group/DM | Show all whitelisted groups. |
| `/debug_jobs` | DM | Show job queue status. |
| `/job_status` | DM | Show periodic verification job status. |
| `/test_verify` | DM | Run verification manually for all groups. |

---

## 🔄 Verification Flow

1. Admin sets up group using `/setup`.
2. Bot generates unique verification link.
3. User clicks link → enters wallet address in DM.
4. Bot checks token balance.
5. If sufficient, bot requests **1 token transfer** to verifier wallet.
6. Bot confirms transfer on-chain.
7. Bot generates one-time invite link → sends to user.

---

## 🔄 Group Setup (Admin Flow)

1. Admin runs /setup in group.
2. Bot checks if group is whitelisted.
3. Not whitelisted:
   • Adds group to pending list
   • Notifies bot owner with approve/reject buttons
   • Waits for approval from owner
4. Whitelisted: continue
5. Interactive setup prompts admin for:
   • Chain (ETH only right now)
   • Token contract address
   • Minimum required balance
   • Verifier wallet address
6. Saves config → generates unique verification link for the group.
7. Replies with link, admin shares it with members.

---

## 🔄 Member Verification (DM Flow)

1. User clicks verification link → bot starts session in DM.
2. User clicks “Enter Wallet Address” → bot asks for ETH address.
3. Bot checks wallet balance:
   • Enough tokens: asks user to send exactly 1 token to verifier address.
   • Not enough tokens: tells user they fail verification.
4. User sends token → types done.
5. Bot checks transfer on-chain (Moralis):
   • Success: creates one-time invite link → DMs it to user.
   • Fail: lets user retry after 60s or cancel.

---

## 🖼 Auto-Moderation

- **On Join:** Instantly kicks unverified users and DMs them a verification link.
- **Periodic Check:** Every ~6 hours, re-verifies all stored users and removes those below threshold.

---

## 🛡 Security Notes

- Wallet addresses are stored short-term for verification and access control.
- Invite links are one-time use and expire quickly.
- Owner ID is hard-coded in `main.py` – change `ADMIN_USER_ID` to your own Telegram user ID before deployment.

---

## 📜 License

MIT – use freely, but verify code before production deployment.
