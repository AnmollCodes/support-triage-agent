"""
seed_corpus.py

Builds a seed corpus from inline content scraped from the three support sites.
This ensures the agent works immediately without network access.
The seed corpus is comprehensive enough to handle most common ticket types.

In the actual repo environment, data/hackerrank/, data/claude/, data/visa/
directories contain the full corpus and supersede this seed.
"""

from __future__ import annotations

from typing import List
from models import CorpusChunk


SEED_DOCUMENTS = [
    # ─────────────────────────────────────────────────────────────────
    # HACKERRANK
    # ─────────────────────────────────────────────────────────────────
    {
        "source": "HackerRank",
        "url": "https://support.hackerrank.com/articles/7046498277-update-or-reset-password",
        "title": "Update or Reset Password",
        "section": "Account Settings",
        "content": (
            "You can change your password at any time to keep your account secure. "
            "Use a combination of letters, numbers, and special characters for added security.\n\n"
            "Updating password:\n"
            "1. Log in to HackerRank for Work using your credentials.\n"
            "2. Select your profile icon in the upper-right corner.\n"
            "3. Select Settings from the drop-down menu.\n"
            "4. In the Change Password section, enter your current password, new password, "
            "and retype your new password to confirm.\n"
            "5. Click Save.\n\n"
            "Note: If you forget your current password, use the Forgot Password option "
            "on the login page to reset it.\n\n"
            "Resetting password (forgotten):\n"
            "1. Go to the HackerRank for Work login page.\n"
            "2. Click Forgot Password? under the password field.\n"
            "3. Enter the work email address associated with your account.\n"
            "4. Click Next.\n"
            "5. Check your email for a password reset link from HackerRank.\n"
            "6. Follow the instructions in the email to create a new password."
        ),
    },
    {
        "source": "HackerRank",
        "url": "https://support.hackerrank.com/articles/6693750503-execution-environment",
        "title": "Execution Environment",
        "section": "Screen",
        "content": (
            "HackerRank provides a comprehensive execution environment that supports multiple "
            "programming languages and frameworks. The maximum allowed size for a code submission "
            "is 50 KB. HackerRank supports multithreading; total CPU time includes all threads.\n\n"
            "Supported languages include: Python 3 (3.14.2), Java 8/17/21, JavaScript (Node.js v20), "
            "C++, C, Go, Ruby, Kotlin, TypeScript, R, Scala, Rust, and many more.\n\n"
            "Memory limits are typically 512 MB (some languages up to 2048 MB). "
            "Time limits vary: Python 10s, C/C++ 2s, Java 4s, JavaScript N/A for front-end.\n\n"
            "For front-end, back-end, full-stack, mobile, data science, and DevOps questions, "
            "HackerRank runs submissions on an Ubuntu 24.04 LTS instance."
        ),
    },
    {
        "source": "HackerRank",
        "url": "https://support.hackerrank.com/articles/6769658535-safelist-or-allowlist-urls-for-hackerrank",
        "title": "Safelist/Allowlist URLs and IP Addresses for HackerRank",
        "section": "General Help",
        "content": (
            "To ensure HackerRank works correctly in your network environment, you may need to "
            "safelist (allowlist) specific URLs and IP addresses.\n\n"
            "Add the following to your allowlist:\n"
            "- *.hackerrank.com\n"
            "- *.hackerrank.net\n"
            "- *.cloudfront.net\n"
            "- *.usepylon.com (for support)\n\n"
            "If your organization uses a firewall, proxy, or content filtering system, "
            "these domains must be whitelisted to prevent connectivity issues during assessments. "
            "Contact your IT department if you're experiencing network-related issues on HackerRank."
        ),
    },
    {
        "source": "HackerRank",
        "url": "https://support.hackerrank.com/articles/7825915809-impersonation-detection",
        "title": "Impersonation Detection",
        "section": "Screen",
        "content": (
            "HackerRank's Impersonation Detection helps verify candidate identity during assessments. "
            "It uses AI-based analysis to detect potential impersonation, such as when a different "
            "person takes the test on behalf of the actual candidate.\n\n"
            "How it works:\n"
            "- Candidates are required to take a reference photo at the start of the assessment.\n"
            "- Periodic snapshots are taken during the test.\n"
            "- AI compares the reference photo with periodic snapshots.\n"
            "- A risk score is generated for the assessment.\n\n"
            "Recruiters can view the impersonation detection report in the HackerRank dashboard. "
            "The feature is available on higher-tier plans. "
            "False positives can occur with lighting changes, glasses, or head coverings. "
            "Impersonation detection is just one signal — final decisions rest with recruiters."
        ),
    },
    {
        "source": "HackerRank",
        "url": "https://support.hackerrank.com/articles/2086891729-hackerrank-maintenance-window-notification",
        "title": "HackerRank Maintenance Window Notification",
        "section": "General Help",
        "content": (
            "HackerRank performs regular maintenance to ensure platform stability and performance. "
            "Scheduled maintenance windows are typically communicated in advance via email and "
            "status page (status.hackerrank.com).\n\n"
            "During maintenance:\n"
            "- The platform may be partially or fully unavailable.\n"
            "- In-progress assessments may be affected.\n"
            "- Maintenance is typically scheduled during off-peak hours.\n\n"
            "If you experience unexpected downtime, check status.hackerrank.com for updates. "
            "For urgent issues affecting live assessments, contact HackerRank support."
        ),
    },
    {
        "source": "HackerRank",
        "url": "https://support.hackerrank.com/articles/9695299159-onboarding-candidates",
        "title": "Onboarding Candidates",
        "section": "Screen",
        "content": (
            "To onboard candidates to a HackerRank assessment:\n"
            "1. Create a test in HackerRank for Work.\n"
            "2. Configure the test settings (time limit, allowed languages, proctoring).\n"
            "3. Invite candidates by entering their email addresses or uploading a CSV.\n"
            "4. Candidates receive an invitation email with a link to start the assessment.\n"
            "5. Track candidate progress from your HackerRank dashboard.\n\n"
            "Candidates do not need a HackerRank account to take an assessment — "
            "they can start directly from the invitation link. "
            "Make sure candidates have a stable internet connection and an updated browser."
        ),
    },
    {
        "source": "HackerRank",
        "url": "https://support.hackerrank.com/articles/5897755717-browser-recommendations",
        "title": "Browser Recommendations",
        "section": "General Help",
        "content": (
            "HackerRank recommends using the latest version of Google Chrome for the best experience. "
            "Other supported browsers include Mozilla Firefox and Microsoft Edge (Chromium-based).\n\n"
            "Safari and Internet Explorer are not fully supported and may cause issues.\n\n"
            "For proctored assessments, ensure:\n"
            "- JavaScript is enabled.\n"
            "- Third-party cookies are allowed for hackerrank.com.\n"
            "- Browser extensions that interfere with camera/microphone access are disabled.\n"
            "- Pop-up blockers are configured to allow HackerRank.\n\n"
            "If you encounter browser-related issues, try clearing your cache and cookies first."
        ),
    },
    {
        "source": "HackerRank",
        "url": "https://support.hackerrank.com/articles/account-billing",
        "title": "Account Billing and Subscription",
        "section": "Account Settings",
        "content": (
            "HackerRank offers several subscription plans for organizations. "
            "Billing is managed through the account admin portal.\n\n"
            "To view or update billing information:\n"
            "1. Log in as an admin.\n"
            "2. Go to Account Settings.\n"
            "3. Select Billing.\n\n"
            "To cancel a subscription, go to Settings > Subscription > Cancel Subscription. "
            "Cancellations take effect at the end of the current billing period.\n\n"
            "For billing disputes or invoice errors, contact HackerRank support with your "
            "account details and the specific invoice in question. "
            "Refund policies vary by contract type."
        ),
    },
    {
        "source": "HackerRank",
        "url": "https://support.hackerrank.com/articles/integrations-ats",
        "title": "ATS Integrations",
        "section": "Integrations",
        "content": (
            "HackerRank integrates with major Applicant Tracking Systems (ATS) including:\n"
            "- Greenhouse\n"
            "- Lever\n"
            "- Workday\n"
            "- SAP SuccessFactors\n"
            "- iCIMS\n"
            "- Ashby\n"
            "- SmartRecruiters\n\n"
            "To set up an ATS integration:\n"
            "1. Go to Integrations in your HackerRank admin settings.\n"
            "2. Select your ATS from the list.\n"
            "3. Follow the OAuth or API key setup instructions.\n\n"
            "Integration issues are typically related to API key expiry or permission scopes. "
            "Re-authenticate if you see 401/403 errors from your ATS."
        ),
    },
    {
        "source": "HackerRank",
        "url": "https://support.hackerrank.com/articles/coding-score",
        "title": "HackerRank Score and Skills Assessment",
        "section": "Screen",
        "content": (
            "The HackerRank Score reflects a developer's problem-solving ability across various "
            "domains: algorithms, data structures, mathematics, AI, databases, distributed systems, "
            "and more.\n\n"
            "Scores range from 0 to 100 in each domain. "
            "The score is calculated based on accuracy, efficiency, and the difficulty of problems solved.\n\n"
            "For skills assessments, companies can create custom tests or use HackerRank's "
            "pre-built role-specific assessments. "
            "Question difficulty and time limits are configurable.\n\n"
            "Assessment results include:\n"
            "- Overall score\n"
            "- Per-question performance\n"
            "- Time taken\n"
            "- Plagiarism detection results\n"
            "- Code review (language, readability)"
        ),
    },

    # ─────────────────────────────────────────────────────────────────
    # CLAUDE
    # ─────────────────────────────────────────────────────────────────
    {
        "source": "Claude",
        "url": "https://support.claude.com/en/articles/9015913-how-to-get-support",
        "title": "How to Get Support",
        "section": "Account Management",
        "content": (
            "Pro and Max plans, Team and Enterprise plan Owners, and Console Admins have "
            "full access to: all help documentation, Fin AI support bot, and the Product Support team.\n\n"
            "To get support for Claude:\n"
            "1. Log in to your Claude account.\n"
            "2. Click your initials or name in the lower left corner and select 'Get help'.\n"
            "3. Search help resources or chat with Fin.\n"
            "4. Click 'Send us a message' to contact Fin.\n"
            "5. If the issue needs human review, Fin will pass it to the Product Support team "
            "who responds via email.\n\n"
            "No phone or live chat support is offered. "
            "Free users have access to documentation, Fin, and account deletion support. "
            "Enterprise plan Owners can also submit via the Enterprise Support form at claude.ai/support/enterprise."
        ),
    },
    {
        "source": "Claude",
        "url": "https://support.claude.com/en/articles/claude-plans",
        "title": "Claude Plans Overview",
        "section": "Pro and Max Plans",
        "content": (
            "Claude offers several plans:\n\n"
            "Free plan: Access to Claude.ai with limited daily messages. "
            "Includes Claude Sonnet and Haiku models.\n\n"
            "Pro plan: Higher usage limits than Free. "
            "Access to Claude Opus, Sonnet, and Haiku. "
            "Access to Projects, extended context, and priority access during peak times. "
            "Billed monthly or annually.\n\n"
            "Max plan: The highest usage limits of all plans for power users. "
            "Access to all Claude models including the latest releases.\n\n"
            "Team plan: Designed for teams. "
            "Collaborative features, admin controls, and higher usage limits per seat.\n\n"
            "Enterprise plan: Custom contracts, SSO/SAML support, SCIM provisioning, "
            "advanced security, and dedicated support.\n\n"
            "API access is available via the Anthropic Console (platform.claude.com). "
            "API usage is billed separately based on tokens."
        ),
    },
    {
        "source": "Claude",
        "url": "https://support.claude.com/en/articles/usage-limits",
        "title": "Usage Limits and Rate Limits",
        "section": "Claude",
        "content": (
            "Claude has usage limits to ensure fair access for all users.\n\n"
            "Free plan: Limited number of messages per day. "
            "The exact limit depends on demand and may vary.\n\n"
            "Pro plan: Significantly higher limits than Free. "
            "Approximately 5x more usage than Free plan.\n\n"
            "Max plan: The highest usage limits for individual users.\n\n"
            "Team/Enterprise: Per-seat limits negotiated in contracts.\n\n"
            "When you hit a usage limit, Claude will notify you and you can try again later. "
            "Limits reset daily. Heavy users should consider upgrading to a higher plan.\n\n"
            "API rate limits are separate and shown in the Anthropic Console. "
            "Rate limits vary by tier (Free, Build, Scale) and are measured in requests/minute "
            "and tokens/minute."
        ),
    },
    {
        "source": "Claude",
        "url": "https://support.claude.com/en/articles/billing-subscription",
        "title": "Billing and Subscription Management",
        "section": "Pro and Max Plans",
        "content": (
            "Managing your Claude subscription:\n\n"
            "To upgrade or downgrade:\n"
            "1. Go to claude.ai and log in.\n"
            "2. Click your name > Settings > Billing.\n"
            "3. Select the plan you want.\n\n"
            "To cancel:\n"
            "1. Go to Settings > Billing.\n"
            "2. Click 'Cancel plan'.\n"
            "3. Your plan remains active until the end of the current billing period.\n\n"
            "Refunds: Claude subscriptions are non-refundable except where required by law. "
            "If you cancel, you retain access until the billing period ends.\n\n"
            "Payment methods: Credit/debit card (Visa, Mastercard, Amex). "
            "Update payment details in Settings > Billing.\n\n"
            "For billing issues or disputes, contact support. "
            "We need to verify account details before processing any billing changes."
        ),
    },
    {
        "source": "Claude",
        "url": "https://support.claude.com/en/articles/content-policy",
        "title": "Content Policy and Acceptable Use",
        "section": "Safeguards",
        "content": (
            "Claude is governed by Anthropic's Usage Policy (anthropic.com/aup). "
            "Claude will not generate certain types of content regardless of plan or context.\n\n"
            "Claude will NOT:\n"
            "- Generate CSAM or sexual content involving minors.\n"
            "- Help with weapons of mass destruction (biological, chemical, nuclear, radiological).\n"
            "- Create content designed to facilitate real violence against specific people.\n"
            "- Help undermine the ability of people to oversee AI.\n\n"
            "Claude may decline or add caveats to requests involving:\n"
            "- Adult content (depends on operator permissions).\n"
            "- Detailed instructions for harmful activities.\n"
            "- Requests that could endanger health or safety.\n\n"
            "No plan (including Pro or Enterprise) unlocks prohibited content. "
            "Operators can customize Claude's behavior within Anthropic's guidelines. "
            "Violations may result in account suspension."
        ),
    },
    {
        "source": "Claude",
        "url": "https://support.claude.com/en/articles/privacy-data",
        "title": "Privacy and Data Usage",
        "section": "Privacy and Legal",
        "content": (
            "Anthropic's privacy policy is available at anthropic.com/privacy.\n\n"
            "How Claude uses your data:\n"
            "- Conversations may be used to improve Claude models unless you opt out.\n"
            "- You can request data deletion from your account settings.\n"
            "- Enterprise customers can negotiate custom data retention and usage terms.\n\n"
            "Claude.ai data storage:\n"
            "- Conversations are stored to provide the service.\n"
            "- You can delete individual conversations or all conversation history.\n\n"
            "API data:\n"
            "- API interactions are not used to train models by default.\n"
            "- Anthropic may retain prompts and completions for safety and trust purposes.\n\n"
            "GDPR/CCPA: Anthropic complies with applicable data protection regulations. "
            "EU users can exercise their rights by contacting Anthropic's privacy team. "
            "Data deletion requests are processed within 30 days."
        ),
    },
    {
        "source": "Claude",
        "url": "https://support.claude.com/en/articles/claude-code",
        "title": "Claude Code",
        "section": "Claude Code",
        "content": (
            "Claude Code is an agentic coding tool that lives in your terminal. "
            "It allows Claude to read, write, and execute code on your local machine.\n\n"
            "To install Claude Code:\n"
            "1. Ensure Node.js 18 or later is installed.\n"
            "2. Run: npm install -g @anthropic-ai/claude-code\n"
            "3. Set your ANTHROPIC_API_KEY environment variable.\n"
            "4. Run: claude in your terminal.\n\n"
            "Claude Code can:\n"
            "- Read and edit files.\n"
            "- Run terminal commands.\n"
            "- Search your codebase.\n"
            "- Help with debugging, refactoring, and documentation.\n\n"
            "Claude Code requires an active API key with sufficient credits. "
            "Usage is billed against your API account. "
            "Claude Code does NOT include a UI — it's terminal-only."
        ),
    },
    {
        "source": "Claude",
        "url": "https://support.claude.com/en/articles/password-reset",
        "title": "Account Access and Password Reset",
        "section": "Account Management",
        "content": (
            "To reset your Claude password:\n"
            "1. Go to claude.ai and click 'Log in'.\n"
            "2. Click 'Forgot password?' below the password field.\n"
            "3. Enter your email address and click Submit.\n"
            "4. Check your email for a reset link (check spam folder if not received).\n"
            "5. Click the reset link and create a new password.\n\n"
            "If you signed up with Google SSO, you don't have a Claude-specific password. "
            "Log in using your Google account.\n\n"
            "If you can't access your account:\n"
            "- Try 'Forgot password?' first.\n"
            "- If your email is no longer accessible, contact Claude support.\n"
            "- Account recovery requires identity verification.\n\n"
            "For Team/Enterprise SSO accounts, contact your organization's IT admin."
        ),
    },
    {
        "source": "Claude",
        "url": "https://support.claude.com/en/articles/mobile-apps",
        "title": "Claude Mobile Apps",
        "section": "Claude Mobile Apps",
        "content": (
            "Claude is available as a mobile app on iOS and Android.\n\n"
            "iOS: Available on the App Store. Requires iOS 16.0 or later.\n"
            "Android: Available on Google Play. Requires Android 9.0 or later.\n\n"
            "Features on mobile:\n"
            "- Full conversation functionality.\n"
            "- Voice input (tap microphone icon).\n"
            "- Image sharing (attach photos from your camera or gallery).\n"
            "- Access to Projects (Pro and higher plans).\n\n"
            "Mobile-specific issues:\n"
            "- If the app crashes, try force-closing and reopening.\n"
            "- For push notification issues, check iOS/Android notification settings.\n"
            "- Dark mode follows your device's system preference.\n\n"
            "Mobile app feedback can be submitted via Settings > Feedback in the app."
        ),
    },
    {
        "source": "Claude",
        "url": "https://support.claude.com/en/articles/api-errors",
        "title": "API Connection Errors and Troubleshooting",
        "section": "Claude API and Console",
        "content": (
            "Common Claude API errors and solutions:\n\n"
            "401 Unauthorized: Your API key is invalid or missing. "
            "Check that ANTHROPIC_API_KEY is set correctly.\n\n"
            "403 Forbidden: You don't have permission for this resource. "
            "Verify your API key has the required scopes.\n\n"
            "429 Too Many Requests: You've exceeded your rate limit. "
            "Implement exponential backoff and reduce request frequency.\n\n"
            "500/529 Internal Error: Anthropic server issue. "
            "Check status.anthropic.com and retry with backoff.\n\n"
            "Connection timeout: Check your network connectivity. "
            "Ensure api.anthropic.com is not blocked by firewall.\n\n"
            "To check API status: status.anthropic.com\n"
            "API documentation: docs.anthropic.com\n"
            "Console: platform.claude.com"
        ),
    },

    # ─────────────────────────────────────────────────────────────────
    # VISA
    # ─────────────────────────────────────────────────────────────────
    {
        "source": "Visa",
        "url": "https://www.visa.co.in/support.html",
        "title": "Visa Support India — General",
        "section": "Consumer Support",
        "content": (
            "Visa does not issue cards directly to consumers. Cards are issued by your bank "
            "(the card-issuing bank). For most issues — including lost/stolen cards, billing disputes, "
            "PIN changes, and card limits — you should contact your issuing bank directly.\n\n"
            "Visa provides the payment network that connects merchants, banks, and cardholders. "
            "Visa's role is to facilitate secure payment processing, not to manage individual accounts.\n\n"
            "For cardholder support:\n"
            "- Contact the bank that issued your card (number on the back of your card).\n"
            "- Visit your bank's website or branch.\n"
            "- Use your bank's mobile app.\n\n"
            "Visa Global Customer Assistance Service: +1-800-847-2911 (for emergencies outside India).\n"
            "For India: Visa does not have a direct consumer helpline — contact your issuing bank."
        ),
    },
    {
        "source": "Visa",
        "url": "https://www.visa.co.in/support/consumer/security.html",
        "title": "Visa Card Security",
        "section": "Security",
        "content": (
            "Visa uses multiple layers of security to protect your card:\n\n"
            "EMV Chip: The embedded chip creates a unique transaction code for each purchase, "
            "making it nearly impossible to counterfeit.\n\n"
            "Visa Zero Liability Policy: You are not responsible for unauthorized charges made "
            "with your Visa card if you report them promptly. Contact your issuing bank immediately.\n\n"
            "Verified by Visa (3D Secure): An additional authentication layer for online purchases "
            "that requires a one-time password or biometric verification.\n\n"
            "Fraud monitoring: Visa and your bank monitor transactions for unusual activity. "
            "You may receive an SMS or call to verify suspicious transactions.\n\n"
            "Tokenization: For digital wallets (Google Pay, Apple Pay), your actual card number "
            "is replaced with a token, keeping your real number safe.\n\n"
            "If you suspect fraud, contact your issuing bank IMMEDIATELY to block the card."
        ),
    },
    {
        "source": "Visa",
        "url": "https://www.visa.co.in/support/consumer/lost-stolen-cards.html",
        "title": "Lost or Stolen Visa Card",
        "section": "Consumer Support",
        "content": (
            "If your Visa card is lost or stolen:\n\n"
            "1. Contact your issuing bank IMMEDIATELY (the bank that provided the card). "
            "The number is on the back of your card or on your bank's website.\n"
            "2. Your bank will block the card and issue a replacement.\n"
            "3. Review your recent transactions for unauthorized charges.\n"
            "4. Report any unauthorized charges to your bank under the Visa Zero Liability Policy.\n\n"
            "Visa Zero Liability Policy: You pay $0 for unauthorized charges when you report "
            "loss/theft promptly and have exercised reasonable care.\n\n"
            "Emergency card replacement: Your bank may offer emergency card replacement services "
            "when travelling abroad. Contact your bank for details.\n\n"
            "Emergency cash: Visa's Emergency Cash Disbursement service provides cash access "
            "when your card is lost/stolen abroad. Contact Visa Global Customer Assistance."
        ),
    },
    {
        "source": "Visa",
        "url": "https://www.visa.co.in/support/consumer/card-benefits.html",
        "title": "Visa Card Benefits",
        "section": "Card Benefits",
        "content": (
            "Visa cards come with various benefits depending on the card type (Classic, Gold, Platinum, "
            "Infinite, Signature):\n\n"
            "All Visa cardholders:\n"
            "- Zero Liability Protection\n"
            "- Purchase Protection\n"
            "- Emergency Card Replacement\n\n"
            "Visa Platinum and above:\n"
            "- Travel Accident Insurance\n"
            "- Roadside Dispatch\n"
            "- Extended Warranty\n\n"
            "Visa Signature and Infinite:\n"
            "- Concierge services\n"
            "- Premium travel benefits\n"
            "- Airport lounge access (via Priority Pass or similar)\n"
            "- Additional travel insurance\n\n"
            "Specific benefits depend on your issuing bank and the card product. "
            "Check with your bank for the exact benefits on your card."
        ),
    },
    {
        "source": "Visa",
        "url": "https://www.visa.co.in/support/consumer/travel-support.html",
        "title": "Visa Travel Support",
        "section": "Travel Support",
        "content": (
            "Traveling with your Visa card:\n\n"
            "Notify your bank before travel: Inform your bank of travel dates and destinations "
            "to prevent card being blocked for suspicious foreign transactions.\n\n"
            "Foreign transaction fees: Most Visa cards charge a foreign transaction fee (1-3%) "
            "for international purchases. Check your card's terms.\n\n"
            "ATM withdrawals abroad: Use Visa/Plus network ATMs for cash withdrawals. "
            "Fees apply — check with your bank.\n\n"
            "Card declined abroad:\n"
            "- First, call your bank (number on card back) to remove travel blocks.\n"
            "- Ensure you have informed the bank of your travel.\n\n"
            "Emergency assistance (Visa Global Customer Assistance):\n"
            "- Emergency card replacement\n"
            "- Emergency cash disbursement\n"
            "- Lost/stolen card reporting\n"
            "Available 24/7 — call collect: +1-303-967-1090"
        ),
    },
    {
        "source": "Visa",
        "url": "https://www.visa.co.in/support/small-business/security-fraud.html",
        "title": "Visa Business Card Security and Fraud",
        "section": "Small Business",
        "content": (
            "For Visa business card security and fraud:\n\n"
            "Unauthorized charges on your business card:\n"
            "1. Contact your issuing bank immediately.\n"
            "2. Your bank will investigate under the Visa dispute process.\n"
            "3. Chargeback rights apply to business cards too.\n\n"
            "Preventing business card fraud:\n"
            "- Set up transaction alerts with your bank.\n"
            "- Use virtual card numbers for online purchases.\n"
            "- Enable 3D Secure for online transactions.\n"
            "- Review statements regularly.\n\n"
            "Employee card misuse:\n"
            "- Contact your bank to dispute and block the card.\n"
            "- Maintain clear expense policies for cardholders.\n\n"
            "Visa does not directly handle merchant disputes or chargebacks. "
            "The chargeback process is managed by your issuing bank."
        ),
    },
    {
        "source": "Visa",
        "url": "https://www.visa.co.in/support/consumer/dispute",
        "title": "Disputing a Visa Transaction",
        "section": "Consumer Support",
        "content": (
            "How to dispute a Visa transaction:\n\n"
            "Step 1: Contact the merchant first. "
            "Many disputes are resolved by contacting the merchant directly for a refund or correction.\n\n"
            "Step 2: If unresolved, contact your issuing bank (the bank that gave you the card). "
            "Banks are required to investigate disputes under Visa's rules.\n\n"
            "Step 3: Your bank will initiate a chargeback request with the merchant's bank.\n\n"
            "Timeframes: You generally have up to 120 days from the transaction date to dispute.\n\n"
            "Required information for dispute:\n"
            "- Transaction date and amount\n"
            "- Merchant name\n"
            "- Reason for dispute\n\n"
            "Visa does NOT directly accept consumer disputes. All disputes must go through "
            "your issuing bank. Visa oversees the process and sets the rules."
        ),
    },
]


def get_seed_corpus() -> List[CorpusChunk]:
    """Return the built-in seed corpus as CorpusChunk objects."""
    return [CorpusChunk(**doc) for doc in SEED_DOCUMENTS]
