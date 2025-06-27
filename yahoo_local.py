import asyncio
from dotenv import load_dotenv
import os
from pydantic import BaseModel
import csv

from agents import Agent, Runner, trace
from agents.extensions.models.litellm_model import LitellmModel
from agents.mcp import MCPServerStdio
# import tiktoken


class TableContent(BaseModel):
    csv_content: str
    source_url: str

class TableCheckerOutput(BaseModel):
    is_valid: bool
    reason: str = None  # Optional reason for invalidity

class DateContent(BaseModel):
    date_content: str
    source_url: str

class DateCheckerOutput(BaseModel):
    is_valid: bool
    source_url: str
    reason: str = None  # Optional reason for invalidity

class ModifyTableContent(BaseModel):
    csv_content: str

class FilteredTableOutput(BaseModel):
    filtered_rows_present: list[list[str]]
    filtered_rows_earlier: list[list[str]]

class ETFTrendAnalysisOutput(BaseModel):
    summary: str


async def main():
    """
    This example demonstrates a deterministic flow, where each step is performed by an agent.
    1. The first agent fetch the Yahoo table content of a specific URL.
    2. The second agent checks if the Yahoo table content is valid.
    3. Add a gate to retry if the Yahoo table content is not valid.
    4. The first agent fetches another etfdb table content of another specific URL.
    5. The third agent checks if the etfdb table content is valid.
    6. Add a gate to retry if the etfdb table content is not valid.
    7. The fourth agent fetches the current date and time.
    8. The fifth agent checks if the date content's format is valid.
    9. Add a gate to retry if the date content's format is not valid.
    10. The sixth agent modifies both table contents and adds the current date as the first column.
    11. Then save the modified table contents to CSV files.
    12. The seventh agent compares the Yahoo table and the etfdb table.
    """

    load_dotenv()  # Load environment variables from .env file

    # model = "gpt-4.1-2025-04-14"
    model_openai = "gpt-4.1-mini"
    # model = "o4-mini"
    api_key_openai = os.getenv("OPENAI_API_KEY")
    agent_model_openai=LitellmModel(model=model_openai, api_key=api_key_openai)

    # model_anthropic = "anthropic/claude-3-7-sonnet-20250219"
    # model_anthropic = "anthropic/claude-3-5-sonnet-20240620"
    model_anthropic = "anthropic/claude-sonnet-4-20250514" 
    api_key_anthropic = os.getenv("ANTHROPIC_API_KEY")
    agent_model_anthropic=LitellmModel(model=model_anthropic, api_key=api_key_anthropic)

    # Create MCP servers using native OpenAI Agents SDK
    web_search_and_fetch_server = MCPServerStdio(
        params={
            "command": "uvx",
            "args": ["duckduckgo-mcp-server"],
        },
        name="fetch",
        client_session_timeout_seconds=5
    )

    # Define agents
    # 1. Fetch table content agent
    fetch_table_agent = Agent(
        name="fetch_table_agent",
        instructions="""Fetch the table content of an URL based on the user's input.
        Extract tables from the webpage and remove the comma marks if they exist. Then 
        format them as CSV and return both the CSV content and the source URL.""",
        model=agent_model_openai,
        output_type=TableContent,
        mcp_servers=[web_search_and_fetch_server],
    )

    # 2. Check table Yahoo content agent
    table_yahoo_checker_agent = Agent(
        name="table_yahoo_checker_agent",
        instructions=(
            "Perform the following tasks: \n"
            "- Check if the table content is valid by ensuring that it includes headers that match "
            "(case-insensitive) 'Symbol', 'Name', 'Price', 'Change', 'Change %', 'Volume', '50 Day Average', "
            "'200 Day Average', '3 Month Return', 'YTD Return', and '52 Wk Change %'. \n"
            "- Also, ensure that the table contains 20 data rows (plus header row). \n"
            "- Finally, Check if the number of items in the SECOND row of the table is the same as that of the header row."
        ),
        output_type=TableCheckerOutput,
        model=agent_model_openai,
    )

    # 3. Check table etfdb content agent
    table_etfdb_checker_agent = Agent(
        name="table_etfdb_checker_agent",
        instructions=(
            "Perform the following tasks: \n"
            "- Check if the table content is valid by ensuring that it includes headers that match "
            "(case-insensitive) 'Symbol', 'Name', 'Avg Daily Share Volume (3mo)', and 'AUM'. \n"
            "- Also, ensure that the table contains 20 data rows (plus header row). \n"
            "- Finally, Check if the number of items in the SECOND row of the table is the same as that "
            "of the header row."
        ),
        output_type=TableCheckerOutput,
        model=agent_model_openai,
    )    

    # 4. Fetch current date and time agent
    fetch_date_agent = Agent(
        name="fetch_date_agent",
        instructions="""Fetch the current date and time. You can use any reliable time API service.
        Some options include:
        - https://www.timeanddate.com/worldclock/usa/chicago
        - https://www.google.com/search?q=current+time+in+chicago
        Try each URL until you get a successful response. Return the date and time in the format 
        "YYYY-MM-DD HH:mm:ss". Try to convert the date to the correct format if necessary. 
        Return both the date content and the source URL.

        If all API calls fail, use the local system time as a fallback.""",
        model=agent_model_openai,
        output_type=DateContent,
        mcp_servers=[web_search_and_fetch_server],
    )

    # 5. Check date content agent
    date_checker_agent = Agent(
        name="date_checker_agent",
        instructions="Check if the date content has a valid format 'YYYY-MM-DD HH:mm:ss'.",
        output_type=DateCheckerOutput,
        model=agent_model_openai,
    )

    # 6. Modify table content agent
    modify_table_agent = Agent(
        name="modify_table_agent",
        instructions="Modify the table content in the .CSV file based on the user's instructions. ",
        output_type=ModifyTableContent,
        model=agent_model_openai,
    )

    # 7. Analyze ETF trends agent
    analyze_etf_trends_agent = Agent(
        name="analyze_etf_trends_agent",
        instructions=(
            "Compare the two tables: 'table_yahoo_content' and 'table_etfdb_content'. "
            "The first table contains the most active ETFs by daily trading volume from Yahoo Finance, and "
            "the second table contains the most active ETFs by average daily share volume over the last 3 months "
            "from ETFdb. \n"
            "Identify trends in ETF activity, focusing on changes in market sentiment and health, risk appetite, "
            "sector rotation, and practical trading insights. "
            "Focus on the fact that the volume in the Yahoo table is for one day, while that in the etfdb table is the average "
            "for the last 3 months. \n"
            "Summarize your analysis in a list of findings. Explicitly mentioning the current date and the two tables you are comparing. "
            "Return your summary in the 'summary' field."
        ),
        model=agent_model_anthropic,
        output_type=ETFTrendAnalysisOutput,
    )

    input_prompt_yahoo = (
        "Please fetch the top 20 rows of the most active ETFs from the URL "
        "https://finance.yahoo.com/markets/etfs/most-active/ as a new table. "
        "Do NOT fetch the last item in the headers, which is '52 Wk Range'. "
        )
    
    input_prompt_etfdb = (
        "Please fetch the top 20 rows of the most active ETFs from the URL "
        "https://etfdb.com/compare/volume/ as a new table. Return the table in CSV format. "
        )

    # Ensure the data directory exists
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)

    # Define file paths in the data directory
    yahoo_raw_csv_path = os.path.join(data_dir, "table_yahoo_output_raw.csv")
    yahoo_output_csv_path = os.path.join(data_dir, "table_yahoo_output.csv")
    etfdb_raw_csv_path = os.path.join(data_dir, "table_etfdb_output_raw.csv")
    etfdb_one_day_csv_path = os.path.join(data_dir, "table_etfdb_one_day.csv")

    # Ensure the entire workflow is a single trace
    async with web_search_and_fetch_server:
        with trace("Deterministic story flow"):
            # 1. Fetch and Check the table Yahoo content with retry logic
            max_retries = 3
            retry_count = 0
            while retry_count < max_retries:
                # Fetch the table content each time
                table_yahoo_result = await Runner.run(
                    fetch_table_agent,
                    input_prompt_yahoo,
                )
                print(f"Table content fetched: {table_yahoo_result.final_output.csv_content[:70]}...")
                print(f"Source URL: {table_yahoo_result.final_output.source_url}")

                csv_content = table_yahoo_result.final_output.csv_content

                with open(yahoo_raw_csv_path, "w") as f:
                    f.write(csv_content)

                table_yahoo_checker_result = await Runner.run(
                    table_yahoo_checker_agent,
                    f"""Please check the following table content:
                    CSV Content: {table_yahoo_result.final_output.csv_content}
                    Source URL: {table_yahoo_result.final_output.source_url}
                    """,
                )

                # Add a gate to stop if the table content has some issues
                assert isinstance(table_yahoo_checker_result.final_output, TableCheckerOutput)
                if not table_yahoo_checker_result.final_output.is_valid:
                    print(f"Table content is not valid (attempt {retry_count+1}/3). "
                          f"The reason is: {table_yahoo_checker_result.final_output.reason}")
                    retry_count += 1
                    if retry_count == max_retries:
                        print("Table content is not valid after 3 attempts. Stopping here.")
                        return
                    print("\nRetrying table fetch and check...")
                    continue
                print("\nTable content is valid, so we continue to fetch the etfdb table...")
                break

            # 2. Fetch and Check the etfdb table content with retry logic
            max_retries = 3
            retry_count = 0
            while retry_count < max_retries:
                # Fetch the table content each time
                table_etfdb_result = await Runner.run(
                    fetch_table_agent,
                    input_prompt_etfdb,
                )
                print(f"Table content fetched: {table_etfdb_result.final_output.csv_content[:70]}...")
                print(f"Source URL: {table_etfdb_result.final_output.source_url}")

                csv_content = table_etfdb_result.final_output.csv_content

                with open(etfdb_raw_csv_path, "w") as f:
                    f.write(csv_content)

                table_etfdb_checker_result = await Runner.run(
                    table_etfdb_checker_agent,
                    f"""Please check the following table content:
                    CSV Content: {table_etfdb_result.final_output.csv_content}
                    Source URL: {table_etfdb_result.final_output.source_url}
                    """,
                )

                # Add a gate to stop if the table content has some issues
                assert isinstance(table_etfdb_checker_result.final_output, TableCheckerOutput)
                if not table_etfdb_checker_result.final_output.is_valid:
                    print(f"Table content is not valid (attempt {retry_count+1}/3). "
                          f"The reason is: {table_etfdb_checker_result.final_output.reason}")
                    retry_count += 1
                    if retry_count == max_retries:
                        print("Table content is not valid after 3 attempts. Stopping here.")
                        return
                    print("\nRetrying table fetch and check...")
                    continue
                print("\nTable content is valid, so we continue to fetch the current date.")
                break

            # 3. Fetch the current date and time with retry logic
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                fetch_date_result = await Runner.run(
                    fetch_date_agent,
                    "Fetch the current date and time.",
                )
                print(f"\nCurrent date and time fetched: {fetch_date_result.final_output.date_content}")
                print(f"Source URL: {fetch_date_result.final_output.source_url}")

                # Check if the date format is valid
                date_checker_result = await Runner.run(
                    date_checker_agent,
                    f"""Please check the following date content:
                    Date Content: {fetch_date_result.final_output.date_content}
                    Source URL: {fetch_date_result.final_output.source_url}
                    """,
                )

                assert isinstance(date_checker_result.final_output, DateCheckerOutput)
                if not date_checker_result.final_output.is_valid:
                    print(f"Date format is not valid (attempt {retry_count+1}/3). "
                          f"The reason is: {date_checker_result.final_output.reason}")
                    retry_count += 1
                    if retry_count == max_retries:
                        print("Date format is not valid after 3 attempts. Stopping here.")
                        return
                    print("\nRetrying date fetch and check...")
                    await asyncio.sleep(1)  # Add a short delay between retries
                    continue
                print(("\nDate content format is valid. \n"
                       "Start adding this date as the first column in the Yahoo table...")
                )
                break

            # 4. Modify the table Yahoo content to add the current date and save it to a CSV file
            modify_table_yahoo_result = await Runner.run(
                modify_table_agent,
                f"""Please add a new column with the name “Date” as the first column of the table, 
                and add the current date and time you just found as the value in each row.
                Please also change the header '3 Month Return' to '3 Month Return %'  
                and 'YTD Return' to 'YTD Return %'.
                CSV table Content: {table_yahoo_result.final_output.csv_content} 
                Current Date: {fetch_date_result.final_output.date_content}
                """,
            )

            print(f"\nModified table content: {modify_table_yahoo_result.final_output.csv_content[:80]}...")
            modify_csv_content = modify_table_yahoo_result.final_output.csv_content

            # Save or replace the modified table content to a CSV file
            with open(yahoo_output_csv_path, "w") as f:
                f.write(modify_csv_content)

            print(("\nSuccessfully saved the modified table to the file 'table_yahoo_output.csv.' "
                    "\nStart adding the current date as the first column in the etfdb table..."))

            # 5. Modify the table etfdb content to add the current date and save it to a CSV file
            modify_table_etfdb_result = await Runner.run(
                modify_table_agent,
                f"""Please add a new column with the name “Date” as the first column of the table, 
                and add the current date and time you just found as the value in each row.
                CSV table Content: {table_etfdb_result.final_output.csv_content} 
                Current Date: {fetch_date_result.final_output.date_content}
                """,
            )

            print(f"\nModified table content: {modify_table_etfdb_result.final_output.csv_content[:80]}...")
            modify_csv_content = modify_table_etfdb_result.final_output.csv_content

            # Save or replace the modified table content to a CSV file
            with open(etfdb_one_day_csv_path, "w") as f:
                f.write(modify_csv_content)

            print(("\nSuccessfully saved the modified table to the file 'table_etfdb_one_day.csv.'"
                    "\nStart comparing the Yahoo table and the etfdb table......"))

            # 6. Load the modified table Yahoo and the modified table etfdb content from the files
            with open(yahoo_output_csv_path, "r") as f:
                reader = csv.reader(f)
                table_yahoo_content = list(reader)

            with open(etfdb_one_day_csv_path, "r") as f:
                reader = csv.reader(f)
                table_etfdb_content = list(reader)

            # 7. Analyze ETF trends with retry logic
            max_retries = 3
            retry_count = 0
            while retry_count < max_retries:
                try:
                    trend_analysis_result = await Runner.run(
                        analyze_etf_trends_agent,
                        f"""Please analyze the trends in ETF activity based on the following two tables:
                            "table_yahoo_content": {table_yahoo_content},
                            "table_etfdb_content": {table_etfdb_content}
                            """,
                    )
                    print("\nETF Trend Analysis:\n")
                    print(trend_analysis_result.final_output.summary)
                    print("\n\nEnd of the deterministic story flow.\n")
                    break  # Success, exit the retry loop
                except Exception as e:
                    retry_count += 1
                    print(f"Error analyzing ETF trends (attempt {retry_count}/3): {e}")
                    if retry_count == max_retries:
                        print("Failed to analyze ETF trends after 3 attempts. Stopping here.")
                        return
                    print("\nRetrying ETF trend analysis...")
                    await asyncio.sleep(2)  # Optional: short delay before retry
            
            print("")

if __name__ == "__main__":
    asyncio.run(main())