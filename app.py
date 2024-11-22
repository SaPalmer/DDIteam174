import sqlite3
import pandas as pd
import dash
from dash import dcc, html, Input, Output, State, callback_context
import plotly.graph_objs as go
import networkx as nx
import os
from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()
api_key = os.getenv("OPEN_AI_SECRET_KEY")
ingestion_model = os.getenv("INGESTION_MODEL")
client = OpenAI(api_key=api_key) if api_key else None

conn_graph = sqlite3.connect("data/ddi-graph.db")
ddi_edges_df = pd.read_sql_query("SELECT * FROM DDI_GRAPH", conn_graph)
conn_graph.close()

conn_prj = sqlite3.connect("data/prj174.db")
reactions_df = pd.read_sql_query("SELECT * FROM vwEventDrugReaction", conn_prj)
conn_prj.close()

drug_reactions_df = reactions_df.copy(deep=True)

indications = reactions_df["drugindication"].dropna().unique()
indication_options = [{"label": ind, "value": ind} for ind in indications]

network_drug_options = [
    {"label": drug, "value": drug}
    for drug in pd.unique(ddi_edges_df[["drug_a", "drug_b"]].values.ravel("K"))
]

app = dash.Dash(__name__)

app.layout = html.Div(
    [
        html.H1("Drug-Drug Interaction Network"),
        html.H3("Drug Reactions by Medical Condition"),
        dcc.Dropdown(
            id="indication-dropdown",
            options=indication_options,
            placeholder="Select medical condition to explore drug reactions for...",
        ),
        html.Div(
            [
                html.Div(
                    [dcc.Graph(id="bar-chart")],
                    style={"width": "33%", "display": "inline-block"},
                ),
                html.Div(
                    [dcc.Graph(id="top-reactions-bar-chart")],
                    style={"width": "33%", "display": "inline-block"},
                ),
                html.Div(
                    [dcc.Graph(id="bottom-reactions-bar-chart")],
                    style={"width": "33%", "display": "inline-block"},
                ),
            ],
            style={"display": "flex", "flex-direction": "row"},
        ),
        html.H3("Reaction Summary"),
        html.Div(
            id="reaction-summary", style={"whiteSpace": "pre-wrap", "marginTop": "10px"}
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.H3("Patient Sex Distribution"),
                        dcc.Graph(id="patient-sex-chart"),
                    ],
                    style={"width": "49%", "display": "inline-block"},
                ),
                html.Div(
                    [
                        html.H3("Patient Onset Age Distribution"),
                        dcc.Graph(id="patient-age-chart"),
                    ],
                    style={"width": "49%", "display": "inline-block"},
                ),
            ],
            style={"display": "flex", "flex-direction": "row"},
        ),
        dcc.Dropdown(
            id="drug-input",
            options=network_drug_options,
            placeholder="Select drug(s)",
            multi=True,
        ),
        html.Button(id="submit-button", n_clicks=0, children="Submit"),
        dcc.Graph(id="network-graph"),
        dcc.Graph(id="severity-timeline"),
    ]
)

G = nx.Graph()

unique_drugs = pd.unique(ddi_edges_df[["drug_a", "drug_b"]].values.ravel("K"))
G.add_nodes_from(unique_drugs)

for idx, row in ddi_edges_df.iterrows():
    G.add_edge(row["drug_a"], row["drug_b"], weight=row["weight"])


pos = {}


@app.callback(
    [
        Output("bar-chart", "figure"),
        Output("top-reactions-bar-chart", "figure"),
        Output("bottom-reactions-bar-chart", "figure"),
        Output("patient-sex-chart", "figure"),
        Output("patient-age-chart", "figure"),
    ],
    [Input("indication-dropdown", "value"), Input("bar-chart", "clickData")],
)
def update_bar_charts(selected_indication, drug_click_data):
    if selected_indication:
        filtered_df = drug_reactions_df[
            drug_reactions_df["drugindication"] == selected_indication
        ]

        drug_counts = (
            filtered_df["medicinalproduct"]
            .value_counts()
            .sort_values(ascending=False)
            .head(20)
        )

        drug_fig = go.Figure(
            data=[
                go.Bar(
                    x=drug_counts.values[::-1],
                    y=drug_counts.index[::-1],
                    orientation="h",
                )
            ],
            layout=go.Layout(
                title=f"Most Frequently Reported Drugs for {selected_indication}",
                xaxis={"title": "Count"},
                yaxis={"title": "Drug"},
            ),
        )

        if drug_click_data and "points" in drug_click_data:
            clicked_drug = drug_click_data["points"][0]["y"]
            side_effects_df = filtered_df[
                filtered_df["medicinalproduct"] == clicked_drug
            ]

        else:
            side_effects_df = filtered_df
            clicked_drug = None

        reaction_counts = side_effects_df["reaction"].value_counts()

        top_reactions = reaction_counts.head(10)[::-1]
        bottom_reactions = reaction_counts.tail(10)[::-1]

        max_count = max(reaction_counts.max(), 1)

        title_suffix = f" for {clicked_drug}" if clicked_drug else ""

        top_reactions_fig = go.Figure(
            data=[
                go.Bar(x=top_reactions.values, y=top_reactions.index, orientation="h")
            ],
            layout=go.Layout(
                title=f"Top 10 Most Reported Reactions{title_suffix}",
                xaxis={"title": "Count", "range": [0, max_count]},
                yaxis={"title": "Reaction"},
            ),
        )

        bottom_reactions_fig = go.Figure(
            data=[
                go.Bar(
                    x=bottom_reactions.values, y=bottom_reactions.index, orientation="h"
                )
            ],
            layout=go.Layout(
                title=f"Bottom 10 Least Reported Reactions{title_suffix}",
                xaxis={"title": "Count", "range": [0, max_count]},
                yaxis={"title": "Reaction"},
            ),
        )

        sex_counts = side_effects_df["patientsex"].value_counts().reset_index()
        sex_counts.columns = ["patientsex", "count"]
        sex_fig = go.Figure(
            data=[
                go.Bar(
                    x=sex_counts["patientsex"],
                    y=sex_counts["count"],
                    name="Patient Sex",
                )
            ],
            layout=go.Layout(
                title="Count of SafetyReportIDs by Patient Sex",
                xaxis_title="Patient Sex",
                yaxis_title="Count of SafetyReportIDs",
            ),
        )

        # Patient Onset Age Chart
        age_fig = go.Figure(
            data=[
                go.Histogram(
                    x=side_effects_df[side_effects_df["patientonsetage"] > 0][
                        "patientonsetage"
                    ],
                    nbinsx=25,
                    marker_color="#636EFA",
                )
            ],
            layout=go.Layout(
                title="Distribution of Patient Onset Age",
                xaxis_title="Patient Onset Age",
                yaxis_title="Count",
                bargap=0.1,
            ),
        )

    else:
        drug_fig = go.Figure()
        top_reactions_fig = go.Figure()
        bottom_reactions_fig = go.Figure()
        sex_fig = go.Figure()
        age_fig = go.Figure()

    return drug_fig, top_reactions_fig, bottom_reactions_fig, sex_fig, age_fig


def get_reaction_summary(reaction_name):
    if not client:
        return "Please set up the OPEN_AI_SECRET_KEY in your .env file to use this functionality."

    messages = [
        {
            "role": "system",
            "content": """
            You are an assistent who is only supposed to provide a brief summary and severity of the medical reaction whenever the following function is called:
                get_reaction_summary(reaction_name)
            
            Each request to you should return a brief summary and severity of the medical reaction. The goal is to provide a concise summary of the reaction and its severity level. Your response to the function should always be the following text format - you are never allowed to respond in any other way. You must always provide the requested summary and severity level. You must always make sure that the generated data matches the expected format of the response exactly.

            Text format to put the summary and severity level is shown below:
                Summary of <reaction_name>: <summary> (severity level: <severity_level>)
            """,
        }
    ]

    message = f"User : get_reaction_summary({reaction_name})"
    if reaction_name:
        messages.append(
            {"role": "user", "content": message},
        )
        chat = client.chat.completions.create(model=ingestion_model, messages=messages)

    return chat.choices[0].message.content


@app.callback(
    Output("reaction-summary", "children"),
    [
        Input("top-reactions-bar-chart", "clickData"),
        Input("bottom-reactions-bar-chart", "clickData"),
    ],
)
def update_reaction_summary(top_click, bottom_click):
    ctx = callback_context
    if not ctx.triggered:
        return "Click on a side effect bar to see the summary."
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if button_id == "top-reactions-bar-chart" and top_click and "points" in top_click:
        reaction_name = top_click["points"][0]["label"]
    elif (
        button_id == "bottom-reactions-bar-chart"
        and bottom_click
        and "points" in bottom_click
    ):
        reaction_name = bottom_click["points"][0]["label"]
    else:
        return "Click on a side effect bar to see the summary."
    summary = get_reaction_summary(reaction_name)
    return summary


@app.callback(
    Output("network-graph", "figure"),
    [Input("submit-button", "n_clicks")],
    [State("drug-input", "value")],
)
def update_network(n_clicks, selected_drugs):
    global pos
    if n_clicks == 0 or not selected_drugs:
        return go.Figure()

    if not isinstance(selected_drugs, list):
        selected_drugs = [selected_drugs]

    subgraph_nodes = set()
    for drug in selected_drugs:
        if drug in G:
            subgraph_nodes.add(drug)

            neighbors = sorted(
                G[drug].items(), key=lambda item: item[1].get("weight", 1), reverse=True
            )
            top_neighbors = [neighbor for neighbor, attrs in neighbors[:20]]
            subgraph_nodes.update(top_neighbors)
        else:
            print(f"Drug {drug} not found in the graph.")
    subgraph = G.subgraph(subgraph_nodes).copy()

    if subgraph.number_of_nodes() == 0:
        print("Subgraph is empty.")
        return go.Figure()

    pos = nx.spring_layout(subgraph, weight="weight", seed=42)

    fig = create_network_figure(subgraph, selected_drugs)
    return fig


def create_network_figure(subgraph, selected_drugs):
    global pos

    node_x = []
    node_y = []
    node_color = []
    node_size = []
    node_text = []
    hover_text = []

    edge_x = []
    edge_y = []
    edge_weights = []

    for edge in subgraph.edges(data=True):
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]
        weight = edge[2].get("weight", 1)
        edge_weights.append(weight)

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        line=dict(width=1, color="#888"),
        hoverinfo="none",
        mode="lines",
    )

    for node in subgraph.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        node_label = node
        if node in selected_drugs:
            color = "red"
            text = node_label
            size = 20
        else:
            color = "blue"
            text = ""
            size = 10
        node_color.append(color)
        node_size.append(size)
        node_text.append(text)
        hover_text.append(node_label)

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        text=node_text,
        textposition="top center",
        mode="markers+text",
        hoverinfo="text",
        hovertext=hover_text,
        marker=dict(showscale=False, color=node_color, size=node_size, line_width=2),
    )

    fig = go.Figure(
        data=[edge_trace, node_trace],
        layout=go.Layout(
            title="Drug-Drug Interaction Network",
            showlegend=False,
            hovermode="closest",
            margin=dict(b=20, l=5, r=5, t=40),
            annotations=[],
            xaxis=dict(showgrid=False, zeroline=False),
            yaxis=dict(showgrid=False, zeroline=False),
        ),
    )

    return fig


@app.callback(Output("severity-timeline", "figure"), [Input("drug-input", "value")])
def update_severity_timeline(selected_drugs):
    if not selected_drugs:
        return go.Figure()

    if not isinstance(selected_drugs, list):
        selected_drugs = [selected_drugs]

    mask = drug_reactions_df["medicinalproduct"].isin(selected_drugs)
    timeline_df = drug_reactions_df[mask].copy()

    timeline_df["receiptdate"] = pd.to_datetime(timeline_df["receiptdate"])
    timeline_df["month"] = timeline_df["receiptdate"].dt.to_period("M")

    severity_counts = (
        timeline_df.groupby(["month", "serious"])["safetyreportid"]
        .count()
        .reset_index()
    )

    pivot_df = severity_counts.pivot(
        index="month", columns="serious", values="safetyreportid"
    ).fillna(0)

    fig = go.Figure()

    colors = ["#fee8c8", "#fdbb84", "#e34a33"]
    for severity, color in zip(sorted(timeline_df["serious"].unique()), colors):
        if severity in pivot_df.columns:
            fig.add_trace(
                go.Bar(
                    name=f"Severity: {severity}",
                    x=[str(x) for x in pivot_df.index],
                    y=pivot_df[severity],
                    marker_color=color,
                )
            )

    fig.update_layout(
        title=f'Monthly FAERS Reports by Severity for {", ".join(selected_drugs)}',
        xaxis_title="Month-Year of Report",
        yaxis_title="Count of Reports",
        barmode="stack",
        showlegend=True,
        legend_title="Severity Level",
    )

    return fig


if __name__ == "__main__":
    app.run_server(debug=True)
