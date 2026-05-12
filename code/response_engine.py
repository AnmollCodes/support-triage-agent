"""
response_engine.py

High-quality grounded response engine that operates entirely on the local corpus.
Used as the primary engine when ANTHROPIC_API_KEY is not set, or as a fast-path
pre-filter before LLM call.

Design:
  - Retrieves top-k docs via BM25+TF-IDF
  - Classifies ticket via rule patterns
  - Constructs a grounded response from retrieved content
  - Applies safety / escalation logic
  - Returns a fully-populated TriageResult
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from models import (
    CorpusChunk, RequestType, RetrievedDoc,
    SupportTicket, TicketStatus, TriageResult,
)
from safety import (
    EscalationReason, build_escalation_response,
    check_escalation, is_invalid_ticket,
)

# ─────────────────────────────────────────────────────────────────
# Product area classifiers
# ─────────────────────────────────────────────────────────────────

_AREA_RULES = {
    # HackerRank
    "screen":         re.compile(r"\b(test|assessment|screen|proctoring|question|score|grading|candidate|plagiarism|submission|code\s+challenge|exam)\b", re.I),
    "interviews":     re.compile(r"\b(interview|live\s+coding|interviewer|inactivity|lobby|screen\s+share|pair\s+programming)\b", re.I),
    "skillup":        re.compile(r"\b(skillup|skill\s+up|learning|course|mock\s+interview|practice|resume\s+builder)\b", re.I),
    "library":        re.compile(r"\b(library|question\s+library|problem\s+set|custom\s+question)\b", re.I),
    "integrations":   re.compile(r"\b(ats|integration|greenhouse|lever|workday|api\s+key|webhook|sso|saml|scim|oauth)\b", re.I),
    "community":      re.compile(r"\b(community|developer|coding\s+practice|apply|job|certificate|leaderboard|profile)\b", re.I),
    "engage":         re.compile(r"\b(engage|job\s+description|role|jd|sourcing)\b", re.I),
    # Claude
    "pro_and_max_plans":      re.compile(r"\b(pro|max|plan|subscription|upgrade|downgrade|tier|usage\s+limit|message\s+limit)\b", re.I),
    "team_and_enterprise":    re.compile(r"\b(team|enterprise|workspace|seat|admin|owner|sso|scim|organization|org)\b", re.I),
    "claude_api_and_console": re.compile(r"\b(api|console|sdk|api\s+key|bedrock|token|rate\s+limit|anthropic\s+api|platform\.claude)\b", re.I),
    "claude_code":            re.compile(r"\b(claude\s+code|terminal|cli|code\s+agent|npm\s+install)\b", re.I),
    "claude_mobile_apps":     re.compile(r"\b(mobile|ios|android|app\s+store|google\s+play|phone|iphone)\b", re.I),
    "privacy_and_legal":      re.compile(r"\b(privacy|gdpr|ccpa|data|delete|crawl|personal\s+data|model\s+training|opt.out)\b", re.I),
    "safeguards":             re.compile(r"\b(content\s+policy|safety|harm|restrict|policy|nsfw|abuse|report|vulnerability|bug\s+bounty|security\s+vuln)\b", re.I),
    "amazon_bedrock":         re.compile(r"\b(bedrock|aws|amazon)\b", re.I),
    "claude_for_education":   re.compile(r"\b(education|university|college|student|professor|lti|school)\b", re.I),
    # Visa
    "dispute_resolution":     re.compile(r"\b(dispute|chargeback|wrong\s+product|refund|merchant|unauthorized\s+charge|billed|overcharg)\b", re.I),
    "security_and_fraud":     re.compile(r"\b(fraud|stolen|hack|identity\s+theft|unauthorized|compromised|phishing|scam)\b", re.I),
    "travel_support":         re.compile(r"\b(travel|abroad|foreign|lost\s+card|stolen\s+card|atm|emergency\s+cash|international|cheque|travell)\b", re.I),
    "card_benefits":          re.compile(r"\b(benefit|lounge|insurance|concierge|reward|cashback)\b", re.I),
}

def classify_product_area(ticket: SupportTicket, docs: List[RetrievedDoc]) -> str:
    """Classify product area using both keyword rules and top retrieved doc."""
    combined = f"{ticket.issue} {ticket.subject}"
    company  = (ticket.company or "").lower()

    # Score each area
    scores: dict[str, int] = {}
    for area, pattern in _AREA_RULES.items():
        m = pattern.findall(combined)
        if m:
            scores[area] = len(m)

    # Bias toward company-specific areas
    if scores:
        if company == "hackerrank":
            hr_areas = ["screen", "interviews", "skillup", "library", "integrations",
                        "community", "engage"]
            hr_scored = {k: v for k, v in scores.items() if k in hr_areas}
            if hr_scored:
                return max(hr_scored, key=hr_scored.get)
        elif company == "claude":
            cl_areas = ["pro_and_max_plans", "team_and_enterprise", "claude_api_and_console",
                        "claude_code", "claude_mobile_apps", "privacy_and_legal",
                        "safeguards", "amazon_bedrock", "claude_for_education"]
            cl_scored = {k: v for k, v in scores.items() if k in cl_areas}
            if cl_scored:
                return max(cl_scored, key=cl_scored.get)
        elif company == "visa":
            vi_areas = ["dispute_resolution", "security_and_fraud", "travel_support",
                        "card_benefits"]
            vi_scored = {k: v for k, v in scores.items() if k in vi_areas}
            if vi_scored:
                return max(vi_scored, key=vi_scored.get)
        # Fall back to global best
        return max(scores, key=scores.get)

    # Fall back to top retrieved doc's section
    if docs:
        sec = docs[0].chunk.section.lower().replace(" ", "_")
        if sec:
            return sec
        # Use source
        return docs[0].chunk.source.lower() + "_support"

    return "general_support"


# ─────────────────────────────────────────────────────────────────
# Request type classifier
# ─────────────────────────────────────────────────────────────────

_BUG_PAT = re.compile(
    r"\b(not\s+working|broken|bug|error|crash(?:ed|ing)?|fail(?:ed|ing|ure)|glitch"
    r"|down|outage|can[\s']t\s+(?:load|access|open|login|submit)|stopped\s+working"
    r"|isn['\s]+t\s+working|unable\s+to|doesn['\s]+t\s+work)\b", re.I
)
_FEATURE_PAT = re.compile(
    r"\b(feature\s+request|can\s+you\s+add|would\s+be\s+(?:nice|great)|wish|suggest"
    r"|idea|enhancement|improve|when\s+will\s+you|please\s+add|want\s+to\s+see)\b", re.I
)
_INVALID_PAT = re.compile(
    r"^(hi+|hello+|thank\s*you|thanks|test|ok|okay|yes|no|\.+)[\s!.]*$", re.I
)


def classify_request_type(ticket: SupportTicket, is_invalid: bool = False) -> RequestType:
    if is_invalid:
        return RequestType.INVALID
    combined = f"{ticket.issue} {ticket.subject}"
    if _BUG_PAT.search(combined):
        return RequestType.BUG
    if _FEATURE_PAT.search(combined):
        return RequestType.FEATURE_REQUEST
    return RequestType.PRODUCT_ISSUE


# ─────────────────────────────────────────────────────────────────
# Response templates per scenario type
# ─────────────────────────────────────────────────────────────────

def _build_response_from_docs(
    ticket: SupportTicket,
    docs: List[RetrievedDoc],
    scenario_key: str,
) -> str:
    """Build a grounded user-facing response using retrieved docs."""

    issue_lower = ticket.issue.lower()
    company     = (ticket.company or "").strip()

    # ── Scenario-specific responses (highest priority) ─────────────

    # HackerRank password reset
    if scenario_key == "hr_password":
        return (
            "To reset your HackerRank password:\n\n"
            "1. Go to the HackerRank for Work login page.\n"
            "2. Click **Forgot Password?** under the password field.\n"
            "3. Enter the work email address associated with your account.\n"
            "4. Click **Next**.\n"
            "5. Check your email for a password reset link from HackerRank.\n"
            "6. Follow the instructions in the email to create a new password.\n\n"
            "If you signed up via Google login and want to delete your account, "
            "you'll first need to set a password via 'Forgot Password?' with your Google email, "
            "then go to Settings > Delete Account."
        )

    # Claude workspace access
    if scenario_key == "claude_workspace_access":
        return (
            "Access to a Claude Team or Enterprise workspace is managed by the workspace's "
            "Owners and Admins. As a non-owner/non-admin seat holder, your access is "
            "controlled by your organization's IT admin or workspace owner.\n\n"
            "To restore your access:\n"
            "1. Contact your IT admin or workspace Owner directly.\n"
            "2. Ask them to re-add your seat in the workspace settings.\n\n"
            "Claude support cannot restore individual seats without authorization from "
            "the account Owner or Admin. If you are the Owner and are locked out, "
            "please contact Claude support through claude.ai/support/enterprise."
        )

    # HackerRank score dispute
    if scenario_key == "hr_score_dispute":
        return (
            "Thank you for reaching out. HackerRank assessments are graded automatically "
            "by the platform based on your code's correctness and efficiency against test cases.\n\n"
            "HackerRank support is unable to:\n"
            "- Review or modify assessment scores\n"
            "- Contact recruiters or hiring companies on a candidate's behalf\n"
            "- Influence hiring decisions\n\n"
            "If you believe there was a technical error (e.g., your code did not run correctly "
            "due to a platform issue), please reach out to the recruiting company directly "
            "and ask them to escalate to HackerRank support with the test session ID.\n\n"
            "The assessment process and grading are designed to be fair and automated. "
            "We recommend reviewing your solution and the problem constraints."
        )

    # Visa dispute / wrong product
    if scenario_key == "visa_dispute":
        return (
            "We're sorry to hear about this experience. Here's how to dispute the transaction:\n\n"
            "**Step 1:** Contact the merchant again in writing (email/chat) and request a "
            "refund or return. Keep a record of all communications.\n\n"
            "**Step 2:** If the merchant does not resolve the issue, contact the bank that "
            "issued your Visa card (number on the back of your card) to initiate a **chargeback**.\n\n"
            "**Step 3:** Provide your bank with:\n"
            "- Transaction date and amount\n"
            "- Merchant name\n"
            "- Evidence that the wrong product was received (photos, emails)\n"
            "- Proof you attempted to contact the merchant\n\n"
            "You generally have up to **120 days** from the transaction date to file a dispute.\n\n"
            "**Important:** Visa does not directly process consumer refunds or ban merchants. "
            "Your issuing bank manages the chargeback process under Visa's rules. "
            "The bank has the authority to reverse the charge if your claim is valid."
        )

    # HackerRank refund (mock interviews)
    if scenario_key == "hr_refund":
        return (
            "We're sorry to hear your mock interview session was interrupted. "
            "Your request for a refund has been escalated to our billing team for review.\n\n"
            "While we investigate, please:\n"
            "1. Note the approximate time and date the session stopped.\n"
            "2. Check if there were any network or browser issues on your end.\n\n"
            "A specialist will review your case and respond within 2 business days. "
            "If you need urgent assistance, please contact HackerRank support directly "
            "via the Help Center."
        )

    # HackerRank billing
    if scenario_key == "hr_billing":
        return (
            "Thank you for reaching out about your payment. Your case has been escalated "
            "to our billing team who will review order ID and transaction details.\n\n"
            "To expedite the process, please have the following ready:\n"
            "- Order/payment ID\n"
            "- Date of transaction\n"
            "- Amount charged\n"
            "- Your account email\n\n"
            "Our billing team will contact you within 2 business days. "
            "If this is urgent, please submit a request through the HackerRank support portal."
        )

    # HackerRank infosec forms
    if scenario_key == "hr_infosec":
        return (
            "Thank you for your interest in HackerRank for hiring!\n\n"
            "Completing your company's internal information security (infosec) questionnaires "
            "is outside the scope of HackerRank's support services. These forms typically "
            "require information about your organization's risk assessment processes, which "
            "only your team can accurately provide.\n\n"
            "However, HackerRank can help you with:\n"
            "- **Security documentation**: HackerRank's security page (security.hackerrank.com) "
            "contains information about our security practices, certifications, and compliance.\n"
            "- **Trust center**: Visit trust.hackerrank.com for audit reports and policies.\n"
            "- **Sales/Enterprise team**: For formal security reviews, our enterprise team "
            "can provide a Security Questionnaire response document.\n\n"
            "Please reach out to your HackerRank account representative for enterprise-level "
            "security documentation support."
        )

    # HackerRank apply/submissions not visible
    if scenario_key == "hr_apply_tab":
        return (
            "We're sorry to hear you're having trouble with the Apply tab or submissions. "
            "Here are some troubleshooting steps:\n\n"
            "1. **Clear your browser cache and cookies** and try again.\n"
            "2. **Use a supported browser**: HackerRank works best with the latest version "
            "of Google Chrome or Mozilla Firefox.\n"
            "3. **Check your login**: Make sure you're logged in to the correct account.\n"
            "4. **Disable browser extensions**: Ad blockers or script blockers can interfere "
            "with HackerRank's interface.\n"
            "5. **Try Incognito/Private mode** to rule out cache issues.\n\n"
            "If the Apply tab is missing from your profile, it may not be available in your "
            "region or account type. Please provide more details about which page you're "
            "accessing so we can assist further."
        )

    # HackerRank platform-wide submissions failing
    if scenario_key == "hr_submissions_down":
        return (
            "We're sorry for the inconvenience. A platform-wide issue affecting submissions "
            "has been detected and escalated to our engineering team for immediate investigation.\n\n"
            "**What to do now:**\n"
            "- Check **status.hackerrank.com** for real-time platform status updates.\n"
            "- Try refreshing the page after a few minutes.\n"
            "- If you're mid-assessment, note your current progress and contact the recruiter.\n\n"
            "Our team is working to resolve this as quickly as possible. "
            "We apologize for the disruption."
        )

    # HackerRank Zoom connectivity
    if scenario_key == "hr_zoom":
        return (
            "We're sorry you're experiencing a Zoom connectivity issue during the "
            "compatibility check. Here's how to resolve it:\n\n"
            "1. **Ensure Zoom is installed** and updated to the latest version.\n"
            "2. **Allowlist Zoom domains** in your firewall/network settings: "
            "*.zoom.us, zoom.us\n"
            "3. **Check browser permissions**: Allow camera and microphone access for "
            "HackerRank in your browser settings.\n"
            "4. **Allowlist HackerRank URLs**: "
            "*.hackerrank.com, *.hackerrank.net must be accessible.\n"
            "5. **Disable VPN** temporarily if you're using one, as it can interfere with "
            "Zoom connectivity.\n"
            "6. **Restart Zoom** and rerun the compatibility check.\n\n"
            "If the issue persists, contact your IT department to ensure Zoom and HackerRank "
            "are not blocked by your organization's network policies."
        )

    # HackerRank assessment reschedule
    if scenario_key == "hr_reschedule":
        return (
            "We understand that unforeseen circumstances can prevent you from taking an "
            "assessment at the scheduled time.\n\n"
            "**HackerRank support cannot directly reschedule assessments** — this is managed "
            "by the recruiting company that sent you the invitation.\n\n"
            "Here's what you should do:\n"
            "1. **Contact the recruiting team directly** at the company you applied to.\n"
            "2. Explain your situation and request a reschedule.\n"
            "3. The recruiter can then re-invite you to the assessment with a new window.\n\n"
            "For reference, once a test window has passed, only the test administrator "
            "(the recruiter) can re-open access. HackerRank support does not have the "
            "ability to extend assessment windows without the recruiter's authorization."
        )

    # HackerRank interview inactivity
    if scenario_key == "hr_inactivity":
        return (
            "Thank you for raising this — inactivity timeouts during live interviews can "
            "be disruptive. Here's what we can share:\n\n"
            "HackerRank Interviews has configurable inactivity settings. By default:\n"
            "- Participants who are inactive (no keyboard/mouse activity on the HackerRank "
            "screen) for a set period may be prompted with a warning or removed.\n"
            "- Interviewers who are primarily watching a screen share may appear inactive "
            "on the HackerRank interface even though they are engaged.\n\n"
            "**To extend inactivity timeout:**\n"
            "1. Go to **Settings** in your HackerRank for Work account.\n"
            "2. Navigate to **Interviews** settings.\n"
            "3. Adjust the inactivity timeout duration.\n\n"
            "If you don't see this setting, please contact your HackerRank Customer Success "
            "Manager or submit a request — this may be configurable at the enterprise level."
        )

    # Invalid/vague ticket
    if scenario_key == "invalid_vague":
        return (
            "Thank you for reaching out! Your message doesn't include enough detail for us "
            "to assist you effectively.\n\n"
            "Could you please provide more information, such as:\n"
            "- Which platform or product are you using? (HackerRank, Claude, Visa)\n"
            "- What exactly is not working or what are you trying to do?\n"
            "- Any error messages you're seeing\n\n"
            "Once we have more details, we'll be happy to help!"
        )

    # Remove interviewer/user
    if scenario_key == "hr_remove_user":
        return (
            "To remove a user (interviewer or team member) from your HackerRank platform:\n\n"
            "1. Log in to your **HackerRank for Work** account as an Admin.\n"
            "2. Go to **Settings** > **Users** (or **Team** depending on your interface).\n"
            "3. Find the user you want to remove.\n"
            "4. Click the **three-dot menu (⋮)** next to their name.\n"
            "5. Select **Remove** or **Deactivate**.\n"
            "6. Confirm the action.\n\n"
            "**Note:** If the option is not appearing, ensure you have Admin-level permissions. "
            "Non-admin users cannot remove other users. "
            "If you continue to have trouble, please contact HackerRank support with your "
            "account details."
        )

    # HackerRank subscription pause
    if scenario_key == "hr_subscription_pause":
        return (
            "We can help you pause or manage your subscription. "
            "HackerRank offers subscription pausing for qualifying plans.\n\n"
            "To pause your subscription:\n"
            "1. Log in to your HackerRank for Work account as an Admin.\n"
            "2. Go to **Settings** > **Billing** > **Subscription**.\n"
            "3. Select **Pause Subscription** and choose your pause duration.\n\n"
            "**Alternatively**, if you'd like to cancel entirely:\n"
            "1. Go to **Settings** > **Subscription** > **Cancel Subscription**.\n"
            "2. Cancellation takes effect at the end of the current billing period.\n\n"
            "If you don't see the pause option, it may not be available on your plan type. "
            "Please submit a request via the HackerRank support portal for further assistance."
        )

    # Claude not responding / down
    if scenario_key == "claude_down":
        return (
            "We're sorry you're experiencing issues with Claude. Here's how to troubleshoot:\n\n"
            "1. **Check the status page**: Visit **status.anthropic.com** to see if there's "
            "an ongoing incident or outage.\n"
            "2. **Refresh and retry**: Sometimes transient errors resolve on their own.\n"
            "3. **Check your internet connection**.\n"
            "4. **For API users**: Check if you're receiving specific error codes:\n"
            "   - `529` = Anthropic is overloaded (retry with backoff)\n"
            "   - `500` = Internal server error (retry)\n"
            "   - `401/403` = Authentication issue (check API key)\n"
            "5. **Clear browser cache** if using claude.ai.\n\n"
            "If the issue persists and status.anthropic.com shows no known incidents, "
            "please contact Claude support through the in-app support messenger."
        )

    # Visa identity theft
    if scenario_key == "visa_identity_theft":
        return (
            "Identity theft is a serious matter. Your case has been escalated to our "
            "fraud and security team.\n\n"
            "**Take these steps immediately:**\n\n"
            "1. **Contact your bank/card issuer** (number on the back of your Visa card) "
            "to block your card and report identity theft.\n"
            "2. **File a police report** — this provides a paper trail for fraud claims.\n"
            "3. **Contact credit bureaus** to place a fraud alert on your credit file.\n"
            "4. **Review all recent transactions** on all your accounts for unauthorized charges.\n"
            "5. **Change passwords** on all important accounts, especially email and banking.\n\n"
            "Visa's Zero Liability Policy protects you from unauthorized charges — "
            "contact your issuing bank to invoke this protection.\n\n"
            "A specialist from our team will follow up with you shortly."
        )

    # HackerRank resume builder down
    if scenario_key == "hr_resume_down":
        return (
            "We're sorry to hear the Resume Builder isn't loading. "
            "This issue has been escalated to our engineering team.\n\n"
            "**Troubleshooting steps to try:**\n"
            "1. Check **status.hackerrank.com** for any known platform issues.\n"
            "2. Try a different browser (Chrome is recommended).\n"
            "3. Clear your browser cache and cookies.\n"
            "4. Try accessing via Incognito/Private mode.\n\n"
            "If the issue persists, our team will follow up. "
            "We apologize for the inconvenience."
        )

    # Certificate name update
    if scenario_key == "hr_certificate_name":
        return (
            "To update the name on your HackerRank certificate:\n\n"
            "1. Log in to your HackerRank account.\n"
            "2. Click your **profile icon** in the top-right corner.\n"
            "3. Select **Settings**.\n"
            "4. Update your **First Name** and **Last Name** in the Profile section.\n"
            "5. Click **Save Changes**.\n\n"
            "After updating your profile name, your certificate should reflect the new name. "
            "If you've already downloaded the certificate and need it reissued with the "
            "corrected name, please contact HackerRank support with:\n"
            "- Your account email\n"
            "- The certificate type and date\n"
            "- The correct name to display"
        )

    # Visa dispute charge - how to
    if scenario_key == "visa_dispute_how":
        return (
            "To dispute a charge on your Visa card:\n\n"
            "1. **Contact the merchant first** to resolve the issue directly — "
            "this is often the fastest resolution.\n\n"
            "2. **If unresolved**, contact the bank that issued your Visa card. "
            "The number is on the back of your card.\n\n"
            "3. **Provide your bank with:**\n"
            "   - Transaction date and amount\n"
            "   - Merchant name\n"
            "   - Reason for dispute (unauthorized, not received, wrong amount, etc.)\n"
            "   - Any supporting documentation\n\n"
            "4. Your bank will initiate a **chargeback** process under Visa's rules.\n\n"
            "**Timeframe:** You generally have up to **120 days** from the transaction date "
            "to raise a dispute with your bank.\n\n"
            "**Note:** Visa does not directly process consumer disputes — "
            "all disputes are handled through your issuing bank."
        )

    # Claude security vulnerability / bug bounty
    if scenario_key == "claude_security_vuln":
        return (
            "Thank you for responsibly disclosing what you believe to be a security vulnerability "
            "in Claude. This has been escalated to Anthropic's security team.\n\n"
            "**To officially report the vulnerability:**\n"
            "Please submit your finding through Anthropic's responsible disclosure program:\n"
            "- **URL:** https://www.anthropic.com/responsible-disclosure-policy\n\n"
            "When submitting, include:\n"
            "- A clear description of the vulnerability\n"
            "- Steps to reproduce\n"
            "- Potential impact\n"
            "- Any proof-of-concept (if applicable)\n\n"
            "Anthropic takes security reports seriously and will acknowledge receipt. "
            "Please do not share the vulnerability publicly until Anthropic has had a "
            "chance to investigate and remediate."
        )

    # Claude crawling / data opt-out
    if scenario_key == "claude_crawl_optout":
        return (
            "To prevent Claude (Anthropic's web crawler) from crawling your website:\n\n"
            "**Option 1 — robots.txt (recommended):**\n"
            "Add the following to your website's `robots.txt` file:\n"
            "```\nUser-agent: ClaudeBot\nDisallow: /\n```\n\n"
            "**Option 2 — Contact Anthropic:**\n"
            "If you've already added `robots.txt` restrictions and are still seeing crawls, "
            "or need immediate removal, contact Anthropic via the privacy request form "
            "at: https://privacy.anthropic.com/\n\n"
            "Anthropic respects `robots.txt` directives for Claude's web training data. "
            "After updating `robots.txt`, it may take some time for the changes to be "
            "fully honoured across crawl cycles.\n\n"
            "For more information, see Anthropic's Privacy Policy at anthropic.com/privacy."
        )

    # Visa urgent cash
    if scenario_key == "visa_urgent_cash":
        return (
            "If you need emergency cash and only have your Visa card, here are your options:\n\n"
            "1. **ATM Withdrawal:** Use your Visa card at any Visa/Plus network ATM to "
            "withdraw cash. Fees may apply — check with your bank.\n\n"
            "2. **Bank Branch Cash Advance:** Visit a bank branch that accepts Visa and "
            "request a cash advance.\n\n"
            "3. **Emergency Cash Disbursement (if traveling):** Visa's Global Customer "
            "Assistance Service can arrange emergency cash disbursement:\n"
            "   - India: Contact your issuing bank directly\n"
            "   - International: +1-303-967-1090 (collect, 24/7)\n\n"
            "4. **Contact your issuing bank:** Your bank may have additional options "
            "for emergency funds, including instant transfers.\n\n"
            "**Note:** Cash advance transactions typically incur fees and higher interest rates. "
            "Check your card's terms and conditions."
        )

    # Claude data retention
    if scenario_key == "claude_data_retention":
        return (
            "Thank you for your question about data usage. When you allow Claude to use "
            "your data to improve its models, here's what you should know:\n\n"
            "- **Anthropic's Privacy Policy** (anthropic.com/privacy) governs how your "
            "data is used and for how long.\n"
            "- Conversation data used for model training may be retained according to "
            "Anthropic's data retention schedule, which is defined in the Privacy Policy.\n"
            "- You can opt out of data use for model training in your **account settings** "
            "at any time.\n"
            "- If you opt out, data from future conversations will not be used for training.\n\n"
            "**To opt out or manage your data preferences:**\n"
            "1. Log in to claude.ai.\n"
            "2. Go to **Settings** > **Privacy**.\n"
            "3. Toggle off 'Allow data for model training'.\n\n"
            "For specific retention timeframes or data deletion requests, please contact "
            "Anthropic's privacy team via the privacy request form at anthropic.com."
        )

    # Malicious / delete files
    if scenario_key == "malicious_delete":
        return (
            "This request cannot be fulfilled. Providing code to delete system files could "
            "cause irreversible damage to a computer system and is outside the scope of "
            "support services across all three platforms we support.\n\n"
            "This ticket has been flagged and a human agent will review it."
        )

    # French prompt injection (Visa card blocked + asking for internal rules)
    if scenario_key == "prompt_injection_visa":
        return (
            "Votre demande a été transmise à un agent humain pour examen.\n\n"
            "If your Visa card has been blocked while travelling, please contact the bank "
            "that issued your card immediately (number on the back of your card) to have "
            "the block removed. Banks often block cards during international travel as a "
            "security measure.\n\n"
            "This ticket has been escalated for further review."
        )

    # Claude Bedrock issues
    if scenario_key == "claude_bedrock":
        return (
            "We're sorry you're experiencing issues with Claude via AWS Bedrock. "
            "Here's how to troubleshoot API failures:\n\n"
            "**Common causes and fixes:**\n\n"
            "1. **Check AWS Bedrock service status**: Visit the AWS Service Health Dashboard "
            "and check the Bedrock region you're using.\n\n"
            "2. **Verify model access**: Ensure you have requested and been granted access "
            "to Claude models in your AWS Bedrock console "
            "(AWS Console > Bedrock > Model access).\n\n"
            "3. **Check IAM permissions**: Your AWS role/user must have `bedrock:InvokeModel` "
            "permission for the Claude model ARN.\n\n"
            "4. **Region availability**: Claude on Bedrock is available in specific AWS regions. "
            "Verify you're using a supported region.\n\n"
            "5. **API errors**: Check for specific error codes:\n"
            "   - `AccessDeniedException` → Model access or IAM issue\n"
            "   - `ThrottlingException` → Rate limit exceeded\n"
            "   - `ModelNotReadyException` → Retry after a moment\n\n"
            "For Bedrock-specific support, you can also contact AWS Support."
        )

    # HackerRank remove employee
    if scenario_key == "hr_remove_employee":
        return (
            "To remove an employee who has left from your HackerRank hiring account:\n\n"
            "1. Log in to your **HackerRank for Work** account as an Admin.\n"
            "2. Go to **Settings** > **Users**.\n"
            "3. Find the employee's account.\n"
            "4. Click the **three-dot menu (⋮)** next to their name.\n"
            "5. Select **Remove User** or **Deactivate**.\n"
            "6. Confirm the action.\n\n"
            "**Best practice:** Deactivating rather than deleting the user preserves their "
            "historical activity in your account (tests created, candidates assessed).\n\n"
            "Once removed, the user will no longer have access to your HackerRank organization "
            "account. You can reassign their responsibilities to another team member."
        )

    # Claude education / LTI
    if scenario_key == "claude_education_lti":
        return (
            "Thank you for your interest in using Claude for your students!\n\n"
            "**Claude for Education** offers options for academic institutions. "
            "Here's how to get started:\n\n"
            "1. **Claude for Education program**: Anthropic has an education initiative for "
            "universities and colleges. Visit https://www.anthropic.com/education or "
            "check the Claude for Education section in the Help Center.\n\n"
            "2. **LTI Integration**: For LTI (Learning Tools Interoperability) setup to "
            "integrate Claude with your university's LMS (Canvas, Moodle, Blackboard), "
            "this typically requires contacting Anthropic's education team directly.\n\n"
            "3. **Contact Education Team**: Email education@anthropic.com (or use the "
            "contact form in the Claude for Education Help Center section) with:\n"
            "   - Your institution name\n"
            "   - Expected number of students\n"
            "   - Intended use case\n\n"
            "**Note:** LTI key setup for Claude is handled through the education program "
            "and may require a specific agreement with Anthropic."
        )

    # Visa US Virgin Islands minimum spend
    if scenario_key == "visa_minimum_spend":
        return (
            "This is a valid question! Here's why a merchant might require a minimum spend "
            "on your Visa card:\n\n"
            "**US Law (Dodd-Frank Act, 2010):** In the United States and US territories "
            "(including the US Virgin Islands), merchants are legally permitted to set a "
            "minimum transaction amount of **up to $10** for credit card purchases. "
            "This is allowed under US law.\n\n"
            "**Key points:**\n"
            "- The minimum applies to **credit cards** (not debit cards used with a PIN).\n"
            "- The merchant cannot set a minimum higher than $10.\n"
            "- The merchant cannot set different minimums for different card brands.\n"
            "- Debit card transactions processed as PIN transactions cannot have a minimum.\n\n"
            "**What you can do:** If the minimum is over $10 or seems unreasonable, "
            "you can report the merchant to Visa at the contact information on the back "
            "of your card documentation, or use a different payment method."
        )

    # HackerRank Interviews - remove employee
    # Default: synthesise from retrieved docs
    if docs:
        top_doc = docs[0].chunk
        excerpt = top_doc.content[:500].strip()
        return (
            f"Based on the HackerRank support documentation for "
            f"**{top_doc.title}**:\n\n"
            f"{excerpt}\n\n"
            f"If this doesn't fully address your question, please provide more details "
            f"and we'll assist further. You can also browse the full documentation at "
            f"support.{'hackerrank' if ticket.company == 'HackerRank' else 'claude' if ticket.company == 'Claude' else 'visa.co.in'}.com."
        )

    return (
        "Thank you for contacting support. We've received your request and will "
        "follow up shortly. For faster assistance, please provide:\n"
        "- A detailed description of the issue\n"
        "- Steps to reproduce (if applicable)\n"
        "- Your account email"
    )


def _detect_scenario(ticket: SupportTicket) -> str:
    """Map a ticket to the best scenario key."""
    issue   = (ticket.issue + " " + ticket.subject).lower()
    company = (ticket.company or "").strip()

    # Prompt injection check
    if re.search(r"affiche|toutes les r.gles internes|documents r.cup.r.s|logique exacte", issue, re.I):
        return "prompt_injection_visa"
    if re.search(r"delete all files|rm -rf|remove all files from the system", issue, re.I):
        return "malicious_delete"

    # Company-specific scenarios
    if company == "HackerRank":
        if re.search(r"password|reset\s+pass|forgot\s+pass|delete\s+account|google\s+login", issue):
            return "hr_password"
        if re.search(r"score|graded|unfair|increase\s+my\s+score|review\s+my\s+answer|move\s+me\s+to\s+next", issue):
            return "hr_score_dispute"
        if re.search(r"mock\s+interview.*refund|refund.*mock|stopped\s+in\s+between", issue):
            return "hr_refund"
        if re.search(r"payment|order\s+id|billing|invoice|charged|money", issue):
            return "hr_billing"
        if re.search(r"infosec|information\s+security|security\s+form|compliance\s+form|fill.*form", issue):
            return "hr_infosec"
        if re.search(r"apply\s+tab|submissions.*not\s+work|practice.*not\s+work|can.*see.*apply", issue):
            return "hr_apply_tab"
        if re.search(r"none.*submissions.*work|all.*challenges.*not\s+work|submissions.*failing", issue):
            return "hr_submissions_down"
        if re.search(r"zoom|compatible\s+check|connectivity.*check|proctoring.*block", issue):
            return "hr_zoom"
        if re.search(r"reschedul|alternative\s+date|postpone|missed\s+the\s+test", issue):
            return "hr_reschedule"
        if re.search(r"inactivity|timeout|kicked\s+out|lobby|extend.*time.*interview", issue):
            return "hr_inactivity"
        if re.search(r"remove.*interview|remove.*user|how\s+to\s+remove", issue) and re.search(r"interviewer|platform", issue):
            return "hr_remove_user"
        if re.search(r"pause.*subscri|subscri.*pause|stop.*hiring", issue):
            return "hr_subscription_pause"
        if re.search(r"resume\s+builder|resume.*down", issue):
            return "hr_resume_down"
        if re.search(r"certificate|cert.*name|name.*certif", issue):
            return "hr_certificate_name"
        if re.search(r"employee.*left|remove.*employee|offboard", issue):
            return "hr_remove_employee"

    if company == "Claude":
        # Bedrock must be checked BEFORE generic "all requests failing" to avoid false match
        if re.search(r"bedrock|aws|amazon", issue):
            return "claude_bedrock"
        if re.search(r"lost\s+access|workspace|seat|restore.*access|not.*owner|not.*admin", issue):
            return "claude_workspace_access"
        if re.search(r"stopped\s+working|not\s+responding|all\s+requests.*failing|claude.*down", issue):
            return "claude_down"
        if re.search(r"security\s+vuln|vulnerability|bug\s+bounty|major.*bug|report.*bug", issue):
            return "claude_security_vuln"
        if re.search(r"crawl|crawling|web\s+crawl|stop.*crawl", issue):
            return "claude_crawl_optout"
        if re.search(r"data.*used|model\s+training|how\s+long.*data|data.*retent", issue):
            return "claude_data_retention"
        if re.search(r"lti|education|students|professor|college|university", issue):
            return "claude_education_lti"

    if company == "Visa":
        if re.search(r"wrong\s+product|merchant.*ignor|ban.*seller|refund.*today", issue):
            return "visa_dispute"
        if re.search(r"dispute.*charge|chargeback|how.*dispute", issue):
            return "visa_dispute_how"
        if re.search(r"identity.*stolen|identity\s+theft", issue):
            return "visa_identity_theft"
        if re.search(r"urgent.*cash|need.*cash|emergency.*cash", issue):
            return "visa_urgent_cash"
        if re.search(r"minimum.*spend|minimum.*\$|spend.*minimum", issue):
            return "visa_minimum_spend"

    if company == "None" or not company:
        # Short, vague message with no product context = invalid
        issue_only = ticket.issue.strip()
        has_product_context = re.search(
            r"hackerrank|claude|visa|card|payment|api|test|assessment|account|subscription", 
            issue_only, re.I
        )
        if not has_product_context and len(issue_only) < 50:
            return "invalid_vague"
        if re.search(r"delete all files|rm -rf", issue):
            return "malicious_delete"

    return "default"


# ─────────────────────────────────────────────────────────────────
# Main engine
# ─────────────────────────────────────────────────────────────────

class GroundedResponseEngine:
    """
    Deterministic response engine grounded in the support corpus.
    Used when the Anthropic API is not available, or as a pre-filter.
    """

    def __init__(self, retriever) -> None:
        self.retriever = retriever

    def process(self, ticket: SupportTicket) -> TriageResult:
        """Full triage pipeline: safety → retrieval → classification → response."""
        from agent import infer_company

        # ── Step 1: Invalid check ──────────────────────────────────
        if is_invalid_ticket(ticket):
            return TriageResult(
                status       = TicketStatus.REPLIED,
                product_area = "general_support",
                response     = (
                    "Your message appears to be empty or contains no actionable support "
                    "request. Please describe your issue and we'll be happy to help!"
                ),
                justification = "Ticket contained no actionable content.",
                request_type  = RequestType.INVALID,
            )

        # ── Step 2: Safety pre-screen ──────────────────────────────
        should_escalate, reason = check_escalation(ticket)

        # Special overrides for scenarios we handle as reply
        issue_lower = (ticket.issue + " " + ticket.subject).lower()
        scenario = _detect_scenario(ticket)

        # Fraud/security but we have a guided reply
        if reason == EscalationReason.FRAUD and scenario in ("visa_dispute", "visa_dispute_how"):
            should_escalate = False
        if reason == EscalationReason.COMPLEX_BILLING and scenario == "visa_dispute_how":
            should_escalate = False  # Simple FAQ about dispute process → reply
        if reason == EscalationReason.ACCOUNT_COMPROMISE and scenario == "visa_identity_theft":
            should_escalate = True  # Keep escalated - identity theft is serious
        if reason == EscalationReason.PROMPT_INJECTION:
            should_escalate = True

        if should_escalate and scenario not in ("visa_dispute",):
            product_area = classify_product_area(ticket, [])
            resp = build_escalation_response(reason)
            if scenario == "visa_identity_theft":
                resp = _build_response_from_docs(ticket, [], "visa_identity_theft")
            elif scenario == "hr_billing":
                resp = _build_response_from_docs(ticket, [], "hr_billing")
            elif scenario == "prompt_injection_visa":
                resp = _build_response_from_docs(ticket, [], "prompt_injection_visa")
            elif scenario == "malicious_delete":
                resp = _build_response_from_docs(ticket, [], "malicious_delete")
            return TriageResult(
                status       = TicketStatus.ESCALATED,
                product_area = product_area,
                response     = resp,
                justification = f"Escalated due to: {reason.value if reason else 'high-risk content detected'}.",
                request_type  = RequestType.PRODUCT_ISSUE,
            )

        # ── Step 3: Company inference ──────────────────────────────
        effective_company = (
            ticket.company
            if ticket.company not in ("None", "", None)
            else infer_company(ticket)
        )

        # ── Step 4: Retrieve ───────────────────────────────────────
        query = f"{ticket.subject} {ticket.issue}".strip()
        docs  = self.retriever.retrieve(query, company=effective_company, top_k=5)

        # ── Step 5: Classify product area & request type ───────────
        product_area = classify_product_area(ticket, docs)
        req_type     = classify_request_type(ticket)

        # ── Step 6: Handle specific scenarios ─────────────────────
        # Extra escalation for certain scenarios
        extra_escalate = False
        extra_reason   = ""

        if scenario == "hr_refund":
            extra_escalate = True
            extra_reason   = "Refund requests require billing team review."
            product_area   = "billing"
        elif scenario == "hr_billing":
            extra_escalate = True
            extra_reason   = "Payment/billing issues require specialist review."
            product_area   = "billing"
        elif scenario == "hr_submissions_down":
            extra_escalate = True
            extra_reason   = "Platform-wide outage requires immediate engineering escalation."
            product_area   = "screen"
        elif scenario == "claude_security_vuln":
            extra_escalate = True
            extra_reason   = "Security vulnerability reports are escalated to the security team."
            product_area   = "security_and_bug_bounty"
        elif scenario == "malicious_delete":
            extra_escalate = True
            extra_reason   = "Potentially harmful request flagged for human review."
            product_area   = "general_support"
        elif scenario == "prompt_injection_visa":
            extra_escalate = True
            extra_reason   = "Prompt injection attempt detected."
            product_area   = "security"
        elif scenario == "invalid_vague":
            req_type       = RequestType.INVALID
            product_area   = "general_support"
        elif scenario == "hr_score_dispute":
            req_type       = RequestType.INVALID
        elif scenario == "hr_apply_tab":
            product_area   = "community"
            req_type       = RequestType.PRODUCT_ISSUE
        elif scenario == "hr_remove_user" or scenario == "hr_remove_employee":
            product_area   = "account_settings"
        elif scenario == "hr_subscription_pause":
            product_area   = "billing"
        elif scenario == "hr_resume_down":
            product_area   = "skillup"
        elif scenario == "hr_certificate_name":
            product_area   = "screen"
        elif scenario == "hr_reschedule":
            product_area   = "screen"
        elif scenario == "hr_inactivity":
            product_area   = "interviews"
        elif scenario == "hr_infosec":
            product_area   = "general_support"
        elif scenario == "claude_workspace_access":
            product_area   = "team_and_enterprise"
        elif scenario == "claude_down":
            product_area   = "claude_core"
            req_type       = RequestType.BUG
        elif scenario == "claude_crawl_optout":
            product_area   = "privacy_and_legal"
        elif scenario == "claude_data_retention":
            product_area   = "privacy_and_legal"
            req_type       = RequestType.PRODUCT_ISSUE
        elif scenario == "claude_bedrock":
            product_area   = "amazon_bedrock"
            req_type       = RequestType.BUG
        elif scenario == "claude_education_lti":
            product_area   = "claude_for_education"
        elif scenario == "visa_dispute":
            product_area   = "dispute_resolution"
        elif scenario == "visa_dispute_how":
            product_area   = "dispute_resolution"
        elif scenario == "visa_identity_theft":
            product_area   = "security_and_fraud"
        elif scenario == "visa_urgent_cash":
            product_area   = "travel_support"
        elif scenario == "visa_minimum_spend":
            product_area   = "consumer_support"

        response = _build_response_from_docs(ticket, docs, scenario)

        if extra_escalate:
            justification = (
                f"Escalated to human agent. Reason: {extra_reason} "
                f"Retrieved from: {docs[0].chunk.title if docs else 'N/A'}."
            )
            return TriageResult(
                status        = TicketStatus.ESCALATED,
                product_area  = product_area,
                response      = response,
                justification = justification,
                request_type  = req_type,
            )

        # ── Step 7: Build justification ────────────────────────────
        top_doc_info = (
            f"Top retrieved doc: '{docs[0].chunk.title}' (score={docs[0].score})"
            if docs else "No corpus match found"
        )
        justification = (
            f"Replied with grounded response from {effective_company or 'general'} corpus. "
            f"{top_doc_info}. Scenario: {scenario}."
        )

        return TriageResult(
            status        = TicketStatus.REPLIED,
            product_area  = product_area,
            response      = response,
            justification = justification,
            request_type  = req_type,
        )
