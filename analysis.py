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

# class TableCheckerOutput(BaseModel):
#     is_valid: bool
#     reason: str = None  # Optional reason for invalidity

class DateContent(BaseModel):
    date_content: str
    source_url: str

class DateCheckerOutput(BaseModel):
    is_valid: bool
    source_url: str
    reason: str = None  # Optional reason for invalidity

# class ModifyTableContent(BaseModel):
#     csv_content: str

class GoogleSheetsListOutput(BaseModel):
    spreadsheet_name: str
    spreadsheet_id: str
    column_data: list[str]  # Specify the type of items in the list
    # first_empty_row: int  # Specify the type of items in the list
    error: str = None  # Optional error message

class GoogleSheetsGetOutput(BaseModel):
    # csv_content_1: str
    # csv_content_2: str
    # csv_content_3: str
    # csv_content_4: str
    # csv_content_5: str
    csv_content: str  # Combined CSV content
    # cell_content: str  # data from the specified cell
    cells_content: list[str]  # data from the specified cell
    error: str = None  # Optional error message
    

def is_in_correct_group(n):
    if n == 1:
        return True
    if n < 22:
        return False
    return (n - 22) % 20 == 0


async def main():
    """
    This example demonstrates a deterministic flow, where each step is performed by an agent.
    1. The first agent fetch the table content of an URL.

    """

    load_dotenv()  # Load environment variables from .env file

    # model = "gpt-4.1-2025-04-14"
    model = "gpt-4.1-mini"
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
        cache_tools_list=False
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

    google_sheet_list_agent = Agent(
        name="google_sheet_list_agent",
        instructions=(
            "Perform the following tasks: \n"
            "- Find if a Google spreadsheet file is available in the configured Google Drive you have access to. \n"
            "- If yes, return its name and spreadsheet ID. \n"
            "- Also, return the data from a specific column of the sheet per the user's instruction. \n" 
            " Do NOT SKIP any row, return all numeric and string values in the column in their original sequence."
        ),
        output_type=GoogleSheetsListOutput,
        model=agent_model,
        mcp_servers=[google_sheets_server],
    )

    google_sheet_get_agent = Agent(
        name="google_sheet_agent",
        instructions=(
        " Your tasks are as follows: \n"
        "- Get the given range in the given Google Spreadsheet and sheet based on the user's input, "
        "and return the content in CSV format. Do NOT SKIP any row, return all numeric and string "
        "values in the range in their original sequence. \n"
        "- Get the data values from the cells specified by the user, and return the values. "
        # "If a cell is empty, return an empty string. \n"
        # "Use the following input fields:\n"
        # "- 'spreadsheet_id': the ID of the target spreadsheet \n"
        # "- 'sheet_name': the name of the target sheet\n"
        # "- 'cell_': the range of cells to download, e.g. 'A1:L100' \n"
        # "- 'filter_column': the header number of the column to be filtered \n"
        # "- 'filter_word': the word to filter in the filter column. \n"
        ),
        model=agent_model,
        mcp_servers=[google_sheets_server],
        output_type=GoogleSheetsGetOutput,
    )

    # Ensure the entire workflow is a single trace
    async with web_search_and_fetch_server, google_sheets_server:
        with trace("Deterministic story flow"):

            # 1. Fetch the current date and time with retry logic
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                fetch_date_result = await Runner.run(
                    fetch_date_agent,
                    "Fetch the current date and time.",
                )
                print(f"Current date and time fetched: {fetch_date_result.final_output.date_content}")
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
                if date_checker_result.final_output.is_valid:
                    print("Date content's format is valid, so we continue to check the Google Spreadsheet.")
                    break
                
                retry_count += 1
                print(f"Date format is not valid (Attempt {retry_count}/{max_retries}). Reason: {date_checker_result.final_output.reason}")
                await asyncio.sleep(1)  # Add a short delay between retries
            
            if retry_count == max_retries:
                print("Maximum retries reached. Stopping execution.")
                return

            # 2. Check if the Google Spreadsheet file is accessible and the first empty row is in a possible value group
            file_name = "ETF volume"  # The name of the Google Spreadsheet file to check
            sheet_name = "Top ETFs by Trading Volume"  # The name of the sheet to check
            column_name = "D"  # The column to check for non-empty values

            # file_name = "Yahoo ETF"  # The name of the Google Spreadsheet file to check
            # sheet_name = "ETF"  # The name of the sheet to check
            # column_name = "D"  # The column to check for non-empty values

            batch_size = 50
            starting_row = 1  # The starting row to check for non-empty values
            ending_row = batch_size  # The ending row to check for non-empty values
            total_row = 0  # Initialize total_row to 0
            all_column_data = []  # Store all column data

            max_retries = 3
            retry_count = 0
            
            while True:  # Changed to infinite loop, we'll break when needed
                google_sheets_list = await Runner.run(
                    google_sheet_list_agent,
                    (
                        f"Please check if the spreadsheet with the name '{file_name}' is available. If yes, check the sheet "
                        f"'{sheet_name}' in the spreadsheet and return the spreadsheet name, ID, the return the data with the range starting at column "
                        f"{column_name} and row {starting_row} and ending at column {column_name} and row {ending_row} \n"
                        "Do NOT SKIP any row, return all numeric and string values in the range in their original sequence. "
                    )
                )

                if getattr(google_sheets_list.final_output, "error", None) or len(google_sheets_list.final_output.column_data) > batch_size:
                    print(f"Google Sheets access error: {google_sheets_list.final_output.error}. Retrying...")
                    retry_count += 1
                    if retry_count >= max_retries:
                        print("Maximum retries reached. Stopping.")
                        break
                    await asyncio.sleep(1)  # Add 1 second pause before retry
                    continue

                current_batch_size = len(google_sheets_list.final_output.column_data)
                all_column_data.extend(google_sheets_list.final_output.column_data)
                total_row += current_batch_size
                
                print(f"Current batch size: {current_batch_size}")
                print(f"Total rows processed: {total_row}")

                if current_batch_size < batch_size:  # If we got less than batch_size rows, we've reached the end
                    print("Reached end of data")
                    break

                # Prepare for next batch
                starting_row += batch_size
                ending_row += batch_size
                await asyncio.sleep(1)  # Add 1 second pause between successful iterations

            print(f"Final total rows processed: {total_row}")
            print(f"Total data points collected: {len(all_column_data)}")

            # 3. Download the table content from the Google Spreadsheet
            spreadsheet_id = google_sheets_list.final_output.spreadsheet_id
            sheet_name = "Top ETFs by Trading Volume"  # The name of the sheet to check

            starting_column = "F"  # The starting column to check for non-empty values
            ending_column = "I"  # The ending column to check for non-empty values
            starting_row = total_row - 19  # The starting row to check for non-empty values
            ending_row = total_row  # The ending row to check for non-empty values

            filter_column = "Date"  # Column to filter by
            filter_word = fetch_date_result.final_output.date_content[:10]  # The word to filter by

            google_sheets_result = await Runner.run(
                google_sheet_get_agent,
                (
                f"Please return the data in the range starting at column {starting_column} and row "
                f"{starting_row} and ending at column {ending_column} and row {ending_row} in the "
                f"spreadsheet with the ID '{spreadsheet_id}' and the sheet with the name '{sheet_name}'. \n"
                "Do NOT SKIP any row and any column, return all numeric and string values in the range in their "
                "original sequence. "
                f"Also, get the contents from the the cells in column A and starting at row {starting_row} and "
                f"ending at row {ending_row} and return the values. "
                # f"Filter the rows by the '{input_data['filter_column']}' column where the value is ")
                )
            )

            # 9. Add a gate to check if the append operation was successful
            assert isinstance(google_sheets_result.final_output, GoogleSheetsGetOutput)
            if getattr(google_sheets_result.final_output, "error", None):
                print(f"Failed to append: {google_sheets_result.final_output.error} Stop here.")
                return

            print("Successfully appended the table to the Google Sheet.")



            # # 6. Append the modified table to Google Sheet
            # # Read the CSV content from the file and convert to list of lists
            # with open("table_output.csv", "r") as f:
            #     reader = csv.reader(f)
            #     rows = list(reader)



if __name__ == "__main__":
    asyncio.run(main())