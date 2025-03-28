import random
import requests
import json
from urllib.parse import quote
from agents import function_tool

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