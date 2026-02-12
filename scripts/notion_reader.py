import os
import sys
import requests
import json
from typing import List, Dict, Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_VERSION = "2022-06-28"

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json"
}

def search_page_by_title(title: str, database_id: str) -> str | None:
    search_url = "https://api.notion.com/v1/search"
    payload = {
        "query": title,
        "filter": {
            "property": "object",
            "value": "page"
        },
        "sort": {
            "direction": "descending",
            "timestamp": "last_edited_time"
        }
    }
    
    response = requests.post(search_url, headers=HEADERS, json=payload)
    if response.status_code != 200:
        print(f"Error searching Notion: {response.text}", file=sys.stderr)
        return None
    
    results = response.json().get("results", [])
    
    found_pages = []
    for page in results:
        if page.get("parent", {}).get("type") == "database_id" and \
           page["parent"]["database_id"] == database_id:
            page_title_property = page.get("properties", {}).get("Nome", {}).get("title")
            if page_title_property:
                page_title = "".join([t["plain_text"] for t in page_title_property if "plain_text" in t])
                if title == "" or page_title == title: # Added condition to list all if title is empty
                    found_pages.append((page_title, page["id"]))
    
    if title == "" and found_pages:
        print("Available pages in the database:", file=sys.stderr)
        for p_title, p_id in found_pages:
            print(f"- {p_title} (ID: {p_id})", file=sys.stderr)
        return None # Indicate no specific page found but listed available
    
    for p_title, p_id in found_pages:
        if p_title == title:
            return p_id
            
    return None



def get_block_content(block_id: str) -> List[Dict[str, Any]]:
    block_url = f"https://api.notion.com/v1/blocks/{block_id}/children"
    response = requests.get(block_url, headers=HEADERS)
    if response.status_code != 200:
        print(f"Error fetching block content: {response.text}", file=sys.stderr)
        return []
    return response.json().get("results", [])

def blocks_to_markdown(blocks: List[Dict[str, Any]]) -> str:
    markdown_content = []
    for block in blocks:
        block_type = block["type"]
        
        if block_type == "paragraph":
            text = "".join([rt["plain_text"] for rt in block["paragraph"]["rich_text"]])
            markdown_content.append(text)
        elif block_type == "heading_1":
            text = "".join([rt["plain_text"] for rt in block["heading_1"]["rich_text"]])
            markdown_content.append(f"# {text}")
        elif block_type == "heading_2":
            text = "".join([rt["plain_text"] for rt in block["heading_2"]["rich_text"]])
            markdown_content.append(f"## {text}")
        elif block_type == "heading_3":
            text = "".join([rt["plain_text"] for rt in block["heading_3"]["rich_text"]])
            markdown_content.append(f"### {text}")
        elif block_type == "to_do":
            text = "".join([rt["plain_text"] for rt in block["to_do"]["rich_text"]])
            checked = "[x]" if block["to_do"]["checked"] else "[ ]"
            markdown_content.append(f"- {checked} {text}")
        elif block_type == "code":
            text = "".join([rt["plain_text"] for rt in block["code"]["rich_text"]])
            language = block["code"].get("language", "plain text")
            markdown_content.append(f"``` {language}\n{text}\n```")
        elif block_type == "bulleted_list_item":
            text = "".join([rt["plain_text"] for rt in block["bulleted_list_item"]["rich_text"]])
            markdown_content.append(f"- {text}")
        elif block_type == "numbered_list_item":
            text = "".join([rt["plain_text"] for rt in block["numbered_list_item"]["rich_text"]])
            # This is a simplification; for actual numbered lists, you'd need to track the number
            markdown_content.append(f"1. {text}")
        elif block_type == "callout":
            icon = block["callout"].get("icon", {}).get("emoji", "💡")
            text = "".join([rt["plain_text"] for rt in block["callout"]["rich_text"]])
            markdown_content.append(f"{icon} {text}")
        elif block_type == "child_page":
            title = block["child_page"].get("title", "")
            markdown_content.append(f"[[{title}]]") # Notion-style link to child page
        elif block_type == "image":
            # This is a simplification. You might want to handle different image sources (external/file)
            image_url = block["image"].get("external", {}).get("url") or block["image"].get("file", {}).get("url")
            if image_url:
                markdown_content.append(f"![Image]({image_url})")
        elif block_type == "divider":
            markdown_content.append("---")
        # Add more block types as needed
        
        markdown_content.append("") # Add a newline between blocks for readability
            
    return "\n".join(markdown_content)

def main():
    if len(sys.argv) < 3:
        print("Usage: python notion_reader.py <page_title> <notion_database_id>", file=sys.stderr)
        sys.exit(1)
        
    page_title = sys.argv[1]
    notion_database_id = sys.argv[2]
    
    print(f"Searching for page '{page_title}' in database '{notion_database_id}'...", file=sys.stderr)
    page_id = search_page_by_title(page_title, notion_database_id)
    
    if page_id:
        print(f"Found page with ID: {page_id}. Fetching content...", file=sys.stderr)
        blocks = get_block_content(page_id)
        if blocks:
            markdown = blocks_to_markdown(blocks)
            print(markdown)
        else:
            print(f"No content found for page '{page_title}'.", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"Page '{page_title}' not found in database '{notion_database_id}'.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
