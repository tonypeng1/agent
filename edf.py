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

class DateContent(BaseModel):
    csv_content: str
    source_url: str

class TableCheckerOutput(BaseModel):
    is_valid: bool
    contain_expected_data: bool

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

    fetch_date_agent = Agent(
        name="fetch_date_agent",
        instructions="""Fetch the current date and time from the URL 
        http://worldtimeapi.org/api/timezone/America/Chicago, 
        then return it in the format “YYYY-MM-DD HH:mm:ss”. 
        Return both the date content and the source URL.""",
        model=agent_model,
        output_type=DateContent,
        mcp_servers=[web_search_and_fetch_server],
    )

    table_checker_agent = Agent(
        name="table_checker_agent",
        instructions="Check if the table content is valid and contains the expected data.",
        output_type=TableCheckerOutput,
        model=agent_model,
    )

    # story_agent = Agent(
    #     name="story_agent",
    #     instructions="Write a short story based on the given outline.",
    #     output_type=str,
    #     model=agent_model,
    # )

    input_prompt = (
        "Please fetch the top 20 rows of the most active ETFs from the URL "
        "https://finance.yahoo.com/markets/etfs/most-active/ as a new table."
        "Fetch as many columns as possible. "
        )

    # Ensure the entire workflow is a single trace
    async with web_search_and_fetch_server:
        with trace("Deterministic story flow"):
            # 1. Fetch the table content
            table_result = await Runner.run(
                fetch_table_agent,
                input_prompt,
            )
            print(f"Table content fetched: {table_result.final_output.csv_content[:100]}...")
            print(f"Source URL: {table_result.final_output.source_url}")

            csv_content = table_result.final_output.csv_content
            # Optionally save to file
            with open("table_output.csv", "w") as f:
                f.write(csv_content)

            # # 2. Fetch the current 
            # fetch_date_result = await Runner.run(
            #     fetch_date_agent,
            #     "Fetch the current date and time.",
            # )
            # print(f"Current date and time fetched: {fetch_date_result.final_output.csv_content}")
            # print(f"Source URL: {fetch_date_result.final_output.source_url}")

            # # 1. Generate an outline
            # outline_result = await Runner.run(
            #     story_outline_agent,
            #     input_prompt,
            # )
            # print(f"Outline generated: {outline_result.final_output}")

            # 2. Check the table content
            table_checker_result = await Runner.run(
                table_checker_agent,
                f"""Please check the following table content:
                CSV Content: {table_result.final_output.csv_content}
                Source URL: {table_result.final_output.source_url}
                """,
            )
            print(f"Table checker result: {table_checker_result.final_output}")

            # 3. Add a gate to stop if the table content 
            assert isinstance(table_checker_result.final_output, TableCheckerOutput)
            if not table_checker_result.final_output.is_valid:
                print("Table content is not valid, so we stop here.")
                return
            print("Table content is valid, so we continue to check if it contains the expected data.")

            if not table_checker_result.final_output.contain_expected_data:
                print("Table content does not contain the expected data, so we stop here.")
                return
            print("Table content is valid and contains the expected data, so we continue to write the story.")

            # # 4. Write the story
            # story_result = await Runner.run(
            #     story_agent,
            #     outline_result.final_output,
            # )
            # print(f"Story: {story_result.final_output}")


if __name__ == "__main__":
    asyncio.run(main())