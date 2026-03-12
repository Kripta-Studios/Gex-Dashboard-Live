import os, sys, glob, argparse, requests
import pandas as pd, numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path

# ─── PDF compilation ───────────────────────────────────────────────────
def compile_pdf_local(tex_path: Path):
    import subprocess, shutil
    if not shutil.which("lualatex"):
        print(f"  [PDF] '{tex_path.name}' saved. Install LuaLaTeX to compile.")
        return
    print(f"  [PDF] Compiling {tex_path.name} via lualatex...")
    try:
        for _ in range(2):
            subprocess.run(
                ["lualatex", "-interaction=nonstopmode",
                 "-output-directory", str(tex_path.parent), str(tex_path.name)],
                cwd=str(tex_path.parent),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        pdf = tex_path.with_suffix('.pdf')
        if pdf.exists():
            print(f"  [PDF] Created {pdf.name}")
        else:
            print(f"  [PDF] Compilation may have failed — check .log file")
    except Exception as e:
        print(f"  [PDF] Error: {e}")

# ─── Style ─────────────────────────────────────────────────────────────
plt.style.use('default')
COLORS = {'GBT': '#0366D6', 'RL': '#D73A4A', 'DRAWDOWN': '#CB2431',
          'LONG': '#28A745', 'SHORT': '#CB2431', 'EXIT': '#586069'}

# ─── Helpers ───────────────────────────────────────────────────────────
def find_latest_backtest(results_dir: Path):
    mlp = sorted(list(results_dir.glob("gbt_only_*.csv")) +
                 list(results_dir.glob("mlp_only_*.csv")),
                 key=os.path.getmtime, reverse=True)
    rl  = sorted(list(results_dir.glob("gbt_rl_*.csv")) +
                 list(results_dir.glob("mlp_rl_*.csv")),
                 key=os.path.getmtime, reverse=True)
    if not mlp or not rl:
        print(f"No gbt_only_*.csv or gbt_rl_*.csv in {results_dir}")
        sys.exit(1)
    return mlp[0], rl[0]

def compute_drawdown(equity_s: pd.Series):
    rm = equity_s.cummax()
    dd_abs = equity_s - rm
    dd_pct = dd_abs / rm
    return dd_pct, dd_abs

def calc_metrics(df: pd.DataFrame) -> dict:
    """Calculate metrics matching backtest_rl.py calculate_metrics()."""
    if df.empty:
        return {"error": "No trades"}
    n = len(df)
    wins = df[df["pnl_dollars"] > 0]
    losses = df[df["pnl_dollars"] < 0]
    wr = len(wins) / n * 100
    gw = wins["pnl_dollars"].sum() if len(wins) > 0 else 0
    gl = abs(losses["pnl_dollars"].sum()) if len(losses) > 0 else 1e-6
    pf = gw / gl if gl > 0 else 0
    total_pnl = df["pnl_dollars"].sum()
    cum = df["pnl_dollars"].cumsum()
    max_dd = (cum - cum.cummax()).min()
    if n > 1:
        daily_ret = df.groupby("date")["pnl_dollars"].sum()
        sharpe = daily_ret.mean() / (daily_ret.std() + 1e-8) * np.sqrt(252)
    else:
        sharpe = 0
    mean_w = wins["pnl_pct"].mean() if len(wins) > 0 else 0
    mean_l = abs(losses["pnl_pct"].mean()) if len(losses) > 0 else 1e-6
    wl = mean_w / mean_l if mean_l > 0 else 0
    ah_w = wins["hold_minutes"].mean() if len(wins) > 0 else 0
    ah_l = losses["hold_minutes"].mean() if len(losses) > 0 else 0
    return {"total": n, "wins": len(wins), "losses": len(losses),
            "win_rate": wr, "pf": pf, "total_pnl": total_pnl,
            "max_dd": max_dd, "sharpe": sharpe, "wl_ratio": wl,
            "avg_hold_win": ah_w, "avg_hold_loss": ah_l}

def _esc(s):
    """Escape special LaTeX characters."""
    return str(s).replace('&', r'\&').replace('%', r'\%').replace('_', r'\_').replace('#', r'\#')

# ─── LaTeX document preamble (LuaLaTeX, colorful, modern) ─────────────
def latex_preamble():
    return r"""\documentclass[11pt,a4paper,twoside]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{mathpazo}
\usepackage[margin=1in]{geometry}
\usepackage{booktabs,longtable,tabularx,colortbl,multirow}
\usepackage{graphicx,float,xcolor,tikz,pgfplots}
\usepackage{fancyhdr,titlesec,enumitem}
\usepackage{hyperref}

% ─── Color Palette ───
\definecolor{bgdark}{HTML}{FFFFFF}
\definecolor{cardbg}{HTML}{F8F9FA}
\definecolor{accent}{HTML}{0366D6}
\definecolor{accentrl}{HTML}{D73A4A}
\definecolor{txtmain}{HTML}{24292E}
\definecolor{txtsub}{HTML}{586069}
\definecolor{wingreen}{HTML}{28A745}
\definecolor{lossred}{HTML}{CB2431}
\definecolor{rowalt}{HTML}{FFFFFF}
\definecolor{bordergray}{HTML}{E1E4E8}

\color{txtmain}

% ─── Header/Footer ───
\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0.4pt}
\renewcommand{\headrule}{\hbox to\headwidth{\color{bordergray}\leaders\hrule height \headrulewidth\hfill}}
\fancyhead[L]{\color{txtsub}\small GEX Dashboard Live}
\fancyhead[R]{\color{txtsub}\small Backtest Analysis Report}
\fancyfoot[C]{\color{txtsub}\small\thepage}

% ─── Section Styling ───
\titleformat{\section}{\Large\bfseries\color{accent}}{\thesection}{1em}{}[\color{bordergray}\titlerule]
\titleformat{\subsection}{\large\bfseries\color{accentrl}}{\thesubsection}{0.8em}{}
\titleformat{\subsubsection}{\normalsize\bfseries\color{txtmain}}{\thesubsubsection}{0.6em}{}

% ─── Custom commands ───
\newcommand{\metricbox}[3]{%
  \begin{tikzpicture}
    \node[fill=cardbg, rounded corners=4pt, minimum width=3.8cm, minimum height=1.6cm,
          draw=bordergray, line width=0.5pt, inner sep=6pt] (box) {
      \begin{minipage}{3.4cm}\centering
        {\color{txtsub}\scriptsize #1}\\[2pt]
        {\color{#3}\Large\bfseries #2}
      \end{minipage}
    };
  \end{tikzpicture}%
}
\newcommand{\pnlcolor}[1]{\ifnum#1>0\color{wingreen}\else\color{lossred}\fi}

\hypersetup{colorlinks=true,linkcolor=accent,urlcolor=accent}

\begin{document}
"""

# ─── LaTeX: Comparison Table ──────────────────────────────────────────
def latex_comparison(mlp_m, rl_m, out):
    out.append(r"\section*{GBT-Only vs GBT+RL Comparison}")
    out.append(r"\vspace{4pt}")

    # Metric cards row
    out.append(r"\noindent\begin{center}")
    out.append(r"\metricbox{GBT-Only Trades}{%d}{accent}" % mlp_m.get("total", 0))
    out.append(r"\hspace{4pt}")
    out.append(r"\metricbox{GBT+RL Trades}{%d}{accentrl}" % rl_m.get("total", 0))
    out.append(r"\hspace{4pt}")
    pf_imp = 0
    if mlp_m.get("pf", 0) > 0:
        pf_imp = (rl_m.get("pf", 0) / mlp_m.get("pf", 1) - 1) * 100
    pf_color = "wingreen" if pf_imp >= 0 else "lossred"
    out.append(r"\metricbox{PF Improvement}{%.1f\%%}{%s}" % (pf_imp, pf_color))
    out.append(r"\end{center}")
    out.append(r"\vspace{8pt}")

    # Main comparison table
    out.append(r"\noindent\begin{center}")
    out.append(r"\rowcolors{2}{cardbg}{rowalt}")
    out.append(r"\begin{tabular}{>{\color{txtmain}}l >{\color{accent}}r >{\color{accentrl}}r >{\color{txtsub}}r}")
    out.append(r"\toprule")
    out.append(r"\rowcolor{cardbg}")
    out.append(r"\textcolor{txtmain}{\textbf{Metric}} & \textcolor{accent}{\textbf{GBT-Only}} & \textcolor{accentrl}{\textbf{GBT+RL}} & \textcolor{txtsub}{\textbf{Delta}} \\")
    out.append(r"\midrule")

    def _row(label, key, fmt=".2f", invert=False):
        v1 = mlp_m.get(key, 0); v2 = rl_m.get(key, 0)
        d = v2 - v1
        sign = "+" if d > 0 else ""
        better = (d < 0) if invert else (d > 0)
        col = "wingreen" if better else "lossred"
        if abs(d) < 0.01: col = "txtsub"
        f1 = f"{v1:{fmt}}"; f2 = f"{v2:{fmt}}"; fd = f"{sign}{d:{fmt}}"
        out.append(f"{label} & {f1} & {f2} & \\textcolor{{{col}}}{{{fd}}} \\\\")

    _row("Total Trades", "total", "d", False)
    _row("Win Rate (\\%)", "win_rate", ".1f")
    _row("Profit Factor", "pf", ".2f")
    _row("Total P\\&L (\\$)", "total_pnl", ",.1f")
    _row("Max Drawdown (\\$)", "max_dd", ",.1f", True)
    _row("Sharpe Ratio", "sharpe", ".2f")
    _row("W/L Size Ratio", "wl_ratio", ".2f")
    _row("Avg Hold Win (min)", "avg_hold_win", ".0f", False)
    _row("Avg Hold Loss (min)", "avg_hold_loss", ".0f", True)

    out.append(r"\bottomrule")
    out.append(r"\end{tabular}")
    out.append(r"\end{center}")
    out.append(r"\vspace{6pt}")

# ─── LaTeX: Per-Ticker Breakdown ──────────────────────────────────────
def latex_ticker_breakdown(mlp_df, rl_df, out):
    out.append(r"\section*{Performance by Ticker}")

    for label, df, col in [("GBT-Only", mlp_df, "accent"), ("GBT+RL", rl_df, "accentrl")]:
        if df.empty:
            continue
        out.append(r"\subsection*{\textcolor{%s}{%s}}" % (col, label))
        out.append(r"\noindent\begin{center}")
        out.append(r"\rowcolors{2}{cardbg}{rowalt}")
        out.append(r"\begin{tabular}{>{\color{txtmain}}l rrrr}")
        out.append(r"\toprule")
        out.append(r"\rowcolor{cardbg}")
        out.append(r"\textbf{Ticker} & \textbf{Trades} & \textbf{WR (\%)} & \textbf{PF} & \textbf{P\&L (\$)} \\")
        out.append(r"\midrule")
        for t in sorted(df["ticker"].unique()):
            t_df = df[df["ticker"] == t]
            m = calc_metrics(t_df)
            if "error" in m: continue
            pnl = m["total_pnl"]
            pnl_col = "wingreen" if pnl >= 0 else "lossred"
            out.append(f"{t} & {m['total']} & {m['win_rate']:.1f} & {m['pf']:.2f} & \\textcolor{{{pnl_col}}}{{{pnl:+,.1f}}} \\\\")
        out.append(r"\bottomrule")
        out.append(r"\end{tabular}")
        out.append(r"\end{center}")
        out.append(r"\vspace{4pt}")

# ─── LaTeX: RL Exit Reasons ───────────────────────────────────────────
def latex_exit_reasons(rl_df, out):
    if rl_df.empty or "exit_reason" not in rl_df.columns:
        return
    out.append(r"\section*{RL Exit Reasons}")
    out.append(r"\noindent\begin{center}")
    out.append(r"\rowcolors{2}{cardbg}{rowalt}")
    out.append(r"\begin{tabular}{>{\color{txtmain}}l rr}")
    out.append(r"\toprule")
    out.append(r"\rowcolor{cardbg}")
    out.append(r"\textbf{Reason} & \textbf{Count} & \textbf{\%} \\")
    out.append(r"\midrule")
    total = len(rl_df)
    for reason, count in rl_df["exit_reason"].value_counts().items():
        pct = count / total * 100
        out.append(f"{_esc(reason)} & {count} & {pct:.1f}\\% \\\\")
    out.append(r"\bottomrule")
    out.append(r"\end{tabular}")
    out.append(r"\end{center}")

# ─── LaTeX: RL Strike Analysis ────────────────────────────────────────
def latex_strike_analysis(rl_df, out):
    if rl_df.empty or "strike_bucket" not in rl_df.columns:
        return
    out.append(r"\section*{RL Strike Analysis}")
    out.append(r"\noindent\begin{center}")
    out.append(r"\rowcolors{2}{cardbg}{rowalt}")
    out.append(r"\begin{tabular}{>{\color{txtmain}}l rrrrr>{\color{txtsub}}r}")
    out.append(r"\toprule")
    out.append(r"\rowcolor{cardbg}")
    out.append(r"\textbf{Bucket} & \textbf{Trades} & \textbf{\%} & \textbf{WR} & \textbf{PF} & \textbf{Avg Dist} & \textbf{Avg P\&L} \\")
    out.append(r"\midrule")
    total = len(rl_df)
    for bucket in ['deep_otm','otm_far','otm_near','otm_light','atm','itm_light','itm']:
        b_df = rl_df[rl_df['strike_bucket'] == bucket]
        if b_df.empty: continue
        bc = len(b_df)
        bp = bc / total * 100
        bw = len(b_df[b_df['pnl_dollars'] > 0]) / bc * 100
        gw = b_df[b_df['pnl_dollars'] > 0]['pnl_dollars'].sum()
        gl = abs(b_df[b_df['pnl_dollars'] < 0]['pnl_dollars'].sum())
        bpf = min(gw / gl, 999.99) if gl > 0 else (999.99 if gw > 0 else 0.0)
        bd = b_df['strike_distance_pts'].mean() if 'strike_distance_pts' in b_df.columns else 0
        ba = b_df['pnl_dollars'].mean()
        pnl_col = "wingreen" if ba >= 0 else "lossred"
        out.append(f"{_esc(bucket)} & {bc} & {bp:.1f}\\% & {bw:.1f}\\% & {bpf:.2f} & {bd:+.1f}p & \\textcolor{{{pnl_col}}}{{{ba:+,.2f}}} \\\\")
    out.append(r"\bottomrule")
    out.append(r"\end{tabular}")
    out.append(r"\end{center}")

# ─── LaTeX: Alpha vs Beta ─────────────────────────────────────────────
def latex_alpha_beta(mlp_df, rl_df, training_data_path, out):
    out.append(r"\section*{Alpha vs Beta Analysis}")
    # Try to load training data for market returns
    try:
        raw = pd.read_parquet(training_data_path)
        raw['date'] = raw['date'].astype(str)
        daily_grp = raw.groupby(['ticker','date'])['spot_price'].agg(['first','last']).reset_index()
        daily_grp['mkt_ret_pct'] = (daily_grp['last'] / daily_grp['first'] - 1) * 100
        daily_grp['mkt_dir'] = np.where(daily_grp['mkt_ret_pct'] > 0, 'UP', 'DOWN')
    except Exception as e:
        out.append(f"\\textcolor{{lossred}}{{Could not load training data for alpha/beta: {_esc(str(e))}}}")
        return

    for label, tdf, col in [("GBT-Only", mlp_df, "accent"), ("GBT+RL", rl_df, "accentrl")]:
        if tdf.empty: continue
        tdf = tdf.copy()
        tdf['date'] = tdf['date'].astype(str)
        merged = tdf.merge(daily_grp[['ticker','date','mkt_ret_pct','mkt_dir']], on=['ticker','date'], how='inner')

        up = merged[merged['mkt_dir'] == 'UP']
        dn = merged[merged['mkt_dir'] == 'DOWN']

        def _pf_wr(d):
            if d.empty: return 0,0
            w = len(d[d['pnl_dollars']>0])
            wr = w/len(d)*100
            gw = d[d['pnl_dollars']>0]['pnl_dollars'].sum()
            gl = abs(d[d['pnl_dollars']<0]['pnl_dollars'].sum())+1e-9
            return gw/gl, wr

        pf_up, wr_up = _pf_wr(up)
        pf_dn, wr_dn = _pf_wr(dn)

        daily_d = merged.groupby('date')['pnl_dollars'].sum().reset_index()
        daily_d['cum'] = daily_d['pnl_dollars'].cumsum()
        daily_d['start'] = 100_000 + daily_d['cum'].shift(1).fillna(0)
        daily_d['port_ret'] = (daily_d['pnl_dollars'] / daily_d['start']) * 100
        dm = daily_grp[['date','mkt_ret_pct']].drop_duplicates()
        ds = daily_d.merge(dm, on='date', how='inner')
        corr = ds['port_ret'].corr(ds['mkt_ret_pct'], method='spearman') if len(ds) > 1 else 0

        corr_col = "wingreen" if abs(corr) < 0.3 else ("accentrl" if abs(corr) < 0.6 else "lossred")

        out.append(r"\subsection*{\textcolor{%s}{%s Performance by Market Trend}}" % (col, label))
        out.append(r"\noindent\begin{center}")
        out.append(r"\metricbox{Rank Corr w/ Market}{%+.2f}{%s}" % (corr, corr_col))
        out.append(r"\hspace{4pt}")
        out.append(r"\metricbox{Market UP Trades}{%d}{wingreen}" % len(up))
        out.append(r"\hspace{4pt}")
        out.append(r"\metricbox{Market DOWN Trades}{%d}{lossred}" % len(dn))
        out.append(r"\end{center}")
        out.append(r"\vspace{4pt}")

        out.append(r"\noindent\begin{center}")
        out.append(r"\rowcolors{2}{cardbg}{rowalt}")
        out.append(r"\begin{tabular}{>{\color{txtmain}}l rrr}")
        out.append(r"\toprule")
        out.append(r"\rowcolor{cardbg}")
        out.append(r"\textbf{Market} & \textbf{Trades} & \textbf{WR (\%)} & \textbf{PF} \\")
        out.append(r"\midrule")
        out.append(f"UP Days & {len(up)} & {wr_up:.1f} & {pf_up:.2f} \\\\")
        out.append(f"DOWN Days & {len(dn)} & {wr_dn:.1f} & {pf_dn:.2f} \\\\")
        out.append(r"\bottomrule")
        out.append(r"\end{tabular}")
        out.append(r"\end{center}")
        out.append(r"\vspace{6pt}")

# ─── LaTeX: Detailed Strategy Analysis ────────────────────────────────
def latex_strategy_detail(df, name, color, out):
    """Detailed stats: monthly, best/worst trades, drawdown streaks."""
    if df.empty: return
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'].astype(str))
    df = df.sort_values('date').reset_index(drop=True)

    n = len(df)
    wins = df[df['pnl_dollars'] > 0]
    losses = df[df['pnl_dollars'] <= 0]
    wr = len(wins)/n*100 if n else 0
    gw = wins['pnl_dollars'].sum()
    gl = abs(losses['pnl_dollars'].sum())
    pf = gw/gl if gl > 0 else float('inf')
    if 'balance' not in df.columns:
        df['balance'] = 10000.0 + df['pnl_dollars'].cumsum()
    net = df['balance'].iloc[-1] - df['balance'].iloc[0]
    dd_pct, dd_abs = compute_drawdown(df['balance'])
    max_dd_p = dd_pct.min()*100
    max_dd_a = dd_abs.min()

    out.append(r"\section*{\textcolor{%s}{%s}}" % (color, name))

    # Metric cards
    out.append(r"\noindent\begin{center}")
    pnl_col = "wingreen" if net >= 0 else "lossred"
    out.append(r"\metricbox{Trades}{%d}{%s}" % (n, color))
    out.append(r"\hspace{3pt}")
    out.append(r"\metricbox{Win Rate}{%.1f\%%}{%s}" % (wr, "wingreen" if wr >= 50 else "lossred"))
    out.append(r"\hspace{3pt}")
    out.append(r"\metricbox{Profit Factor}{%.2f}{%s}" % (pf, "wingreen" if pf >= 1 else "lossred"))
    out.append(r"\hspace{3pt}")
    out.append(r"\metricbox{Net P\&L}{\$%s}{%s}" % (f"{net:,.0f}", pnl_col))
    out.append(r"\hspace{3pt}")
    out.append(r"\metricbox{Max DD}{\$%s}{lossred}" % f"{abs(max_dd_a):,.0f}")
    out.append(r"\hspace{3pt}")
    out.append(r"\metricbox{Avg Hold}{%.0f min}{txtsub}" % df['hold_minutes'].mean())
    out.append(r"\end{center}")
    out.append(r"\vspace{6pt}")

    # Monthly table
    out.append(r"\subsection*{Monthly Breakdown}")
    df['Month'] = df['date'].dt.to_period('M')
    monthly = df.groupby('Month').agg({'pnl_dollars': ['count', 'sum', lambda x: (x>0).mean()*100]})
    monthly.columns = ['Trades', 'PNL', 'WR']

    out.append(r"\noindent\begin{center}")
    out.append(r"\rowcolors{2}{cardbg}{rowalt}")
    out.append(r"\begin{tabular}{>{\color{txtmain}}l rrr}")
    out.append(r"\toprule")
    out.append(r"\rowcolor{cardbg}")
    out.append(r"\textbf{Month} & \textbf{Trades} & \textbf{WR (\%)} & \textbf{P\&L (\$)} \\")
    out.append(r"\midrule")
    for month, row in monthly.iterrows():
        p = row['PNL']
        pc = "wingreen" if p >= 0 else "lossred"
        out.append(f"{month} & {row['Trades']:.0f} & {row['WR']:.1f} & \\textcolor{{{pc}}}{{{p:,.2f}}} \\\\")
    out.append(r"\bottomrule")
    out.append(r"\end{tabular}")
    out.append(r"\end{center}")

    # Top/Bottom 5
    for title, sub_df in [("Top 5 Winners", df.nlargest(5, 'pnl_dollars')),
                          ("Top 5 Losers", df.nsmallest(5, 'pnl_dollars'))]:
        out.append(r"\subsection*{%s}" % title)
        out.append(r"\noindent\begin{center}")
        out.append(r"\rowcolors{2}{cardbg}{rowalt}")
        out.append(r"\begin{tabular}{>{\color{txtmain}}l llll r}")
        out.append(r"\toprule")
        out.append(r"\rowcolor{cardbg}")
        out.append(r"\textbf{Date} & \textbf{Entry} & \textbf{Ticker} & \textbf{Dir} & \textbf{Hold} & \textbf{P\&L (\$)} \\")
        out.append(r"\midrule")
        for _, t in sub_df.iterrows():
            d = t['date'].strftime('%Y-%m-%d') if hasattr(t['date'], 'strftime') else str(t['date'])[:10]
            et = t.get('entry_time', '')
            tk = t.get('ticker', '')
            dr = t.get('direction', '')
            hm = t.get('hold_minutes', 0)
            pnl = t['pnl_dollars']
            pc = "wingreen" if pnl >= 0 else "lossred"
            out.append(f"{d} & {et} & {tk} & {dr} & {hm:.0f}m & \\textcolor{{{pc}}}{{{pnl:,.2f}}} \\\\")
        out.append(r"\bottomrule")
        out.append(r"\end{tabular}")
        out.append(r"\end{center}")

    out.append(r"\clearpage")

# ─── LaTeX: Full Trade Log ─────────────────────────────────────────────
def latex_full_trade_log(df, name, color, out):
    """Outputs a complete table of all trades in a longtable environment."""
    if df.empty: return
    df = df.copy()
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'].astype(str))
    df = df.sort_values(by=['date', 'entry_time']).reset_index(drop=True)

    out.append(r"\section*{\textcolor{%s}{Full Trade Log: %s}}" % (color, name))
    
    # We use a longtable so it can break across pages.
    out.append(r"\begin{center}")
    out.append(r"\small") # Use a smaller font size to fit everything
    out.append(r"\rowcolors{2}{cardbg}{rowalt}")
    out.append(r"\begin{longtable}{>{\color{txtmain}}l l l l l r r r r r >{\color{txtmain}}l r}")
    out.append(r"\toprule")
    out.append(r"\rowcolor{cardbg}")
    out.append(r"\textbf{Date} & \textbf{In} & \textbf{Out} & \textbf{Tckr} & \textbf{Dir} & \textbf{Entry} & \textbf{Exit} & \textbf{\%\(\Delta\)Spot} & \textbf{\%\(\Delta\)Prem} & \textbf{Hold} & \textbf{Reason} & \textbf{P\&L (\$)} \\")
    out.append(r"\midrule")
    out.append(r"\endfirsthead")
    
    out.append(r"\toprule")
    out.append(r"\rowcolor{cardbg}")
    out.append(r"\textbf{Date} & \textbf{In} & \textbf{Out} & \textbf{Tckr} & \textbf{Dir} & \textbf{Entry} & \textbf{Exit} & \textbf{\%\(\Delta\)Spot} & \textbf{\%\(\Delta\)Prem} & \textbf{Hold} & \textbf{Reason} & \textbf{P\&L (\$)} \\")
    out.append(r"\midrule")
    out.append(r"\endhead")
    
    out.append(r"\midrule")
    out.append(r"\multicolumn{12}{r}{\textit{Continued on next page...}} \\")
    out.append(r"\endfoot")
    
    out.append(r"\bottomrule")
    out.append(r"\endlastfoot")

    for _, t in df.iterrows():
        d = t['date'].strftime('%m-%d') if hasattr(t['date'], 'strftime') else str(t['date'])[5:10]
        et = str(t.get('entry_time', ''))
        ex_t = str(t.get('exit_time', ''))
        tk = str(t.get('ticker', ''))
        dr = str(t.get('direction', ''))
        
        entry_spot = float(t.get('entry_price', 0))
        exit_spot = float(t.get('exit_price', 0))
        
        # Spot movement percent relative to entry
        if entry_spot > 0:
            spot_pct = (exit_spot - entry_spot) / entry_spot * 100.0
            if dr == 'SHORT':
                spot_pct = -spot_pct
        else:
            spot_pct = 0.0
            
        # Premium/Overall movement percent
        prem_pct = float(t.get('pnl_pct', 0)) * 100.0
        
        if 'entry_premium' in t and t['entry_premium'] > 0:
            entry_val = f"{t['entry_premium']:.2f}"
            exit_val = f"{t.get('exit_premium', 0):.2f}"
        else:
            entry_val = f"{entry_spot:.2f}"
            exit_val = f"{exit_spot:.2f}"

        hm = t.get('hold_minutes', 0)
        rs = _esc(str(t.get('exit_reason', '')))
        
        pnl = t.get('pnl_dollars', 0.0)
        pc = "wingreen" if pnl >= 0 else "lossred"
        
        spot_pc = "wingreen" if spot_pct >= 0 else "lossred"
        prem_pc = "wingreen" if prem_pct >= 0 else "lossred"

        out.append(f"{d} & {et} & {ex_t} & {tk} & {dr} & {entry_val} & {exit_val} & \\textcolor{{{spot_pc}}}{{{spot_pct:+.2f}\\%}} & \\textcolor{{{prem_pc}}}{{{prem_pct:+.2f}\\%}} & {hm:.0f}m & {rs} & \\textcolor{{{pc}}}{{{pnl:,.2f}}} \\\\")

    out.append(r"\end{longtable}")
    out.append(r"\end{center}")
    out.append(r"\clearpage")

# ─── Charts ────────────────────────────────────────────────────────────
def plot_equity_curves(mlp_df, rl_df, output_dir, prefix=""):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    for df, name, ax, c in zip([mlp_df, rl_df], ['GBT-Only', 'GBT+RL'],
                                [ax1, ax2], [COLORS['GBT'], COLORS['RL']]):
        if df.empty: continue
        d = df.copy()
        d['date'] = pd.to_datetime(d['date'].astype(str))
        if 'balance' not in d.columns:
            d['balance'] = 10000.0 + d['pnl_dollars'].cumsum()
        w = d.set_index('date').resample('D')['balance'].last().ffill()
        ax.plot(w.index, w.values, color=c, linewidth=2, label=f'Balance {name}')
        ax.fill_between(w.index, w.values, w.iloc[0], color=c, alpha=0.1)
        _, dd = compute_drawdown(w)
        ax2t = ax.twinx()
        ax2t.fill_between(dd.index, dd.values, 0, color=COLORS['DRAWDOWN'], alpha=0.3)
        ax2t.set_ylabel('Drawdown ($)', color=COLORS['DRAWDOWN'])
        ax.set_title(f'Equity: {name} (Daily)', fontsize=14)
        ax.set_ylabel('Balance ($)')
        ax.grid(True, alpha=0.2, linestyle='--')
    plt.tight_layout()
    plt.savefig(output_dir / f'{prefix}equity_curves.png', dpi=300, bbox_inches='tight')
    plt.close()

def plot_strike_pie(rl_df, output_dir, prefix=""):
    if 'strike_bucket' not in rl_df.columns or rl_df.empty: return
    bc = rl_df['strike_bucket'].value_counts()
    plt.figure(figsize=(10, 8))
    plt.pie(bc.values, labels=bc.index, autopct='%1.1f%%', startangle=90,
            colors=plt.cm.viridis(np.linspace(0, 1, len(bc))))
    plt.title('RL Strike Distribution', fontsize=16)
    plt.savefig(output_dir / f'{prefix}rl_strike_distribution.png', dpi=300, bbox_inches='tight')
    plt.close()

# ─── MAIN ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Analyze backtest results — Full Report")
    parser.add_argument("--month", type=str, default=None, help="Filter month YYYYMM")
    parser.add_argument("--mlp-file", type=str, default=None)
    parser.add_argument("--rl-file", type=str, default=None)
    parser.add_argument("--training-data", type=str, default=None, help="Path to training parquet for alpha/beta")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    results_dir = project_root / "backtest_results"
    out_dir = script_dir / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Find / load CSVs
    if args.mlp_file and args.rl_file:
        mlp_path, rl_path = Path(args.mlp_file), Path(args.rl_file)
    else:
        mlp_path, rl_path = find_latest_backtest(results_dir)
    print(f"GBT file: {mlp_path.name}")
    print(f"RL file:  {rl_path.name}")

    try: mlp_df = pd.read_csv(mlp_path)
    except Exception as e: print(f"Load GBT failed: {e}"); mlp_df = pd.DataFrame()
    try: rl_df = pd.read_csv(rl_path)
    except Exception as e: print(f"Load RL failed: {e}"); rl_df = pd.DataFrame()

    # Normalize dates
    for df in [mlp_df, rl_df]:
        if 'date' in df.columns:
            df['date'] = df['date'].astype(str)

    # Month filter
    if args.month:
        tp = pd.Period(args.month, freq='M')
        for label, df in [("GBT", mlp_df), ("RL", rl_df)]:
            if df.empty: continue
            df['_td'] = pd.to_datetime(df['date'])
            mask = df['_td'].dt.to_period('M') == tp
            if label == "GBT": mlp_df = df[mask].drop(columns=['_td'])
            else: rl_df = df[mask].drop(columns=['_td'])
        print(f"Month filter {args.month}: {len(mlp_df)} GBT, {len(rl_df)} RL trades")

    # Compute metrics (ALL tickers combined = overall)
    mlp_m = calc_metrics(mlp_df)
    rl_m  = calc_metrics(rl_df)

    # Training data path for alpha/beta
    if args.training_data:
        td_path = Path(args.training_data)
    else:
        # Auto-detect latest training data
        candidates = [
            project_root / "training_data" / "training_data_spx_qqq_march.parquet",
            project_root / "training_data" / "training_data_spx_qqq.parquet",
            project_root / "training_data" / "training_data_derived.parquet",
        ]
        td_path = None
        for c in candidates:
            if c.exists():
                td_path = c
                break

    # ─── Generate charts FIRST (so PNGs exist for LaTeX) ───
    prefix = f"{args.month}_" if args.month else "All_"
    print("Generating charts...")
    plot_equity_curves(mlp_df, rl_df, out_dir, prefix)
    plot_strike_pie(rl_df, out_dir, prefix)
    print(f"Charts saved to: {out_dir}")

    # Chart file paths (relative to .tex location = out_dir)
    equity_png = f"{prefix}equity_curves.png"
    strike_png = f"{prefix}rl_strike_distribution.png"

    # ─── Build LaTeX ───
    tex = []
    tex.append(latex_preamble())

    # Title
    month_label = f" — {args.month}" if args.month else " — All Time"
    tickers_in_data = set()
    if 'ticker' in mlp_df.columns: tickers_in_data.update(mlp_df['ticker'].unique())
    if 'ticker' in rl_df.columns: tickers_in_data.update(rl_df['ticker'].unique())
    tickers_str = ", ".join(sorted(tickers_in_data)) if tickers_in_data else "ALL"

    tex.append(r"\begin{center}")
    tex.append(r"{\Huge\bfseries\color{accent} GEX Dashboard Live}\\[6pt]")
    tex.append(r"{\Large\color{txtsub} Backtest Analysis Report%s}\\[4pt]" % month_label)
    tex.append(r"{\normalsize\color{txtsub} Tickers: %s \quad|\quad GBT: %s \quad|\quad RL: %s}" % (
        tickers_str, _esc(mlp_path.name), _esc(rl_path.name)))
    tex.append(r"\end{center}")
    tex.append(r"\vspace{12pt}")
    tex.append(r"\noindent\textcolor{bordergray}{\rule{\textwidth}{0.5pt}}")
    tex.append(r"\vspace{8pt}")

    # 1. Comparison
    latex_comparison(mlp_m, rl_m, tex)
    # 2. Per-ticker
    latex_ticker_breakdown(mlp_df, rl_df, tex)
    tex.append(r"\clearpage")
    # 3. Detailed GBT-Only
    latex_strategy_detail(mlp_df, "GBT-Only (Synthetic Futures)", "accent", tex)
    # 4. Detailed GBT+RL
    latex_strategy_detail(rl_df, "GBT+RL (Real Options)", "accentrl", tex)
    # 5. RL Exit Reasons
    latex_exit_reasons(rl_df, tex)
    # 6. Strike Analysis
    latex_strike_analysis(rl_df, tex)
    tex.append(r"\clearpage")
    # 7. Alpha vs Beta
    if td_path and td_path.exists():
        latex_alpha_beta(mlp_df, rl_df, td_path, tex)
    else:
        tex.append(r"\section*{Alpha vs Beta Analysis}")
        tex.append(r"\textcolor{txtsub}{Training data not found — skipping alpha/beta analysis.}")
        tex.append(r"\textcolor{txtsub}{Use --training-data to specify path.}")

    # 8. Embedded Charts
    tex.append(r"\clearpage")
    tex.append(r"\section*{Charts}")

    # Equity curves
    equity_path = out_dir / equity_png
    if equity_path.exists():
        tex.append(r"\subsection*{Equity Curves}")
        tex.append(r"\begin{center}")
        tex.append(r"\includegraphics[width=0.95\textwidth]{" + equity_png + r"}")
        tex.append(r"\end{center}")
        tex.append(r"\vspace{8pt}")

    # Strike distribution
    strike_path = out_dir / strike_png
    if strike_path.exists():
        tex.append(r"\subsection*{RL Strike Distribution}")
        tex.append(r"\begin{center}")
        tex.append(r"\includegraphics[width=0.7\textwidth]{" + strike_png + r"}")
        tex.append(r"\end{center}")

    tex.append(r"\clearpage")

    # 9. Full Trade Logs Appendix
    latex_full_trade_log(mlp_df, "GBT-Only", "accent", tex)
    latex_full_trade_log(rl_df, "GBT+RL", "accentrl", tex)

    tex.append(r"\end{document}")

    # Save .tex and compile
    report_path = out_dir / f"{prefix}backtest_analysis_report.tex"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(tex))
    print(f"\nReport saved: {report_path}")
    compile_pdf_local(report_path)

if __name__ == "__main__":
    main()
