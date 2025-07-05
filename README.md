# ETF Activity Analysis Agents

This repository automates the process of fetching, validating, transforming, and analyzing ETF (Exchange-Traded Fund) activity data from online sources using agent-based workflows. The system leverages LLM models and MCP, orchestrated through the OpenAI Agents SDK, to perform deterministic multi-step agent pipelines.

## Features

- **Automated Data Fetching:** Retrieves ETF tables from Yahoo Finance and ETFdb with retry logic.
- **Data Validation:** Ensures fetched tables have the correct structure and expected number of rows.
- **Date Handling:** Fetches and validates the current date/time for timestamping data with retry logic.
- **Data Transformation:** Adds date columns and standardizes headers in CSV outputs.
- **Historical Comparison:** Filters and compares ETF data across different dates for trend analysis.
- **Trend Analysis:** Uses LLMs to summarize and interpret ETF activity trends.

## Main Scripts

### [`yahoo_local.py`](yahoo_local.py)

This script orchestrates a workflow to compare the top 20 most active ETFs between Yahoo Finance (based on the current one-day volume) and ETFdb (based on the volume of 3-month average):

1. **Fetches** the top 20 most active ETFs from Yahoo Finance with retry logic.
2. **Validates** the Yahoo table structure and content.
3. **Fetches** the top 20 most active ETFs from ETFdb with retry logic.
4. **Validates** the ETFdb table structure and content.
5. **Fetches and validates** the current date and time with retry logic.
6. **Adds** the current date as the first column in both tables and standardizes headers.
7. **Saves** the modified tables as CSV files in the `data/` directory.
8. **Loads** the modified tables and **analyzes trends** between the two sources using an LLM agent, focusing on differences in trends between daily vs. 3-month average volumes.

> **Note:** The "Volume" column in the Yahoo Finance data represents the current one-day ETF trading volume, while the "Avg Daily Share Volume (3mo)" column from ETFdb is a 3-month average. This distinction is important for interpreting trends and comparing activity between the two sources.

### [`edf_local.py`](edf_local.py)

This script focuses on historical and trend analysis using only ETFdb data (based on the volume of 3-month average). Current code is set to compare the current data with the data of about a week ago.

1. **Fetches** the top 20 most active ETFs from ETFdb with retry logic.
2. **Validates** the table structure and content.
3. **Fetches and validates** the current date and time with retry logic.
4. **Adds** the current date as the first column in the table.
5. **Appends** the modified table to a cumulative CSV file in the `data/` directory.
6. **Filters** the table by specific dates (current and some weeks earlier).
7. **Analyzes and compare** the trends between the two filtered tables using an LLM agent.

## Data Files

- All output CSVs are stored in the `data/` directory.
- The main cumulative file is `data/table_etfdb_output.csv`. All other files include the data of only one day. 

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
4. Move into the project directory and check out the specific version:
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
- To only fetch and append the daily data from ETFdb, comment out the advanced features (historical filtering and trend analysis) in `edf_local.py`.

## Terminal Output of Running `edf_local.py`

[07/05/25 08:39:30] INFO     Processing request of type ListToolsRequest                                 server.py:619
[07/05/25 08:39:32] INFO     Processing request of type CallToolRequest                                  server.py:619
                    INFO     HTTP Request: GET https://etfdb.com/compare/volume/ "HTTP/1.1 200 OK"     _client.py:1740
Table content fetched: Symbol,Name,Avg Daily Share Volume (3mo),AUM
TSLL,Direxion Daily TSLA ...
Source URL: https://etfdb.com/compare/volume/

Table content is valid, so we continue to fetch the current date.
[07/05/25 08:39:45] INFO     Processing request of type ListToolsRequest                                 server.py:619
[07/05/25 08:39:50] INFO     Processing request of type CallToolRequest                                  server.py:619
                    INFO     Processing request of type CallToolRequest                                  server.py:619
                    INFO     HTTP Request: GET https://www.google.com/search?q=current+time+in+chicago _client.py:1740
                             "HTTP/1.1 200 OK"                                                                        
                    INFO     HTTP Request: GET https://www.timeanddate.com/worldclock/usa/chicago      _client.py:1740
                             "HTTP/1.1 200 OK"                                                                        

Current date and time fetched: 2025-07-05 08:39:50
Source URL: https://www.timeanddate.com/worldclock/usa/chicago

Date content's format is valid. 
Start adding this date as the first column in the table...

Modified table content: Date,Symbol,Name,Avg Daily Share Volume (3mo),AUM
2025-07-05 08:39:50,TSLL,Direx...

Successfully appended the modified table to the file 'data/table_etfdb_output.csv.'

Modified table content loaded from file: [['Date', 'Symbol', 'Name', 'Avg Daily Share Volume (3mo)', 'AUM'], ['6/17/25 21:11', 'TSLL', 'Direxion Daily TSLA Bull 2X Shares', '220132203', '6294550']]...

Start filering the table by dates...

Filtered table content (present): [['Date', 'Symbol', 'Name', 'Avg Daily Share Volume (3mo)', 'AUM'], ['2025-07-05 08:39:50', 'TSLL', 'Direxion Daily TSLA Bull 2X Shares', '216441906', '6425910.00'], ['2025-07-05 08:39:50', 'SOXL', 'Direxion Daily Semiconductor Bull 3x Shares', '215086266', '14307300.00']]...

Filtered table content (earlier): [['Date', 'Symbol', 'Name', 'Avg Daily Share Volume (3mo)', 'AUM'], ['6/17/25 21:11', 'TSLL', 'Direxion Daily TSLA Bull 2X Shares', '220132203', '6294550'], ['6/17/25 21:11', 'SOXL', 'Direxion Daily Semiconductor Bull 3x Shares', '209241109', '11519500']]...

Start ETF trend analysis...

ETF Trend Analysis:

**ETF Activity Analysis: June 17, 2025 vs July 5, 2025**

The 3-month average share volume data reveals several key trends in ETF activity between the two dates:

**Market Sentiment & Health:**
- **Increased bearish positioning**: SOXS (semiconductor bear 3x) volume surged 29.8% to 110M shares, moving from 6th to 4th most active, indicating growing pessimism about semiconductor sector
- **Broad market defensive positioning**: SPY volume increased 3.9% to 82.4M shares while maintaining its massive \$636B AUM, suggesting investors seeking safer large-cap exposure
- **Tech sector uncertainty**: QQQ saw modest volume increase of 2.9% but significant AUM growth of 4.9% to \$353B, showing mixed signals in tech allocation

**Risk Appetite Changes:**
- **Reduced leverage appetite**: TQQQ (3x long QQQ) volume declined 3.9% despite AUM increasing 10.0% to \$26.8B, suggesting investors holding positions but reducing new leveraged bets
- **Increased hedging activity**: SQQQ (3x short QQQ) volume remained stable at 114.7M shares, maintaining its position as 3rd most active ETF

**Sector Rotation Patterns:**
- **Semiconductor sector volatility**: SOXL maintained high activity at 215M shares with AUM growing 24.2% to \$14.3B, while its inverse SOXS saw the volume surge mentioned above
- **Financial sector stability**: XLF volume declined slightly (0.8%) but AUM increased 5.6% to \$50.6B, indicating steady institutional accumulation
- **Emerging market interest**: FXI volume decreased 5.5% but maintained \$6.2B AUM, suggesting reduced China exposure

**Notable Developments:**
- **Cryptocurrency ETF momentum**: IBIT volume increased 5.7% with AUM growing 8.0% to \$76.3B, showing continued institutional Bitcoin adoption
- **New leveraged entries**: AMDL (2x AMD) appeared in top 20 with 30.8M shares volume, indicating renewed interest in leveraged semiconductor plays
- **Tesla positioning shifts**: TSLL volume decreased 1.7% while inverse TSLZ remained stable, suggesting consolidation in Tesla-related trades

**Key Takeaway**: The data suggests a market in transition, with increased defensive positioning in semiconductors, steady institutional accumulation in core holdings, and growing interest in cryptocurrency exposure, all while maintaining elevated options for both bullish and bearish leveraged plays.

End of the deterministic story flow.

