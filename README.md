# Securities Settlement Recognized Loss Calculator

## Project Structure

```
settlement_calculator/
├── index.html          ← Main browser-based calculator (open directly in Chrome/Edge)
├── calculate.py        ← Python verification script
├── README.md           ← This file
└── (data files not included — upload via the HTML interface)
```

---

## How to Use

### Option A — Browser Calculator (Recommended)

1. Open `index.html` in **Google Chrome** or **Microsoft Edge**
2. Select the settlement tab: **Kraft Heinz** or **Twitter**
3. Click **"Upload"** and choose your Excel file (`.xlsx` / `.xls` / `.csv`)
4. Results appear instantly — per client, per fund, per trade
5. Click **"Export Results to CSV"** to download

**Required Excel columns (any order):**

| Column | Description |
|--------|-------------|
| `Fund Name` | Portfolio / fund identifier |
| `Transaction Type` | `Beginning Holdings`, `Purchase`, `Sale`, `End Holdings` |
| `Purchases` | Number of shares purchased (leave blank for non-purchases) |
| `Sales` | Number of shares sold (leave blank for non-sales) |
| `Holdings` | Shares held (only for Beginning/End Holdings rows) |
| `Price per share` | Transaction price |
| `Trade Date` | Date of transaction |
| `Entity` | Client name/identifier |

---

### Option B — Python Script

```bash
# Install dependency
pip install pandas openpyxl --break-system-packages

# Run with provided data files
python3 calculate.py Masked_Kraft_Heinz_Securities_Litigation.xlsx Masked_Twitter__Inc___N_D__Cal____2016_.xlsx

# Output: printed results + recognized_loss_summary.csv
```

---

## Calculation Methodology

### Kraft Heinz Securities Litigation (Case No. 1:19-cv-01339)

**Class Period:** November 6, 2015 – August 7, 2019

**Artificial Inflation (Table A):**
| Date Range | Inflation Per Share |
|---|---|
| Nov 6, 2015 – Nov 1, 2018 | $12.59 |
| Nov 2, 2018 – Feb 21, 2019 | $10.93 |
| Feb 22, 2019 – Aug 7, 2019 | $4.04 |
| Aug 8, 2019 (sale only) | $1.33 |

**Sale Scenarios (per settlement notice ¶72):**
- Sold before Nov 2, 2018 → **$0.00**
- Sold Nov 2, 2018 – Aug 7, 2019 → **lesser of** (inflation diff) **or** (price diff)
- Sold Aug 8 – Nov 5, 2019 → **least of** (inflation diff), (price diff), **(price − 90-day avg)**
- Held Nov 5, 2019 → **lesser of** (inflation at buy) **or** (price − $27.55)

**90-Day Look-Back Average:** $27.55 (Aug 8 – Nov 5, 2019)

**FIFO Matching:** Sales matched against opening position then chronological purchases.

---

### Twitter Inc. Securities Litigation (Case No. 4:16-cv-05314-JST)

**Class Period:** February 6, 2015 – July 28, 2015

**Corrective Disclosures:**
- April 28, 2015 at 3:07 PM EDT (threshold price: $50.45)
- July 28, 2015 (end of day)

**Decline in Inflation (Table 1 — simplified):**

| Purchase Band | Sold ≥ Aug 1 | Sold Jul 31 | Sold Jul 29-30 | Sold Apr 29 – Jul 28 |
|---|---|---|---|---|
| Feb 6 – Apr 28 AM | $20.34 | $18.69 | $18.27 | $12.93 |
| Apr 28 PM | $11.37 | $9.72 | $9.30 | $3.96 |
| Apr 29 – Jul 28 | $7.41 | $5.76 | $5.34 | $0.00 |

**90-Day Look-Back Average:** $28.06 (Aug 3 – Oct 30, 2015)
**Holding Value:** $29.72 (shares held as of Aug 3, 2015)

**Market Gain/Loss Constraint:** Per settlement notice ¶68, if a claimant had a Market Gain on overall Twitter transactions, their Recognized Claim = $0. If Market Loss < Recognized Loss, Recognized Claim = Market Loss.

---

## Calculated Recognized Losses

### Kraft Heinz — Summary

| Client | Total Recognized Loss |
|---|---|
| Client 1-1 | $138,614.00 |
| Client 1-2 | $1,648,800.43 |
| Client 2 | $8,872,819.81 |
| **GRAND TOTAL** | **$10,660,234.24** |

### Twitter — Summary

| Client | Total Recognized Loss |
|---|---|
| Client 1-1 | $1,418.00 |
| Client 1-2 | $97,430.71 |
| Client 2 | $24,748.95 |
| **GRAND TOTAL** | **$123,597.66** |

---

## Notes on Null Values

The input data may have null/blank values in Purchases, Sales, or Holdings columns — this is expected and handled correctly:

- `Purchases` = null on a `Sale` or `Holdings` row → treated as 0
- `Sales` = null on a `Purchase` or `Holdings` row → treated as 0
- `Holdings` = null on `Purchase` or `Sale` rows → correctly ignored
- `Price per share` = null on `Beginning Holdings` → price not used for those lots (limitation applied conservatively)

---

## Tools Used

- **HTML + JavaScript** — browser-based calculator (no server needed)
- **SheetJS (xlsx.full.min.js)** — Excel file parsing in browser (CDN)
- **Python / pandas** — server-side verification script
- **Claude Sonnet 4.6** — AI-assisted development
