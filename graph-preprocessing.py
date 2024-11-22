import sqlite3
import pandas as pd
import numpy as np
import os


def build_ddi_graph(db_path):
    conn = sqlite3.connect(db_path)
    conn_2 = sqlite3.connect("data/prj174.db")
    graph_conn = sqlite3.connect("data/ddi-graph.db")

    drugs_df = pd.read_sql_query(
        "SELECT safetyreportid, medicinalproduct, drugstartdate, drugenddate FROM DRUGS",
        conn,
    )
    reactions_df = pd.read_sql_query(
        "SELECT * FROM vwEventDrugReaction",
        conn_2,
    )
    reactions_df["safetyreportid"] = reactions_df["safetyreportid"].astype(str)

    drugs_df["drugstartdate"] = pd.to_datetime(
        drugs_df["drugstartdate"], errors="coerce"
    )
    drugs_df["drugenddate"] = pd.to_datetime(drugs_df["drugenddate"], errors="coerce")

    drugs_df["drugstartdate"].fillna(pd.Timestamp.min, inplace=True)
    drugs_df["drugenddate"].fillna(pd.Timestamp.max, inplace=True)

    edge_dict = {}
    grouped = drugs_df.groupby("safetyreportid")
    for safetyreportid, group in grouped:
        group = group.copy()
        if len(group) > 1:

            start_dates = group["drugstartdate"].values
            end_dates = group["drugenddate"].values
            drugs = group["medicinalproduct"].values

            report_severity = pd.NA # disregard severity for now

            if pd.isna(report_severity):
                report_severity = 0

            overlap_matrix = (start_dates[:, None] <= end_dates) & (
                end_dates[:, None] >= start_dates
            )

            np.fill_diagonal(overlap_matrix, False)

            overlapping_indices = np.argwhere(overlap_matrix)

            for idx in overlapping_indices:
                i, j = idx
                drug_a = drugs[i]
                drug_b = drugs[j]

                if drug_a > drug_b:
                    drug_a, drug_b = drug_b, drug_a

                edge_key = (drug_a, drug_b)
                if edge_key not in edge_dict:
                    edge_dict[edge_key] = {"count": 0, "severity_sum": 0}

                edge_dict[edge_key]["count"] += 1
                edge_dict[edge_key]["severity_sum"] += report_severity

    edges_list = []
    for (drug_a, drug_b), data in edge_dict.items():
        edges_list.append(
            {
                "drug_a": drug_a,
                "drug_b": drug_b,
                "weight": data["count"],
                "mean_severity": data["severity_sum"] / data["count"],
            }
        )

    edges_df = pd.DataFrame(edges_list)

    node_severity = {}
    for _, row in edges_df.iterrows():

        if row["drug_a"] not in node_severity:
            node_severity[row["drug_a"]] = {"severity_sum": 0, "count": 0}
        node_severity[row["drug_a"]]["severity_sum"] += row["mean_severity"]
        node_severity[row["drug_a"]]["count"] += 1

        if row["drug_b"] not in node_severity:
            node_severity[row["drug_b"]] = {"severity_sum": 0, "count": 0}
        node_severity[row["drug_b"]]["severity_sum"] += row["mean_severity"]
        node_severity[row["drug_b"]]["count"] += 1

    nodes_list = [
        {"drug": drug, "mean_severity": data["severity_sum"] / data["count"]}
        for drug, data in node_severity.items()
    ]
    nodes_df = pd.DataFrame(nodes_list)

    edges_df.to_sql("DDI_GRAPH", graph_conn, if_exists="replace", index=False)
    nodes_df.to_sql("DDI_NODES", graph_conn, if_exists="replace", index=False)

    conn.close()
    graph_conn.close()

    return edges_df, nodes_df, reactions_df


if __name__ == "__main__":
    build_ddi_graph("data/fda_data.db")
