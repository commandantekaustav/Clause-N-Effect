from langchain_community.tools.tavily_search import TavilySearchResults

def execute_tavily_search(query: str) -> str:
    """
    Executes a web search targeting the latest Indian labor policies and statutes.
    Includes comprehensive exception safety to handle connection timeouts, API failures, 
    and variable output types returned by the LangChain Tavily integration.
    """
    try:
        # Request k=2 top results to restrict token overhead and maintain speed
        web_search_tool = TavilySearchResults(k=2)
        
        # Invoke search passing a string directly (dictionary serialization occasionally breaks)
        search_results = web_search_tool.invoke(query)
        
        if isinstance(search_results, str):
            return search_results
        elif isinstance(search_results, list):
            context_pieces = []
            for item in search_results:
                if isinstance(item, dict):
                    context_pieces.append(item.get("content", ""))
                else:
                    context_pieces.append(str(item))
            return "\n".join(context_pieces)
        else:
            return str(search_results)
            
    except Exception as e:
        return f"Warning: Web search fallback failed due to: {str(e)}. Proceeding with local documents only."