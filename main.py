import os
import yfinance as yf
import pandas as pd
import requests

def calculate_technical_edge(ticker):
    try:
        stock = yf.Ticker(ticker)
        
        # 1. Mengambil Fundamental & Kapitalisasi Pasar
        info = stock.info
        market_cap = info.get('marketCap', 0)
        
        # Kategorisasi berdasarkan Market Cap (Rupiah)
        if market_cap > 50_000_000_000_000:
            category = "🔵 *BLUE CHIP (Lapis 1 | > Rp 50T)*"
            cat_score = 1
        elif market_cap >= 5_000_000_000_000:
            category = "🟡 *SECOND LINER (Lapis 2 | Rp 5T - 50T)*"
            cat_score = 2
        else:
            category = "🔴 *GORENGAN (Lapis 3 | < Rp 5T)*"
            cat_score = 3
            
        # Pengecekan Fundamental Sederhana
        per = info.get('trailingPE')
        pbv = info.get('priceToBook')
        
        fundamental_alert = ""
        if per and per > 50:
            fundamental_alert += f"⚠️ PER Overvalued ({per:.1f}x) "
        if pbv and pbv > 10:
            fundamental_alert += f"⚠️ PBV Overvalued ({pbv:.1f}x) "

        df = stock.history(period="6mo")
        if df.empty or len(df) < 50:
            return None

        # 2. Filter Volume & Likuiditas (14 hari terakhir)
        last_14_days = df.tail(14)
        avg_volume = last_14_days['Volume'].mean()
        current_price = df['Close'].iloc[-1]
        
        avg_transaction_value = avg_volume * current_price
        
        liquidity_warning = ""
        # Jika transaksi di bawah Rp 5 Miliar per hari
        if avg_transaction_value < 5_000_000_000:
            liquidity_warning = "⚠️ TIDAK LIKUID (Risiko Nyangkut)"

        # 3. Indikator Dow Theory (Fase Markup)
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        
        sma20 = df['SMA_20'].iloc[-1]
        sma50 = df['SMA_50'].iloc[-1]
        
        is_uptrend = (current_price > sma20) and (sma20 > sma50)
        status = "✅ UPTREND" if is_uptrend else "❌ DOWNTREND"
        
        # 4. Manajemen Risiko: Stop Loss dinamis berbasis ATR
        df['High-Low'] = df['High'] - df['Low']
        df['High-PrevClose'] = abs(df['High'] - df['Close'].shift(1))
        df['Low-PrevClose'] = abs(df['Low'] - df['Close'].shift(1))
        df['TrueRange'] = df[['High-Low', 'High-PrevClose', 'Low-PrevClose']].max(axis=1)
        current_atr = df['TrueRange'].rolling(window=14).mean().iloc[-1]
        
        stop_loss = current_price - (2 * current_atr)
        
        # 5. Format Output yang Rapi
        report_line = f"*{ticker}* | {status} | Harga: Rp {current_price:,.0f} | SL: Rp {stop_loss:,.0f}"
        
        if liquidity_warning:
            report_line += f"\n    └ {liquidity_warning}"
        if fundamental_alert:
            report_line += f"\n    └ Fundamental: {fundamental_alert.strip()}"
            
        return {
            "category": category,
            "cat_score": cat_score,
            "market_cap": market_cap,
            "text": report_line
        }
    except Exception as e:
        return None

def send_telegram(message):
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print("\n=== HASIL SCREENER (Telegram Belum Disetting) ===")
        print(message)
        return
        
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

if __name__ == "__main__":
    print("Mesin Kuantitatif Memulai Pemindaian...")
    # Mengambil list saham, jika tidak ada secret akan memakai default 3 saham
    raw_stocks = os.environ.get('STOCK_LIST', 'BRIS.JK,TLKM.JK,GOTO.JK')
    tickers = [t.strip() for t in raw_stocks.split(',') if t.strip()]
    
    results = []
    for ticker in tickers:
        print(f"Menganalisis {ticker}...")
        res = calculate_technical_edge(ticker)
        if res:
            results.append(res)
            
    # Mengurutkan dari Lapis 1 -> 2 -> 3, dan Market Cap terbesar ke terkecil
    results.sort(key=lambda x: (x['cat_score'], -x['market_cap']))
    
    final_report = "📊 *SCREENER SAHAM SYARIAH (JII)* 📊\n"
    
    current_cat = None
    for res in results:
        if res['category'] != current_cat:
            current_cat = res['category']
            final_report += f"\n{current_cat}\n"
        
        final_report += f"• {res['text']}\n"
            
    send_telegram(final_report)
    print("Pemindaian Selesai.")