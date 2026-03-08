import json, re, os
from typing import Dict, List, Optional, Tuple, Any
from difflib import SequenceMatcher
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate a response from the LLM"""
        pass


# class MockLLMProvider(LLMProvider):
#     """Mock LLM provider for testing without API keys"""
    
#     def generate(self, prompt: str) -> str:
#         prompt_lower = prompt.lower()
        
#         # Semantic comparison responses
#         if "same sensitive user data" in prompt_lower or "semantic comparison" in prompt_lower:
#             return self._mock_semantic_comparison()
        
#         # Parameter mutation responses
#         if "parameter mutation" in prompt_lower or "fuzzing" in prompt_lower or "hidden endpoints" in prompt_lower:
#             return self._mock_parameter_mutation()
        
#         return '{"error": "Unknown prompt type"}'
    
#     def _mock_semantic_comparison(self) -> str:
#         return '''{
#             "contains_same_data": false,
#             "confidence": 0.92,
#             "reasoning": "Document B shows login form while Document A shows user dashboard with PII",
#             "data_types_missing": ["email", "phone", "address", "payment_info"],
#             "is_error_page": false,
#             "is_login_redirect": true
#         }'''
    
#     def _mock_parameter_mutation(self) -> str:
#         return '''{
#             "suggested_mutations": [
#                 {
#                     "original": "/api/v1/users/profile",
#                     "mutated": "/api/v1/admin/profile",
#                     "reasoning": "Testing privilege escalation by replacing 'users' with 'admin'",
#                     "expected_behavior": "Should return 403 if properly protected"
#                 },
#                 {
#                     "original": "/api/v1/users/123",
#                     "mutated": "/api/v1/users/124",
#                     "reasoning": "IDOR test - sequential ID access",
#                     "expected_behavior": "Should only return data if user 124 is authorized"
#                 },
#                 {
#                     "original": "/api/v1/users/profile",
#                     "mutated": "/api/v1/internal/users/profile",
#                     "reasoning": "Hidden internal endpoint pattern",
#                     "expected_behavior": "May expose additional fields"
#                 }
#             ],
#             "confidence": 0.85
#         }'''


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        import os
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.client = None
        self._init_client()
    
    def _init_client(self):
        try:
            from openai import OpenAI
            if self.api_key:
                self.client = OpenAI(api_key=self.api_key)
        except ImportError:
            pass
    
    def generate(self, prompt: str) -> str:
        if not self.client:
            return '{"error": "OpenAI client not initialized"}'
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1500
            )
            return response.choices[0].message.content
        except Exception as e:
            return f'{{"error": "{str(e)}"}}'
        

class OpenRouterProvider(LLMProvider):
    # default oss-120b
    def __init__(self, api_key: Optional[str] = None, model = "openrouter/free"):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model
        self._init_client()
    
    def _init_client(self):
        try:
            from openrouter import OpenRouter
            self.client = OpenRouter(api_key=self.api_key)

            print("openrouter initiated")
        except ImportError:
            pass

    def generate(self, prompt: str) -> str:
        try:
            response = self.client.chat.send(
            model=self.model,
            messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            return response.choices[0].message.content
        except Exception as e:
            return f'{{"error": "{str(e)}}}'


class GroqProvider(LLMProvider):
    # default oss-120b
    def __init__(self, api_key: Optional[str] = None, model = "llama-3.3-70b-versatile"):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model
        self._init_client()
    
    def _init_client(self):
        try:
            from groq import Groq
            self.client = Groq(api_key=self.api_key)
        except ImportError:
            print("import groq error, did you pip install groq?")
            pass

    def generate(self, prompt: str) -> str:
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=1,
                max_completion_tokens=20480,
                top_p=1,
                stream=False,
                stop=None,
            )

            return completion.choices[0].message.content
        
        except Exception as e:
            return f'{{"error": "{str(e)}}}'
        
class OpenAICompatibleProvider(LLMProvider):
    """OpenAI Compatible GPT provider"""
    def __init__(self, base_url: str, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        import os
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.base_url = base_url
        self.client = None
        self._init_client()
    
    def _init_client(self):
        try:
            from openai import OpenAI
            if self.api_key:
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        except ImportError:
            pass
    
    def generate(self, prompt: str) -> str:
        if not self.client:
            return '{"error": "OpenAI client not initialized"}'
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                # temperature=0.1,
                # max_tokens=102400
            )

            return response.choices[0].message.content
        except Exception as e:
            return f'{{"error": "{str(e)}"}}'

class AIEngine:
    """
    AI Engine with two core features:
    1. Semantic State Comparison
    2. Intelligent Parameter Mutation
    """
    
    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        self.provider = llm_provider or self._get_default_provider()
    
    def _get_default_provider(self) -> LLMProvider:
        """Auto-select the best available LLM provider"""
        try:
            provider = OpenAIProvider()
            if provider.client:
                print("[AI Engine] Using OpenAIProvider")
                return provider
        except:
            pass

    # Semantic State Comparison
    def compare_dom_snapshots(
        self, 
        user_a_html: str, 
        user_b_html: str,
        user_a_role: str = "owner",
        user_b_role: str = "tester",
        url: str = ""
    ) -> Dict:
        """
        Compare two DOM snapshots semantically to determine if User B accessed
        the same sensitive data as User A, or if it's just an error/login page.
        
        Args:
            user_a_html: HTML response from the privileged user (ground truth)
            user_b_html: HTML response from the testing user (to verify)
            user_a_role: Role name of user A
            user_b_role: Role name of user B
            url: The URL being compared
            
        Returns:
            Dict with comparison results:
            - contains_same_data: bool - Does B have same data as A?
            - confidence: float - AI confidence score
            - reasoning: str - Explanation of the decision
            - data_types_missing: List[str] - What sensitive data is missing
            - is_error_page: bool - Is this an error page?
            - is_login_redirect: bool - Is this a login redirect?
        """
        # Pre-process HTML to extract key elements
        user_a_summary = self._extract_page_summary(user_a_html)
        user_b_summary = self._extract_page_summary(user_b_html)
        
        # Quick text similarity check
        text_similarity = SequenceMatcher(
            None, 
            user_a_summary['text_content'], 
            user_b_summary['text_content']
        ).ratio()
        
        # If very similar, likely same content
        if text_similarity > 0.95:
            return {
                "contains_same_data": True,
                "confidence": text_similarity,
                "reasoning": "Pages are textually identical (>95% similarity)",
                "data_types_missing": [],
                "is_error_page": False,
                "is_login_redirect": False,
                "similarity_score": text_similarity
            }
        
        # If very different, use AI to analyze
        prompt = f"""
You are a security analysis AI comparing two HTML documents to detect access control violations.

URL Being Tested: {url}
User A (Privileged - {user_a_role}): Has legitimate access
User B (Testing - {user_b_role}): Attempting access

USER A'S PAGE SUMMARY:
Title: {user_a_summary['title']}
Headings: {user_a_summary['headings']}
Form Fields: {user_a_summary['form_fields']}
Data Indicators: {user_a_summary['data_indicators']}
Text Preview: {user_a_summary['text_content'][:500]}

USER B'S PAGE SUMMARY:
Title: {user_b_summary['title']}
Headings: {user_b_summary['headings']}
Form Fields: {user_b_summary['form_fields']}
Data Indicators: {user_b_summary['data_indicators']}
Text Preview: {user_b_summary['text_content'][:500]}

Analyze if User B's page contains the SAME sensitive user data as User A's page,
or if it's merely an empty UI shell, error message, or login redirect.

Respond in JSON format:
{{
    "contains_same_data": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "detailed explanation",
    "data_types_missing": ["email", "phone", "address", etc],
    "is_error_page": true/false,
    "is_login_redirect": true/false,
    "indicators": ["list of key differences"]
}}
"""
        
        response = self.provider.generate(prompt)
        
        try:
            # Extract JSON from response
            json_match = re.search(r'\{{.*\}}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(response)
            
            result['similarity_score'] = text_similarity
            return result
            
        except json.JSONDecodeError:
            # Fallback: use text similarity
            return {
                "contains_same_data": text_similarity > 0.8,
                "confidence": text_similarity,
                "reasoning": f"Text similarity: {text_similarity:.2%}",
                "data_types_missing": [],
                "is_error_page": "error" in user_b_summary['title'].lower(),
                "is_login_redirect": "login" in user_b_summary['title'].lower(),
                "similarity_score": text_similarity
            }
    
    def _extract_page_summary(self, html: str) -> Dict:
        """Extract key elements from HTML for comparison"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Extract key data
            title = soup.title.string if soup.title else ""
            headings = [h.get_text(strip=True) for h in soup.find_all(['h1', 'h2', 'h3'])][:5]
            
            # Find form fields
            forms = soup.find_all('form')
            form_fields = []
            for form in forms:
                inputs = form.find_all(['input', 'textarea', 'select'])
                form_fields.extend([i.get('name', i.get('id', 'unnamed')) for i in inputs])
            
            # Look for data indicators (PII patterns)
            text = soup.get_text(separator=' ', strip=True)
            data_indicators = []
            
            # Check for common data patterns
            if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text):
                data_indicators.append("email")
            if re.search(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', text):
                data_indicators.append("phone")
            if re.search(r'\$[\d,]+\.?\d*', text):
                data_indicators.append("payment")
            if re.search(r'\b\d{1,5}\s+\w+\s+(street|st|avenue|ave|road|rd|boulevard|blvd)', text, re.I):
                data_indicators.append("address")
            if re.search(r'(password|credit.?card|ssn|social.?security)', text, re.I):
                data_indicators.append("sensitive_keywords")
            
            return {
                'title': title,
                'headings': headings,
                'form_fields': list(set(form_fields)),
                'data_indicators': data_indicators,
                'text_content': text[:2000]  # Limit text length
            }
        except ImportError:
            # Fallback: regex-based extraction when BeautifulSoup not available
            return self._extract_with_regex(html)
        except Exception as e:
            return {
                'title': '',
                'headings': [],
                'form_fields': [],
                'data_indicators': [],
                'text_content': html[:1000],
                'error': str(e)
            }
    
    def _extract_with_regex(self, html: str) -> Dict:
        """Fallback HTML extraction using regex when BeautifulSoup unavailable"""
        # Extract title
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.I | re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""
        
        # Extract headings
        headings = re.findall(r'<h[1-3][^>]*>(.*?)</h[1-3]>', html, re.I | re.DOTALL)
        headings = [re.sub(r'<[^>]+>', '', h).strip() for h in headings[:5]]
        
        # Extract form fields
        inputs = re.findall(r'<input[^>]*name=["\']([^"\']+)["\']', html, re.I)
        inputs += re.findall(r'<input[^>]*id=["\']([^"\']+)["\']', html, re.I)
        
        # Get text content (remove tags)
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.I | re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.I | re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Detect data indicators
        data_indicators = []
        if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text):
            data_indicators.append("email")
        if re.search(r'\$[\d,]+\.?\d*', text):
            data_indicators.append("payment")
        if re.search(r'(password|credit.?card|ssn)', text, re.I):
            data_indicators.append("sensitive_keywords")
        
        return {
            'title': title,
            'headings': headings,
            'form_fields': list(set(inputs)),
            'data_indicators': data_indicators,
            'text_content': text[:2000]
        }
    
    # Intelligent Parameter Mutation (AI Fuzzing)
    def generate_parameter_mutations(
        self, 
        url: str,
        method: str = "GET",
        request_data: Optional[Dict] = None,
        context: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Use AI to analyze URLs and request data to suggest hidden API endpoints
        or ID parameter mutations for testing IDOR and privilege escalation.
        
        Args:
            url: The discovered URL to mutate
            method: HTTP method
            request_data: Optional request body/payload
            context: Additional context (role, headers, etc.)
            
        Returns:
            List of mutation suggestions:
            - original: The original URL
            - mutated: The suggested mutation
            - reasoning: Why this mutation was suggested
            - expected_behavior: What response to expect
            - risk_level: LOW/MEDIUM/HIGH/CRITICAL
        """
        prompt = f"""
You are an expert penetration tester performing intelligent fuzzing to discover hidden endpoints.

ORIGINAL ENDPOINT:
URL: {url}
Method: {method}
Request Data: {json.dumps(request_data) if request_data else 'None'}
Context: {json.dumps(context) if context else 'None'}

Analyze this endpoint and suggest parameter mutations to test for:
1. IDOR (Insecure Direct Object Reference) vulnerabilities
2. Hidden admin/internal endpoints
3. Privilege escalation paths
4. Debug/backdoor endpoints

For each mutation, provide:
- The mutated URL/parameter
- Reasoning for why this mutation makes sense
- Expected behavior if properly protected
- Risk level

Respond in JSON format:
{{
    "suggested_mutations": [
        {{
            "original": "{url}",
            "mutated": "suggested URL",
            "mutated_params": {{"key": "value"}},
            "reasoning": "why this mutation",
            "expected_behavior": "expected response",
            "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
            "attack_type": "IDOR|PRIVILEGE_ESCALATION|HIDDEN_ENDPOINT|DEBUG"
        }}
    ],
    "confidence": 0.0-1.0,
    "analysis_summary": "overall assessment"
}}

Common mutation patterns to consider:
- Replace 'user' with 'admin', 'internal', 'system', 'root'
- Change IDs: /users/123 → /users/1, /users/0, /users/-1
- Add hidden parameters: ?debug=1, ?admin=true, ?internal=true
- Path traversal: /api/users → /api/admin/users, /api/internal/users
- HTTP method switching: GET → POST, PUT, DELETE, PATCH
- Version changes: /v1/ → /v2/, /beta/, /internal/
"""
        
        response = self.provider.generate(prompt)
        
        try:
            json_match = re.search(r'\{{.*\}}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(response)
            
            return result.get('suggested_mutations', [])
            
        except json.JSONDecodeError:
            # Fallback: generate basic mutations
            return self._generate_fallback_mutations(url, method)
    
    def batch_generate_parameter_mutations(self, discovered_urls: List[str]):
        url_list_text = "\n".join([f"- {url}" for url in discovered_urls])

        """
        Use AI to analyze URLs and request data to suggest hidden API endpoints
        or ID parameter mutations for testing IDOR and privilege escalation.
        
        Args:
            url: The discovered URL to mutate
            
        Returns:
            List of mutation suggestions:
            - original: The original URL
            - mutated: The suggested mutation
            - reasoning: Why this mutation was suggested
            - expected_behavior: What response to expect
            - risk_level: LOW/MEDIUM/HIGH/CRITICAL
        """
        prompt = f"""
You are an expert penetration tester analyzing {len(discovered_urls)} endpoints simultaneously.

ENDPOINTS TO ANALYZE:
{url_list_text}

For EACH endpoint, suggest mutations following the same JSON schema.
Return a single JSON object with a "mutations_by_endpoint" key containing
a dictionary where keys are URLs and values are arrays of mutation objects.

Respond in JSON format:
{{
    "mutations_by_endpoint": {{
        "URL": [
            {{
                "original": "URL",
                "mutated": "suggested URL",
                "mutated_params": {{"key": "value"}},
                "reasoning": "why this mutation",
                "expected_behavior": "expected response",
                "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
                "attack_type": "IDOR|PRIVILEGE_ESCALATION|HIDDEN_ENDPOINT|DEBUG"
            }}
        ],
    }}
    "confidence": 0.0-1.0,
    "analysis_summary": "overall assessment"
}}

Common mutation patterns to consider:
- Replace 'user' with 'admin', 'internal', 'system', 'root'
- Change IDs: /users/123 → /users/1, /users/0, /users/-1
- Add hidden parameters: ?debug=1, ?admin=true, ?internal=true
- Path traversal: /api/users → /api/admin/users, /api/internal/users
- HTTP method switching: GET → POST, PUT, DELETE, PATCH
- Version changes: /v1/ → /v2/, /beta/, /internal/
"""
        
        response = self.provider.generate(prompt)
        
        try:
            # Try to extract JSON block from response
            json_match = re.search(r'```json\s*(.*?)\s*```', response, flags=re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                # Try parsing the raw response directly
                result = json.loads(response.strip())
            
            return result.get('mutations_by_endpoint', [])

        except json.JSONDecodeError:
            print("failed")
            return {}

    # dummy testing
    def _generate_fallback_mutations(self, url: str, method: str) -> List[Dict]:
        """Generate basic mutations when AI fails"""
        mutations = []
        
        # Common path replacements
        replacements = [
            ('user', 'admin'),
            ('user', 'internal'),
            ('api', 'api/internal'),
            ('api/v1', 'api/v2'),
            ('api/v1', 'api/admin'),
            ('profile', 'admin/profile'),
            ('profile', 'internal/profile'),
        ]
        
        for old, new in replacements:
            if old in url.lower():
                mutated = url.lower().replace(old, new)
                mutations.append({
                    "original": url,
                    "mutated": mutated,
                    "mutated_params": {},
                    "reasoning": f"Replace '{old}' with '{new}' to test for hidden endpoints",
                    "expected_behavior": "Should return 403 if properly protected",
                    "risk_level": "HIGH",
                    "attack_type": "HIDDEN_ENDPOINT"
                })
        
        # ID mutations for numeric IDs
        id_patterns = re.findall(r'/\d+', url)
        for pattern in id_patterns:
            base_id = int(pattern[1:])
            for offset in [-1, 0, 1, 2]:
                new_id = base_id + offset
                mutated = url.replace(pattern, f'/{new_id}')
                if mutated != url:
                    mutations.append({
                        "original": url,
                        "mutated": mutated,
                        "mutated_params": {},
                        "reasoning": f"IDOR test with ID {new_id} (offset {offset})",
                        "expected_behavior": "Should only return data if user is authorized for this ID",
                        "risk_level": "CRITICAL",
                        "attack_type": "IDOR"
                    })
        
        return mutations
    
    def batch_compare_snapshots(
        self, 
        comparisons: List[Tuple[str, str, str, str, str]]
    ) -> List[Dict]:
        """
        Batch process multiple DOM snapshot comparisons.
        
        Args:
            comparisons: List of tuples (url, user_a_html, user_b_html, role_a, role_b)
            
        Returns:
            List of comparison results
        """
        results = []
        for url, html_a, html_b, role_a, role_b in comparisons:
            result = self.compare_dom_snapshots(html_a, html_b, role_a, role_b, url)
            result['url'] = url
            results.append(result)
        return results
    
    def generate_fuzzing_campaign(
        self, 
        discovered_urls: List[str],
        roles: List[str]
    ) -> Dict:
        """
        Generate a complete fuzzing campaign based on discovered URLs.
        
        Returns:
            Dict with test cases organized by attack type
        """
        all_mutations = []
        
        # original single prompt
        # for url in discovered_urls:
        #     mutations = self.generate_parameter_mutations(url)
        #     all_mutations.extend(mutations)
        
        # new batch prompt
        mutations = self.batch_generate_parameter_mutations(discovered_urls)
        for distinct_url_mutations in mutations.values():
            all_mutations.extend(distinct_url_mutations)
        
        # Organize by attack type
        campaign = {
            "idor_tests": [],
            "privilege_escalation_tests": [],
            "hidden_endpoint_tests": [],
            "debug_tests": [],
            "total_mutations": len(all_mutations)
        }
        
        for mutation in all_mutations:
            attack_type = mutation.get('attack_type', 'UNKNOWN')
            if attack_type == 'IDOR':
                campaign['idor_tests'].append(mutation)
            elif attack_type == 'PRIVILEGE_ESCALATION':
                campaign['privilege_escalation_tests'].append(mutation)
            elif attack_type == 'HIDDEN_ENDPOINT':
                campaign['hidden_endpoint_tests'].append(mutation)
            elif attack_type == 'DEBUG':
                campaign['debug_tests'].append(mutation)
        
        return campaign


# testing code
if __name__ == "__main__":
    print("=" * 70)
    print("AI Engine for Agentic Prompts - Demo")
    print("Features: Semantic State Comparison | Intelligent Parameter Mutation")
    print("=" * 70)
    
    groqProvider = GroqProvider()
    engine = AIEngine(llm_provider=groqProvider)
    
    # Demo 1: Semantic State Comparison
    print("\n1. SEMANTIC STATE COMPARISON")
    print("-" * 70)
    
    # Simulate User A's dashboard (privileged)
    user_a_html = """
    <html>
    <head><title>User Dashboard</title></head>
    <body>
        <h1>Welcome John Doe</h1>
        <div class="profile">
            <p>Email: john.doe@example.com</p>
            <p>Phone: 555-1234</p>
            <p>Address: 123 Main St, City</p>
            <p>Credit Card: ****1234</p>
        </div>
    </body>
    </html>
    """
    
    # Simulate User B's response (unauthorized - login page)
    user_b_html = """
    <html>
    <head><title>Login - Please Sign In</title></head>
    <body>
        <h1>Login</h1>
        <form action="/login" method="post">
            <input type="text" name="username" placeholder="Username">
            <input type="password" name="password" placeholder="Password">
            <button type="submit">Login</button>
        </form>
    </body>
    </html>
    """
    
    result = engine.compare_dom_snapshots(
        user_a_html,
        user_b_html,
        user_a_role="authenticated_user",
        user_b_role="guest",
        url="/user/profile"
    )
    
    print(f"URL: /user/profile")
    print(f"Contains Same Data: {result['contains_same_data']}")
    print(f"Confidence: {result['confidence']:.0%}")
    print(f"Reasoning: {result['reasoning']}")
    print(f"Is Login Redirect: {result.get('is_login_redirect', False)}")
    
    # Demo 2: Parameter Mutation
    print("\n2. INTELLIGENT PARAMETER MUTATION")
    print("-" * 70)
    
    discovered_urls = [
        "/api/v1/users/profile",
        "/api/v1/users/123",
        "/api/v1/orders/456"
    ]
    
    print("Discovered URLs:")
    for url in discovered_urls:
        print(f"  - {url}")
    
    print("\nGenerated Mutations:")
    campaign = engine.generate_fuzzing_campaign(discovered_urls, ["user", "admin"])
    
    for mutation in campaign['idor_tests'][:2]:
        print(f"\n  [IDOR] {mutation['original']}")
        print(f"         → {mutation['mutated']}")
        print(f"         Reason: {mutation['reasoning']}")
    
    for mutation in campaign['hidden_endpoint_tests'][:2]:
        print(f"\n  [Hidden] {mutation['original']}")
        print(f"           → {mutation['mutated']}")
        print(f"           Reason: {mutation['reasoning']}")
    
    print(f"\nTotal Mutations Generated: {campaign['total_mutations']}")
    
    print("\n" + "=" * 70)
    print("Demo complete! AI Engine is ready for use.")
    print("=" * 70)
