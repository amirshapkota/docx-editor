"""
ML Pipeline for Comment-Edit Compliance Checking
Integrated into the existing DOCX Editor Django project
"""

import os
import pickle
import re
import difflib
from typing import Dict, List, Tuple, Optional, Any

# Try to import ML dependencies gracefully
try:
    import numpy as np
    import pandas as pd
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, classification_report
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline
    from textblob import TextBlob
    ML_DEPENDENCIES_AVAILABLE = True
    
except ImportError as e:
    print(f"Warning: ML dependencies not fully available: {e}")
    ML_DEPENDENCIES_AVAILABLE = False
    # Create dummy classes to prevent import errors
    np = None
    pd = None


# Constraint detection patterns
CONSTRAINT_PATTERNS = {
    'word_count': [
        r'(?:should\s+not\s+exceed|must\s+not\s+exceed|limit\s+to|maximum\s+of|max\s+of|no\s+more\s+than)\s+(\d+)\s+words?',
        r'(\d+)\s+words?\s+(?:limit|maximum|max)',
        r'keep\s+(?:it\s+)?(?:under|below)\s+(\d+)\s+words?',
        r'word\s+count\s+(?:should\s+be\s+)?(?:under|below|less\s+than)\s+(\d+)',
        r'reduce\s+to\s+(\d+)\s+words?\s+or\s+fewer'
    ],
    'word_count_min': [
        r'(?:should\s+be\s+at\s+least|minimum\s+of|min\s+of|at\s+least)\s+(\d+)\s+words?',
        r'(\d+)\s+words?\s+(?:minimum|min)',
        r'expand\s+to\s+(?:at\s+least\s+)?(\d+)\s+words?',
        r'need(?:s)?\s+(?:at\s+least\s+)?(\d+)\s+more\s+words?'
    ],
    'sentence_count': [
        r'(?:should\s+not\s+exceed|limit\s+to|maximum\s+of|max\s+of)\s+(\d+)\s+sentences?',
        r'(\d+)\s+sentences?\s+(?:limit|maximum|max)',
        r'keep\s+to\s+(\d+)\s+sentences?\s+or\s+fewer'
    ],
    'character_limit': [
        r'(?:should\s+not\s+exceed|limit\s+to|maximum\s+of)\s+(\d+)\s+characters?',
        r'(\d+)\s+characters?\s+(?:limit|maximum|max)'
    ],
    'formatting': [
        r'(?:make\s+|format\s+(?:as\s+)?|should\s+be\s+)(bold|italic|underlined?)',
        r'(?:use\s+|apply\s+)(bullet\s+points?|numbered\s+list|headings?)',
        r'(?:convert\s+to\s+|format\s+as\s+)(heading\s*\d?|title|subtitle)'
    ],
    'style': [
        r'(?:use\s+|write\s+in\s+|make\s+it\s+)(formal|informal|academic|conversational)\s+(?:tone|style)',
        r'(?:be\s+more\s+|make\s+it\s+)(concise|detailed|specific|general)',
        r'(?:use\s+)(active|passive)\s+voice',
        r'(?:write\s+in\s+)(first|second|third)\s+person'
    ],
    'content_requirements': [
        r'(?:add|include|mention)\s+(.+?)(?:\.|$)',
        r'(?:remove|delete|omit)\s+(.+?)(?:\.|$)',
        r'(?:explain|describe|elaborate\s+on)\s+(.+?)(?:\.|$)',
        r'(?:provide\s+examples?\s+(?:of|for))\s+(.+?)(?:\.|$)'
    ]
}


class ConstraintDetector:
    """Detect and validate specific constraints mentioned in comments"""
    
    def __init__(self):
        self.constraint_patterns = CONSTRAINT_PATTERNS
    
    def detect_constraints(self, comment_text: str) -> Dict[str, Any]:
        """Detect all constraints mentioned in a comment"""
        constraints = {}
        comment_lower = comment_text.lower().strip()
        
        # Word count constraints
        for pattern in self.constraint_patterns['word_count']:
            matches = re.finditer(pattern, comment_lower, re.IGNORECASE)
            for match in matches:
                limit = int(match.group(1))
                constraints['word_count_max'] = limit
                break
        
        # Minimum word count
        for pattern in self.constraint_patterns['word_count_min']:
            matches = re.finditer(pattern, comment_lower, re.IGNORECASE)
            for match in matches:
                limit = int(match.group(1))
                constraints['word_count_min'] = limit
                break
        
        # Sentence count constraints
        for pattern in self.constraint_patterns['sentence_count']:
            matches = re.finditer(pattern, comment_lower, re.IGNORECASE)
            for match in matches:
                limit = int(match.group(1))
                constraints['sentence_count_max'] = limit
                break
        
        # Character limit constraints
        for pattern in self.constraint_patterns['character_limit']:
            matches = re.finditer(pattern, comment_lower, re.IGNORECASE)
            for match in matches:
                limit = int(match.group(1))
                constraints['character_limit_max'] = limit
                break
        
        # Formatting constraints
        for pattern in self.constraint_patterns['formatting']:
            matches = re.finditer(pattern, comment_lower, re.IGNORECASE)
            for match in matches:
                if 'formatting_requirements' not in constraints:
                    constraints['formatting_requirements'] = []
                constraints['formatting_requirements'].append(match.group(1))
        
        # Style constraints
        for pattern in self.constraint_patterns['style']:
            matches = re.finditer(pattern, comment_lower, re.IGNORECASE)
            for match in matches:
                if 'style_requirements' not in constraints:
                    constraints['style_requirements'] = []
                constraints['style_requirements'].append(match.group(1))
        
        # Content requirements
        for pattern in self.constraint_patterns['content_requirements']:
            matches = re.finditer(pattern, comment_lower, re.IGNORECASE)
            for match in matches:
                if 'content_requirements' not in constraints:
                    constraints['content_requirements'] = []
                requirement_text = match.group(1).strip()
                if len(requirement_text) > 3:  # Avoid capturing tiny fragments
                    constraints['content_requirements'].append(requirement_text)
        
        return constraints
    
    def validate_constraints(self, constraints: Dict[str, Any], original_text: str, edited_text: str) -> Dict[str, Any]:
        """Validate whether the edited text meets the detected constraints"""
        validation_results = {
            'constraints_detected': len(constraints) > 0,
            'total_constraints': len(constraints),
            'violations': [],
            'compliance_score': 1.0,
            'constraint_details': {}
        }
        
        if not constraints:
            return validation_results
        
        violations = []
        
        # Validate word count constraints
        if 'word_count_max' in constraints:
            word_count = len(edited_text.split())
            max_words = constraints['word_count_max']
            validation_results['constraint_details']['word_count'] = {
                'actual': word_count,
                'max_allowed': max_words,
                'compliant': word_count <= max_words
            }
            if word_count > max_words:
                violations.append(f"Word count {word_count} exceeds limit of {max_words}")
        
        if 'word_count_min' in constraints:
            word_count = len(edited_text.split())
            min_words = constraints['word_count_min']
            validation_results['constraint_details']['word_count_min'] = {
                'actual': word_count,
                'min_required': min_words,
                'compliant': word_count >= min_words
            }
            if word_count < min_words:
                violations.append(f"Word count {word_count} below minimum of {min_words}")
        
        # Validate sentence count constraints
        if 'sentence_count_max' in constraints:
            sentence_count = len([s for s in edited_text.split('.') if s.strip()])
            max_sentences = constraints['sentence_count_max']
            validation_results['constraint_details']['sentence_count'] = {
                'actual': sentence_count,
                'max_allowed': max_sentences,
                'compliant': sentence_count <= max_sentences
            }
            if sentence_count > max_sentences:
                violations.append(f"Sentence count {sentence_count} exceeds limit of {max_sentences}")
        
        # Validate character limit constraints
        if 'character_limit_max' in constraints:
            char_count = len(edited_text)
            max_chars = constraints['character_limit_max']
            validation_results['constraint_details']['character_count'] = {
                'actual': char_count,
                'max_allowed': max_chars,
                'compliant': char_count <= max_chars
            }
            if char_count > max_chars:
                violations.append(f"Character count {char_count} exceeds limit of {max_chars}")
        
        # Basic content requirement checking (simple keyword matching)
        if 'content_requirements' in constraints:
            content_compliance = []
            for requirement in constraints['content_requirements']:
                # Simple check if the requirement keywords appear in the edited text
                requirement_words = requirement.lower().split()
                edited_lower = edited_text.lower()
                has_keywords = any(word in edited_lower for word in requirement_words if len(word) > 3)
                content_compliance.append({
                    'requirement': requirement,
                    'compliant': has_keywords
                })
                if not has_keywords:
                    violations.append(f"Content requirement not met: {requirement}")
            validation_results['constraint_details']['content_requirements'] = content_compliance
        
        # Calculate overall compliance score
        if violations:
            compliance_score = max(0.0, 1.0 - (len(violations) / len(constraints)))
        else:
            compliance_score = 1.0
        
        validation_results['violations'] = violations
        validation_results['compliance_score'] = compliance_score
        
        return validation_results


class ComplianceFeatureExtractor:
    """Extract features from original text, comment, and edited text for ML model"""
    
    def __init__(self):
        self.vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        self.constraint_detector = ConstraintDetector()
    
    def extract_text_features(self, original: str, comment: str, edited: str) -> Dict:
        """Extract comprehensive features from the text triplet"""
        
        features = {}
        
        # Basic text statistics
        features['original_length'] = len(original)
        features['comment_length'] = len(comment)
        features['edited_length'] = len(edited)
        features['edit_length_ratio'] = len(edited) / max(len(original), 1)
        
        # Edit distance and similarity
        features['edit_distance'] = self._levenshtein_distance(original, edited)
        features['edit_ratio'] = difflib.SequenceMatcher(None, original, edited).ratio()
        
        # Semantic similarity (basic word overlap)
        features['comment_edit_overlap'] = self._word_overlap(comment, edited)
        features['comment_original_overlap'] = self._word_overlap(comment, original)
        
        # Sentiment analysis
        try:
            original_sentiment = TextBlob(original).sentiment
            comment_sentiment = TextBlob(comment).sentiment
            edited_sentiment = TextBlob(edited).sentiment
            
            features['sentiment_change'] = edited_sentiment.polarity - original_sentiment.polarity
            features['comment_sentiment'] = comment_sentiment.polarity
            features['sentiment_alignment'] = abs(edited_sentiment.polarity - comment_sentiment.polarity)
        except:
            # Fallback if TextBlob fails
            features['sentiment_change'] = 0.0
            features['comment_sentiment'] = 0.0
            features['sentiment_alignment'] = 0.0
        
        # Change type detection
        features.update(self._detect_change_types(original, edited))
        
        # Comment intent matching
        features.update(self._analyze_comment_intent(comment, original, edited))
        
        # NEW: Constraint-based features
        constraint_features = self._extract_constraint_features(comment, original, edited)
        features.update(constraint_features)
        
        return features
    
    def _extract_constraint_features(self, comment: str, original: str, edited: str) -> Dict:
        """Extract features related to specific constraints mentioned in comments"""
        features = {}
        
        # Detect constraints in comment
        constraints = self.constraint_detector.detect_constraints(comment)
        
        # Basic constraint detection features
        features['has_constraints'] = len(constraints) > 0
        features['num_constraints'] = len(constraints)
        features['has_word_count_constraint'] = 'word_count_max' in constraints or 'word_count_min' in constraints
        features['has_sentence_constraint'] = 'sentence_count_max' in constraints
        features['has_formatting_constraint'] = 'formatting_requirements' in constraints
        features['has_style_constraint'] = 'style_requirements' in constraints
        features['has_content_constraint'] = 'content_requirements' in constraints
        
        # If constraints detected, validate compliance
        if constraints:
            validation = self.constraint_detector.validate_constraints(constraints, original, edited)
            
            features['constraint_compliance_score'] = validation['compliance_score']
            features['num_constraint_violations'] = len(validation['violations'])
            features['constraint_fully_compliant'] = validation['compliance_score'] >= 1.0
            
            # Specific constraint compliance features
            if 'word_count' in validation['constraint_details']:
                wc_detail = validation['constraint_details']['word_count']
                features['word_count_compliant'] = wc_detail['compliant']
                features['word_count_ratio'] = wc_detail['actual'] / max(wc_detail['max_allowed'], 1)
            
            if 'word_count_min' in validation['constraint_details']:
                wc_min_detail = validation['constraint_details']['word_count_min']
                features['word_count_min_compliant'] = wc_min_detail['compliant']
                features['word_count_min_ratio'] = wc_min_detail['actual'] / max(wc_min_detail['min_required'], 1)
            
            if 'sentence_count' in validation['constraint_details']:
                sc_detail = validation['constraint_details']['sentence_count']
                features['sentence_count_compliant'] = sc_detail['compliant']
            
            # Store validation details for explanation (don't include in ML features)
            # features['_constraint_validation'] = validation  # Commented out - causes ML training issues
        else:
            # No constraints detected - default values
            features['constraint_compliance_score'] = 1.0  # No constraints to violate
            features['num_constraint_violations'] = 0
            features['constraint_fully_compliant'] = True
            features['word_count_compliant'] = True
            features['word_count_min_compliant'] = True
            features['sentence_count_compliant'] = True
        
        return features
    
    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Calculate edit distance between two strings"""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def _word_overlap(self, text1: str, text2: str) -> float:
        """Calculate word overlap ratio between two texts"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0
        return len(words1.intersection(words2)) / len(words1.union(words2))
    
    def _detect_change_types(self, original: str, edited: str) -> Dict:
        """Detect types of changes made"""
        features = {}
        
        # Grammar/spelling changes (basic detection)
        original_words = original.lower().split()
        edited_words = edited.lower().split()
        
        features['word_count_change'] = len(edited_words) - len(original_words)
        features['has_additions'] = len(edited_words) > len(original_words)
        features['has_deletions'] = len(edited_words) < len(original_words)
        
        # Check for common edit patterns
        features['capitalization_changes'] = self._count_capitalization_changes(original, edited)
        features['punctuation_changes'] = self._count_punctuation_changes(original, edited)
        
        return features
    
    def _count_capitalization_changes(self, original: str, edited: str) -> int:
        """Count changes in capitalization"""
        orig_caps = sum(1 for c in original if c.isupper())
        edit_caps = sum(1 for c in edited if c.isupper())
        return abs(edit_caps - orig_caps)
    
    def _count_punctuation_changes(self, original: str, edited: str) -> int:
        """Count changes in punctuation"""
        orig_punct = sum(1 for c in original if c in '.,!?;:')
        edit_punct = sum(1 for c in edited if c in '.,!?;:')
        return abs(edit_punct - orig_punct)
    
    def _analyze_comment_intent(self, comment: str, original: str, edited: str) -> Dict:
        """Analyze if the edit matches comment intent"""
        features = {}
        
        # Keyword-based intent detection
        comment_lower = comment.lower()
        
        # Action keywords in comments
        action_keywords = {
            'grammar': ['grammar', 'spelling', 'typo', 'correct', 'fix'],
            'clarity': ['clear', 'clarify', 'unclear', 'confusing'],
            'style': ['style', 'tone', 'formal', 'informal'],
            'content': ['add', 'remove', 'include', 'expand', 'detail'],
            'structure': ['organize', 'structure', 'rearrange', 'order']
        }
        
        for intent_type, keywords in action_keywords.items():
            features[f'comment_suggests_{intent_type}'] = any(kw in comment_lower for kw in keywords)
        
        # Check if specific words from comment appear in edits
        comment_words = set(re.findall(r'\b\w+\b', comment_lower))
        original_words = set(re.findall(r'\b\w+\b', original.lower()))
        edited_words = set(re.findall(r'\b\w+\b', edited.lower()))
        
        # Words suggested in comment that were added
        suggested_words_added = comment_words.intersection(edited_words - original_words)
        features['suggested_words_implemented'] = len(suggested_words_added) / max(len(comment_words), 1)
        
        return features


class ComplianceClassifier:
    """ML model for predicting comment-edit compliance"""
    
    def __init__(self):
        self.feature_extractor = ComplianceFeatureExtractor()
        self.model = None
        self.feature_names = None
        
    def prepare_training_data(self, data: List[Dict]) -> Tuple[Any, Any]:
        """Prepare training data from comment-edit pairs"""
        features_list = []
        labels = []
        
        for item in data:
            features = self.feature_extractor.extract_text_features(
                item['original_text'],
                item['comment_text'], 
                item['edited_text']
            )
            features_list.append(features)
            labels.append(item['compliance_label'])
        
        # Convert to DataFrame for easier handling
        df = pd.DataFrame(features_list)
        self.feature_names = df.columns.tolist()
        
        return df.values, np.array(labels)
    
    def train(self, training_data: List[Dict]) -> Dict:
        """Train the compliance classifier"""
        X, y = self.prepare_training_data(training_data)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Create and train model
        self.model = RandomForestClassifier(
            n_estimators=100,
            random_state=42,
            class_weight='balanced'
        )
        
        self.model.fit(X_train, y_train)
        
        # Evaluate
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        report = classification_report(y_test, y_pred, output_dict=True)
        
        return {
            'accuracy': accuracy,
            'classification_report': report,
            'feature_importance': dict(zip(self.feature_names, self.model.feature_importances_))
        }
    
    def predict(self, original: str, comment: str, edited: str) -> Dict:
        """Predict compliance for a single comment-edit pair"""
        if self.model is None:
            raise ValueError("Model must be trained before making predictions")
        
        features = self.feature_extractor.extract_text_features(original, comment, edited)
        feature_vector = np.array([[features[name] for name in self.feature_names]])
        
        prediction = self.model.predict(feature_vector)[0]
        probabilities = self.model.predict_proba(feature_vector)[0]
        
        # Map probabilities to class names
        class_probs = dict(zip(self.model.classes_, probabilities))
        
        base_result = {
            'prediction': prediction,
            'confidence': max(probabilities),
            'probabilities': class_probs,
            'compliance_score': class_probs.get('compliant', 0.0)
        }
        
        # Add constraint-specific information if available
        if '_constraint_validation' in features:
            constraint_validation = features['_constraint_validation']
            base_result['constraint_validation'] = constraint_validation
            
            # Adjust compliance score based on constraint violations
            if constraint_validation['violations']:
                # Reduce compliance score if there are constraint violations
                constraint_penalty = len(constraint_validation['violations']) * 0.2
                base_result['compliance_score'] = max(0.0, base_result['compliance_score'] - constraint_penalty)
                
                # Override prediction if there are serious constraint violations
                if len(constraint_validation['violations']) >= 2:
                    base_result['prediction'] = 'non_compliant'
                elif len(constraint_validation['violations']) == 1:
                    base_result['prediction'] = 'partial'
        
        return base_result
    
    def explain_prediction(self, original: str, comment: str, edited: str) -> Dict:
        """Provide explanation for the prediction"""
        features = self.feature_extractor.extract_text_features(original, comment, edited)
        
        # Get feature importances
        feature_importance = dict(zip(self.feature_names, self.model.feature_importances_))
        
        # Find top contributing features
        top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:5]
        
        explanation = {
            'top_features': top_features,
            'feature_values': features,
            'interpretation': self._interpret_features(features, top_features)
        }
        
        # Add constraint-specific explanations
        if '_constraint_validation' in features:
            constraint_validation = features['_constraint_validation']
            explanation['constraint_analysis'] = {
                'constraints_detected': constraint_validation['constraints_detected'],
                'total_constraints': constraint_validation['total_constraints'],
                'violations': constraint_validation['violations'],
                'compliance_score': constraint_validation['compliance_score'],
                'details': constraint_validation['constraint_details']
            }
            
            # Add constraint-specific interpretations
            constraint_interpretations = self._interpret_constraints(constraint_validation)
            explanation['interpretation'].extend(constraint_interpretations)
        
        return explanation
    
    def _interpret_constraints(self, constraint_validation: Dict) -> List[str]:
        """Generate human-readable interpretations of constraint validation results"""
        interpretations = []
        
        if not constraint_validation['constraints_detected']:
            interpretations.append("No specific constraints detected in comment")
            return interpretations
        
        if constraint_validation['violations']:
            interpretations.append(f"Found {len(constraint_validation['violations'])} constraint violation(s)")
            for violation in constraint_validation['violations']:
                interpretations.append(f"⚠️ {violation}")
        else:
            interpretations.append("✅ All detected constraints are satisfied")
        
        # Specific constraint details
        details = constraint_validation['constraint_details']
        
        if 'word_count' in details:
            wc = details['word_count']
            status = "✅" if wc['compliant'] else "❌"
            interpretations.append(f"{status} Word count: {wc['actual']}/{wc['max_allowed']} (max)")
        
        if 'word_count_min' in details:
            wc_min = details['word_count_min']
            status = "✅" if wc_min['compliant'] else "❌"
            interpretations.append(f"{status} Word count: {wc_min['actual']}/{wc_min['min_required']} (min)")
        
        if 'sentence_count' in details:
            sc = details['sentence_count']
            status = "✅" if sc['compliant'] else "❌"
            interpretations.append(f"{status} Sentence count: {sc['actual']}/{sc['max_allowed']} (max)")
        
        if 'character_count' in details:
            cc = details['character_count']
            status = "✅" if cc['compliant'] else "❌"
            interpretations.append(f"{status} Character count: {cc['actual']}/{cc['max_allowed']} (max)")
        
        if 'content_requirements' in details:
            content_reqs = details['content_requirements']
            for req in content_reqs:
                status = "✅" if req['compliant'] else "❌"
                interpretations.append(f"{status} Content requirement: {req['requirement']}")
        
        return interpretations
    
    def _interpret_features(self, features: Dict, top_features: List[Tuple]) -> List[str]:
        """Generate human-readable interpretation of key features"""
        interpretations = []
        
        for feature_name, importance in top_features:
            value = features.get(feature_name, 0)
            
            if feature_name == 'edit_ratio':
                if value > 0.8:
                    interpretations.append("Text changed minimally (high similarity)")
                elif value < 0.3:
                    interpretations.append("Text changed significantly (low similarity)")
            
            elif feature_name == 'comment_edit_overlap':
                if value > 0.5:
                    interpretations.append("Strong word overlap between comment and edit")
                elif value < 0.1:
                    interpretations.append("Little word overlap between comment and edit")
            
            elif feature_name == 'sentiment_alignment':
                if value < 0.2:
                    interpretations.append("Edit sentiment aligns well with comment sentiment")
                elif value > 0.5:
                    interpretations.append("Edit sentiment differs from comment sentiment")
            
            elif feature_name.startswith('comment_suggests_'):
                if value > 0:
                    intent_type = feature_name.replace('comment_suggests_', '')
                    interpretations.append(f"Comment suggests {intent_type} changes")
            
            # NEW: Constraint-related feature interpretations
            elif feature_name == 'has_constraints':
                if value > 0:
                    interpretations.append("Comment contains specific constraints")
                else:
                    interpretations.append("No specific constraints detected in comment")
            
            elif feature_name == 'constraint_compliance_score':
                if value >= 1.0:
                    interpretations.append("All constraints fully satisfied")
                elif value >= 0.5:
                    interpretations.append("Most constraints satisfied")
                else:
                    interpretations.append("Multiple constraint violations")
            
            elif feature_name == 'word_count_compliant':
                if value > 0:
                    interpretations.append("Word count requirement met")
                else:
                    interpretations.append("Word count requirement violated")
            
            elif feature_name == 'has_word_count_constraint':
                if value > 0:
                    interpretations.append("Comment specifies word count limit")
            
            elif feature_name == 'num_constraint_violations':
                if value > 0:
                    interpretations.append(f"Found {int(value)} constraint violation(s)")
        
        return interpretations
    
    def save_model(self, filepath: str):
        """Save trained model to file"""
        model_data = {
            'model': self.model,
            'feature_names': self.feature_names,
            'feature_extractor': self.feature_extractor
        }
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
    
    def load_model(self, filepath: str):
        """Load trained model from file"""
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)
        
        self.model = model_data['model']
        self.feature_names = model_data['feature_names']
        self.feature_extractor = model_data['feature_extractor']


def create_default_training_data():
    """Load comprehensive training data from JSON file"""
    import json
    
    # Load comprehensive training data
    try:
        training_data_path = os.path.join(os.path.dirname(__file__), 'compliance_training_data.json')
        if os.path.exists(training_data_path):
            with open(training_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"[SUCCESS] Loaded comprehensive training data: {len(data)} examples")
                return data
        else:
            print(f"[ERROR] Training data file not found at: {training_data_path}")
            raise FileNotFoundError(f"Training data file not found: {training_data_path}")
    except Exception as e:
        print(f"[ERROR] Error loading comprehensive training data: {e}")
        raise e


def retrain_model_with_comprehensive_data():
    """Force retrain the model with comprehensive data (useful after data updates)"""
    if not ML_DEPENDENCIES_AVAILABLE:
        print("[ERROR] ML dependencies not available. Cannot retrain model.")
        return None
        
    try:
        # Load comprehensive training data
        training_data = create_default_training_data()
        print(f"[INFO] Loaded {len(training_data)} training examples")
        
        # Analyze data distribution
        labels = [item['compliance_label'] for item in training_data]
        from collections import Counter
        distribution = Counter(labels)
        print("[INFO] Data distribution:")
        for label, count in distribution.items():
            percentage = (count / len(training_data)) * 100
            print(f"  - {label}: {count} examples ({percentage:.1f}%)")
        
        # Train new model
        classifier = ComplianceClassifier()
        print("[INFO] Training new model...")
        metrics = classifier.train(training_data)
        
        # Save the trained model
        model_path = 'ml_models/compliance_model.pkl'
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        classifier.save_model(model_path)
        
        # Display training results
        print("[SUCCESS] Model retrained successfully!")
        print(f"[METRICS] Training Accuracy: {metrics['accuracy']:.1%}")
        
        # Show classification report
        if 'classification_report' in metrics:
            report = metrics['classification_report']
            print("[METRICS] Classification Report:")
            for label in ['compliant', 'partial', 'non_compliant']:
                if label in report:
                    precision = report[label]['precision']
                    recall = report[label]['recall']
                    f1 = report[label]['f1-score']
                    print(f"  - {label}: P={precision:.3f}, R={recall:.3f}, F1={f1:.3f}")
        
        # Show top features
        if 'feature_importance' in metrics:
            top_features = sorted(metrics['feature_importance'].items(), key=lambda x: x[1], reverse=True)[:8]
            print("[FEATURES] Top 8 important features:")
            for feature, importance in top_features:
                print(f"  - {feature}: {importance:.3f}")
        
        print(f"[SAVED] Model saved to: {model_path}")
        return classifier
        
    except Exception as e:
        print(f"[ERROR] Error retraining model: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_or_create_default_model():
    """Get existing model or create a new one with comprehensive training data"""
    if not ML_DEPENDENCIES_AVAILABLE:
        print("Warning: ML dependencies not available. Cannot create ML model.")
        return None
        
    model_path = 'ml_models/compliance_model.pkl'
    
    # Try to load existing model first
    if os.path.exists(model_path):
        try:
            classifier = ComplianceClassifier()
            classifier.load_model(model_path)
            print(f"[SUCCESS] Loaded existing ML model from: {model_path}")
            return classifier
        except Exception as e:
            print(f"[WARNING] Could not load existing model: {e}")
            print("[INFO] Creating new model...")
    
    # Create new model with comprehensive training data
    try:
        classifier = ComplianceClassifier()
        training_data = create_default_training_data()
        
        print(f"[TRAINING] Training ML model with {len(training_data)} examples...")
        metrics = classifier.train(training_data)
        
        # Ensure ml_models directory exists
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        classifier.save_model(model_path)
        
        print(f"[SUCCESS] Created ML model with {metrics['accuracy']:.1%} accuracy")
        print(f"[SAVED] Model saved to: {model_path}")
        
        # Display feature importance for top features
        if 'feature_importance' in metrics:
            top_features = sorted(metrics['feature_importance'].items(), key=lambda x: x[1], reverse=True)[:5]
            print("[FEATURES] Top 5 important features:")
            for feature, importance in top_features:
                print(f"  - {feature}: {importance:.3f}")
        
        return classifier
        
    except Exception as e:
        print(f"[ERROR] Could not create ML model: {e}")
        import traceback
        traceback.print_exc()
        return None