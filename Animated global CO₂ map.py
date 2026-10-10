
"""
GLOBAL CLIMATE CHANGE MAP & TIMELINE
Python project for VS Code
"""

from pathlib import Path
import webbrowser
import requests
import pandas as pd
import plotly.express as px
import folium

# =========================================================
# CONFIGURATION
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

DATA_URL = (
    "https://raw.githubusercontent.com/"
    "owid/co2-data/master/owid-co2-data.csv"
)

START_YEAR = 1970

BG_COLOR = "#0B1220"
CARD_COLOR = "#151F32"
TEXT_COLOR = "#E8EEF7"

# =========================================================
# 1. DOWNLOAD DATA
# =========================================================

def download_data():
    print("\nDownloading climate data...")

    response = requests.get(
        DATA_URL,
        headers={"User-Agent": "GlobalClimateDashboard/1.0"},
        timeout=120
    )
    response.raise_for_status()

    csv_path = OUTPUT_DIR / "climate_data.csv"
    csv_path.write_bytes(response.content)

    from io import BytesIO

    df = pd.read_csv(
        BytesIO(response.content),
        low_memory=False
    )

    print("Dataset downloaded successfully!")
    return df


# =========================================================
# 2. CLEAN DATA
# =========================================================

def clean_data(df):
    required = [
        "country", "year", "iso_code",
        "co2", "population", "gdp"
    ]

    missing = [c for c in required if c not in df.columns]

    if missing:
        raise ValueError(
            f"Required columns are missing: {missing}"
        )

    data = df[required].copy()

    for column in ["year", "co2", "population", "gdp"]:
        data[column] = pd.to_numeric(
            data[column], errors="coerce"
        )

    data = data[
        (data["year"] >= START_YEAR)
        & data["iso_code"].str.fullmatch(
            r"[A-Z]{3}", na=False
        )
        & (data["co2"] >= 0)
        & (data["population"] > 0)
    ].copy()

    data["year"] = data["year"].astype(int)

    data["gdp_per_capita"] = (
        data["gdp"] / data["population"]
    )

    data = data.drop_duplicates(
        subset=["iso_code", "year"]
    )

    return data


# =========================================================
# 3. COMMON CHART STYLING
# =========================================================

def style_chart(fig, height=600):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=BG_COLOR,
        plot_bgcolor=CARD_COLOR,
        font=dict(
            family="Arial",
            color=TEXT_COLOR,
            size=13
        ),
        title_x=0.03,
        height=height,
        margin=dict(l=40, r=40, t=80, b=50)
    )

    fig.update_xaxes(gridcolor="#263449")
    fig.update_yaxes(gridcolor="#263449")

    return fig


def save_chart(fig, filename):
    path = OUTPUT_DIR / filename

    fig.write_html(
        str(path),
        include_plotlyjs=True,
        full_html=True
    )

    print(f"Created: {path}")
    return path


# =========================================================
# 4. ANIMATED WORLD MAP
# =========================================================

def create_animated_map(data):
    print("\nCreating animated world map...")

    map_data = data.dropna(subset=["co2"]).copy()

    if map_data.empty:
        raise ValueError("No emissions data is available.")

    color_max = map_data["co2"].quantile(0.98)

    fig = px.choropleth(
        map_data,
        locations="iso_code",
        locationmode="ISO-3",
        color="co2",
        animation_frame="year",
        animation_group="iso_code",
        hover_name="country",
        hover_data={
            "iso_code": False,
            "year": True,
            "co2": ":,.2f",
            "population": ":,.0f"
        },
        color_continuous_scale="YlOrRd",
        range_color=[0, max(color_max, 1)],
        projection="natural earth",
        title="Global CO₂ Emissions: Historical Timeline",
        labels={
            "co2": "Annual CO₂ emissions (million tonnes)",
            "year": "Year"
        }
    )

    fig.update_geos(
        showframe=False,
        showcoastlines=True,
        coastlinecolor="#64748B",
        showcountries=True,
        countrycolor="#475569",
        showland=True,
        landcolor="#182235",
        bgcolor=BG_COLOR
    )

    style_chart(fig, 700)

    save_chart(fig, "animated_world_map.html")


# =========================================================
# 5. GDP VS CO₂ BUBBLE CHART
# =========================================================

def create_gdp_chart(data, latest_year):
    print("\nCreating GDP bubble chart...")

    bubble = data[
        (data["year"] == latest_year)
        & data["gdp_per_capita"].notna()
        & (data["gdp_per_capita"] > 0)
    ].copy()

    # If GDP data is unavailable in the latest emissions
    # year, use the latest year with usable GDP information.
    if bubble.empty:
        valid = data[
            data["gdp_per_capita"].notna()
            & (data["gdp_per_capita"] > 0)
        ]

        if valid.empty:
            print("GDP data is unavailable. Skipping chart.")
            return

        year = int(valid["year"].max())

        bubble = valid[valid["year"] == year].copy()
    else:
        year = latest_year

    bubble = bubble.dropna(
        subset=["co2", "population", "gdp_per_capita"]
    )

    fig = px.scatter(
        bubble,
        x="gdp_per_capita",
        y="co2",
        size="population",
        color="co2",
        hover_name="country",
        hover_data={
            "population": ":,.0f",
            "gdp_per_capita": ":,.2f",
            "co2": ":,.2f"
        },
        size_max=45,
        log_x=True,
        color_continuous_scale="Turbo",
        title=f"GDP Per Capita vs CO₂ Emissions ({year})",
        labels={
            "gdp_per_capita": "GDP per capita (dataset units)",
            "co2": "Annual CO₂ emissions (million tonnes)",
            "population": "Population"
        }
    )

    fig.update_traces(
        marker=dict(
            opacity=0.8,
            line=dict(width=0.5, color="white")
        )
    )

    style_chart(fig, 650)
    save_chart(fig, "gdp_vs_co2.html")


# =========================================================
# 6. HISTORICAL TIMELINE
# =========================================================

def create_timeline(data):
    print("\nCreating historical timeline...")

    yearly = (
        data.groupby("year", as_index=False)
        .agg(
            total_co2=("co2", "sum"),
            reporting_countries=("iso_code", "nunique")
        )
    )

    fig = px.line(
        yearly,
        x="year",
        y="total_co2",
        markers=True,
        title="Reported Country CO₂ Emissions Over Time",
        labels={
            "year": "Year",
            "total_co2": "Sum of emissions (million tonnes)"
        },
        hover_data=["reporting_countries"]
    )

    fig.update_traces(
        line=dict(color="#38BDF8", width=3),
        marker=dict(size=5)
    )

    style_chart(fig, 500)
    save_chart(fig, "emissions_timeline.html")


# =========================================================
# 7. TOP 10 EMITTERS
# =========================================================

def create_top_emitters(data, latest_year):
    print("\nCreating top emitters chart...")

    latest = data[data["year"] == latest_year]

    top = (
        latest.sort_values("co2", ascending=False)
        .head(10)
        .sort_values("co2", ascending=True)
    )

    fig = px.bar(
        top,
        x="co2",
        y="country",
        orientation="h",
        text="co2",
        color="co2",
        color_continuous_scale="YlOrRd",
        title=f"Top 10 CO₂ Emitters ({latest_year})",
        labels={
            "co2": "Annual emissions (million tonnes)",
            "country": "Country"
        }
    )

    fig.update_traces(
        texttemplate="%{text:,.0f}",
        textposition="outside",
        cliponaxis=False
    )

    style_chart(fig, 600)
    save_chart(fig, "top_emitters.html")


# =========================================================
# 8. FOLIUM WORLD MAP
# =========================================================

def create_folium_map(data, latest_year):
    print("\nCreating Folium map...")

    latest = data[data["year"] == latest_year].copy()

    geojson_url = (
        "https://raw.githubusercontent.com/"
        "datasets/geo-countries/master/data/countries.geojson"
    )

    response = requests.get(
        geojson_url,
        headers={"User-Agent": "GlobalClimateDashboard/1.0"},
        timeout=60
    )
    response.raise_for_status()

    geojson = response.json()

    properties = geojson["features"][0]["properties"]

    possible_keys = [
        "ISO3166-1-Alpha-3",
        "ISO_A3",
        "ADM0_A3",
        "iso_a3"
    ]

    geo_key = next(
        (key for key in possible_keys if key in properties),
        None
    )

    if geo_key is None:
        print("Could not identify the country code field.")
        return

    world = folium.Map(
        location=[20, 0],
        zoom_start=2,
        tiles="CartoDB positron",
        control_scale=True
    )

    folium.Choropleth(
        geo_data=geojson,
        data=latest,
        columns=["iso_code", "co2"],
        key_on=f"feature.properties.{geo_key}",
        fill_color="YlOrRd",
        fill_opacity=0.8,
        line_opacity=0.25,
        nan_fill_color="#D1D5DB",
        legend_name=(
            f"CO₂ emissions in {latest_year} "
            "(million tonnes)"
        )
    ).add_to(world)

    folium.LayerControl().add_to(world)

    output = OUTPUT_DIR / "folium_world_map.html"
    world.save(str(output))

    print(f"Created: {output}")


# =========================================================
# 9. MAIN PROGRAM
# =========================================================

def main():
    try:
        df = download_data()
        data = clean_data(df)

        if data.empty:
            raise ValueError("No valid country data found.")

        latest_year = int(data["year"].max())

        print("\n" + "=" * 55)
        print("GLOBAL CLIMATE CHANGE DASHBOARD")
        print("=" * 55)
        print(f"Year range: {START_YEAR}–{latest_year}")
        print(f"Countries represented: {data['iso_code'].nunique()}")
        print(f"Country-year records: {len(data):,}")
        print("=" * 55)

        # Save the cleaned dataset.
        data.to_csv(
            OUTPUT_DIR / "global_climate_cleaned.csv",
            index=False
        )

        # Create each visualization.
        create_animated_map(data)
        create_gdp_chart(data, latest_year)
        create_timeline(data)
        create_top_emitters(data, latest_year)

        try:
            create_folium_map(data, latest_year)
        except Exception as error:
            print(f"Folium map could not be created: {error}")

        # Create an HTML home page for easy navigation.
        links = [
            ("Animated World Map", "animated_world_map.html"),
            ("GDP vs CO₂ Bubble Chart", "gdp_vs_co2.html"),
            ("Historical Timeline", "emissions_timeline.html"),
            ("Top 10 Emitters", "top_emitters.html"),
            ("Folium World Map", "folium_world_map.html")
        ]

        cards = "\n".join(
            f"""
            <a class="card" href="{filename}">
                <span>{title}</span>
                <span class="arrow">↗</span>
            </a>
            """
            for title, filename in links
            if (OUTPUT_DIR / filename).exists()
        )

        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
        <meta charset="UTF-8">
        <meta name="viewport"
              content="width=device-width, initial-scale=1">
        <title>Global Climate Analytics</title>
        <style>
            body {{
                margin: 0;
                padding: 40px 20px;
                background: {BG_COLOR};
                color: {TEXT_COLOR};
                font-family: Arial, sans-serif;
            }}
            main {{
                max-width: 1000px;
                margin: auto;
            }}
            h1 {{ font-size: 36px; }}
            p {{ color: #9CAEC4; line-height: 1.7; }}
            .grid {{
                display: grid;
                grid-template-columns:
                    repeat(auto-fit, minmax(240px, 1fr));
                gap: 18px;
                margin-top: 30px;
            }}
            .card {{
                display: flex;
                justify-content: space-between;
                gap: 10px;
                padding: 25px;
                border: 1px solid #263449;
                border-radius: 14px;
                background: {CARD_COLOR};
                color: {TEXT_COLOR};
                text-decoration: none;
                transition: transform .2s, border-color .2s;
            }}
            .card:hover {{
                transform: translateY(-4px);
                border-color: #38BDF8;
            }}
            .arrow {{ color: #38BDF8; }}
            footer {{
                margin-top: 40px;
                color: #9CAEC4;
                font-size: 13px;
            }}
        </style>
        </head>
        <body>
        <main>
            <p>CLIMATE DATA SCIENCE PROJECT</p>
            <h1>🌍 Global Climate Analytics</h1>
            <p>
                Explore global CO₂ emissions, historical trends,
                GDP relationships, and country comparisons.
                Data period: {START_YEAR}–{latest_year}.
            </p>
            <div class="grid">{cards}</div>
            <footer>
                Data source: Our World in Data CO₂ dataset.
                Values depend on country reporting coverage.
            </footer>
        </main>
        </body>
        </html>
        """

        home = OUTPUT_DIR / "index.html"
        home.write_text(html, encoding="utf-8")

        print("\nPROJECT COMPLETED SUCCESSFULLY!")
        print(f"Dashboard: {home.resolve()}")

        # Open the dashboard in your default browser.
        webbrowser.open(home.resolve().as_uri())

    except requests.RequestException as error:
        print("\nDATA DOWNLOAD ERROR")
        print(error)
        print(
            "Check your internet connection, or try again later."
        )

    except Exception as error:
        print("\nPROJECT ERROR")
        print(error)
        raise


if __name__ == "__main__":
    main()
