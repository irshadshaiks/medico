import json
from typing import Dict, List, Any, Optional

LANGUAGES = {
    "en": {"name": "English", "native": "English"},
    "hi": {"name": "Hindi", "native": "हिन्दी"},
    "bn": {"name": "Bengali", "native": "বাংলা"},
    "ta": {"name": "Tamil", "native": "தமிழ்"},
    "te": {"name": "Telugu", "native": "తెలుగు"},
    "mr": {"name": "Marathi", "native": "मराठी"},
    "gu": {"name": "Gujarati", "native": "ગુજરાતી"},
    "kn": {"name": "Kannada", "native": "ಕನ್ನಡ"},
    "ml": {"name": "Malayalam", "native": "മലയാളം"},
    "pa": {"name": "Punjabi", "native": "ਪੰਜਾਬੀ"},
    "or": {"name": "Odia", "native": "ଓଡ଼ିଆ"},
}

CONSENT_TEXTS = {
    "en": {
        "title": "Clinical Intake & Data Consent",
        "description": "MediKiosk will conduct an interactive clinical interview in your language and review previous medical records. This information will be structured directly for your attending physician. Nothing here constitutes a medical prescription or final diagnosis. Your data is protected under healthcare privacy standards.",
        "button": "I Agree & Begin Intake",
        "greeting": "Namaste and welcome. I am MediKiosk, your pre-consultation assistant. To help the doctor understand your condition thoroughly, what is the primary health issue or discomfort you are experiencing today?",
        "quick_complaints": ["Chest Pain / Pressure", "Shortness of Breath", "Fever & Chills", "Abdominal Pain", "Chronic Diabetes / BP Checkup", "Persistent Cough", "Severe Headache / Dizziness"]
    },
    "hi": {
        "title": "नैदानिक सेवन और डेटा सहमति",
        "description": "मेडीकियोस्क आपकी भाषा में प्राथमिक स्वास्थ्य साक्षात्कार लेगा और आपके पुराने मेडिकल रिकॉर्ड का विश्लेषण करेगा। यह जानकारी सीधे आपके डॉक्टर के लिए तैयार की जाएगी। यह कोई अंतिम निदान नहीं है। आपका डेटा पूरी तरह सुरक्षित है।",
        "button": "मैं सहमत हूँ और साक्षात्कार शुरू करें",
        "greeting": "नमस्ते। मैं मेडीकियोस्क हूँ, आपका परामर्श-पूर्व सहायक। डॉक्टर को आपकी स्थिति बेहतर ढंग से समझाने के लिए, कृपया बताएं कि आज आपको क्या मुख्य स्वास्थ्य समस्या या बेचैनी है?",
        "quick_complaints": ["सीने में दर्द या भारीपन", "सांस लेने में तकलीफ", "तेज बुखार और ठंड", "पेट में तेज दर्द", "डायबिटीज / बीपी फॉलो-अप", "लगातार खांसी", "सिरदर्द या चक्कर आना"]
    },
    "bn": {
        "title": "ক্লিনিক্যাল ইনটেক ও সম্মতি",
        "description": "মেডিকিয়স্ক আপনার ভাষায় একটি প্রাথমিক স্বাস্থ্য সাক্ষাৎকার গ্রহণ করবে এবং আপনার পূর্ববর্তী মেডিকেল রেকর্ড পর্যালোচনা করবে। এই তথ্য ডাক্তারের পরীক্ষার জন্য প্রস্তুত করা হবে।",
        "button": "আমি সম্মত ও শুরু করুন",
        "greeting": "নমস্কার। আমি মেডিকিয়স্ক। ডাক্তারের সাথে আপনার সাক্ষাতের আগে, অনুগ্রহ করে বলুন আজ আপনার প্রধান শারীরিক সমস্যা কী?",
        "quick_complaints": ["বুকে ব্যথা বা চাপ", "শ্বাসকষ্ট", "জ্বর এবং কাঁপুনি", "পেটে ব্যথা", "ডায়াবেটিস / প্রেসার চেকআপ", "কাশি", "মাথা ঘোরা"]
    },
    "ta": {
        "title": "மருத்துவ ஒப்புதல் படிவம்",
        "description": "மெடிகியோஸ்க் உங்கள் தாய்மொழியில் மருத்துவ தகவல்களைப் பெற்று உங்கள் முந்தைய அறிக்கைகளை ஆராயும். இது மருத்துவருக்கு உதவ மட்டுமே.",
        "button": "நான் ஒப்புக்கொள்கிறேன் & தொடங்கு",
        "greeting": "வணக்கம். நான் மெடிகியோஸ்க். உங்கள் மருத்துவருக்கு உதவ, இன்று நீங்கள் சந்திக்கும் முக்கிய உடல்நலப் பிரச்சினை என்ன என்பதை தெரிவிக்கவும்?",
        "quick_complaints": ["மார்பு வலி / அழுத்தம்", "மூச்சுத் திணறல்", "காய்ச்சல்", "வயிற்று வலி", "சர்க்கரை / இரத்த அழுத்தம் பரிசோதனை", "இருமல்", "தலைச்சுற்றல்"]
    },
    "te": {
        "title": "వైద్య సమ్మతి పత్రం",
        "description": "మెడికియోస్క్ మీ భాషలో మీ ఆరోగ్య సమస్యల వివరాలు సేకరిస్తుంది మరియు మునుపటి నివేదికలను విశ్లేషిస్తుంది.",
        "button": "నేను అంగీకరిస్తున్నాను & ప్రారంభించు",
        "greeting": "నమస్కారం. నేను మెడికియోస్క్. డాక్టర్‌కి మీ ఆరోగ్య పరిస్థితి వివరించడానికి, నేడు మీకు ఎదురవుతున్న ముఖ్యమైన సమస్య ఏమిటి?",
        "quick_complaints": ["ఛాతీ నొప్పి / బిగుతు", "శ్వాస తీసుకోవడంలో ఇబ్బంది", "తీవ్ర జ్వరం", "కడుపు నొప్పి", "షుగర్ / బీపీ తనిఖీ", "దగ్గు", "తలతిరగడం"]
    },
    "mr": {
        "title": "वैद्यकीय संमती",
        "description": "मेडीकियोस्क आपल्या भाषेत प्राथमिक आरोग्य तपासणी करेल आणि जुने वैद्यकीय अहवाल तपासेल.",
        "button": "मी सहमत आहे आणि सुरू करा",
        "greeting": "नमस्कार. मी मेडीकियोस्क आहे. डॉक्टरांना तुमची स्थिती समजण्यासाठी, आज तुम्हाला काय त्रास होत आहे ते सांगा?",
        "quick_complaints": ["छातीत दुखणे किंवा जडपणा", "श्वास घेण्यास त्रास", "ताप आणि थंडी", "पोटदुखी", "मधुमेह / रक्तदाब तपासणी", "खोकला", "चक्कर येणे"]
    },
    "gu": {
        "title": "તબીબી સંમતિ",
        "description": "મેડિકિઓસ્ક તમારી ભાષામાં પ્રાથમિક પૂછપરછ કરશે અને જૂના રિપોર્ટ્સ તપાસશે.",
        "button": "હું સંમત છું & શરૂ કરો",
        "greeting": "નમસ્તે. હું મેડિકિઓસ્ક છું. ડૉક્ટરને તમારી સ્થિતિ સમજવામાં મદદ કરવા માટે, આજે તમને શું મુખ્ય તકલીફ છે?",
        "quick_complaints": ["છાતીમાં દુખાવો / દબાણ", "શ્વાસ લેવામાં તકલીફ", "તાવ", "પેટમાં દુખાવો", "ડાયાબિટીસ / બીપી ચેકઅપ", "ખાંસી", "ચક્કર આવવા"]
    },
    "kn": {
        "title": "ವೈದ್ಯಕೀಯ ಸಮ್ಮತಿ",
        "description": "ಮೆಡಿಕಿಯೋಸ್ಕ್ ನಿಮ್ಮ ಭಾಷೆಯಲ್ಲಿ ಆರೋಗ್ಯ ವಿಚಾರಣೆ ನಡೆಸುತ್ತದೆ ಮತ್ತು ಹಳೆಯ ವರದಿಗಳನ್ನು ಪರಿಶೀಲಿಸುತ್ತದೆ.",
        "button": "ನಾನು ಒಪ್ಪುತ್ತೇನೆ & ಪ್ರಾರಂಭಿಸಿ",
        "greeting": "ನಮಸ್ಕಾರ. ನಾನು ಮೆಡಿಕಿಯೋಸ್ಕ್. ವೈದ್ಯರಿಗೆ ನಿಮ್ಮ ಸಮಸ್ಯೆ ತಿಳಿಸಲು, ಇಂದು ನಿಮಗೆ ಯಾವ ತೊಂದರೆ ಇದೆ?",
        "quick_complaints": ["ಎದೆ ನೋವು / ಒತ್ತಡ", "ಉಸಿರಾಟದ ತೊಂದರೆ", "ಜ್ವರ", "ಹೊಟ್ಟೆ ನೋವು", "ಮಧುಮೇಹ / ಬಿಪಿ ಪರೀಕ್ಷೆ", "ಕೆಮ್ಮು", "ತಲೆಸುತ್ತು"]
    },
    "ml": {
        "title": "മെഡിക്കൽ സമ്മതം",
        "description": "മെഡിക്കിയോസ്ക് നിങ്ങളുടെ ഭാഷയിൽ പ്രാഥമിക വിവരങ്ങൾ ശേഖരിക്കുകയും മുൻകാല റിപ്പോർട്ടുകൾ പരിശോധിക്കുകയും ചെയ്യും.",
        "button": "ഞാൻ സമ്മതിക്കുന്നു & ആരംഭിക്കുക",
        "greeting": "നമസ്കാരം. ഞാൻ മെഡിക്കിയോസ്ക്. ഡോക്ടർക്ക് നിങ്ങളുടെ അവസ്ഥ മനസ്സിലാക്കാൻ, ഇന്ന് നിങ്ങൾക്ക് എന്താണ് പ്രധാന പ്രശ്നം?",
        "quick_complaints": ["നെഞ്ചുവേദന / ഭാരം", "ശ്വാസതടസ്സം", "പനി", "വയറുവേദന", "പ്രമേഹം / ബിപി പരിശോധന", "ചുമ", "തലകറക്കം"]
    },
    "pa": {
        "title": "ਮੈਡੀਕਲ ਸਹਿਮਤੀ",
        "description": "ਮੈਡੀਕਿਓਸਕ ਤੁਹਾਡੀ ਭਾਸ਼ਾ ਵਿੱਚ ਮੁਢਲੀ ਜਾਣਕਾਰੀ ਲਵੇਗਾ ਅਤੇ ਪੁਰਾਣੀਆਂ ਰਿਪੋਰਟਾਂ ਦੀ ਜਾਂਚ ਕਰੇਗਾ।",
        "button": "ਮੈਂ ਸਹਿਮਤ ਹਾਂ ਅਤੇ ਸ਼ੁਰੂ ਕਰੋ",
        "greeting": "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ। ਮੈਂ ਮੈਡੀਕਿਓਸਕ ਹਾਂ। ਡਾਕਟਰ ਲਈ ਜਾਣਕਾਰੀ ਤਿਆਰ ਕਰਨ ਲਈ, ਕਿਰਪਾ ਕਰਕੇ ਦੱਸੋ ਕਿ ਅੱਜ ਤੁਹਾਨੂੰ ਕੀ ਮੁੱਖ ਤਕਲੀਫ ਹੈ?",
        "quick_complaints": ["ਛਾਤੀ ਵਿੱਚ ਦਰਦ ਜਾਂ ਦਬਾਅ", "ਸਾਹ ਲੈਣ ਵਿੱਚ ਔਖ", "ਬੁਖ਼ਾਰ ਅਤੇ ਕਾਂਬਾ", "ਢਿੱਡ ਪੀੜ", "ਸ਼ੂਗਰ / ਬੀਪੀ ਚੈੱਕਅੱਪ", "ਖੰਘ", "ਚੱਕਰ ਆਉਣੇ"]
    },
    "or": {
        "title": "ଡାକ୍ତରୀ ସମ୍ମତି",
        "description": "ମେଡିକିଓସ୍କ ଆପଣଙ୍କ ଭାଷାରେ ପ୍ରାଥମିକ ସ୍ୱାସ୍ଥ୍ୟ ସୂଚନା ନେବ ଏବଂ ପୂର୍ବ ରିପୋର୍ଟ ଯାଞ୍ଚ କରିବ।",
        "button": "ମୁଁ ସହମତ ଏବଂ ଆରମ୍ଭ କରନ୍ତୁ",
        "greeting": "ନମସ୍କାର। ମୁଁ ମେଡିକିଓସ୍କ। ଡାକ୍ତରଙ୍କୁ ସାହାଯ୍ୟ କରିବା ପାଇଁ, ଦୟାକରି କୁହନ୍ତୁ ଆଜି ଆପଣଙ୍କର ମୁଖ୍ୟ ଶାରୀରିକ ସମସ୍ୟା କଣ?",
        "quick_complaints": ["ଛାତିରେ ଯନ୍ତ୍ରଣା", "ଶ୍ୱାସକଷ୍ଟ", "ଜ୍ୱର", "ପେଟ ଯନ୍ତ୍ରଣା", "ମଧୁମେହ / ବିପି ପରୀକ୍ଷା", "କାଶ", "ମୁଣ୍ଡ ବୁଲାଇବା"]
    }
}

INTERVIEW_STEPS = [
    {
        "step_id": "chief_complaint",
        "title": "Chief Complaint",
        "question_en": "What is the primary health issue or discomfort you are experiencing today?",
        "question_hi": "कृपया बताएं कि आज आपको क्या मुख्य स्वास्थ्य समस्या या बेचैनी है?",
        "chips_en": ["Chest Pain / Pressure", "Shortness of Breath", "Fever & Chills", "Abdominal Pain", "Follow-up for Diabetes / BP", "Persistent Cough"],
        "chips_hi": ["सीने में दर्द या भारीपन", "सांस लेने में तकलीफ", "तेज बुखार और ठंड", "पेट में दर्द", "डायबिटीज/बीपी फॉलोअप", "लगातार खांसी"]
    },
    {
        "step_id": "onset_duration",
        "title": "Onset & Duration",
        "question_en": "When did this discomfort start, and is it constant or coming in waves?",
        "question_hi": "यह परेशानी कब शुरू हुई, और क्या यह लगातार हो रही है या रुक-रुक कर आ रही है?",
        "chips_en": ["Started 1-2 hours ago (Sudden)", "Since this morning (6-8 hours)", "Past 2-3 days", "Over a week ago", "Constant severe ache", "Comes and goes in waves"],
        "chips_hi": ["1-2 घंटे पहले अचानक", "आज सुबह से (6-8 घंटे)", "पिछले 2-3 दिनों से", "एक हफ्ते से ज्यादा", "लगातार तेज दर्द", "रुक-रुक कर लहरों की तरह"]
    },
    {
        "step_id": "pain_character_radiation",
        "title": "Pain Character & Radiation",
        "question_en": "How would you describe the feeling, and does it spread or radiate to other areas (like your arm, neck, jaw, or back)?",
        "question_hi": "इस दर्द या बेचैनी का अहसास कैसा है, और क्या यह शरीर के अन्य हिस्सों (जैसे बाएं हाथ, गर्दन, जबड़े या पीठ) में भी फैल रहा है?",
        "chips_en": ["Heavy pressure / Tight band", "Sharp stabbing pain", "Radiates to left arm & shoulder", "Radiates to jaw/neck", "Burning sensation", "Dull ache, stays localized"],
        "chips_hi": ["भारी दबाव / जकड़न जैसा", "तेज चुभने वाला दर्द", "बाएं हाथ और कंधे में फैल रहा है", "जबड़े और गर्दन की तरफ जा रहा है", "सीने में जलन", "हल्का दर्द, केवल एक जगह"]
    },
    {
        "step_id": "severity_scale",
        "title": "Severity Scale",
        "question_en": "On a pain and discomfort scale from 1 (mild) to 10 (unbearable emergency), how severe is it right now?",
        "question_hi": "1 (हल्का) से 10 (असहनीय / गंभीर आपातकाल) के पैमाने पर, अभी आपकी तकलीफ कितनी तीव्र है?",
        "chips_en": ["10/10 - Unbearable emergency", "8-9/10 - Very severe", "6-7/10 - Moderate to high", "4-5/10 - Moderate", "1-3/10 - Mild discomfort"],
        "chips_hi": ["10/10 - असहनीय आपातकाल", "8-9/10 - बहुत ज्यादा तीव्र", "6-7/10 - मध्यम से तेज", "4-5/10 - सामान्य मध्यम", "1-3/10 - हल्का दर्द"]
    },
    {
        "step_id": "red_flags",
        "title": "Emergency Warning Signs",
        "question_en": "Are you experiencing any of these critical symptoms right now? (Select all that apply or 'None')",
        "question_hi": "क्या आपको इनमें से कोई भी गंभीर लक्षण महसूस हो रहे हैं? (कृपया चयन करें)",
        "chips_en": ["Shortness of breath / Gasping", "Cold sweating & dizziness", "Palpitations / Racing heart", "Nausea or vomiting", "None of these"],
        "chips_hi": ["सांस फूलना / हांफना", "ठंडा पसीना और चक्कर आना", "दिल की धड़कन तेज होना", "उल्टी या मतली का अहसास", "इनमें से कोई नहीं"]
    },
    {
        "step_id": "past_history",
        "title": "Past Medical History",
        "question_en": "Do you have any known existing medical conditions or chronic illnesses?",
        "question_hi": "क्या आपको पहले से कोई पुरानी बीमारी या स्वास्थ्य संबंधी समस्या है?",
        "chips_en": ["Type 2 Diabetes", "Hypertension (High BP)", "Heart disease / Prior Angioplasty", "Asthma / Respiratory condition", "Kidney disease", "No chronic conditions"],
        "chips_hi": ["टाइप 2 डायबिटीज (शुगर)", "हाई ब्लड प्रेशर (उच्च रक्तचाप)", "दिल की बीमारी / पुरानी एंजियोप्लास्टी", "दमा / अस्थमा", "किडनी की समस्या", "कोई पुरानी बीमारी नहीं"]
    },
    {
        "step_id": "current_medications",
        "title": "Current Medications & Allergies",
        "question_en": "What medicines are you taking regularly, and do you have any allergies to penicillin or other drugs?",
        "question_hi": "आप नियमित रूप से कौन सी दवाएं ले रहे हैं, और क्या आपको किसी दवा (जैसे पेनिसिलिन आदि) से एलर्जी है?",
        "chips_en": ["Metformin / Sugar medicines", "BP tablets (Amlodipine / Telmisartan)", "Blood thinners (Aspirin / Clopidogrel)", "Inhaler for asthma", "No regular medicines", "No known drug allergies", "Allergic to Penicillin / Sulfa"],
        "chips_hi": ["मेटफॉर्मिन / शुगर की गोलियां", "बीपी की दवा (एम्लोडिपिन/टेल्मीसार्टन)", "खून पतला करने की दवा (एस्पिरिन)", "अस्थमा इनहेलर", "कोई नियमित दवा नहीं", "किसी दवा से एलर्जी नहीं", "पेनिसिलिन से एलर्जी है"]
    },
    {
        "step_id": "document_upload_prompt",
        "title": "Upload Previous Medical Documents",
        "question_en": "Thank you. Did you bring any previous lab test reports (blood tests, ECG, X-Ray) or doctor prescriptions? You can upload or snap a photo now for instant clinical extraction.",
        "question_hi": "धन्यवाद। क्या आप अपने साथ कोई पुरानी लैब जांच रिपोर्ट (ब्लड टेस्ट, ईसीजी, एक्स-रे) या डॉक्टर की पर्ची लाए हैं? आप त्वरित विश्लेषण के लिए उन्हें अभी अपलोड या फोटो खींच सकते हैं।",
        "chips_en": ["I have prescription slips", "I have recent blood lab reports", "I have an ECG / Scan", "No previous reports with me"],
        "chips_hi": ["मेरे पास डॉक्टर की पर्ची है", "मेरे पास ब्लड टेस्ट रिपोर्ट है", "मेरे पास ईसीजी/स्कैन है", "मेरे पास कोई पुरानी रिपोर्ट नहीं है"]
    }
]

def get_next_question(messages_count: int, language: str = "en") -> Optional[Dict[str, Any]]:
    # 0 = initial greeting already sent
    # messages_count // 2 tells which step we are on (user replies to each step)
    step_idx = messages_count // 2
    if step_idx < len(INTERVIEW_STEPS):
        step = INTERVIEW_STEPS[step_idx]
        lang = language if language in ["en", "hi"] else "en"
        q_key = f"question_{lang}"
        c_key = f"chips_{lang}"
        question = step.get(q_key, step["question_en"])
        chips = step.get(c_key, step["chips_en"])
        return {
            "step_id": step["step_id"],
            "title": step["title"],
            "question": question,
            "chips": chips,
            "is_final": (step_idx == len(INTERVIEW_STEPS) - 1)
        }
    return None
