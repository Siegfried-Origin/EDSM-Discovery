# 🚀 Elite Dangerous – First Discoveries & Traffic Analyzer

This script retrieves your first discovered systems from the EDSM API and optionally analyzes their traffic statistics.
It supports caching, progress tracking, interval segmentation, and automatic resume.

# Usage

## 📦 Download

👉 Windows users can download the prebuilt `.exe` from the Releases section.

## 🔑 Getting Your API Key & Commander Name

- Create or log into your account on EDSM
- Go to: https://www.edsm.net/en/settings/api
- Copy:
  - `Commander Name`
  - `API Key`

## 🛠 Run the script directly

Requirements:
- Python 3.10+ (recommended 3.11 or newer)
- A free account on EDSM

1️⃣ Clone the repository
```bash
git clone https://github.com/Siegfried-Origin/EDSM-Discovery.git
cd EDSM-Discovery
```

2️⃣ Create a virtual environment (recommended)
```bash
python -m venv venv
```

Activate it:

Windows
```bash
venv\Scripts\activate
```

Mac/Linux
```bash
source venv/bin/activate
```

3️⃣ Install dependencies
```bash
pip install -r requirements.txt
```

▶️ Running the Script
```bash
python edsm_discovery.py
```

## 🏗 Optional: Build an Executable

To generate a standalone Windows executable:
```bash
pip install pyinstaller
pyinstaller --onefile edsm_discovery.py
```

The executable will be available in: `dist/edsm_discovery.exe`

# ⚙️ First Run Configuration

On first execution, the script can generate a .env file automatically.

If needed, you can manually create a .env file in the project root:

```
COMMANDER=YourCommanderName
API_KEY=YourApiKeyHere
```

# 📁 Generated Files

After execution, you may see:
- `.env` → your API credentials - DO NOT SHARE!
- `discovery_cache.json` → cached discoveries
- `export.csv` → final results


# ⚠️ Notes

- Respect EDSM API rate limits.
- Do not share your API key publicly.
- Large date ranges may take time on first run.


If you like the project, feel free to ⭐ the repository!