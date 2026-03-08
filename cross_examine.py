import json
from typing import List, Dict, Set, Optional

from crawler import WebCrawler
from ai_engine import AIEngine


class Violation:
    """Represents a single Access Control breach"""
    def __init__(self, url: str, owner: str, tester: str, v_type: str, severity: str, reasoning: str, status_code: int = None, confidence: str = "low"):
        self.url = url
        self.owner_role = owner
        self.tester_role = tester
        self.type = v_type
        self.severity = severity
        self.reasoning = reasoning
        self.status_code = status_code
        self.confidence = confidence
    
    def to_dict(self):
        return {
            "url": self.url,
            "owner_role": self.owner_role,
            "tester_role": self.tester_role,
            "violation_type": self.type,
            "severity": self.severity,
            "note": self.reasoning,
            "status_code": self.status_code,
            "confidence": self.confidence
        }

class CrossExaminar:
    # role hierarchy - Define privilege levels
    _levels = {
        "guest":      0,  # No login - lowest privilege
        "test":       2,  # testphp.vulnweb.com's admin account
        "admin":      2,  # Generic admin
        "customer":   1,  # For future use
        "customer_b": 1,  # For IDOR testing (future)
        "user":       1,
        "manager":    2,
        "superadmin": 3
    }

    def __init__(self, crawlers: List, ai_engine: Optional[AIEngine] = None):
        self.crawlers: Dict[str, WebCrawler] = {c.role: c for c in crawlers}
        self.ai_engine = ai_engine
        self.violations: List[Violation] = []
        self.all_results: List[Dict] = []
        self.shared_urls = self._find_shared_urls()

    def _find_shared_urls(self):
        # STEP 4: URL FILTERING
        # Find shared (public) and exclusive (protected) URLs
        """
        Find URLs that ALL roles can access (public URLs).
        These should be skipped in violation testing.
        
        Args:
            crawlers: List of WebCrawler instances
        
        Returns:
            Set of URLs accessible by everyone
        """

        if not self.crawlers:
            return set()
        
        # Start with first crawler's accessible URLs
        crawlers_list = list(self.crawlers.values())
        shared = set(crawlers_list[0].accessed_url)
        
        # Intersect with all other crawlers (keep only common URLs)
        for crawler in crawlers_list[1:]:
            shared &= set(crawler.accessed_url)
        
        print(f"\n  Shared/public URLs found: {len(shared)}")
        if shared:
            sample = sorted(list(shared))[:3]
            for url in sample:
                print(f"    - {url}")
            if len(shared) > 3:
                print(f"    ... and {len(shared) - 3} more")
        
        return shared

    def _get_level(self, role_name: str) -> int:
        """
        Get the privilege level for a role.
        Higher number = more privileges.
        Unknown roles default to 0 (guest level).
        """

        return self._levels.get(role_name.lower(), 0)


    def _replay_request(self, crawler: WebCrawler, url: str) -> Dict:
        """
        Attempt to access a URL using a crawler's authenticated session.
        
        Args:
            crawler: WebCrawler instance with authenticated browser session
            url: URL to test access against
        
        Returns:
            Dict with status_code and whether access was granted
        """

        try:
            status_code = crawler.get_status_code(url)
            return {
                "url": url,
                "status_code": status_code,
                "access_granted": status_code < 400,
                "method": "browser_session"
            }
        except Exception as e:
            return {
                "url": url,
                "status_code": None,
                "access_granted": False,
                "error": str(e)
            }


    def _analyze_access_result(self, result: Dict) -> Dict:
        """
        Analyze the result and determine confidence level.
        
        Returns:
            Dict with access_granted (bool), confidence level, and reason
        """

        status = result.get("status_code")

        if status is None:
            return {"access_granted": False, "confidence": "low", "reason": "Request failed - could not determine"}

        if 200 <= status < 300:
            return {"access_granted": True, "confidence": "high", "reason": f"HTTP {status} - Access granted"}
        elif 300 <= status < 400:
            return {"access_granted": False, "confidence": "medium", "reason": f"HTTP {status} - Redirect (likely to login)"}
        elif status in [401, 403]:
            return {"access_granted": False, "confidence": "high", "reason": f"HTTP {status} - Access denied"}
        elif status == 404:
            return {"access_granted": False, "confidence": "medium", "reason": "HTTP 404 - Not found or hidden"}
        elif status >= 500:
            return {"access_granted": False, "confidence": "low", "reason": f"HTTP {status} - Server error"}
        else:
            return {"access_granted": False, "confidence": "medium", "reason": f"HTTP {status} - Client error"}


    def _classify_violation(self, url: str, owner_role: str, tester_role: str) -> Dict:
        """
        Classify what type of violation this is and how severe.
        
        Returns:
            Dict with violation type, severity, and note
        """
        url_lower = url.lower()
        owner_level = self._get_level(owner_role)
        tester_level = self._get_level(tester_role)

        if owner_level == tester_level and owner_role != tester_role:
            return {"type": "HORIZONTAL_PRIVILEGE_ESCALATION", "severity": "HIGH",
                    "note": f"Same-level user '{tester_role}' accessing '{owner_role}' resources (IDOR)"}

        if any(w in url_lower for w in ['/admin', '/administrator', '/manage', '/backend']):
            return {"type": "VERTICAL_PRIVILEGE_ESCALATION", "severity": "CRITICAL",
                    "note": f"Non-admin role '{tester_role}' accessing admin endpoint"}

        if any(w in url_lower for w in ['/api/', '/rest/', '/graphql', '/v1/', '/v2/']):
            return {"type": "API_AUTHORIZATION_BYPASS", "severity": "HIGH",
                    "note": f"Unauthorized API access by '{tester_role}'"}

        if any(w in url_lower for w in ['/user', '/users', '/profile', '/account']):
            return {"type": "USER_DATA_ACCESS", "severity": "HIGH",
                    "note": f"Unauthorized access to user data by '{tester_role}'"}

        return {"type": "BROKEN_ACCESS_CONTROL", "severity": "MEDIUM",
                "note": f"Role '{tester_role}' accessing '{owner_role}' protected resource"}


    def perform_examination(self):
        """
        Main cross-examination logic.
        Runs both standard (HTTP status-code based) and AI-based examination.
        Covers both vertical access (lower privilege -> higher privilege)
        and horizontal access (same privilege, different roles).
        """

        # ── Phase 1: Standard HTTP status-code cross-examination ──
        print(f"\n{'='*60}")
        print(f"  STANDARD CROSS-EXAMINATION (HTTP status-code based)")
        print(f"{'='*60}")
        self._perform_standard_examination()

        # ── Phase 2: AI-powered semantic cross-examination ──
        if self.ai_engine:
            print(f"\n{'='*60}")
            print(f"  AI-POWERED CROSS-EXAMINATION (semantic comparison)")
            print(f"{'='*60}")
            self._perform_ai_examination()
        else:
            print(f"\n  Skipping AI examination (no AI engine configured)")

        # ── Phase 3: Negative testing via AI parameter mutations ──
        if self.ai_engine:
            print(f"\n{'='*60}")
            print(f"  NEGATIVE TESTING (AI-generated parameter mutations)")
            print(f"{'='*60}")
            self._perform_mutation_examination()
        else:
            print(f"\n  Skipping mutation testing (no AI engine configured)")


    def _perform_standard_examination(self):
        """
        Standard cross-examination using HTTP status codes.
        Tests whether lower-privilege roles can access higher-privilege URLs
        and whether same-level roles can access each other's resources (IDOR).
        """
        total_tests = 0

        # Sort roles by privilege level (lowest first)
        sorted_roles = sorted(self.crawlers.keys(), key=lambda r: self._get_level(r))

        print(f"\n  Role hierarchy (low → high privilege):")
        for role in sorted_roles:
            c = self.crawlers[role]
            level = self._get_level(role)
            login_status = f"logged in as {c.username}" if c.username else "guest (no login)"
            print(f"    Level {level}: {role:12} ({login_status})")

        # ── Vertical testing: lower-privilege trying to reach higher-privilege URLs ──
        for owner_role in sorted_roles:
            owner_crawler = self.crawlers[owner_role]
            owner_level = self._get_level(owner_role)

            exclusive_urls = self._get_exclusive_urls(owner_crawler)

            if not exclusive_urls:
                print(f"\n  [{owner_role}] has no exclusive URLs to test")
                continue

            print(f"\n  [{owner_role}] has {len(exclusive_urls)} exclusive URLs")
            sample = sorted(list(exclusive_urls))[:3]
            for url in sample:
                print(f"    - {url}")
            if len(exclusive_urls) > 3:
                print(f"    ... and {len(exclusive_urls) - 3} more")

            for tester_role in sorted_roles:
                tester_level = self._get_level(tester_role)

                # Only test UPWARD access (lower trying to reach higher)
                if tester_level >= owner_level:
                    continue
                if tester_role == owner_role:
                    continue

                tester_crawler = self.crawlers[tester_role]
                print(f"\n  Testing: Can [{tester_role}] access [{owner_role}]'s exclusive URLs?")
                print(f"  {'-'*60}")

                pair_violations = []

                for url in exclusive_urls:
                    total_tests += 1

                    raw_result = self._replay_request(tester_crawler, url)
                    analysis = self._analyze_access_result(raw_result)

                    result = {
                        "url": url,
                        "owner_role": owner_role,
                        "tester_role": tester_role,
                        "status_code": raw_result.get("status_code"),
                        "access_granted": analysis["access_granted"],
                        "confidence": analysis["confidence"],
                        "reason": analysis["reason"]
                    }
                    self.all_results.append(result)

                    if analysis["access_granted"]:
                        violation_info = self._classify_violation(url, owner_role, tester_role)
                        self.violations.append(
                            Violation(
                                url=url,
                                owner=owner_role,
                                tester=tester_role,
                                v_type=violation_info["type"],
                                severity=violation_info["severity"],
                                reasoning=violation_info["note"],
                                status_code=raw_result.get("status_code"),
                                confidence=analysis["confidence"]
                            )
                        )
                        pair_violations.append(url)
                        print(f"  🚨 VULNERABLE | {url}")
                    else:
                        print(f"  ✓ Denied      | {url[:70]}")

                print(f"\n  Result: {len(pair_violations)} violations found")

        # ── IDOR Testing (same privilege level, different users) ──
        print(f"\n  {'='*60}")
        print(f"  IDOR TESTING (same privilege, different users)")
        print(f"  {'='*60}")

        same_level_pairs = [
            (a, b) for a in sorted_roles for b in sorted_roles
            if a != b and self._get_level(a) == self._get_level(b)
        ]

        if not same_level_pairs:
            print(f"\n  No same-level role pairs to test for IDOR")

        for owner_role, tester_role in same_level_pairs:
            owner = self.crawlers[owner_role]
            tester = self.crawlers[tester_role]
            owner_urls = set(owner.accessed_url) - self.shared_urls
            tester_urls = set(tester.accessed_url) - self.shared_urls
            unique_to_owner = owner_urls - tester_urls

            if not unique_to_owner:
                print(f"\n  No unique URLs for [{owner_role}] vs [{tester_role}]")
                continue

            print(f"\n  IDOR: Can [{tester_role}] access [{owner_role}]'s unique URLs?")
            print(f"  {'-'*60}")

            for url in unique_to_owner:
                total_tests += 1

                raw_result = self._replay_request(tester, url)
                analysis = self._analyze_access_result(raw_result)

                result = {
                    "url": url,
                    "owner_role": owner_role,
                    "tester_role": tester_role,
                    "status_code": raw_result.get("status_code"),
                    "access_granted": analysis["access_granted"],
                    "confidence": analysis["confidence"],
                    "reason": analysis["reason"]
                }
                self.all_results.append(result)

                if analysis["access_granted"]:
                    self.violations.append(
                        Violation(
                            url=url,
                            owner=owner_role,
                            tester=tester_role,
                            v_type="IDOR_HORIZONTAL",
                            severity="HIGH",
                            reasoning=f"User '{tester_role}' accessing '{owner_role}' personal resources",
                            status_code=raw_result.get("status_code"),
                            confidence=analysis["confidence"]
                        )
                    )
                    print(f"  🚨 IDOR FOUND | {url}")
                else:
                    print(f"  ✓ Denied      | {url[:70]}")

        print(f"\n  Standard examination complete. {total_tests} tests performed.")


    def _perform_ai_examination(self):
        """
        AI-powered cross-examination using semantic DOM comparison.
        Catches cases where status code says 200 but content is actually different/restricted.
        """
        roles = sorted(self.crawlers.keys(), key=lambda r: self._get_level(r))

        for i, owner_role in enumerate(roles):
            owner_crawler = self.crawlers[owner_role]
            exclusive_urls = self._get_exclusive_urls(owner_crawler)

            for tester_role in roles:
                # 1. vertical testing (lower -> higher)
                if self._get_level(tester_role) < self._get_level(owner_role):
                    self._test_url_set(exclusive_urls, owner_role, tester_role)
                
                # 2. horizontal testing (same level, different role)
                elif tester_role != owner_role and self._get_level(tester_role) == self._get_level(owner_role):
                    self._test_url_set(exclusive_urls, owner_role, tester_role, is_idor=True)
    
    def _perform_mutation_examination(self):
        """
        Negative testing: Use AI to generate mutated URLs that nobody crawled,
        then replay them with each role's session to find hidden vulnerabilities.

        Example: Crawler finds /api/user/profile -> AI suggests /api/admin/profile
                 -> replay /api/admin/profile with user session -> violation if 200
        """
        # Collect all discovered URLs across all roles
        all_discovered = set()
        for crawler in self.crawlers.values():
            all_discovered |= set(crawler.accessed_url)

        if not all_discovered:
            print(f"\n  No discovered URLs to mutate")
            return

        print(f"\n  Generating mutations for {len(all_discovered)} discovered URLs...")
        campaign = self.ai_engine.generate_fuzzing_campaign(
            list(all_discovered),
            list(self.crawlers.keys())
        )

        all_mutations = (
            campaign.get("idor_tests", []) +
            campaign.get("privilege_escalation_tests", []) +
            campaign.get("hidden_endpoint_tests", []) +
            campaign.get("debug_tests", [])
        )

        if not all_mutations:
            print(f"\n  AI generated 0 mutations")
            return

        print(f"\n  AI generated {len(all_mutations)} mutations to test")
        total_tests = 0

        # Sort roles lowest-privilege first
        sorted_roles = sorted(self.crawlers.keys(), key=lambda r: self._get_level(r))

        for mutation in all_mutations:
            mutated_url = mutation.get("mutated")
            original_url = mutation.get("original", "")
            attack_type = mutation.get("attack_type", "UNKNOWN")
            risk_level = mutation.get("risk_level", "MEDIUM")

            if not mutated_url:
                continue

            # Skip if this URL was already discovered (already tested in standard phase)
            if mutated_url in all_discovered:
                continue

            print(f"\n  [{attack_type}] {original_url}")
            print(f"         -> {mutated_url}")

            for tester_role in sorted_roles:
                tester_crawler = self.crawlers[tester_role]
                total_tests += 1

                raw_result = self._replay_request(tester_crawler, mutated_url)
                analysis = self._analyze_access_result(raw_result)

                result = {
                    "url": mutated_url,
                    "owner_role": "MUTATED",
                    "tester_role": tester_role,
                    "status_code": raw_result.get("status_code"),
                    "access_granted": analysis["access_granted"],
                    "confidence": analysis["confidence"],
                    "reason": analysis["reason"],
                    "mutation_source": original_url,
                    "attack_type": attack_type
                }
                self.all_results.append(result)

                if analysis["access_granted"]:
                    self.violations.append(
                        Violation(
                            url=mutated_url,
                            owner="MUTATED",
                            tester=tester_role,
                            v_type=f"MUTATION_{attack_type}",
                            severity=risk_level,
                            reasoning=f"AI-mutated from {original_url}: {mutation.get('reasoning', '')}",
                            status_code=raw_result.get("status_code"),
                            confidence=analysis["confidence"]
                        )
                    )
                    print(f"    !! [{tester_role}] ACCESS GRANTED | {mutated_url}")
                else:
                    print(f"    OK [{tester_role}] Denied        | {mutated_url[:50]}")

        print(f"\n  Mutation testing complete. {total_tests} tests performed.")


    def _test_url_set(self, urls: Set[str], owner_role: str, tester_role: str, is_idor=False):
        tester_crawler = self.crawlers[tester_role]
        owner_crawler = self.crawlers[owner_role]

        for url in urls: 
            # 1. replay request and get HTML
            status_code, tester_html = tester_crawler.get_page_content(url)

            if status_code < 400:
                # 2. trigger semantic comparison
                owner_html = owner_crawler.get_stored_html(url)

                ai_result = self.ai_engine.compare_dom_snapshots(
                    user_a_html=owner_html,
                    user_b_html=tester_html,
                    user_a_role=owner_role,
                    user_b_role=tester_role,
                    url=url
                )

                if ai_result.get("contains_same_data"):
                    v_type = "IDOR_HORIZONTAL" if is_idor else "VERTICAL_PE"
                    self.violations.append(
                        Violation(
                            url=url,
                            owner=owner_role,
                            tester=tester_role,
                            v_type=v_type,
                            severity="HIGH" if is_idor else "CRITICAL",
                            reasoning=ai_result.get("reasoning", "AI confirmed data leak"),
                            status_code=status_code,
                            confidence=str(ai_result.get("confidence", "medium"))
                        )
                    )

    def _get_exclusive_urls(self, owner_crawler) -> Set[str]:
        """
        Find URLs that only the owner role (and higher) can access.
        
        Args:
            owner_crawler: The crawler whose exclusive URLs we want
        
        Returns:
            Set of URLs exclusive to this role
        """
        owner_urls = set(owner_crawler.accessed_url)
        owner_level = self._get_level(owner_crawler.role)
        
        # Collect URLs from lower-privilege roles
        lower_role_urls = set()
        for crawler in self.crawlers.values():
            if self._get_level(crawler.role) < owner_level:
                lower_role_urls |= set(crawler.accessed_url)
        
        # Exclusive = owner has it, lower roles don't, and it's not public
        exclusive = owner_urls - lower_role_urls - self.shared_urls
        
        return exclusive
    
    def generate_report(self, output_file: str = "security_report.json"):
        """
        Generate a comprehensive JSON report with all findings.
        
        Args:
            output_file: Path to save JSON report (default: security_report.json)
        
        Returns:
            Complete report dict
        """

        # Count by severity
        severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for v in self.violations:
            severity_counts[v.severity] = severity_counts.get(v.severity, 0) + 1

        # Count by type
        type_counts = {}
        for v in self.violations:
            type_counts[v.type] = type_counts.get(v.type, 0) + 1

        report = {
            "summary": {
                "total_tests": len(self.all_results),
                "total_violations": len(self.violations),
                "by_severity": severity_counts,
                "by_type": type_counts,
                "roles_tested": [
                    {
                        "role": c.role,
                        "username": c.username if c.username else "guest",
                        "pages_crawled": len(set(c.url_collections.keys())),
                        "urls_accessible": len(c.accessed_url),
                        "apis_found": len(c.api_collections)
                    }
                    for c in self.crawlers.values()
                ]
            },
            "violations": [v.to_dict() for v in self.violations],
            "all_results": self.all_results
        }

        with open(output_file, "w") as f:
            json.dump(report, f, indent=4)

        # Terminal summary
        print(f"\n{'='*70}")
        print(f"CROSS-EXAMINATION SUMMARY")
        print(f"{'='*70}")
        print(f"Violations found:       {len(self.violations)}")
        print(f"  CRITICAL: {severity_counts['CRITICAL']}")
        print(f"  HIGH:     {severity_counts['HIGH']}")
        print(f"  MEDIUM:   {severity_counts['MEDIUM']}")
        print(f"  LOW:      {severity_counts['LOW']}")

        if type_counts:
            print(f"\nViolation types:")
            for vtype, count in type_counts.items():
                print(f"  {vtype}: {count}")

        print(f"\nDetailed report saved to: {output_file}")
        print(f"{'='*70}")

        return report
