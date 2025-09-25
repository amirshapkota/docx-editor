# Basic ML compliance functionality for testing
# This file can be expanded with full ML features later

def basic_compliance_check(original_text, comment_text, edited_text):
    """
    Basic rule-based compliance checking
    Returns a compliance score and explanation
    """
    
    # Simple keyword-based checking
    comment_words = set(comment_text.lower().split())
    original_words = set(original_text.lower().split()) 
    edited_words = set(edited_text.lower().split())
    
    # Check if text was actually changed
    text_changed = original_text.strip() != edited_text.strip()
    
    # Check word overlap between comment and changes
    added_words = edited_words - original_words
    comment_word_overlap = len(comment_words.intersection(added_words)) > 0
    
    # Basic scoring logic
    compliance_score = 0.0
    explanations = []
    
    if not text_changed:
        compliance_score = 0.1
        explanations.append("Text was not modified")
    else:
        compliance_score = 0.5  # Base score for making changes
        explanations.append("Text was modified")
        
        if comment_word_overlap:
            compliance_score += 0.3
            explanations.append("Changes include words mentioned in comment")
        
        # Check for length changes (might indicate detail addition)
        if len(edited_text) > len(original_text) * 1.2:
            compliance_score += 0.2
            explanations.append("Text was expanded with additional details")
    
    # Cap at 1.0
    compliance_score = min(compliance_score, 1.0)
    
    # Determine prediction label
    if compliance_score > 0.7:
        prediction = "compliant"
    elif compliance_score > 0.4:
        prediction = "partial"
    else:
        prediction = "non_compliant"
    
    return {
        'compliance_score': compliance_score,
        'prediction': prediction,
        'confidence': 0.8,  # Fixed confidence for basic checker
        'explanations': explanations
    }


class BasicComplianceChecker:
    """Simple compliance checker that doesn't require ML dependencies"""
    
    def __init__(self):
        self.model_type = "Rule-based"
    
    def predict(self, original, comment, edited):
        """Make a prediction using basic rules"""
        return basic_compliance_check(original, comment, edited)
    
    def explain_prediction(self, original, comment, edited):
        """Provide explanation for the prediction"""
        result = basic_compliance_check(original, comment, edited)
        return {
            'interpretation': result['explanations'],
            'top_features': [('text_similarity', 0.3), ('word_overlap', 0.4)]
        }


def get_basic_compliance_model():
    """Get the basic compliance model (no ML dependencies needed)"""
    return BasicComplianceChecker()