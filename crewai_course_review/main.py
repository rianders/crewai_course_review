# -*- coding: utf-8 -*-
"""
CrewAI Testing

This script is used for testing CrewAI functionalities, specifically focusing on reviewing a Github project.
"""

import os
import requests
import re
import ast
from google.colab import userdata
from crewai import Agent, Task, Crew, Process
from langchain.tools import tool

# Environment variables setup
os.environ["OPENAI_API_KEY"] = userdata.get('OPENAI_API_KEY')
GITHUB_ACCESS_TOKEN = userdata.get('GITHUB_ACCESS_TOKEN')


def fetch_github_content(repo_url, access_token=None, destination_directory="/content/github_files"):
    """
    Fetch the content of a GitHub repository.
    
    Args:
        repo_url (str): URL of the GitHub repository.
        access_token (str): Personal Access Token for GitHub API.
        destination_directory (str): Directory to save the fetched files.
    
    Returns:
        list: List of files with their content.
    """
    # Extract owner and repo name from URL
    owner, repo = repo_url.split("/")[-2], repo_url.split("/")[-1]

    # GitHub API endpoint and headers
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if access_token:
        headers["Authorization"] = f"token {access_token}"

    response = requests.get(api_url, headers=headers)
    response.raise_for_status()
    repo_contents = response.json()

    # Process repository contents
    files_content = []
    for item in repo_contents:
        if item['type'] == 'file':
            file_response = requests.get(item['download_url'], headers=headers)
            file_response.raise_for_status()
            files_content.append({
                "name": item['name'],
                "path": item['path'],
                "content": file_response.text
            })

    # Save files to the destination directory
    os.makedirs(destination_directory, exist_ok=True)
    for item in files_content:
        with open(os.path.join(destination_directory, item["name"]), "w") as file:
            file.write(item["content"])

    return files_content


def parse_documentation(doc_content):
    """
    Parse documentation content.

    Args:
        doc_content (str): Documentation file content.
    
    Returns:
        dict: Parsed content as a dictionary.
    """
    parsed_content = {}
    current_header = None
    current_text = []

    for line in doc_content.split("\n"):
        if re.match(r"^#+\s", line):
            if current_header:
                parsed_content[current_header] = "\n".join(current_text)
            current_header = line.strip("# ").strip()
            current_text = []
        else:
            current_text.append(line)

    if current_header:
        parsed_content[current_header] = "\n".join(current_text)

    return parsed_content


def parse_code(code_content):
    """
    Parse code content.

    Args:
        code_content (str): Code file content.
    
    Returns:
        dict: Parsed content as a dictionary.
    """
    parsed_code = {}
    try:
        tree = ast.parse(code_content)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                name = node.name
                docstring = ast.get_docstring(node)
                parsed_code[name] = {
                    "type": "Function" if isinstance(node, ast.FunctionDef) else "Class",
                    "docstring": docstring
                }
    except SyntaxError as e:
        print(f"Syntax error in code: {e}")

    return parsed_code


# Define custom tools for CrewAI agents
@tool
def markdown_formatter(response: str) -> str:
"""
Format a given response string into Markdown format.
Args:
    response (str): Response string to format.

Returns:
    str: Markdown-formatted string.
"""
return f"**Answer:** {response}"

@tool
def markdown_loader(file_path: str) -> str:
"""
Load the content of a Markdown file.

less
Args:
    file_path (str): Path to the Markdown file.

Returns:
    str: Content of the Markdown file.
"""
try:
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()
except Exception as e:
    return f"Error loading file: {str(e)}"

def ingest_into_crewai(parsed_data, content_location, debug=True):
"""
Ingest the parsed data into CrewAI and kickoff the crew's work.

less
Args:
    parsed_data (list): Parsed data to be ingested.
    content_location (str): Location of the content.
    debug (bool): Flag to enable verbose output.
"""
try:
    documentation_analyst = Agent(
        role='Documentation Analyst',
        goal='Analyze project documentation for quality and completeness.',
        backstory='Experienced in analyzing technical project documentation.',
        tools=[markdown_loader],
        verbose=debug
    )

    code_reviewer = Agent(
        role='Code Reviewer',
        goal='Review Python code for style, efficiency, and best practices.',
        backstory='Skilled in Python code review, focusing on style and best practices.',
        verbose=debug
    )

    inquiry_agent = Agent(
        role='Inquiry and Suggestion Analyst',
        goal='Generate questions and suggestions based on processed information',
        backstory='Skilled in synthesizing information and identifying key improvement areas.',
        verbose=debug
    )

    response_agent = Agent(
        role='Markdown Response Specialist',
        goal='Provide Markdown-formatted answers to questions',
        tools=[markdown_formatter],
        backstory='Expert in technical writing and content curation for Markdown formatting.',
        verbose=debug
    )

    # Create tasks for each file
    tasks = []
    for item in parsed_data:
        if item["type"] == "documentation":
            tasks.append(Task(description=f'Analyze {item["name"]}.', agent=documentation_analyst))
            tasks.append(Task(description=f'Formulate questions and suggestions for {item["name"]}.', agent=inquiry_agent))
            tasks.append(Task(description=f'Provide Markdown responses for {item["name"]}.', agent=response_agent))
        elif item["type"] == "code":
            tasks.append(Task(description=f'Review code in {item["name"]}.', agent=code_reviewer))
            tasks.append(Task(description=f'Formulate questions and suggestions for {item["name"]}.', agent=inquiry_agent))
            tasks.append(Task(description=f'Provide Markdown responses for {item["name"]}.', agent=response_agent))

    crew = Crew(agents=[documentation_analyst, code_reviewer, inquiry_agent, response_agent], tasks=tasks, process=Process.sequential, verbose=True)

    # Execute CrewAI process
    result = crew.kickoff()
    print("CrewAI tasks completed successfully.")
    return result
except Exception as e:
    print(f"Error during CrewAI process: {e}")
    return None

def main():
repo_url = "https://github.com/rianders/2024SP-SocialEngagementUsingXR"
access_token = GITHUB_ACCESS_TOKEN

try:
    content_location = "/content/github_files/"
    contents = fetch_github_content(repo_url, access_token, content_location)
    parsed_data = []

    for content in contents:
        if content['name'].endswith('.md'):
            parsed_data.append({"type": "documentation", "content": parse_documentation(content['content']), "name": content['name']})
        elif content['name'].endswith('.py'):
            parsed_data.append({"type": "code", "content": parse_code(content['content
']), "name": content['name']})

    # Ingest parsed data into CrewAI
    result = ingest_into_crewai(parsed_data, content_location, debug=False)
    if result:
        print("Repository contents processed and ingested into CrewAI successfully.")
    else:
        print("Failed to process repository contents with CrewAI.")
except Exception as e:
    print(f"Error processing repository: {e}")

if name == "main":
main()   
