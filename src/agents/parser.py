"""Stream parsing logic for SQL Agent."""

from typing import Dict, Optional

from langchain_core.messages import AIMessage, ToolMessage
from src.utils.logger import logger


def parse_streaming_chunk(chunk: dict, current_sql: Optional[str] = None, current_response: Optional[str] = None) -> Optional[Dict]:
    """
    Parses a streaming chunk from the agent to extract relevant information.
    
    Args:
        chunk: Agent stream chunk.
        current_sql: Currently detected SQL (for tracking).
        current_response: Current response (for tracking).
        
    Returns:
        Dict with chunk info or None if no relevant info.
        Keys: 'type' (sql|execution|data|analysis|error), 'content', 'sql', 'complete'
    """
    try:
        chunk_info = {}
        
        # Search for messages in the chunk
        for key, value in chunk.items():
            if isinstance(value, dict) and "messages" in value:
                messages = value["messages"]
                
                for msg in messages:
                    # Detect SQL generated in AIMessage with tool_calls
                    if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            if tool_call.get("name") == "validated_sql_query":
                                args = tool_call.get("args", {})
                                sql = args.get("query")
                                if sql and sql != current_sql:
                                    chunk_info.update({
                                        "type": "sql",
                                        "sql": sql,
                                        "content": sql,
                                        "complete": True
                                    })
                                    return chunk_info
                    
                    # Detect execution results in ToolMessage
                    if isinstance(msg, ToolMessage):
                        content = getattr(msg, "content", None) or str(msg)
                        if content and content != current_response:
                            # Detect if it's an error
                            if "Error" in content or "error" in content.lower():
                                chunk_info.update({
                                    "type": "error",
                                    "content": content,
                                    "complete": True
                                })
                            else:
                                # It's an execution result
                                chunk_info.update({
                                    "type": "execution",
                                    "content": content,
                                    "complete": True
                                })
                            return chunk_info
                    
                    # Detect final agent response (analysis)
                    if isinstance(msg, AIMessage) and hasattr(msg, "content") and msg.content:
                        content = msg.content
                        # If it's not a tool call and has content, it's analysis/response
                        if not (hasattr(msg, "tool_calls") and msg.tool_calls):
                            # Verify if it's new content (not just SQL)
                            if content and len(content) > 50:  # Significant responses
                                chunk_info.update({
                                    "type": "analysis",
                                    "content": content,
                                    "complete": False  # Can keep generating
                                })
                                return chunk_info
        
        # If there is partial content in the chunk but not a complete message
        if "agent" in chunk:
            agent_chunk = chunk["agent"]
            if isinstance(agent_chunk, dict) and "messages" in agent_chunk:
                for msg in agent_chunk["messages"]:
                    if hasattr(msg, "content") and msg.content:
                        content = msg.content
                        # Partial analysis content
                        if len(content) > 10:
                            chunk_info.update({
                                "type": "analysis",
                                "content": content,
                                "complete": False
                            })
                            return chunk_info
        
        return None
        
    except Exception as e:
        logger.debug(f"Error parsing streaming chunk: {e}")
        return None