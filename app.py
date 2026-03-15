import pandas as pd
from pathlib import Path
import networkx as nx
import plotly.graph_objects as go
import streamlit as st


# =========================================================
# Page config
# =========================================================
st.set_page_config(page_title="DUR Risk Map", layout="wide")


# =========================================================
# Utilities
# =========================================================
def clean_text(x):
    if pd.isna(x):
        return "-"
    x = str(x).strip()
    return x if x else "-"


def choose_label(eng, kor):
    eng = clean_text(eng)
    kor = clean_text(kor)
    return eng if eng != "-" else kor


def unique_join(series):
    values = []
    for v in series:
        v = clean_text(v)
        if v != "-" and v not in values:
            values.append(v)
    return " / ".join(values) if values else "-"


def bool_to_yes_no(x):
    return "Yes" if bool(x) else "No"


def truncate_text(text, max_len=90):
    text = clean_text(text)
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def load_dur_csv(file_path):
    df = pd.read_csv(
        file_path,
        encoding="utf-8-sig",
        engine="python",
        on_bad_lines="skip"
    )
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
    df.columns = df.columns.str.strip()

    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].apply(clean_text)

    return df


# =========================================================
# Build edge table
# =========================================================
def make_canonical_pair(row):
    source_code = clean_text(row["DUR성분코드"])
    source_label_eng = choose_label(row["DUR성분명영문"], row["DUR성분명"])
    source_label_kor = clean_text(row["DUR성분명"])

    target_code = clean_text(row["병용금기DUR성분코드"])
    target_label_eng = choose_label(row["병용금기DUR성분영문명"], row["병용금기DUR성분명"])
    target_label_kor = clean_text(row["병용금기DUR성분명"])

    left = {
        "code": source_code,
        "label_eng": source_label_eng,
        "label_kor": source_label_kor
    }
    right = {
        "code": target_code,
        "label_eng": target_label_eng,
        "label_kor": target_label_kor
    }

    if left["code"] <= right["code"]:
        return pd.Series({
            "source_code": left["code"],
            "source_label_eng": left["label_eng"],
            "source_label_kor": left["label_kor"],
            "target_code": right["code"],
            "target_label_eng": right["label_eng"],
            "target_label_kor": right["label_kor"],
        })
    else:
        return pd.Series({
            "source_code": right["code"],
            "source_label_eng": right["label_eng"],
            "source_label_kor": right["label_kor"],
            "target_code": left["code"],
            "target_label_eng": left["label_eng"],
            "target_label_kor": left["label_kor"],
        })


def build_edge_table(ac_df):
    df = ac_df.copy()

    cols = [
        "DUR성분코드",
        "DUR성분명영문",
        "DUR성분명",
        "병용금기DUR성분코드",
        "병용금기DUR성분영문명",
        "병용금기DUR성분명",
        "금기내용"
    ]
    df = df[cols].copy()

    for col in cols:
        df[col] = df[col].apply(clean_text)

    df = df[
        (df["DUR성분코드"] != "-") &
        (df["병용금기DUR성분코드"] != "-") &
        (df["DUR성분코드"] != df["병용금기DUR성분코드"])
    ].copy()

    pair_df = df.apply(make_canonical_pair, axis=1)
    df = pd.concat([df, pair_df], axis=1)

    edge_df = (
        df.groupby(
            [
                "source_code",
                "source_label_eng",
                "source_label_kor",
                "target_code",
                "target_label_eng",
                "target_label_kor",
            ],
            as_index=False
        )
        .agg(
            reason=("금기내용", unique_join),
            raw_count=("금기내용", "size")
        )
        .sort_values(
            by=["raw_count", "source_label_eng", "target_label_eng"],
            ascending=[False, True, True]
        )
        .reset_index(drop=True)
    )

    return edge_df


# =========================================================
# Build node table
# =========================================================
def build_node_table(edge_df):
    left_nodes = edge_df[
        ["source_code", "source_label_eng", "source_label_kor"]
    ].copy().rename(columns={
        "source_code": "code",
        "source_label_eng": "label_eng",
        "source_label_kor": "label_kor"
    })

    right_nodes = edge_df[
        ["target_code", "target_label_eng", "target_label_kor"]
    ].copy().rename(columns={
        "target_code": "code",
        "target_label_eng": "label_eng",
        "target_label_kor": "label_kor"
    })

    node_df = pd.concat([left_nodes, right_nodes], ignore_index=True)
    node_df = node_df.drop_duplicates().reset_index(drop=True)

    all_codes = pd.concat(
        [edge_df["source_code"], edge_df["target_code"]],
        ignore_index=True
    )
    degree_df = (
        all_codes.value_counts()
        .rename_axis("code")
        .reset_index(name="degree")
    )

    node_df = node_df.merge(degree_df, on="code", how="left")
    node_df["degree"] = node_df["degree"].fillna(0).astype(int)

    return node_df.sort_values(
        ["degree", "label_eng"],
        ascending=[False, True]
    ).reset_index(drop=True)


# =========================================================
# Add overlays (BC, CC, FC)
# =========================================================
def add_overlays(node_df, bc_df, cc_df, fc_df):
    bc_use = bc_df[["DUR성분코드", "연령기준", "금기내용"]].copy()
    bc_use = bc_use[bc_use["DUR성분코드"] != "-"].copy()

    bc_summary = (
        bc_use.groupby("DUR성분코드", as_index=False)
        .agg(
            age_rule=("연령기준", unique_join),
            age_reason=("금기내용", unique_join)
        )
        .rename(columns={"DUR성분코드": "code"})
    )
    bc_summary["is_age_contra"] = True

    cc_use = cc_df[["DUR성분코드", "등급", "금기내용"]].copy()
    cc_use = cc_use[cc_use["DUR성분코드"] != "-"].copy()

    cc_summary = (
        cc_use.groupby("DUR성분코드", as_index=False)
        .agg(
            preg_grade=("등급", unique_join),
            preg_reason=("금기내용", unique_join)
        )
        .rename(columns={"DUR성분코드": "code"})
    )
    cc_summary["is_preg_contra"] = True

    fc_use = fc_df[["DUR성분코드", "금기내용"]].copy()
    fc_use = fc_use[fc_use["DUR성분코드"] != "-"].copy()

    fc_summary = (
        fc_use.groupby("DUR성분코드", as_index=False)
        .agg(
            elderly_reason=("금기내용", unique_join)
        )
        .rename(columns={"DUR성분코드": "code"})
    )
    fc_summary["is_elderly_caution"] = True

    node_overlay_df = node_df.copy()

    node_overlay_df = node_overlay_df.merge(
        bc_summary[["code", "is_age_contra", "age_rule", "age_reason"]],
        on="code",
        how="left"
    )
    node_overlay_df = node_overlay_df.merge(
        cc_summary[["code", "is_preg_contra", "preg_grade", "preg_reason"]],
        on="code",
        how="left"
    )
    node_overlay_df = node_overlay_df.merge(
        fc_summary[["code", "is_elderly_caution", "elderly_reason"]],
        on="code",
        how="left"
    )

    bool_cols = ["is_age_contra", "is_preg_contra", "is_elderly_caution"]
    text_cols = ["age_rule", "age_reason", "preg_grade", "preg_reason", "elderly_reason"]

    for col in bool_cols:
        node_overlay_df[col] = node_overlay_df[col].fillna(False).astype(bool)

    for col in text_cols:
        node_overlay_df[col] = node_overlay_df[col].fillna("-")

    return node_overlay_df


# =========================================================
# Build graph
# =========================================================
def build_graph(edge_df, node_overlay_df):
    G = nx.Graph()

    for _, row in node_overlay_df.iterrows():
        G.add_node(
            row["code"],
            label_eng=row["label_eng"],
            label_kor=row["label_kor"],
            degree=row["degree"],
            is_age_contra=row["is_age_contra"],
            age_rule=row["age_rule"],
            age_reason=row["age_reason"],
            is_preg_contra=row["is_preg_contra"],
            preg_grade=row["preg_grade"],
            preg_reason=row["preg_reason"],
            is_elderly_caution=row["is_elderly_caution"],
            elderly_reason=row["elderly_reason"]
        )

    for _, row in edge_df.iterrows():
        G.add_edge(
            row["source_code"],
            row["target_code"],
            reason=row["reason"],
            raw_count=row["raw_count"]
        )

    return G


# =========================================================
# Plotly ego network
# =========================================================
def draw_ego_network_plotly_by_name(G, node_overlay_df, drug_name_eng):
    sub = node_overlay_df[node_overlay_df["label_eng"] == drug_name_eng].copy()

    if len(sub) == 0:
        st.warning(f"'{drug_name_eng}' not found.")
        return None

    center_code = sub.iloc[0]["code"]

    neighbors = list(G.neighbors(center_code))
    ego_nodes = [center_code] + neighbors
    ego_G = G.subgraph(ego_nodes).copy()

    pos = nx.spring_layout(ego_G, seed=42, k=0.8)

    # -------------------------
    # Edge traces
    # -------------------------
    edge_x, edge_y = [], []
    edge_hover_x, edge_hover_y, edge_hover_text = [], [], []

    for u, v, data in ego_G.edges(data=True):
        x0, y0 = pos[u]
        x1, y1 = pos[v]

        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

        mx = (x0 + x1) / 2
        my = (y0 + y1) / 2
        edge_hover_x.append(mx)
        edge_hover_y.append(my)

        u_name = G.nodes[u].get("label_eng", u)
        v_name = G.nodes[v].get("label_eng", v)

        edge_hover_text.append(
            f"<b>{u_name}</b> ↔ <b>{v_name}</b><br>"
            f"Reason: {data.get('reason', '-')}<br>"
            f"Source Rows: {data.get('raw_count', '-')}"
        )

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        line=dict(width=1.5, color="gray"),
        hoverinfo="none",
        mode="lines",
        showlegend=False
    )

    edge_hover_trace = go.Scatter(
        x=edge_hover_x,
        y=edge_hover_y,
        mode="markers",
        marker=dict(size=10, color="rgba(0,0,0,0)"),
        text=edge_hover_text,
        hoverinfo="text",
        showlegend=False
    )

    # -------------------------
    # Node trace
    # -------------------------
    node_x, node_y = [], []
    node_text, node_sizes, node_colors, node_labels = [], [], [], []

    for node in ego_G.nodes():
        x, y = pos[node]
        attr = G.nodes[node]
        is_center = (node == center_code)

        node_x.append(x)
        node_y.append(y)

        if is_center:
            color = "red"
        elif attr.get("is_preg_contra", False):
            color = "orange"
        elif attr.get("is_elderly_caution", False):
            color = "purple"
        elif attr.get("is_age_contra", False):
            color = "green"
        else:
            color = "skyblue"

        node_colors.append(color)
        node_sizes.append(36 if is_center else 14 + attr.get("degree", 1) * 1.2)

        label_eng = attr.get("label_eng", node)
        label_kor = attr.get("label_kor", "-")

        # 라벨은 중심 + degree 상위 이웃만 표시하면 덜 복잡함
        if is_center or attr.get("degree", 0) >= 20:
            node_labels.append(label_eng)
        else:
            node_labels.append("")

        node_text.append(
            f"<b>{label_eng}</b><br>"
            f"Korean: {label_kor}<br>"
            f"Degree: {attr.get('degree', 0)}<br>"
            f"Pregnancy Contraindication: {bool_to_yes_no(attr.get('is_preg_contra', False))}<br>"
            f"Pregnancy Grade: {attr.get('preg_grade', '-')}<br>"
            f"Elderly Caution: {bool_to_yes_no(attr.get('is_elderly_caution', False))}<br>"
            f"Age Contraindication: {bool_to_yes_no(attr.get('is_age_contra', False))}<br>"
            f"Age Rule: {attr.get('age_rule', '-')}"
        )

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=node_labels,
        textposition="top center",
        hoverinfo="text",
        hovertext=node_text,
        marker=dict(
            size=node_sizes,
            color=node_colors,
            line=dict(width=1, color="black")
        ),
        showlegend=False
    )

    fig = go.Figure(data=[edge_trace, edge_hover_trace, node_trace])

    fig.update_layout(
        title=f"Interactive Ego Network of {drug_name_eng}",
        title_x=0.5,
        hovermode="closest",
        margin=dict(l=20, r=20, t=50, b=20),
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False),
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=820
    )

    return fig


# =========================================================
# Neighbor table
# =========================================================
def get_neighbor_table(G, node_overlay_df, drug_name_eng):
    sub = node_overlay_df[node_overlay_df["label_eng"] == drug_name_eng].copy()
    if len(sub) == 0:
        return pd.DataFrame()

    center_code = sub.iloc[0]["code"]

    rows = []
    for neighbor in G.neighbors(center_code):
        edge_data = G.get_edge_data(center_code, neighbor)
        attr = G.nodes[neighbor]

        rows.append({
            "Drug (EN)": attr.get("label_eng", neighbor),
            "Drug (KR)": attr.get("label_kor", "-"),
            "Degree": attr.get("degree", 0),
            "Pregnancy Contra": bool_to_yes_no(attr.get("is_preg_contra", False)),
            "Elderly Caution": bool_to_yes_no(attr.get("is_elderly_caution", False)),
            "Age Contra": bool_to_yes_no(attr.get("is_age_contra", False)),
            "Contraindication Reason": truncate_text(edge_data.get("reason", "-"), 100),
            "Source Rows": edge_data.get("raw_count", "-"),
            "_full_reason": edge_data.get("reason", "-"),
        })

    neighbor_df = pd.DataFrame(rows).sort_values(
        ["Degree", "Drug (EN)"],
        ascending=[False, True]
    ).reset_index(drop=True)

    return neighbor_df


# =========================================================
# Top hubs table
# =========================================================
def get_top_hubs(node_overlay_df, n=20):
    df = node_overlay_df.copy()

    df["Pregnancy Contra"] = df["is_preg_contra"].apply(bool_to_yes_no)
    df["Elderly Caution"] = df["is_elderly_caution"].apply(bool_to_yes_no)
    df["Age Contra"] = df["is_age_contra"].apply(bool_to_yes_no)

    return df[[
        "label_eng",
        "label_kor",
        "degree",
        "Pregnancy Contra",
        "Elderly Caution",
        "Age Contra"
    ]].rename(columns={
        "label_eng": "Drug (EN)",
        "label_kor": "Drug (KR)",
        "degree": "Degree"
    }).sort_values("Degree", ascending=False).head(n)


# =========================================================
# Cached pipeline
# =========================================================
@st.cache_data
def load_pipeline():
    base_path = Path("data") / "raw"

    ac_df = load_dur_csv(base_path / "OpenData_PotOpenDurIngr_AC20260312.csv")
    bc_df = load_dur_csv(base_path / "OpenData_PotOpenDurIngr_BC20260312.csv")
    cc_df = load_dur_csv(base_path / "OpenData_PotOpenDurIngr_CC20260312.csv")
    fc_df = load_dur_csv(base_path / "OpenData_PotOpenDurIngr_FC20260312.csv")

    edge_df = build_edge_table(ac_df)
    node_df = build_node_table(edge_df)
    node_overlay_df = add_overlays(node_df, bc_df, cc_df, fc_df)

    return edge_df, node_overlay_df


@st.cache_resource
def get_graph(_edge_df, _node_overlay_df):
    return build_graph(_edge_df, _node_overlay_df)


# =========================================================
# App
# =========================================================
st.title("DUR Risk Map")
st.caption("Interactive ego-network explorer for public DUR contraindication rules")

edge_df, node_overlay_df = load_pipeline()
G = get_graph(edge_df, node_overlay_df)

drug_options = sorted(node_overlay_df["label_eng"].dropna().unique().tolist())
default_drug = "Rifampicin" if "Rifampicin" in drug_options else drug_options[0]

selected_drug = st.sidebar.selectbox(
    "Select a drug",
    drug_options,
    index=drug_options.index(default_drug)
)

selected_row = node_overlay_df[node_overlay_df["label_eng"] == selected_drug].iloc[0]
neighbor_df = get_neighbor_table(G, node_overlay_df, selected_drug)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Drug", selected_drug)
c2.metric("Degree", int(selected_row["degree"]))
c3.metric("Direct Contraindicated Neighbors", len(neighbor_df))
c4.metric("Pregnancy Contra", bool_to_yes_no(selected_row["is_preg_contra"]))
c5.metric("Elderly Caution", bool_to_yes_no(selected_row["is_elderly_caution"]))

fig = draw_ego_network_plotly_by_name(G, node_overlay_df, selected_drug)
if fig is not None:
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Directly connected contraindicated drugs")

display_neighbor_df = neighbor_df.drop(columns=["_full_reason"]).copy()
st.dataframe(display_neighbor_df, use_container_width=True, hide_index=True)

with st.expander("Show full contraindication reasons"):
    full_reason_df = neighbor_df[["Drug (EN)", "Drug (KR)", "_full_reason"]].rename(
        columns={"_full_reason": "Full Reason"}
    )
    st.dataframe(full_reason_df, use_container_width=True, hide_index=True)

with st.expander("Top hub ingredients in the full network"):
    st.dataframe(get_top_hubs(node_overlay_df, n=20), use_container_width=True, hide_index=True)