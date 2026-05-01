"""
Securities Settlement Recognized Loss Calculator
Verification script — matches Plan of Allocation from settlement notices.
"""

import pandas as pd
import numpy as np
from datetime import date, datetime
from collections import defaultdict

# ─────────────────────────────────────────────
# SHARED UTILITIES
# ─────────────────────────────────────────────
def safe_num(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return 0.0
    try:
        return float(v)
    except:
        return 0.0

def to_date(v):
    if v is None:
        return None
    if isinstance(v, (date, datetime)):
        return v.date() if isinstance(v, datetime) else v
    if isinstance(v, str):
        for fmt in ('%Y-%m-%d','%m/%d/%Y','%d/%m/%Y','%Y-%m-%dT%H:%M:%S'):
            try:
                return datetime.strptime(v.strip(), fmt).date()
            except:
                continue
    return None

def normalize_row(row):
    def get(*keys):
        for k in keys:
            v = row.get(k)
            if v is not None and str(v).strip() not in ('', 'nan', 'NaT'):
                return v
        return None

    holdings_raw = get('Holdings','holdings','Holding')
    holdings = safe_num(holdings_raw) if holdings_raw is not None else None

    return {
        'fundName': str(get('Fund Name','fund_name') or '').strip(),
        'txType':   str(get('Transaction Type','transaction_type') or '').strip(),
        'purchases': safe_num(get('Purchases','purchases','Buy')),
        'sales':     safe_num(get('Sales','sales','Sell')),
        'holdings':  holdings,
        'price':     safe_num(get('Price per share','Price','price')),
        'date':      to_date(get('Trade Date','Date','date','trade_date')),
        'entity':    str(get('Entity','entity','Client') or '').strip(),
    }

# ─────────────────────────────────────────────
# KRAFT HEINZ ENGINE
# ─────────────────────────────────────────────
KH_CLASS_START = date(2015, 11, 6)
KH_CLASS_END   = date(2019, 8, 7)
KH_LOOKBACK_AVG = 27.55

KH_INFLATION_BANDS = [
    (date(2015,11,6),  date(2018,11,1),  12.59),
    (date(2018,11,2),  date(2019,2,21),  10.93),
    (date(2019,2,22),  date(2019,8,7),    4.04),
    (date(2019,8,8),   date(2019,8,8),    1.33),
]

# Table B — average closing prices (90-day lookback)
KH_LOOKBACK_TABLE = {
    date(2019,8,8):28.22, date(2019,8,9):27.36, date(2019,8,12):27.00,
    date(2019,8,13):26.74, date(2019,8,14):26.50, date(2019,8,15):26.26,
    date(2019,8,16):26.14, date(2019,8,19):26.08, date(2019,8,20):25.98,
    date(2019,8,21):25.91, date(2019,8,22):25.88, date(2019,8,23):25.84,
    date(2019,8,26):25.82, date(2019,8,27):25.76, date(2019,8,28):25.72,
    date(2019,8,29):25.69, date(2019,8,30):25.68, date(2019,9,3):25.71,
    date(2019,9,4):25.73,  date(2019,9,5):25.78,  date(2019,9,6):25.85,
    date(2019,9,9):25.95,  date(2019,9,10):26.08, date(2019,9,11):26.21,
    date(2019,9,12):26.33, date(2019,9,13):26.44, date(2019,9,16):26.56,
    date(2019,9,17):26.62, date(2019,9,18):26.68, date(2019,9,19):26.73,
    date(2019,9,20):26.78, date(2019,9,23):26.82, date(2019,9,24):26.86,
    date(2019,9,25):26.89, date(2019,9,26):26.93, date(2019,9,27):26.95,
    date(2019,9,30):26.98, date(2019,10,1):26.99, date(2019,10,2):26.98,
    date(2019,10,3):26.96, date(2019,10,4):26.96, date(2019,10,7):26.96,
    date(2019,10,8):26.96, date(2019,10,9):26.95, date(2019,10,10):26.95,
    date(2019,10,11):26.96,date(2019,10,14):26.96,date(2019,10,15):26.97,
    date(2019,10,16):26.98,date(2019,10,17):27.00,date(2019,10,18):27.01,
    date(2019,10,21):27.03,date(2019,10,22):27.05,date(2019,10,23):27.08,
    date(2019,10,24):27.11,date(2019,10,25):27.13,date(2019,10,28):27.15,
    date(2019,10,29):27.17,date(2019,10,30):27.19,date(2019,10,31):27.28,
    date(2019,11,1):27.37, date(2019,11,4):27.46, date(2019,11,5):27.55,
}

def kh_inflation(d):
    if not d: return 0.0
    for (f, t, inf) in KH_INFLATION_BANDS:
        if f <= d <= t:
            return inf
    return 0.0

def kh_lookback(sale_date):
    return KH_LOOKBACK_TABLE.get(sale_date, KH_LOOKBACK_AVG)

def calc_kh_fund(rows_sorted):
    """FIFO calculation for one fund in KH settlement."""
    fifo = []  # list of [shares_remaining, purchase_date, inflation_at_buy, buy_price]

    # Beginning holdings → treat as purchased at class start
    for r in rows_sorted:
        if r['txType'] == 'Beginning Holdings' and r['holdings'] and r['holdings'] > 0:
            inf = kh_inflation(KH_CLASS_START)
            fifo.append([r['holdings'], KH_CLASS_START, inf, None])

    # Purchases in class period
    for r in rows_sorted:
        if r['txType'] == 'Purchase' and r['purchases'] > 0 and r['date']:
            if KH_CLASS_START <= r['date'] <= KH_CLASS_END:
                inf = kh_inflation(r['date'])
                fifo.append([r['purchases'], r['date'], inf, r['price']])

    fifo.sort(key=lambda x: x[1])  # FIFO by date

    total_rla = 0.0
    detail = []

    corr1 = date(2018, 11, 2)
    lookback_end = date(2019, 11, 5)

    # Sales
    for r in rows_sorted:
        if r['txType'] == 'Sale' and r['sales'] > 0 and r['date']:
            shares_to_sell = r['sales']
            sd = r['date']
            sp = r['price']

            # Sale inflation
            if sd >= date(2019, 8, 8):
                sale_inf = 1.33
            else:
                sale_inf = kh_inflation(sd)

            while shares_to_sell > 0 and fifo:
                lot = fifo[0]
                take = min(lot[0], shares_to_sell)

                if sd < corr1:
                    rla = 0.0
                    note = 'Sold before Nov 2 2018'
                elif sd <= KH_CLASS_END:
                    inf_diff = lot[2] - sale_inf
                    price_diff = (lot[3] - sp) if lot[3] else float('inf')
                    rla = max(0, min(inf_diff, price_diff))
                    note = 'Nov 2 2018 – Aug 7 2019'
                elif sd <= lookback_end:
                    inf_diff = lot[2] - sale_inf
                    avg_close = kh_lookback(sd)
                    price_diff = (lot[3] - sp) if lot[3] else float('inf')
                    lb_diff = (lot[3] - avg_close) if lot[3] else float('inf')
                    rla = max(0, min(inf_diff, price_diff, lb_diff))
                    note = f'90-day lookback (avg={avg_close:.2f})'
                else:
                    rla = 0.0
                    note = 'After lookback period'

                total_rla += rla * take
                detail.append({'action':'SELL','date':sd,'shares':take,'price':sp,
                                'buy_date':lot[1],'buy_inf':lot[2],'rla_ps':rla,
                                'rla_total':rla*take,'note':note})
                lot[0] -= take
                shares_to_sell -= take
                if lot[0] <= 0:
                    fifo.pop(0)

    # End holdings
    for r in rows_sorted:
        if r['txType'] == 'End Holdings' and r['holdings'] and r['holdings'] > 0:
            held = r['holdings']
            for lot in fifo:
                if held <= 0: break
                take = min(lot[0], held)
                price_diff = (lot[3] - KH_LOOKBACK_AVG) if lot[3] else float('inf')
                rla = max(0, min(lot[2], price_diff))
                total_rla += rla * take
                detail.append({'action':'HELD','date':r['date'],'shares':take,'price':KH_LOOKBACK_AVG,
                                'buy_date':lot[1],'buy_inf':lot[2],'rla_ps':rla,
                                'rla_total':rla*take,'note':'End Holdings – lookback $27.55'})
                held -= take

    return total_rla, detail

def run_kh(filepath):
    df = pd.read_excel(filepath, sheet_name=0)
    df.columns = [str(c).strip() for c in df.columns]
    rows = [normalize_row(r) for r in df.to_dict('records')]
    rows = [r for r in rows if r['txType'] and r['date']]

    groups = defaultdict(list)
    for r in rows:
        groups[(r['entity'], r['fundName'])].append(r)

    results = []
    for (entity, fund), grp in groups.items():
        grp.sort(key=lambda x: x['date'])
        rla, detail = calc_kh_fund(grp)
        results.append({'entity': entity, 'fund': fund, 'rla': rla, 'detail': detail})

    return results

# ─────────────────────────────────────────────
# TWITTER ENGINE
# ─────────────────────────────────────────────
TW_CLASS_START  = date(2015, 2, 6)
TW_CLASS_END    = date(2015, 7, 28)
TW_CORR1        = date(2015, 4, 28)
TW_CORR2        = date(2015, 7, 28)
TW_LOOKBACK_AVG = 28.06
TW_HOLD_VAL     = 29.72

# Table 1 — decline in inflation (purchase band x sale timing)
TW_DECLINE = {
    'pre_corr1': {
        'pre_corr1': 0, 'corr1_pm': 8.97, 'corr1_to_jul28': 12.93,
        'jul29_30': 18.27, 'jul31': 18.69, 'aug1_plus': 20.34,
    },
    'corr1_pm': {
        'pre_corr1': 0, 'corr1_pm': 0, 'corr1_to_jul28': 3.96,
        'jul29_30': 9.30, 'jul31': 9.72, 'aug1_plus': 11.37,
    },
    'corr1_to_corr2': {
        'pre_corr1': 0, 'corr1_pm': 0, 'corr1_to_jul28': 0,
        'jul29_30': 5.34, 'jul31': 5.76, 'aug1_plus': 7.41,
    },
    'post_corr2': {'pre_corr1':0,'corr1_pm':0,'corr1_to_jul28':0,'jul29_30':0,'jul31':0,'aug1_plus':0},
}

# Table 2 — average closing prices
TW_LOOKBACK_TABLE = {
    date(2015,8,3):29.27,date(2015,8,4):29.31,date(2015,8,5):29.03,date(2015,8,6):28.66,
    date(2015,8,7):28.33,date(2015,8,10):28.53,date(2015,8,11):28.68,date(2015,8,12):28.77,
    date(2015,8,13):28.75,date(2015,8,14):28.78,date(2015,8,17):28.80,date(2015,8,18):28.76,
    date(2015,8,19):28.67,date(2015,8,20):28.48,date(2015,8,21):28.31,date(2015,8,24):28.11,
    date(2015,8,25):27.89,date(2015,8,26):27.73,date(2015,8,27):27.67,date(2015,8,28):27.62,
    date(2015,8,31):27.63,date(2015,9,1):27.61,date(2015,9,2):27.61,date(2015,9,3):27.64,
    date(2015,9,4):27.66,date(2015,9,8):27.64,date(2015,9,9):27.63,date(2015,9,10):27.63,
    date(2015,9,11):27.62,date(2015,9,14):27.60,date(2015,9,15):27.58,date(2015,9,16):27.59,
    date(2015,9,17):27.58,date(2015,9,18):27.59,date(2015,9,21):27.59,date(2015,9,22):27.57,
    date(2015,9,23):27.55,date(2015,9,24):27.52,date(2015,9,25):27.46,date(2015,9,28):27.41,
    date(2015,9,29):27.37,date(2015,9,30):27.36,date(2015,10,1):27.29,date(2015,10,2):27.27,
    date(2015,10,5):27.29,date(2015,10,6):27.30,date(2015,10,7):27.35,date(2015,10,8):27.41,
    date(2015,10,9):27.48,date(2015,10,12):27.51,date(2015,10,13):27.54,date(2015,10,14):27.57,
    date(2015,10,15):27.61,date(2015,10,16):27.68,date(2015,10,19):27.74,date(2015,10,20):27.80,
    date(2015,10,21):27.82,date(2015,10,22):27.84,date(2015,10,23):27.89,date(2015,10,26):27.94,
    date(2015,10,27):27.99,date(2015,10,28):28.04,date(2015,10,29):28.05,date(2015,10,30):28.06,
}

def tw_purchase_band(d):
    if not d: return 'post_corr2'
    if d < TW_CORR1: return 'pre_corr1'
    if d == TW_CORR1: return 'corr1_pm'
    if TW_CORR1 < d <= TW_CORR2: return 'corr1_to_corr2'
    return 'post_corr2'

def tw_sale_bucket(sd, sp=None):
    if sd < TW_CORR1: return 'pre_corr1'
    if sd == TW_CORR1:
        # $50.45 threshold for AM vs PM
        if sp is not None and sp >= 50.45: return 'pre_corr1'
        return 'corr1_pm'
    if TW_CORR1 < sd <= TW_CORR2: return 'corr1_to_jul28'
    if sd in (date(2015,7,29), date(2015,7,30)): return 'jul29_30'
    if sd == date(2015,7,31): return 'jul31'
    return 'aug1_plus'

def tw_lookback(sd):
    return TW_LOOKBACK_TABLE.get(sd, TW_LOOKBACK_AVG)

def calc_tw_fund(rows_sorted):
    fifo = []  # [shares, purchase_date, band, buy_price, is_beginning]

    # Beginning holdings
    for r in rows_sorted:
        if r['txType'] == 'Beginning Holdings' and r['holdings'] and r['holdings'] > 0:
            fifo.append([r['holdings'], TW_CLASS_START, 'pre_corr1', r['price'], True])

    # Purchases
    for r in rows_sorted:
        if r['txType'] == 'Purchase' and r['purchases'] > 0 and r['date']:
            band = tw_purchase_band(r['date'])
            fifo.append([r['purchases'], r['date'], band, r['price'], False])

    fifo.sort(key=lambda x: x[1])

    total_rla = 0.0
    total_buy_amt = sum(l[0]*l[3] for l in fifo if not l[4])
    total_sale_proceeds = 0.0
    detail = []

    # Sales
    for r in rows_sorted:
        if r['txType'] == 'Sale' and r['sales'] > 0 and r['date']:
            shares_to_sell = r['sales']
            sd = r['date']
            sp = r['price']
            bucket = tw_sale_bucket(sd, sp)

            while shares_to_sell > 0 and fifo:
                lot = fifo[0]
                take = min(lot[0], shares_to_sell)
                band = lot[2]

                decline = TW_DECLINE.get(band, {}).get(bucket, 0)
                price_diff = (lot[3] - sp) if lot[3] else float('inf')

                if sd >= date(2015,8,3) and sd <= date(2015,10,30):
                    avg_close = tw_lookback(sd)
                    lb_diff = (lot[3] - avg_close) if lot[3] else float('inf')
                    rla = max(0, min(decline, price_diff, lb_diff))
                    note = f'90-day lookback avg={avg_close:.2f}'
                elif sd > date(2015,10,30):
                    lb_diff = (lot[3] - TW_LOOKBACK_AVG) if lot[3] else float('inf')
                    rla = max(0, min(decline, lb_diff))
                    note = 'Beyond Oct 30 lookback'
                else:
                    rla = max(0, min(decline, price_diff))
                    note = f'Standard; decline={decline:.4f}'

                total_rla += rla * take
                if not lot[4]:
                    total_sale_proceeds += take * sp
                detail.append({'action':'SELL','date':sd,'shares':take,'price':sp,
                                'buy_date':lot[1],'band':band,'rla_ps':rla,
                                'rla_total':rla*take,'note':note})
                lot[0] -= take
                shares_to_sell -= take
                if lot[0] <= 0:
                    fifo.pop(0)

    # End holdings
    for r in rows_sorted:
        if r['txType'] == 'End Holdings' and r['holdings'] and r['holdings'] > 0:
            held = r['holdings']
            for lot in fifo:
                if held <= 0: break
                take = min(lot[0], held)
                band = lot[2]
                decline = TW_DECLINE.get(band, {}).get('aug1_plus', 0)
                lb_diff = (lot[3] - TW_HOLD_VAL) if lot[3] else float('inf')
                rla = max(0, min(decline, lb_diff))
                total_rla += rla * take
                detail.append({'action':'HELD','date':r['date'],'shares':take,'price':TW_HOLD_VAL,
                                'buy_date':lot[1],'band':band,'rla_ps':rla,
                                'rla_total':rla*take,'note':'End Holdings $29.72'})
                held -= take

    # Market gain/loss check
    holding_value = sum(l[0]*TW_HOLD_VAL for l in fifo)
    market_loss = total_buy_amt - (total_sale_proceeds + holding_value)
    final_rla = max(0, min(total_rla, market_loss)) if market_loss > 0 else 0

    return final_rla, total_rla, market_loss, detail

def run_tw(filepath):
    df = pd.read_excel(filepath, sheet_name=0)
    df.columns = [str(c).strip() for c in df.columns]
    rows = [normalize_row(r) for r in df.to_dict('records')]
    rows = [r for r in rows if r['txType'] and r['date']]

    groups = defaultdict(list)
    for r in rows:
        groups[(r['entity'], r['fundName'])].append(r)

    results = []
    for (entity, fund), grp in groups.items():
        grp.sort(key=lambda x: x['date'])
        rla, raw_rla, mkt_loss, detail = calc_tw_fund(grp)
        results.append({'entity':entity,'fund':fund,'rla':rla,'raw_rla':raw_rla,'market_loss':mkt_loss,'detail':detail})

    return results

# ─────────────────────────────────────────────
# MAIN — RUN AND PRINT RESULTS
# ─────────────────────────────────────────────
if __name__ == '__main__':
    import sys, os

    kh_path = r"C:\Users\Admin\Desktop\Placement Preparation\DRRT\Main Project\settlement_calculator\Masked_Kraft Heinz Securities Litigation.xlsx"
    tw_path = r"C:\Users\Admin\Desktop\Placement Preparation\DRRT\Main Project\settlement_calculator\Masked_Twitter, Inc. (N.D. Cal.) (2016).xlsx"

    # Allow path override from CLI
    if len(sys.argv) > 1: kh_path = sys.argv[1]
    if len(sys.argv) > 2: tw_path = sys.argv[2]

    print("=" * 70)
    print("KRAFT HEINZ SECURITIES LITIGATION — RECOGNIZED LOSS CALCULATION")
    print("=" * 70)

    kh_results = run_kh(kh_path)

    by_entity = defaultdict(float)
    for r in kh_results:
        by_entity[r['entity']] += r['rla']

    grand_total = 0
    for entity, total in sorted(by_entity.items()):
        print(f"\nClient: {entity}  ->  Total RLA: ${total:>14,.2f}")
        fund_results = [r for r in kh_results if r['entity'] == entity]
        for r in sorted(fund_results, key=lambda x: x['fund']):
            if r['rla'] > 0:
                print(f"    {r['fund']:<20} ${r['rla']:>12,.2f}")
        grand_total += total

    print("\n" + "-" * 70)
    print(f"GRAND TOTAL (Kraft Heinz):  ${grand_total:>12,.2f}")
    print("-" * 70)

    print("\n" + "=" * 70)
    print("TWITTER INC. SECURITIES LITIGATION — RECOGNIZED LOSS CALCULATION")
    print("=" * 70)

    tw_results = run_tw(tw_path)

    by_entity_tw = defaultdict(float)
    for r in tw_results:
        by_entity_tw[r['entity']] += r['rla']

    grand_total_tw = 0
    for entity, total in sorted(by_entity_tw.items()):
        print(f"\nClient: {entity}  Total RLA: ${total:>14,.2f}")
        fund_results = [r for r in tw_results if r['entity'] == entity]
        for r in sorted(fund_results, key=lambda x: x['fund']):
            if r['rla'] > 0:
                print(f"    {r['fund']:<20} ${r['rla']:>12,.2f}  (raw={r['raw_rla']:,.2f}, mkt_loss={r['market_loss']:,.2f})")
        grand_total_tw += total

    print("\n" + "-" * 70)
    print(f"GRAND TOTAL (Twitter):      ${grand_total_tw:>12,.2f}")
    print("-" * 70)

    # Export summary to CSV
    rows_out = []
    for r in kh_results:
        rows_out.append({'Case':'Kraft Heinz','Entity':r['entity'],'Fund':r['fund'],'Recognized_Loss':round(r['rla'],2)})
    for r in tw_results:
        rows_out.append({'Case':'Twitter','Entity':r['entity'],'Fund':r['fund'],'Recognized_Loss':round(r['rla'],2)})

    out_df = pd.DataFrame(rows_out)
    out_df.to_csv('recognized_loss_summary.csv', index=False)
    print("\nSummary exported to recognized_loss_summary.csv")
