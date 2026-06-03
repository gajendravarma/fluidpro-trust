import re
from difflib import SequenceMatcher

class CompanyMatcher:
    """Match company names between Pulseway and ManageEngine using fuzzy matching"""
    
    @staticmethod
    def normalize_name(name):
        """Normalize company name for matching"""
        if not name:
            return ""
        
        # Convert to lowercase and remove common suffixes/prefixes
        normalized = name.lower().strip()
        
        # Remove common business suffixes
        suffixes = ['ltd', 'limited', 'pvt', 'private', 'inc', 'corp', 'corporation', 'llc']
        for suffix in suffixes:
            normalized = re.sub(rf'\b{suffix}\b', '', normalized)
        
        # Remove extra spaces and punctuation
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    @staticmethod
    def similarity(name1, name2):
        """Calculate similarity between two company names"""
        norm1 = CompanyMatcher.normalize_name(name1)
        norm2 = CompanyMatcher.normalize_name(name2)
        
        if not norm1 or not norm2:
            return 0.0
        
        # Exact match after normalization
        if norm1 == norm2:
            return 1.0
        
        # Check if one contains the other
        if norm1 in norm2 or norm2 in norm1:
            return 0.9
        
        # Check word overlap
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        
        if words1 and words2:
            overlap = len(words1.intersection(words2))
            total = len(words1.union(words2))
            word_similarity = overlap / total
            
            if word_similarity > 0.5:
                return word_similarity
        
        # Use sequence matcher for character similarity
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    @staticmethod
    def find_best_match(target_name, candidate_names, threshold=0.6):
        """Find the best matching company name from candidates"""
        best_match = None
        best_score = 0.0
        
        for candidate in candidate_names:
            score = CompanyMatcher.similarity(target_name, candidate)
            if score > best_score and score >= threshold:
                best_score = score
                best_match = candidate
        
        return best_match, best_score
    
    @staticmethod
    def get_company_mappings():
        """Get predefined company mappings for common variations"""
        return {
            # Pulseway name -> ManageEngine variations
            'MarketXcel': ['Market Xcel', 'MarketXcel', 'market excel', 'mx'],
            'CG Logistics': ['CGL', 'C G Logistics', 'CG Logistics', 'cgl logistics'],
            'Digtinctive Pune': ['Digtinctive', 'Digtinctive Pune', 'distinctive'],
            'Aiqmen': ['Aiqmen', 'Aquimen'],
            'FIICC': ['FIICC', 'FIC', 'FICC'],
            'SOC': ['SOC', 'SOC Alerts']
        }
    
    @staticmethod
    def match_company(pulseway_company, manageengine_companies):
        """Match a Pulseway company name to ManageEngine companies"""
        
        # First try exact mappings
        mappings = CompanyMatcher.get_company_mappings()
        if pulseway_company in mappings:
            for me_company in manageengine_companies:
                for variation in mappings[pulseway_company]:
                    if CompanyMatcher.similarity(variation, me_company) > 0.8:
                        return me_company
        
        # Then try fuzzy matching
        best_match, score = CompanyMatcher.find_best_match(
            pulseway_company, manageengine_companies, threshold=0.6
        )
        
        return best_match if best_match else pulseway_company
