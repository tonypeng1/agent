import asyncio
from dotenv import load_dotenv
import os
from pydantic import BaseModel

from agents import Agent, Runner, trace
from agents.extensions.models.litellm_model import LitellmModel


class OutlineCheckerOutput(BaseModel):
    good_quality: bool
    is_scifi: bool


async def main():
    input_prompt = ("A story about life of a new immigrant in a big city, "
                    "who is trying to find a job and make friends. "
                    "The story should be set in a futuristic world, ")

    # Ensure the entire workflow is a single trace
    with trace("Deterministic story flow"):
        # 1. Generate an outline
        outline_result = await Runner.run(
            story_outline_agent,
            input_prompt,
        )
        print(f"Outline generated: {outline_result.final_output}")

        # 2. Check the outline
        outline_checker_result = await Runner.run(
            outline_checker_agent,
            outline_result.final_output,
        )
        print(f"Outline checker result: {outline_checker_result.final_output}")

        # 3. Add a gate to stop if the outline is not good quality or not a scifi story
        assert isinstance(outline_checker_result.final_output, OutlineCheckerOutput)
        if not outline_checker_result.final_output.good_quality:
            print("Outline is not good quality, so we stop here.")
            return
        print("Outline is good quality, so we continue to check if it is a scifi story.")

        if not outline_checker_result.final_output.is_scifi:
            print("Outline is not a scifi story, so we stop here.")
            return

        print("Outline is good quality and a scifi story, so we continue to write the story.")

        # 4. Write the story
        story_result = await Runner.run(
            story_agent,
            outline_result.final_output,
        )
        print(f"Story: {story_result.final_output}")


if __name__ == "__main__":

    """
    This example demonstrates a deterministic flow, where each step is performed by an agent.
    1. The first agent generates a story outline
    2. We feed the outline into the second agent
    3. The second agent checks if the outline is good quality and if it is a scifi story
    4. If the outline is not good quality or not a scifi story, we stop here
    5. If the outline is good quality and a scifi story, we feed the outline into the third agent
    6. The third agent writes the story
    """

    load_dotenv()  # Load environment variables from .env file

    # model = "gpt-4.1"
    # api_key = os.getenv("OPENAI_API_KEY")

    model = "claude-3-7-sonnet-20250219"
    api_key = os.getenv("ANTHROPIC_API_KEY")

    agent_model=LitellmModel(model=model, api_key=api_key)

    story_outline_agent = Agent(
        name="story_outline_agent",
        instructions="Generate a very short story outline based on the user's input.",
        model=agent_model,
    )

    outline_checker_agent = Agent(
        name="outline_checker_agent",
        instructions="Read the given story outline, and judge the quality. Also, determine if it is a scifi story.",
        output_type=OutlineCheckerOutput,
        model=agent_model,
    )

    story_agent = Agent(
        name="story_agent",
        instructions="Write a short story based on the given outline.",
        output_type=str,
        model=agent_model,
    )

    asyncio.run(main())