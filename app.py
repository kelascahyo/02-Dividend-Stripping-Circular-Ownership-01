import streamlit as st
import pandas as pd
import networkx as nx
import json
import math
from jinja2 import Template

# --- 1. CONFIGURATION & STYLING ---
st.set_page_config(
    page_title="Tax Fraud Analytical Tools: Dividend Stripping Network Detector",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS to inject dark theme backgrounds uniformly across components
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    h1, h2, h3 { color: #ff4b4b !important; }
    .stAlert p { color: #000000 !important; }
    .stRadio label { color: #f1f3f6 !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATA LOADING PIPELINE WITH CACHING ---
@st.cache_data
def load_graph_data():
    try:
        # Load masked dataset files
        nodes_df = pd.read_csv("nodes_masked.csv")
        edges_df = pd.read_csv("edges_masked_part1_a.csv")
        
        # Initialize Directed Graph via NetworkX
        G = nx.DiGraph()
        
        # Populate nodes with taxpayer profile attributes
        for _, row in nodes_df.iterrows():
            node_id = int(row['id'])
            G.add_node(
                node_id, 
                nama=str(row['nama']).strip(), 
                jenis_node=str(row['jenis_node']).strip(),
                is_in_cycle=False
            )
            
        # Populate edges representing equity and dividend relationships
        for _, row in edges_df.iterrows():
            u = int(row['sumber'])
            v = int(row['target'])
            
            # Ensure both source and target nodes exist in the graph to avoid discrepancies
            if not G.has_node(u):
                G.add_node(u, nama=f"Unknown-{u}", jenis_node="Unknown", is_in_cycle=False)
            if not G.has_node(v):
                G.add_node(v, nama=f"Unknown-{v}", jenis_node="Unknown", is_in_cycle=False)
                
            G.add_edge(
                u, v,
                rel_id=int(row['rel_id']),
                persentase=float(row['persentase']),
                nilai=float(row['nilai']),
                dividen=float(row['dividen']),
                is_cycle=False
            )
        return G, nodes_df, edges_df
    except Exception as e:
        st.error(f"❌ Critical Error Loading Data: {e}. Please ensure 'nodes_masked.csv' and 'edges_masked_part1_a.csv' are present in the same directory.")
        st.stop()

# --- 3. ALGORITHMIC GRAPH ANALYSIS (CYCLE DETECTION) ---
def analyze_cycles(G):
    # Detect all directed simple closed loops using NetworkX
    all_cycles = list(nx.simple_cycles(G))
    
    cycle_nodes = set()
    cycle_edges = set()
    
    for cycle in all_cycles:
        for i in range(len(cycle)):
            u = cycle[i]
            v = cycle[(i + 1) % len(cycle)]
            cycle_nodes.add(u)
            cycle_edges.add((u, v))
            
            # Flag matching properties directly inside the NetworkX graph instance
            G.nodes[u]['is_in_cycle'] = True
            G.edges[u, v]['is_cycle'] = True
                
    return all_cycles, cycle_nodes, cycle_edges

# Execute Data Processing Pipeline
G, nodes_df, edges_df = load_graph_data()
all_cycles, cycle_nodes, cycle_edges = analyze_cycles(G)

# --- 4. SIDEBAR CONTROL PANEL & METRICS ---
st.sidebar.title("🛡️ Tax Intelligence Control Panel")
st.sidebar.markdown("---")
st.sidebar.subheader("Network Filtering")

view_mode = st.sidebar.radio(
    "Select Graph View Scope:",
    ["Show Only Circular Loops / High Risk Networks", "Show Entire Taxpayer Network Structure"]
)

st.sidebar.markdown("---")
st.sidebar.subheader("Key Network Summary Metrics")
st.sidebar.metric("Total Observed Taxpayers", f"{len(G.nodes):,}")
st.sidebar.metric("Total Corporate Relationships", f"{len(G.edges):,}")
st.sidebar.metric("Flagged Circular Loop Cycles", f"{len(all_cycles)}")

# --- 5. MAIN DASHBOARD HEADING & ANALYTICAL NARRATIVE ---
st.title("🔗 Tax Fraud Analytics: Circular Ownership & Dividend Stripping Network Detector")

st.markdown("""
### 📊 Domain Intelligence & Investigation Methodology

#### 1. What is Dividend Stripping & Circular Ownership?
**Circular Ownership** occurs when companies form a closed-loop ownership structure (e.g., *Company A owns Company B, Company B owns Company C, and Company C returns to own Company A*). In tax forensics, this pattern is frequently utilized for **Dividend Stripping** or illicit capital churning. It artificially inflates capital injections or funnels high-value dividend distributions within a closed circuit, effectively eroding the tax base or exploiting tax treaty loopholes to minimize/avoid tax liabilities inappropriately.

#### 2. Network Graph Algorithmic Approach
* **Cycle Detection Logic**: We utilize specialized graph-traversal techniques implemented via **NetworkX (e.g., Johnson's or Tarjan's algorithm)** to parse the directed network and pinpoint all isolated `simple_cycles` or Strongly Connected Components (SCCs).
* **Interactive D3.js Visual Mapping**: 
    * **High-Risk Elements**: Entities and transactions trapped inside a cyclic pattern are styled with a **glowing crimson red**.
    * **Dynamic Stroke Width**: The border thickness of the relationship arrows scales proportionally to the **Volume of Dividends (`dividen`)** flowing between those entities, granting immediate visual triage to the highest-exposure risk vectors.
""", unsafe_allow_html=True)

st.markdown("---")

# --- 6. D3.JS GRAPH JSON PACKAGING ---
# Determine which sub-network view scope to load based on the user's sidebar selection
if view_mode == "Show Only Circular Loops / High Risk Networks":
    nodes_to_render = [n for n, attr in G.nodes(data=True) if attr.get('is_in_cycle', False)]
    if len(nodes_to_render) == 0:
        sub_G = nx.DiGraph()  # Empty graph fallback if no cycles exist
    else:
        sub_G = G.subgraph(nodes_to_render).copy()
else:
    sub_G = G

d3_nodes = []
for n, attr in sub_G.nodes(data=True):
    d3_nodes.append({
        "id": str(int(n)),  # CRITICAL: Forces pure uniform string mapping to prevent blank D3 graph renders
        "nama": attr.get("nama", f"Taxpayer-{n}"),
        "jenis_node": attr.get("jenis_node", "Unknown"),
        "is_in_cycle": attr.get("is_in_cycle", False)
    })

d3_links = []
for u, v, attr in sub_G.edges(data=True):
    div_val = attr.get("dividen", 0)
    nil_val = attr.get("nilai", 0)
    
    # Dynamic logarithmic thickness bounding (Min: 1.5px, Max: 12px)
    base_val = div_val if div_val > 0 else nil_val
    if base_val > 0:
        stroke_w = max(1.5, min(12.0, math.log10(base_val) - 4.0))
    else:
        stroke_w = 1.5
        
    d3_links.append({
        "source": str(int(u)),  # CRITICAL: Strict string matching with Node ID
        "target": str(int(v)),  # CRITICAL: Strict string matching with Node ID
        "rel_id": str(attr.get("rel_id", "")),
        "persentase": attr.get("persentase", 0),
        "nilai": attr.get("nilai", 0),
        "dividen": attr.get("dividen", 0),
        "is_cycle": attr.get("is_cycle", False),
        "stroke_width": float(stroke_w)
    })

# Pack into serializable Python dictionary and dump to clean JSON string
d3_data_json = json.dumps({"nodes": d3_nodes, "links": d3_links})

# --- 7. RENDERING THE D3.JS IFRAME COMPONENT ---
st.subheader("🔮 Interactive D3.js Network Graph Visualization Canvas View")
st.caption("💡 User Hints: Use your mouse scroll-wheel to zoom in/out. Click and drag individual taxpayer nodes to rearrange layouts. Hover over a node to instantly isolate its operational path and view its metadata profile summary.")

try:
    with open("d3_graph.html", "r", encoding="utf-8") as f:
        html_template = f.read()
    
    # Inject JSON payload into HTML template via Jinja2
    template = Template(html_template)
    rendered_html = template.render(graph_data_json=d3_data_json)
    
    # Display within standard Streamlit layout viewport frame
    st.components.v1.html(rendered_html, height=650, scrolling=False)
except FileNotFoundError:
    st.error("❌ Component Rendering Failure: 'd3_graph.html' file template was not found in your repository directory.")
except Exception as e:
    st.error(f"❌ Runtime Exception rendering HTML Engine: {e}")

# --- 8. FORENSIC AUDIT RECORD RECONCILIATION TABLE ---
st.markdown("---")
st.subheader("🚨 Verified Circular Loop Auditing Trail Table")

if len(all_cycles) > 0:
    st.warning(f"System has successfully isolated {len(all_cycles)} distinct high-risk circular network loops. Transactional connections are verified below:")
    
    audit_records = []
    for idx, cycle in enumerate(all_cycles):
        for i in range(len(cycle)):
            s = cycle[i]
            t = cycle[(i + 1) % len(cycle)]
            
            s_name = G.nodes[s].get('nama', f"Taxpayer-{s}")
            t_name = G.nodes[t].get('nama', f"Taxpayer-{t}")
            
            edge_data = G[s][t]
            p_share = edge_data.get('persentase', 0)
            v_share = edge_data.get('nilai', 0)
            d_share = edge_data.get('dividen', 0)
            
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
    st.success("Splendid! Data signature clean. No cyclical corporate loop paths or circular ownership anomalies detected within the current dataset.")
