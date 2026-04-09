# API Keys — How to Obtain

Add each key to your `.env` file after obtaining it.

---

## 1. OpenAI API Key — `OPENAI_API_KEY`

Used by `agent.py` to extract concepts from transcripts (GPT-4o).

**Steps:**
1. Go to [platform.openai.com](https://platform.openai.com) and sign up or log in.
2. Click your profile icon (top-right) → **API keys**.
3. Click **Create new secret key**, give it a name, and copy it immediately (it won't be shown again).
4. Add billing info under **Settings → Billing** — the API requires a paid account.
5. Paste into `.env`:
   ```
   OPENAI_API_KEY=sk-...
   ```

---

## 2. Notion Integration Token — `NOTION_TOKEN`

Used by `server.py` to read topics and save notes to Notion.

**Steps:**
1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations) and click **New integration**.
2. Give it a name (e.g. `reel-knowledge-agent`), select your workspace, and click **Submit**.
3. Copy the **Internal Integration Secret**
4. Paste into `.env`:
   ```
   NOTION_TOKEN=secret_...
   ```

---

## 3. Notion Database ID — `NOTION_DATABASE_ID`

The specific database where notes will be saved.

**Steps:**
1. Open Notion and create a new database (full-page, not inline).
2. Add these properties to the database:
   | Property name | Type      |
   |---------------|-----------|
   | Name          | Title     |
   | Topic         | Text      |
   | Subtopic      | Text      |
3. Share the database with your integration: open the database → **⋯ menu → Connections → Add connection** → select your integration.
4. Copy the database ID from the URL:
   ```
   https://www.notion.so/YOUR_WORKSPACE/THIS_PART_IS_THE_ID?v=...
   ```
   It is the 32-character hex string before the `?v=`.
5. Paste into `.env`:
   ```
   NOTION_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

---

## 4. Telegram Bot Token — `TELEGRAM_BOT_TOKEN`

Used by `bot.py` to receive reel links from users.

**Steps:**
1. Open Telegram and search for **@BotFather**.
2. Send `/newbot` and follow the prompts (choose a name and username ending in `bot`).
3. BotFather will send you a token that looks like `123456789:ABCdef...`.
4. Paste into `.env`:
   ```
   TELEGRAM_BOT_TOKEN=123456789:ABCdef...
   ```

---

## Final `.env` should look like

```
OPENAI_API_KEY=sk-...
NOTION_TOKEN=secret_...
NOTION_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_BOT_TOKEN=123456789:ABCdef...
```

---

## Dependencies to install

```bash
pip install mcp openai yt-dlp openai-whisper python-dotenv requests python-telegram-bot
```

> `openai-whisper` also requires `ffmpeg` installed on your system:
> - macOS: `brew install ffmpeg`
> - Ubuntu: `sudo apt install ffmpeg`
