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
    1. The first agent fetch the table content of an URL.
    2. The second agent checks if the table content is valid.
    3. Add a gate to stop if the table content is not valid.
    4. The third agent fetches the current date and time.
    5. Add a gate to stop if the date content's format is not valid.
    6. The fourth agent modifies the table content to add the current date as the first column.
    7. The fifth agent checks if a specific Google Spreadsheet file is accessible.
    8. Add a gate to stop if the Google Spreadsheet file is not accessible.
    9. The sixth agent appends the modified table content to the Google Spreadsheet.
    10. Add a gate to check if the append operation was successful.
    """

    load_dotenv()  # Load environment variables from .env file

    # model = "gpt-4.1-2025-04-14"
    model = "gpt-4.1-mini"
    # model = "o4-mini"
    api_key = os.getenv("OPENAI_API_KEY")

    # model_anthropic = "anthropic/claude-3-7-sonnet-20250219"
    model_anthropic = "anthropic/claude-3-5-sonnet-20240620"
    api_key_anthropic = os.getenv("ANTHROPIC_API_KEY")

    agent_model=LitellmModel(model=model, api_key=api_key)
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
    fetch_table_agent = Agent(
        name="fetch_table_agent",
        instructions="""Fetch the table content of an URL based on the user's input.
        Extract tables from the webpage and remove the comma marks if they exist. Then 
        format them as CSV and return both the CSV content and the source URL.""",
        model=agent_model,
        output_type=TableContent,
        mcp_servers=[web_search_and_fetch_server],
    )

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
        model=agent_model,
    )

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
        model=agent_model,
    )

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
        model=agent_model,
        output_type=DateContent,
        mcp_servers=[web_search_and_fetch_server],
    )

    date_checker_agent = Agent(
        name="date_checker_agent",
        instructions="Check if the date content has a valid format 'YYYY-MM-DD HH:mm:ss'.",
        output_type=DateCheckerOutput,  # Currently using TableCheckerOutput
        model=agent_model,
    )

    modify_etfdb_table_agent = Agent(
        name="modify_table_agent",
        instructions="Modify the table content in the .CSV file based on the user's instructions. ",
        output_type=ModifyTableContent,
        model=agent_model,
    )

    filter_by_date_agent = Agent(
        name="filter_by_date_agent",
        instructions=(
            "Given a table in list-of-lists format (first row is header) and a target date string, "
            "filter the table to only include rows where the 'Date' column matches the target date exactly. "
            "If there is no exact match, return the rows with the closest date (by time difference) to the target date. "
            "Return these filtered rows, including the header, as a list of lists and save them in the field 'filtered_rows_present'.\n\n"
            "Additionally, filter the table by another target date that is about a week earlier than the given target date. "
            "If there are no dates at least a week earlier, choose the earliest available date in the table. "
            "Return these filtered rows, including the header, as a list of lists and save them in the field 'filtered_rows_earlier'.\n\n"
            "**IMPORTANT:** Return a valid JSON object. The values for 'filtered_rows_present' and 'filtered_rows_earlier' must be JSON arrays (not strings). Example:\n"
            "{\n"
            '  "filtered_rows_present": [["Date", "Symbol", ...], ["2025-06-20", "TSLL", ...]],\n'
            '  "filtered_rows_earlier": [["Date", "Symbol", ...], ["2025-06-13", "TSLL", ...]]\n'
            "}"
        ),
        model=agent_model_anthropic,
        output_type=FilteredTableOutput,
    )

    analyze_etf_trends_agent = Agent(
        name="analyze_etf_trends_agent",
        instructions=(
            "Compare the two tables: 'filtered_rows_present' and 'filtered_rows_earlier'. "
            "Analyze the trends in ETF activity, such as changes in volume, rankings, or other notable differences. "
            "Summarize your findings in a concise paragraph. Make sure to mention the dates of the two tables in your analysis. "
            "Return the summary in the field 'summary'."
        ),
        model=agent_model_anthropic,
        output_type=ETFTrendAnalysisOutput,
    )


    input_prompt_etfdb = (
        "Please fetch the top 20 rows of the most active ETFs from the URL "
        "https://etfdb.com/compare/volume/ as a new table. Return the table in CSV format. "
        )
    
    input_prompt_yahoo = (
        "Please fetch the top 20 rows of the most active ETFs from the URL "
        "https://finance.yahoo.com/markets/etfs/most-active/ as a new table. "
        "Do NOT fetch the last item in the headers, which is '52 Wk Range'. "
        )

    # Ensure the entire workflow is a single trace
    async with web_search_and_fetch_server:
        with trace("Deterministic story flow"):
            # 1. Fetch and Check the table content with retry logic
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
                
                with open("table_etfdb_output_raw.csv", "w") as f:
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
                    print("Retrying table fetch and check...")
                    continue
                print("\nTable content is valid, so we continue to fetch the current date.")
                break

            # 2. Fetch the current date and time with retry logic
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                fetch_date_result = await Runner.run(
                    fetch_date_agent,
                    "Fetch the current date and time.",
                )
                print(f"\nCurrent date and time fetched: {fetch_date_result.final_output.date_content}")
                print(f"Source URL: {fetch_date_result.final_output.source_url}")

                # 2. Check if the date format is valid
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
                    print("Retrying date fetch and check...")
                    await asyncio.sleep(1)  # Add a short delay between retries
                    continue
                print(("\nDate content's format is valid. \n"
                       "Start adding this date as the first column in the table...")
                )
                break

            # 3. Modify the table content to add the current date
            modify_table_etfdb_result = await Runner.run(
                modify_etfdb_table_agent,
                f"""Please add a new column with the name “Date” as the first column of the table, 
                and add the current date and time you just found as the value in each row.
                CSV table Content: {table_etfdb_result.final_output.csv_content} 
                Current Date: {fetch_date_result.final_output.date_content}
                """,
            )

            # modify_table_result = await Runner.run(
            #     modify_table_agent,
            #     f"""Please add a new column with the name “Date” as the first column of the table, 
            #     and add the current date and time you just found as the value in each row.
            #     Please also change the header '3 Month Return' to '3 Month Return %'  
            #     and 'YTD Return' to 'YTD Return %'.
            #     CSV table Content: {table_yahoo_result.final_output.csv_content} 
            #     Current Date: {fetch_date_result.final_output.date_content}
            #     """,
            # )

            print(f"\nModified table content: {modify_table_etfdb_result.final_output.csv_content[:80]}...")
            modify_csv_content = modify_table_etfdb_result.final_output.csv_content

            # Save or append the modified table content to a CSV file
            # Check if file exists to handle headers appropriately
            file_exists = os.path.isfile("table_etfdb_output.csv")
            with open("table_etfdb_output.csv", "a") as f:
                # If file exists, skip the header line
                if file_exists:
                    # Split content into lines and remove header
                    content_lines = modify_csv_content.split('\n')
                    content_without_header = '\n'.join(content_lines[1:])
                    f.write('\n' + content_without_header)
                else:
                    f.write(modify_csv_content)

            print("\nSuccessfully appended the modified table to the file 'table_etfdb_output.csv.'")

            # 4. Load the modified table content from the CSV file and perform ETF trend analysis
            # Load the modified table content from the CSV file
            with open("table_etfdb_output.csv", "r") as f:
                reader = csv.reader(f)
                modified_table_content = list(reader)
            print(
                (f"Modified table content loaded from file: {modified_table_content[:2]}...\n"
                 "\nStart filering the table by dates...")
            )

            # Filter the table by a specific date
            target_date = fetch_date_result.final_output.date_content
            filtered_table_result = await Runner.run(
                filter_by_date_agent,
                f"""Please filter the following table content by the target date:
                    "table": {modified_table_content}
                    "target Date": {target_date}
                    """,
            )

            filtered_rows_present = filtered_table_result.final_output.filtered_rows_present
            filtered_rows_earlier = filtered_table_result.final_output.filtered_rows_earlier
            print(f"\nFiltered table content (present): {filtered_rows_present[:3]}...")
            print(f"\nFiltered table content (earlier): {filtered_rows_earlier[:3]}...")
            print("\nStart ETF trend analysis...")

            # 5. Analyze ETF trends
            trend_analysis_result = await Runner.run(
                analyze_etf_trends_agent,
                f"""Please analyze the trends in ETF activity based on the following two tables:
                    "filtered_rows_present": {filtered_rows_present},
                    "filtered_rows_earlier": {filtered_rows_earlier}
                    """,
            )
            print("\nETF Trend Analysis:\n")
            print(trend_analysis_result.final_output.summary)
            print("\n\nEnd of the deterministic story flow.\n")


if __name__ == "__main__":
    asyncio.run(main())