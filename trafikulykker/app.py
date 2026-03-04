import pandas as pd
import plotly.graph_objects as go
from faicons import icon_svg
from shiny import App, reactive, render, ui
from shinywidgets import output_widget, render_widget

from shared import age_choices, app_dir, df, transport_choices

INJURY_ORDER = ["Dræbte", "Alvorligt tilskadekomne", "Lettere tilskadekomne"]
SEX_ORDER = ["Kvinder", "Mænd"]
INJURY_ICONS = ["skull-crossbones", "triangle-exclamation", "bandage"]


app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.input_selectize(
            "ages",
            "Age group",
            choices=age_choices,
            selected=age_choices,
            multiple=True,
        ),
        ui.input_selectize(
            "transport_modes",
            "Transport mode",
            choices=transport_choices,
            selected=transport_choices,
            multiple=True,
        ),
        title="Filter controls",
    ),
    ui.layout_columns(
        *[
            ui.value_box(
                f"{injury} - Kvinder",
                ui.output_text(f"kpi_women_{idx}"),
                showcase=icon_svg(INJURY_ICONS[idx]),
            )
            for idx, injury in enumerate(INJURY_ORDER)
        ],
        fill=False,
    ),
    ui.layout_columns(
        *[
            ui.value_box(
                f"{injury} - Mænd",
                ui.output_text(f"kpi_men_{idx}"),
                showcase=icon_svg(INJURY_ICONS[idx]),
            )
            for idx, injury in enumerate(INJURY_ORDER)
        ],
        fill=False,
    ),
    *[
        ui.card(
            ui.card_header(f"{injury} (all years)"),
            output_widget(f"incidence_trend_{idx}", height="640px"),
            full_screen=False,
            style="min-height: 700px; max-height: 820px; overflow-y: auto;",
        )
        for idx, injury in enumerate(INJURY_ORDER)
    ],
    ui.include_css(app_dir / "styles.css"),
    title="Traffic Accident Incidence Dashboard",
    fillable=True,
)


def server(input, output, session):
    all_years = sorted(df["year"].unique().tolist())
    min_year = min(all_years)
    max_year = max(all_years)

    transport_order = [
        "I alt",
        "Almindelig personbil",
        "Motorcykel",
        "Knallert",
        "Cykel",
        "Fodgænger",
    ]
    transport_legend_label = {
        "I alt": "I alt",
        "Almindelig personbil": "🚗",
        "Motorcykel": "🏍️",
        "Knallert": "🛵",
        "Cykel": "🚲",
        "Fodgænger": "🚶",
    }
    transport_marker_symbol = {
        "I alt": "circle",
        "Almindelig personbil": "square",
        "Motorcykel": "triangle-up",
        "Knallert": "diamond",
        "Cykel": "x",
        "Fodgænger": "cross",
    }
    transport_rank = {name: idx for idx, name in enumerate(transport_order)}
    blue_shades = ["#1f77b4", "#2a6fbb", "#3a7dc4", "#4a8acc", "#5a98d4", "#6aa5dc"]
    red_shades = ["#d62728", "#d64a4a", "#de5f5f", "#e57575", "#ec8b8b", "#f2a1a1"]

    def sex_short(name: str) -> str:
        text = name.lower()
        if "mænd" in text or "men" in text:
            return "Mænd"
        if "kvinder" in text or "women" in text:
            return "Kvinder"
        return name

    def series_color(sex_label: str, transport_mode: str) -> str:
        palette = blue_shades if sex_label == "Mænd" else red_shades
        idx = transport_rank.get(transport_mode, 0) % len(palette)
        return palette[idx]

    @reactive.calc
    def filtered_df():
        ages = set(input.ages()) if input.ages() else set()
        transports = set(input.transport_modes()) if input.transport_modes() else set()

        filt = df.copy()
        if ages:
            filt = filt[filt["age_group"].isin(ages)]
        if transports:
            filt = filt[filt["transport_mode"].isin(transports)]
        return filt

    def kpi_value(sex_label: str, injury: str) -> str:
        data = filtered_df().copy()
        if data.empty:
            return "No data"

        data["sex"] = data["sex_indicator"].map(sex_short)
        data = data[(data["sex"] == sex_label) & (data["injury_severity"] == injury)]
        if data.empty:
            return "No data"
        return f"{data['incidence_per_100k'].mean():.2f} per 100,000"

    def build_injury_figure(injury: str) -> go.Figure:
        data = filtered_df().copy()
        data = data[data["injury_severity"] == injury]

        if data.empty:
            fig = go.Figure()
            fig.add_annotation(
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                text="No data for selected filters",
                showarrow=False,
            )
            fig.update_xaxes(visible=False)
            fig.update_yaxes(visible=False)
            return fig

        grouped = (
            data.groupby(["sex_indicator", "transport_mode", "year"], as_index=False)[
                "incidence_per_100k"
            ]
            .mean()
            .sort_values(["transport_mode", "sex_indicator", "year"])
        )
        grouped["sex"] = grouped["sex_indicator"].map(sex_short)

        transports_in_data = [
            x for x in transport_order if x in grouped["transport_mode"].unique()
        ]
        sex_in_data = [x for x in SEX_ORDER if x in grouped["sex"].unique()]

        full_idx = pd.MultiIndex.from_product(
            [sex_in_data, transports_in_data, all_years],
            names=["sex", "transport_mode", "year"],
        )
        completed = (
            grouped.set_index(["sex", "transport_mode", "year"])
            .reindex(full_idx)
            .reset_index()
        )

        fig = go.Figure()
        for transport in transports_in_data:
            for sex in sex_in_data:
                trace_df = completed[
                    (completed["transport_mode"] == transport)
                    & (completed["sex"] == sex)
                ]
                fig.add_trace(
                    go.Scatter(
                        x=trace_df["year"],
                        y=trace_df["incidence_per_100k"],
                        mode="lines+markers",
                        name=f"{sex} | {transport_legend_label.get(transport, transport)}",
                        legendgroup=f"{transport}_{sex}",
                        line=dict(color=series_color(sex, transport)),
                        marker=dict(symbol=transport_marker_symbol.get(transport, "circle"), size=9),
                        connectgaps=False,
                    )
                )

        fig.update_layout(
            legend_title_text="Sex | Transport mode",
            margin=dict(l=40, r=20, t=40, b=40),
            height=620,
        )
        fig.update_xaxes(
            title="Year",
            range=[min_year, max_year],
            dtick=2,
            tickmode="linear",
        )
        fig.update_yaxes(title="Average incidence per 100,000")
        return fig

    @output(id="incidence_trend_0")
    @render_widget
    def incidence_trend_0():
        return build_injury_figure(INJURY_ORDER[0])

    @output(id="incidence_trend_1")
    @render_widget
    def incidence_trend_1():
        return build_injury_figure(INJURY_ORDER[1])

    @output(id="incidence_trend_2")
    @render_widget
    def incidence_trend_2():
        return build_injury_figure(INJURY_ORDER[2])

    @output(id="kpi_women_0")
    @render.text
    def kpi_women_0():
        return kpi_value("Kvinder", INJURY_ORDER[0])

    @output(id="kpi_women_1")
    @render.text
    def kpi_women_1():
        return kpi_value("Kvinder", INJURY_ORDER[1])

    @output(id="kpi_women_2")
    @render.text
    def kpi_women_2():
        return kpi_value("Kvinder", INJURY_ORDER[2])

    @output(id="kpi_men_0")
    @render.text
    def kpi_men_0():
        return kpi_value("Mænd", INJURY_ORDER[0])

    @output(id="kpi_men_1")
    @render.text
    def kpi_men_1():
        return kpi_value("Mænd", INJURY_ORDER[1])

    @output(id="kpi_men_2")
    @render.text
    def kpi_men_2():
        return kpi_value("Mænd", INJURY_ORDER[2])


app = App(app_ui, server)
