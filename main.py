from crawler import WebCrawler
from generate_report import generate_pdf
from cross_examine import CrossExaminar
from ai_engine import AIEngine, GroqProvider

BASE_URL = "https://opensource-demo.orangehrmlive.com/"

# Define roles to test
ROLES = [
    {"role": "admin", "username": "Admin", "password": "admin123"},
    {"role": "guest", "username": "", "password": ""}
]

crawlers = []

# configure ai engine
groqProvider = GroqProvider(api_key="MY_GROQ_API_KEY") # Replace with your actual Groq API key
aiEngine = AIEngine(llm_provider=groqProvider) # For testing with AI integration
#aiEngine = None  # For testing without AI integration

# Crawl as each role
for role_config in ROLES:
    # Shows which role is being crawled
    print("\n" + "="*60)
    print(f"CRAWLING AS: {role_config['role'].upper()}")
    print("="*60 + "\n")
    
    testCrawler = WebCrawler(
        BASE_URL,
        role_config["role"],
        role_config["username"],
        role_config["password"]
    )
    
    testCrawler.visit_page()
    if not testCrawler.login_url:
        print("DEBUG: No login form found on homepage, checking /login.php...")
        testCrawler.visit_page(BASE_URL + "login.php")

    if testCrawler.login_url and testCrawler.username:
        print(f"\n→ Login form found at {testCrawler.login_url}, logging in as '{testCrawler.username}'...\n")
        testCrawler.visit_page(testCrawler.login_url)
        after_login_url = testCrawler.login()
        print(f"→ Logged in! Redirected to: {after_login_url}\n")
    else:
        print(f"DEBUG: login_url = {testCrawler.login_url}, username = {testCrawler.username}")
        after_login_url = None
        
    # Crawl
    queue = testCrawler.url_collections[testCrawler.currentpage]
    visited = set()
    to_visit = queue.copy()

    # Add post-login page so dashboard gets crawled
    if after_login_url and after_login_url not in to_visit:
        to_visit.append(after_login_url)
    
    while to_visit:
        url = to_visit.pop(0)
        
        if url not in visited:
            testCrawler.visit_page(url)
            visited.add(url)
            
            new_urls = testCrawler.url_collections.get(url, [])
            for new_url in new_urls:
                if new_url not in visited and new_url not in to_visit:
                    to_visit.append(new_url)
        
        print(f"Queue: {len(to_visit)}, Visited: {len(visited)}")
    
    #Shows summary after crawl
    print(f"\n→ Crawl complete for '{role_config['role']}': {len(visited)} pages visited\n")
    crawlers.append(testCrawler)

#Cross-examination
print("\n" + "="*60)
print("STARTING CROSS-EXAMINATION")
print("="*60 + "\n")

print("Discovered URLs:")
for url in visited:
    print(f"  - {url}")

cx = CrossExaminar(crawlers, aiEngine)
cx.perform_examination()
cx.generate_report("access_control_report.json")

generate_pdf(BASE_URL, "access_control_report.json")
