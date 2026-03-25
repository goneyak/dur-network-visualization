import pandas as pd
from pathlib import Path
import networkx as nx
import plotly.graph_objects as go
import streamlit as st
import os
import re


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


def truncate_text(text, max_len=100):
    text = clean_text(text)
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def unique_join_raw(series):
    values = []
    for v in series:
        if pd.isna(v):
            continue
        raw = str(v)
        if not raw.strip():
            continue
        if raw not in values:
            values.append(raw)
    return " / ".join(values) if values else "-"


def clean_reason_text(text):
    if pd.isna(text):
        return "-"

    s = str(text)
    s = s.replace("\r", " ").replace("\n", " ").replace("\t", " ")

    # Split by common separators, trim leading list marks, and re-join deterministically.
    parts = re.split(r"\s*(?:\||/|;|,|ㆍ|·)\s*", s)
    normalized = []
    for part in parts:
        part = re.sub(r"^[\s\-_•·]+", "", part)
        part = re.sub(r"\s+", " ", part).strip()
        if part and part != "-" and part not in normalized:
            normalized.append(part)

    return " / ".join(normalized) if normalized else "-"


def shorten_reason_deterministic(text, max_len=100):
    text = clean_text(text)
    if text == "-":
        return "-"
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "..."


@st.cache_data(show_spinner=False)
def summarize_reason_with_llm(reason_clean, max_len=100):
    fallback = shorten_reason_deterministic(reason_clean, max_len=max_len)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets.get("OPENAI_API_KEY")
        except Exception:
            api_key = None

    if not api_key:
        return fallback

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": "Summarize medical contraindication text into one concise sentence. Keep factual meaning.",
                },
                {
                    "role": "user",
                    "content": f"Text: {reason_clean}\nMax chars: {max_len}",
                },
            ],
            max_output_tokens=120,
        )

        out = clean_text(getattr(response, "output_text", ""))
        return shorten_reason_deterministic(out, max_len=max_len)
    except Exception:
        return fallback


def get_reason_short(reason_clean, use_llm=False, max_len=100):
    if use_llm:
        return summarize_reason_with_llm(reason_clean, max_len=max_len)
    return shorten_reason_deterministic(reason_clean, max_len=max_len)


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


def pick_first_existing(df, candidates):
    for col in candidates:
        if col in df.columns:
            return col
    return None


def build_rule_summary(
    df,
    flag_name,
    rule_col_candidates,
    reason_col_candidates
):
    code_col = "DUR성분코드"
    if code_col not in df.columns:
        raise ValueError(f"'{code_col}' column not found.")

    df = df.copy()
    df = df[df[code_col] != "-"].copy()

    rule_col = pick_first_existing(df, rule_col_candidates)
    reason_col = pick_first_existing(df, reason_col_candidates)

    agg_map = {}

    if rule_col is not None:
        agg_map["rule_text"] = (rule_col, unique_join)
    else:
        df["_rule_text_fallback"] = "-"
        agg_map["rule_text"] = ("_rule_text_fallback", unique_join)

    if reason_col is not None:
        agg_map["reason_text"] = (reason_col, unique_join)
    else:
        df["_reason_text_fallback"] = "-"
        agg_map["reason_text"] = ("_reason_text_fallback", unique_join)

    summary = (
        df.groupby(code_col, as_index=False)
        .agg(**agg_map)
        .rename(columns={code_col: "code"})
    )

    summary[flag_name] = True
    return summary


def node_passes_filters(
    attr,
    preg_only=False,
    elderly_only=False,
    age_only=False,
    group_only=False
):
    if preg_only and not attr.get("is_preg_contra", False):
        return False
    if elderly_only and not attr.get("is_elderly_caution", False):
        return False
    if age_only and not attr.get("is_age_contra", False):
        return False
    if group_only and not attr.get("is_group_overlap", False):
        return False
    return True


def add_detail_line(lines, label, value, show_if_dash=False):
    value = clean_text(value)
    if value == "-" and not show_if_dash:
        return
    lines.append(f"<div style='margin-bottom:4px;'><b>{label}</b>: {value}</div>")


def add_bool_line(lines, label, value):
    if bool(value):
        lines.append(f"<div style='margin-bottom:4px;'><b>{label}</b>: Yes</div>")


def render_compact_detail_box(title, lines):
    if not lines:
        return
    html = f"""
    <div style="
        border:1px solid #e5e7eb;
        border-radius:10px;
        padding:10px 12px;
        background:#fafafa;
        margin-bottom:10px;
    ">
        <div style="font-weight:600; margin-bottom:6px;">{title}</div>
        <div style="font-size:13px; line-height:1.35;">
            {''.join(lines)}
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_legend():
    st.markdown(
        """
        <div style="
            padding:10px 12px;
            border:1px solid #e5e7eb;
            border-radius:10px;
            background:#fafafa;
            font-size:13px;
            line-height:1.7;
            margin-bottom:10px;
        ">
            <b>Graph guide</b><br>
            <b>Node size</b> = degree (direct contraindication connections)<br>
            <b>Node color</b> =
            <span style="color:red;"><b>●</b></span> Selected
            <span style="color:orange;"><b>●</b></span> Pregnancy
            <span style="color:purple;"><b>●</b></span> Elderly
            <span style="color:green;"><b>●</b></span> Age-related
            <span style="color:goldenrod;"><b>●</b></span> Group overlap
            <span style="color:skyblue;"><b>●</b></span> General<br>
            <b>Node border</b> = DUR risk flag count &nbsp;
            <span style="color:darkgray;">— 1 flag</span> &nbsp;
            <span style="color:darkorange;">— 2 flags</span> &nbsp;
            <span style="color:crimson;">— 3+ flags</span><br>
            <b>Edge thickness</b> = source data rows (thicker = more documented relationship)
        </div>
        """,
        unsafe_allow_html=True
    )


def render_flag_badges(row):
    badges = []
    if row["is_preg_contra"]:
        badges.append("Pregnancy")
    if row["is_elderly_caution"]:
        badges.append("Elderly")
    if row["is_age_contra"]:
        badges.append("Age")
    if row["is_group_overlap"]:
        badges.append("Group")
    if row["is_dose_caution"]:
        badges.append("Dose")
    if row["is_duration_caution"]:
        badges.append("Duration")

    return ", ".join(badges) if badges else "None"


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

    # Keep raw reason untouched; clean only the fields needed for canonical edge building.
    for col in [
        "DUR성분코드",
        "DUR성분명영문",
        "DUR성분명",
        "병용금기DUR성분코드",
        "병용금기DUR성분영문명",
        "병용금기DUR성분명",
    ]:
        df[col] = df[col].apply(clean_text)

    df["reason_raw_item"] = df["금기내용"]
    df["reason_clean_item"] = df["금기내용"].apply(clean_reason_text)

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
            reason_raw=("reason_raw_item", unique_join_raw),
            reason_clean=("reason_clean_item", unique_join_raw),
            raw_count=("금기내용", "size")
        )
        .sort_values(
            by=["raw_count", "source_label_eng", "target_label_eng"],
            ascending=[False, True, True]
        )
        .reset_index(drop=True)
    )

    edge_df["reason_short"] = edge_df["reason_clean"].apply(
        lambda x: shorten_reason_deterministic(x, max_len=100)
    )
    # Backward-compatible alias for existing hover logic.
    edge_df["reason"] = edge_df["reason_clean"]

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
# Add overlays
# =========================================================
def add_overlays(node_df, bc_df, cc_df, fc_df, gc_df, dc_df, ec_df):
    # BC
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

    # CC
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

    # FC
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

    # GC
    gc_cols = [c for c in ["DUR성분코드", "효능군", "계열명"] if c in gc_df.columns]
    gc_use = gc_df[gc_cols].copy()
    gc_use = gc_use[gc_use["DUR성분코드"] != "-"].copy()

    agg_dict = {}
    if "효능군" in gc_use.columns:
        agg_dict["group_name"] = ("효능군", unique_join)
    if "계열명" in gc_use.columns:
        agg_dict["class_name"] = ("계열명", unique_join)

    gc_summary = (
        gc_use.groupby("DUR성분코드", as_index=False)
        .agg(**agg_dict)
        .rename(columns={"DUR성분코드": "code"})
    )
    gc_summary["is_group_overlap"] = True

    if "group_name" not in gc_summary.columns:
        gc_summary["group_name"] = "-"
    if "class_name" not in gc_summary.columns:
        gc_summary["class_name"] = "-"

    # DC
    dc_summary = build_rule_summary(
        dc_df,
        flag_name="is_dose_caution",
        rule_col_candidates=["용량기준", "최대용량", "1일최대용량", "용법용량", "용량"],
        reason_col_candidates=["금기내용", "주의내용", "상세내용"]
    ).rename(columns={
        "rule_text": "dose_rule",
        "reason_text": "dose_reason"
    })

    # EC
    ec_summary = build_rule_summary(
        ec_df,
        flag_name="is_duration_caution",
        rule_col_candidates=["투여기간기준", "기간기준", "최대투여기간", "투여기간"],
        reason_col_candidates=["금기내용", "주의내용", "상세내용"]
    ).rename(columns={
        "rule_text": "duration_rule",
        "reason_text": "duration_reason"
    })

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
    node_overlay_df = node_overlay_df.merge(
        gc_summary[["code", "is_group_overlap", "group_name", "class_name"]],
        on="code",
        how="left"
    )
    node_overlay_df = node_overlay_df.merge(
        dc_summary[["code", "is_dose_caution", "dose_rule", "dose_reason"]],
        on="code",
        how="left"
    )
    node_overlay_df = node_overlay_df.merge(
        ec_summary[["code", "is_duration_caution", "duration_rule", "duration_reason"]],
        on="code",
        how="left"
    )

    bool_cols = [
        "is_age_contra",
        "is_preg_contra",
        "is_elderly_caution",
        "is_group_overlap",
        "is_dose_caution",
        "is_duration_caution"
    ]
    text_cols = [
        "age_rule",
        "age_reason",
        "preg_grade",
        "preg_reason",
        "elderly_reason",
        "group_name",
        "class_name",
        "dose_rule",
        "dose_reason",
        "duration_rule",
        "duration_reason"
    ]

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
            elderly_reason=row["elderly_reason"],
            is_group_overlap=row["is_group_overlap"],
            group_name=row["group_name"],
            class_name=row["class_name"],
            is_dose_caution=row["is_dose_caution"],
            dose_rule=row["dose_rule"],
            dose_reason=row["dose_reason"],
            is_duration_caution=row["is_duration_caution"],
            duration_rule=row["duration_rule"],
            duration_reason=row["duration_reason"]
        )

    for _, row in edge_df.iterrows():
        G.add_edge(
            row["source_code"],
            row["target_code"],
            reason=row["reason"],
            reason_raw=row["reason_raw"],
            reason_clean=row["reason_clean"],
            reason_short=row["reason_short"],
            raw_count=row["raw_count"]
        )

    return G


# =========================================================
# Plot functions
# =========================================================
def get_node_color(attr, is_selected=False):
    if is_selected:
        return "red"
    if attr.get("is_preg_contra", False):
        return "orange"
    if attr.get("is_elderly_caution", False):
        return "purple"
    if attr.get("is_age_contra", False):
        return "green"
    if attr.get("is_group_overlap", False):
        return "gold"
    return "skyblue"


def count_flags(attr):
    flag_keys = [
        "is_preg_contra", "is_elderly_caution", "is_age_contra",
        "is_group_overlap", "is_dose_caution", "is_duration_caution"
    ]
    return sum(1 for k in flag_keys if attr.get(k, False))


def draw_ego_network_plotly_by_name(
    G,
    node_overlay_df,
    drug_name_eng,
    preg_only=False,
    elderly_only=False,
    age_only=False,
    group_only=False,
    top_n_neighbors=20
):
    sub = node_overlay_df[node_overlay_df["label_eng"] == drug_name_eng].copy()

    if len(sub) == 0:
        st.warning(f"'{drug_name_eng}' not found.")
        return None

    center_code = sub.iloc[0]["code"]

    raw_neighbors = list(G.neighbors(center_code))
    filtered_neighbors = []

    for neighbor in raw_neighbors:
        attr = G.nodes[neighbor]
        if node_passes_filters(
            attr,
            preg_only=preg_only,
            elderly_only=elderly_only,
            age_only=age_only,
            group_only=group_only
        ):
            filtered_neighbors.append(neighbor)

    filtered_neighbors = sorted(
        filtered_neighbors,
        key=lambda n: G.nodes[n].get("degree", 0),
        reverse=True
    )[:top_n_neighbors]

    ego_nodes = [center_code] + filtered_neighbors
    ego_G = G.subgraph(ego_nodes).copy()

    if ego_G.number_of_nodes() == 1:
        st.info("No neighbors match the current filter settings.")
        return None

    pos = nx.spring_layout(ego_G, seed=42, k=0.85)

    _edge_buckets = [
        {"x": [], "y": [], "width": 1.2, "color": "rgba(200,200,200,0.7)"},
        {"x": [], "y": [], "width": 2.4, "color": "rgba(130,130,130,0.8)"},
        {"x": [], "y": [], "width": 4.0, "color": "rgba(50,50,50,0.9)"},
    ]
    edge_hover_x, edge_hover_y, edge_hover_text = [], [], []

    for u, v, data in ego_G.edges(data=True):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        rc = data.get("raw_count", 1)
        if rc >= 5:
            bkt = _edge_buckets[2]
        elif rc >= 2:
            bkt = _edge_buckets[1]
        else:
            bkt = _edge_buckets[0]
        bkt["x"].extend([x0, x1, None])
        bkt["y"].extend([y0, y1, None])

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

    edge_traces = [
        go.Scatter(
            x=b["x"], y=b["y"],
            line=dict(width=b["width"], color=b["color"]),
            hoverinfo="none",
            mode="lines",
            showlegend=False
        )
        for b in _edge_buckets if b["x"]
    ]

    edge_hover_trace = go.Scatter(
        x=edge_hover_x,
        y=edge_hover_y,
        mode="markers",
        marker=dict(size=10, color="rgba(0,0,0,0)"),
        text=edge_hover_text,
        hoverinfo="text",
        showlegend=False
    )

    node_x, node_y = [], []
    node_text, node_sizes, node_colors, node_labels = [], [], [], []
    node_border_widths, node_border_colors = [], []

    for node in ego_G.nodes():
        x, y = pos[node]
        attr = G.nodes[node]
        is_center = (node == center_code)

        node_x.append(x)
        node_y.append(y)
        node_colors.append(get_node_color(attr, is_selected=is_center))
        node_sizes.append(42 if is_center else 12 + attr.get("degree", 1) * 1.0)

        n_flags = count_flags(attr)
        if is_center:
            node_border_widths.append(2.5)
            node_border_colors.append("black")
        elif n_flags >= 3:
            node_border_widths.append(3.0)
            node_border_colors.append("crimson")
        elif n_flags >= 2:
            node_border_widths.append(2.0)
            node_border_colors.append("darkorange")
        else:
            node_border_widths.append(1.0)
            node_border_colors.append("darkgray")

        label_eng = attr.get("label_eng", node)
        label_kor = attr.get("label_kor", "-")
        node_labels.append(label_eng if is_center else "")

        node_text.append(
            f"<b>{label_eng}</b><br>"
            f"Korean: {label_kor}<br>"
            f"Degree: {attr.get('degree', 0)}<br>"
            f"Pregnancy: {bool_to_yes_no(attr.get('is_preg_contra', False))}<br>"
            f"Elderly: {bool_to_yes_no(attr.get('is_elderly_caution', False))}<br>"
            f"Age-related: {bool_to_yes_no(attr.get('is_age_contra', False))}<br>"
            f"Group overlap: {bool_to_yes_no(attr.get('is_group_overlap', False))}<br>"
            f"Dose caution: {bool_to_yes_no(attr.get('is_dose_caution', False))}<br>"
            f"Duration caution: {bool_to_yes_no(attr.get('is_duration_caution', False))}"
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
            line=dict(width=node_border_widths, color=node_border_colors)
        ),
        showlegend=False
    )

    fig = go.Figure(data=[*edge_traces, edge_hover_trace, node_trace])

    fig.update_layout(
        title=f"Ego Network: {drug_name_eng}",
        title_x=0.5,
        hovermode="closest",
        margin=dict(l=10, r=10, t=45, b=10),
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False),
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=760
    )

    return fig


def draw_global_network_plotly(
    G,
    selected_drug_code=None,
    show_labels=False,
    min_degree=1
):
    nodes_to_show = [
        n for n in G.nodes()
        if G.nodes[n].get("degree", 0) >= min_degree or n == selected_drug_code
    ]
    plot_G = G.subgraph(nodes_to_show)
    pos = nx.spring_layout(plot_G, seed=42, k=0.35)

    _edge_buckets = [
        {"x": [], "y": [], "width": 0.8, "color": "rgba(210,210,210,0.6)"},
        {"x": [], "y": [], "width": 1.8, "color": "rgba(150,150,150,0.75)"},
        {"x": [], "y": [], "width": 3.2, "color": "rgba(70,70,70,0.9)"},
    ]
    edge_hover_x, edge_hover_y, edge_hover_text = [], [], []

    for u, v, data in plot_G.edges(data=True):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        rc = data.get("raw_count", 1)
        if rc >= 5:
            bkt = _edge_buckets[2]
        elif rc >= 2:
            bkt = _edge_buckets[1]
        else:
            bkt = _edge_buckets[0]
        bkt["x"].extend([x0, x1, None])
        bkt["y"].extend([y0, y1, None])

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

    edge_traces = [
        go.Scatter(
            x=b["x"], y=b["y"],
            line=dict(width=b["width"], color=b["color"]),
            hoverinfo="none",
            mode="lines",
            showlegend=False
        )
        for b in _edge_buckets if b["x"]
    ]

    edge_hover_trace = go.Scatter(
        x=edge_hover_x,
        y=edge_hover_y,
        mode="markers",
        marker=dict(size=7, color="rgba(0,0,0,0)"),
        text=edge_hover_text,
        hoverinfo="text",
        showlegend=False
    )

    node_x, node_y = [], []
    node_text, node_sizes, node_colors, node_labels = [], [], [], []
    node_border_widths, node_border_colors = [], []

    for node in plot_G.nodes():
        x, y = pos[node]
        attr = G.nodes[node]
        is_selected = (node == selected_drug_code)

        node_x.append(x)
        node_y.append(y)
        node_colors.append(get_node_color(attr, is_selected=is_selected))

        degree = attr.get("degree", 0)
        size = 8 + degree * 1.0
        if is_selected:
            size = max(size, 26)
        node_sizes.append(size)

        n_flags = count_flags(attr)
        if is_selected:
            node_border_widths.append(2.5)
            node_border_colors.append("black")
        elif n_flags >= 3:
            node_border_widths.append(2.5)
            node_border_colors.append("crimson")
        elif n_flags >= 2:
            node_border_widths.append(1.8)
            node_border_colors.append("darkorange")
        else:
            node_border_widths.append(0.7)
            node_border_colors.append("darkgray")

        label_eng = attr.get("label_eng", node)
        label_kor = attr.get("label_kor", "-")
        node_labels.append(label_eng if show_labels else "")

        node_text.append(
            f"<b>{label_eng}</b><br>"
            f"Korean: {label_kor}<br>"
            f"Degree: {degree}<br>"
            f"Pregnancy: {bool_to_yes_no(attr.get('is_preg_contra', False))}<br>"
            f"Elderly: {bool_to_yes_no(attr.get('is_elderly_caution', False))}<br>"
            f"Age-related: {bool_to_yes_no(attr.get('is_age_contra', False))}<br>"
            f"Group overlap: {bool_to_yes_no(attr.get('is_group_overlap', False))}"
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
            line=dict(width=node_border_widths, color=node_border_colors)
        ),
        showlegend=False
    )

    fig = go.Figure(data=[*edge_traces, edge_hover_trace, node_trace])

    fig.update_layout(
        title=f"Global DUR Contraindication Network ({plot_G.number_of_nodes()} drugs, {plot_G.number_of_edges()} connections)",
        title_x=0.5,
        hovermode="closest",
        margin=dict(l=10, r=10, t=45, b=10),
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False),
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=860
    )

    return fig


# =========================================================
# Tables
# =========================================================
def get_neighbor_table(
    G,
    node_overlay_df,
    drug_name_eng,
    preg_only=False,
    elderly_only=False,
    age_only=False,
    group_only=False,
    top_n_neighbors=20,
    use_llm_reason_short=False
):
    sub = node_overlay_df[node_overlay_df["label_eng"] == drug_name_eng].copy()
    if len(sub) == 0:
        return pd.DataFrame()

    center_code = sub.iloc[0]["code"]

    rows = []
    for neighbor in G.neighbors(center_code):
        attr = G.nodes[neighbor]

        if not node_passes_filters(
            attr,
            preg_only=preg_only,
            elderly_only=elderly_only,
            age_only=age_only,
            group_only=group_only
        ):
            continue

        edge_data = G.get_edge_data(center_code, neighbor)
        reason_raw = edge_data.get("reason_raw", "-")
        reason_clean = edge_data.get("reason_clean", clean_reason_text(reason_raw))
        reason_short = get_reason_short(
            reason_clean,
            use_llm=use_llm_reason_short,
            max_len=100,
        )

        rows.append({
            "Drug (EN)": attr.get("label_eng", neighbor),
            "Drug (KR)": attr.get("label_kor", "-"),
            "Degree": attr.get("degree", 0),
            "Pregnancy": bool_to_yes_no(attr.get("is_preg_contra", False)),
            "Elderly": bool_to_yes_no(attr.get("is_elderly_caution", False)),
            "Age-related": bool_to_yes_no(attr.get("is_age_contra", False)),
            "Group overlap": bool_to_yes_no(attr.get("is_group_overlap", False)),
            "Reason": reason_short,
            "Source Rows": edge_data.get("raw_count", "-"),
            "_reason_clean": reason_clean,
            "_reason_raw": reason_raw,
        })

    if len(rows) == 0:
        return pd.DataFrame(columns=[
            "Drug (EN)", "Drug (KR)", "Degree", "Pregnancy", "Elderly",
            "Age-related", "Group overlap", "Reason", "Source Rows", "_reason_clean", "_reason_raw"
        ])

    neighbor_df = pd.DataFrame(rows).sort_values(
        ["Degree", "Drug (EN)"],
        ascending=[False, True]
    ).reset_index(drop=True)

    return neighbor_df.head(top_n_neighbors)


def get_top_hubs(node_overlay_df, n=20):
    df = node_overlay_df.copy()

    df["Pregnancy"] = df["is_preg_contra"].apply(bool_to_yes_no)
    df["Elderly"] = df["is_elderly_caution"].apply(bool_to_yes_no)
    df["Age-related"] = df["is_age_contra"].apply(bool_to_yes_no)
    df["Group overlap"] = df["is_group_overlap"].apply(bool_to_yes_no)

    return df[[
        "label_eng",
        "label_kor",
        "degree",
        "Pregnancy",
        "Elderly",
        "Age-related",
        "Group overlap"
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
    gc_df = load_dur_csv(base_path / "OpenData_PotOpenDurIngr_GC20260312.csv")
    dc_df = load_dur_csv(base_path / "OpenData_PotOpenDurIngr_DC20260312.csv")
    ec_df = load_dur_csv(base_path / "OpenData_PotOpenDurIngr_EC20260312.csv")

    edge_df = build_edge_table(ac_df)
    node_df = build_node_table(edge_df)
    node_overlay_df = add_overlays(
        node_df, bc_df, cc_df, fc_df, gc_df, dc_df, ec_df
    )

    return edge_df, node_overlay_df


@st.cache_resource
def get_graph(_edge_df, _node_overlay_df):
    return build_graph(_edge_df, _node_overlay_df)


# =========================================================
# App
# =========================================================
st.title("DUR Risk Map")
st.caption("Interactive explorer for public DUR contraindication rules")

edge_df, node_overlay_df = load_pipeline()
G = get_graph(edge_df, node_overlay_df)

# Sidebar
st.sidebar.header("Explore")
drug_options = sorted(node_overlay_df["label_eng"].dropna().unique().tolist())
default_drug = "Rifampicin" if "Rifampicin" in drug_options else drug_options[0]

selected_drug = st.sidebar.selectbox(
    "Drug",
    drug_options,
    index=drug_options.index(default_drug)
)

st.sidebar.markdown("### Filters")
preg_only = st.sidebar.checkbox("Pregnancy only", value=False)
elderly_only = st.sidebar.checkbox("Elderly only", value=False)
age_only = st.sidebar.checkbox("Age-related only", value=False)
group_only = st.sidebar.checkbox("Group overlap only", value=False)

top_n_neighbors = st.sidebar.slider(
    "Visible neighbors",
    min_value=5,
    max_value=50,
    value=20,
    step=5
)

use_llm_reason_short = st.sidebar.checkbox(
    "Use LLM for short reasons (optional)",
    value=False,
    help="If an API key/backend is available, short reasons can use LLM summarization. Otherwise safe deterministic fallback is used.",
)

selected_row = node_overlay_df[node_overlay_df["label_eng"] == selected_drug].iloc[0]
selected_drug_code = selected_row["code"]

neighbor_df = get_neighbor_table(
    G,
    node_overlay_df,
    selected_drug,
    preg_only=preg_only,
    elderly_only=elderly_only,
    age_only=age_only,
    group_only=group_only,
    top_n_neighbors=top_n_neighbors,
    use_llm_reason_short=use_llm_reason_short,
)

tabs = st.tabs(["Ego Network", "Global Network"])
tab1, tab2 = tabs

with tab1:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Drug", selected_drug)
    c2.metric("Degree", int(selected_row["degree"]))
    c3.metric("Visible neighbors", len(neighbor_df))
    c4.metric("Flags", render_flag_badges(selected_row))

    graph_col, detail_col = st.columns([2.2, 1])

    with graph_col:
        render_legend()

        fig = draw_ego_network_plotly_by_name(
            G,
            node_overlay_df,
            selected_drug,
            preg_only=preg_only,
            elderly_only=elderly_only,
            age_only=age_only,
            group_only=group_only,
            top_n_neighbors=top_n_neighbors
        )

        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)

    with detail_col:
        st.markdown("### Drug Detail")

        core_lines = []
        add_bool_line(core_lines, "Pregnancy", selected_row["is_preg_contra"])
        add_detail_line(core_lines, "Pregnancy grade", selected_row["preg_grade"])
        add_bool_line(core_lines, "Elderly", selected_row["is_elderly_caution"])
        add_bool_line(core_lines, "Age-related", selected_row["is_age_contra"])
        add_detail_line(core_lines, "Age rule", selected_row["age_rule"])
        add_bool_line(core_lines, "Group overlap", selected_row["is_group_overlap"])
        add_detail_line(core_lines, "Group name", selected_row["group_name"])
        add_detail_line(core_lines, "Class name", selected_row["class_name"])

        if not core_lines:
            core_lines.append("<div style='margin-bottom:4px;'>No flagged DUR metadata available.</div>")

        render_compact_detail_box("Core DUR info", core_lines)

        additional_lines = []
        add_bool_line(additional_lines, "Dose caution", selected_row["is_dose_caution"])
        add_detail_line(additional_lines, "Dose rule", selected_row["dose_rule"])
        add_detail_line(additional_lines, "Dose reason", selected_row["dose_reason"])
        add_bool_line(additional_lines, "Duration caution", selected_row["is_duration_caution"])
        add_detail_line(additional_lines, "Duration rule", selected_row["duration_rule"])
        add_detail_line(additional_lines, "Duration reason", selected_row["duration_reason"])

        render_compact_detail_box("Additional rules", additional_lines)

    st.markdown("### Connected Drugs")
    if len(neighbor_df) == 0:
        st.info("No directly connected drugs match the current filter settings.")
    else:
        display_neighbor_df = neighbor_df.drop(columns=["_reason_clean", "_reason_raw"]).copy()
        st.dataframe(display_neighbor_df, use_container_width=True, hide_index=True)

        with st.expander("Show cleaned contraindication reasons"):
            clean_reason_df = neighbor_df[["Drug (EN)", "Drug (KR)", "_reason_clean"]].rename(
                columns={"_reason_clean": "Reason (Clean)"}
            )
            st.dataframe(clean_reason_df, use_container_width=True, hide_index=True)

        with st.expander("Show raw contraindication reasons (optional)"):
            raw_reason_df = neighbor_df[["Drug (EN)", "Drug (KR)", "_reason_raw"]].rename(
                columns={"_reason_raw": "Reason (Raw)"}
            )
            st.dataframe(raw_reason_df, use_container_width=True, hide_index=True)

with tab2:
    top_left, top_right = st.columns([3, 1])

    with top_left:
        st.markdown("### Global Network Overview")
        st.caption("Zoom and hover to inspect how drugs are connected across the full network.")
    with top_right:
        show_global_labels = st.checkbox("Show all labels", value=False)

    min_degree_global = st.slider(
        "Min degree (hide low-connectivity nodes)",
        min_value=1,
        max_value=20,
        value=3,
        step=1,
        help="Only show drugs with at least this many direct contraindication connections. Lower values show more nodes but increase clutter."
    )

    render_legend()

    global_fig = draw_global_network_plotly(
        G,
        selected_drug_code=selected_drug_code,
        show_labels=show_global_labels,
        min_degree=min_degree_global
    )
    st.plotly_chart(global_fig, use_container_width=True)

    st.markdown("### Top Hub Ingredients")
    st.dataframe(get_top_hubs(node_overlay_df, n=20), use_container_width=True, hide_index=True)