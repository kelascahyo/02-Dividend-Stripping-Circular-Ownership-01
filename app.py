import streamlit as st
import pandas as pd
import networkx as nx
import json
from jinja2 import Template

# Pengaturan Konfigurasi Utama Halaman Streamlit
st.set_page_config(
    page_title="Tax Fraud Analytical Tools: Dividend Stripping Network Detector",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Kustomisasi tema CSS agar background gelap seragam
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    h1, h2, h3 { color: #ff4b4b !important; }
    .stAlert p { color: #000000 !important; }
    </style>
""", unsafe_allow_index=True)

# --- FUNGSI LOAD DATA (DI-CACHE SUPAYA PERFORMA CEPAT) ---
@st.cache_data
def load_graph_data():
    # Load dataset masked
    nodes_df = pd.read_csv("nodes_masked.csv")
    edges_df = pd.read_csv("edges_masked_part1_a.csv")
    
    # Inisialisasi Directed Graph dengan NetworkX
    G = nx.DiGraph()
    
    # Daftarkan properti node ke dalam graf
    for _, row in nodes_df.iterrows():
        G.add_node(
            int(row['id']), 
            nama=row['nama'], 
            jenis_node=row['jenis_node'],
            is_in_cycle=False
        )
        
    # Tambahkan relasi edge (sumber -> target) ke graf
    for _, row in edges_df.iterrows():
        G.add_edge(
            int(row['sumber']), 
            int(row['target']),
            rel_id=int(row['rel_id']),
            persentase=float(row['persentase']),
            nilai=float(row['nilai']),
            dividen=float(row['dividen']),
            is_cycle=False
        )
    return G, nodes_df, edges_df

# --- EKSEKUSI DETEKSI SIKLUS (CYCLE DETECTION) ---
def analyze_cycles(G):
    # Menggunakan algoritma berbasis basis data untuk menemukan seluruh siklus tertutup (Simple Cycles)
    all_cycles = list(nx.simple_cycles(G))
    
    # Himpunan penampung node dan edge yang terlibat di dalam siklus melingkar
    cycle_nodes = set()
    cycle_edges = set()
    
    for cycle in all_cycles:
        for i in range(len(cycle)):
            u = cycle[i]
            v = cycle[(i + 1) % len(cycle)]
            cycle_nodes.add(u)
            cycle_edges.add((u, v))
            
            # Ubah status flag internal pada objek graf NetworkX
            if G.has_node(u):
                G.nodes[u]['is_in_cycle'] = True
            if G.has_edge(u, v):
                G[u][v]['is_cycle'] = True
                
    return all_cycles, cycle_nodes, cycle_edges

# Eksekusi pipeline data
try:
    G, nodes_df, edges_df = load_graph_data()
    all_cycles, cycle_nodes, cycle_edges = analyze_cycles(G)
except FileNotFoundError as e:
    st.error(f"❌ Initialization Failed: Please make sure 'nodes_masked.csv' and 'edges_masked_part1_a.csv' exist in your directory. Error: {e}")
    st.stop()

# --- SIDEBAR CONTROL PANEL ---
st.sidebar.title("🛡️ Tax Intelligence Control Panel")
st.sidebar.markdown("---")
st.sidebar.subheader("Network Filtering")

# Filter visualisasi interaktif di halaman utama
view_mode = st.sidebar.radio(
    "Select Graph View Scope:",
    ["Show Only Circular Loops / High Risk Networks", "Show Entire Taxpayer Network Structure"]
)

st.sidebar.markdown("---")
st.sidebar.subheader("Key Network Summary Metrics")
st.sidebar.metric("Total Observed Taxpayers", len(G.nodes))
st.sidebar.metric("Total Corporate Relationships", len(G.edges))
st.sidebar.metric("Flagged Circular Loop Cycles", len(all_cycles))

# --- MAIN DASHBOARD INTERFACE ---
st.title("🔗 Tax Fraud Analytics: Circular Ownership & Dividend Stripping Network Detector")

# --- NARASI PENJELASAN (ENGLISH LANGUAGE AS REQUESTED) ---
st.markdown("""
### 📊 Domain Intelligence & Investigation Methodology

#### 1. What is Dividend Stripping & Circular Ownership?
**Circular Ownership** occurs when companies form a closed-loop ownership structure (e.g., *Company A owns Company B, Company B owns Company C, and Company C owns Company A*). In tax forensics, this pattern is frequently utilized for **Dividend Stripping** or illicit capital churning. It artificially inflates capital injections or funnels high-value dividend distributions within a closed circuit, effectively eroding the tax base or exploiting tax treaty loopholes to minimize/avoid tax liabilities inappropriately.

#### 2. Network Graph Algorithmic Approach
* **Cycle Detection Logic**: We utilize specialized graph graph-traversal techniques implemented via **NetworkX (e.g., Johnson's or Tarjan's algorithm)** to parse the directed network and pinpoint all isolated `simple_cycles` or Strongly Connected Components (SCCs).
* **Interactive D3.js Visual Mapping**: 
    * **High-Risk Elements**: Entities and transactions trapped inside a cyclic pattern are styled with **glowing crimson red**.
    * **Dynamic Stroke Width**: The border thickness of the relationship arrows scales proportionally to the **Volume of Dividends (`dividen`)** flowing between those entities, granting immediate visual triage to the highest-exposure risk vectors.
""")

st.markdown("---")

# --- PROSES PACKAGING DATA UNTUK D3.JS ---
# Tentukan node dan edge mana saja yang dikirim ke frontend berdasarkan mode filter sidebar
if view_mode == "Show Only Circular Loops / High Risk Networks":
    # Cari sub-graf yang hanya berisi node yang masuk dalam siklus
    nodes_to_render = [n for n, attr in G.nodes(data=True) if attr.get('is_in_cycle', False)]
    sub_G = G.subgraph(nodes_to_render).copy()
else:
    sub_G = G

# Format data ke struktur JSON standar yang dimengerti D3.js (nodes dan links)
d3_nodes = []
for n, attr in sub_G.nodes(data=True):
    d3_nodes.append({
        "id": str(n),
        "nama": attr.get("nama", str(n)),
        "jenis_node": attr.get("jenis_node", "Unknown"),
        "is_in_cycle": attr.get("is_in_cycle", False)
    })

d3_links = []
for u, v, attr in sub_G.edges(data=True):
    # Hitung ketebalan garis (stroke width) logaritmik dinamis berdasarkan nilai dividen / nilai transaksi
    div_val = attr.get("dividen", 0)
    nil_val = attr.get("nilai", 0)
    
    # Menghitung stroke width: jika ada dividen pakai dividen, jika tidak pakai nilai kepemilikan. Berikan batas min 1.5, max 10
    base_val = div_val if div_val > 0 else nil_val
    if base_val > 0:
        import math
        stroke_w = max(1.5, min(12, math.log10(base_val) - 4))
    else:
        stroke_w = 1.5
        
    d3_links.append({
        "source": str(u),
        "target": str(v),
        "rel_id": str(attr.get("rel_id", "")),
        "persentase": attr.get("persentase", 0),
        "nilai": attr.get("nilai", 0),
        "dividen": attr.get("dividen", 0),
        "is_cycle": attr.get("is_cycle", False),
        "stroke_width": stroke_w
    })

d3_data_json = json.dumps({"nodes": d3_nodes, "links": d3_links})

# --- RENDER KOMPONEN VISUALISASI D3.JS ---
st.subheader("🔮 Interactive D3.js Network Graph Visualization View")
st.caption("💡 Tips: Use mouse scroll wheel to zoom in/out, click and drag nodes to rearrange layout. Hover over nodes to highlight direct paths and view core metadata profile details.")

try:
    with open("d3_graph.html", "r", encoding="utf-8") as f:
        html_template = f.read()
    
    # Inject data JSON ke html template menggunakan Jinja2
    template = Template(html_template)
    rendered_html = template.render(graph_data_json=d3_data_json)
    
    # Tampilkan HTML ke dalam aplikasi Streamlit
    st.components.v1.html(rendered_html, height=650, scrolling=False)
except Exception as e:
    st.error(f"Failed to render custom D3 graph canvas template component: {e}")

# --- FORENSIC DATA RECONCILIATION TABLE ---
st.markdown("---")
st.subheader("🚨 Verified Circular Loop Auditing Trail Table")

if len(all_cycles) > 0:
    st.warning(f"System identified {len(all_cycles)} distinct high-risk circular network structures. Details are tabulated chronologically below:")
    
    audit_records = []
    for idx, cycle in enumerate(all_cycles):
        cycle_names = []
        total_cycle_dividen = 0
        total_cycle_equity = 0
        
        # Iterasi jembatan relasi dalam siklus tertutup ini
        for i in range(len(cycle)):
            s = cycle[i]
            t = cycle[(i + 1) % len(cycle)]
            
            s_name = G.nodes[s].get('nama', str(s))
            t_name = G.nodes[t].get('nama', str(t))
            
            edge_data = G[s][t]
            p_share = edge_data.get('persentase', 0)
            v_share = edge_data.get('nilai', 0)
            d_share = edge_data.get('dividen', 0)
            
            total_cycle_dividen += d_share
            total_cycle_equity += v_share
            
            audit_records.append({
                "Loop ID": f"Loop #{idx+1}",
                "From Taxpayer": s_name,
                "To Target Taxpayer": t_name,
                "Ownership %": f"{p_share}%",
                "Equity Value (IDR)": f"{v_share:,.2f}",
                "Dividend Flow (IDR)": f"{d_share:,.2f}"
            })
            
    audit_df = pd.DataFrame(audit_records)
    st.dataframe(audit_df, use_container_width=True, hide_index=True)
else:
    st.success("Splendid! Clean data signature. No cyclic loops or circular ownership anomalies detected in the provided dataset.")
