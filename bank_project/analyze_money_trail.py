#!/usr/bin/env python3
"""
analyze_money_trail.py
- Reads a transactions CSV
- Builds a directed graph
- Detects directed simple cycles up to length 6 (layering)
- Computes per-account features and a simple risk score
- Produces outputs:
    - accounts_analysis.csv (full per-account features + risk)
    - suspicious_accounts.csv (High+Medium risk)
    - network_plot.png (visual snapshot)
Usage:
    python analyze_money_trail.py --input sample_transactions.csv --outdir output
If no input provided, script will generate a demo sample CSV automatically.
"""
import os, csv, argparse, datetime, random
from collections import defaultdict
import pandas as pd
import matplotlib.pyplot as plt

def make_demo_csv(path, n_accounts=80, n_random_tx=300):
    accounts = [f"AC{str(i).zfill(4)}" for i in range(1, n_accounts+1)]
    rows = []
    txn_id = 1
    base_time = datetime.datetime(2025,10,1,9,0,0)
    def add_tx(s,r,amt,ts):
        nonlocal txn_id
        rows.append({
            "txn_id": f"t{txn_id:06d}",
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "sender_account": s,
            "receiver_account": r,
            "amount": round(amt,2),
            "channel": random.choice(["NEFT","IMPS","RTGS","CASH"])
        })
        txn_id += 1

    random.seed(42)
    # random normal transactions
    for _ in range(n_random_tx):
        s = random.choice(accounts)
        r = random.choice(accounts)
        if r==s: continue
        amt = random.uniform(100,50000)
        ts = base_time + datetime.timedelta(minutes=random.randint(0,60*48))
        add_tx(s,r,amt,ts)

    # intentional cycle 1
    cyc1 = ["AC0001","AC0002","AC0003"]
    t0 = datetime.datetime(2025,10,2,10,0,0)
    for i in range(4):
        for a,b in zip(cyc1, cyc1[1:]+cyc1[:1]):
            add_tx(a,b, random.uniform(40000,50000), t0 + datetime.timedelta(minutes=i*5))

    # intentional cycle 2
    cyc2 = ["AC0050","AC0051","AC0052"]
    t1 = datetime.datetime(2025,10,3,12,0,0)
    for i in range(2):
        for a,b in zip(cyc2, cyc2[1:]+cyc2[:1]):
            add_tx(a,b, random.uniform(20000,30000), t1 + datetime.timedelta(minutes=i*3))

    # structuring pattern
    origin = "AC0070"
    t2 = datetime.datetime(2025,10,4,9,0,0)
    for i in range(25):
        target = random.choice(accounts)
        if target == origin: continue
        add_tx(origin, target, random.uniform(500,2000), t2 + datetime.timedelta(minutes=i))

    # write csv
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["txn_id","timestamp","sender_account","receiver_account","amount","channel"])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

def load_and_aggregate(input_csv):
    df = pd.read_csv(input_csv, encoding="utf-8-sig", parse_dates=["timestamp"])
      # temporary exit after printing

    edge_agg = defaultdict(lambda: {"amount":0.0, "count":0})
    for _, row in df.iterrows():
        s = row["sender_account"]
        r = row["receiver_account"]
        amt = float(row["amount"])
        key = (s,r)
        edge_agg[key]["amount"] += amt
        edge_agg[key]["count"] += 1
    nodes = sorted(set(df["sender_account"]).union(set(df["receiver_account"])))
    return df, edge_agg, nodes

def build_adj(edge_agg):
    adj = defaultdict(set)
    for (s,r),v in edge_agg.items():
        adj[s].add(r)
    return adj

def detect_cycles(adj, nodes, max_cycle_len=6):
    cycles = set()
    # DFS search from each node
    def dfs(start, current, visited, path):
        if len(path) > max_cycle_len:
            return
        for nb in adj.get(current, []):
            if nb == start and len(path) >= 2:
                cyc = tuple(path + [start])
                # canonical rotation - represent cycle by lexicographically smallest rotation
                rots = []
                L = len(cyc)-1
                seq = cyc[:-1]
                for i in range(L):
                    rot = seq[i:]+seq[:i]
                    rots.append(tuple(rot))
                canon = min(rots)
                cycles.add(canon)
            elif nb not in visited and nb != start:
                visited.add(nb)
                dfs(start, nb, visited, path + [nb])
                visited.remove(nb)
    for n in nodes:
        dfs(n,n,set(),[n])
    return list(cycles)

def compute_account_features(nodes, edge_agg, df, cycles_list):
    node_cycle_count = defaultdict(int)
    for cyc in cycles_list:
        for n in cyc:
            node_cycle_count[n] += 1
    account_stats = {}
    for node in nodes:
        in_edges = [(s,r,v) for (s,r),v in edge_agg.items() if r==node]
        out_edges = [(s,r,v) for (s,r),v in edge_agg.items() if s==node]
        in_amt = sum(x[2]["amount"] for x in in_edges)
        out_amt = sum(x[2]["amount"] for x in out_edges)
        in_cnt = sum(x[2]["count"] for x in in_edges)
        out_cnt = sum(x[2]["count"] for x in out_edges)
        distinct_counterparties = len(set([x[0] for x in in_edges] + [x[1] for x in out_edges]))
        avg_amt = ((in_amt + out_amt) / max(1, (in_cnt+out_cnt)))
        cycle_count = node_cycle_count.get(node,0)
        account_stats[node] = {
            "in_amount": in_amt,
            "out_amount": out_amt,
            "in_count": in_cnt,
            "out_count": out_cnt,
            "distinct_counterparties": distinct_counterparties,
            "avg_amount": avg_amt,
            "cycle_count": cycle_count
        }
    acct_df = pd.DataFrame.from_dict(account_stats, orient="index").reset_index().rename(columns={"index":"account"})
    # normalize
    def normalize_col(s):
        return (s - s.min())/(s.max()-s.min()) if s.max()!=s.min() else s*0.0
    acct_df["cycle_norm"] = normalize_col(acct_df["cycle_count"])
    acct_df["burst_norm"] = normalize_col(acct_df["out_count"] + acct_df["in_count"])
    acct_df["struct_norm"] = acct_df["avg_amount"].apply(lambda x: 1.0 if x < 2500 else 0.0)
    acct_df["pagerank_norm"] = normalize_col(acct_df["out_amount"] + acct_df["in_amount"])
    acct_df["risk_score"] = 0.45*acct_df["cycle_norm"] + 0.25*acct_df["burst_norm"] + 0.15*acct_df["struct_norm"] + 0.15*acct_df["pagerank_norm"]
    acct_df["risk_score"] = acct_df["risk_score"].clip(0,1)
    def category(x):
        if x >= 0.7: return "High"
        if x >= 0.4: return "Medium"
        return "Low"
    acct_df["risk_category"] = acct_df["risk_score"].apply(category)
    def top_reason(row):
        reasons=[]
        if row["cycle_count"]>0: reasons.append(f"Cycle({int(row['cycle_count'])})")
        if (row["in_count"]+row["out_count"])>20: reasons.append("BurstTxns")
        if row["avg_amount"]<2500: reasons.append("Structuring")
        if not reasons: reasons.append("UnusualPattern")
        return ", ".join(reasons)
    acct_df["top_reason"] = acct_df.apply(top_reason, axis=1)
    return acct_df

def save_outputs(acct_df, outdir):
    os.makedirs(outdir, exist_ok=True)
    full_csv = os.path.join(outdir, "accounts_analysis.csv")
    suspicious_csv = os.path.join(outdir, "suspicious_accounts.csv")
    acct_df.to_csv(full_csv, index=False)
    suspicious = acct_df[acct_df["risk_category"]!="Low"].sort_values("risk_score", ascending=False)
    suspicious.to_csv(suspicious_csv, index=False)
    return full_csv, suspicious_csv

def try_plot_network(edge_agg, acct_df, outdir):
    try:
        import networkx as nx
        G = nx.DiGraph()
        for (s,r),v in edge_agg.items():
            G.add_edge(s,r, weight=v["amount"], count=v["count"])
        pos = nx.spring_layout(G, seed=8)
        plt.figure(figsize=(10,8))
        node_list = list(G.nodes())
        score_map = acct_df.set_index("account")["risk_score"].to_dict()
        sizes = [200 + 1800 * score_map.get(n, 0) for n in node_list]
        nx.draw_networkx_edges(G, pos, alpha=0.2, arrowsize=8)
        nx.draw_networkx_nodes(G, pos, node_size=sizes)
        nx.draw_networkx_labels(G, pos, font_size=7)
        plt.axis("off")
        path = os.path.join(outdir, "network_plot.png")
        plt.title("Transaction Network (node size ~ risk score)")
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()
        return path
    except Exception as e:
        # fallback: simple scatter of node ids (no network)
        try:
            plt.figure(figsize=(8,5))
            acct_df_sorted = acct_df.sort_values("risk_score", ascending=False).head(30)
            plt.bar(range(len(acct_df_sorted)), acct_df_sorted["risk_score"])
            plt.xticks(range(len(acct_df_sorted)), acct_df_sorted["account"], rotation=90)
            plt.tight_layout()
            path = os.path.join(outdir, "network_plot_bar.png")
            plt.savefig(path, dpi=150, bbox_inches="tight")
            plt.close()
            return path
        except Exception as e2:
            return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", help="input transactions CSV (if omitted a demo CSV will be generated)", default=None)
    parser.add_argument("--outdir", help="output directory", default="output")
    args = parser.parse_args()

    if args.input is None:
        demo_path = os.path.join(args.outdir, "sample_transactions.csv")
        os.makedirs(args.outdir, exist_ok=True)
        print("No input given — generating demo CSV at", demo_path)
        make_demo_csv(demo_path)
        input_csv = demo_path
    else:
        input_csv = args.input

    print("Loading ", input_csv)
    df, edge_agg, nodes = load_and_aggregate(input_csv)
    adj = build_adj(edge_agg)
    print("Detecting cycles (this may take a little time for very large graphs)...")
    cycles = detect_cycles(adj, nodes, max_cycle_len=6)
    print(f"Found {len(cycles)} unique cycles (length <=6)")
    acct_df = compute_account_features(nodes, edge_agg, df, cycles)
    full_csv, suspicious_csv = save_outputs(acct_df, args.outdir)
    print("Saved full analysis:", full_csv)
    print("Saved suspicious accounts (High+Medium):", suspicious_csv)
    imgpath = try_plot_network(edge_agg, acct_df, args.outdir)
    if imgpath:
        print("Network image saved at:", imgpath)
    else:
        print("Network image not created.")
    print("Top 10 suspicious accounts:")
    print(acct_df[acct_df["risk_category"]!="Low"].sort_values("risk_score", ascending=False).head(10).to_string(index=False))

if __name__ == "__main__":
    main()
