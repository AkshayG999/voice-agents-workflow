from agents import Agent
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions
from healthcare_agents.functions.health_functions import get_health_info, classify_medical_intent
from healthcare_agents.functions.specialized_functions import get_medication_info, get_nutrition_advice
from healthcare_agents.functions.cancer_research import web_search_cancer_info

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

cancer_research_agent = Agent(
    name="Cancer Research",
    handoff_description="A specialized oncology and cancer research agent with access to medical databases including PubMed and NCI.",
    instructions=prompt_with_handoff_instructions(
        "You're a cancer research specialist with access to the latest medical information from PubMed, the National Cancer Institute, and other reputable sources. Provide evidence-based information about cancer types, treatments, research developments, and prevention. Always cite your sources and emphasize that patients should consult with oncologists for personalized medical advice. Be compassionate, accurate, and clear in your explanations. Always respond in English only. Use the web search tool to provide up-to-date cancer information when necessary.",
    ),
    model="gpt-4o-mini",
    tools=[web_search_cancer_info],
)

# Main agent with routing capabilities
main_agent = Agent(
    name="Assistant",
    instructions=prompt_with_handoff_instructions(
        "You're speaking to a human seeking health information. Be polite, empathetic, and concise. Use the classify_medical_intent tool to determine the appropriate specialist for health queries. Hand off to: General Healthcare for basic health questions, Cardiology for heart-related queries, Neurology for brain and nervous system questions, Nutrition for diet inquiries, Medication for pharmaceutical questions, Mental Health for psychological wellbeing topics, and Cancer Research for any cancer or oncology related questions. If the user speaks in Spanish, handoff to the Spanish agent. Always respond in English only unless directed to the Spanish agent. Maintain memory of the conversation history to provide contextually relevant responses. Reference previous interactions when appropriate.",
    ),
    model="gpt-4o-mini",
    handoffs=[general_healthcare_agent, cardiology_agent, neurology_agent, nutrition_agent, medication_agent, mental_health_agent, cancer_research_agent],
    tools=[classify_medical_intent],
) 