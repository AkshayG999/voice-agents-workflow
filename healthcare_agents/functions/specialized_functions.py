import requests
import json
from urllib.parse import quote
from agents import function_tool

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