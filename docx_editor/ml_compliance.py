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


class ComplianceFeatureExtractor:
    """Extract features from original text, comment, and edited text for ML model"""
    
    def __init__(self):
        self.vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
    
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
        
        return {
            'prediction': prediction,
            'confidence': max(probabilities),
            'probabilities': class_probs,
            'compliance_score': class_probs.get('compliant', 0.0)
        }
    
    def explain_prediction(self, original: str, comment: str, edited: str) -> Dict:
        """Provide explanation for the prediction"""
        features = self.feature_extractor.extract_text_features(original, comment, edited)
        
        # Get feature importances
        feature_importance = dict(zip(self.feature_names, self.model.feature_importances_))
        
        # Find top contributing features
        top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            'top_features': top_features,
            'feature_values': features,
            'interpretation': self._interpret_features(features, top_features)
        }
    
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
    """Create sample training data for initial model"""
    return [
        # Compliant examples
        {
            'original_text': "The system is working fine.",
            'comment_text': "Please fix the grammar - use 'functioning' instead of 'working'",
            'edited_text': "The system is functioning fine.",
            'compliance_label': 'compliant'
        },
        {
            'original_text': "We need data.",
            'comment_text': "Be more specific about what kind of data",
            'edited_text': "We need customer behavioral data and sales metrics.",
            'compliance_label': 'compliant'
        },
        {
            'original_text': "Users like the feature.",
            'comment_text': "Add statistics to support this claim",
            'edited_text': "85% of surveyed users reported liking the feature.",
            'compliance_label': 'compliant'
        },
        {
            'original_text': "The process takes time.",
            'comment_text': "Specify how long it takes",
            'edited_text': "The process takes approximately 2-3 hours to complete.",
            'compliance_label': 'compliant'
        },
        {
            'original_text': "The application runs slowly.",
            'comment_text': "Please add details about performance metrics",
            'edited_text': "The application runs slowly, with average response times of 3-5 seconds.",
            'compliance_label': 'compliant'
        },
        {
            'original_text': "Customer feedback is positive.",
            'comment_text': "Include specific feedback examples",
            'edited_text': "Customer feedback is positive, with users praising the intuitive interface and fast loading times.",
            'compliance_label': 'compliant'
        },
        
        # Partial compliance examples
        {
            'original_text': "It's broken.",
            'comment_text': "Explain what's broken and how to fix it",
            'edited_text': "It's not working properly.",  # Still vague
            'compliance_label': 'partial'
        },
        {
            'original_text': "The weather is nice today.",
            'comment_text': "Please fix the grammar",
            'edited_text': "The weather is nice today and sunny.",  # Added content but didn't fix non-existent grammar
            'compliance_label': 'partial'
        },
        {
            'original_text': "Sales went up.",
            'comment_text': "Add specific numbers and timeframe",
            'edited_text': "Sales increased significantly.",  # Better but still no numbers
            'compliance_label': 'partial'
        },
        {
            'original_text': "The meeting was good.",
            'comment_text': "Provide details about what was discussed",
            'edited_text': "The meeting was productive.",  # Better word but no details
            'compliance_label': 'partial'
        },
        
        # Non-compliant examples  
        {
            'original_text': "The results were good.",
            'comment_text': "Please be more specific about the results",
            'edited_text': "The weather was nice.",  # Completely changed topic
            'compliance_label': 'non_compliant'
        },
        {
            'original_text': "We should implement the feature.",
            'comment_text': "Explain the technical requirements",
            'edited_text': "I like chocolate ice cream.",  # Completely unrelated
            'compliance_label': 'non_compliant'
        },
        {
            'original_text': "The report is finished.",
            'comment_text': "Add the submission deadline",
            'edited_text': "The cat is sleeping.",  # Completely different content
            'compliance_label': 'non_compliant'
        },
        {
            'original_text': "Performance improved.",
            'comment_text': "Add percentage improvement and metrics",
            'edited_text': "Blue is my favorite color.",  # Irrelevant change
            'compliance_label': 'non_compliant'
        }
    ]


def get_or_create_default_model():
    """Get existing model or create a new one with default training data"""
    if not ML_DEPENDENCIES_AVAILABLE:
        print("Warning: ML dependencies not available. Cannot create ML model.")
        return None
        
    model_path = 'ml_models/compliance_model.pkl'
    
    if os.path.exists(model_path):
        try:
            classifier = ComplianceClassifier()
            classifier.load_model(model_path)
            return classifier
        except Exception as e:
            print(f"Warning: Could not load existing model: {e}")
    
    # Create new model with default training data
    try:
        classifier = ComplianceClassifier()
        training_data = create_default_training_data()
        
        metrics = classifier.train(training_data)
        classifier.save_model(model_path)
        print(f"Created default ML model with accuracy: {metrics['accuracy']:.2f}")
        return classifier
    except Exception as e:
        print(f"Warning: Could not create default ML model: {e}")
        return None