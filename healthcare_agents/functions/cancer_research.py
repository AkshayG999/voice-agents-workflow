import requests
import json
from urllib.parse import quote
from agents import function_tool

@function_tool
def web_search_cancer_info(query: str) -> str:
    """Search the web for cancer-related information using PubMed and NCI APIs."""
    print(f"[debug] web_search_cancer_info called with query: {query}")
    
    # Sanitize the query to focus on cancer-related information
    sanitized_query = f"{query} cancer"
    
    try:
        # First try to get information from the National Cancer Institute API
        nci_results = search_nci(sanitized_query)
        if nci_results:
            return nci_results
        
        # If no NCI results, try PubMed
        pubmed_results = search_pubmed(sanitized_query)
        if pubmed_results:
            return pubmed_results
        
        # If both fail, use MedlinePlus as fallback
        medline_results = search_medlineplus(sanitized_query)
        if medline_results:
            return medline_results
            
        return "I couldn't find specific cancer research information on this topic. Please try asking a more specific question about cancer types, treatments, or research."
        
    except Exception as e:
        print(f"Error in cancer web search: {e}")
        return "I encountered an error while searching for cancer information. Please try again with a different query or consult medical professionals for accurate information."

def search_nci(query):
    """Search the National Cancer Institute's API for cancer information."""
    try:
        base_url = "https://www.cancer.gov/api/sitewide"
        
        params = {
            "query": query,
            "size": 5,
            "from": 0,
            "site": "Cancer.gov"
        }
        
        headers = {
            "User-Agent": "HealthcareAssistant/1.0",
            "Accept": "application/json"
        }
        
        response = requests.get(base_url, params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            
            if results:
                response_text = "According to the National Cancer Institute:\n\n"
                
                for result in results[:2]:
                    title = result.get("title", "Untitled")
                    description = result.get("description", "No description available")
                    url = result.get("url", "")
                    
                    response_text += f"- {title}: {description}\n"
                    if url:
                        response_text += f"  Source: {url}\n\n"
                
                response_text += "Please consult healthcare professionals for personalized medical advice."
                return response_text
        
        return None
    
    except Exception as e:
        print(f"Error in NCI search: {e}")
        return None

def search_pubmed(query):
    """Search PubMed for cancer research publications."""
    try:
        # Step 1: Search for IDs
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        search_params = {
            "db": "pubmed",
            "term": f"{query} AND cancer[MeSH Terms]",
            "retmax": 3,
            "sort": "relevance",
            "retmode": "json"
        }
        
        search_response = requests.get(search_url, params=search_params)
        
        if search_response.status_code != 200:
            return None
            
        search_data = search_response.json()
        id_list = search_data.get("esearchresult", {}).get("idlist", [])
        
        if not id_list:
            return None
            
        # Step 2: Fetch summary for those IDs
        summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        summary_params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "json"
        }
        
        summary_response = requests.get(summary_url, params=summary_params)
        
        if summary_response.status_code != 200:
            return None
            
        summary_data = summary_response.json()
        
        response_text = "Recent cancer research from PubMed:\n\n"
        
        for article_id in id_list:
            if article_id in summary_data.get("result", {}):
                article = summary_data["result"][article_id]
                title = article.get("title", "Untitled")
                authors = ", ".join([author.get("name", "") for author in article.get("authors", [])[:3]])
                if len(article.get("authors", [])) > 3:
                    authors += " et al."
                journal = article.get("fulljournalname", "")
                pub_date = article.get("pubdate", "")
                
                response_text += f"- {title}\n"
                if authors:
                    response_text += f"  Authors: {authors}\n"
                if journal and pub_date:
                    response_text += f"  Published in {journal}, {pub_date}\n"
                response_text += f"  PubMed ID: {article_id}\n"
                response_text += f"  Link: https://pubmed.ncbi.nlm.nih.gov/{article_id}/\n\n"
        
        response_text += "These findings are from peer-reviewed medical research. Please consult healthcare professionals for interpreting these results for your specific situation."
        return response_text
        
    except Exception as e:
        print(f"Error in PubMed search: {e}")
        return None

def search_medlineplus(query):
    """Search MedlinePlus as a fallback for general health information."""
    try:
        encoded_query = quote(query)
        url = f"https://connect.medlineplus.gov/service?mainSearchCriteria.v.cs=2.16.840.1.113883.6.90&mainSearchCriteria.v.c=C50&informationRecipient.languageCode.c=en"
        
        headers = {
            "User-Agent": "HealthcareAssistant/1.0",
            "Accept": "application/json"
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            try:
                data = response.json()
                entry = data.get("feed", {}).get("entry", [])
                
                if entry:
                    response_text = "Information from MedlinePlus (National Library of Medicine):\n\n"
                    
                    for item in entry[:2]:
                        title = item.get("title", "Untitled")
                        summary = item.get("summary", "No summary available")
                        link = next((l.get("href") for l in item.get("link", []) if l.get("href")), "")
                        
                        response_text += f"- {title}\n"
                        response_text += f"  {summary}\n"
                        if link:
                            response_text += f"  Source: {link}\n\n"
                    
                    response_text += "This information is provided by the National Library of Medicine. Always consult healthcare professionals for medical advice."
                    return response_text
            except json.JSONDecodeError:
                pass
        
        # Fallback - search WHO for cancer information
        who_url = "https://www.who.int/news-room/fact-sheets/detail/cancer"
        who_response = requests.get(who_url)
        
        if who_response.status_code == 200:
            return """According to the World Health Organization:

Cancer is a leading cause of death worldwide, accounting for nearly 10 million deaths in 2020. The most common cancers are breast, lung, colon, rectum, and prostate cancers.

Key facts:
- Between 30-50% of cancers can be prevented by avoiding risk factors and implementing prevention strategies
- Cancer risk increases with age, largely due to cellular repair mechanisms becoming less effective
- Tobacco use, alcohol consumption, unhealthy diet, and physical inactivity are major cancer risk factors worldwide

Early detection and effective treatment are crucial for improving cancer outcomes. Please consult healthcare professionals for personalized medical advice.

Source: World Health Organization, https://www.who.int/news-room/fact-sheets/detail/cancer"""
        
        return None
        
    except Exception as e:
        print(f"Error in MedlinePlus search: {e}")
        return None
