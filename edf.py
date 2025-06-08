import asyncio
from dotenv import load_dotenv
import os
from pydantic import BaseModel
import csv

from agents import Agent, Runner, trace
from agents.extensions.models.litellm_model import LitellmModel
from agents.mcp import MCPServerStdio
import tiktoken


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

class GoogleSheetsListOutput(BaseModel):
    spreadsheet_name: str
    spreadsheet_id: str
    error: str = None  # Optional error message

class GoogleSheetsAppendOutput(BaseModel):
    success: bool
    error: str = None # Optional error message
    

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

    model = "gpt-4.1-2025-04-14"
    # model = "gpt-4.1-mini"
    # model = "o4-mini"
    api_key = os.getenv("OPENAI_API_KEY")

    # model = "anthropic/claude-3-7-sonnet-20250219"
    # model = "anthropic/claude-3-5-sonnet-20240620"
    # api_key = os.getenv("ANTHROPIC_API_KEY")

    agent_model=LitellmModel(model=model, api_key=api_key)

    # Create MCP servers using native OpenAI Agents SDK
    web_search_and_fetch_server = MCPServerStdio(
        params={
            "command": "uvx",
            "args": ["duckduckgo-mcp-server"],
        },
        name="fetch",
        client_session_timeout_seconds=5
    )

    google_sheets_server = MCPServerStdio(
        params={
            "name": "mcp-google-sheets",
            "key": "McpGoogleSheets",
            "description": "Access Google drive",
            "command": "uvx",
            "args": [
                "mcp-google-sheets"
            ],
            "env": {
                "SERVICE_ACCOUNT_PATH": "/Users/tony3/Documents/endless-science-458714-i5-82adc8d5f14f.json",
                "DRIVE_FOLDER_ID": "18yoPfDe6nkHZDYu6MJl6eqYKh-MyJGbK"
                }
            },
        name="mcp-google-sheets",
        client_session_timeout_seconds=5,
        cache_tools_list=True
    )

    # Define agents
    fetch_table_agent = Agent(
        name="fetch_table_agent",
        instructions="""Fetch the table content of an URL based on the user's input.
        Extract tables from the webpage and format them as CSV. 
        Return both the CSV content and the source URL.""",
        model=agent_model,
        output_type=TableContent,
        mcp_servers=[web_search_and_fetch_server],
    )

    table_checker_agent = Agent(
        name="table_checker_agent",
        instructions=(
            "Check if the table content is valid by ensuring that it includes headers that match "
            "(case-insensitive) 'Symbol', 'Name', 'Price', 'Change', 'Change %', 'Volume', '50 Day Average', "
            "'200 Day Average', '3 Month Return', 'YTD Return', and '52 Wk Change %'. "
            "Also, ensure that the table contains at least 20 data rows (plus header row)."
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
        "YYYY-MM-DD HH:mm:ss". Return both the date content and the source URL.

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

    modify_table_agent = Agent(
        name="modify_table_agent",
        instructions="Modify the table content in the .CSV file based on the user's instructions. ",
        output_type=ModifyTableContent,
        model=agent_model,
    )

    google_sheet_list_agent = Agent(
        name="google_sheet_list_agent",
        instructions="""Find if a Google spreadsheet file is available in the configured Google Drive 
        folder you have access to. If yes, list this file name and its Google spreadsheet ID.""",
        output_type=GoogleSheetsListOutput,
        model=agent_model,
        mcp_servers=[google_sheets_server],
    )

    google_sheet_agent = Agent(
        name="google_sheet_agent",
        # instructions="""Append the given rows to the specified sheet in the given Google Spreadsheet.
        # The input will be a dictionary containing the spreadsheet_id, sheet_name, and rows to append.
        # For example: {"spreadsheet_id": "...", "sheet_name": "...", "rows": "[['2024-07-31', 'Task A Completed'], ['2024-08-01', 'Task B Started']]"}.
        # Parse the dictionary to extract the spreadsheet_id, sheet_name, and rows. Do not include a header row.""",
        instructions="""APPEND new rows to the specified sheet in the given Google Spreadsheet.""",
        model="gpt-4.1-mini",
        mcp_servers=[google_sheets_server],
        output_type=GoogleSheetsAppendOutput,
    )

    input_prompt = (
        "Please fetch the top 20 rows of the most active ETFs from the URL "
        "https://finance.yahoo.com/markets/etfs/most-active/ as a new table. "
        "Do NOT fetch the last item in the headers, which is '52 Wk Range'. "
        )

    # Ensure the entire workflow is a single trace
    async with web_search_and_fetch_server, google_sheets_server:
        with trace("Deterministic story flow"):
            # 1. Fetch the table content
            table_result = await Runner.run(
                fetch_table_agent,
                input_prompt,
            )
            print(f"Table content fetched: {table_result.final_output.csv_content[:70]}...")
            print(f"Source URL: {table_result.final_output.source_url}")

            csv_content = table_result.final_output.csv_content
            # Optionally save to file
            with open("table_output.csv", "w") as f:
                f.write(csv_content)

            # 2. Check the table content
            table_checker_result = await Runner.run(
                table_checker_agent,
                f"""Please check the following table content:
                CSV Content: {table_result.final_output.csv_content}
                Source URL: {table_result.final_output.source_url}
                """,
            )

            # 3. Add a gate to stop if the table content has some issues
            assert isinstance(table_checker_result.final_output, TableCheckerOutput)
            if not table_checker_result.final_output.is_valid:
                print(f"Table content is not valid so we stop here. The reson is: {table_checker_result.final_output.reason}")
                return
            print("Table content is valid, so we continue to fetch the current date.")

            # 4. Fetch the current date and time
            fetch_date_result = await Runner.run(
                fetch_date_agent,
                "Fetch the current date and time.",
            )
            print(f"Current date and time fetched: {fetch_date_result.final_output.date_content}")
            print(f"Source URL: {fetch_date_result.final_output.source_url}")

            # 5. Add a gate to stop if the table content's format is not valid
            date_checker_result = await Runner.run(
                date_checker_agent,
                f"""Please check the following date content:
                Date Content: {fetch_date_result.final_output.date_content}
                Source URL: {fetch_date_result.final_output.source_url}
                """,
            )

            assert isinstance(date_checker_result.final_output, DateCheckerOutput)
            if not date_checker_result.final_output.is_valid:
                print(f"Date content's format is not valid so we stop here. The reason is: {date_checker_result.final_output.reason}")
                return
            print("Date content's format is valid, so we continue to add this date as the first column in the table.")

            # 6. Modify the table content to add the current date
            modify_table_result = await Runner.run(
                modify_table_agent,
                f"""Please add a new column with the name “Date” as the first column of the table, 
                and add the current date and time you just found as the value in each row.
                Please also change the header '3 Month Return' to '3 Month Return %'  
                and 'YTD Return' to 'YTD Return %'.
                CSV table Content: {table_result.final_output.csv_content} 
                Current Date: {fetch_date_result.final_output.date_content}
                """,
            )

            print(f"Modified table content: {modify_table_result.final_output.csv_content[:80]}...")

            modify_csv_content = modify_table_result.final_output.csv_content
            # Optionally save to file
            with open("table_output.csv", "w") as f:
                f.write(modify_csv_content)

            # 7. Check if the Google Spreadsheet file is accessible 
            google_sheets_list = await Runner.run(
                google_sheet_list_agent,
                "Please check if the spreadsheet with the name 'Yahoo ETF' is available.",
            )

            # 8. Add a gate to stop if the Google Spreadsheet file is not accessible
            if getattr(google_sheets_list.final_output, "error", None):
                print(f"Google Sheets access error: {google_sheets_list.final_output.error}. Stop here.")
                return
            else:
                print(f"""The spread sheet file '{google_sheets_list.final_output.spreadsheet_name}' has an ID: {google_sheets_list.final_output.spreadsheet_id}. Continue to append the modified table content.""")
                
            # 9. Append the modified table to Google Sheet
            # Read the CSV content from the file and convert to list of lists
            with open("table_output.csv", "r") as f:
                reader = csv.reader(f)
                rows = list(reader)

            # Convert percentage columns to string with '%' if not already
            percent_headers = [i for i, h in enumerate(rows[0]) if h.strip().endswith('%')]
            for row_idx, row in enumerate(rows):
                for col_idx in percent_headers:
                    if row_idx == 0:
                        continue  # Skip header
                    cell = row[col_idx]
                    # Always force as string with percent sign, prefixed with a single quote
                    if not cell.endswith('%'):
                        try:
                            val = float(cell)
                            row[col_idx] = f"'{val * 100:.2f}%"
                        except Exception:
                            row[col_idx] = f"'{cell}" if not cell.startswith("'") else cell
                    else:
                        # If already percent, still prefix with single quote if not present
                        if not cell.startswith("'"):
                            row[col_idx] = f"'{cell}"

            spreadsheet_id = google_sheets_list.final_output.spreadsheet_id
            sheet_name = "ETF"
            # rows_to_append = [['2024-07-31', 'Task A Completed'], ['2024-08-01', 'Task B Started']]

            input_data = {
                "spreadsheet_id": spreadsheet_id,
                "sheet_name": sheet_name,
                "rows": rows
            }
            google_sheets_result = await Runner.run(
                google_sheet_agent,
                [{"role": "user", "content": str(input_data)}],
            )

            # 10. Add a gate to check if the append operation was successful
            assert isinstance(google_sheets_result.final_output, GoogleSheetsAppendOutput)
            if getattr(google_sheets_result.final_output, "error", None):
                print(f"Failed to append: {google_sheets_result.final_output.error}. Stop here.")
                return

            print("Successfully appended the table to the Google Sheet.")

            # # Separate header and data rows
            # header, *data_rows = rows

            # # Batch size for appending rows
            # batch_size = 1

            # # Append data in batches to avoid token limits
            # for i in range(0, len(data_rows), batch_size):
            #     batch = data_rows[i:i+batch_size]
            #     print(f"Appending batch {i//batch_size + 1}: {len(batch)} rows")
            #     print(f"Batch content: {batch}")
            #     google_sheets_result = await Runner.run(
            #         google_sheet_agent,
            #         f"""Append these rows to the '{sheet_name}' sheet in spreadsheet {spreadsheet_name}: {batch}""",
            #     )
            #     if getattr(google_sheets_result.final_output, "error", None):
            #         print(f"Failed to append batch {i//batch_size + 1}: google_sheets_result.final_output.error} Stop here.")
            #         return

            # print("Successfully appended all batches to the Google Sheet.")


if __name__ == "__main__":
    asyncio.run(main())