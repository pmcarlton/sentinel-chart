# Japan infectious disease surveillance: sentinel reports

[日本語](README.ja.md)

This app shows weekly reports of infectious diseases in Japan. It uses provisional data from the Japan Institute for Health Security (JIHS). You can view national trends and compare prefectures for up to two diseases.

**This is an unofficial summary.** For official figures and updates, use the [JIHS infectious disease surveillance site](https://id-info.jihs.go.jp/surveillance/idwr/index.html). JIHS may revise provisional data.

## Run the app

You need Python 3, an internet connection, and permission to write to this folder. From the project folder, run:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Streamlit will print a local address. Open it in your browser.

The first launch loads the CSV files in `data/` into a local database. This may take a little time. To stop the app, press `Ctrl+C` in the terminal.

## Use the app

1. Choose English or Japanese in the sidebar.
2. Choose a disease in **Disease 1**. Choose a second disease in **Disease 2**, or choose **None**.
3. Choose reported case counts or cases per sentinel. A sentinel is a reporting medical facility; the count is not the total number of cases in Japan.
4. Choose a week with the slider, or select a point on the trend chart.
5. Select a prefecture in the table to zoom the map. Use the reset button to return to the national view.

Hover over **Data interpretation** for notes about comparing diseases and changes in reporting. The sidebar links to the source for the selected week when available.

## Read the map

With one disease, darker color means a higher value. With two diseases, the first adds magenta and the second adds green. White means both values are zero; dark gray means both are high. Yellow means a value is missing.

Each disease's color is scaled to its highest prefectural value in the loaded archive for the selected measure. The two colors therefore show each disease's level relative to its own maximum, not a direct comparison of case numbers. The source uses `-` for some values; the app treats these as missing.

Diseases can use different types of reporting facilities and cover different patient populations. Take care when comparing them. The influenza reporting network also changed in 2025 week 15, which affects comparisons across that date.

## Data and updates

- `data/` contains source CSV files. The app saves newly downloaded files there and may replace files when it refreshes recent weeks.
- `japan_surveillance_verified.db` is a local SQLite database created from those files. It is not tracked by Git.
- When opened, the app checks for updates at most once every six hours. An open session also checks periodically. It looks for newly completed weeks and refreshes the latest three archived weeks. If the app is stopped, it checks when opened again.
- The sidebar shows the last automatic check and reports download errors. The full backfill button can fetch missing historical weeks and refresh recent data.
- Map boundaries are downloaded separately. The map needs an internet connection if the boundary data is not cached.

If an update fails, check your connection and try the backfill button later. If no data appears, check that `data/` contains the source CSV files and that the app can write to the project folder.
