from os import link

from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys 
from bs4 import BeautifulSoup
import time
import json

api_patterns = [
        # Standard API paths
        '/api/', '/apis/', '/rest/', '/restapi/', '/restful/',
        '/graphql', '/graphiql', '/gql', '/query',
        '/v1/', '/v2/', '/v3/', '/v4/', '/version1/', '/version2/',
        '/service/', '/services/', '/backend/', '/gateway/',
        '/data/', '/json/', '/xml/', '/rpc/', '/soap/',
        '/ajax/', '/xhr/', '/fetch/', '/remote/',
        
        # Common endpoint names
        '/user', '/users', '/profile', '/account', '/me',
        '/admin', '/adminapi', '/manage', '/management',
        '/config', '/configuration', '/settings', '/preferences',
        '/auth', '/login', '/logout', '/signin', '/signup', '/register',
        '/token', '/oauth', '/jwt', '/session', '/csrf',
        '/search', '/lookup', '/find', '/query',
        '/list', '/get', '/fetch', '/retrieve',
        '/create', '/add', '/insert', '/post',
        '/update', '/edit', '/modify', '/change', '/patch',
        '/delete', '/remove', '/destroy', '/clear',
        '/upload', '/download', '/export', '/import', '/file',
        '/order', '/cart', '/checkout', '/payment', '/invoice',
        '/product', '/products', '/item', '/items', '/catalog',
        '/category', '/categories', '/collection',
        '/comment', '/comments', '/post', '/posts', '/blog',
        '/message', '/messages', '/chat', '/notification',
        '/report', '/reports', '/analytics', '/stats', '/statistics',
        '/dashboard', '/home', '/feed', '/activity',
        '/public', '/private', '/internal', '/external',
        '/health', '/healthcheck', '/ping', '/status', '/metrics',
        
        # File extensions
        '.json', '.xml', '.yaml', '.csv', '.tsv',
        '.jsonp', '.jsond', '.geojson',
        '.do', '.action', '.ws', '.asmx', '.svc',
        
        # URL parameters (often indicate API)
        '?', '=', '&', 'format=json', 'format=xml',
        'callback=', 'jsonp=', 'data=', '_=',
        'page=', 'limit=', 'offset=', 'sort=', 'order=',
        'filter=', 'where=', 'query=', 'q=',
        'id=', 'userId=', 'productId=', 'token=',
        
        # HTTP methods in URL (bad practice but common)
        '/get', '/post', '/put', '/delete', '/patch',
        
        # Technology specific
        '/odata/', '/$batch', '/_api', '/_vti_bin/',
        '/wp-json/', '/wp-admin/admin-ajax.php',
        '/index.php?route=', '/index.php?option=',
        '/cgi-bin/', '/servlet/', '/struts/',
        
        # Cloud/AWS
        '.amazonaws.com/', '.s3.', '.cloudfront.net/',
        '.azure.com/', '.azurewebsites.net/',
        '.googleapis.com/', '.appspot.com/',
        '.herokuapp.com/', '.ngrok.io/',
        
        # Microservices patterns
        '/users/', '/products/', '/orders/', '/payments/',
        '/inventory/', '/shipping/', '/cart/',
        
        # Real-time
        '/socket.io/', '/websocket', '/ws/', '/stream',
        '/events', '/webhook', '/callback',
        
        # Documentation
        '/swagger', '/swagger.json', '/swagger-ui',
        '/api-docs', '/docs', '/redoc', '/openapi.json',
        
        # GraphQL specific
        '/graphql/console', '/graphql/explorer', '/playground',
        '/graphiql', '/gql/',
        
        # Authentication/Authorization
        '/oauth2/', '/oauth/token', '/authorize', '/authenticate',
        '/validate', '/verify', '/check', '/permissions',
        
        # File operations
        '/media/', '/image/', '/img/', '/assets/',
        '/static/', '/public/', '/storage/', '/cdn/',
        
        # Common CRUD patterns in URLs
        '/api/v1/users', '/api/v1/products', '/api/v1/orders',
        '/rest/v1/items', '/rest/v2/customers',
        
        # Mobile app patterns
        '/mobile/', '/app/', '/android/', '/ios/',
        '/mobileapi/', '/appapi/', '/mapi/',
        
        # Testing/Development
        '/test/', '/dev/', '/staging/', '/sandbox/',
        '/mock/', '/fake/', '/demo/', '/sample/',
        
        # Webhooks
        '/webhook/', '/hooks/', '/events/',
        
        # Search patterns
        '/search/suggest', '/search/autocomplete', '/typeahead',
        '/instantsearch', '/fulltext',
        
        # Export/Import
        '/export/csv', '/export/pdf', '/export/excel',
        '/import/batch', '/bulk', '/mass',
        
        # Admin/Operations
        '/ops/', '/operations/', '/monitor/', '/admin/ops/',
        '/system/', '/sys/', '/maintenance/',
        
        # Error/Debug
        '/debug/', '/trace/', '/log/', '/logs/',
        
        # Metrics/Monitoring
        '/metrics/', '/monitoring/', '/stats/prometheus',
        '/health/check', '/ready', '/live',
        
        # Versioning in paths
        '/2018-01-01/', '/2020-07-20/', '/latest/',
        
        # GraphQL operations (in URL)
        'query=', 'mutation=', 'subscription=',
        'variables=', 'operationName=',
        
        # Batch operations
        '/batch', '/bulk', '/mass',
        '/multi', '/multiple', '/collection',
        
        # Relationships
        '/users/{id}/posts', '/posts/{id}/comments',
        '/orders/{id}/items', '/categories/{id}/products',
        
        # Actions (non-CRUD)
        '/login', '/logout', '/register', '/reset-password',
        '/forgot-password', '/change-password', '/verify-email',
        '/resend', '/confirm', '/approve', '/reject',
        '/activate', '/deactivate', '/suspend', '/ban',
        '/block', '/unblock', '/mute', '/unmute',
        '/follow', '/unfollow', '/like', '/unlike',
        '/upvote', '/downvote', '/favorite', '/bookmark',
        '/share', '/report', '/flag', '/hide',
        '/archive', '/unarchive', '/restore', '/trash',
        '/publish', '/unpublish', '/draft', '/schedule',
        '/clone', '/copy', '/duplicate', '/move',
        '/merge', '/split', '/combine', '/separate',
        '/calculate', '/compute', '/process', '/transform',
        '/validate', '/sanitize', '/clean', '/normalize',
        '/parse', '/extract', '/convert', '/render',
        '/preview', '/thumbnail', '/resize', '/crop',
        '/rotate', '/flip', '/mirror', '/filter',
        '/sort', '/filter', '/paginate', '/group',
        '/aggregate', '/summarize', '/count', '/average',
        '/min', '/max', '/distinct', '/unique'
]
    
# Static file patterns to SKIP
static_files = [
        '.css', '.js', '.map', '.ts', '.jsx', '.tsx',
        '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp',
        '.woff', '.woff2', '.ttf', '.eot', '.otf',
        '.mp4', '.webm', '.ogg', '.mp3', '.wav',
        '.pdf', '.doc', '.docx', '.xls', '.xlsx',
        '.zip', '.tar', '.gz', '.rar', '.7z',
        '.txt', '.md', '.rst', '.log',
        'favicon', 'robots.txt', 'sitemap.xml',
        '.br', '.gz', '.zst', '.wasm',
        '.part', '.crdownload', '.tmp', '.temp'
]

web_indicators = [
        '.php', '.asp', '.aspx', '.jsp', '.cgi',
        '.html', '.htm', '.do', '.action'
    ]


class WebCrawler:
    def __init__(self, base_url:str, role:str, username:str, password:str):
        self.role = role
        self.username = username
        self.password = password

        browser_options = Options()
        browser_options.add_argument("-headless")
        browser_options.set_capability("goog:loggingPrefs", {"performance": "ALL", "browser": "ALL"})
        self.browser = webdriver.Chrome(service=Service(),options=browser_options)

        self.base_url = base_url
        self.login_url = ""
        self.currentpage = ""
        
        self.url_collections = {base_url:[]}
        self.forms_collections = {base_url:[]}
        self.api_collections = []
        self.loginform_collections = {}
        self.accessed_url = []

        self.html_snapshots = {}


    def convert_to_full_url(self,link):
        if not link:
            return None
        
        # Already a full URL
        if link.startswith(self.base_url):
            return link
        
        # Hash route: #/login
        elif link.startswith("#/"):
            return self.base_url + "/" + link
        
        # Relative path: /login
        elif link.startswith("/"):
            return self.base_url.rstrip('/') + link
        
        # Other (might be relative like "login" or "about")
        else:
            # Skip javascript:, mailto:, tel:, etc.
            if ":" in link and not link.startswith("http"):
                return None
            return self.base_url + "/" + link
    

    def get_links_from_page(self):
        #Find all clickable links and convert them to full URLs
        html = self.browser.page_source
        soup = BeautifulSoup(html, "html.parser")
        
        internal_links = []
        external_links = []

        for link_tag in soup.find_all("a"):
            href = link_tag.get("href")
            full_url = self.convert_to_full_url(href)
            
            if full_url:
                if self.base_url in full_url:
                    # Internal — crawl this
                    internal_links.append(full_url)
                else:
                    # External — record but don't crawl
                    external_links.append(full_url)
        
        # Remove duplicates
        internal_links = list(set(internal_links))
        external_links = list(set(external_links))

        # Internal links go into crawl queue
        self.url_collections[self.currentpage] = internal_links
        # External links stored separately for reference
        if not hasattr(self, 'external_url_collections'):
            self.external_url_collections = {}
        self.external_url_collections[self.currentpage] = external_links

    def is_login_form(self,form_element):
       
        # Get all relevant attributes
        form_id = form_element.get('id', '').lower()
        form_class = ' '.join(form_element.get('class', [])).lower()
        form_name = form_element.get('name', '').lower()
        form_action = form_element.get('action', '').lower()
        
        # Check inputs within form
        inputs = form_element.find_all('input')
        has_password = False
        has_username_email = False
        has_suitable_length = False

        visible_input_count = 0
        
        for input_tag in inputs:
            input_type = input_tag.get('type', '').lower()
            input_name = input_tag.get('name', '').lower()
            input_id = input_tag.get('id', '').lower()
            input_placeholder = input_tag.get('placeholder', '').lower()
            
            if input_type != "hidden" and not(input_tag.has_attr('disabled')):
                visible_input_count+=1


            # Check for password field
            if input_type == 'password' or 'password' in input_name or 'pass' in input_name:
                has_password = True
                
            # Check for username/email field
            if any(word in input_name or word in input_id or word in input_placeholder 
                for word in ['user', 'name', 'email', 'login']):
                has_username_email = True
        
        if visible_input_count <= 3:
            has_suitable_length =  True

        # Check form level indicators
        form_text = f"{form_id} {form_class} {form_name} {form_action}"
        
        # Return True if it looks like a login form
        if has_password and has_username_email and has_suitable_length:
            return True
        
        if has_password and any(word in form_text for word in ['login', 'signin', 'auth']):
            return True
        
        return False
    
    
    def get_forms_from_page(self):
        """Find all forms on the current page"""
        html = self.browser.page_source
        soup = BeautifulSoup(html, "html.parser")

        forms = []
        
        for form_tag in soup.find_all("form"):
            if self.is_login_form(form_tag):
                self.login_url = self.currentpage
                self.loginform_collections[self.login_url] =  form_tag
            formId = form_tag.get("id","")
            formName = form_tag.get("name","")
            action = form_tag.get("action", "")
            method = form_tag.get("method", "GET")
            inputs = form_tag.find_all("input")
    
            form_info = {
                "object": form_tag,
                "id": formId,
                "name": formName,
                "action": action,
                "method": method,
                "number_of_inputs": len(inputs),
            }
            forms.append(form_info)

        self.forms_collections[self.currentpage] = forms


    def get_api_from_page(self):
        logs = self.browser.get_log('performance')
        no_dupe = []
        for log in logs:
            try:
                log_json = json.loads(log['message'])
                message = log_json['message']
                
                # Check if it's a network request
                if message['method'] == 'Network.requestWillBeSent':
                    request = message['params']['request']
                    url = request['url']
                    
                    # Simple API detection - look for common patterns
                    if any(x in url.lower() for x in api_patterns):
                        # Skip static files
                        if not any(x in url.lower() for x in (static_files+web_indicators)):
                            if (url not in no_dupe) and (self.base_url in url):
                                no_dupe.append(url)
                                self.api_collections.append({'url': url,'method': request.get('method', 'GET')})
            except:
                continue
    
    
    def login(self):
        password_input = None
        username_input = None
        login_form = self.loginform_collections[self.login_url]
        inputs = login_form.find_all("input")
        for i in inputs:
            input_type = i.get("type","")
            if(input_type == "password"):
                password_input = i
            elif(input_type != "submit" and input_type != "hidden"):
                username_input = i
        username_id = username_input.get("id","")
        password_id = password_input.get("id","")

        username_name = username_input.get("name","")
        password_name = password_input.get("name","")


        if(username_id != ""):
            username_field = self.browser.find_element(By.ID, username_id)
        else:
            username_field = self.browser.find_element(By.NAME,username_name )
        if(password_id != ""):
            password_field = self.browser.find_element(By.ID, password_id)
        else:
            password_field = self.browser.find_element(By.NAME, password_name)
        
        username_field.send_keys(self.username)
        password_field.send_keys(self.password)
        password_field.send_keys(Keys.ENTER)

        time.sleep(3)
        url_after_login = self.browser.current_url

        return url_after_login


    def get_status_code(self, url):
        try:
            script = """
            arguments[1](fetch(arguments[0], {
                method: 'HEAD',
                credentials: 'include',
                redirect: 'manual'
            }).then(r => [r.status, r.headers.get('location')]).catch(() => [0, null]));
            """
            status, redirect = self.browser.execute_async_script(script, url)
            return status
        except:
            return 0, None
    

    def store_html_snapshot(self):
        """
        Captures the current browser page source and saves it to the snapshot 
        collection, keyed by the current URL. Used during the 'Owner' crawl.
        """
        current_url = self.browser.current_url
        self.html_snapshots[current_url] = self.browser.page_source
        print(f"Snapshot stored for: {current_url}")


    def get_stored_html(self, url: str):
        """
        Retrieves the ground-truth HTML for a specific URL captured during
        the initial crawl.
        """
        return self.html_snapshots.get(url, "")


    def get_page_content(self, url: str):
        """
        Navigates to a URL and returns the HTTP status code and full HTML source.
        Used by the Cross-Examiner to capture the 'Tester' view.
        """
        
        try:
            self.browser.get(url)
            time.sleep(2)
            status_code = self.get_status_code(url)
            html_source = self.browser.page_source
            return status_code, html_source
        
        except Exception as e:
            print(f"Error fetching content url {url}: {e}")
            return 0, ""

    def visit_page(self, url=None):
        if url == None:
            url = self.base_url
        """Visit one page and collect information"""
        print(f"Visiting: {url}")
        
        try:
            self.browser.get(url)
            self.currentpage = self.browser.current_url
            status_code = self.get_status_code(url)
            if status_code < 400:
                self.store_html_snapshot()
                self.accessed_url.append(self.currentpage)
            
            time.sleep(2)  # Wait for page to load
            
            title = self.browser.title

            self.get_links_from_page()
            print("LINKS OK")

            self.get_forms_from_page()
            print("FORMS OK")

            self.get_api_from_page()
            print("API OK")
            
            page_info = {
                "url": url,
                "title": title,
                "number_of_links": len(self.url_collections[self.currentpage]),
                "number_of_forms": len(self.forms_collections[self.currentpage]),
                "links": self.url_collections[self.currentpage],
                "forms": self.forms_collections[self.currentpage],
            }
            
            print(f"  - Found {len(self.url_collections[self.currentpage])} links and {len(self.forms_collections[self.currentpage])} forms")
            
        except Exception as error:
            print(f"  - ERROR: {error}")
            return None, []
    