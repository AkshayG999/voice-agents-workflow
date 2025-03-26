import random
import requests
import json
from urllib.parse import quote
from collections.abc import AsyncIterator
from agents import Agent, Runner, TResponseInputItem, function_tool
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions
from agents.voice import VoiceWorkflowBase, VoiceWorkflowHelper
from openai import AsyncOpenAI
import os
from typing import Callable, Awaitable
from dotenv import load_dotenv  

load_dotenv()

# Initialize at module level
client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
)


@function_tool
def get_weather(city: str) -> str:
    """Get the weather for a given city."""
    print(f"[debug] get_weather called with city: {city}")
    choices = ["sunny", "cloudy", "rainy", "snowy"]
    return f"The weather in {city} is {random.choice(choices)}."


@function_tool
def get_health_info(condition: str) -> str:
    """Get information about a health condition."""
    print(f"[debug] get_health_info called with condition: {condition}")
    
    health_info = {
        "headache": "Common headaches are often caused by stress, dehydration, or lack of sleep. Try drinking water and resting.",
        "cold": "Common cold symptoms include runny nose, sore throat, and cough. Rest and hydration are typically recommended.",
        "fever": "Fever is often a sign that your body is fighting an infection. Rest and monitor your temperature.",
        "allergies": "Allergies can cause sneezing, itchy eyes, and congestion. Over-the-counter antihistamines may help.",
        "insomnia": "Insomnia is difficulty falling or staying asleep. Consider improving sleep hygiene and reducing caffeine intake.",
        "anxiety": "Anxiety can manifest as worry, restlessness, and physical symptoms. Deep breathing exercises may help manage symptoms.",
        "back pain": "Back pain can result from poor posture, muscle strain, or underlying conditions. Gentle stretching may provide relief.",
        "high blood pressure": "High blood pressure often has no symptoms but can lead to serious health problems. Regular monitoring is important.",
        "diabetes": "Diabetes affects how your body processes blood sugar. Symptoms may include increased thirst and frequent urination.",
    }
    
    return health_info.get(condition.lower(), f"I don't have specific information about {condition}. Please consult a healthcare professional.")


@function_tool
def classify_medical_intent(query: str) -> str:
    """Classify the medical intent of a user query to route to the appropriate specialist."""
    print(f"[debug] classify_medical_intent called with query: {query}")
    
    query = query.lower()
    
    # Simple keyword-based classification
    if any(word in query for word in ["heart", "chest pain", "blood pressure", "cardiovascular"]):
        return "cardiology"
    elif any(word in query for word in ["brain", "headache", "migraine", "memory", "neurological"]):
        return "neurology"
    elif any(word in query for word in ["diet", "nutrition", "food", "weight", "eating"]):
        return "nutrition"
    elif any(word in query for word in ["medicine", "drug", "medication", "pill", "prescription"]):
        return "medication"
    elif any(word in query for word in ["mental", "anxiety", "depression", "stress", "mood"]):
        return "mental_health"
    elif any(word in query for word in ["cancer", "tumor", "oncology", "chemotherapy", "radiation", "malignant"]):
        return "cancer_research"
    else:
        return "general_health"


@function_tool
def get_medication_info(medication: str) -> str:
    """Get information about medications, including usage, side effects, and precautions."""
    print(f"[debug] get_medication_info called with medication: {medication}")
    
    medication_info = {
        "aspirin": "Aspirin is used to relieve pain, reduce inflammation, and lower fever. Common side effects include stomach irritation. Should not be given to children due to risk of Reye's syndrome.",
        "ibuprofen": "Ibuprofen is a nonsteroidal anti-inflammatory drug used for pain relief and reducing inflammation. Take with food to reduce stomach irritation. Not recommended for those with certain heart conditions.",
        "acetaminophen": "Acetaminophen relieves pain and reduces fever but doesn't reduce inflammation. Liver damage can occur if taken in high doses or with alcohol.",
        "lisinopril": "Lisinopril is an ACE inhibitor used to treat high blood pressure and heart failure. Side effects may include dry cough and dizziness.",
        "metformin": "Metformin is used to treat type 2 diabetes by improving blood sugar control. Common side effects include digestive issues. Take with meals.",
    }
    
    return medication_info.get(medication.lower(), f"I don't have specific information about {medication}. Please consult a healthcare professional or pharmacist.")


@function_tool
def get_nutrition_advice(food_or_condition: str) -> str:
    """Get nutritional advice for specific foods or health conditions."""
    print(f"[debug] get_nutrition_advice called with: {food_or_condition}")
    
    nutrition_info = {
        "diabetes": "Focus on foods with low glycemic index, like whole grains, legumes, and non-starchy vegetables. Limit added sugars and refined carbs.",
        "hypertension": "The DASH diet is recommended - reduce sodium, increase potassium with fruits and vegetables, and limit processed foods.",
        "heart health": "Choose heart-healthy fats like those in olive oil, avocados, and fatty fish. Limit saturated and trans fats.",
        "weight loss": "Focus on whole foods, increase protein and fiber intake, and be mindful of portion sizes and caloric density.",
        "vegetarian": "Ensure adequate protein from sources like legumes, tofu, and dairy. Consider supplements for vitamin B12 and iron.",
        "gluten free": "Focus on naturally gluten-free foods like rice, potatoes, fruits, vegetables, and lean proteins. Be careful of cross-contamination.",
    }
    
    return nutrition_info.get(food_or_condition.lower(), f"For {food_or_condition}, I recommend consulting with a registered dietitian for personalized nutritional advice.")


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
        # Documentation: https://www.cancer.gov/syndication/api
        base_url = "https://www.cancer.gov/api/sitewide"
        
        params = {
            "query": query,
            "size": 5,  # Number of results to return
            "from": 0,   # Starting position
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
                # Format the results into a readable response
                response_text = "According to the National Cancer Institute:\n\n"
                
                for result in results[:2]:  # Limit to top 2 results for conciseness
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
        # Use the NCBI E-utilities API (PubMed)
        # Documentation: https://www.ncbi.nlm.nih.gov/books/NBK25500/
        
        # Step 1: Search for IDs
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        search_params = {
            "db": "pubmed",
            "term": f"{query} AND cancer[MeSH Terms]",
            "retmax": 3,  # Get top 3 results
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
        
        # Format the results
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
        # MedlinePlus Connect API
        # Documentation: https://medlineplus.gov/connect/service.html
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
                    
                    for item in entry[:2]:  # Limit to top 2 results
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
                # If not JSON, it might be XML, use a simple fallback
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


# Specialized healthcare agents
general_healthcare_agent = Agent(
    name="General Healthcare",
    handoff_description="A general healthcare specialist that provides basic health information and triage.",
    instructions=prompt_with_handoff_instructions(
        "You're a general healthcare assistant. Provide helpful health information but always remind users to consult healthcare professionals for medical advice. Be polite and concise. Always respond in English only. If the query is specialized, recommend the appropriate specialist.",
    ),
    model="gpt-4o-mini",
    tools=[get_health_info, classify_medical_intent],
)

cardiology_agent = Agent(
    name="Cardiology",
    handoff_description="A cardiology specialist for heart-related queries.",
    instructions=prompt_with_handoff_instructions(
        "You're a cardiology assistant specializing in heart health. Provide information about heart conditions, cardiovascular health, and related symptoms. Always emphasize the importance of seeking professional medical advice. Be polite and concise. Always respond in English only.",
    ),
    model="gpt-4o-mini",
    tools=[get_health_info],
)

neurology_agent = Agent(
    name="Neurology",
    handoff_description="A neurology specialist for brain and nervous system queries.",
    instructions=prompt_with_handoff_instructions(
        "You're a neurology assistant specializing in brain and nervous system health. Provide information about neurological conditions, brain health, and related symptoms. Always emphasize the importance of seeking professional medical advice. Be polite and concise. Always respond in English only.",
    ),
    model="gpt-4o-mini",
    tools=[get_health_info],
)

nutrition_agent = Agent(
    name="Nutrition",
    handoff_description="A nutrition specialist for diet and food-related queries.",
    instructions=prompt_with_handoff_instructions(
        "You're a nutrition assistant specializing in dietary advice. Provide information about healthy eating, dietary requirements for various conditions, and general nutrition facts. Always emphasize consulting with a registered dietitian for personalized advice. Be polite and concise. Always respond in English only.",
    ),
    model="gpt-4o-mini",
    tools=[get_nutrition_advice],
)

medication_agent = Agent(
    name="Medication",
    handoff_description="A pharmacy specialist for medication-related queries.",
    instructions=prompt_with_handoff_instructions(
        "You're a medication assistant specializing in pharmaceutical information. Provide general information about medications, potential side effects, and usage guidelines. Always emphasize the importance of following a doctor's prescription and consulting with a pharmacist. Be polite and concise. Always respond in English only.",
    ),
    model="gpt-4o-mini",
    tools=[get_medication_info],
)

mental_health_agent = Agent(
    name="Mental Health",
    handoff_description="A mental health specialist for psychological and emotional wellbeing queries.",
    instructions=prompt_with_handoff_instructions(
        "You're a mental health assistant specializing in psychological wellbeing. Provide supportive information about mental health conditions, stress management, and emotional wellbeing. Always emphasize the importance of seeking professional help from therapists or counselors. Be empathetic, polite, and concise. Always respond in English only.",
    ),
    model="gpt-4o-mini",
    tools=[get_health_info],
)

# Add new cancer research agent
cancer_research_agent = Agent(
    name="Cancer Research",
    handoff_description="A specialized oncology and cancer research agent with access to medical databases including PubMed and NCI.",
    instructions=prompt_with_handoff_instructions(
        "You're a cancer research specialist with access to the latest medical information from PubMed, the National Cancer Institute, and other reputable sources. Provide evidence-based information about cancer types, treatments, research developments, and prevention. Always cite your sources and emphasize that patients should consult with oncologists for personalized medical advice. Be compassionate, accurate, and clear in your explanations. Always respond in English only. Use the web search tool to provide up-to-date cancer information when necessary.",
    ),
    model="gpt-4o-mini",
    tools=[web_search_cancer_info],
)

# Updated main agent with improved routing capabilities and healthcare specializations
agent = Agent(
    name="Assistant",
    instructions=prompt_with_handoff_instructions(
        "You're speaking to a human seeking health information. Be polite, empathetic, and concise. Use the classify_medical_intent tool to determine the appropriate specialist for health queries. Hand off to: General Healthcare for basic health questions, Cardiology for heart-related queries, Neurology for brain and nervous system questions, Nutrition for diet inquiries, Medication for pharmaceutical questions, Mental Health for psychological wellbeing topics, and Cancer Research for any cancer or oncology related questions. If the user speaks in Spanish, handoff to the Spanish agent. Always respond in English only unless directed to the Spanish agent. Maintain memory of the conversation history to provide contextually relevant responses. Reference previous interactions when appropriate.",
    ),
    model="gpt-4o-mini",
    handoffs=[general_healthcare_agent, cardiology_agent, neurology_agent, nutrition_agent, medication_agent, mental_health_agent, cancer_research_agent],
    tools=[classify_medical_intent, get_weather],
)


class MyWorkflow(VoiceWorkflowBase):
    def __init__(self, 
                secret_word: str, 
                on_start: Callable[[str], Awaitable[None]], 
                on_response: Callable[[str], Awaitable[None]] = None):
        """
        Args:
            secret_word: The secret word to guess.
            on_start: A coroutine that is called when the workflow starts. The transcription
                is passed in as an argument.
            on_response: A coroutine that is called with the agent's complete response text.
        """
        self._input_history: list[TResponseInputItem] = []
        self._current_agent = agent
        self._secret_word = secret_word.lower()
        self._on_start = on_start
        self._on_response = on_response

    async def run(self, transcription: str) -> AsyncIterator[str]:
        await self._on_start(transcription)

        # Add the transcription to the input history
        self._input_history.append(
            {
                "role": "user",
                "content": transcription,
            }
        )

        # If the user guessed the secret word, do alternate logic
        if self._secret_word in transcription.lower():
            response_text = "You guessed the secret word!"
            yield response_text
            self._input_history.append(
                {
                    "role": "assistant",
                    "content": response_text,
                }
            )
            # Send the response to the client if callback is provided
            if self._on_response:
                await self._on_response(response_text)
            return

        # Otherwise, run the agent
        result = Runner.run_streamed(self._current_agent, self._input_history)

        # Collect the complete response while streaming chunks
        full_response = []
        async for chunk in VoiceWorkflowHelper.stream_text_from(result):
            full_response.append(chunk)
            yield chunk

        # Join the collected chunks to get the complete response
        complete_response = "".join(full_response)
        
        # Send the complete response to the client if callback is provided
        if self._on_response:
            await self._on_response(complete_response)

        # Update the input history and current agent
        self._input_history = result.to_input_list()
        self._current_agent = result.last_agent