import asyncio
from dotenv import load_dotenv
import os
from pydantic import BaseModel

from agents import Agent, Runner, trace
from agents.extensions.models.litellm_model import LitellmModel
from agents.mcp import MCPServerStdio


class TableContent(BaseModel):
    csv_content: str
    source_url: str

class TableCheckerOutput(BaseModel):
    is_valid: bool
    contain_expected_data: bool

class DateContent(BaseModel):
    date_content: str
    source_url: str

class DateCheckerOutput(BaseModel):
    is_valid: bool
    source_url: str

class ModifyTableContent(BaseModel):
    csv_content: str


async def main():
    """
    This example demonstrates a deterministic flow, where each step is performed by an agent.
    1. The first agent fetch the table content of an URL.
    2. We feed the outline into the second agent
    3. The second agent checks if the outline is good quality and if it is a scifi story
    4. If the outline is not good quality or not a scifi story, we stop here
    5. If the outline is good quality and a scifi story, we feed the outline into the third agent
    6. The third agent writes the story
    """

    load_dotenv()  # Load environment variables from .env file

    model = "gpt-4.1-2025-04-14"
    api_key = os.getenv("OPENAI_API_KEY")

    # model = "claude-3-7-sonnet-20250219"
    # api_key = os.getenv("ANTHROPIC_API_KEY")

    agent_model=LitellmModel(model=model, api_key=api_key)

    # Create MCP server using native OpenAI Agents SDK
    web_search_and_fetch_server = MCPServerStdio(
        params={
            "command": "uvx",
            "args": ["duckduckgo-mcp-server"],
        },
        name="fetch"
    )

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
        instructions="Check if the table content is valid and contains the expected data.",
        output_type=TableCheckerOutput,
        model=agent_model,
    )

    fetch_date_agent = Agent(
        name="fetch_date_agent",
        instructions="""Fetch the current date and time. You can use any reliable time API service.
        Some options include:
        - https://timeapi.io/api/Time/current/zone?timeZone=America/Chicago
        - https://worldclockapi.com/api/json/cst/now
        
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

    input_prompt = (
        "Please fetch the top 20 rows of the most active ETFs from the URL "
        "https://finance.yahoo.com/markets/etfs/most-active/ as a new table. "
        "Fetch as many columns as possible. "
        # "Change all the cells with percentages to a decimal format (e.g., 0.56% to 0.0056), "
        # "except for the cells in the first row, which are symbols. "
        # "In the first row, change the percentage symbol to the word 'ratio', and "
        " change the '3 Month Return' to '3 Month Return %', and "
        " YTD Return' to 'YTD Return %'. "
        )

    # Ensure the entire workflow is a single trace
    async with web_search_and_fetch_server:
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
                print("Table content is not valid, so we stop here.")
                return
            print("Table content is valid, so we continue to check if it contains the expected data.")

            if not table_checker_result.final_output.contain_expected_data:
                print("Table content does not contain the expected data, so we stop here.")
                return
            print("Table content is valid and contains the expected data, so we continue to fetch the current date.")

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
                print("Date content's format is not valid, so we stop here.")
                return
            print("Date content's format is valid, so we continue to add this date to the fetched table.")

            # 6. Modify the table content to add the current date
            modify_table_result = await Runner.run(
                modify_table_agent,
                f"""Please add a new column with the name “Date” as the first column of the table, 
                and add the current date and time you just found as the value in each row. 
                Please also delete the last item in the first row, which is '52 Wk Range'.
                CSV table Content: {table_result.final_output.csv_content} 
                Current Date: {fetch_date_result.final_output.date_content}
                """,
            )

            print(f"Modified table content: {modify_table_result.final_output.csv_content[:70]}...")

            modify_csv_content = modify_table_result.final_output.csv_content
            # Optionally save to file
            with open("table_output.csv", "w") as f:
                f.write(modify_csv_content)


if __name__ == "__main__":
    asyncio.run(main())