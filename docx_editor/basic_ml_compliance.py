# Basic ML compliance functionality for testing
# This file can be expanded with full ML features later
import re
from typing import Dict, Any

def basic_compliance_check(original_text, comment_text, edited_text):
    """
    Enhanced rule-based compliance checking with constraint validation
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
    
    # NEW: Check for specific constraints in comments
    constraint_violations = check_basic_constraints(comment_text, edited_text)
    
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
    
    # Apply constraint penalties
    if constraint_violations:
        penalty = len(constraint_violations) * 0.3
        compliance_score = max(0.0, compliance_score - penalty)
        explanations.extend([f"Constraint violation: {v}" for v in constraint_violations])
    else:
        # Bonus for meeting constraints
        if has_constraints(comment_text):
            compliance_score += 0.2
            explanations.append("All detected constraints satisfied")
    
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
        'explanations': explanations,
        'constraint_violations': constraint_violations
    }


def check_basic_constraints(comment_text: str, edited_text: str) -> list:
    """Check for basic constraint violations"""
    violations = []
    comment_lower = comment_text.lower()
    
    # Word count constraints
    word_count_patterns = [
        r'(?:should\s+not\s+exceed|must\s+not\s+exceed|limit\s+to|maximum\s+of|max\s+of|no\s+more\s+than)\s+(\d+)\s+words?',
        r'(\d+)\s+words?\s+(?:limit|maximum|max)',
        r'keep\s+(?:it\s+)?(?:under|below)\s+(\d+)\s+words?'
    ]
    
    for pattern in word_count_patterns:
        matches = re.finditer(pattern, comment_lower, re.IGNORECASE)
        for match in matches:
            max_words = int(match.group(1))
            actual_words = len(edited_text.split())
            if actual_words > max_words:
                violations.append(f"Word count {actual_words} exceeds limit of {max_words}")
            break
    
    # Minimum word count constraints
    min_word_patterns = [
        r'(?:should\s+be\s+at\s+least|minimum\s+of|min\s+of|at\s+least)\s+(\d+)\s+words?',
        r'(\d+)\s+words?\s+(?:minimum|min)',
        r'expand\s+to\s+(?:at\s+least\s+)?(\d+)\s+words?'
    ]
    
    for pattern in min_word_patterns:
        matches = re.finditer(pattern, comment_lower, re.IGNORECASE)
        for match in matches:
            min_words = int(match.group(1))
            actual_words = len(edited_text.split())
            if actual_words < min_words:
                violations.append(f"Word count {actual_words} below minimum of {min_words}")
            break
    
    # Sentence count constraints
    sentence_patterns = [
        r'(?:should\s+not\s+exceed|limit\s+to|maximum\s+of|max\s+of)\s+(\d+)\s+sentences?',
        r'(\d+)\s+sentences?\s+(?:limit|maximum|max)'
    ]
    
    for pattern in sentence_patterns:
        matches = re.finditer(pattern, comment_lower, re.IGNORECASE)
        for match in matches:
            max_sentences = int(match.group(1))
            actual_sentences = len([s for s in edited_text.split('.') if s.strip()])
            if actual_sentences > max_sentences:
                violations.append(f"Sentence count {actual_sentences} exceeds limit of {max_sentences}")
            break
    
    # Character limit constraints
    char_patterns = [
        r'(?:should\s+not\s+exceed|limit\s+to|maximum\s+of)\s+(\d+)\s+characters?',
        r'(\d+)\s+characters?\s+(?:limit|maximum|max)'
    ]
    
    for pattern in char_patterns:
        matches = re.finditer(pattern, comment_lower, re.IGNORECASE)
        for match in matches:
            max_chars = int(match.group(1))
            actual_chars = len(edited_text)
            if actual_chars > max_chars:
                violations.append(f"Character count {actual_chars} exceeds limit of {max_chars}")
            break
    
    return violations


def has_constraints(comment_text: str) -> bool:
    """Check if comment contains any detectable constraints"""
    comment_lower = comment_text.lower()
    
    constraint_indicators = [
        r'\d+\s+words?',
        r'\d+\s+sentences?',
        r'\d+\s+characters?',
        r'should\s+not\s+exceed',
        r'limit\s+to',
        r'maximum\s+of',
        r'minimum\s+of',
        r'at\s+least',
        r'no\s+more\s+than'
    ]
    
    return any(re.search(pattern, comment_lower, re.IGNORECASE) for pattern in constraint_indicators)


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
        
        explanation = {
            'interpretation': result['explanations'],
            'top_features': [('text_similarity', 0.3), ('word_overlap', 0.4)]
        }
        
        # Add constraint information if available
        if result.get('constraint_violations'):
            explanation['constraint_analysis'] = {
                'constraints_detected': has_constraints(comment),
                'violations': result['constraint_violations'],
                'total_violations': len(result['constraint_violations'])
            }
        
        return explanation


def get_basic_compliance_model():
    """Get the basic compliance model (no ML dependencies needed)"""
    return BasicComplianceChecker()