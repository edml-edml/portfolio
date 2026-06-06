import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import io
import os

# --- 1. WEBアプリのUI設定 ---
st.set_page_config(page_title="MT5 Portfolio Analyzer", layout="wide")
st.title("📊 MT5 ポートフォリオ合成・分析ツール")
st.write("2つ以上のMT5履歴CSVファイルをアップロードして、ポートフォリオのリスク分散効果を分析します。")

# --- 2. ファイルアップロード部品（Streamlit専用） ---
uploaded_files = st.file_uploader(
    "MT5の履歴CSVファイルをアップロードしてください（複数選択可）", 
    type="csv", 
    accept_multiple_files=True
)

# --- 3. データパース関数の定義 ---
def parse_mt5_csv(file_bytes):
    try:
        text = file_bytes.decode('shift-jis')
    except UnicodeDecodeError:
        try:
            text = file_bytes.decode('utf-8')
        except UnicodeDecodeError:
            text = file_bytes.decode('utf-16')

    # 【修正箇所】「時間」と「損益」の両方が含まれる行をヘッダーとして厳密に検索
    lines = text.splitlines()
    header_idx = 0
    for i, line in enumerate(lines):
        if ('損益' in line and '時間' in line) or ('Profit' in line and 'Time' in line):
            header_idx = i
            break

    df = pd.read_csv(io.StringIO(text), skiprows=header_idx)
    df.columns = [str(c).strip() for c in df.columns]
    
    time_col = [c for c in df.columns if any(k in c for k in ['Time', '時間', '日付', 'Date'])][0]
    profit_col = [c for c in df.columns if any(k in c for k in ['Profit', '利益', '損益'])][0]
    
    df[time_col] = pd.to_datetime(df[time_col].astype(str).str.replace('.', '-', regex=False), errors='coerce')
    df[profit_col] = df[profit_col].astype(str).str.replace(' ', '', regex=False).str.replace(',', '', regex=False)
    df[profit_col] = pd.to_numeric(df[profit_col], errors='coerce').fillna(0)
    
    df = df.dropna(subset=[time_col])
    
    df_daily = df.groupby(df[time_col].dt.date)[profit_col].sum().reset_index()
    df_daily.columns = ['Date', 'Profit']
    df_daily['Date'] = pd.to_datetime(df_daily['Date'])
    df_daily.set_index('Date', inplace=True)
    
    return df_daily

# --- 4. 統計計算関数 ---
def calculate_metrics(equity_series):
    total_profit = equity_series.iloc[-1]
    peak = equity_series.cummax()
    dd = (peak - equity_series).max()
    return total_profit, dd

# --- 5. メイン処理（ファイルが2つ以上アップロードされたら実行） ---
if uploaded_files and len(uploaded_files) >= 2:
    st.success(f"✅ {len(uploaded_files)}つのファイルを読み込みました。解析結果は以下の通りです。")
    
    dfs = {}
    for uploaded_file in uploaded_files:
        label = os.path.splitext(uploaded_file.name)[0]
        # Streamlitでは .read() でバイトデータを取得
        dfs[label] = parse_mt5_csv(uploaded_file.read())

    # 時間軸の同期
    min_date = min([df.index.min() for df in dfs.values()])
    max_date = max([df.index.max() for df in dfs.values()])
    all_dates = pd.date_range(start=min_date, end=max_date, freq='D')

    portfolio = pd.DataFrame(index=all_dates)
    
    for label, df in dfs.items():
        portfolio[f'Profit_{label}'] = df['Profit']
        
    portfolio.fillna(0, inplace=True)

    equity_cols = []
    for label in dfs.keys():
        col_name = f'Equity_{label}'
        portfolio[col_name] = portfolio[f'Profit_{label}'].cumsum()
        equity_cols.append(col_name)

    portfolio['Equity_Total'] = portfolio[equity_cols].sum(axis=1)

    # --- 6. 結果のWEB表示（見栄えの良いカラム表示） ---
    st.subheader("📊 ポートフォリオ合成・分析レポート")
    
    metrics = {}
    for label in dfs.keys():
        metrics[label] = calculate_metrics(portfolio[f'Equity_{label}'])
    profit_Total, dd_Total = calculate_metrics(portfolio['Equity_Total'])

    # Total結果を大きく表示
    col1, col2 = st.columns(2)
    col1.metric("🚀 合成 総損益 (Total)", f"¥ {profit_Total:,.0f}")
    col2.metric("🛡️ 合成 最大DD (Total)", f"¥ {dd_Total:,.0f}")
    
    st.divider()
    
    # 各単体の結果を表示
    cols = st.columns(len(metrics))
    for i, (label, (profit, dd)) in enumerate(metrics.items()):
        cols[i].write(f"**【{label}】**")
        cols[i].write(f"総損益: ¥ {profit:,.0f}")
        cols[i].write(f"最大DD: ¥ {dd:,.0f}")

    # --- 7. グラフのWEB表示 ---
    st.subheader("📈 資産曲線グラフ (Equity Curve)")
    
    fig, ax = plt.subplots(figsize=(14, 7))
    line_colors = ['#2ecc71', '#f1c40f', '#3498db', '#9b59b6', '#e67e22', '#7f8c8d']
    
    for i, label in enumerate(dfs.keys()):
        color = line_colors[i % len(line_colors)]
        ax.plot(portfolio.index, portfolio[f'Equity_{label}'], label=label, color=color, alpha=0.6, linestyle='--')

    ax.plot(portfolio.index, portfolio['Equity_Total'], label='Combined Portfolio (Total)', color='#e74c3c', linewidth=3.0)

    ax.set_title(f'Portfolio Equity Curve Analysis ({len(dfs)} Strategies combined)', fontsize=16, fontweight='bold', pad=15)
    ax.set_xlabel('Timeline', fontsize=12)
    ax.set_ylabel('Cumulative Profit / Loss (JPY)', fontsize=12)
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend(fontsize=10, loc='upper left')
    ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}'))

    plt.tight_layout()
    
    # Streamlitでグラフを描画
    st.pyplot(fig)

elif uploaded_files and len(uploaded_files) == 1:
    st.warning("⚠️ ポートフォリオ合成には最低2つのファイルが必要です。もう1つファイルを追加してください。")