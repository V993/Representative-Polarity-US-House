# Predicting Ideological Polarity in the House of Representatives
#### Author: Leonardo Matone

Site accessible at: [https://v993.github.io/Representative-Polarity-US-House/](https://v993.github.io/Representative-Polarity-US-House/)

## Data:

The ETL process for all of the sources utilized in this project is very long and complex. The two main files required to recreate the data used in this study are **data.py** and **fresh_data/get_datasets.py**. The former includes the process of merging all collected tables, and the latter includes functional calls to collect each table from various sources. A combination of web scraping, mass file downloads, and the occasional API call led to the sources attached here.

An example of loading the data (which takes around 1.5 minutes) is in this project's webpage, and the final notebook (**leonardo_final.ipynb**). Information about decisions made in data wrangling can be found in the aforementioned files, and several notebooks exist in the root of this diretory (prefixed with "test") which include rudementary explorations of the data used in the merging process.

In short, replicating **full_df.csv** is accomplished in the following code: 

```
from data import get_df
df = get_df()
```

This data was accumulated from the following sources:

1. [VoteView](https://voteview.com/data) DW-NOMINATE scores of representatives in the house of congress
2. [OpenSecrets](https://www.opensecrets.org/) data on lobbying, campaign finance, and personal finances for congressional representatives
3. [FEC](https://www.fec.gov/campaign-finance-data/congressional-candidate-data-summary-tables/?year=2018&segment=24) campaign finance data for congressional representatives
4. [Pew Research Center](https://www.pewresearch.org/religion/religious-landscape-study/state/) religious populations in each state, and questions from the census on belief in god
5. [US Census](https://www.census.gov/data/datasets/time-series/demo/saipe/model-tables.html) decennial population and geodata per state
6. [KFF](https://www.kff.org/other/state-indicator/total-residents/?currentTimeframe=0&sortModel=%7B%22colId%22:%22Location%22,%22sort%22:%22asc%22%7D) state demographics data including race and poverty statistics
7. [IRS](https://www.census.gov/data/datasets/time-series/demo/saipe/model-tables.html) data on SAIPE (Small Area Income and Poverty Estimates)
