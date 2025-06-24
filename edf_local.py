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
    1. The first agent fetch the etfdb table content of a specific URL.
    2. The second agent checks if the table content is valid.
    3. Add a gate to retry if the table content is not valid.
    4. The third agent fetches the current date and time.
    5. The fourth agent checks if the date content's format is valid.
    6. Add a gate to retry if the date content's format is not valid.
    7. The fifth agent modifies the table content and adds the current date as the first column.
    8. Then save or append the modified table content to a CSV file.
    9. The sixth agent filters the table by a specific date and another date that is about a week earlier.
    10. The seventh agent compares the trends in ETF activity based on the two filtered tables.
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

    # 2. Check table content agent
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

    # 3. Fetch current date and time agent
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

    # 4. Check date content agent
    date_checker_agent = Agent(
        name="date_checker_agent",
        instructions="Check if the date content has a valid format 'YYYY-MM-DD HH:mm:ss'.",
        output_type=DateCheckerOutput,
        model=agent_model_openai,
    )

    # 5. Modify table content agent
    modify_table_agent = Agent(
        name="modify_table_agent",
        instructions="Modify the table content in the .CSV file based on the user's instructions. ",
        output_type=ModifyTableContent,
        model=agent_model_openai,
    )

    # 6. Filter table by date agent
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

    # 7. Analyze ETF trends agent
    analyze_etf_trends_agent = Agent(
        name="analyze_etf_trends_agent",
        instructions=(
            "Compare the two tables: 'filtered_rows_present' and 'filtered_rows_earlier'. "
            "Identify trends in ETF activity, focusing on changes in market sentiment and health, risk appetite, "
            "sector rotation, and practical trading insights. "
            "Quantify changes (ONLY SIGNIFICANT ONES) in either volume and AUM as percentages where possible. "
            "If you use a dollar sign, add a backslash before the dollar signs (\$) to escape it. "
            "Summarize your analysis in a list of findings. Explicitly mentioning the dates of both tables and stating that the share volume "
            "represents a 3-month average. Return your summary in the 'summary' field."
        ),
        model=agent_model_anthropic,
        output_type=ETFTrendAnalysisOutput,
    )

    input_prompt_etfdb = (
        "Please fetch the top 20 rows of the most active ETFs from the URL "
        "https://etfdb.com/compare/volume/ as a new table. Return the table in CSV format. "
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
                modify_table_agent,
                f"""Please add a new column with the name “Date” as the first column of the table, 
                and add the current date and time you just found as the value in each row.
                CSV table Content: {table_etfdb_result.final_output.csv_content} 
                Current Date: {fetch_date_result.final_output.date_content}
                """,
            )

            print(f"\nModified table content: {modify_table_etfdb_result.final_output.csv_content[:80]}...")
            modify_csv_content = modify_table_etfdb_result.final_output.csv_content

            # Save or append the modified table content to a CSV file by Checking if the file exists and
            # handle headers appropriately
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

            # # 4. Load the modified table and filter the table by a specific date with retry logic
            # with open("table_etfdb_output.csv", "r") as f:
            #     reader = csv.reader(f)
            #     modified_table_content = list(reader)
            # print(
            #     (f"\nModified table content loaded from file: {modified_table_content[:2]}...\n"
            #      "\nStart filering the table by dates...")
            # )

            # max_retries = 3
            # retry_count = 0
            # while retry_count < max_retries:
            #     try:
            #         target_date = fetch_date_result.final_output.date_content
            #         filtered_table_result = await Runner.run(
            #             filter_by_date_agent,
            #             f"""Please filter the following table content by the target date:
            #                 "table": {modified_table_content}
            #                 "target Date": {target_date}
            #                 """,
            #         )

            #         filtered_rows_present = filtered_table_result.final_output.filtered_rows_present
            #         filtered_rows_earlier = filtered_table_result.final_output.filtered_rows_earlier
            #         print(f"\nFiltered table content (present): {filtered_rows_present[:3]}...")
            #         print(f"\nFiltered table content (earlier): {filtered_rows_earlier[:3]}...")
            #         print("\nStart ETF trend analysis...")
            #         break  # Success, exit the retry loop
            #     except Exception as e:
            #         retry_count += 1
            #         print(f"Error filtering table by date (attempt {retry_count}/3): {e}")
            #         if retry_count == max_retries:
            #             print("Failed to filter table by date after 3 attempts. Stopping here.")
            #             return
            #         print("Retrying table filtering...")
            #         await asyncio.sleep(2)  # Optional: short delay before retry

            # # 5. Analyze ETF trends with retry logic
            # max_retries = 3
            # retry_count = 0
            # while retry_count < max_retries:
            #     try:
            #         trend_analysis_result = await Runner.run(
            #             analyze_etf_trends_agent,
            #             f"""Please analyze the trends in ETF activity based on the following two tables:
            #                 "filtered_rows_present": {filtered_rows_present},
            #                 "filtered_rows_earlier": {filtered_rows_earlier}
            #                 """,
            #         )
            #         print("\nETF Trend Analysis:\n")
            #         print(trend_analysis_result.final_output.summary)
            #         print("\n\nEnd of the deterministic story flow.\n")
            #         break  # Success, exit the retry loop
            #     except Exception as e:
            #         retry_count += 1
            #         print(f"Error analyzing ETF trends (attempt {retry_count}/3): {e}")
            #         if retry_count == max_retries:
            #             print("Failed to analyze ETF trends after 3 attempts. Stopping here.")
            #             return
            #         print("Retrying ETF trend analysis...")
            #         await asyncio.sleep(2)  # Optional: short delay before retry
                    
            print("")

if __name__ == "__main__":
    asyncio.run(main())