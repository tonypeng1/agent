# ETF Activity Analysis Agents

This repository automates the process of fetching, validating, transforming, and analyzing ETF (Exchange-Traded Fund) activity data from online sources using agent-based workflows. The system leverages LLM models and MCP, orchestrated through the OpenAI Agents SDK, to perform deterministic multi-step agent pipelines.

## Features

- **Automated Data Fetching:** Retrieves ETF tables from Yahoo Finance and ETFdb.
- **Data Validation:** Ensures fetched tables have the correct structure and expected number of rows.
- **Date Handling:** Fetches and validates the current date/time for timestamping data.
- **Data Transformation:** Adds date columns and standardizes headers in CSV outputs.
- **Historical Comparison:** (Planned/Partial) Filters and compares ETF data across different dates for trend analysis.
- **Trend Analysis:** Uses LLMs to summarize and interpret ETF activity trends.

## Main Scripts

### [`yahoo_local.py`](yahoo_local.py)

This script orchestrates a workflow to compare ETF activity between Yahoo Finance (based on the current one-day volume) and ETFdb (based on the volume of 3-month average):

1. **Fetches** the top 20 most active ETFs from Yahoo Finance.
2. **Validates** the Yahoo table structure and content.
3. **Fetches** the top 20 most active ETFs from ETFdb.
4. **Validates** the ETFdb table structure and content.
5. **Fetches and validates** the current date and time.
6. **Adds** the current date as the first column in both tables and standardizes headers.
7. **Saves** the modified tables as CSV files in the `data/` directory.
8. **Loads** the modified tables and **analyzes trends** between the two sources using an LLM agent, focusing on differences in daily vs. 3-month average volumes.

> **Note:** The "Volume" column in the Yahoo Finance data represents the current one-day ETF trading volume, while the "Avg Daily Share Volume (3mo)" column from ETFdb is a 3-month average. This distinction is important for interpreting trends and comparing activity between the two sources.

### [`edf_local.py`](edf_local.py)

This script focuses on historical and trend analysis using only ETFdb data (based on the volume of 3-month average):

1. **Fetches** the top 20 most active ETFs from ETFdb.
2. **Validates** the table structure and content.
3. **Fetches and validates** the current date and time.
4. **Adds** the current date as the first column in the table.
5. **Appends** the modified table to a cumulative CSV file in the `data/` directory.
6. **Filters** the table by specific dates (current and about a week earlier).
7. **Analyzes** Compare the trends between the two filtered tables using an LLM agent.

## Data Files

- All output CSVs are stored in the `data/` directory.
- The main cumulative file is `data/table_etfdb_output.csv`.

## Requirements

- Python 3.13+
- See [`pyproject.toml`](pyproject.toml) for dependencies.

## Usage

1. Install `uv` if you do not have it. [Installation guide](https://docs.astral.sh/uv/getting-started/installation/)
2. Set up your `.env` file with the required API keys.
3. Clone the repository:
   ```
   git clone https://github.com/tonypeng1/agent.git
   ```
4. Change into the project directory and check out the specific version:
   ```
   cd agent
   git checkout v0.1
   ```
5. Run one of the main scripts:
   ```
   uv run edf_local.py
   ```
   or
   ```
   uv run yahoo_local.py
   ```
   `uv` will automatically create (if needed) and update the environment with the dependencies specified in the lockfile before running your script.

## Notes

- The scripts use agent-based orchestration and require access to OpenAI and Anthropic APIs.
- To only fetch and append the daily data from ETF DB, comment out the advanced features (historical filtering and trend analysis) in `edf_local.py`.
